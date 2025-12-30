"""
行业选择API路由测试

测试T206实现的行业选择API路由功能。

生成命令: /speckit.implement T206
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import datetime, UTC
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.domain.agent.industry import IndustryCategory
from src.domain.knowledge_base.industry_database import DatabaseType, DataSource
from src.interfaces.api.app import app
from src.infrastructure.storage.sqlite.connection import get_connection_manager
from src.shared.config.settings import get_config


class TestIndustrySelectionAPI:
    """行业选择API测试类"""

    def setup_method(self):
        """测试前设置"""
        self.client = TestClient(app)
        
        # 获取测试数据
        self.test_industry_id = None
        self.test_database_id = None
        self.test_selection_id = None
        
        # 从数据库获取测试数据
        self._load_test_data()

    def _load_test_data(self):
        """从数据库加载测试数据"""
        try:
            # 获取连接管理器
            connection_manager = get_connection_manager()
            
            with connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取行业数据
                cursor.execute("SELECT id FROM industries WHERE code = 'ENERGY_STORAGE' LIMIT 1")
                result = cursor.fetchone()
                if result:
                    self.test_industry_id = result[0]
                    # 构造 mock 行业数据，供后续 patch 使用
                    self.mock_industry = {
                        "id": self.test_industry_id,
                        "name": "储能行业",
                        "code": "ENERGY_STORAGE",
                        "category": IndustryCategory.ENERGY.value,
                        "description": "储能产业相关",
                        "is_active": True,
                        "sort_order": 1,
                        "created_at": datetime.now(UTC).isoformat(),
                        "updated_at": datetime.now(UTC).isoformat(),
                        "metadata": {},
                    }
                
                # 获取数据库数据
                cursor.execute("SELECT id FROM industry_databases WHERE code = 'ENERGY_STORAGE_KB' LIMIT 1")
                result = cursor.fetchone()
                if result:
                    self.test_database_id = result[0]
                    # 构造 mock 数据库数据
                    self.mock_database = {
                        "id": self.test_database_id,
                        "name": "储能行业知识库",
                        "code": "ENERGY_STORAGE_KB",
                        "industry_id": self.test_industry_id,
                        "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                        "data_source": DataSource.PLATFORM_BUILTIN.value,
                        "description": "储能行业知识库",
                        "is_active": True,
                        "is_public": True,
                        "sort_order": 1,
                        "documents_count": 100,
                        "size_mb": 50.5,
                        "last_updated": datetime.now(UTC).isoformat(),
                        "created_at": datetime.now(UTC).isoformat(),
                        "updated_at": datetime.now(UTC).isoformat(),
                        "metadata": {},
                    }
                
                # 获取选择记录数据
                cursor.execute("SELECT id FROM industry_selections LIMIT 1")
                result = cursor.fetchone()
                if result:
                    self.test_selection_id = result[0]
                    # 构造 mock 选择数据
                    import json
                    self.mock_selection = {
                        "id": self.test_selection_id,
                        "session_id": str(uuid.uuid4()),
                        "industry_id": self.test_industry_id,
                        "database_ids": json.dumps([self.test_database_id]) if self.test_database_id else "[]",
                        "selection_name": "测试选择",
                        "description": "测试描述",
                        "is_active": True,
                        "created_at": datetime.now(UTC).isoformat(),
                        "updated_at": datetime.now(UTC).isoformat(),
                        "metadata": {},
                    }
                    
                # 如果缺少关键数据，创建模拟数据以保证测试依赖的属性存在
                if not (self.test_industry_id and self.test_database_id and self.test_selection_id):
                    self._create_mock_data()

        except Exception as e:
            print(f"加载测试数据失败: {e}")
            # 如果数据库中没有数据，使用模拟数据
            self._create_mock_data()

    def _create_mock_data(self):
        """创建模拟数据（当数据库中没有数据时使用）"""
        # 模拟行业数据
        self.test_industry_id = str(uuid.uuid4())
        self.mock_industry = {
            "id": self.test_industry_id,
            "name": "储能行业",
            "code": "ENERGY_STORAGE",
            "category": IndustryCategory.ENERGY.value,
            "description": "储能产业相关",
            "is_active": True,
            "sort_order": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "metadata": {},
        }

        # 模拟数据库数据
        self.test_database_id = str(uuid.uuid4())
        self.mock_database = {
            "id": self.test_database_id,
            "name": "储能行业知识库",
            "code": "ENERGY_STORAGE_KB",
            "industry_id": self.test_industry_id,
            "database_type": DatabaseType.KNOWLEDGE_BASE.value,
            "data_source": DataSource.PLATFORM_BUILTIN.value,
            "description": "储能行业知识库",
            "is_active": True,
            "is_public": True,
            "sort_order": 1,
            "documents_count": 100,
            "size_mb": 50.5,
            "last_updated": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "metadata": {},
        }

        # 模拟选择数据
        import json
        self.test_selection_id = str(uuid.uuid4())
        self.mock_selection = {
            "id": self.test_selection_id,
            "session_id": str(uuid.uuid4()),
            "industry_id": self.test_industry_id,
            "database_ids": json.dumps([self.test_database_id]),
            "selection_name": "测试选择",
            "description": "测试描述",
            "is_active": True,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "metadata": "{}",
        }


    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_list_industries_success(self, mock_get_service):
        """测试成功获取行业列表"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industries.return_value = [
            {
                "id": self.test_industry_id,
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": IndustryCategory.ENERGY.value,
                "description": "储能产业相关",
                "is_active": True,
                "sort_order": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            }
        ]
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.post(
            "/api/v1/industry-selection/industries/list",
            json={
                "category": IndustryCategory.ENERGY.value,
                "is_active": True,
                "sort_by": "sort_order",
                "sort_order": "asc",
                "limit": 50,
                "offset": 0,
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["industries"]) == 1
        assert data["industries"][0]["name"] == "储能行业"
        assert data["total"] == 1
        assert data["has_more"] is False

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_list_industries_with_filters(self, mock_get_service):
        """测试带过滤条件的行业列表"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industries.return_value = [
            {
                "id": self.test_industry_id,
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": IndustryCategory.ENERGY.value,
                "description": "储能产业相关",
                "is_active": True,
                "sort_order": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            }
        ]
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.post(
            "/api/v1/industry-selection/industries/list",
            json={
                "category": IndustryCategory.ENERGY.value,
                "is_active": True,
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["industries"]) == 1

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_industry_detail_success(self, mock_get_service):
        """测试成功获取行业详情"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industry_by_id.return_value = {
            "id": self.test_industry_id,
            "name": "储能行业",
            "code": "ENERGY_STORAGE",
            "category": IndustryCategory.ENERGY.value,
            "description": "储能产业相关",
            "is_active": True,
            "sort_order": 1,
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "metadata": {},
        }
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.get(
            f"/api/v1/industry-selection/industries/{self.test_industry_id}"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "储能行业"
        assert data["code"] == "ENERGY_STORAGE"

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_industry_detail_not_found(self, mock_get_service):
        """测试获取不存在的行业详情"""
        # 模拟服务
        mock_service = Mock()
        from src.shared.exceptions.base_exceptions import ResourceNotFoundError
        mock_service.get_industry_by_id.side_effect = ResourceNotFoundError(
            "行业不存在", resource_type="Industry", resource_id=str(uuid.uuid4())
        )
        mock_get_service.return_value = mock_service

        # 发送请求 - 使用一个不存在的UUID
        response = self.client.get(
            f"/api/v1/industry-selection/industries/{str(uuid.uuid4())}"
        )

        # 验证响应
        assert response.status_code == 500

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_list_databases_success(self, mock_get_service):
        """测试成功获取数据库列表"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industry_databases.return_value = [
            {
                "id": self.test_database_id,
                "name": "储能行业知识库",
                "code": "ENERGY_STORAGE_KB",
                "industry_id": self.test_industry_id,
                "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                "data_source": DataSource.PLATFORM_BUILTIN.value,
                "description": "储能行业知识库",
                "is_active": True,
                "is_public": True,
                "sort_order": 1,
                "documents_count": 100,
                "size_mb": 50.5,
                "last_updated": datetime.now(UTC).isoformat(),
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            }
        ]
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.post(
            "/api/v1/industry-selection/databases/list",
            json={
                "industry_id": self.test_industry_id,
                "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                "is_active": True,
                "limit": 50,
                "offset": 0,
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["databases"]) == 1
        assert data["databases"][0]["name"] == "储能行业知识库"
        assert data["total"] == 1

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_list_databases_with_filters(self, mock_get_service):
        """测试带过滤条件的数据库列表"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industry_databases.return_value = [
            {
                "id": self.test_database_id,
                "name": "储能行业知识库",
                "code": "ENERGY_STORAGE_KB",
                "industry_id": self.test_industry_id,
                "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                "data_source": DataSource.PLATFORM_BUILTIN.value,
                "description": "储能行业知识库",
                "is_active": True,
                "is_public": True,
                "sort_order": 1,
                "documents_count": 100,
                "size_mb": 50.5,
                "last_updated": datetime.now(UTC).isoformat(),
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            }
        ]
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.post(
            "/api/v1/industry-selection/databases/list",
            json={
                "industry_id": self.test_industry_id,
                "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                "data_source": DataSource.PLATFORM_BUILTIN.value,
                "is_public": True,
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["databases"]) == 1

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_database_detail_success(self, mock_get_service):
        """测试成功获取数据库详情"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_database_by_id.return_value = {
            "id": self.test_database_id,
            "name": "储能行业知识库",
            "code": "ENERGY_STORAGE_KB",
            "industry_id": self.test_industry_id,
            "database_type": DatabaseType.KNOWLEDGE_BASE.value,
            "data_source": DataSource.PLATFORM_BUILTIN.value,
            "description": "储能行业知识库",
            "is_active": True,
            "is_public": True,
            "sort_order": 1,
            "documents_count": 100,
            "size_mb": 50.5,
            "last_updated": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "metadata": {},
        }
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.get(
            f"/api/v1/industry-selection/databases/{self.test_database_id}"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "储能行业知识库"
        assert data["code"] == "ENERGY_STORAGE_KB"

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_save_industry_selection_success(self, mock_get_service):
        """测试成功保存行业选择"""
        # 模拟服务
        mock_service = Mock()
        mock_service.validate_industry_selection.return_value = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "industry": {
                "id": self.test_industry_id,
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": IndustryCategory.ENERGY.value,
                "description": "储能产业相关",
                "is_active": True,
                "sort_order": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            },
            "databases": [
                {
                    "id": self.test_database_id,
                    "name": "储能行业知识库",
                    "code": "ENERGY_STORAGE_KB",
                    "industry_id": self.test_industry_id,
                    "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                    "data_source": DataSource.PLATFORM_BUILTIN.value,
                    "description": "储能行业知识库",
                    "is_active": True,
                    "is_public": True,
                    "sort_order": 1,
                    "documents_count": 100,
                    "size_mb": 50.5,
                    "last_updated": datetime.now(UTC).isoformat(),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "metadata": {},
                }
            ],
        }
        mock_service.save_industry_selection.return_value = {
            "selection": {
                "id": self.test_selection_id,
                "session_id": str(uuid.uuid4()),
                "industry_id": self.test_industry_id,
                "database_ids": f'["{self.test_database_id}"]',
                "selection_name": "测试选择",
                "description": "测试描述",
                "is_active": True,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": "{}",
            },
            "industry": {
                "id": self.test_industry_id,
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": IndustryCategory.ENERGY.value,
                "description": "储能产业相关",
                "is_active": True,
                "sort_order": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            },
            "databases": [
                {
                    "id": self.test_database_id,
                    "name": "储能行业知识库",
                    "code": "ENERGY_STORAGE_KB",
                    "industry_id": self.test_industry_id,
                    "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                    "data_source": DataSource.PLATFORM_BUILTIN.value,
                    "description": "储能行业知识库",
                    "is_active": True,
                    "is_public": True,
                    "sort_order": 1,
                    "documents_count": 100,
                    "size_mb": 50.5,
                    "last_updated": datetime.now(UTC).isoformat(),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "metadata": {},
                }
            ],
        }
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.post(
            "/api/v1/industry-selection/selections",
            json={
                "industry_id": self.test_industry_id,
                "database_ids": [self.test_database_id],
                "session_id": str(uuid.uuid4()),
                "selection_name": "测试选择",
                "description": "测试描述",
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["industry"]["name"] == "储能行业"
        assert len(data["databases"]) == 1
        assert data["selection_name"] == "测试选择"

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_save_industry_selection_without_session(self, mock_get_service):
        """测试保存行业选择时不提供session_id"""
        # 模拟服务
        mock_service = Mock()
        mock_service.validate_industry_selection.return_value = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "industry": self.mock_industry,
            "databases": [self.mock_database],
        }
        mock_service.save_industry_selection.return_value = {
            "selection": self.mock_selection,
            "industry": self.mock_industry,
            "databases": [self.mock_database],
        }
        mock_get_service.return_value = mock_service

        # 发送请求 - 不提供session_id
        response = self.client.post(
            "/api/v1/industry-selection/selections",
            json={
                "industry_id": self.mock_industry["id"],
                "database_ids": [self.mock_database["id"]],
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_industry_selection_detail_success(self, mock_get_service):
        """测试成功获取行业选择详情"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industry_selection.return_value = {
            "selection": {
                "id": self.test_selection_id,
                "session_id": str(uuid.uuid4()),
                "industry_id": self.test_industry_id,
                "database_ids": f'["{self.test_database_id}"]',
                "selection_name": "测试选择",
                "description": "测试描述",
                "is_active": True,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": "{}",
            },
            "industry": {
                "id": self.test_industry_id,
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": IndustryCategory.ENERGY.value,
                "description": "储能产业相关",
                "is_active": True,
                "sort_order": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            },
            "databases": [
                {
                    "id": self.test_database_id,
                    "name": "储能行业知识库",
                    "code": "ENERGY_STORAGE_KB",
                    "industry_id": self.test_industry_id,
                    "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                    "data_source": DataSource.PLATFORM_BUILTIN.value,
                    "description": "储能行业知识库",
                    "is_active": True,
                    "is_public": True,
                    "sort_order": 1,
                    "documents_count": 100,
                    "size_mb": 50.5,
                    "last_updated": datetime.now(UTC).isoformat(),
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "metadata": {},
                }
            ],
            "database_ids": [self.test_database_id],
        }
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.get(
            f"/api/v1/industry-selection/selections/{self.test_selection_id}"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["industry"]["name"] == "储能行业"
        assert len(data["databases"]) == 1

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_list_industry_selections_success(self, mock_get_service):
        """测试成功获取行业选择列表"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_selections_by_session.return_value = [
            {
                "selection": {
                    "id": self.test_selection_id,
                    "session_id": str(uuid.uuid4()),
                    "industry_id": self.test_industry_id,
                    "database_ids": f'["{self.test_database_id}"]',
                    "selection_name": "测试选择",
                    "description": "测试描述",
                    "is_active": True,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "metadata": "{}",
                },
                "industry": {
                    "id": self.test_industry_id,
                    "name": "储能行业",
                    "code": "ENERGY_STORAGE",
                    "category": IndustryCategory.ENERGY.value,
                    "description": "储能产业相关",
                    "is_active": True,
                    "sort_order": 1,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "metadata": {},
                },
                "databases": [
                    {
                        "id": self.test_database_id,
                        "name": "储能行业知识库",
                        "code": "ENERGY_STORAGE_KB",
                        "industry_id": self.test_industry_id,
                        "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                        "data_source": DataSource.PLATFORM_BUILTIN.value,
                        "description": "储能行业知识库",
                        "is_active": True,
                        "is_public": True,
                        "sort_order": 1,
                        "documents_count": 100,
                        "size_mb": 50.5,
                        "last_updated": datetime.now(UTC).isoformat(),
                        "created_at": datetime.now(UTC).isoformat(),
                        "updated_at": datetime.now(UTC).isoformat(),
                        "metadata": {},
                    }
                ],
                "database_ids": [self.test_database_id],
            }
        ]
        mock_get_service.return_value = mock_service

        # 发送请求
        session_id = str(uuid.uuid4())
        response = self.client.post(
            "/api/v1/industry-selection/selections/list",
            json={
                "session_id": session_id,
                "is_active": True,
                "limit": 20,
                "offset": 0,
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["selections"]) == 1
        assert data["total"] == 1

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_update_industry_selection_success(self, mock_get_service):
        """测试成功更新行业选择"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industry_selection.return_value = {
            "selection": self.mock_selection,
            "industry": self.mock_industry,
            "databases": [self.mock_database],
            "database_ids": [self.mock_database["id"]],
        }
        # 返回更新后的选择记录，selection_name 应与请求保持一致
        updated_selection = self.mock_selection.copy()
        updated_selection["selection_name"] = "更新后的选择名称"
        updated_selection["description"] = "更新后的描述"
        mock_service.update_industry_selection.return_value = {
            "selection": updated_selection,
            "industry": self.mock_industry,
            "databases": [self.mock_database],
            "database_ids": [self.mock_database["id"]],
        }
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.put(
            f"/api/v1/industry-selection/selections/{self.mock_selection['id']}",
            json={
                "selection_name": "更新后的选择名称",
                "description": "更新后的描述",
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["selection_name"] == "更新后的选择名称"

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_delete_industry_selection_success(self, mock_get_service):
        """测试成功删除行业选择"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industry_selection.return_value = {
            "selection": self.mock_selection,
            "industry": self.mock_industry,
            "databases": [self.mock_database],
            "database_ids": [self.mock_database["id"]],
        }
        mock_service.delete_industry_selection.return_value = True
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.delete(
            f"/api/v1/industry-selection/selections/{self.mock_selection['id']}"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "行业选择记录删除成功"

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_delete_industry_selection_not_found(self, mock_get_service):
        """测试删除不存在的行业选择"""
        # 模拟服务
        mock_service = Mock()
        from src.shared.exceptions.base_exceptions import ResourceNotFoundError
        mock_service.delete_industry_selection.side_effect = ResourceNotFoundError(
            "选择记录不存在", resource_type="IndustrySelection", resource_id=str(uuid.uuid4())
        )
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.delete(
            f"/api/v1/industry-selection/selections/{str(uuid.uuid4())}"
        )

        # 验证响应
        assert response.status_code == 500

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_industry_statistics_success(self, mock_get_service):
        """测试成功获取行业统计信息"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_industry_statistics.return_value = {
            "industry": {
                "id": self.test_industry_id,
                "name": "储能行业",
                "code": "ENERGY_STORAGE",
                "category": IndustryCategory.ENERGY.value,
                "description": "储能产业相关",
                "is_active": True,
                "sort_order": 1,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            },
            "total_databases": 10,
            "active_databases": 8,
            "public_databases": 5,
            "database_type_stats": {
                DatabaseType.KNOWLEDGE_BASE.value: 5,
                DatabaseType.MARKET_DATA.value: 3,
                DatabaseType.POLICY_DATABASE.value: 2,
            },
            "data_source_stats": {
                DataSource.PLATFORM_BUILTIN.value: 6,
                DataSource.USER_UPLOADED.value: 4,
            },
            "last_updated": datetime.now(UTC).isoformat(),
        }
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.post(
            "/api/v1/industry-selection/industries/statistics",
            json={
                "industry_id": self.test_industry_id,
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["total_databases"] == 10
        assert data["active_databases"] == 8
        assert data["public_databases"] == 5

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_validate_industry_selection_success(self, mock_get_service):
        """测试成功验证行业选择"""
        # 模拟服务
        mock_service = Mock()
        mock_service.validate_industry_selection.return_value = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "industry": self.mock_industry,
            "databases": [self.mock_database],
        }
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.post(
            "/api/v1/industry-selection/validate",
            json={
                "industry_id": self.mock_industry["id"],
                "database_ids": [self.mock_database["id"]],
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert len(data["errors"]) == 0

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_validate_industry_selection_invalid(self, mock_get_service):
        """测试验证无效的行业选择"""
        # 模拟服务
        mock_service = Mock()
        mock_service.validate_industry_selection.return_value = {
            "is_valid": False,
            "errors": ["数据库不属于该行业"],
            "warnings": [],
            "industry": self.mock_industry,
            "databases": [],
        }
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.post(
            "/api/v1/industry-selection/validate",
            json={
                "industry_id": self.mock_industry["id"],
                "database_ids": [str(uuid.uuid4())],  # 无效的数据库ID
            },
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert len(data["errors"]) > 0

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_storage_industries_success(self, mock_get_service):
        """测试成功获取储能相关行业"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_storage_industries.return_value = [self.mock_industry]
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.get("/api/v1/industry-selection/industries/storage")

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["industries"]) >= 1
        assert any(ind["name"] == "储能行业" for ind in data["industries"])

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_energy_industries_success(self, mock_get_service):
        """测试成功获取能源相关行业"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_energy_industries.return_value = [self.mock_industry]
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.get("/api/v1/industry-selection/industries/energy")

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["industries"]) >= 1

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_knowledge_base_databases_success(self, mock_get_service):
        """测试成功获取知识库类型数据库"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_knowledge_base_databases.return_value = [
            {
                "id": self.test_database_id,
                "name": "储能行业知识库",
                "code": "ENERGY_STORAGE_KB",
                "industry_id": self.test_industry_id,
                "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                "data_source": DataSource.PLATFORM_BUILTIN.value,
                "description": "储能行业知识库",
                "is_active": True,
                "is_public": True,
                "sort_order": 1,
                "documents_count": 100,
                "size_mb": 50.5,
                "last_updated": datetime.now(UTC).isoformat(),
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            }
        ]
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.get(
            f"/api/v1/industry-selection/databases/knowledge-base/{self.test_industry_id}"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["databases"]) >= 1
        assert all(db["database_type"] == DatabaseType.KNOWLEDGE_BASE.value for db in data["databases"])

    @patch('src.interfaces.api.routes.industry_selection.get_industry_selection_service')
    def test_get_platform_builtin_databases_success(self, mock_get_service):
        """测试成功获取平台内置数据库"""
        # 模拟服务
        mock_service = Mock()
        mock_service.get_platform_builtin_databases.return_value = [
            {
                "id": self.test_database_id,
                "name": "储能行业知识库",
                "code": "ENERGY_STORAGE_KB",
                "industry_id": self.test_industry_id,
                "database_type": DatabaseType.KNOWLEDGE_BASE.value,
                "data_source": DataSource.PLATFORM_BUILTIN.value,
                "description": "储能行业知识库",
                "is_active": True,
                "is_public": True,
                "sort_order": 1,
                "documents_count": 100,
                "size_mb": 50.5,
                "last_updated": datetime.now(UTC).isoformat(),
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "metadata": {},
            }
        ]
        mock_get_service.return_value = mock_service

        # 发送请求
        response = self.client.get(
            f"/api/v1/industry-selection/databases/platform-builtin/{self.test_industry_id}"
        )

        # 验证响应
        assert response.status_code == 200
        data = response.json()
        assert len(data["databases"]) >= 1
        assert all(db["data_source"] == DataSource.PLATFORM_BUILTIN.value for db in data["databases"])

    def test_list_industries_validation_error(self):
        """测试获取行业列表时验证错误"""
        # 发送请求 - 无效的category
        response = self.client.post(
            "/api/v1/industry-selection/industries/list",
            json={
                "category": "INVALID_CATEGORY",
            },
        )

        # 验证响应
        assert response.status_code == 422  # 验证错误

    def test_save_industry_selection_validation_error(self):
        """测试保存行业选择时验证错误"""
        # 发送请求 - 缺少必需字段
        response = self.client.post(
            "/api/v1/industry-selection/selections",
            json={
                "industry_id": str(uuid.uuid4()),
                # 缺少database_ids
            },
        )

        # 验证响应
        assert response.status_code == 422  # 验证错误

    def test_save_industry_selection_too_many_databases(self):
        """测试保存行业选择时数据库数量过多"""
        # 发送请求 - 超过10个数据库
        response = self.client.post(
            "/api/v1/industry-selection/selections",
            json={
                "industry_id": str(uuid.uuid4()),
                "database_ids": [str(uuid.uuid4()) for _ in range(11)],
            },
        )

        # 验证响应
        assert response.status_code == 422  # 验证错误


if __name__ == "__main__":
    pytest.main([__file__])
