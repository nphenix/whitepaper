"""
T020任务基本功能测试

测试Arq异步任务队列的基本功能。

生成命令: /speckit.implement T020
生成时间: 2025-12-09
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.infrastructure.tasks import (
    TaskClient,
    TaskContext,
    TaskPriority,
    TaskStatus,
    get_task_registry,
    get_task_settings,
    task,
    task_client,
)


# 测试任务定义
@task(name="test_task", max_retries=2, priority=TaskPriority.NORMAL)
async def test_task(ctx: TaskContext, message: str) -> str:
    """测试任务"""
    # 模拟一些工作
    await asyncio.sleep(0.1)
    return f"Processed: {message}"


@task(name="failing_task", max_retries=1)
async def failing_task(ctx: TaskContext) -> None:
    """总是失败的任务"""
    msg = "This task always fails"
    raise ValueError(msg)


class TestTaskQueueBasicFunctionality:
    """任务队列基本功能测试"""

    @pytest.mark.asyncio
    async def test_task_settings_creation(self):
        """测试任务设置创建"""
        settings = get_task_settings()

        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.queue.name == "whitepaper_tasks"
        assert settings.queue.max_jobs == 100
        assert settings.worker_name == "whitepaper_worker"

    @pytest.mark.asyncio
    async def test_task_client_creation(self):
        """测试任务客户端创建"""
        settings = get_task_settings()

        async with task_client(settings) as client:
            assert isinstance(client, TaskClient)
            assert client.settings == settings

    @pytest.mark.asyncio
    async def test_task_registration(self):
        """测试任务注册"""
        registry = get_task_registry()

        # 注册任务
        registry.register_task(test_task)
        registry.register_task(failing_task)

        # 验证任务已注册
        assert "test_task" in registry.list_tasks()
        assert "failing_task" in registry.list_tasks()

        # 获取任务
        test_task_instance = registry.get_task("test_task")
        failing_task_instance = registry.get_task("failing_task")

        assert test_task_instance is not None
        assert failing_task_instance is not None
        assert test_task_instance.name == "test_task"
        assert failing_task_instance.name == "failing_task"

    @pytest.mark.asyncio
    async def test_task_execution_direct(self):
        """测试任务直接执行"""
        # 创建任务上下文
        context = TaskContext(
            task_id="test_123",
            retry_count=0,
            max_retries=3,
            priority=TaskPriority.NORMAL,
        )

        # 直接执行任务
        result = await test_task(context, "Hello, World!")

        # 验证结果
        assert result.status == TaskStatus.COMPLETED
        assert result.result == "Processed: Hello, World!"
        assert result.task_id == "test_123"
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_task_failure_direct(self):
        """测试任务直接执行失败"""
        # 创建任务上下文
        context = TaskContext(
            task_id="test_456",
            retry_count=0,
            max_retries=1,
            priority=TaskPriority.NORMAL,
        )

        # 直接执行任务
        result = await failing_task(context)

        # 验证结果
        assert result.status == TaskStatus.FAILED
        assert "This task always fails" in result.error
        assert result.task_id == "test_456"
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_task_client_submission(self):
        """测试任务客户端提交"""
        settings = get_task_settings()

        # 使用模拟的Redis连接
        with patch("src.infrastructure.tasks.client.ArqRedis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            # 模拟Redis操作
            mock_redis.enqueue_job.return_value = None
            mock_redis.get.return_value = None
            mock_redis.delete.return_value = 0
            mock_redis.scan_iter.return_value = []
            mock_redis.llen.return_value = 0

            async with task_client(settings) as client:
                # 提交任务
                job_id = await client.submit_task(
                    "test_task", "Hello, World!", priority=TaskPriority.NORMAL
                )

                assert job_id is not None
                assert isinstance(job_id, str)

                # 验证Redis调用
                mock_redis.enqueue_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_client_status_query(self):
        """测试任务客户端状态查询"""
        settings = get_task_settings()

        # 使用模拟的Redis连接
        with patch("src.infrastructure.tasks.client.ArqRedis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            # 模拟Redis操作
            mock_redis.enqueue_job.return_value = None
            mock_redis.get.return_value = None
            mock_redis.delete.return_value = 0
            mock_redis.scan_iter.return_value = []
            mock_redis.llen.return_value = 0

            async with task_client(settings) as client:
                # 提交任务
                job_id = await client.submit_task(
                    "test_task", "Status test", priority=TaskPriority.HIGH
                )

                # 模拟任务在队列中
                mock_redis.get.return_value = None

                # 检查任务状态
                status = await client.get_task_status(job_id)
                assert status is not None
                # 任务可能还在队列中,状态可能是unknown
                assert status.get("status") in [TaskStatus.PENDING, "unknown"]
                assert status.get("task_id") == job_id

    @pytest.mark.asyncio
    async def test_task_client_result_retrieval(self):
        """测试任务客户端结果获取"""
        settings = get_task_settings()

        # 使用模拟的Redis连接
        with patch("src.infrastructure.tasks.client.ArqRedis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            # 模拟Redis操作
            mock_redis.enqueue_job.return_value = None
            mock_redis.get.return_value = None
            mock_redis.delete.return_value = 0
            mock_redis.scan_iter.return_value = []
            mock_redis.llen.return_value = 0

            async with task_client(settings) as client:
                # 提交任务
                job_id = await client.submit_task(
                    "test_task", "Result test", priority=TaskPriority.NORMAL
                )

                # 直接模拟 get_task_status 方法返回完成状态
                with patch.object(client, "get_task_status") as mock_get_status:
                    mock_get_status.return_value = {
                        "task_id": job_id,
                        "status": TaskStatus.COMPLETED,
                        "result": "Processed: Result test",
                    }

                    # 获取任务结果
                    result = await client.get_task_result(job_id)

                    assert result is not None
                    # get_task_result 在 wait=False 时只返回 result 字段
                    assert result == "Processed: Result test"

    @pytest.mark.asyncio
    async def test_task_priority_handling(self):
        """测试任务优先级处理"""
        settings = get_task_settings()

        # 使用模拟的Redis连接
        with patch("src.infrastructure.tasks.client.ArqRedis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            # 模拟Redis操作
            mock_redis.enqueue_job.return_value = None
            mock_redis.get.return_value = None
            mock_redis.delete.return_value = 0
            mock_redis.scan_iter.return_value = []
            mock_redis.llen.return_value = 0

            async with task_client(settings) as client:
                # 提交不同优先级的任务
                high_priority_job = await client.submit_task(
                    "test_task", "High priority", priority=TaskPriority.HIGH
                )

                low_priority_job = await client.submit_task(
                    "test_task", "Low priority", priority=TaskPriority.LOW
                )

                assert high_priority_job is not None
                assert low_priority_job is not None
                assert high_priority_job != low_priority_job

                # 验证Redis调用
                assert mock_redis.enqueue_job.call_count == 2

    @pytest.mark.asyncio
    async def test_task_queue_info(self):
        """测试任务队列信息"""
        settings = get_task_settings()

        # 使用模拟的Redis连接
        with patch("src.infrastructure.tasks.client.ArqRedis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            # 模拟Redis操作
            mock_redis.get.return_value = None
            mock_redis.delete.return_value = 0
            mock_redis.scan_iter.return_value = []
            mock_redis.llen.return_value = 5  # 模拟5个任务在队列中

            async with task_client(settings) as client:
                # 获取队列信息
                queue_info = await client.get_queue_info()

                assert queue_info is not None
                assert queue_info.get("queue_name") == settings.queue.name
                assert queue_info.get("queue_length") == 5
                assert queue_info.get("max_jobs") == settings.queue.max_jobs


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
