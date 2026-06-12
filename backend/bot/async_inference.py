#!/usr/bin/env python3
"""
QQ智能助手 - 异步推理服务 (供消息管道使用)

将不同推理后端 (Mock/Ollama/vLLM) 统一为异步接口，
供 AsyncMessagePipeline 使用。

阶段3优化：
  - 语义缓存：L1进程内LRU + L2 Redis，减少重复推理
  - 熔断器保护：vLLM 连续失败自动降级
  - 连接池复用：共享 httpx.AsyncClient，避免每请求创建
"""
import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class AsyncInferenceService:
    """异步推理服务 — 统一接口，支持多后端"""

    def __init__(
        self,
        backend: str = "mock",
        ollama_url: str = "http://localhost:11434",
        vllm_url: str = "http://localhost:8001/v1",
        openai_url: str = "https://api.deepseek.com",
        openai_key: str = "",
        model_name: str = "qwen2.5-7b",
        timeout: float = 120.0,
    ):
        self.backend = backend
        self.ollama_url = ollama_url
        self.vllm_url = vllm_url
        self.openai_url = openai_url
        self.openai_key = openai_key
        self.model_name = model_name
        self.timeout = timeout
        self._stats = {"total": 0, "success": 0, "failed": 0, "total_latency": 0.0, "cache_hits": 0}

        # 共享 httpx 客户端（懒初始化）
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()

        # 语义缓存（懒初始化）
        self._semantic_cache = None

        # 熔断器（懒初始化，仅 vLLM 后端使用）
        self._circuit_breaker = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        """确保 httpx.AsyncClient 已创建（连接池复用）"""
        if self._client is not None and not self._client.is_closed:
            return self._client
        async with self._client_lock:
            if self._client is not None and not self._client.is_closed:
                return self._client
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
            )
            return self._client

    async def _ensure_cache(self):
        """懒初始化语义缓存"""
        if self._semantic_cache is None:
            try:
                from cache.semantic_cache import get_semantic_cache
                self._semantic_cache = await get_semantic_cache()
            except Exception as e:
                logger.warning(f"语义缓存初始化失败: {e}")

    async def _ensure_circuit_breaker(self):
        """懒初始化熔断器"""
        if self._circuit_breaker is None:
            try:
                from infra.circuit_breaker import CircuitBreaker, DegradationMode
                self._circuit_breaker = CircuitBreaker(
                    name="inference_service",
                    failure_threshold=5,
                    recovery_timeout=30.0,
                    half_open_max_calls=2,
                    degradation_mode=DegradationMode.DEFAULT,
                )
                self._circuit_breaker.set_default("[系统提示] 暂时无法处理您的消息，请稍后再试")
            except Exception as e:
                logger.warning(f"熔断器初始化失败: {e}")

    async def infer(self, group_id: str, user_id: str, message: str) -> str:
        """异步推理 — 不阻塞事件循环，支持语义缓存和熔断保护"""
        import time
        start = time.monotonic()
        self._stats["total"] += 1

        # 检查语义缓存
        await self._ensure_cache()
        if self._semantic_cache:
            try:
                cached = await self._semantic_cache.get(message, context=f"g:{group_id}")
                if cached is not None:
                    self._stats["cache_hits"] += 1
                    self._stats["success"] += 1
                    logger.debug(f"语义缓存命中: {message[:30]}...")
                    return cached
            except Exception as e:
                logger.debug(f"缓存查询失败: {e}")

        # 熔断器保护
        await self._ensure_circuit_breaker()
        if self._circuit_breaker and self._circuit_breaker.state.value == "open":
            logger.warning("熔断器开启，执行降级")
            self._stats["failed"] += 1
            return "[系统提示] 推理服务暂时不可用，请稍后再试"

        try:
            if self.backend == "mock":
                reply = await self._infer_mock(message)
            elif self.backend == "ollama":
                reply = await self._infer_ollama(message)
            elif self.backend == "vllm":
                reply = await self._infer_vllm(message)
            elif self.backend == "openai_compat":
                reply = await self._infer_openai(message)
            else:
                reply = await self._infer_mock(message)

            self._stats["success"] += 1
            self._stats["total_latency"] += time.monotonic() - start

            # 写入缓存
            if self._semantic_cache:
                try:
                    await self._semantic_cache.set(message, reply, context=f"g:{group_id}")
                except Exception as e:
                    logger.debug(f"缓存写入失败: {e}")

            # 熔断器记录成功
            if self._circuit_breaker:
                self._circuit_breaker._stats.record_success()
                if self._circuit_breaker.state.value == "half_open":
                    await self._circuit_breaker.reset()

            return reply

        except Exception as e:
            self._stats["failed"] += 1

            # 熔断器记录失败
            if self._circuit_breaker:
                self._circuit_breaker._stats.record_failure()
                self._circuit_breaker._failure_count += 1
                self._circuit_breaker._last_failure_time = time.monotonic()
                if self._circuit_breaker._failure_count >= self._circuit_breaker.failure_threshold:
                    self._circuit_breaker._transition_to_open()

            logger.error(f"推理失败 [{self.backend}]: {e}")
            return "[系统提示] 暂时无法处理您的消息，请稍后再试"

    async def _infer_mock(self, message: str) -> str:
        """Mock 推理 (开发测试用)"""
        import random
        await asyncio.sleep(random.uniform(0.1, 0.3))
        replies = [
            f"收到你的消息啦～关于「{message[:20]}」我来想想怎么回复你～",
            f"哈哈，这个问题有意思！{message[:20]}... 😄",
            f"嗯嗯，我理解你的意思～ {message[:20]}... 让我帮你看看！",
        ]
        return random.choice(replies)

    async def _infer_ollama(self, message: str) -> str:
        """Ollama 推理"""
        client = await self._ensure_client()
        resp = await client.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": [{"role": "user", "content": message}],
                "stream": False,
            },
        )
        if resp.status_code == 200:
            return resp.json()["message"]["content"].strip()
        raise RuntimeError(f"Ollama 错误: {resp.status_code}")

    async def _infer_vllm(self, message: str) -> str:
        """vLLM 推理 (OpenAI 兼容协议，连接池复用)"""
        max_tokens = int(os.getenv("MAX_TOKENS", "512"))
        temperature = float(os.getenv("TEMPERATURE", "0.85"))

        client = await self._ensure_client()
        resp = await client.post(
            f"{self.vllm_url}/chat/completions",
            json={
                "model": self.model_name,
                "messages": [{"role": "user", "content": message}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": 0.92,
            },
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        raise RuntimeError(f"vLLM 错误: {resp.status_code} - {resp.text[:200]}")

    async def _infer_openai(self, message: str) -> str:
        """OpenAI 兼容 API 推理"""
        if not self.openai_key:
            raise RuntimeError("未配置 OpenAI API Key")

        client = await self._ensure_client()
        resp = await client.post(
            f"{self.openai_url}/v1/chat/completions",
            json={
                "model": self.model_name,
                "messages": [{"role": "user", "content": message}],
                "max_tokens": 512,
                "temperature": 0.8,
            },
            headers={"Authorization": f"Bearer {self.openai_key}"},
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        raise RuntimeError(f"OpenAI 错误: {resp.status_code}")

    async def close(self):
        """关闭连接池"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        if self._semantic_cache:
            await self._semantic_cache.close()

    def get_stats(self) -> dict:
        """获取推理统计"""
        s = dict(self._stats)
        processed = max(s.get("success", 1), 1)
        return {
            **s,
            "avg_latency_ms": round(s["total_latency"] / processed * 1000, 1) if processed else 0,
            "backend": self.backend,
            "cache_hit_rate": round(
                s.get("cache_hits", 0) / max(s.get("total", 1), 1) * 100, 1
            ),
        }
