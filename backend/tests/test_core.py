"""
核心模块单元测试

测试不需要外部服务的核心逻辑：
- 语义缓存 L1 (进程内LRU)
- 熔断器状态机
- 消息队列数据模型
- 文本归一化
- 令牌桶限流器
"""

import asyncio
import time
import pytest

# ============================================
# 语义缓存 L1 测试
# ============================================

class TestL1LRUCache:
    """L1 进程内 LRU 缓存测试"""

    def _make_cache(self, max_size=5, ttl=10.0):
        from cache.semantic_cache import L1LRUCache
        return L1LRUCache(max_size=max_size, default_ttl=ttl)

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        cache = self._make_cache()
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key(self):
        cache = self._make_cache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self):
        cache = self._make_cache(ttl=0.1)
        await cache.set("key1", "value1")
        # Should exist immediately
        assert await cache.get("key1") == "value1"
        # Wait for TTL to expire
        await asyncio.sleep(0.15)
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        cache = self._make_cache(max_size=3)
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        # Adding 4th item should evict "a" (oldest)
        await cache.set("d", 4)
        assert await cache.get("a") is None
        assert await cache.get("d") == 4

    @pytest.mark.asyncio
    async def test_lru_access_promotes(self):
        cache = self._make_cache(max_size=3)
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        # Access "a" to promote it
        await cache.get("a")
        # Adding 4th item should evict "b" (now oldest)
        await cache.set("d", 4)
        assert await cache.get("a") == 1
        assert await cache.get("b") is None

    @pytest.mark.asyncio
    async def test_delete(self):
        cache = self._make_cache()
        await cache.set("key1", "value1")
        assert await cache.delete("key1") is True
        assert await cache.get("key1") is None
        assert await cache.delete("key1") is False

    @pytest.mark.asyncio
    async def test_clear(self):
        cache = self._make_cache()
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.clear()
        assert await cache.get("a") is None
        assert await cache.get("b") is None

    @pytest.mark.asyncio
    async def test_stats(self):
        cache = self._make_cache()
        await cache.set("a", 1)
        await cache.get("a")  # hit
        await cache.get("missing")  # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1


# ============================================
# 文本归一化测试
# ============================================

class TestTextNormalization:
    """文本归一化工具测试"""

    def test_normalize_lowercase(self):
        from cache.semantic_cache import normalize_text
        assert normalize_text("Hello World") == "helloworld"

    def test_normalize_strip(self):
        from cache.semantic_cache import normalize_text
        assert normalize_text("  hello  ") == "hello"

    def test_normalize_punctuation(self):
        from cache.semantic_cache import normalize_text
        assert normalize_text("你好，世界！") == "你好世界"

    def test_normalize_whitespace(self):
        from cache.semantic_cache import normalize_text
        assert normalize_text("hello   world") == "helloworld"

    def test_text_hash_deterministic(self):
        from cache.semantic_cache import text_hash
        h1 = text_hash("hello world")
        h2 = text_hash("hello world")
        assert h1 == h2

    def test_text_hash_different_inputs(self):
        from cache.semantic_cache import text_hash
        h1 = text_hash("hello")
        h2 = text_hash("world")
        assert h1 != h2


# ============================================
# 熔断器状态机测试
# ============================================

class TestCircuitBreaker:
    """熔断器三状态机测试"""

    def _make_cb(self, threshold=3, timeout=1.0):
        from infra.circuit_breaker import CircuitBreaker, DegradationMode
        return CircuitBreaker(
            name="test",
            failure_threshold=threshold,
            recovery_timeout=timeout,
            degradation_mode=DegradationMode.DEFAULT,
        )

    @pytest.mark.asyncio
    async def test_initial_state_closed(self):
        cb = self._make_cb()
        assert cb.state.value == "closed"

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        cb = self._make_cb(threshold=3)
        async def failing_func():
            raise RuntimeError("fail")

        for _ in range(3):
            try:
                await cb.call(failing_func)
            except RuntimeError:
                pass
        assert cb.state.value == "open"

    @pytest.mark.asyncio
    async def test_success_resets_failures(self):
        cb = self._make_cb(threshold=3)
        async def failing_func():
            raise RuntimeError("fail")
        async def success_func():
            return "ok"

        # 2 failures
        for _ in range(2):
            try:
                await cb.call(failing_func)
            except RuntimeError:
                pass
        # 1 success resets
        result = await cb.call(success_func)
        assert result == "ok"
        # Need 3 more failures to open
        for _ in range(3):
            try:
                await cb.call(failing_func)
            except RuntimeError:
                pass
        assert cb.state.value == "open"

    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self):
        cb = self._make_cb(threshold=2, timeout=0.1)
        async def failing_func():
            raise RuntimeError("fail")

        for _ in range(2):
            try:
                await cb.call(failing_func)
            except RuntimeError:
                pass
        assert cb.state.value == "open"

        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        assert cb.state.value == "half_open"

    @pytest.mark.asyncio
    async def test_degradation_returns_default(self):
        from infra.circuit_breaker import CircuitBreaker, DegradationMode
        cb = CircuitBreaker(
            name="test",
            failure_threshold=1,
            recovery_timeout=60,
            degradation_mode=DegradationMode.DEFAULT,
        )
        cb.set_default("fallback")
        async def failing_func():
            raise RuntimeError("fail")

        # Trigger open
        try:
            await cb.call(failing_func)
        except RuntimeError:
            pass
        # Should return default value instead of raising
        result = await cb.call(failing_func)
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_reset(self):
        cb = self._make_cb(threshold=1)
        async def failing_func():
            raise RuntimeError("fail")
        try:
            await cb.call(failing_func)
        except RuntimeError:
            pass
        assert cb.state.value == "open"
        await cb.reset()
        assert cb.state.value == "closed"

    @pytest.mark.asyncio
    async def test_stats(self):
        cb = self._make_cb()
        async def success_func():
            return "ok"
        await cb.call(success_func)
        stats = cb.get_stats()
        assert stats["success_calls"] == 1
        assert stats["state"] == "closed"


# ============================================
# 消息队列数据模型测试
# ============================================

class TestQueueMessage:
    """消息队列数据模型测试"""

    def test_to_dict_and_from_dict(self):
        from cache.message_queue import QueueMessage
        msg = QueueMessage(
            group_id="g1",
            user_id="u1",
            message="hello",
            priority=5,
        )
        d = msg.to_dict()
        restored = QueueMessage.from_dict(d)
        assert restored.group_id == "g1"
        assert restored.user_id == "u1"
        assert restored.message == "hello"
        assert restored.priority == 5

    def test_default_values(self):
        from cache.message_queue import QueueMessage
        msg = QueueMessage()
        assert msg.priority == 10
        assert msg.retry_count == 0
        assert msg.group_id == ""
        assert msg.message == ""


# ============================================
# 令牌桶限流器测试
# ============================================

class TestGroupRateLimiter:
    """按群限流器测试"""

    def _make_limiter(self, rate=10.0, capacity=20):
        from bot.async_pipeline import GroupRateLimiter
        return GroupRateLimiter(default_rate=rate, default_capacity=capacity)

    def test_allows_within_capacity(self):
        limiter = self._make_limiter(rate=10, capacity=20)
        for _ in range(20):
            assert limiter.acquire("g1") is True

    def test_rejects_over_capacity(self):
        limiter = self._make_limiter(rate=1, capacity=2)
        assert limiter.acquire("g1") is True
        assert limiter.acquire("g1") is True
        assert limiter.acquire("g1") is False

    def test_independent_groups(self):
        limiter = self._make_limiter(rate=1, capacity=1)
        assert limiter.acquire("g1") is True
        # g2 is independent
        assert limiter.acquire("g2") is True

    def test_token_refill(self):
        limiter = self._make_limiter(rate=100, capacity=2)
        assert limiter.acquire("g1") is True
        assert limiter.acquire("g1") is True
        assert limiter.acquire("g1") is False
        # Wait for refill
        time.sleep(0.05)  # 50ms * 100/s = 5 tokens
        assert limiter.acquire("g1") is True

    def test_cleanup(self):
        limiter = self._make_limiter()
        limiter.acquire("g1")
        # Force stale by manipulating last_refill time
        limiter._buckets["g1"] = (0, time.monotonic() - 7200)
        limiter.cleanup(max_age=3600)
        assert "g1" not in limiter._buckets
