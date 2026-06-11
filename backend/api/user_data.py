"""用户数据持久化API"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends

from db.models import UserDataRequest
from db.database import db
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/api/user/data")
async def get_user_data(page_key: str = "", current_user: dict = Depends(get_current_user)):
    """获取用户表单数据"""
    username = current_user["sub"]

    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="用户不存在")
        user_id = user_row['id']

        if page_key:
            cursor.execute(
                'SELECT page_key, data_json, updated_at FROM user_data WHERE user_id = ? AND page_key = ?',
                (user_id, page_key)
            )
            row = cursor.fetchone()
            if not row:
                return {"success": True, "data": None}
            return {
                "success": True,
                "data": {
                    "page_key": row['page_key'],
                    "data_json": row['data_json'],
                    "updated_at": row['updated_at']
                }
            }
        else:
            cursor.execute('SELECT page_key, data_json, updated_at FROM user_data WHERE user_id = ?', (user_id,))
            rows = cursor.fetchall()
            data = {
                row['page_key']: {
                    "data_json": row['data_json'],
                    "updated_at": row['updated_at']
                }
                for row in rows
            }
            return {"success": True, "data": data}
    finally:
        conn.close()


@router.put("/api/user/data")
async def save_user_data(request: UserDataRequest, current_user: dict = Depends(get_current_user)):
    """保存用户表单数据"""
    username = current_user["sub"]

    conn = db._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        user_row = cursor.fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="用户不存在")
        user_id = user_row['id']

        now = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO user_data (user_id, page_key, data_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, page_key) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = excluded.updated_at
        ''', (user_id, request.page_key, request.data_json, now))
        conn.commit()
        return {"success": True, "message": "数据保存成功"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
    finally:
        conn.close()
