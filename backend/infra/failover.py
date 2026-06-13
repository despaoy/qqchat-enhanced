"""故障自动转移方案模块。

实现多provider的故障检测、自动转移和恢复管理，
支持多种转移策略和健康检查机制。
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger(__name__)


class ProviderHealthStatus(Enum):
    """Provider健康状态枚举。"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class FailoverStrategy(Enum):
    """故障转移策略枚举。"""
    AUTO_FAILOVER = "auto_failover"    # 自动切换
    MANUAL = "manual"                  # 需确认
    PRIORITY_BASED = "priority_based"  # 按优先级


@dataclass
class ProviderHealth:
    """Provider健康状态记录。

    Attributes:
        name: Provider名称。
        status: 当前健康状态。
        last_check_time: 最后检查时间。
        consecutive_failures: 连续失败次数。
        last_failure_time: 最后一次失败时间。
        last_success_time: 最后一次成功时间。
        latency_ms: 最近一次响应延迟（毫秒）。
        total_checks: 总检查次数。
        total_failures: 总失败次数。
    """
    name: str
    status: ProviderHealthStatus = ProviderHealthStatus.HEALTHY
    last_check_time: Optional[float] = None
    consecutive_failures: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    latency_ms: float = 0.0
    total_checks: int = 0
    total_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check_time": self.last_check_time,
            "consecutive_failures": self.consecutive_failures,
            "last_failure_time": self.last_failure_time,
            "last_success_time": self.last_success_time,
            "latency_ms": self.latency_ms,
            "total_checks": self.total_checks,
            "total_failures": self.total_failures,
        }


@dataclass
class ProviderConfig:
    """Provider配置。

    Attributes:
        name: Provider名称。
        priority: 优先级，数值越小优先级越高。
        health_check_url: 健康检查URL或标识。
        ping_fn: 自定义健康检查函数（异步），返回bool表示是否健康。
        timeout: 超时时间（秒），无响应视为故障。
    """
    name: str
    priority: int = 0
    health_check_url: Optional[str] = None
    ping_fn: Optional[Callable[[], Coroutine[Any, Any, bool]]] = None
    timeout: float = 30.0


@dataclass
class FailoverEvent:
    """故障转移事件记录。

    Attributes:
        timestamp: 事件时间。
        from_provider: 源Provider。
        to_provider: 目标Provider。
        reason: 转移原因。
    """
    timestamp: datetime
    from_provider: str
    to_provider: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "from_provider": self.from_provider,
            "to_provider": self.to_provider,
            "reason": self.reason,
        }


class HealthChecker:
    """定期健康检查器，维护provider健康状态表。

    按配置的间隔对每个provider执行心跳检测，更新健康状态。

    Args:
        check_interval: 健康检查间隔（秒）。
        timeout: 单次检查超时（秒）。
        failure_threshold: 连续失败多少次标记为UNHEALTHY。
        degraded_threshold: 连续失败多少次标记为DEGRADED。
    """

    def __init__(
        self,
        check_interval: float = 10.0,
        timeout: float = 30.0,
        failure_threshold: int = 3,
        degraded_threshold: int = 1,
    ) -> None:
        self.check_interval = check_interval
        self.timeout = timeout
        self.failure_threshold = failure_threshold
        self.degraded_threshold = degraded_threshold

        self._health_table: dict[str, ProviderHealth] = {}
        self._configs: dict[str, ProviderConfig] = {}
        self._task: Optional[asyncio.Task[None]] = None
        self._running: bool = False
        self._on_status_change: Optional[Callable[[str, ProviderHealthStatus, ProviderHealthStatus], None]] = None

    def register(self, config: ProviderConfig) -> None:
        """注册一个Provider到健康检查表。

        Args:
            config: Provider配置。
        """
        self._configs[config.name] = config
        if config.name not in self._health_table:
            self._health_table[config.name] = ProviderHealth(name=config.name)
            logger.info("注册Provider健康检查: %s (优先级: %d)", config.name, config.priority)

    def unregister(self, name: str) -> None:
        """取消注册一个Provider。"""
        self._configs.pop(name, None)
        self._health_table.pop(name, None)
        logger.info("取消注册Provider: %s", name)

    def set_on_status_change(
        self, callback: Callable[[str, ProviderHealthStatus, ProviderHealthStatus], None]
    ) -> None:
        """设置健康状态变更回调。

        Args:
            callback: 回调函数，参数为(provider_name, old_status, new_status)。
        """
        self._on_status_change = callback

    async def check_one(self, name: str) -> ProviderHealth:
        """检查单个Provider的健康状态。

        Args:
            name: Provider名称。

        Returns:
            更新后的健康状态。
        """
        config = self._configs.get(name)
        health = self._health_table.get(name)
        if config is None or health is None:
            return health or ProviderHealth(name=name)

        old_status = health.status
        start_time = time.monotonic()

        try:
            is_healthy = False
            if config.ping_fn is not None:
                try:
                    is_healthy = await asyncio.wait_for(
                        config.ping_fn(), timeout=self.timeout,
                    )
                except asyncio.TimeoutError:
                    is_healthy = False
            elif config.health_check_url is not None:
                # 默认使用简单的连接检查
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_connection(
                            config.health_check_url.split("//")[-1].split("/")[0].split(":")[0],
                            int(config.health_check_url.split(":")[-1].split("/")[0])
                            if ":" in config.health_check_url.split("//")[-1]
                            else 80,
                        ),
                        timeout=self.timeout,
                    )
                    writer.close()
                    await writer.wait_closed()
                    is_healthy = True
                except (OSError, asyncio.TimeoutError, ValueError):
                    is_healthy = False
            else:
                # 无检查方式，默认健康
                is_healthy = True

            elapsed_ms = (time.monotonic() - start_time) * 1000
            health.latency_ms = elapsed_ms
            health.last_check_time = time.monotonic()
            health.total_checks += 1

            if is_healthy:
                health.consecutive_failures = 0
                health.last_success_time = time.monotonic()
                if health.consecutive_failures == 0:
                    health.status = ProviderHealthStatus.HEALTHY
                else:
                    health.status = ProviderHealthStatus.DEGRADED
            else:
                health.consecutive_failures += 1
                health.total_failures += 1
                health.last_failure_time = time.monotonic()
                if health.consecutive_failures >= self.failure_threshold:
                    health.status = ProviderHealthStatus.UNHEALTHY
                elif health.consecutive_failures >= self.degraded_threshold:
                    health.status = ProviderHealthStatus.DEGRADED

        except Exception as e:
            logger.error("健康检查异常 [%s]: %s", name, e)
            health.consecutive_failures += 1
            health.total_failures += 1
            health.last_failure_time = time.monotonic()
            health.last_check_time = time.monotonic()
            health.total_checks += 1
            if health.consecutive_failures >= self.failure_threshold:
                health.status = ProviderHealthStatus.UNHEALTHY
            elif health.consecutive_failures >= self.degraded_threshold:
                health.status = ProviderHealthStatus.DEGRADED

        # 触发状态变更回调
        if old_status != health.status and self._on_status_change:
            try:
                self._on_status_change(name, old_status, health.status)
            except Exception as e:
                logger.error("状态变更回调执行失败 [%s]: %s", name, e)

        logger.debug(
            "健康检查 [%s]: %s (延迟: %.1fms, 连续失败: %d)",
            name, health.status.value, health.latency_ms, health.consecutive_failures,
        )
        return health

    async def check_all(self) -> dict[str, ProviderHealth]:
        """检查所有已注册Provider的健康状态（并行执行）。"""
        if not self._configs:
            return {}
        names = list(self._configs.keys())
        coros = [self.check_one(name) for name in names]
        completed = await asyncio.gather(*coros, return_exceptions=True)
        results: dict[str, ProviderHealth] = {}
        for name, result in zip(names, completed):
            if isinstance(result, Exception):
                logger.error("并行健康检查异常 [%s]: %s", name, result)
                health = self._health_table.get(name)
                results[name] = health if health else ProviderHealth(name=name)
            else:
                results[name] = result
        return results

    def get_health(self, name: str) -> Optional[ProviderHealth]:
        """获取指定Provider的健康状态。"""
        return self._health_table.get(name)

    def get_all_health(self) -> dict[str, ProviderHealth]:
        """获取所有Provider的健康状态。"""
        return dict(self._health_table)

    async def start(self) -> None:
        """启动定期健康检查。"""
        if self._running:
            logger.warning("健康检查器已在运行")
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop())
        logger.info("健康检查器已启动，间隔: %.1f 秒", self.check_interval)

    async def _check_loop(self) -> None:
        """定期健康检查循环。"""
        while self._running:
            try:
                await self.check_all()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("健康检查循环异常: %s", e)
                await asyncio.sleep(5)

    async def stop(self) -> None:
        """停止定期健康检查。"""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("健康检查器已停止")


class FailoverManager:
    """故障自动转移管理器。

    管理多provider的故障检测和自动转移，支持多种转移策略。

    Args:
        strategy: 故障转移策略。
        auto_revert: 原provider恢复后是否自动切回。
        health_checker: 自定义健康检查器，不提供则自动创建。
        on_failover: 故障转移事件回调。
    """

    def __init__(
        self,
        strategy: FailoverStrategy = FailoverStrategy.AUTO_FAILOVER,
        auto_revert: bool = False,
        health_checker: Optional[HealthChecker] = None,
        on_failover: Optional[Callable[[FailoverEvent], None]] = None,
    ) -> None:
        self.strategy = strategy
        self.auto_revert = auto_revert
        self.on_failover = on_failover

        self._health_checker = health_checker or HealthChecker()
        self._providers: dict[str, ProviderConfig] = {}
        self._active_provider: Optional[str] = None
        self._failover_history: list[FailoverEvent] = []
        self._lock = asyncio.Lock()
        self._revert_task: Optional[asyncio.Task[None]] = None

    def add_provider(self, config: ProviderConfig) -> None:
        """添加一个Provider。

        Args:
            config: Provider配置。
        """
        self._providers[config.name] = config
        self._health_checker.register(config)
        if self._active_provider is None:
            self._active_provider = config.name
            logger.info("设置初始活跃Provider: %s", config.name)

    def remove_provider(self, name: str) -> None:
        """移除一个Provider。

        如果移除的是当前活跃Provider，自动切换到下一个可用Provider。

        Args:
            name: Provider名称。
        """
        self._providers.pop(name, None)
        self._health_checker.unregister(name)

        if self._active_provider == name:
            self._active_provider = self._get_next_available_provider()
            if self._active_provider:
                logger.info("活跃Provider被移除，切换到: %s", self._active_provider)
            else:
                logger.warning("活跃Provider被移除，无可用Provider")

    @property
    def active_provider(self) -> Optional[str]:
        """获取当前活跃Provider名称。"""
        return self._active_provider

    def _get_next_available_provider(self, exclude: Optional[str] = None) -> Optional[str]:
        """获取下一个可用的Provider。

        按优先级排序，选择健康状态最好的Provider。

        Args:
            exclude: 要排除的Provider名称。

        Returns:
            下一个可用Provider名称，无可用时返回None。
        """
        candidates = []
        for name, config in self._providers.items():
            if name == exclude:
                continue
            health = self._health_checker.get_health(name)
            if health and health.status != ProviderHealthStatus.UNHEALTHY:
                candidates.append((config.priority, health.status, name))

        if not candidates:
            # 如果没有健康的，尝试降级的
            for name, config in self._providers.items():
                if name == exclude:
                    continue
                candidates.append((config.priority, ProviderHealthStatus.UNHEALTHY, name))

        if not candidates:
            return None

        # 按优先级排序，同优先级按健康状态排序
        status_order = {
            ProviderHealthStatus.HEALTHY: 0,
            ProviderHealthStatus.DEGRADED: 1,
            ProviderHealthStatus.UNHEALTHY: 2,
        }
        candidates.sort(key=lambda x: (x[0], status_order.get(x[1], 99)))
        return candidates[0][2]

    async def _execute_failover(
        self, from_provider: str, to_provider: str, reason: str
    ) -> None:
        """执行故障转移。

        Args:
            from_provider: 源Provider。
            to_provider: 目标Provider。
            reason: 转移原因。
        """
        async with self._lock:
            event = FailoverEvent(
                timestamp=datetime.now(),
                from_provider=from_provider,
                to_provider=to_provider,
                reason=reason,
            )
            self._failover_history.append(event)
            self._active_provider = to_provider

            logger.warning(
                "故障转移: %s -> %s (原因: %s)",
                from_provider, to_provider, reason,
            )

            if self.on_failover:
                try:
                    self.on_failover(event)
                except Exception as e:
                    logger.error("故障转移回调执行失败: %s", e)

    async def check_and_failover(self) -> Optional[str]:
        """检查当前活跃Provider健康状态，必要时执行故障转移。

        Returns:
            新的活跃Provider名称，未转移返回None。
        """
        if self._active_provider is None:
            return None

        health = self._health_checker.get_health(self._active_provider)
        if health is None:
            return None

        # 只在UNHEALTHY时触发转移
        if health.status != ProviderHealthStatus.UNHEALTHY:
            return None

        if self.strategy == FailoverStrategy.MANUAL:
            logger.warning(
                "Provider [%s] 不健康，但转移策略为MANUAL，需手动确认",
                self._active_provider,
            )
            return None

        # 查找下一个可用Provider
        next_provider = self._get_next_available_provider(exclude=self._active_provider)
        if next_provider is None:
            logger.error("无可用Provider可转移")
            return None

        if self.strategy == FailoverStrategy.PRIORITY_BASED:
            # 按优先级选择
            next_config = self._providers.get(next_provider)
            current_config = self._providers.get(self._active_provider)
            if next_config and current_config and next_config.priority >= current_config.priority:
                logger.info(
                    "Provider [%s] 优先级不高于当前 [%s]，不转移",
                    next_provider, self._active_provider,
                )
                return None

        old_provider = self._active_provider
        reason = (
            f"Provider [{old_provider}] 连续失败 {health.consecutive_failures} 次，"
            f"状态为 {health.status.value}"
        )
        await self._execute_failover(old_provider, next_provider, reason)
        return next_provider

    async def manual_failover(self, target_provider: str) -> bool:
        """手动执行故障转移到指定Provider。

        Args:
            target_provider: 目标Provider名称。

        Returns:
            是否转移成功。
        """
        if target_provider not in self._providers:
            logger.error("目标Provider不存在: %s", target_provider)
            return False

        if self._active_provider == target_provider:
            logger.info("目标Provider已是当前活跃Provider: %s", target_provider)
            return True

        old_provider = self._active_provider or "none"
        await self._execute_failover(
            old_provider, target_provider, "手动转移",
        )
        return True

    async def start(self) -> None:
        """启动故障转移管理器和健康检查器。"""
        await self._health_checker.start()
        if self.auto_revert:
            self._revert_task = asyncio.create_task(self._auto_revert_loop())
        logger.info("故障转移管理器已启动 (策略: %s, 自动切回: %s)", self.strategy.value, self.auto_revert)

    async def stop(self) -> None:
        """停止故障转移管理器和健康检查器。"""
        await self._health_checker.stop()
        if self._revert_task is not None:
            self._revert_task.cancel()
            try:
                await self._revert_task
            except asyncio.CancelledError:
                pass
            self._revert_task = None
        logger.info("故障转移管理器已停止")

    async def _auto_revert_loop(self) -> None:
        """自动切回循环。

        定期检查原主Provider是否恢复，恢复后自动切回。
        """
        # 记录初始主Provider（优先级最高的）
        primary_provider = self._get_primary_provider()

        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次

                if primary_provider and self._active_provider != primary_provider:
                    health = self._health_checker.get_health(primary_provider)
                    if health and health.status == ProviderHealthStatus.HEALTHY:
                        logger.info(
                            "原主Provider [%s] 已恢复，自动切回",
                            primary_provider,
                        )
                        old_provider = self._active_provider or "none"
                        await self._execute_failover(
                            old_provider,
                            primary_provider,
                            f"原主Provider [{primary_provider}] 已恢复，自动切回",
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("自动切回循环异常: %s", e)
                await asyncio.sleep(10)

    def _get_primary_provider(self) -> Optional[str]:
        """获取优先级最高的Provider。"""
        if not self._providers:
            return None
        return min(self._providers.values(), key=lambda p: p.priority).name

    def get_failover_status(self) -> dict[str, Any]:
        """获取当前故障转移状态。

        Returns:
            包含活跃Provider、各Provider健康状态、转移历史等信息的字典。
        """
        health_table = {
            name: health.to_dict()
            for name, health in self._health_checker.get_all_health().items()
        }
        recent_events = [
            event.to_dict() for event in self._failover_history[-10:]
        ]
        return {
            "active_provider": self._active_provider,
            "strategy": self.strategy.value,
            "auto_revert": self.auto_revert,
            "primary_provider": self._get_primary_provider(),
            "health_table": health_table,
            "total_failovers": len(self._failover_history),
            "recent_events": recent_events,
        }

    def get_failover_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取故障转移历史记录。

        Args:
            limit: 最大返回条数。

        Returns:
            转移事件列表。
        """
        events = self._failover_history[-limit:]
        return [event.to_dict() for event in events]

    async def call(self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any) -> Any:
        """通过当前活跃Provider调用函数。

        如果当前Provider不可用，自动尝试故障转移。

        Args:
            func: 要调用的异步函数。
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            函数调用结果。

        Raises:
            RuntimeError: 所有Provider均不可用时抛出。
        """
        if self._active_provider is None:
            raise RuntimeError("无可用Provider")

        # 先检查是否需要故障转移
        await self.check_and_failover()

        if self._active_provider is None:
            raise RuntimeError("故障转移后仍无可用Provider")

        config = self._providers.get(self._active_provider)
        health = self._health_checker.get_health(self._active_provider)

        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=config.timeout if config else 30.0,
            )
            # 调用成功，更新健康状态
            if health:
                health.consecutive_failures = 0
                health.last_success_time = time.monotonic()
                if health.status == ProviderHealthStatus.DEGRADED:
                    health.status = ProviderHealthStatus.HEALTHY
            return result

        except asyncio.TimeoutError:
            if health:
                health.consecutive_failures += 1
                health.total_failures += 1
                health.last_failure_time = time.monotonic()
                if health.consecutive_failures >= self._health_checker.failure_threshold:
                    health.status = ProviderHealthStatus.UNHEALTHY
                else:
                    health.status = ProviderHealthStatus.DEGRADED

            logger.warning(
                "Provider [%s] 调用超时，尝试故障转移",
                self._active_provider,
            )
            # 尝试故障转移
            new_provider = await self.check_and_failover()
            if new_provider:
                # 用新Provider重试
                return await self.call(func, *args, **kwargs)
            raise

        except Exception as e:
            if health:
                health.consecutive_failures += 1
                health.total_failures += 1
                health.last_failure_time = time.monotonic()

            logger.error("Provider [%s] 调用失败: %s", self._active_provider, e)
            raise
