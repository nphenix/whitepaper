"""
行业选择API路由

实现行业和数据库选择相关的API接口,包括行业列表,数据库列表,
选择保存,选择查询等功能.使用T202行业选择服务,调用industry_selection_schemas定义的Schema.

生成命令: /speckit.implement T206
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.domain.agent.industry import IndustryCategory
from src.domain.knowledge_base.industry_database import DatabaseType, DataSource
from src.interfaces.api.schemas.industry_selection_schemas import (
    DatabaseListResponse,
    DatabaseResponse,
    DeleteResponse,
    IndustryDatabaseListRequest,
    IndustryListRequest,
    IndustryListResponse,
    IndustryResponse,
    IndustrySelectionListRequest,
    IndustrySelectionListResponse,
    IndustrySelectionRequestValidator,
    IndustrySelectionResponse,
    IndustrySelectionUpdateRequestValidator,
    IndustryStatisticsRequest,
    IndustryStatisticsResponse,
    IndustryValidationRequest,
    IndustryValidationResponse,
)
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/industry-selection", tags=["行业选择"])

# 全局行业选择服务实例
_industry_selection_service: IndustrySelectionService | None = None


def get_industry_selection_service() -> IndustrySelectionService:
    """获取行业选择服务实例

    Returns:
        IndustrySelectionService: 行业选择服务实例
    """
    global _industry_selection_service
    if _industry_selection_service is None:
        _industry_selection_service = IndustrySelectionService()
    return _industry_selection_service

# 为了支持测试中使用 mock.patch 替换 get_industry_selection_service,
# 将实际依赖解耦到一个包装函数中,保证每次请求都会重新从模块属性读取.
def _get_industry_selection_service_dep() -> IndustrySelectionService:
    return get_industry_selection_service()


def _convert_industry_to_response(industry_data: dict[str, Any]) -> IndustryResponse:
    """将行业数据转换为响应格式

    Args:
        industry_data: 行业数据字典

    Returns:
        IndustryResponse: 行业响应对象
    """
    # 处理 metadata 字段 - 可能是字符串或字典
    metadata = industry_data.get("metadata", {})
    if isinstance(metadata, str):
        try:
            import json
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    elif metadata is None:
        metadata = {}

    return IndustryResponse(
        id=uuid.UUID(industry_data["id"]),
        name=industry_data["name"],
        code=industry_data["code"],
        category=IndustryCategory(industry_data["category"]),
        description=industry_data.get("description"),
        is_active=industry_data["is_active"],
        sort_order=industry_data["sort_order"],
        created_at=industry_data["created_at"],
        updated_at=industry_data["updated_at"],
        metadata=metadata,
    )


def _convert_database_to_response(database_data: dict[str, Any]) -> DatabaseResponse:
    """将数据库数据转换为响应格式

    Args:
        database_data: 数据库数据字典

    Returns:
        DatabaseResponse: 数据库响应对象
    """
    # 处理 metadata 字段 - 可能是字符串或字典
    metadata = database_data.get("metadata", {})
    if isinstance(metadata, str):
        try:
            import json
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    elif metadata is None:
        metadata = {}

    return DatabaseResponse(
        id=uuid.UUID(database_data["id"]),
        name=database_data["name"],
        code=database_data["code"],
        industry_id=uuid.UUID(database_data["industry_id"]),
        database_type=DatabaseType(database_data["database_type"]),
        data_source=DataSource(database_data["data_source"]),
        description=database_data.get("description"),
        is_active=database_data["is_active"],
        is_public=database_data["is_public"],
        sort_order=database_data["sort_order"],
        documents_count=database_data.get("documents_count", 0),
        size_mb=database_data.get("size_mb", 0.0),
        last_updated=database_data.get("last_updated"),
        created_at=database_data["created_at"],
        updated_at=database_data["updated_at"],
        metadata=metadata,
    )


@router.post(
    "/industries/list",
    response_model=IndustryListResponse,
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取行业列表",
    description="获取行业列表,支持按分类,激活状态过滤和排序",
)
async def list_industries(
    request: IndustryListRequest,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustryListResponse:
    """
    获取行业列表接口

    Args:
        request: 行业列表请求
        service: 行业选择服务

    Returns:
        IndustryListResponse: 行业列表响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取行业列表
        industries_data = service.get_industries(
            category=request.category,
            is_active=request.is_active,
            sort_by=request.sort_by.value if request.sort_by else "sort_order",
            sort_order=request.sort_order.value if request.sort_order else "asc",
        )

        # 转换为响应格式
        industries = [
            _convert_industry_to_response(ind) for ind in industries_data
        ]

        # 计算分页信息
        total = len(industries)
        offset = request.offset or 0
        limit = request.limit or 50
        has_more = offset + limit < total

        # 应用分页
        paginated_industries = industries[offset : offset + limit]

        return IndustryListResponse(
            industries=paginated_industries,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    except Exception as e:
        logger.exception("获取行业列表异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取行业列表失败",
        ) from e


# 注意:具体的路由(storage, energy)必须放在通用路由({industry_id})之前
# 否则 FastAPI 会将 "storage" 和 "energy" 当作 industry_id 处理

@router.get(
    "/industries/storage",
    response_model=IndustryListResponse,
    responses={
        500: {"description": "服务器内部错误"},
    },
    summary="获取储能相关行业",
    description="获取储能相关的行业列表",
)
async def get_storage_industries(
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustryListResponse:
    """
    获取储能相关行业接口

    Args:
        service: 行业选择服务

    Returns:
        IndustryListResponse: 行业列表响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取储能相关行业
        industries_data = service.get_storage_industries()

        # 转换为响应格式
        industries = [
            _convert_industry_to_response(ind) for ind in industries_data
        ]

        # 处理空列表的情况
        if not industries:
            industries = []

        return IndustryListResponse(
            industries=industries,
            total=len(industries),
            limit=len(industries) if industries else 1,
            offset=0,
            has_more=False,
        )

    except Exception as e:
        logger.exception("获取储能相关行业异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取储能相关行业失败",
        ) from e


@router.get(
    "/industries/energy",
    response_model=IndustryListResponse,
    responses={
        500: {"description": "服务器内部错误"},
    },
    summary="获取能源相关行业",
    description="获取能源分类的行业列表",
)
async def get_energy_industries(
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustryListResponse:
    """
    获取能源相关行业接口

    Args:
        service: 行业选择服务

    Returns:
        IndustryListResponse: 行业列表响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取能源相关行业
        industries_data = service.get_energy_industries()

        # 转换为响应格式
        industries = [
            _convert_industry_to_response(ind) for ind in industries_data
        ]

        # 处理空列表的情况
        if not industries:
            industries = []

        return IndustryListResponse(
            industries=industries,
            total=len(industries),
            limit=len(industries) if industries else 1,
            offset=0,
            has_more=False,
        )

    except Exception as e:
        logger.exception("获取能源相关行业异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取能源相关行业失败",
        ) from e


@router.get(
    "/industries/{industry_id}",
    response_model=IndustryResponse,
    responses={
        404: {"description": "行业不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取行业详情",
    description="根据行业ID获取行业详细信息",
)
async def get_industry_detail(
    industry_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustryResponse:
    """
    获取行业详情接口

    Args:
        industry_id: 行业ID
        service: 行业选择服务

    Returns:
        IndustryResponse: 行业详情响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取行业详情
        industry_data = service.get_industry_by_id(industry_id)

        # 转换为响应格式
        return _convert_industry_to_response(industry_data)

    except Exception as e:
        logger.exception("获取行业详情异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取行业详情失败: {e}",
        ) from e


@router.post(
    "/databases/list",
    response_model=DatabaseListResponse,
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取行业数据库列表",
    description="获取行业数据库列表,支持按行业,类型,来源等条件过滤和排序",
)
async def list_databases(
    request: IndustryDatabaseListRequest,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> DatabaseListResponse:
    """
    获取行业数据库列表接口

    Args:
        request: 行业数据库列表请求
        service: 行业选择服务

    Returns:
        DatabaseListResponse: 数据库列表响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取数据库列表
        databases_data = service.get_industry_databases(
            industry_id=str(request.industry_id) if request.industry_id else None,
            database_type=request.database_type,
            data_source=request.data_source,
            is_active=request.is_active,
            is_public=request.is_public,
            sort_by=request.sort_by.value if request.sort_by else "sort_order",
            sort_order=request.sort_order.value if request.sort_order else "asc",
        )

        # 转换为响应格式
        databases = [
            _convert_database_to_response(db) for db in databases_data
        ]

        # 计算分页信息
        total = len(databases)
        offset = request.offset or 0
        limit = request.limit or 50
        has_more = offset + limit < total

        # 应用分页
        paginated_databases = databases[offset : offset + limit]

        return DatabaseListResponse(
            databases=paginated_databases,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    except Exception as e:
        logger.exception("获取行业数据库列表异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取行业数据库列表失败",
        ) from e


@router.get(
    "/databases/{database_id}",
    response_model=DatabaseResponse,
    responses={
        404: {"description": "数据库不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取数据库详情",
    description="根据数据库ID获取数据库详细信息",
)
async def get_database_detail(
    database_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> DatabaseResponse:
    """
    获取数据库详情接口

    Args:
        database_id: 数据库ID
        service: 行业选择服务

    Returns:
        DatabaseResponse: 数据库详情响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取数据库详情
        database_data = service.get_database_by_id(database_id)

        # 转换为响应格式
        return _convert_database_to_response(database_data)

    except Exception as e:
        logger.exception("获取数据库详情异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据库详情失败: {e}",
        ) from e


@router.post(
    "/selections",
    response_model=IndustrySelectionResponse,
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="保存行业和数据库选择",
    description="保存用户的行业和数据库选择,记录到数据库中",
)
async def save_industry_selection(
    request: IndustrySelectionRequestValidator,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustrySelectionResponse:
    """
    保存行业和数据库选择接口

    Args:
        request: 行业选择请求
        service: 行业选择服务

    Returns:
        IndustrySelectionResponse: 选择响应

    Raises:
        HTTPException: 保存失败时抛出
    """
    try:
        # 生成会话ID(如果未提供)
        session_id = request.session_id or str(uuid.uuid4())

        # 保存选择
        result = service.save_industry_selection(
            session_id=session_id,
            industry_id=str(request.industry_id),
            database_ids=[str(db_id) for db_id in request.database_ids],
            selection_name=request.selection_name,
            description=request.description,
        )

        # 转换为响应格式
        selection = result["selection"]
        industry = _convert_industry_to_response(result["industry"])
        databases = [
            _convert_database_to_response(db) for db in result["databases"]
        ]

        # 处理 database_ids 字段 - 可能是 JSON 字符串
        database_ids = selection.get("database_ids", "[]")
        if isinstance(database_ids, str):
            try:
                import json
                database_ids = json.loads(database_ids)
            except (json.JSONDecodeError, TypeError):
                database_ids = []

        # 处理 metadata 字段 - 可能是 JSON 字符串
        metadata = selection.get("metadata", {})
        if isinstance(metadata, str):
            try:
                import json
                metadata = json.loads(metadata) if metadata else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        elif metadata is None:
            metadata = {}

        return IndustrySelectionResponse(
            id=uuid.UUID(selection["id"]),
            session_id=selection["session_id"],
            industry=industry,
            databases=databases,
            selection_name=selection.get("selection_name"),
            description=selection.get("description"),
            is_active=selection["is_active"],
            created_at=selection["created_at"],
            updated_at=selection["updated_at"],
            metadata=metadata,
        )

    except Exception as e:
        logger.exception("保存行业和数据库选择异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存行业和数据库选择失败: {e}",
        ) from e


@router.get(
    "/selections/{selection_id}",
    response_model=IndustrySelectionResponse,
    responses={
        404: {"description": "选择记录不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取行业选择详情",
    description="根据选择记录ID获取选择详情",
)
async def get_industry_selection_detail(
    selection_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustrySelectionResponse:
    """
    获取行业选择详情接口

    Args:
        selection_id: 选择记录ID
        service: 行业选择服务

    Returns:
        IndustrySelectionResponse: 选择详情响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取选择详情
        result = service.get_industry_selection(selection_id)

        # 转换为响应格式
        selection = result["selection"]
        industry = _convert_industry_to_response(result["industry"])
        databases = [
            _convert_database_to_response(db) for db in result["databases"]
        ]

        # 处理 database_ids 字段 - 可能是 JSON 字符串
        database_ids = selection.get("database_ids", "[]")
        if isinstance(database_ids, str):
            try:
                import json
                database_ids = json.loads(database_ids)
            except (json.JSONDecodeError, TypeError):
                database_ids = []

        # 处理 metadata 字段 - 可能是 JSON 字符串
        metadata = selection.get("metadata", {})
        if isinstance(metadata, str):
            try:
                import json
                metadata = json.loads(metadata) if metadata else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        elif metadata is None:
            metadata = {}

        return IndustrySelectionResponse(
            id=uuid.UUID(selection["id"]),
            session_id=selection["session_id"],
            industry=industry,
            databases=databases,
            selection_name=selection.get("selection_name"),
            description=selection.get("description"),
            is_active=selection["is_active"],
            created_at=selection["created_at"],
            updated_at=selection["updated_at"],
            metadata=metadata,
        )

    except Exception as e:
        logger.exception("获取行业选择详情异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取行业选择详情失败: {e}",
        ) from e


@router.post(
    "/selections/list",
    response_model=IndustrySelectionListResponse,
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取行业选择列表",
    description="根据会话ID获取行业选择记录列表",
)
async def list_industry_selections(
    request: IndustrySelectionListRequest,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustrySelectionListResponse:
    """
    获取行业选择列表接口

    Args:
        request: 行业选择列表请求
        service: 行业选择服务

    Returns:
        IndustrySelectionListResponse: 选择列表响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取选择列表
        selections_data = service.get_selections_by_session(
            session_id=request.session_id,
            is_active=request.is_active,
            sort_by=request.sort_by.value if request.sort_by else "created_at",
            sort_order=request.sort_order.value if request.sort_order else "desc",
        )

        # 转换为响应格式
        selections = []
        for item in selections_data:
            selection = item["selection"]
            industry = _convert_industry_to_response(item["industry"])
            databases = [
                _convert_database_to_response(db) for db in item["databases"]
            ]

            # 处理 database_ids 字段 - 可能是 JSON 字符串
            database_ids = selection.get("database_ids", "[]")
            if isinstance(database_ids, str):
                try:
                    import json
                    database_ids = json.loads(database_ids)
                except (json.JSONDecodeError, TypeError):
                    database_ids = []

            # 处理 metadata 字段 - 可能是 JSON 字符串
            metadata = selection.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata) if metadata else {}
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif metadata is None:
                metadata = {}

            selections.append(
                IndustrySelectionResponse(
                    id=uuid.UUID(selection["id"]),
                    session_id=selection["session_id"],
                    industry=industry,
                    databases=databases,
                    selection_name=selection.get("selection_name"),
                    description=selection.get("description"),
                    is_active=selection["is_active"],
                    created_at=selection["created_at"],
                    updated_at=selection["updated_at"],
                    metadata=metadata,
                )
            )

        # 计算分页信息
        total = len(selections)
        offset = request.offset or 0
        limit = request.limit or 20
        has_more = offset + limit < total

        # 应用分页
        paginated_selections = selections[offset : offset + limit]

        return IndustrySelectionListResponse(
            selections=paginated_selections,
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    except Exception as e:
        logger.exception("获取行业选择列表异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取行业选择列表失败",
        ) from e


@router.put(
    "/selections/{selection_id}",
    response_model=IndustrySelectionResponse,
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "选择记录不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="更新行业选择",
    description="更新已存在的行业选择记录",
)
async def update_industry_selection(
    selection_id: str,
    request: IndustrySelectionUpdateRequestValidator,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustrySelectionResponse:
    """
    更新行业选择接口

    Args:
        selection_id: 选择记录ID
        request: 更新请求
        service: 行业选择服务

    Returns:
        IndustrySelectionResponse: 更新后的选择响应

    Raises:
        HTTPException: 更新失败时抛出
    """
    try:
        # 更新选择
        result = service.update_industry_selection(
            selection_id=selection_id,
            industry_id=str(request.industry_id) if request.industry_id else None,
            database_ids=[str(db_id) for db_id in request.database_ids]
            if request.database_ids else None,
            selection_name=request.selection_name,
            description=request.description,
            is_active=request.is_active,
        )

        # 转换为响应格式
        selection = result["selection"]
        industry = _convert_industry_to_response(result["industry"])
        databases = [
            _convert_database_to_response(db) for db in result["databases"]
        ]

        # 处理 database_ids 字段 - 可能是 JSON 字符串
        database_ids = selection.get("database_ids", "[]")
        if isinstance(database_ids, str):
            try:
                import json
                database_ids = json.loads(database_ids)
            except (json.JSONDecodeError, TypeError):
                database_ids = []

        # 处理 metadata 字段 - 可能是 JSON 字符串
        metadata = selection.get("metadata", {})
        if isinstance(metadata, str):
            try:
                import json
                metadata = json.loads(metadata) if metadata else {}
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        elif metadata is None:
            metadata = {}

        return IndustrySelectionResponse(
            id=uuid.UUID(selection["id"]),
            session_id=selection["session_id"],
            industry=industry,
            databases=databases,
            selection_name=selection.get("selection_name"),
            description=selection.get("description"),
            is_active=selection["is_active"],
            created_at=selection["created_at"],
            updated_at=selection["updated_at"],
            metadata=metadata,
        )

    except Exception as e:
        logger.exception("更新行业选择异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新行业选择失败: {e}",
        ) from e


@router.delete(
    "/selections/{selection_id}",
    response_model=DeleteResponse,
    responses={
        404: {"description": "选择记录不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="删除行业选择",
    description="删除指定的行业选择记录",
)
async def delete_industry_selection(
    selection_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> DeleteResponse:
    """
    删除行业选择接口

    Args:
        selection_id: 选择记录ID
        service: 行业选择服务

    Returns:
        DeleteResponse: 删除结果响应

    Raises:
        HTTPException: 删除失败时抛出
    """
    try:
        # 删除选择
        success = service.delete_industry_selection(selection_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"行业选择记录不存在: {selection_id}",
            )

        return DeleteResponse(
            success=True,
            message="行业选择记录删除成功",
            deleted_id=uuid.UUID(selection_id),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除行业选择异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除行业选择失败: {e}",
        ) from e


@router.post(
    "/industries/statistics",
    response_model=IndustryStatisticsResponse,
    responses={
        400: {"description": "请求参数错误"},
        404: {"description": "行业不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取行业统计信息",
    description="获取指定行业的统计信息,包括数据库数量,类型分布等",
)
async def get_industry_statistics(
    request: IndustryStatisticsRequest,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustryStatisticsResponse:
    """
    获取行业统计信息接口

    Args:
        request: 行业统计请求
        service: 行业选择服务

    Returns:
        IndustryStatisticsResponse: 统计信息响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取统计信息
        statistics = service.get_industry_statistics(str(request.industry_id))

        # 转换为响应格式
        industry = _convert_industry_to_response(statistics["industry"])

        return IndustryStatisticsResponse(
            industry=industry,
            total_databases=statistics["total_databases"],
            active_databases=statistics["active_databases"],
            public_databases=statistics["public_databases"],
            database_type_stats=statistics["database_type_stats"],
            data_source_stats=statistics["data_source_stats"],
            last_updated=statistics["last_updated"],
        )

    except Exception as e:
        logger.exception("获取行业统计信息异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取行业统计信息失败: {e}",
        ) from e


@router.post(
    "/validate",
    response_model=IndustryValidationResponse,
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="验证行业和数据库选择",
    description="验证行业和数据库选择的有效性,返回验证结果和错误信息",
)
async def validate_industry_selection(
    request: IndustryValidationRequest,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> IndustryValidationResponse:
    """
    验证行业和数据库选择接口

    Args:
        request: 验证请求
        service: 行业选择服务

    Returns:
        IndustryValidationResponse: 验证结果响应

    Raises:
        HTTPException: 验证失败时抛出
    """
    try:
        # 验证选择
        validation_result = service.validate_industry_selection(
            industry_id=str(request.industry_id),
            database_ids=[str(db_id) for db_id in request.database_ids],
        )

        # 转换为响应格式
        industry = None
        if validation_result["industry"]:
            industry = _convert_industry_to_response(validation_result["industry"])

        databases = []
        for db_data in validation_result["databases"]:
            databases.append(_convert_database_to_response(db_data))

        return IndustryValidationResponse(
            is_valid=validation_result["is_valid"],
            errors=validation_result["errors"],
            warnings=validation_result["warnings"],
            industry=industry,
            databases=databases,
        )

    except Exception as e:
        logger.exception("验证行业和数据库选择异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"验证行业和数据库选择失败: {e}",
        ) from e




@router.get(
    "/databases/knowledge-base/{industry_id}",
    response_model=DatabaseListResponse,
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取知识库类型数据库",
    description="获取指定行业的知识库类型数据库列表",
)
async def get_knowledge_base_databases(
    industry_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> DatabaseListResponse:
    """
    获取知识库类型数据库接口

    Args:
        industry_id: 行业ID
        service: 行业选择服务

    Returns:
        DatabaseListResponse: 数据库列表响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取知识库类型数据库
        databases_data = service.get_knowledge_base_databases(industry_id)

        # 转换为响应格式
        databases = [
            _convert_database_to_response(db) for db in databases_data
        ]

        # 处理空列表的情况
        if not databases:
            databases = []

        return DatabaseListResponse(
            databases=databases,
            total=len(databases),
            limit=len(databases) if databases else 1,
            offset=0,
            has_more=False,
        )

    except Exception as e:
        logger.exception("获取知识库类型数据库异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取知识库类型数据库失败: {e}",
        ) from e


@router.get(
    "/databases/platform-builtin/{industry_id}",
    response_model=DatabaseListResponse,
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取平台内置数据库",
    description="获取指定行业的平台内置数据库列表",
)
async def get_platform_builtin_databases(
    industry_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> DatabaseListResponse:
    """
    获取平台内置数据库接口

    Args:
        industry_id: 行业ID
        service: 行业选择服务

    Returns:
        DatabaseListResponse: 数据库列表响应

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取平台内置数据库
        databases_data = service.get_platform_builtin_databases(industry_id)

        # 转换为响应格式
        databases = [
            _convert_database_to_response(db) for db in databases_data
        ]

        # 处理空列表的情况
        if not databases:
            databases = []

        return DatabaseListResponse(
            databases=databases,
            total=len(databases),
            limit=len(databases) if databases else 1,
            offset=0,
            has_more=False,
        )

    except Exception as e:
        logger.exception("获取平台内置数据库异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取平台内置数据库失败: {e}",
        ) from e
