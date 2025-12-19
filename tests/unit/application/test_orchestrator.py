"""
生成命令: /speckit.implement T018
生成时间: 2025-12-09
来源: specs/001-multi-agent-doc-system/tasks.md
"""

"""Agent编排器测试

测试AgentOrchestrator和相关组件的功能。
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from src.application.agent_base import AgentConfig, AgentStatus, BaseAgent

# 项目导入
from src.application.orchestrator import (
    AgentExecutionResult,
    AgentOrchestrator,
    OrchestrationConfig,
    create_orchestrator,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.agent_exceptions import (
    AgentOrchestrationError,
)


class MockAgent(BaseAgent):
    """测试用的Mock Agent"""

    def __init__(self, config, llm_service=None, memory=None):
        super().__init__(config, llm_service, memory)
        self._invoke_result = {"status": "completed", "messages": []}

    def get_tools(self) -> list:
        return []

    def set_invoke_result(self, result):
        """设置调用结果用于测试"""
        self._invoke_result = result

    async def invoke(self, input_data, config=None):
        return self._invoke_result

    async def ainvoke(self, input_data, config=None):
        return self._invoke_result

    @property
    def status(self):
        """获取Agent状态"""
        return self.get_status()


class TestOrchestrationConfig:
    """编排器配置测试"""

    def test_orchestration_config_creation(self):
        """测试编排器配置创建"""
        config: OrchestrationConfig = {
            "orchestrator_id": "test_orchestrator_001",
            "max_concurrent_agents": 5,
            "default_timeout": 300,
            "enable_parallel_execution": True,
            "error_handling_strategy": "continue",
        }

        assert config["orchestrator_id"] == "test_orchestrator_001"
        assert config["max_concurrent_agents"] == 5
        assert config["enable_parallel_execution"] is True


class TestAgentOrchestrator:
    """Agent编排器测试"""

    @pytest.fixture
    def mock_llm_service(self):
        """Mock LLM服务"""
        return Mock(spec=LLMService)

    @pytest.fixture
    def orchestration_config(self) -> OrchestrationConfig:
        """测试编排器配置"""
        return {
            "orchestrator_id": "test_orchestrator_001",
            "max_concurrent_agents": 5,
            "default_timeout": 300,
            "enable_parallel_execution": True,
            "error_handling_strategy": "continue",
        }

    @pytest.fixture
    def orchestrator(self, orchestration_config, mock_llm_service):
        """测试编排器实例"""
        return AgentOrchestrator(orchestration_config, mock_llm_service)

    @pytest.fixture
    def agent_config_1(self) -> AgentConfig:
        """测试Agent配置1"""
        return {
            "agent_id": "agent_001",
            "agent_name": "测试Agent1",
            "agent_type": "test",
            "description": "第一个测试Agent",
            "model_provider": "openai_compatible",
            "temperature": 0.7,
            "max_tokens": 4096,
            "enable_memory": True,
        }

    @pytest.fixture
    def agent_config_2(self) -> AgentConfig:
        """测试Agent配置2"""
        return {
            "agent_id": "agent_002",
            "agent_name": "测试Agent2",
            "agent_type": "test",
            "description": "第二个测试Agent",
            "model_provider": "openai_compatible",
            "temperature": 0.7,
            "max_tokens": 4096,
            "enable_memory": True,
        }

    def test_orchestrator_initialization(self, orchestrator, orchestration_config):
        """测试编排器初始化"""
        assert orchestrator.orchestrator_id == "test_orchestrator_001"
        assert orchestrator.config == orchestration_config
        assert len(orchestrator._agents) == 0
        assert len(orchestrator._agent_configs) == 0

    def test_agent_registration(self, orchestrator, agent_config_1):
        """测试Agent注册"""
        agent = MockAgent(agent_config_1)

        # 注册Agent
        orchestrator.register_agent(agent)

        # 验证注册结果
        assert "agent_001" in orchestrator._agents
        assert orchestrator._agents["agent_001"] == agent
        assert "agent_001" in orchestrator._agent_configs
        assert orchestrator._agent_configs["agent_001"] == agent_config_1

    def test_agent_config_registration(self, orchestrator, agent_config_1):
        """测试Agent配置注册"""
        # 注册配置
        orchestrator.register_agent_config(agent_config_1)

        # 验证注册结果
        assert "agent_001" in orchestrator._agent_configs
        assert orchestrator._agent_configs["agent_001"] == agent_config_1

    def test_agent_registration_override(self, orchestrator, agent_config_1):
        """测试Agent注册覆盖"""
        agent1 = MockAgent(agent_config_1)
        agent2 = MockAgent(agent_config_1)

        # 注册两次
        orchestrator.register_agent(agent1)
        orchestrator.register_agent(agent2)

        # 验证覆盖
        assert orchestrator._agents["agent_001"] == agent2

    def test_plan_creation_no_dependencies(
        self, orchestrator, agent_config_1, agent_config_2
    ):
        """测试无依赖关系的计划创建"""
        plan = orchestrator.create_plan(
            name="测试计划",
            description="无依赖关系测试计划",
            agent_configs=[agent_config_1, agent_config_2],
        )

        # 验证计划结构
        assert plan["name"] == "测试计划"
        assert plan["description"] == "无依赖关系测试计划"
        assert len(plan["agents"]) == 2
        assert len(plan["dependencies"]) == 0
        assert len(plan["execution_order"]) == 1  # 应该只有一层
        assert set(plan["execution_order"][0]) == {"agent_001", "agent_002"}

    def test_plan_creation_with_dependencies(
        self, orchestrator, agent_config_1, agent_config_2
    ):
        """测试有依赖关系的计划创建"""
        dependencies = {"agent_002": ["agent_001"]}  # agent_002 依赖 agent_001

        plan = orchestrator.create_plan(
            name="依赖测试计划",
            description="有依赖关系测试计划",
            agent_configs=[agent_config_1, agent_config_2],
            dependencies=dependencies,
        )

        # 验证依赖关系
        assert plan["dependencies"] == dependencies
        assert len(plan["execution_order"]) == 2  # 应该有两层
        assert plan["execution_order"][0] == ["agent_001"]  # 第一层
        assert plan["execution_order"][1] == ["agent_002"]  # 第二层

    def test_execution_order_calculation(self, orchestrator):
        """测试执行顺序计算"""
        # 复杂依赖关系:A->B, A->C, B->D, C->D
        dependencies = {
            "agent_B": ["agent_A"],
            "agent_C": ["agent_A"],
            "agent_D": ["agent_B", "agent_C"],
        }
        agent_ids = ["agent_A", "agent_B", "agent_C", "agent_D"]

        execution_order = orchestrator._calculate_execution_order(
            agent_ids, dependencies
        )

        # 验证执行顺序
        assert len(execution_order) == 3
        assert execution_order[0] == ["agent_A"]  # 第一层:无依赖
        assert set(execution_order[1]) == {"agent_B", "agent_C"}  # 第二层:依赖A
        assert execution_order[2] == ["agent_D"]  # 第三层:依赖B和C

    def test_circular_dependency_detection(self, orchestrator):
        """测试循环依赖检测"""
        # 循环依赖:A->B, B->C, C->A
        dependencies = {
            "agent_B": ["agent_A"],
            "agent_C": ["agent_B"],
            "agent_A": ["agent_C"],
        }
        agent_ids = ["agent_A", "agent_B", "agent_C"]

        with pytest.raises(AgentOrchestrationError, match="循环依赖"):
            orchestrator._calculate_execution_order(agent_ids, dependencies)

    @pytest.mark.asyncio
    async def test_plan_execution_parallel(
        self, orchestrator, agent_config_1, agent_config_2
    ):
        """测试计划并行执行"""
        # 创建Mock Agent
        agent1 = MockAgent(agent_config_1)
        agent2 = MockAgent(agent_config_2)

        # 设置调用结果
        agent1.set_invoke_result({"status": "completed", "messages": []})
        agent2.set_invoke_result({"status": "completed", "messages": []})

        # 注册Agent
        orchestrator.register_agent(agent1)
        orchestrator.register_agent(agent2)

        # 创建计划
        plan = orchestrator.create_plan(
            name="并行执行测试",
            description="测试并行执行",
            agent_configs=[agent_config_1, agent_config_2],
        )

        # 执行计划
        input_data = {"messages": [{"role": "user", "content": "测试输入"}]}
        results = await orchestrator.execute_plan(plan, input_data)

        # 验证结果
        assert len(results) == 2
        assert "agent_001" in results
        assert "agent_002" in results
        assert results["agent_001"]["status"] == "completed"
        assert results["agent_002"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_plan_execution_sequential(
        self, orchestrator, agent_config_1, agent_config_2
    ):
        """测试计划顺序执行"""
        # 创建顺序执行的编排器
        config_sequential = orchestrator.config.copy()
        config_sequential["enable_parallel_execution"] = False
        orchestrator_sequential = AgentOrchestrator(config_sequential)

        # 创建Mock Agent
        agent1 = MockAgent(agent_config_1)
        agent2 = MockAgent(agent_config_2)

        # 设置调用结果
        agent1.set_invoke_result({"status": "completed", "messages": []})
        agent2.set_invoke_result({"status": "completed", "messages": []})

        # 注册Agent
        orchestrator_sequential.register_agent(agent1)
        orchestrator_sequential.register_agent(agent2)

        # 创建计划
        plan = orchestrator_sequential.create_plan(
            name="顺序执行测试",
            description="测试顺序执行",
            agent_configs=[agent_config_1, agent_config_2],
        )

        # 执行计划
        input_data = {"messages": [{"role": "user", "content": "测试输入"}]}
        results = await orchestrator_sequential.execute_plan(plan, input_data)

        # 验证结果
        assert len(results) == 2
        assert "agent_001" in results
        assert "agent_002" in results
        assert results["agent_001"]["status"] == "completed"
        assert results["agent_002"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_plan_execution_with_dependencies(
        self, orchestrator, agent_config_1, agent_config_2
    ):
        """测试有依赖关系的计划执行"""
        # 创建Mock Agent
        agent1 = MockAgent(agent_config_1)
        agent2 = MockAgent(agent_config_2)

        # 设置调用结果
        agent1.set_invoke_result({"status": "completed", "messages": []})
        agent2.set_invoke_result({"status": "completed", "messages": []})

        # 注册Agent
        orchestrator.register_agent(agent1)
        orchestrator.register_agent(agent2)

        # 创建有依赖关系的计划
        dependencies = {"agent_002": ["agent_001"]}
        plan = orchestrator.create_plan(
            name="依赖执行测试",
            description="测试依赖执行",
            agent_configs=[agent_config_1, agent_config_2],
            dependencies=dependencies,
        )

        # 执行计划
        input_data = {"messages": [{"role": "user", "content": "测试输入"}]}
        results = await orchestrator.execute_plan(plan, input_data)

        # 验证结果
        assert len(results) == 2
        assert results["agent_001"]["status"] == "completed"
        assert results["agent_002"]["status"] == "completed"

        # 验证执行顺序(agent_001应该先执行)
        agent1_end = results["agent_001"]["end_time"]
        agent2_start = results["agent_002"]["start_time"]
        assert agent1_end <= agent2_start

    @pytest.mark.asyncio
    async def test_agent_creation_not_implemented(self, orchestrator, agent_config_1):
        """测试Agent创建未实现错误"""
        # 只注册配置,不注册Agent实例
        orchestrator.register_agent_config(agent_config_1)

        plan = orchestrator.create_plan(
            name="未实现测试",
            description="测试未实现的Agent创建",
            agent_configs=[agent_config_1],
        )

        input_data = {"messages": []}

        # 执行计划(由于默认错误处理策略是continue,不会抛出异常)
        results = await orchestrator.execute_plan(plan, input_data)

        # 验证执行结果包含错误信息
        assert "agent_001" in results
        assert results["agent_001"]["status"] == "failed"
        assert "需要实现具体Agent的创建逻辑" in results["agent_001"]["error"]

    def test_get_agent_status(self, orchestrator, agent_config_1):
        """测试获取Agent状态"""
        agent = MockAgent(agent_config_1)
        orchestrator.register_agent(agent)

        # 测试注册的Agent状态
        status = orchestrator.get_agent_status("agent_001")
        assert status == AgentStatus.IDLE

        # 测试不存在的Agent
        status = orchestrator.get_agent_status("nonexistent")
        assert status is None

    def test_get_execution_results(self, orchestrator):
        """测试获取执行结果"""
        # 初始结果为空
        results = orchestrator.get_execution_results()
        assert results == {}

        # 模拟结果
        mock_result: AgentExecutionResult = {
            "agent_id": "test_agent",
            "agent_name": "测试Agent",
            "status": "completed",
            "start_time": datetime.now(),
            "end_time": datetime.now(),
            "result": None,
            "error": None,
            "execution_time": 1.0,
        }

        orchestrator._execution_results["test_agent"] = mock_result

        # 获取结果
        results = orchestrator.get_execution_results()
        assert "test_agent" in results
        assert results["test_agent"]["status"] == "completed"

    def test_orchestrator_reset(self, orchestrator, agent_config_1):
        """测试编排器重置"""
        agent = MockAgent(agent_config_1)
        orchestrator.register_agent(agent)

        # 设置一些状态
        orchestrator._execution_results["test"] = {"status": "test"}
        orchestrator._current_plan = {"plan_id": "test"}

        # 重置
        orchestrator.reset()

        # 验证重置结果
        assert len(orchestrator._execution_results) == 0
        assert orchestrator._current_plan is None
        assert agent.get_status() == AgentStatus.IDLE

    def test_orchestration_middleware(self, orchestrator):
        """测试编排中间件"""

        def dummy_middleware(data):
            return data

        orchestrator.add_orchestration_middleware(dummy_middleware)

        assert len(orchestrator._orchestration_middleware) == 1
        assert orchestrator._orchestration_middleware[0] == dummy_middleware

    def test_string_representation(self, orchestrator):
        """测试字符串表示"""
        str_repr = str(orchestrator)
        assert "AgentOrchestrator" in str_repr
        assert "test_orchestrator_001" in str_repr
        assert "0" in str_repr  # agent count


class TestCreateOrchestrator:
    """创建编排器便捷函数测试"""

    def test_create_orchestrator_default(self):
        """测试默认参数创建编排器"""
        orchestrator = create_orchestrator("test_orch")

        assert orchestrator.orchestrator_id == "test_orch"
        assert orchestrator.config["max_concurrent_agents"] == 10
        assert orchestrator.config["enable_parallel_execution"] is True
        assert orchestrator.config["error_handling_strategy"] == "continue"

    def test_create_orchestrator_custom(self):
        """测试自定义参数创建编排器"""
        orchestrator = create_orchestrator(
            "custom_orch", max_concurrent_agents=5, error_handling_strategy="fail_fast"
        )

        assert orchestrator.orchestrator_id == "custom_orch"
        assert orchestrator.config["max_concurrent_agents"] == 5
        assert orchestrator.config["error_handling_strategy"] == "fail_fast"


if __name__ == "__main__":
    pytest.main([__file__])
