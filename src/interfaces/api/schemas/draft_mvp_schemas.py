"""
草稿相关API Schema

定义草稿生成,查询,更新等API的请求和响应Schema.
使用Pydantic进行数据验证.

生成命令: /speckit.implement T240
生成时间: 2025-12-25
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.domain.agent.draft import DraftSectionType, DraftStatus


class SortOrder(str, Enum):
    """排序方向枚举"""

    ASC = "asc"
    DESC = "desc"


class SortBy(str, Enum):
    """排序字段枚举"""

    TITLE = "title"
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    STATUS = "status"


# === 请求Schema ===


class DraftGenerateRequest(BaseModel):
    """草稿生成请求"""

    optimized_outline_id: uuid.UUID = Field(..., description="优化后的大纲ID")
    industry_id: uuid.UUID = Field(..., description="行业ID")
    database_ids: list[uuid.UUID] = Field(
        default_factory=list, description="数据库ID列表"
    )
    report_type: str | None = Field(
        None, description="报告类型(如:市场研究报告)"
    )
    language: str | None = Field(None, description="报告语言(默认:中文)")
    style: str | None = Field(None, description="写作风格(默认:专业,客观,数据驱动)")


class DraftUpdateRequest(BaseModel):
    """草稿更新请求"""

    title: str | None = Field(None, min_length=1, max_length=200, description="草稿标题")
    description: str | None = Field(None, max_length=500, description="草稿描述")
    status: DraftStatus | None = Field(None, description="草稿状态")


class DraftListRequest(BaseModel):
    """草稿列表查询请求"""

    outline_id: uuid.UUID | None = Field(None, description="大纲ID(筛选)")
    industry_id: uuid.UUID | None = Field(None, description="行业ID(筛选)")
    status: DraftStatus | None = Field(None, description="状态(筛选)")
    page: int = Field(1, ge=1, description="页码(从1开始)")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")
    sort_by: SortBy = Field(SortBy.CREATED_AT, description="排序字段")
    sort_order: SortOrder = Field(SortOrder.DESC, description="排序方向")


class DraftQualityAssessmentRequest(BaseModel):
    """草稿质量评估请求"""

    use_llm: bool = Field(True, description="是否使用LLM进行逻辑一致性评估")


class DraftHTMLExportRequest(BaseModel):
    """草稿HTML导出请求"""

    draft_id: uuid.UUID | None = Field(None, description="草稿ID（优先级高于outline_id）")
    outline_id: uuid.UUID | None = Field(None, description="大纲ID（导出该大纲下最新草稿）")
    output_dir: str = Field("data/output/final", description="输出目录")
    filename: str | None = Field(None, description="输出文件名（可选）")
    datajson_dir: str | None = Field(None, description="datajson目录路径（可选）")
    include_appendix: bool = Field(True, description="是否包含附录数据表格")


# === 响应Schema ===


class DraftSectionResponse(BaseModel):
    """草稿章节响应"""

    id: uuid.UUID = Field(..., description="章节ID")
    parent_id: uuid.UUID | None = Field(None, description="父级章节ID")
    section_type: DraftSectionType = Field(..., description="章节类型")
    level: int = Field(..., description="章节层级")
    title: str | None = Field(None, description="章节标题")
    content: str = Field(..., description="章节内容")
    order: int = Field(..., description="排序顺序")
    source_references: list[uuid.UUID] = Field(
        default_factory=list, description="信息源引用ID列表"
    )
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class DraftResponse(BaseModel):
    """草稿响应"""

    id: uuid.UUID = Field(..., description="草稿ID")
    title: str = Field(..., description="草稿标题")
    description: str | None = Field(None, description="草稿描述")
    outline_id: uuid.UUID = Field(..., description="关联的大纲ID")
    industry_id: uuid.UUID = Field(..., description="所属行业ID")
    database_ids: list[uuid.UUID] = Field(
        default_factory=list, description="使用的数据库ID列表"
    )
    status: DraftStatus = Field(..., description="草稿状态")
    sections: list[DraftSectionResponse] = Field(
        default_factory=list, description="章节列表"
    )
    current_version: int = Field(..., description="当前版本号")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class DraftGenerateResponse(BaseModel):
    """草稿生成响应"""

    draft: DraftResponse = Field(..., description="生成的草稿")
    draft_id: str = Field(..., description="草稿ID(字符串格式)")
    title: str = Field(..., description="草稿标题")
    status: str = Field(..., description="草稿状态")
    total_sections: int = Field(..., description="章节总数")
    created_at: str = Field(..., description="创建时间(ISO格式)")


class DraftDetailResponse(BaseModel):
    """草稿详情响应"""

    draft: DraftResponse = Field(..., description="草稿详情")
    statistics: dict[str, Any] = Field(default_factory=dict, description="统计信息")


class DraftListResponse(BaseModel):
    """草稿列表响应"""

    drafts: list[DraftResponse] = Field(..., description="草稿列表")
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    total_pages: int = Field(..., description="总页数")


class QualityScoreResponse(BaseModel):
    """质量评分响应"""

    dimension: str = Field(..., description="质量维度")
    score: float = Field(..., ge=0.0, le=1.0, description="评分(0-1)")
    description: str = Field(..., description="评分说明")


class ImprovementSuggestionResponse(BaseModel):
    """改进建议响应"""

    dimension: str = Field(..., description="质量维度")
    priority: str = Field(..., description="优先级(high/medium/low)")
    suggestion: str = Field(..., description="改进建议")
    affected_sections: list[str] = Field(
        default_factory=list, description="受影响的章节ID列表"
    )


class DraftQualityAssessmentResponse(BaseModel):
    """草稿质量评估响应"""

    overall_score: float = Field(..., ge=0.0, le=1.0, description="总体评分(0-1)")
    dimension_scores: list[QualityScoreResponse] = Field(
        ..., description="各维度评分列表"
    )
    improvement_suggestions: list[ImprovementSuggestionResponse] = Field(
        ..., description="改进建议列表"
    )
    summary: str = Field(..., description="评估摘要")
    details: dict[str, Any] = Field(
        default_factory=dict, description="详细评估信息"
    )


class DraftUpdateResponse(BaseModel):
    """草稿更新响应"""

    draft: DraftResponse = Field(..., description="更新后的草稿")
    updated_at: str = Field(..., description="更新时间(ISO格式)")


class DeleteResponse(BaseModel):
    """删除响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    draft_id: str | None = Field(None, description="草稿ID")


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str = Field(..., description="错误消息")
    detail: str | None = Field(None, description="错误详情")
    code: str | None = Field(None, description="错误代码")


class DraftHTMLExportResponse(BaseModel):
    """草稿HTML导出响应"""

    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    draft_id: str | None = Field(None, description="草稿ID")
    outline_id: str | None = Field(None, description="大纲ID")
    file_path: str = Field(..., description="生成的HTML文件路径")
    file_url: str | None = Field(None, description="文件URL（如果支持）")


# === 便利函数 ===


def create_success_response(message: str = "操作成功") -> dict[str, Any]:
    """创建成功响应

    Args:
        message: 成功消息

    Returns:
        成功响应字典
    """
    return {"success": True, "message": message}


def create_error_response(
    error: str, detail: str | None = None, code: str | None = None
) -> ErrorResponse:
    """创建错误响应

    Args:
        error: 错误消息
        detail: 错误详情
        code: 错误代码

    Returns:
        错误响应对象
    """
    return ErrorResponse(error=error, detail=detail, code=code)

