"""
T214: 大纲优化建议展示功能测试

测试大纲优化建议展示服务的各种功能，包括：
1. 新增章节展示
2. 调整顺序展示
3. 完善描述展示
4. 优化建议汇总和统计
5. 多种展示格式（文本、Markdown、JSON等）

生成命令: /speckit.implement T214
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid

import pytest

from src.application.services.outline_optimization_display import (
    OutlineOptimizationDisplay,
    create_optimization_display,
)
from src.domain.agent.optimized_outline import (
    OptimizationChangeType,
    OptimizedOutline,
    OptimizedOutlineItem,
    OptimizationSummary,
)
from src.domain.agent.outline import Outline, OutlineItem, OutlineItemType, OutlineStatus


class TestOutlineOptimizationDisplay:
    """大纲优化建议展示服务测试"""

    @pytest.fixture
    def sample_outline(self) -> Outline:
        """创建示例大纲"""
        outline = Outline(
            title="储能产业发展研究报告",
            description="关于储能产业的综合分析报告",
            industry_id=uuid.uuid4(),
            database_ids=[],
            status=OutlineStatus.DRAFT,
        )

        # 添加大纲项
        section1 = OutlineItem(
            parent_id=None,
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章 概述",
            order=1,
        )
        outline.add_item(section1)

        section2 = OutlineItem(
            parent_id=None,
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第二章 市场分析",
            order=2,
        )
        outline.add_item(section2)

        subsection2_1 = OutlineItem(
            parent_id=section2.id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="市场规模",
            order=1,
        )
        outline.add_item(subsection2_1)

        return outline

    @pytest.fixture
    def sample_optimized_outline(self, sample_outline: Outline) -> OptimizedOutline:
        """创建示例优化大纲"""
        optimized_outline = OptimizedOutline(
            original_outline_id=sample_outline.id,
            optimization_status="PENDING",
        )

        # 添加优化摘要
        summary = OptimizationSummary(
            optimized_outline_id=optimized_outline.id,
            total_changes=4,
            added_items=1,
            modified_items=1,
            deleted_items=0,
            moved_items=0,
            reordered_items=1,
            merged_items=0,
            split_items=1,
            quality_score=0.85,
            completeness_score=0.90,
            coherence_score=0.80,
            relevance_score=0.88,
            optimization_summary="优化了大纲结构，补充了缺失章节",
            key_improvements=[
                "增加了技术分析章节",
                "优化了市场分析的顺序",
                "细化了市场规模描述",
            ],
            potential_issues=[
                "第三章可能需要更多数据支持",
            ],
        )
        optimized_outline.set_summary(summary)

        # 添加新增章节
        new_section = OutlineItem(
            parent_id=None,
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第三章 技术分析",
            order=3,
            description="储能技术发展现状和趋势",
        )
        optimized_item_new = OptimizedOutlineItem(
            original_outline_id=sample_outline.id,
            original_item_id=None,
            original_item=None,
            optimized_item=new_section,
            change_type=OptimizationChangeType.ADD,
            change_description="新增技术分析章节",
            optimization_reason="技术分析是储能产业报告的重要组成部分",
            optimization_suggestions=[
                "建议包含储能技术分类",
                "建议包含技术发展趋势",
            ],
        )
        optimized_outline.add_optimized_item(optimized_item_new)

        # 添加修改项
        subsection2_1 = sample_outline.get_items_by_level(2)[0]
        modified_section = OutlineItem(
            parent_id=subsection2_1.parent_id,
            item_type=subsection2_1.item_type,
            level=subsection2_1.level,
            title=subsection2_1.title,
            description="全球及中国储能市场规模分析，包含历年数据和未来预测",
            order=subsection2_1.order,
        )
        optimized_item_modified = OptimizedOutlineItem(
            original_outline_id=sample_outline.id,
            original_item_id=subsection2_1.id,
            original_item=subsection2_1,
            optimized_item=modified_section,
            change_type=OptimizationChangeType.MODIFY,
            change_description="完善市场规模描述",
            optimization_reason="需要更详细的市场规模描述",
            optimization_suggestions=[
                "建议添加具体数据",
                "建议包含预测数据",
            ],
        )
        optimized_outline.add_optimized_item(optimized_item_modified)

        # 添加重排项
        section2 = sample_outline.get_items_by_level(1)[1]
        reordered_section = OutlineItem(
            parent_id=section2.parent_id,
            item_type=section2.item_type,
            level=section2.level,
            title=section2.title,
            order=1,  # 从2改为1
        )
        optimized_item_reordered = OptimizedOutlineItem(
            original_outline_id=sample_outline.id,
            original_item_id=section2.id,
            original_item=section2,
            optimized_item=reordered_section,
            change_type=OptimizationChangeType.REORDER,
            change_description="调整市场分析章节顺序",
            optimization_reason="市场分析应该在概述之后",
            optimization_suggestions=[
                "建议将市场分析放在概述之后",
            ],
        )
        optimized_outline.add_optimized_item(optimized_item_reordered)

        return optimized_outline

    @pytest.fixture
    def display_service(
        self, sample_optimized_outline: OptimizedOutline, sample_outline: Outline
    ) -> OutlineOptimizationDisplay:
        """创建展示服务实例"""
        return OutlineOptimizationDisplay(
            optimized_outline=sample_optimized_outline,
            original_outline=sample_outline,
        )

    def test_get_change_type_display_name(self, display_service: OutlineOptimizationDisplay):
        """测试获取变更类型显示名称"""
        assert display_service.get_change_type_display_name(OptimizationChangeType.ADD) == "新增章节"
        assert display_service.get_change_type_display_name(OptimizationChangeType.MODIFY) == "修改内容"
        assert display_service.get_change_type_display_name(OptimizationChangeType.DELETE) == "删除章节"
        assert display_service.get_change_type_display_name(OptimizationChangeType.MOVE) == "移动位置"
        assert display_service.get_change_type_display_name(OptimizationChangeType.REORDER) == "调整顺序"
        assert display_service.get_change_type_display_name(OptimizationChangeType.MERGE) == "合并章节"
        assert display_service.get_change_type_display_name(OptimizationChangeType.SPLIT) == "拆分章节"
        assert display_service.get_change_type_display_name(OptimizationChangeType.NONE) == "无变更"
        # 测试字符串输入
        assert display_service.get_change_type_display_name("ADD") == "新增章节"

    def test_get_change_type_emoji(self, display_service: OutlineOptimizationDisplay):
        """测试获取变更类型Emoji图标"""
        assert display_service.get_change_type_emoji(OptimizationChangeType.ADD) == "➕"
        assert display_service.get_change_type_emoji(OptimizationChangeType.MODIFY) == "✏️"
        assert display_service.get_change_type_emoji(OptimizationChangeType.DELETE) == "🗑️"
        assert display_service.get_change_type_emoji(OptimizationChangeType.MOVE) == "🔄"
        assert display_service.get_change_type_emoji(OptimizationChangeType.REORDER) == "📊"
        assert display_service.get_change_type_emoji(OptimizationChangeType.MERGE) == "🔗"
        assert display_service.get_change_type_emoji(OptimizationChangeType.SPLIT) == "✂️"
        assert display_service.get_change_type_emoji(OptimizationChangeType.NONE) == "✅"

    def test_get_change_type_color(self, display_service: OutlineOptimizationDisplay):
        """测试获取变更类型颜色"""
        assert display_service.get_change_type_color(OptimizationChangeType.ADD) == "green"
        assert display_service.get_change_type_color(OptimizationChangeType.MODIFY) == "blue"
        assert display_service.get_change_type_color(OptimizationChangeType.DELETE) == "red"
        assert display_service.get_change_type_color(OptimizationChangeType.MOVE) == "orange"
        assert display_service.get_change_type_color(OptimizationChangeType.REORDER) == "purple"
        assert display_service.get_change_type_color(OptimizationChangeType.MERGE) == "cyan"
        assert display_service.get_change_type_color(OptimizationChangeType.SPLIT) == "yellow"
        assert display_service.get_change_type_color(OptimizationChangeType.NONE) == "gray"

    def test_display_added_sections(self, display_service: OutlineOptimizationDisplay):
        """测试展示新增章节"""
        added_sections = display_service.display_added_sections()
        assert len(added_sections) == 1
        assert added_sections[0]["title"] == "第三章 技术分析"
        assert added_sections[0]["emoji"] == "➕"
        assert added_sections[0]["color"] == "green"
        assert added_sections[0]["display_name"] == "新增章节"
        assert added_sections[0]["optimization_reason"] == "技术分析是储能产业报告的重要组成部分"
        assert len(added_sections[0]["optimization_suggestions"]) == 2

    def test_display_modified_descriptions(self, display_service: OutlineOptimizationDisplay):
        """测试展示完善描述"""
        modified_items = display_service.display_modified_descriptions()
        assert len(modified_items) == 1
        assert modified_items[0]["title"] == "市场规模"
        assert modified_items[0]["emoji"] == "✏️"
        assert modified_items[0]["color"] == "blue"
        assert modified_items[0]["display_name"] == "修改内容"
        assert modified_items[0]["description_after"] is not None
        assert len(modified_items[0]["description_after"]) > 0
        assert len(modified_items[0]["optimization_suggestions"]) == 2

    def test_display_reordered_sections(self, display_service: OutlineOptimizationDisplay):
        """测试展示调整顺序"""
        reordered_sections = display_service.display_reordered_sections()
        assert len(reordered_sections) == 1
        assert reordered_sections[0]["title"] == "第二章 市场分析"
        assert reordered_sections[0]["emoji"] == "📊"
        assert reordered_sections[0]["color"] == "purple"
        assert reordered_sections[0]["display_name"] == "调整顺序"
        assert reordered_sections[0]["order_before"] == 2
        assert reordered_sections[0]["order_after"] == 1

    def test_display_moved_sections(self, display_service: OutlineOptimizationDisplay):
        """测试展示移动位置"""
        moved_sections = display_service.display_moved_sections()
        # 示例中没有移动项
        assert len(moved_sections) == 0

    def test_display_deleted_sections(self, display_service: OutlineOptimizationDisplay):
        """测试展示删除章节"""
        deleted_sections = display_service.display_deleted_sections()
        # 示例中没有删除项
        assert len(deleted_sections) == 0

    def test_display_all_changes(self, display_service: OutlineOptimizationDisplay):
        """测试展示所有变更"""
        all_changes = display_service.display_all_changes()
        assert "added_sections" in all_changes
        assert "modified_descriptions" in all_changes
        assert "reordered_sections" in all_changes
        assert "moved_sections" in all_changes
        assert "deleted_sections" in all_changes
        assert "change_statistics" in all_changes
        assert len(all_changes["added_sections"]) == 1
        assert len(all_changes["modified_descriptions"]) == 1
        assert len(all_changes["reordered_sections"]) == 1

    def test_display_summary(self, display_service: OutlineOptimizationDisplay):
        """测试展示优化摘要"""
        summary = display_service.display_summary()
        assert summary["total_changes"] == 4
        assert summary["added_items"] == 1
        assert summary["modified_items"] == 1
        assert summary["reordered_items"] == 1
        assert summary["quality_score"] == 0.85
        assert summary["completeness_score"] == 0.90
        assert summary["coherence_score"] == 0.80
        assert summary["relevance_score"] == 0.88
        assert summary["average_score"] == 0.86
        assert len(summary["key_improvements"]) == 3
        assert len(summary["potential_issues"]) == 1

    def test_to_text(self, display_service: OutlineOptimizationDisplay):
        """测试转换为文本格式"""
        text = display_service.to_text()
        assert isinstance(text, str)
        assert len(text) > 0
        assert "优化摘要" in text
        assert "新增章节" in text
        assert "完善描述" in text
        assert "调整顺序" in text
        assert "总变更数" in text
        assert "质量评分" in text
        assert "关键改进点" in text

    def test_to_markdown(self, display_service: OutlineOptimizationDisplay):
        """测试转换为Markdown格式"""
        markdown = display_service.to_markdown()
        assert isinstance(markdown, str)
        assert len(markdown) > 0
        assert "# 大纲优化摘要" in markdown
        assert "# 新增章节" in markdown
        assert "# 完善描述" in markdown
        assert "# 调整顺序" in markdown
        assert "## 变更统计" in markdown
        assert "## 质量评分" in markdown
        assert "## 关键改进点" in markdown

    def test_to_json(self, display_service: OutlineOptimizationDisplay):
        """测试转换为JSON格式"""
        import json

        json_str = display_service.to_json()
        assert isinstance(json_str, str)
        assert len(json_str) > 0

        # 验证可以解析
        data = json.loads(json_str)
        assert "summary" in data
        assert "changes" in data
        assert data["summary"]["total_changes"] == 4

    def test_to_dict(self, display_service: OutlineOptimizationDisplay):
        """测试转换为字典格式"""
        data = display_service.to_dict()
        assert isinstance(data, dict)
        assert "summary" in data
        assert "changes" in data
        assert "optimized_outline" in data
        assert "original_outline" in data
        assert data["summary"]["total_changes"] == 4

    def test_empty_optimized_outline(self, sample_outline: Outline):
        """测试空优化大纲"""
        optimized_outline = OptimizedOutline(
            original_outline_id=sample_outline.id,
            optimization_status="PENDING",
        )
        display_service = OutlineOptimizationDisplay(
            optimized_outline=optimized_outline,
            original_outline=sample_outline,
        )

        # 所有展示方法应该返回空列表或空字典
        assert len(display_service.display_added_sections()) == 0
        assert len(display_service.display_modified_descriptions()) == 0
        assert len(display_service.display_reordered_sections()) == 0
        assert len(display_service.display_moved_sections()) == 0
        assert len(display_service.display_deleted_sections()) == 0

        # 摘要应该为空字典
        summary = display_service.display_summary()
        assert summary == {}

        # 文本和Markdown应该仍然可以生成
        text = display_service.to_text()
        assert isinstance(text, str)

        markdown = display_service.to_markdown()
        assert isinstance(markdown, str)

    def test_create_optimization_display(self, sample_optimized_outline: OptimizedOutline, sample_outline: Outline):
        """测试创建优化建议展示对象的便捷函数"""
        display_service = create_optimization_display(
            optimized_outline=sample_optimized_outline,
            original_outline=sample_outline,
        )
        assert isinstance(display_service, OutlineOptimizationDisplay)
        assert display_service.optimized_outline == sample_optimized_outline
        assert display_service.original_outline == sample_outline

    def test_create_optimization_display_without_original(self, sample_optimized_outline: OptimizedOutline):
        """测试不提供原始大纲时创建展示对象"""
        display_service = create_optimization_display(
            optimized_outline=sample_optimized_outline,
        )
        assert isinstance(display_service, OutlineOptimizationDisplay)
        assert display_service.optimized_outline == sample_optimized_outline
        assert display_service.original_outline is None

    def test_text_format_structure(self, display_service: OutlineOptimizationDisplay):
        """测试文本格式结构"""
        text = display_service.to_text()
        lines = text.split("\n")

        # 检查分隔线
        assert any("=" * 60 in line for line in lines)

        # 检查标题
        assert any("优化摘要" in line for line in lines)
        assert any("新增章节" in line for line in lines)
        assert any("完善描述" in line for line in lines)
        assert any("调整顺序" in line for line in lines)

    def test_markdown_format_structure(self, display_service: OutlineOptimizationDisplay):
        """测试Markdown格式结构"""
        markdown = display_service.to_markdown()
        lines = markdown.split("\n")

        # 检查一级标题
        assert any(line.startswith("# ") for line in lines)

        # 检查表格
        assert any("|" in line for line in lines)

        # 检查列表
        assert any(line.startswith("- ") for line in lines)

    def test_json_format_structure(self, display_service: OutlineOptimizationDisplay):
        """测试JSON格式结构"""
        import json

        json_str = display_service.to_json()
        data = json.loads(json_str)

        # 检查顶层结构
        assert "summary" in data
        assert "changes" in data

        # 检查changes结构
        changes = data["changes"]
        assert "added_sections" in changes
        assert "modified_descriptions" in changes
        assert "reordered_sections" in changes
        assert "moved_sections" in changes
        assert "deleted_sections" in changes
        assert "change_statistics" in changes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
