"""
大纲优化建议展示服务

该模块提供大纲优化建议的展示功能,包括:
1. 新增章节展示
2. 调整顺序展示
3. 完善描述展示
4. 优化建议汇总和统计
5. 多种展示格式(文本,Markdown,JSON等)

用于MVP 4步流程中的第二步: 大纲手写和AI优化.

生成命令: /speckit.implement T214
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
from typing import Any

from src.domain.agent.optimized_outline import (
    OptimizationChangeType,
    OptimizedOutline,
)
from src.domain.agent.outline import Outline
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class OutlineOptimizationDisplay:
    """
    大纲优化建议展示服务

    提供优化建议的格式化展示功能,支持多种展示格式.
    """

    def __init__(self, optimized_outline: OptimizedOutline, original_outline: Outline | None = None):
        """初始化优化建议展示服务

        Args:
            optimized_outline: 优化后的大纲对象
            original_outline: 原始大纲对象(可选)
        """
        self.optimized_outline = optimized_outline
        self.original_outline = original_outline

    def get_change_type_display_name(self, change_type: OptimizationChangeType | str) -> str:
        """获取变更类型的显示名称

        Args:
            change_type: 变更类型

        Returns:
            显示名称
        """
        change_type_value = (
            change_type.value if hasattr(change_type, "value") else change_type
        )

        display_names = {
            "ADD": "新增章节",
            "MODIFY": "修改内容",
            "DELETE": "删除章节",
            "MOVE": "移动位置",
            "REORDER": "调整顺序",
            "MERGE": "合并章节",
            "SPLIT": "拆分章节",
            "NONE": "无变更",
        }
        return display_names.get(change_type_value, change_type_value)

    def get_change_type_emoji(self, change_type: OptimizationChangeType | str) -> str:
        """获取变更类型的Emoji图标

        Args:
            change_type: 变更类型

        Returns:
            Emoji图标
        """
        change_type_value = (
            change_type.value if hasattr(change_type, "value") else change_type
        )

        emojis = {
            "ADD": "+",
            "MODIFY": "✏️",
            "DELETE": "🗑️",
            "MOVE": "🔄",
            "REORDER": "📊",
            "MERGE": "🔗",
            "SPLIT": "✂️",
            "NONE": "✅",
        }
        return emojis.get(change_type_value, "📝")

    def get_change_type_color(self, change_type: OptimizationChangeType | str) -> str:
        """获取变更类型的颜色(用于Markdown/HTML)

        Args:
            change_type: 变更类型

        Returns:
            颜色代码
        """
        change_type_value = (
            change_type.value if hasattr(change_type, "value") else change_type
        )

        colors = {
            "ADD": "green",
            "MODIFY": "blue",
            "DELETE": "red",
            "MOVE": "orange",
            "REORDER": "purple",
            "MERGE": "cyan",
            "SPLIT": "yellow",
            "NONE": "gray",
        }
        return colors.get(change_type_value, "gray")

    def display_added_sections(self) -> list[dict[str, Any]]:
        """展示新增章节

        Returns:
            新增章节列表
        """
        added_items = self.optimized_outline.get_new_items()
        return [
            {
                "id": str(item.id),
                "title": item.optimized_item.title,
                "description": item.optimized_item.description,
                "level": item.optimized_item.level,
                "order": item.optimized_item.order,
                "optimization_reason": item.optimization_reason,
                "optimization_suggestions": item.optimization_suggestions,
                "display_name": self.get_change_type_display_name(item.change_type),
                "emoji": self.get_change_type_emoji(item.change_type),
                "color": self.get_change_type_color(item.change_type),
            }
            for item in added_items
        ]

    def display_reordered_sections(self) -> list[dict[str, Any]]:
        """展示调整顺序的章节

        Returns:
            调整顺序的章节列表
        """
        reordered_items = [
            item
            for item in self.optimized_outline.optimized_items
            if item.change_type == OptimizationChangeType.REORDER
        ]
        return [
            {
                "id": str(item.id),
                "original_item_id": str(item.original_item_id) if item.original_item_id else None,
                "title": item.optimized_item.title,
                "level": item.optimized_item.level,
                "order_before": item.original_item.order if item.original_item else None,
                "order_after": item.optimized_item.order,
                "change_description": item.change_description,
                "optimization_reason": item.optimization_reason,
                "optimization_suggestions": item.optimization_suggestions,
                "display_name": self.get_change_type_display_name(item.change_type),
                "emoji": self.get_change_type_emoji(item.change_type),
                "color": self.get_change_type_color(item.change_type),
            }
            for item in reordered_items
        ]

    def display_modified_descriptions(self) -> list[dict[str, Any]]:
        """展示完善描述的章节

        Returns:
            完善描述的章节列表
        """
        modified_items = self.optimized_outline.get_modified_items()
        return [
            {
                "id": str(item.id),
                "original_item_id": str(item.original_item_id) if item.original_item_id else None,
                "title": item.optimized_item.title,
                "description_before": item.original_item.description if item.original_item else None,
                "description_after": item.optimized_item.description,
                "change_description": item.change_description,
                "optimization_reason": item.optimization_reason,
                "optimization_suggestions": item.optimization_suggestions,
                "display_name": self.get_change_type_display_name(item.change_type),
                "emoji": self.get_change_type_emoji(item.change_type),
                "color": self.get_change_type_color(item.change_type),
            }
            for item in modified_items
        ]

    def display_moved_sections(self) -> list[dict[str, Any]]:
        """展示移动位置的章节

        Returns:
            移动位置的章节列表
        """
        moved_items = self.optimized_outline.get_moved_items()
        return [
            {
                "id": str(item.id),
                "original_item_id": str(item.original_item_id) if item.original_item_id else None,
                "title": item.optimized_item.title,
                "level": item.optimized_item.level,
                "parent_id_before": (
                    str(item.original_item.parent_id) if item.original_item and item.original_item.parent_id else None
                ),
                "parent_id_after": (
                    str(item.optimized_item.parent_id) if item.optimized_item.parent_id else None
                ),
                "change_description": item.change_description,
                "optimization_reason": item.optimization_reason,
                "optimization_suggestions": item.optimization_suggestions,
                "display_name": self.get_change_type_display_name(item.change_type),
                "emoji": self.get_change_type_emoji(item.change_type),
                "color": self.get_change_type_color(item.change_type),
            }
            for item in moved_items
        ]

    def display_deleted_sections(self) -> list[dict[str, Any]]:
        """展示删除的章节

        Returns:
            删除的章节列表
        """
        deleted_items = self.optimized_outline.get_deleted_items()
        return [
            {
                "id": str(item.id),
                "original_item_id": str(item.original_item_id) if item.original_item_id else None,
                "title": item.original_item.title if item.original_item else "",
                "description": item.original_item.description if item.original_item else None,
                "level": item.original_item.level if item.original_item else None,
                "change_description": item.change_description,
                "optimization_reason": item.optimization_reason,
                "optimization_suggestions": item.optimization_suggestions,
                "display_name": self.get_change_type_display_name(item.change_type),
                "emoji": self.get_change_type_emoji(item.change_type),
                "color": self.get_change_type_color(item.change_type),
            }
            for item in deleted_items
        ]

    def display_all_changes(self) -> dict[str, Any]:
        """展示所有变更

        Returns:
            所有变更的汇总
        """
        return {
            "added_sections": self.display_added_sections(),
            "modified_descriptions": self.display_modified_descriptions(),
            "reordered_sections": self.display_reordered_sections(),
            "moved_sections": self.display_moved_sections(),
            "deleted_sections": self.display_deleted_sections(),
            "change_statistics": self.optimized_outline.calculate_change_statistics(),
        }

    def display_summary(self) -> dict[str, Any]:
        """展示优化摘要

        Returns:
            优化摘要信息
        """
        summary = self.optimized_outline.summary
        if not summary:
            return {}

        return {
            "total_changes": summary.total_changes,
            "added_items": summary.added_items,
            "modified_items": summary.modified_items,
            "deleted_items": summary.deleted_items,
            "moved_items": summary.moved_items,
            "reordered_items": summary.reordered_items,
            "merged_items": summary.merged_items,
            "split_items": summary.split_items,
            "quality_score": summary.quality_score,
            "completeness_score": summary.completeness_score,
            "coherence_score": summary.coherence_score,
            "relevance_score": summary.relevance_score,
            "average_score": summary.get_average_score(),
            "optimization_summary": summary.optimization_summary,
            "key_improvements": summary.key_improvements,
            "potential_issues": summary.potential_issues,
        }

    def to_text(self) -> str:
        """转换为文本格式

        Returns:
            文本格式的优化建议
        """
        lines = []

        # 优化摘要
        summary = self.display_summary()
        if summary:
            lines.append("=" * 60)
            lines.append("优化摘要")
            lines.append("=" * 60)
            lines.append(f"总变更数: {summary.get('total_changes', 0)}")
            lines.append(f"新增章节: {summary.get('added_items', 0)}")
            lines.append(f"修改内容: {summary.get('modified_items', 0)}")
            lines.append(f"删除章节: {summary.get('deleted_items', 0)}")
            lines.append(f"移动位置: {summary.get('moved_items', 0)}")
            lines.append(f"调整顺序: {summary.get('reordered_items', 0)}")
            lines.append(f"质量评分: {summary.get('quality_score', 0):.2f}")
            lines.append(f"完整度评分: {summary.get('completeness_score', 0):.2f}")
            lines.append(f"连贯性评分: {summary.get('coherence_score', 0):.2f}")
            lines.append(f"相关性评分: {summary.get('relevance_score', 0):.2f}")
            lines.append(f"平均评分: {summary.get('average_score', 0):.2f}")
            lines.append("")
            lines.append("优化摘要描述:")
            lines.append(summary.get("optimization_summary", ""))
            lines.append("")

            # 关键改进点
            if summary.get("key_improvements"):
                lines.append("关键改进点:")
                for improvement in summary["key_improvements"]:
                    lines.append(f"  - {improvement}")
                lines.append("")

            # 潜在问题
            if summary.get("potential_issues"):
                lines.append("潜在问题:")
                for issue in summary["potential_issues"]:
                    lines.append(f"  - {issue}")
                lines.append("")

        # 新增章节
        added_sections = self.display_added_sections()
        if added_sections:
            lines.append("=" * 60)
            lines.append("新增章节")
            lines.append("=" * 60)
            for section in added_sections:
                indent = "  " * (section["level"] - 1)
                lines.append(f"{indent}{section['emoji']} {section['title']}")
                if section.get("description"):
                    lines.append(f"{indent}  描述: {section['description']}")
                if section.get("optimization_reason"):
                    lines.append(f"{indent}  原因: {section['optimization_reason']}")
                if section.get("optimization_suggestions"):
                    lines.append(f"{indent}  建议:")
                    for suggestion in section["optimization_suggestions"]:
                        lines.append(f"{indent}    - {suggestion}")
                lines.append("")

        # 完善描述
        modified_descriptions = self.display_modified_descriptions()
        if modified_descriptions:
            lines.append("=" * 60)
            lines.append("完善描述")
            lines.append("=" * 60)
            for item in modified_descriptions:
                lines.append(f"{item['emoji']} {item['title']}")
                if item.get("description_before"):
                    lines.append(f"  原描述: {item['description_before']}")
                if item.get("description_after"):
                    lines.append(f"  新描述: {item['description_after']}")
                if item.get("change_description"):
                    lines.append(f"  变更: {item['change_description']}")
                if item.get("optimization_suggestions"):
                    lines.append("  建议:")
                    for suggestion in item["optimization_suggestions"]:
                        lines.append(f"    - {suggestion}")
                lines.append("")

        # 调整顺序
        reordered_sections = self.display_reordered_sections()
        if reordered_sections:
            lines.append("=" * 60)
            lines.append("调整顺序")
            lines.append("=" * 60)
            for item in reordered_sections:
                lines.append(f"{item['emoji']} {item['title']}")
                lines.append(f"  原顺序: {item['order_before']} -> 新顺序: {item['order_after']}")
                if item.get("change_description"):
                    lines.append(f"  变更: {item['change_description']}")
                if item.get("optimization_suggestions"):
                    lines.append("  建议:")
                    for suggestion in item["optimization_suggestions"]:
                        lines.append(f"    - {suggestion}")
                lines.append("")

        # 移动位置
        moved_sections = self.display_moved_sections()
        if moved_sections:
            lines.append("=" * 60)
            lines.append("移动位置")
            lines.append("=" * 60)
            for item in moved_sections:
                lines.append(f"{item['emoji']} {item['title']}")
                lines.append(f"  原父级: {item['parent_id_before']} -> 新父级: {item['parent_id_after']}")
                if item.get("change_description"):
                    lines.append(f"  变更: {item['change_description']}")
                if item.get("optimization_suggestions"):
                    lines.append("  建议:")
                    for suggestion in item["optimization_suggestions"]:
                        lines.append(f"    - {suggestion}")
                lines.append("")

        # 删除章节
        deleted_sections = self.display_deleted_sections()
        if deleted_sections:
            lines.append("=" * 60)
            lines.append("删除章节")
            lines.append("=" * 60)
            for item in deleted_sections:
                indent = "  " * (item["level"] - 1)
                lines.append(f"{indent}{item['emoji']} {item['title']}")
                if item.get("description"):
                    lines.append(f"{indent}  描述: {item['description']}")
                if item.get("optimization_reason"):
                    lines.append(f"{indent}  原因: {item['optimization_reason']}")
                if item.get("optimization_suggestions"):
                    lines.append(f"{indent}  建议:")
                    for suggestion in item["optimization_suggestions"]:
                        lines.append(f"{indent}    - {suggestion}")
                lines.append("")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """转换为Markdown格式

        Returns:
            Markdown格式的优化建议
        """
        lines = []

        # 优化摘要
        summary = self.display_summary()
        if summary:
            lines.append("# 大纲优化摘要")
            lines.append("")
            lines.append("## 变更统计")
            lines.append("")
            lines.append("| 指标 | 数值 |")
            lines.append("|------|------|")
            lines.append(f"| 总变更数 | {summary.get('total_changes', 0)} |")
            lines.append(f"| 新增章节 | {summary.get('added_items', 0)} |")
            lines.append(f"| 修改内容 | {summary.get('modified_items', 0)} |")
            lines.append(f"| 删除章节 | {summary.get('deleted_items', 0)} |")
            lines.append(f"| 移动位置 | {summary.get('moved_items', 0)} |")
            lines.append(f"| 调整顺序 | {summary.get('reordered_items', 0)} |")
            lines.append("")
            lines.append("## 质量评分")
            lines.append("")
            lines.append("| 评分项 | 分数 |")
            lines.append("|--------|------|")
            lines.append(f"| 质量评分 | {summary.get('quality_score', 0):.2f} |")
            lines.append(f"| 完整度评分 | {summary.get('completeness_score', 0):.2f} |")
            lines.append(f"| 连贯性评分 | {summary.get('coherence_score', 0):.2f} |")
            lines.append(f"| 相关性评分 | {summary.get('relevance_score', 0):.2f} |")
            lines.append(f"| 平均评分 | {summary.get('average_score', 0):.2f} |")
            lines.append("")
            lines.append("## 优化摘要")
            lines.append("")
            lines.append(summary.get("optimization_summary", ""))
            lines.append("")

            # 关键改进点
            if summary.get("key_improvements"):
                lines.append("## 关键改进点")
                lines.append("")
                for improvement in summary["key_improvements"]:
                    lines.append(f"- {improvement}")
                lines.append("")

            # 潜在问题
            if summary.get("potential_issues"):
                lines.append("## 潜在问题")
                lines.append("")
                for issue in summary["potential_issues"]:
                    lines.append(f"- {issue}")
                lines.append("")

        # 新增章节
        added_sections = self.display_added_sections()
        if added_sections:
            lines.append("# 新增章节")
            lines.append("")
            for section in added_sections:
                indent = "  " * (section["level"] - 1)
                header_level = min(section["level"] + 1, 6)
                lines.append(f"{indent}{'#' * header_level} {section['emoji']} {section['title']}")
                if section.get("description"):
                    lines.append(f"{indent}**描述**: {section['description']}")
                if section.get("optimization_reason"):
                    lines.append(f"{indent}**原因**: {section['optimization_reason']}")
                if section.get("optimization_suggestions"):
                    lines.append(f"{indent}**建议**:")
                    for suggestion in section["optimization_suggestions"]:
                        lines.append(f"{indent}  - {suggestion}")
                lines.append("")

        # 完善描述
        modified_descriptions = self.display_modified_descriptions()
        if modified_descriptions:
            lines.append("# 完善描述")
            lines.append("")
            for item in modified_descriptions:
                lines.append(f"## {item['emoji']} {item['title']}")
                if item.get("description_before"):
                    lines.append(f"**原描述**: {item['description_before']}")
                if item.get("description_after"):
                    lines.append(f"**新描述**: {item['description_after']}")
                if item.get("change_description"):
                    lines.append(f"**变更**: {item['change_description']}")
                if item.get("optimization_suggestions"):
                    lines.append("**建议**:")
                    for suggestion in item["optimization_suggestions"]:
                        lines.append(f"  - {suggestion}")
                lines.append("")

        # 调整顺序
        reordered_sections = self.display_reordered_sections()
        if reordered_sections:
            lines.append("# 调整顺序")
            lines.append("")
            for item in reordered_sections:
                lines.append(f"## {item['emoji']} {item['title']}")
                lines.append(f"**原顺序**: {item['order_before']} → **新顺序**: {item['order_after']}")
                if item.get("change_description"):
                    lines.append(f"**变更**: {item['change_description']}")
                if item.get("optimization_suggestions"):
                    lines.append("**建议**:")
                    for suggestion in item["optimization_suggestions"]:
                        lines.append(f"  - {suggestion}")
                lines.append("")

        # 移动位置
        moved_sections = self.display_moved_sections()
        if moved_sections:
            lines.append("# 移动位置")
            lines.append("")
            for item in moved_sections:
                lines.append(f"## {item['emoji']} {item['title']}")
                lines.append(f"**原父级**: {item['parent_id_before']} → **新父级**: {item['parent_id_after']}")
                if item.get("change_description"):
                    lines.append(f"**变更**: {item['change_description']}")
                if item.get("optimization_suggestions"):
                    lines.append("**建议**:")
                    for suggestion in item["optimization_suggestions"]:
                        lines.append(f"  - {suggestion}")
                lines.append("")

        # 删除章节
        deleted_sections = self.display_deleted_sections()
        if deleted_sections:
            lines.append("# 删除章节")
            lines.append("")
            for item in deleted_sections:
                indent = "  " * (item["level"] - 1)
                header_level = min(item["level"] + 1, 6)
                lines.append(f"{indent}{'#' * header_level} {item['emoji']} {item['title']}")
                if item.get("description"):
                    lines.append(f"{indent}**描述**: {item['description']}")
                if item.get("optimization_reason"):
                    lines.append(f"{indent}**原因**: {item['optimization_reason']}")
                if item.get("optimization_suggestions"):
                    lines.append(f"{indent}**建议**:")
                    for suggestion in item["optimization_suggestions"]:
                        lines.append(f"{indent}  - {suggestion}")
                lines.append("")

        return "\n".join(lines)

    def to_json(self, indent: int = 2) -> str:
        """转换为JSON格式

        Args:
            indent: JSON缩进空格数

        Returns:
            JSON格式的优化建议
        """
        data = {
            "summary": self.display_summary(),
            "changes": self.display_all_changes(),
        }
        return json.dumps(data, ensure_ascii=False, indent=indent)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式

        Returns:
            字典格式的优化建议
        """
        return {
            "summary": self.display_summary(),
            "changes": self.display_all_changes(),
            "optimized_outline": self.optimized_outline.to_dict(),
            "original_outline": self.original_outline.to_dict() if self.original_outline else None,
        }


# 便利函数


def create_optimization_display(
    optimized_outline: OptimizedOutline,
    original_outline: Outline | None = None,
) -> OutlineOptimizationDisplay:
    """创建优化建议展示对象的便捷函数

    Args:
        optimized_outline: 优化后的大纲对象
        original_outline: 原始大纲对象(可选)

    Returns:
        OutlineOptimizationDisplay实例
    """
    return OutlineOptimizationDisplay(
        optimized_outline=optimized_outline,
        original_outline=original_outline,
    )
