"""
测试全局配置：设置必要的环境变量，避免 pydantic-settings 因缺失字段报错
见 CLAUDE.md §10.1：dev 环境允许 Mock 模式
"""
import os
import pytest

# 在导入任何 app 模块之前设置环境变量
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "test-access-key")
os.environ.setdefault("MINIO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-unit-tests-only")
os.environ.setdefault("LLM_API_MOCK", "true")
