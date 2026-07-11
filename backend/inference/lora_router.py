"""多 LoRA 路由器 - 基于意图和角色关键词的轻量级路由。

遵循路线图 guardrail：
- 路由目标: base_chat / rag_required / persona_adapter
- 记录路由置信度和降级决策
- 由环境变量 LORA_ROUTER_ENABLED 控制（默认 false）
- 规则版路由，不依赖 LLM
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class RouteTarget(str, Enum):
    """路由目标类型。"""
    BASE_CHAT = "base_chat"
    RAG_REQUIRED = "rag_required"
    PERSONA_ADAPTER = "persona_adapter"


@dataclass
class RoutingDecision:
    """路由决策结果。"""
    target: str  # RouteTarget value
    adapter_name: str = "default"
    confidence: float = 0.0
    reason: str = ""
    fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# 默认角色关键词映射
DEFAULT_PERSONA_KEYWORDS: Dict[str, List[str]] = {
    "hutao": ["胡桃", "往生堂", "堂主", "火系", "蝶引来生", "护摩"],
    "zhongli": ["钟离", "岩王帝君", "摩拉克斯", "岩神", "岩柱", "天星"],
    "qiqi": ["七七", "不卜庐", "僵尸", "符咒", "治疗"],
    "xiao": ["魈", "降魔大圣", "护法夜叉", "面具", "风系"],
}


class LoRARouter:
    """多 LoRA 路由器。

    根据用户查询内容选择路由目标：
    - 含知识/百科类问题 → RAG_REQUIRED
    - 含角色关键词 → PERSONA_ADAPTER（选择对应适配器）
    - 其他 → BASE_CHAT
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.enabled = config.get("enabled", False)
        self.default_adapter = config.get("default_adapter", "default")
        self.rag_confidence_threshold = config.get("rag_confidence_threshold", 0.5)
        self.persona_keywords: Dict[str, List[str]] = config.get(
            "persona_keywords", DEFAULT_PERSONA_KEYWORDS
        )
        self._intent_detector = None
        self._routing_logs: List[Dict[str, Any]] = []
        self._max_logs = 500

    def _get_intent_detector(self):
        """延迟加载意图检测器。"""
        if self._intent_detector is None:
            try:
                from knowledge.intent_detector import needs_rag
                self._intent_detector = needs_rag
            except ImportError:
                logger.warning("intent_detector 不可用，路由器将仅依赖关键词匹配")
                self._intent_detector = None
        return self._intent_detector

    def route(self, query: str, intent_result: Optional[tuple] = None) -> RoutingDecision:
        """路由查询到合适的适配器。

        Args:
            query: 用户查询文本
            intent_result: 预计算的意图检测结果 (need_rag, confidence, kb_name)

        Returns:
            RoutingDecision
        """
        if not self.enabled:
            return RoutingDecision(
                target=RouteTarget.BASE_CHAT.value,
                adapter_name=self.default_adapter,
                confidence=1.0,
                reason="路由器未启用，使用默认适配器",
                fallback=True,
            )

        # 1. 检查是否需要 RAG（知识检索）
        need_rag = False
        rag_confidence = 0.0
        if intent_result is not None:
            need_rag = intent_result[0] if len(intent_result) > 0 else False
            rag_confidence = intent_result[1] if len(intent_result) > 1 else 0.0
        else:
            detector = self._get_intent_detector()
            if detector:
                try:
                    need_rag, rag_confidence, _ = detector(query)
                except Exception:
                    need_rag = False

        if need_rag and rag_confidence >= self.rag_confidence_threshold:
            return RoutingDecision(
                target=RouteTarget.RAG_REQUIRED.value,
                adapter_name=self.default_adapter,
                confidence=rag_confidence,
                reason=f"意图检测需要 RAG (confidence={rag_confidence:.2f})",
            )

        # 2. 检查角色关键词匹配
        best_persona = None
        best_match_count = 0
        for persona, keywords in self.persona_keywords.items():
            match_count = sum(1 for kw in keywords if kw in query)
            if match_count > best_match_count:
                best_match_count = match_count
                best_persona = persona

        if best_persona and best_match_count > 0:
            confidence = min(1.0, best_match_count / 3.0)
            adapter_name = f"{best_persona}_lora_7b"
            # 验证适配器名称安全性
            if not all(c.isalnum() or c in "_-" for c in adapter_name):
                adapter_name = self.default_adapter
            return RoutingDecision(
                target=RouteTarget.PERSONA_ADAPTER.value,
                adapter_name=adapter_name,
                confidence=confidence,
                reason=f"匹配角色 {best_persona} ({best_match_count} 个关键词)",
            )

        # 3. 默认基础聊天
        return RoutingDecision(
            target=RouteTarget.BASE_CHAT.value,
            adapter_name=self.default_adapter,
            confidence=0.5,
            reason="未匹配 RAG 或角色关键词，使用基础聊天",
        )

    def log_routing(self, decision: RoutingDecision, trace_id: str = ""):
        """记录路由日志（Python logger + 内存存储）。"""
        from datetime import datetime, timezone
        logger.info(
            f"LoRA路由: target={decision.target}, adapter={decision.adapter_name}, "
            f"confidence={decision.confidence:.2f}, reason={decision.reason}, traceId={trace_id}"
        )
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            **decision.to_dict(),
        }
        self._routing_logs.append(entry)
        if len(self._routing_logs) > self._max_logs:
            self._routing_logs = self._routing_logs[-self._max_logs:]

    def get_routing_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """返回最近的路由日志（按时间倒序）。"""
        return list(reversed(self._routing_logs[-limit:]))


# 默认配置
DEFAULT_ROUTER_CONFIG = {
    "enabled": os.getenv("LORA_ROUTER_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"},
    "default_adapter": "default",
    "rag_confidence_threshold": 0.5,
    "persona_keywords": DEFAULT_PERSONA_KEYWORDS,
}

_router: Optional[LoRARouter] = None


def get_lora_router() -> LoRARouter:
    """获取 LoRARouter 单例。"""
    global _router
    if _router is None:
        _router = LoRARouter(DEFAULT_ROUTER_CONFIG)
    return _router


def route_query(query: str, intent_result: Optional[tuple] = None) -> RoutingDecision:
    """便捷函数：路由查询并记录日志。"""
    router = get_lora_router()
    decision = router.route(query, intent_result)
    router.log_routing(decision)
    return decision
