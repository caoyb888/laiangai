"""扫描版 PDF OCR 解析器，完整实现见任务 23"""
from .base import BaseParser, ParsedDocument, DocumentMeta
import structlog

logger = structlog.get_logger()


class OcrParser(BaseParser):
    async def parse(self, content: bytes, file_name: str) -> ParsedDocument:
        raise NotImplementedError("OCR 解析器将在任务 23 中实现")
