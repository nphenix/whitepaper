"""
大纲前端集成接口

提供简化的RESTful API接口,便于前端组件(大纲编辑器,优化建议展示组件)调用.
使用查询参数简化GET请求,提供快速操作功能.

生成命令: /speckit.implement T218
生成时间: 2025-12-24
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from src.application.services.outline_optimization_display import (
    create_optimization_display,
)
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.domain.agent.optimized_outline import OptimizedOutline
from src.domain.agent.outline import Outline, OutlineStatus
from src.interfaces.api.schemas.outline_schemas import (
    create_success_response,
)
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/outline-frontend", tags=["大纲前端集成"])

# 全局服务实例
_outline_optimization_service: OutlineOptimizationService | None = None


def get_outline_optimization_service() -> OutlineOptimizationService:
    """获取大纲优化服务实例

    Returns:
        OutlineOptimizationService: 大纲优化服务实例
    """
    global _outline_optimization_service
    if _outline_optimization_service is None:
        _outline_optimization_service = OutlineOptimizationService()
    return _outline_optimization_service


@router.get(
    "/editor/outline/{outline_id}",
    responses={
        404: {"description": "大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取大纲编辑器数据",
    description="获取大纲的树形结构数据,便于前端编辑器渲染",
)
async def get_outline_editor_data(
    outline_id: str,
    format: str = Query("tree", description="返回格式:tree(树形结构)或 flat(扁平列表)"),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取大纲编辑器数据接口

    Args:
        outline_id: 大纲ID
        format: 返回格式(tree或flat)
        outline_service: 大纲优化服务

    Returns:
        大纲编辑器数据
    """
    try:
        # 获取大纲详情
        result = outline_service.get_outline(outline_id)

        # 转换大纲数据
        outline_data = result["outline"]
        items_data = result["items"]

        # 根据格式返回数据
        if format == "flat":
            # 扁平列表格式
            return create_success_response(
                message="获取大纲编辑器数据成功",
                data={
                    "outline": outline_data,
                    "items": items_data,
                },
            )
        else:
            # 树形结构格式(默认)
            # 构建树结构
            tree = _build_outline_tree(items_data)

            return create_success_response(
                message="获取大纲编辑器数据成功",
                data={
                    "outline": outline_data,
                    "tree": tree,
                    "total_items": len(items_data),
                },
            )

    except Exception as e:
        logger.exception("获取大纲编辑器数据异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取大纲编辑器数据失败: {e}",
        ) from e


def _build_outline_tree(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建大纲树结构

    Args:
        items: 大纲项列表

    Returns:
        树形结构的大纲
    """
    # 创建项字典
    items_dict = {item["id"]: item for item in items}

    # 构建树
    tree = []
    for item in items:
        if not item.get("parent_id"):
            # 根节点
            tree.append(_build_tree_node(item, items_dict))

    return tree


def _build_tree_node(
    item: dict[str, Any], items_dict: dict[str, dict[str, Any]]
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
        if other_item.get("parent_id") == item["id"]:
            children.append(_build_tree_node(other_item, items_dict))

    # 按order排序
    order_value = item.get("order_index") or item.get("order", 0)
    children.sort(key=lambda x: x.get("order", 0))

    return {
        "id": item["id"],
        "title": item["title"],
        "description": item.get("description"),
        "item_type": item.get("item_type"),
        "level": item.get("level", 1),
        "order": order_value,
        "is_optimized": bool(item.get("is_optimized", False)),
        "optimization_suggestions": item.get("optimization_suggestions", []),
        "children": children,
    }


@router.get(
    "/optimization/display/{optimized_outline_id}",
    responses={
        404: {"description": "优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取优化建议展示数据",
    description="获取优化建议的展示数据,支持多种展示格式",
)
async def get_optimization_display_data(
    optimized_outline_id: str,
    format: str = Query("json", description="展示格式:json,text,markdown"),
    change_type: str | None = Query(None, description="变更类型过滤:ADD,MODIFY,DELETE,MOVE,REORDER等"),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取优化建议展示数据接口

    Args:
        optimized_outline_id: 优化后大纲ID
        format: 展示格式(json,text,markdown)
        change_type: 变更类型过滤(可选)
        outline_service: 大纲优化服务

    Returns:
        优化建议展示数据
    """
    try:
        # 获取优化后大纲
        result = outline_service.get_optimized_outline(optimized_outline_id)

        # 尝试转换为OptimizedOutline对象(如果失败,使用简化格式)
        try:
            optimized_outline = _convert_to_optimized_outline(result)

            # 获取原始大纲(如果存在)
            original_outline_id = result["optimized_outline"].get("original_outline_id")
            original_outline = None
            if original_outline_id:
                try:
                    original_result = outline_service.get_outline(original_outline_id)
                    original_outline = _convert_to_outline(original_result)
                except Exception:
                    # 如果获取原始大纲失败,继续处理
                    logger.warning("获取原始大纲失败,继续处理优化建议展示", outline_id=original_outline_id)

            # 创建展示对象
            display = create_optimization_display(
                optimized_outline=optimized_outline,
                original_outline=original_outline,
            )

            # 根据格式返回数据
            if format == "text":
                return create_success_response(
                    message="获取优化建议展示数据成功",
                    data={
                        "format": "text",
                        "content": display.to_text(),
                    },
                )
            elif format == "markdown":
                return create_success_response(
                    message="获取优化建议展示数据成功",
                    data={
                        "format": "markdown",
                        "content": display.to_markdown(),
                    },
                )
            else:
                # JSON格式(默认)
                display_data = display.to_dict()

                # 如果指定了变更类型过滤,只返回该类型的变更
                if change_type:
                    filtered_changes = {}
                    if change_type == "ADD":
                        filtered_changes["added_sections"] = display.display_added_sections()
                    elif change_type == "MODIFY":
                        filtered_changes["modified_descriptions"] = display.display_modified_descriptions()
                    elif change_type == "MOVE":
                        filtered_changes["moved_sections"] = display.display_moved_sections()
                    elif change_type == "REORDER":
                        filtered_changes["reordered_sections"] = display.display_reordered_sections()
                    elif change_type == "DELETE":
                        filtered_changes["deleted_sections"] = display.display_deleted_sections()

                    display_data["changes"] = filtered_changes

                return create_success_response(
                    message="获取优化建议展示数据成功",
                    data=display_data,
                )
        except Exception as conversion_error:
            # 如果转换失败,使用简化格式直接返回数据库结果
            logger.warning("转换OptimizedOutline对象失败,使用简化格式", error=str(conversion_error))

            # 直接格式化数据库结果
            display_data = _format_optimization_data_simple(result, change_type)

            return create_success_response(
                message="获取优化建议展示数据成功(简化格式)",
                data=display_data,
            )

    except Exception as e:
        logger.exception("获取优化建议展示数据异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取优化建议展示数据失败: {e}",
        ) from e


def _format_optimization_data_simple(result: dict[str, Any], change_type: str | None = None) -> dict[str, Any]:
    """格式化优化数据(简化版本,直接使用数据库结果)

    Args:
        result: 数据库查询结果
        change_type: 变更类型过滤(可选)

    Returns:
        格式化后的优化数据
    """
    optimized_outline_data = result["optimized_outline"]
    items_data = result["items"]
    summary_data = result.get("summary")

    # 按变更类型分组
    changes_by_type = {
        "ADD": [],
        "MODIFY": [],
        "DELETE": [],
        "MOVE": [],
        "REORDER": [],
        "MERGE": [],
        "SPLIT": [],
        "NONE": [],
    }

    for item_data in items_data:
        item_change_type = item_data.get("change_type", "NONE")
        if item_change_type in changes_by_type:
            changes_by_type[item_change_type].append(item_data)

    # 如果指定了变更类型过滤,只返回该类型的变更
    if change_type and change_type in changes_by_type:
        filtered_changes = {change_type: changes_by_type[change_type]}
    else:
        filtered_changes = {k: v for k, v in changes_by_type.items() if v}

    return {
        "optimized_outline": optimized_outline_data,
        "summary": summary_data,
        "changes": filtered_changes,
        "total_changes": len(items_data),
    }


@router.get(
    "/optimization/summary/{optimized_outline_id}",
    responses={
        404: {"description": "优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取优化摘要",
    description="获取优化摘要信息,包括变更统计和质量评分",
)
async def get_optimization_summary(
    optimized_outline_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取优化摘要接口

    Args:
        optimized_outline_id: 优化后大纲ID
        outline_service: 大纲优化服务

    Returns:
        优化摘要信息
    """
    try:
        # 获取优化后大纲
        result = outline_service.get_optimized_outline(optimized_outline_id)

        # 尝试转换为OptimizedOutline对象(如果失败,使用简化格式)
        try:
            optimized_outline = _convert_to_optimized_outline(result)

            # 创建展示对象
            display = create_optimization_display(optimized_outline=optimized_outline)

            # 获取摘要
            summary = display.display_summary()

            return create_success_response(
                message="获取优化摘要成功",
                data=summary,
            )
        except Exception as conversion_error:
            # 如果转换失败,直接返回数据库中的摘要数据
            logger.warning("转换OptimizedOutline对象失败,使用简化格式", error=str(conversion_error))

            summary_data = result.get("summary", {})
            return create_success_response(
                message="获取优化摘要成功(简化格式)",
                data=summary_data,
            )

    except Exception as e:
        logger.exception("获取优化摘要异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取优化摘要失败: {e}",
        ) from e


@router.get(
    "/optimization/changes/{optimized_outline_id}",
    responses={
        404: {"description": "优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取优化变更列表",
    description="获取所有优化变更的列表,支持按变更类型过滤",
)
async def get_optimization_changes(
    optimized_outline_id: str,
    change_type: str | None = Query(None, description="变更类型过滤:ADD,MODIFY,DELETE,MOVE,REORDER等"),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取优化变更列表接口

    Args:
        optimized_outline_id: 优化后大纲ID
        change_type: 变更类型过滤(可选)
        outline_service: 大纲优化服务

    Returns:
        优化变更列表
    """
    try:
        # 获取优化后大纲
        result = outline_service.get_optimized_outline(optimized_outline_id)

        # 尝试转换为OptimizedOutline对象(如果失败,使用简化格式)
        try:
            optimized_outline = _convert_to_optimized_outline(result)

            # 创建展示对象
            display = create_optimization_display(optimized_outline=optimized_outline)

            # 根据变更类型获取数据
            if change_type == "ADD":
                changes = display.display_added_sections()
            elif change_type == "MODIFY":
                changes = display.display_modified_descriptions()
            elif change_type == "MOVE":
                changes = display.display_moved_sections()
            elif change_type == "REORDER":
                changes = display.display_reordered_sections()
            elif change_type == "DELETE":
                changes = display.display_deleted_sections()
            else:
                # 返回所有变更
                changes = display.display_all_changes()

            return create_success_response(
                message="获取优化变更列表成功",
                data={
                    "change_type": change_type,
                    "changes": changes,
                    "total": len(changes) if isinstance(changes, list) else sum(len(v) for v in changes.values() if isinstance(v, list)),
                },
            )
        except Exception as conversion_error:
            # 如果转换失败,使用简化格式
            logger.warning("转换OptimizedOutline对象失败,使用简化格式", error=str(conversion_error))

            # 直接使用数据库结果
            items_data = result["items"]
            if change_type:
                filtered_items = [item for item in items_data if item.get("change_type") == change_type]
            else:
                filtered_items = items_data

            return create_success_response(
                message="获取优化变更列表成功(简化格式)",
                data={
                    "change_type": change_type,
                    "changes": filtered_items,
                    "total": len(filtered_items),
                },
            )

    except Exception as e:
        logger.exception("获取优化变更列表异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取优化变更列表失败: {e}",
        ) from e


@router.get(
    "/optimization/status/{optimized_outline_id}",
    responses={
        404: {"description": "优化后大纲不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取优化状态统计",
    description="获取优化状态的统计信息,包括接受/拒绝数量,完成率等",
)
async def get_optimization_status_stats(
    optimized_outline_id: str,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取优化状态统计接口

    Args:
        optimized_outline_id: 优化后大纲ID
        outline_service: 大纲优化服务

    Returns:
        优化状态统计信息
    """
    try:
        # 获取优化状态
        status_info = outline_service.get_optimization_status(optimized_outline_id)

        return create_success_response(
            message="获取优化状态统计成功",
            data=status_info,
        )

    except Exception as e:
        logger.exception("获取优化状态统计异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取优化状态统计失败: {e}",
        ) from e


def _convert_to_optimized_outline(result: dict[str, Any]) -> OptimizedOutline:
    """将数据库结果转换为OptimizedOutline对象

    Args:
        result: 数据库查询结果

    Returns:
        OptimizedOutline对象
    """
    from src.domain.agent.optimized_outline import (
        OptimizationChangeType,
        OptimizationSummary,
        OptimizedOutline,
        OptimizedOutlineItem,
    )
    from src.domain.agent.outline import OutlineItem, OutlineItemType

    optimized_outline_data = result["optimized_outline"]
    items_data = result["items"]
    summary_data = result.get("summary")

    # 兼容旧表结构：optimized_outline_items 表不存在或 items 为空时，
    # 尝试从 optimized_outlines.optimized_structure(JSON树) 重建优化项，
    # 以支持草稿生成等依赖 optimized_items 的流程。
    if (not items_data) and optimized_outline_data.get("optimized_structure"):
        try:
            optimized_structure = optimized_outline_data.get("optimized_structure")
            if isinstance(optimized_structure, str):
                optimized_structure = json.loads(optimized_structure)

            if not isinstance(optimized_structure, list):
                optimized_structure = []

            # 兼容旧表结构：optimized_outlines 可能只有 outline_id
            original_outline_id_str = (
                optimized_outline_data.get("original_outline_id")
                or optimized_outline_data.get("outline_id")
            )

            def walk(
                nodes: list[dict[str, Any]],
                parent_outline_item_id: uuid.UUID | None = None,
                fallback_level: int = 1,
            ) -> list[OptimizedOutlineItem]:
                out: list[OptimizedOutlineItem] = []
                for idx, node in enumerate(nodes):
                    outline_item_id_str = node.get("optimized_item_id") or node.get("id")
                    try:
                        outline_item_id = uuid.UUID(str(outline_item_id_str))
                    except Exception:
                        outline_item_id = uuid.uuid4()

                    try:
                        opt_item_id = uuid.UUID(str(node.get("id") or uuid.uuid4()))
                    except Exception:
                        opt_item_id = uuid.uuid4()

                    item_type_raw = node.get("item_type") or "SECTION"
                    try:
                        item_type = OutlineItemType(item_type_raw)
                    except Exception:
                        item_type = OutlineItemType.SECTION

                    level = int(node.get("level") or fallback_level)
                    order = int(node.get("order") or idx)
                    title = str(node.get("title") or "")
                    description = node.get("description")

                    optimized_item = OutlineItem(
                        id=outline_item_id,
                        parent_id=parent_outline_item_id,
                        item_type=item_type,
                        level=level,
                        title=title,
                        description=description,
                        order=order,
                    )

                    change_type_raw = node.get("change_type") or "NONE"
                    try:
                        change_type = OptimizationChangeType(change_type_raw)
                    except Exception:
                        change_type = OptimizationChangeType.NONE

                    out.append(
                        OptimizedOutlineItem(
                            id=opt_item_id,
                            original_outline_id=uuid.UUID(str(original_outline_id_str)),
                            original_item_id=None,
                            original_item=None,
                            optimized_item=optimized_item,
                            change_type=change_type,
                            change_description=node.get("change_description"),
                            optimization_reason=node.get("optimization_reason"),
                            optimization_suggestions=node.get("optimization_suggestions") or [],
                            is_accepted=bool(node.get("is_accepted", False)),
                            user_feedback=node.get("user_feedback"),
                            metadata=node.get("metadata") or {},
                        )
                    )

                    children = node.get("children") or []
                    if isinstance(children, list) and children:
                        out.extend(walk(children, outline_item_id, fallback_level=level + 1))
                return out

            optimized_items = walk(optimized_structure)

            # summary 仍按原逻辑处理（旧表一般没有 summary）
            summary = None
            if summary_data:
                summary = OptimizationSummary(**summary_data)

            return OptimizedOutline(
                id=uuid.UUID(optimized_outline_data["id"]),
                original_outline_id=uuid.UUID(str(original_outline_id_str)),
                optimized_items=optimized_items,
                summary=summary,
                is_accepted=bool(optimized_outline_data.get("is_accepted", False)),
                optimization_status=optimized_outline_data.get("optimization_status", "PENDING"),
                created_at=datetime.fromisoformat(
                    optimized_outline_data.get("created_at", datetime.now(UTC).isoformat()).replace("Z", "+00:00")
                ),
                updated_at=datetime.fromisoformat(
                    optimized_outline_data.get("updated_at", datetime.now(UTC).isoformat()).replace("Z", "+00:00")
                )
                if optimized_outline_data.get("updated_at")
                else datetime.now(UTC),
                metadata=json.loads(optimized_outline_data.get("metadata", "{}"))
                if isinstance(optimized_outline_data.get("metadata"), str)
                else (optimized_outline_data.get("metadata") or {}),
            )
        except Exception:
            # fallback 失败则继续走原逻辑（可能依赖 items_data）
            pass

    # 构建优化项列表
    optimized_items = []
    for item_data in items_data:
        # 获取原始项(如果存在)
        original_item = None
        original_item_id = item_data.get("original_item_id")
        if original_item_id:
            # 从outline_items表获取原始项
            # 注意:这里需要从服务中获取,但为了简化,我们假设原始项信息已经在item_data中
            # 实际使用时,应该通过服务获取完整的原始项信息
            pass

        # 获取优化后项(从outline_items表)
        optimized_item_id = item_data.get("optimized_item_id")
        if optimized_item_id:
            # 从outline_items表获取优化后项的详细信息
            # 注意:这里需要从服务中获取,但为了简化,我们使用item_data中的信息
            # 实际使用时,应该通过服务获取完整的优化后项信息
            # 从outline_items表获取优化后项
            from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
            outline_item_adapter = SQLiteAdapter(
                table_name="outline_items",
                id_field="id",
            )
            optimized_item_data = outline_item_adapter.get_by_id(optimized_item_id)

            if optimized_item_data:
                optimized_item = OutlineItem(
                    id=uuid.UUID(optimized_item_data["id"]),
                    parent_id=uuid.UUID(optimized_item_data["parent_id"]) if optimized_item_data.get("parent_id") else None,
                    item_type=OutlineItemType(optimized_item_data.get("item_type", "HEADING")),
                    level=optimized_item_data.get("level", 1),
                    title=optimized_item_data.get("title", ""),
                    description=optimized_item_data.get("description"),
                    order=optimized_item_data.get("order_index") or optimized_item_data.get("order", 0),
                )
            else:
                # 如果获取失败,使用item_data中的信息
                optimized_item = OutlineItem(
                    id=uuid.UUID(optimized_item_id),
                    parent_id=uuid.UUID(item_data["parent_id"]) if item_data.get("parent_id") else None,
                    item_type=OutlineItemType(item_data.get("item_type", "HEADING")),
                    level=item_data.get("level", 1),
                    title=item_data.get("title", ""),
                    description=item_data.get("description"),
                    order=item_data.get("order_index") or item_data.get("order", 0),
                )
        else:
            # 如果没有optimized_item_id,跳过该项
            continue

        # 处理optimization_suggestions字段
        optimization_suggestions = item_data.get("optimization_suggestions", "[]")
        if isinstance(optimization_suggestions, str):
            try:
                optimization_suggestions = json.loads(optimization_suggestions)
            except (json.JSONDecodeError, TypeError):
                optimization_suggestions = []
        elif optimization_suggestions is None:
            optimization_suggestions = []

        # 构建OptimizedOutlineItem
        optimized_item_obj = OptimizedOutlineItem(
            id=uuid.UUID(item_data["id"]),
            original_outline_id=uuid.UUID(optimized_outline_data["original_outline_id"]),
            original_item_id=uuid.UUID(item_data["original_item_id"]) if item_data.get("original_item_id") else None,
            original_item=original_item,
            optimized_item=optimized_item,
            change_type=OptimizationChangeType(item_data.get("change_type", "NONE")),
            change_description=item_data.get("change_description"),
            optimization_reason=item_data.get("optimization_reason"),
            optimization_suggestions=optimization_suggestions,
            is_accepted=bool(item_data.get("is_accepted", False)),
            user_feedback=item_data.get("user_feedback"),
            metadata=item_data.get("metadata", {}),
        )
        optimized_items.append(optimized_item_obj)

    # 构建优化摘要
    summary = None
    if summary_data:
        # 处理JSON字段
        key_improvements = summary_data.get("key_improvements", [])
        if isinstance(key_improvements, str):
            try:
                key_improvements = json.loads(key_improvements)
            except (json.JSONDecodeError, TypeError):
                key_improvements = []
        elif key_improvements is None:
            key_improvements = []

        potential_issues = summary_data.get("potential_issues", [])
        if isinstance(potential_issues, str):
            try:
                potential_issues = json.loads(potential_issues)
            except (json.JSONDecodeError, TypeError):
                potential_issues = []
        elif potential_issues is None:
            potential_issues = []

        metadata = summary_data.get("metadata", {})
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                metadata = {}
        elif metadata is None:
            metadata = {}

        # 处理created_at字段
        created_at_str = summary_data.get("created_at")
        if isinstance(created_at_str, str):
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        else:
            created_at = datetime.now(UTC)

        summary = OptimizationSummary(
            id=uuid.UUID(summary_data["id"]),
            optimized_outline_id=uuid.UUID(optimized_outline_data["id"]),
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
            optimization_summary=summary_data.get("optimization_summary", ""),
            key_improvements=key_improvements,
            potential_issues=potential_issues,
            created_at=created_at,
            metadata=metadata,
        )

    # 处理metadata字段
    metadata = optimized_outline_data.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            metadata = {}
    elif metadata is None:
        metadata = {}

    # 处理日期字段
    created_at_str = optimized_outline_data.get("created_at")
    if isinstance(created_at_str, str):
        created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
    else:
        created_at = datetime.now(UTC)

    updated_at_str = optimized_outline_data.get("updated_at")
    if isinstance(updated_at_str, str):
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
    else:
        updated_at = datetime.now(UTC)

    # 构建OptimizedOutline
    optimized_outline = OptimizedOutline(
        id=uuid.UUID(optimized_outline_data["id"]),
        original_outline_id=uuid.UUID(optimized_outline_data["original_outline_id"]),
        optimized_items=optimized_items,
        summary=summary,
        is_accepted=bool(optimized_outline_data.get("is_accepted", False)),
        user_feedback=optimized_outline_data.get("user_feedback"),
        optimization_status=optimized_outline_data.get("optimization_status", "PENDING"),
        created_at=created_at,
        updated_at=updated_at,
        metadata=metadata,
    )

    return optimized_outline


def _convert_to_outline(result: dict[str, Any]) -> Outline:
    """将数据库结果转换为Outline对象

    Args:
        result: 数据库查询结果

    Returns:
        Outline对象
    """
    from src.domain.agent.outline import Outline, OutlineItem, OutlineItemType

    outline_data = result["outline"]
    items_data = result["items"]

    # 创建Outline对象
    outline = Outline(
        id=uuid.UUID(outline_data["id"]),
        title=outline_data["title"],
        description=outline_data.get("description"),
        industry_id=uuid.UUID(outline_data["industry_id"]),
        status=OutlineStatus(outline_data["status"]),
        current_version=outline_data.get("current_version", 1),
    )

    # 添加大纲项
    for item_data in items_data:
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

    return outline

