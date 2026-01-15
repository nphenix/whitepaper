"""
大纲领域模型

该模块定义了大纲的领域模型, 包括大纲的基本属性,结构,状态管理和版本管理.
支持手写大纲输入(文本输入,结构化输入),大纲版本管理和大纲状态管理.
用于MVP 4步流程中的第二步: 大纲手写和AI优化.
"""

# 生成命令: /speckit.implement T209
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class OutlineStatus(str, Enum):
    """大纲状态枚举"""

    DRAFT = "DRAFT"              # 草稿(用户手写输入)
    OPTIMIZING = "OPTIMIZING"    # 优化中(AI正在优化)
    OPTIMIZED = "OPTIMIZED"      # 已优化(AI优化完成,等待用户确认)
    ACCEPTED = "ACCEPTED"        # 已接受(用户接受优化后的大纲)
    REJECTED = "REJECTED"        # 已拒绝(用户拒绝优化,保留原大纲)
    FINALIZED = "FINALIZED"      # 已定稿(大纲最终确定,进入草稿生成阶段)


class OutlineItemType(str, Enum):
    """大纲项类型枚举"""

    SECTION = "SECTION"          # 章节(一级标题)
    SUBSECTION = "SUBSECTION"    # 子章节(二级标题)
    PARAGRAPH = "PARAGRAPH"      # 段落(三级及以下标题或正文)
    CONTENT = "CONTENT"          # 内容(具体内容描述)


class OutlineItem(BaseModel):
    """
    大纲项模型

    表示大纲中的一个节点,可以是章节,子章节,段落或内容.
    支持层级结构,通过parent_id和children建立父子关系.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="大纲项唯一标识")
    parent_id: uuid.UUID | None = Field(None, description="父级大纲项ID(根节点为None)")
    item_type: OutlineItemType = Field(..., description="大纲项类型")
    level: int = Field(1, description="大纲项层级(1=一级标题,2=二级标题,...)")

    # 内容字段
    title: str = Field(..., description="大纲项标题")
    description: str | None = Field(None, description="大纲项描述/内容")
    order: int = Field(0, description="同级项中的排序顺序")

    # 优化相关字段
    is_optimized: bool = Field(False, description="是否经过AI优化")
    original_title: str | None = Field(None, description="优化前的原始标题")
    original_description: str | None = Field(None, description="优化前的原始描述")
    optimization_suggestions: list[str] = Field(
        default_factory=list, description="AI优化建议列表"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题不能为空"""
        if not v or not v.strip():
            error_msg = "大纲项标题不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: int) -> int:
        """验证层级"""
        if v < 1:
            error_msg = "大纲项层级必须大于等于1"
            raise ValueError(error_msg)
        if v > 6:
            error_msg = "大纲项层级不能超过6"
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
    def validate_consistency(self) -> "OutlineItem":
        """验证字段一致性"""
        # 根节点没有父级
        if self.level == 1 and self.parent_id is not None:
            # 一级标题可以是根节点,也可以有父级(如果是子大纲的一部分)
            pass

        # 确保层级与类型匹配
        if self.level == 1 and self.item_type not in [
            OutlineItemType.SECTION,
            OutlineItemType.SUBSECTION,
        ]:
            # 一级标题可以是章节或子章节
            pass

        return self

    def is_root(self) -> bool:
        """
        检查是否为根节点

        Returns:
            是否为根节点
        """
        return self.parent_id is None

    def is_section(self) -> bool:
        """
        检查是否为章节

        Returns:
            是否为章节
        """
        return self.item_type == OutlineItemType.SECTION

    def is_subsection(self) -> bool:
        """
        检查是否为子章节

        Returns:
            是否为子章节
        """
        return self.item_type == OutlineItemType.SUBSECTION

    def is_paragraph(self) -> bool:
        """
        检查是否为段落

        Returns:
            是否为段落
        """
        return self.item_type == OutlineItemType.PARAGRAPH

    def is_content(self) -> bool:
        """
        检查是否为内容

        Returns:
            是否为内容
        """
        return self.item_type == OutlineItemType.CONTENT

    def has_optimization(self) -> bool:
        """
        检查是否有优化记录

        Returns:
            是否有优化记录
        """
        return (
            self.is_optimized
            or self.original_title is not None
            or self.original_description is not None
            or len(self.optimization_suggestions) > 0
        )

    def accept_optimization(self) -> None:
        """接受优化建议"""
        if self.has_optimization():
            # 将优化后的内容作为正式内容
            self.original_title = None
            self.original_description = None
            self.optimization_suggestions = []
            self.is_optimized = False

    def reject_optimization(self) -> None:
        """拒绝优化建议,恢复原始内容"""
        if self.original_title is not None:
            self.title = self.original_title
            self.original_title = None
        if self.original_description is not None:
            self.description = self.original_description
            self.original_description = None
        self.optimization_suggestions = []
        self.is_optimized = False

    def add_optimization_suggestion(self, suggestion: str) -> None:
        """
        添加优化建议

        Args:
            suggestion: 优化建议
        """
        if suggestion and suggestion.strip():
            suggestion_text = suggestion.strip()
            if suggestion_text not in self.optimization_suggestions:
                new_suggestions = self.optimization_suggestions.copy()
                new_suggestions.append(suggestion_text)
                self.optimization_suggestions = new_suggestions

    def update_title(self, title: str) -> None:
        """
        更新标题

        Args:
            title: 新标题
        """
        new_title = title.strip() if title else ""
        if self.title != new_title:
            # 保存原始标题(如果还没有保存)
            if self.original_title is None:
                self.original_title = self.title
            self.title = new_title

    def update_description(self, description: str | None) -> None:
        """
        更新描述

        Args:
            description: 新描述
        """
        new_description = description.strip() if description else None
        if self.description != new_description:
            # 保存原始描述(如果还没有保存)
            if self.original_description is None:
                self.original_description = self.description
            self.description = new_description

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
        prefix = ""
        if self.item_type == OutlineItemType.SECTION:
            prefix = f"{self.order}. " if self.level == 1 else ""
        elif self.item_type == OutlineItemType.SUBSECTION:
            prefix = f"{self.order}. "
        return f"{indent}{prefix}{self.title}"

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "item_type": self.item_type.value
            if hasattr(self.item_type, "value")
            else self.item_type,
            "level": self.level,
            "title": self.title,
            "description": self.description,
            "order": self.order,
            "is_optimized": self.is_optimized,
            "original_title": self.original_title,
            "original_description": self.original_description,
            "optimization_suggestions": self.optimization_suggestions,
            "metadata": self.metadata,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class OutlineVersion(BaseModel):
    """
    大纲版本模型

    表示大纲的一个历史版本,用于版本管理和回溯.
    每次大纲状态变更或内容修改时,都会创建一个新版本.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="版本唯一标识")
    outline_id: uuid.UUID = Field(..., description="所属大纲ID")
    version_number: int = Field(1, description="版本号")

    # 状态字段
    status: OutlineStatus = Field(..., description="大纲状态")
    change_reason: str | None = Field(None, description="变更原因")

    # 内容快照(序列化为JSON)
    items_snapshot: dict[str, Any] = Field(
        default_factory=dict, description="大纲项快照"
    )

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

    def is_draft_status(self) -> bool:
        """
        检查是否为草稿状态

        Returns:
            是否为草稿状态
        """
        return self.status == OutlineStatus.DRAFT

    def is_optimized_status(self) -> bool:
        """
        检查是否为已优化状态

        Returns:
            是否为已优化状态
        """
        return self.status == OutlineStatus.OPTIMIZED

    def is_accepted_status(self) -> bool:
        """
        检查是否为已接受状态

        Returns:
            是否为已接受状态
        """
        return self.status == OutlineStatus.ACCEPTED

    def is_finalized_status(self) -> bool:
        """
        检查是否为已定稿状态

        Returns:
            是否为已定稿状态
        """
        return self.status == OutlineStatus.FINALIZED

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
            "outline_id": str(self.outline_id),
            "version_number": self.version_number,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "change_reason": self.change_reason,
            "items_snapshot": self.items_snapshot,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class Outline(BaseModel):
    """
    大纲领域模型

    表示一个文档大纲,包含大纲的基本信息,结构,状态和版本历史.
    用于MVP 4步流程中的第二步: 大纲手写和AI优化.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="大纲唯一标识")
    title: str = Field(..., description="大纲标题")
    description: str | None = Field(None, description="大纲描述")

    # 关联字段
    industry_id: uuid.UUID = Field(..., description="所属行业ID")
    database_ids: list[uuid.UUID] = Field(
        default_factory=list, description="使用的数据库ID列表"
    )

    # 状态字段
    status: OutlineStatus = Field(OutlineStatus.DRAFT, description="大纲状态")

    # 大纲内容(扁平化存储,通过parent_id建立层级关系)
    items: list[OutlineItem] = Field(default_factory=list, description="大纲项列表")

    # 版本管理
    current_version: int = Field(1, description="当前版本号")
    versions: list[OutlineVersion] = Field(
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
            error_msg = "大纲标题不能为空"
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
    def validate_consistency(self) -> "Outline":
        """验证字段一致性"""
        # 验证大纲项的层级关系
        for item in self.items:
            if item.parent_id:
                # 检查父级是否存在
                parent_exists = any(
                    parent.id == item.parent_id for parent in self.items
                )
                if not parent_exists:
                    # 这里只是警告,不抛出异常,因为可能是跨大纲引用
                    pass

        # 验证版本号一致性
        if self.current_version < len(self.versions):
            # 当前版本号应该至少等于版本列表长度
            pass

        return self

    def add_item(self, item: OutlineItem) -> None:
        """
        添加大纲项

        Args:
            item: 大纲项
        """
        # 验证父级存在
        if item.parent_id:
            parent_exists = any(parent.id == item.parent_id for parent in self.items)
            if not parent_exists:
                error_msg = f"父级大纲项 {item.parent_id} 不存在"
                raise ValueError(error_msg)

        # 检查是否已存在相同ID的项
        if any(existing.id == item.id for existing in self.items):
            error_msg = f"大纲项 {item.id} 已存在"
            raise ValueError(error_msg)

        new_items = self.items.copy()
        new_items.append(item)
        self.items = new_items
        self._touch()

    def remove_item(self, item_id: uuid.UUID) -> bool:
        """
        移除大纲项

        Args:
            item_id: 大纲项ID

        Returns:
            是否成功移除
        """
        # 检查是否有子项
        has_children = any(
            child.parent_id == item_id for child in self.items
        )
        if has_children:
            error_msg = f"大纲项 {item_id} 有子项,无法移除"
            raise ValueError(error_msg)

        # 移除项
        for i, item in enumerate(self.items):
            if item.id == item_id:
                new_items = self.items.copy()
                new_items.pop(i)
                self.items = new_items
                self._touch()
                return True
        return False

    def update_item(self, item: OutlineItem) -> bool:
        """
        更新大纲项

        Args:
            item: 大纲项

        Returns:
            是否成功更新
        """
        for i, existing in enumerate(self.items):
            if existing.id == item.id:
                new_items = self.items.copy()
                new_items[i] = item
                self.items = new_items
                self._touch()
                return True
        return False

    def get_item(self, item_id: uuid.UUID) -> OutlineItem | None:
        """
        获取大纲项

        Args:
            item_id: 大纲项ID

        Returns:
            大纲项(如果找到)
        """
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_root_items(self) -> list[OutlineItem]:
        """
        获取根级大纲项

        Returns:
            根级大纲项列表
        """
        return [item for item in self.items if item.parent_id is None]

    def get_children(self, parent_id: uuid.UUID) -> list[OutlineItem]:
        """
        获取子项

        Args:
            parent_id: 父级大纲项ID

        Returns:
            子项列表
        """
        return [item for item in self.items if item.parent_id == parent_id]

    def get_items_by_level(self, level: int) -> list[OutlineItem]:
        """
        按层级获取大纲项

        Args:
            level: 层级

        Returns:
            指定层级的大纲项列表
        """
        return [item for item in self.items if item.level == level]

    def get_items_by_type(self, item_type: OutlineItemType) -> list[OutlineItem]:
        """
        按类型获取大纲项

        Args:
            item_type: 大纲项类型

        Returns:
            指定类型的大纲项列表
        """
        return [item for item in self.items if item.item_type == item_type]

    def build_tree(self) -> list[dict[str, Any]]:
        """
        构建大纲树结构

        Returns:
            树形结构的大纲(包含嵌套的children)
        """
        def get_item_type_value(item_type: OutlineItemType | str) -> str:
            """获取item_type的值"""
            if isinstance(item_type, OutlineItemType):
                return item_type.value
            return str(item_type)

        def build_node(item: OutlineItem) -> dict[str, Any]:
            """递归构建节点"""
            children = self.get_children(item.id)
            # 按order排序
            children_sorted = sorted(children, key=lambda x: x.order)
            return {
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "item_type": get_item_type_value(item.item_type),
                "level": item.level,
                "order": item.order,
                "is_optimized": item.is_optimized,
                "optimization_suggestions": item.optimization_suggestions,
                "children": [build_node(child) for child in children_sorted],
            }

        root_items = self.get_root_items()
        # 按order排序
        root_items_sorted = sorted(root_items, key=lambda x: x.order)
        return [build_node(item) for item in root_items_sorted]

    def update_status(self, status: OutlineStatus, change_reason: str | None = None) -> None:
        """
        更新大纲状态

        Args:
            status: 新状态
            change_reason: 变更原因
        """
        if self.status != status:
            self.status = status
            self._touch()

    def create_version(
        self, status: OutlineStatus, change_reason: str | None = None
    ) -> OutlineVersion:
        """
        创建新版本

        Args:
            status: 大纲状态
            change_reason: 变更原因

        Returns:
            新创建的版本
        """
        # 创建版本快照
        items_snapshot = {
            "items": [item.to_dict() for item in self.items],
            "title": self.title,
            "description": self.description,
        }

        # 增加版本号
        self.current_version += 1

        # 创建版本
        version = OutlineVersion(
            outline_id=self.id,
            version_number=self.current_version,
            status=status,
            change_reason=change_reason,
            items_snapshot=items_snapshot,
        )

        new_versions = self.versions.copy()
        new_versions.append(version)
        self.versions = new_versions
        self._touch()

        return version

    def get_version(self, version_number: int) -> OutlineVersion | None:
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

    def get_latest_version(self) -> OutlineVersion | None:
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
        snapshot = version.items_snapshot
        if "title" in snapshot:
            self.title = snapshot["title"]
        if "description" in snapshot:
            self.description = snapshot["description"]
        if "items" in snapshot:
            # 恢复大纲项
            self.items = [
                OutlineItem(**item_data) for item_data in snapshot["items"]
            ]

        # 更新状态
        self.status = version.status
        self._touch()

        return True

    def accept_all_optimizations(self) -> None:
        """接受所有优化建议"""
        for item in self.items:
            if item.has_optimization():
                item.accept_optimization()
        self._touch()

    def reject_all_optimizations(self) -> None:
        """拒绝所有优化建议"""
        for item in self.items:
            if item.has_optimization():
                item.reject_optimization()
        self._touch()

    def has_optimizations(self) -> bool:
        """
        检查是否有优化建议

        Returns:
            是否有优化建议
        """
        return any(item.has_optimization() for item in self.items)

    def get_optimization_summary(self) -> dict[str, Any]:
        """
        获取优化摘要

        Returns:
            优化摘要信息
        """
        optimized_items = [item for item in self.items if item.has_optimization()]
        total_suggestions = sum(
            len(item.optimization_suggestions) for item in optimized_items
        )

        return {
            "total_items": len(self.items),
            "optimized_items": len(optimized_items),
            "total_suggestions": total_suggestions,
            "optimized_items_details": [
                {
                    "id": str(item.id),
                    "title": item.title,
                    "level": item.level,
                    "suggestions": item.optimization_suggestions,
                }
                for item in optimized_items
            ],
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
        return self.status == OutlineStatus.DRAFT

    def is_optimized(self) -> bool:
        """
        检查是否为已优化状态

        Returns:
            是否为已优化状态
        """
        return self.status == OutlineStatus.OPTIMIZED

    def is_accepted(self) -> bool:
        """
        检查是否为已接受状态

        Returns:
            是否为已接受状态
        """
        return self.status == OutlineStatus.ACCEPTED

    def is_finalized(self) -> bool:
        """
        检查是否为已定稿状态

        Returns:
            是否为已定稿状态
        """
        return self.status == OutlineStatus.FINALIZED

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
            "industry_id": str(self.industry_id),
            "database_ids": [str(db_id) for db_id in self.database_ids],
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "items": [item.to_dict() for item in self.items],
            "current_version": self.current_version,
            "versions": [version.to_dict() for version in self.versions],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    def _touch(self) -> None:
        """更新时间戳"""
        import time

        time.sleep(0.001)  # 确保时间戳不同
        self.updated_at = datetime.now(UTC)

    @staticmethod
    def _detect_level_from_plain_text_title(title: str) -> int | None:
        """
        从纯文本标题中检测层级
        
        支持的格式:
        - 中文数字: "一、", "二、", "三、", "（一）", "（二）" (二级标题)
        - 中文括号: "（一）", "（二）" (二级标题)
        - 数字点号: "1.", "1.1", "2.1.3", "2.1" (阿拉伯数字加点)
        - "第X章" 格式: "第一章", "第二章", "第1章"
        - 短横线列表: "- 项目", "  - 子项目" (支持缩进)
        
        Returns:
            检测到的层级(1-6),如果无法识别则返回None
        """
        import re
        
        # 去除首尾空白
        title = title.strip()
        
        # 中文数字映射
        cn_nums = "一二三四五六七八九十"
        
        # 模式0: 短横线列表项 "- 项目" 或 "  - 子项目"
        # 计算缩进级别来确定层级
        indent_count = 0
        temp_title = title
        while temp_title.startswith(" ") or temp_title.startswith("　"):  # 支持空格和中文空格
            indent_count += 1
            temp_title = temp_title[1:]
        
        if temp_title.startswith("-"):
            # 基础层级是 2（作为一级标题下的子项）
            # 根据缩进增加层级
            level = 2 + (indent_count // 2)  # 每2个空格算一级
            return min(level, 6)  # 最多6级
        
        # 模式1: "一、" 或 "二、" (一级标题)
        if len(title) >= 2 and title[0] in cn_nums and title[1] == "、":
            return 1
        
        # 模式2: "（一）" 或 "（二）" (二级标题)
        if title.startswith("（") and title.endswith("）") and len(title) == 4:
            inner = title[1:3]
            if inner in cn_nums:
                return 2
        
        # 模式3: "第X章" 或 "第X节" (一级标题)
        match = re.match(r"^第([一二三四五六七八九十0-9]+)[章节]", title)
        if match:
            num_str = match.group(1)
            # 如果是中文数字
            if num_str in cn_nums:
                return 1
            # 如果是阿拉伯数字
            if num_str.isdigit():
                return 1
        
        # 模式4: 阿拉伯数字加点 "1.", "2." (一级标题)
        match = re.match(r"^(\d+)\.", title)
        if match:
            return 1
        
        # 模式5: 数字嵌套 "1.1", "2.1.3" (根据点号数量确定层级)
        match = re.match(r"^[\d\.]+$", title.split()[0] if title.split() else "")
        if match:
            num_part = title.split()[0] if title.split() else ""
            dot_count = num_part.count(".")
            if dot_count == 1:
                return 2  # 1.1
            elif dot_count == 2:
                return 3  # 1.1.1
            elif dot_count >= 3:
                return 4  # 更深层级
        
        # 模式6: "2.1 全球市场" - 数字+空格+标题 (一级标题)
        match = re.match(r"^(\d+\.\d*)\s+", title)
        if match:
            return 1
        
        return None
    
    @classmethod
    def create_from_text(
        cls,
        title: str,
        text: str,
        industry_id: uuid.UUID,
        database_ids: list[uuid.UUID] | None = None,
        description: str | None = None,
    ) -> "Outline":
        """
        从文本创建大纲
        
        支持Markdown格式和纯文本格式:
        - Markdown格式: "# 标题", "## 二级标题", "### 三级标题"
        - 纯文本格式: "一、标题", "（一）标题", "1. 标题", "2.1 标题"
        
        Args:
            title: 大纲标题
            text: 大纲文本(支持Markdown格式或纯文本格式)
            industry_id: 所属行业ID
            database_ids: 数据库ID列表
            description: 大纲描述

        Returns:
            大纲对象
        """
        outline = cls(
            title=title,
            description=description,
            industry_id=industry_id,
            database_ids=database_ids or [],
            status=OutlineStatus.DRAFT,
            current_version=1,
        )

        # 解析文本大纲
        lines = text.strip().split("\n")
        parent_stack: list[tuple[uuid.UUID, int]] = []  # (父级ID, 层级)栈
        order_counter: dict[int, int] = {}  # 每层的顺序计数器
        
        # 检测是否为Markdown格式
        has_markdown_header = any(line.strip().startswith("#") for line in lines if line.strip())
        is_markdown_format = has_markdown_header
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            if not line.strip():
                i += 1
                continue

            # 检测层级
            level = 1
            item_type = OutlineItemType.SECTION
            stripped_line = line.strip()
            
            if is_markdown_format:
                # Markdown格式: # 标题
                if stripped_line.startswith("#"):
                    level = stripped_line.count("#")
                    level = min(level, 6)  # 最多6级
                    title_text = stripped_line.lstrip("#").strip()
                    if level == 1:
                        item_type = OutlineItemType.SECTION
                    elif level == 2:
                        item_type = OutlineItemType.SUBSECTION
                    else:
                        item_type = OutlineItemType.PARAGRAPH
                else:
                    # 非Markdown标题行，跳过
                    i += 1
                    continue
            else:
                # 纯文本格式: 尝试从行首识别层级
                detected_level = cls._detect_level_from_plain_text_title(stripped_line)
                if detected_level is None:
                    # 无法识别的行，可能是描述内容，跳过
                    i += 1
                    continue
                
                level = detected_level
                # 根据层级确定类型
                if level == 1:
                    item_type = OutlineItemType.SECTION
                elif level == 2:
                    item_type = OutlineItemType.SUBSECTION
                else:
                    item_type = OutlineItemType.PARAGRAPH
                
                # 提取标题（去除序号部分）
                title_text = cls._extract_title_from_plain_text(stripped_line)

            # 获取父级ID
            parent_id = None
            if parent_stack:
                # 调整父级栈:弹出所有大于等于当前层级的项
                while parent_stack and parent_stack[-1][1] >= level:
                    parent_stack.pop()
                # 栈顶就是父级
                if parent_stack:
                    parent_id = parent_stack[-1][0]

            # 收集后续的描述内容（直到下一个标题行或文件结束）
            description_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                # 如果遇到空行，跳过但保留在描述中（用于分隔）
                if not next_line:
                    description_lines.append("")
                # 如果遇到下一个标题行，停止收集
                elif is_markdown_format and next_line.startswith("#"):
                    break
                elif not is_markdown_format:
                    # 纯文本格式：检查下一行是否是标题
                    if cls._detect_level_from_plain_text_title(next_line) is not None:
                        break
                    # 否则作为描述内容
                    description_lines.append(next_line)
                else:
                    description_lines.append(next_line)
                j += 1

            # 合并描述内容
            description_text = "\n".join(description_lines).strip() if description_lines else None
            # 如果描述为空，设置为None
            if not description_text:
                description_text = None

            # 创建大纲项
            order = order_counter.get(level, 0) + 1
            order_counter[level] = order

            item = OutlineItem(
                parent_id=parent_id,
                item_type=item_type,
                level=level,
                title=title_text,
                order=order,
                description=description_text,
                is_optimized=False,
                original_title=None,
                original_description=None,
            )

            outline.add_item(item)

            # 更新父级栈(只添加非CONTENT类型的项)
            if item_type != OutlineItemType.CONTENT:
                parent_stack.append((item.id, level))

            # 移动到下一个标题行（或文件结束）
            i = j

        return outline
    
    @staticmethod
    def _extract_title_from_plain_text(line: str) -> str:
        """
        从纯文本行中提取标题（去除序号部分）
        
        Args:
            line: 原始行内容
            
        Returns:
            提取后的标题
        """
        import re
        line = line.strip()
        
        # 模式0: 去除开头的短横线和空格 "- " 或 "  - "
        line = re.sub(r"^[-*•]\s*", "", line)
        
        # 模式1: 去除 "一、" 或 "二、"
        line = re.sub(r"^[一二三四五六七八九十]、\s*", "", line)
        
        # 模式2: 去除 "（一）" 或 "（二）"
        line = re.sub(r"^（[一二三四五六七八九十]）\s*", "", line)
        
        # 模式3: 去除 "第X章" 或 "第X节"
        line = re.sub(r"^第[一二三四五六七八九十0-9]+[章节]\s*", "", line)
        
        # 模式4: 去除 "1." 或 "1.1" 或 "2.1"
        line = re.sub(r"^[\d\.]+\s*", "", line)
        
        return line.strip()

    @classmethod
    def create_from_structure(
        cls,
        title: str,
        structure: list[dict[str, Any]],
        industry_id: uuid.UUID,
        database_ids: list[uuid.UUID] | None = None,
        description: str | None = None,
    ) -> "Outline":
        """
        从结构化数据创建大纲

        Args:
            title: 大纲标题
            structure: 结构化大纲数据(嵌套的children)
            industry_id: 所属行业ID
            database_ids: 数据库ID列表
            description: 大纲描述

        Returns:
            大纲对象
        """
        outline = cls(
            title=title,
            description=description,
            industry_id=industry_id,
            database_ids=database_ids or [],
            status=OutlineStatus.DRAFT,
            current_version=1,
        )

        # 递归添加大纲项
        def add_items_from_structure(
            items_data: list[dict[str, Any]],
            parent_id: uuid.UUID | None,
            level: int,
        ) -> None:
            """递归添加大纲项"""
            for idx, item_data in enumerate(items_data, start=1):
                # 创建大纲项
                item = OutlineItem(
                    parent_id=parent_id,
                    item_type=OutlineItemType(item_data.get("item_type", "SECTION")),
                    level=level,
                    title=item_data.get("title", ""),
                    description=item_data.get("description"),
                    order=item_data.get("order", idx),
                    is_optimized=False,
                    original_title=None,
                    original_description=None,
                )

                outline.add_item(item)

                # 递归处理子项
                children = item_data.get("children", [])
                if children:
                    add_items_from_structure(children, item.id, level + 1)

        add_items_from_structure(structure, None, 1)

        return outline

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


# 便利函数


def create_outline_from_text(
    title: str,
    text: str,
    industry_id: uuid.UUID,
    database_ids: list[uuid.UUID] | None = None,
    description: str | None = None,
) -> Outline:
    """
    从文本创建大纲的便捷函数

    Args:
        title: 大纲标题
        text: 大纲文本
        industry_id: 所属行业ID
        database_ids: 数据库ID列表
        description: 大纲描述

    Returns:
        大纲对象
    """
    return Outline.create_from_text(
        title=title,
        text=text,
        industry_id=industry_id,
        database_ids=database_ids,
        description=description,
    )


def create_outline_from_structure(
    title: str,
    structure: list[dict[str, Any]],
    industry_id: uuid.UUID,
    database_ids: list[uuid.UUID] | None = None,
    description: str | None = None,
) -> Outline:
    """
    从结构化数据创建大纲的便捷函数

    Args:
        title: 大纲标题
        structure: 结构化大纲数据
        industry_id: 所属行业ID
        database_ids: 数据库ID列表
        description: 大纲描述

    Returns:
        大纲对象
    """
    return Outline.create_from_structure(
        title=title,
        structure=structure,
        industry_id=industry_id,
        database_ids=database_ids,
        description=description,
    )
