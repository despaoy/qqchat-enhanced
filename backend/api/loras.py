"""LoRA管理API"""
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException

from db.database import db, LORA_DIR_MAP

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/loras")
async def get_loras(status: Optional[str] = None):
    """获取LoRA模型列表"""
    return {
        "loras": db.get_loras(status)
    }


@router.post("/api/loras/scan")
async def scan_loras():
    """扫描 loras/ 目录，自动发现并注册新的 LoRA 适配器，更新已有记录元信息"""
    lora_base = Path(__file__).parent.parent / "loras"
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
        meta = db._read_lora_metadata(adapter_path)

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
                conn = db._get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE loras SET size = ?, trainedSteps = ?, totalSteps = ?
                    WHERE name = ?
                ''', (size_str, trained_steps, total_steps, d.name))
                conn.commit()
                updated_count += 1
            except Exception as e:
                logger.error(f"更新 LoRA 失败 {d.name}: {e}")
            continue

        # 新增记录
        max_id = max((int(l["id"]) for l in existing_loras), default=0) + 1

        try:
            conn = db._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO loras (id, name, description, status, style, size, trainedSteps, totalSteps, createdAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(max_id), d.name, f"LoRA 适配器 - {d.name}", "inactive",
                "", size_str, trained_steps, total_steps,
                __import__('datetime').datetime.now().strftime("%Y-%m-%d")
            ))
            conn.commit()
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
async def update_lora_status(lora_id: str, request: Request):
    """更新LoRA模型状态"""
    body = await request.json()
    status = body.get("status", "inactive")

    lora = db.update_lora_status(lora_id, status)
    if lora:
        return {"success": True, "message": f"LoRA状态已更新为{status}", "lora": lora}

    raise HTTPException(status_code=404, detail="LoRA模型不存在")


@router.delete("/api/loras/{lora_id}")
async def delete_lora(lora_id: str):
    """删除LoRA模型"""
    try:
        conn = db._get_connection()
        cursor = conn.cursor()

        # 检查LoRA是否存在
        cursor.execute('SELECT * FROM loras WHERE id = ?', (lora_id,))
        lora = cursor.fetchone()

        if not lora:
            conn.close()
            raise HTTPException(status_code=404, detail="LoRA模型不存在")

        # 删除LoRA
        cursor.execute('DELETE FROM loras WHERE id = ?', (lora_id,))
        conn.commit()
        conn.close()

        logger.info(f"删除LoRA模型: {lora_id}")
        return {"success": True, "message": "LoRA模型已删除"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除LoRA失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
