#!/usr/bin/env python3
"""
QQ智能助手 - 异步推理服务 (供消息管道使用)

将不同推理后端 (Mock/Ollama/vLLM) 统一为空闲接口，
供 AsyncMessagePipeline 使用。
"""
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class AsyncInferenceService:
    """异步推理服务 — 统一接口，支持多后端"""

    def __init__(
        self,
        backend: str = "mock",       # mock / ollama / vllm / openai_compat
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
        self._stats = {"total": 0, "success": 0, "failed": 0, "total_latency": 0.0}

    async def infer(self, group_id: str, user_id: str, message: str) -> str:
        """异步推理 — 不阻塞事件循环

        Returns:
            LLM 生成的回复文本
        """
        import time
        start = time.monotonic()
        self._stats["total"] += 1

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
            return reply

        except Exception as e:
            self._stats["failed"] += 1
            logger.error(f"推理失败 [{self.backend}]: {e}")
            return f"[系统提示] 暂时无法处理您的消息，请稍后再试"

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
        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10.0)) as client:
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
        """vLLM 推理 (OpenAI 兼容协议)"""
        import os
        max_tokens = int(os.getenv("MAX_TOKENS", "512"))
        temperature = float(os.getenv("TEMPERATURE", "0.85"))

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10.0)) as client:
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

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10.0)) as client:
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

    def get_stats(self) -> dict:
        """获取推理统计"""
        s = dict(self._stats)
        processed = s.get("success", 1)
        return {
            **s,
            "avg_latency_ms": round(s["total_latency"] / processed * 1000, 1) if processed else 0,
            "backend": self.backend,
        }
