"""
Industry领域模型单元测试

该模块测试Industry领域模型的各种功能，包括创建、验证、更新等操作。
"""

import pytest
import uuid
from datetime import datetime, UTC

from src.domain.agent.industry import (
    Industry,
    IndustryCategory,
    PREDEFINED_INDUSTRIES,
    get_predefined_industries,
    get_industry_by_code,
    get_energy_storage_industries,
    get_energy_industries,
)


class TestIndustry:
    """Industry领域模型测试类"""

    def test_industry_creation_success(self) -> None:
        """测试成功创建行业对象"""
        industry = Industry(
            name="测试行业",
            code="TEST_INDUSTRY",
            category=IndustryCategory.TECHNOLOGY,
            description="这是一个测试行业",
        )

        assert industry.name == "测试行业"
        assert industry.code == "TEST_INDUSTRY"
        assert industry.category == IndustryCategory.TECHNOLOGY
        assert industry.description == "这是一个测试行业"
        assert industry.is_active is True
        assert industry.sort_order == 0
        assert isinstance(industry.id, uuid.UUID)
        assert isinstance(industry.created_at, datetime)
        assert isinstance(industry.updated_at, datetime)

    def test_industry_creation_with_all_fields(self) -> None:
        """测试使用所有字段创建行业对象"""
        now = datetime.now(UTC)
        industry_id = uuid.uuid4()
        
        industry = Industry(
            id=industry_id,
            name="完整测试行业",
            code="FULL_TEST",
            category=IndustryCategory.ENERGY,
            description="这是一个完整的测试行业",
            is_active=False,
            sort_order=5,
            created_at=now,
            updated_at=now,
            metadata={"key": "value"},
        )

        assert industry.id == industry_id
        assert industry.name == "完整测试行业"
        assert industry.code == "FULL_TEST"
        assert industry.category == IndustryCategory.ENERGY
        assert industry.description == "这是一个完整的测试行业"
        assert industry.is_active is False
        assert industry.sort_order == 5
        assert industry.created_at == now
        assert industry.updated_at == now
        assert industry.metadata == {"key": "value"}

    def test_industry_name_validation_empty(self) -> None:
        """测试行业名称为空时的验证"""
        with pytest.raises(ValueError, match="行业名称不能为空"):
            Industry(
                name="",
                code="TEST",
                category=IndustryCategory.TECHNOLOGY,
            )

        with pytest.raises(ValueError, match="行业名称不能为空"):
            Industry(
                name="   ",
                code="TEST",
                category=IndustryCategory.TECHNOLOGY,
            )

    def test_industry_name_validation_whitespace(self) -> None:
        """测试行业名称包含空白字符的处理"""
        industry = Industry(
            name="  测试行业  ",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
        )
        assert industry.name == "测试行业"

    def test_industry_code_validation_empty(self) -> None:
        """测试行业代码为空时的验证"""
        with pytest.raises(ValueError, match="行业代码不能为空"):
            Industry(
                name="测试行业",
                code="",
                category=IndustryCategory.TECHNOLOGY,
            )

        with pytest.raises(ValueError, match="行业代码不能为空"):
            Industry(
                name="测试行业",
                code="   ",
                category=IndustryCategory.TECHNOLOGY,
            )

    def test_industry_code_validation_format(self) -> None:
        """测试行业代码格式验证"""
        # 有效格式
        industry = Industry(
            name="测试行业",
            code="test_code",
            category=IndustryCategory.TECHNOLOGY,
        )
        assert industry.code == "TEST_CODE"

        industry = Industry(
            name="测试行业",
            code="TEST_CODE_123",
            category=IndustryCategory.TECHNOLOGY,
        )
        assert industry.code == "TEST_CODE_123"

        # 无效格式
        with pytest.raises(ValueError, match="行业代码只能包含字母、数字和下划线"):
            Industry(
                name="测试行业",
                code="TEST-CODE",
                category=IndustryCategory.TECHNOLOGY,
            )

        with pytest.raises(ValueError, match="行业代码只能包含字母、数字和下划线"):
            Industry(
                name="测试行业",
                code="TEST CODE",
                category=IndustryCategory.TECHNOLOGY,
            )

    def test_industry_description_validation(self) -> None:
        """测试行业描述验证"""
        # 有效描述
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            description="  这是一个测试描述  ",
        )
        assert industry.description == "这是一个测试描述"

        # 空描述
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            description="   ",
        )
        assert industry.description is None

        # None描述
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            description=None,
        )
        assert industry.description is None

    def test_industry_sort_order_validation(self) -> None:
        """测试排序顺序验证"""
        # 有效排序
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            sort_order=5,
        )
        assert industry.sort_order == 5

        # 无效排序
        with pytest.raises(ValueError, match="排序顺序不能为负数"):
            Industry(
                name="测试行业",
                code="TEST",
                category=IndustryCategory.TECHNOLOGY,
                sort_order=-1,
            )

    def test_update_description(self) -> None:
        """测试更新行业描述"""
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            description="原始描述",
        )
        
        original_updated_at = industry.updated_at
        # 等待一小段时间确保时间戳不同
        import time
        time.sleep(0.001)
        industry.update_description("新的描述")
        
        assert industry.description == "新的描述"
        assert industry.updated_at > original_updated_at

    def test_update_description_empty(self) -> None:
        """测试更新为空描述"""
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            description="原始描述",
        )
        
        industry.update_description("")
        assert industry.description is None

    def test_activate_deactivate(self) -> None:
        """测试激活和停用行业"""
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            is_active=True,
        )
        
        original_updated_at = industry.updated_at
        
        # 测试停用
        industry.deactivate()
        assert industry.is_active is False
        assert industry.updated_at > original_updated_at
        
        # 测试重复停用（不应该更新时间戳）
        original_updated_at = industry.updated_at
        industry.deactivate()
        assert industry.updated_at == original_updated_at
        
        # 测试激活
        industry.activate()
        assert industry.is_active is True
        assert industry.updated_at > original_updated_at

    def test_set_sort_order(self) -> None:
        """测试设置排序顺序"""
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            sort_order=0,
        )
        
        original_updated_at = industry.updated_at
        industry.set_sort_order(5)
        
        assert industry.sort_order == 5
        assert industry.updated_at > original_updated_at

    def test_set_sort_order_invalid(self) -> None:
        """测试设置无效排序顺序"""
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
        )
        
        with pytest.raises(ValueError, match="排序顺序不能为负数"):
            industry.set_sort_order(-1)

    def test_metadata_operations(self) -> None:
        """测试元数据操作"""
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
        )
        
        original_updated_at = industry.updated_at
        
        # 测试添加元数据
        industry.add_metadata("key1", "value1")
        assert industry.get_metadata("key1") == "value1"
        assert industry.updated_at > original_updated_at
        
        # 测试获取不存在的元数据
        assert industry.get_metadata("nonexistent") is None
        assert industry.get_metadata("nonexistent", "default") == "default"
        
        # 测试更新元数据
        original_updated_at = industry.updated_at
        industry.add_metadata("key1", "value2")
        assert industry.get_metadata("key1") == "value2"
        assert industry.updated_at > original_updated_at
        
        # 测试移除元数据
        original_updated_at = industry.updated_at
        result = industry.remove_metadata("key1")
        assert result is True
        assert industry.get_metadata("key1") is None
        assert industry.updated_at > original_updated_at
        
        # 测试移除不存在的元数据
        original_updated_at = industry.updated_at
        result = industry.remove_metadata("nonexistent")
        assert result is False
        assert industry.updated_at == original_updated_at

    def test_is_energy_industry(self) -> None:
        """测试是否为能源行业"""
        energy_industry = Industry(
            name="能源行业",
            code="ENERGY",
            category=IndustryCategory.ENERGY,
        )
        tech_industry = Industry(
            name="技术行业",
            code="TECH",
            category=IndustryCategory.TECHNOLOGY,
        )
        
        assert energy_industry.is_energy_industry() is True
        assert tech_industry.is_energy_industry() is False

    def test_is_storage_industry(self) -> None:
        """测试是否为储能相关行业"""
        storage_industry = Industry(
            name="储能行业",
            code="STORAGE",
            category=IndustryCategory.ENERGY,
        )
        battery_industry = Industry(
            name="电池行业",
            code="BATTERY",
            category=IndustryCategory.MANUFACTURING,
        )
        tech_industry = Industry(
            name="技术行业",
            code="TECH",
            category=IndustryCategory.TECHNOLOGY,
        )
        
        assert storage_industry.is_storage_industry() is True
        assert battery_industry.is_storage_industry() is True
        assert tech_industry.is_storage_industry() is False

    def test_get_display_name(self) -> None:
        """测试获取显示名称"""
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
        )
        
        assert industry.get_display_name() == "测试行业 (TEST)"

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        industry = Industry(
            name="测试行业",
            code="TEST",
            category=IndustryCategory.TECHNOLOGY,
            description="测试描述",
            metadata={"key": "value"},
        )
        
        result = industry.to_dict()
        
        assert isinstance(result, dict)
        assert result["name"] == "测试行业"
        assert result["code"] == "TEST"
        assert result["category"] == "TECHNOLOGY"
        assert result["description"] == "测试描述"
        assert result["is_active"] is True
        assert result["sort_order"] == 0
        assert result["metadata"] == {"key": "value"}
        assert isinstance(result["id"], str)
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)


class TestIndustryFactoryMethods:
    """Industry工厂方法测试类"""

    def test_create_energy_storage_industry(self) -> None:
        """测试创建储能行业"""
        industry = Industry.create_energy_storage_industry()
        
        assert industry.name == "储能行业"
        assert industry.code == "ENERGY_STORAGE"
        assert industry.category == IndustryCategory.ENERGY
        assert "储能" in industry.description
        assert industry.sort_order == 1
        assert industry.is_active is True

    def test_create_energy_industry(self) -> None:
        """测试创建能源行业"""
        industry = Industry.create_energy_industry()
        
        assert industry.name == "能源行业"
        assert industry.code == "ENERGY"
        assert industry.category == IndustryCategory.ENERGY
        assert "能源" in industry.description
        assert industry.sort_order == 2
        assert industry.is_active is True

    def test_create_new_energy_industry(self) -> None:
        """测试创建新能源行业"""
        industry = Industry.create_new_energy_industry()
        
        assert industry.name == "新能源行业"
        assert industry.code == "NEW_ENERGY"
        assert industry.category == IndustryCategory.ENERGY
        assert "新能源" in industry.description
        assert industry.sort_order == 3
        assert industry.is_active is True


class TestPredefinedIndustries:
    """预定义行业测试类"""

    def test_predefined_industries_not_empty(self) -> None:
        """测试预定义行业不为空"""
        assert len(PREDEFINED_INDUSTRIES) > 0

    def test_predefined_industries_structure(self) -> None:
        """测试预定义行业结构"""
        for industry in PREDEFINED_INDUSTRIES:
            assert isinstance(industry, Industry)
            assert industry.name
            assert industry.code
            assert industry.category
            assert industry.is_active is True

    def test_get_predefined_industries(self) -> None:
        """测试获取预定义行业"""
        industries = get_predefined_industries()
        
        assert isinstance(industries, list)
        assert len(industries) == len(PREDEFINED_INDUSTRIES)
        # 确保返回的是副本，不是原列表
        assert industries is not PREDEFINED_INDUSTRIES

    def test_get_industry_by_code(self) -> None:
        """测试根据代码获取行业"""
        # 测试存在的代码
        industry = get_industry_by_code("ENERGY_STORAGE")
        assert industry is not None
        assert industry.code == "ENERGY_STORAGE"
        
        # 测试不存在的代码
        industry = get_industry_by_code("NONEXISTENT")
        assert industry is None
        
        # 测试大小写不敏感
        industry = get_industry_by_code("energy_storage")
        assert industry is not None
        assert industry.code == "ENERGY_STORAGE"

    def test_get_energy_storage_industries(self) -> None:
        """测试获取储能相关行业"""
        industries = get_energy_storage_industries()
        
        assert isinstance(industries, list)
        assert len(industries) >= 1  # 至少包含储能行业
        
        for industry in industries:
            assert industry.is_storage_industry()

    def test_get_energy_industries(self) -> None:
        """测试获取能源相关行业"""
        industries = get_energy_industries()
        
        assert isinstance(industries, list)
        assert len(industries) >= 1  # 至少包含一个能源行业
        
        for industry in industries:
            assert industry.is_energy_industry()


class TestIndustryCategory:
    """IndustryCategory枚举测试类"""

    def test_industry_category_values(self) -> None:
        """测试行业分类枚举值"""
        expected_categories = {
            "ENERGY",
            "TECHNOLOGY",
            "MANUFACTURING",
            "FINANCE",
            "HEALTHCARE",
            "EDUCATION",
            "RETAIL",
            "REAL_ESTATE",
            "TRANSPORTATION",
            "AGRICULTURE",
            "OTHER",
        }
        
        actual_categories = {category.value for category in IndustryCategory}
        assert actual_categories == expected_categories

    def test_industry_category_count(self) -> None:
        """测试行业分类数量"""
        assert len(IndustryCategory) == 11