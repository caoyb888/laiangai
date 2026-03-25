"""
操作审计日志工具，完整实现见任务 16（审计日志模块）。
此文件在任务 3 阶段提供 log_operation 接口占位。
"""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import OperationLog


async def log_operation(
    db: AsyncSession,
    user_id: str | None,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    extra: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    写入操作审计日志。
    extra 中禁止包含文档原始内容，见 CLAUDE.md §4.3
    """
    import json
    log = OperationLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_json=json.dumps(extra, ensure_ascii=False) if extra else None,
    )
    db.add(log)
    # 不主动 commit，由上层 get_db 依赖统一提交
