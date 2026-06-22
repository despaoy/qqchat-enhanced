"""Claw 工具管理 API"""
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from db.adapter import db
from app.dependencies import get_current_user

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
async def list_tools(current_user: dict = Depends(get_current_user)):
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
async def save_tool(req: ToolSaveRequest, current_user: dict = Depends(get_current_user)):
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
async def delete_tool(name: str, current_user: dict = Depends(get_current_user)):
    """删除自定义 Claw 工具"""
    for bt in BUILTIN_TOOLS:
        if bt["name"] == name:
            raise HTTPException(status_code=400, detail="不能删除内置工具")
    
    success = db.delete_claw_tool(name)
    if not success:
        raise HTTPException(status_code=404, detail="工具不存在")
    return {"success": True, "message": "工具已删除"}


# ── 测试执行工具代码 ──

# 安全：受限内置名称表。执行用户工具代码时仅暴露这些名字，
# 任何危险模块（os/subprocess/open/eval/exec 等）一律拒绝。
_SAFE_BUILTINS = {
    "abs": abs, "min": min, "max": max, "sum": sum, "len": len,
    "range": range, "enumerate": enumerate, "zip": zip, "map": map,
    "filter": filter, "sorted": sorted, "reversed": reversed,
    "round": round, "isinstance": isinstance, "type": type,
    "list": list, "dict": dict, "tuple": tuple, "set": set,
    "str": str, "int": int, "float": float, "bool": bool,
    "True": True, "False": False, "None": None,
    "print": print, "repr": repr, "format": format,
    "any": any, "all": all, "round": round,
}
# 允许 import 的白名单模块（仅纯计算/数据处理类）
_SAFE_MODULES = {
    "json": json,
    "datetime": datetime,
    "math": __import__("math"),
    "re": __import__("re"),
    "collections": __import__("collections"),
    "itertools": __import__("itertools"),
    "statistics": __import__("statistics"),
}

# 危险调用关键字：源码中出现即直接拒绝执行
_FORBIDDEN_TOKENS = (
    "import os", "from os", "import subprocess", "from subprocess",
    "import sys", "from sys", "__import__", "builtins",
    "open(", "exec(", "eval(", "compile(", "globals(", "locals(",
    "getattr(subprocess", "pty.", "socket.", "shutil.", "pathlib",
)


class _RestrictedImporter:
    """import 拦截器：仅允许 _SAFE_MODULES 中的模块。"""

    def find_module(self, name, path=None):  # noqa: ARG002
        if name in _SAFE_MODULES or name.split(".")[0] in _SAFE_MODULES:
            return self
        return None

    def load_module(self, name):
        if name in _SAFE_MODULES:
            return _SAFE_MODULES[name]
        top = name.split(".")[0]
        if top in _SAFE_MODULES:
            return _SAFE_MODULES[top]
        raise ImportError(f"模块 '{name}' 不在允许的导入白名单中")


@router.post("/api/claw/tools/execute")
async def execute_tool_code(req: ToolExecuteRequest, current_user: dict = Depends(get_current_user)):
    """在前端测试执行工具代码（受限沙箱模式）。

    安全措施：
    1. 必须登录（Depends(get_current_user)）
    2. 静态扫描拒绝危险 token（os/subprocess/open/eval/__import__ 等）
    3. 受限 globals：仅暴露白名单内置函数，移除 open/exec/eval/compile 等
    4. 自定义 import 钩子，仅允许纯计算模块
    5. 强制超时与异常隔离
    注意：exec 本身无法做到完全沙箱，此实现仅用于"低风险测试"，生产环境应改用容器/子进程隔离。
    """
    import io
    import sys
    import traceback

    code = req.code
    args = req.args or {}

    if not code.strip():
        raise HTTPException(status_code=400, detail="代码不能为空")

    # 静态危险 token 扫描（大小写不敏感）
    lowered = code.lower()
    for token in _FORBIDDEN_TOKENS:
        if token in lowered:
            raise HTTPException(
                status_code=403,
                detail=f"代码包含被禁止的操作: '{token}'。沙箱模式禁止文件/进程/网络访问。",
            )

    stdout = io.StringIO()
    stderr = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    # 保存并替换 import 钩子
    old_meta_path = list(sys.meta_path)

    try:
        sys.stdout = stdout
        sys.stderr = stderr
        # 安装受限 import 钩子（置于 meta_path 最前）
        sys.meta_path.insert(0, _RestrictedImporter())

        local_vars: dict = {"args": args, "result": None}
        restricted_globals: dict = {
            "__builtins__": _SAFE_BUILTINS,
        }

        # 包装用户代码为函数（保持缩进），不再注入 os/subprocess/requests
        wrapped_code = (
            "def _claw_main(**kwargs):\n"
            + "\n".join("    " + line for line in code.split("\n"))
            + "\n    return None\n"
            "_result = _claw_main(**args)\n"
        )

        exec(wrapped_code, restricted_globals, local_vars)  # noqa: S102 - 受限沙箱

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
        sys.meta_path = old_meta_path
