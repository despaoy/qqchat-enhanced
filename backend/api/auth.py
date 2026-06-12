"""用户认证API"""

from fastapi import APIRouter, HTTPException, Depends, Response, Request

from db.models import RegisterRequest, LoginRequest
from db.adapter import db
from app.config import create_access_token
from app.dependencies import get_current_user

router = APIRouter()


def _hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码（自动加盐）"""
    import bcrypt

    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def _set_auth_cookie(response: Response, token: str):
    """设置 httpOnly Cookie 存储 JWT Token"""
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # TODO: 生产环境改为 True（需HTTPS）
        samesite="lax",
        max_age=86400,  # 24小时，与JWT_EXPIRY_HOURS一致
        path="/",
    )


@router.post("/api/auth/register")
async def register(request: RegisterRequest, response: Response):
    """用户注册"""
    try:
        existing = db.get_user_by_username(request.username)
        if existing:
            raise HTTPException(status_code=409, detail="用户名已存在")

        password_hash = _hash_password(request.password)
        user = db.add_user(request.username, password_hash)
        user_id = user["id"]
        now = user["created_at"]
        token = create_access_token(request.username, user_id)
        _set_auth_cookie(response, token)
        return {
            "success": True,
            "token": token,
            "user": {"id": user_id, "username": request.username, "created_at": now}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


@router.post("/api/auth/login")
async def login(request: LoginRequest, response: Response):
    """用户登录"""
    try:
        row = db.get_user_by_username(request.username)
        if not row:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        import bcrypt

        if not bcrypt.checkpw(request.password.encode('utf-8'), row['password_hash'].encode('utf-8')):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = create_access_token(row['username'], row['id'])
        _set_auth_cookie(response, token)
        return {
            "success": True,
            "token": token,
            "user": {
                "id": row['id'],
                "username": row['username'],
                "created_at": row['created_at']
            }
        }
    except HTTPException:
        raise


@router.post("/api/auth/logout")
async def logout(response: Response):
    """用户登出 - 清除 Cookie"""
    response.delete_cookie(key="access_token", path="/")
    return {"success": True}


@router.get("/api/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    return {
        "success": True,
        "user": {
            "id": current_user["user_id"],
            "username": current_user["sub"],
        }
    }
