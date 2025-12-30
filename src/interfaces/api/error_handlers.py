"""
适配层统一错误处理模块

提供统一的错误处理机制,包括:
- 异常到HTTP状态码的映射
- 友好的错误消息生成
- 错误日志记录
- 用户反馈收集支持

生成命令: /speckit.implement T246
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import functools
import traceback
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status

from src.interfaces.api.schemas.frontend_adapter_schemas import create_error_response
from src.shared.exceptions.base_exceptions import (
    BaseApplicationError,
    BusinessLogicError,
    ConfigurationError,
    CustomPermissionError,
    CustomTimeoutError,
    ProcessingError,
    RateLimitError,
    ResourceNotFoundError,
    ValidationError,
)
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 类型变量
F = TypeVar("F", bound=Callable[..., Any])


# === 异常到HTTP状态码的映射 ===

EXCEPTION_STATUS_MAP: dict[type[BaseApplicationError], int] = {
    ResourceNotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_400_BAD_REQUEST,
    BusinessLogicError: status.HTTP_400_BAD_REQUEST,
    CustomPermissionError: status.HTTP_403_FORBIDDEN,
    CustomTimeoutError: status.HTTP_408_REQUEST_TIMEOUT,
    RateLimitError: status.HTTP_429_TOO_MANY_REQUESTS,
    ProcessingError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    BaseApplicationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
}

# === 友好的错误消息映射 ===

FRIENDLY_MESSAGES: dict[str, str] = {
    "ResourceNotFoundError": "请求的资源不存在",
    "ValidationError": "请求参数验证失败",
    "BusinessLogicError": "业务规则验证失败",
    "CustomPermissionError": "权限不足",
    "CustomTimeoutError": "操作超时,请稍后重试",
    "RateLimitError": "请求过于频繁,请稍后重试",
    "ProcessingError": "数据处理失败",
    "ConfigurationError": "系统配置错误",
    "BaseApplicationError": "系统内部错误",
    "ValueError": "参数值无效",
    "TypeError": "参数类型错误",
    "KeyError": "缺少必需的参数",
    "AttributeError": "对象属性错误",
    "FileNotFoundError": "文件不存在",
    "PermissionError": "文件权限不足",
    "ConnectionError": "网络连接失败",
    "TimeoutError": "操作超时",
}


def get_friendly_message(exception: Exception) -> str:
    """获取友好的错误消息

    Args:
        exception: 异常对象

    Returns:
        友好的错误消息
    """
    exception_type = type(exception).__name__

    # 优先使用异常的自定义消息
    if isinstance(exception, BaseApplicationError):
        return exception.message

    # 使用预定义的友好消息
    if exception_type in FRIENDLY_MESSAGES:
        base_message = FRIENDLY_MESSAGES[exception_type]
        # 如果有详细信息,追加到基础消息
        if str(exception) and str(exception) != exception_type:
            return f"{base_message}: {exception!s}"
        return base_message

    # 默认消息
    return f"操作失败: {exception!s}"


def get_http_status_code(exception: Exception) -> int:
    """获取异常对应的HTTP状态码

    Args:
        exception: 异常对象

    Returns:
        HTTP状态码
    """
    # 如果是HTTPException,直接返回其状态码
    if isinstance(exception, HTTPException):
        return exception.status_code

    # 查找异常类型对应的状态码
    exception_type = type(exception)
    for exc_class, status_code in EXCEPTION_STATUS_MAP.items():
        if issubclass(exception_type, exc_class):
            return status_code

    # 默认返回500
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def get_error_code(exception: Exception) -> str | None:
    """获取错误代码

    Args:
        exception: 异常对象

    Returns:
        错误代码(如果有)
    """
    if isinstance(exception, BaseApplicationError):
        return exception.error_code

    # 根据异常类型生成错误代码
    exception_type = type(exception).__name__
    error_code_map = {
        "ResourceNotFoundError": "RESOURCE_NOT_FOUND",
        "ValidationError": "VALIDATION_ERROR",
        "BusinessLogicError": "BUSINESS_LOGIC_ERROR",
        "CustomPermissionError": "PERMISSION_DENIED",
        "CustomTimeoutError": "TIMEOUT_ERROR",
        "RateLimitError": "RATE_LIMIT_EXCEEDED",
        "ProcessingError": "PROCESSING_ERROR",
        "ConfigurationError": "CONFIGURATION_ERROR",
        "ValueError": "INVALID_VALUE",
        "TypeError": "INVALID_TYPE",
        "KeyError": "MISSING_KEY",
        "FileNotFoundError": "FILE_NOT_FOUND",
        "PermissionError": "PERMISSION_DENIED",
        "ConnectionError": "CONNECTION_ERROR",
        "TimeoutError": "TIMEOUT_ERROR",
    }

    return error_code_map.get(exception_type, "UNKNOWN_ERROR")


# === 错误处理装饰器 ===


def handle_errors(
    operation_name: str | None = None,
    log_level: str = "error",
    include_traceback: bool = False,
) -> Callable[[F], F]:
    """错误处理装饰器

    自动捕获异常并转换为统一的错误响应格式.

    Args:
        operation_name: 操作名称(用于日志记录)
        log_level: 日志级别("error", "warning", "info")
        include_traceback: 是否在响应中包含堆栈跟踪(仅开发环境)

    Returns:
        装饰器函数

    示例:
        @handle_errors(operation_name="创建大纲")
        async def create_outline(...):
            ...
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            # 获取操作名称
            op_name = operation_name or func.__name__

            try:
                # 执行原函数
                result = await func(*args, **kwargs)
                return result

            except BaseApplicationError as e:
                # 应用层异常,记录警告或错误
                get_http_status_code(e)
                error_code = get_error_code(e)
                friendly_message = get_friendly_message(e)

                # 记录日志
                log_message = f"{op_name}失败: {friendly_message}"
                if log_level == "warning":
                    logger.warning(
                        log_message,
                        extra={
                            "error_code": error_code,
                            "exception_type": type(e).__name__,
                            "details": e.details,
                        },
                    )
                else:
                    logger.error(
                        log_message,
                        extra={
                            "error_code": error_code,
                            "exception_type": type(e).__name__,
                            "details": e.details,
                        },
                        exc_info=True,
                    )

                # 构建错误响应
                error_response = create_error_response(
                    error=friendly_message,
                    details=str(e) if include_traceback else None,
                    error_code=error_code,
                )

                # 如果是HTTPException,直接抛出(让FastAPI处理)
                if isinstance(e, HTTPException):
                    raise e

                # 返回错误响应(适配层统一格式)
                return error_response

            except HTTPException as e:
                # FastAPI HTTP异常,直接抛出
                raise e

            except Exception as e:
                # 未预期的异常,记录错误日志
                get_http_status_code(e)
                error_code = get_error_code(e)
                friendly_message = get_friendly_message(e)

                logger.exception(
                    f"{op_name}发生未预期的异常: {friendly_message}",
                    extra={
                        "error_code": error_code,
                        "exception_type": type(e).__name__,
                        "traceback": traceback.format_exc() if include_traceback else None,
                    },
                )

                # 构建错误响应
                error_response = create_error_response(
                    error=friendly_message,
                    details=traceback.format_exc() if include_traceback else None,
                    error_code=error_code,
                )

                return error_response

        return wrapper  # type: ignore

    return decorator


# === 错误响应生成器 ===


def create_error_response_from_exception(
    exception: Exception,
    include_traceback: bool = False,
) -> dict[str, Any]:
    """从异常创建错误响应

    Args:
        exception: 异常对象
        include_traceback: 是否包含堆栈跟踪

    Returns:
        错误响应字典
    """
    friendly_message = get_friendly_message(exception)
    error_code = get_error_code(exception)
    details = None

    if include_traceback:
        details = traceback.format_exc()

    return create_error_response(
        error=friendly_message,
        details=details,
        error_code=error_code,
    )


# === 用户反馈收集支持 ===


class FeedbackCollector:
    """用户反馈收集器

    用于收集用户对错误或功能的反馈.
    """

    def __init__(self):
        """初始化反馈收集器"""
        self._feedback_storage = None

    def collect_feedback(
        self,
        user_id: str | None,
        error_code: str | None,
        error_message: str,
        user_feedback: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """收集用户反馈

        Args:
            user_id: 用户ID(可选)
            error_code: 错误代码
            error_message: 错误消息
            user_feedback: 用户反馈内容
            metadata: 额外的元数据

        Returns:
            是否成功收集
        """
        try:
            # 记录反馈日志
            logger.info(
                "收集用户反馈",
                extra={
                    "user_id": user_id,
                    "error_code": error_code,
                    "error_message": error_message,
                    "user_feedback": user_feedback,
                    "metadata": metadata,
                },
            )

            # TODO: 实现反馈存储逻辑(可选)
            # 可以存储到数据库,文件或发送到外部服务
            # if self._feedback_storage:
            #     self._feedback_storage.save(...)

            return True

        except Exception as e:
            logger.warning(f"收集用户反馈失败: {e}")
            return False


# 全局反馈收集器实例
_feedback_collector: FeedbackCollector | None = None


def get_feedback_collector() -> FeedbackCollector:
    """获取反馈收集器实例

    Returns:
        反馈收集器实例
    """
    global _feedback_collector
    if _feedback_collector is None:
        _feedback_collector = FeedbackCollector()
    return _feedback_collector

