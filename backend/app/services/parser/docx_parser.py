import io
import re
from docx import Document as DocxDocument
from docx.text.paragraph import Paragraph as DocxParagraph
from docx.table import Table as DocxTable
from .base import BaseParser, ParsedDocument, DocumentMeta, TextBlock, TableBlock, BlockType
import structlog

logger = structlog.get_logger()

# 标题样式名映射
HEADING_STYLE_MAP: dict[str, int] = {
    "Heading 1": 1, "Heading 2": 2, "Heading 3": 3,
    "Heading 4": 4, "Heading 5": 5, "Heading 6": 6,
    "标题 1": 1, "标题 2": 2, "标题 3": 3,
    "标题1": 1, "标题2": 2, "标题3": 3,
    # 钢铁行业文档常见样式
    "一级标题": 1, "二级标题": 2, "三级标题": 3,
}


class DocxParser(BaseParser):

    async def parse(self, content: bytes, file_name: str) -> ParsedDocument:
        try:
            doc = DocxDocument(io.BytesIO(content))
        except Exception as e:
            logger.error("Word 文档打开失败", file_name=file_name, error=str(e))
            raise ValueError(f"无法解析 Word 文档: {e}")

        blocks: list[TextBlock | TableBlock] = []
        index = 0
        section_stack: list[str] = []   # 维护章节路径

        # 遍历文档元素（段落 + 表格，保持顺序）
        for element in doc.element.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                para = DocxParagraph(element, doc)
                text = para.text.strip()
                if not text:
                    continue

                style_name = para.style.name if para.style else ""
                level = HEADING_STYLE_MAP.get(style_name, 0)

                if level > 0:
                    # 维护章节路径栈
                    section_stack = section_stack[:level - 1]
                    section_stack.append(text)
                    block_type = BlockType.HEADING
                elif style_name.lower() in ("list paragraph",):
                    block_type = BlockType.LIST_ITEM
                else:
                    block_type = BlockType.PARAGRAPH

                blocks.append(TextBlock(
                    block_type=block_type,
                    text=text,
                    level=level,
                    index=index,
                    section_path="/".join(section_stack[:-1]) if level > 0 else "/".join(section_stack),
                    style_name=style_name,
                ))
                index += 1

            elif tag == "tbl":
                table = DocxTable(element, doc)
                rows = []
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    rows.append(row_data)
                blocks.append(TableBlock(
                    rows=rows,
                    index=index,
                    section_path="/".join(section_stack),
                ))
                index += 1

        # 提取元数据
        core_props = doc.core_properties
        word_count = sum(len(b.text) for b in blocks if isinstance(b, TextBlock))
        title = core_props.title or (blocks[0].text if blocks else "")

        meta = DocumentMeta(
            file_name=file_name,
            file_type="docx",
            page_count=None,     # docx 不直接提供页数
            word_count=word_count,
            title=title[:512],
            author=core_props.author or "",
        )

        raw_text = self._build_raw_text(blocks)

        logger.info("Word 解析完成",
                    file_name=file_name,
                    blocks=len(blocks),
                    word_count=word_count)

        return ParsedDocument(meta=meta, blocks=blocks, raw_text=raw_text)
