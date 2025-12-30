"""
大纲优化提示词模板

该模块提供大纲优化的提示词模板,用于T211大纲优化Agent.
遵循LangChain 1.0最佳实践,使用ChatPromptTemplate和结构化输出.
支持变量替换和默认约束条件.

生成命令: /speckit.implement T211A
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

from typing import Any

from langchain_core.prompts import ChatPromptTemplate


class OutlineOptimizationPrompts:
    """
    大纲优化提示词模板类

    提供大纲优化的提示词模板和辅助方法.
    支持变量替换(行业,数据库,报告类型等).
    支持默认约束条件(报告类型,语言,风格等).
    """

    # 默认约束条件(MVP使用,不依赖阶段6)
    DEFAULT_CONSTRAINTS = {
        # 报告类型
        "report_type": "市场研究报告",
        # 语言风格
        "language": "中文",
        "style": "专业,客观,数据驱动",
        # 内容要求
        "content_requirements": [
            "内容必须基于事实和数据,避免主观臆断",
            "必须引用可靠的信息源,确保内容可信度",
            "数据必须准确,来源必须明确标注",
            "内容必须符合行业标准和专业规范",
        ],
        # 结构要求
        "structure_requirements": [
            "大纲结构必须清晰,层次分明",
            "章节顺序必须符合逻辑,便于阅读",
            "标题必须简洁明了,准确反映内容",
            "必须包含必要的章节:摘要,引言,正文,结论",
        ],
        # 质量标准
        "quality_standards": [
            "完整性:覆盖主题的所有重要方面",
            "准确性:信息准确无误,数据可靠",
            "逻辑性:内容逻辑清晰,论证严密",
            "可读性:语言流畅,易于理解",
            "专业性:符合行业专业标准",
        ],
    }

    @classmethod
    def get_system_message(
        cls,
        industry_name: str,
        report_type: str = "市场研究报告",
        language: str = "中文",
        style: str = "专业,客观,数据驱动",
    ) -> str:
        """
        获取系统消息

        Args:
            industry_name: 行业名称
            report_type: 报告类型
            language: 语言
            style: 风格

        Returns:
            系统消息字符串
        """
        content_requirements = "\n".join(
            f"- {req}" for req in cls.DEFAULT_CONSTRAINTS["content_requirements"]
        )
        structure_requirements = "\n".join(
            f"- {req}" for req in cls.DEFAULT_CONSTRAINTS["structure_requirements"]
        )
        quality_standards = "\n".join(
            f"- {std}" for std in cls.DEFAULT_CONSTRAINTS["quality_standards"]
        )

        return f"""你是一个专业的文档大纲优化专家,专注于{language}语言的{report_type}.

你的主要任务:
1. 分析用户提供的文档大纲结构
2. 识别大纲中的问题(缺失章节,逻辑顺序,层次结构等)
3. 提供具体的优化建议(新增,修改,删除,移动,重排,合并,拆分)
4. 确保优化后的大纲符合{report_type}的专业标准

行业背景:
- 目标行业: {industry_name}
- 报告类型: {report_type}
- 语言: {language}
- 风格: {style}

内容要求:
{content_requirements}

结构要求:
{structure_requirements}

质量标准:
{quality_standards}

优化原则:
- 保持原意:尽量保留用户原始大纲的核心思想和结构
- 增强逻辑:优化章节之间的逻辑关系和层次结构
- 补充缺失:识别并补充缺失的重要章节或内容
- 精简冗余:合并或删除重复或冗余的章节
- 规范命名:确保标题简洁明了,符合专业标准

输出格式要求:
请以JSON格式返回优化结果,包含以下字段:
- optimization_summary: 优化摘要信息
  - total_changes: 总变更数
  - added_items: 新增项数
  - modified_items: 修改项数
  - deleted_items: 删除项数
  - moved_items: 移动项数
  - reordered_items: 重排项数
  - merged_items: 合并项数
  - split_items: 拆分项数
  - quality_score: 优化质量评分(0-1)
  - completeness_score: 完整度评分(0-1)
  - coherence_score: 连贯性评分(0-1)
  - relevance_score: 相关性评分(0-1)
  - optimization_summary: 优化摘要描述
  - key_improvements: 关键改进点列表
  - potential_issues: 潜在问题列表
- optimized_items: 优化后的大纲项列表
  - original_item_id: 原始大纲项ID(新增项为null)
  - change_type: 变更类型(ADD/MODIFY/DELETE/MOVE/REORDER/MERGE/SPLIT/NONE)
  - change_description: 变更描述
  - optimization_reason: 优化原因
  - optimization_suggestions: 优化建议列表
  - optimized_item: 优化后的大纲项
    - item_type: 项类型(SECTION/SUBSECTION/PARAGRAPH)
    - level: 层级
    - title: 标题
    - description: 描述
    - order: 排序顺序

请基于以上原则,对用户提供的大纲进行优化分析,并提供具体的优化建议.
"""

    @classmethod
    def get_optimization_prompt(cls) -> ChatPromptTemplate:
        """
        获取优化提示词模板

        Returns:
            ChatPromptTemplate对象
        """
        template = """请分析以下文档大纲,并提供优化建议.

大纲信息:
- 大纲标题: {outline_title}
- 大纲描述: {outline_description}
- 目标行业: {industry_name}
- 数据库: {database_names}
- 报告类型: {report_type}

大纲结构:
{outline_structure}

请分析大纲的完整性,准确性,逻辑性和可读性,并提供具体的优化建议.
确保优化建议符合{report_type}的专业标准和{industry_name}的行业特点.

请以JSON格式返回优化结果."""

        return ChatPromptTemplate.from_template(template)

    @classmethod
    def format_outline_structure(cls, outline_dict: dict[str, Any]) -> str:
        """
        格式化大纲结构为可读文本

        Args:
            outline_dict: 大纲字典

        Returns:
            格式化的大纲结构文本
        """
        items = outline_dict.get("items", [])
        if not items:
            return "(空大纲)"

        lines = []
        for item in items:
            indent = "  " * (item.get("level", 1) - 1)
            title = item.get("title", "")
            description = item.get("description", "")
            item_type = item.get("item_type", "")
            level = item.get("level", 1)

            # 格式化项
            item_line = f"{indent}[{item_type} L{level}] {title}"
            if description:
                item_line += f": {description}"
            lines.append(item_line)

        return "\n".join(lines)

    @classmethod
    def build_optimization_input(
        cls,
        outline_title: str,
        outline_description: str | None,
        industry_name: str,
        database_names: list[str] | None,
        outline_structure: str,
        report_type: str = "市场研究报告",
    ) -> dict[str, Any]:
        """
        构建优化输入

        Args:
            outline_title: 大纲标题
            outline_description: 大纲描述
            industry_name: 行业名称
            database_names: 数据库名称列表
            outline_structure: 大纲结构(格式化后的文本)
            report_type: 报告类型

        Returns:
            优化输入字典
        """
        return {
            "outline_title": outline_title,
            "outline_description": outline_description or "",
            "industry_name": industry_name,
            "database_names": ", ".join(database_names) if database_names else "",
            "outline_structure": outline_structure,
            "report_type": report_type,
        }


# 便利函数


def get_outline_optimization_prompt() -> ChatPromptTemplate:
    """
    获取大纲优化提示词模板的便捷函数

    Returns:
        ChatPromptTemplate对象
    """
    return OutlineOptimizationPrompts.get_optimization_prompt()


def get_outline_optimization_system_message(
    industry_name: str,
    report_type: str = "市场研究报告",
    language: str = "中文",
    style: str = "专业,客观,数据驱动",
) -> str:
    """
    获取大纲优化系统消息的便捷函数

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
