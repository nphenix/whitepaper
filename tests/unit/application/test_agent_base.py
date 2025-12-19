"""
生成命令: /speckit.implement T018
生成时间: 2025-12-09
重构时间: 2025-12-09
重构说明: 更新测试以匹配新的API(使用create_agent替代手搓LCEL链)
"""

"""Agent基础框架测试

测试BaseAgent和相关组件的功能。
基于LangChain 1.0的create_agent API。
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AIMessage, HumanMessage

# 项目导入
from src.application.agent_base import AgentConfig, AgentStatus, BaseAgent
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.agent_exceptions import (
    AgentConfigurationError,
    AgentExecutionError,
)


class MockAgent(BaseAgent):
    """测试用的Mock Agent"""

    def get_tools(self) -> list:
        return []

    def __str__(self) -> str:
        return f"MockAgent(id={self.agent_id}, name={self.agent_name}, type={self.agent_type})"


class TestAgentConfig:
    """AgentConfig测试"""

    def test_agent_config_creation(self):
        """测试Agent配置创建"""
        config: AgentConfig = {
            "agent_id": "test_agent_001",
            "agent_name": "测试Agent",
            "agent_type": "test",
            "description": "用于测试的Agent",
            "model_provider": "openai_compatible",
            "model_name": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 4096,
            "tools": [],
            "enable_tool_calling": False,
            "max_steps": 10,
            "timeout": 300,
            "enable_memory": True,
            "middleware_config": {},
        }

        assert config["agent_id"] == "test_agent_001"
        assert config["agent_name"] == "测试Agent"
        assert config["model_provider"] == "openai_compatible"


class TestBaseAgent:
    """BaseAgent测试"""

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM服务"""
        from unittest.mock import AsyncMock, Mock

        service = Mock(spec=LLMService)
        mock_model = Mock(spec=BaseLanguageModel)

        # 创建AsyncMock对象,确保支持async/await
        mock_model.ainvoke = AsyncMock(return_value=AIMessage(content="测试响应"))
        mock_model.invoke = AsyncMock(return_value=AIMessage(content="测试响应"))

        # 确保Mock对象有正确的spec
        service.get_chat_model = Mock(return_value=mock_model)
        return service

    @pytest.fixture
    def agent_config(self) -> AgentConfig:
        """测试Agent配置"""
        return {
            "agent_id": "test_agent_001",
            "agent_name": "测试Agent",
            "agent_type": "test",
            "description": "用于测试的Agent",
            "model_provider": "openai_compatible",
            "model_name": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 4096,
            "tools": [],
            "enable_tool_calling": False,
            "max_steps": 10,
            "timeout": 300,
            "enable_memory": True,
            "middleware_config": {},
        }

    @pytest.fixture
    def agent(self, agent_config, mock_llm_service):
        """测试Agent实例"""
        return MockAgent(agent_config, mock_llm_service)

    def test_agent_initialization(self, agent, agent_config, mock_llm_service):
        """测试Agent初始化"""
        assert agent.agent_id == "test_agent_001"
        assert agent.agent_name == "测试Agent"
        assert agent.agent_type == "test"
        assert agent.get_status() == AgentStatus.IDLE
        assert agent.llm_service == mock_llm_service

    def test_agent_model_property(self, agent, mock_llm_service):
        """测试模型属性获取"""
        model = agent.model
        assert model is not None
        mock_llm_service.get_chat_model.assert_called_once_with(
            provider="openai_compatible"
        )

    def test_agent_model_caching(self, agent, mock_llm_service):
        """测试模型实例缓存"""
        # 第一次调用
        model1 = agent.model
        # 第二次调用
        model2 = agent.model

        assert model1 is model2
        # 只应该调用一次
        mock_llm_service.get_chat_model.assert_called_once()

    def test_agent_model_loading_error(self, agent_config):
        """测试模型加载错误"""
        mock_llm_service = Mock(spec=LLMService)
        mock_llm_service.get_chat_model.side_effect = Exception("模型加载失败")

        agent = MockAgent(agent_config, mock_llm_service)

        with pytest.raises(AgentConfigurationError):
            _ = agent.model

    def test_agent_system_message(self, agent):
        """测试系统消息"""
        prompt = agent._get_system_message()
        assert "测试Agent" in prompt

    def test_agent_tools(self, agent):
        """测试工具获取"""
        tools = agent.get_tools()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    @patch("src.application.agent_base.create_agent")
    async def test_agent_invoke_success(
        self, mock_create_agent, agent, mock_llm_service
    ):
        """测试Agent调用成功(使用create_agent)"""
        # Mock create_agent返回的Agent
        mock_agent_runnable = AsyncMock()
        mock_agent_runnable.ainvoke = AsyncMock(
            return_value={"messages": [AIMessage(content="测试响应")]}
        )
        mock_create_agent.return_value = mock_agent_runnable

        # 准备输入数据
        input_data = {
            "messages": [HumanMessage(content="测试输入")],
        }

        # 执行Agent
        result = await agent.ainvoke(input_data)

        # 验证结果
        assert isinstance(result, dict)
        assert "messages" in result
        assert agent.get_status() == AgentStatus.COMPLETED

        # 验证create_agent被调用
        mock_create_agent.assert_called_once()

        # 验证Agent的ainvoke被调用
        mock_agent_runnable.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_invoke_with_no_messages(self, agent):
        """测试无消息输入的Agent调用"""
        input_data = {"messages": []}

        with pytest.raises(AgentExecutionError):
            await agent.ainvoke(input_data)

    def test_agent_result_management(self, agent):
        """测试Agent结果管理"""
        # 初始状态
        assert agent.get_status() == AgentStatus.IDLE
        assert agent.get_result() is None

        # 模拟结果更新
        mock_result = {
            "messages": [AIMessage(content="测试响应")],
        }

        agent._current_result = mock_result
        agent._status = AgentStatus.COMPLETED

        # 验证结果
        assert agent.get_status() == AgentStatus.COMPLETED
        assert agent.get_result() == mock_result

    def test_agent_reset(self, agent):
        """测试Agent重置"""
        # 设置一些状态
        agent._status = AgentStatus.COMPLETED
        agent._current_result = {"messages": [AIMessage(content="测试")]}

        # 重置
        agent.reset()

        # 验证重置结果
        assert agent.get_status() == AgentStatus.IDLE
        assert agent.get_result() is None

    def test_agent_string_representation(self, agent):
        """测试Agent字符串表示"""
        str_repr = str(agent)
        assert "test_agent_001" in str_repr
        assert "测试Agent" in str_repr
        assert "test" in str_repr


class TestAgentCreation:
    """Agent创建测试(基于create_agent)"""

    @pytest.fixture
    def agent_config(self) -> AgentConfig:
        """测试Agent配置"""
        return {
            "agent_id": "creation_test_agent",
            "agent_name": "创建测试Agent",
            "agent_type": "test",
            "description": "用于创建测试的Agent",
            "model_provider": "openai_compatible",
            "model_name": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 4096,
            "tools": [],
            "enable_tool_calling": False,
            "max_steps": 5,
            "timeout": 300,
            "enable_memory": False,
            "middleware_config": {},
        }

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM服务"""
        service = Mock(spec=LLMService)
        mock_model = Mock(spec=BaseLanguageModel)
        service.get_chat_model = Mock(return_value=mock_model)
        return service

    @patch("src.application.agent_base.create_agent")
    def test_agent_creation(self, mock_create_agent, agent_config, mock_llm_service):
        """测试Agent创建(使用create_agent)"""
        mock_agent_runnable = Mock()
        mock_create_agent.return_value = mock_agent_runnable

        agent = MockAgent(agent_config, mock_llm_service)

        # 调用_build_agent
        result = agent._build_agent()

        # 验证create_agent被调用
        mock_create_agent.assert_called_once()
        assert result == mock_agent_runnable

        # 验证调用参数
        call_args = mock_create_agent.call_args
        assert call_args.kwargs["model"] is not None
        assert (
            "system_message" in call_args.kwargs or "system_prompt" in call_args.kwargs
        )
        assert call_args.kwargs["tools"] == []


if __name__ == "__main__":
    pytest.main([__file__])
