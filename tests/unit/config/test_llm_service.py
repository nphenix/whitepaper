# 生成命令: /speckit.implement T009
# 生成时间: 2025-12-07
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
LLM服务单元测试
测试LangChain 1.0动态模型统一集中配置服务
只测试KAT(OpenAI兼容)和阿里百炼(DashScope)
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.shared.config.llm_service import (
    DashScopeChatModel,
    DashScopeEmbeddingModel,
    DashScopeProvider,
    DashScopeRerankWrapper,
    LLMProvider,
    LLMService,
    OpenAICompatibleProvider,
    get_llm_service,
    llm_service,
)
from src.shared.config.settings import AppConfig


class TestLLMProvider:
    """LLM提供商抽象基类测试"""

    def test_abstract_methods(self):
        """测试抽象方法"""
        with pytest.raises(TypeError):
            LLMProvider()


class TestOpenAICompatibleProvider:
    """OpenAI兼容提供商测试(KAT)"""

    def setup_method(self):
        """测试前设置"""
        self.provider = OpenAICompatibleProvider()

    @patch.dict(
        os.environ,
        {
            "LLM_API_KEY": "test_kat_key",
            "LLM_BASE_URL": "https://api.katpro1.com/v1",
            "LLM_MODEL_NAME": "katpro1-gpt-4",
            "LLM_TEMPERATURE": "0.7",
            "LLM_MAX_TOKENS": "4096",
            "LLM_TIMEOUT": "60",
        },
    )
    def test_create_chat_model_success(self):
        """测试成功创建KAT聊天模型"""
        config = {
            "api_key": "test_kat_key",
            "base_url": "https://api.katpro1.com/v1",
            "model_name": "katpro1-gpt-4",
            "temperature": 0.7,
            "max_tokens": 4096,
            "timeout": 60,
        }

        with patch("src.shared.config.llm_service.init_chat_model") as mock_init:
            mock_model = MagicMock()
            mock_init.return_value = mock_model

            result = self.provider.create_chat_model(config)

            assert result == mock_model
            mock_init.assert_called_once()
            call_args = mock_init.call_args
            assert call_args[1]["model"] == "openai:katpro1-gpt-4"
            assert call_args[1]["temperature"] == 0.7
            assert call_args[1]["max_tokens"] == 4096
            assert call_args[1]["timeout"] == 60
            assert call_args[1]["api_key"] == "test_kat_key"
            assert call_args[1]["base_url"] == "https://api.katpro1.com/v1"

    def test_create_chat_model_missing_config(self):
        """测试缺少配置时的聊天模型创建"""
        config = {}  # 空配置

        with pytest.raises(Exception, match="配置项 'model_name' 未设置"):
            self.provider.create_chat_model(config)

    def test_create_rerank_model_not_supported(self):
        """测试不支持的重排序模型创建"""
        config = {}

        with pytest.raises(NotImplementedError, match="OpenAI 不支持重排序模型"):
            self.provider.create_rerank_model(config)


class TestDashScopeProvider:
    """阿里百炼DashScope提供商测试"""

    def setup_method(self):
        """测试前设置"""
        self.provider = DashScopeProvider()

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    @patch.dict(
        os.environ,
        {
            "LLM_API_KEY": "test_dashscope_key",
            "LLM_MODEL_NAME": "qwen-turbo",
            "LLM_TEMPERATURE": "0.7",
            "LLM_MAX_TOKENS": "2048",
        },
    )
    def test_create_chat_model_success(self):
        """测试成功创建DashScope聊天模型"""
        config = {
            "api_key": "test_dashscope_key",
            "model_name": "qwen-turbo",
            "temperature": 0.7,
            "max_tokens": 2048,
        }

        with patch(
            "src.shared.config.llm_service.DashScopeChatModel"
        ) as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            result = self.provider.create_chat_model(config)

            assert result == mock_model
            mock_model_class.assert_called_once_with(
                model_name="qwen-turbo",
                temperature=0.7,
                max_tokens=2048,
                api_key="test_dashscope_key",
            )

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", False)
    def test_create_chat_model_dashscope_unavailable(self):
        """测试DashScope不可用时创建聊天模型"""
        config = {}

        with pytest.raises(ImportError, match="dashscope 包未安装"):
            self.provider.create_chat_model(config)

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_create_embedding_model_success(self):
        """测试成功创建DashScope嵌入模型"""
        config = {"api_key": "test_dashscope_key", "model_name": "text-embedding-v4"}

        with patch(
            "src.shared.config.llm_service.DashScopeEmbeddingModel"
        ) as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            result = self.provider.create_embedding_model(config)

            assert result == mock_model
            mock_model_class.assert_called_once_with(
                model_name="text-embedding-v4", api_key="test_dashscope_key"
            )

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_create_rerank_model_success(self):
        """测试成功创建DashScope重排序模型"""
        config = {
            "api_key": "test_dashscope_key",
            "model_name": "qwen3-rerank",
            "top_k": 5,
        }

        with patch(
            "src.shared.config.llm_service.DashScopeRerankWrapper"
        ) as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper_class.return_value = mock_wrapper

            result = self.provider.create_rerank_model(config)

            assert result == mock_wrapper
            mock_wrapper_class.assert_called_once_with(
                api_key="test_dashscope_key", model="qwen3-rerank", top_n=5
            )


class TestDashScopeChatModel:
    """DashScope聊天模型测试"""

    def setup_method(self):
        """测试前设置"""
        with patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True):
            self.model = DashScopeChatModel(
                model_name="qwen-turbo",
                temperature=0.7,
                max_tokens=2048,
                api_key="test_key",
            )

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_initialization(self):
        """测试初始化"""
        with patch("src.shared.config.llm_service.dashscope") as mock_dashscope:
            model = DashScopeChatModel(
                model_name="qwen-turbo",
                temperature=0.7,
                max_tokens=2048,
                api_key="test_key",
            )

            assert model.model_name == "qwen-turbo"
            assert model.temperature == 0.7
            assert model.max_tokens == 2048
            assert model.api_key == "test_key"
            mock_dashscope.api_key = "test_key"

    def test_llm_type(self):
        """测试模型类型"""
        assert self.model._llm_type == "dashscope"

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_generate_success(self):
        """测试成功生成响应"""
        # 模拟消息
        mock_message = MagicMock()
        mock_message.type = "human"
        mock_message.content = "你好"

        # 模拟API响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output.choices = [MagicMock()]
        mock_response.output.choices[0].message.content = "你好!有什么可以帮助您的吗?"

        with patch("src.shared.config.llm_service.Generation") as mock_generation:
            mock_generation.call.return_value = mock_response

            with patch("src.shared.config.llm_service.LLMResult") as mock_llm_result:
                with patch(
                    "src.shared.config.llm_service.Generation"
                ) as mock_generation_class:
                    mock_generation_instance = MagicMock()
                    mock_generation_class.return_value = mock_generation_instance
                    mock_llm_result.return_value = MagicMock()

                    result = self.model._generate([mock_message])

                    assert result is not None
                    mock_generation.call.assert_called_once()

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_stream_success(self):
        """测试成功流式生成"""
        mock_message = MagicMock()
        mock_message.type = "human"
        mock_message.content = "你好"

        # 模拟流式响应
        mock_response1 = MagicMock()
        mock_response1.status_code = 200
        mock_response1.output.choices = [MagicMock()]
        mock_response1.output.choices[0].message.content = "你好"

        mock_response2 = MagicMock()
        mock_response2.status_code = 200
        mock_response2.output.choices = [MagicMock()]
        mock_response2.output.choices[0].message.content = "!"

        with patch("src.shared.config.llm_service.Generation") as mock_generation:
            mock_generation.call.return_value = [mock_response1, mock_response2]

            with patch("src.shared.config.llm_service.GenerationChunk") as mock_chunk:
                mock_chunk_instance = MagicMock()
                mock_chunk.return_value = mock_chunk_instance

                results = list(self.model._stream([mock_message]))

                assert len(results) == 2


class TestDashScopeEmbeddingModel:
    """DashScope嵌入模型测试"""

    def setup_method(self):
        """测试前设置"""
        with patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True):
            self.model = DashScopeEmbeddingModel(
                model_name="text-embedding-v4", api_key="test_key"
            )

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_embed_query_success(self):
        """测试成功嵌入查询"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output.embeddings = [MagicMock()]
        mock_response.output.embeddings[0].embedding = [0.1] * 1536

        with patch("src.shared.config.llm_service.TextEmbedding") as mock_embedding:
            mock_embedding.call.return_value = mock_response

            result = self.model.embed_query("测试文本")

            assert result == [0.1] * 1536
            mock_embedding.call.assert_called_once_with(
                model="text-embedding-v4", input="测试文本"
            )

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_embed_documents(self):
        """测试批量嵌入文档"""
        with patch.object(
            self.model, "embed_query", return_value=[0.1] * 1536
        ) as mock_embed_query:
            result = self.model.embed_documents(["文本1", "文本2"])

            assert len(result) == 2
            assert result[0] == [0.1] * 1536
            assert result[1] == [0.1] * 1536
            assert mock_embed_query.call_count == 2


class TestDashScopeRerankWrapper:
    """DashScope重排序包装器测试"""

    def setup_method(self):
        """测试前设置"""
        with patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True):
            self.wrapper = DashScopeRerankWrapper(
                api_key="test_key", model="qwen3-rerank", top_n=5
            )

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_initialization(self):
        """测试初始化"""
        with patch("src.shared.config.llm_service.dashscope") as mock_dashscope:
            wrapper = DashScopeRerankWrapper(
                api_key="test_key", model="qwen3-rerank", top_n=5
            )

            assert wrapper.api_key == "test_key"
            assert wrapper.model == "qwen3-rerank"
            assert wrapper.top_n == 5
            mock_dashscope.api_key = "test_key"

    @patch("src.shared.config.llm_service.DASHSCOPE_AVAILABLE", True)
    def test_rerank_success(self):
        """测试成功重排序"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output = {
            "results": [
                {"document": {"text": "文档1"}, "index": 0, "relevance_score": 0.9},
                {"document": {"text": "文档2"}, "index": 1, "relevance_score": 0.8},
            ]
        }

        with patch("src.shared.config.llm_service.Rerank") as mock_rerank:
            mock_rerank.call.return_value = mock_response

            result = self.wrapper.rerank(query="测试查询", documents=["文档1", "文档2"])

            assert len(result) == 2
            assert result[0]["document"] == "文档1"
            assert result[0]["relevance_score"] == 0.9
            assert result[1]["document"] == "文档2"
            assert result[1]["relevance_score"] == 0.8


class TestLLMService:
    """LLM服务测试"""

    def setup_method(self):
        """测试前设置"""
        # 清理单例状态
        LLMService._instance = None
        self.service = LLMService()

    def test_singleton_pattern(self):
        """测试单例模式"""
        service1 = LLMService()
        service2 = LLMService()
        assert service1 is service2

    def test_get_llm_service_function(self):
        """测试获取LLM服务函数"""
        service1 = get_llm_service()
        service2 = get_llm_service()
        assert service1 is service2
        assert service1 is llm_service

    def test_get_available_providers(self):
        """测试获取可用提供商"""
        providers = self.service.get_available_providers()
        assert "openai_compatible" in providers  # KAT
        assert "dashscope" in providers  # 阿里百炼

    def test_is_provider_available(self):
        """测试提供商可用性检查"""
        assert self.service.is_provider_available("openai_compatible") is True  # KAT
        assert self.service.is_provider_available("dashscope") is True  # 阿里百炼
        assert self.service.is_provider_available("non_existing") is False

    def test_set_config(self):
        """测试设置配置"""
        config = AppConfig()
        self.service.set_config(config)
        assert self.service._config == config

    def test_get_chat_model_without_config(self):
        """测试未设置配置时获取聊天模型"""
        with pytest.raises(ValueError, match="配置未设置"):
            self.service.get_chat_model()

    def test_get_embedding_model_without_config(self):
        """测试未设置配置时获取嵌入模型"""
        with pytest.raises(ValueError, match="配置未设置"):
            self.service.get_embedding_model()

    def test_get_rerank_model_without_config(self):
        """测试未设置配置时获取重排序模型"""
        with pytest.raises(ValueError, match="配置未设置"):
            self.service.get_rerank_model()

    @patch.dict(
        os.environ,
        {
            "LLM_API_KEY": "test_kat_key",
            "LLM_BASE_URL": "https://api.katpro1.com/v1",
            "LLM_MODEL_NAME": "katpro1-gpt-4",
            "LLM_TEMPERATURE": "0.7",
            "LLM_MAX_TOKENS": "4096",
            "LLM_TIMEOUT": "60",
        },
    )
    def test_get_chat_model_kat(self):
        """测试获取KAT聊天模型"""
        config = AppConfig()
        self.service.set_config(config)

        with patch("src.shared.config.llm_service.init_chat_model") as mock_init:
            mock_model = MagicMock()
            mock_init.return_value = mock_model

            result = self.service.get_chat_model("openai_compatible")

            assert result == mock_model
            mock_init.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "EMBEDDING_API_KEY": "test_dashscope_key",
            "EMBEDDING_MODEL_NAME": "text-embedding-v4",
            "EMBEDDING_DIMENSION": "1536",
            "EMBEDDING_BATCH_SIZE": "32",
        },
    )
    def test_get_embedding_model_dashscope(self):
        """测试获取DashScope嵌入模型"""
        config = AppConfig()
        self.service.set_config(config)

        with patch(
            "src.shared.config.llm_service.DashScopeEmbeddingModel"
        ) as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            result = self.service.get_embedding_model("dashscope")

            assert result == mock_model
            mock_model_class.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "RERANK_API_KEY": "test_dashscope_key",
            "RERANK_MODEL_NAME": "qwen3-rerank",
            "RERANK_TOP_K": "10",
        },
    )
    def test_get_rerank_model_dashscope(self):
        """测试获取DashScope重排序模型"""
        config = AppConfig()
        self.service.set_config(config)

        with patch(
            "src.shared.config.llm_service.DashScopeRerankWrapper"
        ) as mock_wrapper_class:
            mock_wrapper = MagicMock()
            mock_wrapper_class.return_value = mock_wrapper

            result = self.service.get_rerank_model("dashscope")

            assert result == mock_wrapper
            mock_wrapper_class.assert_called_once()

    def test_model_caching(self):
        """测试模型缓存"""
        config = AppConfig()
        self.service.set_config(config)

        with patch("src.shared.config.llm_service.init_chat_model") as mock_init:
            mock_model = MagicMock()
            mock_init.return_value = mock_model

            # 第一次获取
            result1 = self.service.get_chat_model("openai_compatible")
            # 第二次获取(应该从缓存返回)
            result2 = self.service.get_chat_model("openai_compatible")

            assert result1 is result2
            # 只应该调用一次
            assert mock_init.call_count == 1

    def test_clear_cache(self):
        """测试清空缓存"""
        config = AppConfig()
        self.service.set_config(config)

        # 添加一些缓存
        self.service._chat_models["test"] = MagicMock()
        self.service._embedding_models["test"] = MagicMock()
        self.service._rerank_models["test"] = MagicMock()

        # 清空缓存
        self.service.clear_cache()

        assert len(self.service._chat_models) == 0
        assert len(self.service._embedding_models) == 0
        assert len(self.service._rerank_models) == 0

    def test_build_chat_config_kat(self):
        """测试构建KAT聊天配置"""
        config = AppConfig()
        self.service.set_config(config)

        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "test_kat_key",
                "LLM_BASE_URL": "https://api.katpro1.com/v1",
                "LLM_MODEL_NAME": "katpro1-gpt-4",
                "LLM_TEMPERATURE": "0.7",
                "LLM_MAX_TOKENS": "4096",
                "LLM_TIMEOUT": "60",
            },
        ):
            chat_config = self.service._build_chat_config("openai_compatible")

            assert chat_config["api_key"] == "test_kat_key"
            assert chat_config["base_url"] == "https://api.katpro1.com/v1"
            assert chat_config["model_name"] == "katpro1-gpt-4"
            assert chat_config["temperature"] == 0.7
            assert chat_config["max_tokens"] == 4096
            assert chat_config["timeout"] == 60

    def test_build_embedding_config_dashscope(self):
        """测试构建DashScope嵌入配置"""
        config = AppConfig()
        self.service.set_config(config)

        with patch.dict(
            os.environ,
            {
                "EMBEDDING_API_KEY": "test_dashscope_key",
                "EMBEDDING_MODEL_NAME": "text-embedding-v4",
                "EMBEDDING_DIMENSION": "1536",
                "EMBEDDING_BATCH_SIZE": "32",
            },
        ):
            embedding_config = self.service._build_embedding_config("dashscope")

            assert embedding_config["api_key"] == "test_dashscope_key"
            assert embedding_config["model_name"] == "text-embedding-v4"
            assert embedding_config["dimension"] == 1536
            assert embedding_config["batch_size"] == 32

    def test_build_rerank_config_dashscope(self):
        """测试构建DashScope重排序配置"""
        config = AppConfig()
        self.service.set_config(config)

        with patch.dict(
            os.environ,
            {
                "RERANK_API_KEY": "test_dashscope_key",
                "RERANK_MODEL_NAME": "qwen3-rerank",
                "RERANK_TOP_K": "10",
            },
        ):
            rerank_config = self.service._build_rerank_config("dashscope")

            assert rerank_config["api_key"] == "test_dashscope_key"
            assert rerank_config["model_name"] == "qwen3-rerank"
            assert rerank_config["top_k"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
