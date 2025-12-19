"""任务定义和基类

提供任务的基础类和相关类型定义,包括:
- 基础任务类
- 任务结果类型
- 任务状态枚举
- 任务优先级枚举
- 任务装饰器
"""

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 等待执行
    RUNNING = "running"  # 正在执行
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"  # 执行失败
    CANCELLED = "cancelled"  # 已取消
    RETRYING = "retrying"  # 重试中
    TIMEOUT = "timeout"  # 超时


class TaskPriority(str, Enum):
    """任务优先级枚举"""

    CRITICAL = "critical"  # 紧急
    HIGH = "high"  # 高
    NORMAL = "normal"  # 正常
    LOW = "low"  # 低
    BULK = "bulk"  # 批量


T = TypeVar("T")


@dataclass
class TaskResult[T]:
    """任务结果

    Args:
        task_id: 任务ID
        status: 任务状态
        result: 执行结果
        error: 错误信息
        start_time: 开始时间
        end_time: 结束时间
        duration: 执行时长(秒)
        retry_count: 重试次数
        metadata: 元数据
    """

    task_id: str
    status: TaskStatus
    result: Any | None = None
    error: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration: float | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration": self.duration,
            "retry_count": self.retry_count,
            "metadata": self.metadata,
        }


class TaskContext(BaseModel):
    """任务上下文

    Args:
        task_id: 任务ID
        retry_count: 重试次数
        max_retries: 最大重试次数
        priority: 优先级
        timeout: 超时时间
        metadata: 元数据
    """

    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    priority: TaskPriority = Field(default=TaskPriority.NORMAL)
    timeout: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseTask(ABC):
    """基础任务类

    所有任务都应该继承此类,实现 execute 方法。

    Attributes:
        name: 任务名称
        description: 任务描述
        version: 任务版本
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        priority: 默认优先级
    """

    def __init__(
        self,
        name: str | None = None,
        description: str | None = None,
        version: str = "1.0.0",
        timeout: int | None = None,
        max_retries: int = 3,
        priority: TaskPriority = TaskPriority.NORMAL,
    ):
        self.name = name or self.__class__.__name__
        self.description = description or f"{self.name} task"
        self.version = version
        self.timeout = timeout
        self.max_retries = max_retries
        self.priority = priority

    @abstractmethod
    async def execute(self, context: TaskContext, *args: Any, **kwargs: Any) -> Any:
        """执行任务

        Args:
            context: 任务上下文
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            任务执行结果

        Raises:
            Exception: 任务执行异常
        """

    async def __call__(
        self, context: TaskContext, *args: Any, **kwargs: Any
    ) -> TaskResult:
        """调用任务

        Args:
            context: 任务上下文
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            任务结果
        """
        start_time = datetime.now()

        try:
            # 设置超时
            if self.timeout:
                result = await asyncio.wait_for(
                    self.execute(context, *args, **kwargs), timeout=self.timeout
                )
            else:
                result = await self.execute(context, *args, **kwargs)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return TaskResult(
                task_id=context.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                retry_count=context.retry_count,
                metadata={
                    "task_name": self.name,
                    "task_version": self.version,
                    "priority": context.priority.value,
                },
            )

        except TimeoutError:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return TaskResult(
                task_id=context.task_id,
                status=TaskStatus.TIMEOUT,
                error=f"Task timed out after {self.timeout} seconds",
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                retry_count=context.retry_count,
                metadata={
                    "task_name": self.name,
                    "task_version": self.version,
                    "priority": context.priority.value,
                },
            )

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            return TaskResult(
                task_id=context.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                retry_count=context.retry_count,
                metadata={
                    "task_name": self.name,
                    "task_version": self.version,
                    "priority": context.priority.value,
                },
            )

    def validate_args(self, *args: Any, **kwargs: Any) -> bool:
        """验证参数

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            是否验证通过
        """
        return True

    def get_retry_delay(self, retry_count: int) -> int:
        """获取重试延迟时间

        Args:
            retry_count: 重试次数

        Returns:
            延迟时间(秒)
        """
        # 指数退避策略
        base_delay = 60
        return min(base_delay * (2**retry_count), 3600)


def task(
    name: str | None = None,
    description: str | None = None,
    timeout: int | None = None,
    max_retries: int = 3,
    priority: TaskPriority = TaskPriority.NORMAL,
    queue: str = "default",
) -> Callable[[Callable[..., Any]], BaseTask]:
    """任务装饰器

    Args:
        name: 任务名称
        description: 任务描述
        timeout: 超时时间(秒)
        max_retries: 最大重试次数
        priority: 优先级
        queue: 队列名称

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[..., Any]) -> BaseTask:
        class DecoratedTask(BaseTask):
            def __init__(self, original_func: Callable[..., Any]) -> None:
                super().__init__(
                    name=name or original_func.__name__,
                    description=description
                    or original_func.__doc__
                    or f"{original_func.__name__} task",
                    timeout=timeout,
                    max_retries=max_retries,
                    priority=priority,
                )
                self.func = original_func
                self.queue = queue

            async def execute(
                self, context: TaskContext, *args: Any, **kwargs: Any
            ) -> Any:
                return await self.func(context, *args, **kwargs)

        # 创建并返回任务实例
        return DecoratedTask(func)

    return decorator


# 常用任务类型定义
DocumentProcessingTask = BaseTask
IndexingTask = BaseTask
AgentTask = BaseTask
CrawlingTask = BaseTask


# 预定义的任务
class HealthCheckTask(BaseTask):
    """健康检查任务"""

    def __init__(self) -> None:
        super().__init__(
            name="health_check",
            description="System health check task",
            timeout=30,
            max_retries=1,
            priority=TaskPriority.HIGH,
        )

    async def execute(
        self, context: TaskContext, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """执行健康检查"""
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "task_id": context.task_id,
        }


class CleanupTask(BaseTask):
    """清理任务"""

    def __init__(self) -> None:
        super().__init__(
            name="cleanup",
            description="Clean up temporary files and expired data",
            timeout=300,
            max_retries=2,
            priority=TaskPriority.LOW,
        )

    async def execute(
        self, context: TaskContext, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        """执行清理操作"""
        # 这里可以实现具体的清理逻辑
        return {
            "cleaned_files": 0,
            "cleaned_records": 0,
            "timestamp": datetime.now().isoformat(),
        }
