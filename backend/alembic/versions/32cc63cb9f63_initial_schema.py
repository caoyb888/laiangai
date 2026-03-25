"""initial schema

Revision ID: 32cc63cb9f63
Revises:
Create Date: 2026-03-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "32cc63cb9f63"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 用户表 ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True, comment="UUID"),
        sa.Column("username", sa.String(64), nullable=False, unique=True, comment="用户名"),
        sa.Column("display_name", sa.String(128), nullable=False, comment="显示姓名"),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("department", sa.String(128), nullable=True, comment="所属部门"),
        sa.Column(
            "role",
            sa.Enum("admin", "reviewer", "viewer", name="userrole"),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="0"),
        comment="用户表",
    )

    # ── 文档表 ────────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True, comment="UUID"),
        sa.Column("uploader_id", sa.String(36), nullable=False, comment="上传用户ID"),
        sa.Column("file_name", sa.String(512), nullable=False, comment="原始文件名"),
        sa.Column("file_type", sa.Enum("docx", "doc", "pdf", "txt", name="filetype"), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=False, comment="字节数"),
        sa.Column("page_count", sa.Integer, nullable=True, comment="页数"),
        sa.Column("minio_key", sa.String(1024), nullable=False, comment="MinIO 对象路径"),
        sa.Column("checksum_md5", sa.String(32), nullable=False, comment="文件 MD5，防重复上传"),
        sa.Column(
            "parse_status",
            sa.Enum("pending", "processing", "done", "failed", name="parsestatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("parse_error", sa.Text, nullable=True, comment="解析失败原因"),
        sa.Column("category", sa.String(64), nullable=True, comment="文档分类"),
        sa.Column("title", sa.String(512), nullable=True, comment="解析出的文档标题"),
        sa.Column("word_count", sa.Integer, nullable=True, comment="解析后字数"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="0"),
        comment="文档表",
    )
    op.create_index("idx_uploader", "documents", ["uploader_id"])
    op.create_index("idx_checksum", "documents", ["checksum_md5"])
    op.create_index("idx_parse_status", "documents", ["parse_status"])

    # ── 文档解析内容表 ──────────────────────────────────────────────────────────
    op.create_table(
        "document_contents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False, unique=True),
        sa.Column("raw_text", mysql.LONGTEXT, nullable=False, comment="纯文本，用于字符级比对"),
        sa.Column("structured_json", mysql.LONGTEXT, nullable=False, comment="ParsedDocument JSON"),
        sa.Column("vector_ids", sa.Text, nullable=True, comment="Milvus 向量ID列表，JSON格式"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        comment="文档解析内容表",
    )
    op.create_index("idx_document", "document_contents", ["document_id"])

    # ── 比对任务表 ────────────────────────────────────────────────────────────
    op.create_table(
        "compare_tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("creator_id", sa.String(36), nullable=False, comment="发起用户ID"),
        sa.Column("doc_a_id", sa.String(36), nullable=False, comment="文档A（基准）"),
        sa.Column("doc_b_id", sa.String(36), nullable=False, comment="文档B（对比）"),
        sa.Column("task_name", sa.String(256), nullable=True, comment="任务名称"),
        sa.Column("compare_level", sa.String(64), nullable=False, server_default="char,semantic,risk"),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "done", "failed", name="taskstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("progress", sa.SmallInteger, nullable=False, server_default="0", comment="进度 0-100"),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("total_diffs", sa.Integer, nullable=True, comment="总差异数"),
        sa.Column("critical_diffs", sa.Integer, nullable=True, comment="重大差异数"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="0"),
        comment="比对任务表",
    )
    op.create_index("idx_creator", "compare_tasks", ["creator_id"])
    op.create_index("idx_status", "compare_tasks", ["status"])
    op.create_index("idx_docs", "compare_tasks", ["doc_a_id", "doc_b_id"])

    # ── 比对差异详情表 ─────────────────────────────────────────────────────────
    op.create_table(
        "diff_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("seq_no", sa.Integer, nullable=False, comment="差异序号，用于导航"),
        sa.Column("diff_type", sa.Enum("insert", "delete", "modify", "move", name="difftype"), nullable=False),
        sa.Column(
            "diff_level",
            sa.Enum("CRITICAL", "MAJOR", "MINOR", name="difflevel"),
            nullable=False,
            server_default="MINOR",
        ),
        sa.Column("doc_a_section", sa.String(512), nullable=True, comment="A文档章节路径"),
        sa.Column("doc_a_para_idx", sa.Integer, nullable=True, comment="A文档段落索引"),
        sa.Column("doc_a_text", mysql.LONGTEXT, nullable=True, comment="A文档片段原文"),
        sa.Column("doc_b_section", sa.String(512), nullable=True),
        sa.Column("doc_b_para_idx", sa.Integer, nullable=True),
        sa.Column("doc_b_text", mysql.LONGTEXT, nullable=True, comment="B文档片段原文"),
        sa.Column("semantic_desc", sa.Text, nullable=True, comment="LLM语义分析说明"),
        sa.Column("risk_keywords", sa.String(512), nullable=True, comment="命中的风险关键词，逗号分隔"),
        sa.Column("is_reviewed", sa.Boolean, nullable=False, server_default="0", comment="人工已审阅标记"),
        sa.Column("reviewer_note", sa.Text, nullable=True, comment="审阅备注"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        comment="比对差异详情表",
    )
    op.create_index("idx_task", "diff_items", ["task_id"])
    op.create_index("idx_task_level", "diff_items", ["task_id", "diff_level"])
    op.create_index("idx_seq", "diff_items", ["task_id", "seq_no"])

    # ── 报告表 ────────────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), nullable=False),
        sa.Column("creator_id", sa.String(36), nullable=False),
        sa.Column("report_format", sa.Enum("pdf", "docx", name="reportformat"), nullable=False),
        sa.Column("minio_key", sa.String(1024), nullable=False),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="0"),
        comment="导出报告表",
    )
    op.create_index("idx_task_reports", "reports", ["task_id"])

    # ── LLM 调用审计日志表（见 CLAUDE.md §4.3）──────────────────────────────
    op.create_table(
        "llm_audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("document_id", sa.String(36), nullable=True, comment="文档ID（非内容）"),
        sa.Column("provider", sa.String(32), nullable=False, comment="qianwen|deepseek"),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=True, comment="响应耗时毫秒"),
        sa.Column(
            "status",
            sa.Enum("success", "failed", "timeout", name="llmcallstatus"),
            nullable=False,
        ),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("desensitized", sa.Boolean, nullable=False, server_default="1", comment="是否已脱敏，必须为1"),
        sa.Column("called_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        comment="LLM调用审计日志，保留180天",
    )
    op.create_index("idx_llm_user", "llm_audit_log", ["user_id"])
    op.create_index("idx_llm_task", "llm_audit_log", ["task_id"])
    op.create_index("idx_called_at", "llm_audit_log", ["called_at"])

    # ── 操作审计日志表 ─────────────────────────────────────────────────────────
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(64), nullable=False, comment="UPLOAD_DOC|CREATE_TASK|EXPORT_REPORT|LOGIN..."),
        sa.Column("resource_type", sa.String(32), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("extra_json", sa.Text, nullable=True, comment="附加信息JSON（不含文档内容）"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        comment="操作审计日志",
    )
    op.create_index("idx_user_action", "operation_logs", ["user_id", "action"])
    op.create_index("idx_op_created_at", "operation_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("operation_logs")
    op.drop_table("llm_audit_log")
    op.drop_table("reports")
    op.drop_table("diff_items")
    op.drop_table("compare_tasks")
    op.drop_table("document_contents")
    op.drop_table("documents")
    op.drop_table("users")
