"""
生成命令: /speckit.implement T018
生成时间: 2025-12-09
来源: specs/001-multi-agent-doc-system/tasks.md

Agent编排器

基于LangChain 1.0的Agent编排器,实现:
1. 多Agent协作编排
2. 统一的生命周期管理
3. 中间件支持
4. 错误隔离和恢复
5. 可观测性

完全基于LangChain 1.0的LCEL和Runnable接口,不依赖LangGraph。
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig

from src.shared.config.llm_service import LLMService
from src.shared.exceptions.agent_exceptions import (
    AgentConfigurationError,
    AgentOrchestrationError,
)
from src.shared.utils.logging import get_logger

# 项目导入
from .agent_base import AgentConfig, AgentStatus, BaseAgent

logger = get_logger(__name__)


class OrchestrationConfig(TypedDict):
    """编排器配置"""

    orchestrator_id: str
    max_concurrent_agents: int
    default_timeout: int
    enable_parallel_execution: bool
    error_handling_strategy: str  # 'fail_fast', 'continue', 'retry'


class AgentExecutionResult(TypedDict):
    """Agent执行结果"""

    agent_id: str
    agent_name: str
    status: str
    start_time: datetime
    end_time: datetime | None
    result: dict[str, Any] | None  # Agent执行结果,包含messages和structured_response
    error: str | None
    execution_time: float | None


class OrchestrationPlan(TypedDict):
    """编排计划"""

    plan_id: str
    name: str
    description: str
    agents: list[AgentConfig]
    dependencies: dict[str, list[str]]  # agent_id -> list of dependent agent_ids
    execution_order: list[list[str]]  # 并行执行的agent组


class AgentOrchestrator:
    """Agent编排器

    基于LangChain 1.0的Agent编排器,支持:
    1. 多Agent协作
    2. 依赖管理
    3. 并行执行
    4. 错误隔离
    5. 可观测性

    完全基于LangChain 1.0的LCEL和Runnable接口实现,不依赖LangGraph。
    """

    def __init__(
        self,
        config: OrchestrationConfig,
        llm_service: LLMService | None = None,
    ):
        """初始化编排器

        Args:
            config: 编排器配置
            llm_service: LLM服务实例
        """
        self.config = config
        self.orchestrator_id = config["orchestrator_id"]

        # LLM服务
        self.llm_service = llm_service or LLMService()

        # Agent注册表
        self._agents: dict[str, BaseAgent] = {}
        self._agent_configs: dict[str, AgentConfig] = {}

        # 执行状态
        self._execution_results: dict[str, AgentExecutionResult] = {}
        self._current_plan: OrchestrationPlan | None = None

        # 中间件
        self._orchestration_middleware: list[callable] = []

        logger.info("初始化Agent编排器: %s", self.orchestrator_id)

    def register_agent(self, agent: BaseAgent) -> None:
        """注册Agent

        Args:
            agent: Agent实例
        """
        agent_id = agent.agent_id
        if agent_id in self._agents:
            logger.warning("Agent %s 已存在,将被替换", agent_id)

        self._agents[agent_id] = agent
        self._agent_configs[agent_id] = agent.config

        logger.info("注册Agent: %s (ID: %s)", agent.agent_name, agent_id)

    def register_agent_config(self, config: AgentConfig) -> None:
        """注册Agent配置

        Args:
            config: Agent配置
        """
        agent_id = config["agent_id"]
        self._agent_configs[agent_id] = config

        logger.debug("注册Agent配置: %s (ID: %s)", config["agent_name"], agent_id)

    def create_plan(
        self,
        name: str,
        description: str,
        agent_configs: list[AgentConfig],
        dependencies: dict[str, list[str]] | None = None,
    ) -> OrchestrationPlan:
        """创建编排计划

        Args:
            name: 计划名称
            description: 计划描述
            agent_configs: Agent配置列表
            dependencies: Agent依赖关系

        Returns:
            编排计划
        """
        plan_id = str(uuid.uuid4())

        # 注册Agent配置
        for config in agent_configs:
            self.register_agent_config(config)

        # 分析依赖关系,确定执行顺序
        execution_order = self._calculate_execution_order(
            [config["agent_id"] for config in agent_configs], dependencies or {}
        )

        plan: OrchestrationPlan = {
            "plan_id": plan_id,
            "name": name,
            "description": description,
            "agents": agent_configs,
            "dependencies": dependencies or {},
            "execution_order": execution_order,
        }

        logger.info("创建编排计划: %s (ID: %s)", name, plan_id)
        logger.debug("执行顺序: %s", execution_order)

        return plan

    def _calculate_execution_order(
        self, agent_ids: list[str], dependencies: dict[str, list[str]]
    ) -> list[list[str]]:
        """计算执行顺序

        Args:
            agent_ids: Agent ID列表
            dependencies: 依赖关系,格式为 {agent_id: [depends_on_agent_ids]}

        Returns:
            分层执行顺序,每层可并行执行
        """
        # 简化的拓扑排序算法
        in_degree = dict.fromkeys(agent_ids, 0)

        # 计算入度:如果agent_id依赖于dep,那么agent_id的入度增加
        for agent_id in agent_ids:
            for dep in dependencies.get(agent_id, []):
                if dep in in_degree:
                    in_degree[agent_id] += 1

        # 拓扑排序
        execution_order = []
        remaining = set(agent_ids)

        while remaining:
            # 找到当前层可以执行的Agent(无依赖或依赖已满足)
            current_layer = [
                agent_id for agent_id in remaining if in_degree[agent_id] == 0
            ]

            if not current_layer:
                msg = "存在循环依赖"
                raise AgentOrchestrationError(msg)

            execution_order.append(current_layer)

            # 更新依赖:当agent_id执行完成后,依赖于它的其他agent的入度减少
            for agent_id in current_layer:
                remaining.remove(agent_id)
                # 查找哪些agent依赖于当前agent_id
                for other_agent_id, deps in dependencies.items():
                    if agent_id in deps and other_agent_id in remaining:
                        in_degree[other_agent_id] -= 1

        return execution_order

    async def execute_plan(
        self,
        plan: OrchestrationPlan,
        input_data: dict[str, Any],
        config: RunnableConfig | None = None,
    ) -> dict[str, AgentExecutionResult]:
        """执行编排计划

        Args:
            plan: 编排计划
            input_data: 输入数据
            config: 运行配置

        Returns:
            执行结果字典
        """
        self._current_plan = plan
        self._execution_results.clear()

        logger.info("开始执行编排计划: %s (ID: %s)", plan["name"], plan["plan_id"])

        # 初始化共享状态
        shared_state: dict[str, Any] = {
            "input": input_data,
            "intermediate_results": {},
            "errors": {},
        }

        try:
            # 按执行顺序执行Agent
            for layer_idx, agent_ids in enumerate(plan["execution_order"]):
                logger.info("执行第 %d 层Agent: %s", layer_idx + 1, agent_ids)

                # 并行执行当前层的Agent
                if self.config.get("enable_parallel_execution", True):
                    layer_results = await self._execute_layer_parallel(
                        agent_ids, shared_state, config
                    )
                else:
                    layer_results = await self._execute_layer_sequential(
                        agent_ids, shared_state, config
                    )

                # 更新共享状态
                self._update_shared_state(shared_state, layer_results)

                # 检查错误处理策略
                strategy = self.config.get("error_handling_strategy", "continue")
                if strategy == "fail_fast" and any(
                    r["error"] for r in layer_results.values()
                ):
                    logger.error("检测到错误,根据fail_fast策略停止执行")
                    break

            logger.info("编排计划执行完成: %s", plan["name"])
            return self._execution_results

        except Exception as e:
            logger.error("编排计划执行失败: %s", e)
            msg = f"计划执行失败: {e}"
            raise AgentOrchestrationError(msg) from e

    async def _execute_layer_parallel(
        self,
        agent_ids: list[str],
        shared_state: dict[str, Any],
        config: RunnableConfig | None,
    ) -> dict[str, AgentExecutionResult]:
        """并行执行一层Agent

        Args:
            agent_ids: Agent ID列表
            shared_state: 共享状态
            config: 运行配置

        Returns:
            执行结果
        """
        # 创建并发任务
        tasks = []
        for agent_id in agent_ids:
            task = self._execute_single_agent(agent_id, shared_state, config)
            tasks.append(task)

        # 并行执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        layer_results: dict[str, AgentExecutionResult] = {}
        for i, result in enumerate(results):
            agent_id = agent_ids[i]
            if isinstance(result, Exception):
                layer_results[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": agent_id,
                    "status": "failed",
                    "start_time": datetime.now(),
                    "end_time": datetime.now(),
                    "result": None,
                    "error": str(result),
                    "execution_time": 0.0,
                }
                logger.error("Agent %s 执行失败: %s", agent_id, result)
            else:
                layer_results[agent_id] = result

        return layer_results

    async def _execute_layer_sequential(
        self,
        agent_ids: list[str],
        shared_state: dict[str, Any],
        config: RunnableConfig | None,
    ) -> dict[str, AgentExecutionResult]:
        """顺序执行一层Agent

        Args:
            agent_ids: Agent ID列表
            shared_state: 共享状态
            config: 运行配置

        Returns:
            执行结果
        """
        layer_results: dict[str, AgentExecutionResult] = {}

        for agent_id in agent_ids:
            try:
                result = await self._execute_single_agent(
                    agent_id, shared_state, config
                )
                layer_results[agent_id] = result

                # 更新共享状态,以便后续Agent使用
                shared_state["intermediate_results"][agent_id] = result

            except Exception as e:
                layer_results[agent_id] = {
                    "agent_id": agent_id,
                    "agent_name": agent_id,
                    "status": "failed",
                    "start_time": datetime.now(),
                    "end_time": datetime.now(),
                    "result": None,
                    "error": str(e),
                    "execution_time": 0.0,
                }
                logger.error("Agent %s 执行失败: %s", agent_id, e)

                # 根据错误处理策略决定是否继续
                strategy = self.config.get("error_handling_strategy", "continue")
                if strategy == "fail_fast":
                    break

        return layer_results

    async def _execute_single_agent(
        self, agent_id: str, shared_state: dict[str, Any], config: RunnableConfig | None
    ) -> AgentExecutionResult:
        """执行单个Agent

        Args:
            agent_id: Agent ID
            shared_state: 共享状态
            config: 运行配置

        Returns:
            执行结果
        """
        start_time = datetime.now()

        try:
            # 获取或创建Agent
            agent = self._get_or_create_agent(agent_id)

            # 准备输入数据
            agent_input = {
                "messages": shared_state["input"].get("messages", []),
                "context": {
                    "shared_state": shared_state,
                    "agent_id": agent_id,
                },
            }

            # 执行Agent
            logger.info("执行Agent: %s (ID: %s)", agent.agent_name, agent_id)

            result = await agent.invoke(agent_input, config)

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            execution_result: AgentExecutionResult = {
                "agent_id": agent_id,
                "agent_name": agent.agent_name,
                "status": "completed",
                "start_time": start_time,
                "end_time": end_time,
                "result": result,
                "error": None,
                "execution_time": execution_time,
            }

            self._execution_results[agent_id] = execution_result
            logger.info(
                "Agent %s 执行完成,耗时: %.2f秒", agent.agent_name, execution_time
            )

            return execution_result

        except Exception as e:
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            execution_result: AgentExecutionResult = {
                "agent_id": agent_id,
                "agent_name": agent_id,
                "status": "failed",
                "start_time": start_time,
                "end_time": end_time,
                "result": None,
                "error": str(e),
                "execution_time": execution_time,
            }

            self._execution_results[agent_id] = execution_result
            logger.error("Agent %s 执行失败: %s", agent_id, e)

            raise

    def _get_or_create_agent(self, agent_id: str) -> BaseAgent:
        """获取或创建Agent实例

        Args:
            agent_id: Agent ID

        Returns:
            Agent实例
        """
        if agent_id in self._agents:
            return self._agents[agent_id]

        if agent_id not in self._agent_configs:
            msg = "未找到Agent配置: %s", agent_id
            raise AgentConfigurationError(msg)

        # 这里需要根据配置创建具体的Agent实例
        # 由于这是基础框架,我们抛出未实现异常
        # 子类应该重写此方法来创建具体的Agent
        msg = "需要实现具体Agent的创建逻辑。Agent ID: %s", agent_id
        raise NotImplementedError(msg)

    def _update_shared_state(
        self,
        shared_state: dict[str, Any],
        layer_results: dict[str, AgentExecutionResult],
    ) -> None:
        """更新共享状态

        Args:
            shared_state: 共享状态
            layer_results: 层执行结果
        """
        for agent_id, result in layer_results.items():
            if result["status"] == "completed" and result["result"]:
                shared_state["intermediate_results"][agent_id] = result["result"]
            elif result["error"]:
                shared_state["errors"][agent_id] = result["error"]

    def get_execution_results(self) -> dict[str, AgentExecutionResult]:
        """获取执行结果

        Returns:
            执行结果字典
        """
        return self._execution_results.copy()

    def get_agent_status(self, agent_id: str) -> AgentStatus | None:
        """获取Agent状态

        Args:
            agent_id: Agent ID

        Returns:
            Agent状态
        """
        if agent_id in self._agents:
            return self._agents[agent_id].get_status()
        elif agent_id in self._execution_results:
            result = self._execution_results[agent_id]
            return AgentStatus(result["status"])
        return None

    def reset(self) -> None:
        """重置编排器状态"""
        for agent in self._agents.values():
            agent.reset()

        self._execution_results.clear()
        self._current_plan = None

        logger.info("编排器 %s 状态已重置", self.orchestrator_id)

    def add_orchestration_middleware(self, middleware: callable) -> None:
        """添加编排中间件

        Args:
            middleware: 中间件函数
        """
        self._orchestration_middleware.append(middleware)
        logger.debug("添加编排中间件: %s", middleware.__name__)

    def __str__(self) -> str:
        return (
            "AgentOrchestrator(id=%s, agents=%s)",
            self.orchestrator_id,
            len(self._agents),
        )

    def __repr__(self) -> str:
        return self.__str__()


# 便捷函数
def create_orchestrator(
    orchestrator_id: str, max_concurrent_agents: int = 10, **kwargs
) -> AgentOrchestrator:
    """创建编排器的便捷函数

    Args:
        orchestrator_id: 编排器ID
        max_concurrent_agents: 最大并发Agent数
        **kwargs: 其他配置参数

    Returns:
        编排器实例
    """
    config: OrchestrationConfig = {
        "orchestrator_id": orchestrator_id,
        "max_concurrent_agents": max_concurrent_agents,
        "default_timeout": 300,
        "enable_parallel_execution": True,
        "error_handling_strategy": kwargs.get("error_handling_strategy", "continue"),
    }

    return AgentOrchestrator(config)
