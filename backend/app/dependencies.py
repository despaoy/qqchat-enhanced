"""FastAPI 依赖注入"""
from fastapi import Request, HTTPException
from app.config import verify_token


async def get_current_user(request: Request) -> dict:
    """从请求中提取并验证当前用户"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="缺少认证 Token")
    token = auth_header[7:]
    return verify_token(token)
