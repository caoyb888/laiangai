"""
审计日志模块单元测试
见 CLAUDE.md §4.3：禁止在日志中记录文档原始内容
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from app.core.audit import log_operation, BLOCKED_KEYS


def make_db(execute_side_effect: Exception | None = None) -> AsyncMock:
    """构造伪造的 AsyncSession"""
    db = AsyncMock()
    if execute_side_effect:
        db.execute.side_effect = execute_side_effect
    return db


class TestBlockedKeys:

    def test_blocked_keys_covers_content_fields(self) -> None:
        assert "content" in BLOCKED_KEYS
        assert "text" in BLOCKED_KEYS
        assert "raw_text" in BLOCKED_KEYS
        assert "doc_content" in BLOCKED_KEYS
        assert "body" in BLOCKED_KEYS

    def test_blocked_keys_is_frozenset(self) -> None:
        assert isinstance(BLOCKED_KEYS, frozenset)


class TestLogOperationSecurity:
    """验证 extra 中的敏感字段被过滤，见 CLAUDE.md §4.3"""

    @pytest.mark.asyncio
    async def test_blocks_text_field(self) -> None:
        db = make_db()
        await log_operation(db, "user-1", "TEST", extra={"text": "原始文档内容"})
        call_kwargs = db.execute.call_args[0][1]
        assert call_kwargs["extra"] is None  # 被过滤后 safe_extra 为空

    @pytest.mark.asyncio
    async def test_blocks_raw_text_field(self) -> None:
        db = make_db()
        await log_operation(db, "user-1", "TEST", extra={"raw_text": "原文"})
        call_kwargs = db.execute.call_args[0][1]
        assert call_kwargs["extra"] is None

    @pytest.mark.asyncio
    async def test_blocks_content_field(self) -> None:
        db = make_db()
        await log_operation(db, "user-1", "TEST", extra={"content": "文档内容"})
        call_kwargs = db.execute.call_args[0][1]
        assert call_kwargs["extra"] is None

    @pytest.mark.asyncio
    async def test_allows_safe_fields(self) -> None:
        db = make_db()
        await log_operation(db, "user-1", "TEST", extra={"file_size": 1024, "category": "contract"})
        call_kwargs = db.execute.call_args[0][1]
        parsed = json.loads(call_kwargs["extra"])
        assert parsed["file_size"] == 1024
        assert parsed["category"] == "contract"

    @pytest.mark.asyncio
    async def test_mixed_extra_filters_blocked_keeps_safe(self) -> None:
        db = make_db()
        await log_operation(
            db, "user-1", "TEST",
            extra={"file_size": 512, "raw_text": "原始内容", "doc_id": "abc"}
        )
        call_kwargs = db.execute.call_args[0][1]
        parsed = json.loads(call_kwargs["extra"])
        assert "raw_text" not in parsed
        assert parsed["file_size"] == 512
        assert parsed["doc_id"] == "abc"

    @pytest.mark.asyncio
    async def test_none_extra_yields_none(self) -> None:
        db = make_db()
        await log_operation(db, "user-1", "TEST", extra=None)
        call_kwargs = db.execute.call_args[0][1]
        assert call_kwargs["extra"] is None


class TestLogOperationFields:
    """验证所有字段正确传递到 SQL"""

    @pytest.mark.asyncio
    async def test_all_fields_passed(self) -> None:
        db = make_db()
        await log_operation(
            db,
            user_id="u-001",
            action="UPLOAD_DOC",
            resource_type="document",
            resource_id="d-123",
            extra={"file_name": "合同.docx"},
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )
        kw = db.execute.call_args[0][1]
        assert kw["user_id"] == "u-001"
        assert kw["action"] == "UPLOAD_DOC"
        assert kw["resource_type"] == "document"
        assert kw["resource_id"] == "d-123"
        assert kw["ip"] == "10.0.0.1"
        assert kw["user_agent"] == "Mozilla/5.0"

    @pytest.mark.asyncio
    async def test_minimal_call_no_error(self) -> None:
        """仅传必填字段不抛异常"""
        db = make_db()
        await log_operation(db, None, "SYSTEM_EVENT")
        assert db.execute.called

    @pytest.mark.asyncio
    async def test_none_user_id_allowed(self) -> None:
        db = make_db()
        await log_operation(db, None, "ANON_ACTION")
        kw = db.execute.call_args[0][1]
        assert kw["user_id"] is None


class TestLogOperationErrorHandling:
    """验证写入失败不影响主流程，见 CLAUDE.md §4.3"""

    @pytest.mark.asyncio
    async def test_db_error_does_not_raise(self) -> None:
        db = make_db(execute_side_effect=Exception("DB连接失败"))
        # 不应抛出异常
        await log_operation(db, "user-1", "TEST_ACTION")

    @pytest.mark.asyncio
    async def test_db_error_logs_error(self) -> None:
        db = make_db(execute_side_effect=Exception("超时"))
        with patch("app.core.audit.logger") as mock_logger:
            await log_operation(db, "user-1", "TEST_ACTION")
            mock_logger.error.assert_called_once()
            call_kwargs = mock_logger.error.call_args
            assert "action" in call_kwargs[1] or "TEST_ACTION" in str(call_kwargs)
