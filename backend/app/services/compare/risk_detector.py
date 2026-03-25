"""
风险识别模块：在 LLM 语义分析基础上，叠加规则引擎二次判断
保障关键字段（金额/日期/期限/违约）100% 捕获率，见方案 §7.2
"""
import re
from dataclasses import dataclass
from app.models.compare_task import DiffLevel


@dataclass
class RiskSignal:
    keyword: str
    level:   DiffLevel
    reason:  str


# 风险关键词规则库（可扩展至数据库配置化）
RISK_RULES: list[tuple[re.Pattern, DiffLevel, str]] = [
    # CRITICAL 级
    (re.compile(r"金额|价款|合同价|总价|单价|付款|结算|发票"), DiffLevel.CRITICAL, "涉及金额/付款条款"),
    (re.compile(r"交货期|竣工|验收期限|完成时间|有效期|合同期"), DiffLevel.CRITICAL, "涉及期限条款"),
    (re.compile(r"违约|赔偿|罚款|索赔|责任|免责"), DiffLevel.CRITICAL, "涉及违约责任"),
    (re.compile(r"质量标准|技术指标|性能参数|化学成分|力学性能|钢级"), DiffLevel.CRITICAL, "涉及技术质量指标"),
    (re.compile(r"安全生产|职业危害|有害气体|防护|应急"), DiffLevel.CRITICAL, "涉及安全生产要求"),
    (re.compile(r"知识产权|保密|竞业|专利|著作权"), DiffLevel.CRITICAL, "涉及知识产权/保密"),
    # MAJOR 级
    (re.compile(r"甲方|乙方|丙方|发包方|承包方|供方|需方"), DiffLevel.MAJOR, "涉及合同主体"),
    (re.compile(r"交货地点|交付地点|收货地址|工厂地址"), DiffLevel.MAJOR, "涉及交货/交付地点"),
    (re.compile(r"争议解决|仲裁|管辖|法院"), DiffLevel.MAJOR, "涉及争议解决方式"),
    (re.compile(r"数量|重量|规格|型号|牌号"), DiffLevel.MAJOR, "涉及产品数量/规格"),
]


class RiskDetector:

    def detect(self, diff_item: dict) -> tuple[DiffLevel, list[str]]:
        """
        对单个差异项检测风险等级
        :return: (最终等级, 命中关键词列表)
        """
        # 合并 A/B 文本进行检测
        combined = " ".join(filter(None, [
            diff_item.get("doc_a_text", ""),
            diff_item.get("doc_b_text", ""),
        ]))

        # LLM 已给出的等级作为基础
        llm_level_str = diff_item.get("diff_level", "MINOR")
        llm_level = DiffLevel(llm_level_str) if llm_level_str in DiffLevel.__members__ else DiffLevel.MINOR

        signals: list[RiskSignal] = []
        for pattern, level, reason in RISK_RULES:
            if pattern.search(combined):
                keywords = pattern.findall(combined)
                signals.append(RiskSignal(
                    keyword=",".join(set(keywords[:3])),  # 最多取3个
                    level=level,
                    reason=reason,
                ))

        if not signals:
            return llm_level, []

        # 取规则引擎与 LLM 两者中更高的等级
        level_order = {DiffLevel.MINOR: 0, DiffLevel.MAJOR: 1, DiffLevel.CRITICAL: 2}
        rule_max_level = max(signals, key=lambda s: level_order[s.level]).level
        final_level = rule_max_level if level_order[rule_max_level] > level_order[llm_level] else llm_level

        risk_keywords = list({s.keyword for s in signals if s.level == DiffLevel.CRITICAL})
        return final_level, risk_keywords
