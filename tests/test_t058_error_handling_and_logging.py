# 生成命令: T058 - 添加错误处理和日志记录
# 生成时间: 2025-12-21
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
T058 错误处理和日志记录测试

测试知识库服务的错误处理和日志记录功能。
"""

import pytest
import logging
import uuid
from unittest.mock import Mock, patch
from datetime import datetime

from src.application.services.knowledge_base_service import (
    KnowledgeBaseService,
    KnowledgeBaseServiceError,
    DocumentLoadError,
    DocumentParseError,
    IndexBuildError,
    QueryError,
    ResourceError,
    ConfigurationError,
    ConcurrencyError,
    KnowledgeBaseLogger
)
from src.application.services.indexing_progress_service import IndexingProgressService
from src.domain.document.document import Document, DocumentFormat, DocumentStatus
from src.domain.indexing.indexing_progress import IndexingProgress


class TestKnowledgeBaseServiceExceptions:
    """测试知识库服务异常类"""
    
    def test_base_exception(self):
        """测试基础异常"""
        error = KnowledgeBaseServiceError("测试错误", "TEST_ERROR", {"key": "value"})
        assert str(error) == "测试错误"
        assert error.error_code == "TEST_ERROR"
        assert error.details == {"key": "value"}
    
    def test_document_load_error(self):
        """测试文档加载错误"""
        error = DocumentLoadError("加载失败", "/path/to/doc.pdf")
        assert str(error) == "加载失败"
        assert error.error_code == "DOCUMENT_LOAD_ERROR"
        assert error.document_path == "/path/to/doc.pdf"
    
    def test_document_parse_error(self):
        """测试文档解析错误"""
        error = DocumentParseError("解析失败", "doc123")
        assert str(error) == "解析失败"
        assert error.error_code == "DOCUMENT_PARSE_ERROR"
        assert error.document_id == "doc123"
    
    def test_index_build_error(self):
        """测试索引构建错误"""
        error = IndexBuildError("索引构建失败", "vector")
        assert str(error) == "索引构建失败"
        assert error.error_code == "INDEX_BUILD_ERROR"
        assert error.index_type == "vector"
    
    def test_query_error(self):
        """测试查询错误"""
        error = QueryError("查询失败", "test query")
        assert str(error) == "查询失败"
        assert error.error_code == "QUERY_ERROR"
        assert error.query == "test query"
    
    def test_resource_error(self):
        """测试资源错误"""
        error = ResourceError("资源不足", "memory")
        assert str(error) == "资源不足"
        assert error.error_code == "RESOURCE_ERROR"
        assert error.resource_type == "memory"
    
    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("配置错误", "api_key")
        assert str(error) == "配置错误"
        assert error.error_code == "CONFIGURATION_ERROR"
        assert error.config_key == "api_key"
    
    def test_concurrency_error(self):
        """测试并发错误"""
        error = ConcurrencyError("并发冲突", "op123")
        assert str(error) == "并发冲突"
        assert error.error_code == "CONCURRENCY_ERROR"
        assert error.operation_id == "op123"


class TestKnowledgeBaseLogger:
    """测试知识库日志记录器"""
    
    def setup_method(self):
        """设置测试方法"""
        self.logger = KnowledgeBaseLogger()
    
    @patch('src.application.services.knowledge_base_service.logger')
    def test_log_operation_start(self, mock_logger):
        """测试记录操作开始"""
        operation_id = str(uuid.uuid4())
        operation_type = "create_knowledge_base"
        knowledge_base_id = "kb123"
        
        self.logger.log_operation_start(
            operation_id=operation_id,
            operation_type=operation_type,
            knowledge_base_id=knowledge_base_id,
            document_count=10
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "操作开始"
        assert call_args[1]["extra"]["operation_id"] == operation_id
        assert call_args[1]["extra"]["operation_type"] == operation_type
        assert call_args[1]["extra"]["knowledge_base_id"] == knowledge_base_id
        assert call_args[1]["extra"]["status"] == "started"
        assert call_args[1]["extra"]["document_count"] == 10
    
    @patch('src.application.services.knowledge_base_service.logger')
    def test_log_operation_success(self, mock_logger):
        """测试记录操作成功"""
        operation_id = str(uuid.uuid4())
        operation_type = "create_knowledge_base"
        knowledge_base_id = "kb123"
        duration_ms = 1000
        
        self.logger.log_operation_success(
            operation_id=operation_id,
            operation_type=operation_type,
            knowledge_base_id=knowledge_base_id,
            duration_ms=duration_ms,
            document_count=10
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "操作成功"
        assert call_args[1]["extra"]["operation_id"] == operation_id
        assert call_args[1]["extra"]["operation_type"] == operation_type
        assert call_args[1]["extra"]["knowledge_base_id"] == knowledge_base_id
        assert call_args[1]["extra"]["status"] == "success"
        assert call_args[1]["extra"]["duration_ms"] == duration_ms
        assert call_args[1]["extra"]["document_count"] == 10
    
    @patch('src.application.services.knowledge_base_service.logger')
    def test_log_operation_error(self, mock_logger):
        """测试记录操作错误"""
        operation_id = str(uuid.uuid4())
        operation_type = "create_knowledge_base"
        knowledge_base_id = "kb123"
        error = Exception("测试错误")
        duration_ms = 1000
        
        self.logger.log_operation_error(
            operation_id=operation_id,
            operation_type=operation_type,
            knowledge_base_id=knowledge_base_id,
            error=error,
            duration_ms=duration_ms,
            document_count=10
        )
        
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        assert call_args[0][0] == "操作失败: 测试错误"
        assert call_args[1]["extra"]["operation_id"] == operation_id
        assert call_args[1]["extra"]["operation_type"] == operation_type
        assert call_args[1]["extra"]["knowledge_base_id"] == knowledge_base_id
        assert call_args[1]["extra"]["status"] == "error"
        assert call_args[1]["extra"]["error_type"] == "Exception"
        assert call_args[1]["extra"]["error_message"] == "测试错误"
        assert call_args[1]["extra"]["duration_ms"] == duration_ms
        assert call_args[1]["extra"]["document_count"] == 10
        assert call_args[1]["exc_info"] is True
    
    @patch('src.application.services.knowledge_base_service.logger')
    def test_log_performance_metrics(self, mock_logger):
        """测试记录性能指标"""
        operation_type = "create_knowledge_base"
        knowledge_base_id = "kb123"
        metrics = {"document_count": 10, "chunk_count": 50}
        
        self.logger.log_performance_metrics(
            operation_type=operation_type,
            knowledge_base_id=knowledge_base_id,
            metrics=metrics
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "性能指标"
        assert call_args[1]["extra"]["operation_type"] == operation_type
        assert call_args[1]["extra"]["knowledge_base_id"] == knowledge_base_id
        assert call_args[1]["extra"]["metrics"] == metrics
    
    @patch('src.application.services.knowledge_base_service.logger')
    def test_log_progress_update(self, mock_logger):
        """测试记录进度更新"""
        operation_id = str(uuid.uuid4())
        knowledge_base_id = "kb123"
        current = 5
        total = 10
        stage = "loading_documents"
        
        self.logger.log_progress_update(
            operation_id=operation_id,
            knowledge_base_id=knowledge_base_id,
            current=current,
            total=total,
            stage=stage
        )
        
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "进度更新: 5/10"
        assert call_args[1]["extra"]["operation_id"] == operation_id
        assert call_args[1]["extra"]["knowledge_base_id"] == knowledge_base_id
        assert call_args[1]["extra"]["progress_current"] == current
        assert call_args[1]["extra"]["progress_total"] == total
        assert call_args[1]["extra"]["progress_percentage"] == 50.0
        assert call_args[1]["extra"]["stage"] == stage


class TestKnowledgeBaseServiceErrorHandling:
    """测试知识库服务错误处理"""
    
    def setup_method(self):
        """设置测试方法"""
        self.progress_service = Mock(spec=IndexingProgressService)
        self.service = KnowledgeBaseService(self.progress_service)
    
    def test_create_knowledge_base_with_empty_document(self):
        """测试创建知识库时处理空文档"""
        documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content=""  # 空内容
            ),
            Document(
                id=uuid.uuid4(),
                filename="doc2.pdf",
                file_path="/path/to/doc2.pdf",
                file_size=2000,
                format=DocumentFormat.PDF,
                content="有效内容"
            )
        ]
        
        with pytest.raises(DocumentLoadError) as exc_info:
            self.service.create_knowledge_base("kb123", documents)
        
        assert exc_info.value.error_code == "DOCUMENT_LOAD_ERROR"
    
    def test_create_duplicate_knowledge_base(self):
        """测试创建重复知识库"""
        documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content="有效内容"
            )
        ]
        
        # 第一次创建成功
        self.service.create_knowledge_base("kb123", documents)
        
        # 第二次创建应该失败
        with pytest.raises(ConcurrencyError) as exc_info:
            self.service.create_knowledge_base("kb123", documents)
        
        assert exc_info.value.error_code == "CONCURRENCY_ERROR"
    
    def test_query_nonexistent_knowledge_base(self):
        """测试查询不存在的知识库"""
        with pytest.raises(ResourceError) as exc_info:
            self.service.query("nonexistent", "查询内容")
        
        assert exc_info.value.error_code == "RESOURCE_ERROR"
        assert exc_info.value.resource_type == "knowledge_base"
    
    def test_update_nonexistent_knowledge_base(self):
        """测试更新不存在的知识库"""
        documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content="内容"
            )
        ]
        
        with pytest.raises(ResourceError) as exc_info:
            self.service.update_knowledge_base("nonexistent", documents)
        
        assert exc_info.value.error_code == "RESOURCE_ERROR"
        assert exc_info.value.resource_type == "knowledge_base"
    
    def test_delete_nonexistent_knowledge_base(self):
        """测试删除不存在的知识库"""
        with pytest.raises(ResourceError) as exc_info:
            self.service.delete_knowledge_base("nonexistent")
        
        assert exc_info.value.error_code == "RESOURCE_ERROR"
        assert exc_info.value.resource_type == "knowledge_base"


class TestKnowledgeBaseServiceLogging:
    """测试知识库服务日志记录"""
    
    def setup_method(self):
        """设置测试方法"""
        self.progress_service = Mock(spec=IndexingProgressService)
        self.service = KnowledgeBaseService(self.progress_service)
    
    @patch('src.application.services.knowledge_base_service.logger')
    def test_create_knowledge_base_logging(self, mock_logger):
        """测试创建知识库的日志记录"""
        documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content="内容"
            )
        ]
        
        # 模拟日志记录
        mock_logger.info.return_value = None
        mock_logger.error.return_value = None
        
        result = self.service.create_knowledge_base("kb123", documents)
        
        # 验证日志被调用
        assert mock_logger.info.called or mock_logger.error.called
        
        # 验证返回结果
        assert result["id"] == "kb123"
        assert result["document_count"] == 1
    
    @patch('src.application.services.knowledge_base_service.logger')
    def test_query_logging(self, mock_logger):
        """测试查询的日志记录"""
        documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content="内容"
            )
        ]
        
        # 先创建知识库
        self.service.create_knowledge_base("kb123", documents)
        
        # 重置mock
        mock_logger.reset_mock()
        
        # 执行查询
        results = self.service.query("kb123", "查询内容")
        
        # 验证日志被调用
        assert mock_logger.info.called
        
        # 验证查询结果
        assert len(results) > 0
    
    @patch('src.application.services.knowledge_base_service.logger')
    def test_error_logging(self, mock_logger):
        """测试错误日志记录"""
        documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content=""  # 空内容会导致错误
            )
        ]
        
        # 重置mock
        mock_logger.reset_mock()
        
        # 尝试创建知识库（应该失败）
        try:
            self.service.create_knowledge_base("kb123", documents)
        except DocumentLoadError:
            pass  # 预期的错误
        
        # 验证错误日志被调用
        assert mock_logger.error.called


class TestKnowledgeBaseServiceIntegration:
    """测试知识库服务集成功能"""
    
    def setup_method(self):
        """设置测试方法"""
        self.progress_service = Mock(spec=IndexingProgressService)
        self.service = KnowledgeBaseService(self.progress_service)
    
    def test_full_workflow(self):
        """测试完整工作流程"""
        documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content="这是第一个文档的内容"
            ),
            Document(
                id=uuid.uuid4(),
                filename="doc2.pdf",
                file_path="/path/to/doc2.pdf",
                file_size=2000,
                format=DocumentFormat.PDF,
                content="这是第二个文档的内容"
            )
        ]
        
        # 创建知识库
        result = self.service.create_knowledge_base("kb123", documents)
        assert result["id"] == "kb123"
        assert result["document_count"] == 2
        assert result["chunk_count"] > 0
        
        # 查询知识库
        results = self.service.query("kb123", "文档")
        assert len(results) > 0
        assert all("content" in result for result in results)
        
        # 更新知识库
        new_documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc3.pdf",
                file_path="/path/to/doc3.pdf",
                file_size=1500,
                format=DocumentFormat.PDF,
                content="新文档内容"
            )
        ]
        update_result = self.service.update_knowledge_base("kb123", new_documents)
        assert update_result["document_count"] == 3
        
        # 获取知识库信息
        info = self.service.get_knowledge_base_info("kb123")
        assert info is not None
        assert info["id"] == "kb123"
        assert info["document_count"] == 3
        
        # 列出所有知识库
        kb_list = self.service.list_knowledge_bases()
        assert len(kb_list) == 1
        assert kb_list[0]["id"] == "kb123"
        
        # 删除知识库
        delete_result = self.service.delete_knowledge_base("kb123")
        assert delete_result is True
        
        # 验证知识库已删除
        info = self.service.get_knowledge_base_info("kb123")
        assert info is None
    
    def test_error_recovery(self):
        """测试错误恢复"""
        documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content="有效内容"
            ),
            Document(
                id=uuid.uuid4(),
                filename="doc2.pdf",
                file_path="/path/to/doc2.pdf",
                file_size=2000,
                format=DocumentFormat.PDF,
                content=""  # 空文档会导致错误
            )
        ]
        
        # 尝试创建知识库（应该失败）
        with pytest.raises(DocumentLoadError):
            self.service.create_knowledge_base("kb123", documents)
        
        # 验证知识库未创建
        info = self.service.get_knowledge_base_info("kb123")
        assert info is None
        
        # 使用有效文档创建知识库
        valid_documents = [
            Document(
                id=uuid.uuid4(),
                filename="doc1.pdf",
                file_path="/path/to/doc1.pdf",
                file_size=1000,
                format=DocumentFormat.PDF,
                content="有效内容"
            )
        ]
        result = self.service.create_knowledge_base("kb123", valid_documents)
        assert result["id"] == "kb123"
        
        # 验证知识库已创建
        info = self.service.get_knowledge_base_info("kb123")
        assert info is not None


if __name__ == "__main__":
    pytest.main([__file__])