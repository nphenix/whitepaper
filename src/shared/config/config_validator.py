"""配置验证器

提供统一的配置验证逻辑,消除重复代码(DRY原则).
遵循单一职责原则(SOLID),专注于配置验证功能.
"""

import os
from typing import Any

from ..exceptions.base_exceptions import ValidationError


class ConfigValidator:
    """配置验证器

    提供统一的配置验证方法,消除重复的验证逻辑.
    """

    @staticmethod
    def validate_required_keys(
        config: dict[str, Any],
        required_keys: list[str],
        config_source: str = "配置",
    ) -> None:
        """验证必需配置项是否存在

        Args:
            config: 配置字典
            required_keys: 必需配置项列表
            config_source: 配置来源描述(用于错误消息)

        Raises:
            ValidationError: 如果缺少必需配置项
        """
        missing_keys = [
            key for key in required_keys if key not in config or config[key] is None
        ]
        if missing_keys:
            error_msg = (
                f"{config_source}缺少必需配置项: {', '.join(missing_keys)}."
                f"请在 .env 文件中配置这些项."
            )
            raise ValidationError(error_msg, field_name="config")

    @staticmethod
    def get_env_or_config(
        env_key: str,
        config_dict: dict[str, Any] | None,
        config_key: str | None = None,
        required: bool = True,
        default: Any = None,
    ) -> Any:
        """从配置字典或环境变量获取值

        Args:
            env_key: 环境变量键(作为后备)
            config_dict: 配置字典(优先使用)
            config_key: 配置字典中的键(如果为None则使用env_key)
            required: 是否为必需项
            default: 默认值(仅在required=False时使用)

        Returns:
            配置值

        Raises:
            ValidationError: 如果required=True且值不存在
        """
        config_key = config_key or env_key

        # 优先从配置字典获取(确保配置对象的值优先于环境变量)
        if config_dict and config_key in config_dict:
            value = config_dict.get(config_key)
            if value is not None:
                return str(value) if not isinstance(value, str) else value

        # 其次从环境变量获取(作为后备)
        value = os.getenv(env_key)
        if value is not None:
            return value

        # 如果必需但未找到,抛出异常
        if required:
            error_msg = f"{env_key} 环境变量未设置,请在 .env 文件中配置"
            raise ValidationError(error_msg, field_name=env_key)

        # 返回默认值
        return default

    @staticmethod
    def build_base_chat_config(
        config_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建基础聊天模型配置

        Args:
            config_dict: 配置字典

        Returns:
            基础配置字典(包含temperature,max_tokens,timeout)

        Raises:
            ValidationError: 如果必需配置缺失
        """
        temperature_str = ConfigValidator.get_env_or_config(
            "LLM_TEMPERATURE", config_dict, "temperature"
        )
        max_tokens_str = ConfigValidator.get_env_or_config(
            "LLM_MAX_TOKENS", config_dict, "max_tokens"
        )
        timeout_str = ConfigValidator.get_env_or_config(
            "LLM_TIMEOUT", config_dict, "timeout"
        )

        return {
            "temperature": float(temperature_str),
            "max_tokens": int(max_tokens_str),
            "timeout": int(timeout_str),
        }

    @staticmethod
    def build_openai_compatible_config(
        config_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建OpenAI兼容配置

        Args:
            config_dict: 配置字典

        Returns:
            完整的OpenAI兼容配置

        Raises:
            ValidationError: 如果必需配置缺失
        """
        base_config = ConfigValidator.build_base_chat_config(config_dict)

        base_url = ConfigValidator.get_env_or_config(
            "LLM_BASE_URL", config_dict, "base_url"
        )
        api_key = ConfigValidator.get_env_or_config(
            "LLM_API_KEY", config_dict, "api_key"
        )
        model_name = ConfigValidator.get_env_or_config(
            "LLM_MODEL_NAME", config_dict, "model_name"
        )

        base_config.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "model_name": model_name,
            }
        )

        return base_config

    @staticmethod
    def build_gemini_config(
        config_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建Gemini配置

        Args:
            config_dict: 配置字典

        Returns:
            完整的Gemini配置

        Raises:
            ValidationError: 如果必需配置缺失
        """
        base_config = ConfigValidator.build_base_chat_config(config_dict)

        api_key = ConfigValidator.get_env_or_config(
            "GEMINI_API_KEY", config_dict, "api_key"
        )
        model_name = ConfigValidator.get_env_or_config(
            "GEMINI_MODEL_NAME", config_dict, "model_name"
        )

        base_config.update(
            {
                "api_key": api_key,
                "model_name": model_name,
            }
        )

        return base_config

    @staticmethod
    def build_anthropic_config(
        config_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建Anthropic配置

        Args:
            config_dict: 配置字典

        Returns:
            完整的Anthropic配置

        Raises:
            ValidationError: 如果必需配置缺失
        """
        base_config = ConfigValidator.build_base_chat_config(config_dict)

        api_key = ConfigValidator.get_env_or_config(
            "ANTHROPIC_API_KEY", config_dict, "api_key"
        )
        model_name = ConfigValidator.get_env_or_config(
            "ANTHROPIC_MODEL_NAME", config_dict, "model_name"
        )

        base_config.update(
            {
                "api_key": api_key,
                "model_name": model_name,
            }
        )

        return base_config

    @staticmethod
    def build_dashscope_chat_config(
        config_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建DashScope聊天配置

        Args:
            config_dict: 配置字典

        Returns:
            完整的DashScope聊天配置

        Raises:
            ValidationError: 如果必需配置缺失
        """
        base_config = ConfigValidator.build_base_chat_config(config_dict)

        api_key = ConfigValidator.get_env_or_config(
            "LLM_API_KEY", config_dict, "api_key"
        )
        model_name = ConfigValidator.get_env_or_config(
            "LLM_MODEL_NAME", config_dict, "model_name"
        )
        base_url = ConfigValidator.get_env_or_config(
            "LLM_BASE_URL", config_dict, "base_url"
        )

        base_config.update(
            {
                "api_key": api_key,
                "model_name": model_name,
                "base_url": base_url,
            }
        )

        return base_config

    @staticmethod
    def build_embedding_config(
        provider: str,
        config_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建嵌入模型配置

        Args:
            provider: 提供商名称 (ollama, dashscope, openai, flagembedding)
            config_dict: 配置字典

        Returns:
            嵌入模型配置

        Raises:
            ValidationError: 如果必需配置缺失
        """
        dimension_str = ConfigValidator.get_env_or_config(
            "EMBEDDING_DIMENSION", config_dict, "dimension"
        )
        batch_size_str = ConfigValidator.get_env_or_config(
            "EMBEDDING_BATCH_SIZE", config_dict, "batch_size"
        )

        config = {
            "dimension": int(dimension_str),
            "batch_size": int(batch_size_str),
        }

        if provider == "ollama":
            # Ollama 本地部署配置
            model_name = ConfigValidator.get_env_or_config(
                "EMBEDDING_MODEL_NAME", config_dict, "model_name"
            )
            base_url = ConfigValidator.get_env_or_config(
                "EMBEDDING_BASE_URL", config_dict, "base_url", required=False,
                default="http://localhost:11434"
            )
            api_key = ConfigValidator.get_env_or_config(
                "EMBEDDING_API_KEY", config_dict, "api_key", required=False, default=""
            )

            config.update(
                {
                    "model_name": model_name,
                    "base_url": base_url,
                    "api_key": api_key,
                }
            )
        elif provider == "dashscope":
            api_key = ConfigValidator.get_env_or_config(
                "EMBEDDING_API_KEY", config_dict, "api_key"
            )
            model_name = ConfigValidator.get_env_or_config(
                "EMBEDDING_MODEL_NAME", config_dict, "model_name"
            )
            base_url = ConfigValidator.get_env_or_config(
                "EMBEDDING_BASE_URL",
                config_dict,
                "base_url",
                required=False,
                default="https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
            )

            config.update(
                {
                    "api_key": api_key,
                    "model_name": model_name,
                    "base_url": base_url,
                }
            )
        elif provider == "openai":
            api_key = ConfigValidator.get_env_or_config(
                "OPENAI_EMBEDDING_API_KEY", config_dict, "api_key"
            )
            model_name = ConfigValidator.get_env_or_config(
                "OPENAI_EMBEDDING_MODEL_NAME", config_dict, "model_name"
            )

            config.update(
                {
                    "api_key": api_key,
                    "model_name": model_name,
                }
            )
        elif provider == "flagembedding":
            # FlagEmbedding 本地部署配置
            model_name = ConfigValidator.get_env_or_config(
                "EMBEDDING_MODEL_NAME", config_dict, "model_name"
            )
            model_path = ConfigValidator.get_env_or_config(
                "EMBEDDING_MODEL_PATH", config_dict, "model_path"
            )
            # FlagEmbedding 不需要 API Key 和 base_url
            config.update(
                {
                    "model_name": model_name,
                    "model_path": model_path,
                    "api_key": "",
                    "base_url": "",
                }
            )

        return config

    @staticmethod
    def build_rerank_config(
        provider: str,
        config_dict: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建重排序模型配置

        Args:
            provider: 提供商名称 (ollama, dashscope, flagembedding)
            config_dict: 配置字典

        Returns:
            重排序模型配置

        Raises:
            ValidationError: 如果必需配置缺失
        """
        top_k_str = ConfigValidator.get_env_or_config(
            "RERANK_TOP_K", config_dict, "top_k"
        )

        config = {
            "top_k": int(top_k_str),
        }

        if provider == "ollama":
            # Ollama/vLLM/Xinference 本地部署配置
            model_name = ConfigValidator.get_env_or_config(
                "RERANK_MODEL_NAME", config_dict, "model_name"
            )
            base_url = ConfigValidator.get_env_or_config(
                "RERANK_BASE_URL", config_dict, "base_url", required=False,
                default="http://localhost:8000"
            )
            api_key = ConfigValidator.get_env_or_config(
                "RERANK_API_KEY", config_dict, "api_key", required=False, default=""
            )

            config.update(
                {
                    "model_name": model_name,
                    "base_url": base_url,
                    "api_key": api_key,
                }
            )
        elif provider == "dashscope":
            api_key = ConfigValidator.get_env_or_config(
                "RERANK_API_KEY", config_dict, "api_key"
            )
            model_name = ConfigValidator.get_env_or_config(
                "RERANK_MODEL_NAME", config_dict, "model_name"
            )

            config.update(
                {
                    "api_key": api_key,
                    "model_name": model_name,
                }
            )
        elif provider == "flagembedding":
            # FlagEmbedding 本地部署配置
            model_name = ConfigValidator.get_env_or_config(
                "RERANK_MODEL_NAME", config_dict, "model_name"
            )
            model_path = ConfigValidator.get_env_or_config(
                "RERANK_MODEL_PATH", config_dict, "model_path"
            )
            # FlagEmbedding 不需要 API Key 和 base_url
            config.update(
                {
                    "model_name": model_name,
                    "model_path": model_path,
                    "api_key": "",
                    "base_url": "",
                }
            )

        return config
