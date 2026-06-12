"""消息记录API"""
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from db.adapter import db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/messages")
async def get_messages(
    search: Optional[str] = None,
    sessionType: Optional[str] = None,
    lora: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """获取消息记录"""
    total_all = db.get_message_count()
    messages = db.get_messages(limit=limit, offset=offset)

    # 过滤
    if search:
        messages = [m for m in messages if
            search.lower() in m.get("message", "").lower() or
            search.lower() in m.get("reply", "").lower() or
            search.lower() in m.get("userName", "").lower()]

    if sessionType and sessionType != "all":
        messages = [m for m in messages if m.get("sessionType") == sessionType]

    if lora and lora != "all":
        messages = [m for m in messages if m.get("loraName") == lora]

    return {
        "messages": messages,
        "total": len(messages),
        "total_all": total_all
    }


@router.get("/api/sessions")
async def get_session_summaries():
    """获取所有会话的聚合统计（按sessionId分组）"""
    sessions = db.get_session_summaries()
    return {"sessions": sessions}


class SessionBotToggle(BaseModel):
    sessionId: str
    enabled: bool


@router.put("/api/sessions/bot-toggle")
async def toggle_session_bot(req: SessionBotToggle):
    """设置某个会话的机器人开关"""
    db.set_session_bot_enabled(req.sessionId, req.enabled)
    return {"success": True, "sessionId": req.sessionId, "botEnabled": req.enabled}


class BatchDeleteRequest(BaseModel):
    search: Optional[str] = None
    sessionType: Optional[str] = None
    lora: Optional[str] = None
    sessionName: Optional[str] = None


@router.delete("/api/messages/batch")
async def delete_messages_batch(req: BatchDeleteRequest):
    """批量删除消息（基于筛选条件）"""
    count = db.delete_messages_by_filter(
        search=req.search,
        sessionType=req.sessionType,
        lora=req.lora,
        sessionName=req.sessionName
    )
    return {"success": True, "deleted": count, "message": f"已删除 {count} 条记录"}


@router.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: int):
    """删除单条消息记录"""
    success = db.delete_message(msg_id)
    if not success:
        return {"success": False, "message": "消息不存在"}
    return {"success": True, "message": "删除成功"}
