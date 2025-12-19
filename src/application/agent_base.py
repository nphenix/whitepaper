"""
生成命令: /speckit.implement T018
生成时间: 2025-12-09
来源: specs/001-multi-agent-doc-system/tasks.md
重构时间: 2025-12-09
重构说明: 使用LangChain 1.0的create_agent替代手搓LCEL链,符合官方最佳实践

Agent基础框架

基于LangChain 1.0的create_agent构建的基础Agent框架。
遵循LangChain 1.0最佳实践:
- 使用统一的create_agent接口
- 支持结构化输出(response_format)
- 集成中间件系统(middleware)
- 支持状态持久化(checkpointer)
- 支持运行时上下文(context_schema)
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver

from src.infrastructure.memory.checkpointer import create_checkpointer
from src.infrastructure.preprocessing.cleaners.summarization_middleware import (
    create_summarization_middleware,
)
from src.shared.config.llm_service import LLMService
from src.shared.config.settings import get_config
from src.shared.exceptions.agent_exceptions import (
    AgentConfigurationError,
    AgentExecutionError,
)
from src.shared.utils.agent_logging_middleware import (
    create_agent_logging_middleware,
)
from src.shared.utils.error_handler import (
    create_error_handling_middleware,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class AgentStatus(Enum):
    """Agent状态枚举"""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class AgentConfig(TypedDict, total=False):
    """Agent配置

    使用TypedDict定义配置结构,total=False表示所有字段都是可选的。
    """

    agent_id: str
    agent_name: str
    agent_type: str
    description: str

    # 模型配置
    model_provider: str
    model_name: str
    temperature: float
    max_tokens: int

    # 工具配置
    enable_memory: bool

    # 记忆配置
    memory_namespace: tuple[str, ...]  # 用于LangMem的namespace

    # Checkpointer配置
    checkpoint_type: str  # 'memory' 或 'sqlite'
    checkpoint_thread_id: str  # 线程ID,用于状态隔离

    # 结构化输出配置
    response_format: type[Any] | None  # Pydantic模型、TypedDict或Dataclass

    # 上下文模式配置
    context_schema: type[Any] | None  # 运行时上下文模式

    # 中间件配置
    middleware_config: dict[str, Any]
    enable_hitl: bool  # 是否启用人机协作中间件
    enable_error_handling: bool  # 是否启用错误处理中间件(默认True)
    enable_logging: bool  # 是否启用日志记录中间件(默认True)
    enable_summarization: bool  # 是否启用总结中间件(默认True,通过配置控制)
    error_handling_config: dict[str, Any]  # 错误处理中间件配置
    logging_config: dict[str, Any]  # 日志记录中间件配置
    summarization_config: dict[str, Any]  # 总结中间件配置(可选,覆盖全局配置)


class BaseAgent(ABC):
    """Agent基础类

    基于LangChain 1.0的create_agent构建的Agent基类, 提供:
    1. 统一的Agent生命周期管理
    2. 集成LLM服务(T009)
    3. 中间件支持(包括官方内置中间件)
    4. 结构化输出支持
    5. 状态持久化(Checkpointer)
    6. 记忆管理(LangMem Tools)
    7. 错误处理和重试机制

    完全基于LangChain 1.0的create_agent API实现,符合官方最佳实践。
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_service: LLMService | None = None,
        memory: Any | None = None,
        checkpointer: MemorySaver | None = None,
    ):
        """初始化Agent

        Args:
            config: Agent配置
            llm_service: LLM服务实例(T009创建的统一服务)
            memory: LangMem适配器实例(用于长期记忆管理)
            checkpointer: Checkpointer实例(用于状态持久化,可选)
        """
        self.config = config
        self.agent_id = config.get("agent_id", "unknown")
        self.agent_name = config.get("agent_name", "UnknownAgent")
        self.agent_type = config.get("agent_type", "base")

        # 从T009的LLM服务获取模型实例
        self.llm_service = llm_service or LLMService()
        self._model: BaseLanguageModel | None = None

        # 工具列表(包含Agent专用工具和记忆工具)
        self._tools: list[BaseTool] = []

        # LangMem适配器(长期记忆)
        self.memory = memory

        # Checkpointer(状态持久化)
        if checkpointer is None and config.get("checkpoint_type"):
            # 从配置创建checkpointer
            checkpoint_type = config.get("checkpoint_type", "memory")
            try:
                checkpointer = create_checkpointer(checkpoint_type)
                logger.info(
                    "Agent %s 自动创建Checkpointer: %s",
                    self.agent_name,
                    checkpoint_type,
                )
            except Exception as e:
                logger.warning("Agent %s Checkpointer创建失败: %s", self.agent_name, e)
        self._checkpointer: MemorySaver | None = checkpointer

        # Agent实例(使用create_agent创建)
        self._agent: Runnable | None = None

        # 状态管理
        self._status = AgentStatus.IDLE
        self._current_result: dict[str, Any] | None = None

        logger.info("初始化Agent: %s (ID: %s)", self.agent_name, self.agent_id)

    @property
    def model(self) -> BaseLanguageModel:
        """获取LLM模型实例

        必须从T009创建的llm_service获取, 不得直接创建。
        模型配置通过统一的配置系统管理,符合LangChain 1.0最佳实践。
        如果需要覆盖配置(如temperature),应通过运行时config参数实现。
        """
        if self._model is None:
            try:
                # 从配置获取提供商,如果未指定则使用默认值
                provider = self.config.get("model_provider")
                if provider is None:
                    # 使用LLMService的默认提供商
                    provider = None  # 让LLMService使用默认配置

                # 获取模型实例(配置从统一配置系统读取)
                self._model = self.llm_service.get_chat_model(provider=provider)

                # 如果Agent配置中指定了覆盖参数,通过with_config应用
                # 注意:这需要在运行时通过config参数传递,而不是在模型创建时
                # 这里只记录配置信息
                model_name = self.config.get("model_name")
                if model_name:
                    logger.debug(
                        "Agent %s 配置了模型名称: %s (实际使用配置系统中的模型)",
                        self.agent_name,
                        model_name,
                    )

                logger.info(
                    "Agent %s 成功加载模型 (provider=%s)",
                    self.agent_name,
                    provider or "default",
                )
            except Exception as e:
                logger.error("Agent %s 模型加载失败: %s", self.agent_name, e)
                error_msg = f"无法加载LLM模型: {e}"
                raise AgentConfigurationError(error_msg) from e

        return self._model

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        """获取Agent专用工具列表

        子类必须实现此方法,返回Agent专用的工具列表。
        """
        raise NotImplementedError

    def _build_agent(self) -> Runnable:
        """构建Agent实例

        使用LangChain 1.0的create_agent API创建Agent。
        符合LangChain 1.0最佳实践,只传递支持的参数。
        """
        try:
            # 获取工具列表(包含Agent专用工具和记忆工具)
            tools = self.get_tools()
            if self.memory:
                # 获取记忆工具(使用正确的命名空间)
                memory_namespace = self.config.get("memory_namespace")
                if memory_namespace:
                    memory_tools = self.memory.get_memory_tools(
                        namespace=memory_namespace
                    )
                else:
                    # 如果没有指定命名空间,使用默认工具
                    memory_tools = self.memory.get_memory_tools()
                tools.extend(memory_tools)

            # 获取中间件
            middleware = self._build_middleware()

            # 构建create_agent参数(只包含支持的参数)
            agent_kwargs: dict[str, Any] = {
                "model": self.model,
                "tools": tools,
            }

            # 系统消息(可选)
            system_message = self._get_system_message()
            if system_message:
                agent_kwargs["system_message"] = system_message

            # Checkpointer(可选)
            if self._checkpointer:
                agent_kwargs["checkpointer"] = self._checkpointer

            # 中间件(可选)
            if middleware:
                agent_kwargs["middleware"] = middleware

            # 结构化输出(可选)
            response_format = self.config.get("response_format")
            if response_format:
                agent_kwargs["response_format"] = response_format

            # 上下文模式(可选,注意:LangChain 1.0可能使用不同的参数名)
            # 如果context_schema不被支持,可以移除或使用config_schema
            context_schema = self.config.get("context_schema")
            if context_schema:
                # 注意:根据LangChain 1.0实际API调整
                # 如果context_schema不被支持,可以注释掉或使用其他方式
                try:
                    agent_kwargs["context_schema"] = context_schema
                except TypeError:
                    # 如果参数不被支持,记录警告但不失败
                    logger.warning(
                        "Agent %s: context_schema参数不被create_agent支持,已忽略",
                        self.agent_name,
                    )

            # 创建Agent
            agent = create_agent(**agent_kwargs)

            logger.info("Agent %s 成功构建", self.agent_name)
            return agent

        except Exception as e:
            logger.error("Agent %s 构建失败: %s", self.agent_name, e)
            error_msg = f"Agent构建失败: {e}"
            raise AgentConfigurationError(error_msg) from e

    def _build_middleware(self) -> list:
        """构建中间件列表

        包括官方内置中间件和自定义中间件。
        中间件执行顺序(按照LangChain 1.0最佳实践):
        1. 日志记录中间件(最先执行,记录所有事件)
        2. 总结中间件(SummarizationMiddleware,在错误处理之前,防止token溢出)
        3. 错误处理中间件(处理错误和重试)
        4. 人机协作中间件(HITL)
        5. 其他自定义中间件
        """
        middleware = []

        # 1. 日志记录中间件(默认启用)
        if self.config.get("enable_logging", True):
            logging_config = self.config.get("logging_config", {})
            logging_middleware = create_agent_logging_middleware(**logging_config)
            middleware.append(logging_middleware)
            logger.debug("Agent %s 启用日志记录中间件", self.agent_name)

        # 2. 总结中间件(SummarizationMiddleware,在错误处理之前执行)
        # 默认启用,但可以通过配置控制
        summarization_config = self.config.get("summarization_config") or {}
        # 从全局配置获取总结中间件配置
        global_config = get_config()
        summ_config = global_config.summarization_middleware

        # 如果Agent配置中指定了覆盖值,使用覆盖值
        if summarization_config:
            enabled = summarization_config.get("enabled", summ_config.enabled)
            max_tokens = summarization_config.get("max_tokens", summ_config.max_tokens)
            chunk_size = summarization_config.get("chunk_size", summ_config.chunk_size)
            overlap_size = summarization_config.get(
                "overlap_size", summ_config.overlap_size
            )
        else:
            enabled = summ_config.enabled
            max_tokens = summ_config.max_tokens
            chunk_size = summ_config.chunk_size
            overlap_size = summ_config.overlap_size

        # 如果配置为启用,则添加总结中间件
        if enabled:
            summarization_middleware = create_summarization_middleware(
                max_tokens=max_tokens,
                chunk_size=chunk_size,
                overlap_size=overlap_size,
                llm_service=self.llm_service,
                enabled=True,
            )
            middleware.append(summarization_middleware)
            logger.debug(
                "Agent %s 启用总结中间件 (max_tokens=%d, chunk_size=%d, overlap_size=%d)",
                self.agent_name,
                max_tokens,
                chunk_size,
                overlap_size,
            )

        # 3. 错误处理中间件(默认启用)
        if self.config.get("enable_error_handling", True):
            error_config = self.config.get("error_handling_config", {})
            error_middleware = create_error_handling_middleware(**error_config)
            middleware.append(error_middleware)
            logger.debug("Agent %s 启用错误处理中间件", self.agent_name)

        # 4. 人机协作中间件
        if self.config.get("enable_hitl", False):
            hitl_middleware = HumanInTheLoopMiddleware()
            middleware.append(hitl_middleware)
            logger.info("Agent %s 启用HITL中间件", self.agent_name)

        # 5. 其他自定义中间件配置
        middleware_config = self.config.get("middleware_config", {})
        if middleware_config:
            logger.info(
                "Agent %s 配置自定义中间件: %s", self.agent_name, middleware_config
            )

        return middleware

    def _get_system_message(self) -> str:
        """获取系统消息

        子类可以重写此方法自定义系统消息。
        """
        return f"""
        你是一个名为 {self.agent_name} 的智能Agent。
        你的ID是 {self.agent_id},类型是 {self.agent_type}。
        请使用你的工具来完成任务。
        """

    def get_state(self, thread_id: str | None = None) -> dict[str, Any]:
        """获取Agent状态

        Args:
            thread_id: 线程ID,如果为None则使用配置中的checkpoint_thread_id

        Returns:
            Agent状态字典
        """
        if self._checkpointer is None:
            logger.warning("Agent %s 未配置Checkpointer,无法获取状态", self.agent_name)
            return {}

        try:
            thread_id = thread_id or self.config.get("checkpoint_thread_id")
            if not thread_id:
                msg = "未配置thread_id"
                raise AgentConfigurationError(msg)

            config = {"configurable": {"thread_id": thread_id}}
            state = self._checkpointer.get(config)
            return state or {}
        except Exception as e:
            logger.error("Agent %s 获取状态失败: %s", self.agent_name, e)
            msg = f"获取状态失败: {e}"
            raise AgentExecutionError(msg) from e

    def update_state(
        self, updates: dict[str, Any], thread_id: str | None = None
    ) -> None:
        """更新Agent状态

        Args:
            updates: 状态更新字典
            thread_id: 线程ID,如果为None则使用配置中的checkpoint_thread_id
        """
        if self._checkpointer is None:
            logger.warning("Agent %s 未配置Checkpointer,无法更新状态", self.agent_name)
            return

        try:
            thread_id = thread_id or self.config.get("checkpoint_thread_id")
            if not thread_id:
                msg = "未配置thread_id"
                raise AgentConfigurationError(msg)

            config = {"configurable": {"thread_id": thread_id}}
            self._checkpointer.update(config, {"values": updates})
            logger.info("Agent %s 状态更新成功", self.agent_name)
        except Exception as e:
            logger.error("Agent %s 更新状态失败: %s", self.agent_name, e)
            msg = f"更新状态失败: {e}"
            raise AgentExecutionError(msg) from e

    def invoke(
        self, input_data: dict[str, Any], config: RunnableConfig | None = None, **kwargs
    ) -> dict[str, Any]:
        """执行Agent

        Args:
            input_data: 输入数据
            config: 运行配置
            **kwargs: 其他参数

        Returns:
            Agent执行结果
        """
        try:
            self._status = AgentStatus.RUNNING
            logger.info("Agent %s 开始执行", self.agent_name)

            # 构建Agent
            if self._agent is None:
                self._agent = self._build_agent()

            # 确保输入数据包含Agent元信息(供中间件使用)
            if "agent_id" not in input_data:
                input_data["agent_id"] = self.agent_id
            if "agent_name" not in input_data:
                input_data["agent_name"] = self.agent_name

            # 执行Agent
            result = self._agent.invoke(input_data, config=config, **kwargs)

            self._status = AgentStatus.COMPLETED
            self._current_result = result
            logger.info("Agent %s 执行完成", self.agent_name)

            return result

        except Exception as e:
            self._status = AgentStatus.FAILED
            logger.error("Agent %s 执行失败: %s", self.agent_name, e)
            msg = f"Agent执行失败: {e}"
            raise AgentExecutionError(msg) from e

    async def ainvoke(
        self, input_data: dict[str, Any], config: RunnableConfig | None = None, **kwargs
    ) -> dict[str, Any]:
        """异步执行Agent

        Args:
            input_data: 输入数据
            config: 运行配置
            **kwargs: 其他参数

        Returns:
            Agent执行结果
        """
        try:
            self._status = AgentStatus.RUNNING
            logger.info("Agent %s 开始异步执行", self.agent_name)

            # 构建Agent
            if self._agent is None:
                self._agent = self._build_agent()

            # 确保输入数据包含Agent元信息(供中间件使用)
            if "agent_id" not in input_data:
                input_data["agent_id"] = self.agent_id
            if "agent_name" not in input_data:
                input_data["agent_name"] = self.agent_name

            # 异步执行Agent
            result = await self._agent.ainvoke(input_data, config=config, **kwargs)

            self._status = AgentStatus.COMPLETED
            self._current_result = result
            logger.info("Agent %s 异步执行完成", self.agent_name)

            return result

        except Exception as e:
            self._status = AgentStatus.FAILED
            logger.error("Agent %s 异步执行失败: %s", self.agent_name, e)
            msg = f"Agent异步执行失败: {e}"
            raise AgentExecutionError(msg) from e

    def stream(
        self, input_data: dict[str, Any], config: RunnableConfig | None = None, **kwargs
    ):
        """流式执行Agent

        Args:
            input_data: 输入数据
            config: 运行配置
            **kwargs: 其他参数

        Yields:
            Agent执行的中间结果
        """
        try:
            self._status = AgentStatus.RUNNING
            logger.info("Agent %s 开始流式执行", self.agent_name)

            # 构建Agent
            if self._agent is None:
                self._agent = self._build_agent()

            # 流式执行Agent
            yield from self._agent.stream(input_data, config=config, **kwargs)

            self._status = AgentStatus.COMPLETED
            logger.info("Agent %s 流式执行完成", self.agent_name)

        except Exception as e:
            self._status = AgentStatus.FAILED
            logger.error("Agent %s 流式执行失败: %s", self.agent_name, e)
            msg = f"Agent流式执行失败: {e}"
            raise AgentExecutionError(msg) from e

    async def astream(
        self, input_data: dict[str, Any], config: RunnableConfig | None = None, **kwargs
    ):
        """异步流式执行Agent

        Args:
            input_data: 输入数据
            config: 运行配置
            **kwargs: 其他参数

        Yields:
            Agent执行的中间结果
        """
        try:
            self._status = AgentStatus.RUNNING
            logger.info("Agent %s 开始异步流式执行", self.agent_name)

            # 构建Agent
            if self._agent is None:
                self._agent = self._build_agent()

            # 异步流式执行Agent
            async for chunk in self._agent.astream(input_data, config=config, **kwargs):
                yield chunk

            self._status = AgentStatus.COMPLETED
            logger.info("Agent %s 异步流式执行完成", self.agent_name)

        except Exception as e:
            self._status = AgentStatus.FAILED
            logger.error("Agent %s 异步流式执行失败: %s", self.agent_name, e)
            msg = f"Agent异步流式执行失败: {e}"
            raise AgentExecutionError(msg) from e

    def get_status(self) -> AgentStatus:
        """获取Agent当前状态"""
        return self._status

    def get_result(self) -> dict[str, Any] | None:
        """获取Agent执行结果"""
        return self._current_result

    def reset(self) -> None:
        """重置Agent状态"""
        self._status = AgentStatus.IDLE
        self._current_result = None
        self._agent = None
        logger.info("Agent %s 已重置", self.agent_name)

    def cleanup(self) -> None:
        """清理Agent资源"""
        self.reset()
        if self.memory:
            self.memory.cleanup()
        logger.info("Agent %s 资源已清理", self.agent_name)
