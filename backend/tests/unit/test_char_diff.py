"""
字符级比对引擎单元测试
见 CLAUDE.md §8.1：services/compare/ 覆盖率 ≥ 90%
"""
import pytest

from app.services.compare.char_diff import (
    CharDiffEngine,
    CharDiffResult,
    CharDiffSpan,
    DiffOp,
)


# ──────────────────────── Fixtures ────────────────────────────


@pytest.fixture
def engine() -> CharDiffEngine:
    return CharDiffEngine(cleanup_semantic=True)


@pytest.fixture
def engine_no_cleanup() -> CharDiffEngine:
    return CharDiffEngine(cleanup_semantic=False)


# ──────────────────────── DiffOp 枚举 ─────────────────────────


class TestDiffOp:

    def test_values(self) -> None:
        assert DiffOp.EQUAL == "equal"
        assert DiffOp.INSERT == "insert"
        assert DiffOp.DELETE == "delete"


# ───────────────────────── diff() ─────────────────────────────


class TestDiff:

    def test_identical_texts_returns_similarity_1(self, engine: CharDiffEngine) -> None:
        result = engine.diff("相同文本", "相同文本")
        assert result.similarity == 1.0
        assert result.total_changes == 0
        assert len(result.spans) == 1
        assert result.spans[0].op == DiffOp.EQUAL

    def test_identical_texts_span_contains_full_text(self, engine: CharDiffEngine) -> None:
        text = "完整文本内容"
        result = engine.diff(text, text)
        assert result.spans[0].text == text

    def test_completely_different_texts(self, engine: CharDiffEngine) -> None:
        result = engine.diff("AAAA", "BBBB")
        assert result.similarity < 1.0
        assert result.total_changes > 0

    def test_insert_only(self, engine: CharDiffEngine) -> None:
        result = engine.diff("abc", "abcXYZ")
        ops = {s.op for s in result.spans}
        assert DiffOp.INSERT in ops
        assert result.total_changes == 3

    def test_delete_only(self, engine: CharDiffEngine) -> None:
        result = engine.diff("abcXYZ", "abc")
        ops = {s.op for s in result.spans}
        assert DiffOp.DELETE in ops
        assert result.total_changes == 3

    def test_modify_middle(self, engine: CharDiffEngine) -> None:
        result = engine.diff("前缀内容后缀", "前缀修改后缀")
        assert result.similarity < 1.0
        assert result.total_changes > 0

    def test_similarity_range(self, engine: CharDiffEngine) -> None:
        result = engine.diff("文档内容A版本", "文档内容B版本修改")
        assert 0.0 <= result.similarity <= 1.0

    def test_similarity_rounded_to_4_decimal_places(self, engine: CharDiffEngine) -> None:
        result = engine.diff("abcde", "abcXY")
        # 结果精度应为4位小数
        assert result.similarity == round(result.similarity, 4)

    def test_empty_string_a(self, engine: CharDiffEngine) -> None:
        result = engine.diff("", "新增内容")
        assert result.total_changes == len("新增内容")
        assert result.similarity == 0.0

    def test_empty_string_b(self, engine: CharDiffEngine) -> None:
        result = engine.diff("删除内容", "")
        assert result.total_changes == len("删除内容")
        assert result.similarity == 0.0

    def test_both_empty(self, engine: CharDiffEngine) -> None:
        result = engine.diff("", "")
        assert result.similarity == 1.0
        assert result.total_changes == 0

    def test_pos_a_tracking(self, engine: CharDiffEngine) -> None:
        """EQUAL span 的 pos_a 应为正确的字符偏移"""
        result = engine.diff("ABCDEF", "ABCXEF")
        equal_spans = [s for s in result.spans if s.op == DiffOp.EQUAL]
        assert equal_spans[0].pos_a == 0

    def test_no_cleanup_semantic(self, engine_no_cleanup: CharDiffEngine) -> None:
        """cleanup_semantic=False 时不做语义清洗，结果仍有效"""
        result = engine_no_cleanup.diff("hello world", "hello earth")
        assert result.similarity < 1.0
        assert result.total_changes > 0

    def test_chinese_text_diff(self, engine: CharDiffEngine) -> None:
        result = engine.diff(
            "甲方应于合同签订后三十日内支付首付款。",
            "甲方应于合同签订后六十日内支付首付款。",
        )
        assert result.similarity < 1.0
        delete_texts = [s.text for s in result.spans if s.op == DiffOp.DELETE]
        insert_texts = [s.text for s in result.spans if s.op == DiffOp.INSERT]
        assert any("三十" in t for t in delete_texts)
        assert any("六十" in t for t in insert_texts)

    def test_result_is_charDiffResult_instance(self, engine: CharDiffEngine) -> None:
        result = engine.diff("a", "b")
        assert isinstance(result, CharDiffResult)

    def test_spans_are_charDiffSpan_instances(self, engine: CharDiffEngine) -> None:
        result = engine.diff("abc", "axc")
        for span in result.spans:
            assert isinstance(span, CharDiffSpan)


# ────────────────────── diff_paragraphs() ─────────────────────


class TestDiffParagraphs:

    def test_identical_paragraphs_produce_no_diffs(self, engine: CharDiffEngine) -> None:
        paras = ["第一段", "第二段", "第三段"]
        result = engine.diff_paragraphs(paras, paras)
        # 完全相同的段落不应出现在结果中
        assert result == []

    def test_insert_paragraph(self, engine: CharDiffEngine) -> None:
        pa = ["第一段内容", "第二段内容"]
        pb = ["第一段内容", "新增段落内容在此处", "第二段内容"]
        result = engine.diff_paragraphs(pa, pb)
        insert_items = [r for r in result if r["diff_type"] == "insert"]
        assert len(insert_items) >= 1
        assert any(r["doc_b_text"] == "新增段落内容在此处" for r in insert_items)

    def test_delete_paragraph(self, engine: CharDiffEngine) -> None:
        pa = ["第一段内容", "被删除的段落", "第二段内容"]
        pb = ["第一段内容", "第二段内容"]
        result = engine.diff_paragraphs(pa, pb)
        delete_items = [r for r in result if r["diff_type"] == "delete"]
        assert len(delete_items) >= 1
        assert any(r["doc_a_text"] == "被删除的段落" for r in delete_items)

    def test_modify_paragraph(self, engine: CharDiffEngine) -> None:
        pa = ["合同金额为人民币一百万元整。"]
        pb = ["合同金额为人民币两百万元整。"]
        result = engine.diff_paragraphs(pa, pb)
        assert len(result) == 1
        assert result[0]["diff_type"] == "modify"
        assert result[0]["doc_a_text"] == pa[0]
        assert result[0]["doc_b_text"] == pb[0]
        assert "char_spans" in result[0]

    def test_seq_no_increments(self, engine: CharDiffEngine) -> None:
        pa = ["段落一内容", "段落二内容"]
        pb = ["段落一内容", "段落二修改版"]
        result = engine.diff_paragraphs(pa, pb)
        seq_nos = [r["seq_no"] for r in result]
        assert seq_nos == sorted(seq_nos)

    def test_modify_item_has_similarity(self, engine: CharDiffEngine) -> None:
        pa = ["原始内容在这里，略有不同。"]
        pb = ["修改内容在这里，略有不同。"]
        result = engine.diff_paragraphs(pa, pb)
        assert len(result) == 1
        assert 0.0 <= result[0]["similarity"] <= 1.0

    def test_insert_item_similarity_is_zero(self, engine: CharDiffEngine) -> None:
        pa: list[str] = []
        pb = ["全新段落内容，文档B新增。"]
        result = engine.diff_paragraphs(pa, pb)
        assert result[0]["diff_type"] == "insert"
        assert result[0]["similarity"] == 0.0
        assert result[0]["doc_a_text"] is None

    def test_delete_item_similarity_is_zero(self, engine: CharDiffEngine) -> None:
        pa = ["将被删除的段落内容。"]
        pb: list[str] = []
        result = engine.diff_paragraphs(pa, pb)
        assert result[0]["diff_type"] == "delete"
        assert result[0]["similarity"] == 0.0
        assert result[0]["doc_b_text"] is None

    def test_empty_both_lists(self, engine: CharDiffEngine) -> None:
        result = engine.diff_paragraphs([], [])
        assert result == []

    def test_char_spans_ops_are_valid(self, engine: CharDiffEngine) -> None:
        pa = ["这是原始版本的合同条款内容。"]
        pb = ["这是修改版本的合同条款内容。"]
        result = engine.diff_paragraphs(pa, pb)
        assert result[0]["diff_type"] == "modify"
        valid_ops = {DiffOp.EQUAL, DiffOp.INSERT, DiffOp.DELETE}
        for span in result[0]["char_spans"]:
            assert span["op"] in valid_ops


# ─────────────────── _align_paragraphs() ─────────────────────


class TestAlignParagraphs:

    def test_identical_lists_align_one_to_one(self, engine: CharDiffEngine) -> None:
        paras = ["段落一内容", "段落二内容", "段落三内容"]
        aligned = engine._align_paragraphs(paras, paras)
        paired = [p for p in aligned if p["a"] is not None and p["b"] is not None]
        assert len(paired) == 3

    def test_empty_a_all_inserts(self, engine: CharDiffEngine) -> None:
        aligned = engine._align_paragraphs([], ["新段落一", "新段落二"])
        assert all(p["a"] is None for p in aligned)
        assert len(aligned) == 2

    def test_empty_b_all_deletes(self, engine: CharDiffEngine) -> None:
        aligned = engine._align_paragraphs(["旧段落一", "旧段落二"], [])
        assert all(p["b"] is None for p in aligned)
        assert len(aligned) == 2

    def test_short_paragraphs_not_compared(self, engine: CharDiffEngine) -> None:
        """长度 ≤ 10 的段落不计算相似度，依赖精确匹配"""
        pa = ["短"]
        pb = ["短"]
        aligned = engine._align_paragraphs(pa, pb)
        # 完全相同，应被对齐
        paired = [p for p in aligned if p["a"] == "短" and p["b"] == "短"]
        assert len(paired) == 1

    def test_low_similarity_paragraphs_not_paired(self, engine: CharDiffEngine) -> None:
        """相似度 < 0.6 的段落不应被配对"""
        pa = ["AAAAAAAAAAAAAAAAAAAAAA"]
        pb = ["BBBBBBBBBBBBBBBBBBBBBB"]
        aligned = engine._align_paragraphs(pa, pb)
        # 完全不同，应各自为 delete/insert
        paired = [p for p in aligned if p["a"] is not None and p["b"] is not None]
        assert len(paired) == 0

    def test_result_covers_all_inputs(self, engine: CharDiffEngine) -> None:
        """对齐结果必须覆盖 A 和 B 的所有段落"""
        pa = ["段落一内容足够长", "段落二内容足够长", "段落三内容足够长"]
        pb = ["段落一内容足够长", "段落四内容足够长"]
        aligned = engine._align_paragraphs(pa, pb)
        a_texts = [p["a"] for p in aligned if p["a"] is not None]
        b_texts = [p["b"] for p in aligned if p["b"] is not None]
        assert set(a_texts) == set(pa)
        assert set(b_texts) == set(pb)
