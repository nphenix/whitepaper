"""
大纲优化Agent

基于BaseAgent实现的大纲优化Agent,使用LangChain 1.0的Agent框架和结构化输出.
用于MVP 4步流程中的第二步: 大纲手写和AI优化.

生成命令: /speckit.implement T211
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
import uuid
from typing import Any

from pydantic import BaseModel, Field

from src.application.agent_base import AgentConfig, BaseAgent
from src.application.agents.outline_optimization_prompts import (
    OutlineOptimizationPrompts,
)
from src.domain.agent.optimized_outline import (
    OptimizationChangeType,
    OptimizationSummary,
    OptimizedOutline,
    OptimizedOutlineItem,
)
from src.domain.agent.outline import Outline, OutlineItem, OutlineItemType
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.agent_exceptions import (
    AgentExecutionError,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class OptimizationResult(BaseModel):
    """优化结果模型

    用于结构化输出的大纲优化结果.
    """

    optimization_summary: dict[str, Any] = Field(
        ..., description="优化摘要信息"
    )
    optimized_items: list[dict[str, Any]] = Field(
        ..., description="优化后的大纲项列表"
    )


class OutlineOptimizerAgent(BaseAgent):
    """
    大纲优化Agent

    基于BaseAgent实现的大纲优化Agent,提供:
    1. 大纲结构分析(识别缺失章节,逻辑顺序,层次结构)
    2. 大纲优化建议生成(新增章节,调整顺序,完善描述)
    3. 结构化输出(使用Pydantic模型确保格式一致)

    核心功能:
    - optimize_outline(outline, industry_name, database_names, report_type): 优化大纲
    - analyze_outline_structure(outline): 分析大纲结构
    - generate_optimization_suggestions(outline, context): 生成优化建议

    架构优势:
    - 使用LangChain 1.0的create_agent API
    - 支持结构化输出(response_format)
    - 统一使用BaseAgent的生命周期管理
    - 自动获得错误处理,日志记录,状态持久化等能力
    - 符合LangChain 1.0最佳实践
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_service: LLMService | None = None,
        report_type: str = "市场研究报告",
        language: str = "中文",
        style: str = "专业,客观,数据驱动",
        **kwargs,
    ):
        """初始化大纲优化Agent

        Args:
            config: Agent配置
            llm_service: LLM服务实例,如果为None则使用默认实例
            report_type: 报告类型(如市场研究报告,产业分析报告等)
            language: 语言(如中文,英文等)
            style: 风格(如专业,客观,数据驱动等)
            **kwargs: 传递给BaseAgent的其他参数
        """
        super().__init__(config, llm_service=llm_service, **kwargs)

        # MVP默认约束条件(不依赖阶段6)
        self.report_type = report_type
        self.language = language
        self.style = style

        logger.info(
            "初始化OutlineOptimizerAgent: %s, 报告类型=%s, 语言=%s, 风格=%s",
            self.agent_name,
            self.report_type,
            self.language,
            self.style,
        )

    def get_tools(self) -> list:
        """获取Agent专用工具列表

        大纲优化Agent主要使用LLM直接进行优化,不需要额外的工具.
        如果需要,可以添加知识库检索工具等.

        Returns:
            空列表(大纲优化主要依赖LLM直接推理)
        """
        # 大纲优化Agent主要使用LLM直接进行优化
        # 如果需要,可以添加知识库检索工具等
        return []

    def optimize_outline(
        self,
        outline: Outline,
        industry_name: str,
        database_names: list[str] | None = None,
        report_type: str | None = None,
    ) -> OptimizedOutline:
        """优化大纲

        使用LLM分析大纲结构,并提供优化建议.
        支持新增章节,调整顺序,完善描述等优化类型.

        Args:
            outline: 原始大纲对象
            industry_name: 行业名称
            database_names: 数据库名称列表
            report_type: 报告类型(如果不指定则使用默认值)

        Returns:
            优化后的大纲对象(OptimizedOutline)

        Raises:
            AgentExecutionError: 优化失败时抛出
        """
        try:
            logger.info(
                "开始优化大纲: %s, 行业=%s, 数据库=%s",
                outline.title,
                industry_name,
                database_names,
            )

            # 使用指定的报告类型或默认值
            report_type = report_type or self.report_type
            database_names = database_names or []

            # 1. 格式化大纲结构
            outline_structure = OutlineOptimizationPrompts.format_outline_structure(
                outline.to_dict()
            )

            # 2. 获取系统消息
            system_message = OutlineOptimizationPrompts.get_system_message(
                industry_name=industry_name,
                report_type=report_type,
                language=self.language,
                style=self.style,
            )

            # 3. 构建提示词模板
            prompt_template = OutlineOptimizationPrompts.get_optimization_prompt()

            # 4. 格式化提示词模板（只传入模板需要的变量，不包含 system_message）
            formatted_messages = prompt_template.format_messages(
                outline_title=outline.title,
                outline_description=outline.description or "",
                industry_name=industry_name,
                database_names=", ".join(database_names) if database_names else "",
                outline_structure=outline_structure,
                report_type=report_type,
            )

            # 5. 构建完整的消息列表（包含系统消息和用户消息）
            messages = [
                {"role": "system", "content": system_message},
            ] + formatted_messages

            # 6. 使用结构化输出调用LLM
            # 注意:这里直接使用模型调用,不使用create_agent
            # 因为大纲优化是一个单次推理任务,不需要工具调用
            from langchain_core.output_parsers import JsonOutputParser
            from langchain_core.prompts import ChatPromptTemplate

            # 创建提示词
            prompt = ChatPromptTemplate.from_messages(messages)

            # 创建输出解析器
            output_parser = JsonOutputParser()

            # 构建链
            chain = prompt | self.model | output_parser

            # 执行链
            result = chain.invoke({})

            logger.info("LLM优化结果: %s", json.dumps(result, ensure_ascii=False))

            # 6. 解析优化结果并创建OptimizedOutline
            optimized_outline = self._parse_optimization_result(
                outline=outline,
                result=result,
                industry_name=industry_name,
                database_names=database_names,
                report_type=report_type,
            )

            logger.info("大纲优化完成: %s", outline.title)
            return optimized_outline

        except Exception as e:
            logger.error("大纲优化失败: %s", e)
            msg = f"大纲优化失败: {e}"
            raise AgentExecutionError(msg) from e

    def _parse_optimization_result(
        self,
        outline: Outline,
        result: dict[str, Any],
        industry_name: str,
        database_names: list[str],
        report_type: str,
    ) -> OptimizedOutline:
        """解析优化结果并创建OptimizedOutline

        Args:
            outline: 原始大纲对象
            result: LLM优化结果
            industry_name: 行业名称
            database_names: 数据库名称列表
            report_type: 报告类型

        Returns:
            优化后的大纲对象
        """
        # 创建OptimizedOutline
        optimized_outline = OptimizedOutline(
            original_outline_id=outline.id,
            optimization_status="PENDING",
        )

        # 1. 解析优化摘要
        summary_data = result.get("optimization_summary", {})
        # 如果优化摘要为空，提供默认值（LLM可能返回空字符串）
        optimization_summary_text = summary_data.get("optimization_summary", "")
        if not optimization_summary_text or not optimization_summary_text.strip():
            # 根据变更统计生成默认摘要
            total_changes = summary_data.get("total_changes", 0)
            if total_changes == 0:
                optimization_summary_text = "大纲无需优化，已保持原样"
            else:
                optimization_summary_text = f"大纲优化完成，共进行了{total_changes}项变更"
        
        # 处理key_improvements和potential_issues，确保所有元素都是字符串
        # LLM可能返回混合类型（字符串、整数等），需要统一转换为字符串
        key_improvements_raw = summary_data.get("key_improvements", [])
        key_improvements = []
        if isinstance(key_improvements_raw, list):
            for item in key_improvements_raw:
                if isinstance(item, str):
                    key_improvements.append(item)
                else:
                    # 将非字符串类型转换为字符串
                    key_improvements.append(str(item))
        elif key_improvements_raw:
            # 如果不是列表，尝试转换为列表
            logger.warning("key_improvements不是列表格式: %s", type(key_improvements_raw))
            key_improvements = [str(key_improvements_raw)]
        
        potential_issues_raw = summary_data.get("potential_issues", [])
        potential_issues = []
        if isinstance(potential_issues_raw, list):
            for item in potential_issues_raw:
                if isinstance(item, str):
                    potential_issues.append(item)
                else:
                    # 将非字符串类型转换为字符串
                    potential_issues.append(str(item))
        elif potential_issues_raw:
            # 如果不是列表，尝试转换为列表
            logger.warning("potential_issues不是列表格式: %s", type(potential_issues_raw))
            potential_issues = [str(potential_issues_raw)]
        
        optimization_summary = OptimizationSummary(
            optimized_outline_id=optimized_outline.id,
            total_changes=summary_data.get("total_changes", 0),
            added_items=summary_data.get("added_items", 0),
            modified_items=summary_data.get("modified_items", 0),
            deleted_items=summary_data.get("deleted_items", 0),
            moved_items=summary_data.get("moved_items", 0),
            reordered_items=summary_data.get("reordered_items", 0),
            merged_items=summary_data.get("merged_items", 0),
            split_items=summary_data.get("split_items", 0),
            quality_score=summary_data.get("quality_score", 0.0),
            completeness_score=summary_data.get("completeness_score", 0.0),
            coherence_score=summary_data.get("coherence_score", 0.0),
            relevance_score=summary_data.get("relevance_score", 0.0),
            optimization_summary=optimization_summary_text,
            key_improvements=key_improvements,
            potential_issues=potential_issues,
        )
        optimized_outline.set_summary(optimization_summary)

        # 2. 解析优化项
        optimized_items_data = result.get("optimized_items", [])
        if not isinstance(optimized_items_data, list):
            logger.warning(
                "LLM返回的 optimized_items 不是 list，跳过解析: type=%s",
                type(optimized_items_data),
            )
            optimized_items_data = []

        def _safe_outline_item_type(v: Any) -> OutlineItemType:
            if not v:
                return OutlineItemType.SECTION
            try:
                return OutlineItemType(str(v))
            except Exception:
                return OutlineItemType.SECTION

        def _safe_change_type(v: Any) -> OptimizationChangeType:
            if not v:
                return OptimizationChangeType.NONE
            try:
                return OptimizationChangeType(str(v))
            except Exception:
                return OptimizationChangeType.NONE

        def _safe_int(v: Any, default: int) -> int:
            try:
                return int(v)
            except Exception:
                return default

        for item_data in optimized_items_data:
            if not isinstance(item_data, dict):
                logger.warning("optimized_items 中出现非 dict 项，已跳过: %s", type(item_data))
                continue
            # 获取原始项(如果存在)
            original_item_id_str = item_data.get("original_item_id")
            original_item = None
            original_item_id = None
            if original_item_id_str:
                # 只有当original_item_id是有效的UUID格式时才尝试转换
                # LLM可能返回非UUID格式的ID（如数字字符串"1"）
                try:
                    original_item_id = uuid.UUID(original_item_id_str)
                    original_item = outline.get_item(original_item_id)
                except (ValueError, TypeError):
                    # 如果不是有效的UUID格式，记录警告并跳过原始项匹配
                    logger.warning(
                        "原始项ID不是有效的UUID格式，跳过匹配: original_item_id=%s",
                        original_item_id_str
                    )
                    original_item_id = None
                    original_item = None

            # 创建优化后项
            optimized_item_data = item_data.get("optimized_item", {})
            if not isinstance(optimized_item_data, dict):
                logger.warning(
                    "optimized_item 不是 dict，已跳过: %s (item_data keys=%s)",
                    type(optimized_item_data),
                    list(item_data.keys()),
                )
                continue

            title = str(optimized_item_data.get("title") or "").strip()
            # LLM 有时会返回脏数据（例如最后一个元素只有 original_item_id=null），
            # 这种情况不应让整个优化流程失败。
            if not title:
                logger.warning("优化项标题为空，已跳过该项: item_data=%s", item_data)
                continue

            optimized_item = OutlineItem(
                parent_id=None,  # 父级ID将在后续处理
                item_type=_safe_outline_item_type(optimized_item_data.get("item_type")),
                level=_safe_int(optimized_item_data.get("level", 1), default=1),
                title=title,
                description=optimized_item_data.get("description"),
                order=_safe_int(optimized_item_data.get("order", 0), default=0),
            )

            # 创建优化项
            optimized_outline_item = OptimizedOutlineItem(
                original_outline_id=outline.id,
                original_item_id=original_item_id,
                original_item=original_item,
                optimized_item=optimized_item,
                change_type=_safe_change_type(item_data.get("change_type", "NONE")),
                change_description=item_data.get("change_description"),
                optimization_reason=item_data.get("optimization_reason"),
                optimization_suggestions=item_data.get(
                    "optimization_suggestions", []
                ),
            )

            optimized_outline.add_optimized_item(optimized_outline_item)

        logger.info(
            "解析优化结果完成: %d个优化项",
            len(optimized_outline.optimized_items),
        )

        return optimized_outline

    def analyze_outline_structure(self, outline: Outline) -> dict[str, Any]:
        """分析大纲结构

        分析大纲的完整性,准确性,逻辑性和可读性.

        Args:
            outline: 大纲对象

        Returns:
            分析结果字典
        """
        analysis = {
            "total_items": len(outline.items),
            "root_items": len(outline.get_root_items()),
            "max_level": max((item.level for item in outline.items), default=0),
            "items_by_level": {},
            "items_by_type": {},
        }

        # 按层级统计
        for level in range(1, 7):
            items_at_level = outline.get_items_by_level(level)
            analysis["items_by_level"][f"level_{level}"] = len(
                items_at_level
            )

        # 按类型统计
        for item_type in OutlineItemType:
            items_of_type = outline.get_items_by_type(item_type)
            analysis["items_by_type"][item_type.value] = len(
                items_of_type
            )

        # 分析结构问题
        issues = []

        # 检查是否有孤立节点
        for item in outline.items:
            if item.parent_id:
                parent_exists = any(
                    parent.id == item.parent_id for parent in outline.items
                )
                if not parent_exists:
                    issues.append(f"孤立节点: {item.title}")

        # 检查层级是否合理
        for item in outline.items:
            if item.level > 4:
                issues.append(
                    f"层级过深: {item.title} (层级={item.level})"
                )

        analysis["issues"] = issues

        return analysis

    def generate_optimization_suggestions(
        self, outline: Outline, context: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """生成优化建议

        基于大纲分析和上下文信息,生成优化建议.

        Args:
            outline: 大纲对象
            context: 上下文信息(行业,数据库等)

        Returns:
            优化建议列表
        """
        suggestions = []

        # 分析大纲结构
        structure_analysis = self.analyze_outline_structure(outline)

        # 基于分析结果生成建议
        if structure_analysis["issues"]:
            for issue in structure_analysis["issues"]:
                suggestions.append(
                    {
                        "type": "FIX_ISSUE",
                        "description": issue,
                        "priority": "HIGH",
                    }
                )

        # 检查完整性
        root_items = outline.get_root_items()
        if len(root_items) < 3:
            suggestions.append(
                {
                    "type": "ADD_SECTION",
                    "description": "建议增加更多一级章节以完善大纲结构",
                    "priority": "MEDIUM",
                }
            )

        # 检查层级深度
        max_level = structure_analysis["max_level"]
        if max_level < 2:
            suggestions.append(
                {
                    "type": "ADD_SUBSECTION",
                    "description": "建议增加二级章节以细化内容",
                    "priority": "MEDIUM",
                }
            )

        return suggestions

    def _get_system_message(self) -> str:
        """获取系统消息

        重写BaseAgent的系统消息,提供大纲优化Agent的专用说明.
        """
        base_message = super()._get_system_message()
        return f"""{base_message}

你是一个专业的文档大纲优化专家,专注于{self.language}语言的{self.report_type}.

你的主要任务:
1. 分析用户提供的文档大纲结构
2. 识别大纲中的问题(缺失章节,逻辑顺序,层次结构等)
3. 提供具体的优化建议(新增,修改,删除,移动,重排,合并,拆分)
4. 确保优化后的大纲符合{self.report_type}的专业标准

优化原则:
- 保持原意:尽量保留用户原始大纲的核心思想和结构
- 增强逻辑:优化章节之间的逻辑关系和层次结构
- 补充缺失:识别并补充缺失的重要章节或内容
- 精简冗余:合并或删除重复或冗余的章节
- 规范命名:确保标题简洁明了,符合专业标准

语言和风格:
- 语言:{self.language}
- 风格:{self.style}
- 语气:正式,权威

请基于以上原则,对用户提供的大纲进行优化分析,并提供具体的优化建议.
"""


# 便利函数


def create_outline_optimizer_agent(
    agent_id: str = "outline_optimizer_mvp",
    agent_name: str = "OutlineOptimizerMVP",
    llm_service: LLMService | None = None,
    report_type: str = "市场研究报告",
    language: str = "中文",
    style: str = "专业,客观,数据驱动",
    **kwargs,
) -> OutlineOptimizerAgent:
    """创建大纲优化Agent的便捷函数

    Args:
        agent_id: Agent ID
        agent_name: Agent名称
        llm_service: LLM服务实例
        report_type: 报告类型
        language: 语言
        style: 风格
        **kwargs: 传递给Agent的其他参数

    Returns:
        OutlineOptimizerAgent实例
    """
    config = AgentConfig(
        agent_id=agent_id,
        agent_name=agent_name,
        agent_type="outline_optimizer",
        description="大纲优化Agent,用于分析和优化文档大纲结构",
        model_provider=kwargs.get("model_provider"),
        model_name=kwargs.get("model_name"),
        temperature=kwargs.get("temperature", 0.3),
        max_tokens=kwargs.get("max_tokens", 4000),
        enable_memory=kwargs.get("enable_memory", False),
        enable_error_handling=kwargs.get("enable_error_handling", True),
        enable_logging=kwargs.get("enable_logging", True),
    )

    return OutlineOptimizerAgent(
        config=config,
        llm_service=llm_service,
        report_type=report_type,
        language=language,
        style=style,
        **kwargs,
    )
