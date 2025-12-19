"""
文档相关API Schema

定义文档上传、预处理、查询等API的请求和响应Schema。
使用Pydantic进行数据验证。

生成命令: /speckit.implement T035
生成时间: 2025-12-17
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator


class DocumentFormat(str, Enum):
    """文档格式枚举"""

    PDF = "pdf"
    HTML = "html"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"


class DocumentStatus(str, Enum):
    """文档处理状态枚举"""

    PENDING = "pending"
    PARSING = "parsing"
    INDEXED = "indexed"
    FAILED = "failed"


class ProcessingStatus(str, Enum):
    """预处理状态枚举"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CleaningLevel(str, Enum):
    """清洗级别枚举"""

    BASIC = "basic"
    STANDARD = "standard"
    DEEP = "deep"


# === 请求Schema ===


class DocumentUploadRequest(BaseModel):
    """文档上传请求"""

    format: DocumentFormat | None = Field(
        None, description="文档格式(可选, 如果不指定则自动识别)"
    )
    enable_chart_conversion: bool | None = Field(
        default=True, description="是否启用图表转换功能"
    )
    cleaning_level: CleaningLevel | None = Field(
        default=CleaningLevel.STANDARD, description="清洗级别"
    )
    use_async: bool | None = Field(default=False, description="是否使用异步处理")
    metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="附加元数据"
    )


class DocumentProcessRequest(BaseModel):
    """文档处理请求"""

    document_id: uuid.UUID = Field(..., description="文档ID")
    enable_chart_conversion: bool | None = Field(
        default=True, description="是否启用图表转换功能"
    )
    cleaning_level: CleaningLevel | None = Field(
        default=CleaningLevel.STANDARD, description="清洗级别"
    )
    use_async: bool | None = Field(default=False, description="是否使用异步处理")


class BatchDocumentProcessRequest(BaseModel):
    """批量文档处理请求"""

    document_ids: list[uuid.UUID] = Field(
        default=..., min_length=1, max_length=50, description="文档ID列表(最多50个)"
    )
    enable_chart_conversion: bool | None = Field(
        default=True, description="是否启用图表转换功能"
    )
    cleaning_level: CleaningLevel | None = Field(
        default=CleaningLevel.STANDARD, description="清洗级别"
    )
    batch_size: int | None = Field(default=10, ge=1, le=20, description="批量处理大小")


class DocumentQueryRequest(BaseModel):
    """文档查询请求"""

    status: DocumentStatus | None = Field(None, description="文档状态过滤")
    format: DocumentFormat | None = Field(None, description="文档格式过滤")
    uploaded_by: uuid.UUID | None = Field(None, description="上传用户ID过滤")
    start_date: datetime | None = Field(None, description="开始日期过滤")
    end_date: datetime | None = Field(None, description="结束日期过滤")
    limit: int | None = Field(default=20, ge=1, le=100, description="返回数量限制")
    offset: int | None = Field(default=0, ge=0, description="偏移量")
    search: str | None = Field(
        None, min_length=1, max_length=100, description="搜索关键词"
    )


class DocumentDeleteRequest(BaseModel):
    """文档删除请求"""

    force: bool | None = Field(default=False, description="是否强制删除(包括处理结果)")


# === 响应Schema ===


class FormatInfo(BaseModel):
    """格式信息"""

    format: str = Field(..., description="检测到的格式")
    mime_type: str = Field(..., description="MIME类型")
    extension: str = Field(..., description="文件扩展名")
    confidence: float = Field(..., ge=0.0, le=1.0, description="检测置信度")


class DocumentMetadata(BaseModel):
    """文档元数据"""

    file_size: int = Field(..., gt=0, description="文件大小(字节)")
    mime_type: str | None = Field(None, description="MIME类型")
    format_info: FormatInfo | None = Field(None, description="格式信息")
    uploaded_at: datetime = Field(..., description="上传时间")
    parsed_at: datetime | None = Field(None, description="解析完成时间")
    processing_duration: float | None = Field(None, description="处理持续时间(秒)")
    error_message: str | None = Field(None, description="错误信息")
    quality_score: float | None = Field(
        None, ge=0.0, le=1.0, description="处理质量评分"
    )
    custom_metadata: dict[str, Any] | None = Field(
        default_factory=dict, description="自定义元数据"
    )


class DocumentResponse(BaseModel):
    """文档响应"""

    id: uuid.UUID = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    status: DocumentStatus = Field(..., description="文档状态")
    format: DocumentFormat = Field(..., description="文档格式")
    uploaded_by: uuid.UUID = Field(..., description="上传用户ID")
    metadata: DocumentMetadata = Field(..., description="文档元数据")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""

    document: DocumentResponse = Field(..., description="文档信息")
    processing_task_id: str | None = Field(None, description="异步处理任务ID")
    message: str = Field(..., description="响应消息")


class DocumentProcessResponse(BaseModel):
    """文档处理响应"""

    document: DocumentResponse = Field(..., description="文档信息")
    processing_result: dict[str, Any] | None = Field(None, description="处理结果详情")
    processing_task_id: str | None = Field(None, description="异步处理任务ID")
    message: str = Field(..., description="响应消息")


class ProcessingStatistics(BaseModel):
    """处理统计信息"""

    total_documents: int = Field(..., ge=0, description="总文档数")
    successful_documents: int = Field(..., ge=0, description="成功处理文档数")
    failed_documents: int = Field(..., ge=0, description="失败处理文档数")
    total_processing_time: float = Field(..., ge=0.0, description="总处理时间(秒)")
    average_processing_time: float | None = Field(
        None, ge=0.0, description="平均处理时间(秒)"
    )
    charts_converted: int | None = Field(None, ge=0, description="转换的图表数量")


class BatchDocumentProcessResponse(BaseModel):
    """批量文档处理响应"""

    task_id: str = Field(..., description="批量处理任务ID")
    statistics: ProcessingStatistics = Field(..., description="处理统计信息")
    results: list[DocumentProcessResponse] = Field(..., description="各文档的处理结果")
    message: str = Field(..., description="响应消息")


class DocumentListResponse(BaseModel):
    """文档列表响应"""

    documents: list[DocumentResponse] = Field(..., description="文档列表")
    total: int = Field(..., ge=0, description="总数量")
    limit: int = Field(..., ge=1, le=100, description="返回数量限制")
    offset: int = Field(..., ge=0, description="偏移量")
    has_more: bool = Field(..., description="是否有更多数据")


class DocumentDeleteResponse(BaseModel):
    """文档删除响应"""

    document_id: uuid.UUID = Field(..., description="删除的文档ID")
    success: bool = Field(..., description="删除是否成功")
    message: str = Field(..., description="响应消息")


class DocumentValidationResponse(BaseModel):
    """文档验证响应"""

    is_valid: bool = Field(..., description="是否通过验证")
    errors: list[str] = Field(default_factory=list, description="验证错误列表")
    warnings: list[str] = Field(default_factory=list, description="验证警告列表")
    format_info: FormatInfo | None = Field(None, description="格式信息")


class ProcessingProgressResponse(BaseModel):
    """处理进度响应"""

    task_id: str = Field(..., description="任务ID")
    status: ProcessingStatus = Field(..., description="处理状态")
    progress: float = Field(..., ge=0.0, le=1.0, description="进度百分比")
    current_step: str | None = Field(None, description="当前处理步骤")
    estimated_remaining_time: int | None = Field(None, description="预估剩余时间(秒)")
    error_message: str | None = Field(None, description="错误信息")
    result: dict[str, Any] | None = Field(None, description="处理结果(完成时)")


class ChartConversionResult(BaseModel):
    """图表转换结果"""

    image_path: str = Field(..., description="图片路径")
    is_chart: bool = Field(..., description="是否为图表")
    chart_type: str | None = Field(None, description="图表类型")
    json_path: str | None = Field(None, description="转换后的JSON文件路径")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="识别置信度")
    error_message: str | None = Field(None, description="错误信息")


class DocumentProcessingDetail(BaseModel):
    """文档处理详情"""

    document_id: uuid.UUID = Field(..., description="文档ID")
    processing_steps: list[str] = Field(..., description="处理步骤列表")
    step_details: dict[str, Any] = Field(default_factory=dict, description="步骤详情")
    chart_conversions: list[ChartConversionResult] = Field(
        default_factory=list, description="图表转换结果"
    )
    quality_metrics: dict[str, Any] = Field(
        default_factory=dict, description="质量指标"
    )
    performance_metrics: dict[str, Any] = Field(
        default_factory=dict, description="性能指标"
    )


class ErrorResponse(BaseModel):
    """错误响应"""

    error: bool = Field(default=True, description="是否为错误")
    error_code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: dict[str, Any] | None = Field(None, description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="错误时间")
    path: str | None = Field(None, description="请求路径")


# === 验证器 ===


class DocumentUploadRequestValidator(DocumentUploadRequest):
    """文档上传请求(带验证器)"""

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: DocumentFormat | None) -> DocumentFormat | None:
        """验证文档格式"""
        # 这里可以添加额外的格式验证逻辑
        return v

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v: dict[str, Any]) -> dict[str, Any]:
        """验证元数据"""
        # 限制元数据大小
        if len(str(v)) > 10000:  # 10KB限制
            error_msg = "元数据过大, 最多支持10KB"
            raise ValueError(error_msg)
        return v


class DocumentQueryRequestValidator(DocumentQueryRequest):
    """文档查询请求(带验证器)"""

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: datetime | None, info: Any) -> datetime | None:
        """验证日期范围"""
        if v and info.data.get("start_date") and v <= info.data["start_date"]:
            error_msg = "结束日期必须晚于开始日期"
            raise ValueError(error_msg)
        return v

    @field_validator("search")
    @classmethod
    def validate_search(cls, v: str | None) -> str | None:
        """验证搜索关键词"""
        if v:
            # 移除特殊字符
            import re

            v = re.sub(r'[<>:"/\\|?*]', "", v)
            if not v.strip():
                error_msg = "搜索关键词不能为空"
                raise ValueError(error_msg)
        return v.strip() if v else None


# === 便捷函数 ===


def create_error_response(
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    path: str | None = None,
) -> ErrorResponse:
    """创建错误响应

    Args:
        error_code: 错误代码
        message: 错误消息
        details: 错误详情
        path: 请求路径

    Returns:
        ErrorResponse: 错误响应对象
    """
    return ErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        path=path,
    )


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
