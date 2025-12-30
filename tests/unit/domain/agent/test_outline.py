"""
Outline领域模型单元测试

该模块测试Outline领域模型的各种功能，包括创建、验证、更新、版本管理等操作。
"""

import pytest
import uuid
from datetime import datetime, UTC

from src.domain.agent.outline import (
    Outline,
    OutlineItem,
    OutlineItemType,
    OutlineStatus,
    OutlineVersion,
    create_outline_from_structure,
    create_outline_from_text,
)


class TestOutlineItem:
    """OutlineItem领域模型测试类"""

    def test_outline_item_creation_success(self) -> None:
        """测试成功创建大纲项对象"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            description="这是第一章的描述",
            order=1,
        )

        assert item.title == "第一章"
        assert item.description == "这是第一章的描述"
        assert item.item_type == OutlineItemType.SECTION
        assert item.level == 1
        assert item.order == 1
        assert item.parent_id is None
        assert isinstance(item.id, uuid.UUID)

    def test_outline_item_creation_with_parent(self) -> None:
        """测试创建带父级的大纲项"""
        parent_id = uuid.uuid4()
        item = OutlineItem(
            parent_id=parent_id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )

        assert item.parent_id == parent_id
        assert item.item_type == OutlineItemType.SUBSECTION
        assert item.level == 2

    def test_outline_item_title_validation_empty(self) -> None:
        """测试标题为空时的验证"""
        with pytest.raises(ValueError, match="大纲项标题不能为空"):
            OutlineItem(
                item_type=OutlineItemType.SECTION,
                level=1,
                title="",
                order=1,
            )

        with pytest.raises(ValueError, match="大纲项标题不能为空"):
            OutlineItem(
                item_type=OutlineItemType.SECTION,
                level=1,
                title="   ",
                order=1,
            )

    def test_outline_item_title_validation_whitespace(self) -> None:
        """测试标题包含空白字符的处理"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="  第一章  ",
            order=1,
        )
        assert item.title == "第一章"

    def test_outline_item_description_validation(self) -> None:
        """测试描述验证"""
        # 有效描述
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            description="  这是描述  ",
            order=1,
        )
        assert item.description == "这是描述"

        # 空描述
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            description="   ",
            order=1,
        )
        assert item.description is None

        # None描述
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            description=None,
            order=1,
        )
        assert item.description is None

    def test_outline_item_level_validation(self) -> None:
        """测试层级验证"""
        # 有效层级
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=6,
            title="第六级标题",
            order=1,
        )
        assert item.level == 6

        # 无效层级（小于1）
        with pytest.raises(ValueError, match="大纲项层级必须大于等于1"):
            OutlineItem(
                item_type=OutlineItemType.SECTION,
                level=0,
                title="标题",
                order=1,
            )

        # 无效层级（大于6）
        with pytest.raises(ValueError, match="大纲项层级不能超过6"):
            OutlineItem(
                item_type=OutlineItemType.SECTION,
                level=7,
                title="标题",
                order=1,
            )

    def test_outline_item_order_validation(self) -> None:
        """测试排序顺序验证"""
        # 有效排序
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=5,
        )
        assert item.order == 5

        # 无效排序
        with pytest.raises(ValueError, match="排序顺序不能为负数"):
            OutlineItem(
                item_type=OutlineItemType.SECTION,
                level=1,
                title="第一章",
                order=-1,
            )

    def test_is_root(self) -> None:
        """测试是否为根节点"""
        root_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        assert root_item.is_root() is True

        parent_id = uuid.uuid4()
        child_item = OutlineItem(
            parent_id=parent_id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        assert child_item.is_root() is False

    def test_is_section(self) -> None:
        """测试是否为章节"""
        section_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        assert section_item.is_section() is True

        subsection_item = OutlineItem(
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        assert subsection_item.is_section() is False

    def test_is_subsection(self) -> None:
        """测试是否为子章节"""
        subsection_item = OutlineItem(
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        assert subsection_item.is_subsection() is True

        section_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        assert section_item.is_subsection() is False

    def test_is_paragraph(self) -> None:
        """测试是否为段落"""
        paragraph_item = OutlineItem(
            item_type=OutlineItemType.PARAGRAPH,
            level=3,
            title="段落内容",
            order=1,
        )
        assert paragraph_item.is_paragraph() is True

        section_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        assert section_item.is_paragraph() is False

    def test_is_content(self) -> None:
        """测试是否为内容"""
        content_item = OutlineItem(
            item_type=OutlineItemType.CONTENT,
            level=1,
            title="具体内容描述",
            order=1,
        )
        assert content_item.is_content() is True

        section_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        assert section_item.is_content() is False

    def test_has_optimization(self) -> None:
        """测试是否有优化记录"""
        # 无优化记录
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        assert item.has_optimization() is False

        # 有优化记录
        item.is_optimized = True
        assert item.has_optimization() is True

        # 有原始标题
        item.is_optimized = False
        item.original_title = "原始标题"
        assert item.has_optimization() is True

        # 有优化建议
        item.original_title = None
        item.optimization_suggestions = ["建议1", "建议2"]
        assert item.has_optimization() is True

    def test_accept_optimization(self) -> None:
        """测试接受优化建议"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="优化后的标题",
            order=1,
        )
        item.original_title = "原始标题"
        item.optimization_suggestions = ["建议1", "建议2"]
        item.is_optimized = True

        assert item.has_optimization() is True

        item.accept_optimization()

        assert item.original_title is None
        assert item.optimization_suggestions == []
        assert item.is_optimized is False
        assert item.has_optimization() is False

    def test_reject_optimization(self) -> None:
        """测试拒绝优化建议"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="优化后的标题",
            order=1,
        )
        item.original_title = "原始标题"
        item.original_description = "原始描述"
        item.optimization_suggestions = ["建议1", "建议2"]
        item.is_optimized = True

        item.reject_optimization()

        assert item.title == "原始标题"
        assert item.description == "原始描述"
        assert item.original_title is None
        assert item.original_description is None
        assert item.optimization_suggestions == []
        assert item.is_optimized is False

    def test_add_optimization_suggestion(self) -> None:
        """测试添加优化建议"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )

        item.add_optimization_suggestion("建议1")
        assert "建议1" in item.optimization_suggestions

        item.add_optimization_suggestion("建议2")
        assert "建议2" in item.optimization_suggestions
        assert len(item.optimization_suggestions) == 2

        # 添加重复建议
        item.add_optimization_suggestion("建议1")
        assert len(item.optimization_suggestions) == 2

    def test_update_title(self) -> None:
        """测试更新标题"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="原始标题",
            order=1,
        )

        item.update_title("新标题")

        assert item.title == "新标题"
        assert item.original_title == "原始标题"

    def test_update_description(self) -> None:
        """测试更新描述"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            description="原始描述",
            order=1,
        )

        item.update_description("新描述")

        assert item.description == "新描述"
        assert item.original_description == "原始描述"

    def test_set_order(self) -> None:
        """测试设置排序顺序"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )

        item.set_order(5)

        assert item.order == 5

    def test_set_order_invalid(self) -> None:
        """测试设置无效排序顺序"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )

        with pytest.raises(ValueError, match="排序顺序不能为负数"):
            item.set_order(-1)

    def test_metadata_operations(self) -> None:
        """测试元数据操作"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )

        # 测试添加元数据
        item.add_metadata("key1", "value1")
        assert item.get_metadata("key1") == "value1"

        # 测试获取不存在的元数据
        assert item.get_metadata("nonexistent") is None
        assert item.get_metadata("nonexistent", "default") == "default"

        # 测试更新元数据
        item.add_metadata("key1", "value2")
        assert item.get_metadata("key1") == "value2"

        # 测试移除元数据
        result = item.remove_metadata("key1")
        assert result is True
        assert item.get_metadata("key1") is None

        # 测试移除不存在的元数据
        result = item.remove_metadata("nonexistent")
        assert result is False

    def test_get_display_title(self) -> None:
        """测试获取显示标题"""
        # 一级章节
        section_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        assert section_item.get_display_title() == "1. 第一章"

        # 二级子章节
        subsection_item = OutlineItem(
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        assert subsection_item.get_display_title() == "  1. 第一节"

        # 三级段落
        paragraph_item = OutlineItem(
            item_type=OutlineItemType.PARAGRAPH,
            level=3,
            title="段落内容",
            order=1,
        )
        assert paragraph_item.get_display_title() == "    段落内容"

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            description="描述",
            order=1,
            metadata={"key": "value"},
        )

        result = item.to_dict()

        assert isinstance(result, dict)
        assert result["title"] == "第一章"
        assert result["description"] == "描述"
        assert result["item_type"] == "SECTION"
        assert result["level"] == 1
        assert result["order"] == 1
        assert result["metadata"] == {"key": "value"}
        assert isinstance(result["id"], str)


class TestOutlineVersion:
    """OutlineVersion领域模型测试类"""

    def test_outline_version_creation_success(self) -> None:
        """测试成功创建大纲版本对象"""
        outline_id = uuid.uuid4()
        version = OutlineVersion(
            outline_id=outline_id,
            version_number=1,
            status=OutlineStatus.DRAFT,
            change_reason="初始版本",
            items_snapshot={"items": []},
        )

        assert version.outline_id == outline_id
        assert version.version_number == 1
        assert version.status == OutlineStatus.DRAFT
        assert version.change_reason == "初始版本"
        assert version.items_snapshot == {"items": []}
        assert isinstance(version.id, uuid.UUID)
        assert isinstance(version.created_at, datetime)

    def test_outline_version_number_validation(self) -> None:
        """测试版本号验证"""
        outline_id = uuid.uuid4()

        # 有效版本号
        version = OutlineVersion(
            outline_id=outline_id,
            version_number=1,
            status=OutlineStatus.DRAFT,
        )
        assert version.version_number == 1

        # 无效版本号
        with pytest.raises(ValueError, match="版本号必须大于等于1"):
            OutlineVersion(
                outline_id=outline_id,
                version_number=0,
                status=OutlineStatus.DRAFT,
            )

    def test_outline_version_change_reason_validation(self) -> None:
        """测试变更原因验证"""
        outline_id = uuid.uuid4()

        # 有效变更原因
        version = OutlineVersion(
            outline_id=outline_id,
            version_number=1,
            status=OutlineStatus.DRAFT,
            change_reason="  变更原因  ",
        )
        assert version.change_reason == "变更原因"

        # 空变更原因
        version = OutlineVersion(
            outline_id=outline_id,
            version_number=1,
            status=OutlineStatus.DRAFT,
            change_reason="   ",
        )
        assert version.change_reason is None

        # None变更原因
        version = OutlineVersion(
            outline_id=outline_id,
            version_number=1,
            status=OutlineStatus.DRAFT,
            change_reason=None,
        )
        assert version.change_reason is None

    def test_is_draft_status(self) -> None:
        """测试是否为草稿状态"""
        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.DRAFT,
        )
        assert version.is_draft_status() is True

        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.OPTIMIZED,
        )
        assert version.is_draft_status() is False

    def test_is_optimized_status(self) -> None:
        """测试是否为已优化状态"""
        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.OPTIMIZED,
        )
        assert version.is_optimized_status() is True

        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.DRAFT,
        )
        assert version.is_optimized_status() is False

    def test_is_accepted_status(self) -> None:
        """测试是否为已接受状态"""
        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.ACCEPTED,
        )
        assert version.is_accepted_status() is True

        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.DRAFT,
        )
        assert version.is_accepted_status() is False

    def test_is_finalized_status(self) -> None:
        """测试是否为已定稿状态"""
        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.FINALIZED,
        )
        assert version.is_finalized_status() is True

        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.DRAFT,
        )
        assert version.is_finalized_status() is False

    def test_metadata_operations(self) -> None:
        """测试元数据操作"""
        version = OutlineVersion(
            outline_id=uuid.uuid4(),
            version_number=1,
            status=OutlineStatus.DRAFT,
        )

        # 测试添加元数据
        version.add_metadata("key1", "value1")
        assert version.get_metadata("key1") == "value1"

        # 测试获取不存在的元数据
        assert version.get_metadata("nonexistent") is None
        assert version.get_metadata("nonexistent", "default") == "default"

        # 测试更新元数据
        version.add_metadata("key1", "value2")
        assert version.get_metadata("key1") == "value2"

        # 测试移除元数据
        result = version.remove_metadata("key1")
        assert result is True
        assert version.get_metadata("key1") is None

        # 测试移除不存在的元数据
        result = version.remove_metadata("nonexistent")
        assert result is False

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        outline_id = uuid.uuid4()
        version = OutlineVersion(
            outline_id=outline_id,
            version_number=1,
            status=OutlineStatus.DRAFT,
            change_reason="测试",
            items_snapshot={"items": []},
            metadata={"key": "value"},
        )

        result = version.to_dict()

        assert isinstance(result, dict)
        assert result["outline_id"] == str(outline_id)
        assert result["version_number"] == 1
        assert result["status"] == "DRAFT"
        assert result["change_reason"] == "测试"
        assert result["items_snapshot"] == {"items": []}
        assert result["metadata"] == {"key": "value"}
        assert isinstance(result["id"], str)
        assert isinstance(result["created_at"], str)


class TestOutline:
    """Outline领域模型测试类"""

    def test_outline_creation_success(self) -> None:
        """测试成功创建大纲对象"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="储能行业白皮书大纲",
            description="储能行业白皮书的大纲",
            industry_id=industry_id,
            database_ids=[uuid.uuid4()],
        )

        assert outline.title == "储能行业白皮书大纲"
        assert outline.description == "储能行业白皮书的大纲"
        assert outline.industry_id == industry_id
        assert outline.status == OutlineStatus.DRAFT
        assert len(outline.items) == 0
        assert outline.current_version == 1
        assert len(outline.versions) == 0
        assert isinstance(outline.id, uuid.UUID)
        assert isinstance(outline.created_at, datetime)
        assert isinstance(outline.updated_at, datetime)

    def test_outline_title_validation_empty(self) -> None:
        """测试标题为空时的验证"""
        industry_id = uuid.uuid4()

        with pytest.raises(ValueError, match="大纲标题不能为空"):
            Outline(
                title="",
                industry_id=industry_id,
            )

        with pytest.raises(ValueError, match="大纲标题不能为空"):
            Outline(
                title="   ",
                industry_id=industry_id,
            )

    def test_outline_title_validation_whitespace(self) -> None:
        """测试标题包含空白字符的处理"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="  储能行业白皮书大纲  ",
            industry_id=industry_id,
        )
        assert outline.title == "储能行业白皮书大纲"

    def test_outline_description_validation(self) -> None:
        """测试描述验证"""
        industry_id = uuid.uuid4()

        # 有效描述
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
            description="  这是描述  ",
        )
        assert outline.description == "这是描述"

        # 空描述
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
            description="   ",
        )
        assert outline.description is None

        # None描述
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
            description=None,
        )
        assert outline.description is None

    def test_outline_current_version_validation(self) -> None:
        """测试当前版本号验证"""
        industry_id = uuid.uuid4()

        # 有效版本号
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
            current_version=5,
        )
        assert outline.current_version == 5

        # 无效版本号
        with pytest.raises(ValueError, match="当前版本号必须大于等于1"):
            Outline(
                title="大纲",
                industry_id=industry_id,
                current_version=0,
            )

    def test_add_item_success(self) -> None:
        """测试成功添加大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )

        outline.add_item(item)

        assert len(outline.items) == 1
        assert outline.items[0] == item

    def test_add_item_with_parent(self) -> None:
        """测试添加带父级的大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        parent_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(parent_item)

        child_item = OutlineItem(
            parent_id=parent_item.id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        outline.add_item(child_item)

        assert len(outline.items) == 2
        assert child_item.parent_id == parent_item.id

    def test_add_item_parent_not_exists(self) -> None:
        """测试添加父级不存在的大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        parent_id = uuid.uuid4()
        child_item = OutlineItem(
            parent_id=parent_id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )

        with pytest.raises(ValueError, match="父级大纲项.*不存在"):
            outline.add_item(child_item)

    def test_add_item_duplicate_id(self) -> None:
        """测试添加重复ID的大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        item_id = uuid.uuid4()
        item1 = OutlineItem(
            id=item_id,
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(item1)

        item2 = OutlineItem(
            id=item_id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )

        with pytest.raises(ValueError, match="大纲项.*已存在"):
            outline.add_item(item2)

    def test_remove_item_success(self) -> None:
        """测试成功移除大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(item)

        result = outline.remove_item(item.id)

        assert result is True
        assert len(outline.items) == 0

    def test_remove_item_not_found(self) -> None:
        """测试移除不存在的大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        result = outline.remove_item(uuid.uuid4())

        assert result is False

    def test_remove_item_with_children(self) -> None:
        """测试移除有子项的大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        parent_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(parent_item)

        child_item = OutlineItem(
            parent_id=parent_item.id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        outline.add_item(child_item)

        with pytest.raises(ValueError, match="大纲项.*有子项"):
            outline.remove_item(parent_item.id)

    def test_update_item_success(self) -> None:
        """测试成功更新大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(item)

        updated_item = OutlineItem(
            id=item.id,
            item_type=OutlineItemType.SECTION,
            level=1,
            title="更新后的标题",
            order=1,
        )

        result = outline.update_item(updated_item)

        assert result is True
        assert outline.items[0].title == "更新后的标题"

    def test_update_item_not_found(self) -> None:
        """测试更新不存在的大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )

        result = outline.update_item(item)

        assert result is False

    def test_get_item_success(self) -> None:
        """测试成功获取大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(item)

        result = outline.get_item(item.id)

        assert result is not None
        assert result == item

    def test_get_item_not_found(self) -> None:
        """测试获取不存在的大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        result = outline.get_item(uuid.uuid4())

        assert result is None

    def test_get_root_items(self) -> None:
        """测试获取根级大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 添加根级项
        root_item1 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        root_item2 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第二章",
            order=2,
        )
        outline.add_item(root_item1)
        outline.add_item(root_item2)

        # 添加子项
        child_item = OutlineItem(
            parent_id=root_item1.id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        outline.add_item(child_item)

        root_items = outline.get_root_items()

        assert len(root_items) == 2
        assert root_item1 in root_items
        assert root_item2 in root_items
        assert child_item not in root_items

    def test_get_children(self) -> None:
        """测试获取子项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        parent_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(parent_item)

        child_item1 = OutlineItem(
            parent_id=parent_item.id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        child_item2 = OutlineItem(
            parent_id=parent_item.id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第二节",
            order=2,
        )
        outline.add_item(child_item1)
        outline.add_item(child_item2)

        children = outline.get_children(parent_item.id)

        assert len(children) == 2
        assert child_item1 in children
        assert child_item2 in children

    def test_get_items_by_level(self) -> None:
        """测试按层级获取大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 添加不同层级的大纲项
        level1_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        level2_item = OutlineItem(
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        level3_item = OutlineItem(
            item_type=OutlineItemType.PARAGRAPH,
            level=3,
            title="段落",
            order=1,
        )
        outline.add_item(level1_item)
        outline.add_item(level2_item)
        outline.add_item(level3_item)

        level1_items = outline.get_items_by_level(1)
        level2_items = outline.get_items_by_level(2)
        level3_items = outline.get_items_by_level(3)

        assert len(level1_items) == 1
        assert level1_item in level1_items

        assert len(level2_items) == 1
        assert level2_item in level2_items

        assert len(level3_items) == 1
        assert level3_item in level3_items

    def test_get_items_by_type(self) -> None:
        """测试按类型获取大纲项"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 添加不同类型的大纲项
        section_item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        subsection_item = OutlineItem(
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        paragraph_item = OutlineItem(
            item_type=OutlineItemType.PARAGRAPH,
            level=3,
            title="段落",
            order=1,
        )
        outline.add_item(section_item)
        outline.add_item(subsection_item)
        outline.add_item(paragraph_item)

        section_items = outline.get_items_by_type(OutlineItemType.SECTION)
        subsection_items = outline.get_items_by_type(OutlineItemType.SUBSECTION)
        paragraph_items = outline.get_items_by_type(OutlineItemType.PARAGRAPH)

        assert len(section_items) == 1
        assert section_item in section_items

        assert len(subsection_items) == 1
        assert subsection_item in subsection_items

        assert len(paragraph_items) == 1
        assert paragraph_item in paragraph_items

    def test_build_tree(self) -> None:
        """测试构建大纲树结构"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 添加层级结构
        root_item1 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        root_item2 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第二章",
            order=2,
        )
        outline.add_item(root_item1)
        outline.add_item(root_item2)

        child_item1 = OutlineItem(
            parent_id=root_item1.id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第一节",
            order=1,
        )
        child_item2 = OutlineItem(
            parent_id=root_item1.id,
            item_type=OutlineItemType.SUBSECTION,
            level=2,
            title="第二节",
            order=2,
        )
        outline.add_item(child_item1)
        outline.add_item(child_item2)

        tree = outline.build_tree()

        assert len(tree) == 2
        assert tree[0]["title"] == "第一章"
        assert tree[1]["title"] == "第二章"
        assert len(tree[0]["children"]) == 2
        assert tree[0]["children"][0]["title"] == "第一节"
        assert tree[0]["children"][1]["title"] == "第二节"
        assert len(tree[1]["children"]) == 0

    def test_update_status(self) -> None:
        """测试更新大纲状态"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
            status=OutlineStatus.DRAFT,
        )

        original_updated_at = outline.updated_at
        import time
        time.sleep(0.001)

        outline.update_status(OutlineStatus.OPTIMIZED, "AI优化完成")

        assert outline.status == OutlineStatus.OPTIMIZED
        assert outline.updated_at > original_updated_at

    def test_create_version(self) -> None:
        """测试创建新版本"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 添加一些大纲项
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(item)

        # 创建版本
        version = outline.create_version(
            OutlineStatus.DRAFT, "初始版本"
        )

        assert version.outline_id == outline.id
        assert version.version_number == 2
        assert version.status == OutlineStatus.DRAFT
        assert version.change_reason == "初始版本"
        assert outline.current_version == 2
        assert len(outline.versions) == 1

    def test_get_version(self) -> None:
        """测试获取指定版本"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 创建多个版本
        version1 = outline.create_version(OutlineStatus.DRAFT, "版本1")
        version2 = outline.create_version(OutlineStatus.OPTIMIZED, "版本2")

        # 获取版本（version1是版本2，version2是版本3）
        retrieved_version = outline.get_version(2)

        assert retrieved_version is not None
        assert retrieved_version.id == version1.id
        assert retrieved_version.version_number == 2

    def test_get_version_not_found(self) -> None:
        """测试获取不存在的版本"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        version = outline.get_version(999)

        assert version is None

    def test_get_latest_version(self) -> None:
        """测试获取最新版本"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 没有版本时返回None
        assert outline.get_latest_version() is None

        # 创建版本
        version1 = outline.create_version(OutlineStatus.DRAFT, "版本1")
        version2 = outline.create_version(OutlineStatus.OPTIMIZED, "版本2")

        latest_version = outline.get_latest_version()

        assert latest_version is not None
        assert latest_version.id == version2.id
        assert latest_version.version_number == 3

    def test_restore_version(self) -> None:
        """测试恢复到指定版本"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="原始标题",
            industry_id=industry_id,
        )

        # 添加大纲项
        item1 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(item1)

        # 创建版本
        version = outline.create_version(OutlineStatus.DRAFT, "版本1")

        # 修改大纲
        outline.title = "新标题"
        item2 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第二章",
            order=2,
        )
        outline.add_item(item2)

        # 恢复版本
        result = outline.restore_version(2)

        assert result is True
        assert outline.title == "原始标题"
        assert len(outline.items) == 1
        assert outline.items[0].title == "第一章"
        assert outline.status == OutlineStatus.DRAFT

    def test_restore_version_not_found(self) -> None:
        """测试恢复不存在的版本"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        result = outline.restore_version(999)

        assert result is False

    def test_accept_all_optimizations(self) -> None:
        """测试接受所有优化建议"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 添加有优化建议的大纲项
        item1 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="优化后标题1",
            order=1,
        )
        item1.original_title = "原始标题1"
        item1.optimization_suggestions = ["建议1"]
        outline.add_item(item1)

        item2 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="优化后标题2",
            order=2,
        )
        item2.original_title = "原始标题2"
        item2.optimization_suggestions = ["建议2"]
        outline.add_item(item2)

        # 接受所有优化
        outline.accept_all_optimizations()

        assert item1.original_title is None
        assert item1.optimization_suggestions == []
        assert item2.original_title is None
        assert item2.optimization_suggestions == []

    def test_reject_all_optimizations(self) -> None:
        """测试拒绝所有优化建议"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 添加有优化建议的大纲项
        item1 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="优化后标题1",
            order=1,
        )
        item1.original_title = "原始标题1"
        outline.add_item(item1)

        item2 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="优化后标题2",
            order=2,
        )
        item2.original_title = "原始标题2"
        outline.add_item(item2)

        # 拒绝所有优化
        outline.reject_all_optimizations()

        assert item1.title == "原始标题1"
        assert item1.original_title is None
        assert item2.title == "原始标题2"
        assert item2.original_title is None

    def test_has_optimizations(self) -> None:
        """测试是否有优化建议"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 没有优化建议
        assert outline.has_optimizations() is False

        # 添加有优化建议的大纲项
        item = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="优化后标题",
            order=1,
        )
        item.original_title = "原始标题"
        outline.add_item(item)

        # 有优化建议
        assert outline.has_optimizations() is True

    def test_get_optimization_summary(self) -> None:
        """测试获取优化摘要"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 添加大纲项
        item1 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第一章",
            order=1,
        )
        outline.add_item(item1)

        item2 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第二章",
            order=2,
        )
        item2.optimization_suggestions = ["建议1", "建议2"]
        outline.add_item(item2)

        item3 = OutlineItem(
            item_type=OutlineItemType.SECTION,
            level=1,
            title="第三章",
            order=3,
        )
        item3.optimization_suggestions = ["建议3"]
        outline.add_item(item3)

        # 获取优化摘要
        summary = outline.get_optimization_summary()

        assert summary["total_items"] == 3
        assert summary["optimized_items"] == 2
        assert summary["total_suggestions"] == 3
        assert len(summary["optimized_items_details"]) == 2

    def test_add_database(self) -> None:
        """测试添加数据库"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        database_id = uuid.uuid4()
        outline.add_database(database_id)

        assert database_id in outline.database_ids
        assert len(outline.database_ids) == 1

        # 添加重复数据库ID
        outline.add_database(database_id)
        assert len(outline.database_ids) == 1

    def test_remove_database(self) -> None:
        """测试移除数据库"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        database_id = uuid.uuid4()
        outline.add_database(database_id)

        result = outline.remove_database(database_id)

        assert result is True
        assert database_id not in outline.database_ids

        # 移除不存在的数据库ID
        result = outline.remove_database(uuid.uuid4())
        assert result is False

    def test_metadata_operations(self) -> None:
        """测试元数据操作"""
        industry_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            industry_id=industry_id,
        )

        # 测试添加元数据
        outline.add_metadata("key1", "value1")
        assert outline.get_metadata("key1") == "value1"

        # 测试获取不存在的元数据
        assert outline.get_metadata("nonexistent") is None
        assert outline.get_metadata("nonexistent", "default") == "default"

        # 测试更新元数据
        outline.add_metadata("key1", "value2")
        assert outline.get_metadata("key1") == "value2"

        # 测试移除元数据
        result = outline.remove_metadata("key1")
        assert result is True
        assert outline.get_metadata("key1") is None

        # 测试移除不存在的元数据
        result = outline.remove_metadata("nonexistent")
        assert result is False

    def test_is_draft(self) -> None:
        """测试是否为草稿状态"""
        outline = Outline(
            title="大纲",
            industry_id=uuid.uuid4(),
            status=OutlineStatus.DRAFT,
        )
        assert outline.is_draft() is True

        outline.status = OutlineStatus.OPTIMIZED
        assert outline.is_draft() is False

    def test_is_optimized(self) -> None:
        """测试是否为已优化状态"""
        outline = Outline(
            title="大纲",
            industry_id=uuid.uuid4(),
            status=OutlineStatus.OPTIMIZED,
        )
        assert outline.is_optimized() is True

        outline.status = OutlineStatus.DRAFT
        assert outline.is_optimized() is False

    def test_is_accepted(self) -> None:
        """测试是否为已接受状态"""
        outline = Outline(
            title="大纲",
            industry_id=uuid.uuid4(),
            status=OutlineStatus.ACCEPTED,
        )
        assert outline.is_accepted() is True

        outline.status = OutlineStatus.DRAFT
        assert outline.is_accepted() is False

    def test_is_finalized(self) -> None:
        """测试是否为已定稿状态"""
        outline = Outline(
            title="大纲",
            industry_id=uuid.uuid4(),
            status=OutlineStatus.FINALIZED,
        )
        assert outline.is_finalized() is True

        outline.status = OutlineStatus.DRAFT
        assert outline.is_finalized() is False

    def test_get_display_name(self) -> None:
        """测试获取显示名称"""
        outline = Outline(
            title="储能行业白皮书大纲",
            industry_id=uuid.uuid4(),
            current_version=3,
        )

        assert outline.get_display_name() == "储能行业白皮书大纲 (v3)"

    def test_to_dict(self) -> None:
        """测试转换为字典"""
        industry_id = uuid.uuid4()
        database_id = uuid.uuid4()
        outline = Outline(
            title="大纲",
            description="描述",
            industry_id=industry_id,
            database_ids=[database_id],
            status=OutlineStatus.DRAFT,
            metadata={"key": "value"},
        )

        result = outline.to_dict()

        assert isinstance(result, dict)
        assert result["title"] == "大纲"
        assert result["description"] == "描述"
        assert result["industry_id"] == str(industry_id)
        assert result["database_ids"] == [str(database_id)]
        assert result["status"] == "DRAFT"
        assert result["current_version"] == 1
        assert result["metadata"] == {"key": "value"}
        assert isinstance(result["id"], str)
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)


class TestOutlineFactoryMethods:
    """Outline工厂方法测试类"""

    def test_create_from_text_markdown(self) -> None:
        """测试从Markdown文本创建大纲"""
        industry_id = uuid.uuid4()
        text = """# 第一章 储能行业概述

## 第一节 储能技术分类

### 1.1 电化学储能

### 1.2 物理储能

# 第二章 市场分析
"""

        outline = Outline.create_from_text(
            title="储能行业白皮书大纲",
            text=text,
            industry_id=industry_id,
        )

        assert outline.title == "储能行业白皮书大纲"
        # 5个大纲项：2个一级标题 + 1个二级标题 + 2个三级标题
        assert len(outline.items) == 5
        root_items = outline.get_root_items()
        assert len(root_items) == 2
        assert root_items[0].title == "第一章 储能行业概述"
        assert root_items[1].title == "第二章 市场分析"
        # 检查子项
        children = outline.get_children(root_items[0].id)
        assert len(children) == 1
        assert children[0].title == "第一节 储能技术分类"
        # 检查三级子项
        grandchildren = outline.get_children(children[0].id)
        assert len(grandchildren) == 2

    def test_create_from_text_plain(self) -> None:
        """测试从纯文本创建大纲"""
        industry_id = uuid.uuid4()
        text = """第一章 储能行业概述
储能行业概述内容

第一节 储能技术分类
储能技术分类内容

第二章 市场分析
市场分析内容
"""

        outline = Outline.create_from_text(
            title="储能行业白皮书大纲",
            text=text,
            industry_id=industry_id,
        )

        assert outline.title == "储能行业白皮书大纲"
        # 纯文本（非#开头）会被跳过，所以items为空
        assert len(outline.items) == 0

    def test_create_from_structure(self) -> None:
        """测试从结构化数据创建大纲"""
        industry_id = uuid.uuid4()
        structure = [
            {
                "title": "第一章 储能行业概述",
                "item_type": "SECTION",
                "description": "储能行业概述内容",
                "children": [
                    {
                        "title": "第一节 储能技术分类",
                        "item_type": "SUBSECTION",
                        "description": "储能技术分类内容",
                        "children": [],
                    },
                    {
                        "title": "第二节 市场规模",
                        "item_type": "SUBSECTION",
                        "children": [],
                    },
                ],
            },
            {
                "title": "第二章 政策分析",
                "item_type": "SECTION",
                "children": [],
            },
        ]

        outline = Outline.create_from_structure(
            title="储能行业白皮书大纲",
            structure=structure,
            industry_id=industry_id,
        )

        assert outline.title == "储能行业白皮书大纲"
        assert len(outline.items) == 4
        assert outline.get_root_items()[0].title == "第一章 储能行业概述"
        assert outline.get_root_items()[1].title == "第二章 政策分析"

    def test_create_from_structure_with_order(self) -> None:
        """测试从结构化数据创建大纲（带自定义order）"""
        industry_id = uuid.uuid4()
        structure = [
            {
                "title": "第二章",
                "item_type": "SECTION",
                "order": 2,
                "children": [],
            },
            {
                "title": "第一章",
                "item_type": "SECTION",
                "order": 1,
                "children": [],
            },
        ]

        outline = Outline.create_from_structure(
            title="大纲",
            structure=structure,
            industry_id=industry_id,
        )

        root_items = outline.get_root_items()
        assert root_items[0].title == "第二章"
        assert root_items[0].order == 2
        assert root_items[1].title == "第一章"
        assert root_items[1].order == 1


class TestOutlineItemType:
    """OutlineItemType枚举测试类"""

    def test_outline_item_type_values(self) -> None:
        """测试大纲项类型枚举值"""
        expected_types = {
            "SECTION",
            "SUBSECTION",
            "PARAGRAPH",
            "CONTENT",
        }

        actual_types = {item_type.value for item_type in OutlineItemType}
        assert actual_types == expected_types

    def test_outline_item_type_count(self) -> None:
        """测试大纲项类型数量"""
        assert len(OutlineItemType) == 4


class TestOutlineStatus:
    """OutlineStatus枚举测试类"""

    def test_outline_status_values(self) -> None:
        """测试大纲状态枚举值"""
        expected_statuses = {
            "DRAFT",
            "OPTIMIZING",
            "OPTIMIZED",
            "ACCEPTED",
            "REJECTED",
            "FINALIZED",
        }

        actual_statuses = {status.value for status in OutlineStatus}
        assert actual_statuses == expected_statuses

    def test_outline_status_count(self) -> None:
        """测试大纲状态数量"""
        assert len(OutlineStatus) == 6


class TestConvenienceFunctions:
    """便利函数测试类"""

    def test_create_outline_from_text(self) -> None:
        """测试从文本创建大纲的便捷函数"""
        industry_id = uuid.uuid4()
        text = "# 第一章\n内容"

        outline = create_outline_from_text(
            title="大纲",
            text=text,
            industry_id=industry_id,
        )

        assert isinstance(outline, Outline)
        assert outline.title == "大纲"
        assert len(outline.items) > 0

    def test_create_outline_from_structure(self) -> None:
        """测试从结构化数据创建大纲的便捷函数"""
        industry_id = uuid.uuid4()
        structure = [
            {
                "title": "第一章",
                "item_type": "SECTION",
                "children": [],
            }
        ]

        outline = create_outline_from_structure(
            title="大纲",
            structure=structure,
            industry_id=industry_id,
        )

        assert isinstance(outline, Outline)
        assert outline.title == "大纲"
        assert len(outline.items) > 0
