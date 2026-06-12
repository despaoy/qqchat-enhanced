#!/usr/bin/env python3
"""
QQ智能助手 - 异步消息处理管道

高并发消息处理架构:
  QQ消息 → 快速接收(ack) → Redis Streams / 内存队列 → Worker Pool → LLM推理 → 回复

特性:
  - 消息接收与处理解耦，不阻塞 QQ 协议连接
  - 优先级流（0=最高，10=默认），Redis Streams 持久化
  - 背压控制：队列满时拒绝新消息，防止 OOM
  - 每群独立限流：防止单群刷屏影响全局
  - 消费者组：多 Worker 负载均衡
  - 死信队列：失败消息自动转入 mq:dead_letter
  - Redis 不可用时自动回退到内存队列
  - 异步 LLM 调用：vLLM provider 使用 httpx.AsyncClient 不阻塞
"""
import asyncio
import os
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Dict, Callable, Awaitable

from cache.message_queue import RedisMessageQueue, QueueMessage

logger = logging.getLogger(__name__)


@dataclass(order=True)
class MessageTask:
    """消息处理任务 (优先级队列元素)"""
    priority: int          # 越小越优先 (0=最高优先级)
    created_at: float = field(compare=False)
    group_id: str = field(compare=False)
    user_id: str = field(compare=False)
    message: str = field(compare=False)
    callback: Optional[Callable[[str], Awaitable[None]]] = field(compare=False, default=None)


class GroupRateLimiter:
    """按群独立的令牌桶限流器"""

    def __init__(self, default_rate: float = 30.0, default_capacity: int = 60):
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self._buckets: Dict[str, tuple[float, float]] = {}

    def acquire(self, group_id: str) -> bool:
        now = time.monotonic()
        tokens, last_refill = self._buckets.get(group_id, (self.default_capacity, now))
        elapsed = now - last_refill
        refill = elapsed * self.default_rate
        tokens = min(self.default_capacity, tokens + refill)

        if tokens >= 1.0:
            self._buckets[group_id] = (tokens - 1.0, now)
            return True
        else:
            self._buckets[group_id] = (tokens, now)
            return False

    def cleanup(self, max_age: float = 3600.0):
        now = time.monotonic()
        stale = [gid for gid, (_, last) in self._buckets.items() if now - last > max_age]
        for gid in stale:
            del self._buckets[gid]


class AsyncMessagePipeline:
    """异步消息处理管道 — Redis Streams + 内存回退"""

    def __init__(
        self,
        max_queue_size: int = 500,
        concurrency: int = 10,
        group_rate_limit: float = 5.0,
        priority_keywords: Optional[Dict[str, int]] = None,
        redis_url: Optional[str] = None,
    ):
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.group_limiter = GroupRateLimiter(default_rate=group_rate_limit)
        self.priority_keywords = priority_keywords or {
            "急": 0, "紧急": 0, "帮我": 1, "请问": 2,
        }
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._stats: Dict[str, int] = defaultdict(int)

        # Redis Streams 消息队列
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._mq = RedisMessageQueue(redis_url=self._redis_url)

        # 内存回退队列（仅 Redis 不可用时使用）
        self._fallback_queue: asyncio.PriorityQueue[MessageTask] = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )
        self._use_redis = True

        # 回调映射 (message_id → callback)
        self._callbacks: Dict[str, Callable[[str], Awaitable[None]]] = {}

    def calculate_priority(self, group_id: str, message: str) -> int:
        """计算消息优先级 (数值越小优先级越高)"""
        for keyword, pri in self.priority_keywords.items():
            if keyword in message:
                return pri
        return 10

    async def enqueue(
        self,
        group_id: str,
        user_id: str,
        message: str,
        reply_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> bool:
        """将消息放入处理队列

        Returns:
            True: 成功入队
            False: 队列满或限流，消息被丢弃
        """
        if not self.group_limiter.acquire(group_id):
            self._stats["group_rate_limited"] += 1
            logger.debug(f"群 {group_id} 触发限流，消息丢弃")
            return False

        priority = self.calculate_priority(group_id, message)

        # 存储回调
        if reply_callback:
            import uuid
            msg_id = uuid.uuid4().hex
            self._callbacks[msg_id] = reply_callback
        else:
            msg_id = None

        # 尝试 Redis 入队
        if self._use_redis:
            try:
                result = await self._mq.enqueue(
                    group_id=group_id,
                    user_id=user_id,
                    message=message,
                    priority=priority,
                )
                if result:
                    self._stats["enqueued"] += 1
                    return True
                self._stats["queue_full_dropped"] += 1
                return False
            except Exception as e:
                logger.warning(f"Redis入队失败，回退到内存队列: {e}")
                self._use_redis = False

        # 内存回退
        task = MessageTask(
            priority=priority,
            created_at=time.monotonic(),
            group_id=group_id,
            user_id=user_id,
            message=message,
            callback=reply_callback,
        )
        try:
            self._fallback_queue.put_nowait(task)
            self._stats["enqueued"] += 1
            return True
        except asyncio.QueueFull:
            self._stats["queue_full_dropped"] += 1
            logger.warning(f"消息队列已满，丢弃消息")
            return False

    async def _dequeue(self, timeout: float = 1.0) -> Optional[MessageTask]:
        """从队列取出消息，优先使用 Redis Streams"""
        if self._use_redis:
            try:
                msg = await self._mq.dequeue(timeout=timeout)
                if msg:
                    callback = self._callbacks.pop(msg.id, None)
                    return MessageTask(
                        priority=msg.priority,
                        created_at=msg.created_at,
                        group_id=msg.group_id,
                        user_id=msg.user_id,
                        message=msg.message,
                        callback=callback,
                    )
                return None
            except Exception as e:
                logger.warning(f"Redis出队失败，回退到内存队列: {e}")
                self._use_redis = False

        # 内存回退
        try:
            return await asyncio.wait_for(self._fallback_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def _worker(self, worker_id: int, inference_fn: Callable[[str, str, str], Awaitable[str]]):
        """工作协程：从队列取消息 → 推理 → 回复"""
        while self._running:
            task = await self._dequeue(timeout=1.0)
            if task is None:
                continue

            async with self.semaphore:
                start = time.monotonic()
                try:
                    reply = await inference_fn(task.group_id, task.user_id, task.message)
                    elapsed = time.monotonic() - start
                    self._stats["processed"] += 1
                    self._stats["total_latency"] += elapsed

                    if task.callback:
                        await task.callback(reply)

                except Exception as e:
                    self._stats["failed"] += 1
                    logger.error(f"Worker {worker_id} 处理失败: {e}")

                    # Redis 模式下移动到死信队列
                    if self._use_redis:
                        try:
                            await self._mq.move_to_dead_letter(
                                QueueMessage(
                                    group_id=task.group_id,
                                    user_id=task.user_id,
                                    message=task.message,
                                    priority=task.priority,
                                ),
                                reason=str(e),
                            )
                        except Exception:
                            pass

    async def start(self, inference_fn: Callable[[str, str, str], Awaitable[str]]):
        """启动消息处理管道"""
        self._running = True

        # 初始化 Redis 连接
        await self._mq._ensure_client()

        # 启动后台 pending 消息认领循环
        asyncio.create_task(self._claim_loop())

        self._workers = [
            asyncio.create_task(self._worker(i, inference_fn))
            for i in range(self.concurrency)
        ]

        mode = "Redis Streams" if self._use_redis else "内存队列"
        logger.info(f"消息管道已启动: {self.concurrency} workers, 模式={mode}")

    async def _claim_loop(self):
        """定期认领超时的 pending 消息"""
        while self._running:
            try:
                await asyncio.sleep(15)  # 每15秒检查一次
                if self._use_redis:
                    await self._mq.claim_pending_messages()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"Claim loop error: {e}")

    async def stop(self):
        """优雅关闭"""
        self._running = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        await self._mq.close()
        logger.info("消息管道已停止")

    def get_stats(self) -> Dict:
        """获取管道统计信息"""
        stats = dict(self._stats)
        processed = max(stats.get("processed", 1), 1)
        avg_latency = stats.get("total_latency", 0) / processed
        stats.update({
            "queue_size": self._fallback_queue.qsize() if not self._use_redis else 0,
            "avg_latency_ms": round(avg_latency * 1000, 1),
            "mode": "redis" if self._use_redis else "memory",
        })
        return stats
