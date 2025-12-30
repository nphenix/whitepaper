"""
行业数据库领域模型

该模块定义了行业数据库的领域模型, 包括数据库的基本属性,与行业的关联和验证规则.
支持储能行业数据库等预定义数据库, 用于MVP 4步流程中的行业和数据库选择.
"""

# 生成命令: /speckit.implement T201
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.domain.agent.industry import Industry


class DatabaseType(str, Enum):
    """数据库类型枚举"""

    KNOWLEDGE_BASE = "KNOWLEDGE_BASE"        # 知识库
    MARKET_DATA = "MARKET_DATA"              # 市场数据
    POLICY_DATABASE = "POLICY_DATABASE"      # 政策数据库
    TECHNOLOGY_DATABASE = "TECHNOLOGY_DATABASE"  # 技术数据库
    INDUSTRY_REPORTS = "INDUSTRY_REPORTS"    # 行业报告
    RESEARCH_PAPERS = "RESEARCH_PAPERS"      # 研究论文
    NEWS_ARTICLES = "NEWS_ARTICLES"          # 新闻文章
    PATENT_DATABASE = "PATENT_DATABASE"      # 专利数据库
    OTHER = "OTHER"                          # 其他


class DataSource(str, Enum):
    """数据来源枚举"""

    PLATFORM_BUILTIN = "PLATFORM_BUILTIN"    # 平台内置
    USER_UPLOADED = "USER_UPLOADED"          # 用户上传
    WEB_CRAWLED = "WEB_CRAWLED"              # 网络爬取
    THIRD_PARTY = "THIRD_PARTY"              # 第三方
    MIXED = "MIXED"                          # 混合来源


class IndustryDatabase(BaseModel):
    """
    行业数据库领域模型

    表示一个特定行业的数据库, 包含数据库的基本信息,类型,来源和与行业的关联.
    用于MVP 4步流程中的第一步: 行业和数据库选择.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="数据库唯一标识")
    name: str = Field(..., description="数据库名称")
    code: str = Field(..., description="数据库代码(唯一标识符)")
    industry_id: uuid.UUID = Field(..., description="所属行业ID")
    database_type: DatabaseType = Field(..., description="数据库类型")
    data_source: DataSource = Field(..., description="数据来源")
    description: str | None = Field(None, description="数据库描述")

    # 状态字段
    is_active: bool = Field(True, description="是否启用")
    is_public: bool = Field(True, description="是否公开")
    sort_order: int = Field(0, description="排序顺序")

    # 统计字段
    documents_count: int = Field(0, description="文档数量")
    size_mb: float = Field(0.0, description="数据库大小(MB)")
    last_updated: datetime | None = Field(default=None, description="最后更新时间")

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
        """验证数据库名称不能为空"""
        if not v or not v.strip():
            error_msg = "数据库名称不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        """验证数据库代码格式"""
        if not v or not v.strip():
            error_msg = "数据库代码不能为空"
            raise ValueError(error_msg)

        v = v.strip().upper()
        # 检查代码格式: 只允许字母,数字和下划线
        if not v.replace("_", "").isalnum():
            error_msg = "数据库代码只能包含字母,数字和下划线"
            raise ValueError(error_msg)

        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证数据库描述"""
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

    @field_validator("documents_count")
    @classmethod
    def validate_documents_count(cls, v: int) -> int:
        """验证文档数量"""
        if v < 0:
            error_msg = "文档数量不能为负数"
            raise ValueError(error_msg)
        return v

    @field_validator("size_mb")
    @classmethod
    def validate_size_mb(cls, v: float) -> float:
        """验证数据库大小"""
        if v < 0:
            error_msg = "数据库大小不能为负数"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_consistency(self) -> "IndustryDatabase":
        """验证字段一致性"""
        # 如果是储能行业数据库, 检查名称是否包含相关关键词
        if "储能" in self.name or "ENERGY_STORAGE" in self.code:
            storage_keywords = ["储能", "电池", "蓄能", "energy storage", "battery"]
            if not any(keyword in self.name.lower() for keyword in [kw.lower() for kw in storage_keywords]):
                # 这里只是警告, 不抛出异常, 因为可能有些特殊的储能数据库名称
                pass

        return self

    def update_description(self, description: str) -> None:
        """
        更新数据库描述

        Args:
            description: 新的描述内容
        """
        new_description = description.strip() if description else None
        if self.description != new_description:
            self.description = new_description
            self.updated_at = datetime.now(UTC)

    def update_statistics(self, documents_count: int, size_mb: float) -> None:
        """
        更新统计信息

        Args:
            documents_count: 文档数量
            size_mb: 数据库大小(MB)
        """
        if documents_count < 0 or size_mb < 0:
            error_msg = "文档数量和数据库大小不能为负数"
            raise ValueError(error_msg)

        if self.documents_count != documents_count or self.size_mb != size_mb:
            self.documents_count = documents_count
            self.size_mb = size_mb
            self.last_updated = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)

    def activate(self) -> None:
        """激活数据库"""
        if not self.is_active:
            self.is_active = True
            # 确保时间戳更新
            import time

            time.sleep(0.001)  # 确保时间戳不同
            self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        """停用数据库"""
        if self.is_active:
            self.is_active = False
            # 确保时间戳更新
            import time

            time.sleep(0.001)  # 确保时间戳不同
            self.updated_at = datetime.now(UTC)

    def set_public(self, is_public: bool) -> None:
        """
        设置公开状态

        Args:
            is_public: 是否公开
        """
        if self.is_public != is_public:
            self.is_public = is_public
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

    def is_knowledge_base_type(self) -> bool:
        """
        检查是否为知识库类型

        Returns:
            是否为知识库类型
        """
        return self.database_type == DatabaseType.KNOWLEDGE_BASE

    def is_platform_builtin(self) -> bool:
        """
        检查是否为平台内置数据库

        Returns:
            是否为平台内置数据库
        """
        return self.data_source == DataSource.PLATFORM_BUILTIN

    def is_storage_database(self) -> bool:
        """
        检查是否为储能相关数据库

        Returns:
            是否为储能相关数据库
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

    def get_type_display_name(self) -> str:
        """
        获取类型显示名称

        Returns:
            类型显示名称
        """
        type_names = {
            DatabaseType.KNOWLEDGE_BASE: "知识库",
            DatabaseType.MARKET_DATA: "市场数据",
            DatabaseType.POLICY_DATABASE: "政策数据库",
            DatabaseType.TECHNOLOGY_DATABASE: "技术数据库",
            DatabaseType.INDUSTRY_REPORTS: "行业报告",
            DatabaseType.RESEARCH_PAPERS: "研究论文",
            DatabaseType.NEWS_ARTICLES: "新闻文章",
            DatabaseType.PATENT_DATABASE: "专利数据库",
            DatabaseType.OTHER: "其他",
        }
        return type_names.get(self.database_type, "未知")

    def get_source_display_name(self) -> str:
        """
        获取来源显示名称

        Returns:
            来源显示名称
        """
        source_names = {
            DataSource.PLATFORM_BUILTIN: "平台内置",
            DataSource.USER_UPLOADED: "用户上传",
            DataSource.WEB_CRAWLED: "网络爬取",
            DataSource.THIRD_PARTY: "第三方",
            DataSource.MIXED: "混合来源",
        }
        return source_names.get(self.data_source, "未知")

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
            "industry_id": str(self.industry_id),
            "database_type": self.database_type.value
            if hasattr(self.database_type, "value")
            else self.database_type,
            "data_source": self.data_source.value
            if hasattr(self.data_source, "value")
            else self.data_source,
            "description": self.description,
            "is_active": self.is_active,
            "is_public": self.is_public,
            "sort_order": self.sort_order,
            "documents_count": self.documents_count,
            "size_mb": self.size_mb,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def create_energy_storage_knowledge_base(cls, industry_id: uuid.UUID) -> "IndustryDatabase":
        """
        创建储能行业知识库实例

        Args:
            industry_id: 所属行业ID

        Returns:
            储能行业知识库对象
        """
        return cls(
            name="储能行业知识库",
            code="ENERGY_STORAGE_KB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="储能行业知识库包含储能技术,市场,政策等相关文档和数据",
            sort_order=1,
            is_active=True,
            is_public=True,
            documents_count=0,
            size_mb=0.0,
        )

    @classmethod
    def create_energy_storage_market_database(cls, industry_id: uuid.UUID) -> "IndustryDatabase":
        """
        创建储能行业市场数据库实例

        Args:
            industry_id: 所属行业ID

        Returns:
            储能行业市场数据库对象
        """
        return cls(
            name="储能行业市场数据库",
            code="ENERGY_STORAGE_MARKET",
            industry_id=industry_id,
            database_type=DatabaseType.MARKET_DATA,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="储能行业市场数据库包含市场规模,价格趋势,竞争格局等市场数据",
            sort_order=2,
            is_active=True,
            is_public=True,
            documents_count=0,
            size_mb=0.0,
        )

    @classmethod
    def create_energy_storage_policy_database(cls, industry_id: uuid.UUID) -> "IndustryDatabase":
        """
        创建储能行业政策数据库实例

        Args:
            industry_id: 所属行业ID

        Returns:
            储能行业政策数据库对象
        """
        return cls(
            name="储能行业政策数据库",
            code="ENERGY_STORAGE_POLICY",
            industry_id=industry_id,
            database_type=DatabaseType.POLICY_DATABASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="储能行业政策数据库包含国家政策,地方政策,行业标准等政策信息",
            sort_order=3,
            is_active=True,
            is_public=True,
            documents_count=0,
            size_mb=0.0,
        )

    @classmethod
    def create_energy_industry_knowledge_base(cls, industry_id: uuid.UUID) -> "IndustryDatabase":
        """
        创建能源行业知识库实例

        Args:
            industry_id: 所属行业ID

        Returns:
            能源行业知识库对象
        """
        return cls(
            name="能源行业知识库",
            code="ENERGY_KB",
            industry_id=industry_id,
            database_type=DatabaseType.KNOWLEDGE_BASE,
            data_source=DataSource.PLATFORM_BUILTIN,
            description="能源行业知识库包含传统能源和新能源相关知识",
            sort_order=4,
            is_active=True,
            is_public=True,
            documents_count=0,
            size_mb=0.0,
        )

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


def create_predefined_industry_databases(industry: Industry) -> list[IndustryDatabase]:
    """
    为指定行业创建预定义数据库

    Args:
        industry: 行业对象

    Returns:
        预定义数据库列表
    """
    databases = []

    # 为储能行业创建特定的数据库
    if industry.is_storage_industry():
        databases.append(IndustryDatabase.create_energy_storage_knowledge_base(industry.id))
        databases.append(IndustryDatabase.create_energy_storage_market_database(industry.id))
        databases.append(IndustryDatabase.create_energy_storage_policy_database(industry.id))

    # 为能源行业创建通用数据库
    if industry.is_energy_industry():
        databases.append(IndustryDatabase.create_energy_industry_knowledge_base(industry.id))

    # 为其他行业创建通用知识库
    if not databases:
        databases.append(
            IndustryDatabase(
                name=f"{industry.name}知识库",
                code=f"{industry.code}_KB",
                industry_id=industry.id,
                database_type=DatabaseType.KNOWLEDGE_BASE,
                data_source=DataSource.PLATFORM_BUILTIN,
                description=f"{industry.name}相关知识库",
                sort_order=1,
                is_active=True,
                is_public=True,
                documents_count=0,
                size_mb=0.0,
            )
        )

    return databases


def get_industry_database_by_code(
    databases: list[IndustryDatabase], code: str
) -> IndustryDatabase | None:
    """
    根据代码获取行业数据库

    Args:
        databases: 数据库列表
        code: 数据库代码

    Returns:
        数据库对象(如果找到)
    """
    for database in databases:
        if database.code == code.upper():
            return database
    return None


def get_storage_databases(databases: list[IndustryDatabase]) -> list[IndustryDatabase]:
    """
    获取储能相关数据库

    Args:
        databases: 数据库列表

    Returns:
        储能相关数据库列表
    """
    return [database for database in databases if database.is_storage_database()]


def get_knowledge_base_databases(databases: list[IndustryDatabase]) -> list[IndustryDatabase]:
    """
    获取知识库类型数据库

    Args:
        databases: 数据库列表

    Returns:
        知识库类型数据库列表
    """
    return [database for database in databases if database.is_knowledge_base_type()]


def get_active_databases(databases: list[IndustryDatabase]) -> list[IndustryDatabase]:
    """
    获取活跃数据库

    Args:
        databases: 数据库列表

    Returns:
        活跃数据库列表
    """
    return [database for database in databases if database.is_active]


def get_public_databases(databases: list[IndustryDatabase]) -> list[IndustryDatabase]:
    """
    获取公开数据库

    Args:
        databases: 数据库列表

    Returns:
        公开数据库列表
    """
    return [database for database in databases if database.is_public]
