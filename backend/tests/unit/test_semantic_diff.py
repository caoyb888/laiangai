"""
语义级比对引擎单元测试
见 CLAUDE.md §8.1：services/compare/ 覆盖率 ≥ 90%
"""
import math
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.compare.semantic_diff import SemanticDiffEngine


# ──────────────────────── Fixtures ────────────────────────────


def _make_engine(vec_map: dict[str, list[float]] | None = None) -> SemanticDiffEngine:
    """构造 SemanticDiffEngine，Mock 掉 VectorizerService.encode。
    vec_map: text -> vector，未覆盖的文本返回零向量。
    """
    engine = SemanticDiffEngine.__new__(SemanticDiffEngine)

    dim = 1024

    def _encode(texts: list[str]) -> list[list[float]]:
        result = []
        for t in texts:
            if vec_map and t in vec_map:
                result.append(vec_map[t])
            else:
                result.append([0.0] * dim)
        return result

    mock_vec = MagicMock()
    mock_vec.encode.side_effect = _encode
    engine.vectorizer = mock_vec
    return engine


def _unit_vec(dim: int = 1024, seed: int = 0) -> list[float]:
    """生成可重复的单位向量"""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    v /= np.linalg.norm(v)
    return v.tolist()


# ──────────────────── cosine_similarity() ─────────────────────


class TestCosineSimilarity:

    def setup_method(self) -> None:
        self.engine = _make_engine()

    def test_identical_vectors_return_1(self) -> None:
        v = _unit_vec(seed=1)
        assert math.isclose(self.engine.cosine_similarity(v, v), 1.0, abs_tol=1e-5)

    def test_orthogonal_vectors_return_0(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert math.isclose(self.engine.cosine_similarity(a, b), 0.0, abs_tol=1e-6)

    def test_opposite_vectors_return_negative(self) -> None:
        v = _unit_vec(seed=2)
        neg = [-x for x in v]
        result = self.engine.cosine_similarity(v, neg)
        assert result < 0

    def test_zero_vector_a_returns_0(self) -> None:
        a = [0.0] * 1024
        b = _unit_vec(seed=3)
        assert self.engine.cosine_similarity(a, b) == 0.0

    def test_zero_vector_b_returns_0(self) -> None:
        a = _unit_vec(seed=4)
        b = [0.0] * 1024
        assert self.engine.cosine_similarity(a, b) == 0.0

    def test_both_zero_vectors_returns_0(self) -> None:
        z = [0.0] * 4
        assert self.engine.cosine_similarity(z, z) == 0.0

    def test_result_in_range_minus1_to_1(self) -> None:
        a = _unit_vec(seed=5)
        b = _unit_vec(seed=6)
        result = self.engine.cosine_similarity(a, b)
        assert -1.0 <= result <= 1.0

    def test_returns_float(self) -> None:
        v = _unit_vec(seed=7)
        result = self.engine.cosine_similarity(v, v)
        assert isinstance(result, float)

    def test_small_vectors(self) -> None:
        a = [3.0, 4.0]
        b = [3.0, 4.0]
        assert math.isclose(self.engine.cosine_similarity(a, b), 1.0, abs_tol=1e-6)


# ─────────────────── analyze_diff_pairs() ─────────────────────


class TestAnalyzeDiffPairs:

    def test_empty_list_returns_empty(self) -> None:
        engine = _make_engine()
        assert engine.analyze_diff_pairs([]) == []

    def test_no_modify_items_returns_unchanged(self) -> None:
        engine = _make_engine()
        pairs = [
            {"seq_no": 0, "diff_type": "insert", "doc_a_text": None, "doc_b_text": "新增内容"},
            {"seq_no": 1, "diff_type": "delete", "doc_a_text": "删除内容", "doc_b_text": None},
        ]
        result = engine.analyze_diff_pairs(pairs)
        assert result == pairs
        engine.vectorizer.encode.assert_not_called()

    def test_modify_item_gets_semantic_similarity(self) -> None:
        va = _unit_vec(seed=10)
        vb = _unit_vec(seed=10)   # 相同向量，相似度1.0
        engine = _make_engine({"文本A": va, "文本B": vb})
        pairs = [{"seq_no": 0, "diff_type": "modify", "doc_a_text": "文本A", "doc_b_text": "文本B"}]
        result = engine.analyze_diff_pairs(pairs)
        assert "semantic_similarity" in result[0]
        assert math.isclose(result[0]["semantic_similarity"], 1.0, abs_tol=1e-4)

    def test_high_similarity_sets_equivalent_flag(self) -> None:
        """余弦相似度 >= threshold 时应设置 semantic_is_equivalent=True"""
        va = _unit_vec(seed=11)
        engine = _make_engine({"文本A": va, "文本B": va})
        pairs = [{"seq_no": 0, "diff_type": "modify", "doc_a_text": "文本A", "doc_b_text": "文本B"}]
        result = engine.analyze_diff_pairs(pairs, threshold=0.5)
        assert result[0].get("semantic_is_equivalent") is True

    def test_low_similarity_does_not_set_equivalent_flag(self) -> None:
        """余弦相似度 < threshold 时不应设置 semantic_is_equivalent"""
        va = _unit_vec(seed=20)
        vb = [-x for x in va]    # 反向向量，相似度≈-1
        engine = _make_engine({"文本A": va, "文本B": vb})
        pairs = [{"seq_no": 0, "diff_type": "modify", "doc_a_text": "文本A", "doc_b_text": "文本B"}]
        result = engine.analyze_diff_pairs(pairs, threshold=0.92)
        assert "semantic_is_equivalent" not in result[0]

    def test_semantic_similarity_rounded_to_4_decimals(self) -> None:
        va = _unit_vec(seed=30)
        vb = _unit_vec(seed=31)
        engine = _make_engine({"A": va, "B": vb})
        pairs = [{"seq_no": 0, "diff_type": "modify", "doc_a_text": "A", "doc_b_text": "B"}]
        result = engine.analyze_diff_pairs(pairs)
        sim = result[0]["semantic_similarity"]
        assert sim == round(sim, 4)

    def test_non_modify_items_unchanged_in_mixed_list(self) -> None:
        va = _unit_vec(seed=40)
        engine = _make_engine({"A": va, "B": va})
        pairs = [
            {"seq_no": 0, "diff_type": "insert", "doc_a_text": None, "doc_b_text": "新增"},
            {"seq_no": 1, "diff_type": "modify", "doc_a_text": "A",   "doc_b_text": "B"},
            {"seq_no": 2, "diff_type": "delete", "doc_a_text": "旧段", "doc_b_text": None},
        ]
        result = engine.analyze_diff_pairs(pairs)
        assert "semantic_similarity" not in result[0]
        assert "semantic_similarity" in result[1]
        assert "semantic_similarity" not in result[2]

    def test_multiple_modify_items_all_annotated(self) -> None:
        va1, vb1 = _unit_vec(seed=50), _unit_vec(seed=51)
        va2, vb2 = _unit_vec(seed=52), _unit_vec(seed=53)
        engine = _make_engine({"A1": va1, "B1": vb1, "A2": va2, "B2": vb2})
        pairs = [
            {"seq_no": 0, "diff_type": "modify", "doc_a_text": "A1", "doc_b_text": "B1"},
            {"seq_no": 1, "diff_type": "modify", "doc_a_text": "A2", "doc_b_text": "B2"},
        ]
        result = engine.analyze_diff_pairs(pairs)
        assert "semantic_similarity" in result[0]
        assert "semantic_similarity" in result[1]

    def test_modify_missing_doc_a_text_skipped(self) -> None:
        """doc_a_text 为空的 modify 项不应进行语义分析"""
        engine = _make_engine()
        pairs = [{"seq_no": 0, "diff_type": "modify", "doc_a_text": None, "doc_b_text": "B"}]
        result = engine.analyze_diff_pairs(pairs)
        assert "semantic_similarity" not in result[0]
        engine.vectorizer.encode.assert_not_called()

    def test_modify_missing_doc_b_text_skipped(self) -> None:
        """doc_b_text 为空的 modify 项不应进行语义分析"""
        engine = _make_engine()
        pairs = [{"seq_no": 0, "diff_type": "modify", "doc_a_text": "A", "doc_b_text": None}]
        result = engine.analyze_diff_pairs(pairs)
        assert "semantic_similarity" not in result[0]
        engine.vectorizer.encode.assert_not_called()

    def test_uses_config_threshold_when_none_passed(self) -> None:
        """未传 threshold 时使用配置文件中的 semantic_similarity_threshold"""
        va = _unit_vec(seed=60)
        engine = _make_engine({"A": va, "B": va})
        pairs = [{"seq_no": 0, "diff_type": "modify", "doc_a_text": "A", "doc_b_text": "B"}]
        with patch("app.services.compare.semantic_diff.settings") as mock_settings:
            mock_settings.semantic_similarity_threshold = 0.5
            result = engine.analyze_diff_pairs(pairs, threshold=None)
        assert result[0].get("semantic_is_equivalent") is True

    def test_encode_called_once_for_batch(self) -> None:
        """两个 modify 项只应调用两次 encode（A 批次一次，B 批次一次）"""
        va1, vb1 = _unit_vec(seed=70), _unit_vec(seed=71)
        va2, vb2 = _unit_vec(seed=72), _unit_vec(seed=73)
        engine = _make_engine({"A1": va1, "B1": vb1, "A2": va2, "B2": vb2})
        pairs = [
            {"seq_no": 0, "diff_type": "modify", "doc_a_text": "A1", "doc_b_text": "B1"},
            {"seq_no": 1, "diff_type": "modify", "doc_a_text": "A2", "doc_b_text": "B2"},
        ]
        engine.analyze_diff_pairs(pairs)
        assert engine.vectorizer.encode.call_count == 2

    def test_original_list_mutated_in_place(self) -> None:
        """analyze_diff_pairs 直接修改并返回同一列表对象"""
        va = _unit_vec(seed=80)
        engine = _make_engine({"A": va, "B": va})
        pairs = [{"seq_no": 0, "diff_type": "modify", "doc_a_text": "A", "doc_b_text": "B"}]
        result = engine.analyze_diff_pairs(pairs)
        assert result is pairs


# ─────────────────── search_similar_paragraphs() ──────────────


class TestSearchSimilarParagraphs:

    def _make_hit(self, block_index: int, section_path: str, chunk_text: str, score: float) -> MagicMock:
        hit = MagicMock()
        hit.entity.get.side_effect = lambda key: {
            "block_index": block_index,
            "section_path": section_path,
            "chunk_text": chunk_text,
        }.get(key)
        hit.score = score
        return hit

    def test_returns_correct_hit_structure(self) -> None:
        engine = _make_engine({"查询文本": _unit_vec(seed=90)})
        hit = self._make_hit(3, "第一章/第一节", "相似段落内容", 0.9512345)

        mock_collection = MagicMock()
        mock_collection.search.return_value = [[hit]]

        with patch("app.services.compare.semantic_diff.get_milvus_collection", return_value=mock_collection):
            result = engine.search_similar_paragraphs("查询文本", "doc-001", top_k=5)

        assert len(result) == 1
        assert result[0]["block_index"] == 3
        assert result[0]["section_path"] == "第一章/第一节"
        assert result[0]["chunk_text"] == "相似段落内容"
        assert result[0]["score"] == round(0.9512345, 4)

    def test_score_rounded_to_4_decimals(self) -> None:
        engine = _make_engine({"文本": _unit_vec(seed=91)})
        hit = self._make_hit(0, "", "内容", 0.123456789)
        mock_collection = MagicMock()
        mock_collection.search.return_value = [[hit]]

        with patch("app.services.compare.semantic_diff.get_milvus_collection", return_value=mock_collection):
            result = engine.search_similar_paragraphs("文本", "doc-002")

        assert result[0]["score"] == round(0.123456789, 4)

    def test_empty_results_returns_empty_list(self) -> None:
        engine = _make_engine({"文本": _unit_vec(seed=92)})
        mock_collection = MagicMock()
        mock_collection.search.return_value = [[]]

        with patch("app.services.compare.semantic_diff.get_milvus_collection", return_value=mock_collection):
            result = engine.search_similar_paragraphs("文本", "doc-003")

        assert result == []

    def test_search_called_with_correct_params(self) -> None:
        query_vec = _unit_vec(seed=93)
        engine = _make_engine({"搜索文本": query_vec})
        mock_collection = MagicMock()
        mock_collection.search.return_value = [[]]

        with patch("app.services.compare.semantic_diff.get_milvus_collection", return_value=mock_collection):
            engine.search_similar_paragraphs("搜索文本", "doc-004", top_k=3)

        call_kwargs = mock_collection.search.call_args
        assert call_kwargs[1]["limit"] == 3 or call_kwargs[0][2] == 3 or mock_collection.search.call_args.kwargs.get("limit") == 3 or mock_collection.search.call_args.args[2] == 3

    def test_search_filters_by_doc_id(self) -> None:
        engine = _make_engine({"文本": _unit_vec(seed=94)})
        mock_collection = MagicMock()
        mock_collection.search.return_value = [[]]

        with patch("app.services.compare.semantic_diff.get_milvus_collection", return_value=mock_collection):
            engine.search_similar_paragraphs("文本", "doc-xyz-999")

        call_args = mock_collection.search.call_args
        # expr 参数应包含 doc_id 过滤
        all_args = list(call_args.args) + list(call_args.kwargs.values())
        assert any("doc-xyz-999" in str(a) for a in all_args)

    def test_multiple_hits_all_returned(self) -> None:
        engine = _make_engine({"文本": _unit_vec(seed=95)})
        hits = [self._make_hit(i, f"章节{i}", f"内容{i}", 0.9 - i * 0.1) for i in range(3)]
        mock_collection = MagicMock()
        mock_collection.search.return_value = [hits]

        with patch("app.services.compare.semantic_diff.get_milvus_collection", return_value=mock_collection):
            result = engine.search_similar_paragraphs("文本", "doc-005", top_k=3)

        assert len(result) == 3
        assert result[0]["block_index"] == 0
        assert result[2]["block_index"] == 2
