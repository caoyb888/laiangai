# CLAUDE.md — 莱钢集团 AI 文档比对系统开发规范

> 本文件是项目 AI 辅助开发的核心约束文件。所有代码生成、架构建议、重构操作均须遵守本文件规定，不得擅自偏离。如需修改本文件，须经项目负责人审批。

---

## 一、项目概况

| 字段 | 内容 |
|------|------|
| 项目名称 | 莱钢集团 AI 文档比对系统（一期） |
| 项目代号 | `lgsteel-doc-compare` |
| 当前阶段 | 一期开发（2026-03-25 至 2026-05-31） |
| 方案版本 | 解决方案 V1.1 |
| 核心目标 | 基于公共 LLM API + 本地向量引擎，实现多格式文档智能比对 |

---

## 二、技术栈约束

### 2.1 强制技术栈（不得替换）

| 层次 | 技术 | 版本要求 | 说明 |
|------|------|---------|------|
| 前端框架 | Vue 3 | ≥ 3.4 | Composition API，禁止使用 Options API |
| 前端组件库 | Element Plus | ≥ 2.6 | 禁止引入其他 UI 组件库混用 |
| 后端框架 | Python FastAPI | ≥ 0.110 | 全异步设计，禁止使用 Flask/Django |
| 文档解析-Word | python-docx | ≥ 1.1 | 配合 Apache Tika 使用 |
| 文档解析-PDF | pdfplumber | ≥ 0.10 | 文字版 PDF；扫描版走 OCR 分支 |
| 文档解析-通用 | Apache Tika | latest | 格式识别入口 |
| 向量模型 | BGE-M3 | latest stable | **本地部署，CPU 推理，禁止调用外部向量 API** |
| 向量数据库 | Milvus | ≥ 2.4 | 本地 Docker 部署 |
| 关系型数据库 | MySQL | 8.0.x | 禁止使用 PostgreSQL 或 SQLite（生产环境） |
| 缓存 | Redis | ≥ 7.2 | 会话、任务状态、热点结果缓存 |
| 对象存储 | MinIO | latest stable | 本地部署，禁止直接使用本地文件系统存储文档 |
| 容器化 | Docker + Docker Compose | Docker ≥ 26 | 一期不引入 Kubernetes |
| 包管理-前端 | pnpm | ≥ 9 | 禁止使用 npm / yarn |
| 包管理-后端 | uv | ≥ 0.4 | 禁止使用 pip 直接安装（CI 环境除外） |

### 2.2 LLM API 调用规范（关键约束）

**主用：** 通义千问 API（阿里云 DashScope）  
**备用：** DeepSeek API  
**禁止：** OpenAI API、Azure OpenAI、任何未经项目负责人审批的第三方 LLM 服务

```python
# ✅ 正确：通过统一的 LLMClient 调用，包含脱敏与审计
from app.services.llm_client import LLMClient
result = await LLMClient.analyze_diff(chunks=desensitized_chunks)

# ❌ 禁止：直接实例化 SDK 或硬编码 API Key
import dashscope
dashscope.api_key = "sk-xxx"  # 绝对禁止
```

**API Key 管理：**
- 所有 API Key 仅通过环境变量注入，格式：`LLM_API_KEY_PRIMARY` / `LLM_API_KEY_BACKUP`
- 禁止出现在任何代码文件、配置文件、日志输出、注释中
- `.env` 文件纳入 `.gitignore`，禁止提交到版本库
- 代码扫描：CI 流程中启用 `truffleHog` 或 `gitleaks` 检测密钥泄露

---

## 三、目录结构规范

```
lgsteel-doc-compare/
├── CLAUDE.md                    # 本文件
├── docker-compose.yml           # 全栈编排
├── docker-compose.dev.yml       # 开发环境覆盖
├── .env.example                 # 环境变量模板（不含真实值）
├── .gitignore
│
├── backend/                     # Python FastAPI 后端
│   ├── app/
│   │   ├── main.py              # 应用入口，仅做路由挂载
│   │   ├── config.py            # 配置读取（Pydantic Settings）
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── documents.py # 文档上传/管理接口
│   │   │   │   ├── compare.py   # 比对任务接口
│   │   │   │   ├── reports.py   # 报告导出接口
│   │   │   │   └── auth.py      # 认证接口
│   │   ├── services/
│   │   │   ├── parser/          # 文档解析服务
│   │   │   │   ├── base.py
│   │   │   │   ├── docx_parser.py
│   │   │   │   ├── pdf_parser.py
│   │   │   │   └── ocr_parser.py
│   │   │   ├── compare/         # 比对核心逻辑
│   │   │   │   ├── char_diff.py     # 字符级比对
│   │   │   │   ├── semantic_diff.py # 语义级比对
│   │   │   │   └── risk_detector.py # 风险识别
│   │   │   ├── llm_client.py    # LLM API 统一客户端（含脱敏、重试、切换）
│   │   │   ├── desensitizer.py  # 内容脱敏服务
│   │   │   ├── vectorizer.py    # BGE-M3 向量化服务
│   │   │   └── report_gen.py    # 报告生成服务
│   │   ├── models/              # SQLAlchemy ORM 模型
│   │   ├── schemas/             # Pydantic 请求/响应 Schema
│   │   ├── repositories/        # 数据库访问层
│   │   ├── core/
│   │   │   ├── security.py      # JWT、权限
│   │   │   ├── audit.py         # 操作审计日志
│   │   │   └── exceptions.py    # 统一异常定义
│   │   └── tasks/               # Celery/asyncio 异步任务
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/            # 测试用文档样本（脱敏处理后）
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic/                 # 数据库迁移
│
├── frontend/                    # Vue 3 前端
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/
│   │   ├── stores/              # Pinia 状态管理
│   │   ├── views/
│   │   │   ├── DocumentView.vue
│   │   │   ├── CompareView.vue  # 核心双栏比对页
│   │   │   └── ReportView.vue
│   │   ├── components/
│   │   │   ├── compare/
│   │   │   │   ├── DiffPanel.vue        # 双栏差异展示
│   │   │   │   ├── DiffNavigator.vue    # 差异导航条
│   │   │   │   └── RiskBadge.vue        # 风险等级标注
│   │   │   └── common/
│   │   ├── api/                 # Axios 请求封装
│   │   ├── utils/
│   │   └── types/               # TypeScript 类型定义
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
│
└── infra/
    ├── nginx/
    ├── mysql/
    │   └── init.sql
    └── milvus/
```

**目录约束：**
- 禁止在 `app/api/` 层直接写业务逻辑，接口层只做参数校验和调用 `services/`
- 禁止在 `services/` 层直接写 SQL，数据库操作统一走 `repositories/`
- 所有与 LLM 相关的调用，必须且只能通过 `services/llm_client.py`

---

## 四、数据安全与脱敏规范（最高优先级）

> ⚠️ 本节规范优先级高于所有开发便利性考量，违反将导致代码审查不通过。

### 4.1 脱敏必须在调用 LLM API 前完成

```python
# 必须遵循的调用链
raw_chunks = chunker.split(document_text)
desensitized = await desensitizer.process(raw_chunks)  # 步骤不可跳过
result = await llm_client.analyze(desensitized)        # 只发送脱敏后内容
```

### 4.2 脱敏字段清单（最低要求）

| 字段类型 | 脱敏规则 | 示例 |
|---------|---------|------|
| 公司全称 | 替换为 `[企业名称]` | 莱芜钢铁集团有限公司 → `[企业名称]` |
| 合同编号 | 替换为 `[合同编号]` | HT-2026-001 → `[合同编号]` |
| 人员姓名 | 替换为 `[姓名]` | 张三 → `[姓名]` |
| 金额数字（合同金额） | 替换为 `[金额]` | 人民币1,500万元 → `人民币[金额]` |
| 银行账号 | 完全替换 `[银行账号]` | — |
| 手机/电话 | 替换为 `[联系方式]` | — |
| 身份证号 | 完全替换 `[证件号]` | — |

> 脱敏逻辑实现在 `services/desensitizer.py`，使用正则 + NER 双重识别，禁止仅依赖其中一种。

### 4.3 API 调用审计

- 每次 LLM API 调用必须写入审计日志，记录：时间戳、调用方用户ID、文档ID（非内容）、Token消耗量、响应时长
- 审计日志表 `llm_audit_log` 保留 **180天**，不可被普通用户查询
- 禁止将文档原始内容写入任何日志文件

### 4.4 文档存储安全

- 所有上传文档存储在 MinIO，禁止存储在容器本地文件系统
- MinIO Bucket 设置为 **私有**，禁止公开访问
- 文档访问通过后端签名 URL（有效期 ≤ 15分钟），禁止前端直接访问 MinIO
- 文档传输全程 HTTPS，禁止 HTTP 明文传输

---

## 五、后端开发规范

### 5.1 Python 代码规范

- Python 版本：**3.11+**
- 格式化工具：`ruff format`（禁止使用 black/autopep8）
- Lint 工具：`ruff check`，配置见 `pyproject.toml`
- 类型注解：**所有函数必须有完整类型注解**，包括返回值
- 异步规范：IO 密集型操作（数据库、文件、HTTP）必须使用 `async/await`

```python
# ✅ 正确示例
async def get_compare_result(
    task_id: str,
    db: AsyncSession = Depends(get_db),
) -> CompareResultSchema:
    ...

# ❌ 禁止：无类型注解
def get_compare_result(task_id, db):
    ...

# ❌ 禁止：同步 IO 阻塞异步事件循环
def read_file(path):
    with open(path) as f:      # 应使用 aiofiles
        return f.read()
```

### 5.2 API 设计规范

- 所有接口前缀：`/api/v1/`
- 请求/响应统一使用 Pydantic Schema，禁止直接返回 ORM 对象
- 统一响应结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {},
  "request_id": "uuid"
}
```

- 错误码规范：

| 范围 | 含义 |
|------|------|
| 4000-4099 | 参数校验错误 |
| 4100-4199 | 认证/权限错误 |
| 4200-4299 | 业务逻辑错误 |
| 5000-5099 | 系统内部错误 |
| 5100-5199 | 外部服务错误（LLM API 等） |

### 5.3 数据库规范

- 所有表必须有 `id`（UUID）、`created_at`、`updated_at`、`is_deleted` 字段
- 禁止物理删除，一律使用软删除（`is_deleted = 1`）
- 数据库变更必须通过 Alembic 迁移脚本，禁止手动执行 DDL
- 字段命名：下划线命名法（`snake_case`）
- 涉及文档内容的字段类型使用 `LONGTEXT`，禁止 `TEXT`（MySQL 65KB 上限不够）

### 5.4 文档解析规范

```python
# 解析器必须继承 BaseParser 并实现 parse() 方法
class BaseParser(ABC):
    @abstractmethod
    async def parse(self, file_path: str) -> ParsedDocument:
        """返回标准化的 ParsedDocument，包含 sections、tables、metadata"""
        ...

# ParsedDocument 标准结构
@dataclass
class ParsedDocument:
    title: str
    sections: list[Section]      # 章节列表，保留层级
    tables: list[Table]          # 表格列表
    metadata: DocumentMeta       # 格式、页数、字数等
    raw_text: str                # 纯文本（用于字符级比对）
```

### 5.5 LLM 客户端规范

```python
class LLMClient:
    """
    统一 LLM 调用客户端，负责：
    1. 主/备 API 自动切换（主用通义千问，备用 DeepSeek）
    2. 指数退避重试（最多3次）
    3. Token 用量统计与限流
    4. 调用前验证脱敏是否已执行（通过标记位）
    """

    MAX_CHUNK_TOKENS = 2000      # 单次发送最大 Token 数
    MAX_RETRY = 3
    TIMEOUT_SECONDS = 30
```

- 禁止在 `LLMClient` 之外直接调用任何 LLM SDK
- 单次发送内容不超过 `MAX_CHUNK_TOKENS`，超出须分批
- 所有 Prompt 模板存放在 `app/services/prompts/` 目录，禁止在业务代码中硬编码 Prompt 字符串

---

## 六、前端开发规范

### 6.1 Vue 3 规范

- 全部使用 `<script setup lang="ts">` 语法，禁止 Options API
- 状态管理：Pinia，禁止使用 Vuex
- 路由：Vue Router 4，使用懒加载：`() => import('./views/CompareView.vue')`
- 组件命名：PascalCase，文件名与组件名一致
- Props 必须定义类型，禁止使用 `any`

```typescript
// ✅ 正确
const props = defineProps<{
  diffResult: DiffResult
  readOnly?: boolean
}>()

// ❌ 禁止
const props = defineProps(['diffResult', 'readOnly'])
```

### 6.2 差异展示组件规范（核心组件）

差异颜色体系为全项目统一标准，禁止局部修改：

```css
/* 定义在全局 CSS 变量中，所有组件引用变量，禁止硬编码颜色值 */
:root {
  --diff-delete-bg: #ffd7d7;     /* 删除：红色背景 */
  --diff-delete-text: #d32f2f;
  --diff-insert-bg: #d7ffd7;     /* 新增：绿色背景 */
  --diff-insert-text: #2e7d32;
  --diff-modify-bg: #fff9d7;     /* 修改：黄色背景 */
  --diff-modify-text: #f57f17;
  --diff-move-bg: #d7eaff;       /* 移动：蓝色背景 */
  --diff-move-text: #1565c0;
  --diff-risk-high: #d32f2f;     /* 风险等级颜色 */
  --diff-risk-medium: #f57c00;
  --diff-risk-low: #388e3c;
}
```

长文档渲染必须使用虚拟滚动（`vue-virtual-scroller`），禁止一次性渲染全部差异节点。

### 6.3 文件上传规范

```typescript
// 前端上传约束，必须在上传前校验
const ALLOWED_TYPES = [
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document', // .docx
  'application/msword',    // .doc
  'application/pdf',       // .pdf
  'text/plain',            // .txt
]
const MAX_FILE_SIZE_MB = 200

// 禁止：上传前不做类型和大小校验
```

### 6.4 HTTP 请求规范

- 所有请求通过统一的 `src/api/request.ts` axios 实例，禁止组件内直接 `fetch`/`axios`
- Token 在请求拦截器中统一注入，禁止在业务代码中手动添加 Authorization 头
- 错误处理在响应拦截器中统一处理，业务代码只处理成功响应

---

## 七、比对核心算法规范

### 7.1 三层比对流水线顺序

```
字符级比对（python-difflib / diff-match-patch）
        ↓ 结果作为候选差异集
段落级比对（BGE-M3 向量余弦相似度，阈值 < 0.92 视为差异）
        ↓ 合并字符级结果，过滤误报
语义级比对（LLM API，仅对段落级已标记的差异块执行）
        ↓ 输出差异分级 + 风险提示
最终比对结果
```

**约束：**
- 语义级比对（LLM 调用）仅对已被前两层标记的差异块执行，禁止对全文发送 LLM 分析
- 相似度阈值 0.92 为初始值，可通过配置文件调整，禁止硬编码在算法内部

### 7.2 差异分级标准

| 级别 | 标识 | 判定条件 |
|------|------|---------|
| 重大差异 | `CRITICAL` | 涉及金额、期限、违约责任、甲乙方权利义务等关键条款变更 |
| 一般差异 | `MAJOR` | 条款内容变更但不涉及核心权责 |
| 格式差异 | `MINOR` | 仅格式、标点、空白、序号等变化，无实质内容差异 |

### 7.3 性能约束

| 场景 | 响应时间目标 | 硬性上限 |
|------|------------|---------|
| 10页以内文档比对 | ≤ 3分钟 | 5分钟 |
| 50页以内文档比对 | ≤ 8分钟 | 15分钟 |
| 字符级比对（单独） | ≤ 10秒 | 30秒 |

超过软目标须在代码注释中说明原因，超过硬性上限须上报技术负责人。

---

## 八、测试规范

### 8.1 覆盖率要求

| 模块 | 最低覆盖率 |
|------|----------|
| `services/compare/` 比对核心 | **90%** |
| `services/desensitizer.py` 脱敏 | **95%** |
| `services/llm_client.py` | **85%** |
| `api/v1/` 接口层 | **80%** |
| 其余模块 | 70% |

### 8.2 测试文件规范

- 单元测试文件命名：`test_<被测文件名>.py`，放在 `tests/unit/`
- 集成测试：`tests/integration/`，需要真实数据库连接，使用测试数据库
- 测试用例文档：`tests/fixtures/` 中的文档样本须为**脱敏处理后**的虚构内容，禁止使用真实业务文档

### 8.3 LLM 调用 Mock

- 单元测试中**禁止真实调用 LLM API**，必须 Mock `LLMClient`
- 集成测试中使用 `LLM_API_MOCK=true` 环境变量切换到 Mock 模式

```python
# 测试中必须使用 Mock
@pytest.fixture
def mock_llm(monkeypatch):
    async def _mock_analyze(chunks):
        return MockDiffResult(diffs=[...])
    monkeypatch.setattr(LLMClient, "analyze_diff", _mock_analyze)
```

---

## 九、Git 工作流规范

### 9.1 分支策略

```
main          # 生产分支，只接受来自 release/* 的合并，tag 标记版本
develop       # 集成分支，功能完成后合并到此
feature/*     # 功能分支，命名如 feature/doc-parser-pdf
bugfix/*      # Bug 修复分支
release/*     # 发布准备分支，如 release/v1.0.0
```

- 禁止直接向 `main` 和 `develop` 提交，必须通过 PR/MR
- `main` 分支需要至少 1 人 Code Review 通过后才可合并

### 9.2 Commit Message 规范

格式：`<type>(<scope>): <subject>`

| type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不影响功能） |
| `test` | 测试相关 |
| `docs` | 文档更新 |
| `chore` | 构建/依赖/配置变更 |
| `perf` | 性能优化 |
| `security` | 安全相关修复 |

示例：
```
feat(compare): 实现段落级向量相似度比对
fix(desensitizer): 修复合同编号正则未匹配纯数字编号的问题
security(llm_client): 增加 API Key 使用前掩码校验
```

### 9.3 禁止提交内容

- `.env` 文件或任何含真实密钥的配置文件
- 真实业务文档（合同、规程等）
- 超过 10MB 的二进制文件（模型权重等通过独立渠道管理）
- 含有硬编码 IP 地址或内网域名的代码

CI 流程中配置 `gitleaks` 自动检测，检测失败将阻断 PR 合并。

---

## 十、部署与环境规范

### 10.1 环境分级

| 环境 | 说明 | 数据库 | LLM 调用 |
|------|------|-------|---------|
| `dev` | 本地开发 | SQLite 可选 | Mock 模式 |
| `test` | 集成测试 | MySQL（测试库） | Mock 模式 |
| `staging` | 预发布验证 | MySQL（独立库） | 真实 API，限流 |
| `prod` | 生产环境 | MySQL（生产库） | 真实 API |

### 10.2 环境变量清单

```bash
# 必须配置（无默认值）
DATABASE_URL=mysql+aiomysql://user:pass@host:3306/lgdoc
REDIS_URL=redis://:pass@host:6379/0
MINIO_ENDPOINT=host:9000
MINIO_ACCESS_KEY=
MINIO_SECRET_KEY=
LLM_API_KEY_PRIMARY=          # 通义千问 API Key
LLM_API_KEY_BACKUP=           # DeepSeek API Key（备用）
JWT_SECRET_KEY=               # 随机生成，≥ 32 字符
MILVUS_HOST=
MILVUS_PORT=19530

# 可选配置（有默认值）
LLM_PRIMARY_PROVIDER=qianwen  # qianwen | deepseek
LLM_API_MOCK=false            # true 时使用 Mock，禁止在 prod 设为 true
SEMANTIC_SIMILARITY_THRESHOLD=0.92
MAX_FILE_SIZE_MB=200
LOG_LEVEL=INFO
AUDIT_LOG_RETENTION_DAYS=180
```

### 10.3 Docker Compose 规范

- 服务命名：`lgdoc-frontend`、`lgdoc-backend`、`lgdoc-mysql`、`lgdoc-redis`、`lgdoc-minio`、`lgdoc-milvus`
- 所有服务必须配置 `restart: unless-stopped`
- 数据库、MinIO、Milvus 必须配置 `volumes` 持久化，禁止数据存储在容器层
- 生产环境禁止暴露 MySQL、Redis、MinIO、Milvus 端口到宿主机外网网卡

---

## 十一、一期开发禁止事项（DO NOT）

以下事项在一期开发周期内严格禁止，如有必要须升级为变更请求走审批流程：

| # | 禁止事项 | 原因 |
|---|---------|------|
| 1 | 引入 GPU 相关依赖或配置 | 一期全部走公共 API，GPU 规划在二期 |
| 2 | 实现 Excel 报表比对功能 | 二期范围 |
| 3 | 实现图纸/图片内容比对 | 二期范围 |
| 4 | 引入 Kubernetes 配置 | 一期 Docker Compose 足够，避免复杂度 |
| 5 | 接入 OA/ERP 系统 | 二期集成规划 |
| 6 | 前端存储文档内容到 localStorage/sessionStorage | 安全风险 |
| 7 | 日志中输出文档原始内容 | 数据安全 |
| 8 | 向未经审批的 LLM API 发送任何内容 | 合规风险 |
| 9 | 绕过 `LLMClient` 直接调用 LLM SDK | 架构约束 |
| 10 | 绕过 `desensitizer` 直接发送文档内容至 LLM | 最高优先级安全约束 |

---

## 十二、代码审查检查清单

PR 提交前，开发者自查；Reviewer 审查时逐项核对：

**安全类（必过）**
- [ ] 无 API Key、密码、内网地址硬编码
- [ ] LLM 调用前脱敏标记位已设置
- [ ] 无文档原始内容写入日志
- [ ] MinIO 文档访问通过签名 URL，非直接暴露

**功能类**
- [ ] 新增接口有对应的 Pydantic Schema 定义
- [ ] 数据库变更有 Alembic 迁移脚本
- [ ] 异步 IO 操作未阻塞事件循环
- [ ] 差异颜色使用 CSS 变量，未硬编码

**测试类**
- [ ] 核心模块覆盖率达标
- [ ] LLM 调用在测试中已 Mock
- [ ] 测试 fixtures 无真实业务文档

**规范类**
- [ ] Commit message 符合规范
- [ ] 无禁止事项中的功能代码
- [ ] 类型注解完整

---

## 十三、变更管理

本文件的任何修改须遵循以下流程：

1. 提交变更申请，说明修改原因和影响范围
2. 技术负责人审核技术合理性
3. 项目负责人审批
4. 更新本文件，在文件末尾追加变更记录

### 变更记录

| 版本 | 日期 | 变更内容 | 审批人 |
|------|------|---------|-------|
| V1.0 | 2026-03-25 | 初始版本，依据解决方案 V1.1 制定 | — |

---

*CLAUDE.md V1.0 | 项目：lgsteel-doc-compare | 创建于 2026-03-25*  
*本文件约束所有 AI 辅助代码生成行为，与项目代码同等重要，须纳入版本管理。*
