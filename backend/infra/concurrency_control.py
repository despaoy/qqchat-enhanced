"""Concurrency controls for chat generation.

This module is intentionally dependency-light so it can protect both the
management chat endpoint and AstrBot integration before any model work starts.
"""

from __future__ import annotations

import asyncio
import itertools
import os
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


class RateLimitExceeded(Exception):
    def __init__(self, scope: str, retry_after: float = 1.0):
        super().__init__(scope)
        self.scope = scope
        self.retry_after = retry_after


class InferenceQueueFull(Exception):
    pass


@dataclass
class _Bucket:
    tokens: float
    updated_at: float


class TokenBucketLimiter:
    def __init__(self, rate: float, capacity: int):
        self.rate = max(float(rate), 0.0)
        self.capacity = max(int(capacity), 1)
        self._buckets: dict[str, _Bucket] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, key: str, cost: float = 1.0) -> tuple[bool, float]:
        now = time.monotonic()
        async with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = _Bucket(tokens=float(self.capacity), updated_at=now)
                self._buckets[key] = bucket

            elapsed = max(0.0, now - bucket.updated_at)
            bucket.updated_at = now
            bucket.tokens = min(float(self.capacity), bucket.tokens + elapsed * self.rate)

            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True, 0.0

            if self.rate <= 0:
                return False, 60.0
            return False, max(0.0, (cost - bucket.tokens) / self.rate)

    async def cleanup(self, max_age: float = 3600.0) -> None:
        cutoff = time.monotonic() - max_age
        async with self._lock:
            stale = [key for key, bucket in self._buckets.items() if bucket.updated_at < cutoff]
            for key in stale:
                self._buckets.pop(key, None)


@dataclass(order=True)
class _QueuedInference:
    priority: int
    sequence: int
    enqueued_at: float = field(compare=False)
    session_id: str = field(compare=False)
    factory: Callable[[], Awaitable[Any]] = field(compare=False)
    future: asyncio.Future = field(compare=False)


class InferenceRuntime:
    def __init__(self) -> None:
        self.max_queue_size = int(os.getenv("INFERENCE_QUEUE_MAX_SIZE", "100"))
        self.worker_count = int(os.getenv("INFERENCE_WORKERS", os.getenv("MODEL_MAX_CONCURRENCY", "2")))
        self.queue_timeout = float(os.getenv("INFERENCE_QUEUE_TIMEOUT", "180"))
        self._queue: asyncio.PriorityQueue[_QueuedInference] = asyncio.PriorityQueue(maxsize=self.max_queue_size)
        self._sequence = itertools.count()
        self._workers_started = False
        self._workers: list[asyncio.Task] = []
        self._start_lock = asyncio.Lock()
        self._session_locks: dict[str, asyncio.Lock] = {}
        self._session_locks_guard = asyncio.Lock()
        self._active_count = 0
        self._active_guard = asyncio.Lock()
        self._stats = {"submitted": 0, "completed": 0, "failed": 0, "rejected": 0}

        self.global_limiter = TokenBucketLimiter(
            float(os.getenv("CHAT_GLOBAL_QPS", "20")),
            int(os.getenv("CHAT_GLOBAL_BURST", "40")),
        )
        self.conversation_limiter = TokenBucketLimiter(
            float(os.getenv("CHAT_CONVERSATION_QPS", "1")),
            int(os.getenv("CHAT_CONVERSATION_BURST", "5")),
        )
        self.sender_limiter = TokenBucketLimiter(
            float(os.getenv("CHAT_SENDER_QPS", "0.5")),
            int(os.getenv("CHAT_SENDER_BURST", "3")),
        )

    async def check_rate_limits(self, platform: str, conversation_id: str, sender_id: str) -> None:
        checks = [
            ("global", self.global_limiter, "global"),
            ("conversation", self.conversation_limiter, f"{platform}:{conversation_id}"),
        ]
        if sender_id:
            checks.append(("sender", self.sender_limiter, f"{platform}:{sender_id}"))

        for scope, limiter, key in checks:
            allowed, retry_after = await limiter.acquire(key)
            if not allowed:
                raise RateLimitExceeded(scope, retry_after)

    async def submit(
        self,
        factory: Callable[[], Awaitable[Any]],
        *,
        session_id: str,
        priority: int,
        timeout: float | None = None,
    ) -> Any:
        await self._ensure_workers()
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        item = _QueuedInference(
            priority=priority,
            sequence=next(self._sequence),
            enqueued_at=time.monotonic(),
            session_id=session_id or "default",
            factory=factory,
            future=future,
        )
        try:
            self._queue.put_nowait(item)
        except asyncio.QueueFull as exc:
            self._stats["rejected"] += 1
            raise InferenceQueueFull("inference queue is full") from exc

        self._stats["submitted"] += 1
        try:
            return await asyncio.wait_for(future, timeout=timeout or self.queue_timeout)
        except asyncio.TimeoutError:
            if not future.done():
                future.cancel()
            raise

    async def _ensure_workers(self) -> None:
        if self._workers_started:
            return
        async with self._start_lock:
            if self._workers_started:
                return
            for idx in range(max(1, self.worker_count)):
                self._workers.append(asyncio.create_task(self._worker(idx)))
            self._workers_started = True

    async def _get_session_lock(self, session_id: str) -> asyncio.Lock:
        async with self._session_locks_guard:
            lock = self._session_locks.get(session_id)
            if lock is None:
                lock = asyncio.Lock()
                self._session_locks[session_id] = lock
            return lock

    async def _worker(self, worker_id: int) -> None:
        while True:
            item = await self._queue.get()
            try:
                if item.future.cancelled():
                    continue
                lock = await self._get_session_lock(item.session_id)
                async with lock:
                    if item.future.cancelled():
                        continue
                    async with self._active_guard:
                        self._active_count += 1
                    try:
                        result = await item.factory()
                    finally:
                        async with self._active_guard:
                            self._active_count = max(0, self._active_count - 1)
                if not item.future.done():
                    item.future.set_result(result)
                self._stats["completed"] += 1
            except Exception as exc:
                self._stats["failed"] += 1
                if not item.future.done():
                    item.future.set_exception(exc)
            finally:
                self._queue.task_done()

    def priority_for(self, source: str, conversation_type: str) -> int:
        if source == "admin":
            return 0
        if conversation_type == "private":
            return 10
        if conversation_type == "channel":
            return 40
        return 50

    def stats(self) -> dict[str, Any]:
        return {
            **self._stats,
            "queue_size": self._queue.qsize(),
            "max_queue_size": self.max_queue_size,
            "workers": self.worker_count,
            "active": self._active_count,
            "session_locks": len(self._session_locks),
        }


inference_runtime = InferenceRuntime()
