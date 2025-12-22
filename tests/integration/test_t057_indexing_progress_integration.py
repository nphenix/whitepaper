# 生成命令: /speckit.implement T057
# 生成时间: 2025-12-21
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
索引构建进度跟踪和状态管理集成测试 (T057)

该模块测试索引构建进度跟踪和状态管理与知识库服务的集成功能。
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.application.services.indexing_progress_service import get_progress_service
from src.application.services.knowledge_base_service import KnowledgeBaseService
from src.domain.indexing.indexing_progress import TaskStatus, TaskType
from src.infrastructure.tasks.indexing_tasks import IndexingTasks


class TestIndexingProgressIntegration:
    """索引构建进度跟踪和状态管理集成测试类"""
    
    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_documents_dir(self, temp_dir):
        """模拟文档目录"""
        docs_dir = Path(temp_dir) / "documents"
        docs_dir.mkdir(parents=True)
        
        # 创建模拟的clean.md文件
        doc_dir = docs_dir / "test_doc"
        doc_dir.mkdir(parents=True)
        extracted_dir = doc_dir / "extracted_dir"
        extracted_dir.mkdir(parents=True)
        
        # 创建clean.md文件
        clean_md = extracted_dir / "clean.md"
        with open(clean_md, "w", encoding="utf-8") as f:
            f.write("""# 测试文档

## 第一章
这是第一章的内容。

## 第二章
这是第二章的内容。

### 2.1 小节
这是2.1小节的内容。
""")
        
        # 创建clean_content_list.json文件
        clean_content_list = extracted_dir / "clean_content_list.json"
        with open(clean_content_list, "w", encoding="utf-8") as f:
            f.write("""[
    {
        "title": "测试文档",
        "content": "测试文档内容",
        "page": 1
    }
]""")
        
        return str(doc_dir)
    
    @pytest.fixture
    def mock_progress_service(self):
        """模拟进度跟踪服务"""
        with patch('src.application.services.indexing_progress_service.get_progress_service') as mock_get_service:
            service = MagicMock()
            mock_get_service.return_value = service
            
            # 设置默认返回值
            service.create_progress.return_value = MagicMock()
            service.update_progress.return_value = MagicMock()
            service.update_step.return_value = MagicMock()
            service.get_progress_summary.return_value = {
                "task_id": "test-task-id",
                "status": "completed",
                "progress_percentage": 100.0,
                "steps": []
            }
            
            yield service
    
    @pytest.fixture
    def knowledge_base_service(self):
        """知识库服务实例"""
        # 使用临时目录作为索引路径
        with tempfile.TemporaryDirectory() as temp_dir:
            kb_service = KnowledgeBaseService(
                vector_collection_name="test_collection",
                bm25_index_path=os.path.join(temp_dir, "test_bm25.pkl"),
                metadata_table_name="test_metadata",
                enable_vector=False,  # 禁用向量索引以简化测试
                enable_bm25=False,     # 禁用BM25索引以简化测试
                enable_metadata=False,  # 禁用元数据索引以简化测试
            )
            yield kb_service
    
    def test_create_knowledge_base_with_progress_tracking(
        self, 
        knowledge_base_service, 
        mock_documents_dir, 
        mock_progress_service
    ):
        """测试创建知识库时的进度跟踪"""
        # 执行创建知识库
        result = knowledge_base_service.create_knowledge_base(
            name="test_kb",
            directories=[mock_documents_dir],
            description="测试知识库",
            task_id="test-task-id"
        )
        
        # 验证结果
        assert result is not None
        assert result["name"] == "test_kb"
        assert result["status"] == "ready"
        
        # 验证进度跟踪服务调用
        mock_progress_service.create_progress.assert_called_once()
        call_args = mock_progress_service.create_progress.call_args[1]
        
        assert call_args["task_id"] == "test-task-id"
        assert call_args["knowledge_base_id"] == str(knowledge_base_service.knowledge_base_id)
        assert call_args["task_type"] == TaskType.CREATE_KNOWLEDGE_BASE
        assert len(call_args["steps"]) == 4  # 加载、解析、分块、构建索引
        
        # 验证进度更新调用
        assert mock_progress_service.update_progress.call_count >= 5  # 开始 + 4个步骤完成 + 任务完成
        
        # 验证步骤更新调用
        assert mock_progress_service.update_step.call_count == 4  # 4个步骤
    
    def test_create_knowledge_base_error_handling(
        self, 
        knowledge_base_service, 
        mock_progress_service
    ):
        """测试创建知识库时的错误处理"""
        # 模拟文档加载错误
        with patch.object(
            knowledge_base_service, 
            '_load_documents', 
            side_effect=Exception("文档加载失败")
        ):
            # 执行创建知识库，应该抛出异常
            with pytest.raises(Exception):
                knowledge_base_service.create_knowledge_base(
                    name="test_kb",
                    directories=["/non/existent/path"],
                    description="测试知识库",
                    task_id="test-task-id"
                )
            
            # 验证进度跟踪服务调用
            mock_progress_service.create_progress.assert_called_once()
            
            # 验证错误状态更新
            update_calls = mock_progress_service.update_progress.call_args_list
            error_update_found = False
            for call in update_calls:
                if "status" in call[1] and call[1]["status"] == TaskStatus.FAILED:
                    error_update_found = True
                    assert "error_message" in call[1]
                    break
            
            assert error_update_found, "应该调用错误状态更新"
    
    def test_indexing_tasks_with_progress_tracking(self, mock_documents_dir, mock_progress_service):
        """测试索引任务与进度跟踪的集成"""
        # 创建任务管理器
        task_manager = IndexingTasks()
        
        # 执行创建知识库任务
        import asyncio
        task_id = asyncio.run(task_manager.create_knowledge_base_task(
            name="test_kb",
            directories=[mock_documents_dir],
            description="测试知识库",
            enable_vector=False,  # 禁用向量索引以简化测试
            enable_bm25=False,     # 禁用BM25索引以简化测试
            enable_metadata=False,  # 禁用元数据索引以简化测试
        ))
        
        # 验证任务ID
        assert task_id is not None
        assert len(task_id) > 0
        
        # 验证任务状态
        task_status = asyncio.run(task_manager.get_task_status(task_id))
        assert task_status is not None
        assert task_status["task_id"] == task_id
        assert task_status["task_type"] == "create_knowledge_base"
        
        # 验证进度跟踪服务调用
        mock_progress_service.create_progress.assert_called()
        
        # 验证任务结果包含进度信息
        if "progress" in task_status:
            assert "task_id" in task_status["progress"]
            assert "status" in task_status["progress"]
    
    def test_progress_service_integration(self, mock_documents_dir):
        """测试进度跟踪服务的完整集成"""
        # 创建进度跟踪服务
        progress_service = get_progress_service()
        
        # 创建进度记录
        progress = progress_service.create_progress(
            task_id="integration-test-task",
            knowledge_base_id="test-kb-id",
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            steps=[
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
        )
        
        # 验证进度记录创建
        assert progress is not None
        assert progress.task_id == "integration-test-task"
        assert progress.task_type == TaskType.CREATE_KNOWLEDGE_BASE
        assert len(progress.steps) == 4
        
        # 开始任务
        progress_service.update_progress(
            task_id="integration-test-task",
            status=TaskStatus.RUNNING
        )
        
        # 更新步骤状态
        progress_service.update_step(
            task_id="integration-test-task",
            step_name="load_documents",
            status="completed"
        )
        
        progress_service.update_step(
            task_id="integration-test-task",
            step_name="parse_documents",
            status="completed"
        )
        
        # 更新进度
        progress_service.update_progress(
            task_id="integration-test-task",
            completed_steps=2,
            documents_count=1,
            nodes_count=10
        )
        
        # 完成任务
        progress_service.update_progress(
            task_id="integration-test-task",
            status=TaskStatus.COMPLETED,
            completed_steps=4,
            chunks_count=20,
            vector_indexed_count=20,
            bm25_indexed_count=20,
            metadata_indexed_count=20
        )
        
        # 获取进度记录
        updated_progress = progress_service.get_progress("integration-test-task")
        
        # 验证更新结果
        assert updated_progress is not None
        assert updated_progress.status == TaskStatus.COMPLETED
        assert updated_progress.completed_steps == 4
        assert updated_progress.progress_percentage == 100.0
        assert updated_progress.documents_count == 1
        assert updated_progress.nodes_count == 10
        assert updated_progress.chunks_count == 20
        assert updated_progress.vector_indexed_count == 20
        assert updated_progress.bm25_indexed_count == 20
        assert updated_progress.metadata_indexed_count == 20
        
        # 验证步骤状态
        load_step = updated_progress.get_step_by_name("load_documents")
        assert load_step is not None
        assert load_step.status.value == "completed"
        
        parse_step = updated_progress.get_step_by_name("parse_documents")
        assert parse_step is not None
        assert parse_step.status.value == "completed"
        
        # 获取进度摘要
        summary = progress_service.get_progress_summary("integration-test-task")
        
        # 验证摘要
        assert summary is not None
        assert summary["task_id"] == "integration-test-task"
        assert summary["status"] == "completed"
        assert summary["progress_percentage"] == 100.0
        assert summary["total_steps"] == 4
        assert summary["completed_steps"] == 4
        assert summary["statistics"]["documents_count"] == 1
        assert summary["statistics"]["nodes_count"] == 10
        assert summary["statistics"]["chunks_count"] == 20
        assert len(summary["steps"]) == 4
        
        # 删除进度记录
        deleted = progress_service.delete_progress("integration-test-task")
        assert deleted is True
        
        # 验证删除
        deleted_progress = progress_service.get_progress("integration-test-task")
        assert deleted_progress is None