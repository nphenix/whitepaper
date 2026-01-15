"""
前端适配层 API Schema

定义前端适配层接口的请求和响应Schema.
统一响应格式:{ success: bool, data?: any, error?: string }

生成命令: /speckit.implement T249, T247
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import re
import uuid
from enum import Enum
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

# === 统一响应格式 ===


class FrontendResponse(BaseModel):
    """前端适配层统一响应格式"""

    success: bool = Field(..., description="操作是否成功")
    data: Any | None = Field(None, description="响应数据")
    error: str | None = Field(None, description="错误信息")


def create_success_response(data: Any = None, message: str | None = None) -> dict[str, Any]:
    """创建成功响应

    Args:
        data: 响应数据
        message: 成功消息(可选)

    Returns:
        成功响应字典
    """
    response: dict[str, Any] = {"success": True}
    if data is not None:
        response["data"] = data
    if message:
        response["message"] = message
    return response


def create_error_response(
    error: str,
    details: str | None = None,
    error_code: str | None = None
) -> dict[str, Any]:
    """创建错误响应

    Args:
        error: 错误信息
        details: 错误详情(可选)
        error_code: 错误代码(可选,用于程序化处理)

    Returns:
        错误响应字典
    """
    response: dict[str, Any] = {"success": False, "error": error}
    if details:
        response["details"] = details
    if error_code:
        response["error_code"] = error_code
    return response


# === 自定义验证器函数 ===


def validate_uuid_format(value: str, field_name: str = "ID") -> str:
    """验证UUID格式

    Args:
        value: 要验证的值
        field_name: 字段名称(用于错误消息)

    Returns:
        验证后的值

    Raises:
        ValueError: 如果格式无效
    """
    if not value or not value.strip():
        msg = f"{field_name}不能为空"
        raise ValueError(msg)

    value = value.strip()
    try:
        uuid.UUID(value)
    except ValueError:
        msg = f"{field_name}格式无效,必须是有效的UUID格式"
        raise ValueError(msg)

    return value


def validate_url_format(value: str) -> str:
    """验证URL格式

    Args:
        value: 要验证的URL

    Returns:
        验证后的URL

    Raises:
        ValueError: 如果URL格式无效
    """
    if not value or not value.strip():
        msg = "URL不能为空"
        raise ValueError(msg)

    value = value.strip()
    parsed = urlparse(value)

    if not parsed.scheme or not parsed.netloc:
        msg = "URL格式无效,必须包含协议(如http://或https://)和域名"
        raise ValueError(msg)

    if parsed.scheme not in ["http", "https"]:
        msg = "URL协议必须是http或https"
        raise ValueError(msg)

    return value


def validate_non_empty_string(value: str, field_name: str = "字段", min_length: int = 1, max_length: int | None = None) -> str:
    """验证非空字符串

    Args:
        value: 要验证的值
        field_name: 字段名称(用于错误消息)
        min_length: 最小长度
        max_length: 最大长度(可选)

    Returns:
        验证后的值(去除首尾空格)

    Raises:
        ValueError: 如果验证失败
    """
    if not value or not isinstance(value, str):
        msg = f"{field_name}不能为空"
        raise ValueError(msg)

    value = value.strip()

    if len(value) < min_length:
        msg = f"{field_name}长度不能少于{min_length}个字符"
        raise ValueError(msg)

    if max_length and len(value) > max_length:
        msg = f"{field_name}长度不能超过{max_length}个字符"
        raise ValueError(msg)

    return value


# === 大纲相关请求 ===


class OutlineCreateRequest(BaseModel):
    """创建大纲请求(前端格式)"""

    outlineText: str = Field(..., description="大纲文本内容", min_length=10, max_length=50000)
    config: dict[str, Any] | None = Field(None, description="配置信息(可选)")
    guide: str | None = Field(None, description="指南内容(Markdown格式,可选),创建大纲时自动保存")

    @field_validator("outlineText")
    @classmethod
    def validate_outline_text(cls, v: str) -> str:
        """验证大纲文本"""
        return validate_non_empty_string(v, "大纲文本", min_length=10, max_length=50000)

    @field_validator("config")
    @classmethod
    def validate_config(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """验证配置信息"""
        if v is None:
            return None

        # 验证配置中的特定字段
        if v.get("title"):
            if not isinstance(v["title"], str) or len(v["title"].strip()) == 0:
                msg = "配置中的title必须是非空字符串"
                raise ValueError(msg)
            if len(v["title"]) > 200:
                msg = "配置中的title长度不能超过200个字符"
                raise ValueError(msg)

        if v.get("industry_id"):
            validate_uuid_format(str(v["industry_id"]), "行业ID")

        if v.get("database_ids"):
            if not isinstance(v["database_ids"], list):
                msg = "配置中的database_ids必须是列表"
                raise ValueError(msg)
            for db_id in v["database_ids"]:
                validate_uuid_format(str(db_id), "数据库ID")

        return v


class OutlinePolishRequest(BaseModel):
    """大纲优化请求(前端格式)"""

    outlineText: str = Field(..., description="需要优化的大纲文本", min_length=10, max_length=50000)

    @field_validator("outlineText")
    @classmethod
    def validate_outline_text(cls, v: str) -> str:
        """验证大纲文本"""
        return validate_non_empty_string(v, "大纲文本", min_length=10, max_length=50000)


class OutlineCreateResponse(BaseModel):
    """创建大纲响应(前端格式)"""

    outlineId: str = Field(..., description="大纲ID")
    optimizedOutline: str | None = Field(None, description="优化后的大纲文本(可选)")


class OutlinePolishResponse(BaseModel):
    """大纲优化响应(前端格式)"""

    polishedOutline: str = Field(..., description="优化后的大纲文本")


# === 文件上传响应 ===


class FileUploadResponse(BaseModel):
    """文件上传响应(前端格式)"""

    file: dict[str, Any] = Field(..., description="上传的文件信息")
    filename: str | None = Field(None, description="文件名")
    path: str | None = Field(None, description="文件路径")
    size: int | None = Field(None, description="文件大小")


# === 草稿相关请求和响应 ===


class DraftGenerateRequest(BaseModel):
    """生成草稿请求(前端格式)"""

    outlineId: str = Field(..., description="大纲ID")
    config: dict[str, Any] | None = Field(None, description="配置信息(可选)")

    @field_validator("outlineId")
    @classmethod
    def validate_outline_id(cls, v: str) -> str:
        """验证大纲ID格式"""
        return validate_uuid_format(v, "大纲ID")

    @field_validator("config")
    @classmethod
    def validate_config(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """验证配置信息"""
        if v is None:
            return None

        # 验证报告类型
        if v.get("report_type"):
            if not isinstance(v["report_type"], str):
                msg = "配置中的report_type必须是字符串"
                raise ValueError(msg)
            valid_types = ["市场研究报告", "政策分析报告", "技术评估报告", "行业白皮书"]
            if v["report_type"] not in valid_types:
                msg = f"配置中的report_type必须是以下之一: {', '.join(valid_types)}"
                raise ValueError(msg)

        # 验证语言
        if v.get("language"):
            if not isinstance(v["language"], str):
                msg = "配置中的language必须是字符串"
                raise ValueError(msg)
            valid_languages = ["zh-CN", "en-US", "zh-TW"]
            if v["language"] not in valid_languages:
                msg = f"配置中的language必须是以下之一: {', '.join(valid_languages)}"
                raise ValueError(msg)

        # 验证风格
        if v.get("style"):
            if not isinstance(v["style"], str):
                msg = "配置中的style必须是字符串"
                raise ValueError(msg)
            valid_styles = ["专业", "通俗", "学术", "商务"]
            if v["style"] not in valid_styles:
                msg = f"配置中的style必须是以下之一: {', '.join(valid_styles)}"
                raise ValueError(msg)

        return v


class DraftResponse(BaseModel):
    """草稿响应(前端格式)"""

    draft: str = Field(..., description="草稿内容")
    sources: dict[str, Any] | None = Field(None, description="来源信息(可选)")


# === 来源管理请求和响应 ===


class SourceDetail(BaseModel):
    """来源详细信息(可选)"""

    title: str | None = Field(None, description="标题", max_length=500)
    authors: str | None = Field(None, description="作者", max_length=200)
    year: str | None = Field(None, description="年份")
    domain: str | None = Field(None, description="域名/来源", max_length=200)
    cited: int | None = Field(None, description="引用次数", ge=0)
    excerpt: str | None = Field(None, description="摘要/简介", max_length=1000)
    url: str | None = Field(None, description="链接(用于自定义URL)", max_length=2000)

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: str | None) -> str | None:
        """验证年份格式"""
        if v is None:
            return None

        v = v.strip()
        # 验证年份格式(4位数字,范围1900-2100)
        if not re.match(r"^\d{4}$", v):
            msg = "年份格式无效,必须是4位数字(如:2024)"
            raise ValueError(msg)

        year_int = int(v)
        if year_int < 1900 or year_int > 2100:
            msg = "年份必须在1900到2100之间"
            raise ValueError(msg)

        return v

    @field_validator("cited")
    @classmethod
    def validate_cited(cls, v: int | None) -> int | None:
        """验证引用次数"""
        if v is not None and v < 0:
            msg = "引用次数不能为负数"
            raise ValueError(msg)
        return v

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        """验证URL格式"""
        if v is None:
            return None
        return validate_url_format(v)


class SourceSelectionRequest(BaseModel):
    """来源选择请求(前端格式)"""

    selectedSources: list[int] = Field(default_factory=list, description="选中的来源ID列表")
    customUrls: list[str] = Field(default_factory=list, description="自定义URL列表", max_length=100)
    uploadedFiles: list[str] = Field(
        default_factory=list,
        description="上传文件的document_id(UUID字符串)列表，将写入 outline_sources(source_type=uploaded_file)",
        max_length=100,
    )
    sourceDetails: dict[str, SourceDetail] | None = Field(
        None,
        description="来源详细信息,key为source_id(字符串格式),value为来源详细信息对象."
        "用于在保存时存储完整的来源信息,以便后续获取时能够显示详细信息."
    )

    @field_validator("selectedSources")
    @classmethod
    def validate_selected_sources(cls, v: list[int]) -> list[int]:
        """验证选中的来源ID列表"""
        if len(v) > 100:
            msg = "选中的来源数量不能超过100个"
            raise ValueError(msg)

        # 验证ID都是正整数
        for source_id in v:
            if not isinstance(source_id, int) or source_id <= 0:
                msg = "来源ID必须是正整数"
                raise ValueError(msg)

        # 去重
        return list(set(v))

    @field_validator("customUrls")
    @classmethod
    def validate_custom_urls(cls, v: list[str]) -> list[str]:
        """验证自定义URL列表"""
        if len(v) > 100:
            msg = "自定义URL数量不能超过100个"
            raise ValueError(msg)

        # 验证每个URL格式
        validated_urls = []
        for url in v:
            validated_url = validate_url_format(url)
            validated_urls.append(validated_url)

        # 去重
        return list(set(validated_urls))

    @field_validator("uploadedFiles")
    @classmethod
    def validate_uploaded_files(cls, v: list[str]) -> list[str]:
        """验证上传文件document_id列表"""
        if len(v) > 100:
            msg = "上传文件数量不能超过100个"
            raise ValueError(msg)
        validated: list[str] = []
        for doc_id in v:
            validated.append(validate_uuid_format(str(doc_id), "上传文件document_id"))
        # 去重
        return list(set(validated))

    @model_validator(mode="after")
    def validate_at_least_one_source(self) -> "SourceSelectionRequest":
        """验证至少选择一个来源"""
        if not self.selectedSources and not self.customUrls and not self.uploadedFiles:
            msg = "至少需要选择一个来源(推荐文献或自定义URL)"
            raise ValueError(msg)
        return self


class SourceSelectionResponse(BaseModel):
    """来源选择响应(前端格式)"""

    sources: list[dict[str, Any]] = Field(default_factory=list, description="来源列表")


# === 历史记录响应 ===


class HistoryItem(BaseModel):
    """历史记录项"""

    id: str = Field(..., description="记录ID")
    title: str = Field(..., description="标题")
    date: str = Field(..., description="创建日期")
    hasDraft: bool = Field(False, description="是否有草稿")


class HistoryResponse(BaseModel):
    """历史记录响应(前端格式)"""

    history: list[HistoryItem] = Field(default_factory=list, description="历史记录列表")


# === AI 聊天相关请求和响应 ===


class ChatRequest(BaseModel):
    """AI 聊天请求(前端格式)"""

    message: str = Field(..., description="用户消息", min_length=1, max_length=2000)
    outlineId: str | None = Field(None, description="大纲ID(可选,用于上下文关联)")
    enableContext: bool = Field(True, description="是否启用上下文记忆(默认启用)")
    topK: int | None = Field(5, description="RAG检索返回的文档数量(默认5)", ge=1, le=20)
    stream: bool = Field(False, description="是否使用流式响应(默认False)")

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """验证用户消息"""
        return validate_non_empty_string(v, "用户消息", min_length=1, max_length=2000)

    @field_validator("outlineId")
    @classmethod
    def validate_outline_id(cls, v: str | None) -> str | None:
        """验证大纲ID格式"""
        if v is None:
            return None
        return validate_uuid_format(v, "大纲ID")

    @field_validator("topK")
    @classmethod
    def validate_top_k(cls, v: int | None) -> int | None:
        """验证topK参数"""
        if v is not None:
            if v < 1:
                msg = "topK必须大于等于1"
                raise ValueError(msg)
            if v > 20:
                msg = "topK不能超过20"
                raise ValueError(msg)
        return v


class ChatResponse(BaseModel):
    """AI 聊天响应(前端格式)"""

    response: str = Field(..., description="AI回复内容")
    timestamp: str = Field(..., description="响应时间戳")
    sources: list[dict[str, Any]] | None = Field(
        None, description="检索到的相关文档来源(可选)"
    )


# === 白皮书分析相关请求和响应 ===


class AnalyzeWhitepaperRequest(BaseModel):
    """白皮书分析请求(前端格式)"""

    draft_id: str | None = Field(None, description="草稿ID(可选,如果提供则从草稿获取内容)")
    content: str | None = Field(None, description="白皮书内容(可选,如果未提供draft_id则必需)", max_length=1000000)

    @field_validator("draft_id")
    @classmethod
    def validate_draft_id(cls, v: str | None) -> str | None:
        """验证草稿ID格式"""
        if v is None:
            return None
        return validate_uuid_format(v, "草稿ID")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str | None) -> str | None:
        """验证白皮书内容"""
        if v is not None:
            if len(v.strip()) < 100:
                msg = "白皮书内容长度不能少于100个字符"
                raise ValueError(msg)
            if len(v) > 1000000:
                msg = "白皮书内容长度不能超过1000000个字符"
                raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_at_least_one_provided(self) -> "AnalyzeWhitepaperRequest":
        """验证至少提供draft_id或content之一"""
        if not self.draft_id and not self.content:
            msg = "必须提供draft_id或content参数之一"
            raise ValueError(msg)
        return self


class ContentQualityAssessment(BaseModel):
    """内容质量评估"""

    depth_score: float = Field(..., ge=0.0, le=10.0, description="论述深度评分(0-10分)")
    comprehensiveness_score: float = Field(..., ge=0.0, le=10.0, description="全面性评分(0-10分)")
    data_support_score: float = Field(..., ge=0.0, le=10.0, description="数据支撑评分(0-10分)")
    depth_comment: str = Field(..., description="深度评估说明")
    comprehensiveness_comment: str = Field(..., description="全面性评估说明")
    data_support_comment: str = Field(..., description="数据支撑评估说明")


class StructureAnalysis(BaseModel):
    """结构分析"""

    organization_score: float = Field(..., ge=0.0, le=10.0, description="章节安排评分(0-10分)")
    coherence_score: float = Field(..., ge=0.0, le=10.0, description="逻辑连贯性评分(0-10分)")
    emphasis_score: float = Field(..., ge=0.0, le=10.0, description="重点突出程度评分(0-10分)")
    organization_comment: str = Field(..., description="章节安排评估说明")
    coherence_comment: str = Field(..., description="逻辑连贯性评估说明")
    emphasis_comment: str = Field(..., description="重点突出程度评估说明")


class CredibilityAssessment(BaseModel):
    """专业性与可信度评估"""

    terminology_score: float = Field(..., ge=0.0, le=10.0, description="术语使用准确性评分(0-10分)")
    citation_score: float = Field(..., ge=0.0, le=10.0, description="引用文献质量评分(0-10分)")
    insight_score: float = Field(..., ge=0.0, le=10.0, description="行业洞察深度评分(0-10分)")
    terminology_comment: str = Field(..., description="术语使用评估说明")
    citation_comment: str = Field(..., description="引用文献评估说明")
    insight_comment: str = Field(..., description="行业洞察评估说明")


class ImprovementSuggestion(BaseModel):
    """改进建议项"""

    category: str = Field(..., description="建议类别(如:内容补充,结构优化,表达改进等)")
    priority: str = Field(..., description="优先级(高,中,低)")
    suggestion: str = Field(..., description="具体建议内容")
    location: str | None = Field(None, description="建议位置(如章节名称)")


class AnalyzeWhitepaperResponse(BaseModel):
    """白皮书分析响应(前端格式)"""

    content_quality: ContentQualityAssessment = Field(..., description="内容质量评估")
    structure_analysis: StructureAnalysis = Field(..., description="结构分析")
    credibility: CredibilityAssessment = Field(..., description="专业性与可信度评估")
    improvement_suggestions: list[ImprovementSuggestion] = Field(..., description="改进建议列表")
    overall_score: float = Field(..., ge=1.0, le=10.0, description="综合评分(1-10分)")
    summary: str = Field(..., description="分析摘要")
    strengths: list[str] = Field(..., description="优点列表")
    weaknesses: list[str] = Field(..., description="待改进点列表")
    timestamp: str = Field(..., description="分析时间戳")


# === 工作流状态管理相关请求和响应 ===


class WorkflowStepStatus(str, Enum):
    """工作流步骤状态枚举"""
    PENDING = "pending"  # 待处理
    COMPLETED = "completed"  # 已完成


class WorkflowCurrentStatus(str, Enum):
    """工作流当前状态枚举"""
    STEP1_SELECTED = "step1_selected"  # 步骤1:行业和数据库选择完成
    STEP2_OPTIMIZED = "step2_optimized"  # 步骤2:大纲优化完成
    STEP3_SOURCES_SELECTED = "step3_sources_selected"  # 步骤3:来源选择完成
    STEP4_GENERATED = "step4_generated"  # 步骤4:草稿生成完成


class WorkflowStatusResponse(BaseModel):
    """工作流状态响应(前端格式)"""

    workflowId: str = Field(..., description="工作流ID")
    currentStatus: str = Field(..., description="当前状态")
    step1Status: str = Field(..., description="步骤1状态")
    step2Status: str = Field(..., description="步骤2状态")
    step3Status: str = Field(..., description="步骤3状态")
    step4Status: str = Field(..., description="步骤4状态")
    stepData: dict[str, Any] = Field(default_factory=dict, description="步骤数据(用于数据传递)")
    createdAt: str = Field(..., description="创建时间")
    updatedAt: str = Field(..., description="更新时间")


class UpdateWorkflowStepRequest(BaseModel):
    """更新工作流步骤状态请求(前端格式)"""

    status: str = Field(..., description="步骤状态:pending 或 completed")
    stepData: dict[str, Any] | None = Field(None, description="步骤数据(可选,用于数据传递)")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """验证步骤状态"""
        valid_statuses = ["pending", "completed"]
        if v not in valid_statuses:
            msg = f"步骤状态必须是以下之一: {', '.join(valid_statuses)}"
            raise ValueError(msg)
        return v


# === 用户反馈相关请求和响应 ===


class UserFeedbackRequest(BaseModel):
    """用户反馈请求(前端格式)"""

    error_code: str | None = Field(None, description="错误代码(如果有)", max_length=50)
    error_message: str = Field(..., description="错误消息或问题描述", min_length=1, max_length=500)
    user_feedback: str = Field(..., description="用户反馈内容", min_length=1, max_length=2000)
    metadata: dict[str, Any] | None = Field(None, description="额外的元数据(可选)")

    @field_validator("error_message")
    @classmethod
    def validate_error_message(cls, v: str) -> str:
        """验证错误消息"""
        return validate_non_empty_string(v, "错误消息", min_length=1, max_length=500)

    @field_validator("user_feedback")
    @classmethod
    def validate_user_feedback(cls, v: str) -> str:
        """验证用户反馈内容"""
        return validate_non_empty_string(v, "用户反馈", min_length=1, max_length=2000)


class UserFeedbackResponse(BaseModel):
    """用户反馈响应(前端格式)"""

    success: bool = Field(..., description="是否成功收集反馈")
    message: str | None = Field(None, description="响应消息")
