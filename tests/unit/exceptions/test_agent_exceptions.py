# 生成命令: T010 自定义异常类实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
Agent异常类单元测试
"""

from src.shared.exceptions.agent_exceptions import (
    AgentCallbackError,
    AgentConfigurationError,
    AgentError,
    AgentExecutionError,
    AgentInputError,
    AgentMemoryError,
    AgentStateError,
    AgentToolError,
    LangChainError,
    wrap_langchain_error,
)


class TestAgentError:
    """测试Agent基础异常类"""

    def test_basic_agent_error(self):
        """测试基本Agent错误"""
        error = AgentError("Agent error occurred")
        assert error.message == "Agent error occurred"
        assert isinstance(error, Exception)

    def test_agent_error_with_details(self):
        """测试带详细信息的Agent错误"""
        error = AgentError(
            "Agent error occurred", agent_name="DocumentProcessor", agent_id="agent_001"
        )

        assert error.message == "Agent error occurred"
        assert error.details["agent_name"] == "DocumentProcessor"
        assert error.details["agent_id"] == "agent_001"


class TestAgentExecutionError:
    """测试Agent执行错误异常"""

    def test_basic_agent_execution_error(self):
        """测试基本Agent执行错误"""
        error = AgentExecutionError("Execution failed")
        assert error.message == "Execution failed"
        assert isinstance(error, AgentError)

    def test_agent_execution_error_with_details(self):
        """测试带详细信息的Agent执行错误"""
        error = AgentExecutionError(
            "Execution failed", execution_id="exec_001", step="document_processing"
        )

        assert error.message == "Execution failed"
        assert error.details["execution_id"] == "exec_001"
        assert error.details["step"] == "document_processing"


class TestLangChainError:
    """测试LangChain错误异常"""

    def test_basic_langchain_error(self):
        """测试基本LangChain错误"""
        original_error = ValueError("Original LangChain error")
        error = LangChainError(
            "LangChain operation failed", original_error=original_error
        )

        assert error.message == "LangChain operation failed"
        assert error.original_error == original_error
        assert isinstance(error, AgentExecutionError)

    def test_langchain_error_with_component(self):
        """测试带组件信息的LangChain错误"""
        original_error = ValueError("Original LangChain error")
        error = LangChainError(
            "LangChain operation failed",
            original_error=original_error,
            langchain_component="ChatOpenAI",
        )

        assert error.message == "LangChain operation failed"
        assert error.details["langchain_component"] == "ChatOpenAI"

    def test_langchain_error_timeout_detection(self):
        """测试超时错误检测"""
        original_error = TimeoutError("Request timeout after 30 seconds")
        error = LangChainError(
            "LangChain operation failed", original_error=original_error
        )

        assert error.details["error_type"] == "timeout"

    def test_langchain_error_rate_limit_detection(self):
        """测试速率限制错误检测"""
        original_error = Exception("Rate limit exceeded")
        error = LangChainError(
            "LangChain operation failed", original_error=original_error
        )

        assert error.details["error_type"] == "rate_limit"

    def test_langchain_error_authentication_detection(self):
        """测试认证错误检测"""
        original_error = Exception("Invalid API key")
        error = LangChainError(
            "LangChain operation failed", original_error=original_error
        )

        assert error.details["error_type"] == "authentication"

    def test_langchain_error_model_unavailable_detection(self):
        """测试模型不可用错误检测"""
        original_error = Exception("Model gpt-5 not found")
        error = LangChainError(
            "LangChain operation failed", original_error=original_error
        )

        assert error.details["error_type"] == "model_unavailable"


class TestAgentToolError:
    """测试Agent工具错误异常"""

    def test_basic_agent_tool_error(self):
        """测试基本Agent工具错误"""
        error = AgentToolError("Tool execution failed")
        assert error.message == "Tool execution failed"
        assert isinstance(error, AgentExecutionError)

    def test_agent_tool_error_with_details(self):
        """测试带详细信息的Agent工具错误"""
        error = AgentToolError(
            "Tool execution failed",
            tool_name="document_parser",
            tool_args={"file_path": "/path/to/file.pdf"},
        )

        assert error.message == "Tool execution failed"
        assert error.details["tool_name"] == "document_parser"
        assert error.details["tool_args"] == {"file_path": "/path/to/file.pdf"}


class TestAgentInputError:
    """测试Agent输入错误异常"""

    def test_basic_agent_input_error(self):
        """测试基本Agent输入错误"""
        error = AgentInputError("Invalid input")
        assert error.message == "Invalid input"
        assert isinstance(error, AgentError)

    def test_agent_input_error_with_details(self):
        """测试带详细信息的Agent输入错误"""
        error = AgentInputError(
            "Invalid input",
            input_field="email",
            input_value="invalid-email",
            validation_rule="email_format",
        )

        assert error.message == "Invalid input"
        assert error.details["input_field"] == "email"
        assert error.details["input_value"] == "invalid-email"
        assert error.details["validation_rule"] == "email_format"


class TestAgentStateError:
    """测试Agent状态错误异常"""

    def test_basic_agent_state_error(self):
        """测试基本Agent状态错误"""
        error = AgentStateError("Invalid state")
        assert error.message == "Invalid state"
        assert isinstance(error, AgentError)

    def test_agent_state_error_with_details(self):
        """测试带详细信息的Agent状态错误"""
        error = AgentStateError(
            "Invalid state",
            current_state="processing",
            expected_state=["idle", "ready"],
        )

        assert error.message == "Invalid state"
        assert error.details["current_state"] == "processing"
        assert error.details["expected_state"] == ["idle", "ready"]


class TestAgentConfigurationError:
    """测试Agent配置错误异常"""

    def test_basic_agent_configuration_error(self):
        """测试基本Agent配置错误"""
        error = AgentConfigurationError("Invalid configuration")
        assert error.message == "Invalid configuration"
        assert isinstance(error, AgentError)

    def test_agent_configuration_error_with_details(self):
        """测试带详细信息的Agent配置错误"""
        error = AgentConfigurationError(
            "Invalid configuration",
            config_key="model_name",
            config_value="invalid-model",
        )

        assert error.message == "Invalid configuration"
        assert error.details["config_key"] == "model_name"
        assert error.details["config_value"] == "invalid-model"


class TestAgentMemoryError:
    """测试Agent内存错误异常"""

    def test_basic_agent_memory_error(self):
        """测试基本Agent内存错误"""
        error = AgentMemoryError("Memory operation failed")
        assert error.message == "Memory operation failed"
        assert isinstance(error, AgentError)

    def test_agent_memory_error_with_details(self):
        """测试带详细信息的Agent内存错误"""
        error = AgentMemoryError(
            "Memory operation failed",
            memory_operation="store",
            memory_key="conversation_history",
        )

        assert error.message == "Memory operation failed"
        assert error.details["memory_operation"] == "store"
        assert error.details["memory_key"] == "conversation_history"


class TestAgentCallbackError:
    """测试Agent回调错误异常"""

    def test_basic_agent_callback_error(self):
        """测试基本Agent回调错误"""
        error = AgentCallbackError("Callback failed")
        assert error.message == "Callback failed"
        assert isinstance(error, AgentError)

    def test_agent_callback_error_with_details(self):
        """测试带详细信息的Agent回调错误"""
        error = AgentCallbackError(
            "Callback failed", callback_name="on_llm_start", callback_event="llm_start"
        )

        assert error.message == "Callback failed"
        assert error.details["callback_name"] == "on_llm_start"
        assert error.details["callback_event"] == "llm_start"


class TestWrapLangChainError:
    """测试LangChain异常包装函数"""

    def test_wrap_langchain_error_basic(self):
        """测试基本LangChain异常包装"""
        original_error = ValueError("Original error")
        wrapped_error = wrap_langchain_error(original_error)

        assert isinstance(wrapped_error, LangChainError)
        assert wrapped_error.message == "LangChain操作失败: Original error"
        assert wrapped_error.original_error == original_error

    def test_wrap_langchain_error_with_custom_message(self):
        """测试带自定义消息的LangChain异常包装"""
        original_error = ValueError("Original error")
        wrapped_error = wrap_langchain_error(
            original_error, message="Custom error message"
        )

        assert wrapped_error.message == "Custom error message"
        assert wrapped_error.original_error == original_error

    def test_wrap_langchain_error_with_agent_name(self):
        """测试带Agent名称的LangChain异常包装"""
        original_error = ValueError("Original error")
        wrapped_error = wrap_langchain_error(
            original_error, agent_name="DocumentProcessor"
        )

        assert wrapped_error.details["agent_name"] == "DocumentProcessor"

    def test_wrap_langchain_error_with_component(self):
        """测试带组件信息的LangChain异常包装"""
        original_error = ValueError("Original error")
        wrapped_error = wrap_langchain_error(
            original_error, langchain_component="ChatOpenAI"
        )

        assert wrapped_error.details["langchain_component"] == "ChatOpenAI"
