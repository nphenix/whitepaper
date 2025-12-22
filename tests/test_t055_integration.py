"""
T055 知识库API集成测试

验证知识库API的实际功能。

生成命令: /speckit.implement T055
生成时间: 2025-12-21
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from src.interfaces.api.app import app


class TestKnowledgeBaseIntegration:
    """知识库API集成测试类"""

    def setup_method(self):
        """测试前设置"""
        self.client = TestClient(app)

    def test_knowledge_base_api_endpoints(self):
        """测试知识库API端点是否可访问"""
        # 测试列出知识库端点
        response = self.client.get("/api/v1/knowledge-base/list")
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
        assert "data" in data

    def test_knowledge_base_create_endpoint(self):
        """测试知识库创建端点"""
        # 检查data/source目录是否存在
        source_dir = Path("data/source")
        if not source_dir.exists():
            pytest.skip("data/source目录不存在，跳过创建测试")
        
        # 准备请求数据
        request_data = {
            "name": "Integration Test KB",
            "directories": ["data/source"],
            "description": "Integration test knowledge base",
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
        assert "knowledge_base" in data
        assert "statistics" in data
        assert "message" in data
        assert data["knowledge_base"]["name"] == "Integration Test KB"

    def test_knowledge_base_error_handling(self):
        """测试知识库API错误处理"""
        # 测试不存在的知识库
        response = self.client.get("/api/v1/knowledge-base/nonexistent-kb/status")
        assert response.status_code == 404
        
        # 测试无效的创建请求
        response = self.client.post("/api/v1/knowledge-base/create", json={})
        assert response.status_code == 422  # 验证错误
        
        # 测试不存在的目录
        request_data = {
            "name": "Test KB",
            "directories": ["nonexistent/directory"],
            "description": "Test knowledge base",
        }
        response = self.client.post("/api/v1/knowledge-base/create", json=request_data)
        assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__])