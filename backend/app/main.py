from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.config import get_settings
from app.core.db import init_db
from app.core.minio_client import init_minio
from app.core.milvus_client import init_milvus
from app.api.v1 import auth, documents, compare, reports
from app.api.v1 import settings as settings_router

logger = structlog.get_logger()
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    logger.info("启动中：初始化数据库连接")
    await init_db()
    logger.info("启动中：初始化 MinIO Bucket")
    await init_minio()
    logger.info("启动中：初始化 Milvus Collection")
    await init_milvus()
    logger.info("服务启动完成")
    yield
    logger.info("服务关闭")


app = FastAPI(
    title="莱钢集团 AI 文档比对系统",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_env != "prod" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["认证"])
app.include_router(documents.router, prefix="/api/v1/documents",  tags=["文档管理"])
app.include_router(compare.router,   prefix="/api/v1/compare",    tags=["比对任务"])
app.include_router(reports.router,   prefix="/api/v1/reports",    tags=["报告导出"])
app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["运行时配置"])
