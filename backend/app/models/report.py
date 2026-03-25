from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, BigInteger, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class ReportFormat(str, PyEnum):
    PDF  = "pdf"
    DOCX = "docx"


class Report(Base):
    """导出报告表，无 updated_at（报告不可变更）"""
    __tablename__ = "reports"

    id:            Mapped[str]             = mapped_column(String(36), primary_key=True)
    task_id:       Mapped[str]             = mapped_column(String(36), nullable=False, index=True)
    creator_id:    Mapped[str]             = mapped_column(String(36), nullable=False)
    report_format: Mapped[ReportFormat]    = mapped_column(Enum(ReportFormat), nullable=False)
    minio_key:     Mapped[str]             = mapped_column(String(1024), nullable=False)
    file_size:     Mapped[int | None]      = mapped_column(BigInteger)
    created_at:    Mapped[datetime]        = mapped_column(DateTime, server_default=func.now(), nullable=False)
    is_deleted:    Mapped[bool]            = mapped_column(default=False, nullable=False)
