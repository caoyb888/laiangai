"""
BGE-M3 本地 CPU 向量化服务
见 CLAUDE.md §2.1：本地部署，CPU 推理，禁止调用外部向量 API
"""
import uuid

import numpy as np
import structlog
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.config import get_settings
from app.services.parser.base import ParsedDocument


def _trunc_bytes(s: str, max_bytes: int) -> str:
    """按 UTF-8 字节数截断字符串（Milvus VARCHAR max_length 按字节计算）"""
    encoded = s.encode("utf-8")
    if len(encoded) <= max_bytes:
        return s
    return encoded[:max_bytes].decode("utf-8", errors="ignore")

logger = structlog.get_logger()
settings = get_settings()

# BGE-M3 分块参数
CHUNK_SIZE = 512         # 每块最大字符数
CHUNK_OVERLAP = 50       # 相邻块重叠字符数


class VectorizerService:

    _model: object | None = None

    @classmethod
    def get_model(cls) -> object:
        if cls._model is None:
            import os
            import torch
            from FlagEmbedding import BGEM3FlagModel  # 懒加载，避免测试时 import 失败

            # PyTorch 2.6 将 weights_only 默认改为 True，旧格式 .bin 文件不兼容
            # FlagEmbedding 内部调用 torch.load 时需要 weights_only=False
            _orig_load = torch.load
            def _patched_load(*args, **kwargs):  # noqa: ANN
                # FlagEmbedding 内部显式传 weights_only=True，setdefault 无法覆盖
                # 旧格式 .pt 权重文件需要 weights_only=False 才能加载
                kwargs["weights_only"] = False
                return _orig_load(*args, **kwargs)
            torch.load = _patched_load

            model_path = os.getenv("BGE_M3_MODEL_PATH", "BAAI/bge-m3")
            logger.info("加载 BGE-M3 模型", path=model_path)
            try:
                cls._model = BGEM3FlagModel(
                    model_path,
                    use_fp16=False,       # CPU 模式不用 fp16
                    device="cpu",
                )
                logger.info("BGE-M3 模型加载完成")
            finally:
                torch.load = _orig_load   # 还原，避免影响其他模块
        return cls._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """对文本列表进行向量化，返回 dense vectors"""
        if not texts:
            return []
        model = self.get_model()
        # batch_size 根据 CPU 内存调整
        embeddings = model.encode(
            texts,
            batch_size=8,
            max_length=512,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        vecs: np.ndarray = embeddings["dense_vecs"]
        return vecs.tolist()

    def chunk_text(self, text: str) -> list[str]:
        """滑动窗口分块"""
        if len(text) <= CHUNK_SIZE:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunks.append(text[start:end])
            if end == len(text):
                break
            start += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def chunk_parsed_document(
        self, parsed: ParsedDocument
    ) -> list[tuple[str, dict]]:
        """
        将 ParsedDocument 分块，返回 (chunk_text, metadata) 列表
        metadata 用于存储 Milvus 中的位置信息
        """
        results: list[tuple[str, dict]] = []
        for block in parsed.get_text_blocks():
            if len(block.text) < 5:    # 过滤过短文本
                continue
            chunks = self.chunk_text(block.text)
            for chunk_idx, chunk in enumerate(chunks):
                results.append((chunk, {
                    "block_index": block.index,
                    "section_path": block.section_path,
                    "chunk_idx": chunk_idx,
                }))
        return results


def vectorize_document_sync(doc_id: str, parsed: ParsedDocument) -> list[str]:
    """同步版向量化，供 asyncio.to_thread 调用，避免阻塞事件循环"""
    import asyncio
    return asyncio.run(vectorize_document(doc_id, parsed))


async def vectorize_document(doc_id: str, parsed: ParsedDocument) -> list[str]:
    """
    文档向量化并存入 Milvus
    返回存储的 vector ID 列表
    """
    service = VectorizerService()
    chunks_with_meta = service.chunk_parsed_document(parsed)
    if not chunks_with_meta:
        logger.info("文档无可向量化内容", doc_id=doc_id)
        return []

    texts = [c[0] for c in chunks_with_meta]
    metas = [c[1] for c in chunks_with_meta]
    vectors = service.encode(texts)

    # 存入 Milvus
    collection = get_milvus_collection()
    vector_ids = [str(uuid.uuid4()) for _ in texts]

    data = [
        vector_ids,                                          # id
        [doc_id] * len(texts),                               # doc_id
        [m["block_index"] for m in metas],                   # block_index
        [_trunc_bytes(m["section_path"], 200) for m in metas],  # section_path
        [_trunc_bytes(t, 500) for t in texts],               # chunk_text
        vectors,                                             # embedding
    ]
    collection.insert(data)
    collection.flush()

    logger.info("向量化完成", doc_id=doc_id, chunks=len(texts))
    return vector_ids


async def delete_document_vectors(doc_id: str) -> None:
    """删除指定文档的所有向量（文档删除时调用）"""
    collection = get_milvus_collection()
    collection.delete(f'doc_id == "{doc_id}"')
    collection.flush()
    logger.info("文档向量已删除", doc_id=doc_id)


def get_milvus_collection() -> Collection:
    """获取或创建 Milvus Collection"""
    connections.connect(
        alias="default",
        host=settings.milvus_host,
        port=settings.milvus_port,
    )
    name = settings.milvus_collection_name

    if utility.has_collection(name):
        col = Collection(name)
        col.load()
        return col

    fields = [
        FieldSchema(name="id",           dtype=DataType.VARCHAR, max_length=36, is_primary=True),
        FieldSchema(name="doc_id",       dtype=DataType.VARCHAR, max_length=36),
        FieldSchema(name="block_index",  dtype=DataType.INT64),
        FieldSchema(name="section_path", dtype=DataType.VARCHAR, max_length=200),
        FieldSchema(name="chunk_text",   dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="embedding",    dtype=DataType.FLOAT_VECTOR, dim=1024),  # BGE-M3 dim=1024
    ]
    schema = CollectionSchema(fields, description="文档段落向量库")
    collection = Collection(name, schema)
    collection.create_index(
        "embedding",
        {"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 128}},
    )
    collection.load()
    logger.info("Milvus Collection 创建完成", collection=name)
    return collection
