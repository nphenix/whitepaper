"""
IndustryDatabase领域模型测试

测试IndustryDatabase领域模型的各种功能，包括创建、验证、业务方法等。
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from src.domain.agent.industry import Industry, IndustryCategory
from src.domain.knowledge_base.industry_database import (
    DatabaseType,
    DataSource,
    IndustryDatabase,
    create_predefined_industry_databases,
    get_industry_database_by_code,
    get_knowledge_base_databases,
    get_storage_databases,
    get_active_databases,
    get_public_databases,
)


class TestIndustryDatabase:
    """IndustryDatabase领域模型测试类"""

    def test_create_industry_database_success(self) -> None:
        """测试成功创建IndustryDatabase"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="测试数据库描述",
        )

        assert database.name == "测试数据库"
        assert database.code == "TEST_DB"
        assert database.industry_id == industry_id
        assert database.database_type == DatabaseType.KNOWLEDGE_BASE
        assert database.data_source == DataSource.PLATFORM_BUILTIN
        assert database.description == "测试数据库描述"
        assert database.is_active is True
        assert database.is_public is True
        assert database.sort_order == 0
        assert database.documents_count == 0
        assert database.size_mb == 0.0
        assert database.last_updated is None
        assert isinstance(database.created_at, datetime)
        assert isinstance(database.updated_at, datetime)
        assert database.metadata == {}

    def test_create_industry_database_with_all_fields(self) -> None:
        """测试创建包含所有字段的IndustryDatabase"""
        industry_id = uuid.uuid4()
        last_updated = datetime.now(UTC)
        created_at = datetime.now(UTC)
        metadata = {"key1": "value1", "key2": "value2"}

        database = IndustryDatabase(
            name="完整数据库",
            code="COMPLETE_DB",
            industry_id=industry_id,
            database_type=DatabaseType.MARKET_DATA,
            data_source=DataSource.USER_UPLOADED,
            description="完整数据库描述",
            is_active=False,
            is_public=False,
            sort_order=5,
            documents_count=100,
            size_mb=50.5,
            last_updated=last_updated,
            created_at=created_at,
            metadata=metadata,
        )

        assert database.name == "完整数据库"
        assert database.code == "COMPLETE_DB"
        assert database.industry_id == industry_id
        assert database.database_type == DatabaseType.MARKET_DATA
        assert database.data_source == DataSource.USER_UPLOADED
        assert database.description == "完整数据库描述"
        assert database.is_active is False
        assert database.is_public is False
        assert database.sort_order == 5
        assert database.documents_count == 100
        assert database.size_mb == 50.5
        assert database.last_updated == last_updated
        assert database.created_at == created_at
        assert database.metadata == metadata

    def test_validate_name_empty(self) -> None:
        """测试验证空名称"""
        industry_id = uuid.uuid4()
        with pytest.raises(ValueError, match="数据库名称不能为空"):
            IndustryDatabase(
                name="",
                code="TEST_DB",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            )

    def test_validate_name_whitespace_only(self) -> None:
        """测试验证仅包含空白字符的名称"""
        industry_id = uuid.uuid4()
        with pytest.raises(ValueError, match="数据库名称不能为空"):
            IndustryDatabase(
                name="   ",
                code="TEST_DB",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            )

    def test_validate_name_trim_whitespace(self) -> None:
        """测试验证名称去除前后空白字符"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="  测试数据库  ",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.name == "测试数据库"

    def test_validate_code_empty(self) -> None:
        """测试验证空代码"""
        industry_id = uuid.uuid4()
        with pytest.raises(ValueError, match="数据库代码不能为空"):
            IndustryDatabase(
                name="测试数据库",
                code="",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            )

    def test_validate_code_whitespace_only(self) -> None:
        """测试验证仅包含空白字符的代码"""
        industry_id = uuid.uuid4()
        with pytest.raises(ValueError, match="数据库代码不能为空"):
            IndustryDatabase(
                name="测试数据库",
                code="   ",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            )

    def test_validate_code_trim_whitespace_and_uppercase(self) -> None:
        """测试验证代码去除前后空白字符并转为大写"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="  test_db  ",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.code == "TEST_DB"

    def test_validate_code_invalid_characters(self) -> None:
        """测试验证包含无效字符的代码"""
        industry_id = uuid.uuid4()
        with pytest.raises(ValueError, match="数据库代码只能包含字母、数字和下划线"):
            IndustryDatabase(
                name="测试数据库",
                code="TEST-DB",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            )

    def test_validate_description_none(self) -> None:
        """测试验证None描述"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description=None,
        )
        assert database.description is None

    def test_validate_description_empty(self) -> None:
        """测试验证空描述"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="",
        )
        assert database.description is None

    def test_validate_description_whitespace_only(self) -> None:
        """测试验证仅包含空白字符的描述"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="   ",
        )
        assert database.description is None

    def test_validate_description_trim_whitespace(self) -> None:
        """测试验证描述去除前后空白字符"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="  测试描述  ",
        )
        assert database.description == "测试描述"

    def test_validate_sort_order_negative(self) -> None:
        """测试验证负数排序顺序"""
        industry_id = uuid.uuid4()
        with pytest.raises(ValueError, match="排序顺序不能为负数"):
            IndustryDatabase(
                name="测试数据库",
                code="TEST_DB",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
                sort_order=-1,
            )

    def test_validate_documents_count_negative(self) -> None:
        """测试验证负数文档数量"""
        industry_id = uuid.uuid4()
        with pytest.raises(ValueError, match="文档数量不能为负数"):
            IndustryDatabase(
                name="测试数据库",
                code="TEST_DB",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
                documents_count=-1,
            )

    def test_validate_size_mb_negative(self) -> None:
        """测试验证负数数据库大小"""
        industry_id = uuid.uuid4()
        with pytest.raises(ValueError, match="数据库大小不能为负数"):
            IndustryDatabase(
                name="测试数据库",
                code="TEST_DB",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
                size_mb=-1.0,
            )

    def test_update_description(self) -> None:
        """测试更新描述"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="原始描述",
        )
        original_updated_at = database.updated_at

        # 等待一小段时间确保时间戳不同
        import time

        time.sleep(0.001)

        database.update_description("新描述")
        assert database.description == "新描述"
        assert database.updated_at > original_updated_at

    def test_update_description_same_value(self) -> None:
        """测试更新相同描述不更新时间戳"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="测试描述",
        )
        original_updated_at = database.updated_at

        database.update_description("测试描述")
        assert database.updated_at == original_updated_at

    def test_update_statistics(self) -> None:
        """测试更新统计信息"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        original_updated_at = database.updated_at
        original_last_updated = database.last_updated

        # 等待一小段时间确保时间戳不同
        import time

        time.sleep(0.001)

        database.update_statistics(100, 50.5)
        assert database.documents_count == 100
        assert database.size_mb == 50.5
        # 检查last_updated是否被正确设置（原来为None，现在应该是一个datetime对象）
        assert database.last_updated is not None
        assert database.last_updated > original_last_updated if original_last_updated is not None else True
        assert database.updated_at > original_updated_at

    def test_update_statistics_negative_values(self) -> None:
        """测试更新负数统计信息"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )

        with pytest.raises(ValueError, match="文档数量和数据库大小不能为负数"):
            database.update_statistics(-1, 50.5)

        with pytest.raises(ValueError, match="文档数量和数据库大小不能为负数"):
            database.update_statistics(100, -1.0)

    def test_activate(self) -> None:
        """测试激活数据库"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            is_active=False,
        )
        original_updated_at = database.updated_at

        # 等待一小段时间确保时间戳不同
        import time

        time.sleep(0.001)

        database.activate()
        assert database.is_active is True
        assert database.updated_at > original_updated_at

    def test_activate_already_active(self) -> None:
        """测试激活已激活的数据库不更新时间戳"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            is_active=True,
        )
        original_updated_at = database.updated_at

        database.activate()
        assert database.is_active is True
        assert database.updated_at == original_updated_at

    def test_deactivate(self) -> None:
        """测试停用数据库"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            is_active=True,
        )
        original_updated_at = database.updated_at

        # 等待一小段时间确保时间戳不同
        import time

        time.sleep(0.001)

        database.deactivate()
        assert database.is_active is False
        assert database.updated_at > original_updated_at

    def test_deactivate_already_inactive(self) -> None:
        """测试停用已停用的数据库不更新时间戳"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            is_active=False,
        )
        original_updated_at = database.updated_at

        database.deactivate()
        assert database.is_active is False
        assert database.updated_at == original_updated_at

    def test_set_public(self) -> None:
        """测试设置公开状态"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            is_public=False,
        )
        original_updated_at = database.updated_at

        # 等待一小段时间确保时间戳不同
        import time

        time.sleep(0.001)

        database.set_public(True)
        assert database.is_public is True
        assert database.updated_at > original_updated_at

    def test_set_public_same_value(self) -> None:
        """测试设置相同公开状态不更新时间戳"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            is_public=True,
        )
        original_updated_at = database.updated_at

        database.set_public(True)
        assert database.is_public is True
        assert database.updated_at == original_updated_at

    def test_set_sort_order(self) -> None:
        """测试设置排序顺序"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            sort_order=1,
        )
        original_updated_at = database.updated_at

        # 等待一小段时间确保时间戳不同
        import time

        time.sleep(0.001)

        database.set_sort_order(5)
        assert database.sort_order == 5
        assert database.updated_at > original_updated_at

    def test_set_sort_order_negative(self) -> None:
        """测试设置负数排序顺序"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )

        with pytest.raises(ValueError, match="排序顺序不能为负数"):
            database.set_sort_order(-1)

    def test_add_metadata(self) -> None:
        """测试添加元数据"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        original_updated_at = database.updated_at

        # 等待一小段时间确保时间戳不同
        import time

        time.sleep(0.001)

        database.add_metadata("key1", "value1")
        assert database.metadata["key1"] == "value1"
        assert database.updated_at > original_updated_at

    def test_add_metadata_same_value(self) -> None:
        """测试添加相同元数据值不更新时间戳"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            metadata={"key1": "value1"},
        )
        original_updated_at = database.updated_at

        database.add_metadata("key1", "value1")
        assert database.metadata["key1"] == "value1"
        assert database.updated_at == original_updated_at

    def test_get_metadata(self) -> None:
        """测试获取元数据"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            metadata={"key1": "value1", "key2": "value2"},
        )

        assert database.get_metadata("key1") == "value1"
        assert database.get_metadata("key2") == "value2"
        assert database.get_metadata("key3") is None
        assert database.get_metadata("key3", "default") == "default"

    def test_remove_metadata(self) -> None:
        """测试移除元数据"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            metadata={"key1": "value1", "key2": "value2"},
        )
        original_updated_at = database.updated_at

        # 等待一小段时间确保时间戳不同
        import time

        time.sleep(0.001)

        result = database.remove_metadata("key1")
        assert result is True
        assert "key1" not in database.metadata
        assert "key2" in database.metadata
        assert database.updated_at > original_updated_at

    def test_remove_metadata_nonexistent(self) -> None:
        """测试移除不存在的元数据"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            metadata={"key1": "value1", "key2": "value2"},
        )
        original_updated_at = database.updated_at

        result = database.remove_metadata("key3")
        assert result is False
        assert database.metadata == {"key1": "value1", "key2": "value2"}
        assert database.updated_at == original_updated_at

    def test_is_knowledge_base_type(self) -> None:
        """测试是否为知识库类型"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.is_knowledge_base_type() is True

        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.MARKET_DATA,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.is_knowledge_base_type() is False

    def test_is_platform_builtin(self) -> None:
        """测试是否为平台内置数据库"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.is_platform_builtin() is True

        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.USER_UPLOADED,
        )
        assert database.is_platform_builtin() is False

    def test_is_storage_database(self) -> None:
        """测试是否为储能相关数据库"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="储能数据库",
            code="STORAGE_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.is_storage_database() is True

        database = IndustryDatabase(
            name="电池数据库",
            code="BATTERY_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.is_storage_database() is True

        database = IndustryDatabase(
            name="能源数据库",
            code="ENERGY_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.is_storage_database() is False

    def test_get_display_name(self) -> None:
        """测试获取显示名称"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.get_display_name() == "测试数据库 (TEST_DB)"

    def test_get_type_display_name(self) -> None:
        """测试获取类型显示名称"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.get_type_display_name() == "知识库"

        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.MARKET_DATA,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.get_type_display_name() == "市场数据"

    def test_get_source_display_name(self) -> None:
        """测试获取来源显示名称"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
        )
        assert database.get_source_display_name() == "平台内置"

        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.USER_UPLOADED,
        )
        assert database.get_source_display_name() == "用户上传"

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        industry_id = uuid.uuid4()
        last_updated = datetime.now(UTC)
        created_at = datetime.now(UTC)
        metadata = {"key1": "value1", "key2": "value2"}

        database = IndustryDatabase(
            name="测试数据库",
            code="TEST_DB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="测试数据库描述",
            is_active=False,
            is_public=False,
            sort_order=5,
            documents_count=100,
            size_mb=50.5,
            last_updated=last_updated,
            created_at=created_at,
            metadata=metadata,
        )

        result = database.to_dict()
        assert result["name"] == "测试数据库"
        assert result["code"] == "TEST_DB"
        assert result["industry_id"] == str(industry_id)
        assert result["database_type"] == "KNOWLEDGE_BASE"
        assert result["data_source"] == "PLATFORM_BUILTIN"
        assert result["description"] == "测试数据库描述"
        assert result["is_active"] is False
        assert result["is_public"] is False
        assert result["sort_order"] == 5
        assert result["documents_count"] == 100
        assert result["size_mb"] == 50.5
        assert result["last_updated"] == last_updated.isoformat()
        assert result["created_at"] == created_at.isoformat()
        assert result["metadata"] == metadata

    def test_create_energy_storage_knowledge_base(self) -> None:
        """测试创建储能行业知识库"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase.create_energy_storage_knowledge_base(industry_id)

        assert database.name == "储能行业知识库"
        assert database.code == "ENERGY_STORAGE_KB"
        assert database.industry_id == industry_id
        assert database.database_type == DatabaseType.KNOWLEDGE_BASE
        assert database.data_source == DataSource.PLATFORM_BUILTIN
        assert "储能行业知识库包含" in database.description
        assert database.is_active is True
        assert database.is_public is True
        assert database.sort_order == 1
        assert database.documents_count == 0
        assert database.size_mb == 0.0

    def test_create_energy_storage_market_database(self) -> None:
        """测试创建储能行业市场数据库"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase.create_energy_storage_market_database(industry_id)

        assert database.name == "储能行业市场数据库"
        assert database.code == "ENERGY_STORAGE_MARKET"
        assert database.industry_id == industry_id
        assert database.database_type == DatabaseType.MARKET_DATA
        assert database.data_source == DataSource.PLATFORM_BUILTIN
        assert "储能行业市场数据库包含" in database.description
        assert database.is_active is True
        assert database.is_public is True
        assert database.sort_order == 2
        assert database.documents_count == 0
        assert database.size_mb == 0.0

    def test_create_energy_storage_policy_database(self) -> None:
        """测试创建储能行业政策数据库"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase.create_energy_storage_policy_database(industry_id)

        assert database.name == "储能行业政策数据库"
        assert database.code == "ENERGY_STORAGE_POLICY"
        assert database.industry_id == industry_id
        assert database.database_type == DatabaseType.POLICY_DATABASE
        assert database.data_source == DataSource.PLATFORM_BUILTIN
        assert "储能行业政策数据库包含" in database.description
        assert database.is_active is True
        assert database.is_public is True
        assert database.sort_order == 3
        assert database.documents_count == 0
        assert database.size_mb == 0.0

    def test_create_energy_industry_knowledge_base(self) -> None:
        """测试创建能源行业知识库"""
        industry_id = uuid.uuid4()
        database = IndustryDatabase.create_energy_industry_knowledge_base(industry_id)

        assert database.name == "能源行业知识库"
        assert database.code == "ENERGY_KB"
        assert database.industry_id == industry_id
        assert database.database_type == DatabaseType.KNOWLEDGE_BASE
        assert database.data_source == DataSource.PLATFORM_BUILTIN
        assert "能源行业知识库包含" in database.description
        assert database.is_active is True
        assert database.is_public is True
        assert database.sort_order == 4
        assert database.documents_count == 0
        assert database.size_mb == 0.0


class TestIndustryDatabaseHelperFunctions:
    """IndustryDatabase辅助函数测试类"""

    def test_create_predefined_industry_databases_storage(self) -> None:
        """测试为储能行业创建预定义数据库"""
        industry = Industry.create_energy_storage_industry()
        databases = create_predefined_industry_databases(industry)

        assert len(databases) == 4  # 储能行业应该有4个预定义数据库（3个储能专用+1个能源通用）

        # 检查数据库类型和代码
        codes = [db.code for db in databases]
        assert "ENERGY_STORAGE_KB" in codes
        assert "ENERGY_STORAGE_MARKET" in codes
        assert "ENERGY_STORAGE_POLICY" in codes
        assert "ENERGY_KB" in codes  # 能源行业知识库

        # 检查所有数据库都属于该行业
        for db in databases:
            assert db.industry_id == industry.id

    def test_create_predefined_industry_databases_energy(self) -> None:
        """测试为能源行业创建预定义数据库"""
        industry = Industry.create_energy_industry()
        databases = create_predefined_industry_databases(industry)

        assert len(databases) == 1  # 能源行业应该有1个预定义数据库

        # 检查数据库类型和代码
        assert databases[0].code == "ENERGY_KB"
        assert databases[0].database_type == DatabaseType.KNOWLEDGE_BASE

        # 检查数据库属于该行业
        assert databases[0].industry_id == industry.id

    def test_create_predefined_industry_databases_other(self) -> None:
        """测试为其他行业创建预定义数据库"""
        industry = Industry(
            name="测试行业",
            code="TEST_INDUSTRY",
            category=IndustryCategory.OTHER,
        )
        databases = create_predefined_industry_databases(industry)

        assert len(databases) == 1  # 其他行业应该有1个通用知识库

        # 检查数据库类型和代码
        assert databases[0].code == "TEST_INDUSTRY_KB"
        assert databases[0].database_type == DatabaseType.KNOWLEDGE_BASE
        assert databases[0].name == "测试行业知识库"

        # 检查数据库属于该行业
        assert databases[0].industry_id == industry.id

    def test_get_industry_database_by_code_found(self) -> None:
        """测试根据代码找到数据库"""
        industry_id = uuid.uuid4()
        databases = [
            IndustryDatabase(
                name="数据库1",
                code="DB1",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
            IndustryDatabase(
                name="数据库2",
                code="DB2",
                industry_id=industry_id,
                database_type=DatabaseType.MARKET_DATA,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
        ]

        result = get_industry_database_by_code(databases, "db1")
        assert result is not None
        assert result.code == "DB1"

    def test_get_industry_database_by_code_not_found(self) -> None:
        """测试根据代码未找到数据库"""
        industry_id = uuid.uuid4()
        databases = [
            IndustryDatabase(
                name="数据库1",
                code="DB1",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
            IndustryDatabase(
                name="数据库2",
                code="DB2",
                industry_id=industry_id,
                database_type=DatabaseType.MARKET_DATA,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
        ]

        result = get_industry_database_by_code(databases, "DB3")
        assert result is None

    def test_get_storage_databases(self) -> None:
        """测试获取储能相关数据库"""
        industry_id = uuid.uuid4()
        databases = [
            IndustryDatabase(
                name="储能数据库",
                code="STORAGE_DB",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
            IndustryDatabase(
                name="电池数据库",
                code="BATTERY_DB",
                industry_id=industry_id,
                database_type=DatabaseType.MARKET_DATA,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
            IndustryDatabase(
                name="能源数据库",
                code="ENERGY_DB",
                industry_id=industry_id,
                database_type=DatabaseType.POLICY_DATABASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
        ]

        result = get_storage_databases(databases)
        assert len(result) == 2
        assert result[0].code == "STORAGE_DB"
        assert result[1].code == "BATTERY_DB"

    def test_get_knowledge_base_databases(self) -> None:
        """测试获取知识库类型数据库"""
        industry_id = uuid.uuid4()
        databases = [
            IndustryDatabase(
                name="知识库1",
                code="KB1",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
            IndustryDatabase(
                name="市场数据库",
                code="MARKET_DB",
                industry_id=industry_id,
                database_type=DatabaseType.MARKET_DATA,
                data_source=DataSource.PLATFORM_BUILTIN,
            ),
            IndustryDatabase(
                name="知识库2",
                code="KB2",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.USER_UPLOADED,
            ),
        ]

        result = get_knowledge_base_databases(databases)
        assert len(result) == 2
        assert result[0].code == "KB1"
        assert result[1].code == "KB2"

    def test_get_active_databases(self) -> None:
        """测试获取活跃数据库"""
        industry_id = uuid.uuid4()
        databases = [
            IndustryDatabase(
                name="活跃数据库1",
                code="ACTIVE1",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
                is_active=True,
            ),
            IndustryDatabase(
                name="非活跃数据库",
                code="INACTIVE",
                industry_id=industry_id,
                database_type=DatabaseType.MARKET_DATA,
                data_source=DataSource.PLATFORM_BUILTIN,
                is_active=False,
            ),
            IndustryDatabase(
                name="活跃数据库2",
                code="ACTIVE2",
                industry_id=industry_id,
                database_type=DatabaseType.POLICY_DATABASE,
                data_source=DataSource.PLATFORM_BUILTIN,
                is_active=True,
            ),
        ]

        result = get_active_databases(databases)
        assert len(result) == 2
        assert result[0].code == "ACTIVE1"
        assert result[1].code == "ACTIVE2"

    def test_get_public_databases(self) -> None:
        """测试获取公开数据库"""
        industry_id = uuid.uuid4()
        databases = [
            IndustryDatabase(
                name="公开数据库1",
                code="PUBLIC1",
                industry_id=industry_id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
                is_public=True,
            ),
            IndustryDatabase(
                name="私有数据库",
                code="PRIVATE",
                industry_id=industry_id,
                database_type=DatabaseType.MARKET_DATA,
                data_source=DataSource.PLATFORM_BUILTIN,
                is_public=False,
            ),
            IndustryDatabase(
                name="公开数据库2",
                code="PUBLIC2",
                industry_id=industry_id,
                database_type=DatabaseType.POLICY_DATABASE,
                data_source=DataSource.PLATFORM_BUILTIN,
                is_public=True,
            ),
        ]

        result = get_public_databases(databases)
        assert len(result) == 2
        assert result[0].code == "PUBLIC1"
        assert result[1].code == "PUBLIC2"