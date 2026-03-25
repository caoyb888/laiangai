from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import String, Text, Integer, DateTime, Enum, SmallInteger
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class TaskStatus(str, PyEnum):
    PENDING    = "pending"
    PROCESSING = "processing"
    DONE       = "done"
    FAILED     = "failed"


class DiffLevel(str, PyEnum):
    CRITICAL = "CRITICAL"
    MAJOR    = "MAJOR"
    MINOR    = "MINOR"


class DiffType(str, PyEnum):
    INSERT = "insert"
    DELETE = "delete"
    MODIFY = "modify"
    MOVE   = "move"


class CompareTask(Base, TimestampMixin):
    __tablename__ = "compare_tasks"

    creator_id:     Mapped[str]          = mapped_column(String(36), nullable=False, index=True)
    doc_a_id:       Mapped[str]          = mapped_column(String(36), nullable=False)
    doc_b_id:       Mapped[str]          = mapped_column(String(36), nullable=False)
    task_name:      Mapped[str | None]   = mapped_column(String(256))
    # compare_level 用 String 存储 SET 值（逗号分隔），SQLAlchemy 不直接支持 MySQL SET 类型
    compare_level:  Mapped[str]          = mapped_column(String(64), default="char,semantic,risk", nullable=False)
    status:         Mapped[TaskStatus]   = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True
    )
    progress:       Mapped[int]          = mapped_column(SmallInteger, default=0, nullable=False)
    error_msg:      Mapped[str | None]   = mapped_column(Text)
    started_at:     Mapped[datetime | None] = mapped_column(DateTime)
    finished_at:    Mapped[datetime | None] = mapped_column(DateTime)
    total_diffs:    Mapped[int | None]   = mapped_column(Integer)
    critical_diffs: Mapped[int | None]   = mapped_column(Integer)


class DiffItem(Base):
    """比对差异详情，无软删除（随任务生命周期管理）"""
    __tablename__ = "diff_items"

    id:             Mapped[str]          = mapped_column(String(36), primary_key=True)
    task_id:        Mapped[str]          = mapped_column(String(36), nullable=False, index=True)
    seq_no:         Mapped[int]          = mapped_column(Integer, nullable=False)
    diff_type:      Mapped[DiffType]     = mapped_column(Enum(DiffType), nullable=False)
    diff_level:     Mapped[DiffLevel]    = mapped_column(
        Enum(DiffLevel), default=DiffLevel.MINOR, nullable=False
    )
    doc_a_section:  Mapped[str | None]   = mapped_column(String(512))
    doc_a_para_idx: Mapped[int | None]   = mapped_column(Integer)
    doc_a_text:     Mapped[str | None]   = mapped_column(LONGTEXT)
    doc_b_section:  Mapped[str | None]   = mapped_column(String(512))
    doc_b_para_idx: Mapped[int | None]   = mapped_column(Integer)
    doc_b_text:     Mapped[str | None]   = mapped_column(LONGTEXT)
    semantic_desc:  Mapped[str | None]   = mapped_column(Text)
    risk_keywords:  Mapped[str | None]   = mapped_column(String(512))
    is_reviewed:    Mapped[bool]         = mapped_column(default=False, nullable=False)
    reviewer_note:  Mapped[str | None]   = mapped_column(Text)
    created_at:     Mapped[datetime]     = mapped_column(
        DateTime, server_default="CURRENT_TIMESTAMP", nullable=False
    )
