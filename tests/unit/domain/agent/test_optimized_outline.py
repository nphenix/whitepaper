"""
优化大纲领域模型单元测试

测试OptimizedOutline、OptimizedOutlineItem、OptimizationSummary等模型的各项功能。
"""

# 生成命令: /speckit.implement T210
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime

import pytest

from src.domain.agent.optimized_outline import (
    OptimizationChangeType,
    OptimizationSummary,
    OptimizedOutline,
    OptimizedOutlineItem,
    create_optimized_outline_from_outline,
)
from src.domain.agent.outline import Outline, OutlineItem, OutlineItemType, OutlineStatus


class TestOptimizationChangeType:
    """测试OptimizationChangeType枚举"""

    def test_enum_values(self) -> None:
        """测试枚举值"""
        assert OptimizationChangeType.ADD.value == "ADD"
        assert OptimizationChangeType.MODIFY.value == "MODIFY"
        assert OptimizationChangeType.DELETE.value == "DELETE"
        assert OptimizationChangeType.MOVE.value == "MOVE"
        assert OptimizationChangeType.REORDER.value == "REORDER"
        assert OptimizationChangeType.MERGE.value == "MERGE"
        assert OptimizationChangeType.SPLIT.value == "SPLIT"
        assert OptimizationChangeType.NONE.value == "NONE"


class TestOptimizedOutlineItem:
    """测试OptimizedOutlineItem模型"""

    def test_create_optimized_item(self) -> None:
        """测试创建优化项"""
        original_item = OutlineItem(
            title="原始标题",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=1,
        )

        optimized_item = OutlineItem(
            title="优化后标题",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=1,
        )

        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            original_item_id=original_item.id,
            original_item=original_item,
            optimized_item=optimized_item,
            change_type=OptimizationChangeType.MODIFY,
            change_description="修改标题",
            optimization_reason="标题不够清晰",
        )

        assert item.original_item_id == original_item.id
        assert item.optimized_item.title == "优化后标题"
        assert item.change_type == OptimizationChangeType.MODIFY
        assert item.change_description == "修改标题"
        assert item.optimization_reason == "标题不够清晰"

    def test_create_new_item(self) -> None:
        """测试创建新增项"""
        optimized_item = OutlineItem(
            title="新增章节",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=2,
        )

        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            optimized_item=optimized_item,
            change_type=OptimizationChangeType.ADD,
            change_description="新增章节",
            optimization_reason="补充缺失内容",
        )

        assert item.is_new_item()
        assert item.original_item_id is None
        assert item.original_item is None

    def test_is_new_item(self) -> None:
        """测试是否为新增项"""
        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            optimized_item=OutlineItem(
                title="新增", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.ADD,
        )
        assert item.is_new_item() is True
        assert item.is_modified_item() is False
        assert item.is_deleted_item() is False
        assert item.is_moved_item() is False

    def test_is_modified_item(self) -> None:
        """测试是否为修改项"""
        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            original_item=OutlineItem(
                title="原始", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            optimized_item=OutlineItem(
                title="修改后", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )
        assert item.is_new_item() is False
        assert item.is_modified_item() is True
        assert item.is_deleted_item() is False
        assert item.is_moved_item() is False

    def test_is_deleted_item(self) -> None:
        """测试是否为删除项"""
        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            original_item=OutlineItem(
                title="删除", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            optimized_item=OutlineItem(
                title="删除", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.DELETE,
        )
        assert item.is_new_item() is False
        assert item.is_modified_item() is False
        assert item.is_deleted_item() is True
        assert item.is_moved_item() is False

    def test_is_moved_item(self) -> None:
        """测试是否为移动项"""
        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            original_item=OutlineItem(
                title="移动", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            optimized_item=OutlineItem(
                title="移动", item_type=OutlineItemType.SECTION, level=1, order=2
            ),
            change_type=OptimizationChangeType.MOVE,
        )
        assert item.is_new_item() is False
        assert item.is_modified_item() is False
        assert item.is_deleted_item() is False
        assert item.is_moved_item() is True

    def test_has_change(self) -> None:
        """测试是否有变更"""
        item_with_change = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            optimized_item=OutlineItem(
                title="有变更", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )
        assert item_with_change.has_change() is True

        item_no_change = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            optimized_item=OutlineItem(
                title="无变更", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.NONE,
        )
        assert item_no_change.has_change() is False

    def test_accept_optimization(self) -> None:
        """测试接受优化"""
        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        assert item.is_accepted is False

        item.accept_optimization("接受建议")
        assert item.is_accepted is True
        assert item.user_feedback == "接受建议"

    def test_reject_optimization(self) -> None:
        """测试拒绝优化"""
        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        item.accept_optimization("先接受")
        assert item.is_accepted is True

        item.reject_optimization("改为拒绝")
        assert item.is_accepted is False
        assert item.user_feedback == "改为拒绝"

    def test_add_suggestion(self) -> None:
        """测试添加优化建议"""
        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        assert len(item.optimization_suggestions) == 0

        item.add_suggestion("建议1")
        assert len(item.optimization_suggestions) == 1
        assert "建议1" in item.optimization_suggestions

        item.add_suggestion("建议2")
        assert len(item.optimization_suggestions) == 2

        # 重复建议不会添加
        item.add_suggestion("建议1")
        assert len(item.optimization_suggestions) == 2

    def test_get_change_summary(self) -> None:
        """测试获取变更摘要"""
        original_item = OutlineItem(
            title="原始标题",
            description="原始描述",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=1,
        )

        optimized_item = OutlineItem(
            title="优化后标题",
            description="优化后描述",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=2,
        )

        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            original_item_id=original_item.id,
            original_item=original_item,
            optimized_item=optimized_item,
            change_type=OptimizationChangeType.MODIFY,
            change_description="修改标题和描述",
        )

        summary = item.get_change_summary()
        assert summary["change_type"] == "MODIFY"
        assert summary["title_before"] == "原始标题"
        assert summary["title_after"] == "优化后标题"
        assert summary["description_before"] == "原始描述"
        assert summary["description_after"] == "优化后描述"
        assert summary["order_before"] == 1
        assert summary["order_after"] == 2

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        item_dict = item.to_dict()
        assert "id" in item_dict
        assert "original_outline_id" in item_dict
        assert "optimized_item" in item_dict
        assert "change_type" in item_dict
        assert item_dict["change_type"] == "MODIFY"


class TestOptimizationSummary:
    """测试OptimizationSummary模型"""

    def test_create_summary(self) -> None:
        """测试创建优化摘要"""
        summary = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            total_changes=10,
            added_items=2,
            modified_items=5,
            deleted_items=1,
            moved_items=2,
            optimization_summary="本次优化共进行了10项变更",
        )

        assert summary.total_changes == 10
        assert summary.added_items == 2
        assert summary.modified_items == 5
        assert summary.deleted_items == 1
        assert summary.moved_items == 2

    def test_quality_score_validation(self) -> None:
        """测试质量评分验证"""
        from pydantic import ValidationError

        # 测试大于1的值
        with pytest.raises(ValidationError):
            OptimizationSummary(
                optimized_outline_id=uuid.uuid4(),
                quality_score=1.5,
                optimization_summary="测试",
            )

        # 测试小于0的值
        with pytest.raises(ValidationError):
            OptimizationSummary(
                optimized_outline_id=uuid.uuid4(),
                quality_score=-0.1,
                optimization_summary="测试",
            )

        # 测试边界值
        summary = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            quality_score=0.0,
            optimization_summary="测试",
        )
        assert summary.quality_score == 0.0

        summary = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            quality_score=1.0,
            optimization_summary="测试",
        )
        assert summary.quality_score == 1.0

    def test_get_average_score(self) -> None:
        """测试获取平均评分"""
        summary = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            quality_score=0.8,
            completeness_score=0.9,
            coherence_score=0.7,
            relevance_score=0.85,
            optimization_summary="测试",
        )

        average = summary.get_average_score()
        expected = (0.8 + 0.9 + 0.7 + 0.85) / 4
        assert average == round(expected, 2)

    def test_has_issues(self) -> None:
        """测试是否有潜在问题"""
        summary_with_issues = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            optimization_summary="测试",
            potential_issues=["问题1", "问题2"],
        )
        assert summary_with_issues.has_issues() is True

        summary_no_issues = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            optimization_summary="测试",
        )
        assert summary_no_issues.has_issues() is False

    def test_has_improvements(self) -> None:
        """测试是否有改进点"""
        summary_with_improvements = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            optimization_summary="测试",
            key_improvements=["改进1", "改进2"],
        )
        assert summary_with_improvements.has_improvements() is True

        summary_no_improvements = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            optimization_summary="测试",
        )
        assert summary_no_improvements.has_improvements() is False

    def test_add_improvement(self) -> None:
        """测试添加改进点"""
        summary = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            optimization_summary="测试",
        )

        assert len(summary.key_improvements) == 0

        summary.add_improvement("改进1")
        assert len(summary.key_improvements) == 1

        summary.add_improvement("改进2")
        assert len(summary.key_improvements) == 2

        # 重复改进不会添加
        summary.add_improvement("改进1")
        assert len(summary.key_improvements) == 2

    def test_add_issue(self) -> None:
        """测试添加潜在问题"""
        summary = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            optimization_summary="测试",
        )

        assert len(summary.potential_issues) == 0

        summary.add_issue("问题1")
        assert len(summary.potential_issues) == 1

        summary.add_issue("问题2")
        assert len(summary.potential_issues) == 2

        # 重复问题不会添加
        summary.add_issue("问题1")
        assert len(summary.potential_issues) == 2

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        summary = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),
            quality_score=0.8,
            completeness_score=0.9,
            optimization_summary="测试摘要",
        )

        summary_dict = summary.to_dict()
        assert "id" in summary_dict
        assert "optimized_outline_id" in summary_dict
        assert "quality_score" in summary_dict
        assert "average_score" in summary_dict
        assert summary_dict["optimization_summary"] == "测试摘要"


class TestOptimizedOutline:
    """测试OptimizedOutline模型"""

    def test_create_optimized_outline(self) -> None:
        """测试创建优化大纲"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(
            original_outline_id=outline_id,
        )

        assert optimized_outline.original_outline_id == outline_id
        assert len(optimized_outline.optimized_items) == 0
        assert optimized_outline.is_accepted is False
        assert optimized_outline.optimization_status == "PENDING"

    def test_add_optimized_item(self) -> None:
        """测试添加优化项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
        )

        optimized_outline.add_optimized_item(item)
        assert len(optimized_outline.optimized_items) == 1
        assert optimized_outline.optimized_items[0].id == item.id

    def test_add_optimized_item_with_wrong_outline_id(self) -> None:
        """测试添加优化项（错误的大纲ID）"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=uuid.uuid4(),  # 不同的ID
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
        )

        with pytest.raises(ValueError, match="优化项的原始大纲ID.*与当前大纲ID.*不匹配"):
            optimized_outline.add_optimized_item(item)

    def test_remove_optimized_item(self) -> None:
        """测试移除优化项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
        )

        optimized_outline.add_optimized_item(item)
        assert len(optimized_outline.optimized_items) == 1

        result = optimized_outline.remove_optimized_item(item.id)
        assert result is True
        assert len(optimized_outline.optimized_items) == 0

    def test_get_optimized_item(self) -> None:
        """测试获取优化项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
        )

        optimized_outline.add_optimized_item(item)

        found_item = optimized_outline.get_optimized_item(item.id)
        assert found_item is not None
        assert found_item.id == item.id

        not_found_item = optimized_outline.get_optimized_item(uuid.uuid4())
        assert not_found_item is None

    def test_get_items_by_change_type(self) -> None:
        """测试按变更类型获取优化项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        # 添加不同类型的项
        item1 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="新增", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.ADD,
        )

        item2 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="修改", item_type=OutlineItemType.SECTION, level=1, order=2
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        optimized_outline.add_optimized_item(item1)
        optimized_outline.add_optimized_item(item2)

        new_items = optimized_outline.get_items_by_change_type(
            OptimizationChangeType.ADD
        )
        assert len(new_items) == 1
        assert new_items[0].id == item1.id

        modified_items = optimized_outline.get_items_by_change_type(
            OptimizationChangeType.MODIFY
        )
        assert len(modified_items) == 1
        assert modified_items[0].id == item2.id

    def test_get_new_items(self) -> None:
        """测试获取新增项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="新增", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.ADD,
        )

        optimized_outline.add_optimized_item(item)

        new_items = optimized_outline.get_new_items()
        assert len(new_items) == 1
        assert new_items[0].id == item.id

    def test_get_modified_items(self) -> None:
        """测试获取修改项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="修改", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        optimized_outline.add_optimized_item(item)

        modified_items = optimized_outline.get_modified_items()
        assert len(modified_items) == 1
        assert modified_items[0].id == item.id

    def test_get_deleted_items(self) -> None:
        """测试获取删除项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="删除", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.DELETE,
        )

        optimized_outline.add_optimized_item(item)

        deleted_items = optimized_outline.get_deleted_items()
        assert len(deleted_items) == 1
        assert deleted_items[0].id == item.id

    def test_get_moved_items(self) -> None:
        """测试获取移动项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="移动", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MOVE,
        )

        optimized_outline.add_optimized_item(item)

        moved_items = optimized_outline.get_moved_items()
        assert len(moved_items) == 1
        assert moved_items[0].id == item.id

    def test_get_changed_items(self) -> None:
        """测试获取所有变更项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        # 添加有变更的项
        item1 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="变更1", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.ADD,
        )

        item2 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="变更2", item_type=OutlineItemType.SECTION, level=1, order=2
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        # 添加无变更的项
        item3 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="无变更", item_type=OutlineItemType.SECTION, level=1, order=3
            ),
            change_type=OptimizationChangeType.NONE,
        )

        optimized_outline.add_optimized_item(item1)
        optimized_outline.add_optimized_item(item2)
        optimized_outline.add_optimized_item(item3)

        changed_items = optimized_outline.get_changed_items()
        assert len(changed_items) == 2

        unchanged_items = optimized_outline.get_unchanged_items()
        assert len(unchanged_items) == 1
        assert unchanged_items[0].id == item3.id

    def test_set_summary(self) -> None:
        """测试设置优化摘要"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        summary = OptimizationSummary(
            optimized_outline_id=optimized_outline.id,
            optimization_summary="测试摘要",
        )

        optimized_outline.set_summary(summary)
        assert optimized_outline.summary is not None
        assert optimized_outline.summary.id == summary.id

    def test_set_summary_with_wrong_outline_id(self) -> None:
        """测试设置优化摘要（错误的大纲ID）"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        summary = OptimizationSummary(
            optimized_outline_id=uuid.uuid4(),  # 不同的ID
            optimization_summary="测试摘要",
        )

        with pytest.raises(ValueError, match="优化摘要的大纲ID.*与当前大纲ID.*不匹配"):
            optimized_outline.set_summary(summary)

    def test_accept_all_optimizations(self) -> None:
        """测试接受所有优化"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item1 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="测试1", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        item2 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="测试2", item_type=OutlineItemType.SECTION, level=1, order=2
            ),
            change_type=OptimizationChangeType.ADD,
        )

        optimized_outline.add_optimized_item(item1)
        optimized_outline.add_optimized_item(item2)

        optimized_outline.accept_all_optimizations("全部接受")
        assert optimized_outline.is_accepted is True
        assert optimized_outline.optimization_status == "ACCEPTED"
        assert optimized_outline.user_feedback == "全部接受"
        assert item1.is_accepted is True
        assert item2.is_accepted is True

    def test_reject_all_optimizations(self) -> None:
        """测试拒绝所有优化"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        optimized_outline.add_optimized_item(item)
        optimized_outline.accept_all_optimizations("先接受")

        optimized_outline.reject_all_optimizations("改为拒绝")
        assert optimized_outline.is_accepted is False
        assert optimized_outline.optimization_status == "REJECTED"
        assert optimized_outline.user_feedback == "改为拒绝"
        assert item.is_accepted is False

    def test_accept_item(self) -> None:
        """测试接受单个优化项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        optimized_outline.add_optimized_item(item)

        result = optimized_outline.accept_item(item.id, "接受")
        assert result is True
        assert item.is_accepted is True
        assert item.user_feedback == "接受"

    def test_reject_item(self) -> None:
        """测试拒绝单个优化项"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="测试", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        optimized_outline.add_optimized_item(item)

        result = optimized_outline.reject_item(item.id, "拒绝")
        assert result is True
        assert item.is_accepted is False
        assert item.user_feedback == "拒绝"

    def test_calculate_change_statistics(self) -> None:
        """测试计算变更统计"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        # 添加不同类型的项
        item1 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="新增", item_type=OutlineItemType.SECTION, level=1, order=1
            ),
            change_type=OptimizationChangeType.ADD,
        )

        item2 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="修改", item_type=OutlineItemType.SECTION, level=1, order=2
            ),
            change_type=OptimizationChangeType.MODIFY,
        )

        item3 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="删除", item_type=OutlineItemType.SECTION, level=1, order=3
            ),
            change_type=OptimizationChangeType.DELETE,
        )

        item4 = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="无变更", item_type=OutlineItemType.SECTION, level=1, order=4
            ),
            change_type=OptimizationChangeType.NONE,
        )

        optimized_outline.add_optimized_item(item1)
        optimized_outline.add_optimized_item(item2)
        optimized_outline.add_optimized_item(item3)
        optimized_outline.add_optimized_item(item4)

        stats = optimized_outline.calculate_change_statistics()
        assert stats["total"] == 4
        assert stats["added"] == 1
        assert stats["modified"] == 1
        assert stats["deleted"] == 1
        assert stats["moved"] == 0
        assert stats["changed"] == 3
        assert stats["unchanged"] == 1

    def test_is_pending(self) -> None:
        """测试是否为待确认状态"""
        optimized_outline = OptimizedOutline(
            original_outline_id=uuid.uuid4(), optimization_status="PENDING"
        )
        assert optimized_outline.is_pending() is True
        assert optimized_outline.is_accepted_status() is False
        assert optimized_outline.is_rejected_status() is False

    def test_is_accepted_status(self) -> None:
        """测试是否为已接受状态"""
        optimized_outline = OptimizedOutline(
            original_outline_id=uuid.uuid4(), optimization_status="ACCEPTED"
        )
        assert optimized_outline.is_pending() is False
        assert optimized_outline.is_accepted_status() is True
        assert optimized_outline.is_rejected_status() is False

    def test_is_rejected_status(self) -> None:
        """测试是否为已拒绝状态"""
        optimized_outline = OptimizedOutline(
            original_outline_id=uuid.uuid4(), optimization_status="REJECTED"
        )
        assert optimized_outline.is_pending() is False
        assert optimized_outline.is_accepted_status() is False
        assert optimized_outline.is_rejected_status() is True

    def test_build_tree(self) -> None:
        """测试构建树结构"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        # 创建层级结构
        root_item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="根章节",
                item_type=OutlineItemType.SECTION,
                level=1,
                order=1,
            ),
            change_type=OptimizationChangeType.NONE,
        )

        child_item = OptimizedOutlineItem(
            original_outline_id=outline_id,
            optimized_item=OutlineItem(
                title="子章节",
                item_type=OutlineItemType.SUBSECTION,
                level=2,
                order=1,
                parent_id=root_item.optimized_item.id,
            ),
            change_type=OptimizationChangeType.ADD,
        )

        optimized_outline.add_optimized_item(root_item)
        optimized_outline.add_optimized_item(child_item)

        tree = optimized_outline.build_tree()
        assert len(tree) == 1
        assert tree[0]["title"] == "根章节"
        assert len(tree[0]["children"]) == 1
        assert tree[0]["children"][0]["title"] == "子章节"

    def test_add_metadata(self) -> None:
        """测试添加元数据"""
        optimized_outline = OptimizedOutline(original_outline_id=uuid.uuid4())

        optimized_outline.add_metadata("key1", "value1")
        assert optimized_outline.get_metadata("key1") == "value1"

        optimized_outline.add_metadata("key1", "value2")
        assert optimized_outline.get_metadata("key1") == "value2"

    def test_remove_metadata(self) -> None:
        """测试移除元数据"""
        optimized_outline = OptimizedOutline(original_outline_id=uuid.uuid4())

        optimized_outline.add_metadata("key1", "value1")
        assert optimized_outline.remove_metadata("key1") is True
        assert optimized_outline.get_metadata("key1") is None

        assert optimized_outline.remove_metadata("key1") is False

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        outline_id = uuid.uuid4()
        optimized_outline = OptimizedOutline(original_outline_id=outline_id)

        outline_dict = optimized_outline.to_dict()
        assert "id" in outline_dict
        assert "original_outline_id" in outline_dict
        assert "optimized_items" in outline_dict
        assert "is_accepted" in outline_dict
        assert "optimization_status" in outline_dict
        assert "change_statistics" in outline_dict


class TestOptimizedOutlineFromOutline:
    """测试从原始大纲创建优化大纲"""

    def test_create_from_outline(self) -> None:
        """测试从原始大纲创建优化大纲"""
        # 创建原始大纲
        outline = Outline(
            title="测试大纲",
            industry_id=uuid.uuid4(),
            status=OutlineStatus.DRAFT,
        )

        # 添加大纲项
        item1 = OutlineItem(
            title="章节1",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=1,
        )
        item2 = OutlineItem(
            title="章节2",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=2,
        )
        outline.add_item(item1)
        outline.add_item(item2)

        # 创建优化大纲
        optimized_outline = OptimizedOutline.create_from_outline(outline)

        assert optimized_outline.original_outline_id == outline.id
        assert len(optimized_outline.optimized_items) == 0

    def test_create_from_outline_with_items(self) -> None:
        """测试从原始大纲创建优化大纲（带优化项）"""
        # 创建原始大纲
        outline = Outline(
            title="测试大纲",
            industry_id=uuid.uuid4(),
            status=OutlineStatus.DRAFT,
        )

        # 添加大纲项
        item1 = OutlineItem(
            title="原始章节",
            item_type=OutlineItemType.SECTION,
            level=1,
            order=1,
        )
        outline.add_item(item1)

        # 创建优化项数据
        optimized_items_data = [
            {
                "original_item_id": str(item1.id),
                "optimized_item": {
                    "title": "优化后章节",
                    "item_type": "SECTION",
                    "level": 1,
                    "order": 1,
                },
                "change_type": "MODIFY",
                "change_description": "修改标题",
                "optimization_reason": "标题不够清晰",
            },
            {
                "optimized_item": {
                    "title": "新增章节",
                    "item_type": "SECTION",
                    "level": 1,
                    "order": 2,
                },
                "change_type": "ADD",
                "change_description": "新增章节",
            },
        ]

        # 创建优化大纲
        optimized_outline = OptimizedOutline.create_from_outline(
            outline, optimized_items_data
        )

        assert optimized_outline.original_outline_id == outline.id
        assert len(optimized_outline.optimized_items) == 2

        # 验证修改项
        modified_item = optimized_outline.get_modified_items()[0]
        assert modified_item.original_item_id == item1.id
        assert modified_item.optimized_item.title == "优化后章节"
        assert modified_item.change_type == OptimizationChangeType.MODIFY

        # 验证新增项
        new_item = optimized_outline.get_new_items()[0]
        assert new_item.original_item_id is None
        assert new_item.optimized_item.title == "新增章节"
        assert new_item.change_type == OptimizationChangeType.ADD


class TestCreateOptimizedOutlineFromOutline:
    """测试便捷函数"""

    def test_create_optimized_outline_from_outline(self) -> None:
        """测试便捷函数"""
        outline = Outline(
            title="测试大纲",
            industry_id=uuid.uuid4(),
            status=OutlineStatus.DRAFT,
        )

        optimized_outline = create_optimized_outline_from_outline(outline)

        assert optimized_outline.original_outline_id == outline.id
        assert isinstance(optimized_outline, OptimizedOutline)
