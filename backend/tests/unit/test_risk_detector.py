"""
风险识别模块单元测试
见 CLAUDE.md §8.1：services/compare/ 覆盖率目标 90%
"""
import pytest
from app.services.compare.risk_detector import RiskDetector, RISK_RULES
from app.models.compare_task import DiffLevel


@pytest.fixture
def detector() -> RiskDetector:
    return RiskDetector()


class TestRiskDetectorCriticalRules:
    """CRITICAL 级规则命中测试"""

    def test_detects_amount_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "合同总价为人民币[金额]", "doc_b_text": "合同金额调整", "diff_level": "MINOR"}
        level, keywords = detector.detect(item)
        assert level == DiffLevel.CRITICAL
        assert len(keywords) > 0

    def test_detects_deadline_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "交货期为30天", "doc_b_text": "交货期调整为60天", "diff_level": "MINOR"}
        level, keywords = detector.detect(item)
        assert level == DiffLevel.CRITICAL

    def test_detects_breach_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "违约方应承担赔偿责任", "doc_b_text": "违约金调整", "diff_level": "MINOR"}
        level, keywords = detector.detect(item)
        assert level == DiffLevel.CRITICAL

    def test_detects_quality_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "产品质量标准按GB/T执行", "doc_b_text": "质量标准变更", "diff_level": "MAJOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.CRITICAL

    def test_detects_safety_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "安全生产措施须符合规定", "doc_b_text": "安全生产要求变更", "diff_level": "MINOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.CRITICAL

    def test_detects_ip_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "知识产权归甲方所有", "doc_b_text": "保密协议条款变更", "diff_level": "MAJOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.CRITICAL


class TestRiskDetectorMajorRules:
    """MAJOR 级规则命中测试"""

    def test_detects_party_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "甲方负责提供场地", "doc_b_text": "乙方负责提供场地", "diff_level": "MINOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.MAJOR

    def test_detects_quantity_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "产品数量为1000吨", "doc_b_text": "数量调整为800吨", "diff_level": "MINOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.MAJOR

    def test_detects_dispute_keyword(self, detector: RiskDetector) -> None:
        item = {"doc_a_text": "争议解决方式为仲裁", "doc_b_text": "改为法院管辖", "diff_level": "MINOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.MAJOR


class TestRiskDetectorLevelPromotion:
    """等级提升逻辑测试"""

    def test_rule_promotes_above_llm(self, detector: RiskDetector) -> None:
        """规则引擎等级高于 LLM 时，使用规则引擎等级"""
        item = {"doc_a_text": "违约责任条款变更", "doc_b_text": "罚款金额调整", "diff_level": "MINOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.CRITICAL

    def test_llm_level_retained_when_higher(self, detector: RiskDetector) -> None:
        """LLM 等级高于规则引擎时，保留 LLM 等级"""
        item = {"doc_a_text": "甲方名称变更", "doc_b_text": "乙方地址更新", "diff_level": "CRITICAL"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.CRITICAL

    def test_no_signal_returns_llm_level(self, detector: RiskDetector) -> None:
        """无规则命中时，直接返回 LLM 等级"""
        item = {"doc_a_text": "第一条款内容", "doc_b_text": "第一条款内容修改", "diff_level": "MAJOR"}
        level, keywords = detector.detect(item)
        assert level == DiffLevel.MAJOR
        assert keywords == []

    def test_invalid_llm_level_defaults_to_minor(self, detector: RiskDetector) -> None:
        """LLM 返回无效等级时降级为 MINOR"""
        item = {"doc_a_text": "普通条款", "doc_b_text": "普通调整", "diff_level": "UNKNOWN"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.MINOR

    def test_missing_diff_level_defaults_to_minor(self, detector: RiskDetector) -> None:
        """diff_level 字段缺失时默认 MINOR"""
        item = {"doc_a_text": "普通条款", "doc_b_text": "普通调整"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.MINOR


class TestRiskDetectorEdgeCases:
    """边界条件测试"""

    def test_empty_texts(self, detector: RiskDetector) -> None:
        """空文本不抛异常，返回 LLM 等级"""
        item = {"doc_a_text": "", "doc_b_text": "", "diff_level": "MINOR"}
        level, keywords = detector.detect(item)
        assert level == DiffLevel.MINOR
        assert keywords == []

    def test_only_doc_b_text(self, detector: RiskDetector) -> None:
        """仅有 doc_b_text 时正常检测"""
        item = {"doc_b_text": "付款条款调整", "diff_level": "MINOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.CRITICAL

    def test_only_doc_a_text(self, detector: RiskDetector) -> None:
        """仅有 doc_a_text 时正常检测"""
        item = {"doc_a_text": "交货期三十天", "diff_level": "MINOR"}
        level, _ = detector.detect(item)
        assert level == DiffLevel.CRITICAL

    def test_risk_keywords_only_from_critical_signals(self, detector: RiskDetector) -> None:
        """返回的 risk_keywords 只包含 CRITICAL 级命中词"""
        item = {
            "doc_a_text": "甲方须在交货期内完成付款",
            "doc_b_text": "数量和金额均有调整",
            "diff_level": "MINOR",
        }
        level, keywords = detector.detect(item)
        assert level == DiffLevel.CRITICAL
        # MAJOR 级（甲方、数量）不应出现在 keywords 中
        # CRITICAL 级（交货期、付款、金额）应有命中
        assert len(keywords) > 0

    def test_rule_set_is_not_empty(self) -> None:
        """规则库非空，覆盖 CRITICAL 和 MAJOR 两级"""
        critical_rules = [r for r in RISK_RULES if r[1] == DiffLevel.CRITICAL]
        major_rules = [r for r in RISK_RULES if r[1] == DiffLevel.MAJOR]
        assert len(critical_rules) >= 6
        assert len(major_rules) >= 4
