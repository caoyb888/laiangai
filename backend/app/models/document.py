from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, BigInteger, Integer, Text, Enum, DateTime, func
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class FileType(str, PyEnum):
    DOCX = "docx"
    DOC  = "doc"
    PDF  = "pdf"
    TXT  = "txt"


class ParseStatus(str, PyEnum):
    PENDING    = "pending"
    PROCESSING = "processing"
    DONE       = "done"
    FAILED     = "failed"


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    uploader_id:  Mapped[str]           = mapped_column(String(36), nullable=False, index=True)
    file_name:    Mapped[str]           = mapped_column(String(512), nullable=False)
    file_type:    Mapped[FileType]      = mapped_column(Enum(FileType, values_callable=lambda x: [e.value for e in x]), nullable=False)
    file_size:    Mapped[int]           = mapped_column(BigInteger, nullable=False)
    page_count:   Mapped[int | None]    = mapped_column(Integer)
    minio_key:    Mapped[str]           = mapped_column(String(1024), nullable=False)
    checksum_md5: Mapped[str]           = mapped_column(String(32), nullable=False, index=True)
    parse_status: Mapped[ParseStatus]   = mapped_column(
        Enum(ParseStatus, values_callable=lambda x: [e.value for e in x]), default=ParseStatus.PENDING, nullable=False, index=True
    )
    parse_error:  Mapped[str | None]    = mapped_column(Text)
    category:     Mapped[str | None]    = mapped_column(String(64))
    title:        Mapped[str | None]    = mapped_column(String(512))
    word_count:   Mapped[int | None]    = mapped_column(Integer)


class DocumentContent(Base):
    """文档解析内容表，不含 is_deleted（内容随文档删除）"""
    __tablename__ = "document_contents"

    id:              Mapped[str]        = mapped_column(String(36), primary_key=True)
    document_id:     Mapped[str]        = mapped_column(String(36), nullable=False, unique=True, index=True)
    raw_text:        Mapped[str]        = mapped_column(LONGTEXT, nullable=False)
    structured_json: Mapped[str]        = mapped_column(LONGTEXT, nullable=False)
    vector_ids:      Mapped[str | None] = mapped_column(Text)
    created_at:      Mapped[datetime]   = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at:      Mapped[datetime]   = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
