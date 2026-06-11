"""增强功能API"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException

from app.config import (
    LOAD_BALANCER_AVAILABLE,
    ASYNC_PROCESSOR_AVAILABLE,
    RESOURCE_POOL_AVAILABLE,
    CIRCUIT_BREAKER_AVAILABLE,
    BACKUP_MANAGER_AVAILABLE,
    FAILOVER_AVAILABLE,
    INPUT_VALIDATOR_AVAILABLE,
    ENCRYPTION_AVAILABLE,
    ACCESS_CONTROL_AVAILABLE,
    LLM_OPTIMIZER_AVAILABLE,
    load_balancer_mgr,
    async_task_queue,
    connection_pool,
    http_client_pool,
    circuit_breaker_registry,
    backup_mgr,
    failover_mgr,
    response_cache,
    rate_limiter,
    encryption_mgr,
    access_control_mgr,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/enhanced/status")
async def get_enhanced_status():
    """获取增强功能状态"""
    status = {
        "loadBalancer": LOAD_BALANCER_AVAILABLE,
        "asyncProcessor": ASYNC_PROCESSOR_AVAILABLE,
        "resourcePool": RESOURCE_POOL_AVAILABLE,
        "circuitBreaker": CIRCUIT_BREAKER_AVAILABLE,
        "backupManager": BACKUP_MANAGER_AVAILABLE,
        "failover": FAILOVER_AVAILABLE,
        "inputValidator": INPUT_VALIDATOR_AVAILABLE,
        "encryption": ENCRYPTION_AVAILABLE,
        "accessControl": ACCESS_CONTROL_AVAILABLE,
        "llmOptimizer": LLM_OPTIMIZER_AVAILABLE,
    }
    return {"success": True, "enhancedFeatures": status}


@router.get("/api/enhanced/stats")
async def get_enhanced_stats():
    """获取增强功能统计信息"""
    stats = {}

    if load_balancer_mgr:
        stats["loadBalancer"] = load_balancer_mgr.get_stats()

    if async_task_queue:
        stats["asyncProcessor"] = async_task_queue.get_queue_stats()

    if connection_pool:
        stats["connectionPool"] = connection_pool.get_pool_stats()

    if http_client_pool:
        stats["httpClientPool"] = http_client_pool.get_pool_stats()

    if circuit_breaker_registry:
        stats["circuitBreakers"] = circuit_breaker_registry.get_all_stats()

    if backup_mgr:
        stats["backup"] = backup_mgr.get_backup_stats()

    if failover_mgr:
        stats["failover"] = failover_mgr.get_failover_status()

    if response_cache:
        stats["responseCache"] = response_cache.stats()

    if rate_limiter:
        stats["rateLimiter"] = rate_limiter.get_stats()

    return {"success": True, "stats": stats}


# --- 负载均衡API ---

@router.get("/api/enhanced/load-balancer/stats")
async def get_load_balancer_stats():
    if not load_balancer_mgr:
        raise HTTPException(status_code=503, detail="负载均衡器不可用")
    return {"success": True, "stats": load_balancer_mgr.get_stats()}


# --- 熔断器API ---

@router.get("/api/enhanced/circuit-breaker/stats")
async def get_circuit_breaker_stats():
    if not circuit_breaker_registry:
        raise HTTPException(status_code=503, detail="熔断器不可用")
    return {"success": True, "stats": circuit_breaker_registry.get_all_stats()}


@router.post("/api/enhanced/circuit-breaker/{name}/reset")
async def reset_circuit_breaker(name: str):
    if not circuit_breaker_registry:
        raise HTTPException(status_code=503, detail="熔断器不可用")
    cb = circuit_breaker_registry.get(name)
    if cb:
        cb.reset()
        return {"success": True, "message": f"熔断器 {name} 已重置"}
    raise HTTPException(status_code=404, detail=f"熔断器 {name} 不存在")


# --- 备份管理API ---

@router.get("/api/enhanced/backups")
async def list_backups():
    if not backup_mgr:
        raise HTTPException(status_code=503, detail="备份管理器不可用")
    return {"success": True, "backups": backup_mgr.list_backups()}


@router.post("/api/enhanced/backups/create")
async def create_backup(backup_type: str = "full"):
    if not backup_mgr:
        raise HTTPException(status_code=503, detail="备份管理器不可用")
    try:
        if backup_type == "full":
            path = backup_mgr.create_full_backup()
        else:
            path = backup_mgr.create_incremental_backup()
        return {"success": True, "message": "备份创建成功", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/enhanced/backups/{backup_name}/restore")
async def restore_backup(backup_name: str):
    if not backup_mgr:
        raise HTTPException(status_code=503, detail="备份管理器不可用")
    try:
        backup_dir = Path(__file__).parent.parent / "backups"
        backup_path = backup_dir / backup_name
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="备份文件不存在")
        backup_mgr.restore(str(backup_path))
        return {"success": True, "message": "备份恢复成功"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 故障转移API ---

@router.get("/api/enhanced/failover/status")
async def get_failover_status():
    if not failover_mgr:
        raise HTTPException(status_code=503, detail="故障转移管理器不可用")
    return {"success": True, "status": failover_mgr.get_failover_status()}


# --- 缓存管理API ---

@router.get("/api/enhanced/cache/stats")
async def get_cache_stats():
    if not response_cache:
        raise HTTPException(status_code=503, detail="响应缓存不可用")
    return {"success": True, "stats": response_cache.get_stats()}


@router.post("/api/enhanced/cache/invalidate")
async def invalidate_cache(pattern: Optional[str] = None):
    if not response_cache:
        raise HTTPException(status_code=503, detail="响应缓存不可用")
    response_cache.invalidate(pattern)
    return {"success": True, "message": "缓存已清除"}


# --- 访问控制API ---

@router.get("/api/enhanced/access-control/keys")
async def list_api_keys():
    if not access_control_mgr:
        raise HTTPException(status_code=503, detail="访问控制不可用")
    return {"success": True, "keys": access_control_mgr.list_api_keys()}


@router.post("/api/enhanced/access-control/keys")
async def create_api_key(request: Request):
    if not access_control_mgr:
        raise HTTPException(status_code=503, detail="访问控制不可用")
    body = await request.json()
    role = body.get("role", "viewer")
    description = body.get("description", "")
    api_key = access_control_mgr.create_api_key(role, description)
    return {"success": True, "apiKey": api_key}


@router.delete("/api/enhanced/access-control/keys/{key_id}")
async def revoke_api_key(key_id: str):
    if not access_control_mgr:
        raise HTTPException(status_code=503, detail="访问控制不可用")
    access_control_mgr.revoke_api_key(key_id)
    return {"success": True, "message": "API Key已吊销"}


# --- 限流器API ---

@router.get("/api/enhanced/rate-limiter/stats")
async def get_rate_limiter_stats():
    if not rate_limiter:
        raise HTTPException(status_code=503, detail="限流器不可用")
    return {"success": True, "stats": rate_limiter.get_stats()}


# --- 异步任务队列API ---

@router.get("/api/enhanced/task-queue/stats")
async def get_task_queue_stats():
    if not async_task_queue:
        raise HTTPException(status_code=503, detail="异步任务队列不可用")
    return {"success": True, "stats": async_task_queue.get_queue_stats()}


# --- 加密管理API ---

@router.get("/api/enhanced/encryption/status")
async def get_encryption_status():
    if not encryption_mgr:
        raise HTTPException(status_code=503, detail="加密管理器不可用")
    return {"success": True, "available": True}
