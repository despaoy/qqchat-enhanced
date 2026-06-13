"""QQ智能助手 - 后端主应用

整合所有模块，创建 FastAPI 应用实例。
路由按领域拆分到 api/ 下各模块，通过 APIRouter 挂载。
"""
import sys
from pathlib import Path
import os
import logging

# 确保 backend 根目录在 Python 路径中，支持跨包导入
_BACKEND_ROOT = Path(__file__).parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# 加载 .env 文件到环境变量（确保 worker 进程也能读取配置）
_env_path = _BACKEND_ROOT / ".env"
if _env_path.exists():
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _, _value = _line.partition("=")
                _key = _key.strip()
                _value = _value.strip()
                if _key and _key not in os.environ:
                    os.environ[_key] = _value

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 应用配置 + 增强模块全局实例
from app.config import (
    connection_pool, http_client_pool, backup_mgr, failover_mgr,
    access_control_mgr, async_task_queue, llm_optimizer,
    RESOURCE_POOL_AVAILABLE, BACKUP_MANAGER_AVAILABLE,
    FAILOVER_AVAILABLE, ACCESS_CONTROL_AVAILABLE,
    load_balancer_mgr, circuit_breaker_registry,
)
from db.adapter import db

logger = logging.getLogger("main")

# ── 导入所有 API 路由 ──
from api.stats import router as stats_router
from api.messages import router as messages_router
from api.generate import router as generate_router
from api.loras import router as loras_router
from api.training import router as training_router
from api.knowledge import router as knowledge_router
from api.models import router as models_router
from api.config import router as config_router
from api.auth import router as auth_router
from api.user_data import router as user_data_router
from api.enhanced import router as enhanced_router
from api.module import router as module_router
from api.claw import router as claw_router


# ═══════════════════════════════════════════
# 应用生命周期
# ═══════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    global connection_pool, http_client_pool, backup_mgr, failover_mgr, access_control_mgr

    logger.info("🚀 QQ智能助手后端服务启动中（增强版）...")

    # 初始化数据库
    try:
        db.init()
        logger.info("✅ 数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")

    # 初始化 Redis 缓存（可选，失败不影响服务）
    try:
        from cache.redis_client import get_redis, health_check
        if health_check():
            logger.info("✅ Redis 缓存连接正常")
        else:
            logger.warning("⚠️ Redis 缓存连接失败，将使用数据库直连模式")
    except Exception as e:
        logger.warning(f"Redis 缓存初始化跳过: {e}")

    if RESOURCE_POOL_AVAILABLE:
        try:
            from infra.resource_pool import ConnectionPool, HttpClientPool
            db_path = str(_BACKEND_ROOT / "qq_assistant.db")
            connection_pool = ConnectionPool(db_path, max_size=20)
            http_client_pool = HttpClientPool(max_connections=100)
            logger.info("✅ 资源池初始化完成")
        except Exception as e:
            logger.warning(f"资源池初始化失败: {e}")

    if BACKUP_MANAGER_AVAILABLE:
        try:
            from infra.backup_manager import BackupManager
            db_path = str(_BACKEND_ROOT / "qq_assistant.db")
            backup_mgr = BackupManager(db_path)
            import asyncio
            asyncio.create_task(backup_mgr.start_scheduled_backup())
            logger.info("✅ 备份管理器初始化完成")
        except Exception as e:
            logger.warning(f"备份管理器初始化失败: {e}")

    if FAILOVER_AVAILABLE:
        try:
            from infra.failover import FailoverManager, ProviderConfig, FailoverStrategy
            failover_mgr = FailoverManager(strategy=FailoverStrategy.AUTO_FAILOVER)

            # 注册 vLLM 推理 provider
            vllm_url = os.getenv("VLLM_BASE_URL", "http://localhost:8001")
            failover_mgr.add_provider(ProviderConfig(
                name="vllm_primary",
                priority=1,
                health_check_url=f"{vllm_url}/health",
            ))

            # 启动健康检查循环
            await failover_mgr.start()
            logger.info("✅ 故障转移管理器初始化完成（vLLM provider 已注册）")
        except Exception as e:
            logger.warning(f"故障转移管理器初始化失败: {e}")

    if ACCESS_CONTROL_AVAILABLE:
        try:
            from infra.access_control import AccessControlManager
            db_path = str(_BACKEND_ROOT / "qq_assistant.db")
            access_control_mgr = AccessControlManager(db_path)
            logger.info("✅ 访问控制管理器初始化完成")
        except Exception as e:
            logger.warning(f"访问控制管理器初始化失败: {e}")

    logger.info("✅ 增强版服务启动完成！")
    yield

    logger.info("👋 服务关闭中，清理资源...")
    if connection_pool:
        await connection_pool.close()
    if http_client_pool:
        await http_client_pool.close()
    if backup_mgr:
        backup_mgr.stop_scheduled_backup()
    if failover_mgr:
        await failover_mgr.stop()
    if async_task_queue:
        await async_task_queue.shutdown()
    if llm_optimizer:
        await llm_optimizer.close()
    logger.info("✅ 资源清理完成")


# ═══════════════════════════════════════════
# 创建应用
# ═══════════════════════════════════════════
app = FastAPI(
    title="QQ智能助手 API (增强版)",
    description="QQ智能助手后端服务API - 高并发/高可靠/高安全增强版",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 安全中间件（可通过环境变量控制开关） ──
import os

_SECURITY_ENABLED = os.getenv("SECURITY_MIDDLEWARE_ENABLED", "true").lower() == "true"

if _SECURITY_ENABLED:
    try:
        from middleware.security import (
            SecurityMiddleware,
            RateLimitMiddleware,
            InputValidationMiddleware,
            SecurityHeadersMiddleware,
            AuditLogMiddleware,
        )
        # 注意：Starlette 中间件按添加顺序的逆序执行，先添加的最后执行
        # 所以最外层（最先执行）的中间件最后添加
        app.add_middleware(AuditLogMiddleware)           # 最外层：审计日志
        app.add_middleware(InputValidationMiddleware)     # 输入验证
        app.add_middleware(RateLimitMiddleware)            # 限流
        app.add_middleware(SecurityMiddleware)             # 认证
        app.add_middleware(SecurityHeadersMiddleware)      # 安全头（最内层）
        logger.info("✅ 安全中间件已启用（认证+限流+输入验证+审计+安全头）")
    except ImportError as e:
        logger.warning(f"安全中间件导入失败，跳过: {e}")

# ── 挂载所有路由 ──
app.include_router(stats_router)
app.include_router(messages_router)
app.include_router(generate_router)
app.include_router(loras_router)
app.include_router(training_router)
app.include_router(knowledge_router)
app.include_router(models_router)
app.include_router(config_router)
app.include_router(auth_router)
app.include_router(user_data_router)
app.include_router(enhanced_router)
app.include_router(module_router)
app.include_router(claw_router)


# ═══════════════════════════════════════════
# 根路由 & 健康检查
# ═══════════════════════════════════════════
@app.get("/")
async def root():
    return {
        "name": "QQ智能助手 API (增强版)",
        "version": "2.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/ready")
async def readiness_check():
    try:
        from db.adapter import is_pg_mode
        if is_pg_mode():
            db.get_config()
        else:
            conn = db.get_connection()
            conn.execute("SELECT 1")
            conn.close()
        return {"status": "ready"}
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="database not ready")


# ═══════════════════════════════════════════
# 全局异常处理
# ═══════════════════════════════════════════
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"请求异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal Server Error",
            "message": "服务器内部错误",
        },
    )
