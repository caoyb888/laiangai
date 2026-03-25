"""BGE-M3 向量化服务，完整实现见任务 9"""
from app.services.parser.base import ParsedDocument
import structlog

logger = structlog.get_logger()


async def vectorize_document(doc_id: str, parsed: ParsedDocument) -> None:
    """向量化解析结果并写入 Milvus（任务 9 实现）"""
    logger.info("向量化任务已入队（向量化服务待实现）", doc_id=doc_id)
