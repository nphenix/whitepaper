"""
知识库条目领域模型

该模块定义了知识库条目的领域模型, 包括条目的基本属性、状态和验证规则。
知识库条目可以来自用户上传的文档或网络检索数据。
"""

# 生成命令: /speckit.implement T041
# 生成时间: 2025-12-19
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class EntrySourceType(str, Enum):
    """条目来源类型枚举"""

    UPLOADED_DOCUMENT = "UPLOADED_DOCUMENT"  # 用户上传的文档
    WEB_DATA_SOURCE = "WEB_DATA_SOURCE"     # 网络检索数据


class SourceReferenceType(str, Enum):
    """来源引用类型枚举"""

    DOCUMENT_CHUNK = "DOCUMENT_CHUNK"  # 文档块引用
    WEB_DATA_SOURCE = "WEB_DATA_SOURCE"  # 网络数据源引用


class KnowledgeEntry(BaseModel):
    """
    知识库条目领域模型

    表示知识库中的条目, 关联文档块和检索结果。
    支持多种数据源: 用户上传的文档和网络检索数据。
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="条目唯一标识")
    title: str = Field(..., description="条目标题")
    summary: str | None = Field(None, description="条目摘要")
    tags: list[str] = Field(default_factory=list, description="标签列表")

    # 来源关联字段
    document_id: uuid.UUID | None = Field(
        None, description="来源文档ID(用户上传的文档)"
    )
    chunk_id: uuid.UUID | None = Field(
        None, description="关联的文档块ID(用户上传的文档)"
    )
    web_data_source_id: uuid.UUID | None = Field(
        None, description="来源网络数据源ID(网络检索数据)"
    )

    # 时间字段
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="更新时间"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    # 可追溯性信息
    source_url: str | None = Field(None, description="来源URL(网络数据源)")
    source_path: str | None = Field(None, description="来源文件路径(用户上传文档)")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题不能为空"""
        if not v or not v.strip():
            error_msg = "条目标题不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: list) -> list[str]:
        """验证标签列表"""
        # 去除重复标签和空标签
        cleaned_tags = []
        seen = set()
        for tag in v:
            # 跳过None值和非字符串类型
            if tag is None or not isinstance(tag, str):
                continue
            if tag and tag.strip() and tag.strip() not in seen:
                cleaned_tags.append(tag.strip())
                seen.add(tag.strip())
        return cleaned_tags

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, v: str | None) -> str | None:
        """验证来源URL格式"""
        if v is None:
            return None

        # 去除首尾空白字符
        v = v.strip()

        # 简单的URL格式验证
        if not v.startswith(("http://", "https://")):
            error_msg = "来源URL必须以http://或https://开头"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_source_relationships(self) -> "KnowledgeEntry":
        """验证来源关系的一致性"""
        # 检查document_id和chunk_id必须同时存在或同时为空
        has_document = self.document_id is not None
        has_chunk = self.chunk_id is not None

        if has_document != has_chunk:
            if has_document and not has_chunk:
                error_msg = "document_id存在时, chunk_id也必须存在"
                raise ValueError(error_msg)
            else:  # has_chunk and not has_document
                error_msg = "chunk_id存在时, document_id也必须存在"
                raise ValueError(error_msg)

        # 检查必须有至少一个数据源
        has_uploaded_source = has_document and has_chunk
        has_web_source = self.web_data_source_id is not None

        if not has_uploaded_source and not has_web_source:
            error_msg = "必须指定至少一个数据源(document_id+chunk_id 或 web_data_source_id)"
            raise ValueError(error_msg)

        # 检查不能同时有两个数据源
        if has_uploaded_source and has_web_source:
            error_msg = "不能同时指定上传文档数据源和网络数据源"
            raise ValueError(error_msg)

        # 验证source_url和source_path与数据源的一致性
        if has_uploaded_source and self.source_url:
            error_msg = "用户上传文档不应设置source_url"
            raise ValueError(error_msg)

        if has_web_source and self.source_path:
            error_msg = "网络数据源不应设置source_path"
            raise ValueError(error_msg)

        return self

    def get_source_type(self) -> EntrySourceType:
        """
        获取条目来源类型

        Returns:
            条目来源类型枚举值
        """
        if self.document_id is not None and self.chunk_id is not None:
            return EntrySourceType.UPLOADED_DOCUMENT
        elif self.web_data_source_id is not None:
            return EntrySourceType.WEB_DATA_SOURCE
        else:
            # 这种情况在验证阶段应该被捕获, 但为了类型安全提供默认值
            error_msg = "无法确定条目来源类型: 缺少必要的数据源信息"
            raise ValueError(error_msg)

    def is_from_uploaded_document(self) -> bool:
        """
        检查条目是否来自用户上传的文档

        Returns:
            是否来自用户上传的文档
        """
        return self.get_source_type() == EntrySourceType.UPLOADED_DOCUMENT

    def is_from_web_data_source(self) -> bool:
        """
        检查条目是否来自网络数据源

        Returns:
            是否来自网络数据源
        """
        return self.get_source_type() == EntrySourceType.WEB_DATA_SOURCE

    def add_tag(self, tag: str) -> None:
        """
        添加标签

        Args:
            tag: 要添加的标签
        """
        if tag and tag.strip() and tag.strip() not in self.tags:
            new_tags = self.tags.copy()
            new_tags.append(tag.strip())
            # 直接更新时间戳
            self.tags = new_tags
            self.updated_at = datetime.now(UTC)

    def remove_tag(self, tag: str) -> bool:
        """
        移除标签

        Args:
            tag: 要移除的标签

        Returns:
            是否成功移除(标签存在)
        """
        if tag in self.tags:
            new_tags = self.tags.copy()
            new_tags.remove(tag)
            # 直接更新时间戳
            self.tags = new_tags
            self.updated_at = datetime.now(UTC)
            return True
        return False

    def add_metadata(self, key: str, value: Any) -> None:
        """
        添加元数据

        Args:
            key: 元数据键
            value: 元数据值
        """
        new_metadata = self.metadata.copy()
        new_metadata[key] = value
        # 直接更新时间戳
        self.metadata = new_metadata
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

    def update_summary(self, summary: str) -> None:
        """
        更新摘要

        Args:
            summary: 新的摘要内容
        """
        # 直接更新时间戳
        self.summary = summary.strip() if summary else None
        self.updated_at = datetime.now(UTC)

    def get_source_reference(self) -> dict[str, Any]:
        """
        获取来源引用信息

        Returns:
            包含来源信息的字典
        """
        source_type = self.get_source_type()

        if source_type == EntrySourceType.UPLOADED_DOCUMENT:
            return {
                "source_type": SourceReferenceType.DOCUMENT_CHUNK.value,
                "document_id": str(self.document_id),
                "chunk_id": str(self.chunk_id),
                "source_path": self.source_path
            }
        else:  # WEB_DATA_SOURCE
            return {
                "source_type": SourceReferenceType.WEB_DATA_SOURCE.value,
                "web_data_source_id": str(self.web_data_source_id),
                "source_url": self.source_url
            }

    def get_source_url(self) -> str | None:
        """
        获取来源URL

        Returns:
            来源URL(如果是网络数据源),否则返回None
        """
        if self.is_from_web_data_source():
            return self.source_url
        return None

    def get_source_path(self) -> str | None:
        """
        获取来源文件路径

        Returns:
            来源文件路径(如果是用户上传文档),否则返回None
        """
        if self.is_from_uploaded_document():
            return self.source_path
        return None

    def is_traceable(self) -> bool:
        """
        检查条目是否可追溯

        Returns:
            是否可追溯到原始来源
        """
        source_type = self.get_source_type()
        if source_type == EntrySourceType.UPLOADED_DOCUMENT:
            return self.source_path is not None
        else:  # WEB_DATA_SOURCE
            return self.source_url is not None

    def get_content_preview(self, max_length: int = 200) -> str:
        """
        获取内容预览

        Args:
            max_length: 预览最大长度

        Returns:
            内容预览字符串
        """
        if not self.summary:
            return ""

        if len(self.summary) <= max_length:
            return self.summary
        else:
            return self.summary[:max_length] + "..."

    def has_tag(self, tag: str) -> bool:
        """
        检查是否包含指定标签

        Args:
            tag: 要检查的标签

        Returns:
            是否包含该标签
        """
        return tag in self.tags

    def get_tags_by_prefix(self, prefix: str) -> list[str]:
        """
        获取指定前缀的标签

        Args:
            prefix: 标签前缀

        Returns:
            匹配前缀的标签列表
        """
        return [tag for tag in self.tags if tag.startswith(prefix)]

    def merge_metadata(self, new_metadata: dict[str, Any]) -> None:
        """
        合并元数据

        Args:
            new_metadata: 要合并的元数据
        """
        merged_metadata = self.metadata.copy()
        merged_metadata.update(new_metadata)
        # 直接更新时间戳
        self.metadata = merged_metadata
        self.updated_at = datetime.now(UTC)

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
            # 直接更新时间戳
            self.metadata = new_metadata
            self.updated_at = datetime.now(UTC)
            return True
        return False

    def set_source_reference(self,
                           document_id: uuid.UUID | None = None,
                           chunk_id: uuid.UUID | None = None,
                           web_data_source_id: uuid.UUID | None = None,
                           source_url: str | None = None,
                           source_path: str | None = None) -> None:
        """
        设置来源引用信息

        Args:
            document_id: 文档ID
            chunk_id: 文档块ID
            web_data_source_id: 网络数据源ID
            source_url: 来源URL
            source_path: 来源文件路径
        """
        # 验证参数组合的有效性
        has_document = document_id is not None
        has_chunk = chunk_id is not None
        has_web_source = web_data_source_id is not None

        if has_document and has_web_source:
            error_msg = "不能同时设置文档来源和网络数据源"
            raise ValueError(error_msg)

        if has_document != has_chunk:
            if has_document and not has_chunk:
                error_msg = "设置document_id时,也必须设置chunk_id"
                raise ValueError(error_msg)
            else:  # has_chunk and not has_document
                error_msg = "设置chunk_id时,也必须设置document_id"
                raise ValueError(error_msg)

        # 更新字段
        if has_document:
            self.document_id = document_id
            self.chunk_id = chunk_id
            self.web_data_source_id = None
            self.source_url = None
            self.source_path = source_path
        elif has_web_source:
            self.document_id = None
            self.chunk_id = None
            self.web_data_source_id = web_data_source_id
            self.source_url = source_url
            self.source_path = None

        # 直接更新时间戳
        self.updated_at = datetime.now(UTC)

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        # 允许字段别名, 便于API接口使用
        populate_by_name = True
        # JSON编码器配置
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
