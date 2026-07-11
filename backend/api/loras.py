"""LoRA管理API"""
import asyncio
import json
import logging
from pathlib import Path
import os
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends
from app.dependencies import get_current_user

from db.adapter import db
from db.database import LORA_DIR_MAP, LORA_ROOT
from inference.lora_utils import resolve_lora_served_name

logger = logging.getLogger(__name__)
router = APIRouter()
_lora_status_lock = asyncio.Lock()


def _resolve_vllm_adapter_path(lora_name: str) -> str:
    """Map a trusted backend LoRA directory to the path visible by vLLM."""
    local_root = LORA_ROOT.resolve()
    local_path = (local_root / lora_name).resolve()
    if not local_path.is_relative_to(local_root):
        raise ValueError("LoRA path escapes the configured root")
    if not (local_path / "adapter_config.json").exists():
        final_path = local_path / "final"
        if (final_path / "adapter_config.json").exists():
            local_path = final_path
        else:
            raise FileNotFoundError("LoRA adapter_config.json was not found")

    vllm_root = Path(os.getenv("VLLM_LORA_ROOT", str(local_root)))
    return str(vllm_root / local_path.relative_to(local_root))


def _read_lora_metadata(adapter_path: Path) -> dict:
    """Read LoRA metadata from adapter_config.json and trainer_state.json."""
    meta = {"rank": 0, "alpha": 0, "trained_steps": 0, "total_steps": 0, "train_completed": False}

    config_path = adapter_path / "adapter_config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            meta["rank"] = cfg.get("r", 0)
            meta["alpha"] = cfg.get("lora_alpha", 0)
        except Exception:
            pass

    state_path = adapter_path / "trainer_state.json"
    if not state_path.exists() and adapter_path.name == "final":
        try:
            checkpoint_dirs = [
                d for d in adapter_path.parent.iterdir()
                if d.is_dir() and d.name.startswith("checkpoint-")
            ]
            if checkpoint_dirs:
                max_ckpt = max(checkpoint_dirs, key=lambda d: int(d.name.split("-")[-1]))
                candidate = max_ckpt / "trainer_state.json"
                if candidate.exists():
                    state_path = candidate
        except Exception:
            pass

    if state_path and state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            meta["trained_steps"] = state.get("global_step", 0)
            meta["total_steps"] = state.get("max_steps", 0)
            meta["train_completed"] = state.get("best_metric") is not None or meta["trained_steps"] > 0
        except Exception:
            pass

    adapter_file = adapter_path / "adapter_model.safetensors"
    if adapter_file.exists() and meta["trained_steps"] == 0:
        meta["train_completed"] = True
        meta["trained_steps"] = 1
        meta["total_steps"] = 1

    return meta


@router.get("/api/loras")
async def get_loras(status: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    """获取LoRA模型列表"""
    return {
        "loras": db.get_loras(status)
    }


@router.post("/api/loras/scan")
async def scan_loras(current_user: dict = Depends(get_current_user)):
    """扫描 loras/ 目录，自动发现并注册新的 LoRA 适配器，更新已有记录元信息"""
    lora_base = LORA_ROOT
    if not lora_base.exists():
        return {"success": True, "message": "loras 目录不存在", "new_count": 0}

    # 获取数据库中已有的 LoRA
    existing_loras = db.get_loras()
    existing_map = {lora["name"]: lora for lora in existing_loras}

    new_count = 0
    updated_count = 0
    for d in sorted(lora_base.iterdir()):
        if not d.is_dir():
            continue

        # 检查是否包含 adapter_config.json
        config_path = d / "adapter_config.json"
        adapter_path = d
        if not config_path.exists() and (d / "final" / "adapter_config.json").exists():
            config_path = d / "final" / "adapter_config.json"
            adapter_path = d / "final"

        if not config_path.exists():
            continue

        # 读取元信息
        meta = _read_lora_metadata(adapter_path)

        # 计算 adapter 大小
        adapter_file = adapter_path / "adapter_model.safetensors"
        size_str = "未知"
        if adapter_file.exists():
            size_mb = adapter_file.stat().st_size / (1024 * 1024)
            size_str = f"{size_mb:.0f}MB"

        trained_steps = meta["trained_steps"]
        total_steps = meta["total_steps"] if meta["total_steps"] > 0 else trained_steps

        if d.name in existing_map:
            # 更新已有记录
            try:
                db.execute_sql(
                    'UPDATE loras SET size = :size, trainedSteps = :trained_steps, totalSteps = :total_steps WHERE name = :name',
                    {"size": size_str, "trained_steps": trained_steps, "total_steps": total_steps, "name": d.name}
                )
                updated_count += 1
            except Exception as e:
                logger.error(f"更新 LoRA 失败 {d.name}: {e}")
            continue

        # 新增记录
        max_id = max((int(l["id"]) for l in existing_loras), default=0) + 1

        try:
            db.add_lora({
                "id": str(max_id),
                "name": d.name,
                "description": f"LoRA 适配器 - {d.name}",
                "status": "inactive",
                "style": "",
                "size": size_str,
                "trainedSteps": trained_steps,
                "totalSteps": total_steps,
                "createdAt": __import__('datetime').datetime.now().strftime("%Y-%m-%d"),
            })
            new_count += 1
            logger.info(f"自动注册 LoRA: {d.name} (size={size_str})")
        except Exception as e:
            logger.error(f"注册 LoRA 失败 {d.name}: {e}")

    msg_parts = []
    if new_count > 0:
        msg_parts.append(f"发现 {new_count} 个新 LoRA")
    if updated_count > 0:
        msg_parts.append(f"更新 {updated_count} 个记录")
    if not msg_parts:
        msg_parts.append("无新增或更新")

    return {"success": True, "message": "，".join(msg_parts), "new_count": new_count, "updated_count": updated_count}


@router.put("/api/loras/{lora_id}/status")
async def update_lora_status(lora_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """更新LoRA模型状态"""
    body = await request.json()
    status = body.get("status", "inactive")
    if status not in {"active", "inactive"}:
        raise HTTPException(status_code=422, detail="LoRA 状态只能是 active 或 inactive")

    existing = next((item for item in db.get_loras() if item["id"] == lora_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail="LoRA模型不存在")

    async with _lora_status_lock:
        if status == "active":
            try:
                from api.generate import get_vllm_client

                client = await get_vllm_client()
                if client is None:
                    raise RuntimeError("vLLM client is unavailable")
                served_name = resolve_lora_served_name(existing["name"])
                adapter_path = _resolve_vllm_adapter_path(existing["name"])
                await client.load_lora_adapter(served_name, adapter_path)
            except (FileNotFoundError, ValueError) as exc:
                logger.warning("Invalid LoRA adapter id=%s error=%s", lora_id, exc)
                raise HTTPException(status_code=422, detail="LoRA 适配器文件无效或配置不完整") from exc
            except Exception as exc:
                logger.exception("Failed to load LoRA into vLLM id=%s", lora_id)
                raise HTTPException(status_code=502, detail="LoRA 无法加载到 vLLM，数据库状态未变更") from exc

        lora = db.update_lora_status(lora_id, status)

    return {"success": True, "message": f"LoRA状态已更新为{status}", "lora": lora}


@router.delete("/api/loras/{lora_id}")
async def delete_lora(lora_id: str, current_user: dict = Depends(get_current_user)):
    """删除LoRA模型"""
    try:
        # 检查LoRA是否存在
        loras = db.get_loras()
        lora = next((l for l in loras if l["id"] == lora_id), None)

        if not lora:
            raise HTTPException(status_code=404, detail="LoRA模型不存在")

        # 删除LoRA
        db.delete_lora(lora_id)

        logger.info(f"删除LoRA模型: {lora_id}")
        return {"success": True, "message": "LoRA模型已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除LoRA失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
