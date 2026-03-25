from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    database_url: str

    # Redis
    redis_url: str

    # MinIO
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket_documents: str = "lgdoc-documents"
    minio_bucket_reports: str   = "lgdoc-reports"
    minio_use_ssl: bool         = False

    # Milvus
    milvus_host: str            = "lgdoc-milvus"
    milvus_port: int            = 19530
    milvus_collection_name: str = "doc_vectors"

    # LLM（见 CLAUDE.md §4.1）
    llm_primary_provider: str   = "qianwen"
    llm_api_key_primary: str    = ""
    llm_api_key_backup: str     = ""
    llm_api_mock: bool          = False

    # 安全
    jwt_secret_key: str
    jwt_algorithm: str          = "HS256"
    jwt_expire_minutes: int     = 480

    # 业务
    semantic_similarity_threshold: float = 0.92
    max_file_size_mb: int       = 200
    max_file_pages: int         = 500
    audit_log_retention_days: int = 180

    # 应用
    app_env: str                = "dev"
    log_level: str              = "INFO"
    cors_origins: str           = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
