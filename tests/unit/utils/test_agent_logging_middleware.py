# 生成命令: T022 错误处理和日志记录中间件
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
Agent日志记录中间件单元测试
"""

import time
from unittest.mock import MagicMock, patch

import pytest
from langchain.messages import AIMessage, HumanMessage

from src.shared.utils.agent_logging_middleware import (
    AgentLoggingMiddleware,
    create_agent_logging_middleware,
)
from src.shared.utils.logging import LogLevel


class TestAgentLoggingMiddleware:
    """测试Agent日志记录中间件"""

    def test_initialization_with_defaults(self):
        """测试默认参数初始化"""
        middleware = AgentLoggingMiddleware()

        assert middleware.log_level == LogLevel.INFO
        assert middleware.log_input is True
        assert middleware.log_output is True
        assert middleware.log_performance is True
        assert middleware.log_state is False
        assert middleware.include_tool_calls is True
        assert middleware._start_times == {}
        assert middleware._execution_count == 0

    def test_initialization_with_parameters(self):
        """测试自定义参数初始化"""
        middleware = AgentLoggingMiddleware(
            log_level=LogLevel.DEBUG,
            log_input=False,
            log_output=False,
            log_performance=False,
            log_state=True,
            include_tool_calls=False,
        )

        assert middleware.log_level == LogLevel.DEBUG
        assert middleware.log_input is False
        assert middleware.log_output is False
        assert middleware.log_performance is False
        assert middleware.log_state is True
        assert middleware.include_tool_calls is False

    def test_initialization_with_string_log_level(self):
        """测试使用字符串日志级别初始化"""
        middleware = AgentLoggingMiddleware(log_level="DEBUG")

        assert middleware.log_level == LogLevel.DEBUG

    def test_before_model_logging(self):
        """测试模型调用前日志记录"""
        middleware = AgentLoggingMiddleware()

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [HumanMessage(content="Hello")],
        }
        runtime = MagicMock()

        with patch(
            "src.shared.utils.agent_logging_middleware.log_structured"
        ) as mock_log:
            result = middleware.before_model(state, runtime)

        # 验证开始日志
        assert mock_log.call_count == 2  # agent_start + agent_input

        # 验证agent_start日志
        start_call = mock_log.call_args_list[0]
        assert start_call[1]["event"] == "agent_start"
        assert start_call[1]["agent_id"] == "test-agent"
        assert start_call[1]["agent_name"] == "TestAgent"

        # 验证agent_input日志
        input_call = mock_log.call_args_list[1]
        assert input_call[1]["event"] == "agent_input"
        assert input_call[1]["message_count"] == 1
        assert input_call[1]["last_message"] == "Hello"

        # 验证开始时间记录
        assert "exec-0" in middleware._start_times
        assert middleware._execution_count == 1

        assert result is None

    def test_before_model_without_input_logging(self):
        """测试不记录输入的模型调用前日志"""
        middleware = AgentLoggingMiddleware(log_input=False)

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [HumanMessage(content="Hello")],
        }
        runtime = MagicMock()

        with patch(
            "src.shared.utils.agent_logging_middleware.log_structured"
        ) as mock_log:
            result = middleware.before_model(state, runtime)

        # 验证只有开始日志
        assert mock_log.call_count == 1
        assert mock_log.call_args[1]["event"] == "agent_start"

        assert result is None

    def test_before_model_with_state_logging(self):
        """测试记录状态的模型调用前日志"""
        middleware = AgentLoggingMiddleware(log_state=True)

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [HumanMessage(content="Hello")],
            "api_key": "secret",  # 敏感信息
            "public_data": "safe",  # 非敏感信息
        }
        runtime = MagicMock()

        with patch(
            "src.shared.utils.agent_logging_middleware.log_structured"
        ) as mock_log:
            result = middleware.before_model(state, runtime)

        # 验证状态日志
        state_calls = [
            call
            for call in mock_log.call_args_list
            if call[1].get("event") == "agent_state"
        ]
        assert len(state_calls) == 1

        # 验证敏感信息被过滤
        logged_state = state_calls[0][1]["state"]
        assert "api_key" not in logged_state
        assert "public_data" in logged_state

        assert result is None

    def test_after_model_logging(self):
        """测试模型调用后日志记录"""
        middleware = AgentLoggingMiddleware()

        # 设置开始时间
        execution_id = "exec-0"
        start_time = time.time()
        middleware._start_times[execution_id] = start_time
        middleware._execution_count = 1

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [
                HumanMessage(content="Hello"),
                AIMessage(content="Hi there"),
            ],
        }
        runtime = MagicMock()

        with (
            patch(
                "src.shared.utils.agent_logging_middleware.log_structured"
            ) as mock_log,
            patch(
                "src.shared.utils.agent_logging_middleware.log_performance"
            ) as mock_perf,
        ):
            result = middleware.after_model(state, runtime)

        # 验证日志调用
        assert (
            mock_log.call_count == 3
        )  # agent_output + agent_tool_calls + agent_complete
        assert mock_perf.call_count == 1

        # 验证开始时间被清理
        assert execution_id not in middleware._start_times

        assert result is None

    def test_after_model_without_output_logging(self):
        """测试不记录输出的模型调用后日志"""
        middleware = AgentLoggingMiddleware(log_output=False)

        # 设置开始时间
        execution_id = "exec-0"
        middleware._start_times[execution_id] = time.time()
        middleware._execution_count = 1

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [AIMessage(content="Hi there")],
        }
        runtime = MagicMock()

        with (
            patch(
                "src.shared.utils.agent_logging_middleware.log_structured"
            ) as mock_log,
            patch(
                "src.shared.utils.agent_logging_middleware.log_performance"
            ) as mock_perf,
        ):
            result = middleware.after_model(state, runtime)

        # 验证没有输出日志
        output_calls = [
            call
            for call in mock_log.call_args_list
            if call[1].get("event") == "agent_output"
        ]
        assert len(output_calls) == 0

        # 验证其他日志仍然存在
        assert mock_log.call_count >= 1  # 至少有agent_complete
        assert mock_perf.call_count == 1

        assert result is None

    def test_after_model_without_performance_logging(self):
        """测试不记录性能的模型调用后日志"""
        middleware = AgentLoggingMiddleware(log_performance=False)

        # 设置开始时间
        execution_id = "exec-0"
        middleware._start_times[execution_id] = time.time()
        middleware._execution_count = 1

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [AIMessage(content="Hi there")],
        }
        runtime = MagicMock()

        with (
            patch(
                "src.shared.utils.agent_logging_middleware.log_structured"
            ) as mock_log,
            patch(
                "src.shared.utils.agent_logging_middleware.log_performance"
            ) as mock_perf,
        ):
            result = middleware.after_model(state, runtime)

        # 验证没有性能日志
        mock_perf.assert_not_called()

        # 验证其他日志仍然存在
        assert mock_log.call_count >= 1

        assert result is None

    def test_after_model_without_start_time(self):
        """测试没有开始时间的模型调用后日志"""
        middleware = AgentLoggingMiddleware()
        middleware._execution_count = 1

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [AIMessage(content="Hi there")],
        }
        runtime = MagicMock()

        with (
            patch("src.shared.utils.agent_logging_middleware.log_structured"),
            patch(
                "src.shared.utils.agent_logging_middleware.log_performance"
            ) as mock_perf,
        ):
            result = middleware.after_model(state, runtime)

        # 验证性能日志使用0.0作为持续时间
        perf_call_args = mock_perf.call_args[0]
        assert (
            perf_call_args[2] == 0.0
        )  # duration (参数位置: logger, operation, duration)

        assert result is None

    def test_extract_tool_calls_from_tool_call_messages(self):
        """测试从工具调用消息中提取工具调用"""
        middleware = AgentLoggingMiddleware()

        # 创建模拟工具调用消息
        tool_call_msg = MagicMock()
        tool_call1 = MagicMock()
        tool_call1.name = "tool1"
        tool_call1.id = "call-1"
        tool_call1.args = {"param": "value1"}

        tool_call2 = MagicMock()
        tool_call2.name = "tool2"
        tool_call2.id = "call-2"
        tool_call2.args = {"param": "value2"}

        tool_call_msg.tool_calls = [tool_call1, tool_call2]
        # 确保没有name属性,避免被误认为是工具响应
        if hasattr(tool_call_msg, "name"):
            del tool_call_msg.name

        state = {
            "messages": [tool_call_msg],
        }

        tool_calls = middleware._extract_tool_calls(state)

        assert len(tool_calls) == 2
        assert tool_calls[0]["tool_name"] == "tool1"
        assert tool_calls[0]["tool_id"] == "call-1"
        assert tool_calls[0]["tool_args"] == {"param": "value1"}
        assert tool_calls[1]["tool_name"] == "tool2"
        assert tool_calls[1]["tool_id"] == "call-2"
        assert tool_calls[1]["tool_args"] == {"param": "value2"}

    def test_extract_tool_calls_from_tool_response_messages(self):
        """测试从工具响应消息中提取工具调用"""
        middleware = AgentLoggingMiddleware()

        # 创建模拟工具响应消息
        tool_response_msg = MagicMock()
        tool_response_msg.name = "test_tool"
        tool_response_msg.content = "Tool execution result"
        # 确保没有tool_calls属性
        if hasattr(tool_response_msg, "tool_calls"):
            del tool_response_msg.tool_calls

        state = {
            "messages": [tool_response_msg],
        }

        tool_calls = middleware._extract_tool_calls(state)

        assert len(tool_calls) == 1
        assert tool_calls[0]["tool_name"] == "test_tool"
        assert tool_calls[0]["tool_response"] == "Tool execution result"

    def test_extract_tool_calls_mixed_messages(self):
        """测试从混合消息中提取工具调用"""
        middleware = AgentLoggingMiddleware()

        # 创建混合消息
        tool_call_msg = MagicMock()
        tool_call1 = MagicMock()
        tool_call1.name = "tool1"
        tool_call1.id = "call-1"
        tool_call1.args = {"param": "value1"}
        tool_call_msg.tool_calls = [tool_call1]

        tool_response_msg = MagicMock()
        tool_response_msg.name = "tool2"
        tool_response_msg.content = "Tool result"
        # 确保没有tool_calls属性
        if hasattr(tool_response_msg, "tool_calls"):
            del tool_response_msg.tool_calls

        regular_msg = MagicMock()
        # 确保regular_msg有content但没有name属性,这样不会被误认为是工具响应
        if hasattr(regular_msg, "tool_calls"):
            del regular_msg.tool_calls
        if hasattr(regular_msg, "name"):
            del regular_msg.name
        # 确保content属性存在
        regular_msg.content = "Regular message"

        state = {
            "messages": [regular_msg, tool_call_msg, tool_response_msg],
        }

        tool_calls = middleware._extract_tool_calls(state)

        assert len(tool_calls) == 3
        # 应该包含1个工具调用和2个工具响应
        tool_names = [call["tool_name"] for call in tool_calls]
        assert "tool1" in tool_names
        assert "tool2" in tool_names

    def test_extract_tool_calls_empty_messages(self):
        """测试从空消息中提取工具调用"""
        middleware = AgentLoggingMiddleware()

        state = {
            "messages": [],
        }

        tool_calls = middleware._extract_tool_calls(state)

        assert len(tool_calls) == 0

    def test_after_model_with_tool_calls_logging(self):
        """测试包含工具调用日志的模型调用后日志"""
        middleware = AgentLoggingMiddleware(include_tool_calls=True)

        # 设置开始时间
        execution_id = "exec-0"
        middleware._start_times[execution_id] = time.time()
        middleware._execution_count = 1

        # 创建包含工具调用的消息
        tool_call_msg = MagicMock()
        tool_call1 = MagicMock()
        tool_call1.name = "test_tool"
        tool_call1.id = "call-1"
        tool_call1.args = {"param": "value"}
        tool_call_msg.tool_calls = [tool_call1]
        # 确保没有name属性,避免被误认为是工具响应
        if hasattr(tool_call_msg, "name"):
            del tool_call_msg.name

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [tool_call_msg],
        }
        runtime = MagicMock()

        with patch(
            "src.shared.utils.agent_logging_middleware.log_structured"
        ) as mock_log:
            result = middleware.after_model(state, runtime)

        # 验证工具调用日志
        tool_calls_calls = [
            call
            for call in mock_log.call_args_list
            if call[1].get("event") == "agent_tool_calls"
        ]
        assert len(tool_calls_calls) == 1

        tool_calls_data = tool_calls_calls[0][1]["tool_calls"]
        assert len(tool_calls_data) == 1
        assert tool_calls_data[0]["tool_name"] == "test_tool"

        assert result is None

    def test_after_model_without_tool_calls_logging(self):
        """测试不包含工具调用日志的模型调用后日志"""
        middleware = AgentLoggingMiddleware(include_tool_calls=False)

        # 设置开始时间
        execution_id = "exec-0"
        middleware._start_times[execution_id] = time.time()
        middleware._execution_count = 1

        # 创建包含工具调用的消息
        tool_call_msg = MagicMock()
        tool_call1 = MagicMock()
        tool_call1.name = "test_tool"
        tool_call1.id = "call-1"
        tool_call1.args = {"param": "value"}
        tool_call_msg.tool_calls = [tool_call1]
        # 确保没有name属性,避免被误认为是工具响应
        if hasattr(tool_call_msg, "name"):
            del tool_call_msg.name

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "messages": [tool_call_msg],
        }
        runtime = MagicMock()

        with patch(
            "src.shared.utils.agent_logging_middleware.log_structured"
        ) as mock_log:
            result = middleware.after_model(state, runtime)

        # 验证没有工具调用日志
        tool_calls_calls = [
            call
            for call in mock_log.call_args_list
            if call[1].get("event") == "agent_tool_calls"
        ]
        assert len(tool_calls_calls) == 0

        # 验证其他日志仍然存在
        assert mock_log.call_count >= 1

        assert result is None

    def test_execution_id_generation(self):
        """测试执行ID生成"""
        middleware = AgentLoggingMiddleware()

        state1 = {"agent_id": "test-agent", "agent_name": "TestAgent"}
        state2 = {"agent_id": "test-agent", "agent_name": "TestAgent"}
        runtime = MagicMock()

        with patch("src.shared.utils.agent_logging_middleware.log_structured"):
            # 第一次调用
            middleware.before_model(state1, runtime)
            assert "exec-0" in middleware._start_times
            assert middleware._execution_count == 1

            # 第二次调用
            middleware.before_model(state2, runtime)
            assert "exec-1" in middleware._start_times
            assert middleware._execution_count == 2

    def test_custom_execution_id_in_state(self):
        """测试状态中的自定义执行ID"""
        middleware = AgentLoggingMiddleware()

        state = {
            "agent_id": "test-agent",
            "agent_name": "TestAgent",
            "execution_id": "custom-exec-123",
        }
        runtime = MagicMock()

        with patch(
            "src.shared.utils.agent_logging_middleware.log_structured"
        ) as mock_log:
            middleware.before_model(state, runtime)
            middleware.after_model(state, runtime)

        # 验证使用了自定义执行ID
        start_calls = [
            call
            for call in mock_log.call_args_list
            if call[1].get("event") == "agent_start"
        ]
        assert start_calls[0][1]["execution_id"] == "custom-exec-123"

        complete_calls = [
            call
            for call in mock_log.call_args_list
            if call[1].get("event") == "agent_complete"
        ]
        assert complete_calls[0][1]["execution_id"] == "custom-exec-123"


class TestCreateAgentLoggingMiddleware:
    """测试Agent日志记录中间件创建函数"""

    def test_create_with_default_parameters(self):
        """测试使用默认参数创建中间件"""
        middleware = create_agent_logging_middleware()

        assert isinstance(middleware, AgentLoggingMiddleware)
        assert middleware.log_level == LogLevel.INFO
        assert middleware.log_input is True
        assert middleware.log_output is True
        assert middleware.log_performance is True
        assert middleware.log_state is False
        assert middleware.include_tool_calls is True

    def test_create_with_custom_parameters(self):
        """测试使用自定义参数创建中间件"""
        middleware = create_agent_logging_middleware(
            log_level=LogLevel.DEBUG,
            log_input=False,
            log_output=False,
            log_performance=False,
            log_state=True,
            include_tool_calls=False,
        )

        assert isinstance(middleware, AgentLoggingMiddleware)
        assert middleware.log_level == LogLevel.DEBUG
        assert middleware.log_input is False
        assert middleware.log_output is False
        assert middleware.log_performance is False
        assert middleware.log_state is True
        assert middleware.include_tool_calls is False

    def test_create_with_string_log_level(self):
        """测试使用字符串日志级别创建中间件"""
        middleware = create_agent_logging_middleware(log_level="ERROR")

        assert isinstance(middleware, AgentLoggingMiddleware)
        assert middleware.log_level == LogLevel.ERROR


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
