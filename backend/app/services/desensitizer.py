"""
内容脱敏服务
在任何内容发送至 LLM API 之前，必须调用此服务
见 CLAUDE.md §4.1，§4.2
"""
import re
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class DesensitizedChunk:
    """携带脱敏标记的文本块，用于传入 LLMClient"""
    text: str
    is_desensitized: bool = True      # 必须为 True，LLMClient 会检查此标记
    original_length: int = 0          # 原文长度（用于 token 估算）


class Desensitizer:
    """
    双重脱敏：正则规则 + NER（简版）
    见 CLAUDE.md §4.2
    """

    # ── 正则规则集（最低要求，见 CLAUDE.md §4.2）────────────────────────────
    _RULES: list[tuple[re.Pattern, str]] = [
        # 合同编号（含数字字母组合）
        (re.compile(r"\b[A-Z]{1,6}[-_]?\d{4}[-_]\d{3,8}\b"), "[合同编号]"),
        # 身份证号（18位）—— 优先于手机号/银行账号，避免被短模式截断
        (re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "[证件号]"),
        # 银行账号（16-19位数字）—— 优先于手机号
        (re.compile(r"(?<!\d)\d{16,19}(?!\d)"), "[银行账号]"),
        # 手机号
        (re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "[联系方式]"),
        # 固话
        (re.compile(r"(?<!\d)0\d{2,3}[-\s]?\d{7,8}(?!\d)"), "[联系方式]"),
        # 邮箱
        (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[邮箱]"),
        # 金额（含"万元""元"单位的数字）；保留货币符号前缀
        (re.compile(r"((?:人民币|[￥¥])?)\d{1,10}(?:[,，]\d{3})*(?:\.\d{1,2})?(?:万元|元|亿元)"), r"\1[金额]"),
        # IP 地址
        (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[内网地址]"),
    ]

    # 需要整体替换的企业名称关键词（可扩展）
    _COMPANY_KEYWORDS: list[str] = [
        "莱芜钢铁", "莱钢集团", "山钢集团", "济南钢铁",
        # 根据实际业务扩充
    ]

    def desensitize(self, text: str) -> DesensitizedChunk:
        """
        对文本执行脱敏处理
        :return: DesensitizedChunk（is_desensitized=True）
        """
        original_length = len(text)
        result = text

        # 1. 公司名称替换
        for keyword in self._COMPANY_KEYWORDS:
            result = result.replace(keyword, "[企业名称]")

        # 2. 正则规则替换
        for pattern, replacement in self._RULES:
            result = pattern.sub(replacement, result)

        # 3. 人名脱敏（简版：匹配"甲方代表：XXX"等上下文模式）
        result = self._desensitize_person_names(result)

        return DesensitizedChunk(
            text=result,
            is_desensitized=True,
            original_length=original_length,
        )

    def desensitize_batch(self, texts: list[str]) -> list[DesensitizedChunk]:
        return [self.desensitize(t) for t in texts]

    def _desensitize_person_names(self, text: str) -> str:
        """
        简版人名识别：匹配"甲方代表：XXX"、"签字人：XXX"等模式
        生产环境可替换为 FlagAI NER 模型精确识别
        """
        name_context_pattern = re.compile(
            r"((?:甲方|乙方|丙方|代表|经办人|签字人|授权人|联系人)[：:]\s*)"
            r"([\u4e00-\u9fff]{2,4})"
        )
        return name_context_pattern.sub(r"\1[姓名]", text)


# 全局单例
_desensitizer = Desensitizer()


def get_desensitizer() -> Desensitizer:
    return _desensitizer
