import re
import chardet
from .base import BaseParser, ParsedDocument, DocumentMeta, TextBlock, TableBlock, BlockType
import structlog

logger = structlog.get_logger()

# 常见标题正则（钢铁行业文档常见格式）
HEADING_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"^第[一二三四五六七八九十百]+[章节条款]"), 1),
    (re.compile(r"^\d+\.\s"), 2),
    (re.compile(r"^\d+\.\d+\s"), 3),
    (re.compile(r"^[一二三四五六七八九十]+、"), 2),
    (re.compile(r"^（[一二三四五六七八九十]+）"), 3),
]


class TxtParser(BaseParser):

    async def parse(self, content: bytes, file_name: str) -> ParsedDocument:
        # 自动检测编码
        detected = chardet.detect(content)
        encoding = detected.get("encoding") or "utf-8"
        try:
            text = content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            text = content.decode("utf-8", errors="replace")

        lines = text.splitlines()
        blocks: list[TextBlock | TableBlock] = []
        index = 0
        section_stack: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            level = 0
            for pattern, lvl in HEADING_PATTERNS:
                if pattern.match(stripped):
                    level = lvl
                    break

            if level > 0:
                section_stack = section_stack[:level - 1]
                section_stack.append(stripped)
                block_type = BlockType.HEADING
            else:
                block_type = BlockType.PARAGRAPH

            blocks.append(TextBlock(
                block_type=block_type,
                text=stripped,
                level=level,
                index=index,
                section_path="/".join(section_stack[:-1] if level > 0 else section_stack),
                style_name="",
            ))
            index += 1

        word_count = sum(len(b.text) for b in blocks)
        meta = DocumentMeta(
            file_name=file_name,
            file_type="txt",
            word_count=word_count,
            title=blocks[0].text[:100] if blocks else "",
        )

        logger.info("TXT 解析完成",
                    file_name=file_name,
                    blocks=len(blocks),
                    word_count=word_count)

        return ParsedDocument(
            meta=meta,
            blocks=blocks,
            raw_text=self._build_raw_text(blocks),
        )
