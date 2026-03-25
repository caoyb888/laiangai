import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_client import LLMClient
from app.services.desensitizer import DesensitizedChunk


class TestLLMClientSecurity:
    """验证安全约束，见 CLAUDE.md §8.3"""

    @pytest.mark.asyncio
    async def test_rejects_undesensitized_chunk(self):
        """未脱敏内容必须被拒绝"""
        bad_chunk = DesensitizedChunk(text="原始内容", is_desensitized=False)
        with pytest.raises(ValueError, match="未脱敏"):
            await LLMClient.analyze_diff([bad_chunk])

    @pytest.mark.asyncio
    async def test_accepts_desensitized_chunk(self, monkeypatch):
        """正确脱敏后的内容可以被处理"""
        monkeypatch.setattr(
            "app.services.llm_client.LLMClient._call_with_retry",
            AsyncMock(return_value={"diff_level": "MINOR", "semantic_desc": "test", "risk_keywords": []})
        )
        good_chunk = DesensitizedChunk(text="已脱敏内容", is_desensitized=True)
        results = await LLMClient.analyze_diff([good_chunk])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_mock_mode_works(self, monkeypatch):
        """Mock 模式下不调用真实 API"""
        monkeypatch.setattr("app.services.llm_client.settings.llm_api_mock", True)
        chunk = DesensitizedChunk(text="测试", is_desensitized=True)
        results = await LLMClient.analyze_diff([chunk])
        assert "[MOCK]" in results[0]["semantic_desc"]

    @pytest.mark.asyncio
    async def test_rejects_multiple_chunks_with_one_undesensitized(self):
        """批量 chunks 中只要有一个未脱敏就整体拒绝"""
        chunks = [
            DesensitizedChunk(text="已脱敏", is_desensitized=True),
            DesensitizedChunk(text="未脱敏", is_desensitized=False),
        ]
        with pytest.raises(ValueError, match="未脱敏"):
            await LLMClient.analyze_diff(chunks)

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self):
        """空列表不触发任何 API 调用"""
        results = await LLMClient.analyze_diff([])
        assert results == []


class TestLLMClientParseResponse:
    """LLM 响应解析容错测试"""

    def test_parse_valid_json(self):
        result = LLMClient._parse_llm_response(
            '{"diff_level": "CRITICAL", "semantic_desc": "金额条款变更", "risk_keywords": ["金额"]}'
        )
        assert result["diff_level"] == "CRITICAL"
        assert result["risk_keywords"] == ["金额"]

    def test_parse_json_with_surrounding_text(self):
        """LLM 在 JSON 前后附加了说明文字"""
        result = LLMClient._parse_llm_response(
            '以下是分析结果：\n{"diff_level": "MAJOR", "semantic_desc": "条款变更", "risk_keywords": []}\n请参考。'
        )
        assert result["diff_level"] == "MAJOR"

    def test_parse_invalid_json_fallback(self):
        """JSON 解析失败时返回容错默认值，不抛异常"""
        result = LLMClient._parse_llm_response("无法解析的响应文本")
        assert result["diff_level"] == "MINOR"
        assert "risk_keywords" in result

    def test_mock_response_contains_mock_marker(self):
        result = LLMClient._mock_response("测试差异内容")
        assert "[MOCK]" in result["semantic_desc"]
        assert "[MOCK]" in result["risk_keywords"]
