"""
草稿生成API路由

实现草稿的生成,查询,更新,删除,质量评估等API接口.
使用T232-T234草稿生成Agent, T238A质量评估服务, 调用draft_mvp_schemas定义的Schema.

生成命令: /speckit.implement T239
生成时间: 2025-12-25
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from src.application.agents.draft_generator_mvp import (
    create_draft_generator_agent,
)
from src.application.services.draft_quality_assessor import (
    create_draft_quality_assessor,
)
from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.domain.agent.draft import Draft, DraftStatus
from src.infrastructure.indexing.hybrid_retriever import HybridRetriever
from src.interfaces.api.schemas.draft_mvp_schemas import (
    DeleteResponse,
    DraftDetailResponse,
    DraftGenerateRequest,
    DraftGenerateResponse,
    DraftListResponse,
    DraftQualityAssessmentRequest,
    DraftQualityAssessmentResponse,
    DraftResponse,
    DraftSectionResponse,
    DraftUpdateRequest,
    DraftUpdateResponse,
    ErrorResponse,
    ImprovementSuggestionResponse,
    QualityScoreResponse,
    SortBy,
    SortOrder,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.base_exceptions import ResourceNotFoundError
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/drafts", tags=["草稿管理"])

# 全局服务实例
_outline_optimization_service: OutlineOptimizationService | None = None
_industry_selection_service: IndustrySelectionService | None = None
_llm_service: LLMService | None = None
_hybrid_retriever: HybridRetriever | None = None

# 草稿服务(使用数据库存储)
_draft_service: Any | None = None


def get_outline_optimization_service() -> OutlineOptimizationService:
    """获取大纲优化服务实例

    Returns:
        OutlineOptimizationService: 大纲优化服务实例
    """
    global _outline_optimization_service
    if _outline_optimization_service is None:
        _outline_optimization_service = OutlineOptimizationService()
    return _outline_optimization_service


def get_industry_selection_service() -> IndustrySelectionService:
    """获取行业选择服务实例

    Returns:
        IndustrySelectionService: 行业选择服务实例
    """
    global _industry_selection_service
    if _industry_selection_service is None:
        _industry_selection_service = IndustrySelectionService()
    return _industry_selection_service


def get_llm_service() -> LLMService:
    """获取LLM服务实例

    Returns:
        LLMService: LLM服务实例
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def get_hybrid_retriever() -> HybridRetriever | None:
    """获取混合检索引擎实例(可选)

    Returns:
        HybridRetriever: 混合检索引擎实例,如果未配置则返回None
    """
    global _hybrid_retriever
    # TODO: 从配置或服务中获取HybridRetriever实例
    # 当前版本暂时返回None,后续版本将实现
    return _hybrid_retriever


def get_draft_service():
    """获取草稿服务实例

    Returns:
        DraftService: 草稿服务实例
    """
    global _draft_service
    if _draft_service is None:
        from src.application.services.draft_service import DraftService
        _draft_service = DraftService()
    return _draft_service


def _handle_route_exception(e: Exception, operation: str) -> HTTPException:
    """处理路由异常,根据异常类型返回适当的HTTP状态码

    Args:
        e: 异常对象
        operation: 操作名称,用于日志

    Returns:
        HTTPException: HTTP异常对象
    """
    if isinstance(e, ResourceNotFoundError):
        logger.warning("%s: %s", operation, e)
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    else:
        logger.exception("%s异常: %s", operation, e)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{operation}失败: {e}",
        )


def _convert_draft_to_response(draft: Draft) -> DraftResponse:
    """将草稿对象转换为响应格式

    Args:
        draft: 草稿对象

    Returns:
        DraftResponse: 草稿响应对象
    """
    sections = [
        DraftSectionResponse(
            id=section.id,
            parent_id=section.parent_id,
            section_type=section.section_type,
            level=section.level,
            title=section.title,
            content=section.content,
            order=section.order,
            source_references=section.source_references,
            metadata=section.metadata,
        )
        for section in draft.sections
    ]

    return DraftResponse(
        id=draft.id,
        title=draft.title,
        description=draft.description,
        outline_id=draft.outline_id,
        industry_id=draft.industry_id,
        database_ids=draft.database_ids,
        status=draft.status,
        sections=sections,
        current_version=draft.current_version,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        metadata=draft.metadata,
    )


@router.post(
    "/generate",
    response_model=DraftGenerateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "大纲或行业不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="生成草稿",
    description="基于优化大纲生成草稿内容,使用DraftGeneratorAgent进行生成",
)
async def generate_draft_endpoint(
    request: DraftGenerateRequest,
    outline_service: OutlineOptimizationService = Depends(
        get_outline_optimization_service
    ),
    industry_service: IndustrySelectionService = Depends(
        get_industry_selection_service
    ),
    llm_service: LLMService = Depends(get_llm_service),
) -> DraftGenerateResponse:
    """
    生成草稿接口

    Args:
        request: 生成草稿请求
        outline_service: 大纲优化服务
        industry_service: 行业选择服务
        llm_service: LLM服务

    Returns:
        DraftGenerateResponse: 生成结果

    Raises:
        HTTPException: 生成失败时抛出
    """
    try:
        # 1. 验证优化大纲是否存在
        optimized_outline = outline_service.get_optimized_outline_by_id(
            str(request.optimized_outline_id)
        )
        if not optimized_outline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"优化大纲不存在: {request.optimized_outline_id}",
            )

        # 2. 验证行业是否存在
        industry = industry_service.get_industry_by_id(str(request.industry_id))
        if not industry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"行业不存在: {request.industry_id}",
            )

        # 3. 获取行业名称
        industry_name = industry.name

        # 4. 获取数据库名称列表
        database_names = []
        if request.database_ids:
            for db_id in request.database_ids:
                database = industry_service.get_database_by_id(str(db_id))
                if database:
                    database_names.append(database.name)

        # 5. 创建草稿生成Agent
        hybrid_retriever = get_hybrid_retriever()
        agent = create_draft_generator_agent(
            llm_service=llm_service,
            report_type=request.report_type,
            language=request.language,
            style=request.style,
            hybrid_retriever=hybrid_retriever,
        )

        # 6. 生成草稿
        draft = agent.generate_draft(
            optimized_outline=optimized_outline,
            industry_name=industry_name,
            database_names=database_names,
            report_type=request.report_type,
        )

        # 7. 保存草稿到数据库
        # 使用固定的测试用户ID(后续版本将从认证中获取)
        test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        draft_service = get_draft_service()
        draft_service.save_draft(draft, test_user_id)

        # 8. 转换为响应格式
        draft_response = _convert_draft_to_response(draft)

        logger.info("草稿生成成功: %s (ID: %s)", draft.title, draft.id)

        return DraftGenerateResponse(
            draft=draft_response,
            draft_id=str(draft.id),
            title=draft.title,
            status=draft.status.value if hasattr(draft.status, "value") else str(draft.status),
            total_sections=len(draft.sections),
            created_at=draft.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("生成草稿异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成草稿失败: {e}",
        )


@router.get(
    "/{draft_id}",
    response_model=DraftDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="获取草稿详情",
    description="根据草稿ID获取草稿详细信息",
)
async def get_draft_detail_endpoint(
    draft_id: str,
) -> DraftDetailResponse:
    """
    获取草稿详情接口

    Args:
        draft_id: 草稿ID

    Returns:
        DraftDetailResponse: 草稿详情

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        # 从数据库获取草稿
        draft_service = get_draft_service()
        draft = draft_service.get_draft(draft_id)

        # 转换为响应格式
        draft_response = _convert_draft_to_response(draft)

        # 获取统计信息
        statistics = draft.get_statistics()

        return DraftDetailResponse(
            draft=draft_response,
            statistics=statistics,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取草稿详情异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取草稿详情失败: {e}",
        )


@router.get(
    "",
    response_model=DraftListResponse,
    responses={
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="获取草稿列表",
    description="获取草稿列表,支持筛选和分页",
)
async def list_drafts_endpoint(
    outline_id: str | None = Query(None, description="大纲ID(筛选)"),
    industry_id: str | None = Query(None, description="行业ID(筛选)"),
    status_filter: str | None = Query(None, alias="status", description="状态(筛选)"),
    page: int = Query(1, ge=1, description="页码(从1开始)"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    sort_by: SortBy = Query(SortBy.CREATED_AT, description="排序字段"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="排序方向"),
) -> DraftListResponse:
    """
    获取草稿列表接口

    Args:
        outline_id: 大纲ID(筛选)
        industry_id: 行业ID(筛选)
        status_filter: 状态(筛选)
        page: 页码
        page_size: 每页数量
        sort_by: 排序字段
        sort_order: 排序方向

    Returns:
        DraftListResponse: 草稿列表
    """
    try:
        # 从数据库获取草稿列表
        draft_service = get_draft_service()

        # 构建过滤条件
        outline_uuid = uuid.UUID(outline_id) if outline_id else None
        industry_uuid = uuid.UUID(industry_id) if industry_id else None
        status_enum = DraftStatus(status_filter) if status_filter else None

        filtered_drafts = draft_service.list_drafts(
            outline_id=outline_uuid,
            industry_id=industry_uuid,
            status=status_enum,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        # 排序
        reverse = sort_order == SortOrder.DESC
        if sort_by == SortBy.TITLE:
            filtered_drafts.sort(key=lambda d: d.title, reverse=reverse)
        elif sort_by == SortBy.CREATED_AT:
            filtered_drafts.sort(key=lambda d: d.created_at, reverse=reverse)
        elif sort_by == SortBy.UPDATED_AT:
            filtered_drafts.sort(key=lambda d: d.updated_at, reverse=reverse)
        elif sort_by == SortBy.STATUS:
            filtered_drafts.sort(
                key=lambda d: d.status.value if hasattr(d.status, "value") else str(d.status),
                reverse=reverse,
            )

        # 分页
        total = len(filtered_drafts)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_drafts = filtered_drafts[start:end]

        # 转换为响应格式
        draft_responses = [
            _convert_draft_to_response(draft) for draft in paginated_drafts
        ]

        total_pages = (total + page_size - 1) // page_size

        return DraftListResponse(
            drafts=draft_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.exception("获取草稿列表异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取草稿列表失败: {e}",
        )


@router.put(
    "/{draft_id}",
    response_model=DraftUpdateResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="更新草稿",
    description="更新草稿的基本信息(标题,描述,状态等)",
)
async def update_draft_endpoint(
    draft_id: str,
    request: DraftUpdateRequest,
) -> DraftUpdateResponse:
    """
    更新草稿接口

    Args:
        draft_id: 草稿ID
        request: 更新请求

    Returns:
        DraftUpdateResponse: 更新结果

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        # 从数据库获取草稿
        draft_service = get_draft_service()
        draft = draft_service.get_draft(draft_id)

        # 更新字段
        if request.title is not None:
            draft.title = request.title
        if request.description is not None:
            draft.description = request.description
        if request.status is not None:
            draft.update_status(request.status)

        # 保存更新到数据库
        # 使用固定的测试用户ID(后续版本将从认证中获取)
        test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        draft_service = get_draft_service()
        draft_service.save_draft(draft, test_user_id)

        # 转换为响应格式
        draft_response = _convert_draft_to_response(draft)

        logger.info("草稿更新成功: %s (ID: %s)", draft.title, draft.id)

        return DraftUpdateResponse(
            draft=draft_response,
            updated_at=draft.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新草稿异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新草稿失败: {e}",
        )


@router.delete(
    "/{draft_id}",
    response_model=DeleteResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="删除草稿",
    description="根据草稿ID删除草稿",
)
async def delete_draft_endpoint(
    draft_id: str,
) -> DeleteResponse:
    """
    删除草稿接口

    Args:
        draft_id: 草稿ID

    Returns:
        DeleteResponse: 删除结果

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        # 从数据库获取草稿
        draft_service = get_draft_service()
        draft = draft_service.get_draft(draft_id)

        # 删除草稿
        draft_service = get_draft_service()
        draft_service.delete_draft(draft_id)

        logger.info("草稿删除成功: %s (ID: %s)", draft.title, draft_id)

        return DeleteResponse(
            success=True,
            message="草稿删除成功",
            draft_id=draft_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除草稿异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除草稿失败: {e}",
        )


@router.post(
    "/{draft_id}/assess-quality",
    response_model=DraftQualityAssessmentResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="评估草稿质量",
    description="评估草稿的结构完整度,数据引用完整性,逻辑一致性等",
)
async def assess_draft_quality_endpoint(
    draft_id: str,
    request: DraftQualityAssessmentRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> DraftQualityAssessmentResponse:
    """
    评估草稿质量接口

    Args:
        draft_id: 草稿ID
        request: 评估请求
        llm_service: LLM服务

    Returns:
        DraftQualityAssessmentResponse: 评估结果

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        # 从数据库获取草稿
        draft_service = get_draft_service()
        draft = draft_service.get_draft(draft_id)

        # 创建质量评估服务
        assessor = create_draft_quality_assessor(llm_service=llm_service)

        # 评估草稿质量
        # 注意:当前版本暂时不传递source_references,后续版本将实现
        result = assessor.assess_quality(
            draft=draft,
            source_references=None,
            use_llm=request.use_llm,
        )

        # 转换为响应格式
        dimension_scores = [
            QualityScoreResponse(
                dimension=score.dimension,
                score=score.score,
                description=score.description,
            )
            for score in result.dimension_scores
        ]

        improvement_suggestions = [
            ImprovementSuggestionResponse(
                dimension=suggestion.dimension,
                priority=suggestion.priority,
                suggestion=suggestion.suggestion,
                affected_sections=suggestion.affected_sections,
            )
            for suggestion in result.improvement_suggestions
        ]

        logger.info("草稿质量评估完成: %s (ID: %s, 评分: %.2f)", draft.title, draft_id, result.overall_score)

        return DraftQualityAssessmentResponse(
            overall_score=result.overall_score,
            dimension_scores=dimension_scores,
            improvement_suggestions=improvement_suggestions,
            summary=result.summary,
            details=result.details,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("评估草稿质量异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"评估草稿质量失败: {e}",
        )

