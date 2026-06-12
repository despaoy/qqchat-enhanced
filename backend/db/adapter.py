"""数据库适配器 - 统一访问接口

根据环境变量 USE_POSTGRESQL 自动选择数据库后端：
- USE_POSTGRESQL=true  → PostgreSQL (SyncPgAdapter)
- USE_POSTGRESQL=false → SQLite (默认)

所有 API 层应通过 `from db.adapter import db` 获取数据库实例。
"""
import os
import logging

logger = logging.getLogger(__name__)

_USE_PG = os.getenv("USE_POSTGRESQL", "false").lower() == "true"

if _USE_PG:
    try:
        from db.pg_database import sync_pg_db
        db = sync_pg_db
        logger.info("✅ 数据库适配器：PostgreSQL 模式（SyncPgAdapter）")
    except ImportError as e:
        logger.warning(f"PostgreSQL 模块导入失败，回退到 SQLite: {e}")
        from db.database import db
        _USE_PG = False
else:
    from db.database import db


def get_db():
    """获取当前活跃的数据库实例"""
    return db


def is_pg_mode() -> bool:
    """当前是否使用 PostgreSQL"""
    return _USE_PG
