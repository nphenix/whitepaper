"""任务队列集成测试"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.infrastructure.tasks import (
    TaskClient,
    TaskPriority,
    get_monitor,
    get_task_registry,
    task,
)


class TestTaskQueueIntegration:
    """任务队列集成测试"""

    @pytest.fixture
    def mock_settings(self):
        """模拟任务队列设置"""
        from src.infrastructure.tasks.settings import TaskSettings

        return TaskSettings(
            redis_host="localhost",
            redis_port=6379,
            redis_db=1,
            redis_password=None,
            queue_name="test_queue",
            max_jobs=10,
            job_timeout=60,
        )

    @pytest.fixture
    def sample_task(self):
        """示例任务"""

        @task(
            name="sample_task",
            description="Sample integration test task",
            timeout=30,
            max_retries=2,
            priority=TaskPriority.NORMAL,
        )
        async def sample_task(data):
            """处理示例数据"""
            await asyncio.sleep(0.1)  # 模拟处理时间
            return {"processed": data, "timestamp": "2023-01-01T00:00:00"}

        return sample_task

    def test_task_registration(self, sample_task):
        """测试任务注册"""
        registry = get_task_registry()

        # 注册任务
        registry.register_task(sample_task)

        # 验证任务已注册
        assert "sample_task" in registry.list_tasks()
        assert "sample_task" in registry.list_functions()

        # 获取任务
        task_instance = registry.get_task("sample_task")
        task_function = registry.get_function("sample_task")

        assert task_instance is not None
        assert task_function is not None
        assert task_instance.name == "sample_task"
        assert callable(task_function)

    @pytest.mark.asyncio
    async def test_task_execution(self, sample_task):
        """测试任务执行"""
        registry = get_task_registry()
        registry.register_task(sample_task)

        # 获取任务函数
        task_function = registry.get_function("sample_task")

        # 创建模拟上下文
        ctx = {
            "job_id": "test_job_123",
            "job_try": 1,
        }

        # 执行任务
        result = await task_function(ctx, "test_data")

        # 验证结果
        assert result["status"] == "completed"
        assert result["result"]["processed"] == "test_data"
        assert result["result"]["timestamp"] == "2023-01-01T00:00:00"
        assert result["task_id"] == "test_job_123"
        assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_task_failure_and_retry(self):
        """测试任务失败和重试"""

        @task(max_retries=2)
        async def failing_task():
            """总是失败的任务"""
            msg = "Task always fails"
            raise ValueError(msg)

        registry = get_task_registry()
        registry.register_task(failing_task)

        # 获取任务函数
        task_function = registry.get_function("failing_task")

        # 第一次执行(应该失败并设置重试)
        ctx = {
            "job_id": "failing_job_123",
            "job_try": 1,  # 第一次尝试
        }

        with pytest.raises(Exception):  # arq 会抛出 RetryError
            await task_function(ctx)

    @pytest.mark.asyncio
    async def test_monitor_integration(self, sample_task):
        """测试监控集成"""
        monitor = get_monitor()

        # 记录成功指标
        monitor.record_task_success("sample_task", 1.5)

        # 记录失败指标
        monitor.record_task_failure("sample_task")

        # 验证指标
        task_metrics = monitor.get_task_metrics("sample_task")
        assert "sample_task" in task_metrics
        assert task_metrics["sample_task"].total_count == 2
        assert task_metrics["sample_task"].success_count == 1
        assert task_metrics["sample_task"].failed_count == 1
        assert task_metrics["sample_task"].avg_duration == 1.5

    @pytest.mark.asyncio
    async def test_client_simulation(self, mock_settings):
        """测试客户端模拟(不需要真实Redis)"""
        # 这个测试模拟客户端操作,不需要真实的Redis连接
        with patch("src.infrastructure.tasks.client.ArqRedis") as mock_redis_class:
            mock_redis = AsyncMock()
            mock_redis_class.return_value = mock_redis

            # 模拟Redis操作
            mock_redis.enqueue_job.return_value = None
            mock_redis.get.return_value = None
            mock_redis.delete.return_value = 0
            mock_redis.scan_iter.return_value = []
            mock_redis.llen.return_value = 0

            # 创建客户端
            client = TaskClient(mock_settings)

            # 模拟任务提交
            task_id = await client.submit_task("test_task", "test_data")
            assert task_id is not None

            # 模拟任务状态查询
            status = await client.get_task_status(task_id)
            assert status is not None

            # 模拟队列信息获取
            queue_info = await client.get_queue_info()
            assert "queue_name" in queue_info

            # 关闭客户端
            await client.close()

    @pytest.mark.asyncio
    async def test_prometheus_metrics(self, sample_task):
        """测试 Prometheus 指标导出"""
        monitor = get_monitor()

        # 记录一些指标
        monitor.record_task_success("sample_task", 1.0)
        monitor.record_task_success("sample_task", 2.0)
        monitor.record_task_failure("sample_task")

        # 导出 Prometheus 指标
        metrics = await monitor.export_prometheus_metrics()

        # 验证指标内容
        assert "arq_task_total" in metrics
        assert "arq_task_success" in metrics
        assert "arq_task_failed" in metrics
        assert "arq_task_avg_duration" in metrics
        assert "sample_task" in metrics

    def test_health_check_integration(self):
        """测试健康检查集成"""
        monitor = get_monitor()

        # 默认状态应该是健康的
        assert monitor.is_healthy() is True

        # 添加一些失败任务
        monitor.record_task_failure("task1")
        monitor.record_task_failure("task2")
        monitor.record_task_success("task3", 1.0)

        # 总任务数不够,应该还是健康的
        assert monitor.is_healthy() is True

        # 添加大量失败任务
        for _ in range(100):
            monitor.record_task_failure("task4")

        # 现在应该是不健康的(失败率过高)
        assert monitor.is_healthy() is False
