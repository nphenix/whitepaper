"""任务队列客户端

提供任务提交,查询和管理的高级接口,包括:
- 任务提交和调度
- 任务状态查询
- 任务结果获取
- 任务取消和重试
- 批量操作支持
"""

import asyncio
import contextlib
from collections.abc import AsyncGenerator, Awaitable
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import uuid4

from arq.connections import ArqRedis
from arq.constants import job_key_prefix, result_key_prefix

from src.shared.utils.logging import get_logger

from .settings import TaskSettings, get_task_settings
from .tasks import TaskPriority, TaskStatus

logger = get_logger(__name__)


class TaskClient:
    """任务队列客户端

    提供任务提交,查询和管理的高级接口.
    """

    def __init__(self, settings: TaskSettings | None = None):
        """初始化客户端

        Args:
            settings: 任务队列配置,如果为 None 则使用默认配置
        """
        self.settings = settings or get_task_settings()
        self._redis: ArqRedis | None = None

    @property
    def redis(self) -> ArqRedis:
        """获取 Redis 客户端

        Returns:
            Redis 客户端
        """
        if self._redis is None:
            self._redis = ArqRedis(
                host=self.settings.redis_host,
                port=self.settings.redis_port,
                db=self.settings.redis_db,
                password=self.settings.redis_password,
                socket_timeout=self.settings.redis_socket_timeout,
                socket_connect_timeout=self.settings.redis_socket_connect_timeout,
            )
        return self._redis

    async def close(self) -> None:
        """关闭客户端"""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def submit_task(
        self,
        task_name: str,
        *args: Any,
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: int | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        queue: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """提交任务

        Args:
            task_name: 任务名称
            *args: 位置参数
            priority: 任务优先级
            delay: 延迟执行时间(秒)
            timeout: 任务超时时间(秒)
            max_retries: 最大重试次数
            queue: 队列名称
            metadata: 元数据
            **kwargs: 关键字参数

        Returns:
            任务ID
        """
        job_id = str(uuid4())

        # 构建任务选项
        job_kwargs: dict[str, Any] = {}

        # 设置优先级(转换为 arq 的 priority 数值)
        if self.settings.queue.enable_priorities:
            priority_map = {
                TaskPriority.CRITICAL: 0,
                TaskPriority.HIGH: 1,
                TaskPriority.NORMAL: 2,
                TaskPriority.LOW: 3,
                TaskPriority.BULK: 4,
            }
            job_kwargs["_priority"] = priority_map.get(priority, 2)

        # 设置延迟
        if delay:
            job_kwargs["_defer_until"] = datetime.utcnow() + timedelta(seconds=delay)

        # 设置超时
        if timeout:
            job_kwargs["_job_timeout"] = timeout

        # 设置最大重试次数
        if max_retries:
            job_kwargs["_max_retries"] = max_retries

        # 设置队列
        if queue:
            job_kwargs["_queue_name"] = queue
        else:
            job_kwargs["_queue_name"] = self.settings.queue.name

        # 设置元数据
        if metadata:
            job_kwargs["_ctx"] = metadata

        try:
            # 提交任务
            await self.redis.enqueue_job(
                task_name,
                *args,
                **kwargs,
                **job_kwargs,
                job_id=job_id,
            )

            logger.info(
                f"Task submitted: {task_name}",
                extra={
                    "task_id": job_id,
                    "task_name": task_name,
                    "priority": priority.value,
                    "delay": delay,
                },
            )

            return job_id

        except Exception as e:
            logger.error(
                f"Failed to submit task: {task_name}",
                extra={
                    "task_id": job_id,
                    "task_name": task_name,
                    "error": str(e),
                },
            )
            raise

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息或 None
        """
        try:
            # 获取任务结果
            result_key = f"{result_key_prefix}{task_id}"
            result_data = await self.redis.get(result_key)

            if result_data:
                import pickle

                # 数据来自受控Redis键,使用pickle序列化存储
                result = pickle.loads(result_data)  # noqa: S301
                return {
                    "task_id": task_id,
                    "status": result.get("status"),
                    "result": result.get("result"),
                    "error": result.get("error"),
                    "start_time": result.get("start_time"),
                    "end_time": result.get("end_time"),
                    "duration": result.get("duration"),
                    "retry_count": result.get("retry_count"),
                }

            # 检查任务是否在队列中
            job_key = f"{job_key_prefix}{task_id}"
            job_data = await self.redis.get(job_key)

            if job_data:
                return {
                    "task_id": task_id,
                    "status": TaskStatus.PENDING,
                    "message": "Task is pending in queue",
                }

            # 任务不存在
            return {
                "task_id": task_id,
                "status": "unknown",
                "message": "Task not found",
            }

        except Exception as e:
            logger.error(
                f"Failed to get task status: {task_id}",
                extra={
                    "task_id": task_id,
                    "error": str(e),
                },
            )
            return None

    async def get_task_result(
        self, task_id: str, wait: bool = False, timeout: int | None = None
    ) -> Any | None:
        """获取任务结果

        Args:
            task_id: 任务ID
            wait: 是否等待任务完成
            timeout: 等待超时时间(秒)

        Returns:
            任务结果或 None
        """
        try:
            if wait:
                # 等待任务完成
                import pickle

                result_key = f"{result_key_prefix}{task_id}"
                start_time = datetime.now()

                while True:
                    result_data = await self.redis.get(result_key)
                    if result_data:
                        # 结果由内部worker写入,可安全反序列化
                        result = pickle.loads(result_data)  # noqa: S301
                        return result

                    # 检查超时
                    if (
                        timeout
                        and (datetime.now() - start_time).total_seconds() > timeout
                    ):
                        msg = (
                            f"Task {task_id} did not complete within {timeout} seconds"
                        )
                        raise TimeoutError(msg)

                    await asyncio.sleep(0.1)
            else:
                # 直接获取结果
                status = await self.get_task_status(task_id)
                if status and status.get("status") == TaskStatus.COMPLETED:
                    return status.get("result")
                return None

        except Exception as e:
            logger.error(
                f"Failed to get task result: {task_id}",
                extra={
                    "task_id": task_id,
                    "error": str(e),
                },
            )
            raise

    async def cancel_task(self, task_id: str) -> bool:
        """取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        try:
            # 从队列中删除任务
            job_key = f"{job_key_prefix}{task_id}"
            result = await self.redis.delete(job_key)

            if result > 0:
                logger.info(f"Task cancelled: {task_id}")
                return True
            else:
                logger.warning(f"Task not found for cancellation: {task_id}")
                return False

        except Exception as e:
            logger.error(
                f"Failed to cancel task: {task_id}",
                extra={
                    "task_id": task_id,
                    "error": str(e),
                },
            )
            return False

    async def retry_task(
        self, task_id: str, delay: int | None = None, max_retries: int | None = None
    ) -> str | None:
        """重试任务

        Args:
            task_id: 原任务ID
            delay: 延迟重试时间(秒)
            max_retries: 最大重试次数

        Returns:
            新任务ID或 None
        """
        try:
            # 获取原任务信息
            status = await self.get_task_status(task_id)
            if not status:
                return None

            # 这里需要根据实际情况重建任务
            # 由于 arq 不直接支持重试,我们需要重新提交任务
            # 这需要知道原任务的信息,这里只是一个示例
            logger.warning("Task retry is not fully implemented")
            return None

        except Exception as e:
            logger.error(
                f"Failed to retry task: {task_id}",
                extra={
                    "task_id": task_id,
                    "error": str(e),
                },
            )
            return None

    async def list_tasks(
        self,
        status: TaskStatus | list[TaskStatus] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """列出任务

        Args:
            status: 任务状态过滤
            limit: 限制数量
            offset: 偏移量

        Returns:
            任务列表
        """
        try:
            # 这里需要根据实际情况实现
            # 由于 arq 不直接支持列出所有任务,这里只是一个示例
            logger.warning("Task listing is not fully implemented")
            return []

        except Exception as e:
            logger.error(
                "Failed to list tasks",
                extra={
                    "status": status,
                    "error": str(e),
                },
            )
            return []

    async def get_queue_info(self) -> dict[str, Any]:
        """获取队列信息

        Returns:
            队列信息
        """
        try:
            queue_name = self.settings.queue.name

            # 获取队列长度
            queue_length = await cast("Awaitable[int]", self.redis.llen(f"arq:queue:{queue_name}"))

            # 获取活跃任务数
            active_jobs = 0
            async for _key in self.redis.scan_iter(f"{job_key_prefix}*"):
                active_jobs += 1

            # 获取待处理结果数
            pending_results = 0
            async for _key in self.redis.scan_iter(f"{result_key_prefix}*"):
                pending_results += 1

            return {
                "queue_name": queue_name,
                "queue_length": queue_length,
                "active_jobs": active_jobs,
                "pending_results": pending_results,
                "max_jobs": self.settings.queue.max_jobs,
            }

        except Exception as e:
            logger.error(
                "Failed to get queue info",
                extra={
                    "error": str(e),
                },
            )
            return {}

    async def cleanup_expired_results(self, ttl: int = 3600) -> int:
        """清理过期结果

        Args:
            ttl: 结果生存时间(秒)

        Returns:
            清理的结果数量
        """
        try:
            import pickle

            cleaned_count = 0
            current_time = datetime.now()

            # 扫描所有结果键
            async for key in self.redis.scan_iter(f"{result_key_prefix}*"):
                try:
                    # 获取结果数据
                    data = await self.redis.get(key)
                    if data:
                        # 清理任务结果时读取内部写入的数据
                        result = pickle.loads(data)  # noqa: S301
                        end_time_str = result.get("end_time")

                        if end_time_str:
                            # 解析结束时间
                            end_time = datetime.fromisoformat(
                                end_time_str.replace("Z", "+00:00")
                            )

                            # 检查是否过期
                            if (current_time - end_time).total_seconds() > ttl:
                                await self.redis.delete(key)
                                cleaned_count += 1

                except Exception as e:
                    logger.warning(
                        f"Failed to clean result: {key}",
                        extra={
                            "key": key,
                            "error": str(e),
                        },
                    )

            logger.info(f"Cleaned {cleaned_count} expired results")
            return cleaned_count

        except Exception as e:
            logger.error(
                "Failed to cleanup expired results",
                extra={
                    "ttl": ttl,
                    "error": str(e),
                },
            )
            return 0


# 上下文管理器支持
@contextlib.asynccontextmanager
async def task_client(
    settings: TaskSettings | None = None,
) -> AsyncGenerator[TaskClient, None]:
    """任务客户端上下文管理器

    Args:
        settings: 任务队列配置

    Yields:
        TaskClient 实例
    """
    client = TaskClient(settings)
    try:
        yield client
    finally:
        await client.close()
