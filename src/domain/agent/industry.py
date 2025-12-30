"""
行业领域模型

该模块定义了行业的领域模型, 包括行业的基本属性,分类和验证规则.
支持储能行业等预定义行业, 用于MVP 4步流程中的行业选择.
"""

# 生成命令: /speckit.implement T200
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class IndustryCategory(str, Enum):
    """行业分类枚举"""

    ENERGY = "ENERGY"                    # 能源行业
    TECHNOLOGY = "TECHNOLOGY"            # 技术行业
    MANUFACTURING = "MANUFACTURING"      # 制造业
    FINANCE = "FINANCE"                  # 金融行业
    HEALTHCARE = "HEALTHCARE"            # 医疗健康
    EDUCATION = "EDUCATION"              # 教育行业
    RETAIL = "RETAIL"                    # 零售行业
    REAL_ESTATE = "REAL_ESTATE"          # 房地产
    TRANSPORTATION = "TRANSPORTATION"    # 交通运输
    AGRICULTURE = "AGRICULTURE"          # 农业行业
    OTHER = "OTHER"                      # 其他行业


class Industry(BaseModel):
    """
    行业领域模型

    表示一个行业分类, 包含行业的基本信息,分类和描述.
    用于MVP 4步流程中的第一步: 行业和数据库选择.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="行业唯一标识")
    name: str = Field(..., description="行业名称")
    code: str = Field(..., description="行业代码(唯一标识符)")
    category: IndustryCategory = Field(..., description="行业分类")
    description: str | None = Field(None, description="行业描述")

    # 状态字段
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序顺序")

    # 时间字段
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="更新时间"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证行业名称不能为空"""
        if not v or not v.strip():
            error_msg = "行业名称不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """验证行业代码格式"""
        if not v or not v.strip():
            error_msg = "行业代码不能为空"
            raise ValueError(error_msg)

        v = v.strip().upper()
        # 检查代码格式: 只允许字母,数字和下划线
        if not v.replace("_", "").isalnum():
            error_msg = "行业代码只能包含字母,数字和下划线"
            raise ValueError(error_msg)

        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证行业描述"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: int) -> int:
        """验证排序顺序"""
        if v < 0:
            error_msg = "排序顺序不能为负数"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_consistency(self) -> "Industry":
        """验证字段一致性"""
        # 如果是能源行业, 检查名称是否包含相关关键词
        if self.category == IndustryCategory.ENERGY:
            energy_keywords = ["能源", "储能", "电力", "新能源", "清洁能源"]
            if not any(keyword in self.name for keyword in energy_keywords):
                # 这里只是警告, 不抛出异常, 因为可能有些特殊的能源行业名称
                pass

        return self

    def update_description(self, description: str) -> None:
        """
        更新行业描述

        Args:
            description: 新的描述内容
        """
        new_description = description.strip() if description else None
        if self.description != new_description:
            self.description = new_description
            self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        """激活行业"""
        if not self.is_active:
            self.is_active = True
            # 确保时间戳更新
            import time

            time.sleep(0.001)  # 确保时间戳不同
            self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        """停用行业"""
        if self.is_active:
            self.is_active = False
            # 确保时间戳更新
            import time

            time.sleep(0.001)  # 确保时间戳不同
            self.updated_at = datetime.now(UTC)

    def set_sort_order(self, sort_order: int) -> None:
        """
        设置排序顺序

        Args:
            sort_order: 新的排序顺序
        """
        if sort_order < 0:
            error_msg = "排序顺序不能为负数"
            raise ValueError(error_msg)

        if self.sort_order != sort_order:
            self.sort_order = sort_order
            # 确保时间戳更新
            import time

            time.sleep(0.001)  # 确保时间戳不同
            self.updated_at = datetime.now(UTC)

    def add_metadata(self, key: str, value: Any) -> None:
        """
        添加元数据

        Args:
            key: 元数据键
            value: 元数据值
        """
        current_value = self.metadata.get(key)
        if current_value != value:
            new_metadata = self.metadata.copy()
            new_metadata[key] = value
            self.metadata = new_metadata
            # 确保时间戳更新
            import time

            time.sleep(0.001)  # 确保时间戳不同
            self.updated_at = datetime.now(UTC)

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        获取元数据

        Args:
            key: 元数据键
            default: 默认值

        Returns:
            元数据值
        """
        return self.metadata.get(key, default)

    def remove_metadata(self, key: str) -> bool:
        """
        移除元数据

        Args:
            key: 要移除的元数据键

        Returns:
            是否成功移除(键存在)
        """
        if key in self.metadata:
            new_metadata = self.metadata.copy()
            del new_metadata[key]
            self.metadata = new_metadata
            # 确保时间戳更新
            import time

            time.sleep(0.001)  # 确保时间戳不同
            self.updated_at = datetime.now(UTC)
            return True
        return False

    def is_energy_industry(self) -> bool:
        """
        检查是否为能源行业

        Returns:
            是否为能源行业
        """
        return self.category == IndustryCategory.ENERGY

    def is_storage_industry(self) -> bool:
        """
        检查是否为储能相关行业

        Returns:
            是否为储能相关行业
        """
        storage_keywords = ["储能", "电池", "蓄能", "energy storage", "battery"]
        return any(
            keyword in self.name.lower()
            for keyword in [kw.lower() for kw in storage_keywords]
        )

    def get_display_name(self) -> str:
        """
        获取显示名称

        Returns:
            格式化的显示名称
        """
        return f"{self.name} ({self.code})"

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "name": self.name,
            "code": self.code,
            "category": self.category.value
            if hasattr(self.category, "value")
            else self.category,
            "description": self.description,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def create_energy_storage_industry(cls) -> "Industry":
        """
        创建储能行业实例

        Returns:
            储能行业对象
        """
        return cls(
            name="储能行业",
            code="ENERGY_STORAGE",
            category=IndustryCategory.ENERGY,
            description="储能行业包括电池储能,抽水蓄能,压缩空气储能等各种储能技术及相关应用",
            sort_order=1,
            is_active=True,
        )

    @classmethod
    def create_energy_industry(cls) -> "Industry":
        """
        创建能源行业实例

        Returns:
            能源行业对象
        """
        return cls(
            name="能源行业",
            code="ENERGY",
            category=IndustryCategory.ENERGY,
            description="能源行业包括传统能源和新能源, 如电力,石油,天然气,太阳能,风能等",
            sort_order=2,
            is_active=True,
        )

    @classmethod
    def create_new_energy_industry(cls) -> "Industry":
        """
        创建新能源行业实例

        Returns:
            新能源行业对象
        """
        return cls(
            name="新能源行业",
            code="NEW_ENERGY",
            category=IndustryCategory.ENERGY,
            description="新能源行业包括太阳能,风能,生物质能,地热能等可再生能源",
            sort_order=3,
            is_active=True,
        )

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


# 预定义行业数据
PREDEFINED_INDUSTRIES = [
    Industry.create_energy_storage_industry(),
    Industry.create_energy_industry(),
    Industry.create_new_energy_industry(),
]


def get_predefined_industries() -> list[Industry]:
    """
    获取所有预定义行业

    Returns:
        预定义行业列表
    """
    return PREDEFINED_INDUSTRIES.copy()


def get_industry_by_code(code: str) -> Industry | None:
    """
    根据代码获取行业

    Args:
        code: 行业代码

    Returns:
        行业对象(如果找到)
    """
    for industry in PREDEFINED_INDUSTRIES:
        if industry.code == code.upper():
            return industry
    return None


def get_energy_storage_industries() -> list[Industry]:
    """
    获取储能相关行业

    Returns:
        储能相关行业列表
    """
    return [industry for industry in PREDEFINED_INDUSTRIES if industry.is_storage_industry()]


def get_energy_industries() -> list[Industry]:
    """
    获取能源相关行业

    Returns:
        能源相关行业列表
    """
    return [industry for industry in PREDEFINED_INDUSTRIES if industry.is_energy_industry()]
