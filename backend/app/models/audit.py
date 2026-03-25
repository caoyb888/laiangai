from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import BigInteger, String, Integer, Enum, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class LlmCallStatus(str, PyEnum):
    SUCCESS = "success"
    FAILED  = "failed"
    TIMEOUT = "timeout"


class LlmAuditLog(Base):
    """
    LLM 调用审计日志，见 CLAUDE.md §4.3
    保留 180 天，不可被普通用户查询
    """
    __tablename__ = "llm_audit_log"

    id:                Mapped[int]               = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id:           Mapped[str]               = mapped_column(String(36), nullable=False, index=True)
    task_id:           Mapped[str | None]         = mapped_column(String(36), index=True)
    document_id:       Mapped[str | None]         = mapped_column(String(36))
    provider:          Mapped[str]               = mapped_column(String(32), nullable=False)
    model_name:        Mapped[str]               = mapped_column(String(64), nullable=False)
    prompt_tokens:     Mapped[int]               = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int]               = mapped_column(Integer, default=0, nullable=False)
    latency_ms:        Mapped[int | None]         = mapped_column(Integer)
    status:            Mapped[LlmCallStatus]      = mapped_column(Enum(LlmCallStatus), nullable=False)
    error_code:        Mapped[str | None]         = mapped_column(String(64))
    desensitized:      Mapped[bool]              = mapped_column(default=True, nullable=False)
    called_at:         Mapped[datetime]          = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)


class OperationLog(Base):
    """操作审计日志，禁止记录文档原始内容，见 CLAUDE.md §4.3"""
    __tablename__ = "operation_logs"

    id:            Mapped[int]           = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id:       Mapped[str | None]    = mapped_column(String(36))
    action:        Mapped[str]           = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str | None]    = mapped_column(String(32))
    resource_id:   Mapped[str | None]    = mapped_column(String(36))
    ip_address:    Mapped[str | None]    = mapped_column(String(45))
    user_agent:    Mapped[str | None]    = mapped_column(String(512))
    extra_json:    Mapped[str | None]    = mapped_column(Text)
    created_at:    Mapped[datetime]      = mapped_column(DateTime, server_default=func.now(), nullable=False, index=True)
