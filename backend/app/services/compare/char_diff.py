"""
字符级精确比对，使用 diff-match-patch 算法
目标准确率 ≥ 99.5%，见方案 §7.2
"""
from dataclasses import dataclass, field
from enum import Enum

import diff_match_patch as dmp_module
import structlog

logger = structlog.get_logger()


class DiffOp(str, Enum):
    EQUAL  = "equal"
    INSERT = "insert"
    DELETE = "delete"


@dataclass
class CharDiffSpan:
    """单个差异片段"""
    op:    DiffOp
    text:  str
    pos_a: int = 0    # 在文档A中的字符偏移
    pos_b: int = 0    # 在文档B中的字符偏移


@dataclass
class CharDiffResult:
    spans:         list[CharDiffSpan] = field(default_factory=list)
    total_changes: int = 0           # 变更字符数
    similarity:    float = 1.0       # 相似度 0-1


class CharDiffEngine:

    def __init__(self, cleanup_semantic: bool = True) -> None:
        self.dmp = dmp_module.diff_match_patch()
        self.dmp.Diff_Timeout = 10.0      # 超时10秒
        self.cleanup_semantic = cleanup_semantic

    def diff(self, text_a: str, text_b: str) -> CharDiffResult:
        """
        对两段文本执行字符级差异比对
        :param text_a: 基准文本（文档A）
        :param text_b: 对比文本（文档B）
        """
        if text_a == text_b:
            return CharDiffResult(
                spans=[CharDiffSpan(DiffOp.EQUAL, text_a)],
                total_changes=0,
                similarity=1.0,
            )

        diffs = self.dmp.diff_main(text_a, text_b)
        if self.cleanup_semantic:
            self.dmp.diff_cleanupSemantic(diffs)

        spans: list[CharDiffSpan] = []
        pos_a, pos_b = 0, 0
        total_change_chars = 0

        for op_code, text in diffs:
            if op_code == dmp_module.diff_match_patch.DIFF_EQUAL:
                spans.append(CharDiffSpan(DiffOp.EQUAL, text, pos_a, pos_b))
                pos_a += len(text)
                pos_b += len(text)
            elif op_code == dmp_module.diff_match_patch.DIFF_DELETE:
                spans.append(CharDiffSpan(DiffOp.DELETE, text, pos_a, pos_b))
                pos_a += len(text)
                total_change_chars += len(text)
            elif op_code == dmp_module.diff_match_patch.DIFF_INSERT:
                spans.append(CharDiffSpan(DiffOp.INSERT, text, pos_a, pos_b))
                pos_b += len(text)
                total_change_chars += len(text)

        total_len = max(len(text_a), len(text_b), 1)
        similarity = 1.0 - total_change_chars / total_len

        return CharDiffResult(
            spans=spans,
            total_changes=total_change_chars,
            similarity=round(similarity, 4),
        )

    def diff_paragraphs(
        self,
        paragraphs_a: list[str],
        paragraphs_b: list[str],
    ) -> list[dict]:
        """
        段落列表级别比对：先做段落对齐，再逐对 diff
        返回可直接写入 diff_items 表的结构列表
        """
        aligned = self._align_paragraphs(paragraphs_a, paragraphs_b)
        results = []
        seq = 0

        for pair in aligned:
            pa, pb = pair["a"], pair["b"]
            if pa is None:
                results.append({
                    "seq_no": seq, "diff_type": "insert",
                    "doc_a_text": None, "doc_b_text": pb,
                    "similarity": 0.0,
                })
            elif pb is None:
                results.append({
                    "seq_no": seq, "diff_type": "delete",
                    "doc_a_text": pa, "doc_b_text": None,
                    "similarity": 0.0,
                })
            else:
                result = self.diff(pa, pb)
                if result.similarity < 1.0:
                    results.append({
                        "seq_no": seq,
                        "diff_type": "modify",
                        "doc_a_text": pa,
                        "doc_b_text": pb,
                        "similarity": result.similarity,
                        "char_spans": [
                            {"op": s.op, "text": s.text}
                            for s in result.spans
                        ],
                    })
            seq += 1

        return results

    def _align_paragraphs(
        self,
        pa_list: list[str],
        pb_list: list[str],
    ) -> list[dict]:
        """
        LCS 动态规划段落对齐
        相似度 > 0.6 的段落视为对应段落
        """
        m, n = len(pa_list), len(pb_list)
        # 构建相似度矩阵
        sim_matrix: dict[tuple[int, int], float] = {}
        for i, a in enumerate(pa_list):
            for j, b in enumerate(pb_list):
                if a == b:
                    sim_matrix[(i, j)] = 1.0
                elif len(a) > 10 and len(b) > 10:
                    r = self.diff(a, b)
                    sim_matrix[(i, j)] = r.similarity

        # 简化：使用最长公共子序列思路
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                sim = sim_matrix.get((i - 1, j - 1), 0)
                if sim >= 0.6:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        # 回溯
        aligned: list[dict] = []
        i, j = m, n
        while i > 0 or j > 0:
            if i > 0 and j > 0 and sim_matrix.get((i - 1, j - 1), 0) >= 0.6:
                aligned.append({"a": pa_list[i - 1], "b": pb_list[j - 1]})
                i -= 1; j -= 1
            elif j > 0 and (i == 0 or dp[i][j - 1] >= dp[i - 1][j]):
                aligned.append({"a": None, "b": pb_list[j - 1]})
                j -= 1
            else:
                aligned.append({"a": pa_list[i - 1], "b": None})
                i -= 1

        aligned.reverse()
        return aligned
