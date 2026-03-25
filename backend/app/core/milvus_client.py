"""
Milvus 客户端：连接管理与健康检查
Collection 的创建/获取逻辑见 app/services/vectorizer.py
"""
import structlog
from pymilvus import connections, utility

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


async def init_milvus() -> None:
    """启动时检查 Milvus 连接并确保 Collection 存在"""
    try:
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port,
        )
        logger.info(
            "Milvus 连接成功",
            host=settings.milvus_host,
            port=settings.milvus_port,
        )
        if not utility.has_collection(settings.milvus_collection_name):
            logger.info(
                "Milvus Collection 不存在，将在首次向量化时自动创建",
                collection=settings.milvus_collection_name,
            )
        else:
            logger.info(
                "Milvus Collection 已存在",
                collection=settings.milvus_collection_name,
            )
    except Exception as e:
        logger.warning("Milvus 连接失败，向量化功能暂不可用", error=str(e))


async def close_milvus() -> None:
    """应用关闭时断开 Milvus 连接"""
    try:
        connections.disconnect("default")
        logger.info("Milvus 连接已断开")
    except Exception as e:
        logger.warning("Milvus 断开连接失败", error=str(e))
