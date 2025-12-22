"""
文档领域模型

该模块定义了文档的领域模型, 包括文档的基本属性、状态和验证规则。
"""

# 生成命令: /speckit.implement T023
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator


class DocumentFormat(str, Enum):
    """文档格式枚举"""

    PDF = "PDF"
    HTML = "HTML"
    DOCX = "DOCX"


class DocumentStatus(str, Enum):
    """文档处理状态枚举"""

    PENDING = "PENDING"
    PARSING = "PARSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


class Document(BaseModel):
    """
    文档领域模型

    表示用户上传的原始文档文件及其元数据。
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="文档唯一标识")
    filename: str = Field(..., description="原始文件名")
    file_path: str = Field(..., description="文件存储路径")
    file_size: int = Field(..., gt=0, description="文件大小(字节)")
    mime_type: str | None = Field(None, description="MIME类型")
    format: DocumentFormat = Field(..., description="文档格式")
    content: str | None = Field(None, description="文档内容")

    # 时间字段
    uploaded_at: datetime = Field(
        default_factory=datetime.utcnow, description="上传时间"
    )
    parsed_at: datetime | None = Field(None, description="解析完成时间")

    # 用户和状态
    uploaded_by: uuid.UUID | None = Field(None, description="上传用户ID")
    status: DocumentStatus = Field(
        default=DocumentStatus.PENDING, description="处理状态"
    )
    error_message: str | None = Field(None, description="错误信息(如果解析失败)")

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, v: str) -> str:
        """验证文件名不能为空"""
        if not v or not v.strip():
            error_msg = "文件名不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """验证文件路径不能为空"""
        if not v or not v.strip():
            error_msg = "文件路径不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: str | None) -> str | None:
        """验证MIME类型的基本格式"""
        # 这里只做基本验证, 跨字段验证在model_validator中进行
        return v

    @field_validator("status")
    @classmethod
    def validate_status_transition(cls, v: str) -> str:
        """验证状态转换的合法性"""
        # 这里可以添加状态机验证逻辑
        # 由于是创建时验证, 暂时只检查是否为有效状态
        valid_statuses = {status.value for status in DocumentStatus}
        if v not in valid_statuses:
            error_msg = f"无效的状态值: {v}"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_mime_type_format_match(self) -> "Document":
        """验证MIME类型与文档格式的匹配"""
        if self.mime_type is None:
            return self

        format_to_mime = {
            DocumentFormat.PDF: "application/pdf",
            DocumentFormat.HTML: ["text/html", "application/xhtml+xml"],
            DocumentFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }

        doc_format = self.format
        if doc_format and doc_format in format_to_mime:
            expected_mimes = format_to_mime[doc_format]
            if isinstance(expected_mimes, list):
                if self.mime_type not in expected_mimes:
                    error_msg = (
                        f"MIME类型 {self.mime_type} 与文档格式 {doc_format} 不匹配"
                    )
                    raise ValueError(error_msg)
            else:
                if self.mime_type != expected_mimes:
                    error_msg = (
                        f"MIME类型 {self.mime_type} 与文档格式 {doc_format} 不匹配"
                    )
                    raise ValueError(error_msg)

        return self

    def update_status(
        self, new_status: DocumentStatus, error_message: str | None = None
    ) -> None:
        """
        更新文档状态

        Args:
            new_status: 新的状态
            error_message: 错误信息(仅在状态为FAILED时使用)
        """
        # 验证状态转换
        if new_status == DocumentStatus.FAILED and not error_message:
            error_msg = "状态为FAILED时必须提供错误信息"
            raise ValueError(error_msg)

        if new_status == DocumentStatus.INDEXED and error_message:
            error_msg = "状态为INDEXED时不能提供错误信息"
            raise ValueError(error_msg)

        self.status = new_status
        self.error_message = error_message

        # 更新时间戳
        if new_status == DocumentStatus.INDEXED:
            self.parsed_at = datetime.utcnow()

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
        return self.status == DocumentStatus.INDEXED

    def is_failed(self) -> bool:
        """
        检查文档处理是否失败

        Returns:
            是否处理失败
        """
        return self.status == DocumentStatus.FAILED

    def is_processing(self) -> bool:
        """
        检查文档是否正在处理中

        Returns:
            是否正在处理中
        """
        return self.status == DocumentStatus.PARSING

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
