"""
模块模式管理API
提供训练/推理模式切换、内存监控、模块状态查询
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.module_manager import get_module_manager, SystemMode, MemoryMonitor

logger = logging.getLogger(__name__)
router = APIRouter()


class SwitchModeRequest(BaseModel):
    target_mode: str  # "training" or "inference"


class SwitchModeResponse(BaseModel):
    success: bool
    from_mode: str
    to_mode: str
    switch_time_ms: float
    memory_freed_gb: float
    message: str
    errors: list[str] = []


class MemoryInfoResponse(BaseModel):
    total_gb: float
    available_gb: float
    used_gb: float
    percent: float
    gpu_total_gb: float = 0
    gpu_used_gb: float = 0
    gpu_available_gb: float = 0
    gpu_percent: float = 0


class ModuleStatusResponse(BaseModel):
    mode: str
    memory: MemoryInfoResponse
    inference_model_loaded: bool
    inference_model_name: str = ""
    active_lora: str = ""
    training_active: bool = False
    generation_active: bool = False
    uptime_seconds: float = 0
    can_switch_to_inference: bool = False
    can_switch_reason: str = ""


@router.get("/api/module/status")
async def get_module_status():
    """获取当前模块状态"""
    mgr = await get_module_manager()
    status = mgr.get_status()

    # 检查是否可以切换到推理模式
    can_switch, reason = MemoryMonitor.can_load_inference_model()

    return ModuleStatusResponse(
        mode=status.mode,
        memory=MemoryInfoResponse(
            total_gb=round(status.memory.total_gb, 2),
            available_gb=round(status.memory.available_gb, 2),
            used_gb=round(status.memory.used_gb, 2),
            percent=round(status.memory.percent, 1),
            gpu_total_gb=round(status.memory.gpu_total_gb, 2),
            gpu_used_gb=round(status.memory.gpu_used_gb, 2),
            gpu_available_gb=round(status.memory.gpu_available_gb, 2),
            gpu_percent=round(status.memory.gpu_percent, 1),
        ),
        inference_model_loaded=status.inference_model_loaded,
        inference_model_name=status.inference_model_name,
        active_lora=status.active_lora,
        training_active=status.training_active,
        generation_active=status.generation_active,
        uptime_seconds=status.uptime_seconds,
        can_switch_to_inference=can_switch,
        can_switch_reason=reason,
    )


@router.post("/api/module/switch", response_model=SwitchModeResponse)
async def switch_mode(request: SwitchModeRequest):
    """切换系统模式"""
    mgr = await get_module_manager()

    if request.target_mode not in ("training", "inference"):
        raise HTTPException(status_code=400, detail=f"无效的模式: {request.target_mode}")

    if mgr.is_switching:
        raise HTTPException(status_code=409, detail="模式切换正在进行中，请稍后")

    if request.target_mode == "training":
        result = await mgr.switch_to_training()
    else:
        result = await mgr.switch_to_inference()

    if not result.success:
        # 不抛异常，返回结果让前端显示原因
        pass

    return SwitchModeResponse(
        success=result.success,
        from_mode=result.from_mode,
        to_mode=result.to_mode,
        switch_time_ms=result.switch_time_ms,
        memory_freed_gb=result.memory_freed_gb,
        message=result.message,
        errors=result.errors,
    )


@router.get("/api/module/memory")
async def get_memory_info():
    """获取内存使用详情"""
    info = MemoryMonitor.get_memory_info()
    can_inference, reason = MemoryMonitor.can_load_inference_model()
    is_safe = MemoryMonitor.is_memory_safe()

    return {
        "system": {
            "total_gb": round(info.total_gb, 2),
            "available_gb": round(info.available_gb, 2),
            "used_gb": round(info.used_gb, 2),
            "percent": round(info.percent, 1),
        },
        "gpu": {
            "total_gb": round(info.gpu_total_gb, 2),
            "used_gb": round(info.gpu_used_gb, 2),
            "available_gb": round(info.gpu_available_gb, 2),
            "percent": round(info.gpu_percent, 1),
        } if info.gpu_total_gb > 0 else None,
        "safety": {
            "is_safe": is_safe,
            "can_load_inference_model": can_inference,
            "reason": reason,
        },
    }


@router.post("/api/module/gc")
async def force_garbage_collection():
    """强制垃圾回收，释放内存"""
    from app.module_manager import MemoryMonitor
    mem_before = MemoryMonitor.get_memory_info()
    MemoryMonitor.force_gc()
    mem_after = MemoryMonitor.get_memory_info()

    freed = round(mem_before.used_gb - mem_after.used_gb, 2)
    return {
        "success": True,
        "memory_freed_gb": max(0, freed),
        "before": {
            "used_gb": round(mem_before.used_gb, 2),
            "percent": round(mem_before.percent, 1),
        },
        "after": {
            "used_gb": round(mem_after.used_gb, 2),
            "percent": round(mem_after.percent, 1),
        },
    }


@router.get("/api/module/history")
async def get_switch_history():
    """获取模式切换历史"""
    mgr = await get_module_manager()
    return {"history": mgr.get_switch_history()}
