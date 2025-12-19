"""
生成命令: T022 错误处理和日志记录中间件
生成时间: 2025-12-09
来源: specs/001-multi-agent-doc-system/tasks.md

Agent日志记录中间件模块

提供统一的Agent日志记录机制,基于LangChain 1.0的中间件系统。
记录Agent执行的生命周期事件、输入输出、性能指标等。
"""

import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime

from .logging import (
    LogLevel,
    get_logger,
    log_performance,
    log_structured,
)

logger = get_logger(__name__)


class AgentLoggingMiddleware(AgentMiddleware):
    """Agent日志记录中间件

    基于LangChain 1.0的AgentMiddleware实现,提供统一的日志记录机制:
    1. 记录Agent执行的生命周期事件
    2. 记录输入参数、中间状态、输出结果
    3. 记录执行时间和性能指标
    4. 支持结构化日志输出

    使用示例:
        ```python
        from src.shared.utils.agent_logging_middleware import AgentLoggingMiddleware

        agent = create_agent(
            model='gpt-4o',
            tools=[...],
            middleware=[AgentLoggingMiddleware(
                log_level='INFO',
                log_input=True,
                log_output=True,
                log_performance=True
            )],
        )
        ```
    """

    def __init__(
        self,
        log_level: str | LogLevel = LogLevel.INFO,
        log_input: bool = True,
        log_output: bool = True,
        log_performance: bool = True,
        log_state: bool = False,
        include_tool_calls: bool = True,
        enable_streaming_events: bool = True,
        enable_token_tracking: bool = True,
    ):
        """初始化日志记录中间件

        Args:
            log_level: 日志级别
            log_input: 是否记录输入
            log_output: 是否记录输出
            log_performance: 是否记录性能指标
            log_state: 是否记录完整状态(可能包含敏感信息)
            include_tool_calls: 是否记录工具调用
            enable_streaming_events: 是否启用流式事件记录(工具调用开始/结束)
            enable_token_tracking: 是否启用token使用量追踪
        """
        if isinstance(log_level, str):
            self.log_level = LogLevel[log_level.upper()]
        else:
            self.log_level = log_level

        self.log_input = log_input
        self.log_output = log_output
        self.log_performance = log_performance
        self.log_state = log_state
        self.include_tool_calls = include_tool_calls
        self.enable_streaming_events = enable_streaming_events
        self.enable_token_tracking = enable_token_tracking

        # 性能追踪
        self._start_times: dict[str, float] = {}
        self._execution_count = 0

        # 工具调用追踪(用于流式事件)
        self._tool_call_times: dict[str, dict[str, float]] = (
            {}
        )  # {execution_id: {tool_name: start_time}}
        self._tool_call_count: dict[str, int] = {}  # {execution_id: count}

        # Token使用量追踪
        self._token_usage: dict[str, dict[str, int]] = (
            {}
        )  # {execution_id: {input_tokens, output_tokens, total_tokens}}

    def before_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """在模型调用前执行,记录输入和开始时间

        Args:
            state: Agent状态
            runtime: 运行时

        Returns:
            状态更新(可选)
        """
        agent_id = state.get("agent_id", "unknown")
        agent_name = state.get("agent_name", "UnknownAgent")
        execution_id = state.get("execution_id", f"exec-{self._execution_count}")

        # 记录开始时间
        start_time = time.time()
        self._start_times[execution_id] = start_time
        self._execution_count += 1

        # 记录Agent开始执行
        log_structured(
            logger,
            self.log_level,
            "Agent %s 开始执行",
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            event="agent_start",
        )

        # 记录输入(如果启用)
        if self.log_input:
            messages = state.get("messages", [])
            input_data = {
                "message_count": len(messages),
                "last_message": (str(messages[-1].content[:200]) if messages else None),
            }

            log_structured(
                logger,
                self.log_level,
                "Agent %s 输入数据",
                agent_id=agent_id,
                agent_name=agent_name,
                execution_id=execution_id,
                event="agent_input",
                **input_data,
            )

        # 记录状态(如果启用且不包含敏感信息)
        if self.log_state:
            # 只记录非敏感的状态信息
            safe_state = {
                k: v
                for k, v in state.items()
                if k not in {"api_key", "password", "secret", "token"}
            }
            log_structured(
                logger,
                self.log_level,
                "Agent %s 状态",
                agent_id=agent_id,
                agent_name=agent_name,
                execution_id=execution_id,
                event="agent_state",
                state=safe_state,
            )

        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """在模型调用后执行,记录输出和性能指标

        Args:
            state: Agent状态
            runtime: 运行时

        Returns:
            状态更新(可选)
        """
        agent_id = state.get("agent_id", "unknown")
        agent_name = state.get("agent_name", "UnknownAgent")
        execution_id = state.get("execution_id", f"exec-{self._execution_count - 1}")

        # 计算执行时间
        start_time = self._start_times.pop(execution_id, None)
        duration = time.time() - start_time if start_time else 0.0

        # 尝试从模型响应中提取token使用量(如果启用)
        if self.enable_token_tracking:
            try:
                # 从runtime或state中提取token使用量
                # 注意:这取决于LangChain版本和模型实现
                messages = state.get("messages", [])
                if messages:
                    last_message = messages[-1]
                    # 检查是否有response_metadata属性(某些模型会提供)
                    if hasattr(last_message, "response_metadata"):
                        metadata = last_message.response_metadata
                        if isinstance(metadata, dict):
                            token_usage = metadata.get("token_usage", {})
                            if token_usage:
                                input_tokens = token_usage.get("prompt_tokens", 0)
                                output_tokens = token_usage.get("completion_tokens", 0)
                                self.track_token_usage(
                                    execution_id, input_tokens, output_tokens
                                )
            except Exception as e:
                # 如果提取失败,记录但不影响主流程
                logger.debug(f"无法提取token使用量: {e}")

        # 记录输出(如果启用)
        if self.log_output:
            messages = state.get("messages", [])
            if messages:
                last_message = messages[-1]
                output_data = {
                    "message_type": type(last_message).__name__,
                    "content_preview": (
                        str(last_message.content[:200])
                        if hasattr(last_message, "content")
                        else None
                    ),
                }

                log_structured(
                    logger,
                    self.log_level,
                    "Agent %s 输出数据",
                    agent_id=agent_id,
                    agent_name=agent_name,
                    execution_id=execution_id,
                    event="agent_output",
                    **output_data,
                )

        # 记录工具调用(如果启用)
        if self.include_tool_calls:
            tool_calls = self._extract_tool_calls(state)
            if tool_calls:
                # 添加工具调用性能指标
                tool_performance = []
                tool_times = self._tool_call_times.get(execution_id, {})
                tool_counts = self._tool_call_count.get(execution_id, {})

                for tool_call in tool_calls:
                    tool_name = tool_call.get("tool_name", "unknown")
                    tool_start = tool_times.get(tool_name)
                    tool_count = tool_counts.get(tool_name, 0)

                    tool_perf = {
                        "tool_name": tool_name,
                        "call_count": tool_count,
                    }
                    if tool_start:
                        tool_duration = time.time() - tool_start
                        tool_perf["duration_seconds"] = tool_duration
                    tool_performance.append(tool_perf)

                log_structured(
                    logger,
                    self.log_level,
                    "Agent %s 工具调用",
                    agent_id=agent_id,
                    agent_name=agent_name,
                    execution_id=execution_id,
                    event="agent_tool_calls",
                    tool_calls=tool_calls,
                    tool_performance=tool_performance,
                )

                # 清理工具调用追踪数据
                self._tool_call_times.pop(execution_id, None)
                self._tool_call_count.pop(execution_id, None)

        # 记录性能指标(如果启用)
        if self.log_performance:
            # 获取token使用量(如果启用)
            token_info = {}
            if self.enable_token_tracking:
                token_usage = self._token_usage.get(execution_id, {})
                if token_usage:
                    token_info = {
                        "input_tokens": token_usage.get("input_tokens", 0),
                        "output_tokens": token_usage.get("output_tokens", 0),
                        "total_tokens": token_usage.get("total_tokens", 0),
                    }
                # 清理token追踪数据
                self._token_usage.pop(execution_id, None)

            log_performance(
                logger,
                "Agent %s 执行",
                duration,
                agent_id=agent_id,
                agent_name=agent_name,
                execution_id=execution_id,
                execution_count=self._execution_count,
                **token_info,
            )

        # 记录Agent执行完成
        complete_data = {
            "duration_seconds": duration,
        }

        # 添加token使用量(如果启用)
        if self.enable_token_tracking:
            token_usage = self._token_usage.get(execution_id, {})
            if token_usage:
                complete_data.update(
                    {
                        "input_tokens": token_usage.get("input_tokens", 0),
                        "output_tokens": token_usage.get("output_tokens", 0),
                        "total_tokens": token_usage.get("total_tokens", 0),
                    }
                )

        log_structured(
            logger,
            self.log_level,
            "Agent %s 执行完成",
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            event="agent_complete",
            **complete_data,
        )

        return None

    def _extract_tool_calls(self, state: AgentState) -> list[dict[str, Any]]:
        """从状态中提取工具调用信息

        Args:
            state: Agent状态

        Returns:
            工具调用列表
        """
        tool_calls = []
        messages = state.get("messages", [])

        for message in messages:
            # 检查是否是工具调用消息
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    tool_calls.append(
                        {
                            "tool_name": getattr(tool_call, "name", "unknown"),
                            "tool_id": getattr(tool_call, "id", None),
                            "tool_args": getattr(tool_call, "args", {}),
                        }
                    )

            # 检查是否是工具响应消息
            if hasattr(message, "name") and hasattr(message, "content"):
                # 可能是ToolMessage
                tool_calls.append(
                    {
                        "tool_name": getattr(message, "name", "unknown"),
                        "tool_response": str(message.content)[:200],
                    }
                )

        return tool_calls

    def before_tool(
        self,
        state: AgentState,
        runtime: Runtime,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> dict[str, Any] | None:
        """在工具调用前执行,记录工具调用开始事件(流式事件)

        注意:此方法可能不被所有LangChain版本支持,如果不可用则通过工具调用消息追踪。

        Args:
            state: Agent状态
            runtime: 运行时
            tool_name: 工具名称
            tool_input: 工具输入

        Returns:
            状态更新(可选)
        """
        if not self.enable_streaming_events:
            return None

        agent_id = state.get("agent_id", "unknown")
        agent_name = state.get("agent_name", "UnknownAgent")
        execution_id = state.get("execution_id", f"exec-{self._execution_count - 1}")

        # 记录工具调用开始时间
        tool_start_time = time.time()
        if execution_id not in self._tool_call_times:
            self._tool_call_times[execution_id] = {}
        self._tool_call_times[execution_id][tool_name] = tool_start_time

        # 更新工具调用计数
        if execution_id not in self._tool_call_count:
            self._tool_call_count[execution_id] = {}
        self._tool_call_count[execution_id][tool_name] = (
            self._tool_call_count[execution_id].get(tool_name, 0) + 1
        )

        # 记录流式事件:工具调用开始
        log_structured(
            logger,
            self.log_level,
            "Agent %s 工具调用开始: %s",
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            event="tool_start",
            tool_name=tool_name,
            tool_input_preview=str(tool_input)[:200] if tool_input else None,
            timestamp=tool_start_time,
        )

        return None

    def after_tool(
        self, state: AgentState, runtime: Runtime, tool_name: str, tool_output: Any
    ) -> dict[str, Any] | None:
        """在工具调用后执行,记录工具调用结束事件(流式事件)

        注意:此方法可能不被所有LangChain版本支持,如果不可用则通过工具响应消息追踪。

        Args:
            state: Agent状态
            runtime: 运行时
            tool_name: 工具名称
            tool_output: 工具输出

        Returns:
            状态更新(可选)
        """
        if not self.enable_streaming_events:
            return None

        agent_id = state.get("agent_id", "unknown")
        agent_name = state.get("agent_name", "UnknownAgent")
        execution_id = state.get("execution_id", f"exec-{self._execution_count - 1}")

        # 计算工具执行时间
        tool_times = self._tool_call_times.get(execution_id, {})
        tool_start_time = tool_times.get(tool_name)
        tool_duration = None
        if tool_start_time:
            tool_duration = time.time() - tool_start_time

        # 记录流式事件:工具调用结束
        log_structured(
            logger,
            self.log_level,
            "Agent %s 工具调用结束: %s",
            agent_id=agent_id,
            agent_name=agent_name,
            execution_id=execution_id,
            event="tool_end",
            tool_name=tool_name,
            tool_output_preview=str(tool_output)[:200] if tool_output else None,
            duration_seconds=tool_duration,
            timestamp=time.time(),
        )

        return None

    def track_token_usage(
        self, execution_id: str, input_tokens: int = 0, output_tokens: int = 0
    ) -> None:
        """追踪token使用量

        注意:此方法需要从模型响应中提取token使用量信息。
        由于LangChain 1.0的模型响应可能包含token使用量,可以在after_model中提取。

        Args:
            execution_id: 执行ID
            input_tokens: 输入token数
            output_tokens: 输出token数
        """
        if not self.enable_token_tracking:
            return

        if execution_id not in self._token_usage:
            self._token_usage[execution_id] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
            }

        self._token_usage[execution_id]["input_tokens"] += input_tokens
        self._token_usage[execution_id]["output_tokens"] += output_tokens
        self._token_usage[execution_id]["total_tokens"] = (
            self._token_usage[execution_id]["input_tokens"]
            + self._token_usage[execution_id]["output_tokens"]
        )


def create_agent_logging_middleware(
    log_level: str | LogLevel = LogLevel.INFO,
    log_input: bool = True,
    log_output: bool = True,
    log_performance: bool = True,
    log_state: bool = False,
    include_tool_calls: bool = True,
    enable_streaming_events: bool = True,
    enable_token_tracking: bool = True,
) -> AgentLoggingMiddleware:
    """创建Agent日志记录中间件的便捷函数

    Args:
        log_level: 日志级别
        log_input: 是否记录输入
        log_output: 是否记录输出
        log_performance: 是否记录性能指标
        log_state: 是否记录完整状态
        include_tool_calls: 是否记录工具调用
        enable_streaming_events: 是否启用流式事件记录(工具调用开始/结束)
        enable_token_tracking: 是否启用token使用量追踪

    Returns:
        Agent日志记录中间件实例
    """
    return AgentLoggingMiddleware(
        log_level=log_level,
        log_input=log_input,
        log_output=log_output,
        log_performance=log_performance,
        log_state=log_state,
        include_tool_calls=include_tool_calls,
        enable_streaming_events=enable_streaming_events,
        enable_token_tracking=enable_token_tracking,
    )
