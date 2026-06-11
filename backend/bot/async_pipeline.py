#!/usr/bin/env python3
"""
QQ智能助手 - 异步消息处理管道

高并发消息处理架构:
  QQ消息 → 快速接收(ack) → asyncio.Queue → Worker Pool → LLM推理 → 回复

特性:
  - 消息接收与处理解耦，不阻塞 QQ 协议连接
  - 按群优先级队列（活跃群优先）
  - 背压控制：队列满时拒绝新消息，防止 OOM
  - 每群独立限流：防止单群刷屏影响全局
  - 异步 LLM 调用：vLLM provider 使用 httpx.AsyncClient 不阻塞
"""
import asyncio
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Dict, Callable, Awaitable

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
        """
        Args:
            default_rate: 默认每群每秒允许的消息数 (30 = 3msg/s × 10群)
            default_capacity: 默认桶容量 (突发容忍)
        """
        self.default_rate = default_rate
        self.default_capacity = default_capacity
        self._buckets: Dict[str, tuple[float, float]] = {}  # group_id → (tokens, last_refill)

    def acquire(self, group_id: str) -> bool:
        """尝试获取一个令牌，返回是否成功"""
        now = time.monotonic()
        tokens, last_refill = self._buckets.get(group_id, (self.default_capacity, now))

        # 计算补充的令牌数
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
        """清理 1 小时未活跃的群桶，防止内存泄漏"""
        now = time.monotonic()
        stale = [gid for gid, (_, last) in self._buckets.items() if now - last > max_age]
        for gid in stale:
            del self._buckets[gid]


class AsyncMessagePipeline:
    """异步消息处理管道 — 高并发消息接收与回复"""

    def __init__(
        self,
        max_queue_size: int = 500,
        concurrency: int = 10,
        group_rate_limit: float = 5.0,         # 每群每秒最多5条
        priority_keywords: Optional[Dict[str, int]] = None,
    ):
        """
        Args:
            max_queue_size: 队列最大长度 (超过则拒绝)
            concurrency: 最大并发 LLM 推理数
            group_rate_limit: 每群每秒最大消息数
            priority_keywords: 关键词 → 优先级映射 (优先级值越小越优先)
        """
        self.queue: asyncio.PriorityQueue[MessageTask] = asyncio.PriorityQueue(maxsize=max_queue_size)
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.group_limiter = GroupRateLimiter(default_rate=group_rate_limit)
        self.priority_keywords = priority_keywords or {
            "急": 0, "紧急": 0, "帮我": 1, "请问": 2,
        }
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._stats: Dict[str, int] = defaultdict(int)

    def calculate_priority(self, group_id: str, message: str) -> int:
        """计算消息优先级 (数值越小优先级越高)"""
        for keyword, pri in self.priority_keywords.items():
            if keyword in message:
                return pri
        return 10  # 默认优先级

    async def enqueue(
        self,
        group_id: str,
        user_id: str,
        message: str,
        reply_callback: Optional[Callable[[str], Awaitable[None]]] = None,
    ) -> bool:
        """将消息放入处理队列，不阻塞调用方

        Returns:
            True: 成功入队
            False: 队列满，消息被丢弃
        """
        # 按群限流检查
        if not self.group_limiter.acquire(group_id):
            self._stats["group_rate_limited"] += 1
            logger.debug(f"群 {group_id} 触发限流，消息丢弃")
            return False

        priority = self.calculate_priority(group_id, message)
        task = MessageTask(
            priority=priority,
            created_at=time.monotonic(),
            group_id=group_id,
            user_id=user_id,
            message=message,
            callback=reply_callback,
        )

        try:
            self.queue.put_nowait(task)
            self._stats["enqueued"] += 1
            return True
        except asyncio.QueueFull:
            self._stats["queue_full_dropped"] += 1
            logger.warning(f"消息队列已满 ({self.queue.maxsize})，丢弃消息")
            return False

    async def _worker(self, worker_id: int, inference_fn: Callable[[str, str, str], Awaitable[str]]):
        """工作协程：从队列取消息 → 推理 → 回复"""
        while self._running:
            try:
                task = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
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

                finally:
                    self.queue.task_done()

    async def start(self, inference_fn: Callable[[str, str, str], Awaitable[str]]):
        """启动消息处理管道

        Args:
            inference_fn: 异步推理函数 async (group_id, user_id, message) → reply
        """
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i, inference_fn))
            for i in range(self.concurrency)
        ]
        logger.info(f"消息管道已启动: {self.concurrency} workers, 队列上限 {self.queue.maxsize}")

    async def stop(self):
        """优雅关闭"""
        self._running = False
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("消息管道已停止")

    def get_stats(self) -> Dict:
        """获取管道统计信息"""
        stats = dict(self._stats)
        processed = stats.get("processed", 1)
        avg_latency = stats.get("total_latency", 0) / processed if processed else 0
        return {
            **stats,
            "queue_size": self.queue.qsize(),
            "avg_latency_ms": round(avg_latency * 1000, 1),
        }
