"""
缓存层：配置数据缓存

在 PostgreSQL 模式下，使用 Redis 缓存高频读取的配置数据，
减少数据库查询压力。
"""
import logging
import random
import time
from typing import Dict, Optional

from cache import redis_client

logger = logging.getLogger(__name__)

CONFIG_CACHE_KEY = "cache:config"
CONFIG_CACHE_TTL = 60  # 配置缓存 60 秒

KNOWLEDGE_STATS_KEY = "cache:knowledge_stats"
_LOCAL_CONFIG_CACHE: tuple[float, Dict] | None = None

KNOWLEDGE_STATS_TTL = 30  # 知识库统计 30 秒


def _ttl_with_jitter(ttl: int) -> int:
    """在TTL基础上添加±10%随机抖动，防止大量缓存同时过期（雪崩）"""
    jitter = int(ttl * random.uniform(-0.1, 0.1))
    return max(1, ttl + jitter)


def get_cached_config() -> Optional[Dict]:
    """Get config from Redis or local in-process TTL cache."""
    cached = redis_client.cache_get(CONFIG_CACHE_KEY)
    if cached is not None:
        return cached
    if _LOCAL_CONFIG_CACHE is None:
        return None
    expires_at, value = _LOCAL_CONFIG_CACHE
    if time.monotonic() >= expires_at:
        return None
    return value


def set_cached_config(config: Dict) -> bool:
    """Cache config in Redis and local memory fallback."""
    global _LOCAL_CONFIG_CACHE
    ttl = _ttl_with_jitter(CONFIG_CACHE_TTL)
    _LOCAL_CONFIG_CACHE = (time.monotonic() + ttl, dict(config))
    return redis_client.cache_set(CONFIG_CACHE_KEY, config, ttl)


def invalidate_config_cache() -> None:
    """Invalidate config cache in Redis and local memory."""
    global _LOCAL_CONFIG_CACHE
    _LOCAL_CONFIG_CACHE = None
    redis_client.cache_delete(CONFIG_CACHE_KEY)


def get_cached_knowledge_stats() -> Optional[Dict]:
    """获取缓存的知识库统计"""
    return redis_client.cache_get(KNOWLEDGE_STATS_KEY)


def set_cached_knowledge_stats(stats: Dict) -> bool:
    """缓存知识库统计"""
    return redis_client.cache_set(KNOWLEDGE_STATS_KEY, stats, _ttl_with_jitter(KNOWLEDGE_STATS_TTL))


def invalidate_knowledge_cache() -> None:
    """使知识库相关缓存全部失效"""
    redis_client.cache_delete(KNOWLEDGE_STATS_KEY)
    # 清空知识库列表缓存
    for key in redis_client.cache_keys("cache:kb:*"):
        redis_client.cache_delete(key)
