# 生成命令: /speckit.implement T057
# 生成时间: 2025-12-21
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
索引构建进度跟踪和状态管理服务测试 (T057)

该模块测试索引构建进度跟踪和状态管理服务的功能。
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.application.services.indexing_progress_service import IndexingProgressService, get_progress_service
from src.domain.indexing.indexing_progress import (
    IndexingProgress,
    IndexingStep,
    StepStatus,
    TaskStatus,
    TaskType,
)


class TestIndexingProgressService:
    """索引构建进度跟踪服务测试类"""
    
    @pytest.fixture
    def mock_db_adapter(self):
        """模拟数据库适配器"""
        adapter = MagicMock()
        adapter.create.return_value = {
            "id": "test-progress-id",
            "task_id": "test-task-id",
            "knowledge_base_id": "test-kb-id",
            "task_type": TaskType.CREATE_KNOWLEDGE_BASE,
            "status": TaskStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return adapter
    
    @pytest.fixture
    def mock_steps_adapter(self):
        """模拟步骤数据库适配器"""
        adapter = MagicMock()
        adapter.create.return_value = {
            "id": "test-step-id",
            "progress_id": "test-progress-id",
            "step_name": "test-step",
            "step_order": 1,
            "status": StepStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return adapter
    
    @pytest.fixture
    def progress_service(self, mock_db_adapter, mock_steps_adapter):
        """进度跟踪服务实例"""
        with patch('src.application.services.indexing_progress_service.SQLiteAdapter') as mock_adapter_class:
            mock_adapter_class.side_effect = [mock_db_adapter, mock_steps_adapter]
            return IndexingProgressService()
    
    def test_create_progress(self, progress_service, mock_db_adapter, mock_steps_adapter):
        """测试创建进度跟踪记录"""
        # 准备测试数据
        task_id = "test-task-id"
        knowledge_base_id = "test-kb-id"
        task_type = TaskType.CREATE_KNOWLEDGE_BASE
        steps = [
            {
                "step_name": "load_documents",
                "step_order": 1,
                "description": "加载文档"
            },
            {
                "step_name": "parse_documents",
                "step_order": 2,
                "description": "解析文档"
            }
        ]
        
        # 执行测试
        progress = progress_service.create_progress(
            task_id=task_id,
            knowledge_base_id=knowledge_base_id,
            task_type=task_type,
            steps=steps
        )
        
        # 验证结果
        assert progress.task_id == task_id
        assert progress.knowledge_base_id == knowledge_base_id
        assert progress.task_type == task_type
        assert len(progress.steps) == 2
        assert progress.steps[0].step_name == "load_documents"
        assert progress.steps[1].step_name == "parse_documents"
        
        # 验证数据库调用
        mock_db_adapter.create.assert_called_once()
        assert mock_steps_adapter.create.call_count == 2
    
    def test_get_progress(self, progress_service, mock_db_adapter, mock_steps_adapter):
        """测试获取进度跟踪记录"""
        # 准备模拟数据
        task_id = "test-task-id"
        progress_record = {
            "id": "test-progress-id",
            "task_id": task_id,
            "knowledge_base_id": "test-kb-id",
            "task_type": TaskType.CREATE_KNOWLEDGE_BASE,
            "status": TaskStatus.RUNNING,
            "start_time": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "total_steps": 2,
            "completed_steps": 1,
            "progress_percentage": 50.0,
        }
        
        step_records = [
            {
                "id": "test-step-1-id",
                "progress_id": "test-progress-id",
                "step_name": "load_documents",
                "step_order": 1,
                "status": StepStatus.COMPLETED,
                "start_time": datetime.now().isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_seconds": 10.5,
                "description": "加载文档",
                "details": {},
                "error_message": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            {
                "id": "test-step-2-id",
                "progress_id": "test-progress-id",
                "step_name": "parse_documents",
                "step_order": 2,
                "status": StepStatus.RUNNING,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "duration_seconds": None,
                "description": "解析文档",
                "details": {},
                "error_message": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        ]
        
        mock_db_adapter.execute_custom_query.return_value = progress_record
        mock_steps_adapter.list.return_value = step_records
        
        # 执行测试
        progress = progress_service.get_progress(task_id)
        
        # 验证结果
        assert progress is not None
        assert progress.task_id == task_id
        assert progress.status == TaskStatus.RUNNING
        assert progress.total_steps == 2
        assert progress.completed_steps == 1
        assert progress.progress_percentage == 50.0
        assert len(progress.steps) == 2
        assert progress.steps[0].step_name == "load_documents"
        assert progress.steps[0].status == StepStatus.COMPLETED
        assert progress.steps[1].step_name == "parse_documents"
        assert progress.steps[1].status == StepStatus.RUNNING
        
        # 验证数据库调用
        mock_db_adapter.execute_custom_query.assert_called_once()
        mock_steps_adapter.list.assert_called_once()
    
    def test_get_progress_not_found(self, progress_service, mock_db_adapter):
        """测试获取不存在的进度跟踪记录"""
        # 准备模拟数据
        task_id = "non-existent-task-id"
        mock_db_adapter.execute_custom_query.return_value = None
        
        # 执行测试
        progress = progress_service.get_progress(task_id)
        
        # 验证结果
        assert progress is None
        
        # 验证数据库调用
        mock_db_adapter.execute_custom_query.assert_called_once()
    
    def test_update_progress(self, progress_service, mock_db_adapter, mock_steps_adapter):
        """测试更新进度跟踪记录"""
        # 准备模拟数据
        task_id = "test-task-id"
        progress_record = {
            "id": "test-progress-id",
            "task_id": task_id,
            "knowledge_base_id": "test-kb-id",
            "task_type": TaskType.CREATE_KNOWLEDGE_BASE,
            "status": TaskStatus.RUNNING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        step_records = []
        
        mock_db_adapter.execute_custom_query.return_value = progress_record
        mock_steps_adapter.list.return_value = step_records
        mock_db_adapter.update.return_value = progress_record
        
        # 执行测试
        progress = progress_service.update_progress(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            current_step="build_indexes",
            completed_steps=4,
            documents_count=10,
            nodes_count=50,
            chunks_count=100,
            vector_indexed_count=100,
            bm25_indexed_count=100,
            metadata_indexed_count=100,
        )
        
        # 验证结果
        assert progress is not None
        assert progress.status == TaskStatus.COMPLETED
        assert progress.current_step == "build_indexes"
        assert progress.completed_steps == 4
        assert progress.documents_count == 10
        assert progress.nodes_count == 50
        assert progress.chunks_count == 100
        assert progress.vector_indexed_count == 100
        assert progress.bm25_indexed_count == 100
        assert progress.metadata_indexed_count == 100
        
        # 验证数据库调用
        assert mock_db_adapter.execute_custom_query.call_count == 2
        # update_progress 方法使用 execute_custom_query 而不是 update
        assert mock_db_adapter.execute_custom_query.call_count == 2
    
    def test_update_step(self, progress_service, mock_db_adapter, mock_steps_adapter):
        """测试更新步骤状态"""
        # 准备模拟数据
        task_id = "test-task-id"
        progress_record = {
            "id": "test-progress-id",
            "task_id": task_id,
            "knowledge_base_id": "test-kb-id",
            "task_type": TaskType.CREATE_KNOWLEDGE_BASE,
            "status": TaskStatus.RUNNING,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        step_records = [
            {
                "id": "test-step-id",
                "progress_id": "test-progress-id",
                "step_name": "load_documents",
                "step_order": 1,
                "status": StepStatus.RUNNING,
                "start_time": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        ]
        
        mock_db_adapter.execute_custom_query.return_value = progress_record
        mock_steps_adapter.list.return_value = step_records
        mock_steps_adapter.update.return_value = step_records[0]
        
        # 执行测试
        step = progress_service.update_step(
            task_id=task_id,
            step_name="load_documents",
            status=StepStatus.COMPLETED,
            description="文档加载完成",
            details={"processed_files": 10}
        )
        
        # 验证结果
        assert step is not None
        assert step.step_name == "load_documents"
        assert step.status == StepStatus.COMPLETED
        assert step.description == "文档加载完成"
        assert step.details["processed_files"] == 10
        
        # 验证数据库调用
        mock_db_adapter.execute_custom_query.assert_called_once()
        mock_steps_adapter.list.assert_called_once()
        mock_steps_adapter.update.assert_called_once()
    
    def test_list_progress(self, progress_service, mock_db_adapter):
        """测试列出进度跟踪记录"""
        # 准备模拟数据
        progress_records = [
            {
                "id": "test-progress-1-id",
                "task_id": "test-task-1-id",
                "knowledge_base_id": "test-kb-1-id",
                "task_type": TaskType.CREATE_KNOWLEDGE_BASE,
                "status": TaskStatus.COMPLETED,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            {
                "id": "test-progress-2-id",
                "task_id": "test-task-2-id",
                "knowledge_base_id": "test-kb-2-id",
                "task_type": TaskType.UPDATE_KNOWLEDGE_BASE,
                "status": TaskStatus.RUNNING,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        ]
        
        # 模拟过滤器，只返回符合条件的记录
        def mock_list_with_filters(table_name=None, filters=None, limit=None, offset=None, order_by=None):
            if filters and filters.get("task_type") == TaskType.CREATE_KNOWLEDGE_BASE and filters.get("status") == TaskStatus.COMPLETED:
                return [progress_records[0]]
            return progress_records
        
        mock_db_adapter.list.side_effect = mock_list_with_filters
        mock_db_adapter.execute_custom_query.return_value = progress_records[0]
        
        # 执行测试
        progress_list = progress_service.list_progress(
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            status=TaskStatus.COMPLETED
        )
        
        # 验证结果
        assert len(progress_list) == 1
        assert progress_list[0].task_id == "test-task-1-id"
        assert progress_list[0].task_type == TaskType.CREATE_KNOWLEDGE_BASE
        assert progress_list[0].status == TaskStatus.COMPLETED
        
        # 验证数据库调用
        mock_db_adapter.list.assert_called_once()
    
    def test_delete_progress(self, progress_service, mock_db_adapter, mock_steps_adapter):
        """测试删除进度跟踪记录"""
        # 准备模拟数据
        task_id = "test-task-id"
        progress_record = {
            "id": "test-progress-id",
            "task_id": task_id,
            "knowledge_base_id": "test-kb-id",
            "task_type": TaskType.CREATE_KNOWLEDGE_BASE,
            "status": TaskStatus.COMPLETED,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        
        step_records = [
            {
                "id": "test-step-1-id",
                "progress_id": "test-progress-id",
                "step_name": "load_documents",
                "step_order": 1,
                "status": StepStatus.COMPLETED,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            {
                "id": "test-step-2-id",
                "progress_id": "test-progress-id",
                "step_name": "parse_documents",
                "step_order": 2,
                "status": StepStatus.COMPLETED,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        ]
        
        mock_db_adapter.execute_custom_query.return_value = progress_record
        mock_steps_adapter.list.return_value = step_records
        mock_db_adapter.delete.return_value = True
        mock_steps_adapter.delete.return_value = True
        
        # 执行测试
        result = progress_service.delete_progress(task_id)
        
        # 验证结果
        assert result is True
        
        # 验证数据库调用
        assert mock_db_adapter.execute_custom_query.call_count == 2
        mock_steps_adapter.list.assert_called_once()
        assert mock_steps_adapter.delete.call_count == 2
        # delete_progress 方法使用 execute_custom_query 而不是 delete
    
    def test_get_progress_summary(self, progress_service, mock_db_adapter, mock_steps_adapter):
        """测试获取进度摘要"""
        # 准备模拟数据
        task_id = "test-task-id"
        progress_record = {
            "id": "test-progress-id",
            "task_id": task_id,
            "knowledge_base_id": "test-kb-id",
            "task_type": TaskType.CREATE_KNOWLEDGE_BASE,
            "status": TaskStatus.COMPLETED,
            "start_time": (datetime.now() - timedelta(minutes=10)).isoformat(),
            "end_time": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "total_steps": 4,
            "completed_steps": 4,
            "progress_percentage": 100.0,
            "documents_count": 10,
            "nodes_count": 50,
            "chunks_count": 100,
            "vector_indexed_count": 100,
            "bm25_indexed_count": 100,
            "metadata_indexed_count": 100,
        }
        
        step_records = [
            {
                "id": "test-step-1-id",
                "progress_id": "test-progress-id",
                "step_name": "load_documents",
                "step_order": 1,
                "status": StepStatus.COMPLETED,
                "start_time": (datetime.now() - timedelta(minutes=10)).isoformat(),
                "end_time": (datetime.now() - timedelta(minutes=8)).isoformat(),
                "duration_seconds": 120.0,
                "description": "加载文档",
                "details": {"processed_files": 10},
                "error_message": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            {
                "id": "test-step-2-id",
                "progress_id": "test-progress-id",
                "step_name": "parse_documents",
                "step_order": 2,
                "status": StepStatus.COMPLETED,
                "start_time": (datetime.now() - timedelta(minutes=8)).isoformat(),
                "end_time": (datetime.now() - timedelta(minutes=6)).isoformat(),
                "duration_seconds": 120.0,
                "description": "解析文档",
                "details": {"parsed_nodes": 50},
                "error_message": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            {
                "id": "test-step-3-id",
                "progress_id": "test-progress-id",
                "step_name": "chunk_documents",
                "step_order": 3,
                "status": StepStatus.COMPLETED,
                "start_time": (datetime.now() - timedelta(minutes=6)).isoformat(),
                "end_time": (datetime.now() - timedelta(minutes=4)).isoformat(),
                "duration_seconds": 120.0,
                "description": "分块处理",
                "details": {"created_chunks": 100},
                "error_message": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            {
                "id": "test-step-4-id",
                "progress_id": "test-progress-id",
                "step_name": "build_indexes",
                "step_order": 4,
                "status": StepStatus.COMPLETED,
                "start_time": (datetime.now() - timedelta(minutes=4)).isoformat(),
                "end_time": datetime.now().isoformat(),
                "duration_seconds": 240.0,
                "description": "构建索引",
                "details": {"indexed_chunks": 100},
                "error_message": None,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }
        ]
        
        mock_db_adapter.execute_custom_query.return_value = progress_record
        mock_steps_adapter.list.return_value = step_records
        
        # 执行测试
        summary = progress_service.get_progress_summary(task_id)
        
        # 验证结果
        assert summary is not None
        assert summary["task_id"] == task_id
        assert summary["knowledge_base_id"] == "test-kb-id"
        assert summary["task_type"] == "create_knowledge_base"
        assert summary["status"] == "completed"
        assert summary["progress_percentage"] == 100.0
        assert summary["total_steps"] == 4
        assert summary["completed_steps"] == 4
        assert summary["statistics"]["documents_count"] == 10
        assert summary["statistics"]["nodes_count"] == 50
        assert summary["statistics"]["chunks_count"] == 100
        assert summary["statistics"]["vector_indexed_count"] == 100
        assert summary["statistics"]["bm25_indexed_count"] == 100
        assert summary["statistics"]["metadata_indexed_count"] == 100
        assert len(summary["steps"]) == 4
        assert summary["steps"][0]["name"] == "load_documents"
        assert summary["steps"][0]["status"] == "completed"
        assert summary["steps"][0]["duration_seconds"] == 120.0
        
        # 验证数据库调用
        mock_db_adapter.execute_custom_query.assert_called_once()
        mock_steps_adapter.list.assert_called_once()


class TestGetProgressService:
    """获取全局进度跟踪服务测试类"""
    
    def test_get_progress_service_singleton(self):
        """测试获取全局进度跟踪服务实例（单例模式）"""
        service1 = get_progress_service()
        service2 = get_progress_service()
        
        # 验证是同一个实例
        assert service1 is service2
        assert isinstance(service1, IndexingProgressService)
        assert isinstance(service2, IndexingProgressService)