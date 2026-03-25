FROM python:3.11-slim AS base

WORKDIR /app

# 安装系统依赖（Apache Tika 需要 Java）
RUN apt-get update && apt-get install -y \
    default-jre-headless \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 安装 Python 依赖（分层缓存：依赖层独立于代码层）
COPY pyproject.toml .
RUN uv pip install --system --no-cache \
    torch --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system --no-cache -r pyproject.toml

# ── 开发阶段（热重载，不预下载模型）──────────────────────────
FROM base AS dev
ENV APP_ENV=dev
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── 生产阶段 ────────────────────────────────────────────────
FROM base AS production

COPY app/ ./app/

# 预下载 BGE-M3 模型（构建时缓存，避免运行时下载，见 CLAUDE.md §2.1）
RUN python -c "\
from FlagEmbedding import BGEM3FlagModel; \
BGEM3FlagModel('BAAI/bge-m3', use_fp16=False, device='cpu')"

ENV APP_ENV=prod
EXPOSE 8000
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop"]
