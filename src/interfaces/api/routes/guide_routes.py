"""
指南内容管理API路由

提供指南内容的保存、读取、删除等API接口。

生成命令: /speckit.implement guide_routes
生成时间: 2026-01-08
来源: 用户需求
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.application.services.guide_storage_service import GuideStorageService
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger
from src.shared.utils.validators import validate_uuid

logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/guides", tags=["指南管理"])

# 全局服务实例
_guide_storage_service: GuideStorageService | None = None


def get_guide_storage_service() -> GuideStorageService:
    """获取指南存储服务实例"""
    global _guide_storage_service
    if _guide_storage_service is None:
        _guide_storage_service = GuideStorageService()
    return _guide_storage_service


# === 请求/响应 Schema ===


class GuideSaveRequest(BaseModel):
    """保存指南请求"""

    outline_id: str = Field(..., description="大纲ID")
    content: str = Field(..., description="指南内容（Markdown格式）")
    title: str | None = Field(None, description="指南标题", max_length=200)
    save_history: bool = Field(default=True, description="是否保存历史版本")


class GuideResponse(BaseModel):
    """指南响应"""

    success: bool = Field(default=True)
    outline_id: str = Field(..., description="大纲ID")
    file_path: str = Field(..., description="文件路径")
    title: str = Field(..., description="标题")
    content_length: int = Field(..., description="内容长度")
    saved_at: str = Field(..., description="保存时间")
    file_exists: bool = Field(default=True, description="文件是否存在")


class GuideGetResponse(BaseModel):
    """获取指南响应"""

    success: bool = Field(default=True)
    outline_id: str = Field(..., description="大纲ID")
    exists: bool = Field(..., description="是否存在")
    file_path: str | None = Field(None, description="文件路径")
    metadata: dict[str, Any] | None = Field(None, description="元数据")
    content: str | None = Field(None, description="指南内容")
    content_length: int | None = Field(0, description="内容长度")


class GuideListResponse(BaseModel):
    """指南列表响应"""

    success: bool = Field(default=True)
    guides: list[dict[str, Any]] = Field(..., description="指南列表")
    total: int = Field(..., description="总数")


class GuideDeleteResponse(BaseModel):
    """删除指南响应"""

    success: bool = Field(default=True)
    outline_id: str = Field(..., description="大纲ID")
    deleted_count: int = Field(..., description="删除的文件数量")
    message: str = Field(default="删除成功")


class GuideHistoryResponse(BaseModel):
    """指南历史版本响应"""

    success: bool = Field(default=True)
    outline_id: str = Field(..., description="大纲ID")
    versions: list[dict[str, Any]] = Field(..., description="历史版本列表")


# === API 端点 ===


@router.post(
    "/save",
    response_model=GuideResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "指南保存成功"},
        400: {"description": "请求参数错误"},
        500: {"description": "服务器内部错误"},
    },
    summary="保存指南内容",
    description="将指南内容保存为Markdown文件",
)
async def save_guide(
    request: GuideSaveRequest,
    service: GuideStorageService = Depends(get_guide_storage_service),
) -> GuideResponse:
    """
    保存指南内容

    - **outline_id**: 大纲ID
    - **content**: 指南内容（Markdown格式）
    - **title**: 指南标题（可选）
    - **save_history**: 是否保存历史版本（默认True）
    """
    try:
        # 验证UUID格式
        validate_uuid(request.outline_id)

        # 保存指南
        result = service.save_guide(
            outline_id=request.outline_id,
            content=request.content,
            title=request.title,
            save_history=request.save_history,
        )

        # 更新大纲的元数据，保存指南文件路径
        from src.application.services.outline_optimization_service import (
            OutlineOptimizationService,
        )

        outline_service = OutlineOptimizationService()
        try:
            outline = outline_service.get_outline(request.outline_id)
            if outline and outline.get("outline"):
                outline_data = outline["outline"]
                outline_service.save_outline_field(
                    request.outline_id,
                    "metadata",
                    {"guide_file_path": result["file_path"]},
                )
        except Exception as e:
            logger.warning("更新大纲元数据失败", outline_id=request.outline_id, error=str(e))

        logger.info(
            "指南保存API成功",
            outline_id=request.outline_id,
            content_length=len(request.content),
        )

        return GuideResponse(
            success=True,
            outline_id=result["outline_id"],
            file_path=result["file_path"],
            title=result["title"],
            content_length=result["content_length"],
            saved_at=result["saved_at"],
        )

    except ProcessingError as e:
        logger.error("保存指南失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        logger.error("参数验证失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception("保存指南时发生未知错误", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存指南失败: {e}",
        ) from e


@router.get(
    "/{outline_id}",
    response_model=GuideGetResponse,
    responses={
        200: {"description": "获取成功"},
        404: {"description": "指南不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取指南内容",
    description="根据大纲ID获取指南内容",
)
async def get_guide(
    outline_id: str,
    service: GuideStorageService = Depends(get_guide_storage_service),
) -> GuideGetResponse:
    """
    获取指南内容

    - **outline_id**: 大纲ID
    """
    try:
        # 验证UUID格式
        validate_uuid(outline_id)

        # 获取指南
        guide = service.get_guide(outline_id)

        if guide is None:
            return GuideGetResponse(
                success=True,
                outline_id=outline_id,
                exists=False,
                file_path=None,
                metadata=None,
                content=None,
                content_length=0,
            )

        logger.debug("获取指南成功", outline_id=outline_id)

        return GuideGetResponse(
            success=True,
            outline_id=outline_id,
            exists=True,
            file_path=guide.get("file_path"),
            metadata=guide.get("metadata"),
            content=guide.get("content"),
            content_length=len(guide.get("content", "")),
        )

    except ProcessingError as e:
        logger.error("获取指南失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except ValueError as e:
        logger.error("参数验证失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{outline_id}/content",
    responses={
        200: {"description": "获取成功"},
        404: {"description": "指南不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取指南纯内容",
    description="仅返回指南的Markdown内容文本",
)
async def get_guide_content(
    outline_id: str,
    service: GuideStorageService = Depends(get_guide_storage_service),
) -> dict[str, Any]:
    """
    获取指南纯内容

    - **outline_id**: 大纲ID
    """
    try:
        # 验证UUID格式
        validate_uuid(outline_id)

        # 获取内容
        content = service.get_guide_content(outline_id)

        if content is None:
            return {
                "success": True,
                "outline_id": outline_id,
                "exists": False,
                "content": None,
            }

        return {
            "success": True,
            "outline_id": outline_id,
            "exists": True,
            "content": content,
            "content_length": len(content),
        }

    except Exception as e:
        logger.exception("获取指南内容失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取指南内容失败: {e}",
        ) from e


@router.get(
    "/{outline_id}/exists",
    responses={
        200: {"description": "检查完成"},
    },
    summary="检查指南是否存在",
    description="检查指定大纲的指南文件是否存在",
)
async def check_guide_exists(
    outline_id: str,
    service: GuideStorageService = Depends(get_guide_storage_service),
) -> dict[str, Any]:
    """
    检查指南是否存在

    - **outline_id**: 大纲ID
    """
    try:
        # 验证UUID格式
        validate_uuid(outline_id)

        exists = service.guide_exists(outline_id)

        return {
            "success": True,
            "outline_id": outline_id,
            "exists": exists,
        }

    except ValueError as e:
        logger.error("参数验证失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{outline_id}/history",
    response_model=GuideHistoryResponse,
    responses={
        200: {"description": "获取成功"},
        500: {"description": "服务器内部错误"},
    },
    summary="获取指南历史版本",
    description="获取指南文件的历史版本列表",
)
async def get_guide_history(
    outline_id: str,
    service: GuideStorageService = Depends(get_guide_storage_service),
) -> GuideHistoryResponse:
    """
    获取指南历史版本

    - **outline_id**: 大纲ID
    """
    try:
        # 验证UUID格式
        validate_uuid(outline_id)

        versions = service.get_history_versions(outline_id)

        return GuideHistoryResponse(
            success=True,
            outline_id=outline_id,
            versions=versions,
        )

    except ProcessingError as e:
        logger.error("获取历史版本失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except ValueError as e:
        logger.error("参数验证失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{outline_id}/restore",
    responses={
        200: {"description": "恢复成功"},
        400: {"description": "请求参数错误"},
        404: {"description": "历史版本不存在"},
        500: {"description": "服务器内部错误"},
    },
    summary="恢复历史版本",
    description="将指南恢复到指定的历史版本",
)
async def restore_guide_version(
    outline_id: str,
    version_file: str = Query(..., description="要恢复的历史版本文件名"),
    service: GuideStorageService = Depends(get_guide_storage_service),
) -> GuideResponse:
    """
    恢复历史版本

    - **outline_id**: 大纲ID
    - **version_file**: 要恢复的历史版本文件名
    """
    try:
        # 验证UUID格式
        validate_uuid(outline_id)

        # 恢复版本
        result = service.restore_version(outline_id, version_file)

        return GuideResponse(
            success=True,
            outline_id=result["outline_id"],
            file_path=result["file_path"],
            title=result["title"],
            content_length=result["content_length"],
            saved_at=result["saved_at"],
        )

    except ProcessingError as e:
        if "不存在" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        logger.error("恢复版本失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except ValueError as e:
        logger.error("参数验证失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{outline_id}",
    response_model=GuideDeleteResponse,
    responses={
        200: {"description": "删除成功"},
        500: {"description": "服务器内部错误"},
    },
    summary="删除指南",
    description="删除指定大纲的指南文件",
)
async def delete_guide(
    outline_id: str,
    delete_history: bool = Query(True, description="是否同时删除历史版本"),
    service: GuideStorageService = Depends(get_guide_storage_service),
) -> GuideDeleteResponse:
    """
    删除指南

    - **outline_id**: 大纲ID
    - **delete_history**: 是否同时删除历史版本（默认True）
    """
    try:
        # 验证UUID格式
        validate_uuid(outline_id)

        # 删除指南
        result = service.delete_guide(outline_id, delete_history=delete_history)

        logger.info(
            "指南删除API成功",
            outline_id=outline_id,
            deleted_count=result["deleted_count"],
        )

        return GuideDeleteResponse(
            success=True,
            outline_id=outline_id,
            deleted_count=result["deleted_count"],
            message="删除成功",
        )

    except ProcessingError as e:
        logger.error("删除指南失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    except ValueError as e:
        logger.error("参数验证失败", error=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/",
    response_model=GuideListResponse,
    responses={
        200: {"description": "获取成功"},
        500: {"description": "服务器内部错误"},
    },
    summary="列出所有指南",
    description="列出所有已保存的指南文件",
)
async def list_guides(
    include_content: bool = Query(False, description="是否包含内容"),
    service: GuideStorageService = Depends(get_guide_storage_service),
) -> GuideListResponse:
    """
    列出所有指南

    - **include_content**: 是否包含内容（默认False，仅返回基本信息）
    """
    try:
        guides = service.list_guides(include_content=include_content)

        return GuideListResponse(
            success=True,
            guides=guides,
            total=len(guides),
        )

    except Exception as e:
        logger.exception("列出指南失败", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"列出指南失败: {e}",
        ) from e
