import asyncio
import os
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型，使 autogenerate 能识别表结构
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models.base import Base
import app.models.user          # noqa: F401
import app.models.document      # noqa: F401
import app.models.compare_task  # noqa: F401
import app.models.report        # noqa: F401
import app.models.audit         # noqa: F401

target_metadata = Base.metadata

# 从环境变量读取数据库 URL（见 CLAUDE.md §10.2）
def get_url() -> str:
    url = os.environ.get("DATABASE_URL", config.get_main_option("sqlalchemy.url", ""))
    return url


def run_migrations_offline() -> None:
    """离线模式：不需要真实数据库连接，直接生成 SQL 脚本"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：使用异步引擎，见 CLAUDE.md §5.1"""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
