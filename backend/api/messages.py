"""消息记录API"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from app.dependencies import get_current_user
from pydantic import BaseModel

from db.adapter import db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/messages")
async def get_messages(
    search: Optional[str] = Query(None),
    sessionType: Optional[str] = Query(None),
    lora: Optional[str] = Query(None),
    sessionId: Optional[str] = Query(None),
    sessionName: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """获取消息记录 — 支持 SQL 层多条件组合过滤 + 分页"""
    total_all = db.get_message_count()

    messages = db.get_messages_filtered(
        search=search,
        session_type=sessionType if sessionType and sessionType != "all" else None,
        lora_name=lora if lora and lora != "all" else None,
        session_id=sessionId,
        session_name=sessionName,
        platform=platform if platform and platform != "all" else None,
        limit=limit,
        offset=offset,
    )
    total = db.get_message_count_filtered(
        search=search,
        session_type=sessionType if sessionType and sessionType != "all" else None,
        lora_name=lora if lora and lora != "all" else None,
        session_id=sessionId,
        session_name=sessionName,
        platform=platform if platform and platform != "all" else None,
    )

    return {
        "messages": messages,
        "total": total,
        "total_all": total_all
    }


@router.get("/api/sessions")
async def get_session_summaries(current_user: dict = Depends(get_current_user)):
    """获取所有会话的聚合统计（按sessionId分组）"""
    sessions = db.get_session_summaries()
    return {"sessions": sessions}


class SessionBotToggle(BaseModel):
    sessionId: str
    enabled: bool
    platform: str = "qq"
    conversationId: Optional[str] = None


@router.put("/api/sessions/bot-toggle")
async def toggle_session_bot(req: SessionBotToggle, current_user: dict = Depends(get_current_user)):
    """设置某个会话的机器人开关"""
    db.set_session_bot_enabled(req.sessionId, req.enabled, req.platform, req.conversationId)
    return {"success": True, "sessionId": req.sessionId, "botEnabled": req.enabled}


class BatchDeleteRequest(BaseModel):
    search: Optional[str] = None
    sessionType: Optional[str] = None
    lora: Optional[str] = None
    sessionName: Optional[str] = None
    platform: Optional[str] = None


@router.delete("/api/messages/batch")
async def delete_messages_batch(req: BatchDeleteRequest, current_user: dict = Depends(get_current_user)):
    """批量删除消息（基于筛选条件）— 需认证"""
    count = db.delete_messages_by_filter(
        search=req.search,
        sessionType=req.sessionType,
        lora=req.lora,
        sessionName=req.sessionName,
        platform=req.platform
    )
    return {"success": True, "deleted": count, "message": f"已删除 {count} 条记录"}


@router.delete("/api/messages/{msg_id}")
async def delete_message(msg_id: int, current_user: dict = Depends(get_current_user)):
    """删除单条消息记录 — 需认证"""
    success = db.delete_message(msg_id)
    if not success:
        raise HTTPException(status_code=404, detail="消息不存在")
    return {"success": True, "message": "删除成功"}
