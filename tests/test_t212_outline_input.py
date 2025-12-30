#!/usr/bin/env python3
"""
大纲输入功能测试脚本

用于测试 T212 大纲输入功能，包括文本输入和结构化输入。
"""

import os
import sys
import uuid

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.application.services.outline_service import OutlineService


def test_outline_service():
    """测试大纲服务"""
    print("开始测试大纲服务...")

    # 初始化服务
    service = OutlineService()

    try:
        # 1. 测试从文本创建大纲
        print("\n1. 测试从文本创建大纲...")
        text_outline = """# 储能产业概述

## 市场规模
### 全球市场规模
### 中国市场规模

## 技术路线
### 锂离子电池
### 液流电池
### 压缩空气储能

## 应用场景
### 电网侧
### 用户侧
### 可再生能源配套
"""

        result = service.create_outline_from_text(
            title="储能产业发展白皮书大纲",
            text=text_outline,
            industry_id=str(uuid.uuid4()),  # 生成测试用的行业ID
            database_ids=[str(uuid.uuid4())],  # 生成测试用的数据库ID
            description="储能产业发展白皮书大纲",
            session_id="test-session-001",
        )

        print(f"   创建大纲成功: {result['outline_id']}")
        print(f"   标题: {result['title']}")
        print(f"   状态: {result['status']}")
        print(f"   大纲项数量: {result['total_items']}")
        outline_id = result["outline_id"]

        # 2. 测试获取大纲详情
        print("\n2. 测试获取大纲详情...")
        detail = service.get_outline(outline_id)
        print("   获取大纲详情成功")
        print(f"   标题: {detail['title']}")
        print(f"   状态: {detail['status']}")
        print(f"   当前版本: {detail['current_version']}")

        # 3. 测试获取大纲树结构
        print("\n3. 测试获取大纲树结构...")
        tree = service.get_outline_tree(outline_id)
        print("   获取大纲树结构成功")
        print(f"   树节点数量: {len(tree['tree'])}")
        for node in tree["tree"]:
            print(f"   - {node['title']} (level {node['level']})")

        # 4. 测试从结构化数据创建大纲
        print("\n4. 测试从结构化数据创建大纲...")
        structure_outline = [
            {
                "item_type": "SECTION",
                "title": "储能产业概述",
                "description": "储能产业的整体介绍",
                "order": 1,
                "children": [
                    {
                        "item_type": "SUBSECTION",
                        "title": "市场规模",
                        "description": "全球和中国市场规模分析",
                        "order": 1,
                        "children": [
                            {
                                "item_type": "PARAGRAPH",
                                "title": "全球市场规模",
                                "description": "全球储能市场规模数据",
                                "order": 1,
                            },
                            {
                                "item_type": "PARAGRAPH",
                                "title": "中国市场规模",
                                "description": "中国储能市场规模数据",
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "item_type": "SUBSECTION",
                        "title": "技术路线",
                        "description": "主要储能技术路线",
                        "order": 2,
                        "children": [
                            {
                                "item_type": "PARAGRAPH",
                                "title": "锂离子电池",
                                "description": "锂离子电池技术",
                                "order": 1,
                            },
                            {
                                "item_type": "PARAGRAPH",
                                "title": "液流电池",
                                "description": "液流电池技术",
                                "order": 2,
                            },
                        ],
                    },
                ],
            }
        ]

        result2 = service.create_outline_from_structure(
            title="储能产业技术路线大纲",
            structure=structure_outline,
            industry_id=str(uuid.uuid4()),
            database_ids=[str(uuid.uuid4())],
            description="储能产业技术路线大纲",
            session_id="test-session-002",
        )

        print(f"   创建大纲成功: {result2['outline_id']}")
        print(f"   标题: {result2['title']}")
        print(f"   状态: {result2['status']}")
        print(f"   大纲项数量: {result2['total_items']}")
        outline_id2 = result2["outline_id"]

        # 5. 测试添加大纲项
        print("\n5. 测试添加大纲项...")
        item_result = service.add_outline_item(
            outline_id=outline_id,
            parent_id=None,
            item_type="SECTION",
            title="新增章节",
            level=1,
            description="新增的章节描述",
            order=4,
        )
        print(f"   添加大纲项成功: {item_result['item_id']}")
        print(f"   标题: {item_result['item']['title']}")
        print(f"   层级: {item_result['item']['level']}")

        # 6. 测试更新大纲项
        print("\n6. 测试更新大纲项...")
        update_result = service.update_outline_item(
            outline_id=outline_id,
            item_id=item_result["item_id"],
            title="更新后的章节标题",
            description="更新后的章节描述",
            order=5,
        )
        print(f"   更新大纲项成功: {update_result['item_id']}")
        print(f"   新标题: {update_result['item']['title']}")

        # 7. 测试更新大纲
        print("\n7. 测试更新大纲...")
        update_outline_result = service.update_outline(
            outline_id=outline_id,
            title="更新后的大纲标题",
            description="更新后的大纲描述",
        )
        print("   更新大纲成功")
        print(f"   新标题: {update_outline_result['title']}")

        # 8. 测试列出大纲
        print("\n8. 测试列出大纲...")
        list_result = service.list_outlines(
            limit=10,
            offset=0,
        )
        print("   列出大纲成功")
        print(f"   总数量: {list_result['total']}")
        print(f"   返回数量: {len(list_result['outlines'])}")

        # 9. 测试删除大纲项
        print("\n9. 测试删除大纲项...")
        delete_item_result = service.delete_outline_item(
            outline_id=outline_id,
            item_id=item_result["item_id"],
        )
        print(f"   删除大纲项成功: {delete_item_result}")

        # 10. 测试删除大纲
        print("\n10. 测试删除大纲...")
        delete_result = service.delete_outline(outline_id)
        print(f"   删除大纲成功: {delete_result}")

        delete_result2 = service.delete_outline(outline_id2)
        print(f"   删除大纲成功: {delete_result2}")

        print("\n✅ 所有测试通过!")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_markdown_parsing():
    """测试Markdown解析功能"""
    print("\n\n测试Markdown解析功能...")

    service = OutlineService()

    try:
        # 测试不同层级的Markdown
        markdown_text = """# 一级标题

## 二级标题

### 三级标题

#### 四级标题

##### 五级标题

###### 六级标题

## 另一个二级标题

### 子章节1
### 子章节2
"""

        result = service.create_outline_from_text(
            title="Markdown解析测试",
            text=markdown_text,
            industry_id=str(uuid.uuid4()),
            database_ids=[],
        )

        print(f"   创建大纲成功: {result['outline_id']}")
        print(f"   大纲项数量: {result['total_items']}")

        # 获取树结构
        tree = service.get_outline_tree(result["outline_id"])
        print("   树结构:")
        for node in tree["tree"]:
            print(f"   - {node['title']} (level {node['level']})")
            for child in node.get("children", []):
                print(f"     - {child['title']} (level {child['level']})")

        # 清理
        service.delete_outline(result["outline_id"])

        print("\n✅ Markdown解析测试通过!")
        return True

    except Exception as e:
        print(f"\n❌ Markdown解析测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_structure_parsing():
    """测试结构化数据解析功能"""
    print("\n\n测试结构化数据解析功能...")

    service = OutlineService()

    try:
        # 测试嵌套结构
        structure = [
            {
                "item_type": "SECTION",
                "title": "第一章",
                "order": 1,
                "children": [
                    {
                        "item_type": "SUBSECTION",
                        "title": "1.1 小节",
                        "order": 1,
                        "children": [
                            {
                                "item_type": "PARAGRAPH",
                                "title": "1.1.1 段落",
                                "order": 1,
                            },
                            {
                                "item_type": "PARAGRAPH",
                                "title": "1.1.2 段落",
                                "order": 2,
                            },
                        ],
                    },
                    {
                        "item_type": "SUBSECTION",
                        "title": "1.2 小节",
                        "order": 2,
                    },
                ],
            },
            {
                "item_type": "SECTION",
                "title": "第二章",
                "order": 2,
                "children": [
                    {
                        "item_type": "SUBSECTION",
                        "title": "2.1 小节",
                        "order": 1,
                    },
                ],
            },
        ]

        result = service.create_outline_from_structure(
            title="结构化数据解析测试",
            structure=structure,
            industry_id=str(uuid.uuid4()),
            database_ids=[],
        )

        print(f"   创建大纲成功: {result['outline_id']}")
        print(f"   大纲项数量: {result['total_items']}")

        # 获取树结构
        tree = service.get_outline_tree(result["outline_id"])
        print("   树结构:")
        for node in tree["tree"]:
            print(f"   - {node['title']} (level {node['level']})")
            for child in node.get("children", []):
                print(f"     - {child['title']} (level {child['level']})")
                for grandchild in child.get("children", []):
                    print(
                        f"       - {grandchild['title']} (level {grandchild['level']})"
                    )

        # 清理
        service.delete_outline(result["outline_id"])

        print("\n✅ 结构化数据解析测试通过!")
        return True

    except Exception as e:
        print(f"\n❌ 结构化数据解析测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("T212 大纲输入功能测试")
    print("=" * 60)

    success = True

    # 运行所有测试
    success = test_outline_service() and success
    success = test_markdown_parsing() and success
    success = test_structure_parsing() and success

    print("\n" + "=" * 60)
    if success:
        print("✅ 所有测试通过!")
        sys.exit(0)
    else:
        print("❌ 部分测试失败!")
        sys.exit(1)
