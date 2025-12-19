"""测试任务定义和基类"""

import asyncio
from datetime import datetime

import pytest

from src.infrastructure.tasks.tasks import (
    BaseTask,
    CleanupTask,
    HealthCheckTask,
    TaskContext,
    TaskPriority,
    TaskResult,
    TaskStatus,
    task,
)


class TestTaskContext:
    """测试任务上下文"""

    def test_task_context_creation(self):
        """测试任务上下文创建"""
        context = TaskContext(
            task_id="test_task_123",
            retry_count=2,
            max_retries=3,
            priority=TaskPriority.HIGH,
            timeout=300,
            metadata={"key": "value"},
        )

        assert context.task_id == "test_task_123"
        assert context.retry_count == 2
        assert context.max_retries == 3
        assert context.priority == TaskPriority.HIGH
        assert context.timeout == 300
        assert context.metadata["key"] == "value"

    def test_task_context_defaults(self):
        """测试任务上下文默认值"""
        context = TaskContext()

        assert context.task_id is not None
        assert len(context.task_id) > 0
        assert context.retry_count == 0
        assert context.max_retries == 3
        assert context.priority == TaskPriority.NORMAL
        assert context.timeout is None
        assert context.metadata == {}


class TestBaseTask:
    """测试基础任务类"""

    def test_base_task_creation(self):
        """测试基础任务创建"""

        class TestTask(BaseTask):
            async def execute(self, context, *args, **kwargs):
                return "test"

        task = TestTask(
            name="test_task",
            description="Test task for testing",
            version="2.0.0",
            timeout=120,
            max_retries=5,
            priority=TaskPriority.HIGH,
        )

        assert task.name == "test_task"
        assert task.description == "Test task for testing"
        assert task.version == "2.0.0"
        assert task.timeout == 120
        assert task.max_retries == 5
        assert task.priority == TaskPriority.HIGH

    def test_base_task_defaults(self):
        """测试基础任务默认值"""

        class TestTask(BaseTask):
            async def execute(self, context, *args, **kwargs):
                return "test_result"

        task = TestTask()

        assert task.name == "TestTask"
        assert task.description == "TestTask task"
        assert task.version == "1.0.0"
        assert task.timeout is None
        assert task.max_retries == 3
        assert task.priority == TaskPriority.NORMAL

    @pytest.mark.asyncio
    async def test_successful_task_execution(self):
        """测试成功任务执行"""

        class SuccessTask(BaseTask):
            async def execute(self, context, *args, **kwargs):
                return {"status": "success", "data": args[0]}

        task = SuccessTask()
        context = TaskContext(task_id="test_123")

        result = await task(context, "test_data")

        assert isinstance(result, TaskResult)
        assert result.task_id == "test_123"
        assert result.status == TaskStatus.COMPLETED
        assert result.result["status"] == "success"
        assert result.result["data"] == "test_data"
        assert result.error is None
        assert result.duration is not None
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_failed_task_execution(self):
        """测试失败任务执行"""

        class FailTask(BaseTask):
            async def execute(self, context, *args, **kwargs):
                msg = "Task failed intentionally"
                raise ValueError(msg)

        task = FailTask()
        context = TaskContext(task_id="test_456")

        result = await task(context)

        assert isinstance(result, TaskResult)
        assert result.task_id == "test_456"
        assert result.status == TaskStatus.FAILED
        assert result.error == "Task failed intentionally"
        assert result.result is None
        assert result.duration is not None
        assert result.retry_count == 0

    @pytest.mark.asyncio
    async def test_timeout_task_execution(self):
        """测试任务执行超时"""

        class SlowTask(BaseTask):
            def __init__(self):
                super().__init__(timeout=1)  # 1秒超时

            async def execute(self, context, *args, **kwargs):
                await asyncio.sleep(2)  # 睡眠2秒
                return "should_not_reach_here"

        task = SlowTask()
        context = TaskContext(task_id="test_timeout")

        result = await task(context)

        assert isinstance(result, TaskResult)
        assert result.task_id == "test_timeout"
        assert result.status == TaskStatus.TIMEOUT
        assert "timed out" in result.error.lower()
        assert result.result is None

    def test_validate_args(self):
        """测试参数验证"""

        class TestTask(BaseTask):
            async def execute(self, context, *args, **kwargs):
                return "test"

        task = TestTask()

        # 默认实现总是返回 True
        assert task.validate_args() is True
        assert task.validate_args("arg1", key="value") is True

    def test_get_retry_delay(self):
        """测试重试延迟计算"""

        class TestTask(BaseTask):
            async def execute(self, context, *args, **kwargs):
                return "test"

        task = TestTask()

        delay_0 = task.get_retry_delay(0)
        delay_1 = task.get_retry_delay(1)
        delay_2 = task.get_retry_delay(2)

        assert delay_0 == 60  # 基础延迟
        assert delay_1 == 120  # 2倍
        assert delay_2 == 240  # 4倍

        # 测试最大延迟限制
        delay_10 = task.get_retry_delay(10)
        assert delay_10 == 3600  # 最大延迟


class TestTaskDecorator:
    """测试任务装饰器"""

    def test_task_decorator_basic(self):
        """测试基础任务装饰器"""

        @task
        async def simple_task(data):
            return {"processed": data}

        # 装饰器应该返回BaseTask实例
        assert isinstance(simple_task, BaseTask)
        assert simple_task.name == "simple_task"
        assert simple_task.description == "simple_task task"
        assert simple_task.timeout is None
        assert simple_task.max_retries == 3
        assert simple_task.priority == TaskPriority.NORMAL
        assert simple_task.queue == "default"

    def test_task_decorator_with_options(self):
        """测试带选项的任务装饰器"""

        @task(
            name="custom_task",
            description="Custom task description",
            timeout=300,
            max_retries=5,
            priority=TaskPriority.HIGH,
            queue="high_priority",
        )
        async def custom_task(data):
            return {"processed": data}

        # 装饰器应该返回BaseTask实例
        assert isinstance(custom_task, BaseTask)
        assert custom_task.name == "custom_task"
        assert custom_task.description == "Custom task description"
        assert custom_task.timeout == 300
        assert custom_task.max_retries == 5
        assert custom_task.priority == TaskPriority.HIGH
        assert custom_task.queue == "high_priority"

    @pytest.mark.asyncio
    async def test_decorated_task_execution(self):
        """测试装饰器任务执行"""

        @task
        async def decorated_task(value):
            return value * 2

        context = TaskContext(task_id="decorated_test")
        result = await decorated_task(context, 5)

        assert result.status == TaskStatus.COMPLETED
        assert result.result == 10


class TestPredefinedTasks:
    """测试预定义任务"""

    def test_health_check_task_creation(self):
        """测试健康检查任务创建"""
        task = HealthCheckTask()

        assert task.name == "health_check"
        assert "health check" in task.description.lower()
        assert task.timeout == 30
        assert task.max_retries == 1
        assert task.priority == TaskPriority.HIGH

    @pytest.mark.asyncio
    async def test_health_check_task_execution(self):
        """测试健康检查任务执行"""
        task = HealthCheckTask()
        context = TaskContext(task_id="health_check_123")

        result = await task(context)

        assert result.status == TaskStatus.COMPLETED
        assert result.result["status"] == "healthy"
        assert "timestamp" in result.result
        assert result.result["task_id"] == "health_check_123"

    def test_cleanup_task_creation(self):
        """测试清理任务创建"""
        task = CleanupTask()

        assert task.name == "cleanup"
        assert "clean up" in task.description.lower()
        assert task.timeout == 300
        assert task.max_retries == 2
        assert task.priority == TaskPriority.LOW

    @pytest.mark.asyncio
    async def test_cleanup_task_execution(self):
        """测试清理任务执行"""
        task = CleanupTask()
        context = TaskContext(task_id="cleanup_123")

        result = await task(context)

        assert result.status == TaskStatus.COMPLETED
        assert result.result["cleaned_files"] == 0
        assert result.result["cleaned_records"] == 0
        assert "timestamp" in result.result


class TestTaskResult:
    """测试任务结果"""

    def test_task_result_creation(self):
        """测试任务结果创建"""
        start_time = datetime.now()
        end_time = datetime.now()

        result = TaskResult(
            task_id="test_123",
            status=TaskStatus.COMPLETED,
            result={"key": "value"},
            start_time=start_time,
            end_time=end_time,
            duration=10.5,
            retry_count=2,
            metadata={"test": True},
        )

        assert result.task_id == "test_123"
        assert result.status == TaskStatus.COMPLETED
        assert result.result == {"key": "value"}
        assert result.start_time == start_time
        assert result.end_time == end_time
        assert result.duration == 10.5
        assert result.retry_count == 2
        assert result.metadata["test"] is True

    def test_task_result_to_dict(self):
        """测试任务结果转换为字典"""
        start_time = datetime(2023, 1, 1, 12, 0, 0)
        end_time = datetime(2023, 1, 1, 12, 0, 10)

        result = TaskResult(
            task_id="test_456",
            status=TaskStatus.FAILED,
            error="Something went wrong",
            start_time=start_time,
            end_time=end_time,
            duration=10.0,
        )

        result_dict = result.to_dict()

        assert result_dict["task_id"] == "test_456"
        assert result_dict["status"] == "failed"
        assert result_dict["result"] is None
        assert result_dict["error"] == "Something went wrong"
        assert result_dict["start_time"] == "2023-01-01T12:00:00"
        assert result_dict["end_time"] == "2023-01-01T12:00:10"
        assert result_dict["duration"] == 10.0
        assert result_dict["retry_count"] == 0
