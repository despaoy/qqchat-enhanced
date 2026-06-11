#!/usr/bin/env python3
"""QQ智能助手 - 后端启动入口

使用方式:
    python run.py               # 启动服务（端口8000）
    python run.py --port 8080   # 指定端口
    python run.py --reload      # 开发模式（热重载）
"""
import sys
import os
import multiprocessing
from pathlib import Path

# 确保 backend 根目录在 Python 路径中
_BACKEND_ROOT = Path(__file__).parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# 删除可能存在的旧 pycache，确保使用新模块结构
import shutil
for root, dirs, files in os.walk(str(_BACKEND_ROOT)):
    if '__pycache__' in dirs:
        shutil.rmtree(os.path.join(root, '__pycache__'), ignore_errors=True)
    dirs[:] = [d for d in dirs if d not in ('__pycache__', 'venv', '.git', 'models', 'data')]

import uvicorn


def main():
    import argparse
    parser = argparse.ArgumentParser(description="QQ智能助手后端服务")
    parser.add_argument("--port", type=int, default=8000, help="监听端口（默认8000）")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    args = parser.parse_args()

    worker_count = min(4, multiprocessing.cpu_count()) if sys.platform != 'win32' else 1

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=worker_count,
        limit_concurrency=500,
        timeout_keep_alive=30,
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    main()
