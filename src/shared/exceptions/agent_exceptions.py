# 生成命令: T010 自定义异常类实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
Agent相关异常类模块

提供Agent执行过程中的异常处理, 包括LangChain异常的包装和转换。
"""

from typing import Any

from .base_exceptions import BaseApplicationError


class AgentError(BaseApplicationError):
    """Agent基础异常类

    所有Agent相关异常的基类。
    """

    def __init__(
        self,
        message: str,
        agent_name: str | None = None,
        agent_id: str | None = None,
        **kwargs,
    ):
        """初始化Agent错误

        Args:
            message: 错误消息
            agent_name: Agent名称
            agent_id: Agent ID
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if agent_name:
            self.details["agent_name"] = agent_name
        if agent_id:
            self.details["agent_id"] = agent_id


class AgentExecutionError(AgentError):
    """Agent执行错误异常

    当Agent执行过程中发生错误时抛出。
    """

    def __init__(
        self,
        message: str,
        execution_id: str | None = None,
        step: str | None = None,
        **kwargs,
    ):
        """初始化Agent执行错误

        Args:
            message: 错误消息
            execution_id: 执行ID
            step: 执行步骤
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if execution_id:
            self.details["execution_id"] = execution_id
        if step:
            self.details["step"] = step


class LangChainError(AgentExecutionError):
    """LangChain相关异常

    用于包装和转换LangChain异常。
    """

    def __init__(
        self,
        message: str,
        original_error: Exception,
        langchain_component: str | None = None,
        **kwargs,
    ):
        """初始化LangChain错误

        Args:
            message: 错误消息
            original_error: 原始LangChain异常
            langchain_component: 相关的LangChain组件
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, original_error=original_error, **kwargs)
        if langchain_component:
            self.details["langchain_component"] = langchain_component

        # 添加LangChain特定的错误信息
        self._extract_langchain_error_info(original_error)

    def _extract_langchain_error_info(self, error: Exception) -> None:
        """从LangChain异常中提取特定信息

        Args:
            error: LangChain异常对象
        """
        error_str = str(error).lower()

        # 检查是否是超时错误
        if "timeout" in error_str:
            self.details["error_type"] = "timeout"
            return

        # 检查是否是速率限制错误
        if "rate limit" in error_str:
            self.details["error_type"] = "rate_limit"
            return

        # 检查是否是API密钥错误
        if "api key" in error_str or "authentication" in error_str:
            self.details["error_type"] = "authentication"
            return

        # 检查是否是模型不可用错误
        if "model" in error_str and (
            "not found" in error_str
            or "unavailable" in error_str
            or "not available" in error_str
        ):
            self.details["error_type"] = "model_unavailable"
            return


class AgentToolError(AgentExecutionError):
    """Agent工具调用错误异常

    当Agent调用工具时发生错误时抛出。
    """

    def __init__(
        self,
        message: str,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        **kwargs,
    ):
        """初始化Agent工具错误

        Args:
            message: 错误消息
            tool_name: 工具名称
            tool_args: 工具调用参数
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if tool_name:
            self.details["tool_name"] = tool_name
        if tool_args:
            self.details["tool_args"] = tool_args


class AgentInputError(AgentError):
    """Agent输入错误异常

    当Agent输入验证失败时抛出。
    """

    def __init__(
        self,
        message: str,
        input_field: str | None = None,
        input_value: Any | None = None,
        validation_rule: str | None = None,
        **kwargs,
    ):
        """初始化Agent输入错误

        Args:
            message: 错误消息
            input_field: 输入字段名
            input_value: 输入值
            validation_rule: 验证规则
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if input_field:
            self.details["input_field"] = input_field
        if input_value is not None:
            self.details["input_value"] = input_value
        if validation_rule:
            self.details["validation_rule"] = validation_rule


class AgentStateError(AgentError):
    """Agent状态错误异常

    当Agent处于不正确的状态时抛出。
    """

    def __init__(
        self,
        message: str,
        current_state: str | None = None,
        expected_state: str | list[str] | None = None,
        **kwargs,
    ):
        """初始化Agent状态错误

        Args:
            message: 错误消息
            current_state: 当前状态
            expected_state: 期望状态
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if current_state:
            self.details["current_state"] = current_state
        if expected_state:
            self.details["expected_state"] = expected_state


class AgentConfigurationError(AgentError):
    """Agent配置错误异常

    当Agent配置不正确时抛出。
    """

    def __init__(
        self,
        message: str,
        config_key: str | None = None,
        config_value: Any | None = None,
        **kwargs,
    ):
        """初始化Agent配置错误

        Args:
            message: 错误消息
            config_key: 配置键名
            config_value: 配置值
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if config_key:
            self.details["config_key"] = config_key
        if config_value is not None:
            self.details["config_value"] = config_value


class AgentMemoryError(AgentError):
    """Agent内存错误异常

    当Agent内存操作失败时抛出。
    """

    def __init__(
        self,
        message: str,
        memory_operation: str | None = None,
        memory_key: str | None = None,
        **kwargs,
    ):
        """初始化Agent内存错误

        Args:
            message: 错误消息
            memory_operation: 内存操作类型
            memory_key: 内存键名
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if memory_operation:
            self.details["memory_operation"] = memory_operation
        if memory_key:
            self.details["memory_key"] = memory_key


class AgentCallbackError(AgentError):
    """Agent回调错误异常

    当Agent回调函数执行失败时抛出。
    """

    def __init__(
        self,
        message: str,
        callback_name: str | None = None,
        callback_event: str | None = None,
        **kwargs,
    ):
        """初始化Agent回调错误

        Args:
            message: 错误消息
            callback_name: 回调函数名
            callback_event: 回调事件类型
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if callback_name:
            self.details["callback_name"] = callback_name
        if callback_event:
            self.details["callback_event"] = callback_event


def wrap_langchain_error(
    error: Exception,
    message: str | None = None,
    agent_name: str | None = None,
    langchain_component: str | None = None,
    **kwargs,
) -> LangChainError:
    """包装LangChain异常为自定义异常

    Args:
        error: 原始LangChain异常
        message: 自定义错误消息, 如果为None则使用原始异常消息
        agent_name: Agent名称
        langchain_component: LangChain组件名称
        **kwargs: 传递给异常的其他参数

    Returns:
        包装后的LangChainError异常
    """
    if message is None:
        message = f"LangChain操作失败: {error!s}"

    return LangChainError(
        message=message,
        original_error=error,
        agent_name=agent_name,
        langchain_component=langchain_component,
        **kwargs,
    )


class AgentTimeoutError(AgentExecutionError):
    """Agent超时异常

    当Agent执行超过配置的超时时间时抛出。
    """

    def __init__(
        self,
        message: str,
        timeout_seconds: int | None = None,
        execution_id: str | None = None,
        **kwargs,
    ):
        """初始化Agent超时错误

        Args:
            message: 错误消息
            timeout_seconds: 超时时间(秒)
            execution_id: 执行ID
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, execution_id=execution_id, **kwargs)
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds


class AgentOrchestrationError(AgentError):
    """Agent编排异常

    当Agent编排过程中发生错误时抛出。
    """

    def __init__(
        self,
        message: str,
        plan_id: str | None = None,
        orchestration_step: str | None = None,
        failed_agents: list[str] | None = None,
        **kwargs,
    ):
        """初始化Agent编排错误

        Args:
            message: 错误消息
            plan_id: 编排计划ID
            orchestration_step: 编排步骤
            failed_agents: 失败的Agent列表
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if plan_id:
            self.details["plan_id"] = plan_id
        if orchestration_step:
            self.details["orchestration_step"] = orchestration_step
        if failed_agents:
            self.details["failed_agents"] = failed_agents
