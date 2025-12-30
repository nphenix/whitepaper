"""
T208 前端集成接口测试

测试前端集成接口的各项功能，包括行业选择选项、数据库选择选项等。

生成命令: /speckit.implement T208
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from src.interfaces.api.app import app


class TestFrontendIntegration:
    """前端集成接口测试类"""

    def setup_method(self):
        """测试方法前置设置"""
        self.client = TestClient(app)

    @patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service")
    def test_get_industry_selection_options(self, mock_service):
        """测试获取行业选择选项接口"""
        # 模拟服务返回数据
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_industries.return_value = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": "ENERGY",
                "description": "储能相关行业",
                "is_active": True,
                "sort_order": 1,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {},
            }
        ]

        # 发送请求
        response = self.client.get("/api/v1/frontend/industries/selection-options")

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "储能行业"
        assert data[0]["code"] == "ENERGY_STORAGE"
        assert data[0]["category"] == "ENERGY"

    @patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service")
    def test_get_storage_industry_options(self, mock_service):
        """测试获取储能行业选项接口"""
        # 模拟服务返回数据
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_storage_industries.return_value = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440001",
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": "ENERGY",
                "description": "储能相关行业",
                "is_active": True,
                "sort_order": 1,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {},
            }
        ]

        # 发送请求
        response = self.client.get("/api/v1/frontend/industries/storage-options")

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "储能行业"
        assert data[0]["code"] == "ENERGY_STORAGE"

    @patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service")
    def test_get_database_selection_options(self, mock_service):
        """测试获取数据库选择选项接口"""
        # 模拟服务返回数据
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_industry_databases.return_value = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "name": "储能行业知识库",
                "code": "ENERGY_STORAGE_KB",
                "industry_id": "550e8400-e29b-41d4-a716-446655440000",
                "database_type": "KNOWLEDGE_BASE",
                "data_source": "PLATFORM_BUILTIN",
                "description": "储能行业知识库",
                "is_active": True,
                "is_public": True,
                "sort_order": 1,
                "documents_count": 100,
                "size_mb": 50.5,
                "last_updated": "2023-01-01T00:00:00",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {},
            }
        ]

        # 发送请求
        response = self.client.get(
            "/api/v1/frontend/databases/selection-options/550e8400-e29b-41d4-a716-446655440000"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "储能行业知识库"
        assert data[0]["code"] == "ENERGY_STORAGE_KB"
        assert data[0]["database_type"] == "KNOWLEDGE_BASE"

    @patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service")
    def test_get_knowledge_base_database_options(self, mock_service):
        """测试获取知识库类型数据库选项接口"""
        # 模拟服务返回数据
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_knowledge_base_databases.return_value = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440003",
                "name": "储能行业知识库",
                "code": "ENERGY_STORAGE_KB",
                "industry_id": "550e8400-e29b-41d4-a716-446655440000",
                "database_type": "KNOWLEDGE_BASE",
                "data_source": "PLATFORM_BUILTIN",
                "description": "储能行业知识库",
                "is_active": True,
                "is_public": True,
                "sort_order": 1,
                "documents_count": 100,
                "size_mb": 50.5,
                "last_updated": "2023-01-01T00:00:00",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {},
            }
        ]

        # 发送请求
        response = self.client.get(
            "/api/v1/frontend/databases/knowledge-base-options/550e8400-e29b-41d4-a716-446655440000"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "储能行业知识库"
        assert data[0]["database_type"] == "KNOWLEDGE_BASE"

    @patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service")
    def test_get_platform_builtin_database_options(self, mock_service):
        """测试获取平台内置数据库选项接口"""
        # 模拟服务返回数据
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_platform_builtin_databases.return_value = [
            {
                "id": "550e8400-e29b-41d4-a716-446655440004",
                "name": "储能行业市场数据库",
                "code": "ENERGY_STORAGE_MARKET",
                "industry_id": "550e8400-e29b-41d4-a716-446655440000",
                "database_type": "MARKET_DATA",
                "data_source": "PLATFORM_BUILTIN",
                "description": "储能行业市场数据库",
                "is_active": True,
                "is_public": True,
                "sort_order": 2,
                "documents_count": 200,
                "size_mb": 75.2,
                "last_updated": "2023-01-01T00:00:00",
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {},
            }
        ]

        # 发送请求
        response = self.client.get(
            "/api/v1/frontend/databases/platform-builtin-options/550e8400-e29b-41d4-a716-446655440000"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "储能行业市场数据库"
        assert data[0]["database_type"] == "MARKET_DATA"

    @patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service")
    def test_quick_save_selection(self, mock_service):
        """测试快速保存行业和数据库选择接口"""
        # 模拟服务返回数据
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.save_industry_selection.return_value = {
            "selection": {
                "id": "550e8400-e29b-41d4-a716-446655440005",
                "session_id": "test-session-id",
                "industry_id": "550e8400-e29b-41d4-a716-446655440000",
                "database_ids": '["550e8400-e29b-41d4-a716-446655440002"]',
                "selection_name": "测试选择",
                "description": None,
                "is_active": True,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {},
            },
            "industry": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
            },
            "databases": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "name": "储能行业知识库",
                    "code": "ENERGY_STORAGE_KB",
                }
            ],
        }

        # 发送请求
        response = self.client.get(
            "/api/v1/frontend/selection/quick-save/550e8400-e29b-41d4-a716-446655440000"
            "?database_ids=550e8400-e29b-41d4-a716-446655440002"
            "&session_id=test-session-id"
            "&selection_name=测试选择"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "行业和数据库选择保存成功"
        assert data["selection_id"] == "550e8400-e29b-41d4-a716-446655440005"
        assert data["session_id"] == "test-session-id"
        assert data["industry_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert data["database_ids"] == ["550e8400-e29b-41d4-a716-446655440002"]
        assert data["selection_name"] == "测试选择"

    @patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service")
    def test_quick_get_selection(self, mock_service):
        """测试快速获取行业选择详情接口"""
        # 模拟服务返回数据
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.get_industry_selection.return_value = {
            "selection": {
                "id": "550e8400-e29b-41d4-a716-446655440005",
                "session_id": "test-session-id",
                "industry_id": "550e8400-e29b-41d4-a716-446655440000",
                "database_ids": '["550e8400-e29b-41d4-a716-446655440002"]',
                "selection_name": "测试选择",
                "description": None,
                "is_active": True,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {},
            },
            "industry": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
            },
            "databases": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "name": "储能行业知识库",
                    "code": "ENERGY_STORAGE_KB",
                }
            ],
        }

        # 发送请求
        response = self.client.get(
            "/api/v1/frontend/selection/quick-get/550e8400-e29b-41d4-a716-446655440005"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["selection_id"] == "550e8400-e29b-41d4-a716-446655440005"
        assert data["session_id"] == "test-session-id"
        assert data["industry_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert data["industry_name"] == "储能行业"
        assert data["industry_code"] == "ENERGY_STORAGE"
        assert data["database_ids"] == ["550e8400-e29b-41d4-a716-446655440002"]
        assert data["database_names"] == ["储能行业知识库"]
        assert data["database_codes"] == ["ENERGY_STORAGE_KB"]
        assert data["selection_name"] == "测试选择"

    def test_get_industry_selection_options_with_filter(self):
        """测试带过滤条件的获取行业选择选项接口"""
        with patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service") as mock_service:
            # 模拟服务返回数据
            mock_service_instance = Mock()
            mock_service.return_value = mock_service_instance
            mock_service_instance.get_industries.return_value = []

            # 发送带过滤条件的请求
            response = self.client.get(
                "/api/v1/frontend/industries/selection-options?category=ENERGY"
            )

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 0

            # 验证服务调用参数
            mock_service_instance.get_industries.assert_called_once_with(
                category="ENERGY",
                is_active=True,
                sort_by="sort_order",
                sort_order="asc",
            )

    def test_get_database_selection_options_with_filter(self):
        """测试带过滤条件的获取数据库选择选项接口"""
        with patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service") as mock_service:
            # 模拟服务返回数据
            mock_service_instance = Mock()
            mock_service.return_value = mock_service_instance
            mock_service_instance.get_industry_databases.return_value = []

            # 发送带过滤条件的请求
            response = self.client.get(
                "/api/v1/frontend/databases/selection-options/550e8400-e29b-41d4-a716-446655440000"
                "?database_type=KNOWLEDGE_BASE&data_source=PLATFORM_BUILTIN"
            )

            # 验证响应
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 0

            # 验证服务调用参数
            mock_service_instance.get_industry_databases.assert_called_once_with(
                industry_id="550e8400-e29b-41d4-a716-446655440000",
                database_type="KNOWLEDGE_BASE",
                data_source="PLATFORM_BUILTIN",
                is_active=True,
                is_public=True,
                sort_by="sort_order",
                sort_order="asc",
            )

    @patch("src.interfaces.api.routes.frontend_integration.get_industry_selection_service")
    def test_quick_save_selection_without_optional_params(self, mock_service):
        """测试不带可选参数的快速保存行业和数据库选择接口"""
        # 模拟服务返回数据 - 使用固定的session_id
        mock_service_instance = Mock()
        mock_service.return_value = mock_service_instance
        mock_service_instance.save_industry_selection.return_value = {
            "selection": {
                "id": "550e8400-e29b-41d4-a716-446655440006",
                "session_id": "auto-generated-session-id",
                "industry_id": "550e8400-e29b-41d4-a716-446655440000",
                "database_ids": '["550e8400-e29b-41d4-a716-446655440002"]',
                "selection_name": None,
                "description": None,
                "is_active": True,
                "created_at": "2023-01-01T00:00:00",
                "updated_at": "2023-01-01T00:00:00",
                "metadata": {},
            },
            "industry": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
            },
            "databases": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "name": "储能行业知识库",
                    "code": "ENERGY_STORAGE_KB",
                }
            ],
        }

        # 发送请求（不带可选参数）
        response = self.client.get(
            "/api/v1/frontend/selection/quick-save/550e8400-e29b-41d4-a716-446655440000"
            "?database_ids=550e8400-e29b-41d4-a716-446655440002"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "行业和数据库选择保存成功"
        assert data["selection_id"] == "550e8400-e29b-41d4-a716-446655440006"
        assert data["industry_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert data["database_ids"] == ["550e8400-e29b-41d4-a716-446655440002"]
        assert data["selection_name"] is None

        # 验证服务调用参数
        mock_service_instance.save_industry_selection.assert_called_once()
        call_args = mock_service_instance.save_industry_selection.call_args[1]
        assert call_args["industry_id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert call_args["database_ids"] == ["550e8400-e29b-41d4-a716-446655440002"]
        assert call_args["selection_name"] is None
        assert call_args["description"] is None
        assert "session_id" in call_args  # 应该自动生成session_id