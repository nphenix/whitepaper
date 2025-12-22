"""
文档块领域模型

该模块定义了文档块的领域模型, 包括块的基本属性、状态和验证规则。
文档块是文档解析后的文本块, 用于索引和检索。
"""

# 生成命令: /speckit.implement T042
# 生成时间: 2025-12-19
# 来源: specs/001-multi-agent-doc-system/tasks.md

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator


class ChunkType(str, Enum):
    """文档块类型枚举"""

    PARAGRAPH = "PARAGRAPH"  # 段落
    HEADING = "HEADING"  # 标题
    LIST_ITEM = "LIST_ITEM"  # 列表项
    TABLE = "TABLE"  # 表格
    CODE = "CODE"  # 代码块
    QUOTE = "QUOTE"  # 引用
    IMAGE = "IMAGE"  # 图片
    OTHER = "OTHER"  # 其他


class DocumentChunk(BaseModel):
    """
    文档块领域模型

    表示文档解析后的文本块, 用于索引和检索。
    包含文本内容、位置信息、章节路径等元数据。
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="块唯一标识")
    document_id: uuid.UUID = Field(..., description="所属文档ID")
    chunk_index: int = Field(..., description="块在文档中的序号")
    content: str = Field(..., description="块文本内容")

    # 位置信息
    start_position: int = Field(..., description="在原始文档中的起始位置")
    end_position: int = Field(..., description="在原始文档中的结束位置")

    # 章节信息
    section_path: str = Field(..., description="章节路径(如 '1.2.3')")
    section_title: str | None = Field(None, description="章节标题")

    # 块类型
    chunk_type: ChunkType = Field(ChunkType.PARAGRAPH, description="块类型")

    # 时间字段
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="创建时间"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="块元数据")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容不能为空"""
        if not v or not v.strip():
            error_msg = "文档块内容不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("chunk_index")
    @classmethod
    def validate_chunk_index(cls, v: int) -> int:
        """验证块索引必须非负"""
        if v < 0:
            error_msg = "块索引必须非负"
            raise ValueError(error_msg)
        return v

    @field_validator("start_position", "end_position")
    @classmethod
    def validate_positions(cls, v: int) -> int:
        """验证位置必须非负"""
        if v < 0:
            error_msg = "位置必须非负"
            raise ValueError(error_msg)
        return v

    @field_validator("section_path")
    @classmethod
    def validate_section_path(cls, v: str) -> str:
        """验证章节路径格式"""
        if not v or not v.strip():
            error_msg = "章节路径不能为空"
            raise ValueError(error_msg)

        # 验证章节路径格式(如 "1.2.3")
        pattern = r"^(\d+\.)*\d+$"
        if not re.match(pattern, v.strip()):
            error_msg = f"章节路径格式无效: {v}. 应为数字和点组成的格式, 如 '1.2.3'"
            raise ValueError(error_msg)

        return v.strip()

    @model_validator(mode="after")
    def validate_position_relationship(self) -> "DocumentChunk":
        """验证位置关系"""
        if self.start_position >= self.end_position:
            error_msg = (
                f"起始位置({self.start_position})必须小于结束位置({self.end_position})"
            )
            raise ValueError(error_msg)
        return self

    def get_content_length(self) -> int:
        """
        获取内容长度

        Returns:
            内容字符数
        """
        return len(self.content)

    def get_content_word_count(self) -> int:
        """
        获取内容词数

        Returns:
            内容词数(基于空格分割)
        """
        # 简单的词数统计, 基于空格和标点符号分割
        words = re.findall(r"\b\w+\b", self.content)
        return len(words)

    def get_section_depth(self) -> int:
        """
        获取章节深度

        Returns:
            章节深度(如 "1.2.3" 返回 3)
        """
        parts = self.section_path.split(".")
        return len(parts)

    def get_parent_section_path(self) -> str | None:
        """
        获取父章节路径

        Returns:
            父章节路径(如果没有父章节则返回None)
        """
        parts = self.section_path.split(".")
        if len(parts) <= 1:
            return None
        return ".".join(parts[:-1])

    def is_heading_chunk(self) -> bool:
        """
        检查是否为标题块

        Returns:
            是否为标题块
        """
        return self.chunk_type == ChunkType.HEADING

    def is_paragraph_chunk(self) -> bool:
        """
        检查是否为段落块

        Returns:
            是否为段落块
        """
        return self.chunk_type == ChunkType.PARAGRAPH

    def is_table_chunk(self) -> bool:
        """
        检查是否为表格块

        Returns:
            是否为表格块
        """
        return self.chunk_type == ChunkType.TABLE

    def is_code_chunk(self) -> bool:
        """
        检查是否为代码块

        Returns:
            是否为代码块
        """
        return self.chunk_type == ChunkType.CODE

    def add_metadata(self, key: str, value: Any) -> None:
        """
        添加元数据

        Args:
            key: 元数据键
            value: 元数据值
        """
        new_metadata = self.metadata.copy()
        new_metadata[key] = value
        self.metadata = new_metadata

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

    def has_metadata(self, key: str) -> bool:
        """
        检查是否存在指定元数据

        Args:
            key: 元数据键

        Returns:
            是否存在指定元数据
        """
        return key in self.metadata

    def get_position_info(self) -> dict[str, Any]:
        """
        获取位置信息

        Returns:
            包含位置信息的字典
        """
        return {
            "start_position": self.start_position,
            "end_position": self.end_position,
            "length": self.end_position - self.start_position,
            "chunk_index": self.chunk_index,
        }

    def get_section_info(self) -> dict[str, Any]:
        """
        获取章节信息

        Returns:
            包含章节信息的字典
        """
        return {
            "section_path": self.section_path,
            "section_title": self.section_title,
            "section_depth": self.get_section_depth(),
            "parent_section_path": self.get_parent_section_path(),
        }

    def get_content_preview(self, max_length: int = 100) -> str:
        """
        获取内容预览

        Args:
            max_length: 最大预览长度

        Returns:
            内容预览(截断到指定长度)
        """
        if len(self.content) <= max_length:
            return self.content
        return self.content[:max_length] + "..."

    def contains_keyword(self, keyword: str, case_sensitive: bool = False) -> bool:
        """
        检查内容是否包含关键词

        Args:
            keyword: 关键词
            case_sensitive: 是否区分大小写

        Returns:
            是否包含关键词
        """
        if not keyword:
            return False

        content = self.content if case_sensitive else self.content.lower()
        search_keyword = keyword if case_sensitive else keyword.lower()
        return search_keyword in content

    def get_keyword_positions(
        self, keyword: str, case_sensitive: bool = False
    ) -> list[int]:
        """
        获取关键词在内容中的位置列表

        Args:
            keyword: 关键词
            case_sensitive: 是否区分大小写

        Returns:
            关键词位置列表(起始位置)
        """
        if not keyword:
            return []

        content = self.content if case_sensitive else self.content.lower()
        search_keyword = keyword if case_sensitive else keyword.lower()

        positions = []
        start = 0
        while True:
            pos = content.find(search_keyword, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos + 1

        return positions

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段的字典
        """
        # 处理chunk_type, 可能已经是字符串值(由于pydantic的use_enum_values配置)
        chunk_type_value = (
            self.chunk_type.value
            if hasattr(self.chunk_type, "value")
            else self.chunk_type
        )

        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "chunk_index": self.chunk_index,
            "content": self.content,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "section_path": self.section_path,
            "section_title": self.section_title,
            "chunk_type": chunk_type_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }
        # 允许字段别名, 便于API接口使用
        populate_by_name = True
