"""Arq Worker 配置和管理

提供基于 Arq 的异步任务队列 Worker,包括:
- Worker 设置和配置
- 任务注册和发现
- 健康检查和监控
- 优雅启动和关闭
- 分布式 Worker 支持
"""

import asyncio
import logging
import signal
from collections.abc import Callable
from typing import Any

from arq import Retry, Worker as ArqWorker
from arq.connections import ArqRedis, RedisSettings

from src.shared.utils.logging import get_logger

from .settings import TaskSettings, get_task_settings
from .tasks import BaseTask, HealthCheckTask, TaskContext, TaskStatus

logger = get_logger(__name__)


class TaskRegistry:
    """任务注册表

    管理所有可执行的任务,支持动态注册和发现.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, BaseTask] = {}
        self._functions: dict[str, Callable] = {}

    def register_task(
        self,
        task: BaseTask | Callable[..., Any] | type[BaseTask],
        name: str | None = None,
    ) -> None:
        """注册任务

        Args:
            task: 任务实例,函数或任务类
            name: 任务名称,如果为 None 则使用默认名称
        """
        if isinstance(task, BaseTask):
            task_name = name or task.name
            self._tasks[task_name] = task
            self._functions[task_name] = self._wrap_task(task)
            logger.info("Registered task: %s", task_name)

        elif callable(task) and not isinstance(task, type):
            # 函数类型任务
            task_name = name or task.__name__
            self._functions[task_name] = task
            logger.info("Registered function task: %s", task_name)

        elif isinstance(task, type) and issubclass(task, BaseTask):
            # 任务类
            task_instance = task()
            task_name = name or task_instance.name
            self._tasks[task_name] = task_instance
            self._functions[task_name] = self._wrap_task(task_instance)
            logger.info("Registered task class: %s", task_name)
        else:
            msg = f"Invalid task type: {type(task)}"
            raise ValueError(msg)

    def get_task(self, name: str) -> BaseTask | None:
        """获取任务实例

        Args:
            name: 任务名称

        Returns:
            任务实例或 None
        """
        return self._tasks.get(name)

    def get_function(self, name: str) -> Callable | None:
        """获取任务函数

        Args:
            name: 任务名称

        Returns:
            任务函数或 None
        """
        return self._functions.get(name)

    def list_tasks(self) -> list[str]:
        """列出所有任务名称

        Returns:
            任务名称列表
        """
        return list(self._tasks.keys())

    def list_functions(self) -> list[str]:
        """列出所有任务函数名称

        Returns:
            任务函数名称列表
        """
        return list(self._functions.keys())

    def _wrap_task(self, task: BaseTask) -> Callable:
        """包装任务为 Arq 可执行的函数

        Args:
            task: 任务实例

        Returns:
            包装后的函数
        """

        async def wrapped_task(ctx: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
            """包装后的任务函数

            Args:
                ctx: Arq 上下文
                *args: 位置参数
                **kwargs: 关键字参数

            Returns:
                任务执行结果
            """
            # 创建任务上下文
            task_ctx = TaskContext(
                task_id=ctx.get("job_id", "unknown"),
                retry_count=ctx.get("job_try", 0) - 1,
                max_retries=task.max_retries,
                timeout=task.timeout,
                metadata=ctx,
            )

            try:
                # 执行任务
                result = await task(task_ctx, *args, **kwargs)

                # 记录成功日志
                if result.status == TaskStatus.COMPLETED:
                    logger.info(
                        "Task %s completed successfully",
                        task.name,
                        extra={
                            "task_id": result.task_id,
                            "duration": result.duration,
                            "result": result.result,
                        },
                    )
                else:
                    logger.warning(
                        "Task %s completed with status: %s",
                        task.name,
                        result.status,
                        extra={
                            "task_id": result.task_id,
                            "duration": result.duration,
                            "error": result.error,
                        },
                    )

                return result.to_dict()

            except Exception as e:
                logger.exception(
                    "Task %s failed",
                    task.name,
                    extra={
                        "task_id": task_ctx.task_id,
                        "retry_count": task_ctx.retry_count,
                        "error": str(e),
                    },
                )

                # 如果还有重试机会,抛出 Retry
                if task_ctx.retry_count < task.max_retries:
                    retry_delay = task.get_retry_delay(task_ctx.retry_count)
                    logger.info(
                        "Retrying task %s in %s seconds",
                        task.name,
                        retry_delay,
                        extra={
                            "task_id": task_ctx.task_id,
                            "retry_count": task_ctx.retry_count + 1,
                        },
                    )
                    raise Retry(defer=retry_delay)

                # 没有重试机会,重新抛出异常
                raise

        wrapped_task.__name__ = task.name
        wrapped_task.__doc__ = task.description
        return wrapped_task


# 全局任务注册表
_registry = TaskRegistry()


def get_task_registry() -> TaskRegistry:
    """获取全局任务注册表

    Returns:
        任务注册表实例
    """
    return _registry


class WorkerSettings(ArqWorker):
    """自定义 Worker 设置

    继承自 arq.Worker,提供额外的配置和功能.
    """

    def __init__(self, settings: TaskSettings):
        self.settings = settings
        self.redis_client: ArqRedis | None = None
        self._shutdown_event = asyncio.Event()

        # 初始化 Redis 设置
        self.redis_settings = RedisSettings(
            host=settings.redis_host,
            port=settings.redis_port,
            database=settings.redis_db,
            password=settings.redis_password,
            ssl=(
                settings.redis_url.startswith("rediss://")
                if settings.redis_url
                else False
            ),
        )

        # 初始化 Worker 基类
        super().__init__(
            functions=list(self._get_registered_functions().values()),
            redis_settings=self.redis_settings,
            queue_name=settings.queue.name,
            max_jobs=settings.queue.max_jobs,
            job_timeout=settings.queue.job_timeout,
            keep_result=settings.queue.keep_result,
            ctx={
                "worker_name": settings.worker_name,
                "settings": settings,
            },
            health_check_interval=settings.health_check.interval,
            health_check_key=f"arq:health:{settings.worker_name}",
        )

        # 设置信号处理
        self._setup_signal_handlers()

    def _get_registered_functions(self) -> dict[str, Callable]:
        """获取已注册的任务函数

        Returns:
            任务函数字典
        """
        return get_task_registry()._functions

    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """信号处理器

        Args:
            signum: 信号编号
            frame: 栈帧
        """
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self._shutdown_event.set()

    async def on_startup(self, ctx: dict[str, Any]) -> None:
        """Worker 启动时的回调

        Args:
            ctx: 上下文
        """
        logger.info("Worker starting up...")

        # 创建 Redis 客户端
        self.redis_client = ArqRedis(
            host=self.settings.redis_host,
            port=self.settings.redis_port,
            db=self.settings.redis_db,
            password=self.settings.redis_password,
            socket_timeout=self.settings.redis_socket_timeout,
            socket_connect_timeout=self.settings.redis_socket_connect_timeout,
        )

        # 测试 Redis 连接
        try:
            await self.redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            raise e from e

        # 注册健康检查任务
        get_task_registry().register_task(HealthCheckTask(), name="health_check")

        logger.info(
            "Worker started with %s tasks registered",
            len(get_task_registry().list_tasks()),
        )

    async def on_shutdown(self, ctx: dict[str, Any]) -> None:
        """Worker 关闭时的回调

        Args:
            ctx: 上下文
        """
        logger.info("Worker shutting down...")

        # 关闭 Redis 连接
        if self.redis_client:
            await self.redis_client.close()

        logger.info("Worker shutdown complete")

    async def health_check(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """健康检查

        Args:
            ctx: 上下文

        Returns:
            健康状态信息
        """
        try:
            # 检查 Redis 连接
            if self.redis_client:
                await self.redis_client.ping()

            return {
                "status": "healthy",
                "worker": self.settings.worker_name,
                "queue": self.settings.queue.name,
                "tasks": len(get_task_registry().list_tasks()),
                "timestamp": asyncio.get_event_loop().time(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "worker": self.settings.worker_name,
                "queue": self.settings.queue.name,
                "timestamp": asyncio.get_event_loop().time(),
            }


def create_worker(settings: TaskSettings | None = None) -> ArqWorker:
    """创建 Arq Worker 实例

    Args:
        settings: 任务队列配置,如果为 None 则使用默认配置

    Returns:
        Worker 实例
    """
    if settings is None:
        settings = get_task_settings()

    return WorkerSettings(settings)


def get_worker_settings(settings: TaskSettings | None = None) -> WorkerSettings:
    """获取 Worker 设置实例

    Args:
        settings: 任务队列配置,如果为 None 则使用默认配置

    Returns:
        WorkerSettings 实例
    """
    if settings is None:
        settings = get_task_settings()

    return WorkerSettings(settings)


async def run_worker(settings: TaskSettings | None = None) -> None:
    """运行 Worker

    Args:
        settings: 任务队列配置,如果为 None 则使用默认配置
    """
    if settings is None:
        settings = get_task_settings()

    worker = create_worker(settings)

    try:
        logger.info("Starting worker: %s", settings.worker_name)
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.exception("Worker failed: %s", e)
        raise e from e
    finally:
        logger.info("Worker stopped")


# CLI 命令支持
def main() -> None:
    """Worker 主入口函数"""
    import argparse

    parser = argparse.ArgumentParser(description="Arq Worker for WhitePaper")
    parser.add_argument(
        "--config",
        type=str,
        help="Configuration file path",
    )
    parser.add_argument(
        "--worker-name",
        type=str,
        help="Worker name",
    )
    parser.add_argument(
        "--queue",
        type=str,
        help="Queue name",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )

    args = parser.parse_args()

    # 设置日志级别
    logging.basicConfig(level=getattr(logging, args.log_level))

    # 加载配置
    settings = get_task_settings()

    # 应用命令行参数
    if args.worker_name:
        settings.worker_name = args.worker_name
    if args.queue:
        settings.queue.name = args.queue

    # 运行 Worker
    asyncio.run(run_worker(settings))


if __name__ == "__main__":
    main()
