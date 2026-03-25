"""
比对任务主流水线
三层比对顺序：字符级 → 语义级（向量） → LLM 语义分析 → 风险识别
见 CLAUDE.md §七 比对核心算法规范
"""
import json
import uuid
from datetime import datetime
from app.core.db import AsyncSessionLocal
from app.repositories.compare_repo import CompareRepository
from app.repositories.document_repo import DocumentRepository
from app.services.compare.char_diff import CharDiffEngine
from app.services.compare.semantic_diff import SemanticDiffEngine
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

            # ─── Step 2: 字符级比对 ────────────────────────────────────────
            char_engine = CharDiffEngine()
            diff_pairs = char_engine.diff_paragraphs(paras_a, paras_b)
            # 过滤掉完全相同的段落
            changed_pairs = [p for p in diff_pairs if p.get("diff_type") != "equal"]

            await repo.update_task_status(task_id, TaskStatus.PROCESSING, progress=35)

            # ─── Step 3: 语义级比对（向量） ────────────────────────────────
            semantic_engine = SemanticDiffEngine()
            changed_pairs = semantic_engine.analyze_diff_pairs(changed_pairs)
            # 过滤语义等价的差异（格式变动）
            real_diffs = [
                p for p in changed_pairs
                if not p.get("semantic_is_equivalent", False)
            ]

            await repo.update_task_status(task_id, TaskStatus.PROCESSING, progress=55)

            # ─── Step 4: LLM 语义分析（仅对已标记差异块）───────────────────
            # 见 CLAUDE.md §七：禁止对全文发送 LLM 分析
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

            await repo.update_task_status(task_id, TaskStatus.PROCESSING, progress=80)

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
