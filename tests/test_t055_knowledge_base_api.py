"""
知识库API路由测试

测试T055实现的知识库管理API路由功能。

生成命令: /speckit.implement T055
生成时间: 2025-12-21
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from src.interfaces.api.app import app


class TestKnowledgeBaseAPI:
    """知识库API测试类"""

    def setup_method(self):
        """测试前设置"""
        self.client = TestClient(app)
        
        # 模拟知识库服务
        self.mock_service = Mock()
        
        # 模拟知识库状态
        self.mock_status = {
            "knowledge_base_id": "test-kb-id",
            "status": "ready",
            "processing_status": {},
            "progress_info": {},
            "indexes": {
                "vector": {"total_nodes": 100},
                "bm25": {"total_docs": 10},
                "metadata": {"total_records": 100},
            },
            "config": {
                "chunking": {
                    "chunk_size": 1024,
                    "chunk_overlap": 200,
                    "split_by_section": True,
                    "split_by_paragraph": True,
                },
                "hybrid_retriever": {
                    "enable_vector": True,
                    "enable_bm25": True,
                    "enable_metadata": True,
                    "enable_graph": False,
                    "fusion_strategy": "rrf",
                    "default_top_k": 10,
                },
            },
        }

    @patch('src.interfaces.api.routes.knowledge_base._knowledge_base_services', {})
    def test_create_knowledge_base_success(self):
        """测试成功创建知识库"""
        # 模拟知识库服务
        mock_service = Mock()
        mock_service.create_knowledge_base.return_value = {
            "knowledge_base_id": "test-kb-id",
            "name": "Test KB",
            "description": "Test knowledge base",
            "status": "ready",
            "created_at": "2025-12-21T00:00:00",
            "updated_at": "2025-12-21T00:00:00",
            "statistics": {
                "documents_count": 10,
                "nodes_count": 100,
                "chunks_count": 200,
                "directories_count": 1,
            },
        }
        mock_service.get_status.return_value = self.mock_status
        
        # 设置模拟
        with patch('src.interfaces.api.routes.knowledge_base._knowledge_base_services', {"test-kb-id": mock_service}):
            # 准备请求数据
            request_data = {
                "name": "Test KB",
                "directories": ["data/source"],  # 使用存在的目录
                "description": "Test knowledge base",
                "enable_vector": True,
                "enable_bm25": True,
                "enable_metadata": True,
                "chunk_size": 1024,
                "chunk_overlap": 200,
                "split_by_section": True,
                "split_by_paragraph": True,
            }
            
            # 发送请求
            response = self.client.post("/api/v1/knowledge-base/create", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["knowledge_base"]["name"] == "Test KB"
            assert data["knowledge_base"]["status"] == "ready"
            assert data["message"] == "知识库创建成功"

    def test_create_knowledge_base_invalid_directory(self):
        """测试创建知识库时目录不存在"""
        # 准备请求数据
        request_data = {
            "name": "Test KB",
            "directories": ["nonexistent/directory"],
            "description": "Test knowledge base",
        }
        
        # 发送请求
        response = self.client.post("/api/v1/knowledge-base/create", json=request_data)
        
        # 验证响应
        assert response.status_code == 400
        data = response.json()
        assert "目录不存在" in str(data)

    @patch('src.interfaces.api.routes.knowledge_base._knowledge_base_services', {"test-kb-id": Mock()})
    def test_update_knowledge_base_success(self):
        """测试成功更新知识库"""
        # 模拟知识库服务
        mock_service = Mock()
        mock_service.update_knowledge_base.return_value = {
            "knowledge_base_id": "test-kb-id",
            "status": "ready",
            "updated_at": "2025-12-21T00:00:00",
            "statistics": {
                "new_documents_count": 5,
                "new_nodes_count": 50,
                "new_chunks_count": 100,
            },
        }
        
        # 替换缓存中的mock服务
        with patch('src.interfaces.api.routes.knowledge_base._knowledge_base_services', {"test-kb-id": mock_service}):
            # 准备请求数据
            request_data = {
                "directories": ["data/source"],  # 使用存在的目录
                "show_progress": False,
            }
            
            # 发送请求
            response = self.client.put("/api/v1/knowledge-base/test-kb-id/update", json=request_data)
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["knowledge_base_id"] == "test-kb-id"
            assert data["status"] == "ready"
            assert data["message"] == "知识库更新成功"

    def test_update_knowledge_base_not_found(self):
        """测试更新不存在的知识库"""
        
        # 准备请求数据
        request_data = {
            "directories": ["data/cleaned/documents/test2"],
        }
        
        # 发送请求
        response = self.client.put("/api/v1/knowledge-base/nonexistent-kb/update", json=request_data)
        
        # 验证响应
        assert response.status_code == 404

    @patch('src.interfaces.api.routes.knowledge_base.get_knowledge_base_service')
    def test_delete_knowledge_base_success(self, mock_get_service):
        """测试成功删除知识库"""
        # 模拟知识库服务
        mock_service = Mock()
        mock_service.delete_knowledge_base.return_value = {
            "knowledge_base_id": "test-kb-id",
            "status": "deleted",
            "deleted_at": "2025-12-21T00:00:00",
        }
        mock_get_service.return_value = mock_service
        
        # 发送请求
        response = self.client.delete("/api/v1/knowledge-base/test-kb-id/delete")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["knowledge_base_id"] == "test-kb-id"
        assert data["status"] == "deleted"
        assert data["message"] == "知识库删除成功"

    @patch('src.interfaces.api.routes.knowledge_base.get_knowledge_base_service')
    def test_query_knowledge_base_success(self, mock_get_service):
        """测试成功查询知识库"""
        # 模拟知识库服务
        mock_service = Mock()
        
        # 模拟查询结果
        mock_node = Mock()
        mock_node.node_id = "node-1"
        mock_node.text = "测试内容"
        mock_node.metadata = {"source": "test.pdf"}
        
        mock_result = Mock()
        mock_result.node = mock_node
        mock_result.score = 0.8
        
        mock_service.query.return_value = [mock_result]
        mock_get_service.return_value = mock_service
        
        # 准备请求数据
        request_data = {
            "query": "测试查询",
            "top_k": 10,
            "use_hybrid": True,
            "use_structured": False,
        }
        
        # 发送请求
        response = self.client.post("/api/v1/knowledge-base/test-kb-id/query", json=request_data)
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["knowledge_base_id"] == "test-kb-id"
        assert data["query"] == "测试查询"
        assert len(data["results"]) == 1
        assert data["results"][0]["content"] == "测试内容"
        assert data["message"] == "查询成功"

    @patch('src.interfaces.api.routes.knowledge_base.get_knowledge_base_service')
    def test_get_knowledge_base_status_success(self, mock_get_service):
        """测试成功获取知识库状态"""
        # 模拟知识库服务
        mock_service = Mock()
        mock_service.get_status.return_value = self.mock_status
        mock_get_service.return_value = mock_service
        
        # 发送请求
        response = self.client.get("/api/v1/knowledge-base/test-kb-id/status")
        
        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["knowledge_base_id"] == "test-kb-id"
        assert data["status"] == "ready"
        assert data["config"]["chunking"]["chunk_size"] == 1024
        assert data["config"]["hybrid_retriever"]["enable_vector"] is True

    @patch('src.interfaces.api.routes.knowledge_base._knowledge_base_services', {})
    def test_list_knowledge_bases_success(self):
        """测试成功列出所有知识库"""
        # 模拟知识库服务
        mock_service1 = Mock()
        mock_service1.get_status.return_value = self.mock_status
        
        mock_service2 = Mock()
        mock_status2 = self.mock_status.copy()
        mock_status2["knowledge_base_id"] = "test-kb-id-2"
        mock_service2.get_status.return_value = mock_status2
        
        # 设置模拟
        with patch('src.interfaces.api.routes.knowledge_base._knowledge_base_services', {
            "test-kb-id": mock_service1,
            "test-kb-id-2": mock_service2
        }):
            # 发送请求
            response = self.client.get("/api/v1/knowledge-base/list")
            
            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "获取知识库列表成功"
            assert data["data"]["total"] == 2
            assert len(data["data"]["knowledge_bases"]) == 2

    def test_create_knowledge_base_validation_error(self):
        """测试创建知识库时验证错误"""
        # 准备请求数据 - 缺少必需字段
        request_data = {
            "description": "Test knowledge base without name",
        }
        
        # 发送请求
        response = self.client.post("/api/v1/knowledge-base/create", json=request_data)
        
        # 验证响应
        assert response.status_code == 422  # 验证错误

    def test_query_knowledge_base_empty_query(self):
        """测试查询知识库时查询文本为空"""
        # 准备请求数据
        request_data = {
            "query": "",
            "top_k": 10,
        }
        
        # 发送请求
        response = self.client.post("/api/v1/knowledge-base/test-kb-id/query", json=request_data)
        
        # 验证响应
        assert response.status_code == 422  # 验证错误


if __name__ == "__main__":
    pytest.main([__file__])