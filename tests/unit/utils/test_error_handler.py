# 生成命令: T022 错误处理和日志记录中间件
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
错误处理中间件单元测试
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain.agents.middleware import ModelResponse
from langchain.messages import AIMessage, ToolMessage

from src.shared.exceptions.agent_exceptions import (
    AgentExecutionError,
    AgentToolError,
    LangChainError,
)
from src.shared.utils.error_handler import (
    ErrorHandlingMiddleware,
    create_error_handling_middleware,
)


class TestErrorHandlingMiddleware:
    """测试错误处理中间件"""

    def test_initialization(self):
        """测试中间件初始化"""
        middleware = ErrorHandlingMiddleware(
            max_retries=5,
            retry_delay=2.0,
            enable_error_recovery=True,
        )

        assert middleware.max_retries == 5
        assert middleware.retry_delay == 2.0
        assert middleware.enable_error_recovery is True
        assert middleware.error_callback is None
        assert middleware._error_count == 0

    def test_initialization_with_callback(self):
        """测试带回调的中间件初始化"""
        callback = MagicMock()
        middleware = ErrorHandlingMiddleware(error_callback=callback)

        assert middleware.error_callback is callback

    def test_wrap_model_call_success(self):
        """测试模型调用成功的情况"""
        middleware = ErrorHandlingMiddleware()

        # 创建模拟请求和处理器
        request = MagicMock()
        request.state = {"agent_id": "test-agent", "agent_name": "TestAgent"}

        handler = MagicMock()
        expected_response = ModelResponse(result=[AIMessage(content="Success")])
        handler.return_value = expected_response

        # 执行包装的模型调用
        result = middleware.wrap_model_call(request, handler)

        # 验证结果
        assert result is expected_response
        assert middleware._error_count == 0
        handler.assert_called_once_with(request)

    def test_wrap_model_call_with_retry_success(self):
        """测试模型调用重试后成功"""
        middleware = ErrorHandlingMiddleware(max_retries=3, retry_delay=0)

        request = MagicMock()
        request.state = {"agent_id": "test-agent", "agent_name": "TestAgent"}

        handler = MagicMock()
        expected_response = ModelResponse(result=[AIMessage(content="Success")])

        # 前两次调用失败,第三次成功
        handler.side_effect = [
            Exception("First error"),
            Exception("Second error"),
            expected_response,
        ]

        with patch("src.shared.utils.error_handler.log_error") as mock_log_error:
            result = middleware.wrap_model_call(request, handler)

        # 验证结果
        assert result is expected_response
        assert middleware._error_count == 0
        assert handler.call_count == 3
        assert mock_log_error.call_count == 2

    def test_wrap_model_call_all_retries_fail(self):
        """测试模型调用所有重试都失败"""
        middleware = ErrorHandlingMiddleware(max_retries=2, retry_delay=0)

        request = MagicMock()
        request.state = {"agent_id": "test-agent", "agent_name": "TestAgent"}

        handler = MagicMock()
        error = ValueError("Model error")
        handler.side_effect = error

        with (
            patch("src.shared.utils.error_handler.log_error") as mock_log_error,
            patch(
                "src.shared.utils.error_handler.log_structured"
            ) as mock_log_structured,pytest.raises(AgentExecutionError) as exc_info
        ):
            middleware.wrap_model_call(request, handler)

        # 验证异常
        assert "Agent执行失败: Model error" in str(exc_info.value)
        assert exc_info.value.details["agent_id"] == "test-agent"
        assert exc_info.value.details["agent_name"] == "TestAgent"

        # 验证调用次数
        assert handler.call_count == 2
        assert mock_log_error.call_count == 2
        assert mock_log_structured.call_count == 1

    def test_wrap_tool_call_success(self):
        """测试工具调用成功的情况"""
        middleware = ErrorHandlingMiddleware()

        # 创建模拟的工具请求
        request = MagicMock()
        tool_call = {"name": "test_tool", "args": {"param": "value"}, "id": "tool-123"}
        request.tool_call = tool_call
        request.state = {"agent_id": "test-agent", "agent_name": "TestAgent"}

        handler = MagicMock()
        expected_response = ToolMessage(content="Tool success", tool_call_id="tool-123")
        handler.return_value = expected_response

        with patch("src.shared.utils.error_handler.log_error") as mock_log_error:
            result = middleware.wrap_tool_call(request, handler)

        # 验证结果
        assert result is expected_response
        handler.assert_called_once_with(request)
        mock_log_error.assert_not_called()

    def test_wrap_tool_call_failure(self):
        """测试工具调用失败的情况"""
        middleware = ErrorHandlingMiddleware()

        # 创建模拟的工具请求
        request = MagicMock()
        tool_call = {"name": "test_tool", "args": {"param": "value"}, "id": "tool-123"}
        request.tool_call = tool_call
        request.state = {"agent_id": "test-agent", "agent_name": "TestAgent"}

        handler = MagicMock()
        error = ValueError("Tool error")
        handler.side_effect = error

        with (
            patch("src.shared.utils.error_handler.log_error") as mock_log_error,
            patch(
                "src.shared.utils.error_handler.log_structured"
            ) as mock_log_structured,
        ):
            result = middleware.wrap_tool_call(request, handler)

        # 验证结果 - 工具错误不抛出异常,而是返回错误消息
        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "tool-123"
        assert "工具 test_tool 调用失败" in result.content

        # 验证日志调用
        mock_log_error.assert_called_once()
        mock_log_structured.assert_called_once()

    def test_wrap_tool_call_without_state(self):
        """测试没有状态的工具调用"""
        middleware = ErrorHandlingMiddleware()

        # 创建模拟的工具请求
        request = MagicMock()
        tool_call = {"name": "test_tool", "args": {}, "id": "tool-123"}
        request.tool_call = tool_call
        # 没有设置state或state不是字典

        handler = MagicMock()
        error = ValueError("Tool error")
        handler.side_effect = error

        with patch("src.shared.utils.error_handler.log_error"):
            result = middleware.wrap_tool_call(request, handler)

        # 验证结果
        assert isinstance(result, ToolMessage)
        assert result.tool_call_id == "tool-123"

    def test_wrap_error_langchain_error(self):
        """测试LangChain错误包装"""
        middleware = ErrorHandlingMiddleware()

        error = Exception("langchain error occurred")
        wrapped = middleware._wrap_error(
            error,
            agent_id="test-agent",
            agent_name="TestAgent",
            error_type="model_call",
        )

        assert isinstance(wrapped, LangChainError)

    def test_wrap_error_tool_error(self):
        """测试工具错误包装"""
        middleware = ErrorHandlingMiddleware()

        error = Exception("Tool failed")
        wrapped = middleware._wrap_error(
            error,
            agent_id="test-agent",
            agent_name="TestAgent",
            tool_name="test_tool",
            tool_args={"param": "value"},
            error_type="tool_call",
        )

        assert isinstance(wrapped, AgentToolError)
        assert wrapped.details["tool_name"] == "test_tool"
        assert wrapped.details["tool_args"] == {"param": "value"}

    def test_wrap_error_general_error(self):
        """测试一般错误包装"""
        middleware = ErrorHandlingMiddleware()

        error = Exception("General error")
        wrapped = middleware._wrap_error(
            error,
            agent_id="test-agent",
            agent_name="TestAgent",
            error_type="unknown",
        )

        assert isinstance(wrapped, AgentExecutionError)
        assert wrapped.details["agent_id"] == "test-agent"
        assert wrapped.details["agent_name"] == "TestAgent"

    def test_format_tool_error_message_timeout(self):
        """测试超时错误消息格式化"""
        middleware = ErrorHandlingMiddleware()
        error = AgentExecutionError("Timeout error", details={"error_type": "timeout"})

        message = middleware._format_tool_error_message(error, "test_tool")

        assert message == "工具 test_tool 调用超时,请稍后重试。"

    def test_format_tool_error_message_rate_limit(self):
        """测试速率限制错误消息格式化"""
        middleware = ErrorHandlingMiddleware()
        error = AgentExecutionError("Rate limit", details={"error_type": "rate_limit"})

        message = middleware._format_tool_error_message(error, "test_tool")

        assert message == "工具 test_tool 调用达到速率限制,请稍后重试。"

    def test_format_tool_error_message_authentication(self):
        """测试认证错误消息格式化"""
        middleware = ErrorHandlingMiddleware()
        error = AgentExecutionError(
            "Auth failed", details={"error_type": "authentication"}
        )

        message = middleware._format_tool_error_message(error, "test_tool")

        assert message == "工具 test_tool 认证失败,请检查配置。"

    def test_format_tool_error_message_model_unavailable(self):
        """测试模型不可用错误消息格式化"""
        middleware = ErrorHandlingMiddleware()
        error = AgentExecutionError(
            "Model down", details={"error_type": "model_unavailable"}
        )

        message = middleware._format_tool_error_message(error, "test_tool")

        assert message == "工具 test_tool 依赖的模型不可用,请稍后重试。"

    def test_format_tool_error_message_general(self):
        """测试一般错误消息格式化"""
        middleware = ErrorHandlingMiddleware()
        error = AgentExecutionError("General error", details={"error_type": "unknown"})

        message = middleware._format_tool_error_message(error, "test_tool")

        assert (
            message
            == "工具 test_tool 调用失败: General error。请检查输入参数或稍后重试。"
        )

    def test_handle_error_with_callback(self):
        """测试带回调的错误处理"""
        callback = MagicMock()
        middleware = ErrorHandlingMiddleware(error_callback=callback)

        error = AgentExecutionError("Test error")
        state = {"agent_id": "test-agent", "agent_name": "TestAgent"}

        with patch("src.shared.utils.error_handler.log_structured") as mock_log:
            middleware._handle_error(error, state)

        # 验证日志和回调
        mock_log.assert_called_once()
        callback.assert_called_once_with(error, state)

    def test_handle_error_callback_failure(self):
        """测试回调失败的情况"""
        callback = MagicMock()
        callback.side_effect = Exception("Callback error")
        middleware = ErrorHandlingMiddleware(error_callback=callback)

        error = AgentExecutionError("Test error")
        state = {"agent_id": "test-agent", "agent_name": "TestAgent"}

        with (
            patch("src.shared.utils.error_handler.log_structured") as mock_log,
            patch("src.shared.utils.error_handler.logger") as mock_logger,
        ):
            middleware._handle_error(error, state)

        # 验证日志记录了回调错误
        mock_log.assert_called_once()
        mock_logger.warning.assert_called_once()

    def test_before_model_with_error_recovery(self):
        """测试带错误恢复的模型调用前处理"""
        middleware = ErrorHandlingMiddleware(enable_error_recovery=True)
        middleware._error_count = 2

        state = {"agent_id": "test-agent", "agent_name": "TestAgent"}
        runtime = MagicMock()

        with patch("src.shared.utils.error_handler.logger") as mock_logger:
            result = middleware.before_model(state, runtime)

        # 验证日志记录
        mock_logger.info.assert_called_once()
        assert result is None

    def test_before_model_without_error_recovery(self):
        """测试不带错误恢复的模型调用前处理"""
        middleware = ErrorHandlingMiddleware(enable_error_recovery=False)
        middleware._error_count = 2

        state = {"agent_id": "test-agent", "agent_name": "TestAgent"}
        runtime = MagicMock()

        with patch("src.shared.utils.error_handler.logger") as mock_logger:
            result = middleware.before_model(state, runtime)

        # 验证没有日志记录
        mock_logger.info.assert_not_called()
        assert result is None

    def test_after_model_reset_error_count(self):
        """测试模型调用后重置错误计数"""
        middleware = ErrorHandlingMiddleware()
        middleware._error_count = 2

        state = {"agent_id": "test-agent", "agent_name": "TestAgent"}
        runtime = MagicMock()

        with patch("src.shared.utils.error_handler.logger") as mock_logger:
            result = middleware.after_model(state, runtime)

        # 验证错误计数重置和日志记录
        assert middleware._error_count == 0
        mock_logger.info.assert_called_once()
        assert result is None

    def test_after_model_no_error_count(self):
        """测试没有错误计数时的模型调用后处理"""
        middleware = ErrorHandlingMiddleware()
        middleware._error_count = 0

        state = {"agent_id": "test-agent", "agent_name": "TestAgent"}
        runtime = MagicMock()

        with patch("src.shared.utils.error_handler.logger") as mock_logger:
            result = middleware.after_model(state, runtime)

        # 验证没有日志记录
        mock_logger.info.assert_not_called()
        assert result is None


class TestCreateErrorHandlingMiddleware:
    """测试错误处理中间件创建函数"""

    def test_create_with_default_parameters(self):
        """测试使用默认参数创建中间件"""
        middleware = create_error_handling_middleware()

        assert isinstance(middleware, ErrorHandlingMiddleware)
        assert middleware.max_retries == 3
        assert middleware.retry_delay == 1.0
        assert middleware.enable_error_recovery is True
        assert middleware.error_callback is None

    def test_create_with_custom_parameters(self):
        """测试使用自定义参数创建中间件"""
        callback = MagicMock()
        middleware = create_error_handling_middleware(
            max_retries=5,
            retry_delay=2.0,
            enable_error_recovery=False,
            error_callback=callback,
        )

        assert isinstance(middleware, ErrorHandlingMiddleware)
        assert middleware.max_retries == 5
        assert middleware.retry_delay == 2.0
        assert middleware.enable_error_recovery is False
        assert middleware.error_callback is callback


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
