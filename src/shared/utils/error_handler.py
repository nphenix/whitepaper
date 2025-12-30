"""
生成命令: T022 错误处理和日志记录中间件
生成时间: 2025-12-09
来源: specs/001-multi-agent-doc-system/tasks.md

错误处理中间件模块

提供统一的Agent错误处理机制,基于LangChain 1.0的中间件系统.
支持错误捕获,分类,恢复和上报功能.
"""

import time
from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.runtime import Runtime

from src.shared.exceptions.agent_exceptions import (
    AgentExecutionError,
    AgentToolError,
    wrap_langchain_error,
)
from src.shared.utils.logging import get_logger, log_error, log_structured

logger = get_logger(__name__)


class ErrorHandlingMiddleware(AgentMiddleware):
    """错误处理中间件

    基于LangChain 1.0的AgentMiddleware实现,提供统一的错误处理机制:
    1. 捕获模型调用错误
    2. 捕获工具调用错误
    3. 错误分类和转换
    4. 错误恢复和重试
    5. 错误上报和日志记录

    使用示例:
        ```python
        from src.shared.utils.error_handler import ErrorHandlingMiddleware

        agent = create_agent(
            model='gpt-4o',
            tools=[...],
            middleware=[ErrorHandlingMiddleware(
                max_retries=3,
                retry_delay=1.0,
                enable_error_recovery=True
            )],
        )
        ```
    """

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        enable_error_recovery: bool = True,
        error_callback: Callable[[Exception, dict[str, Any]], None] | None = None,
    ):
        """初始化错误处理中间件

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
            enable_error_recovery: 是否启用错误恢复
            error_callback: 错误回调函数,用于错误上报
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.enable_error_recovery = enable_error_recovery
        self.error_callback = error_callback
        self._error_count = 0

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """包装模型调用,实现错误处理和重试

        Args:
            request: 模型请求
            handler: 模型调用处理器

        Returns:
            模型响应

        Raises:
            AgentExecutionError: 如果所有重试都失败
        """
        last_error: Exception | None = None
        agent_id = request.state.get("agent_id", "unknown")
        agent_name = request.state.get("agent_name", "UnknownAgent")

        for attempt in range(self.max_retries):
            try:
                # 执行模型调用
                response = handler(request)
                self._error_count = 0  # 重置错误计数
                return response

            except Exception as e:
                last_error = e
                self._error_count += 1

                # 记录错误日志
                log_error(
                    logger,
                    e,
                    context=f"Agent {agent_name} 模型调用失败 (尝试 {attempt + 1}/{self.max_retries})",
                    agent_id=agent_id,
                    agent_name=agent_name,
                    attempt=attempt + 1,
                    max_retries=self.max_retries,
                )

                # 如果是最后一次尝试,不再重试
                if attempt == self.max_retries - 1:
                    break

                # 等待后重试
                if self.retry_delay > 0:
                    time.sleep(self.retry_delay)

        # 所有重试都失败,包装错误并抛出
        if last_error:
            wrapped_error = self._wrap_error(
                last_error,
                agent_id=agent_id,
                agent_name=agent_name,
                error_type="model_call",
            )
            self._handle_error(wrapped_error, request.state)
            raise wrapped_error

        # 理论上不应该到达这里
        msg = "模型调用失败,未知错误"
        raise AgentExecutionError(msg)

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage],
    ) -> ToolMessage:
        """包装工具调用,实现错误处理和自定义错误消息

        Args:
            request: 工具请求
            handler: 工具调用处理器

        Returns:
            工具消息(ToolMessage)

        注意: 工具调用错误不会抛出异常,而是返回错误消息给模型
        """
        try:
            # 执行工具调用
            response = handler(request)
            return response

        except Exception as e:
            # 记录错误日志
            tool_call = request.tool_call
            tool_name = tool_call.get("name", "unknown")
            tool_args = tool_call.get("args", {})
            tool_call_id = tool_call.get("id", "unknown")

            # 从state中获取Agent信息(如果可用)
            state = getattr(request, "state", {})
            agent_id = (
                state.get("agent_id", "unknown")
                if isinstance(state, dict)
                else "unknown"
            )
            agent_name = (
                state.get("agent_name", "UnknownAgent")
                if isinstance(state, dict)
                else "UnknownAgent"
            )

            log_error(
                logger,
                e,
                context=f"Agent {agent_name} 工具调用失败",
                agent_id=agent_id,
                agent_name=agent_name,
                tool_name=tool_name,
                tool_args=tool_args,
            )

            # 包装错误
            wrapped_error = self._wrap_error(
                e,
                agent_id=agent_id,
                agent_name=agent_name,
                tool_name=tool_name,
                tool_args=tool_args,
                error_type="tool_call",
            )

            # 处理错误
            if isinstance(state, dict):
                self._handle_error(wrapped_error, state)

            # 返回友好的错误消息给模型,而不是抛出异常
            # 这样模型可以基于错误信息进行重试或调整
            error_message = self._format_tool_error_message(wrapped_error, tool_name)
            return ToolMessage(
                content=error_message,
                tool_call_id=tool_call_id,
            )

    def _wrap_error(
        self,
        error: Exception,
        agent_id: str | None = None,
        agent_name: str | None = None,
        tool_name: str | None = None,
        tool_args: dict[str, Any] | None = None,
        error_type: str = "unknown",
    ) -> AgentExecutionError:
        """包装错误为自定义异常

        Args:
            error: 原始异常
            agent_id: Agent ID
            agent_name: Agent名称
            tool_name: 工具名称(如果是工具错误)
            tool_args: 工具参数(如果是工具错误)
            error_type: 错误类型

        Returns:
            包装后的异常
        """
        # 检查是否是LangChain相关错误
        error_str = str(error).lower()
        if "langchain" in error_str or "langgraph" in error_str:
            return wrap_langchain_error(
                error,
                agent_name=agent_name,
                langchain_component=error_type,
            )

        # 如果是工具错误,使用AgentToolError
        if tool_name:
            return AgentToolError(
                f"工具调用失败: {error!s}",
                tool_name=tool_name,
                tool_args=tool_args,
                agent_id=agent_id,
                agent_name=agent_name,
            )

        # 其他错误使用AgentExecutionError
        return AgentExecutionError(
            f"Agent执行失败: {error!s}",
            agent_id=agent_id,
            agent_name=agent_name,
        )

    def _format_tool_error_message(
        self, error: AgentExecutionError, tool_name: str
    ) -> str:
        """格式化工具错误消息,返回给模型

        Args:
            error: 错误异常
            tool_name: 工具名称

        Returns:
            格式化的错误消息
        """
        error_type = error.details.get("error_type", "unknown")
        error_message = str(error)

        # 根据错误类型提供不同的错误消息
        error_message_map = {
            "timeout": "调用超时,请稍后重试.",
            "rate_limit": "调用达到速率限制,请稍后重试.",
            "authentication": "认证失败,请检查配置.",
            "model_unavailable": "依赖的模型不可用,请稍后重试.",
        }
        if error_type in error_message_map:
            return f"工具 {tool_name} {error_message_map[error_type]}"
        return f"工具 {tool_name} 调用失败: {error_message}.请检查输入参数或稍后重试."

    def _handle_error(self, error: AgentExecutionError, state: AgentState) -> None:
        """处理错误(上报,记录等)

        Args:
            error: 错误异常
            state: Agent状态
        """
        # 记录结构化错误日志
        log_structured(
            logger,
            "ERROR",
            f"Agent错误处理: {error!s}",
            error_type=type(error).__name__,
            error_message=str(error),
            error_details=error.details,
            agent_id=state.get("agent_id"),
            agent_name=state.get("agent_name"),
            error_count=self._error_count,
        )

        # 调用错误回调(如果配置)
        if self.error_callback:
            try:
                self.error_callback(error, state)
            except Exception as callback_error:
                logger.warning("错误回调执行失败: %s", callback_error, exc_info=True)

    def before_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """在模型调用前执行

        Args:
            state: Agent状态
            runtime: 运行时

        Returns:
            状态更新(可选)
        """
        # 可以在这里添加错误恢复逻辑
        # 例如:检查之前的错误,决定是否继续执行
        if self.enable_error_recovery and self._error_count > 0:
            logger.info(
                "Agent %s 错误恢复检查: 错误计数=%d",
                state.get("agent_name", "Unknown"),
                self._error_count,
            )

        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """在模型调用后执行

        Args:
            state: Agent状态
            runtime: 运行时

        Returns:
            状态更新(可选)
        """
        # 如果模型调用成功,可以重置错误计数
        if self._error_count > 0:
            logger.info(
                "Agent %s 模型调用成功,重置错误计数",
                state.get("agent_name", "Unknown"),
            )
            self._error_count = 0

        return None


def create_error_handling_middleware(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    enable_error_recovery: bool = True,
    error_callback: Callable[[Exception, dict[str, Any]], None] | None = None,
) -> ErrorHandlingMiddleware:
    """创建错误处理中间件的便捷函数

    Args:
        max_retries: 最大重试次数
        retry_delay: 重试延迟(秒)
        enable_error_recovery: 是否启用错误恢复
        error_callback: 错误回调函数

    Returns:
        错误处理中间件实例
    """
    return ErrorHandlingMiddleware(
        max_retries=max_retries,
        retry_delay=retry_delay,
        enable_error_recovery=enable_error_recovery,
        error_callback=error_callback,
    )
