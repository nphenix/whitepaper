"""
白皮书分析服务

该模块实现白皮书质量分析功能,使用LLM和LangChain 1.0进行内容质量评估,
结构分析,专业性与可信度评估,并提供改进建议.

生成命令: /speckit.implement T254
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
from typing import Any

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class WhitepaperAnalysisResult(BaseModel):
    """白皮书分析结果模型"""

    content_quality: dict[str, Any] = Field(..., description="内容质量评估")
    structure_analysis: dict[str, Any] = Field(..., description="结构分析")
    credibility: dict[str, Any] = Field(..., description="专业性与可信度评估")
    improvement_suggestions: list[dict[str, Any]] = Field(..., description="改进建议列表")
    overall_score: float = Field(..., ge=1.0, le=10.0, description="综合评分(1-10分)")
    summary: str = Field(..., description="分析摘要")
    strengths: list[str] = Field(..., description="优点列表")
    weaknesses: list[str] = Field(..., description="待改进点列表")


class WhitepaperAnalysisService:
    """
    白皮书分析服务

    使用LangChain 1.0和LLM进行白皮书质量分析,包括:
    - 内容质量评估(深度,全面性,数据支撑)
    - 结构分析(章节安排,逻辑连贯性)
    - 专业性与可信度评估
    - 改进建议生成
    - 综合评分(1-10分)
    """

    def __init__(self, llm_service: LLMService | None = None):
        """
        初始化白皮书分析服务

        Args:
            llm_service: LLM服务实例,如果为None则使用全局实例
        """
        self.llm_service = llm_service or get_llm_service()
        self._setup_prompt_template()

    def _setup_prompt_template(self):
        """设置提示词模板(符合LangChain 1.0最佳实践)"""
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一位资深的白皮书质量分析师和编辑,专门从事行业分析报告的质量评估.

请对提供的白皮书内容进行全面分析,并用中文提供详细的反馈.你的分析应该涵盖:

1. **内容质量评估**(Content Quality)
   - 论述深度与全面性:评估内容是否深入,是否覆盖了关键主题
   - 数据支撑与证据充分性:评估是否有充分的数据,统计和证据支持
   - 逻辑严密性与论证结构:评估论证是否严密,逻辑是否清晰

2. **结构分析**(Structure Analysis)
   - 章节安排是否合理:评估章节组织是否清晰,层次是否分明
   - 前后逻辑连贯性:评估章节之间的逻辑关系和连贯性
   - 重点突出程度:评估关键信息是否得到适当突出

3. **专业性与可信度**(Credibility)
   - 术语使用准确性:评估专业术语使用是否准确,规范
   - 引用文献质量:评估引用来源是否可靠,是否充分
   - 行业洞察深度:评估对行业的理解和洞察是否深入

4. **改进建议**(Improvement Recommendations)
   - 需要补充的内容或数据
   - 可以删减或简化的部分
   - 表达方式优化建议
   - 可视化建议(图表,数据表等)

5. **总体评分**(Overall Rating)
   - 给出1-10分的综合评分
   - 简要总结优点和待改进点

你的语气应该是建设性的,专业的和可操作的."""),
            ("human", """请分析以下白皮书内容:

{content}

请以JSON格式输出分析结果,包含以下字段:
{{
  "content_quality": {{
    "depth_score": 论述深度评分(0-10分,浮点数),
    "comprehensiveness_score": 全面性评分(0-10分,浮点数),
    "data_support_score": 数据支撑评分(0-10分,浮点数),
    "depth_comment": "深度评估说明(字符串)",
    "comprehensiveness_comment": "全面性评估说明(字符串)",
    "data_support_comment": "数据支撑评估说明(字符串)"
  }},
  "structure_analysis": {{
    "organization_score": 章节安排评分(0-10分,浮点数),
    "coherence_score": 逻辑连贯性评分(0-10分,浮点数),
    "emphasis_score": 重点突出程度评分(0-10分,浮点数),
    "organization_comment": "章节安排评估说明(字符串)",
    "coherence_comment": "逻辑连贯性评估说明(字符串)",
    "emphasis_comment": "重点突出程度评估说明(字符串)"
  }},
  "credibility": {{
    "terminology_score": 术语使用准确性评分(0-10分,浮点数),
    "citation_score": 引用文献质量评分(0-10分,浮点数),
    "insight_score": 行业洞察深度评分(0-10分,浮点数),
    "terminology_comment": "术语使用评估说明(字符串)",
    "citation_comment": "引用文献评估说明(字符串)",
    "insight_comment": "行业洞察评估说明(字符串)"
  }},
  "improvement_suggestions": [
    {{
      "category": "建议类别(如:内容补充、结构优化、表达改进等)",
      "priority": "优先级(高、中、低)",
      "suggestion": "具体建议内容",
      "location": "建议位置(如章节名称,可选)"
    }}
  ],
  "overall_score": 综合评分(1-10分,浮点数),
  "summary": "分析摘要(字符串)",
  "strengths": ["优点1", "优点2", ...],
  "weaknesses": ["待改进点1", "待改进点2", ...]
}}

请确保输出是有效的JSON格式,并且所有评分都在指定范围内."""),
        ])

    def analyze(self, content: str) -> WhitepaperAnalysisResult:
        """
        分析白皮书内容

        Args:
            content: 白皮书内容

        Returns:
            WhitepaperAnalysisResult: 分析结果

        Raises:
            ValueError: 如果内容为空
            Exception: 如果分析失败
        """
        if not content or not content.strip():
            msg = "白皮书内容不能为空"
            raise ValueError(msg)

        try:
            # 获取LLM模型
            llm = self.llm_service.get_chat_model()
            logger.info("开始分析白皮书内容,长度: %d 字符", len(content))

            # 创建输出解析器
            output_parser = JsonOutputParser()

            # 构建链(符合LangChain 1.0最佳实践)
            chain = self.prompt_template | llm | output_parser

            # 执行分析
            result_dict = chain.invoke({"content": content})

            logger.info("LLM分析完成,结果: %s", json.dumps(result_dict, ensure_ascii=False)[:200])

            # 验证和转换结果
            analysis_result = self._validate_and_convert_result(result_dict)

            logger.info("白皮书分析完成,综合评分: %.2f", analysis_result.overall_score)
            return analysis_result

        except Exception as e:
            logger.error("白皮书分析失败: %s", e, exc_info=True)
            msg = f"白皮书分析失败: {e!s}"
            raise Exception(msg) from e

    def _validate_and_convert_result(self, result_dict: dict[str, Any]) -> WhitepaperAnalysisResult:
        """
        验证和转换分析结果

        Args:
            result_dict: LLM返回的原始结果字典

        Returns:
            WhitepaperAnalysisResult: 验证后的分析结果

        Raises:
            ValueError: 如果结果格式不正确
        """
        try:
            # 验证必需字段
            required_fields = [
                "content_quality", "structure_analysis", "credibility",
                "improvement_suggestions", "overall_score", "summary",
                "strengths", "weaknesses"
            ]
            for field in required_fields:
                if field not in result_dict:
                    msg = f"分析结果缺少必需字段: {field}"
                    raise ValueError(msg)

            # 验证评分范围
            score_fields = [
                ("content_quality", ["depth_score", "comprehensiveness_score", "data_support_score"]),
                ("structure_analysis", ["organization_score", "coherence_score", "emphasis_score"]),
                ("credibility", ["terminology_score", "citation_score", "insight_score"]),
            ]

            for section, fields in score_fields:
                for field in fields:
                    score = result_dict[section].get(field, 0)
                    if not isinstance(score, (int, float)) or score < 0 or score > 10:
                        logger.warning("评分 %s.%s 不在有效范围内(0-10),使用默认值5.0", section, field)
                        result_dict[section][field] = 5.0

            # 验证综合评分
            overall_score = result_dict.get("overall_score", 5.0)
            if not isinstance(overall_score, (int, float)) or overall_score < 1 or overall_score > 10:
                logger.warning("综合评分不在有效范围内(1-10),使用默认值5.0")
                overall_score = 5.0
            result_dict["overall_score"] = float(overall_score)

            # 确保改进建议是列表
            if not isinstance(result_dict.get("improvement_suggestions"), list):
                result_dict["improvement_suggestions"] = []

            # 确保优点和待改进点是列表
            if not isinstance(result_dict.get("strengths"), list):
                result_dict["strengths"] = []
            if not isinstance(result_dict.get("weaknesses"), list):
                result_dict["weaknesses"] = []

            # 转换为Pydantic模型(验证数据格式)
            analysis_result = WhitepaperAnalysisResult(**result_dict)

            return analysis_result

        except Exception as e:
            logger.error("验证分析结果失败: %s", e, exc_info=True)
            msg = f"分析结果格式不正确: {e!s}"
            raise ValueError(msg) from e

