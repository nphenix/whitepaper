# 生成命令: T010 自定义异常类实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
LangChain集成测试
"""

from unittest.mock import Mock

from src.shared.exceptions.agent_exceptions import (
    LangChainError,
    wrap_langchain_error,
)


class TestLangChainIntegration:
    """测试LangChain集成"""

    def test_langchain_timeout_error_wrapping(self):
        """测试LangChain超时错误包装"""
        # 模拟LangChain超时异常
        original_error = TimeoutError("Request timeout after 30 seconds")

        wrapped_error = wrap_langchain_error(
            original_error,
            agent_name="DocumentProcessor",
            langchain_component="ChatOpenAI",
        )

        assert isinstance(wrapped_error, LangChainError)
        assert wrapped_error.details["error_type"] == "timeout"
        assert wrapped_error.details["agent_name"] == "DocumentProcessor"
        assert wrapped_error.details["langchain_component"] == "ChatOpenAI"

    def test_langchain_rate_limit_error_wrapping(self):
        """测试LangChain速率限制错误包装"""
        # 模拟LangChain速率限制异常
        original_error = Exception("Rate limit exceeded for API key")

        wrapped_error = wrap_langchain_error(
            original_error,
            agent_name="DocumentProcessor",
            langchain_component="ChatOpenAI",
        )

        assert isinstance(wrapped_error, LangChainError)
        assert wrapped_error.details.get("error_type") == "rate_limit"
        assert wrapped_error.details["agent_name"] == "DocumentProcessor"
        assert wrapped_error.details["langchain_component"] == "ChatOpenAI"

    def test_langchain_authentication_error_wrapping(self):
        """测试LangChain认证错误包装"""
        # 模拟LangChain认证异常
        original_error = Exception("Invalid API key provided")

        wrapped_error = wrap_langchain_error(
            original_error,
            agent_name="DocumentProcessor",
            langchain_component="ChatOpenAI",
        )

        assert isinstance(wrapped_error, LangChainError)
        assert wrapped_error.details["error_type"] == "authentication"
        assert wrapped_error.details["agent_name"] == "DocumentProcessor"
        assert wrapped_error.details["langchain_component"] == "ChatOpenAI"

    def test_langchain_model_unavailable_error_wrapping(self):
        """测试LangChain模型不可用错误包装"""
        # 模拟LangChain模型不可用异常
        original_error = Exception("Model gpt-5 is not available")

        wrapped_error = wrap_langchain_error(
            original_error,
            agent_name="DocumentProcessor",
            langchain_component="ChatOpenAI",
        )

        assert isinstance(wrapped_error, LangChainError)
        assert wrapped_error.details.get("error_type") == "model_unavailable"
        assert wrapped_error.details["agent_name"] == "DocumentProcessor"
        assert wrapped_error.details["langchain_component"] == "ChatOpenAI"

    def test_langchain_generic_error_wrapping(self):
        """测试LangChain通用错误包装"""
        # 模拟LangChain通用异常
        original_error = Exception("Generic error occurred")

        wrapped_error = wrap_langchain_error(
            original_error,
            agent_name="DocumentProcessor",
            langchain_component="ChatOpenAI",
        )

        assert isinstance(wrapped_error, LangChainError)
        assert "error_type" not in wrapped_error.details  # 不应该有特定错误类型
        assert wrapped_error.details["agent_name"] == "DocumentProcessor"
        assert wrapped_error.details["langchain_component"] == "ChatOpenAI"

    def test_langchain_error_to_dict(self):
        """测试LangChain错误转换为字典"""
        original_error = TimeoutError("Request timeout after 30 seconds")

        wrapped_error = wrap_langchain_error(
            original_error,
            agent_name="DocumentProcessor",
            langchain_component="ChatOpenAI",
        )

        error_dict = wrapped_error.to_dict()

        assert error_dict["error_type"] == "LangChainError"
        assert "Request timeout after 30 seconds" in error_dict["message"]
        assert error_dict["details"]["agent_name"] == "DocumentProcessor"
        assert error_dict["details"]["langchain_component"] == "ChatOpenAI"
        assert error_dict["details"]["error_type"] == "timeout"
        assert error_dict["original_error"]["type"] == "TimeoutError"
        assert (
            "Request timeout after 30 seconds"
            in error_dict["original_error"]["message"]
        )

    def test_langchain_integration_with_fallbacks(self):
        """测试LangChain集成与降级机制"""
        # 模拟LLM服务
        mock_primary = Mock()
        mock_fallback = Mock()

        # 模拟主模型失败,降级模型成功
        mock_primary.invoke.side_effect = TimeoutError("Primary model timeout")
        mock_fallback.invoke.return_value = "Fallback response"

        # 这里应该使用实际的LangChain代码来测试集成
        # 由于我们没有实际的LangChain依赖,这里只测试异常包装逻辑

        try:
            mock_primary.invoke("test prompt")
        except TimeoutError as e:
            # 在实际应用中,这里会使用wrap_langchain_error
            wrapped_error = wrap_langchain_error(
                e, agent_name="TestAgent", langchain_component="ChatOpenAI"
            )

            assert isinstance(wrapped_error, LangChainError)
            assert wrapped_error.details["error_type"] == "timeout"

    def test_error_chaining(self):
        """测试异常链"""
        original_error = ValueError("Original error")

        wrapped_error = wrap_langchain_error(
            original_error, message="Custom error message"
        )

        # 测试异常链是否正确
        assert wrapped_error.original_error is original_error
        assert wrapped_error.__cause__ is None  # 我们没有使用from关键字

        # 测试异常链的字符串表示
        error_str = str(wrapped_error)
        assert "Custom error message" in error_str

        # 测试转换为字典时的异常链信息
        error_dict = wrapped_error.to_dict()
        assert error_dict["original_error"]["type"] == "ValueError"
        assert error_dict["original_error"]["message"] == "Original error"
