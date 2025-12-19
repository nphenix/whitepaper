# 生成命令: /speckit.implement T009
# 生成时间: 2025-12-07
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
配置管理模块单元测试
测试关键配置加载和验证逻辑
"""

import os
from unittest.mock import patch

import pytest

from src.shared.config.settings import (
    AppConfig,
    EmbeddingConfig,
    RerankConfig,
    get_config,
    load_config,
)


class TestAppConfig:
    """应用主配置测试"""

    def test_default_values(self):
        """测试默认值"""
        config = AppConfig()
        assert config.environment == "development"
        assert config.testing is False
        assert config.debug is False
        assert config.llm_provider == "openai_compatible"
        assert config.timezone == "Asia/Shanghai"
        assert config.encoding == "utf-8"

    def test_environment_validation(self):
        """测试环境验证"""
        config = AppConfig(environment="production")
        assert config.environment == "production"

        config = AppConfig(environment="testing")
        assert config.environment == "testing"

        # 无效环境
        with pytest.raises(ValueError):
            AppConfig(environment="invalid")

    def test_llm_provider_validation(self):
        """测试LLM提供商验证"""
        config = AppConfig(llm_provider="gemini")
        assert config.llm_provider == "gemini"

        config = AppConfig(llm_provider="anthropic")
        assert config.llm_provider == "anthropic"

        # 无效提供商
        with pytest.raises(ValueError):
            AppConfig(llm_provider="invalid")

    def test_nested_configs(self):
        """测试嵌套配置初始化"""
        config = AppConfig()

        # 检查嵌套配置是否正确初始化
        assert isinstance(config.embedding, EmbeddingConfig)
        assert isinstance(config.rerank, RerankConfig)


class TestLoadConfig:
    """配置加载测试 - 核心业务逻辑"""

    def test_load_default_config(self):
        """测试加载默认配置"""
        config = load_config()
        assert isinstance(config, AppConfig)

    @patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openai_compatible",
            "LLM_API_KEY": "test_openai_key",
            "LLM_BASE_URL": "https://api.openai.com/v1",
            "LLM_MODEL_NAME": "gpt-4",
            "LLM_TEMPERATURE": "0.7",
            "LLM_MAX_TOKENS": "4096",
            "LLM_TIMEOUT": "60",
        },
    )
    def test_openai_compatible_config_from_env(self):
        """测试从环境变量加载OpenAI兼容配置"""
        config = load_config()
        assert config.llm_config["provider"] == "openai_compatible"
        assert config.llm_config["api_key"] == "test_openai_key"
        assert config.llm_config["base_url"] == "https://api.openai.com/v1"
        assert config.llm_config["model_name"] == "gpt-4"
        assert config.llm_config["temperature"] == 0.7
        assert config.llm_config["max_tokens"] == 4096
        assert config.llm_config["timeout"] == 60

    @patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test_gemini_key",
            "GEMINI_MODEL_NAME": "gemini-pro",
            "GEMINI_TEMPERATURE": "0.8",
            "GEMINI_MAX_TOKENS": "2048",
        },
    )
    def test_gemini_config_from_env(self):
        """测试从环境变量加载Gemini配置"""
        config = load_config()
        assert config.llm_config["provider"] == "gemini"
        assert config.llm_config["api_key"] == "test_gemini_key"
        assert config.llm_config["model_name"] == "gemini-pro"
        assert config.llm_config["temperature"] == 0.8
        assert config.llm_config["max_tokens"] == 2048

    @patch.dict(
        os.environ,
        {
            "EMBEDDING_API_KEY": "test_embedding_key",
            "EMBEDDING_MODEL_NAME": "text-embedding-v4",
            "EMBEDDING_PROVIDER": "dashscope",
            "EMBEDDING_DIMENSION": "1536",
            "EMBEDDING_BATCH_SIZE": "32",
        },
    )
    def test_embedding_config_from_env(self):
        """测试从环境变量加载嵌入配置"""
        config = load_config()
        assert config.embedding.api_key == "test_embedding_key"
        assert config.embedding.model_name == "text-embedding-v4"
        assert config.embedding.provider == "dashscope"
        assert config.embedding.dimension == 1536
        assert config.embedding.batch_size == 32

    @patch.dict(
        os.environ,
        {
            "RERANK_API_KEY": "test_rerank_key",
            "RERANK_MODEL_NAME": "qwen3-rerank",
            "RERANK_PROVIDER": "dashscope",
            "RERANK_TOP_K": "10",
        },
    )
    def test_rerank_config_from_env(self):
        """测试从环境变量加载重排序配置"""
        config = load_config()
        assert config.rerank.api_key == "test_rerank_key"
        assert config.rerank.model_name == "qwen3-rerank"
        assert config.rerank.provider == "dashscope"
        assert config.rerank.top_k == 10

    def test_missing_required_env_vars(self):
        """测试缺少必需环境变量的情况"""
        with patch.dict(
            os.environ,
            {
                "LLM_PROVIDER": "openai_compatible",
                # 缺少 LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME
            },
            clear=True,
        ):
            with pytest.raises(ValueError, match="LLM_API_KEY 环境变量未设置"):
                load_config()


class TestGetConfig:
    """获取默认配置测试"""

    def test_get_config_singleton(self):
        """测试配置单例"""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_get_config_type(self):
        """测试配置类型"""
        config = get_config()
        assert isinstance(config, AppConfig)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
