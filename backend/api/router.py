"""多 LoRA 路由 API - 路由配置/适配器兼容性/路由日志"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from app.dependencies import get_current_user
from db.adapter import db
from db.models import RouterConfigUpdate

logger = logging.getLogger(__name__)
router = APIRouter()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/api/router/config")
async def get_router_config(current_user: dict = Depends(get_current_user)):
    """获取路由配置"""
    try:
        rows = db.execute_sql("SELECT value FROM config WHERE key='lora_router_config'")
        if rows:
            config = json.loads(rows[0]["value"])
        else:
            config = {
                "enabled": False,
                "default_adapter": "default",
                "rag_confidence_threshold": 0.3,
                "persona_keywords": {
                    "hutao": ["胡桃", "往生堂", "堂主"],
                    "zhongli": ["钟离", "岩王帝君", "摩拉克斯"],
                    "qiqi": ["七七", "不卜庐"],
                },
            }
        return {"success": True, "config": config}
    except Exception as e:
        logger.error(f"获取路由配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/router/config")
async def update_router_config(req: RouterConfigUpdate,
                               current_user: dict = Depends(get_current_user)):
    """更新路由配置"""
    try:
        rows = db.execute_sql("SELECT value FROM config WHERE key='lora_router_config'")
        if rows:
            config = json.loads(rows[0]["value"])
        else:
            config = {"enabled": False, "default_adapter": "default", "rag_confidence_threshold": 0.3, "persona_keywords": {}}
        if req.enabled is not None:
            config["enabled"] = req.enabled
        if req.default_adapter is not None:
            config["default_adapter"] = req.default_adapter
        if req.rag_confidence_threshold is not None:
            config["rag_confidence_threshold"] = req.rag_confidence_threshold
        if req.persona_keywords is not None:
            config["persona_keywords"] = req.persona_keywords
        db.execute_sql(
            "INSERT INTO config (key, value) VALUES ('lora_router_config', ?) "
            "ON CONFLICT(key) DO UPDATE SET value=?",
            (json.dumps(config, ensure_ascii=False), json.dumps(config, ensure_ascii=False)),
        )
        return {"success": True, "config": config}
    except Exception as e:
        logger.error(f"更新路由配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/router/adapters")
async def list_adapters(current_user: dict = Depends(get_current_user)):
    """列出已注册适配器及兼容性状态"""
    try:
        from db.database import LORA_DIR_MAP
        adapters = []
        for name, path in LORA_DIR_MAP.items():
            compat_rows = db.execute_sql(
                "SELECT * FROM adapter_compatibility WHERE adapter_name=? ORDER BY checked_at DESC LIMIT 1",
                (name,),
            )
            compatibility = None
            if compat_rows:
                r = compat_rows[0]
                try:
                    checks = json.loads(r["checks"]) if r["checks"] else {}
                except Exception:
                    checks = {}
                try:
                    warnings = json.loads(r["warnings"]) if r["warnings"] else []
                except Exception:
                    warnings = []
                try:
                    errors = json.loads(r["errors"]) if r["errors"] else []
                except Exception:
                    errors = []
                compatibility = {
                    "compatible": bool(r["compatible"]), "checked_at": r["checked_at"],
                    "checks": checks, "warnings": warnings, "errors": errors,
                }
            adapters.append({"name": name, "path": path, "compatibility": compatibility})
        return {"success": True, "adapters": adapters, "total": len(adapters)}
    except Exception as e:
        logger.error(f"列出适配器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/router/logs")
async def get_routing_logs(limit: int = 100, current_user: dict = Depends(get_current_user)):
    """获取路由日志"""
    try:
        from inference.lora_router import get_lora_router
        r = get_lora_router()
        logs = r.get_routing_logs(limit=limit)
        return {"success": True, "logs": logs, "total": len(logs)}
    except ImportError:
        return {"success": True, "logs": [], "total": 0, "note": "router module not available"}
    except Exception as e:
        logger.error(f"获取路由日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/router/check/{adapter_name}")
async def check_adapter_compat(adapter_name: str, current_user: dict = Depends(get_current_user)):
    """手动触发适配器兼容性检查"""
    try:
        from inference.adapter_checker import AdapterChecker
        from db.database import LORA_DIR_MAP
        if adapter_name not in LORA_DIR_MAP:
            raise HTTPException(status_code=404, detail=f"adapter {adapter_name} not found")
        checker = AdapterChecker()
        report = checker.check_adapter(LORA_DIR_MAP[adapter_name])
        try:
            db.execute_sql_insert(
                "INSERT INTO adapter_compatibility (adapter_name, checked_at, compatible, checks, warnings, errors) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (adapter_name, _now(), int(report.compatible),
                 json.dumps(report.checks, ensure_ascii=False),
                 json.dumps(report.warnings, ensure_ascii=False),
                 json.dumps(report.errors, ensure_ascii=False)),
            )
        except Exception as e:
            logger.warning(f"存储兼容性记录失败（非致命）: {e}")
        return {
            "success": True,
            "adapter_name": adapter_name,
            "compatible": report.compatible,
            "checks": report.checks,
            "warnings": report.warnings,
            "errors": report.errors,
        }
    except HTTPException:
        raise
    except ImportError:
        return {"success": True, "adapter_name": adapter_name, "compatible": True, "checks": {}, "warnings": ["checker module not available"], "errors": []}
    except Exception as e:
        logger.error(f"兼容性检查失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
