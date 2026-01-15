"""
草稿领域模型

该模块定义了草稿的领域模型, 包括草稿的基本属性,内容,状态管理和版本管理.
支持草稿内容存储和管理,草稿版本管理(保存历史版本),草稿状态管理(草稿,已生成,已编辑等).
用于MVP 3步流程中的第四步: 草生成(带素材追溯链接).
"""

# 生成命令: /speckit.implement T230
# 生成时间: 2025-12-25
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class DraftStatus(str, Enum):
    """草稿状态枚举"""

    DRAFT = "DRAFT"              # 草稿(初始生成状态)
    GENERATING = "GENERATING"    # 生成中(AI正在生成)
    GENERATED = "GENERATED"      # 已生成(AI生成完成)
    EDITING = "EDITING"          # 编辑中(用户正在编辑)
    EDITED = "EDITED"            # 已编辑(用户编辑完成)
    REVIEWING = "REVIEWING"      # 审核中(等待审核)
    APPROVED = "APPROVED"        # 已审核(审核通过)
    FINALIZED = "FINALIZED"      # 已定稿(最终版本)


class DraftSectionType(str, Enum):
    """草稿章节类型枚举"""

    TITLE = "TITLE"              # 标题
    SECTION = "SECTION"          # 章节
    SUBSECTION = "SUBSECTION"    # 子章节
    PARAGRAPH = "PARAGRAPH"      # 段落
    LIST = "LIST"                # 列表
    TABLE = "TABLE"              # 表格
    CHART = "CHART"              # 图表
    QUOTE = "QUOTE"              # 引用
    CODE = "CODE"                # 代码块
    FOOTNOTE = "FOOTNOTE"        # 脚注


class DraftSection(BaseModel):
    """
    草稿章节模型

    表示草稿中的一个章节或段落, 支持层级结构和内容管理.
    每个章节可以关联多个信息源引用.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="章节唯一标识")
    parent_id: uuid.UUID | None = Field(None, description="父级章节ID(根节点为None)")
    section_type: DraftSectionType = Field(..., description="章节类型")
    level: int = Field(1, description="章节层级(1=一级标题, 2=二级标题, ...)")

    # 内容字段
    title: str | None = Field(None, description="章节标题")
    content: str = Field(..., description="章节内容")
    order: int = Field(0, description="同级项中的排序顺序")

    # 引用信息
    source_references: list[uuid.UUID] = Field(
        default_factory=list, description="关联的信息源引用ID列表"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容不能为空"""
        if not v or not v.strip():
            error_msg = "章节内容不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        """验证标题"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: int) -> int:
        """验证层级"""
        if v < 1:
            error_msg = "章节层级必须大于等于1"
            raise ValueError(error_msg)
        if v > 6:
            error_msg = "章节层级不能超过6"
            raise ValueError(error_msg)
        return v

    @field_validator("order")
    @classmethod
    def validate_order(cls, v: int) -> int:
        """验证排序顺序"""
        if v < 0:
            error_msg = "排序顺序不能为负数"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_consistency(self) -> "DraftSection":
        """验证字段一致性"""
        # 标题类型的章节必须有标题
        if self.section_type in [DraftSectionType.TITLE, DraftSectionType.SECTION,
                                  DraftSectionType.SUBSECTION]:
            if not self.title or not self.title.strip():
                # 这里只是警告, 不抛出异常
                pass

        return self

    def is_root(self) -> bool:
        """
        检查是否为根节点

        Returns:
            是否为根节点
        """
        return self.parent_id is None

    def is_title(self) -> bool:
        """
        检查是否为标题

        Returns:
            是否为标题
        """
        return self.section_type == DraftSectionType.TITLE

    def is_section(self) -> bool:
        """
        检查是否为章节

        Returns:
            是否为章节
        """
        return self.section_type == DraftSectionType.SECTION

    def is_subsection(self) -> bool:
        """
        检查是否为子章节

        Returns:
            是否为子章节
        """
        return self.section_type == DraftSectionType.SUBSECTION

    def is_paragraph(self) -> bool:
        """
        检查是否为段落

        Returns:
            是否为段落
        """
        return self.section_type == DraftSectionType.PARAGRAPH

    def is_list(self) -> bool:
        """
        检查是否为列表

        Returns:
            是否为列表
        """
        return self.section_type == DraftSectionType.LIST

    def is_table(self) -> bool:
        """
        检查是否为表格

        Returns:
            是否为表格
        """
        return self.section_type == DraftSectionType.TABLE

    def is_chart(self) -> bool:
        """
        检查是否为图表

        Returns:
            是否为图表
        """
        return self.section_type == DraftSectionType.CHART

    def is_quote(self) -> bool:
        """
        检查是否为引用

        Returns:
            是否为引用
        """
        return self.section_type == DraftSectionType.QUOTE

    def is_code(self) -> bool:
        """
        检查是否为代码块

        Returns:
            是否为代码块
        """
        return self.section_type == DraftSectionType.CODE

    def is_footnote(self) -> bool:
        """
        检查是否为脚注

        Returns:
            是否为脚注
        """
        return self.section_type == DraftSectionType.FOOTNOTE

    def has_source_references(self) -> bool:
        """
        检查是否有关联的信息源引用

        Returns:
            是否有关联的信息源引用
        """
        return len(self.source_references) > 0

    def add_source_reference(self, reference_id: uuid.UUID) -> None:
        """
        添加信息源引用

        Args:
            reference_id: 信息源引用ID
        """
        if reference_id not in self.source_references:
            new_references = self.source_references.copy()
            new_references.append(reference_id)
            self.source_references = new_references

    def remove_source_reference(self, reference_id: uuid.UUID) -> bool:
        """
        移除信息源引用

        Args:
            reference_id: 信息源引用ID

        Returns:
            是否成功移除
        """
        if reference_id in self.source_references:
            new_references = self.source_references.copy()
            new_references.remove(reference_id)
            self.source_references = new_references
            return True
        return False

    def update_content(self, content: str) -> None:
        """
        更新内容

        Args:
            content: 新内容
        """
        new_content = content.strip() if content else ""
        if self.content != new_content:
            self.content = new_content

    def update_title(self, title: str | None) -> None:
        """
        更新标题

        Args:
            title: 新标题
        """
        new_title = title.strip() if title else None
        if self.title != new_title:
            self.title = new_title

    def set_order(self, order: int) -> None:
        """
        设置排序顺序

        Args:
            order: 新的排序顺序
        """
        if order < 0:
            error_msg = "排序顺序不能为负数"
            raise ValueError(error_msg)

        if self.order != order:
            self.order = order

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
            return True
        return False

    def get_display_title(self) -> str:
        """
        获取显示标题

        Returns:
            格式化的显示标题(带层级缩进)
        """
        indent = "  " * (self.level - 1)
        if self.title:
            return f"{indent}{self.title}"
        # 如果没有标题, 使用内容的前50个字符
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"{indent}{content_preview}"

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "section_type": self.section_type.value
            if hasattr(self.section_type, "value")
            else self.section_type,
            "level": self.level,
            "title": self.title,
            "content": self.content,
            "order": self.order,
            "source_references": [str(ref_id) for ref_id in self.source_references],
            "metadata": self.metadata,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class DraftVersion(BaseModel):
    """
    草稿版本模型

    表示草稿的一个历史版本, 用于版本管理和回溯.
    每次草稿状态变更或内容修改时, 都会创建一个新版本.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="版本唯一标识")
    draft_id: uuid.UUID = Field(..., description="所属草稿ID")
    version_number: int = Field(1, description="版本号")

    # 状态字段
    status: DraftStatus = Field(..., description="草稿状态")
    change_reason: str | None = Field(None, description="变更原因")

    # 内容快照(序列化为JSON)
    sections_snapshot: dict[str, Any] = Field(
        default_factory=dict, description="章节快照"
    )

    # 统计信息
    total_sections: int = Field(0, description="总章节数")
    total_words: int = Field(0, description="总字数")
    total_source_references: int = Field(0, description="总信息源引用数")

    # 时间字段
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="创建时间"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("version_number")
    @classmethod
    def validate_version_number(cls, v: int) -> int:
        """验证版本号"""
        if v < 1:
            error_msg = "版本号必须大于等于1"
            raise ValueError(error_msg)
        return v

    @field_validator("change_reason")
    @classmethod
    def validate_change_reason(cls, v: str | None) -> str | None:
        """验证变更原因"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @field_validator("total_sections")
    @classmethod
    def validate_total_sections(cls, v: int) -> int:
        """验证总章节数"""
        if v < 0:
            error_msg = "总章节数不能为负数"
            raise ValueError(error_msg)
        return v

    @field_validator("total_words")
    @classmethod
    def validate_total_words(cls, v: int) -> int:
        """验证总字数"""
        if v < 0:
            error_msg = "总字数不能为负数"
            raise ValueError(error_msg)
        return v

    @field_validator("total_source_references")
    @classmethod
    def validate_total_source_references(cls, v: int) -> int:
        """验证总信息源引用数"""
        if v < 0:
            error_msg = "总信息源引用数不能为负数"
            raise ValueError(error_msg)
        return v

    def is_draft_status(self) -> bool:
        """
        检查是否为草稿状态

        Returns:
            是否为草稿状态
        """
        return self.status == DraftStatus.DRAFT

    def is_generated_status(self) -> bool:
        """
        检查是否为已生成状态

        Returns:
            是否为已生成状态
        """
        return self.status == DraftStatus.GENERATED

    def is_edited_status(self) -> bool:
        """
        检查是否为已编辑状态

        Returns:
            是否为已编辑状态
        """
        return self.status == DraftStatus.EDITED

    def is_approved_status(self) -> bool:
        """
        检查是否为已审核状态

        Returns:
            是否为已审核状态
        """
        return self.status == DraftStatus.APPROVED

    def is_finalized_status(self) -> bool:
        """
        检查是否为已定稿状态

        Returns:
            是否为已定稿状态
        """
        return self.status == DraftStatus.FINALIZED

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
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "draft_id": str(self.draft_id),
            "version_number": self.version_number,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "change_reason": self.change_reason,
            "sections_snapshot": self.sections_snapshot,
            "total_sections": self.total_sections,
            "total_words": self.total_words,
            "total_source_references": self.total_source_references,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class Draft(BaseModel):
    """
    草稿领域模型

    表示一个文档草稿, 包含草稿的基本信息,内容,状态和版本历史.
    用于MVP 3步流程中的第四步: 草稿生成(带素材追溯链接).
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="草稿唯一标识")
    title: str = Field(..., description="草稿标题")
    description: str | None = Field(None, description="草稿描述")

    # 关联字段
    outline_id: uuid.UUID = Field(..., description="关联的大纲ID")
    industry_id: uuid.UUID = Field(..., description="所属行业ID")
    database_ids: list[uuid.UUID] = Field(
        default_factory=list, description="使用的数据库ID列表"
    )

    # 状态字段
    status: DraftStatus = Field(DraftStatus.DRAFT, description="草稿状态")

    # 草稿内容(扁平化存储, 通过parent_id建立层级关系)
    sections: list[DraftSection] = Field(default_factory=list, description="章节列表")

    # 版本管理
    current_version: int = Field(1, description="当前版本号")
    versions: list[DraftVersion] = Field(
        default_factory=list, description="版本历史列表"
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
            error_msg = "草稿标题不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @field_validator("current_version")
    @classmethod
    def validate_current_version(cls, v: int) -> int:
        """验证当前版本号"""
        if v < 1:
            error_msg = "当前版本号必须大于等于1"
            raise ValueError(error_msg)
        return v

    @model_validator(mode="after")
    def validate_consistency(self) -> "Draft":
        """验证字段一致性"""
        # 验证章节的层级关系
        for section in self.sections:
            if section.parent_id:
                # 检查父级是否存在
                parent_exists = any(
                    parent.id == section.parent_id for parent in self.sections
                )
                if not parent_exists:
                    # 这里只是警告, 不抛出异常, 因为可能是跨草稿引用
                    pass

        # 验证版本号一致性
        if self.current_version < len(self.versions):
            # 当前版本号应该至少等于版本列表长度
            pass

        return self

    def add_section(self, section: DraftSection) -> None:
        """
        添加章节

        Args:
            section: 章节
        """
        # 验证父级存在（宽松模式：如果父级不存在，自动降级为根章节）
        if section.parent_id:
            parent_exists = any(parent.id == section.parent_id for parent in self.sections)
            if not parent_exists:
                # 父级不存在，自动降级为根章节（避免草稿生成失败）
                logger.warning(
                    "父级章节 %s 不存在，将章节 '%s' 降级为根章节",
                    section.parent_id,
                    section.title or section.id
                )
                # 创建一个新的 section，移除 parent_id
                section = DraftSection(
                    id=section.id,
                    parent_id=None,  # 降级为根章节
                    section_type=section.section_type,
                    level=section.level,
                    title=section.title,
                    content=section.content,
                    order=section.order,
                    source_references=section.source_references,
                    metadata=section.metadata,
                )

        # 检查是否已存在相同ID的章节
        if any(existing.id == section.id for existing in self.sections):
            error_msg = f"章节 {section.id} 已存在"
            raise ValueError(error_msg)

        new_sections = self.sections.copy()
        new_sections.append(section)
        self.sections = new_sections
        self._touch()

    def get_content(self) -> str:
        """获取草稿内容(Markdown)

        说明：前端适配层会直接调用 draft.get_content()。
        不生成草稿的title作为文档标题，而是使用第一个section的title作为文档主标题
        
        优化版本（2026-01-09）：
        - 修复重复函数定义问题
        - 优化章节渲染逻辑
        - 更好地处理层级关系
        """
        import re

        lines: list[str] = []

        # 定义辅助函数（仅定义一次）
        def strip_markdown_headers_from_content(content: str) -> str:
            """
            清理section content中的所有markdown标题行
            问题：数据库中section的content字段包含了完整的markdown内容（包括子章节标题）
            这些子章节标题会导致重复渲染
            解决：移除content中所有的markdown标题行（#开头的行），只保留正文内容
            """
            if not content:
                return content

            cleaned_lines = []
            for line in content.split('\n'):
                # 检查是否是以#开头的markdown标题行
                stripped = line.strip()
                if stripped.startswith('#'):
                    # 跳过markdown标题行
                    continue
                else:
                    cleaned_lines.append(line)

            result = '\n'.join(cleaned_lines)
            # 清理多余的空行
            result = re.sub(r'\n{3,}', '\n\n', result)
            return result.strip()

        # 按层级和order排序所有章节
        sorted_sections = sorted(self.sections, key=lambda s: (s.level or 1, s.order or 0))

        # 分离根章节和非根章节
        root_sections = []
        child_sections_by_parent: dict[str, list[DraftSection]] = {}

        for s in sorted_sections:
            if s.parent_id is None:
                root_sections.append(s)
            else:
                parent_id_str = str(s.parent_id)
                if parent_id_str not in child_sections_by_parent:
                    child_sections_by_parent[parent_id_str] = []
                child_sections_by_parent[parent_id_str].append(s)

        # 查找第一个SECTION类型的section作为文档主标题
        main_title = None
        main_section_content = None
        main_section_id = None

        for s in root_sections:
            section_type_str = str(s.section_type)
            if main_title is None and section_type_str == "SECTION" and s.title:
                main_title = s.title
                main_section_content = s.content
                main_section_id = s.id
                break

        # 添加文档主标题（如果找到）
        if main_title:
            lines.append(f"# {main_title}\n")
            # 渲染主section的内容（清理markdown标题）
            if main_section_content:
                cleaned_content = strip_markdown_headers_from_content(main_section_content)
                if cleaned_content:
                    lines.append(f"{cleaned_content}\n")

        # 添加描述（如果有）
        if self.description:
            lines.append(f"{self.description}\n")

        # 用于追踪已渲染的章节，避免重复
        rendered_titles: set[str] = set()
        rendered_section_ids: set[str] = set()

        # 添加主标题到已渲染列表
        if main_title:
            rendered_titles.add(main_title.strip().lower())

        def render_section(section: DraftSection, level: int, parent_id: str | None = None) -> None:
            """递归渲染章节"""
            # 检查是否已渲染（避免循环引用或重复）
            section_id_str = str(section.id)
            if section_id_str in rendered_section_ids:
                return
            rendered_section_ids.add(section_id_str)

            # 检查标题是否已渲染（避免同一标题重复）
            if section.title:
                title_key = section.title.strip().lower()
                if title_key in rendered_titles:
                    # 但仍然渲染内容（可能有不同的子章节）
                    pass
                else:
                    rendered_titles.add(title_key)

            # 渲染标题
            if section.title:
                # level=1 对应 Markdown ##，避免与文档标题冲突
                prefix = "#" * min(max(level + 1, 2), 6)
                lines.append(f"{prefix} {section.title}\n")

            # 渲染内容（清理markdown标题）
            if section.content:
                cleaned_content = strip_markdown_headers_from_content(section.content)
                if cleaned_content:
                    lines.append(f"{cleaned_content}\n")

            # 获取并渲染子章节
            children = child_sections_by_parent.get(section_id_str, [])
            # 按order排序子章节
            children = sorted(children, key=lambda s: (s.order or 0))
            for child in children:
                render_section(child, level + 1, section_id_str)

        # 渲染根章节（跳过已作为主标题的章节）
        for section in root_sections:
            section_id_str = str(section.id)
            if section_id_str == str(main_section_id):
                continue  # 跳过主标题章节
            render_section(section, section.level or 1)

        return "\n".join(lines).strip()

    def remove_section(self, section_id: uuid.UUID) -> bool:
        """
        移除章节

        Args:
            section_id: 章节ID

        Returns:
            是否成功移除
        """
        # 检查是否有子章节
        has_children = any(
            child.parent_id == section_id for child in self.sections
        )
        if has_children:
            error_msg = f"章节 {section_id} 有子章节, 无法移除"
            raise ValueError(error_msg)

        # 移除章节
        for i, section in enumerate(self.sections):
            if section.id == section_id:
                new_sections = self.sections.copy()
                new_sections.pop(i)
                self.sections = new_sections
                self._touch()
                return True
        return False

    def update_section(self, section: DraftSection) -> bool:
        """
        更新章节

        Args:
            section: 章节

        Returns:
            是否成功更新
        """
        for i, existing in enumerate(self.sections):
            if existing.id == section.id:
                new_sections = self.sections.copy()
                new_sections[i] = section
                self.sections = new_sections
                self._touch()
                return True
        return False

    def get_section(self, section_id: uuid.UUID) -> DraftSection | None:
        """
        获取章节

        Args:
            section_id: 章节ID

        Returns:
            章节(如果找到)
        """
        for section in self.sections:
            if section.id == section_id:
                return section
        return None

    def get_root_sections(self) -> list[DraftSection]:
        """
        获取根级章节

        Returns:
            根级章节列表
        """
        return [section for section in self.sections if section.parent_id is None]

    def get_children(self, parent_id: uuid.UUID) -> list[DraftSection]:
        """
        获取子章节

        Args:
            parent_id: 父级章节ID

        Returns:
            子章节列表
        """
        return [section for section in self.sections if section.parent_id == parent_id]

    def get_sections_by_level(self, level: int) -> list[DraftSection]:
        """
        按层级获取章节

        Args:
            level: 层级

        Returns:
            指定层级的章节列表
        """
        return [section for section in self.sections if section.level == level]

    def get_sections_by_type(self, section_type: DraftSectionType) -> list[DraftSection]:
        """
        按类型获取章节

        Args:
            section_type: 章节类型

        Returns:
            指定类型的章节列表
        """
        return [section for section in self.sections if section.section_type == section_type]

    def build_tree(self) -> list[dict[str, Any]]:
        """
        构建草稿树结构

        Returns:
            树形结构的草稿(包含嵌套的children)
        """
        def get_section_type_value(section_type: DraftSectionType | str) -> str:
            """获取section_type的值"""
            if isinstance(section_type, DraftSectionType):
                return section_type.value
            return str(section_type)

        def build_node(section: DraftSection) -> dict[str, Any]:
            """递归构建节点"""
            children = self.get_children(section.id)
            # 按order排序
            children_sorted = sorted(children, key=lambda x: x.order)
            return {
                "id": str(section.id),
                "title": section.title,
                "content": section.content,
                "section_type": get_section_type_value(section.section_type),
                "level": section.level,
                "order": section.order,
                "source_references": [str(ref_id) for ref_id in section.source_references],
                "has_source_references": section.has_source_references(),
                "children": [build_node(child) for child in children_sorted],
            }

        root_sections = self.get_root_sections()
        # 按order排序
        root_sections_sorted = sorted(root_sections, key=lambda x: x.order)
        return [build_node(section) for section in root_sections_sorted]

    def update_status(self, status: DraftStatus, change_reason: str | None = None) -> None:
        """
        更新草稿状态

        Args:
            status: 新状态
            change_reason: 变更原因
        """
        if self.status != status:
            self.status = status
            self._touch()

    def create_version(
        self, status: DraftStatus, change_reason: str | None = None
    ) -> DraftVersion:
        """
        创建新版本

        Args:
            status: 草稿状态
            change_reason: 变更原因

        Returns:
            新创建的版本
        """
        # 创建版本快照
        sections_snapshot = {
            "sections": [section.to_dict() for section in self.sections],
            "title": self.title,
            "description": self.description,
        }

        # 计算统计信息
        total_sections = len(self.sections)
        total_words = sum(len(section.content.split()) for section in self.sections)
        total_source_references = sum(
            len(section.source_references) for section in self.sections
        )

        # 增加版本号
        self.current_version += 1

        # 创建版本
        version = DraftVersion(
            draft_id=self.id,
            version_number=self.current_version,
            status=status,
            change_reason=change_reason,
            sections_snapshot=sections_snapshot,
            total_sections=total_sections,
            total_words=total_words,
            total_source_references=total_source_references,
        )

        new_versions = self.versions.copy()
        new_versions.append(version)
        self.versions = new_versions
        self._touch()

        return version

    def get_version(self, version_number: int) -> DraftVersion | None:
        """
        获取指定版本

        Args:
            version_number: 版本号

        Returns:
            版本对象(如果找到)
        """
        for version in self.versions:
            if version.version_number == version_number:
                return version
        return None

    def get_latest_version(self) -> DraftVersion | None:
        """
        获取最新版本

        Returns:
            最新版本对象(如果存在)
        """
        if not self.versions:
            return None
        return self.versions[-1]

    def restore_version(self, version_number: int) -> bool:
        """
        恢复到指定版本

        Args:
            version_number: 版本号

        Returns:
            是否成功恢复
        """
        version = self.get_version(version_number)
        if not version:
            return False

        # 恢复内容
        snapshot = version.sections_snapshot
        if "title" in snapshot:
            self.title = snapshot["title"]
        if "description" in snapshot:
            self.description = snapshot["description"]
        if "sections" in snapshot:
            # 恢复章节
            self.sections = [
                DraftSection(**section_data) for section_data in snapshot["sections"]
            ]

        # 更新状态
        self.status = version.status
        self._touch()

        return True

    def get_statistics(self) -> dict[str, Any]:
        """
        获取草稿统计信息

        Returns:
            统计信息
        """
        total_sections = len(self.sections)
        total_words = sum(len(section.content.split()) for section in self.sections)
        total_characters = sum(len(section.content) for section in self.sections)
        total_source_references = sum(
            len(section.source_references) for section in self.sections
        )

        # 按类型统计
        sections_by_type: dict[str, int] = {}
        for section in self.sections:
            type_value = (
                section.section_type.value
                if hasattr(section.section_type, "value")
                else str(section.section_type)
            )
            sections_by_type[type_value] = sections_by_type.get(type_value, 0) + 1

        # 按层级统计
        sections_by_level: dict[int, int] = {}
        for section in self.sections:
            sections_by_level[section.level] = sections_by_level.get(section.level, 0) + 1

        return {
            "total_sections": total_sections,
            "total_words": total_words,
            "total_characters": total_characters,
            "total_source_references": total_source_references,
            "sections_by_type": sections_by_type,
            "sections_by_level": sections_by_level,
            "current_version": self.current_version,
            "total_versions": len(self.versions),
        }

    def add_database(self, database_id: uuid.UUID) -> None:
        """
        添加数据库

        Args:
            database_id: 数据库ID
        """
        if database_id not in self.database_ids:
            new_database_ids = self.database_ids.copy()
            new_database_ids.append(database_id)
            self.database_ids = new_database_ids
            self._touch()

    def remove_database(self, database_id: uuid.UUID) -> bool:
        """
        移除数据库

        Args:
            database_id: 数据库ID

        Returns:
            是否成功移除
        """
        if database_id in self.database_ids:
            new_database_ids = self.database_ids.copy()
            new_database_ids.remove(database_id)
            self.database_ids = new_database_ids
            self._touch()
            return True
        return False

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

    def is_draft(self) -> bool:
        """
        检查是否为草稿状态

        Returns:
            是否为草稿状态
        """
        return self.status == DraftStatus.DRAFT

    def is_generating(self) -> bool:
        """
        检查是否为生成中状态

        Returns:
            是否为生成中状态
        """
        return self.status == DraftStatus.GENERATING

    def is_generated(self) -> bool:
        """
        检查是否为已生成状态

        Returns:
            是否为已生成状态
        """
        return self.status == DraftStatus.GENERATED

    def is_editing(self) -> bool:
        """
        检查是否为编辑中状态

        Returns:
            是否为编辑中状态
        """
        return self.status == DraftStatus.EDITING

    def is_edited(self) -> bool:
        """
        检查是否为已编辑状态

        Returns:
            是否为已编辑状态
        """
        return self.status == DraftStatus.EDITED

    def is_reviewing(self) -> bool:
        """
        检查是否为审核中状态

        Returns:
            是否为审核中状态
        """
        return self.status == DraftStatus.REVIEWING

    def is_approved(self) -> bool:
        """
        检查是否为已审核状态

        Returns:
            是否为已审核状态
        """
        return self.status == DraftStatus.APPROVED

    def is_finalized(self) -> bool:
        """
        检查是否为已定稿状态

        Returns:
            是否为已定稿状态
        """
        return self.status == DraftStatus.FINALIZED

    def get_display_name(self) -> str:
        """
        获取显示名称

        Returns:
            格式化的显示名称
        """
        return f"{self.title} (v{self.current_version})"

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "title": self.title,
            "description": self.description,
            "outline_id": str(self.outline_id),
            "industry_id": str(self.industry_id),
            "database_ids": [str(db_id) for db_id in self.database_ids],
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "sections": [section.to_dict() for section in self.sections],
            "current_version": self.current_version,
            "versions": [version.to_dict() for version in self.versions],
            "statistics": self.get_statistics(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    def _touch(self) -> None:
        """更新时间戳"""
        import time

        time.sleep(0.001)  # 确保时间戳不同
        self.updated_at = datetime.now(UTC)

    @classmethod
    def create_from_outline(
        cls,
        title: str,
        outline_id: uuid.UUID,
        industry_id: uuid.UUID,
        database_ids: list[uuid.UUID] | None = None,
        description: str | None = None,
    ) -> "Draft":
        """
        从大纲创建草稿

        Args:
            title: 草稿标题
            outline_id: 关联的大纲ID
            industry_id: 所属行业ID
            database_ids: 数据库ID列表
            description: 草稿描述

        Returns:
            草稿对象
        """
        draft = cls(
            title=title,
            description=description,
            outline_id=outline_id,
            industry_id=industry_id,
            database_ids=database_ids or [],
            status=DraftStatus.DRAFT,
            current_version=1,
        )

        # 注意: 这里只是创建空草稿, 实际内容需要通过草稿生成Agent填充
        # 大纲结构信息可以通过outline_id从数据库获取

        return draft

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


# 便利函数


def create_draft_from_outline(
    title: str,
    outline_id: uuid.UUID,
    industry_id: uuid.UUID,
    database_ids: list[uuid.UUID] | None = None,
    description: str | None = None,
) -> Draft:
    """
    从大纲创建草稿的便捷函数

    Args:
        title: 草稿标题
        outline_id: 关联的大纲ID
        industry_id: 所属行业ID
        database_ids: 数据库ID列表
        description: 草稿描述

    Returns:
        草稿对象
    """
    return Draft.create_from_outline(
        title=title,
        outline_id=outline_id,
        industry_id=industry_id,
        database_ids=database_ids,
        description=description,
    )
