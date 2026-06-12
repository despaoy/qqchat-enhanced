#!/usr/bin/env python3
"""检查数据库模式"""
import os
import sys
from pathlib import Path

# 加载 .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value

use_pg = os.getenv("USE_POSTGRESQL", "false").lower() == "true"
print(f"USE_POSTGRESQL env var: {os.getenv('USE_POSTGRESQL', 'not set')}")
print(f"USE_PG computed: {use_pg}")
print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'not set')}")

if use_pg:
    try:
        from db.pg_database import sync_pg_db
        db = sync_pg_db
        db.init()
        config = db.get_config()
        print(f"PG mode: OK, config keys: {len(config)}")
        print(f"botName from PG: {config.get('botName', 'N/A')}")
    except Exception as e:
        print(f"PG mode: FAILED - {e}")
else:
    try:
        from db.database import db
        config = db.get_config()
        print(f"SQLite mode: OK, config keys: {len(config)}")
        print(f"botName from SQLite: {config.get('botName', 'N/A')}")
    except Exception as e:
        print(f"SQLite mode: FAILED - {e}")
