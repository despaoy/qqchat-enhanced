"""
应用配置模块
从 main.py 提取：JWT、LLM 并发控制、搜索工具、增强模块导入、全局实例
"""

import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import HTTPException

# ============================================
# JWT 配置
# ============================================

import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "qq-assistant-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24


def create_access_token(username: str, user_id: int) -> str:
    """创建 JWT access token"""
    payload = {
        "sub": username,
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """验证 JWT token，返回 payload 或抛出异常"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token 无效")


# ============================================
# LLM 并发控制器
# ============================================

LLM_CONCURRENCY_LIMIT = 10  # 最多同时10个LLM调用
llm_semaphore = asyncio.Semaphore(LLM_CONCURRENCY_LIMIT)
llm_request_counter = 0  # 当前排队的请求数
llm_max_queue = 100  # 最大排队数


# ============================================
# 角色信息网络搜索工具
# ============================================

logger = logging.getLogger(__name__)


def _search_character_info(character_desc: str, max_results: int = 3) -> str:
    """在网络上搜索角色信息（短超时+降级，不阻塞生成）"""

    import concurrent.futures
    import httpx
    from urllib.parse import quote

    query = f"{character_desc} 角色 人物介绍"
    query_encoded = quote(query)

    def try_duckduckgo():
        """DuckDuckGo HTML 搜索"""
        try:
            url = f"https://html.duckduckgo.com/html/?q={query_encoded}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            with httpx.Client(timeout=5.0, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200:
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(resp.text, "html.parser")
                    items = soup.select(".result")
                    lines = []
                    for r in items[:max_results]:
                        t = r.select_one(".result__title")
                        s = r.select_one(".result__snippet")
                        if t and s:
                            lines.append(
                                f"- {t.get_text(strip=True)}\n  {s.get_text(strip=True)[:250]}"
                            )
                    return "\n".join(lines) if lines else ""
        except Exception:
            pass
        return ""

    def try_wikipedia():
        """Wikipedia API"""
        try:
            params = {
                "action": "query",
                "list": "search",
                "srsearch": character_desc,
                "format": "json",
                "srlimit": 3,
            }
            with httpx.Client(timeout=5.0) as client:
                resp = client.get("https://zh.wikipedia.org/w/api.php", params=params)
                if resp.status_code == 200:
                    pages = resp.json().get("query", {}).get("search", [])
                    import re

                    return "\n".join(
                        f"- {p['title']}\n  {re.sub(r'<[^>]+>', '', p.get('snippet', ''))[:250]}"
                        for p in pages[:max_results]
                    )
        except Exception:
            pass
        return ""

    # 并行搜索，总超时 6 秒
    result = ""
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(try_duckduckgo): "ddg",
            executor.submit(try_wikipedia): "wiki",
        }
        for future in concurrent.futures.as_completed(futures, timeout=6):
            try:
                r = future.result(timeout=5)
                if r and len(r) > len(result):
                    result = r
            except Exception:
                pass

    if result:
        logger.info(f"角色信息搜索成功: {len(result)} 字符")
    else:
        logger.info("角色信息搜索无结果（网络受限），将基于用户描述生成")

    return result


# ============================================
# 增强模块导入
# ============================================

try:
    from infra.load_balancer import LoadBalancerManager

    LOAD_BALANCER_AVAILABLE = True
except ImportError:
    LOAD_BALANCER_AVAILABLE = False

try:
    from infra.async_processor import AsyncTaskQueue

    ASYNC_PROCESSOR_AVAILABLE = True
except ImportError:
    ASYNC_PROCESSOR_AVAILABLE = False

try:
    from infra.resource_pool import ConnectionPool, HttpClientPool

    RESOURCE_POOL_AVAILABLE = True
except ImportError:
    RESOURCE_POOL_AVAILABLE = False

try:
    from infra.circuit_breaker import CircuitBreakerRegistry

    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False

try:
    from infra.backup_manager import BackupManager

    BACKUP_MANAGER_AVAILABLE = True
except ImportError:
    BACKUP_MANAGER_AVAILABLE = False

try:
    from infra.failover import FailoverManager

    FAILOVER_AVAILABLE = True
except ImportError:
    FAILOVER_AVAILABLE = False

try:
    from infra.input_validator import (
        InputValidator,
        MESSAGE_SCHEMA,
        KNOWLEDGE_SCHEMA,
        TRAINING_SCHEMA,
        CONFIG_SCHEMA,
    )

    INPUT_VALIDATOR_AVAILABLE = True
except ImportError:
    INPUT_VALIDATOR_AVAILABLE = False

try:
    from infra.encryption import EncryptionManager

    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False

try:
    from infra.access_control import AccessControlManager, Permission

    ACCESS_CONTROL_AVAILABLE = True
except ImportError:
    ACCESS_CONTROL_AVAILABLE = False

try:
    from inference.optimizer import (
        LLMCallOptimizer,
        ResponseCache,
        RateLimiter,
        PromptOptimizer,
    )

    LLM_OPTIMIZER_AVAILABLE = True
except ImportError:
    LLM_OPTIMIZER_AVAILABLE = False


# ============================================
# 服务启动时间
# ============================================

service_start_time = datetime.now()


# ============================================
# 增强模块全局实例
# ============================================

load_balancer_mgr = LoadBalancerManager() if LOAD_BALANCER_AVAILABLE else None
async_task_queue = AsyncTaskQueue() if ASYNC_PROCESSOR_AVAILABLE else None
connection_pool = None  # 在lifespan中初始化
http_client_pool = None  # 在lifespan中初始化
circuit_breaker_registry = CircuitBreakerRegistry() if CIRCUIT_BREAKER_AVAILABLE else None
backup_mgr = None  # 在lifespan中初始化
failover_mgr = None  # 在lifespan中初始化
encryption_mgr = EncryptionManager() if ENCRYPTION_AVAILABLE else None
access_control_mgr = None  # 在lifespan中初始化
llm_optimizer = LLMCallOptimizer() if LLM_OPTIMIZER_AVAILABLE else None
response_cache = ResponseCache() if LLM_OPTIMIZER_AVAILABLE else None
rate_limiter = RateLimiter() if LLM_OPTIMIZER_AVAILABLE else None
prompt_optimizer = PromptOptimizer() if LLM_OPTIMIZER_AVAILABLE else None


# ============================================
# 向量数据库
# ============================================

try:
    from knowledge.vector_db import get_vector_db

    VECTOR_DB_AVAILABLE = True
except ImportError:
    VECTOR_DB_AVAILABLE = False


# ============================================
# 对话生成状态追踪（线程安全）
# ============================================

import threading

generation_state_lock = threading.Lock()

generation_state = {
    "is_generating": False,
    "cancel_requested": False,
    "progress": 0,
    "total": 0,
    "batch_num": 0,
    "total_batches": 0,
    "generated_count": 0,
    "all_generated_dialogues": [],
    "started_at": None,
}
