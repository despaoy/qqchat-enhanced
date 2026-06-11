"""Claw 工具管理 API"""
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.database import db

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 内置工具列表（来自 bot/tools.py）──
BUILTIN_TOOLS = [
    {"name": "status", "description": "获取系统状态，包括CPU、内存、磁盘占用率", "builtin": True},
    {"name": "show_tools", "description": "显示所有可使用工具", "builtin": True},
    {"name": "send_file", "description": "发送桌面上指定名称的文件", "builtin": True},
    {"name": "get_coderesult", "description": "获取代码执行结果", "builtin": True},
    {"name": "write_code", "description": "编写并执行 Python 代码解决问题", "builtin": True},
]

# ── 请求/响应模型 ──

class ToolSaveRequest(BaseModel):
    name: str
    description: str = ""
    code: str = ""
    enabled: bool = True

class ToolExecuteRequest(BaseModel):
    code: str
    args: dict = {}


# ── 工具列表 ──

@router.get("/api/claw/tools")
async def list_tools():
    """列出所有 Claw 工具（内置 + 自定义）"""
    custom_tools = db.get_claw_tools()
    result = []
    # 内置工具在前
    for t in BUILTIN_TOOLS:
        result.append({
            "name": t["name"],
            "description": t["description"],
            "code": "",
            "enabled": True,
            "builtin": True,
        })
    # 自定义工具在后
    for t in custom_tools:
        result.append({
            "name": t["name"],
            "description": t["description"],
            "code": t["code"],
            "enabled": bool(t["enabled"]),
            "builtin": False,
            "created_at": t["created_at"],
            "updated_at": t["updated_at"],
        })
    return {"success": True, "tools": result, "total": len(result)}


# ── 保存（创建/更新）工具 ──

@router.post("/api/claw/tools")
async def save_tool(req: ToolSaveRequest):
    """创建或更新自定义 Claw 工具"""
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="工具名称不能为空")
    
    # 检查是否与内置工具重名
    for bt in BUILTIN_TOOLS:
        if bt["name"] == req.name.strip():
            raise HTTPException(status_code=400, detail=f"工具名称 '{req.name}' 与内置工具冲突")
    
    try:
        db.save_claw_tool(req.name.strip(), req.description.strip(), req.code, req.enabled)
        return {"success": True, "message": "工具已保存"}
    except Exception as e:
        logger.error(f"保存 Claw 工具失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 删除工具 ──

@router.delete("/api/claw/tools/{name}")
async def delete_tool(name: str):
    """删除自定义 Claw 工具"""
    for bt in BUILTIN_TOOLS:
        if bt["name"] == name:
            raise HTTPException(status_code=400, detail="不能删除内置工具")
    
    success = db.delete_claw_tool(name)
    if not success:
        raise HTTPException(status_code=404, detail="工具不存在")
    return {"success": True, "message": "工具已删除"}


# ── 测试执行工具代码 ──

@router.post("/api/claw/tools/execute")
async def execute_tool_code(req: ToolExecuteRequest):
    """在前端测试执行工具代码（沙箱模式）"""
    import io
    import sys
    import traceback
    
    code = req.code
    args = req.args or {}
    
    if not code.strip():
        raise HTTPException(status_code=400, detail="代码不能为空")
    
    # 准备执行环境
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    try:
        sys.stdout = stdout
        sys.stderr = stderr
        
        # 构建执行环境
        local_vars = {"args": args, "result": None}
        
        # 包装代码为函数并执行
        wrapped_code = f"""
import os, json, sys, subprocess, datetime, pathlib, shutil, requests

def _claw_main(**kwargs):
{chr(10).join('    ' + line for line in code.split(chr(10)))}
    return None

_result = _claw_main(**args)
"""
        exec(wrapped_code, {"__builtins__": __builtins__}, local_vars)
        
        output = stdout.getvalue()
        error_output = stderr.getvalue()
        exec_result = str(local_vars.get("_result", "")) if local_vars.get("_result") is not None else ""
        
        return {
            "success": True,
            "output": output,
            "error": error_output,
            "result": exec_result,
        }
    except Exception as e:
        return {
            "success": False,
            "output": stdout.getvalue(),
            "error": stderr.getvalue() + "\n" + traceback.format_exc(),
            "result": str(e),
        }
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
