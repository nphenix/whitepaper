"""
大纲相关API Schema

定义大纲输入,大纲查询,大纲更新等API的请求和响应Schema.
使用Pydantic进行数据验证.

生成命令: /speckit.implement T212
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator

from src.domain.agent.outline import OutlineItemType, OutlineStatus


class SortOrder(str, Enum):
    """排序方向枚举"""

    ASC = "asc"
    DESC = "desc"


class SortBy(str, Enum):
    """排序字段枚举"""

    TITLE = "title"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    CURRENT_VERSION = "current_version"


# === 请求Schema ===


class OutlineCreateFromTextRequest(BaseModel):
    """从文本创建大纲请求"""

    title: str = Field(..., min_length=1, max_length=200, description="大纲标题")
    text: str = Field(..., min_length=1, description="大纲文本(支持Markdown格式)")
    industry_id: uuid.UUID = Field(..., description="所属行业ID")
    database_ids: list[uuid.UUID] = Field(
        default_factory=list, description="数据库ID列表"
    )
    description: str | None = Field(None, max_length=500, description="大纲描述")
    session_id: str | None = Field(None, description="会话ID(可选)")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题"""
        return v.strip()

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """验证文本"""
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v:
            v = v.strip()
            return v if v else None
        return None


class OutlineCreateFromStructureRequest(BaseModel):
    """从结构化数据创建大纲请求"""

    title: str = Field(..., min_length=1, max_length=200, description="大纲标题")
    structure: list[dict[str, Any]] = Field(
        ..., min_length=1, description="结构化大纲数据"
    )
    industry_id: uuid.UUID = Field(..., description="所属行业ID")
    database_ids: list[uuid.UUID] = Field(
        default_factory=list, description="数据库ID列表"
    )
    description: str | None = Field(None, max_length=500, description="大纲描述")
    session_id: str | None = Field(None, description="会话ID(可选)")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题"""
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v:
            v = v.strip()
            return v if v else None
        return None


class OutlineDetailRequest(BaseModel):
    """大纲详情请求"""

    outline_id: uuid.UUID = Field(..., description="大纲ID")


class OutlineUpdateRequest(BaseModel):
    """大纲更新请求"""

    title: str | None = Field(None, min_length=1, max_length=200, description="新标题")
    description: str | None = Field(None, max_length=500, description="新描述")
    items: list[dict[str, Any]] | None = Field(None, description="新大纲项列表")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        """验证标题"""
        if v:
            v = v.strip()
            return v if v else None
        return None

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v:
            v = v.strip()
            return v if v else None
        return None


class OutlineItemCreateRequest(BaseModel):
    """大纲项创建请求"""

    parent_id: uuid.UUID | None = Field(None, description="父级大纲项ID(可选)")
    item_type: OutlineItemType = Field(..., description="大纲项类型")
    title: str = Field(..., min_length=1, max_length=200, description="大纲项标题")
    level: int = Field(..., ge=1, le=6, description="大纲项层级")
    description: str | None = Field(None, max_length=1000, description="大纲项描述")
    order: int = Field(default=0, ge=0, description="排序顺序")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题"""
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v:
            v = v.strip()
            return v if v else None
        return None


class OutlineItemUpdateRequest(BaseModel):
    """大纲项更新请求"""

    title: str | None = Field(None, min_length=1, max_length=200, description="新标题")
    description: str | None = Field(None, max_length=1000, description="新描述")
    order: int | None = Field(None, ge=0, description="新排序顺序")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        """验证标题"""
        if v:
            v = v.strip()
            return v if v else None
        return None

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v:
            v = v.strip()
            return v if v else None
        return None


class OutlineItemDeleteRequest(BaseModel):
    """大纲项删除请求"""

    outline_id: uuid.UUID = Field(..., description="大纲ID")
    item_id: uuid.UUID = Field(..., description="大纲项ID")


class OutlineListRequest(BaseModel):
    """大纲列表请求"""

    industry_id: uuid.UUID | None = Field(None, description="所属行业ID过滤条件")
    status: OutlineStatus | None = Field(None, description="状态过滤条件")
    sort_by: SortBy | None = Field(SortBy.CREATED_AT, description="排序字段")
    sort_order: SortOrder | None = Field(
        SortOrder.DESC, description="排序方向(asc/desc)"
    )
    limit: int = Field(default=50, ge=1, le=100, description="返回数量限制")
    offset: int = Field(default=0, ge=0, description="偏移量")


class OutlineDeleteRequest(BaseModel):
    """大纲删除请求"""

    outline_id: uuid.UUID = Field(..., description="大纲ID")


# === 响应Schema ===


class OutlineItemResponse(BaseModel):
    """大纲项响应"""

    id: uuid.UUID = Field(..., description="大纲项唯一标识")
    parent_id: uuid.UUID | None = Field(None, description="父级大纲项ID")
    item_type: OutlineItemType = Field(..., description="大纲项类型")
    level: int = Field(..., description="大纲项层级")
    title: str = Field(..., description="大纲项标题")
    description: str | None = Field(None, description="大纲项描述")
    order: int = Field(..., description="排序顺序")
    is_optimized: bool = Field(default=False, description="是否经过AI优化")
    original_title: str | None = Field(None, description="优化前的原始标题")
    original_description: str | None = Field(None, description="优化前的原始描述")
    optimization_suggestions: list[str] = Field(
        default_factory=list, description="AI优化建议列表"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class OutlineResponse(BaseModel):
    """大纲响应"""

    id: uuid.UUID = Field(..., description="大纲唯一标识")
    title: str = Field(..., description="大纲标题")
    description: str | None = Field(None, description="大纲描述")
    industry_id: uuid.UUID = Field(..., description="所属行业ID")
    database_ids: list[uuid.UUID] = Field(
        default_factory=list, description="使用的数据库ID列表"
    )
    status: OutlineStatus = Field(..., description="大纲状态")
    items: list[OutlineItemResponse] = Field(
        default_factory=list, description="大纲项列表"
    )
    current_version: int = Field(..., description="当前版本号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class OutlineTreeResponse(BaseModel):
    """大纲树响应"""

    outline_id: uuid.UUID = Field(..., description="大纲ID")
    title: str = Field(..., description="大纲标题")
    description: str | None = Field(None, description="大纲描述")
    status: OutlineStatus = Field(..., description="大纲状态")
    tree: list[dict[str, Any]] = Field(..., description="大纲树结构")
    total_items: int = Field(..., ge=0, description="大纲项总数")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class OutlineCreateResponse(BaseModel):
    """大纲创建响应"""

    outline: OutlineResponse = Field(..., description="大纲信息")
    outline_id: str = Field(..., description="大纲ID")
    title: str = Field(..., description="大纲标题")
    status: str = Field(..., description="大纲状态")
    total_items: int = Field(..., ge=0, description="大纲项总数")
    created_at: str = Field(..., description="创建时间")
    session_id: str | None = Field(None, description="会话ID")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class OutlineListResponse(BaseModel):
    """大纲列表响应"""

    outlines: list[dict[str, Any]] = Field(..., description="大纲列表")
    total: int = Field(..., ge=0, description="总数量")
    limit: int = Field(..., ge=1, le=100, description="返回数量限制")
    offset: int = Field(..., ge=0, description="偏移量")
    has_more: bool = Field(..., description="是否有更多数据")


class OutlineDetailResponse(BaseModel):
    """大纲详情响应"""

    outline: OutlineResponse = Field(..., description="大纲信息")
    outline_id: str = Field(..., description="大纲ID")
    title: str = Field(..., description="大纲标题")
    description: str | None = Field(None, description="大纲描述")
    status: str = Field(..., description="大纲状态")
    total_items: int = Field(..., ge=0, description="大纲项总数")
    current_version: int = Field(..., description="当前版本号")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")


class OutlineItemCreateResponse(BaseModel):
    """大纲项创建响应"""

    item: OutlineItemResponse = Field(..., description="大纲项信息")
    item_id: str = Field(..., description="大纲项ID")
    outline_id: str = Field(..., description="大纲ID")


class OutlineItemUpdateResponse(BaseModel):
    """大纲项更新响应"""

    item: OutlineItemResponse = Field(..., description="大纲项信息")
    item_id: str = Field(..., description="大纲项ID")
    outline_id: str = Field(..., description="大纲ID")


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


# === 便捷函数 ===


def create_outline_response(outline_data: dict[str, Any]) -> OutlineResponse:
    """创建大纲响应对象

    Args:
        outline_data: 大纲数据字典

    Returns:
        OutlineResponse: 大纲响应对象
    """
    return OutlineResponse(**outline_data)


def create_outline_item_response(item_data: dict[str, Any]) -> OutlineItemResponse:
    """创建大纲项响应对象

    Args:
        item_data: 大纲项数据字典

    Returns:
        OutlineItemResponse: 大纲项响应对象
    """
    return OutlineItemResponse(**item_data)


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
