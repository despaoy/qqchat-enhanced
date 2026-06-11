"""异步处理机制模块。

提供基于asyncio的异步任务队列，支持优先级调度、
线程池执行、任务取消/超时控制和回调通知。
"""

import asyncio
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """任务状态枚举。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(order=True)
class TaskItem:
    """任务项，支持按优先级排序。"""

    sort_key: int = field(init=False)
    priority: int = field(default=0)
    task_id: str = field(default="")
    coroutine: Optional[Coroutine] = field(default=None, repr=False)
    fn: Optional[Callable] = field(default=None, repr=False)
    args: tuple = field(default=(), repr=False)
    kwargs: dict = field(default_factory=dict, repr=False)
    is_cpu_bound: bool = field(default=False)
    timeout: Optional[float] = field(default=None)
    on_complete: Optional[Callable[[str, Any], None]] = field(default=None, repr=False)
    status: TaskStatus = field(default=TaskStatus.PENDING)
    result: Any = field(default=None, repr=False)
    error: Optional[str] = field(default=None)
    created_at: float = field(default_factory=time.monotonic)
    started_at: Optional[float] = field(default=None)
    completed_at: Optional[float] = field(default=None)

    def __post_init__(self) -> None:
        # 优先级数值越小越优先，取负数使 heapq 弹出最高优先级
        self.sort_key = self.priority


class AsyncTaskQueue:
    """基于asyncio的异步任务队列。

    支持优先级调度、CPU密集型任务的线程池执行、
    任务取消/超时控制和完成回调。

    使用示例::

        queue = AsyncTaskQueue(max_workers=4)

        # 提交异步任务
        task_id = await queue.submit(my_async_func, arg1, arg2, priority=1)

        # 提交CPU密集型任务
        task_id = await queue.submit_cpu_bound(cpu_func, data, priority=0)

        # 获取结果
        result = await queue.get_result(task_id)

        # 关闭队列
        await queue.shutdown()
    """

    def __init__(
        self,
        max_workers: int = 4,
        max_queue_size: int = 1000,
    ) -> None:
        """初始化异步任务队列。

        Args:
            max_workers: 线程池最大工作线程数，用于CPU密集型任务。
            max_queue_size: 队列最大容量。
        """
        self._max_workers = max_workers
        self._max_queue_size = max_queue_size
        self._queue: asyncio.PriorityQueue[TaskItem] = asyncio.PriorityQueue(
            maxsize=max_queue_size
        )
        self._tasks: Dict[str, TaskItem] = {}
        self._results: Dict[str, Any] = {}
        self._running_futures: Dict[str, asyncio.Future] = {}
        self._thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self._lock = asyncio.Lock()
        self._started = False
        self._closed = False
        self._worker_task: Optional[asyncio.Task] = None
        self._total_submitted = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_cancelled = 0
        logger.info(
            "异步任务队列初始化，max_workers=%d, max_queue_size=%d",
            max_workers,
            max_queue_size,
        )

    async def start(self) -> None:
        """启动队列的工作循环。"""
        if self._started:
            return
        self._started = True
        self._closed = False
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("异步任务队列已启动")

    async def _worker_loop(self) -> None:
        """工作循环，从队列取出任务并执行。"""
        while not self._closed:
            try:
                task_item = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            if task_item.status == TaskStatus.CANCELLED:
                self._queue.task_done()
                continue

            task_item.status = TaskStatus.RUNNING
            task_item.started_at = time.monotonic()
            logger.debug("开始执行任务: %s (优先级: %d)", task_item.task_id, task_item.priority)

            try:
                if task_item.is_cpu_bound and task_item.fn is not None:
                    future = asyncio.get_running_loop().run_in_executor(
                        self._thread_pool,
                        task_item.fn,
                        *task_item.args,
                        **task_item.kwargs,
                    )
                elif task_item.coroutine is not None:
                    future = asyncio.create_task(task_item.coroutine)
                else:
                    raise ValueError(f"任务 {task_item.task_id} 没有可执行的协程或函数")

                self._running_futures[task_item.task_id] = future

                if task_item.timeout is not None:
                    result = await asyncio.wait_for(future, timeout=task_item.timeout)
                else:
                    result = await future

                task_item.status = TaskStatus.COMPLETED
                task_item.result = result
                task_item.completed_at = time.monotonic()
                self._results[task_item.task_id] = result
                self._total_completed += 1
                logger.debug("任务完成: %s", task_item.task_id)

                if task_item.on_complete is not None:
                    try:
                        task_item.on_complete(task_item.task_id, result)
                    except Exception as cb_err:
                        logger.error("任务回调执行失败: %s, 错误: %s", task_item.task_id, cb_err)

            except asyncio.CancelledError:
                task_item.status = TaskStatus.CANCELLED
                task_item.completed_at = time.monotonic()
                self._total_cancelled += 1
                logger.info("任务已取消: %s", task_item.task_id)

            except asyncio.TimeoutError:
                task_item.status = TaskStatus.FAILED
                task_item.error = f"任务超时 ({task_item.timeout}s)"
                task_item.completed_at = time.monotonic()
                self._total_failed += 1
                logger.warning("任务超时: %s (超时: %ss)", task_item.task_id, task_item.timeout)

            except Exception as exc:
                task_item.status = TaskStatus.FAILED
                task_item.error = str(exc)
                task_item.completed_at = time.monotonic()
                self._total_failed += 1
                logger.error("任务执行失败: %s, 错误: %s", task_item.task_id, exc)

            finally:
                self._running_futures.pop(task_item.task_id, None)
                self._queue.task_done()

    async def submit(
        self,
        coro: Coroutine,
        priority: int = 0,
        timeout: Optional[float] = None,
        on_complete: Optional[Callable[[str, Any], None]] = None,
    ) -> str:
        """提交异步任务到队列。

        Args:
            coro: 要执行的协程对象。
            priority: 优先级，数值越小越优先执行，默认为0。
            timeout: 超时时间（秒），None表示不限时。
            on_complete: 完成回调函数，签名为 (task_id, result) -> None。

        Returns:
            任务ID。

        Raises:
            RuntimeError: 队列未启动或已关闭。
            asyncio.QueueFull: 队列已满。
        """
        if not self._started:
            await self.start()
        if self._closed:
            raise RuntimeError("队列已关闭，无法提交新任务")

        task_id = str(uuid.uuid4())
        task_item = TaskItem(
            priority=priority,
            task_id=task_id,
            coroutine=coro,
            timeout=timeout,
            on_complete=on_complete,
        )

        async with self._lock:
            self._tasks[task_id] = task_item
            self._total_submitted += 1

        await self._queue.put(task_item)
        logger.debug("提交异步任务: %s (优先级: %d)", task_id, priority)
        return task_id

    async def submit_cpu_bound(
        self,
        fn: Callable,
        *args: Any,
        priority: int = 0,
        timeout: Optional[float] = None,
        on_complete: Optional[Callable[[str, Any], None]] = None,
        **kwargs: Any,
    ) -> str:
        """提交CPU密集型任务到线程池执行。

        Args:
            fn: 要执行的同步函数。
            *args: 函数位置参数。
            priority: 优先级，数值越小越优先执行。
            timeout: 超时时间（秒）。
            on_complete: 完成回调函数。
            **kwargs: 函数关键字参数。

        Returns:
            任务ID。

        Raises:
            RuntimeError: 队列未启动或已关闭。
        """
        if not self._started:
            await self.start()
        if self._closed:
            raise RuntimeError("队列已关闭，无法提交新任务")

        task_id = str(uuid.uuid4())
        task_item = TaskItem(
            priority=priority,
            task_id=task_id,
            fn=fn,
            args=args,
            kwargs=kwargs,
            is_cpu_bound=True,
            timeout=timeout,
            on_complete=on_complete,
        )

        async with self._lock:
            self._tasks[task_id] = task_item
            self._total_submitted += 1

        await self._queue.put(task_item)
        logger.debug("提交CPU任务: %s (优先级: %d)", task_id, priority)
        return task_id

    async def get_result(self, task_id: str, wait: bool = True, timeout: Optional[float] = None) -> Any:
        """获取任务结果。

        Args:
            task_id: 任务ID。
            wait: 是否等待任务完成。
            timeout: 等待超时时间（秒），仅当wait=True时有效。

        Returns:
            任务结果。

        Raises:
            KeyError: 任务不存在。
            RuntimeError: 任务失败或已取消。
            asyncio.TimeoutError: 等待超时。
        """
        async with self._lock:
            task_item = self._tasks.get(task_id)
        if task_item is None:
            raise KeyError(f"任务不存在: {task_id}")

        if wait and task_item.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
            future = self._running_futures.get(task_id)
            if future is not None:
                if timeout is not None:
                    await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
                else:
                    await future
            else:
                # 任务还在队列中等待，轮询状态
                deadline = time.monotonic() + (timeout or float("inf"))
                while task_item.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    if time.monotonic() >= deadline:
                        raise asyncio.TimeoutError(f"等待任务 {task_id} 超时")
                    await asyncio.sleep(0.05)

        if task_item.status == TaskStatus.COMPLETED:
            return task_item.result
        elif task_item.status == TaskStatus.CANCELLED:
            raise RuntimeError(f"任务已取消: {task_id}")
        elif task_item.status == TaskStatus.FAILED:
            raise RuntimeError(f"任务失败: {task_id}, 错误: {task_item.error}")
        else:
            return task_item.result

    async def cancel(self, task_id: str) -> bool:
        """取消任务。

        Args:
            task_id: 任务ID。

        Returns:
            是否成功取消。
        """
        async with self._lock:
            task_item = self._tasks.get(task_id)
        if task_item is None:
            logger.warning("取消任务失败，任务不存在: %s", task_id)
            return False

        if task_item.status == TaskStatus.COMPLETED:
            return False

        if task_item.status == TaskStatus.PENDING:
            task_item.status = TaskStatus.CANCELLED
            task_item.completed_at = time.monotonic()
            self._total_cancelled += 1
            logger.info("已取消排队中的任务: %s", task_id)
            return True

        if task_item.status == TaskStatus.RUNNING:
            future = self._running_futures.get(task_id)
            if future is not None and not future.done():
                future.cancel()
                task_item.status = TaskStatus.CANCELLED
                task_item.completed_at = time.monotonic()
                self._total_cancelled += 1
                logger.info("已取消运行中的任务: %s", task_id)
                return True

        return False

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态。

        Args:
            task_id: 任务ID。

        Returns:
            任务状态，不存在时返回 None。
        """
        task_item = self._tasks.get(task_id)
        return task_item.status if task_item else None

    def get_queue_stats(self) -> Dict[str, Any]:
        """返回队列状态统计。

        Returns:
            队列统计信息字典。
        """
        status_counts: Dict[str, int] = {s.value: 0 for s in TaskStatus}
        for t in self._tasks.values():
            status_counts[t.status.value] += 1

        return {
            "started": self._started,
            "closed": self._closed,
            "max_workers": self._max_workers,
            "max_queue_size": self._max_queue_size,
            "queue_size": self._queue.qsize(),
            "total_submitted": self._total_submitted,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "total_cancelled": self._total_cancelled,
            "running_tasks": len(self._running_futures),
            "status_counts": status_counts,
        }

    async def shutdown(self, wait: bool = True) -> None:
        """关闭队列，停止接收新任务并等待运行中的任务完成。

        Args:
            wait: 是否等待运行中的任务完成。
        """
        if self._closed:
            return
        self._closed = True
        logger.info("正在关闭异步任务队列...")

        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        if wait:
            for task_id, future in list(self._running_futures.items()):
                if not future.done():
                    try:
                        await asyncio.wait_for(future, timeout=10.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        logger.warning("等待任务 %s 完成超时", task_id)

        self._thread_pool.shutdown(wait=wait)
        logger.info("异步任务队列已关闭")
