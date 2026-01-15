"""
分析模块API路由模块

提供白皮书分析相关接口:
- POST /api/analyze-whitepaper: 分析白皮书

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

from datetime import UTC
from typing import Any

from fastapi import APIRouter, Depends

from src.application.services.draft_service import DraftService
from src.application.services.whitepaper_analysis_service import (
    WhitepaperAnalysisService,
)
from src.interfaces.api.error_handlers import (
    create_error_response_from_exception,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    AnalyzeWhitepaperRequest,
    create_error_response,
    create_success_response,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.base_exceptions import ResourceNotFoundError
from src.shared.utils.logging import get_logger

from .core import get_llm_service

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(tags=["白皮书分析"])


@router.post(
    "/analyze-whitepaper",
    response_model=dict[str, Any],
    summary="分析白皮书",
    description="白皮书质量分析接口(前端适配接口)",
)
async def analyze_whitepaper(
    request: AnalyzeWhitepaperRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """
    白皮书质量分析接口(前端适配)

    支持两种方式提供内容:
    1. 通过draft_id获取草稿内容进行分析
    2. 直接提供content内容进行分析

    分析维度:
    - 内容质量评估(深度,全面性,数据支撑)
    - 结构分析(章节安排,逻辑连贯性)
    - 专业性与可信度评估
    - 改进建议生成
    - 综合评分(1-10分)

    Args:
        request: 分析请求
        llm_service: LLM服务

    Returns:
        统一响应格式:{ success: bool, data: AnalyzeWhitepaperResponse }
    """
    try:
        from datetime import datetime

        # 获取内容
        content = None
        if request.draft_id:
            # 从草稿获取内容
            try:
                draft_service = DraftService()
                draft = draft_service.get_draft(request.draft_id)
                # 使用DraftService的内部方法将草稿转换为Markdown格式
                content = draft_service._draft_to_markdown(draft)
                logger.info("从草稿获取内容: draft_id=%s, 长度=%d", request.draft_id, len(content))
            except ResourceNotFoundError:
                return create_error_response(
                    f"草稿不存在: {request.draft_id}",
                    "请检查草稿ID是否正确"
                )
        elif request.content:
            # 直接使用提供的内容
            content = request.content
            logger.info("使用提供的白皮书内容,长度=%d", len(content))
        else:
            return create_error_response(
                "缺少白皮书内容",
                "请提供draft_id或content参数"
            )

        # 创建分析服务
        analysis_service = WhitepaperAnalysisService(llm_service=llm_service)

        # 执行分析
        try:
            analysis_result = analysis_service.analyze(content)
        except ValueError as e:
            return create_error_response(
                "分析参数错误",
                str(e)
            )
        except Exception as e:
            logger.error("分析执行失败: %s", e, exc_info=True)
            return create_error_response(
                "分析执行失败",
                str(e)
            )

        # 转换为响应格式
        response_data = {
            "content_quality": {
                "depth_score": analysis_result.content_quality.get("depth_score", 5.0),
                "comprehensiveness_score": analysis_result.content_quality.get("comprehensiveness_score", 5.0),
                "data_support_score": analysis_result.content_quality.get("data_support_score", 5.0),
                "depth_comment": analysis_result.content_quality.get("depth_comment", ""),
                "comprehensiveness_comment": analysis_result.content_quality.get("comprehensiveness_comment", ""),
                "data_support_comment": analysis_result.content_quality.get("data_support_comment", ""),
            },
            "structure_analysis": {
                "organization_score": analysis_result.structure_analysis.get("organization_score", 5.0),
                "coherence_score": analysis_result.structure_analysis.get("coherence_score", 5.0),
                "emphasis_score": analysis_result.structure_analysis.get("emphasis_score", 5.0),
                "organization_comment": analysis_result.structure_analysis.get("organization_comment", ""),
                "coherence_comment": analysis_result.structure_analysis.get("coherence_comment", ""),
                "emphasis_comment": analysis_result.structure_analysis.get("emphasis_comment", ""),
            },
            "credibility": {
                "terminology_score": analysis_result.credibility.get("terminology_score", 5.0),
                "citation_score": analysis_result.credibility.get("citation_score", 5.0),
                "insight_score": analysis_result.credibility.get("insight_score", 5.0),
                "terminology_comment": analysis_result.credibility.get("terminology_comment", ""),
                "citation_comment": analysis_result.credibility.get("citation_comment", ""),
                "insight_comment": analysis_result.credibility.get("insight_comment", ""),
            },
            "improvement_suggestions": analysis_result.improvement_suggestions or [],
            "overall_score": analysis_result.overall_score,
            "summary": analysis_result.summary,
            "strengths": analysis_result.strengths or [],
            "weaknesses": analysis_result.weaknesses or [],
            "timestamp": datetime.now(UTC).isoformat(),
        }

        logger.info("白皮书分析完成,综合评分: %.2f", analysis_result.overall_score)

        return create_success_response(data=response_data)

    except Exception as e:
        logger.exception("分析白皮书异常: %s", e)
        return create_error_response_from_exception(e)


__all__ = ["router"]
