"""
行业选择相关API Schema

定义行业选择,数据库选择等API的请求和响应Schema.
使用Pydantic进行数据验证.

生成命令: /speckit.implement T207
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator

from src.domain.agent.industry import IndustryCategory
from src.domain.knowledge_base.industry_database import DatabaseType, DataSource


class SortOrder(str, Enum):
    """排序方向枚举"""

    ASC = "asc"
    DESC = "desc"


class SortBy(str, Enum):
    """排序字段枚举"""

    NAME = "name"
    CODE = "code"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    SORT_ORDER = "sort_order"


# === 请求Schema ===

class IndustryListRequest(BaseModel):
    """行业列表请求"""

    category: IndustryCategory | None = Field(None, description="行业分类过滤条件")
    is_active: bool | None = Field(None, description="激活状态过滤条件")
    sort_by: SortBy | None = Field(SortBy.SORT_ORDER, description="排序字段")
    sort_order: SortOrder | None = Field(SortOrder.ASC, description="排序方向(asc/desc)")
    limit: int | None = Field(default=50, ge=1, le=100, description="返回数量限制")
    offset: int | None = Field(default=0, ge=0, description="偏移量")


class IndustryDetailRequest(BaseModel):
    """行业详情请求"""

    industry_id: uuid.UUID = Field(..., description="行业ID")


class IndustryDatabaseListRequest(BaseModel):
    """行业数据库列表请求"""

    industry_id: uuid.UUID | None = Field(None, description="所属行业ID过滤条件")
    database_type: DatabaseType | None = Field(None, description="数据库类型过滤条件")
    data_source: DataSource | None = Field(None, description="数据来源过滤条件")
    is_active: bool | None = Field(None, description="激活状态过滤条件")
    is_public: bool | None = Field(None, description="公开状态过滤条件")
    sort_by: SortBy | None = Field(SortBy.SORT_ORDER, description="排序字段")
    sort_order: SortOrder | None = Field(SortOrder.ASC, description="排序方向(asc/desc)")
    limit: int | None = Field(default=50, ge=1, le=100, description="返回数量限制")
    offset: int | None = Field(default=0, ge=0, description="偏移量")


class DatabaseDetailRequest(BaseModel):
    """数据库详情请求"""

    database_id: uuid.UUID = Field(..., description="数据库ID")


class IndustrySelectionRequest(BaseModel):
    """行业和数据库选择请求"""

    industry_id: uuid.UUID = Field(..., description="选择的行业ID")
    database_ids: list[uuid.UUID] = Field(
        ..., min_length=1, max_length=10, description="选择的数据库ID列表(最多10个)"
    )
    session_id: str | None = Field(None, description="会话ID(可选)")
    selection_name: str | None = Field(None, description="选择名称(可选)")
    description: str | None = Field(None, description="选择描述(可选)")


class IndustrySelectionUpdateRequest(BaseModel):
    """行业选择更新请求"""

    industry_id: uuid.UUID | None = Field(None, description="新的行业ID(可选)")
    database_ids: list[uuid.UUID] | None = Field(None, description="新的数据库ID列表(可选)")
    selection_name: str | None = Field(None, description="新的选择名称(可选)")
    description: str | None = Field(None, description="新的选择描述(可选)")
    is_active: bool | None = Field(None, description="新的激活状态(可选)")


class IndustrySelectionDetailRequest(BaseModel):
    """行业选择详情请求"""

    selection_id: uuid.UUID = Field(..., description="选择记录ID")


class IndustrySelectionListRequest(BaseModel):
    """行业选择列表请求"""

    session_id: str = Field(..., description="会话ID")
    is_active: bool | None = Field(None, description="激活状态过滤条件")
    sort_by: SortBy | None = Field(SortBy.CREATED_AT, description="排序字段")
    sort_order: SortOrder | None = Field(SortOrder.DESC, description="排序方向(asc/desc)")
    limit: int | None = Field(default=20, ge=1, le=100, description="返回数量限制")
    offset: int | None = Field(default=0, ge=0, description="偏移量")


class IndustryStatisticsRequest(BaseModel):
    """行业统计请求"""

    industry_id: uuid.UUID = Field(..., description="行业ID")


class IndustryValidationRequest(BaseModel):
    """行业选择验证请求"""

    industry_id: uuid.UUID = Field(..., description="行业ID")
    database_ids: list[uuid.UUID] = Field(
        ..., min_length=1, max_length=10, description="数据库ID列表(最多10个)"
    )


# === 响应Schema ===

class IndustryResponse(BaseModel):
    """行业响应"""

    id: uuid.UUID = Field(..., description="行业唯一标识")
    name: str = Field(..., description="行业名称")
    code: str = Field(..., description="行业代码(唯一标识符)")
    category: IndustryCategory = Field(..., description="行业分类")
    description: str | None = Field(None, description="行业描述")
    is_active: bool = Field(..., description="是否启用")
    sort_order: int = Field(..., description="排序顺序")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class DatabaseResponse(BaseModel):
    """数据库响应"""

    id: uuid.UUID = Field(..., description="数据库唯一标识")
    name: str = Field(..., description="数据库名称")
    code: str = Field(..., description="数据库代码(唯一标识符)")
    industry_id: uuid.UUID = Field(..., description="所属行业ID")
    database_type: DatabaseType = Field(..., description="数据库类型")
    data_source: DataSource = Field(..., description="数据来源")
    description: str | None = Field(None, description="数据库描述")
    is_active: bool = Field(..., description="是否启用")
    is_public: bool = Field(..., description="是否公开")
    sort_order: int = Field(..., description="排序顺序")
    documents_count: int = Field(..., description="文档数量")
    size_mb: float = Field(..., description="数据库大小(MB)")
    last_updated: datetime | None = Field(None, description="最后更新时间")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class IndustryListResponse(BaseModel):
    """行业列表响应"""

    industries: list[IndustryResponse] = Field(..., description="行业列表")
    total: int = Field(..., ge=0, description="总数量")
    limit: int = Field(..., ge=1, le=100, description="返回数量限制")
    offset: int = Field(..., ge=0, description="偏移量")
    has_more: bool = Field(..., description="是否有更多数据")


class DatabaseListResponse(BaseModel):
    """数据库列表响应"""

    databases: list[DatabaseResponse] = Field(..., description="数据库列表")
    total: int = Field(..., ge=0, description="总数量")
    limit: int = Field(..., ge=1, le=100, description="返回数量限制")
    offset: int = Field(..., ge=0, description="偏移量")
    has_more: bool = Field(..., description="是否有更多数据")


class IndustrySelectionResponse(BaseModel):
    """行业选择响应"""

    id: uuid.UUID = Field(..., description="选择记录ID")
    session_id: str = Field(..., description="会话ID")
    industry: IndustryResponse = Field(..., description="选择的行业")
    databases: list[DatabaseResponse] = Field(..., description="选择的数据库列表")
    selection_name: str | None = Field(None, description="选择名称")
    description: str | None = Field(None, description="选择描述")
    is_active: bool = Field(..., description="是否激活")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class IndustrySelectionListResponse(BaseModel):
    """行业选择列表响应"""

    selections: list[IndustrySelectionResponse] = Field(..., description="选择记录列表")
    total: int = Field(..., ge=0, description="总数量")
    limit: int = Field(..., ge=1, le=100, description="返回数量限制")
    offset: int = Field(..., ge=0, description="偏移量")
    has_more: bool = Field(..., description="是否有更多数据")


class IndustryValidationResponse(BaseModel):
    """行业选择验证响应"""

    is_valid: bool = Field(..., description="是否通过验证")
    errors: list[str] = Field(default_factory=list, description="验证错误列表")
    warnings: list[str] = Field(default_factory=list, description="验证警告列表")
    industry: IndustryResponse | None = Field(None, description="行业信息")
    databases: list[DatabaseResponse] = Field(default_factory=list, description="数据库信息列表")


class IndustryStatisticsResponse(BaseModel):
    """行业统计响应"""

    industry: IndustryResponse = Field(..., description="行业信息")
    total_databases: int = Field(..., ge=0, description="总数据库数量")
    active_databases: int = Field(..., ge=0, description="活跃数据库数量")
    public_databases: int = Field(..., ge=0, description="公开数据库数量")
    database_type_stats: dict[str, int] = Field(..., description="按类型统计")
    data_source_stats: dict[str, int] = Field(..., description="按来源统计")
    last_updated: datetime = Field(..., description="最后更新时间")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class SuccessResponse(BaseModel):
    """成功响应"""

    success: bool = Field(default=True, description="是否成功")
    message: str = Field(..., description="响应消息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="响应时间")


class DeleteResponse(BaseModel):
    """删除响应"""

    success: bool = Field(..., description="删除是否成功")
    message: str = Field(..., description="响应消息")
    deleted_id: uuid.UUID = Field(..., description="删除的记录ID")


# === 验证器 ===

class IndustrySelectionRequestValidator(IndustrySelectionRequest):
    """行业选择请求(带验证器)"""

    @field_validator("selection_name")
    @classmethod
    def validate_selection_name(cls, v: str | None) -> str | None:
        """验证选择名称"""
        if v:
            v = v.strip()
            if len(v) > 100:
                error_msg = "选择名称过长, 最多支持100个字符"
                raise ValueError(error_msg)
            return v
        return None

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证选择描述"""
        if v:
            v = v.strip()
            if len(v) > 500:
                error_msg = "选择描述过长, 最多支持500个字符"
                raise ValueError(error_msg)
            return v
        return None


class IndustrySelectionUpdateRequestValidator(IndustrySelectionUpdateRequest):
    """行业选择更新请求(带验证器)"""

    @field_validator("database_ids")
    @classmethod
    def validate_database_ids(cls, v: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        """验证数据库ID列表"""
        if v is not None:
            if len(v) == 0:
                error_msg = "数据库ID列表不能为空"
                raise ValueError(error_msg)
            if len(v) > 10:
                error_msg = "数据库ID列表过长, 最多支持10个"
                raise ValueError(error_msg)
        return v

    @field_validator("selection_name")
    @classmethod
    def validate_selection_name(cls, v: str | None) -> str | None:
        """验证选择名称"""
        if v:
            v = v.strip()
            if len(v) > 100:
                error_msg = "选择名称过长, 最多支持100个字符"
                raise ValueError(error_msg)
            return v
        return None

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证选择描述"""
        if v:
            v = v.strip()
            if len(v) > 500:
                error_msg = "选择描述过长, 最多支持500个字符"
                raise ValueError(error_msg)
            return v
        return None


# === 便捷函数 ===

def create_industry_response(industry_data: dict[str, Any]) -> IndustryResponse:
    """创建行业响应对象

    Args:
        industry_data: 行业数据字典

    Returns:
        IndustryResponse: 行业响应对象
    """
    return IndustryResponse(**industry_data)


def create_database_response(database_data: dict[str, Any]) -> DatabaseResponse:
    """创建数据库响应对象

    Args:
        database_data: 数据库数据字典

    Returns:
        DatabaseResponse: 数据库响应对象
    """
    return DatabaseResponse(**database_data)


def create_success_response(
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建成功响应

    Args:
        message: 成功消息
        data: 响应数据

    Returns:
        Dict[str, Any]: 成功响应字典
    """
    response = {
        "success": True,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if data:
        response["data"] = data
    return response


def create_error_response(
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """创建错误响应

    Args:
        error_code: 错误代码
        message: 错误消息
        details: 错误详情
        path: 请求路径

    Returns:
        Dict[str, Any]: 错误响应字典
    """
    response = {
        "success": False,
        "error": True,
        "error_code": error_code,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if details:
        response["details"] = details
    if path:
        response["path"] = path
    return response
