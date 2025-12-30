"""
预处理文档领域模型

该模块定义了预处理后的文档领域模型, 包括清洗后的内容,处理信息和验证规则.
"""

# 生成命令: /speckit.implement T024
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

# Document和DocumentFormat在当前模块中未使用, 但保留导入以备将来扩展
# from .document import Document, DocumentFormat


class ProcessingStatus(str, Enum):
    """文档处理状态枚举"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CleaningLevel(str, Enum):
    """清洗级别枚举"""

    BASIC = "basic"  # 基础清洗: 去除多余空白,标准化格式
    STANDARD = "standard"  # 标准清洗: 基础清洗 + 去除噪声,标准化特殊字符
    DEEP = "deep"  # 深度清洗: 标准清洗 + 语义清洗,结构优化


class PreprocessedDocument(BaseModel):
    """
    预处理文档领域模型

    表示经过预处理和清洗后的文档, 包含处理后的内容和相关元数据.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="预处理文档唯一标识")
    original_document_id: uuid.UUID = Field(..., description="原始文档ID")
    title: str | None = Field(None, description="提取的文档标题")
    content: str = Field(..., description="预处理后的文档内容")
    original_content_hash: str = Field(..., description="原始内容哈希值, 用于变更检测")

    # 处理信息
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.PENDING, description="处理状态"
    )
    cleaning_level: CleaningLevel = Field(..., description="应用的清洗级别")
    processing_steps: list[str] = Field(
        default_factory=list, description="执行的处理步骤列表"
    )
    processing_metadata: dict[str, Any] = Field(
        default_factory=dict, description="处理过程元数据"
    )

    # 时间字段
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="创建时间"
    )
    started_at: datetime | None = Field(None, description="开始处理时间")
    completed_at: datetime | None = Field(None, description="完成处理时间")

    # 质量指标
    quality_score: float | None = Field(
        None, ge=0.0, le=1.0, description="处理质量评分"
    )
    error_message: str | None = Field(None, description="错误信息(如果处理失败)")

    # 统计信息
    original_length: int = Field(..., gt=0, description="原始内容长度")
    processed_length: int = Field(..., gt=0, description="处理后内容长度")
    compression_ratio: float | None = Field(None, ge=0.0, description="压缩比")

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容不能为空"""
        if not v or not v.strip():
            error_msg = "预处理后的内容不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("original_content_hash")
    @classmethod
    def validate_hash(cls, v: str) -> str:
        """验证哈希值格式"""
        if not v or len(v) < 8:
            error_msg = "原始内容哈希值无效"
            raise ValueError(error_msg)
        return v

    @field_validator("processing_steps")
    @classmethod
    def validate_processing_steps(cls, v: list[str]) -> list[str]:
        """验证处理步骤列表"""
        if not v:
            error_msg = "处理步骤列表不能为空"
            raise ValueError(error_msg)
        return v

    @field_validator("quality_score")
    @classmethod
    def validate_quality_score(cls, v: float | None) -> float | None:
        """验证质量评分范围"""
        if v is not None and (v < 0.0 or v > 1.0):
            error_msg = "质量评分必须在0.0到1.0之间"
            raise ValueError(error_msg)
        return v

    @field_validator("compression_ratio")
    @classmethod
    def validate_compression_ratio(cls, v: float | None) -> float | None:
        """验证压缩比范围"""
        if v is not None and v < 0.0:
            error_msg = "压缩比不能为负数"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_length_consistency(self) -> "PreprocessedDocument":
        """验证长度一致性"""
        if self.processed_length > self.original_length:
            error_msg = "处理后内容长度不能大于原始内容长度"
            raise ValueError(error_msg)

        # 自动计算压缩比
        if self.compression_ratio is None:
            self.compression_ratio = self.processed_length / self.original_length

        return self

    @model_validator(mode="after")
    def validate_status_timestamps(self) -> "PreprocessedDocument":
        """验证状态和时间戳的一致性"""
        if (
            self.processing_status == ProcessingStatus.PROCESSING
            and not self.started_at
        ):
            error_msg = "处理中的文档必须有开始时间"
            raise ValueError(error_msg)

        if self.processing_status == ProcessingStatus.COMPLETED:
            if not self.started_at:
                error_msg = "已完成的文档必须有开始时间"
                raise ValueError(error_msg)
            if not self.completed_at:
                error_msg = "已完成的文档必须有完成时间"
                raise ValueError(error_msg)
            if self.started_at >= self.completed_at:
                error_msg = "完成时间必须晚于开始时间"
                raise ValueError(error_msg)

        if self.processing_status == ProcessingStatus.FAILED and not self.error_message:
            error_msg = "失败的文档必须提供错误信息"
            raise ValueError(error_msg)

        return self

    def start_processing(self) -> None:
        """
        开始处理文档
        """
        if self.processing_status != ProcessingStatus.PENDING:
            error_msg = (
                f"只有待处理的文档可以开始处理, 当前状态: {self.processing_status}"
            )
            raise ValueError(error_msg)

        self.processing_status = ProcessingStatus.PROCESSING
        self.started_at = datetime.utcnow()

    def complete_processing(
        self, quality_score: float | None = None, error_message: str | None = None
    ) -> None:
        """
        完成文档处理

        Args:
            quality_score: 处理质量评分
            error_message: 错误信息(仅在处理失败时使用)
        """
        if self.processing_status != ProcessingStatus.PROCESSING:
            error_msg = f"只有处理中的文档可以完成, 当前状态: {self.processing_status}"
            raise ValueError(error_msg)

        self.completed_at = datetime.utcnow()

        if error_message:
            self.processing_status = ProcessingStatus.FAILED
            self.error_message = error_message
        else:
            self.processing_status = ProcessingStatus.COMPLETED
            self.quality_score = quality_score

    def add_processing_step(
        self, step: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """
        添加处理步骤

        Args:
            step: 处理步骤名称
            metadata: 步骤相关元数据
        """
        if step not in self.processing_steps:
            self.processing_steps.append(step)

        if metadata:
            step_key = f"step_{step}"
            if step_key not in self.processing_metadata:
                self.processing_metadata[step_key] = {}
            self.processing_metadata[step_key].update(metadata)

    def get_processing_metadata(self, step: str) -> dict[str, Any]:
        """
        获取特定处理步骤的元数据

        Args:
            step: 处理步骤名称

        Returns:
            步骤元数据
        """
        step_key = f"step_{step}"
        metadata = self.processing_metadata.get(step_key, {})
        # 确保返回类型是dict[str, Any]
        if isinstance(metadata, dict):
            return metadata
        return {}

    def add_metadata(self, key: str, value: Any) -> None:
        """
        添加元数据

        Args:
            key: 元数据键
            value: 元数据值
        """
        self.metadata[key] = value

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

    def is_processed(self) -> bool:
        """
        检查文档是否已处理完成

        Returns:
            是否已处理完成
        """
        return self.processing_status == ProcessingStatus.COMPLETED

    def is_failed(self) -> bool:
        """
        检查文档处理是否失败

        Returns:
            是否处理失败
        """
        return self.processing_status == ProcessingStatus.FAILED

    def is_processing(self) -> bool:
        """
        检查文档是否正在处理中

        Returns:
            是否正在处理中
        """
        return self.processing_status == ProcessingStatus.PROCESSING

    def get_processing_duration(self) -> float | None:
        """
        获取处理持续时间(秒)

        Returns:
            处理持续时间, 如果未完成则返回None
        """
        if not self.started_at or not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def get_content_summary(self, max_length: int = 200) -> str:
        """
        获取内容摘要

        Args:
            max_length: 摘要最大长度

        Returns:
            内容摘要
        """
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
