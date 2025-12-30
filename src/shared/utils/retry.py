"""
通用重试工具模块

提供可复用的重试机制,支持指数退避,429错误特殊处理等.
遵循DRY原则,消除重复的重试逻辑.

生成命令: 架构重构
生成时间: 2025-01-XX
来源: 架构质量提升
"""

import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 3.0,
        rate_limit_delay: float = 30.0,
        exponential_base: float = 2.0,
    ):
        """
        初始化重试配置

        Args:
            max_retries: 最大重试次数
            retry_delay: 标准重试延迟(秒)
            rate_limit_delay: 429错误的重试延迟(秒)
            exponential_base: 指数退避的底数
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit_delay = rate_limit_delay
        self.exponential_base = exponential_base


class RetryHandler:
    """重试处理器"""

    def __init__(self, config: RetryConfig | None = None):
        """
        初始化重试处理器

        Args:
            config: 重试配置,如果为None则使用默认配置
        """
        self.config = config or RetryConfig()

    def is_rate_limit_error(self, error: Exception) -> bool:
        """判断是否为429错误(并发限制)

        Args:
            error: 异常对象

        Returns:
            是否为429错误
        """
        error_str = str(error).lower()
        return any(
            keyword in error_str
            for keyword in ["429", "too many requests", "并发", "rate limit"]
        )

    def calculate_wait_time(self, attempt: int, is_rate_limit: bool) -> float:
        """计算等待时间

        Args:
            attempt: 当前尝试次数(从0开始)
            is_rate_limit: 是否为429错误

        Returns:
            等待时间(秒)
        """
        if is_rate_limit:
            # 429错误使用更长的等待时间
            return self.config.rate_limit_delay * (
                self.config.exponential_base**attempt
            )
        else:
            # 其他错误使用标准指数退避
            return self.config.retry_delay * (self.config.exponential_base**attempt)

    def execute_with_retry(
        self,
        func: Callable[[], T],
        operation_name: str = "操作",
        on_retry: Callable[[int, Exception], None] | None = None,
    ) -> T:
        """执行函数并自动重试

        Args:
            func: 要执行的函数(无参数)
            operation_name: 操作名称(用于日志)
            on_retry: 重试时的回调函数,接收(attempt, error)参数

        Returns:
            函数返回值

        Raises:
            Exception: 所有重试都失败时抛出最后一个异常
        """
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries):
            try:
                logger.debug(
                    f"{operation_name}开始(尝试 {attempt + 1}/{self.config.max_retries})..."
                )
                return func()
            except Exception as e:
                last_error = e

                if attempt < self.config.max_retries - 1:
                    is_rate_limit = self.is_rate_limit_error(e)
                    wait_time = self.calculate_wait_time(attempt, is_rate_limit)

                    logger.warning(
                        f"{operation_name}失败(尝试 {attempt + 1}/{self.config.max_retries}): {e},"
                        f"等待 {wait_time:.2f} 秒后重试..."
                    )

                    # 调用重试回调
                    if on_retry:
                        on_retry(attempt, e)

                    time.sleep(wait_time)
                else:
                    logger.error(
                        f"{operation_name}失败,已重试 {self.config.max_retries} 次: {e}"
                    )

        # 所有重试都失败
        if last_error:
            raise last_error
        msg = f"{operation_name}失败,未知错误"
        raise Exception(msg)


def retry_with_config(
    config: RetryConfig | None = None,
    operation_name: str = "操作",
):
    """重试装饰器

    Args:
        config: 重试配置
        operation_name: 操作名称(用于日志)

    Returns:
        装饰器函数
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            handler = RetryHandler(config)
            return handler.execute_with_retry(
                lambda: func(*args, **kwargs),
                operation_name=operation_name,
            )

        return wrapper

    return decorator


# 默认重试处理器实例
_default_retry_handler = RetryHandler()


def retry[T](
    func: Callable[..., T],
    config: RetryConfig | None = None,
    operation_name: str = "操作",
) -> T:
    """执行函数并自动重试(函数式接口)

    Args:
        func: 要执行的函数
        config: 重试配置
        operation_name: 操作名称(用于日志)

    Returns:
        函数返回值
    """
    handler = RetryHandler(config) if config else _default_retry_handler
    return handler.execute_with_retry(
        func,
        operation_name=operation_name,
    )
