# 生成命令: /speckit.implement T051
# 生成时间: 2025-12-20
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
索引任务测试 (T051)

该模块测试文档解析和索引构建的异步任务功能。
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.application.services.knowledge_base_service import (
    KnowledgeBaseService,
    KnowledgeBaseStatus,
)
from src.infrastructure.tasks.indexing_tasks import (
    IndexingTasks,
    TaskResult,
    TaskStatus,
    TaskType,
    WorkerSettings,
    cleanup_expired_tasks,
    create_knowledge_base_async,
    delete_knowledge_base_async,
    execute_create_knowledge_base_task,
    execute_delete_knowledge_base_task,
    execute_query_knowledge_base_task,
    execute_update_knowledge_base_task,
    get_task_manager,
    query_knowledge_base_async,
    update_knowledge_base_async,
)


class TestTaskResult:
    """测试TaskResult类"""

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        start_time = datetime.now()
        end_time = datetime.now()
        
        task_result = TaskResult(
            task_id="test_id",
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            status=TaskStatus.COMPLETED,
            result={"success": True},
            error=None,
            start_time=start_time,
            end_time=end_time,
            progress={"current": 100, "total": 100},
        )
        
        result_dict = task_result.to_dict()
        
        assert result_dict["task_id"] == "test_id"
        assert result_dict["task_type"] == TaskType.CREATE_KNOWLEDGE_BASE.value
        assert result_dict["status"] == TaskStatus.COMPLETED.value
        assert result_dict["result"] == {"success": True}
        assert result_dict["error"] is None
        assert result_dict["start_time"] == start_time.isoformat()
        assert result_dict["end_time"] == end_time.isoformat()
        assert result_dict["duration_seconds"] is not None
        assert result_dict["progress"] == {"current": 100, "total": 100}


class TestIndexingTasks:
    """测试IndexingTasks类"""

    @pytest.fixture
    def task_manager(self) -> IndexingTasks:
        """创建任务管理器实例"""
        return IndexingTasks()

    @pytest.mark.asyncio
    async def test_create_knowledge_base_task(self, task_manager: IndexingTasks) -> None:
        """测试创建知识库任务"""
        task_id = await task_manager.create_knowledge_base_task(
            name="test_kb",
            directories=["/test/dir1", "/test/dir2"],
            description="测试知识库",
        )
        
        assert task_id is not None
        assert task_id in task_manager._task_results
        
        task_result = task_manager._task_results[task_id]
        assert task_result.task_id == task_id
        assert task_result.task_type == TaskType.CREATE_KNOWLEDGE_BASE
        assert task_result.status == TaskStatus.PENDING
        assert task_result.start_time is not None

    @pytest.mark.asyncio
    async def test_update_knowledge_base_task(self, task_manager: IndexingTasks) -> None:
        """测试更新知识库任务"""
        kb_id = str(uuid4())
        task_id = await task_manager.update_knowledge_base_task(
            knowledge_base_id=kb_id,
            directories=["/test/dir3"],
        )
        
        assert task_id is not None
        assert task_id in task_manager._task_results
        
        task_result = task_manager._task_results[task_id]
        assert task_result.task_id == task_id
        assert task_result.task_type == TaskType.UPDATE_KNOWLEDGE_BASE
        assert task_result.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_delete_knowledge_base_task(self, task_manager: IndexingTasks) -> None:
        """测试删除知识库任务"""
        kb_id = str(uuid4())
        task_id = await task_manager.delete_knowledge_base_task(knowledge_base_id=kb_id)
        
        assert task_id is not None
        assert task_id in task_manager._task_results
        
        task_result = task_manager._task_results[task_id]
        assert task_result.task_id == task_id
        assert task_result.task_type == TaskType.DELETE_KNOWLEDGE_BASE
        assert task_result.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_query_knowledge_base_task(self, task_manager: IndexingTasks) -> None:
        """测试查询知识库任务"""
        kb_id = str(uuid4())
        task_id = await task_manager.query_knowledge_base_task(
            knowledge_base_id=kb_id,
            query_str="测试查询",
            top_k=5,
        )
        
        assert task_id is not None
        assert task_id in task_manager._task_results
        
        task_result = task_manager._task_results[task_id]
        assert task_result.task_id == task_id
        assert task_result.task_type == TaskType.QUERY_KNOWLEDGE_BASE
        assert task_result.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_task_status(self, task_manager: IndexingTasks) -> None:
        """测试获取任务状态"""
        # 创建任务
        task_id = await task_manager.create_knowledge_base_task(
            name="test_kb",
            directories=["/test/dir"],
        )
        
        # 获取任务状态
        status = await task_manager.get_task_status(task_id)
        
        assert status is not None
        assert status["task_id"] == task_id
        assert status["status"] == TaskStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, task_manager: IndexingTasks) -> None:
        """测试获取不存在的任务状态"""
        status = await task_manager.get_task_status("not_found")
        assert status is None

    @pytest.mark.asyncio
    async def test_get_all_tasks(self, task_manager: IndexingTasks) -> None:
        """测试获取所有任务状态"""
        # 创建多个任务
        task_id1 = await task_manager.create_knowledge_base_task(
            name="test_kb1",
            directories=["/test/dir1"],
        )
        task_id2 = await task_manager.update_knowledge_base_task(
            knowledge_base_id=str(uuid4()),
            directories=["/test/dir2"],
        )
        
        # 获取所有任务状态
        all_tasks = await task_manager.get_all_tasks()
        
        assert len(all_tasks) >= 2
        task_ids = [task["task_id"] for task in all_tasks]
        assert task_id1 in task_ids
        assert task_id2 in task_ids

    @pytest.mark.asyncio
    async def test_cancel_task(self, task_manager: IndexingTasks) -> None:
        """测试取消任务"""
        # 创建任务
        task_id = await task_manager.create_knowledge_base_task(
            name="test_kb",
            directories=["/test/dir"],
        )
        
        # 取消任务
        success = await task_manager.cancel_task(task_id)
        
        assert success is True
        
        # 检查任务状态
        status = await task_manager.get_task_status(task_id)
        assert status["status"] == TaskStatus.CANCELLED.value

    @pytest.mark.asyncio
    async def test_cancel_completed_task(self, task_manager: IndexingTasks) -> None:
        """测试取消已完成的任务"""
        # 创建任务
        task_id = await task_manager.create_knowledge_base_task(
            name="test_kb",
            directories=["/test/dir"],
        )
        
        # 手动设置为已完成
        task_result = task_manager._task_results[task_id]
        task_result.status = TaskStatus.COMPLETED
        task_result.end_time = datetime.now()
        
        # 尝试取消任务
        success = await task_manager.cancel_task(task_id)
        
        assert success is False

    @pytest.mark.asyncio
    async def test_get_or_create_knowledge_base_service(self, task_manager: IndexingTasks) -> None:
        """测试获取或创建知识库服务"""
        kb_id = str(uuid4())
        
        # 第一次调用应该创建新实例
        service1 = task_manager._get_or_create_knowledge_base_service(
            knowledge_base_id=kb_id,
        )
        assert isinstance(service1, KnowledgeBaseService)
        
        # 第二次调用应该返回相同实例
        service2 = task_manager._get_or_create_knowledge_base_service(
            knowledge_base_id=kb_id,
        )
        assert service1 is service2


class TestExecuteTasks:
    """测试任务执行函数"""

    @pytest.mark.asyncio
    async def test_execute_create_knowledge_base_task_success(self) -> None:
        """测试成功执行创建知识库任务"""
        task_id = str(uuid4())
        
        # 创建任务结果
        task_manager = get_task_manager()
        task_manager._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )
        
        # 模拟知识库服务
        mock_service = MagicMock()
        mock_service.create_knowledge_base.return_value = {
            "knowledge_base_id": str(uuid4()),
            "name": "test_kb",
            "status": KnowledgeBaseStatus.READY.value,
        }
        
        with patch.object(
            task_manager,
            "_get_or_create_knowledge_base_service",
            return_value=mock_service,
        ):
            # 执行任务
            result = await execute_create_knowledge_base_task(
                ctx=None,
                task_id=task_id,
                name="test_kb",
                directories=["/test/dir"],
            )
        
        # 验证结果
        assert result["status"] == TaskStatus.COMPLETED.value
        assert result["result"] is not None
        assert result["error"] is None
        
        # 验证服务调用
        mock_service.create_knowledge_base.assert_called_once_with(
            name="test_kb",
            directories=["/test/dir"],
            description=None,
            show_progress=False,
        )

    @pytest.mark.asyncio
    async def test_execute_create_knowledge_base_task_failure(self) -> None:
        """测试执行创建知识库任务失败"""
        task_id = str(uuid4())
        
        # 创建任务结果
        task_manager = get_task_manager()
        task_manager._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )
        
        # 模拟知识库服务抛出异常
        mock_service = MagicMock()
        mock_service.create_knowledge_base.side_effect = Exception("测试异常")
        
        with patch.object(
            task_manager,
            "_get_or_create_knowledge_base_service",
            return_value=mock_service,
        ):
            # 执行任务
            result = await execute_create_knowledge_base_task(
                ctx=None,
                task_id=task_id,
                name="test_kb",
                directories=["/test/dir"],
            )
        
        # 验证结果
        assert result["status"] == TaskStatus.FAILED.value
        assert result["result"] is None
        assert "测试异常" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_create_knowledge_base_task_not_found(self) -> None:
        """测试执行不存在的创建知识库任务"""
        with pytest.raises(ValueError, match="任务不存在"):
            await execute_create_knowledge_base_task(
                ctx=None,
                task_id="not_found",
                name="test_kb",
                directories=["/test/dir"],
            )

    @pytest.mark.asyncio
    async def test_execute_update_knowledge_base_task_success(self) -> None:
        """测试成功执行更新知识库任务"""
        task_id = str(uuid4())
        kb_id = str(uuid4())
        
        # 创建任务结果
        task_manager = get_task_manager()
        task_manager._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.UPDATE_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )
        
        # 模拟知识库服务
        mock_service = MagicMock()
        mock_service.update_knowledge_base.return_value = {
            "knowledge_base_id": kb_id,
            "status": KnowledgeBaseStatus.READY.value,
            "new_documents_count": 1,
        }
        
        with patch.object(
            task_manager,
            "_get_or_create_knowledge_base_service",
            return_value=mock_service,
        ):
            # 执行任务
            result = await execute_update_knowledge_base_task(
                ctx=None,
                task_id=task_id,
                knowledge_base_id=kb_id,
                directories=["/test/dir"],
            )
        
        # 验证结果
        assert result["status"] == TaskStatus.COMPLETED.value
        assert result["result"] is not None
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_execute_delete_knowledge_base_task_success(self) -> None:
        """测试成功执行删除知识库任务"""
        task_id = str(uuid4())
        kb_id = str(uuid4())
        
        # 创建任务结果
        task_manager = get_task_manager()
        task_manager._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.DELETE_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )
        
        # 模拟知识库服务
        mock_service = MagicMock()
        mock_service.delete_knowledge_base.return_value = {
            "knowledge_base_id": kb_id,
            "status": "deleted",
        }
        
        with patch.object(
            task_manager,
            "_get_or_create_knowledge_base_service",
            return_value=mock_service,
        ):
            # 执行任务
            result = await execute_delete_knowledge_base_task(
                ctx=None,
                task_id=task_id,
                knowledge_base_id=kb_id,
            )
        
        # 验证结果
        assert result["status"] == TaskStatus.COMPLETED.value
        assert result["result"] is not None
        assert result["error"] is None
        
        # 验证服务已从缓存中移除
        assert kb_id not in task_manager._knowledge_base_services

    @pytest.mark.asyncio
    async def test_execute_query_knowledge_base_task_success(self) -> None:
        """测试成功执行查询知识库任务"""
        task_id = str(uuid4())
        kb_id = str(uuid4())
        
        # 创建任务结果
        task_manager = get_task_manager()
        task_manager._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.QUERY_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )
        
        # 模拟查询结果
        mock_node = MagicMock()
        mock_node.node_id = "node_1"
        mock_node.text = "测试文本"
        mock_node.metadata = {"source": "test"}
        
        mock_result = MagicMock()
        mock_result.node = mock_node
        mock_result.score = 0.9
        
        # 模拟知识库服务
        mock_service = MagicMock()
        mock_service.query.return_value = [mock_result]
        
        with patch.object(
            task_manager,
            "_get_or_create_knowledge_base_service",
            return_value=mock_service,
        ):
            # 执行任务
            result = await execute_query_knowledge_base_task(
                ctx=None,
                task_id=task_id,
                knowledge_base_id=kb_id,
                query_str="测试查询",
                top_k=5,
            )
        
        # 验证结果
        assert result["status"] == TaskStatus.COMPLETED.value
        assert result["result"] is not None
        assert result["error"] is None
        assert result["result"]["query"] == "测试查询"
        assert result["result"]["results_count"] == 1
        assert len(result["result"]["results"]) == 1
        assert result["result"]["results"][0]["node_id"] == "node_1"
        assert result["result"]["results"][0]["text"] == "测试文本"
        assert result["result"]["results"][0]["score"] == 0.9


class TestWorkerSettings:
    """测试WorkerSettings配置"""

    def test_worker_settings(self) -> None:
        """测试WorkerSettings配置"""
        settings = WorkerSettings()
        
        # 验证函数列表
        assert len(settings.functions) == 4
        assert execute_create_knowledge_base_task in settings.functions
        assert execute_update_knowledge_base_task in settings.functions
        assert execute_delete_knowledge_base_task in settings.functions
        assert execute_query_knowledge_base_task in settings.functions
        
        # 验证其他配置
        assert settings.retry_jobs is True
        assert settings.max_retries == 3
        assert settings.job_timeout == 3600
        assert settings.queue_name == "indexing_tasks"
        assert len(settings.cron_jobs) == 1


class TestConvenienceFunctions:
    """测试便捷函数"""

    @pytest.mark.asyncio
    async def test_create_knowledge_base_async(self) -> None:
        """测试创建知识库异步便捷函数"""
        with patch("src.infrastructure.tasks.indexing_tasks.get_task_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.create_knowledge_base_task.return_value = "test_task_id"
            mock_get_manager.return_value = mock_manager
            
            task_id = await create_knowledge_base_async(
                name="test_kb",
                directories=["/test/dir"],
                description="测试知识库",
            )
            
            assert task_id == "test_task_id"
            mock_manager.create_knowledge_base_task.assert_called_once_with(
                name="test_kb",
                directories=["/test/dir"],
                description="测试知识库",
            )

    @pytest.mark.asyncio
    async def test_update_knowledge_base_async(self) -> None:
        """测试更新知识库异步便捷函数"""
        kb_id = str(uuid4())
        
        with patch("src.infrastructure.tasks.indexing_tasks.get_task_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.update_knowledge_base_task.return_value = "test_task_id"
            mock_get_manager.return_value = mock_manager
            
            task_id = await update_knowledge_base_async(
                knowledge_base_id=kb_id,
                directories=["/test/dir"],
            )
            
            assert task_id == "test_task_id"
            mock_manager.update_knowledge_base_task.assert_called_once_with(
                knowledge_base_id=kb_id,
                directories=["/test/dir"],
                documents=None,
            )

    @pytest.mark.asyncio
    async def test_delete_knowledge_base_async(self) -> None:
        """测试删除知识库异步便捷函数"""
        kb_id = str(uuid4())
        
        with patch("src.infrastructure.tasks.indexing_tasks.get_task_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.delete_knowledge_base_task.return_value = "test_task_id"
            mock_get_manager.return_value = mock_manager
            
            task_id = await delete_knowledge_base_async(knowledge_base_id=kb_id)
            
            assert task_id == "test_task_id"
            mock_manager.delete_knowledge_base_task.assert_called_once_with(
                knowledge_base_id=kb_id,
            )

    @pytest.mark.asyncio
    async def test_query_knowledge_base_async(self) -> None:
        """测试查询知识库异步便捷函数"""
        kb_id = str(uuid4())
        
        with patch("src.infrastructure.tasks.indexing_tasks.get_task_manager") as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.query_knowledge_base_task.return_value = "test_task_id"
            mock_get_manager.return_value = mock_manager
            
            task_id = await query_knowledge_base_async(
                knowledge_base_id=kb_id,
                query_str="测试查询",
                top_k=5,
            )
            
            assert task_id == "test_task_id"
            mock_manager.query_knowledge_base_task.assert_called_once_with(
                knowledge_base_id=kb_id,
                query_str="测试查询",
                top_k=5,
            )


class TestCleanupExpiredTasks:
    """测试清理过期任务功能"""

    @pytest.mark.asyncio
    async def test_cleanup_expired_tasks(self) -> None:
        """测试清理过期任务"""
        task_manager = get_task_manager()
        
        # 创建过期任务（超过7天）
        old_time = datetime.now()
        # 使用一个较早的时间模拟过期
        import datetime as dt
        old_time = old_time - dt.timedelta(days=8)
        
        old_task_id = str(uuid4())
        task_manager._task_results[old_task_id] = TaskResult(
            task_id=old_task_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            status=TaskStatus.COMPLETED,
            start_time=old_time,
            end_time=old_time,
        )
        
        # 创建未过期任务
        recent_task_id = str(uuid4())
        task_manager._task_results[recent_task_id] = TaskResult(
            task_id=recent_task_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            status=TaskStatus.COMPLETED,
            start_time=datetime.now(),
            end_time=datetime.now(),
        )
        
        # 执行清理
        await cleanup_expired_tasks(ctx=None)
        
        # 验证过期任务已清理
        assert old_task_id not in task_manager._task_results
        # 验证未过期任务保留
        assert recent_task_id in task_manager._task_results


class TestGetTaskManager:
    """测试获取任务管理器"""

    def test_get_task_manager_singleton(self) -> None:
        """测试任务管理器单例"""
        manager1 = get_task_manager()
        manager2 = get_task_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, IndexingTasks)