#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
try:
    from db.pg_database import sync_pg_db
    print("pg_database import: OK")
except ImportError as e:
    print(f"pg_database import: FAILED - {e}")

try:
    from db.pg_database import PgDatabase
    print("PgDatabase class import: OK")
except ImportError as e:
    print(f"PgDatabase class import: FAILED - {e}")

# Check if asyncpg is installed
try:
    import asyncpg
    print(f"asyncpg version: {asyncpg.__version__}")
except ImportError:
    print("asyncpg: NOT INSTALLED")

# Check if sqlalchemy async is available
try:
    from sqlalchemy.ext.asyncio import create_async_engine
    print("sqlalchemy.ext.asyncio: OK")
except ImportError as e:
    print(f"sqlalchemy.ext.asyncio: FAILED - {e}")
