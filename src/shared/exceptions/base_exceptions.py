# 生成命令: T010 自定义异常类实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
基础异常类模块

提供系统级的基础异常类, 用于统一的错误处理.
所有自定义异常都应该继承自这些基础异常类。
"""

from typing import Any


class BaseApplicationError(Exception):
    """应用基础异常类

    所有自定义异常的基类, 提供统一的异常处理接口.
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
    ):
        """初始化基础异常

        Args:
            message: 错误消息
            error_code: 错误代码, 用于程序化处理
            details: 错误详细信息字典
            original_error: 原始异常对象, 用于异常链
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.original_error = original_error

    def __str__(self) -> str:
        """返回异常的字符串表示"""
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """将异常转换为字典格式, 便于序列化

        Returns:
            包含异常信息的字典
        """
        result = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "details": self.details,
        }

        if self.original_error:
            result["original_error"] = {
                "type": self.original_error.__class__.__name__,
                "message": str(self.original_error),
            }

        return result


class ConfigurationError(BaseApplicationError):
    """配置错误异常

    当系统配置不正确或缺失时抛出。
    """

    def __init__(self, message: str, config_key: str | None = None, **kwargs):
        """初始化配置错误

        Args:
            message: 错误消息
            config_key: 相关的配置键名
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if config_key:
            self.details["config_key"] = config_key


class ValidationError(BaseApplicationError):
    """验证错误异常

    当数据验证失败时抛出。
    """

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        field_value: Any | None = None,
        **kwargs,
    ):
        """初始化验证错误

        Args:
            message: 错误消息
            field_name: 验证失败的字段名
            field_value: 验证失败的字段值
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if field_name:
            self.details["field_name"] = field_name
        if field_value is not None:
            self.details["field_value"] = field_value


class BusinessLogicError(BaseApplicationError):
    """业务逻辑错误异常

    当业务规则被违反时抛出。
    """

    def __init__(self, message: str, business_rule: str | None = None, **kwargs):
        """初始化业务逻辑错误

        Args:
            message: 错误消息
            business_rule: 违反的业务规则描述
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if business_rule:
            self.details["business_rule"] = business_rule


class ResourceNotFoundError(BaseApplicationError):
    """资源未找到错误异常

    当请求的资源不存在时抛出。
    """

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        resource_id: str | None = None,
        **kwargs,
    ):
        """初始化资源未找到错误

        Args:
            message: 错误消息
            resource_type: 资源类型
            resource_id: 资源ID
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id:
            self.details["resource_id"] = resource_id


class CustomPermissionError(BaseApplicationError):
    """权限错误异常

    当用户权限不足时抛出。
    """

    def __init__(self, message: str, required_permission: str | None = None, **kwargs):
        """初始化权限错误

        Args:
            message: 错误消息
            required_permission: 需要的权限
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if required_permission:
            self.details["required_permission"] = required_permission


class CustomTimeoutError(BaseApplicationError):
    """超时错误异常

    当操作超时时抛出。
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: float | None = None,
        operation: str | None = None,
        **kwargs,
    ):
        """初始化超时错误

        Args:
            message: 错误消息
            timeout_seconds: 超时时间(秒)
            operation: 超时的操作
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if timeout_seconds is not None:
            self.details["timeout_seconds"] = timeout_seconds
        if operation:
            self.details["operation"] = operation


class RateLimitError(BaseApplicationError):
    """速率限制错误异常

    当请求超过速率限制时抛出。
    """

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
        limit: int | None = None,
        **kwargs,
    ):
        """初始化速率限制错误

        Args:
            message: 错误消息
            retry_after: 建议重试等待时间(秒)
            limit: 速率限制数量
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if retry_after is not None:
            self.details["retry_after"] = retry_after
        if limit is not None:
            self.details["limit"] = limit


class ProcessingError(BaseApplicationError):
    """处理错误异常

    当数据处理过程中出现错误时抛出。
    """

    def __init__(
        self,
        message: str,
        processing_step: str | None = None,
        resource_id: str | None = None,
        **kwargs,
    ):
        """初始化处理错误

        Args:
            message: 错误消息
            processing_step: 处理步骤名称
            resource_id: 相关资源ID
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if processing_step:
            self.details["processing_step"] = processing_step
        if resource_id:
            self.details["resource_id"] = resource_id
