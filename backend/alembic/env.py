"""Alembic 环境配置 - 支持 PostgreSQL 异步迁移"""

import os
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从环境变量覆盖数据库URL
db_url = os.getenv("ALEMBIC_DATABASE_URL")
if not db_url:
    # 兼容 Dockerfile 中的 PG_* 环境变量，自动构建连接串
    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_user = os.getenv("PG_USER", "qqassistant")
    pg_password = os.getenv("PG_PASSWORD", "")
    pg_database = os.getenv("PG_DATABASE", "qqassistant")
    if pg_password:
        db_url = f"postgresql+asyncpg://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)


def run_migrations_offline() -> None:
    """离线模式 - 生成SQL脚本而不连接数据库"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """异步模式 - 使用 asyncpg 连接 PostgreSQL"""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """在线模式 - 连接数据库执行迁移"""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
