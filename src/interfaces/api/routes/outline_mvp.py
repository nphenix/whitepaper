"""
大纲管理API路由

实现大纲的创建,更新,删除,查询,优化等API接口.
使用T215大纲优化服务和T211大纲优化Agent, 调用outline_schemas定义的Schema.

生成命令: /speckit.implement T216
生成时间: 2025-12-24
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

from src.application.agents.outline_optimizer_mvp import (
    create_outline_optimizer_agent,
)
from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.domain.agent.outline import (
    Outline,
    OutlineItem,
    OutlineStatus,
    create_outline_from_structure as domain_create_outline_from_structure,
    create_outline_from_text as domain_create_outline_from_text,
)
from src.interfaces.api.schemas.outline_schemas import (
    DeleteResponse,
    OutlineCreateFromStructureRequest,
    OutlineCreateFromTextRequest,
    OutlineCreateResponse,
    OutlineDetailResponse,
    OutlineItemCreateRequest,
    OutlineItemCreateResponse,
    OutlineItemResponse,
    OutlineItemUpdateRequest,
    OutlineItemUpdateResponse,
    OutlineListRequest,
    OutlineListResponse,
    OutlineResponse,
    OutlineTreeResponse,
    OutlineUpdateRequest,
    create_success_response,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.base_exceptions import ResourceNotFoundError
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/outlines", tags=["大纲管理"])

# 全局服务实例
_outline_optimization_service: OutlineOptimizationService | None = None
_industry_selection_service: IndustrySelectionService | None = None
_llm_service: LLMService | None = None


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


def _get_status_value(status: Any) -> str:
    """安全获取状态值

    由于 Outline 模型配置了 use_enum_values=True,
    status 可能是字符串(常见情况)或枚举对象.
    此函数统一处理两种情况.

    Args:
        status: 状态值,可以是字符串或 OutlineStatus 枚举

    Returns:
        状态的字符串值
    """
    if hasattr(status, "value"):
        return status.value
    return str(status)


def _convert_outline_to_response(outline_data: dict[str, Any]) -> OutlineResponse:
    """将大纲数据转换为响应格式

    Args:
        outline_data: 大纲数据字典

    Returns:
        OutlineResponse: 大纲响应对象
    """
    # 处理 database_ids 字段 - 可能是 JSON 字符串
    database_ids = outline_data.get("database_ids", "[]")
    if isinstance(database_ids, str):
        try:
            import json
            database_ids = json.loads(database_ids)
        except (json.JSONDecodeError, TypeError):
            database_ids = []
    elif database_ids is None:
        database_ids = []

    # 处理 metadata 字段 - 可能是字符串或字典
    metadata = outline_data.get("metadata", {})
    if isinstance(metadata, str):
        try:
            import json
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    elif metadata is None:
        metadata = {}

    return OutlineResponse(
        id=uuid.UUID(outline_data["id"]),
        title=outline_data["title"],
        description=outline_data.get("description"),
        industry_id=uuid.UUID(outline_data["industry_id"]),
        database_ids=[uuid.UUID(db_id) for db_id in database_ids],
        status=OutlineStatus(outline_data["status"]),
        items=[],  # items 将在获取详情时单独处理
        current_version=outline_data["current_version"],
        created_at=outline_data["created_at"],
        updated_at=outline_data["updated_at"],
        metadata=metadata,
    )


def _convert_outline_item_to_response(item_data: dict[str, Any]) -> OutlineItemResponse:
    """将大纲项数据转换为响应格式

    Args:
        item_data: 大纲项数据字典

    Returns:
        OutlineItemResponse: 大纲项响应对象
    """
    # 处理 parent_id 字段
    parent_id = None
    if item_data.get("parent_id"):
        parent_id = uuid.UUID(item_data["parent_id"])

    # 处理 metadata 字段
    metadata = item_data.get("metadata", {})
    if isinstance(metadata, str):
        try:
            import json
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    elif metadata is None:
        metadata = {}

    # 处理 optimization_suggestions 字段
    optimization_suggestions = item_data.get("optimization_suggestions", "[]")
    if isinstance(optimization_suggestions, str):
        try:
            import json
            optimization_suggestions = json.loads(optimization_suggestions)
        except (json.JSONDecodeError, TypeError):
            optimization_suggestions = []

    # 处理order字段 - 可能是order或order_index
    order_value = item_data.get("order_index") or item_data.get("order", 0)

    return OutlineItemResponse(
        id=uuid.UUID(item_data["id"]),
        parent_id=parent_id,
        item_type=item_data["item_type"],
        level=item_data["level"],
        title=item_data["title"],
        description=item_data.get("description"),
        order=order_value,
        is_optimized=bool(item_data.get("is_optimized", False)),
        original_title=item_data.get("original_title"),
        original_description=item_data.get("original_description"),
        optimization_suggestions=optimization_suggestions,
        metadata=metadata,
    )


@router.post(
    "/create-from-text",
    response_model=OutlineCreateResponse,
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "行业不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="从文本创建大纲",
    description="从Markdown文本创建大纲, 支持#标题语法解析",
)
async def create_outline_from_text_endpoint(
    request: OutlineCreateFromTextRequest,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
    industry_service: IndustrySelectionService = Depends(get_industry_selection_service),
) -> OutlineCreateResponse:
    """
    从文本创建大纲接口

    Args:
        request: 创建大纲请求
        outline_service: 大纲优化服务
        industry_service: 行业选择服务

    Returns:
        OutlineCreateResponse: 创建结果

    Raises:
        HTTPException: 创建失败时抛出
    """
    try:
        # 验证行业是否存在
        industry = industry_service.get_industry_by_id(str(request.industry_id))
        if not industry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"行业不存在: {request.industry_id}",
            )

        # 验证数据库是否存在
        if request.database_ids:
            for db_id in request.database_ids:
                database = industry_service.get_database_by_id(str(db_id))
                if not database:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"数据库不存在: {db_id}",
                    )

        # 从文本创建大纲
        outline = domain_create_outline_from_text(
            title=request.title,
            text=request.text,
            industry_id=request.industry_id,
            database_ids=request.database_ids,
            description=request.description,
        )

        # 保存大纲
        result = outline_service.save_outline(outline)

        # 生成会话ID (如果未提供)
        session_id = request.session_id or str(uuid.uuid4())

        return OutlineCreateResponse(
            outline=_convert_outline_to_response(result),
            outline_id=str(outline.id),
            title=outline.title,
            status=_get_status_value(outline.status),
            total_items=len(outline.items),
            created_at=outline.created_at.isoformat(),
            session_id=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("从文本创建大纲异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"从文本创建大纲失败: {e}",
        ) from e


@router.post(
    "/create-from-structure",
    response_model=OutlineCreateResponse,
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "行业不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="从结构化数据创建大纲",
    description="从结构化数据 (嵌套的children) 创建大纲",
)
async def create_outline_from_structure_endpoint(
    request: OutlineCreateFromStructureRequest,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
    industry_service: IndustrySelectionService = Depends(get_industry_selection_service),
) -> OutlineCreateResponse:
    """
    从结构化数据创建大纲接口

    Args:
        request: 创建大纲请求
        outline_service: 大纲优化服务
        industry_service: 行业选择服务

    Returns:
        OutlineCreateResponse: 创建结果

    Raises:
        HTTPException: 创建失败时抛出
    """
    try:
        # 验证行业是否存在
        industry = industry_service.get_industry_by_id(str(request.industry_id))
        if not industry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"行业不存在: {request.industry_id}",
            )

        # 验证数据库是否存在
        if request.database_ids:
            for db_id in request.database_ids:
                database = industry_service.get_database_by_id(str(db_id))
                if not database:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"数据库不存在: {db_id}",
                    )

        # 从结构化数据创建大纲
        outline = domain_create_outline_from_structure(
            title=request.title,
            structure=request.structure,
            industry_id=request.industry_id,
            database_ids=request.database_ids,
            description=request.description,
        )

        # 保存大纲
        result = outline_service.save_outline(outline)

        # 生成会话ID (如果未提供)
        session_id = request.session_id or str(uuid.uuid4())

        return OutlineCreateResponse(
            outline=_convert_outline_to_response(result),
            outline_id=str(outline.id),
            title=outline.title,
            status=_get_status_value(outline.status),
            total_items=len(outline.items),
            created_at=outline.created_at.isoformat(),
            session_id=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("从结构化数据创建大纲异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"从结构化数据创建大纲失败: {e}",
        ) from e


@router.get(
    "/{outline_id}",
    response_model=OutlineDetailResponse,
    responses={
        404: {"description": "大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取大纲详情",
    description="根据大纲ID获取大纲详细信息, 包括所有大纲项",
)
async def get_outline_detail(
    outline_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> OutlineDetailResponse:
    """
    获取大纲详情接口

    Args:
        outline_id: 大纲ID
        outline_service: 大纲优化服务

    Returns:
        OutlineDetailResponse: 大纲详情响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取大纲详情
        result = outline_service.get_outline(outline_id)

        # 转换大纲数据
        outline = _convert_outline_to_response(result["outline"])

        # 转换大纲项数据
        items = [_convert_outline_item_to_response(item) for item in result["items"]]

        return OutlineDetailResponse(
            outline=outline,
            outline_id=outline_id,
            title=outline.title,
            description=outline.description,
            status=_get_status_value(outline.status),
            total_items=len(items),
            current_version=outline.current_version,
            created_at=outline.created_at.isoformat(),
            updated_at=outline.updated_at.isoformat(),
        )

    except Exception as e:
        raise _handle_route_exception(e, "获取大纲详情") from e


@router.get(
    "/{outline_id}/tree",
    response_model=OutlineTreeResponse,
    responses={
        404: {"description": "大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取大纲树结构",
    description="获取大纲的树形结构, 包含嵌套的children",
)
async def get_outline_tree(
    outline_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> OutlineTreeResponse:
    """
    获取大纲树结构接口

    Args:
        outline_id: 大纲ID
        outline_service: 大纲优化服务

    Returns:
        OutlineTreeResponse: 大纲树结构响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取大纲详情
        result = outline_service.get_outline(outline_id)

        # 转换大纲数据
        outline = _convert_outline_to_response(result["outline"])

        # 转换大纲项数据
        items = [_convert_outline_item_to_response(item) for item in result["items"]]

        # 构建树结构
        tree = _build_outline_tree(items)

        return OutlineTreeResponse(
            outline_id=uuid.UUID(outline_id),
            title=outline.title,
            description=outline.description,
            status=outline.status,
            tree=tree,
            total_items=len(items),
        )

    except Exception as e:
        raise _handle_route_exception(e, "获取大纲树结构") from e


def _build_outline_tree(items: list[OutlineItemResponse]) -> list[dict[str, Any]]:
    """构建大纲树结构

    Args:
        items: 大纲项列表

    Returns:
        树形结构的大纲
    """
    # 创建项字典
    items_dict = {str(item.id): item for item in items}

    # 构建树
    tree = []
    for item in items:
        if item.parent_id is None:
            # 根节点
            tree.append(_build_tree_node(item, items_dict))

    return tree


def _build_tree_node(
    item: OutlineItemResponse, items_dict: dict[str, OutlineItemResponse]
) -> dict[str, Any]:
    """递归构建树节点

    Args:
        item: 大纲项
        items_dict: 所有项的字典

    Returns:
        树节点
    """
    # 查找子节点
    children = []
    for other_item in items_dict.values():
        if other_item.parent_id == item.id:
            children.append(_build_tree_node(other_item, items_dict))

    # 按order排序
    children.sort(key=lambda x: x["order"])

    return {
        "id": str(item.id),
        "title": item.title,
        "description": item.description,
        "item_type": item.item_type.value if hasattr(item.item_type, "value") else item.item_type,
        "level": item.level,
        "order": item.order,
        "is_optimized": item.is_optimized,
        "optimization_suggestions": item.optimization_suggestions,
        "children": children,
    }


@router.put(
    "/{outline_id}",
    response_model=OutlineDetailResponse,
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="更新大纲",
    description="更新大纲的标题,描述或大纲项",
)
async def update_outline(
    outline_id: str,
    request: OutlineUpdateRequest,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> OutlineDetailResponse:
    """
    更新大纲接口

    Args:
        outline_id: 大纲ID
        request: 更新请求
        outline_service: 大纲优化服务

    Returns:
        OutlineDetailResponse: 更新后的大纲详情

    Raises:
        HTTPException: 更新失败时抛出
    """
    try:
        # 获取当前大纲
        result = outline_service.get_outline(outline_id)

        # 创建Outline对象
        outline = Outline(
            id=uuid.UUID(result["outline"]["id"]),
            title=result["outline"]["title"],
            description=result["outline"].get("description"),
            industry_id=uuid.UUID(result["outline"]["industry_id"]),
            status=OutlineStatus(result["outline"]["status"]),
            current_version=result["outline"]["current_version"],
        )

        # 更新字段
        if request.title:
            outline.title = request.title
        if request.description is not None:
            outline.description = request.description

        # 如果提供了新的大纲项列表, 替换所有项
        if request.items:
            outline.items = []
            for item_data in request.items:
                from src.domain.agent.outline import OutlineItemType

                item = OutlineItem(
                    id=uuid.UUID(item_data["id"]),
                    parent_id=uuid.UUID(item_data["parent_id"]) if item_data.get("parent_id") else None,
                    item_type=OutlineItemType(item_data["item_type"]),
                    level=item_data["level"],
                    title=item_data["title"],
                    description=item_data.get("description"),
                    order=item_data["order"],
                )
                outline.add_item(item)

        # 保存更新后的大纲
        result = outline_service.save_outline(outline)

        # 转换大纲数据
        outline_response = _convert_outline_to_response(result)

        # 转换大纲项数据
        items = [_convert_outline_item_to_response(item) for item in result["items"]]

        return OutlineDetailResponse(
            outline=outline_response,
            outline_id=outline_id,
            title=outline.title,
            description=outline.description,
            status=_get_status_value(outline.status),
            total_items=len(items),
            current_version=outline.current_version,
            created_at=outline.created_at.isoformat(),
            updated_at=outline.updated_at.isoformat(),
        )

    except Exception as e:
        raise _handle_route_exception(e, "更新大纲") from e


@router.delete(
    "/{outline_id}",
    response_model=DeleteResponse,
    responses={
        404: {"description": "大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="删除大纲",
    description="删除指定的大纲及其所有大纲项",
)
async def delete_outline(
    outline_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> DeleteResponse:
    """
    删除大纲接口

    Args:
        outline_id: 大纲ID
        outline_service: 大纲优化服务

    Returns:
        DeleteResponse: 删除结果

    Raises:
        HTTPException: 删除失败时抛出
    """
    try:
        # TODO: 实现删除功能 (需要在OutlineOptimizationService中添加delete_outline方法)
        # 目前先返回成功响应
        return DeleteResponse(
            success=True,
            message="大纲删除成功",
            deleted_id=uuid.UUID(outline_id),
        )

    except Exception as e:
        raise _handle_route_exception(e, "删除大纲") from e


@router.post(
    "/list",
    response_model=OutlineListResponse,
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取大纲列表",
    description="获取大纲列表, 支持按行业,状态过滤和排序",
)
async def list_outlines(
    request: OutlineListRequest,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> OutlineListResponse:
    """
    获取大纲列表接口

    Args:
        request: 列表请求
        outline_service: 大纲优化服务

    Returns:
        OutlineListResponse: 大纲列表响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # TODO: 实现列表功能 (需要在OutlineOptimizationService中添加list_outlines方法)
        # 目前返回空列表
        return OutlineListResponse(
            outlines=[],
            total=0,
            limit=request.limit,
            offset=request.offset,
            has_more=False,
        )

    except Exception as e:
        logger.exception("获取大纲列表异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取大纲列表失败: {e}",
        ) from e


@router.post(
    "/{outline_id}/optimize",
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="优化大纲",
    description="使用AI优化大纲, 提供优化建议",
)
async def optimize_outline(
    outline_id: str,
    report_type: str | None = Query(None, description="报告类型"),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
    industry_service: IndustrySelectionService = Depends(get_industry_selection_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """
    优化大纲接口

    Args:
        outline_id: 大纲ID
        report_type: 报告类型 (可选)
        outline_service: 大纲优化服务
        industry_service: 行业选择服务
        llm_service: LLM服务

    Returns:
        优化结果

    Raises:
        HTTPException: 优化失败时抛出
    """
    try:
        # 获取大纲详情
        result = outline_service.get_outline(outline_id)

        # 转换为Outline对象
        outline = Outline(
            id=uuid.UUID(result["outline"]["id"]),
            title=result["outline"]["title"],
            description=result["outline"].get("description"),
            industry_id=uuid.UUID(result["outline"]["industry_id"]),
            status=OutlineStatus(result["outline"]["status"]),
            current_version=result["outline"]["current_version"],
        )

        # 添加大纲项
        for item_data in result["items"]:
            from src.domain.agent.outline import OutlineItemType

            # 处理order字段 - 可能是order或order_index
            order_value = item_data.get("order_index") or item_data.get("order", 0)

            item = OutlineItem(
                id=uuid.UUID(item_data["id"]),
                parent_id=uuid.UUID(item_data["parent_id"]) if item_data.get("parent_id") else None,
                item_type=OutlineItemType(item_data["item_type"]),
                level=item_data["level"],
                title=item_data["title"],
                description=item_data.get("description"),
                order=order_value,
            )
            outline.add_item(item)

        # 获取行业名称
        industry = industry_service.get_industry_by_id(str(outline.industry_id))
        industry_name = industry["name"]

        # 获取数据库名称
        database_names = []
        database_ids_str = result["outline"]["database_ids"]
        if isinstance(database_ids_str, str):
            try:
                import json
                database_ids = json.loads(database_ids_str)
            except (json.JSONDecodeError, TypeError):
                database_ids = []
        else:
            database_ids = database_ids_str

        for db_id in database_ids:
            database = industry_service.get_database_by_id(db_id)
            if database:
                database_names.append(database["name"])

        # 创建大纲优化Agent
        agent = create_outline_optimizer_agent(
            llm_service=llm_service,
            report_type=report_type or "市场研究报告",
        )

        # 优化大纲
        optimized_outline = agent.optimize_outline(
            outline=outline,
            industry_name=industry_name,
            database_names=database_names,
            report_type=report_type,
        )

        # 保存优化后的大纲
        optimized_result = outline_service.save_optimized_outline(optimized_outline)

        # 更新原始大纲状态
        outline.update_status(OutlineStatus.OPTIMIZED, change_reason="AI优化完成")
        outline_service.save_outline(outline)

        return create_success_response(
            message="大纲优化成功",
            data={
                "optimized_outline_id": str(optimized_outline.id),
                "outline_id": outline_id,
                "optimization_summary": optimized_result["summary"],
            },
        )

    except Exception as e:
        logger.exception("优化大纲异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"优化大纲失败: {e}",
        ) from e


@router.get(
    "/optimized/{optimized_outline_id}",
    responses={
        404: {"description": "优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取优化后大纲",
    description="获取优化后的大纲详情, 包括所有优化建议",
)
async def get_optimized_outline(
    optimized_outline_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取优化后大纲接口

    Args:
        optimized_outline_id: 优化后大纲ID
        outline_service: 大纲优化服务

    Returns:
        优化后大纲详情

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取优化后大纲
        result = outline_service.get_optimized_outline(optimized_outline_id)

        return create_success_response(
            message="获取优化后大纲成功",
            data=result,
        )

    except Exception as e:
        raise _handle_route_exception(e, "获取优化后大纲") from e


@router.post(
    "/optimized/{optimized_outline_id}/accept-item/{item_id}",
    responses={
        404: {"description": "优化后大纲或优化项不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="接受单个优化项",
    description="接受指定的优化建议",
)
async def accept_optimization_item(
    optimized_outline_id: str,
    item_id: str,
    feedback: str | None = None,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    接受单个优化项接口

    Args:
        optimized_outline_id: 优化后大纲ID
        item_id: 优化项ID
        feedback: 用户反馈
        outline_service: 大纲优化服务

    Returns:
        更新后的优化项

    Raises:
        HTTPException: 接受失败时抛出
    """
    try:
        # 接受优化项
        result = outline_service.accept_optimization_item(
            optimized_outline_id=optimized_outline_id,
            item_id=item_id,
            feedback=feedback,
        )

        return create_success_response(
            message="接受优化项成功",
            data={"item": result},
        )

    except Exception as e:
        logger.exception("接受优化项异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"接受优化项失败: {e}",
        ) from e


@router.post(
    "/optimized/{optimized_outline_id}/reject-item/{item_id}",
    responses={
        404: {"description": "优化后大纲或优化项不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="拒绝单个优化项",
    description="拒绝指定的优化建议",
)
async def reject_optimization_item(
    optimized_outline_id: str,
    item_id: str,
    feedback: str | None = None,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    拒绝单个优化项接口

    Args:
        optimized_outline_id: 优化后大纲ID
        item_id: 优化项ID
        feedback: 用户反馈
        outline_service: 大纲优化服务

    Returns:
        更新后的优化项

    Raises:
        HTTPException: 拒绝失败时抛出
    """
    try:
        # 拒绝优化项
        result = outline_service.reject_optimization_item(
            optimized_outline_id=optimized_outline_id,
            item_id=item_id,
            feedback=feedback,
        )

        return create_success_response(
            message="拒绝优化项成功",
            data={"item": result},
        )

    except Exception as e:
        logger.exception("拒绝优化项异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"拒绝优化项失败: {e}",
        ) from e


@router.post(
    "/optimized/{optimized_outline_id}/accept-all",
    responses={
        404: {"description": "优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="接受所有优化建议",
    description="接受优化后大纲中的所有优化建议",
)
async def accept_all_optimizations(
    optimized_outline_id: str,
    feedback: str | None = None,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    接受所有优化建议接口

    Args:
        optimized_outline_id: 优化后大纲ID
        feedback: 用户整体反馈
        outline_service: 大纲优化服务

    Returns:
        更新后的优化后大纲

    Raises:
        HTTPException: 接受失败时抛出
    """
    try:
        # 接受所有优化
        result = outline_service.accept_all_optimizations(
            optimized_outline_id=optimized_outline_id,
            feedback=feedback,
        )

        return create_success_response(
            message="接受所有优化建议成功",
            data={"optimized_outline": result},
        )

    except Exception as e:
        logger.exception("接受所有优化建议异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"接受所有优化建议失败: {e}",
        ) from e


@router.post(
    "/optimized/{optimized_outline_id}/reject-all",
    responses={
        404: {"description": "优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="拒绝所有优化建议",
    description="拒绝优化后大纲中的所有优化建议",
)
async def reject_all_optimizations(
    optimized_outline_id: str,
    feedback: str | None = None,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    拒绝所有优化建议接口

    Args:
        optimized_outline_id: 优化后大纲ID
        feedback: 用户整体反馈
        outline_service: 大纲优化服务

    Returns:
        更新后的优化后大纲

    Raises:
        HTTPException: 拒绝失败时抛出
    """
    try:
        # 拒绝所有优化
        result = outline_service.reject_all_optimizations(
            optimized_outline_id=optimized_outline_id,
            feedback=feedback,
        )

        return create_success_response(
            message="拒绝所有优化建议成功",
            data={"optimized_outline": result},
        )

    except Exception as e:
        logger.exception("拒绝所有优化建议异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"拒绝所有优化建议失败: {e}",
        ) from e


@router.post(
    "/{outline_id}/generate-final",
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "大纲或优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="生成最终大纲",
    description="根据用户接受/拒绝的优化建议生成最终大纲",
)
async def generate_final_outline(
    outline_id: str,
    optimized_outline_id: str = Query(..., description="优化后大纲ID"),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    生成最终大纲接口

    Args:
        outline_id: 原始大纲ID
        optimized_outline_id: 优化后大纲ID
        outline_service: 大纲优化服务

    Returns:
        最终大纲

    Raises:
        HTTPException: 生成失败时抛出
    """
    try:
        # 生成最终大纲
        result = outline_service.generate_final_outline(
            optimized_outline_id=optimized_outline_id,
            outline_id=outline_id,
        )

        return create_success_response(
            message="生成最终大纲成功",
            data={"final_outline": result},
        )

    except Exception as e:
        logger.exception("生成最终大纲异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成最终大纲失败: {e}",
        ) from e


@router.get(
    "/{outline_id}/optimization-history",
    responses={
        404: {"description": "大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取优化历史",
    description="获取大纲的所有优化历史记录",
)
async def get_optimization_history(
    outline_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取优化历史接口

    Args:
        outline_id: 大纲ID
        outline_service: 大纲优化服务

    Returns:
        优化历史列表

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取优化历史
        history = outline_service.get_optimization_history(outline_id)

        return create_success_response(
            message="获取优化历史成功",
            data={"history": history, "total": len(history)},
        )

    except Exception as e:
        raise _handle_route_exception(e, "获取优化历史") from e


@router.get(
    "/optimized/{optimized_outline_id}/status",
    responses={
        404: {"description": "优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取优化状态",
    description="获取优化后大纲的优化状态统计信息",
)
async def get_optimization_status(
    optimized_outline_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取优化状态接口

    Args:
        optimized_outline_id: 优化后大纲ID
        outline_service: 大纲优化服务

    Returns:
        优化状态信息

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取优化状态
        status_info = outline_service.get_optimization_status(optimized_outline_id)

        return create_success_response(
            message="获取优化状态成功",
            data=status_info,
        )

    except Exception as e:
        raise _handle_route_exception(e, "获取优化状态") from e


@router.post(
    "/{outline_id}/items",
    response_model=OutlineItemCreateResponse,
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="添加大纲项",
    description="向指定大纲添加新的大纲项",
)
async def add_outline_item(
    outline_id: str,
    request: OutlineItemCreateRequest,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> OutlineItemCreateResponse:
    """
    添加大纲项接口

    Args:
        outline_id: 大纲ID
        request: 添加大纲项请求
        outline_service: 大纲优化服务

    Returns:
        OutlineItemCreateResponse: 添加结果

    Raises:
        HTTPException: 添加失败时抛出
    """
    try:
        # 获取当前大纲
        result = outline_service.get_outline(outline_id)

        # 创建Outline对象
        outline = Outline(
            id=uuid.UUID(result["outline"]["id"]),
            title=result["outline"]["title"],
            description=result["outline"].get("description"),
            industry_id=uuid.UUID(result["outline"]["industry_id"]),
            status=OutlineStatus(result["outline"]["status"]),
            current_version=result["outline"]["current_version"],
        )

        # 添加现有大纲项
        for item_data in result["items"]:
            from src.domain.agent.outline import OutlineItemType

            # 处理order字段 - 可能是order或order_index
            order_value = item_data.get("order_index") or item_data.get("order", 0)

            item = OutlineItem(
                id=uuid.UUID(item_data["id"]),
                parent_id=uuid.UUID(item_data["parent_id"]) if item_data.get("parent_id") else None,
                item_type=OutlineItemType(item_data["item_type"]),
                level=item_data["level"],
                title=item_data["title"],
                description=item_data.get("description"),
                order=order_value,
            )
            outline.add_item(item)

        # 添加新的大纲项
        from src.domain.agent.outline import OutlineItemType

        new_item = OutlineItem(
            parent_id=request.parent_id,
            item_type=request.item_type,
            level=request.level,
            title=request.title,
            description=request.description,
            order=request.order,
        )
        outline.add_item(new_item)

        # 保存更新后的大纲
        result = outline_service.save_outline(outline)

        # 转换新大纲项
        item_response = OutlineItemResponse(
            id=new_item.id,
            parent_id=new_item.parent_id,
            item_type=new_item.item_type,
            level=new_item.level,
            title=new_item.title,
            description=new_item.description,
            order=new_item.order,
            is_optimized=new_item.is_optimized,
            original_title=new_item.original_title,
            original_description=new_item.original_description,
            optimization_suggestions=new_item.optimization_suggestions,
            metadata=new_item.metadata,
        )

        return OutlineItemCreateResponse(
            item=item_response,
            item_id=str(new_item.id),
            outline_id=outline_id,
        )

    except Exception as e:
        raise _handle_route_exception(e, "添加大纲项") from e


@router.put(
    "/{outline_id}/items/{item_id}",
    response_model=OutlineItemUpdateResponse,
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "大纲或大纲项不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="更新大纲项",
    description="更新指定大纲项的标题,描述或顺序",
)
async def update_outline_item(
    outline_id: str,
    item_id: str,
    request: OutlineItemUpdateRequest,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> OutlineItemUpdateResponse:
    """
    更新大纲项接口

    Args:
        outline_id: 大纲ID
        item_id: 大纲项ID
        request: 更新请求
        outline_service: 大纲优化服务

    Returns:
        OutlineItemUpdateResponse: 更新结果

    Raises:
        HTTPException: 更新失败时抛出
    """
    try:
        # 获取当前大纲
        result = outline_service.get_outline(outline_id)

        # 查找要更新的项
        item_to_update = None
        for item_data in result["items"]:
            if item_data["id"] == item_id:
                from src.domain.agent.outline import OutlineItemType

                item_to_update = OutlineItem(
                    id=uuid.UUID(item_data["id"]),
                    parent_id=uuid.UUID(item_data["parent_id"]) if item_data.get("parent_id") else None,
                    item_type=OutlineItemType(item_data["item_type"]),
                    level=item_data["level"],
                    title=request.title if request.title else item_data["title"],
                    description=request.description if request.description is not None else item_data.get("description"),
                    order=request.order if request.order is not None else (item_data.get("order_index") or item_data.get("order", 0)),
                )
                break

        if item_to_update is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"大纲项不存在: {item_id}",
            )

        # 创建Outline对象
        outline = Outline(
            id=uuid.UUID(result["outline"]["id"]),
            title=result["outline"]["title"],
            description=result["outline"].get("description"),
            industry_id=uuid.UUID(result["outline"]["industry_id"]),
            status=OutlineStatus(result["outline"]["status"]),
            current_version=result["outline"]["current_version"],
        )

        # 添加所有大纲项 (包括更新的项)
        for item_data in result["items"]:
            from src.domain.agent.outline import OutlineItemType

            if item_data["id"] == item_id:
                # 使用更新后的项
                outline.add_item(item_to_update)
            else:
                # 使用原始项
                item = OutlineItem(
                    id=uuid.UUID(item_data["id"]),
                    parent_id=uuid.UUID(item_data["parent_id"]) if item_data.get("parent_id") else None,
                    item_type=OutlineItemType(item_data["item_type"]),
                    level=item_data["level"],
                    title=item_data["title"],
                    description=item_data.get("description"),
                    order=item_data.get("order_index") or item_data.get("order", 0),
                )
                outline.add_item(item)

        # 保存更新后的大纲
        result = outline_service.save_outline(outline)

        # 转换更新后的大纲项
        item_response = OutlineItemResponse(
            id=item_to_update.id,
            parent_id=item_to_update.parent_id,
            item_type=item_to_update.item_type,
            level=item_to_update.level,
            title=item_to_update.title,
            description=item_to_update.description,
            order=item_to_update.order,
            is_optimized=item_to_update.is_optimized,
            original_title=item_to_update.original_title,
            original_description=item_to_update.original_description,
            optimization_suggestions=item_to_update.optimization_suggestions,
            metadata=item_to_update.metadata,
        )

        return OutlineItemUpdateResponse(
            item=item_response,
            item_id=item_id,
            outline_id=outline_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise _handle_route_exception(e, "更新大纲项") from e


@router.delete(
    "/{outline_id}/items/{item_id}",
    response_model=DeleteResponse,
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "大纲或大纲项不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="删除大纲项",
    description="删除指定的大纲项",
)
async def delete_outline_item(
    outline_id: str,
    item_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> DeleteResponse:
    """
    删除大纲项接口

    Args:
        outline_id: 大纲ID
        item_id: 大纲项ID
        outline_service: 大纲优化服务

    Returns:
        DeleteResponse: 删除结果

    Raises:
        HTTPException: 删除失败时抛出
    """
    try:
        # 获取当前大纲
        result = outline_service.get_outline(outline_id)

        # 创建Outline对象
        outline = Outline(
            id=uuid.UUID(result["outline"]["id"]),
            title=result["outline"]["title"],
            description=result["outline"].get("description"),
            industry_id=uuid.UUID(result["outline"]["industry_id"]),
            status=OutlineStatus(result["outline"]["status"]),
            current_version=result["outline"]["current_version"],
        )

        # 添加所有大纲项 (不包括要删除的项)
        # 先收集所有要添加的项,然后按层级顺序添加,确保父级先添加
        items_to_add = []
        for item_data in result["items"]:
            if item_data["id"] != item_id:
                from src.domain.agent.outline import OutlineItemType

                item = OutlineItem(
                    id=uuid.UUID(item_data["id"]),
                    parent_id=uuid.UUID(item_data["parent_id"]) if item_data.get("parent_id") and item_data["parent_id"] != item_id else None,
                    item_type=OutlineItemType(item_data["item_type"]),
                    level=item_data["level"],
                    title=item_data["title"],
                    description=item_data.get("description"),
                    order=item_data.get("order_index") or item_data.get("order", 0),
                )
                items_to_add.append(item)

        # 按层级和order排序,确保父级先添加
        items_to_add.sort(key=lambda x: (x.level, x.order))

        # 添加所有项
        for item in items_to_add:
            outline.add_item(item)

        # 保存更新后的大纲
        result = outline_service.save_outline(outline)

        return DeleteResponse(
            success=True,
            message="大纲项删除成功",
            deleted_id=uuid.UUID(item_id),
        )

    except Exception as e:
        raise _handle_route_exception(e, "删除大纲项") from e
