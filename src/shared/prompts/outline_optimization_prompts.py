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
    
    意图保护机制:
    - 严格约束模式:添加硬性约束,确保优化不偏离用户意图
    - 变更限制:限制新增、删除、修改章节的比例
    - 关键词保留:确保核心关键词不被丢失
    - 意图验证:要求LLM评估优化后的大纲与原始意图的相关性
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
        # 意图保护约束(新增)
        "intent_protection_constraints": {
            "max_added_ratio": 0.3,  # 最多添加30%的新章节
            "max_deleted_ratio": 0.1,  # 最多删除10%的原始章节
            "max_modified_ratio": 0.3,  # 最多修改30%的原始章节
            "keyword_retention_threshold": 0.7,  # 关键词保留率阈值
        },
    }

    # 严格模式下的硬性约束
    STRICT_CONSTRAINTS = """
【强制性约束 - 必须严格遵守】

1. 【不得删除用户核心章节】
   - 绝对不能删除用户原始大纲中的一级章节(除非用户明确要求)
   - 最多只能删除总章节数的10%
   - 如果认为某些章节不必要,在change_description中详细说明原因

2. 【新增章节必须合理】
   - 新增章节数量不得超过原始章节数量的30%
   - 新增的章节必须与用户原始意图直接相关
   - 避免添加用户未要求的"标准章节",除非确实必要

3. 【修改必须保持原意】
   - 修改章节标题时,必须保留核心关键词
   - 修改程度不能改变章节的本质含义
   - 最多只能修改30%的原始章节

4. 【必须保留用户核心意图】
   - 优化后的大纲必须保留用户原始意图的核心要点
   - 如果优化建议可能偏离用户意图,必须在optimization_summary中明确说明
   - relevance_score必须真实反映与原始大纲的相关程度

5. 【变更必须可追溯】
   - 每个变更都必须有明确的change_description
   - 每个修改都必须有合理的optimization_reason
   - 如果返回的relevance_score低于0.7,说明可能存在意图偏离

【优先级规则】
- 意图保护 > 专业标准 > 结构规范
- 如果上述约束与专业标准冲突,优先遵守意图保护约束
- 如果无法在满足约束的前提下进行优化,请返回原始大纲(使用NONE类型)
"""

    @classmethod
    def get_system_message(
        cls,
        industry_name: str,
        report_type: str = "市场研究报告",
        language: str = "中文",
        style: str = "专业,客观,数据驱动",
        strict_mode: bool = True,
    ) -> str:
        """
        获取系统消息

        Args:
            industry_name: 行业名称
            report_type: 报告类型
            language: 语言
            style: 风格
            strict_mode: 是否使用严格模式(启用意图保护约束)

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

        # 构建系统消息
        message = f"""你是一个专业的文档大纲优化专家,专注于{language}语言的{report_type}.

你的主要任务:
1. 分析用户提供的文档大纲结构
2. 识别大纲中的问题(缺失章节,逻辑顺序,层次结构等)
3. 提供具体的优化建议(新增,修改,删除,移动,重排,合并,拆分)
4. 确保优化后的大纲符合{report_type}的专业标准
5. 【最重要】确保优化后的大纲不偏离用户的原始意图

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
- 【第一优先级】保持原意:必须保留用户原始大纲的核心思想和结构,任何优化都不能偏离用户意图
- 增强逻辑:优化章节之间的逻辑关系和层次结构
- 补充缺失:识别并补充缺失的重要章节或内容
- 精简冗余:合并或删除重复或冗余的章节(但不能删除用户核心章节)
- 规范命名:确保标题简洁明了,符合专业标准

"""

        # 如果启用严格模式,添加硬性约束
        if strict_mode:
            message += cls.STRICT_CONSTRAINTS

        message += """
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
  - relevance_score: 【关键】相关性评分(0-1),必须真实反映与原始大纲的相关程度
  - optimization_summary: 优化摘要描述
  - key_improvements: 关键改进点列表
  - potential_issues: 潜在问题列表(如果relevance_score<0.7,必须说明原因)
- optimized_items: 优化后的大纲项列表
  - original_item_id: 原始大纲项ID(新增项为null)
  - change_type: 变更类型(ADD/MODIFY/DELETE/MOVE/REORDER/MERGE/SPLIT/NONE)
  - change_description: 变更描述(必须有)
  - optimization_reason: 优化原因(必须有)
  - optimization_suggestions: 优化建议列表
  - optimized_item: 优化后的大纲项
    - item_type: 项类型(SECTION/SUBSECTION/PARAGRAPH)
    - level: 层级
    - title: 标题
    - description: 描述
    - order: 排序顺序

请严格遵守上述约束,对用户提供的大纲进行优化。如果无法在满足所有约束的前提下进行优化,请返回原始大纲(所有项使用NONE类型),不要进行任何修改.
"""
        return message

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
