"""
向量化服务单元测试
见 CLAUDE.md §8.1：核心服务覆盖率 ≥ 70%
"""
import pytest
from unittest.mock import MagicMock, patch

from app.services.parser.base import (
    BlockType,
    DocumentMeta,
    ParsedDocument,
    TableBlock,
    TextBlock,
)
from app.services.vectorizer import CHUNK_OVERLAP, CHUNK_SIZE, VectorizerService


# ──────────────────────────── Fixtures ────────────────────────────


def _make_parsed(texts: list[str]) -> ParsedDocument:
    """辅助函数：构造带若干文本块的 ParsedDocument"""
    blocks: list[TextBlock | TableBlock] = [
        TextBlock(
            block_type=BlockType.PARAGRAPH,
            text=t,
            index=i,
            section_path=f"第{i + 1}段",
        )
        for i, t in enumerate(texts)
    ]
    meta = DocumentMeta(file_name="test.docx", file_type="docx")
    doc = ParsedDocument(meta=meta, blocks=blocks)
    doc.raw_text = "\n".join(texts)
    return doc


# ──────────────────────── chunk_text 测试 ────────────────────────


class TestChunkText:

    def setup_method(self) -> None:
        self.svc = VectorizerService()

    def test_short_text_returns_single_chunk(self) -> None:
        text = "短文本"
        result = self.svc.chunk_text(text)
        assert result == [text]

    def test_exact_chunk_size_returns_single_chunk(self) -> None:
        text = "A" * CHUNK_SIZE
        result = self.svc.chunk_text(text)
        assert len(result) == 1
        assert result[0] == text

    def test_long_text_splits_into_multiple_chunks(self) -> None:
        text = "B" * (CHUNK_SIZE * 2)
        result = self.svc.chunk_text(text)
        assert len(result) > 1

    def test_chunks_cover_full_text(self) -> None:
        """重建后文本应覆盖原文（允许重叠部分重复）"""
        text = "C" * (CHUNK_SIZE + 100)
        chunks = self.svc.chunk_text(text)
        # 首块从0开始，末块应覆盖文本末尾
        reconstructed_start = chunks[0][:CHUNK_SIZE - CHUNK_OVERLAP]
        assert text.startswith(reconstructed_start)
        assert text.endswith(chunks[-1][-(len(chunks[-1])):])

    def test_overlap_between_adjacent_chunks(self) -> None:
        text = "X" * (CHUNK_SIZE + CHUNK_OVERLAP + 10)
        chunks = self.svc.chunk_text(text)
        assert len(chunks) >= 2
        # 第一块末尾应与第二块开头有重叠
        overlap = chunks[0][CHUNK_SIZE - CHUNK_OVERLAP:]
        assert chunks[1].startswith(overlap)

    def test_empty_string_returns_single_chunk(self) -> None:
        result = self.svc.chunk_text("")
        assert result == [""]


# ────────────────── chunk_parsed_document 测试 ──────────────────


class TestChunkParsedDocument:

    def setup_method(self) -> None:
        self.svc = VectorizerService()

    def test_normal_document(self) -> None:
        parsed = _make_parsed(["第一段内容，长度足够。", "第二段内容，也足够长。"])
        result = self.svc.chunk_parsed_document(parsed)
        assert len(result) == 2
        texts = [r[0] for r in result]
        assert "第一段内容，长度足够。" in texts
        assert "第二段内容，也足够长。" in texts

    def test_short_texts_are_filtered(self) -> None:
        """少于5字符的块应被过滤"""
        parsed = _make_parsed(["OK", "这是一段足够长的内容可以通过过滤。"])
        result = self.svc.chunk_parsed_document(parsed)
        assert len(result) == 1
        assert result[0][0] == "这是一段足够长的内容可以通过过滤。"

    def test_metadata_contains_block_index_and_section_path(self) -> None:
        parsed = _make_parsed(["这段文字应该足够长以通过过滤条件检查。"])
        result = self.svc.chunk_parsed_document(parsed)
        assert len(result) == 1
        _, meta = result[0]
        assert "block_index" in meta
        assert "section_path" in meta
        assert "chunk_idx" in meta

    def test_long_block_produces_multiple_chunks(self) -> None:
        long_text = "测试文字" * 200   # 约 800 字符，超过 CHUNK_SIZE
        parsed = _make_parsed([long_text])
        result = self.svc.chunk_parsed_document(parsed)
        assert len(result) > 1
        # 所有分块的 block_index 应相同
        assert all(r[1]["block_index"] == 0 for r in result)
        # chunk_idx 应递增
        assert [r[1]["chunk_idx"] for r in result] == list(range(len(result)))

    def test_empty_document_returns_empty_list(self) -> None:
        parsed = _make_parsed([])
        result = self.svc.chunk_parsed_document(parsed)
        assert result == []

    def test_table_blocks_are_ignored(self) -> None:
        """TableBlock 不参与向量化分块"""
        meta = DocumentMeta(file_name="test.docx", file_type="docx")
        table = TableBlock(rows=[["列A", "列B"]], index=0)
        parsed = ParsedDocument(meta=meta, blocks=[table])
        result = self.svc.chunk_parsed_document(parsed)
        assert result == []


# ──────────────────────── encode 测试 ────────────────────────────


class TestEncode:

    def setup_method(self) -> None:
        VectorizerService._model = None   # 重置单例，避免测试间干扰

    def teardown_method(self) -> None:
        VectorizerService._model = None

    def test_encode_empty_list_returns_empty(self) -> None:
        svc = VectorizerService()
        result = svc.encode([])
        assert result == []

    def test_encode_calls_model_with_correct_params(self) -> None:
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": np.array([[0.1] * 1024, [0.2] * 1024])
        }
        VectorizerService._model = mock_model

        svc = VectorizerService()
        texts = ["文本一", "文本二"]
        result = svc.encode(texts)

        mock_model.encode.assert_called_once_with(
            texts,
            batch_size=8,
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        assert len(result) == 2
        assert len(result[0]) == 1024

    def test_encode_returns_list_of_lists(self) -> None:
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = {
            "dense_vecs": np.array([[0.5] * 1024])
        }
        VectorizerService._model = mock_model

        svc = VectorizerService()
        result = svc.encode(["单条文本"])
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert len(result[0]) == 1024

    def test_get_model_singleton(self) -> None:
        """get_model 应返回同一实例（懒加载单例）"""
        import numpy as np

        mock_model = MagicMock()
        mock_model.encode.return_value = {"dense_vecs": np.zeros((1, 1024))}

        with patch("app.services.vectorizer.BGEM3FlagModel", return_value=mock_model):
            m1 = VectorizerService.get_model()
            m2 = VectorizerService.get_model()
            assert m1 is m2


# ──────────────────── vectorize_document 测试 ────────────────────


class TestVectorizeDocument:

    def teardown_method(self) -> None:
        VectorizerService._model = None

    @pytest.mark.asyncio
    async def test_returns_empty_list_for_empty_document(self) -> None:
        from app.services.vectorizer import vectorize_document

        parsed = _make_parsed([])
        # 无需真实 Milvus，空文档直接返回
        result = await vectorize_document("doc-001", parsed)
        assert result == []

    @pytest.mark.asyncio
    async def test_vectorize_stores_to_milvus(self) -> None:
        import numpy as np
        from app.services.vectorizer import vectorize_document

        parsed = _make_parsed(["这是一段测试文字，用于验证向量化流程的正确性。"])

        mock_model = MagicMock()
        mock_model.encode.return_value = {"dense_vecs": np.array([[0.1] * 1024])}
        VectorizerService._model = mock_model

        mock_collection = MagicMock()

        with patch("app.services.vectorizer.get_milvus_collection", return_value=mock_collection):
            result = await vectorize_document("doc-002", parsed)

        assert len(result) == 1
        mock_collection.insert.assert_called_once()
        mock_collection.flush.assert_called_once()
        inserted_data = mock_collection.insert.call_args[0][0]
        # inserted_data[1] 是 doc_id 列表
        assert inserted_data[1] == ["doc-002"]

    @pytest.mark.asyncio
    async def test_vectorize_returns_correct_number_of_ids(self) -> None:
        import numpy as np
        from app.services.vectorizer import vectorize_document

        texts = ["段落一内容足够长以通过过滤。", "段落二内容也足够长以通过过滤。", "段落三内容同样足够。"]
        parsed = _make_parsed(texts)

        mock_model = MagicMock()
        mock_model.encode.return_value = {"dense_vecs": np.array([[0.1] * 1024] * len(texts))}
        VectorizerService._model = mock_model

        mock_collection = MagicMock()

        with patch("app.services.vectorizer.get_milvus_collection", return_value=mock_collection):
            result = await vectorize_document("doc-003", parsed)

        assert len(result) == len(texts)
        # 每个 ID 应为 UUID 格式（36字符）
        for vid in result:
            assert len(vid) == 36


# ─────────────────── delete_document_vectors 测试 ────────────────


class TestDeleteDocumentVectors:

    @pytest.mark.asyncio
    async def test_delete_calls_collection_delete_and_flush(self) -> None:
        from app.services.vectorizer import delete_document_vectors

        mock_collection = MagicMock()

        with patch("app.services.vectorizer.get_milvus_collection", return_value=mock_collection):
            await delete_document_vectors("doc-del-001")

        mock_collection.delete.assert_called_once_with('doc_id == "doc-del-001"')
        mock_collection.flush.assert_called_once()
