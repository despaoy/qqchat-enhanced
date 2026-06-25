"""FastAPI 依赖注入"""
from fastapi import Request, HTTPException
from app.config import verify_token


async def get_current_user(request: Request) -> dict:
    """从请求中提取并验证当前用户（支持 Authorization 头、Cookie 和中间件预验证）"""
    # 1. 如果安全中间件已验证，直接使用
    if hasattr(request.state, "jwt_payload") and request.state.jwt_payload:
        payload = request.state.jwt_payload
        # 检查 Token 是否已被注销
        from api.auth import is_token_revoked
        if is_token_revoked(payload.get("jti", "")):
            raise HTTPException(status_code=401, detail="Token 已注销，请重新登录")
        return {
            "user_id": payload.get("user_id"),
            "username": payload.get("sub", "unknown"),
        }

    token = None

    # 2. 从 Authorization 头获取
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 3. 从 Cookie 获取
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(status_code=401, detail="缺少认证 Token")

    payload = verify_token(token)

    # 检查 Token 是否已被注销
    from api.auth import is_token_revoked
    if is_token_revoked(payload.get("jti", "")):
        raise HTTPException(status_code=401, detail="Token 已注销，请重新登录")

    return payload
