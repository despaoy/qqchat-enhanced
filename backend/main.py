#!/usr/bin/env python3
"""QQ智能助手 - 后端主服务入口（向后兼容）

此文件保留用于向后兼容。新入口请使用 run.py。
实际应用逻辑已拆分到 app/main.py。
"""
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

if __name__ == "__main__":
    import uvicorn
    import multiprocessing
    worker_count = min(4, multiprocessing.cpu_count()) if sys.platform != 'win32' else 1
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=worker_count,
        limit_concurrency=500,
        timeout_keep_alive=30,
        timeout_graceful_shutdown=30,
    )
