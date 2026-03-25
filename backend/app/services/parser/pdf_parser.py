"""PDF 文字版解析器，完整实现见任务 7"""
from .base import BaseParser, ParsedDocument, DocumentMeta
import structlog

logger = structlog.get_logger()


class PdfParser(BaseParser):
    async def parse(self, content: bytes, file_name: str) -> ParsedDocument:
        raise NotImplementedError("PDF 解析器将在任务 7 中实现")
