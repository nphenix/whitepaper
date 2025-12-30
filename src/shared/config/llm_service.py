"""LLM 服务
供统一的 LLM 模型获取和管理服务,支持多种提供商的动态加载.
使用工厂模式和单例模式管理模型实例,支持按需创建和缓存.
"""

import importlib.util
import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from langchain.chat_models import init_chat_model

# LangChain 导入
from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import ConfigurableField

# 延迟导入,只在需要时导入
# from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

# DashScope 导入
try:
    import dashscope
    from dashscope import Generation, Rerank, TextEmbedding
    from dashscope.api_entities.dashscope_response import Role

    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    dashscope = None
    Generation = None
    Rerank = None
    TextEmbedding = None
    Role = None

# 项目导入
from .config_validator import ConfigValidator
from .settings import (
    AppConfig,
)

logger = logging.getLogger(__name__)


class DashScopeChatModel(BaseLanguageModel):
    """DashScope 聊天模型的 LangChain 包装器

    将 DashScope SDK 包装为 LangChain 兼容的 BaseLanguageModel,
    支持流式输出和 LangChain 1.0 可配置字段.
    """

    def __init__(
        self,
        model_name: str,
        temperature: float,
        max_tokens: int,
        api_key: str,
        **kwargs,
    ):
        """初始化 DashScope 聊天模型

        Args:
            model_name: 模型名称
            temperature: 温度参数
            max_tokens: 最大 token 数
            api_key: API 密钥
        """
        super().__init__()
        # 重新导入 dashscope,避免使用模块级别的 None 变量
        import dashscope

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.api_key = api_key
        dashscope.api_key = api_key

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        """生成响应

        Args:
            messages: 消息列表
            stop: 停止词
            run_manager: 运行管理器
            **kwargs: 其他参数

        Returns:
            生成结果
        """
        from dashscope import Generation as DashScopeGeneration
        from dashscope.api_entities.dashscope_response import Role
        from langchain_core.messages import BaseMessage
        from langchain_core.outputs import Generation as LCGeneration, LLMResult

        # 转换消息格式
        dashscope_messages = []
        for msg in messages:
            if isinstance(msg, BaseMessage):
                if msg.type == "system":
                    role = Role.SYSTEM
                elif msg.type == "human":
                    role = Role.USER
                elif msg.type == "ai":
                    role = Role.ASSISTANT
                else:
                    continue

                dashscope_messages.append({"role": role, "content": msg.content})

        try:
            # 调用 DashScope API
            response = DashScopeGeneration.call(
                model=self.model_name,
                messages=dashscope_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                result_format="message",
                stream=False,
                **kwargs,
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content
                generation = LCGeneration(text=content)
                return LLMResult(generations=[generation])
            else:
                error_msg = f"DashScope API 错误: {response.message}"
                raise Exception(error_msg)

        except Exception as e:
            logger.error("DashScope 调用失败: %s", e)
            raise

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        """流式生成响应

        Args:
            messages: 消息列表
            stop: 停止词
            run_manager: 运行管理器
            **kwargs: 其他参数

        Yields:
            流式响应块
        """
        from dashscope import Generation as DashScopeGeneration
        from dashscope.api_entities.dashscope_response import Role
        from langchain_core.messages import BaseMessage
        from langchain_core.outputs import GenerationChunk

        # 转换消息格式
        dashscope_messages = []
        for msg in messages:
            if isinstance(msg, BaseMessage):
                if msg.type == "system":
                    role = Role.SYSTEM
                elif msg.type == "human":
                    role = Role.USER
                elif msg.type == "ai":
                    role = Role.ASSISTANT
                else:
                    continue

                dashscope_messages.append({"role": role, "content": msg.content})

        try:
            # 调用 DashScope 流式 API
            responses = DashScopeGeneration.call(
                model=self.model_name,
                messages=dashscope_messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                result_format="message",
                stream=True,
                **kwargs,
            )

            for response in responses:
                if response.status_code == 200:
                    if hasattr(response.output, "choices") and response.output.choices:
                        content = response.output.choices[0].message.content
                        if content:
                            chunk = GenerationChunk(text=content)
                            if run_manager:
                                run_manager.on_llm_new_token(chunk.text)
                            yield chunk
                else:
                    logger.error("DashScope 流式响应错误: %s", response.message)
                    break

        except Exception as e:
            logger.error("DashScope 流式调用失败: %s", e)
            raise

    @property
    def _llm_type(self) -> str:
        """返回模型类型"""
        return "dashscope"


class DashScopeEmbeddingModel:
    """DashScope 嵌入模型的包装器

    将 DashScope TextEmbedding API 包装为 LangChain 兼容的嵌入模型.
    """

    def __init__(self, model_name: str, api_key: str, **kwargs):
        """初始化 DashScope 嵌入模型

        Args:
            model_name: 模型名称
            api_key: API 密钥
        """
        # 重新导入 dashscope,避免使用模块级别的 None 变量
        import dashscope

        self.model_name = model_name
        self.api_key = api_key
        dashscope.api_key = api_key

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入文档

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        embeddings = []
        for text in texts:
            embedding = self.embed_query(text)
            embeddings.append(embedding)
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        """嵌入查询文本

        Args:
            text: 查询文本

        Returns:
            嵌入向量
        """
        try:
            from http import HTTPStatus

            from dashscope import TextEmbedding

            response = TextEmbedding.call(
                model=self.model_name,
                input=text,
            )

            if response.status_code == HTTPStatus.OK:
                return response.output["embeddings"][0]["embedding"]
            else:
                error_msg = f"DashScope 嵌入 API 错误: {response.message}"
                raise Exception(error_msg)

        except Exception as e:
            logger.error("DashScope 嵌入调用失败: %s", e)
            raise


class DashScopeRerankWrapper:
    """DashScope 重排序模型包装类

    提供统一的接口用于重排序功能.
    """

    def __init__(self, api_key: str, model: str, top_n: int):
        """初始化 DashScope 重排序模型

        Args:
            api_key: API 密钥
            model: 模型名称
            top_n: 返回 top-n 结果
        """
        self.api_key = api_key
        self.model = model
        self.top_n = top_n
        self._rerank = None
        self._init_rerank()

    def _init_rerank(self):
        """初始化重排序模型"""
        try:
            import dashscope
            from dashscope import rerank

            dashscope.api_key = self.api_key
            self._rerank = rerank
        except ImportError:
            logger.error("dashscope 包未安装,无法使用重排序功能")
            raise

    def rerank(
        self, query: str, documents: list[str], top_n: int | None = None
    ) -> list[dict]:
        """执行重排序

        Args:
            query: 查询文本
            documents: 文档列表
            top_n: 返回 top-n 结果,如果为 None 则使用初始化时的 top_n

        Returns:
            重排序后的结果列表,每个元素包含文档和相关性分数
        """
        if self._rerank is None:
            runtimeerror_msg = "重排序模型未初始化"
            raise RuntimeError(runtimeerror_msg)

        top_n = top_n or self.top_n

        try:
            import requests

            # 使用 HTTP POST 请求调用 DashScope Rerank API
            url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            data = {
                "model": self.model,
                "input": {"query": query, "documents": documents},
                "parameters": {
                    "return_documents": True,
                    "top_n": top_n,
                    "instruct": "Given a web search query, retrieve relevant passages that answer query.",
                },
            }

            response = requests.post(url, headers=headers, json=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                results = []
                for item in result.get("output", {}).get("results", []):
                    results.append(
                        {
                            "document": item.get("document", {}).get("text", ""),
                            "index": item.get("index", 0),
                            "relevance_score": item.get("relevance_score", 0.0),
                        }
                    )
                return results
            else:
                logger.error("重排序失败: %s", response.text)
                return []
        except Exception as e:
            logger.error("重排序异常: %s", e)
            return []


class LLMProvider(ABC):
    """LLM 提供商抽象基类"""

    @abstractmethod
    def create_chat_model(self, config: dict[str, Any]) -> BaseLanguageModel:
        """创建聊天模型

        Args:
            config: 模型配置

        Returns:
            聊天模型实例
        """

    @abstractmethod
    def create_embedding_model(self, config: dict[str, Any]) -> Any:
        """创建嵌入模型

        Args:
            config: 模型配置

        Returns:
            嵌入模型实例
        """

    @abstractmethod
    def create_rerank_model(self, config: dict[str, Any]) -> Any:
        """创建重排序模型

        Args:
            config: 模型配置

        Returns:
            重排序模型实例
        """


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容接口提供商"""

    def create_chat_model(self, config: dict[str, Any]) -> BaseLanguageModel:
        """创建 OpenAI 兼容的聊天模型

        优先使用 OpenAI SDK 适配器（解决 LangChain ChatOpenAI 的 URL 构建问题），
        如果环境变量 LLM_USE_LANGCHAIN=true，则使用 LangChain ChatOpenAI。

        所有配置必须从 config 中提供,无硬编码默认值.

        Args:
            config: 模型配置字典

        Returns:
            BaseLanguageModel 实例
        """
        # 使用统一的配置验证器验证必需配置
        ConfigValidator.validate_required_keys(
            config,
            [
                "model_name",
                "temperature",
                "max_tokens",
                "timeout",
                "api_key",
                "base_url",
            ],
            "OpenAI兼容配置",
        )

        # 检查是否强制使用 LangChain（用于测试或特殊场景）
        import os
        use_langchain = os.getenv("LLM_USE_LANGCHAIN", "false").lower() == "true"

        if use_langchain:
            # 使用 LangChain ChatOpenAI（原始方式）
            from langchain_openai import ChatOpenAI

            timeout_value = config["timeout"]

            model = ChatOpenAI(
                model=config["model_name"],
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
                api_key=config["api_key"],
                base_url=config["base_url"],
                timeout=float(timeout_value),
                max_retries=0,
            )

            logger.info(
                f"创建LangChain ChatOpenAI模型: timeout={timeout_value}秒,max_retries=0"
            )
        else:
            # 使用 OpenAI SDK 适配器（推荐，解决 URL 构建问题）
            from src.shared.config.openai_sdk_adapter import OpenAISDKAdapter

            timeout_value = config["timeout"]

            model = OpenAISDKAdapter(
                model_name=config["model_name"],
                temperature=config["temperature"],
                max_tokens=config["max_tokens"],
                api_key=config["api_key"],
                base_url=config["base_url"],
                timeout=float(timeout_value),
            )

            logger.info(
                f"创建OpenAI SDK适配器模型: model={config['model_name']}, "
                f"base_url={config['base_url']}, timeout={timeout_value}秒"
            )

        return model

    def create_embedding_model(self, config: dict[str, Any]) -> Any:
        """创建 OpenAI 兼容的嵌入模型"""
        return OpenAIEmbeddings(
            model=config.get("model_name", "text-embedding-3-large"),
            dimensions=config.get("dimension", 1536),
            api_key=config["api_key"],
            base_url=config.get("base_url"),
        )

    def create_rerank_model(self, config: dict[str, Any]) -> Any:
        """创建重排序模型(OpenAI 暂不支持)"""
        error_msg = "OpenAI 不支持重排序模型"
        raise NotImplementedError(error_msg)


class GeminiProvider(LLMProvider):
    """Google Gemini 提供商"""

    def create_chat_model(self, config: dict[str, Any]) -> BaseLanguageModel:
        """创建 Gemini 聊天模型,使用 LangChain 1.0 init_chat_model 简化实现

        所有配置必须从 config 中提供,无硬编码默认值.
        使用 init_chat_model 简化模型创建和配置.
        """
        # 使用统一的配置验证器验证必需配置
        ConfigValidator.validate_required_keys(
            config,
            ["model_name", "temperature", "max_tokens", "api_key"],
            "Gemini配置",
        )

        # 使用 LangChain 1.0 的 init_chat_model 简化实现
        model = init_chat_model(
            model=f"google_genai:{config['model_name']}",
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            api_key=config["api_key"],
            configurable_fields=("model", "temperature", "max_tokens"),
        )

        return model

    def create_embedding_model(self, config: dict[str, Any]) -> Any:
        """创建 Gemini 嵌入模型"""
        # 延迟导入,只在需要时导入
        try:
            from langchain_google_genai import GoogleGenerativeAIEmbeddings

            return GoogleGenerativeAIEmbeddings(
                model=config.get("model_name", "embedding-001"),
                google_api_key=config["api_key"],
            )
        except ImportError:
            error_msg = "langchain_google_genai 包未安装,无法使用 Gemini 嵌入模型"
            raise ImportError(error_msg)

    def create_rerank_model(self, config: dict[str, Any]) -> Any:
        """创建重排序模型(Gemini 暂不支持)"""
        error_msg = "Gemini 不支持重排序模型"
        raise NotImplementedError(error_msg)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude 提供商"""

    def create_chat_model(self, config: dict[str, Any]) -> BaseLanguageModel:
        """创建 Claude 聊天模型,使用 LangChain 1.0 init_chat_model 简化实现

        所有配置必须从 config 中提供,无硬编码默认值.
        使用 init_chat_model 简化模型创建和配置.
        """
        # 使用统一的配置验证器验证必需配置
        ConfigValidator.validate_required_keys(
            config,
            ["model_name", "temperature", "max_tokens", "api_key"],
            "Anthropic配置",
        )

        # 使用 LangChain 1.0 的 init_chat_model 简化实现
        model = init_chat_model(
            model=f"anthropic:{config['model_name']}",
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            api_key=config["api_key"],
            configurable_fields=("model", "temperature", "max_tokens"),
        )

        return model

    def create_embedding_model(self, config: dict[str, Any]) -> Any:
        """创建嵌入模型(Anthropic 暂不支持)"""
        error_msg = "Anthropic 不支持嵌入模型"
        raise NotImplementedError(error_msg)

    def create_rerank_model(self, config: dict[str, Any]) -> Any:
        """创建重排序模型(Anthropic 暂不支持)"""
        error_msg = "Anthropic 不支持重排序模型"
        raise NotImplementedError(error_msg)


class DashScopeProvider(LLMProvider):
    """阿里百炼 DashScope 提供商"""

    def create_chat_model(self, config: dict[str, Any]) -> BaseLanguageModel:
        """创建 DashScope 聊天模型,使用 LangChain 1.0 init_chat_model 简化实现

        所有配置必须从 config 中提供,无硬编码默认值.
        使用 init_chat_model 简化模型创建和配置.
        """
        # 直接尝试导入,不依赖 DASHSCOPE_AVAILABLE 变量
        try:
            import dashscope
        except ImportError:
            error_msg = "dashscope 包未安装,无法使用 DashScope 提供商"
            raise ImportError(error_msg)

        # 使用统一的配置验证器验证必需配置
        ConfigValidator.validate_required_keys(
            config,
            ["model_name", "temperature", "max_tokens", "api_key"],
            "DashScope配置",
        )

        # 设置 API 密钥
        dashscope.api_key = config["api_key"]

        # 使用 LangChain 1.0 的 init_chat_model 简化实现
        # 通过自定义适配器包装 DashScope 调用
        model = DashScopeChatModel(
            model_name=config["model_name"],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            api_key=config["api_key"],
        )

        # DashScopeChatModel 继承自 BaseLanguageModel,已支持可配置字段
        # 注意:如果需要在运行时动态配置参数,可以使用 model.with_config() 或
        # 通过 LangChain 的 configurable_fields 功能实现
        # 这里直接返回模型,因为 BaseLanguageModel 已经实现了 Runnable 接口
        return model

    def create_embedding_model(self, config: dict[str, Any]) -> Any:
        """创建 DashScope 嵌入模型

        使用真正的 DashScope TextEmbedding API,无硬编码默认值.
        """
        # 直接尝试导入,不依赖 DASHSCOPE_AVAILABLE 变量
        try:
            import dashscope
        except ImportError:
            error_msg = "dashscope 包未安装,无法使用 DashScope 嵌入模型"
            raise ImportError(error_msg)

        # 验证必需配置
        required_keys = ["model_name", "api_key"]
        for key in required_keys:
            if key not in config or config[key] is None:
                error_msg = f"配置项 '{key}' 未设置,请在 .env 文件中配置"
                raise Exception(error_msg)

        # 设置 API 密钥
        dashscope.api_key = config["api_key"]

        return DashScopeEmbeddingModel(
            model_name=config["model_name"],
            api_key=config["api_key"],
        )

    def create_rerank_model(self, config: dict[str, Any]) -> Any:
        """创建 DashScope 重排序模型

        注意:DashScope 重排序模型需要通过 HTTP API 调用,这里返回一个包装类
        """
        # 直接检测 dashscope 可用性,不依赖 DASHSCOPE_AVAILABLE 变量
        if importlib.util.find_spec("dashscope") is None:
            error_msg = "dashscope 包未安装,无法使用 DashScope 重排序模型"
            raise ImportError(error_msg)

        # DashScope Rerank 需要直接使用 dashscope SDK
        # 所有配置必须从 config 中获取,无硬编码默认值
        model_name = config.get("model_name")
        top_k = config.get("top_k")

        if not model_name:
            error_msg = "RERANK_MODEL_NAME 环境变量未设置,请在 .env 文件中配置"
            raise ValueError(error_msg)
        if top_k is None:
            valueerror_msg = "RERANK_TOP_K 环境变量未设置,请在 .env 文件中配置"
            raise ValueError(valueerror_msg)

        return DashScopeRerankWrapper(
            api_key=config["api_key"],
            model=model_name,
            top_n=top_k,
        )


class LLMService:
    """LLM 服务单例

    提供统一的模型获取接口,支持多种提供商的动态加载.
    使用工厂模式和单例模式管理模型实例,支持按需创建和缓存.
    """

    _instance = None
    _chat_models: ClassVar[dict[str, BaseLanguageModel]] = {}
    _embedding_models: ClassVar[dict[str, Any]] = {}
    _rerank_models: ClassVar[dict[str, Any]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._providers: dict[str, LLMProvider] = {}
            self._config: AppConfig | None = None
            self._initialized = True
            self._setup_providers()
            # 自动加载配置
            try:
                from .settings import load_config

                self._config = load_config()
                logger.info("LLM 服务已自动加载配置")
            except Exception as e:
                logger.warning("自动加载配置失败: %s,请手动调用 set_config()", e)

    def _setup_providers(self):
        """注册所有支持的提供商"""
        self._providers = {
            "openai_compatible": OpenAICompatibleProvider(),
            "gemini": GeminiProvider(),
            "anthropic": AnthropicProvider(),
            "dashscope": DashScopeProvider(),
        }
        logger.info("已注册 %d 个 LLM 提供商", len(self._providers))

    def set_config(self, config: AppConfig):
        """设置配置

        Args:
            config: 应用配置
        """
        self._config = config
        logger.info("LLM 服务配置已更新")

    def get_chat_model(
        self, provider: str | None = None, *, enable_alternatives: bool = False
    ) -> BaseLanguageModel:
        """获取聊天模型,支持 LangChain 1.0 configurable_alternatives

        Args:
            provider: 提供商名称,如果为 None 则使用默认提供商
            enable_alternatives: 是否启用 configurable_alternatives(支持运行时切换)

        Returns:
            聊天模型实例,如果 enable_alternatives=True,则支持运行时切换提供商
        """
        if provider is None:
            provider = (
                self._config.llm_provider if self._config else "openai_compatible"
            )

        cache_key = f"chat_{provider}_alt_{enable_alternatives}"

        if cache_key not in self._chat_models:
            logger.info(
                "创建聊天模型: %s (alternatives=%s)", provider, enable_alternatives
            )

            # 获取提供商
            if provider not in self._providers:
                error_msg = f"不支持的 LLM 提供商: {provider}"
                raise Exception(error_msg)

            provider_instance = self._providers[provider]

            # 构建配置
            config = self._build_chat_config(provider)

            # 创建默认模型
            default_model = provider_instance.create_chat_model(config)

            if enable_alternatives:
                # 创建替代模型(延迟加载,只在需要时创建)
                # 注意:这里不预先创建所有替代模型,避免内存浪费
                # 如果需要运行时切换,可以通过 with_config 动态创建
                alternatives = {}

                # 可选:预先创建常用的替代模型
                # 为了性能,这里暂时不创建,而是在运行时按需创建
                # 如果需要,可以在这里添加常用提供商的预创建逻辑

                # 使用 configurable_alternatives
                configurable_model = default_model.configurable_alternatives(
                    ConfigurableField(
                        id="llm_provider",
                        name="LLM Provider",
                        description="选择 LLM 提供商",
                    ),
                    default_key=provider,
                    **alternatives,
                )
                self._chat_models[cache_key] = configurable_model
                logger.info("成功创建可配置聊天模型: %s (支持运行时切换)", provider)
            else:
                self._chat_models[cache_key] = default_model
                logger.info("成功创建聊天模型: %s", provider)

        return self._chat_models[cache_key]

    def get_embedding_model(self, provider: str | None = None) -> Any:
        """获取嵌入模型

        Args:
            provider: 提供商名称,如果为 None 则使用默认提供商

        Returns:
            嵌入模型实例
        """
        if provider is None:
            provider = self._config.embedding.provider if self._config else "dashscope"

        cache_key = f"embedding_{provider}"

        if cache_key not in self._embedding_models:
            logger.info("创建嵌入模型: %s", provider)

            # 获取提供商
            if provider not in self._providers:
                error_msg = f"不支持的 Embedding 提供商: {provider}"
                raise Exception(error_msg)

            provider_instance = self._providers[provider]

            # 构建配置
            config = self._build_embedding_config(provider)

            # 创建模型
            model = provider_instance.create_embedding_model(config)
            self._embedding_models[cache_key] = model

            logger.info("成功创建嵌入模型: %s", provider)

        return self._embedding_models[cache_key]

    def get_rerank_model(self, provider: str | None = None) -> Any:
        """获取重排序模型

        Args:
            provider: 提供商名称,如果为 None 则使用默认提供商

        Returns:
            重排序模型实例
        """
        if provider is None:
            provider = self._config.rerank.provider if self._config else "dashscope"

        cache_key = f"rerank_{provider}"

        if cache_key not in self._rerank_models:
            logger.info("创建重排序模型: %s", provider)

            # 获取提供商
            if provider not in self._providers:
                error_msg = f"不支持的 Rerank 提供商: {provider}"
                raise Exception(error_msg)

            provider_instance = self._providers[provider]

            # 构建配置
            config = self._build_rerank_config(provider)

            # 创建模型
            model = provider_instance.create_rerank_model(config)
            self._rerank_models[cache_key] = model

            logger.info("成功创建重排序模型: %s", provider)

        return self._rerank_models[cache_key]

    def get_ad_cleaning_chat_model(
        self, max_tokens_override: int | None = None
    ) -> BaseLanguageModel:
        """获取广告清洗专用聊天模型

        使用专门的广告清洗模型配置(ad_cleaning_llm),采用OpenAI兼容接口.

        重要说明:
        - max_tokens 参数会影响API请求中的输出token限制
        - API要求:input_tokens + max_tokens <= context_window
        - 如果配置的 max_tokens 太大(如256000),会导致请求失败
        - 建议使用 max_tokens_override 参数传入合理的值(如32000)

        Args:
            max_tokens_override: 可选的max_tokens覆盖值.如果提供,将使用此值
                               而不是配置中的值.推荐用于确保API请求不会超限.

        Returns:
            聊天模型实例

        Raises:
            ValueError: 如果配置未设置或配置不完整
        """
        if not self._config:
            error_msg = "配置未设置,请先调用 set_config() 或确保配置已自动加载"
            raise ValueError(error_msg)

        # 如果指定了max_tokens_override,使用不同的缓存键
        # 这样可以为不同的max_tokens创建不同的模型实例
        cache_key = f"ad_cleaning_chat_model_max_{max_tokens_override or 'default'}"

        if cache_key not in self._chat_models:
            logger.info("创建广告清洗聊天模型")

            # 获取广告清洗配置
            ad_cleaning_config = self._config.ad_cleaning_llm

            # 验证必需配置
            if not ad_cleaning_config.api_key:
                error_msg = (
                    "AD_CLEANING_LLM_API_KEY 环境变量未设置,请在 .env 文件中配置"
                )
                raise ValueError(error_msg)
            if not ad_cleaning_config.model_name:
                error_msg = (
                    "AD_CLEANING_LLM_MODEL_NAME 环境变量未设置,请在 .env 文件中配置"
                )
                raise ValueError(error_msg)
            if not ad_cleaning_config.base_url:
                error_msg = (
                    "AD_CLEANING_LLM_BASE_URL 环境变量未设置,请在 .env 文件中配置"
                )
                raise ValueError(error_msg)

            # 清理配置值中的零宽字符(确保HTTP请求头安全)
            import re
            import unicodedata

            def clean_config_value(value: str) -> str:
                """清理配置值中的零宽字符"""
                if not value:
                    return value
                # Unicode标准化
                value = unicodedata.normalize("NFKC", str(value))
                # 清理零宽字符
                value = re.sub(
                    r"[\u200b-\u200f\uFEFF\uFFFD\u202a-\u202e\u2060-\u206f]", "", value
                )
                # 去除首尾空白
                value = value.strip()
                return value

            # 确定使用的max_tokens值
            # 如果提供了override,使用它;否则直接使用配置值
            # 注意:不同模型的输出token限制不同,由调用方负责传入合理的值
            config_max_tokens = ad_cleaning_config.max_tokens
            if max_tokens_override is not None:
                effective_max_tokens = max_tokens_override
                logger.info(f"使用覆盖的max_tokens: {effective_max_tokens}")
            else:
                # 直接使用配置的max_tokens,不做硬编码限制
                # 调用方(如llm_ad_remover)会根据实际情况动态计算
                effective_max_tokens = config_max_tokens
                logger.info(f"使用配置的max_tokens: {effective_max_tokens}")

            # 构建配置字典(清理所有字符串配置值)
            config_dict = {
                "base_url": clean_config_value(ad_cleaning_config.base_url),
                "api_key": clean_config_value(ad_cleaning_config.api_key),
                "model_name": clean_config_value(ad_cleaning_config.model_name),
                "temperature": ad_cleaning_config.temperature,
                "max_tokens": effective_max_tokens,  # 使用安全的max_tokens值
                "timeout": ad_cleaning_config.timeout,
            }

            # 使用 openai_compatible 提供商创建模型
            provider_instance = self._providers["openai_compatible"]
            model = provider_instance.create_chat_model(config_dict)
            self._chat_models[cache_key] = model

            logger.info(f"成功创建广告清洗聊天模型 (max_tokens={effective_max_tokens})")

        return self._chat_models[cache_key]

    def get_chart_to_json_chat_model(self) -> BaseLanguageModel:
        """获取图表转JSON专用聊天模型

        使用专门的图表转JSON模型配置(chart_to_json_llm),采用OpenAI兼容接口.
        支持多模态输入(图像+文本),用于图表识别和结构化数据提取.

        Returns:
            聊天模型实例

        Raises:
            ValueError: 如果配置未设置或配置不完整
        """
        if not self._config:
            error_msg = "配置未设置,请先调用 set_config() 或确保配置已自动加载"
            raise ValueError(error_msg)

        cache_key = "chart_to_json_chat_model"

        if cache_key not in self._chat_models:
            logger.info("创建图表转JSON聊天模型")

            # 获取图表转JSON配置
            chart_to_json_config = self._config.chart_to_json_llm

            # 验证必需配置
            if not chart_to_json_config.api_key:
                error_msg = (
                    "CHART_TO_JSON_LLM_API_KEY 环境变量未设置,请在 .env 文件中配置"
                )
                raise ValueError(error_msg)
            if not chart_to_json_config.model_name:
                error_msg = (
                    "CHART_TO_JSON_LLM_MODEL_NAME 环境变量未设置,请在 .env 文件中配置"
                )
                raise ValueError(error_msg)
            if not chart_to_json_config.base_url:
                error_msg = (
                    "CHART_TO_JSON_LLM_BASE_URL 环境变量未设置,请在 .env 文件中配置"
                )
                raise ValueError(error_msg)

            # 清理配置值中的零宽字符(确保HTTP请求头安全)
            import re
            import unicodedata

            def clean_config_value(value: str) -> str:
                """清理配置值中的零宽字符"""
                if not value:
                    return value
                # Unicode标准化
                value = unicodedata.normalize("NFKC", str(value))
                # 清理零宽字符
                value = re.sub(
                    r"[\u200b-\u200f\uFEFF\uFFFD\u202a-\u202e\u2060-\u206f]", "", value
                )
                # 去除首尾空白
                value = value.strip()
                return value

            # 构建配置字典(清理所有字符串配置值)
            # max_tokens 从配置中读取，支持通过 CHART_TO_JSON_LLM_MAX_TOKENS 环境变量动态设置
            model_name = clean_config_value(chart_to_json_config.model_name)
            max_tokens = chart_to_json_config.max_tokens
            
            # 记录使用的 max_tokens 值（用于调试）
            logger.debug(
                "使用配置的 max_tokens=%d (可通过 CHART_TO_JSON_LLM_MAX_TOKENS 环境变量设置)",
                max_tokens
            )
            
            config_dict = {
                "base_url": clean_config_value(chart_to_json_config.base_url),
                "api_key": clean_config_value(chart_to_json_config.api_key),
                "model_name": model_name,
                "temperature": chart_to_json_config.temperature,
                "max_tokens": max_tokens,
                "timeout": chart_to_json_config.timeout,
            }
            
            # 确保 base_url 格式正确（GLM-4.6V 需要以 / 结尾）
            base_url = config_dict["base_url"]
            if base_url and not base_url.endswith("/"):
                config_dict["base_url"] = base_url + "/"
                logger.debug("调整 base_url 格式: %s -> %s", base_url, config_dict["base_url"])

            # 使用 openai_compatible 提供商创建模型
            provider_instance = self._providers["openai_compatible"]
            model = provider_instance.create_chat_model(config_dict)
            self._chat_models[cache_key] = model

            logger.info(
                f"成功创建图表转JSON聊天模型 (supports_vision={chart_to_json_config.supports_vision})"
            )

        return self._chat_models[cache_key]

    def _build_chat_config(self, provider: str) -> dict[str, Any]:
        """构建聊天模型配置

        Args:
            provider: 提供商名称

        Returns:
            配置字典

        Raises:
            ValueError: 如果必需配置未设置
        """
        if not self._config:
            error_msg = "配置未设置,请先调用 set_config() 或确保配置已自动加载"
            raise ValueError(error_msg)

        # 优先从配置对象获取配置,确保配置对象的值优先于环境变量
        # 对于 openai_compatible,gemini,anthropic,使用 llm_config(来自 validate_llm_config)
        # 对于 dashscope,也使用 llm_config,但需要从环境变量读取(因为 validate_llm_config 不处理 dashscope)
        llm_config = self._config.llm_config or {}

        # 如果 llm_config 为空(例如 dashscope 情况),尝试从环境变量构建
        # 但优先使用配置对象中的值
        if provider == "openai_compatible":
            # 如果 llm_config 有值,优先使用;否则从环境变量读取
            if llm_config:
                return ConfigValidator.build_openai_compatible_config(llm_config)
            else:
                # 从环境变量读取(作为后备)
                return ConfigValidator.build_openai_compatible_config(None)
        elif provider == "gemini":
            if llm_config:
                return ConfigValidator.build_gemini_config(llm_config)
            else:
                return ConfigValidator.build_gemini_config(None)
        elif provider == "anthropic":
            if llm_config:
                return ConfigValidator.build_anthropic_config(llm_config)
            else:
                return ConfigValidator.build_anthropic_config(None)
        elif provider == "dashscope":
            # DashScope 不在 validate_llm_config 中处理,直接从环境变量读取
            return ConfigValidator.build_dashscope_chat_config(None)
        else:
            error_msg = f"不支持的提供商: {provider}"
            raise ValueError(error_msg)

    def _build_embedding_config(self, provider: str) -> dict[str, Any]:
        """构建嵌入模型配置

        Args:
            provider: 提供商名称

        Returns:
            配置字典

        Raises:
            ValueError: 如果必需配置未设置
        """
        if not self._config:
            error_msg = "配置未设置,请先调用 set_config() 或确保配置已自动加载"
            raise ValueError(error_msg)

        # 使用统一的配置验证器构建配置
        embedding_config = self._config.embedding
        config_dict = {
            "dimension": embedding_config.dimension,
            "batch_size": embedding_config.batch_size,
            "api_key": embedding_config.api_key,
            "model_name": embedding_config.model_name,
        }

        return ConfigValidator.build_embedding_config(provider, config_dict)

    def _build_rerank_config(self, provider: str) -> dict[str, Any]:
        """构建重排序模型配置

        Args:
            provider: 提供商名称

        Returns:
            配置字典

        Raises:
            ValueError: 如果必需配置未设置
        """
        if not self._config:
            error_msg = "配置未设置,请先调用 set_config() 或确保配置已自动加载"
            raise ValueError(error_msg)

        # 使用统一的配置验证器构建配置
        rerank_config = self._config.rerank
        config_dict = {
            "top_k": rerank_config.top_k,
            "api_key": rerank_config.api_key,
            "model_name": rerank_config.model_name,
        }

        return ConfigValidator.build_rerank_config(provider, config_dict)

    def clear_cache(self):
        """清空模型缓存"""
        self._chat_models.clear()
        self._embedding_models.clear()
        self._rerank_models.clear()
        logger.info("LLM 服务缓存已清空")

    def get_available_providers(self) -> list[str]:
        """获取可用的提供商列表

        Returns:
            提供商列表
        """
        return list(self._providers.keys())

    def is_provider_available(self, provider: str) -> bool:
        """检查提供商是否可用

        Args:
            provider: 提供商名称

        Returns:
            是否可用
        """
        return provider in self._providers


# 全局 LLM 服务实例
llm_service = LLMService()


def get_llm_service() -> LLMService:
    """获取 LLM 服务实例

    Returns:
        LLMService 实例
    """
    return llm_service
