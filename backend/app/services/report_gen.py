"""
比对报告生成：支持导出 Word(.docx) 和 PDF 格式
报告格式符合集团文件规范，见方案 §4.2.5
"""
import io
import os
from datetime import datetime

from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import structlog

logger = structlog.get_logger()


class ReportGenerator:

    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "report_templates")

    # 差异等级颜色（见 CLAUDE.md §6.2 颜色体系）
    LEVEL_COLORS = {
        "CRITICAL": RGBColor(0xD3, 0x2F, 0x2F),
        "MAJOR":    RGBColor(0xF5, 0x7C, 0x00),
        "MINOR":    RGBColor(0x38, 0x8E, 0x3C),
    }

    async def generate_docx(self, report_data: dict) -> bytes:
        """生成 Word 格式报告"""
        doc = DocxDocument()

        # ── 封面 ──────────────────────────────────────────────────────────
        title_para = doc.add_heading("文档比对报告", level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph(f"任务名称：{report_data.get('task_name', '未命名')}")
        doc.add_paragraph(f"文档A：{report_data.get('doc_a_name', '')}")
        doc.add_paragraph(f"文档B：{report_data.get('doc_b_name', '')}")
        doc.add_paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        doc.add_page_break()

        # ── 摘要 ──────────────────────────────────────────────────────────
        doc.add_heading("一、比对摘要", level=1)
        summary = report_data.get("summary", {})
        summary_table = doc.add_table(rows=4, cols=2)
        summary_table.style = "Table Grid"
        rows_data = [
            ("总差异数", str(summary.get("total_diffs", 0))),
            ("重大差异（CRITICAL）", str(summary.get("critical_diffs", 0))),
            ("一般差异（MAJOR）", str(summary.get("major_diffs", 0))),
            ("格式差异（MINOR）", str(summary.get("minor_diffs", 0))),
        ]
        for i, (label, value) in enumerate(rows_data):
            summary_table.cell(i, 0).text = label
            summary_table.cell(i, 1).text = value

        doc.add_page_break()

        # ── 差异详情 ──────────────────────────────────────────────────────
        doc.add_heading("二、差异详情", level=1)
        for item in report_data.get("diff_items", []):
            level = item.get("diff_level", "MINOR")
            color = self.LEVEL_COLORS.get(level, RGBColor(0, 0, 0))

            # 差异标题（带颜色）
            p = doc.add_paragraph()
            run = p.add_run(f"[{level}] 差异 #{item.get('seq_no', 0) + 1}")
            run.bold = True
            run.font.color.rgb = color

            if item.get("doc_a_text"):
                doc.add_paragraph(f"原文：{item['doc_a_text'][:500]}")
            if item.get("doc_b_text"):
                doc.add_paragraph(f"修改后：{item['doc_b_text'][:500]}")
            if item.get("semantic_desc"):
                p = doc.add_paragraph()
                p.add_run("分析：").bold = True
                p.add_run(item["semantic_desc"])
            if item.get("risk_keywords"):
                p = doc.add_paragraph()
                p.add_run("风险关键词：").bold = True
                p.add_run(item["risk_keywords"])
            doc.add_paragraph("─" * 50)

        buf = io.BytesIO()
        doc.save(buf)
        return buf.getvalue()

    async def generate_pdf(self, report_data: dict) -> bytes:
        """生成 PDF 格式报告（使用 ReportLab）"""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=72, rightMargin=72, topMargin=72, bottomMargin=72
        )

        # 注册中文字体（需提前放置字体文件）
        font_path = os.path.join(self.TEMPLATE_DIR, "fonts", "SimSun.ttf")
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont("SimSun", font_path))
            base_font = "SimSun"
        else:
            base_font = "Helvetica"  # 退化到英文字体

        styles = getSampleStyleSheet()
        normal_style = ParagraphStyle(
            "NormalCN", parent=styles["Normal"],
            fontName=base_font, fontSize=10, leading=16
        )
        story = []
        story.append(Paragraph("莱钢集团 文档比对报告", styles["Title"]))
        story.append(Spacer(1, 20))

        # 摘要表格
        summary = report_data.get("summary", {})
        table_data = [
            ["项目", "数值"],
            ["总差异数", str(summary.get("total_diffs", 0))],
            ["重大差异", str(summary.get("critical_diffs", 0))],
            ["一般差异", str(summary.get("major_diffs", 0))],
        ]
        t = Table(table_data, colWidths=[200, 100])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("FONTNAME", (0, 0), (-1, -1), base_font),
        ]))
        story.append(t)

        doc.build(story)
        return buf.getvalue()
