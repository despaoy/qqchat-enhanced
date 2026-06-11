"""用户认证API"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends

from db.models import RegisterRequest, LoginRequest
from db.database import db
from app.config import create_access_token
from app.dependencies import get_current_user

router = APIRouter()


def _hash_password(password: str) -> str:
    """使用 bcrypt 哈希密码（自动加盐）"""
    import bcrypt

    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


@router.post("/api/auth/register")
async def register(request: RegisterRequest):
    """用户注册"""
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM users WHERE username = ?', (request.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="用户名已存在")

        password_hash = _hash_password(request.password)
        now = datetime.now().isoformat()
        cursor.execute(
            'INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)',
            (request.username, password_hash, now)
        )
        conn.commit()
        user_id = cursor.lastrowid
        token = create_access_token(request.username, user_id)
        return {
            "success": True,
            "token": token,
            "user": {"id": user_id, "username": request.username, "created_at": now}
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")
    finally:
        conn.close()


@router.post("/api/auth/login")
async def login(request: LoginRequest):
    """用户登录"""
    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, username, password_hash, created_at FROM users WHERE username = ?', (request.username,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        import bcrypt

        if not bcrypt.checkpw(request.password.encode('utf-8'), row['password_hash'].encode('utf-8')):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        token = create_access_token(row['username'], row['id'])
        return {
            "success": True,
            "token": token,
            "user": {
                "id": row['id'],
                "username": row['username'],
                "created_at": row['created_at']
            }
        }
    finally:
        conn.close()


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
