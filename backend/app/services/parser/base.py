from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from enum import Enum


class BlockType(str, Enum):
    HEADING   = "heading"     # 标题
    PARAGRAPH = "paragraph"   # 普通段落
    TABLE     = "table"       # 表格
    LIST_ITEM = "list_item"   # 列表项


@dataclass
class TextBlock:
    block_type: BlockType
    text: str                          # 纯文本内容
    level: int = 0                     # 标题级别（1-6），其他为0
    index: int = 0                     # 在文档中的全局顺序索引
    section_path: str = ""             # 章节路径，如 "第一章/第一节"
    style_name: str = ""               # 原始样式名（Word 段落样式）


@dataclass
class TableBlock:
    rows: list[list[str]]              # 行列结构
    index: int = 0
    section_path: str = ""


@dataclass
class DocumentMeta:
    file_name: str
    file_type: str
    page_count: int | None = None
    word_count: int = 0
    title: str = ""
    author: str = ""


@dataclass
class ParsedDocument:
    """
    标准化解析结果，所有解析器必须返回此结构
    见 CLAUDE.md §5.4
    """
    meta: DocumentMeta
    blocks: list[TextBlock | TableBlock] = field(default_factory=list)
    raw_text: str = ""                 # 拼接所有文本块，用于字符级比对

    def get_text_blocks(self) -> list[TextBlock]:
        return [b for b in self.blocks if isinstance(b, TextBlock)]

    def get_table_blocks(self) -> list[TableBlock]:
        return [b for b in self.blocks if isinstance(b, TableBlock)]


class BaseParser(ABC):
    """
    所有解析器的抽象基类，见 CLAUDE.md §5.4
    """

    @abstractmethod
    async def parse(self, content: bytes, file_name: str) -> ParsedDocument:
        """
        解析文档内容
        :param content: 文件二进制内容
        :param file_name: 原始文件名
        :return: 标准化 ParsedDocument
        """
        ...

    def _build_raw_text(self, blocks: list[TextBlock | TableBlock]) -> str:
        """从 blocks 拼接纯文本"""
        parts = []
        for block in blocks:
            if isinstance(block, TextBlock):
                parts.append(block.text)
            elif isinstance(block, TableBlock):
                for row in block.rows:
                    parts.append(" | ".join(row))
        return "\n".join(parts)
