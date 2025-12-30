"""
优化大纲领域模型

该模块定义了优化后的大纲领域模型,包括优化类型,优化项,优化摘要和优化大纲.
用于MVP 4步流程中的第二步: 大纲手写和AI优化.
与Outline领域模型配合使用,Outline表示用户手写的大纲,OptimizedOutline表示AI优化后的大纲.
"""

# 生成命令: /speckit.implement T210
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from .outline import Outline, OutlineItem, OutlineItemType


class OptimizationChangeType(str, Enum):
    """优化变更类型枚举"""

    ADD = "ADD"                    # 新增章节/项
    MODIFY = "MODIFY"              # 修改内容
    DELETE = "DELETE"              # 删除章节/项
    MOVE = "MOVE"                  # 移动位置
    REORDER = "REORDER"            # 调整顺序
    MERGE = "MERGE"                # 合并章节
    SPLIT = "SPLIT"                # 拆分章节
    NONE = "NONE"                  # 无变更


class OptimizedOutlineItem(BaseModel):
    """
    优化后的大纲项模型

    表示AI优化后的一个大纲项,包含原始项,优化后项,变更类型和优化建议.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="优化项唯一标识")
    original_outline_id: uuid.UUID = Field(..., description="原始大纲ID")

    # 原始项信息(如果存在)
    original_item_id: uuid.UUID | None = Field(None, description="原始大纲项ID(None表示新增)")
    original_item: OutlineItem | None = Field(None, description="原始大纲项(用于对比)")

    # 优化后项信息
    optimized_item: OutlineItem = Field(..., description="优化后的大纲项")

    # 变更信息
    change_type: OptimizationChangeType = Field(
        OptimizationChangeType.NONE, description="变更类型"
    )
    change_description: str | None = Field(None, description="变更描述")

    # 优化建议
    optimization_reason: str | None = Field(None, description="优化原因")
    optimization_suggestions: list[str] = Field(
        default_factory=list, description="优化建议列表"
    )

    # 用户反馈
    is_accepted: bool = Field(False, description="用户是否接受此优化")
    user_feedback: str | None = Field(None, description="用户反馈")

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("optimized_item")
    @classmethod
    def validate_optimized_item(cls, v: OutlineItem) -> OutlineItem:
        """验证优化后的大纲项"""
        return v

    @field_validator("optimization_reason")
    @classmethod
    def validate_optimization_reason(cls, v: str | None) -> str | None:
        """验证优化原因"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @field_validator("change_description")
    @classmethod
    def validate_change_description(cls, v: str | None) -> str | None:
        """验证变更描述"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @model_validator(mode="after")
    def validate_consistency(self) -> "OptimizedOutlineItem":
        """验证字段一致性"""
        # 如果是新增项,original_item_id应该为None
        if self.change_type == OptimizationChangeType.ADD:
            if self.original_item_id is not None:
                # 新增项不应该有原始项ID
                pass
            if self.original_item is not None:
                # 新增项不应该有原始项
                pass

        # 如果是删除项,optimized_item应该标记为删除
        if self.change_type == OptimizationChangeType.DELETE:
            # 删除项的optimized_item可能包含删除前的信息
            pass

        return self

    def is_new_item(self) -> bool:
        """
        检查是否为新增项

        Returns:
            是否为新增项
        """
        return self.change_type == OptimizationChangeType.ADD

    def is_modified_item(self) -> bool:
        """
        检查是否为修改项

        Returns:
            是否为修改项
        """
        return self.change_type == OptimizationChangeType.MODIFY

    def is_deleted_item(self) -> bool:
        """
        检查是否为删除项

        Returns:
            是否为删除项
        """
        return self.change_type == OptimizationChangeType.DELETE

    def is_moved_item(self) -> bool:
        """
        检查是否为移动项

        Returns:
            是否为移动项
        """
        return self.change_type == OptimizationChangeType.MOVE

    def has_change(self) -> bool:
        """
        检查是否有变更

        Returns:
            是否有变更
        """
        return self.change_type != OptimizationChangeType.NONE

    def accept_optimization(self, feedback: str | None = None) -> None:
        """
        接受优化

        Args:
            feedback: 用户反馈
        """
        self.is_accepted = True
        if feedback:
            self.user_feedback = feedback.strip() if feedback.strip() else None

    def reject_optimization(self, feedback: str | None = None) -> None:
        """
        拒绝优化

        Args:
            feedback: 用户反馈
        """
        self.is_accepted = False
        if feedback:
            self.user_feedback = feedback.strip() if feedback.strip() else None

    def add_suggestion(self, suggestion: str) -> None:
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

    def get_change_summary(self) -> dict[str, Any]:
        """
        获取变更摘要

        Returns:
            变更摘要信息
        """
        # 处理change_type可能是字符串的情况(由于use_enum_values配置)
        change_type_value = (
            self.change_type.value
            if hasattr(self.change_type, "value")
            else self.change_type
        )

        summary = {
            "change_type": change_type_value,
            "original_item_id": str(self.original_item_id) if self.original_item_id else None,
            "optimized_item_id": str(self.optimized_item.id),
            "title_before": self.original_item.title if self.original_item else None,
            "title_after": self.optimized_item.title,
            "change_description": self.change_description,
            "optimization_reason": self.optimization_reason,
        }

        # 添加内容变更
        if self.original_item:
            summary["description_before"] = self.original_item.description
        summary["description_after"] = self.optimized_item.description

        # 添加位置变更
        if self.original_item:
            summary["order_before"] = str(self.original_item.order) if self.original_item else None
        summary["order_after"] = str(self.optimized_item.order)

        return summary

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "original_outline_id": str(self.original_outline_id),
            "original_item_id": str(self.original_item_id) if self.original_item_id else None,
            "original_item": self.original_item.to_dict() if self.original_item else None,
            "optimized_item": self.optimized_item.to_dict(),
            "change_type": self.change_type.value
            if hasattr(self.change_type, "value")
            else self.change_type,
            "change_description": self.change_description,
            "optimization_reason": self.optimization_reason,
            "optimization_suggestions": self.optimization_suggestions,
            "is_accepted": self.is_accepted,
            "user_feedback": self.user_feedback,
            "metadata": self.metadata,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class OptimizationSummary(BaseModel):
    """
    优化摘要模型

    表示一次大纲优化的摘要信息,包括变更统计,优化质量评估等.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="摘要唯一标识")
    optimized_outline_id: uuid.UUID = Field(..., description="优化后大纲ID")

    # 变更统计
    total_changes: int = Field(0, description="总变更数")
    added_items: int = Field(0, description="新增项数")
    modified_items: int = Field(0, description="修改项数")
    deleted_items: int = Field(0, description="删除项数")
    moved_items: int = Field(0, description="移动项数")
    reordered_items: int = Field(0, description="重排项数")
    merged_items: int = Field(0, description="合并项数")
    split_items: int = Field(0, description="拆分项数")

    # 质量评估
    quality_score: float = Field(0.0, ge=0.0, le=1.0, description="优化质量评分(0-1)")
    completeness_score: float = Field(0.0, ge=0.0, le=1.0, description="完整度评分(0-1)")
    coherence_score: float = Field(0.0, ge=0.0, le=1.0, description="连贯性评分(0-1)")
    relevance_score: float = Field(0.0, ge=0.0, le=1.0, description="相关性评分(0-1)")

    # 优化描述
    optimization_summary: str = Field(..., description="优化摘要描述")
    key_improvements: list[str] = Field(
        default_factory=list, description="关键改进点列表"
    )
    potential_issues: list[str] = Field(
        default_factory=list, description="潜在问题列表"
    )

    # 时间字段
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="创建时间"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("quality_score")
    @classmethod
    def validate_quality_score(cls, v: float) -> float:
        """验证质量评分"""
        if v < 0.0 or v > 1.0:
            error_msg = "质量评分必须在0到1之间"
            raise ValueError(error_msg)
        # 四舍五入到2位小数
        return round(v, 2)

    @field_validator("completeness_score")
    @classmethod
    def validate_completeness_score(cls, v: float) -> float:
        """验证完整度评分"""
        if v < 0.0 or v > 1.0:
            error_msg = "完整度评分必须在0到1之间"
            raise ValueError(error_msg)
        return round(v, 2)

    @field_validator("coherence_score")
    @classmethod
    def validate_coherence_score(cls, v: float) -> float:
        """验证连贯性评分"""
        if v < 0.0 or v > 1.0:
            error_msg = "连贯性评分必须在0到1之间"
            raise ValueError(error_msg)
        return round(v, 2)

    @field_validator("relevance_score")
    @classmethod
    def validate_relevance_score(cls, v: float) -> float:
        """验证相关性评分"""
        if v < 0.0 or v > 1.0:
            error_msg = "相关性评分必须在0到1之间"
            raise ValueError(error_msg)
        return round(v, 2)

    @field_validator("optimization_summary")
    @classmethod
    def validate_optimization_summary(cls, v: str) -> str:
        """验证优化摘要"""
        if not v or not v.strip():
            error_msg = "优化摘要不能为空"
            raise ValueError(error_msg)
        return v.strip()

    def get_average_score(self) -> float:
        """
        获取平均评分

        Returns:
            平均评分
        """
        scores = [
            self.quality_score,
            self.completeness_score,
            self.coherence_score,
            self.relevance_score,
        ]
        return round(sum(scores) / len(scores), 2)

    def has_issues(self) -> bool:
        """
        检查是否有潜在问题

        Returns:
            是否有潜在问题
        """
        return len(self.potential_issues) > 0

    def has_improvements(self) -> bool:
        """
        检查是否有改进点

        Returns:
            是否有改进点
        """
        return len(self.key_improvements) > 0

    def add_improvement(self, improvement: str) -> None:
        """
        添加改进点

        Args:
            improvement: 改进点描述
        """
        if improvement and improvement.strip():
            improvement_text = improvement.strip()
            if improvement_text not in self.key_improvements:
                new_improvements = self.key_improvements.copy()
                new_improvements.append(improvement_text)
                self.key_improvements = new_improvements

    def add_issue(self, issue: str) -> None:
        """
        添加潜在问题

        Args:
            issue: 问题描述
        """
        if issue and issue.strip():
            issue_text = issue.strip()
            if issue_text not in self.potential_issues:
                new_issues = self.potential_issues.copy()
                new_issues.append(issue_text)
                self.potential_issues = new_issues

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "optimized_outline_id": str(self.optimized_outline_id),
            "total_changes": self.total_changes,
            "added_items": self.added_items,
            "modified_items": self.modified_items,
            "deleted_items": self.deleted_items,
            "moved_items": self.moved_items,
            "reordered_items": self.reordered_items,
            "merged_items": self.merged_items,
            "split_items": self.split_items,
            "quality_score": self.quality_score,
            "completeness_score": self.completeness_score,
            "coherence_score": self.coherence_score,
            "relevance_score": self.relevance_score,
            "average_score": self.get_average_score(),
            "optimization_summary": self.optimization_summary,
            "key_improvements": self.key_improvements,
            "potential_issues": self.potential_issues,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class OptimizedOutline(BaseModel):
    """
    优化后的大纲领域模型

    表示AI优化后的大纲,包含优化后的项,优化摘要,用户反馈等.
    与Outline领域模型配合使用,Outline表示用户手写的大纲,OptimizedOutline表示AI优化后的大纲.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="优化大纲唯一标识")
    original_outline_id: uuid.UUID = Field(..., description="原始大纲ID")

    # 优化后的大纲项
    optimized_items: list[OptimizedOutlineItem] = Field(
        default_factory=list, description="优化后的大纲项列表"
    )

    # 优化摘要
    summary: OptimizationSummary | None = Field(None, description="优化摘要")

    # 用户反馈
    is_accepted: bool = Field(False, description="用户是否接受整个优化")
    user_feedback: str | None = Field(None, description="用户整体反馈")

    # 优化状态
    optimization_status: str = Field("PENDING", description="优化状态(PENDING/ACCEPTED/REJECTED)")

    # 时间字段
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="更新时间"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("optimization_status")
    @classmethod
    def validate_optimization_status(cls, v: str) -> str:
        """验证优化状态"""
        valid_statuses = ["PENDING", "ACCEPTED", "REJECTED"]
        if v not in valid_statuses:
            error_msg = f"优化状态必须是以下之一: {', '.join(valid_statuses)}"
            raise ValueError(error_msg)
        return v

    @field_validator("user_feedback")
    @classmethod
    def validate_user_feedback(cls, v: str | None) -> str | None:
        """验证用户反馈"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @model_validator(mode="after")
    def validate_consistency(self) -> "OptimizedOutline":
        """验证字段一致性"""
        # 验证所有优化项的original_outline_id是否一致
        for item in self.optimized_items:
            if item.original_outline_id != self.original_outline_id:
                # 这里只是警告,不抛出异常
                pass

        return self

    def add_optimized_item(self, item: OptimizedOutlineItem) -> None:
        """
        添加优化项

        Args:
            item: 优化项
        """
        # 验证原始大纲ID是否匹配
        if item.original_outline_id != self.original_outline_id:
            error_msg = f"优化项的原始大纲ID {item.original_outline_id} 与当前大纲ID {self.original_outline_id} 不匹配"
            raise ValueError(error_msg)

        # 检查是否已存在相同ID的项
        if any(existing.id == item.id for existing in self.optimized_items):
            error_msg = f"优化项 {item.id} 已存在"
            raise ValueError(error_msg)

        new_items = self.optimized_items.copy()
        new_items.append(item)
        self.optimized_items = new_items
        self._touch()

    def remove_optimized_item(self, item_id: uuid.UUID) -> bool:
        """
        移除优化项

        Args:
            item_id: 优化项ID

        Returns:
            是否成功移除
        """
        for i, item in enumerate(self.optimized_items):
            if item.id == item_id:
                new_items = self.optimized_items.copy()
                new_items.pop(i)
                self.optimized_items = new_items
                self._touch()
                return True
        return False

    def get_optimized_item(self, item_id: uuid.UUID) -> OptimizedOutlineItem | None:
        """
        获取优化项

        Args:
            item_id: 优化项ID

        Returns:
            优化项(如果找到)
        """
        for item in self.optimized_items:
            if item.id == item_id:
                return item
        return None

    def get_items_by_change_type(
        self, change_type: OptimizationChangeType
    ) -> list[OptimizedOutlineItem]:
        """
        按变更类型获取优化项

        Args:
            change_type: 变更类型

        Returns:
            指定变更类型的优化项列表
        """
        return [item for item in self.optimized_items if item.change_type == change_type]

    def get_new_items(self) -> list[OptimizedOutlineItem]:
        """
        获取新增项

        Returns:
            新增项列表
        """
        return self.get_items_by_change_type(OptimizationChangeType.ADD)

    def get_modified_items(self) -> list[OptimizedOutlineItem]:
        """
        获取修改项

        Returns:
            修改项列表
        """
        return self.get_items_by_change_type(OptimizationChangeType.MODIFY)

    def get_deleted_items(self) -> list[OptimizedOutlineItem]:
        """
        获取删除项

        Returns:
            删除项列表
        """
        return self.get_items_by_change_type(OptimizationChangeType.DELETE)

    def get_moved_items(self) -> list[OptimizedOutlineItem]:
        """
        获取移动项

        Returns:
            移动项列表
        """
        return self.get_items_by_change_type(OptimizationChangeType.MOVE)

    def get_changed_items(self) -> list[OptimizedOutlineItem]:
        """
        获取所有变更项

        Returns:
            变更项列表
        """
        return [item for item in self.optimized_items if item.has_change()]

    def get_unchanged_items(self) -> list[OptimizedOutlineItem]:
        """
        获取未变更项

        Returns:
            未变更项列表
        """
        return [item for item in self.optimized_items if not item.has_change()]

    def set_summary(self, summary: OptimizationSummary) -> None:
        """
        设置优化摘要

        Args:
            summary: 优化摘要
        """
        # 验证摘要ID是否匹配
        if summary.optimized_outline_id != self.id:
            error_msg = f"优化摘要的大纲ID {summary.optimized_outline_id} 与当前大纲ID {self.id} 不匹配"
            raise ValueError(error_msg)

        self.summary = summary
        self._touch()

    def accept_all_optimizations(self, feedback: str | None = None) -> None:
        """
        接受所有优化

        Args:
            feedback: 用户整体反馈
        """
        self.is_accepted = True
        self.optimization_status = "ACCEPTED"
        if feedback:
            self.user_feedback = feedback.strip() if feedback.strip() else None

        # 接受所有优化项
        for item in self.optimized_items:
            item.accept_optimization()

        self._touch()

    def reject_all_optimizations(self, feedback: str | None = None) -> None:
        """
        拒绝所有优化

        Args:
            feedback: 用户整体反馈
        """
        self.is_accepted = False
        self.optimization_status = "REJECTED"
        if feedback:
            self.user_feedback = feedback.strip() if feedback.strip() else None

        # 拒绝所有优化项
        for item in self.optimized_items:
            item.reject_optimization()

        self._touch()

    def accept_item(self, item_id: uuid.UUID, feedback: str | None = None) -> bool:
        """
        接受单个优化项

        Args:
            item_id: 优化项ID
            feedback: 用户反馈

        Returns:
            是否成功接受
        """
        item = self.get_optimized_item(item_id)
        if item:
            item.accept_optimization(feedback)
            self._touch()
            return True
        return False

    def reject_item(self, item_id: uuid.UUID, feedback: str | None = None) -> bool:
        """
        拒绝单个优化项

        Args:
            item_id: 优化项ID
            feedback: 用户反馈

        Returns:
            是否成功拒绝
        """
        item = self.get_optimized_item(item_id)
        if item:
            item.reject_optimization(feedback)
            self._touch()
            return True
        return False

    def calculate_change_statistics(self) -> dict[str, int]:
        """
        计算变更统计

        Returns:
            变更统计信息
        """
        stats = {
            "total": len(self.optimized_items),
            "added": len(self.get_new_items()),
            "modified": len(self.get_modified_items()),
            "deleted": len(self.get_deleted_items()),
            "moved": len(self.get_moved_items()),
            "changed": len(self.get_changed_items()),
            "unchanged": len(self.get_unchanged_items()),
        }
        return stats

    def generate_optimized_outline(self) -> Outline:
        """
        生成优化后的大纲(Outline对象)

        根据用户接受/拒绝的优化项,生成最终的大纲.

        Returns:
            优化后的大纲(Outline对象)
        """
        # 创建新的大纲对象
        # 注意:这里需要原始大纲的信息,但当前模型没有存储原始大纲
        # 实际使用时,需要从数据库或其他地方获取原始大纲
        # 这里返回一个基础的大纲结构
        msg = "此方法需要原始大纲信息,请使用服务层实现"
        raise NotImplementedError(msg)

    def build_tree(self) -> list[dict[str, Any]]:
        """
        构建优化后大纲的树结构

        Returns:
            树形结构的优化大纲(包含嵌套的children)
        """
        def build_node(item: OptimizedOutlineItem) -> dict[str, Any]:
            """递归构建节点"""
            # 获取子项
            children = [
                child
                for child in self.optimized_items
                if child.optimized_item.parent_id == item.optimized_item.id
            ]
            # 按order排序
            children_sorted = sorted(children, key=lambda x: x.optimized_item.order)

            return {
                "id": str(item.id),
                "optimized_item_id": str(item.optimized_item.id),
                "title": item.optimized_item.title,
                "description": item.optimized_item.description,
                "item_type": item.optimized_item.item_type.value
                if hasattr(item.optimized_item.item_type, "value")
                else item.optimized_item.item_type,
                "level": item.optimized_item.level,
                "order": item.optimized_item.order,
                "change_type": item.change_type.value
                if hasattr(item.change_type, "value")
                else item.change_type,
                "is_accepted": item.is_accepted,
                "optimization_suggestions": item.optimization_suggestions,
                "children": [build_node(child) for child in children_sorted],
            }

        # 获取根级项
        root_items = [
            item for item in self.optimized_items if item.optimized_item.parent_id is None
        ]
        # 按order排序
        root_items_sorted = sorted(root_items, key=lambda x: x.optimized_item.order)
        return [build_node(item) for item in root_items_sorted]

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

    def is_pending(self) -> bool:
        """
        检查是否为待确认状态

        Returns:
            是否为待确认状态
        """
        return self.optimization_status == "PENDING"

    def is_accepted_status(self) -> bool:
        """
        检查是否为已接受状态

        Returns:
            是否为已接受状态
        """
        return self.optimization_status == "ACCEPTED"

    def is_rejected_status(self) -> bool:
        """
        检查是否为已拒绝状态

        Returns:
            是否为已拒绝状态
        """
        return self.optimization_status == "REJECTED"

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "original_outline_id": str(self.original_outline_id),
            "optimized_items": [item.to_dict() for item in self.optimized_items],
            "summary": self.summary.to_dict() if self.summary else None,
            "is_accepted": self.is_accepted,
            "user_feedback": self.user_feedback,
            "optimization_status": self.optimization_status,
            "change_statistics": self.calculate_change_statistics(),
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
        original_outline: Outline,
        optimized_items_data: list[dict[str, Any]] | None = None,
    ) -> "OptimizedOutline":
        """
        从原始大纲创建优化大纲

        Args:
            original_outline: 原始大纲
            optimized_items_data: 优化项数据列表(可选)

        Returns:
            优化大纲对象
        """
        optimized_outline = cls(
            original_outline_id=original_outline.id,
            summary=None,
            is_accepted=False,
            user_feedback=None,
            optimization_status="PENDING",
        )

        # 如果提供了优化项数据,创建优化项
        if optimized_items_data:
            for item_data in optimized_items_data:
                # 获取原始项(如果存在)
                original_item_id = item_data.get("original_item_id")
                original_item = None
                if original_item_id:
                    original_item = original_outline.get_item(
                        uuid.UUID(original_item_id)
                    )

                # 创建优化后项
                optimized_item_data = item_data.get("optimized_item", {})
                if isinstance(optimized_item_data, dict):
                    optimized_item = OutlineItem(**optimized_item_data)
                else:
                    # 如果没有提供优化项,使用原始项
                    optimized_item = original_item or OutlineItem(
                        title="未命名",
                        item_type=OutlineItemType.SECTION,
                        level=1,
                        order=1,
                        description=None,
                        is_optimized=False,
                        original_title=None,
                        original_description=None,
                        parent_id=None,
                    )

                # 创建优化项
                optimized_item_obj = OptimizedOutlineItem(
                    original_outline_id=original_outline.id,
                    original_item_id=uuid.UUID(original_item_id) if original_item_id else None,
                    original_item=original_item,
                    optimized_item=optimized_item,
                    change_type=OptimizationChangeType(
                        item_data.get("change_type", "NONE")
                    ),
                    change_description=item_data.get("change_description"),
                    optimization_reason=item_data.get("optimization_reason"),
                    optimization_suggestions=item_data.get(
                        "optimization_suggestions", []
                    ),
                    is_accepted=False,
                    user_feedback=None,
                )

                optimized_outline.add_optimized_item(optimized_item_obj)

        return optimized_outline

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


# 便利函数


def create_optimized_outline_from_outline(
    original_outline: Outline,
    optimized_items_data: list[dict[str, Any]] | None = None,
) -> OptimizedOutline:
    """
    从原始大纲创建优化大纲的便捷函数

    Args:
        original_outline: 原始大纲
        optimized_items_data: 优化项数据列表

    Returns:
        优化大纲对象
    """
    return OptimizedOutline.create_from_outline(
        original_outline=original_outline,
        optimized_items_data=optimized_items_data,
    )
