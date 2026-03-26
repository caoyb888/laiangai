"""
语义向量工具：BGE-M3
- analyze_diff_pairs：计算余弦相似度（已从主流水线移除，保留供调试/离线分析使用）
  原因：BGE-M3 对同类条款相似度普遍 > 0.94，无法用阈值区分关键数字变更，
        改为全量 modify 差异送 LLM 判断。
- search_similar_paragraphs：段落移位检测（向量检索），规划用于 move 类型差异识别
见 CLAUDE.md §七 比对算法规范
"""
import numpy as np
import structlog
from pymilvus import Collection

from app.config import get_settings
from app.services.vectorizer import VectorizerService

logger = structlog.get_logger()
settings = get_settings()


class SemanticDiffEngine:

    def __init__(self) -> None:
        self.vectorizer = VectorizerService()

    def cosine_similarity(self, vec_a: list[float], vec_b: list[float]) -> float:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def analyze_diff_pairs(
        self,
        diff_pairs: list[dict],
        threshold: float | None = None,
    ) -> list[dict]:
        """
        对字符级比对结果的差异对做语义分析
        :param diff_pairs: 来自 CharDiffEngine.diff_paragraphs 的结果列表
        :param threshold: 相似度阈值，None 时用配置值
        :return: 增加了 semantic_similarity 字段的结果列表
        """
        threshold = threshold or settings.semantic_similarity_threshold

        # 过滤需要语义分析的对（modify 类型且有双侧文本）
        pairs_to_analyze = [
            p for p in diff_pairs
            if p.get("diff_type") == "modify"
            and p.get("doc_a_text") and p.get("doc_b_text")
        ]

        if not pairs_to_analyze:
            return diff_pairs

        # 批量向量化（减少模型调用次数）
        texts_a = [p["doc_a_text"] for p in pairs_to_analyze]
        texts_b = [p["doc_b_text"] for p in pairs_to_analyze]
        try:
            vecs_a = self.vectorizer.encode(texts_a)
            vecs_b = self.vectorizer.encode(texts_b)
        except Exception as e:
            logger.warning("BGE-M3 向量化失败，跳过语义去重，保留所有字符级差异", error=str(e))
            return diff_pairs

        # 计算相似度并回写
        pair_idx = 0
        for item in diff_pairs:
            if (item.get("diff_type") == "modify"
                    and item.get("doc_a_text") and item.get("doc_b_text")):
                sim = self.cosine_similarity(vecs_a[pair_idx], vecs_b[pair_idx])
                item["semantic_similarity"] = round(sim, 4)
                # 语义高度相似（>= threshold）降级为格式差异
                if sim >= threshold:
                    item["semantic_is_equivalent"] = True
                pair_idx += 1

        return diff_pairs

    def search_similar_paragraphs(
        self,
        query_text: str,
        doc_id: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        在指定文档的向量库中搜索相似段落
        用于检测段落移位（move 类型差异）
        """
        from app.services.vectorizer import get_milvus_collection

        vec = self.vectorizer.encode([query_text])[0]
        collection: Collection = get_milvus_collection()

        results = collection.search(
            data=[vec],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            expr=f'doc_id == "{doc_id}"',
            output_fields=["block_index", "section_path", "chunk_text"],
        )

        hits = []
        for hit in results[0]:
            hits.append({
                "block_index": hit.entity.get("block_index"),
                "section_path": hit.entity.get("section_path"),
                "chunk_text": hit.entity.get("chunk_text"),
                "score": round(hit.score, 4),
            })
        return hits
