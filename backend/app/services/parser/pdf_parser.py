import io
import re
from .base import BaseParser, ParsedDocument, DocumentMeta, TextBlock, TableBlock, BlockType
import pdfplumber
import structlog

logger = structlog.get_logger()

# 标题正则（模块级，避免每次调用重复编译）
_HEADING_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"^第[一二三四五六七八九十百]+[章节]"), 1),
    (re.compile(r"^\d+\s+[\u4e00-\u9fff]"), 2),
    (re.compile(r"^\d+\.\d+\s"), 3),
    (re.compile(r"^[一二三四五六七八九十]+、"), 2),
]


class PdfParser(BaseParser):
    """
    文字版 PDF 解析器，使用 pdfplumber
    扫描版 PDF（文字置信度低）将被路由到 OcrParser
    """

    # 字符密度阈值（chars / pt²）：低于此值判定为扫描版
    # 文档原值 0.3 有误（A4 页面约 50 万 pt²，实际文字密度约 0.001~0.02）
    # 修正为 0.001：低于此值说明页面几乎无嵌入文字，按扫描版处理
    TEXT_DENSITY_THRESHOLD = 0.001

    async def parse(self, content: bytes, file_name: str) -> ParsedDocument:
        try:
            pdf = pdfplumber.open(io.BytesIO(content))
        except Exception as e:
            raise ValueError(f"无法解析 PDF: {e}")

        page_count = len(pdf.pages)

        # 检测是否为扫描版（抽样前3页）
        if self._is_scanned(pdf):
            pdf.close()
            logger.info("检测为扫描版PDF，转交OCR", file_name=file_name)
            from .ocr_parser import OcrParser
            return await OcrParser().parse(content, file_name)

        blocks: list[TextBlock | TableBlock] = []
        index = 0
        section_stack: list[str] = []

        for page_no, page in enumerate(pdf.pages, 1):
            # 先提取表格，避免文本与表格内容重复
            tables = page.find_tables()
            table_bboxes = [t.bbox for t in tables]

            # 提取表格内容
            for table in tables:
                extracted = table.extract()
                if extracted:
                    rows = [
                        [str(cell or "").strip() for cell in row]
                        for row in extracted
                    ]
                    blocks.append(TableBlock(
                        rows=rows, index=index,
                        section_path="/".join(section_stack)
                    ))
                    index += 1

            # 提取非表格区域文本
            words = page.extract_words(
                x_tolerance=3, y_tolerance=3,
                keep_blank_chars=False, use_text_flow=True
            )

            # 按行分组
            lines = self._group_words_to_lines(words, table_bboxes)

            for line_text in lines:
                if not line_text.strip():
                    continue

                level = self._detect_heading_level(line_text)
                if level > 0:
                    section_stack = section_stack[:level - 1]
                    section_stack.append(line_text.strip())

                blocks.append(TextBlock(
                    block_type=BlockType.HEADING if level > 0 else BlockType.PARAGRAPH,
                    text=line_text.strip(),
                    level=level,
                    index=index,
                    section_path="/".join(section_stack[:-1] if level > 0 else section_stack),
                    style_name=f"page_{page_no}",
                ))
                index += 1

        pdf.close()

        word_count = sum(len(b.text) for b in blocks if isinstance(b, TextBlock))
        meta = DocumentMeta(
            file_name=file_name,
            file_type="pdf",
            page_count=page_count,
            word_count=word_count,
            title=blocks[0].text[:100] if blocks else "",
        )
        logger.info("PDF解析完成", file_name=file_name,
                    pages=page_count, blocks=len(blocks))
        return ParsedDocument(
            meta=meta, blocks=blocks,
            raw_text=self._build_raw_text(blocks)
        )

    def _is_scanned(self, pdf: pdfplumber.PDF) -> bool:
        """抽样检测文字密度，低于阈值判定为扫描版"""
        sample_pages = list(pdf.pages[:min(3, len(pdf.pages))])
        densities = []
        for page in sample_pages:
            area = page.width * page.height
            words = page.extract_words()
            char_count = sum(len(w["text"]) for w in words)
            densities.append(char_count / area if area > 0 else 0)
        avg_density = sum(densities) / len(densities) if densities else 0
        return avg_density < self.TEXT_DENSITY_THRESHOLD

    def _group_words_to_lines(self, words: list, table_bboxes: list) -> list[str]:
        """将 pdfplumber words 按 Y 坐标分组为行，跳过表格区域"""
        if not words:
            return []

        def in_table(word: dict) -> bool:
            x0, y0, x1, y1 = word["x0"], word["top"], word["x1"], word["bottom"]
            for tx0, ty0, tx1, ty1 in table_bboxes:
                if x0 >= tx0 and x1 <= tx1 and y0 >= ty0 and y1 <= ty1:
                    return True
            return False

        words = [w for w in words if not in_table(w)]
        if not words:
            return []

        # 按 top 分组（容差 3pt）
        lines: list[list[str]] = []
        current_line: list[str] = [words[0]["text"]]
        current_y: float = words[0]["top"]
        for w in words[1:]:
            if abs(w["top"] - current_y) < 3:
                current_line.append(w["text"])
            else:
                lines.append(current_line)
                current_line = [w["text"]]
                current_y = w["top"]
        lines.append(current_line)
        return [" ".join(line) for line in lines]

    def _detect_heading_level(self, text: str) -> int:
        """基于正则检测标题级别"""
        for pattern, level in _HEADING_PATTERNS:
            if pattern.match(text.strip()):
                return level
        return 0
