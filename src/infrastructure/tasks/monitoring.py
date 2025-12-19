"""任务队列监控

提供任务队列的监控和统计功能,包括:
- 任务执行统计
- 性能指标收集
- 健康状态监控
- Prometheus 指标导出
- 实时状态跟踪
"""

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.shared.utils.logging import get_logger

from .client import TaskClient
from .settings import TaskSettings, get_task_settings

logger = get_logger(__name__)


@dataclass
class TaskMetrics:
    """任务指标

    Args:
        task_name: 任务名称
        total_count: 总执行次数
        success_count: 成功次数
        failed_count: 失败次数
        avg_duration: 平均执行时间
        min_duration: 最小执行时间
        max_duration: 最大执行时间
        last_success_time: 最后成功时间
        last_failure_time: 最后失败时间
    """

    task_name: str
    total_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    avg_duration: float = 0.0
    min_duration: float = float("inf")
    max_duration: float = 0.0
    last_success_time: datetime | None = None
    last_failure_time: datetime | None = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count

    @property
    def failure_rate(self) -> float:
        """失败率"""
        if self.total_count == 0:
            return 0.0
        return self.failed_count / self.total_count

    def update_success(self, duration: float) -> None:
        """更新成功指标

        Args:
            duration: 执行时长
        """
        self.total_count += 1
        self.success_count += 1
        self.last_success_time = datetime.now()

        # 更新执行时间统计
        if self.total_count == 1:
            self.avg_duration = duration
        else:
            self.avg_duration = (
                (self.avg_duration * (self.total_count - 1)) + duration
            ) / self.total_count

        self.min_duration = min(self.min_duration, duration)
        self.max_duration = max(self.max_duration, duration)

    def update_failure(self) -> None:
        """更新失败指标"""
        self.total_count += 1
        self.failed_count += 1
        self.last_failure_time = datetime.now()

        # 更新执行时间统计(失败任务没有执行时间)
        if self.total_count == 1:
            self.avg_duration = 0.0
        else:
            self.avg_duration = (
                self.avg_duration * (self.total_count - 1)
            ) / self.total_count

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_name": self.task_name,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "avg_duration": self.avg_duration,
            "min_duration": (
                self.min_duration if self.min_duration != float("inf") else 0.0
            ),
            "max_duration": self.max_duration,
            "last_success_time": (
                self.last_success_time.isoformat() if self.last_success_time else None
            ),
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
        }


@dataclass
class QueueMetrics:
    """队列指标

    Args:
        queue_name: 队列名称
        queue_length: 队列长度
        active_jobs: 活跃任务数
        pending_results: 待处理结果数
        worker_count: Worker 数量
        max_jobs: 最大任务数
        throughput: 吞吐量(每秒处理任务数)
        avg_wait_time: 平均等待时间
    """

    queue_name: str
    queue_length: int = 0
    active_jobs: int = 0
    pending_results: int = 0
    worker_count: int = 0
    max_jobs: int = 0
    throughput: float = 0.0
    avg_wait_time: float = 0.0
    last_update: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "queue_name": self.queue_name,
            "queue_length": self.queue_length,
            "active_jobs": self.active_jobs,
            "pending_results": self.pending_results,
            "worker_count": self.worker_count,
            "max_jobs": self.max_jobs,
            "throughput": self.throughput,
            "avg_wait_time": self.avg_wait_time,
            "last_update": self.last_update.isoformat() if self.last_update else None,
        }


class TaskMonitor:
    """任务监控器

    提供任务队列的监控和统计功能。
    """

    def __init__(self, settings: TaskSettings | None = None):
        """初始化监控器

        Args:
            settings: 任务队列配置
        """
        self.settings = settings or get_task_settings()
        self._task_metrics: dict[str, TaskMetrics] = {}
        self._queue_metrics: QueueMetrics = QueueMetrics(
            queue_name=self.settings.queue.name,
            max_jobs=self.settings.queue.max_jobs,
        )
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._client: TaskClient | None = None

    async def start(self) -> None:
        """启动监控器"""
        if self._running:
            return

        self._running = True
        self._client = TaskClient(self.settings)
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        logger.info("Task monitor started")

    async def stop(self) -> None:
        """停止监控器"""
        if not self._running:
            return

        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitor_task

        if self._client:
            await self._client.close()
            self._client = None

        logger.info("Task monitor stopped")

    async def _monitor_loop(self) -> None:
        """监控循环"""
        while self._running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.settings.monitoring.metrics_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Error in monitor loop", extra={"error": str(e)}, exc_info=True
                )
                await asyncio.sleep(5)

    async def _collect_metrics(self) -> None:
        """收集指标"""
        if not self._client:
            return

        try:
            # 收集队列指标
            queue_info = await self._client.get_queue_info()
            self._queue_metrics.queue_length = queue_info.get("queue_length", 0)
            self._queue_metrics.active_jobs = queue_info.get("active_jobs", 0)
            self._queue_metrics.pending_results = queue_info.get("pending_results", 0)
            self._queue_metrics.last_update = datetime.now()

            # 这里可以添加更多指标收集逻辑
            # 例如:从 Redis 或其他存储中收集任务执行历史

        except Exception as e:
            logger.error("Failed to collect metrics", extra={"error": str(e)})

    def record_task_success(self, task_name: str, duration: float) -> None:
        """记录任务成功

        Args:
            task_name: 任务名称
            duration: 执行时长
        """
        if task_name not in self._task_metrics:
            self._task_metrics[task_name] = TaskMetrics(task_name=task_name)

        self._task_metrics[task_name].update_success(duration)

        logger.debug(
            f"Recorded task success: {task_name}",
            extra={
                "task_name": task_name,
                "duration": duration,
            },
        )

    def record_task_failure(self, task_name: str) -> None:
        """记录任务失败

        Args:
            task_name: 任务名称
        """
        if task_name not in self._task_metrics:
            self._task_metrics[task_name] = TaskMetrics(task_name=task_name)

        self._task_metrics[task_name].update_failure()

        logger.debug(
            f"Recorded task failure: {task_name}", extra={"task_name": task_name}
        )

    def get_task_metrics(self, task_name: str | None = None) -> dict[str, TaskMetrics]:
        """获取任务指标

        Args:
            task_name: 任务名称,如果为 None 则返回所有任务指标

        Returns:
            任务指标字典
        """
        if task_name:
            return {
                task_name: self._task_metrics.get(
                    task_name, TaskMetrics(task_name=task_name)
                )
            }
        return self._task_metrics.copy()

    def get_queue_metrics(self) -> QueueMetrics:
        """获取队列指标

        Returns:
            队列指标
        """
        return self._queue_metrics

    def get_summary(self) -> dict[str, Any]:
        """获取监控摘要

        Returns:
            监控摘要
        """
        total_tasks = sum(m.total_count for m in self._task_metrics.values())
        total_success = sum(m.success_count for m in self._task_metrics.values())
        total_failed = sum(m.failed_count for m in self._task_metrics.values())

        return {
            "tasks": {
                "total": total_tasks,
                "success": total_success,
                "failed": total_failed,
                "success_rate": total_success / total_tasks if total_tasks > 0 else 0.0,
                "failure_rate": total_failed / total_tasks if total_tasks > 0 else 0.0,
            },
            "queue": self._queue_metrics.to_dict(),
            "task_details": {
                name: metrics.to_dict() for name, metrics in self._task_metrics.items()
            },
        }

    async def export_prometheus_metrics(self) -> str:
        """导出 Prometheus 格式的指标

        Returns:
            Prometheus 指标字符串
        """
        metrics = []

        # 队列指标
        queue_metrics = self._queue_metrics
        metrics.append(
            f'arq_queue_length{{queue_name="{queue_metrics.queue_name}"}} {queue_metrics.queue_length}'
        )
        metrics.append(
            f'arq_active_jobs{{queue_name="{queue_metrics.queue_name}"}} {queue_metrics.active_jobs}'
        )
        metrics.append(
            f'arq_pending_results{{queue_name="{queue_metrics.queue_name}"}} {queue_metrics.pending_results}'
        )

        # 任务指标
        for task_name, task_metrics in self._task_metrics.items():
            # 清理任务名称,使其符合 Prometheus 标签规范
            safe_task_name = task_name.replace(" ", "_").replace("/", "_")

            metrics.append(
                f'arq_task_total{{task_name="{safe_task_name}"}} {task_metrics.total_count}'
            )
            metrics.append(
                f'arq_task_success{{task_name="{safe_task_name}"}} {task_metrics.success_count}'
            )
            metrics.append(
                f'arq_task_failed{{task_name="{safe_task_name}"}} {task_metrics.failed_count}'
            )
            metrics.append(
                f'arq_task_success_rate{{task_name="{safe_task_name}"}} {task_metrics.success_rate:.4f}'
            )
            metrics.append(
                f'arq_task_avg_duration{{task_name="{safe_task_name}"}} {task_metrics.avg_duration:.4f}'
            )
            metrics.append(
                f'arq_task_max_duration{{task_name="{safe_task_name}"}} {task_metrics.max_duration:.4f}'
            )
            metrics.append(
                f'arq_task_min_duration{{task_name="{safe_task_name}"}} {task_metrics.min_duration:.4f}'
            )

        return "\n".join(metrics)

    def is_healthy(self) -> bool:
        """检查健康状态

        Returns:
            是否健康
        """
        # 检查队列长度是否超过阈值
        if self._queue_metrics.queue_length > self._queue_metrics.max_jobs * 0.8:
            return False

        # 检查失败率是否过高
        total_tasks = sum(m.total_count for m in self._task_metrics.values())
        if total_tasks > 100:  # 至少有100个任务样本
            total_failed = sum(m.failed_count for m in self._task_metrics.values())
            failure_rate = total_failed / total_tasks
            if failure_rate > 0.1:  # 失败率超过10%
                return False

        return True


# 全局监控器实例
_monitor: TaskMonitor | None = None


def get_monitor(settings: TaskSettings | None = None) -> TaskMonitor:
    """获取全局监控器实例

    Args:
        settings: 任务队列配置

    Returns:
        监控器实例
    """
    global _monitor
    if _monitor is None:
        _monitor = TaskMonitor(settings)
    return _monitor
