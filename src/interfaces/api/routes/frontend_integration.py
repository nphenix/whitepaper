"""
前端集成接口

提供前端组件所需的行业选择和数据库选择集成接口,
简化前端调用流程,提供更友好的前端API.

生成命令: /speckit.implement T208
生成时间: 2025-12-23
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.domain.agent.industry import IndustryCategory
from src.domain.knowledge_base.industry_database import DatabaseType, DataSource
from src.interfaces.api.schemas.industry_selection_schemas import (
    DatabaseResponse,
    IndustryResponse,
)
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/frontend", tags=["前端集成"])

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


def _get_industry_selection_service_dep() -> IndustrySelectionService:
    """获取行业选择服务依赖(用于FastAPI依赖注入)"""
    return get_industry_selection_service()


@router.get(
    "/industries/selection-options",
    response_model=list[IndustryResponse],
    responses={
        500: {"description": "服务器内部错误"},
    },
    summary="获取行业选择选项",
    description="获取前端行业选择组件所需的行业选项列表",
)
async def get_industry_selection_options(
    category: IndustryCategory | None = Query(None, description="行业分类过滤"),
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> list[IndustryResponse]:
    """
    获取行业选择选项接口

    Args:
        category: 行业分类过滤条件
        service: 行业选择服务

    Returns:
        List[IndustryResponse]: 行业选项列表

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取行业列表
        industries_data = service.get_industries(
            category=category,
            is_active=True,  # 只返回激活的行业
            sort_by="sort_order",
            sort_order="asc",
        )

        # 转换为响应格式
        industries = []
        for ind in industries_data:
            # 处理 metadata 字段
            metadata = ind.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif metadata is None:
                metadata = {}

            industries.append(
                IndustryResponse(
                    id=uuid.UUID(ind["id"]),
                    name=ind["name"],
                    code=ind["code"],
                    category=IndustryCategory(ind["category"]),
                    description=ind.get("description"),
                    is_active=ind["is_active"],
                    sort_order=ind["sort_order"],
                    created_at=ind["created_at"],
                    updated_at=ind["updated_at"],
                    metadata=metadata,
                )
            )

        return industries

    except Exception as e:
        logger.exception("获取行业选择选项异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取行业选择选项失败",
        ) from e


@router.get(
    "/industries/storage-options",
    response_model=list[IndustryResponse],
    responses={
        500: {"description": "服务器内部错误"},
    },
    summary="获取储能行业选项",
    description="获取前端储能行业选择组件所需的行业选项列表",
)
async def get_storage_industry_options(
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> list[IndustryResponse]:
    """
    获取储能行业选项接口

    Args:
        service: 行业选择服务

    Returns:
        List[IndustryResponse]: 储能行业选项列表

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取储能相关行业
        industries_data = service.get_storage_industries()

        # 转换为响应格式
        industries = []
        for ind in industries_data:
            # 处理 metadata 字段
            metadata = ind.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif metadata is None:
                metadata = {}

            industries.append(
                IndustryResponse(
                    id=uuid.UUID(ind["id"]),
                    name=ind["name"],
                    code=ind["code"],
                    category=IndustryCategory(ind["category"]),
                    description=ind.get("description"),
                    is_active=ind["is_active"],
                    sort_order=ind["sort_order"],
                    created_at=ind["created_at"],
                    updated_at=ind["updated_at"],
                    metadata=metadata,
                )
            )

        return industries

    except Exception as e:
        logger.exception("获取储能行业选项异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取储能行业选项失败",
        ) from e


@router.get(
    "/databases/selection-options/{industry_id}",
    response_model=list[DatabaseResponse],
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取数据库选择选项",
    description="获取前端数据库选择组件所需的数据库选项列表",
)
async def get_database_selection_options(
    industry_id: str,
    database_type: DatabaseType | None = Query(None, description="数据库类型过滤"),
    data_source: DataSource | None = Query(None, description="数据来源过滤"),
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> list[DatabaseResponse]:
    """
    获取数据库选择选项接口

    Args:
        industry_id: 行业ID
        database_type: 数据库类型过滤条件
        data_source: 数据来源过滤条件
        service: 行业选择服务

    Returns:
        List[DatabaseResponse]: 数据库选项列表

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取数据库列表
        databases_data = service.get_industry_databases(
            industry_id=industry_id,
            database_type=database_type,
            data_source=data_source,
            is_active=True,  # 只返回激活的数据库
            is_public=True,  # 只返回公开的数据库
            sort_by="sort_order",
            sort_order="asc",
        )

        # 转换为响应格式
        databases = []
        for db in databases_data:
            # 处理 metadata 字段
            metadata = db.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif metadata is None:
                metadata = {}

            databases.append(
                DatabaseResponse(
                    id=uuid.UUID(db["id"]),
                    name=db["name"],
                    code=db["code"],
                    industry_id=uuid.UUID(db["industry_id"]),
                    database_type=DatabaseType(db["database_type"]),
                    data_source=DataSource(db["data_source"]),
                    description=db.get("description"),
                    is_active=db["is_active"],
                    is_public=db["is_public"],
                    sort_order=db["sort_order"],
                    documents_count=db.get("documents_count", 0),
                    size_mb=db.get("size_mb", 0.0),
                    last_updated=db.get("last_updated"),
                    created_at=db["created_at"],
                    updated_at=db["updated_at"],
                    metadata=metadata,
                )
            )

        return databases

    except Exception as e:
        logger.exception("获取数据库选择选项异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取数据库选择选项失败",
        ) from e


@router.get(
    "/databases/knowledge-base-options/{industry_id}",
    response_model=list[DatabaseResponse],
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取知识库类型数据库选项",
    description="获取前端知识库类型数据库选择组件所需的数据库选项列表",
)
async def get_knowledge_base_database_options(
    industry_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> list[DatabaseResponse]:
    """
    获取知识库类型数据库选项接口

    Args:
        industry_id: 行业ID
        service: 行业选择服务

    Returns:
        List[DatabaseResponse]: 知识库类型数据库选项列表

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取知识库类型数据库
        databases_data = service.get_knowledge_base_databases(industry_id)

        # 转换为响应格式
        databases = []
        for db in databases_data:
            # 处理 metadata 字段
            metadata = db.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif metadata is None:
                metadata = {}

            databases.append(
                DatabaseResponse(
                    id=uuid.UUID(db["id"]),
                    name=db["name"],
                    code=db["code"],
                    industry_id=uuid.UUID(db["industry_id"]),
                    database_type=DatabaseType(db["database_type"]),
                    data_source=DataSource(db["data_source"]),
                    description=db.get("description"),
                    is_active=db["is_active"],
                    is_public=db["is_public"],
                    sort_order=db["sort_order"],
                    documents_count=db.get("documents_count", 0),
                    size_mb=db.get("size_mb", 0.0),
                    last_updated=db.get("last_updated"),
                    created_at=db["created_at"],
                    updated_at=db["updated_at"],
                    metadata=metadata,
                )
            )

        return databases

    except Exception as e:
        logger.exception("获取知识库类型数据库选项异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取知识库类型数据库选项失败",
        ) from e


@router.get(
    "/databases/platform-builtin-options/{industry_id}",
    response_model=list[DatabaseResponse],
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取平台内置数据库选项",
    description="获取前端平台内置数据库选择组件所需的数据库选项列表",
)
async def get_platform_builtin_database_options(
    industry_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> list[DatabaseResponse]:
    """
    获取平台内置数据库选项接口

    Args:
        industry_id: 行业ID
        service: 行业选择服务

    Returns:
        List[DatabaseResponse]: 平台内置数据库选项列表

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取平台内置数据库
        databases_data = service.get_platform_builtin_databases(industry_id)

        # 转换为响应格式
        databases = []
        for db in databases_data:
            # 处理 metadata 字段
            metadata = db.get("metadata", {})
            if isinstance(metadata, str):
                try:
                    import json
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif metadata is None:
                metadata = {}

            databases.append(
                DatabaseResponse(
                    id=uuid.UUID(db["id"]),
                    name=db["name"],
                    code=db["code"],
                    industry_id=uuid.UUID(db["industry_id"]),
                    database_type=DatabaseType(db["database_type"]),
                    data_source=DataSource(db["data_source"]),
                    description=db.get("description"),
                    is_active=db["is_active"],
                    is_public=db["is_public"],
                    sort_order=db["sort_order"],
                    documents_count=db.get("documents_count", 0),
                    size_mb=db.get("size_mb", 0.0),
                    last_updated=db.get("last_updated"),
                    created_at=db["created_at"],
                    updated_at=db["updated_at"],
                    metadata=metadata,
                )
            )

        return databases

    except Exception as e:
        logger.exception("获取平台内置数据库选项异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取平台内置数据库选项失败",
        ) from e


@router.get(
    "/selection/quick-save/{industry_id}",
    responses={
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="快速保存行业和数据库选择",
    description="前端快速保存行业和数据库选择,简化参数",
)
async def quick_save_selection(
    industry_id: str,
    database_ids: list[str] = Query(..., description="数据库ID列表"),
    session_id: str | None = Query(None, description="会话ID"),
    selection_name: str | None = Query(None, description="选择名称"),
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> dict[str, Any]:
    """
    快速保存行业和数据库选择接口

    Args:
        industry_id: 行业ID
        database_ids: 数据库ID列表
        session_id: 会话ID
        selection_name: 选择名称
        service: 行业选择服务

    Returns:
        Dict[str, Any]: 保存结果

    Raises:
        HTTPException: 保存失败时抛出
    """
    try:
        # 生成会话ID(如果未提供)
        session_id = session_id or str(uuid.uuid4())

        # 保存选择
        result = service.save_industry_selection(
            session_id=session_id,
            industry_id=industry_id,
            database_ids=database_ids,
            selection_name=selection_name,
            description=None,  # 快速保存不需要描述
        )

        # 返回简化结果
        return {
            "success": True,
            "message": "行业和数据库选择保存成功",
            "selection_id": result["selection"]["id"],
            "session_id": session_id,
            "industry_id": industry_id,
            "database_ids": database_ids,
            "selection_name": selection_name,
        }

    except Exception as e:
        logger.exception("快速保存行业和数据库选择异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"快速保存行业和数据库选择失败: {e}",
        ) from e


@router.get(
    "/selection/quick-get/{selection_id}",
    responses={
        404: {"description": "选择记录不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="快速获取行业选择详情",
    description="前端快速获取行业选择详情,返回简化格式",
)
async def quick_get_selection(
    selection_id: str,
    service: IndustrySelectionService = Depends(_get_industry_selection_service_dep),
) -> dict[str, Any]:
    """
    快速获取行业选择详情接口

    Args:
        selection_id: 选择记录ID
        service: 行业选择服务

    Returns:
        Dict[str, Any]: 选择详情

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取选择详情
        result = service.get_industry_selection(selection_id)

        # 返回简化结果
        selection = result["selection"]
        industry = result["industry"]
        databases = result["databases"]

        # 处理 database_ids 字段
        database_ids = selection.get("database_ids", "[]")
        if isinstance(database_ids, str):
            try:
                import json
                database_ids = json.loads(database_ids)
            except (json.JSONDecodeError, TypeError):
                database_ids = []

        return {
            "success": True,
            "selection_id": selection["id"],
            "session_id": selection["session_id"],
            "industry_id": industry["id"],
            "industry_name": industry["name"],
            "industry_code": industry["code"],
            "database_ids": database_ids,
            "database_names": [db["name"] for db in databases],
            "database_codes": [db["code"] for db in databases],
            "selection_name": selection.get("selection_name"),
            "description": selection.get("description"),
            "created_at": selection["created_at"],
            "updated_at": selection["updated_at"],
        }

    except Exception as e:
        logger.exception("快速获取行业选择详情异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"快速获取行业选择详情失败: {e}",
        ) from e
