from datetime import timedelta
import structlog
from minio import Minio
from minio.error import S3Error
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

_client: Minio | None = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
    return _client


async def init_minio() -> None:
    """启动时确保 Bucket 存在，设为私有（见 CLAUDE.md §4.4）"""
    client = get_minio()
    for bucket in [settings.minio_bucket_documents, settings.minio_bucket_reports]:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("MinIO Bucket 已创建", bucket=bucket)


def get_presigned_url(bucket: str, key: str, expires_seconds: int = 900) -> str:
    """
    生成带时效的私有访问 URL（有效期 ≤ 15分钟，见 CLAUDE.md §4.4）
    禁止直接暴露 MinIO 地址给前端
    """
    client = get_minio()
    return client.presigned_get_object(
        bucket, key, expires=timedelta(seconds=min(expires_seconds, 900))
    )
