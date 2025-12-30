"""
T204任务测试：行业数据库列表获取功能

测试行业选择服务中的行业数据库列表获取功能，特别是储能行业数据库的获取。
验证T204任务要求是否得到满足。
"""

# 生成命令: /speckit.implement T204
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
import pytest
from datetime import UTC, datetime

from src.application.services.industry_selection_service import IndustrySelectionService
from src.domain.agent.industry import Industry, IndustryCategory
from src.domain.knowledge_base.industry_database import (
    DatabaseType,
    DataSource,
    IndustryDatabase,
)
from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
from src.infrastructure.storage.sqlite.connection import SQLiteConnectionManager


class TestT204IndustryDatabaseList:
    """T204任务测试类：行业数据库列表获取功能"""

    @pytest.fixture
    def test_db(self):
        """测试数据库fixture"""
        db_path = "test_t204_industry_database_list.db"
        connection_manager = SQLiteConnectionManager(db_path)
        
        # 运行003迁移脚本
        with open("scripts/migration/migrations/003_create_industries_tables.sql", "r", encoding="utf-8") as f:
            migration_sql = f.read()
        
        # 提取并执行@up部分
        up_section = migration_sql.split("-- @up")[1].split("-- @down")[0]
        
        # 分割SQL语句并逐个执行
        sql_statements = [stmt.strip() for stmt in up_section.split(";") if stmt.strip()]
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            for stmt in sql_statements:
                cursor.execute(stmt)
            conn.commit()
        
        yield connection_manager
        
        # 清理
        connection_manager.close()
        import os
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.fixture
    def industry_service(self, test_db):
        """行业选择服务fixture"""
        return IndustrySelectionService(connection_manager=test_db)

    def test_get_industry_databases_basic(self, industry_service):
        """测试基本行业数据库列表获取功能"""
        # 获取所有行业数据库
        databases = industry_service.get_industry_databases()
        
        # 验证返回了预定义的数据库
        assert len(databases) >= 4, "应该至少有4个预定义的数据库"
        
        # 验证数据库结构
        for db in databases:
            assert "id" in db
            assert "name" in db
            assert "code" in db
            assert "industry_id" in db
            assert "database_type" in db
            assert "data_source" in db
            assert "is_active" in db
            assert "is_public" in db
            assert "sort_order" in db

    def test_get_industry_databases_by_industry_id(self, industry_service):
        """测试按行业ID获取数据库列表"""
        # 获取储能行业ID
        storage_industry = industry_service.get_industry_by_code("ENERGY_STORAGE")
        storage_industry_id = storage_industry["id"]
        
        # 获取储能行业的数据库
        storage_databases = industry_service.get_industry_databases(
            industry_id=storage_industry_id
        )
        
        # 验证返回了储能行业的数据库
        assert len(storage_databases) == 3, "储能行业应该有3个数据库"
        
        # 验证数据库名称
        database_names = [db["name"] for db in storage_databases]
        expected_names = [
            "储能行业知识库",
            "储能行业市场数据库", 
            "储能行业政策数据库"
        ]
        for name in expected_names:
            assert name in database_names, f"应该包含数据库: {name}"
        
        # 验证所有数据库都属于储能行业
        for db in storage_databases:
            assert db["industry_id"] == storage_industry_id

    def test_get_industry_databases_by_type(self, industry_service):
        """测试按数据库类型获取数据库列表"""
        # 获取知识库类型的数据库
        knowledge_base_databases = industry_service.get_industry_databases(
            database_type=DatabaseType.KNOWLEDGE_BASE
        )
        
        # 验证返回了知识库类型的数据库
        assert len(knowledge_base_databases) >= 2, "应该至少有2个知识库类型的数据库"
        
        # 验证所有数据库都是知识库类型
        for db in knowledge_base_databases:
            assert db["database_type"] == DatabaseType.KNOWLEDGE_BASE.value

    def test_get_industry_databases_by_source(self, industry_service):
        """测试按数据来源获取数据库列表"""
        # 获取平台内置的数据库
        builtin_databases = industry_service.get_industry_databases(
            data_source=DataSource.PLATFORM_BUILTIN
        )
        
        # 验证返回了平台内置的数据库
        assert len(builtin_databases) >= 4, "应该至少有4个平台内置的数据库"
        
        # 验证所有数据库都是平台内置
        for db in builtin_databases:
            assert db["data_source"] == DataSource.PLATFORM_BUILTIN.value

    def test_get_industry_databases_with_filters(self, industry_service):
        """测试使用多个过滤条件获取数据库列表"""
        # 获取储能行业的活跃知识库
        storage_industry = industry_service.get_industry_by_code("ENERGY_STORAGE")
        storage_industry_id = storage_industry["id"]
        
        filtered_databases = industry_service.get_industry_databases(
            industry_id=storage_industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            is_active=True,
            is_public=True
        )
        
        # 验证过滤结果
        assert len(filtered_databases) == 1, "储能行业应该只有1个活跃的公开知识库"
        
        # 验证数据库属性
        db = filtered_databases[0]
        assert db["name"] == "储能行业知识库"
        assert db["database_type"] == DatabaseType.KNOWLEDGE_BASE.value
        assert db["data_source"] == DataSource.PLATFORM_BUILTIN.value
        assert db["is_active"] == True
        assert db["is_public"] == True

    def test_get_industry_databases_sorting(self, industry_service):
        """测试数据库列表排序功能"""
        # 按排序字段升序排列
        databases_asc = industry_service.get_industry_databases(
            sort_by="sort_order",
            sort_order="asc"
        )
        
        # 验证升序排列
        for i in range(1, len(databases_asc)):
            assert databases_asc[i]["sort_order"] >= databases_asc[i-1]["sort_order"]
        
        # 按名称降序排列
        databases_desc = industry_service.get_industry_databases(
            sort_by="name",
            sort_order="desc"
        )
        
        # 验证降序排列
        for i in range(1, len(databases_desc)):
            assert databases_desc[i]["name"] <= databases_desc[i-1]["name"]

    def test_get_storage_industries(self, industry_service):
        """测试获取储能相关行业列表"""
        storage_industries = industry_service.get_storage_industries()
        
        # 验证返回了储能相关行业
        assert len(storage_industries) >= 1, "应该至少有1个储能相关行业"
        
        # 验证行业名称包含储能关键词
        for industry in storage_industries:
            assert "储能" in industry["name"] or "ENERGY_STORAGE" in industry["code"]

    def test_get_energy_industries(self, industry_service):
        """测试获取能源相关行业列表"""
        energy_industries = industry_service.get_energy_industries()
        
        # 验证返回了能源相关行业
        assert len(energy_industries) >= 3, "应该至少有3个能源相关行业"
        
        # 验证所有行业都是能源分类
        for industry in energy_industries:
            assert industry["category"] == IndustryCategory.ENERGY.value

    def test_get_knowledge_base_databases(self, industry_service):
        """测试获取知识库类型数据库列表"""
        # 获取储能行业的知识库
        storage_industry = industry_service.get_industry_by_code("ENERGY_STORAGE")
        storage_industry_id = storage_industry["id"]
        
        knowledge_bases = industry_service.get_knowledge_base_databases(
            storage_industry_id
        )
        
        # 验证返回了知识库
        assert len(knowledge_bases) == 1, "储能行业应该有1个知识库"
        
        # 验证数据库类型
        for kb in knowledge_bases:
            assert kb["database_type"] == DatabaseType.KNOWLEDGE_BASE.value

    def test_get_platform_builtin_databases(self, industry_service):
        """测试获取平台内置数据库列表"""
        # 获取储能行业的平台内置数据库
        storage_industry = industry_service.get_industry_by_code("ENERGY_STORAGE")
        storage_industry_id = storage_industry["id"]
        
        builtin_databases = industry_service.get_platform_builtin_databases(
            storage_industry_id
        )
        
        # 验证返回了平台内置数据库
        assert len(builtin_databases) == 3, "储能行业应该有3个平台内置数据库"
        
        # 验证数据来源
        for db in builtin_databases:
            assert db["data_source"] == DataSource.PLATFORM_BUILTIN.value

    def test_get_industry_statistics(self, industry_service):
        """测试获取行业统计信息"""
        # 获取储能行业统计信息
        storage_industry = industry_service.get_industry_by_code("ENERGY_STORAGE")
        storage_industry_id = storage_industry["id"]
        
        stats = industry_service.get_industry_statistics(storage_industry_id)
        
        # 验证统计信息结构
        assert "industry" in stats
        assert "total_databases" in stats
        assert "active_databases" in stats
        assert "public_databases" in stats
        assert "database_type_stats" in stats
        assert "data_source_stats" in stats
        assert "last_updated" in stats
        
        # 验证统计数据
        assert stats["total_databases"] == 3, "储能行业应该有3个数据库"
        assert stats["active_databases"] == 3, "储能行业应该有3个活跃数据库"
        assert stats["public_databases"] == 3, "储能行业应该有3个公开数据库"
        
        # 验证类型统计
        type_stats = stats["database_type_stats"]
        assert type_stats[DatabaseType.KNOWLEDGE_BASE.value] == 1
        assert type_stats[DatabaseType.MARKET_DATA.value] == 1
        assert type_stats[DatabaseType.POLICY_DATABASE.value] == 1
        
        # 验证来源统计
        source_stats = stats["data_source_stats"]
        assert source_stats[DataSource.PLATFORM_BUILTIN.value] == 3

    def test_validate_industry_selection(self, industry_service):
        """测试行业和数据库选择验证"""
        # 获取储能行业ID
        storage_industry = industry_service.get_industry_by_code("ENERGY_STORAGE")
        storage_industry_id = storage_industry["id"]
        
        # 获取储能行业数据库ID
        storage_databases = industry_service.get_industry_databases(
            industry_id=storage_industry_id
        )
        database_ids = [db["id"] for db in storage_databases]
        
        # 验证有效的选择
        validation_result = industry_service.validate_industry_selection(
            storage_industry_id, database_ids
        )
        
        # 验证结果
        assert validation_result["is_valid"] == True
        assert len(validation_result["errors"]) == 0
        assert validation_result["industry"]["id"] == storage_industry_id
        assert len(validation_result["databases"]) == 3

    def test_error_handling(self, industry_service):
        """测试错误处理"""
        # 测试无效的行业ID - 应该返回空列表而不是抛出异常
        result = industry_service.get_industry_databases(industry_id="invalid-uuid")
        assert result == []
        
        # 测试无效的数据库类型 - 应该抛出ValidationError
        with pytest.raises(Exception):
            industry_service.get_industry_databases(database_type="invalid-type")
        
        # 测试无效的数据源 - 应该抛出ValidationError
        with pytest.raises(Exception):
            industry_service.get_industry_databases(data_source="invalid-source")
        
        # 测试无效的数据库ID - 应该抛出异常
        with pytest.raises(Exception):
            industry_service.get_database_by_id("invalid-uuid")
        
        # 测试不存在的行业 - 应该抛出ResourceNotFoundError
        with pytest.raises(Exception):
            industry_service.get_industry_by_id("00000000-0000-0000-0000-000000000999")

    def test_t204_specific_requirements(self, industry_service):
        """测试T204任务的特定要求：储能行业数据库列表获取"""
        # 获取储能行业
        storage_industry = industry_service.get_industry_by_code("ENERGY_STORAGE")
        storage_industry_id = storage_industry["id"]
        
        # 获取储能行业所有数据库
        storage_databases = industry_service.get_industry_databases(
            industry_id=storage_industry_id
        )
        
        # 验证T204要求：储能行业数据库
        expected_storage_databases = [
            {
                "name": "储能行业知识库",
                "code": "ENERGY_STORAGE_KB",
                "type": DatabaseType.KNOWLEDGE_BASE.value
            },
            {
                "name": "储能行业市场数据库",
                "code": "ENERGY_STORAGE_MARKET",
                "type": DatabaseType.MARKET_DATA.value
            },
            {
                "name": "储能行业政策数据库",
                "code": "ENERGY_STORAGE_POLICY",
                "type": DatabaseType.POLICY_DATABASE.value
            }
        ]
        
        # 验证所有预期的数据库都存在
        actual_databases = {
            db["code"]: {
                "name": db["name"],
                "code": db["code"],
                "type": db["database_type"]
            }
            for db in storage_databases
        }
        
        for expected_db in expected_storage_databases:
            assert expected_db["code"] in actual_databases
            actual_db = actual_databases[expected_db["code"]]
            assert actual_db["name"] == expected_db["name"]
            assert actual_db["type"] == expected_db["type"]
        
        # 验证T204要求：储能行业分析数据库
        market_database = industry_service.get_database_by_code("ENERGY_STORAGE_MARKET")
        assert market_database is not None
        assert market_database["name"] == "储能行业市场数据库"
        assert market_database["database_type"] == DatabaseType.MARKET_DATA.value
        assert market_database["description"] is not None
        assert "市场" in market_database["description"]


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])