CREATE DATABASE IF NOT EXISTS lgdoc CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE lgdoc;

-- ── 用户表 ─────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id            VARCHAR(36)  NOT NULL PRIMARY KEY COMMENT 'UUID',
    username      VARCHAR(64)  NOT NULL UNIQUE      COMMENT '用户名',
    display_name  VARCHAR(128) NOT NULL              COMMENT '显示姓名',
    hashed_password VARCHAR(256) NOT NULL,
    department    VARCHAR(128)                       COMMENT '所属部门',
    role          ENUM('admin','reviewer','viewer') NOT NULL DEFAULT 'viewer',
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    last_login_at DATETIME,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted    TINYINT(1)   NOT NULL DEFAULT 0
) COMMENT='用户表';

-- ── 文档表 ─────────────────────────────────────────────────────────────────
CREATE TABLE documents (
    id            VARCHAR(36)   NOT NULL PRIMARY KEY COMMENT 'UUID',
    uploader_id   VARCHAR(36)   NOT NULL              COMMENT '上传用户ID',
    file_name     VARCHAR(512)  NOT NULL              COMMENT '原始文件名',
    file_type     ENUM('docx','doc','pdf','txt') NOT NULL,
    file_size     BIGINT        NOT NULL              COMMENT '字节数',
    page_count    INT                                 COMMENT '页数',
    minio_key     VARCHAR(1024) NOT NULL              COMMENT 'MinIO 对象路径',
    checksum_md5  VARCHAR(32)   NOT NULL              COMMENT '文件 MD5，防重复上传',
    parse_status  ENUM('pending','processing','done','failed') NOT NULL DEFAULT 'pending',
    parse_error   TEXT                                COMMENT '解析失败原因',
    category      VARCHAR(64)                         COMMENT '文档分类：contract/process/regulation/other',
    title         VARCHAR(512)                        COMMENT '解析出的文档标题',
    word_count    INT                                 COMMENT '解析后字数',
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted    TINYINT(1)    NOT NULL DEFAULT 0,
    INDEX idx_uploader (uploader_id),
    INDEX idx_checksum (checksum_md5),
    INDEX idx_parse_status (parse_status)
) COMMENT='文档表';

-- ── 文档解析内容表（存结构化文本，不存原始文件）──────────────────────────────
CREATE TABLE document_contents (
    id            VARCHAR(36)   NOT NULL PRIMARY KEY,
    document_id   VARCHAR(36)   NOT NULL UNIQUE,
    raw_text      LONGTEXT      NOT NULL COMMENT '纯文本，用于字符级比对',
    structured_json LONGTEXT    NOT NULL COMMENT 'ParsedDocument JSON：章节/段落/表格',
    vector_ids    TEXT                   COMMENT 'Milvus 向量ID列表，JSON格式',
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_document (document_id)
) COMMENT='文档解析内容表';

-- ── 比对任务表 ──────────────────────────────────────────────────────────────
CREATE TABLE compare_tasks (
    id              VARCHAR(36)  NOT NULL PRIMARY KEY,
    creator_id      VARCHAR(36)  NOT NULL               COMMENT '发起用户ID',
    doc_a_id        VARCHAR(36)  NOT NULL               COMMENT '文档A（基准）',
    doc_b_id        VARCHAR(36)  NOT NULL               COMMENT '文档B（对比）',
    task_name       VARCHAR(256)                        COMMENT '任务名称',
    compare_level   SET('char','semantic','risk') NOT NULL DEFAULT 'char,semantic,risk',
    status          ENUM('pending','processing','done','failed') NOT NULL DEFAULT 'pending',
    progress        TINYINT      NOT NULL DEFAULT 0     COMMENT '进度 0-100',
    error_msg       TEXT,
    started_at      DATETIME,
    finished_at     DATETIME,
    total_diffs     INT                                 COMMENT '总差异数',
    critical_diffs  INT                                 COMMENT '重大差异数',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_deleted      TINYINT(1)   NOT NULL DEFAULT 0,
    INDEX idx_creator (creator_id),
    INDEX idx_status (status),
    INDEX idx_docs (doc_a_id, doc_b_id)
) COMMENT='比对任务表';

-- ── 比对结果详情表 ───────────────────────────────────────────────────────────
CREATE TABLE diff_items (
    id              VARCHAR(36)  NOT NULL PRIMARY KEY,
    task_id         VARCHAR(36)  NOT NULL,
    seq_no          INT          NOT NULL               COMMENT '差异序号，用于导航',
    diff_type       ENUM('insert','delete','modify','move') NOT NULL,
    diff_level      ENUM('CRITICAL','MAJOR','MINOR')   NOT NULL DEFAULT 'MINOR',
    -- 位置信息
    doc_a_section   VARCHAR(512)                        COMMENT 'A文档章节路径',
    doc_a_para_idx  INT                                 COMMENT 'A文档段落索引',
    doc_a_text      LONGTEXT                            COMMENT 'A文档片段原文',
    doc_b_section   VARCHAR(512),
    doc_b_para_idx  INT,
    doc_b_text      LONGTEXT                            COMMENT 'B文档片段原文',
    -- AI 分析结果
    semantic_desc   TEXT                                COMMENT 'LLM语义分析说明',
    risk_keywords   VARCHAR(512)                        COMMENT '命中的风险关键词，逗号分隔',
    is_reviewed     TINYINT(1)   NOT NULL DEFAULT 0    COMMENT '人工已审阅标记',
    reviewer_note   TEXT                                COMMENT '审阅备注',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task (task_id),
    INDEX idx_task_level (task_id, diff_level),
    INDEX idx_seq (task_id, seq_no)
) COMMENT='比对差异详情表';

-- ── 报告表 ──────────────────────────────────────────────────────────────────
CREATE TABLE reports (
    id              VARCHAR(36)  NOT NULL PRIMARY KEY,
    task_id         VARCHAR(36)  NOT NULL,
    creator_id      VARCHAR(36)  NOT NULL,
    report_format   ENUM('pdf','docx') NOT NULL,
    minio_key       VARCHAR(1024) NOT NULL,
    file_size       BIGINT,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted      TINYINT(1)   NOT NULL DEFAULT 0,
    INDEX idx_task (task_id)
) COMMENT='导出报告表';

-- ── LLM 调用审计日志表（见 CLAUDE.md §4.3）─────────────────────────────────
CREATE TABLE llm_audit_log (
    id              BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(36)  NOT NULL,
    task_id         VARCHAR(36),
    document_id     VARCHAR(36)  COMMENT '文档ID（非内容）',
    provider        VARCHAR(32)  NOT NULL               COMMENT 'qianwen|deepseek',
    model_name      VARCHAR(64)  NOT NULL,
    prompt_tokens   INT          NOT NULL DEFAULT 0,
    completion_tokens INT        NOT NULL DEFAULT 0,
    latency_ms      INT                                 COMMENT '响应耗时毫秒',
    status          ENUM('success','failed','timeout') NOT NULL,
    error_code      VARCHAR(64),
    desensitized    TINYINT(1)   NOT NULL DEFAULT 1    COMMENT '是否已脱敏，必须为1',
    called_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user (user_id),
    INDEX idx_task (task_id),
    INDEX idx_called_at (called_at)
) COMMENT='LLM调用审计日志，保留180天';

-- ── 操作审计日志表 ───────────────────────────────────────────────────────────
CREATE TABLE operation_logs (
    id              BIGINT       NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id         VARCHAR(36),
    action          VARCHAR(64)  NOT NULL COMMENT 'UPLOAD_DOC|CREATE_TASK|EXPORT_REPORT|LOGIN...',
    resource_type   VARCHAR(32),
    resource_id     VARCHAR(36),
    ip_address      VARCHAR(45),
    user_agent      VARCHAR(512),
    extra_json      TEXT                                COMMENT '附加信息JSON（不含文档内容）',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_action (user_id, action),
    INDEX idx_created_at (created_at)
) COMMENT='操作审计日志';
