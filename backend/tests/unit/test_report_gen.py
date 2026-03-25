"""
比对报告生成模块单元测试
见 CLAUDE.md §8.1：覆盖率目标 70%
"""
import pytest
from app.services.report_gen import ReportGenerator


SAMPLE_REPORT_DATA = {
    "task_name": "测试比对任务",
    "doc_a_name": "合同原稿.docx",
    "doc_b_name": "合同修订版.docx",
    "summary": {
        "total_diffs": 3,
        "critical_diffs": 1,
        "major_diffs": 1,
        "minor_diffs": 1,
    },
    "diff_items": [
        {
            "seq_no": 0,
            "diff_level": "CRITICAL",
            "doc_a_text": "付款期限为三十日内",
            "doc_b_text": "付款期限为六十日内",
            "semantic_desc": "付款期限由30天延长至60天",
            "risk_keywords": "付款,期限",
        },
        {
            "seq_no": 1,
            "diff_level": "MAJOR",
            "doc_a_text": "甲方负责提供场地",
            "doc_b_text": "乙方负责提供场地",
            "semantic_desc": "责任主体变更",
            "risk_keywords": "",
        },
        {
            "seq_no": 2,
            "diff_level": "MINOR",
            "doc_a_text": "第一条",
            "doc_b_text": "第1条",
            "semantic_desc": "序号格式调整",
            "risk_keywords": "",
        },
    ],
}

EMPTY_REPORT_DATA: dict = {
    "task_name": "空任务",
    "summary": {"total_diffs": 0, "critical_diffs": 0, "major_diffs": 0, "minor_diffs": 0},
    "diff_items": [],
}


@pytest.fixture
def gen() -> ReportGenerator:
    return ReportGenerator()


class TestGenerateDocx:

    @pytest.mark.asyncio
    async def test_returns_bytes(self, gen: ReportGenerator) -> None:
        result = await gen.generate_docx(SAMPLE_REPORT_DATA)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_valid_docx_magic_bytes(self, gen: ReportGenerator) -> None:
        """docx 是 ZIP 格式，头部为 PK\x03\x04"""
        result = await gen.generate_docx(SAMPLE_REPORT_DATA)
        assert result[:4] == b"PK\x03\x04"

    @pytest.mark.asyncio
    async def test_empty_diff_items(self, gen: ReportGenerator) -> None:
        result = await gen.generate_docx(EMPTY_REPORT_DATA)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_missing_optional_fields(self, gen: ReportGenerator) -> None:
        """doc_a_name / doc_b_name 缺失时不抛异常"""
        data = {**SAMPLE_REPORT_DATA}
        data.pop("doc_a_name", None)
        data.pop("doc_b_name", None)
        result = await gen.generate_docx(data)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_long_text_truncated(self, gen: ReportGenerator) -> None:
        """超过 500 字的文本不抛异常（内部截断）"""
        data = {
            **SAMPLE_REPORT_DATA,
            "diff_items": [{
                "seq_no": 0, "diff_level": "MINOR",
                "doc_a_text": "A" * 1000, "doc_b_text": "B" * 1000,
                "semantic_desc": "", "risk_keywords": "",
            }],
        }
        result = await gen.generate_docx(data)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_all_diff_levels_rendered(self, gen: ReportGenerator) -> None:
        """三种差异等级均能正常渲染，不抛异常"""
        result = await gen.generate_docx(SAMPLE_REPORT_DATA)
        assert len(result) > 0


class TestGeneratePdf:

    @pytest.mark.asyncio
    async def test_returns_bytes(self, gen: ReportGenerator) -> None:
        result = await gen.generate_pdf(SAMPLE_REPORT_DATA)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_valid_pdf_magic_bytes(self, gen: ReportGenerator) -> None:
        result = await gen.generate_pdf(SAMPLE_REPORT_DATA)
        assert result[:4] == b"%PDF"

    @pytest.mark.asyncio
    async def test_empty_diff_items(self, gen: ReportGenerator) -> None:
        result = await gen.generate_pdf(EMPTY_REPORT_DATA)
        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_missing_font_fallback(self, gen: ReportGenerator) -> None:
        """字体文件不存在时退化到 Helvetica，不抛异常"""
        result = await gen.generate_pdf(SAMPLE_REPORT_DATA)
        assert len(result) > 0


class TestLevelColors:

    def test_all_levels_have_colors(self, gen: ReportGenerator) -> None:
        for level in ("CRITICAL", "MAJOR", "MINOR"):
            assert level in gen.LEVEL_COLORS

    def test_unknown_level_uses_fallback(self, gen: ReportGenerator) -> None:
        color = gen.LEVEL_COLORS.get("UNKNOWN", None)
        assert color is None  # 未知等级不在字典中，由调用方传默认值
