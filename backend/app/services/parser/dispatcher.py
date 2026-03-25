"""
解析任务调度器，完整实现见任务 6（Word/TXT 解析）和任务 7（PDF 解析）。
此文件在任务 5 阶段作为占位，提供 dispatch_parse 接口供文档上传流程调用。
"""
import structlog
from app.models.document import FileType

logger = structlog.get_logger()


async def dispatch_parse(doc_id: str, content: bytes, file_type: FileType) -> None:
    """
    根据文件类型派发到对应解析器（后台任务入口）。
    完整实现在任务 6/7 中填充，当前仅记录日志。
    """
    logger.info("解析任务已入队（解析器待实现）",
                doc_id=doc_id, file_type=file_type)
