"""
大纲优化提示词模板

该模块定义了大纲优化的提示词模板,支持变量替换和默认约束条件.
用于MVP 4步流程中的第二步: 大纲手写和AI优化.

生成命令: /speckit.implement T211A
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class OutlineOptimizationPrompts:
    """大纲优化提示词模板类

    提供大纲优化的提示词模板,支持变量替换和默认约束条件.
    """

    # 默认约束条件(MVP使用,不依赖阶段6)
    DEFAULT_CONSTRAINTS = """
    ## 默认约束条件

    ### 报告类型
    - 市场研究报告
    - 产业分析报告
    - 政策解读报告

    ### 语言风格
    - 语言:中文
    - 风格:专业,客观,数据驱动
    - 语气:正式,权威

    ### 内容要求
    - 必须基于数据和事实
    - 必须有明确的逻辑结构
    - 必须包含行业背景分析
    - 必须包含市场现状分析
    - 必须包含发展趋势分析
    - 必须包含政策环境分析
    - 必须包含竞争格局分析
    - 必须包含风险与挑战分析

    ### 结构要求
    - 一级标题:主要章节(如行业概述,市场分析,发展趋势等)
    - 二级标题:子章节(如市场规模,技术发展,政策影响等)
    - 三级标题:具体内容(如市场规模数据,技术路线图,政策解读等)
    - 层级深度:最多3-4级

    ### 质量标准
    - 完整性:覆盖主题的所有重要方面
    - 准确性:基于可靠的数据和信息
    - 逻辑性:章节之间有清晰的逻辑关系
    - 可读性:标题简洁明了,易于理解
    """

    @staticmethod
    def get_system_message(
        industry_name: str,
        report_type: str = "市场研究报告",
        language: str = "中文",
        style: str = "专业,客观,数据驱动",
    ) -> str:
        """获取系统消息

        Args:
            industry_name: 行业名称(如储能行业,能源行业等)
            report_type: 报告类型(如市场研究报告,产业分析报告等)
            language: 语言(如中文,英文等)
            style: 风格(如专业,客观,数据驱动等)

        Returns:
            系统消息字符串
        """
        return f"""你是一个专业的{industry_name}文档大纲优化专家.

你的职责是分析和优化用户提供的文档大纲,使其更加完善,结构清晰,逻辑严密.

## 你的专长
- 深入了解{industry_name}的行业特点和发展趋势
- 熟悉{report_type}的写作规范和结构要求
- 掌握文档大纲设计的原则和最佳实践

## 优化目标
1. **完整性**:确保大纲覆盖主题的所有重要方面
2. **准确性**:确保大纲基于可靠的数据和信息
3. **逻辑性**:确保章节之间有清晰的逻辑关系
4. **可读性**:确保标题简洁明了,易于理解
5. **专业性**:确保大纲符合{report_type}的专业标准

## 语言和风格
- 语言:{language}
- 风格:{style}
- 语气:正式,权威

{OutlineOptimizationPrompts.DEFAULT_CONSTRAINTS}

## 优化原则
1. **保持原意**:尽量保留用户原始大纲的核心思想和结构
2. **增强逻辑**:优化章节之间的逻辑关系和层次结构
3. **补充缺失**:识别并补充缺失的重要章节或内容
4. **精简冗余**:合并或删除重复或冗余的章节
5. **规范命名**:确保标题简洁明了,符合专业标准

## 优化建议类型
- **ADD(新增)**:建议新增的章节或内容
- **MODIFY(修改)**:建议修改的章节标题或描述
- **DELETE(删除)**:建议删除的冗余或不相关章节
- **MOVE(移动)**:建议调整章节的顺序或位置
- **REORDER(重排)**:建议重新组织章节的层级结构
- **MERGE(合并)**:建议合并相似或相关的章节
- **SPLIT(拆分)**:建议拆分过于复杂的章节

请基于以上原则,对用户提供的大纲进行优化分析,并提供具体的优化建议.
"""

    @staticmethod
    def get_optimization_prompt() -> ChatPromptTemplate:
        """获取大纲优化提示词模板

        Returns:
            ChatPromptTemplate实例
        """
        template = ChatPromptTemplate.from_messages(
            [
                (
                    "human",
                    """请分析以下文档大纲,并提供优化建议.

## 原始大纲信息
- 大纲标题:{outline_title}
- 大纲描述:{outline_description}
- 行业:{industry_name}
- 数据库:{database_names}

## 原始大纲结构
{outline_structure}

## 优化要求
1. 分析大纲的完整性,准确性,逻辑性和可读性
2. 识别需要新增,修改,删除,移动,重排,合并或拆分的章节
3. 为每个优化建议提供具体的理由和说明
4. 确保优化后的大纲符合{report_type}的专业标准

## 输出格式
请以JSON格式输出优化结果,包含以下字段:
```json
{{
  "optimization_summary": {{
    "total_changes": 总变更数,
    "added_items": 新增项数,
    "modified_items": 修改项数,
    "deleted_items": 删除项数,
    "moved_items": 移动项数,
    "reordered_items": 重排项数,
    "merged_items": 合并项数,
    "split_items": 拆分项数,
    "quality_score": 质量评分(0-1),
    "completeness_score": 完整度评分(0-1),
    "coherence_score": 连贯性评分(0-1),
    "relevance_score": 相关性评分(0-1),
    "optimization_summary": "优化摘要描述",
    "key_improvements": ["关键改进点1", "关键改进点2"],
    "potential_issues": ["潜在问题1", "潜在问题2"]
  }},
  "optimized_items": [
    {{
      "original_item_id": "原始项ID(如果是新增则为null)",
      "original_title": "原始标题(如果是新增则为null)",
      "original_description": "原始描述(如果是新增则为null)",
      "optimized_item": {{
        "title": "优化后标题",
        "description": "优化后描述",
        "item_type": "SECTION/SUBSECTION/PARAGRAPH",
        "level": 层级(1-6),
        "order": 排序顺序
      }},
      "change_type": "ADD/MODIFY/DELETE/MOVE/REORDER/MERGE/SPLIT/NONE",
      "change_description": "变更描述",
      "optimization_reason": "优化原因",
      "optimization_suggestions": ["优化建议1", "优化建议2"]
    }}
  ]
}}
```

请开始分析和优化大纲.""",
                ),
            ]
        )
        return template

    @staticmethod
    def format_outline_structure(outline_dict: dict[str, Any]) -> str:
        """格式化大纲结构为可读文本

        Args:
            outline_dict: 大纲字典

        Returns:
            格式化的大纲结构文本
        """
        def format_item(item: dict[str, Any], indent: int = 0) -> str:
            """格式化单个大纲项"""
            prefix = "  " * indent
            item_type = item.get("item_type", "")
            title = item.get("title", "")
            description = item.get("description", "")
            order = item.get("order", 0)

            type_symbol = {
                "SECTION": "#",
                "SUBSECTION": "##",
                "PARAGRAPH": "###",
                "CONTENT": "-",
            }.get(item_type, "-")

            result = f"{prefix}{type_symbol} {order}. {title}"
            if description:
                result += f"\n{prefix}   {description}"

            # 递归处理子项
            children = item.get("children", [])
            if children:
                for child in children:
                    result += "\n" + format_item(child, indent + 2)

            return result

        # 获取根级项
        items = outline_dict.get("items", [])
        root_items = [item for item in items if item.get("parent_id") is None]

        # 按order排序
        root_items_sorted = sorted(root_items, key=lambda x: x.get("order", 0))

        # 格式化
        result = ""
        for item in root_items_sorted:
            result += format_item(item) + "\n"

        return result.strip()

    @staticmethod
    def build_optimization_input(
        outline_title: str,
        outline_description: str | None,
        industry_name: str,
        database_names: list[str],
        outline_structure: str,
        report_type: str = "市场研究报告",
    ) -> dict[str, Any]:
        """构建优化输入字典

        Args:
            outline_title: 大纲标题
            outline_description: 大纲描述
            industry_name: 行业名称
            database_names: 数据库名称列表
            outline_structure: 大纲结构文本
            report_type: 报告类型

        Returns:
            优化输入字典
        """
        return {
            "system_message": OutlineOptimizationPrompts.get_system_message(
                industry_name=industry_name,
                report_type=report_type,
            ),
            "outline_title": outline_title,
            "outline_description": outline_description or "",
            "industry_name": industry_name,
            "database_names": ", ".join(database_names),
            "outline_structure": outline_structure,
            "report_type": report_type,
        }


# 便利函数


def get_outline_optimization_prompt() -> ChatPromptTemplate:
    """获取大纲优化提示词模板的便捷函数

    Returns:
        ChatPromptTemplate实例
    """
    return OutlineOptimizationPrompts.get_optimization_prompt()


def get_outline_optimization_system_message(
    industry_name: str,
    report_type: str = "市场研究报告",
    language: str = "中文",
    style: str = "专业,客观,数据驱动",
) -> str:
    """获取大纲优化系统消息的便捷函数

    Args:
        industry_name: 行业名称
        report_type: 报告类型
        language: 语言
        style: 风格

    Returns:
        系统消息字符串
    """
    return OutlineOptimizationPrompts.get_system_message(
        industry_name=industry_name,
        report_type=report_type,
        language=language,
        style=style,
    )
