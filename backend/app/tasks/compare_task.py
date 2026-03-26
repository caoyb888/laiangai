"""
比对任务主流水线
流程：字符级比对 → LLM 语义分析（全量 modify 差异） → 风险识别
注：向量相似度过滤（SemanticDiffEngine.analyze_diff_pairs）已移除。
    实测 BGE-M3 对同类条款余弦相似度普遍 > 0.94，金额/违约金等关键数字
    变更无法被阈值区分，会造成漏判。当前策略：字符级标记的所有 modify
    差异直接送 LLM，由模型判断实质性。
    SemanticDiffEngine.search_similar_paragraphs 保留用于段落移位检测（规划中）。
见 CLAUDE.md §七 比对核心算法规范
"""
import json
import uuid
from datetime import datetime
from app.core.db import AsyncSessionLocal
from app.repositories.compare_repo import CompareRepository
from app.repositories.document_repo import DocumentRepository
from app.services.compare.char_diff import CharDiffEngine
from app.services.compare.risk_detector import RiskDetector
from app.services.desensitizer import get_desensitizer, DesensitizedChunk
from app.services.llm_client import LLMClient
from app.models.compare_task import TaskStatus, DiffLevel
import structlog

logger = structlog.get_logger()


async def run_compare_pipeline(task_id: str, user_id: str) -> None:
    """
    完整比对流水线
    """
    async with AsyncSessionLocal() as db:
        repo = CompareRepository(db)
        doc_repo = DocumentRepository(db)

        try:
            await repo.update_task_status(task_id, TaskStatus.PROCESSING, progress=5)
            await db.commit()

            # ─── Step 1: 加载两篇文档解析内容 ────────────────────────────────
            task = await repo.get_task(task_id)
            content_a = await doc_repo.get_content(task.doc_a_id)
            content_b = await doc_repo.get_content(task.doc_b_id)

            parsed_a = json.loads(content_a.structured_json)
            parsed_b = json.loads(content_b.structured_json)

            paras_a = [b["text"] for b in parsed_a.get("blocks", [])
                       if b.get("block_type") in ("paragraph", "heading", "list_item")]
            paras_b = [b["text"] for b in parsed_b.get("blocks", [])
                       if b.get("block_type") in ("paragraph", "heading", "list_item")]

            await repo.update_task_status(task_id, TaskStatus.PROCESSING, progress=15)
            await db.commit()

            # ─── Step 2: 字符级比对 ────────────────────────────────────────
            char_engine = CharDiffEngine()
            diff_pairs = char_engine.diff_paragraphs(paras_a, paras_b)
            # 过滤掉完全相同的段落
            changed_pairs = [p for p in diff_pairs if p.get("diff_type") != "equal"]

            await repo.update_task_status(task_id, TaskStatus.PROCESSING, progress=40)
            await db.commit()

            # ─── Step 3: LLM 语义分析（字符级所有 modify 差异全量送入）──────
            # 向量过滤已移除（见文件头注释）
            # 见 CLAUDE.md §七：禁止对全文发送 LLM 分析（此处仅发送字符级差异块）
            real_diffs = changed_pairs
            desensitizer = get_desensitizer()
            risk_detector = RiskDetector()

            llm_chunks: list[DesensitizedChunk] = []
            for pair in real_diffs:
                combined = "\n---\n".join(filter(None, [
                    f"原文：{pair.get('doc_a_text', '')}",
                    f"修改后：{pair.get('doc_b_text', '')}",
                ]))
                llm_chunks.append(desensitizer.desensitize(combined))

            llm_results = await LLMClient.analyze_diff(
                llm_chunks, task_id=task_id, user_id=user_id
            )

            await repo.update_task_status(task_id, TaskStatus.PROCESSING, progress=85)
            await db.commit()

            # ─── Step 5: 风险识别 & 写入数据库 ─────────────────────────────
            diff_items_to_save = []
            critical_count = 0

            for i, pair in enumerate(real_diffs):
                llm_result = llm_results[i] if i < len(llm_results) else {}
                pair.update(llm_result)

                final_level, risk_keywords = risk_detector.detect(pair)
                if final_level == DiffLevel.CRITICAL:
                    critical_count += 1

                diff_items_to_save.append({
                    "id": str(uuid.uuid4()),
                    "task_id": task_id,
                    "seq_no": pair.get("seq_no", i),
                    "diff_type": pair.get("diff_type", "modify"),
                    "diff_level": final_level.value,
                    "doc_a_text": pair.get("doc_a_text"),
                    "doc_b_text": pair.get("doc_b_text"),
                    "semantic_desc": pair.get("semantic_desc", ""),
                    "risk_keywords": ",".join(risk_keywords) if risk_keywords else "",
                })

            await repo.batch_save_diffs(diff_items_to_save)
            await repo.finish_task(
                task_id,
                total_diffs=len(diff_items_to_save),
                critical_diffs=critical_count,
            )
            await db.commit()

            logger.info("比对完成",
                        task_id=task_id,
                        total=len(diff_items_to_save),
                        critical=critical_count)

        except Exception as e:
            await repo.update_task_status(task_id, TaskStatus.FAILED, error_msg=str(e))
            await db.commit()
            logger.error("比对任务失败", task_id=task_id, error=str(e))
