"""
历史记录API路由模块

提供历史记录获取相关接口:
- GET /api/history: 获取历史记录

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from src.application.services.draft_service import DraftService
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.interfaces.api.error_handlers import (
    create_error_response_from_exception,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    HistoryItem,
    create_success_response,
)
from src.shared.utils.logging import get_logger

from .core import get_outline_optimization_service

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(tags=["历史记录"])


@router.get(
    "/history",
    response_model=dict[str, Any],
    summary="获取历史记录",
    description="获取用户历史大纲列表(前端适配接口)",
)
async def get_history(
    limit: int = Query(50, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取历史记录接口(前端适配)

    获取用户历史大纲列表,包括:
    - 大纲标题,创建时间
    - 草稿状态(是否有草稿)
    - 按时间倒序排列
    - 支持分页

    Args:
        limit: 每页数量(默认50)
        offset: 偏移量(默认0)
        outline_service: 大纲优化服务

    Returns:
        统一响应格式:{ success: bool, data: { history: [...] } }
    """
    try:
        # 1. 获取大纲总数(用于分页信息)
        total_count = outline_service.outline_adapter.count(filters=None)

        # 2. 获取大纲列表(按创建时间倒序)
        # 使用outline_adapter直接查询数据库
        # 注意:SQLiteAdapter的list方法不支持offset,所以需要先获取足够的数据,然后手动分页
        # 为了性能,只获取当前页需要的数据量
        fetch_limit = limit + offset if limit + offset > 0 else None
        outline_records = outline_service.outline_adapter.list(
            filters=None,  # 不过滤,获取所有大纲
            limit=fetch_limit,  # 先获取足够的数据,然后手动分页
            order_by="created_at DESC",  # 按创建时间倒序
        )

        # 手动实现分页(因为SQLiteAdapter不支持offset参数)
        outline_records = outline_records[offset:offset + limit] if offset < len(outline_records) else []

        logger.info("获取大纲列表: 总数=%d, 返回=%d (offset=%d, limit=%d)",
                   total_count, len(outline_records), offset, limit)

        # 3. 获取草稿服务实例
        draft_service = DraftService()

        # 4. 转换为HistoryItem格式,并关联草稿状态
        history_items = []
        for outline_record in outline_records:
            outline_id = outline_record.get("id")
            title = outline_record.get("title", "未命名大纲")
            created_at = outline_record.get("created_at", "")

            # 查询是否有草稿(通过outline_id查询)
            has_draft = False
            try:
                outline_uuid = uuid.UUID(str(outline_id))
                drafts = draft_service.list_drafts(outline_id=outline_uuid, limit=1)
                has_draft = len(drafts) > 0
            except Exception as e:
                logger.warning("查询草稿状态失败: outline_id=%s, error=%s", outline_id, e)
                # 如果查询失败,默认has_draft为False

            history_item = HistoryItem(
                id=str(outline_id),
                title=title,
                date=created_at,
                hasDraft=has_draft,
            )
            history_items.append(history_item)

        logger.info("构建历史记录列表完成: 数量=%d", len(history_items))

        # 5. 返回响应
        return create_success_response(
            data={
                "history": [item.model_dump() for item in history_items],
                "total": total_count,
                "limit": limit,
                "offset": offset,
            }
        )

    except Exception as e:
        logger.exception("获取历史记录异常: %s", e)
        return create_error_response_from_exception(e)


__all__ = ["router"]
