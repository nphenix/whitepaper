"""
反馈模块API路由模块

提供用户反馈收集相关接口:
- POST /api/feedback: 提交用户反馈

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

from typing import Any

from fastapi import APIRouter

from src.interfaces.api.error_handlers import (
    create_error_response,
    create_error_response_from_exception,
    handle_errors,
    get_feedback_collector,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    UserFeedbackRequest,
    create_success_response,
)
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(tags=["用户反馈"])


@router.post(
    "/feedback",
    response_model=dict[str, Any],
    summary="提交用户反馈",
    description="收集用户对错误或功能的反馈(前端适配接口)",
)
@handle_errors(operation_name="提交用户反馈", log_level="info")
async def submit_feedback(
    request: UserFeedbackRequest,
) -> dict[str, Any]:
    """
    提交用户反馈接口(前端适配)

    用于收集用户对错误,功能或体验的反馈,帮助改进系统.

    Args:
        request: 用户反馈请求

    Returns:
        统一响应格式:{ success: bool, message?: str }
    """
    # 获取反馈收集器
    feedback_collector = get_feedback_collector()

    # 收集反馈(用户ID暂时使用固定值,后续版本从认证中获取)
    user_id = None  # TODO: 从认证中获取用户ID

    success = feedback_collector.collect_feedback(
        user_id=user_id,
        error_code=request.error_code,
        error_message=request.error_message,
        user_feedback=request.user_feedback,
        metadata=request.metadata,
    )

    if success:
        logger.info(
            "用户反馈收集成功",
            extra={
                "error_code": request.error_code,
                "feedback_length": len(request.user_feedback),
            },
        )
        return create_success_response(
            message="反馈已成功提交,感谢您的反馈!"
        )
    else:
        logger.warning("用户反馈收集失败")
        return create_error_response(
            "提交反馈失败",
            "无法保存反馈,请稍后重试"
        )


__all__ = ["router"]
