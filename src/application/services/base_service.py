"""
服务基类

提供所有服务类的通用功能,包括:
- 统一的错误处理模式
- 资源存在性检查
- 日志记录
- 异常转换

遵循SOLID原则中的单一职责原则和开闭原则.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
from src.shared.exceptions.base_exceptions import (
    ResourceNotFoundError,
    ValidationError,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class BaseService(ABC):
    """
    服务基类

    提供所有服务类的通用功能,遵循DRY原则消除重复代码.
    """

    @abstractmethod
    def get_service_name(self) -> str:
        """
        获取服务名称

        Returns:
            服务名称字符串
        """
        msg = "子类必须实现 get_service_name 方法"
        raise NotImplementedError(msg)

    def __init__(self, connection_manager=None):
        """
        初始化服务基类

        Args:
            connection_manager: SQLite连接管理器,如果为None则使用默认连接
        """
        self._connection_manager = connection_manager
        logger.debug(f"{self.__class__.__name__} 初始化完成")

    def _get_or_create_adapter(
        self,
        table_name: str,
        id_field: str = "id",
        created_at_field: str = "created_at",
        updated_at_field: str = "updated_at",
    ) -> SQLiteAdapter:
        """
        获取或创建SQLiteAdapter实例

        这是一个工厂方法,用于统一创建适配器实例.

        Args:
            table_name: 表名
            id_field: ID字段名
            created_at_field: 创建时间字段名
            updated_at_field: 更新时间字段名

        Returns:
            SQLiteAdapter实例
        """
        return SQLiteAdapter(
            table_name=table_name,
            connection_manager=self._connection_manager,
            id_field=id_field,
            created_at_field=created_at_field,
            updated_at_field=updated_at_field,
        )

    def _get_resource_or_raise(
        self,
        adapter: SQLiteAdapter,
        resource_id: str,
        resource_type: str,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """
        获取资源,如果不存在则抛出ResourceNotFoundError

        这是一个通用的资源获取方法,遵循DRY原则.

        Args:
            adapter: SQLiteAdapter实例
            resource_id: 资源ID
            resource_type: 资源类型(用于错误消息)
            error_message: 自定义错误消息,如果为None则使用默认消息

        Returns:
            资源字典

        Raises:
            ResourceNotFoundError: 资源不存在时抛出
        """
        resource = adapter.get_by_id(resource_id)
        if not resource:
            error_msg = error_message or f"{resource_type}不存在: {resource_id}"
            logger.warning(error_msg)
            raise ResourceNotFoundError(
                error_msg, resource_type=resource_type, resource_id=resource_id
            )
        return resource

    def _handle_service_error(
        self,
        operation_name: str,
        error: Exception,
        *,
        re_raise: type[Exception] | tuple[type[Exception], ...] | None = None,
        default_exception: type[Exception] = ValidationError,
    ) -> None:
        """
        统一的错误处理方法

        封装了通用的错误处理模式:记录日志,转换异常类型.

        Args:
            operation_name: 操作名称(用于日志)
            error: 捕获的异常
            re_raise: 如果异常是此类型,则直接重新抛出
            default_exception: 默认的异常类型,如果re_raise不匹配则抛出此类型

        Raises:
            Exception: 根据re_raise和default_exception参数抛出相应异常
        """
        if re_raise:
            if isinstance(re_raise, tuple):
                if isinstance(error, re_raise):
                    raise
            elif isinstance(error, re_raise):
                raise

        error_msg = f"{operation_name}失败: {error}"
        logger.error(error_msg)
        raise default_exception(error_msg) from error

    def _execute_with_error_handling(
        self,
        operation: Callable[[], T],
        operation_name: str,
        *,
        re_raise: tuple[type[Exception], ...] | type[Exception] | None = None,
        default_exception: type[Exception] = ValidationError,
    ) -> T:
        """
        执行操作并统一处理错误

        这是一个装饰器模式的应用,用于统一错误处理.

        Args:
            operation: 要执行的操作(无参数函数)
            operation_name: 操作名称(用于日志和错误消息)
            re_raise: 如果异常是这些类型,则直接重新抛出
            default_exception: 默认的异常类型

        Returns:
            操作的返回值

        Raises:
            Exception: 根据re_raise和default_exception参数抛出相应异常
        """
        try:
            return operation()
        except Exception as e:
            if re_raise:
                if isinstance(re_raise, tuple):
                    if isinstance(e, re_raise):
                        raise
                elif isinstance(e, re_raise):
                    raise

            self._handle_service_error(
                operation_name, e, re_raise=re_raise, default_exception=default_exception
            )

