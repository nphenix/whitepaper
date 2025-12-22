# 生成命令: /speckit.implement T057
# 生成时间: 2025-12-21
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
T057 索引构建进度跟踪和状态管理集成测试

该模块测试索引构建进度跟踪和状态管理的完整工作流程。
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

from src.application.services.indexing_progress_service import IndexingProgressService
from src.domain.indexing.indexing_progress import (
    IndexingProgress,
    IndexingStep,
    StepStatus,
    TaskStatus,
    TaskType,
)


class TestT057Integration:
    """T057 索引构建进度跟踪和状态管理集成测试类"""
    
    @pytest.fixture
    def progress_service(self):
        """进度跟踪服务实例"""
        return IndexingProgressService()
    
    def test_complete_indexing_workflow(self, progress_service):
        """测试完整的索引构建工作流程"""
        # 1. 创建进度跟踪记录
        task_id = str(uuid4())
        knowledge_base_id = str(uuid4())
        
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
            },
            {
                "step_name": "chunk_documents",
                "step_order": 3,
                "description": "分块处理"
            },
            {
                "step_name": "build_indexes",
                "step_order": 4,
                "description": "构建索引"
            }
        ]
        
        progress = progress_service.create_progress(
            task_id=task_id,
            knowledge_base_id=knowledge_base_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            steps=steps
        )
        
        # 验证初始状态
        assert progress.task_id == task_id
        assert progress.knowledge_base_id == knowledge_base_id
        assert progress.task_type == TaskType.CREATE_KNOWLEDGE_BASE
        assert progress.status == TaskStatus.PENDING
        assert progress.total_steps == 4
        assert progress.completed_steps == 0
        assert progress.progress_percentage == 0.0
        assert len(progress.steps) == 4
        
        # 2. 开始执行任务
        progress = progress_service.update_progress(
            task_id=task_id,
            status=TaskStatus.RUNNING
        )
        
        assert progress.status == TaskStatus.RUNNING
        assert progress.start_time is not None
        
        # 3. 更新步骤状态 - 加载文档
        step = progress_service.update_step(
            task_id=task_id,
            step_name="load_documents",
            status=StepStatus.RUNNING,
            description="正在加载文档..."
        )
        
        assert step.status == StepStatus.RUNNING
        assert step.start_time is not None
        
        # 4. 完成步骤 - 加载文档
        step = progress_service.update_step(
            task_id=task_id,
            step_name="load_documents",
            status=StepStatus.COMPLETED,
            description="文档加载完成",
            details={"processed_files": 10}
        )
        
        assert step.status == StepStatus.COMPLETED
        assert step.end_time is not None
        assert step.duration_seconds > 0
        assert step.details["processed_files"] == 10
        
        # 5. 更新进度统计
        progress = progress_service.update_progress(
            task_id=task_id,
            current_step="parse_documents",
            documents_count=10,
            nodes_count=50
        )
        
        assert progress.current_step == "parse_documents"
        assert progress.documents_count == 10
        assert progress.nodes_count == 50
        
        # 6. 继续完成其他步骤
        for step_name in ["parse_documents", "chunk_documents", "build_indexes"]:
            # 开始步骤
            progress_service.update_step(
                task_id=task_id,
                step_name=step_name,
                status=StepStatus.RUNNING
            )
            
            # 完成步骤
            progress_service.update_step(
                task_id=task_id,
                step_name=step_name,
                status=StepStatus.COMPLETED,
                description=f"{step_name}完成"
            )
        
        # 7. 完成整个任务
        progress = progress_service.update_progress(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            documents_count=10,
            nodes_count=50,
            chunks_count=100,
            vector_indexed_count=100,
            bm25_indexed_count=100,
            metadata_indexed_count=100
        )
        
        assert progress.status == TaskStatus.COMPLETED
        assert progress.end_time is not None
        assert progress.duration_seconds > 0
        assert progress.completed_steps == 4
        assert progress.progress_percentage == 100.0
        assert progress.documents_count == 10
        assert progress.nodes_count == 50
        assert progress.chunks_count == 100
        assert progress.vector_indexed_count == 100
        assert progress.bm25_indexed_count == 100
        assert progress.metadata_indexed_count == 100
        
        # 8. 获取进度摘要
        summary = progress_service.get_progress_summary(task_id)
        
        assert summary is not None
        assert summary["task_id"] == task_id
        assert summary["knowledge_base_id"] == knowledge_base_id
        assert summary["task_type"] == "create_knowledge_base"
        assert summary["status"] == "completed"
        assert summary["progress_percentage"] == 100.0
        assert summary["total_steps"] == 4
        assert summary["completed_steps"] == 4
        assert summary["statistics"]["documents_count"] == 10
        assert summary["statistics"]["nodes_count"] == 50
        assert summary["statistics"]["chunks_count"] == 100
        assert len(summary["steps"]) == 4
        
        # 验证每个步骤的状态
        step_statuses = {step["name"]: step["status"] for step in summary["steps"]}
        assert step_statuses["load_documents"] == "completed"
        assert step_statuses["parse_documents"] == "completed"
        assert step_statuses["chunk_documents"] == "completed"
        assert step_statuses["build_indexes"] == "completed"
    
    def test_error_handling_workflow(self, progress_service):
        """测试错误处理工作流程"""
        # 创建进度跟踪记录
        task_id = str(uuid4())
        knowledge_base_id = str(uuid4())
        
        steps = [
            {
                "step_name": "load_documents",
                "step_order": 1,
                "description": "加载文档"
            }
        ]
        
        progress = progress_service.create_progress(
            task_id=task_id,
            knowledge_base_id=knowledge_base_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            steps=steps
        )
        
        # 开始执行任务
        progress = progress_service.update_progress(
            task_id=task_id,
            status=TaskStatus.RUNNING
        )
        
        # 模拟步骤失败
        step = progress_service.update_step(
            task_id=task_id,
            step_name="load_documents",
            status=StepStatus.FAILED,
            error_message="文件不存在: test.pdf"
        )
        
        assert step.status == StepStatus.FAILED
        assert step.error_message == "文件不存在: test.pdf"
        
        # 标记整个任务失败
        progress = progress_service.update_progress(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_message="文档加载失败",
            error_traceback="Traceback (most recent call last):..."
        )
        
        assert progress.status == TaskStatus.FAILED
        assert progress.error_message == "文档加载失败"
        assert progress.error_traceback == "Traceback (most recent call last):..."
        assert progress.end_time is not None
        
        # 获取进度摘要
        summary = progress_service.get_progress_summary(task_id)
        assert summary["status"] == "failed"
        assert summary["error_message"] == "文档加载失败"
        assert summary["steps"][0]["status"] == "failed"
        assert summary["steps"][0]["error_message"] == "文件不存在: test.pdf"
    
    def test_list_and_filter_progress(self, progress_service):
        """测试列出和过滤进度记录"""
        # 创建多个进度记录
        kb_id = str(uuid4())
        
        # 创建第一个任务（已完成）
        task1_id = str(uuid4())
        progress_service.create_progress(
            task_id=task1_id,
            knowledge_base_id=kb_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE
        )
        progress_service.update_progress(
            task_id=task1_id,
            status=TaskStatus.COMPLETED
        )
        
        # 创建第二个任务（运行中）
        task2_id = str(uuid4())
        progress_service.create_progress(
            task_id=task2_id,
            knowledge_base_id=kb_id,
            task_type=TaskType.UPDATE_KNOWLEDGE_BASE
        )
        progress_service.update_progress(
            task_id=task2_id,
            status=TaskStatus.RUNNING
        )
        
        # 创建第三个任务（不同知识库）
        task3_id = str(uuid4())
        progress_service.create_progress(
            task_id=task3_id,
            knowledge_base_id=str(uuid4()),
            task_type=TaskType.CREATE_KNOWLEDGE_BASE
        )
        progress_service.update_progress(
            task_id=task3_id,
            status=TaskStatus.PENDING
        )
        
        # 测试列出所有记录
        all_progress = progress_service.list_progress()
        assert len(all_progress) >= 3
        
        # 测试按知识库过滤
        kb_progress = progress_service.list_progress(knowledge_base_id=kb_id)
        assert len(kb_progress) == 2
        kb_task_ids = {p.task_id for p in kb_progress}
        assert task1_id in kb_task_ids
        assert task2_id in kb_task_ids
        assert task3_id not in kb_task_ids
        
        # 测试按状态过滤
        completed_progress = progress_service.list_progress(status=TaskStatus.COMPLETED)
        completed_task_ids = {p.task_id for p in completed_progress}
        assert task1_id in completed_task_ids
        assert task2_id not in completed_task_ids
        assert task3_id not in completed_task_ids
        
        # 测试按任务类型过滤
        create_progress = progress_service.list_progress(task_type=TaskType.CREATE_KNOWLEDGE_BASE)
        create_task_ids = {p.task_id for p in create_progress}
        assert task1_id in create_task_ids
        assert task2_id not in create_task_ids
        assert task3_id in create_task_ids
        
        # 测试组合过滤
        filtered_progress = progress_service.list_progress(
            knowledge_base_id=kb_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            status=TaskStatus.COMPLETED
        )
        assert len(filtered_progress) == 1
        assert filtered_progress[0].task_id == task1_id
    
    def test_delete_progress_workflow(self, progress_service):
        """测试删除进度记录工作流程"""
        # 创建进度记录
        task_id = str(uuid4())
        knowledge_base_id = str(uuid4())
        
        progress = progress_service.create_progress(
            task_id=task_id,
            knowledge_base_id=knowledge_base_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            steps=[
                {
                    "step_name": "load_documents",
                    "step_order": 1,
                    "description": "加载文档"
                }
            ]
        )
        
        # 验证记录存在
        retrieved_progress = progress_service.get_progress(task_id)
        assert retrieved_progress is not None
        assert retrieved_progress.task_id == task_id
        
        # 删除记录
        result = progress_service.delete_progress(task_id)
        assert result is True
        
        # 验证记录已删除
        retrieved_progress = progress_service.get_progress(task_id)
        assert retrieved_progress is None
        
        # 测试删除不存在的记录
        result = progress_service.delete_progress("non-existent-task-id")
        assert result is False