"""
操作审计日志，见 CLAUDE.md §4.3
注意：禁止在日志中记录文档原始内容
"""
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

logger = structlog.get_logger()

# 禁止写入审计日志的字段名（可能包含文档原文），见 CLAUDE.md §4.3
BLOCKED_KEYS: frozenset[str] = frozenset({
    "content", "text", "raw_text", "doc_content", "body",
    "structured_json", "parsed_text", "ocr_text",
})


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
    记录用户操作审计日志。
    extra 中禁止包含文档原文内容，见 CLAUDE.md §4.3
    """
    # 安全检查：过滤掉可能包含文档内容的字段
    safe_extra: dict = {}
    if extra:
        safe_extra = {k: v for k, v in extra.items() if k not in BLOCKED_KEYS}

    try:
        await db.execute(text("""
            INSERT INTO operation_logs
              (user_id, action, resource_type, resource_id,
               ip_address, user_agent, extra_json)
            VALUES
              (:user_id, :action, :resource_type, :resource_id,
               :ip, :user_agent, :extra)
        """), {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "ip": ip_address,
            "user_agent": user_agent,
            "extra": json.dumps(safe_extra, ensure_ascii=False) if safe_extra else None,
        })
    except Exception as e:
        # 审计日志失败不影响主流程，但必须记录错误
        logger.error("操作审计日志写入失败", action=action, error=str(e))
