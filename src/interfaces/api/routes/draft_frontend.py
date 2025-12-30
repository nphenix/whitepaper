"""
草稿前端集成接口

提供简化的RESTful API接口,便于前端组件(草稿编辑器,素材追溯展示组件,本地文章跳转链接组件)调用.
使用查询参数简化GET请求,提供快速操作功能.

生成命令: /speckit.implement T242
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

from src.application.services.draft_service import DraftService
from src.application.services.draft_source_trace_service import (
    DraftSourceTraceService,
    ReferenceFormat,
    RenderFormat,
    create_draft_source_trace_service,
)
from src.application.services.local_document_link_service import (
    LocalDocumentLinkService,
)
from src.application.services.source_jump_service import (
    SourceJumpService,
    create_source_jump_service,
)
from src.domain.agent.source_reference import SourceReference
from src.interfaces.api.schemas.draft_mvp_schemas import (
    create_success_response,
)
from src.shared.exceptions.base_exceptions import ResourceNotFoundError
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/draft-frontend", tags=["草稿前端集成"])

# 全局服务实例
_trace_service: DraftSourceTraceService | None = None
_jump_service: SourceJumpService | None = None
_link_service: LocalDocumentLinkService | None = None

# 信息源引用存储(临时,使用内存存储)
_source_references_storage: dict[str, dict[uuid.UUID, SourceReference]] = {}


def get_trace_service() -> DraftSourceTraceService:
    """获取素材追溯显示服务实例

    Returns:
        DraftSourceTraceService: 素材追溯显示服务实例
    """
    global _trace_service
    if _trace_service is None:
        _trace_service = create_draft_source_trace_service()
    return _trace_service


def get_jump_service() -> SourceJumpService:
    """获取素材来源跳转服务实例

    Returns:
        SourceJumpService: 素材来源跳转服务实例
    """
    global _jump_service
    if _jump_service is None:
        _jump_service = create_source_jump_service()
    return _jump_service


def get_link_service() -> LocalDocumentLinkService:
    """获取本地文章链接服务实例

    Returns:
        LocalDocumentLinkService: 本地文章链接服务实例
    """
    global _link_service
    if _link_service is None:
        _link_service = LocalDocumentLinkService()
    return _link_service


# ========== 草稿编辑器相关API ==========


@router.get(
    "/editor/draft/{draft_id}",
    responses={
        404: {"description": "草稿不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取草稿编辑器数据",
    description="获取草稿的章节结构数据,便于前端编辑器渲染",
)
async def get_draft_editor_data(
    draft_id: str,
    format: str = Query(
        "tree", description="返回格式:tree(树形结构)或 flat(扁平列表)"
    ),
) -> dict[str, Any]:
    """
    获取草稿编辑器数据接口

    Args:
        draft_id: 草稿ID
        format: 返回格式(tree或flat)

    Returns:
        草稿编辑器数据
    """
    try:
        # 从数据库获取草稿
        draft_service = DraftService()
        try:
            draft = draft_service.get_draft(draft_id)
        except ResourceNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"草稿不存在: {draft_id}",
            )

        # 转换章节数据
        sections_data = [
            {
                "id": str(section.id),
                "parent_id": str(section.parent_id) if section.parent_id else None,
                "section_type": section.section_type.value,
                "level": section.level,
                "title": section.title,
                "content": section.content,
                "order": section.order,
                "source_references": [str(ref_id) for ref_id in section.source_references],
                "metadata": section.metadata,
            }
            for section in draft.sections
        ]

        # 根据格式返回数据
        def _status_str(v: object) -> str:
            return v.value if hasattr(v, "value") else str(v)

        if format == "flat":
            # 扁平列表格式
            return create_success_response(
                message="获取草稿编辑器数据成功",
                data={
                    "draft": {
                        "id": str(draft.id),
                        "title": draft.title,
                        "description": draft.description,
                        "status": _status_str(draft.status),
                        "created_at": draft.created_at.isoformat(),
                        "updated_at": draft.updated_at.isoformat(),
                    },
                    "sections": sections_data,
                },
            )
        else:
            # 树形结构格式(默认)
            tree = _build_draft_tree(sections_data)

            return create_success_response(
                message="获取草稿编辑器数据成功",
                data={
                    "draft": {
                        "id": str(draft.id),
                        "title": draft.title,
                        "description": draft.description,
                        "status": _status_str(draft.status),
                        "created_at": draft.created_at.isoformat(),
                        "updated_at": draft.updated_at.isoformat(),
                    },
                    "tree": tree,
                    "total_sections": len(sections_data),
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取草稿编辑器数据异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取草稿编辑器数据失败: {e}",
        ) from e


def _build_draft_tree(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """构建草稿树结构

    Args:
        sections: 章节列表

    Returns:
        树形结构的草稿
    """
    # 创建章节字典
    sections_dict = {section["id"]: section for section in sections}

    # 构建树
    tree = []
    for section in sections:
        if not section.get("parent_id"):
            # 根节点
            tree.append(_build_section_tree_node(section, sections_dict))

    return tree


def _build_section_tree_node(
    section: dict[str, Any], sections_dict: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """构建章节树节点

    Args:
        section: 章节数据
        sections_dict: 所有章节字典

    Returns:
        树节点
    """
    node = {
        "id": section["id"],
        "section_type": section["section_type"],
        "level": section["level"],
        "title": section["title"],
        "content": section["content"],
        "order": section["order"],
        "source_references": section["source_references"],
        "metadata": section["metadata"],
        "children": [],
    }

    # 查找子节点
    for _child_id, child_section in sections_dict.items():
        if child_section.get("parent_id") == section["id"]:
            node["children"].append(_build_section_tree_node(child_section, sections_dict))

    # 按order排序子节点
    node["children"].sort(key=lambda x: x["order"])

    return node


# ========== 素材追溯展示组件API ==========


@router.get(
    "/trace/display/{draft_id}",
    responses={
        404: {"description": "草稿不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取素材追溯展示数据",
    description="获取草稿的素材追溯展示数据,支持多种渲染格式(仅支持本地文章)",
)
async def get_source_trace_display(
    draft_id: str,
    render_format: str = Query(
        "markdown", description="渲染格式:markdown,html,plain"
    ),
    reference_format: str = Query(
        "footnote", description="引用格式:footnote,inline,bracket,endnote"
    ),
    trace_service: DraftSourceTraceService = Depends(get_trace_service),
) -> dict[str, Any]:
    """
    获取素材追溯展示数据接口

    Args:
        draft_id: 草稿ID
        render_format: 渲染格式(markdown,html,plain)
        reference_format: 引用格式(footnote,inline,bracket,endnote)
        trace_service: 素材追溯显示服务

    Returns:
        素材追溯展示数据
    """
    try:
        # 从数据库获取草稿
        draft_service = DraftService()
        try:
            draft = draft_service.get_draft(draft_id)
        except ResourceNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"草稿不存在: {draft_id}",
            )

        # 获取信息源引用
        source_references = _source_references_storage.get(draft_id, {})

        # 设置引用格式
        try:
            ref_format = ReferenceFormat(reference_format)
        except ValueError:
            ref_format = ReferenceFormat.FOOTNOTE

        trace_service.set_reference_format(ref_format)

        # 设置渲染格式
        try:
            render_fmt = RenderFormat(render_format)
        except ValueError:
            render_fmt = RenderFormat.MARKDOWN

        # 渲染草稿(包含引用标记)
        rendered_content = trace_service.render_draft_with_references(
            draft=draft,
            source_references=source_references,
            render_format=render_fmt,
        )

        # 统计引用信息
        total_references = len(source_references)
        sections_with_refs = sum(
            1 for section in draft.sections if section.has_source_references()
        )

        return create_success_response(
            message="获取素材追溯展示数据成功",
            data={
                "draft_id": draft_id,
                "draft_title": draft.title,
                "rendered_content": rendered_content,
                "render_format": render_format,
                "reference_format": reference_format,
                "statistics": {
                    "total_sections": len(draft.sections),
                    "sections_with_references": sections_with_refs,
                    "total_references": total_references,
                },
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取素材追溯展示数据异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取素材追溯展示数据失败: {e}",
        ) from e


@router.get(
    "/trace/section/{draft_id}/{section_id}",
    responses={
        404: {"description": "草稿或章节不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取章节素材追溯展示数据",
    description="获取指定章节的素材追溯展示数据(仅支持本地文章)",
)
async def get_section_source_trace_display(
    draft_id: str,
    section_id: str,
    render_format: str = Query(
        "markdown", description="渲染格式:markdown,html,plain"
    ),
    reference_format: str = Query(
        "footnote", description="引用格式:footnote,inline,bracket,endnote"
    ),
    trace_service: DraftSourceTraceService = Depends(get_trace_service),
) -> dict[str, Any]:
    """
    获取章节素材追溯展示数据接口

    Args:
        draft_id: 草稿ID
        section_id: 章节ID
        render_format: 渲染格式
        reference_format: 引用格式
        trace_service: 素材追溯显示服务

    Returns:
        章节素材追溯展示数据
    """
    try:
        # 从数据库获取草稿
        draft_service = DraftService()
        try:
            draft = draft_service.get_draft(draft_id)
        except ResourceNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"草稿不存在: {draft_id}",
            )

        # 查找章节
        section = None
        for sec in draft.sections:
            if str(sec.id) == section_id:
                section = sec
                break

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"章节不存在: {section_id}",
            )

        # 获取信息源引用
        source_references = _source_references_storage.get(draft_id, {})

        # 设置引用格式
        try:
            ref_format = ReferenceFormat(reference_format)
        except ValueError:
            ref_format = ReferenceFormat.FOOTNOTE

        trace_service.set_reference_format(ref_format)

        # 设置渲染格式
        try:
            render_fmt = RenderFormat(render_format)
        except ValueError:
            render_fmt = RenderFormat.MARKDOWN

        # 渲染章节(包含引用标记)
        rendered_content = trace_service.render_section_with_references(
            section=section,
            source_references=source_references,
            render_format=render_fmt,
        )

        return create_success_response(
            message="获取章节素材追溯展示数据成功",
            data={
                "draft_id": draft_id,
                "section_id": section_id,
                "section_title": section.title,
                "rendered_content": rendered_content,
                "render_format": render_format,
                "reference_format": reference_format,
                "reference_count": len(section.source_references),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取章节素材追溯展示数据异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取章节素材追溯展示数据失败: {e}",
        ) from e


# ========== 本地文章跳转链接组件API ==========


@router.get(
    "/jump/link/{draft_id}/{reference_id}",
    responses={
        404: {"description": "草稿或引用不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取跳转链接信息",
    description="获取信息源引用的跳转链接信息(仅支持本地文章)",
)
async def get_jump_link_info(
    draft_id: str,
    reference_id: str,
    scheme: str = Query("file", description="跳转方案:file、http、https"),
    use_http: bool = Query(False, description="是否使用HTTP协议"),
    jump_service: SourceJumpService = Depends(get_jump_service),
) -> dict[str, Any]:
    """
    获取跳转链接信息接口

    Args:
        draft_id: 草稿ID
        reference_id: 信息源引用ID
        scheme: 跳转方案
        use_http: 是否使用HTTP协议
        jump_service: 素材来源跳转服务

    Returns:
        跳转链接信息
    """
    try:
        # 从数据库获取草稿
        draft_service = DraftService()
        try:
            draft_service.get_draft(draft_id)
        except ResourceNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"草稿不存在: {draft_id}",
            )

        # 获取信息源引用
        source_references = _source_references_storage.get(draft_id, {})
        try:
            ref_uuid = uuid.UUID(reference_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的引用ID格式: {reference_id}",
            )

        source_reference = source_references.get(ref_uuid)
        if not source_reference:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"信息源引用不存在: {reference_id}",
            )

        # 获取跳转信息
        jump_info = jump_service.get_jump_info(
            source_reference=source_reference,
            scheme=scheme,
            use_http=use_http,
        )

        if not jump_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法获取跳转信息(可能是不支持的引用类型)",
            )

        return create_success_response(
            message="获取跳转链接信息成功",
            data=jump_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取跳转链接信息异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取跳转链接信息失败: {e}",
        ) from e


@router.get(
    "/jump/format/{draft_id}/{reference_id}",
    responses={
        404: {"description": "草稿或引用不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="格式化跳转链接",
    description="格式化信息源引用的跳转链接(用于Markdown/HTML渲染,仅支持本地文章)",
)
async def format_jump_link(
    draft_id: str,
    reference_id: str,
    format_type: str = Query("markdown", description="格式类型:markdown,html"),
    scheme: str = Query("file", description="跳转方案:file、http、https"),
    use_http: bool = Query(False, description="是否使用HTTP协议"),
    jump_service: SourceJumpService = Depends(get_jump_service),
) -> dict[str, Any]:
    """
    格式化跳转链接接口

    Args:
        draft_id: 草稿ID
        reference_id: 信息源引用ID
        format_type: 格式类型(markdown,html)
        scheme: 跳转方案
        use_http: 是否使用HTTP协议
        jump_service: 素材来源跳转服务

    Returns:
        格式化后的跳转链接
    """
    try:
        # 从数据库获取草稿
        draft_service = DraftService()
        try:
            draft_service.get_draft(draft_id)
        except ResourceNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"草稿不存在: {draft_id}",
            )

        # 获取信息源引用
        source_references = _source_references_storage.get(draft_id, {})
        try:
            ref_uuid = uuid.UUID(reference_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的引用ID格式: {reference_id}",
            )

        source_reference = source_references.get(ref_uuid)
        if not source_reference:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"信息源引用不存在: {reference_id}",
            )

        # 格式化跳转链接
        formatted_link = jump_service.format_jump_link(
            source_reference=source_reference,
            format_type=format_type,
            scheme=scheme,
            use_http=use_http,
        )

        if not formatted_link:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="无法格式化跳转链接(可能是不支持的引用类型)",
            )

        return create_success_response(
            message="格式化跳转链接成功",
            data={
                "formatted_link": formatted_link,
                "format_type": format_type,
                "reference_id": reference_id,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("格式化跳转链接异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"格式化跳转链接失败: {e}",
        ) from e


@router.get(
    "/jump/can-jump/{draft_id}/{reference_id}",
    responses={
        404: {"description": "草稿或引用不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="检查是否可以跳转",
    description="检查信息源引用是否可以跳转(仅支持本地文章)",
)
async def check_can_jump(
    draft_id: str,
    reference_id: str,
    jump_service: SourceJumpService = Depends(get_jump_service),
) -> dict[str, Any]:
    """
    检查是否可以跳转接口

    Args:
        draft_id: 草稿ID
        reference_id: 信息源引用ID
        jump_service: 素材来源跳转服务

    Returns:
        是否可以跳转的信息
    """
    try:
        # 从数据库获取草稿
        draft_service = DraftService()
        try:
            draft_service.get_draft(draft_id)
        except ResourceNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"草稿不存在: {draft_id}",
            )

        # 获取信息源引用
        source_references = _source_references_storage.get(draft_id, {})
        try:
            ref_uuid = uuid.UUID(reference_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"无效的引用ID格式: {reference_id}",
            )

        source_reference = source_references.get(ref_uuid)
        if not source_reference:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"信息源引用不存在: {reference_id}",
            )

        # 检查是否可以跳转
        can_jump = jump_service.can_jump(source_reference)

        return create_success_response(
            message="检查是否可以跳转成功",
            data={
                "can_jump": can_jump,
                "reference_id": reference_id,
                "reference_type": source_reference.reference_type.value,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("检查是否可以跳转异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检查是否可以跳转失败: {e}",
        ) from e

