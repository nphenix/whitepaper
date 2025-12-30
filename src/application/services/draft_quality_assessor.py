"""
草稿质量评估服务

该模块实现草稿质量评估功能,评估草稿的结构完整度,数据引用完整性,逻辑一致性等.
提供质量评分和改进建议,用于MVP 3步流程中的第四步: 草稿生成(带素材追溯链接).

生成命令: /speckit.implement T238A
生成时间: 2025-12-25
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
from enum import Enum
from typing import Any

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.domain.agent.draft import Draft, DraftSectionType
from src.domain.agent.source_reference import SourceReference
from src.shared.config.llm_service import LLMService
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class QualityDimension(str, Enum):
    """质量维度枚举"""

    STRUCTURE = "structure"  # 结构完整度
    REFERENCE = "reference"  # 数据引用完整性
    LOGIC = "logic"  # 逻辑一致性
    LANGUAGE = "language"  # 语言流畅性
    COMPLETENESS = "completeness"  # 内容完整性


class QualityScore(BaseModel):
    """质量评分模型"""

    dimension: str = Field(..., description="质量维度")
    score: float = Field(..., ge=0.0, le=1.0, description="评分(0-1)")
    description: str = Field(..., description="评分说明")


class ImprovementSuggestion(BaseModel):
    """改进建议模型"""

    dimension: str = Field(..., description="质量维度")
    priority: str = Field(..., description="优先级(high/medium/low)")
    suggestion: str = Field(..., description="改进建议")
    affected_sections: list[str] = Field(
        default_factory=list, description="受影响的章节ID列表"
    )


class QualityAssessmentResult(BaseModel):
    """质量评估结果模型"""

    overall_score: float = Field(..., ge=0.0, le=1.0, description="总体评分(0-1)")
    dimension_scores: list[QualityScore] = Field(
        ..., description="各维度评分列表"
    )
    improvement_suggestions: list[ImprovementSuggestion] = Field(
        ..., description="改进建议列表"
    )
    summary: str = Field(..., description="评估摘要")
    details: dict[str, Any] = Field(
        default_factory=dict, description="详细评估信息"
    )


class DraftQualityAssessor:
    """
    草稿质量评估服务

    提供草稿质量评估功能,包括:
    1. 结构完整度评估(章节层级,标题完整性等)
    2. 数据引用完整性评估(引用是否完整,是否有缺失等)
    3. 逻辑一致性评估(使用LLM评估内容逻辑)
    4. 质量评分和改进建议生成
    """

    def __init__(self, llm_service: LLMService | None = None) -> None:
        """
        初始化草稿质量评估服务

        Args:
            llm_service: LLM服务实例(可选,用于逻辑一致性评估)
        """
        self.llm_service = llm_service or LLMService()
        self._model = None

    @property
    def model(self) -> BaseLanguageModel:
        """获取LLM模型实例(延迟加载)

        Returns:
            LLM模型实例
        """
        if self._model is None:
            self._model = self.llm_service.get_chat_model()
        return self._model

    def assess_quality(
        self,
        draft: Draft,
        source_references: dict[str, SourceReference] | None = None,
        use_llm: bool = True,
    ) -> QualityAssessmentResult:
        """
        评估草稿质量

        Args:
            draft: 草稿对象
            source_references: 信息源引用字典(ID -> SourceReference),可选
            use_llm: 是否使用LLM进行逻辑一致性评估(默认True)

        Returns:
            质量评估结果
        """
        logger.info("开始评估草稿质量: %s", draft.title)

        # 1. 评估结构完整度
        structure_score = self._assess_structure_completeness(draft)

        # 2. 评估数据引用完整性
        reference_score = self._assess_reference_completeness(
            draft, source_references or {}
        )

        # 3. 评估逻辑一致性(可选,使用LLM)
        logic_score = None
        if use_llm:
            try:
                logic_score = self._assess_logic_consistency(draft)
            except Exception as e:
                logger.warning("LLM逻辑一致性评估失败: %s", e)
                # 如果LLM评估失败,使用默认值
                logic_score = QualityScore(
                    dimension=QualityDimension.LOGIC.value,
                    score=0.5,
                    description="逻辑一致性评估失败,使用默认评分",
                )

        # 4. 评估语言流畅性(可选,使用LLM)
        language_score = None
        if use_llm:
            try:
                language_score = self._assess_language_fluency(draft)
            except Exception as e:
                logger.warning("LLM语言流畅性评估失败: %s", e)
                language_score = QualityScore(
                    dimension=QualityDimension.LANGUAGE.value,
                    score=0.5,
                    description="语言流畅性评估失败,使用默认评分",
                )

        # 5. 评估内容完整性
        completeness_score = self._assess_content_completeness(draft)

        # 6. 计算总体评分
        dimension_scores = [
            structure_score,
            reference_score,
            completeness_score,
        ]
        if logic_score:
            dimension_scores.append(logic_score)
        if language_score:
            dimension_scores.append(language_score)

        overall_score = sum(score.score for score in dimension_scores) / len(
            dimension_scores
        )

        # 7. 生成改进建议
        improvement_suggestions = self._generate_improvement_suggestions(
            draft, dimension_scores, source_references or {}
        )

        # 8. 生成评估摘要
        summary = self._generate_summary(overall_score, dimension_scores)

        # 9. 构建详细评估信息
        details = {
            "total_sections": len(draft.sections),
            "root_sections": len(draft.get_root_sections()),
            "sections_with_references": sum(
                1
                for section in draft.sections
                if section.has_source_references()
            ),
            "total_references": sum(
                len(section.source_references) for section in draft.sections
            ),
        }

        result = QualityAssessmentResult(
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            improvement_suggestions=improvement_suggestions,
            summary=summary,
            details=details,
        )

        logger.info("草稿质量评估完成: %s (总体评分: %.2f)", draft.title, overall_score)
        return result

    def _assess_structure_completeness(self, draft: Draft) -> QualityScore:
        """
        评估结构完整度

        检查:
        1. 是否有根级章节
        2. 章节层级是否合理
        3. 标题是否完整
        4. 章节顺序是否合理

        Args:
            draft: 草稿对象

        Returns:
            结构完整度评分
        """
        issues = []
        score = 1.0

        # 检查是否有根级章节
        root_sections = draft.get_root_sections()
        if not root_sections:
            issues.append("缺少根级章节")
            score -= 0.3

        # 检查章节层级是否合理
        max_level = max((section.level for section in draft.sections), default=1)
        if max_level > 6:
            issues.append("章节层级过深(超过6级)")
            score -= 0.1

        # 检查标题完整性
        sections_without_title = [
            section
            for section in draft.sections
            if section.section_type
            in [DraftSectionType.TITLE, DraftSectionType.SECTION]
            and (not section.title or not section.title.strip())
        ]
        if sections_without_title:
            issues.append(f"有{len(sections_without_title)}个章节缺少标题")
            score -= min(0.2, len(sections_without_title) * 0.05)

        # 检查章节顺序
        root_sections_sorted = sorted(root_sections, key=lambda s: s.order)
        for i, section in enumerate(root_sections_sorted):
            if section.order != i:
                issues.append("章节顺序不合理")
                score -= 0.1
                break

        # 确保评分在0-1范围内
        score = max(0.0, min(1.0, score))

        description = "结构完整"
        if issues:
            description = f"发现{len(issues)}个结构问题: {', '.join(issues)}"

        return QualityScore(
            dimension=QualityDimension.STRUCTURE.value,
            score=score,
            description=description,
        )

    def _assess_reference_completeness(
        self, draft: Draft, source_references: dict[str, SourceReference]
    ) -> QualityScore:
        """
        评估数据引用完整性

        检查:
        1. 章节是否有引用
        2. 引用是否有效
        3. 引用是否完整

        Args:
            draft: 草稿对象
            source_references: 信息源引用字典

        Returns:
            数据引用完整性评分
        """
        issues = []
        score = 1.0

        total_sections = len(draft.sections)
        if total_sections == 0:
            return QualityScore(
                dimension=QualityDimension.REFERENCE.value,
                score=0.0,
                description="草稿中没有章节",
            )

        # 统计有引用的章节
        sections_with_references = 0
        invalid_references = 0

        for section in draft.sections:
            if section.has_source_references():
                sections_with_references += 1
                # 检查引用是否有效
                for ref_id in section.source_references:
                    ref_id_str = str(ref_id)
                    if ref_id_str not in source_references:
                        invalid_references += 1

        # 计算引用覆盖率
        reference_coverage = sections_with_references / total_sections if total_sections > 0 else 0.0

        # 如果引用覆盖率低于50%,降低评分
        if reference_coverage < 0.5:
            issues.append(f"引用覆盖率低({reference_coverage:.1%})")
            score -= 0.3
        elif reference_coverage < 0.7:
            issues.append(f"引用覆盖率中等({reference_coverage:.1%})")
            score -= 0.15

        # 如果有无效引用,降低评分
        if invalid_references > 0:
            issues.append(f"有{invalid_references}个无效引用")
            score -= min(0.2, invalid_references * 0.05)

        # 确保评分在0-1范围内
        score = max(0.0, min(1.0, score))

        description = "引用完整"
        if issues:
            description = f"发现{len(issues)}个引用问题: {', '.join(issues)}"
        else:
            description = f"引用覆盖率: {reference_coverage:.1%}"

        return QualityScore(
            dimension=QualityDimension.REFERENCE.value,
            score=score,
            description=description,
        )

    def _assess_logic_consistency(self, draft: Draft) -> QualityScore:
        """
        评估逻辑一致性(使用LLM)

        使用LLM评估草稿内容的逻辑一致性,包括:
        1. 章节之间的逻辑连贯性
        2. 内容的前后一致性
        3. 论证的逻辑性

        Args:
            draft: 草稿对象

        Returns:
            逻辑一致性评分
        """
        # 构建草稿内容摘要
        draft_summary = self._build_draft_summary(draft)

        # 构建提示词
        system_message = """你是一个专业的文档质量评估专家,擅长评估文档的逻辑一致性.
请评估以下草稿的逻辑一致性,包括:
1. 章节之间的逻辑连贯性
2. 内容的前后一致性
3. 论证的逻辑性

请给出0-1之间的评分(0表示逻辑不一致,1表示逻辑完全一致),并提供简要说明."""

        user_message = f"""请评估以下草稿的逻辑一致性:

标题: {draft.title}
描述: {draft.description or '无'}

章节结构:
{draft_summary}

请以JSON格式返回评估结果,格式如下:
{{
    "score": 0.85,
    "description": "逻辑一致性评估说明"
}}"""

        try:
            # 调用LLM
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=user_message),
            ]

            response = self.model.invoke(messages)

            # 解析响应
            if hasattr(response, "content"):
                content = response.content
            elif isinstance(response, str):
                content = response
            else:
                content = str(response)

            # 尝试解析JSON
            try:
                # 尝试直接解析JSON
                result = json.loads(content)
            except json.JSONDecodeError:
                # 如果直接解析失败,尝试从文本中提取JSON
                import re

                json_match = re.search(r"\{[^{}]*\"score\"[^{}]*\}", content)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    # 如果还是失败,使用默认值
                    logger.warning("无法解析LLM响应为JSON,使用默认评分")
                    result = {"score": 0.5, "description": "无法解析LLM响应"}

            score = float(result.get("score", 0.5))
            description = result.get("description", "逻辑一致性评估")

            # 确保评分在0-1范围内
            score = max(0.0, min(1.0, score))

            return QualityScore(
                dimension=QualityDimension.LOGIC.value,
                score=score,
                description=description,
            )

        except Exception as e:
            logger.error("LLM逻辑一致性评估失败: %s", e)
            raise

    def _assess_language_fluency(self, draft: Draft) -> QualityScore:
        """
        评估语言流畅性(使用LLM)

        使用LLM评估草稿的语言流畅性,包括:
        1. 语言表达是否流畅
        2. 用词是否准确
        3. 句式是否多样

        Args:
            draft: 草稿对象

        Returns:
            语言流畅性评分
        """
        # 构建草稿内容摘要(取前几个章节的内容)
        content_samples = []
        for section in draft.sections[:5]:  # 只取前5个章节
            if section.content:
                content_samples.append(f"{section.title or '无标题'}: {section.content[:200]}")

        content_text = "\n\n".join(content_samples)

        # 构建提示词
        system_message = """你是一个专业的文档质量评估专家,擅长评估文档的语言流畅性.
请评估以下草稿样本的语言流畅性,包括:
1. 语言表达是否流畅
2. 用词是否准确
3. 句式是否多样

请给出0-1之间的评分(0表示语言不流畅,1表示语言完全流畅),并提供简要说明."""

        user_message = f"""请评估以下草稿样本的语言流畅性:

标题: {draft.title}

内容样本:
{content_text}

请以JSON格式返回评估结果,格式如下:
{{
    "score": 0.85,
    "description": "语言流畅性评估说明"
}}"""

        try:
            # 调用LLM
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=user_message),
            ]

            response = self.model.invoke(messages)

            # 解析响应
            if hasattr(response, "content"):
                content = response.content
            elif isinstance(response, str):
                content = response
            else:
                content = str(response)

            # 尝试解析JSON
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                import re

                json_match = re.search(r"\{[^{}]*\"score\"[^{}]*\}", content)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    logger.warning("无法解析LLM响应为JSON,使用默认评分")
                    result = {"score": 0.5, "description": "无法解析LLM响应"}

            score = float(result.get("score", 0.5))
            description = result.get("description", "语言流畅性评估")

            # 确保评分在0-1范围内
            score = max(0.0, min(1.0, score))

            return QualityScore(
                dimension=QualityDimension.LANGUAGE.value,
                score=score,
                description=description,
            )

        except Exception as e:
            logger.error("LLM语言流畅性评估失败: %s", e)
            raise

    def _assess_content_completeness(self, draft: Draft) -> QualityScore:
        """
        评估内容完整性

        检查:
        1. 章节是否有内容
        2. 内容长度是否合理
        3. 是否有空章节

        Args:
            draft: 草稿对象

        Returns:
            内容完整性评分
        """
        issues = []
        score = 1.0

        total_sections = len(draft.sections)
        if total_sections == 0:
            return QualityScore(
                dimension=QualityDimension.COMPLETENESS.value,
                score=0.0,
                description="草稿中没有章节",
            )

        # 检查空章节
        empty_sections = [
            section
            for section in draft.sections
            if not section.content or not section.content.strip()
        ]
        if empty_sections:
            issues.append(f"有{len(empty_sections)}个空章节")
            score -= min(0.3, len(empty_sections) * 0.05)

        # 检查内容长度
        short_sections = [
            section
            for section in draft.sections
            if section.content and len(section.content.strip()) < 50
        ]
        if short_sections:
            issues.append(f"有{len(short_sections)}个章节内容过短(少于50字)")
            score -= min(0.2, len(short_sections) * 0.03)

        # 确保评分在0-1范围内
        score = max(0.0, min(1.0, score))

        description = "内容完整"
        if issues:
            description = f"发现{len(issues)}个内容问题: {', '.join(issues)}"

        return QualityScore(
            dimension=QualityDimension.COMPLETENESS.value,
            score=score,
            description=description,
        )

    def _generate_improvement_suggestions(
        self,
        draft: Draft,
        dimension_scores: list[QualityScore],
        source_references: dict[str, SourceReference],
    ) -> list[ImprovementSuggestion]:
        """
        生成改进建议

        Args:
            draft: 草稿对象
            dimension_scores: 各维度评分列表
            source_references: 信息源引用字典

        Returns:
            改进建议列表
        """
        suggestions = []

        # 根据各维度评分生成建议
        for score in dimension_scores:
            if score.score < 0.7:  # 评分低于0.7的建议改进
                priority = "high" if score.score < 0.5 else "medium"

                if score.dimension == QualityDimension.STRUCTURE.value:
                    suggestion = self._generate_structure_suggestions(draft)
                elif score.dimension == QualityDimension.REFERENCE.value:
                    suggestion = self._generate_reference_suggestions(
                        draft, source_references
                    )
                elif score.dimension == QualityDimension.LOGIC.value or score.dimension == QualityDimension.LANGUAGE.value:
                    suggestion = score.description  # 使用LLM评估的描述
                elif score.dimension == QualityDimension.COMPLETENESS.value:
                    suggestion = self._generate_completeness_suggestions(draft)
                else:
                    suggestion = f"建议改进{score.dimension}维度"

                suggestions.append(
                    ImprovementSuggestion(
                        dimension=score.dimension,
                        priority=priority,
                        suggestion=suggestion,
                        affected_sections=[],
                    )
                )

        return suggestions

    def _generate_structure_suggestions(self, draft: Draft) -> str:
        """生成结构改进建议"""
        suggestions = []

        root_sections = draft.get_root_sections()
        if not root_sections:
            suggestions.append("添加根级章节")

        sections_without_title = [
            section
            for section in draft.sections
            if section.section_type
            in [DraftSectionType.TITLE, DraftSectionType.SECTION]
            and (not section.title or not section.title.strip())
        ]
        if sections_without_title:
            suggestions.append(f"为{len(sections_without_title)}个章节添加标题")

        return "; ".join(suggestions) if suggestions else "结构良好"

    def _generate_reference_suggestions(
        self, draft: Draft, source_references: dict[str, SourceReference]
    ) -> str:
        """生成引用改进建议"""
        suggestions = []

        sections_without_refs = [
            section
            for section in draft.sections
            if not section.has_source_references()
        ]
        if sections_without_refs:
            suggestions.append(
                f"为{len(sections_without_refs)}个章节添加信息源引用"
            )

        invalid_refs = 0
        for section in draft.sections:
            for ref_id in section.source_references:
                if str(ref_id) not in source_references:
                    invalid_refs += 1
        if invalid_refs > 0:
            suggestions.append(f"修复{invalid_refs}个无效引用")

        return "; ".join(suggestions) if suggestions else "引用完整"

    def _generate_completeness_suggestions(self, draft: Draft) -> str:
        """生成内容完整性改进建议"""
        suggestions = []

        empty_sections = [
            section
            for section in draft.sections
            if not section.content or not section.content.strip()
        ]
        if empty_sections:
            suggestions.append(f"为{len(empty_sections)}个空章节添加内容")

        short_sections = [
            section
            for section in draft.sections
            if section.content and len(section.content.strip()) < 50
        ]
        if short_sections:
            suggestions.append(f"扩充{len(short_sections)}个过短章节的内容")

        return "; ".join(suggestions) if suggestions else "内容完整"

    def _generate_summary(
        self, overall_score: float, dimension_scores: list[QualityScore]
    ) -> str:
        """生成评估摘要"""
        if overall_score >= 0.8:
            quality_level = "优秀"
        elif overall_score >= 0.6:
            quality_level = "良好"
        elif overall_score >= 0.4:
            quality_level = "一般"
        else:
            quality_level = "需要改进"

        summary = f"草稿质量评估: {quality_level}(总体评分: {overall_score:.2f})\n\n"
        summary += "各维度评分:\n"
        for score in dimension_scores:
            summary += f"- {score.dimension}: {score.score:.2f} - {score.description}\n"

        return summary

    def _build_draft_summary(self, draft: Draft) -> str:
        """构建草稿摘要(用于LLM评估)"""
        summary_lines = []
        for section in draft.sections[:10]:  # 只取前10个章节
            title = section.title or "无标题"
            content_preview = (
                section.content[:100] + "..." if len(section.content) > 100 else section.content
            )
            summary_lines.append(f"- {title} (层级{section.level}): {content_preview}")

        return "\n".join(summary_lines)


# 便利函数


def create_draft_quality_assessor(
    llm_service: LLMService | None = None,
) -> DraftQualityAssessor:
    """
    创建草稿质量评估服务实例

    Args:
        llm_service: LLM服务实例(可选)

    Returns:
        草稿质量评估服务实例
    """
    return DraftQualityAssessor(llm_service=llm_service)

