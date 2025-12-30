"""
信息源引用领域模型

该模块定义了信息源引用的领域模型, 支持链接到本地文章和网络文章.
用于MVP 3步流程中的第四步: 草稿生成(带素材追溯链接).

当前版本支持本地文章链接, 网络文章链接功能预留接口(待第三步完成后启用).
"""

# 生成命令: /speckit.implement T231
# 生成时间: 2025-12-24
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class SourceReferenceType(str, Enum):
    """信息源引用类型枚举"""

    LOCAL_DOCUMENT = "LOCAL_DOCUMENT"  # 本地文档引用
    WEB_ARTICLE = "WEB_ARTICLE"        # 网络文章引用(预留接口,待第三步完成后启用)


class LocalDocumentReference(BaseModel):
    """
    本地文档引用模型

    支持文件路径,段落定位,页码定位等本地文档引用信息.
    """

    # 文件路径
    file_path: str = Field(..., description="文件路径(相对路径或绝对路径)")

    # 定位信息
    paragraph_index: int | None = Field(None, description="段落索引(从0开始)")
    page_number: int | None = Field(None, description="页码(从1开始)")
    line_number: int | None = Field(None, description="行号(从1开始)")

    # 内容片段(可选,用于高亮显示)
    content_snippet: str | None = Field(None, description="内容片段(用于高亮显示)")
    start_char: int | None = Field(None, description="起始字符位置")
    end_char: int | None = Field(None, description="结束字符位置")

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """验证文件路径不能为空"""
        if not v or not v.strip():
            error_msg = "文件路径不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("paragraph_index")
    @classmethod
    def validate_paragraph_index(cls, v: int | None) -> int | None:
        """验证段落索引"""
        if v is not None and v < 0:
            error_msg = "段落索引不能为负数"
            raise ValueError(error_msg)
        return v

    @field_validator("page_number")
    @classmethod
    def validate_page_number(cls, v: int | None) -> int | None:
        """验证页码"""
        if v is not None and v < 1:
            error_msg = "页码必须大于等于1"
            raise ValueError(error_msg)
        return v

    @field_validator("line_number")
    @classmethod
    def validate_line_number(cls, v: int | None) -> int | None:
        """验证行号"""
        if v is not None and v < 1:
            error_msg = "行号必须大于等于1"
            raise ValueError(error_msg)
        return v

    @field_validator("start_char", "end_char")
    @classmethod
    def validate_char_position(cls, v: int | None) -> int | None:
        """验证字符位置"""
        if v is not None and v < 0:
            error_msg = "字符位置不能为负数"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_char_range(self) -> "LocalDocumentReference":
        """验证字符范围"""
        if self.start_char is not None and self.end_char is not None:
            if self.start_char > self.end_char:
                error_msg = "起始字符位置不能大于结束字符位置"
                raise ValueError(error_msg)
        return self

    def get_display_path(self) -> str:
        """
        获取显示路径

        Returns:
            格式化的显示路径
        """
        return self.file_path

    def get_location_string(self) -> str:
        """
        获取定位字符串

        Returns:
            格式化的定位信息(如: "第3页, 第2段" 或 "第5行")
        """
        parts = []
        if self.page_number:
            parts.append(f"第{self.page_number}页")
        if self.paragraph_index is not None:
            parts.append(f"第{self.paragraph_index + 1}段")
        if self.line_number:
            parts.append(f"第{self.line_number}行")

        if parts:
            return ", ".join(parts)
        return "未知位置"

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "file_path": self.file_path,
            "paragraph_index": self.paragraph_index,
            "page_number": self.page_number,
            "line_number": self.line_number,
            "content_snippet": self.content_snippet,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class WebArticleReference(BaseModel):
    """
    网络文章引用模型(预留接口)

    支持URL链接,段落定位,关键词高亮等网络文章引用信息.
    当前版本暂时不实现具体功能, 待第三步(信息源爬取)完成后启用.
    """

    # URL链接
    url: str = Field(..., description="文章URL链接")

    # 定位信息
    paragraph_index: int | None = Field(None, description="段落索引(从0开始)")
    section_id: str | None = Field(None, description="章节ID(HTML元素ID)")

    # 关键词高亮(预留接口)
    highlight_keywords: list[str] = Field(
        default_factory=list, description="需要高亮的关键词列表"
    )

    # 内容片段(可选,用于高亮显示)
    content_snippet: str | None = Field(None, description="内容片段(用于高亮显示)")
    start_char: int | None = Field(None, description="起始字符位置")
    end_char: int | None = Field(None, description="结束字符位置")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """验证URL不能为空"""
        if not v or not v.strip():
            error_msg = "URL不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("paragraph_index")
    @classmethod
    def validate_paragraph_index(cls, v: int | None) -> int | None:
        """验证段落索引"""
        if v is not None and v < 0:
            error_msg = "段落索引不能为负数"
            raise ValueError(error_msg)
        return v

    @field_validator("start_char", "end_char")
    @classmethod
    def validate_char_position(cls, v: int | None) -> int | None:
        """验证字符位置"""
        if v is not None and v < 0:
            error_msg = "字符位置不能为负数"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_char_range(self) -> "WebArticleReference":
        """验证字符范围"""
        if self.start_char is not None and self.end_char is not None:
            if self.start_char > self.end_char:
                error_msg = "起始字符位置不能大于结束字符位置"
                raise ValueError(error_msg)
        return self

    def get_display_url(self) -> str:
        """
        获取显示URL

        Returns:
            格式化的显示URL
        """
        return self.url

    def get_location_string(self) -> str:
        """
        获取定位字符串

        Returns:
            格式化的定位信息(如: "第2段" 或 "section-id")
        """
        parts = []
        if self.paragraph_index is not None:
            parts.append(f"第{self.paragraph_index + 1}段")
        if self.section_id:
            parts.append(f"章节: {self.section_id}")

        if parts:
            return ", ".join(parts)
        return "未知位置"

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "url": self.url,
            "paragraph_index": self.paragraph_index,
            "section_id": self.section_id,
            "highlight_keywords": self.highlight_keywords,
            "content_snippet": self.content_snippet,
            "start_char": self.start_char,
            "end_char": self.end_char,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class SourceReference(BaseModel):
    """
    信息源引用领域模型

    表示草稿中引用的信息源, 支持本地文档和网络文章两种类型.
    当前版本完整支持本地文档引用, 网络文章引用功能预留接口(待第三步完成后启用).
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="引用唯一标识")
    reference_type: SourceReferenceType = Field(..., description="引用类型")

    # 引用内容
    title: str = Field(..., description="引用标题(文档标题或文章标题)")
    description: str | None = Field(None, description="引用描述/摘要")

    # 本地文档引用(当前版本支持)
    local_reference: LocalDocumentReference | None = Field(
        None, description="本地文档引用信息"
    )

    # 网络文章引用(预留接口,待第三步完成后启用)
    web_reference: WebArticleReference | None = Field(
        None, description="网络文章引用信息(预留接口)"
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

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题不能为空"""
        if not v or not v.strip():
            error_msg = "引用标题不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @model_validator(mode="after")
    def validate_reference_consistency(self) -> "SourceReference":
        """验证引用类型与引用信息的一致性"""
        if self.reference_type == SourceReferenceType.LOCAL_DOCUMENT:
            if self.local_reference is None:
                error_msg = "本地文档引用类型必须提供local_reference"
                raise ValueError(error_msg)
            if self.web_reference is not None:
                error_msg = "本地文档引用类型不应提供web_reference"
                raise ValueError(error_msg)
        elif self.reference_type == SourceReferenceType.WEB_ARTICLE:
            if self.web_reference is None:
                # 当前版本网络文章引用功能未启用, 允许为None
                # 待第三步完成后, 这里应该要求提供web_reference
                pass
            if self.local_reference is not None:
                error_msg = "网络文章引用类型不应提供local_reference"
                raise ValueError(error_msg)
        return self

    def is_local_document(self) -> bool:
        """
        检查是否为本地文档引用

        Returns:
            是否为本地文档引用
        """
        return self.reference_type == SourceReferenceType.LOCAL_DOCUMENT

    def is_web_article(self) -> bool:
        """
        检查是否为网络文章引用

        Returns:
            是否为网络文章引用
        """
        return self.reference_type == SourceReferenceType.WEB_ARTICLE

    def get_display_link(self) -> str:
        """
        获取显示链接

        Returns:
            格式化的显示链接(文件路径或URL)
        """
        if self.is_local_document() and self.local_reference:
            return self.local_reference.get_display_path()
        elif self.is_web_article() and self.web_reference:
            return self.web_reference.get_display_url()
        return "未知链接"

    def get_location_info(self) -> str:
        """
        获取定位信息

        Returns:
            格式化的定位信息
        """
        if self.is_local_document() and self.local_reference:
            return self.local_reference.get_location_string()
        elif self.is_web_article() and self.web_reference:
            return self.web_reference.get_location_string()
        return "未知位置"

    def is_traceable(self) -> bool:
        """
        检查是否可追溯

        Returns:
            是否可追溯到原始来源
        """
        if self.is_local_document():
            return self.local_reference is not None
        elif self.is_web_article():
            # 当前版本网络文章引用功能未启用
            return False
        return False

    def can_jump_to_source(self) -> bool:
        """
        检查是否可以跳转到来源

        Returns:
            是否可以跳转到来源
        """
        if self.is_local_document():
            return self.local_reference is not None
        elif self.is_web_article():
            # 当前版本网络文章引用功能未启用
            return False
        return False

    def get_jump_url(self) -> str | None:
        """
        获取跳转URL(仅支持本地文章,网络文章功能待第三步完成后启用)

        Returns:
            跳转URL(本地文件路径或网络URL),如果不可跳转则返回None
        """
        if self.is_local_document() and self.local_reference:
            # 返回本地文件路径
            return self.local_reference.file_path
        elif self.is_web_article() and self.web_reference:
            # 当前版本网络文章引用功能未启用
            # 待第三步完成后, 这里可以返回带定位参数的URL
            return None
        return None

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
            self._touch()

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
            self._touch()
            return True
        return False

    def _touch(self) -> None:
        """更新时间戳"""
        import time

        time.sleep(0.001)  # 确保时间戳不同
        self.updated_at = datetime.now(UTC)

    @classmethod
    def create_local_reference(
        cls,
        title: str,
        file_path: str,
        paragraph_index: int | None = None,
        page_number: int | None = None,
        line_number: int | None = None,
        content_snippet: str | None = None,
        description: str | None = None,
    ) -> "SourceReference":
        """
        创建本地文档引用

        Args:
            title: 引用标题
            file_path: 文件路径
            paragraph_index: 段落索引
            page_number: 页码
            line_number: 行号
            content_snippet: 内容片段
            description: 引用描述

        Returns:
            创建的本地文档引用对象
        """
        local_ref = LocalDocumentReference(
            file_path=file_path,
            paragraph_index=paragraph_index,
            page_number=page_number,
            line_number=line_number,
            content_snippet=content_snippet,
            start_char=None,
            end_char=None,
        )

        return cls(
            reference_type=SourceReferenceType.LOCAL_DOCUMENT,
            title=title,
            description=description,
            local_reference=local_ref,
            web_reference=None,
        )

    @classmethod
    def create_web_reference(
        cls,
        title: str,
        url: str,
        paragraph_index: int | None = None,
        section_id: str | None = None,
        highlight_keywords: list[str] | None = None,
        content_snippet: str | None = None,
        description: str | None = None,
    ) -> "SourceReference":
        """
        创建网络文章引用(预留接口,待第三步完成后启用)

        Args:
            title: 引用标题
            url: 文章URL
            paragraph_index: 段落索引
            section_id: 章节ID
            highlight_keywords: 需要高亮的关键词列表
            content_snippet: 内容片段
            description: 引用描述

        Returns:
            创建的网络文章引用对象

        Note:
            当前版本网络文章引用功能未启用, 此方法仅预留接口.
            待第三步(信息源爬取)完成后, 将启用此功能.
        """
        web_ref = WebArticleReference(
            url=url,
            paragraph_index=paragraph_index,
            section_id=section_id,
            highlight_keywords=highlight_keywords or [],
            content_snippet=content_snippet,
            start_char=None,
            end_char=None,
        )

        return cls(
            reference_type=SourceReferenceType.WEB_ARTICLE,
            title=title,
            description=description,
            web_reference=web_ref,
            local_reference=None,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        result = {
            "id": str(self.id),
            "reference_type": self.reference_type.value
            if hasattr(self.reference_type, "value")
            else self.reference_type,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

        if self.local_reference:
            result["local_reference"] = self.local_reference.to_dict()
        if self.web_reference:
            result["web_reference"] = self.web_reference.to_dict()

        return result

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }

