"""
向量嵌入生成器测试 (T053)

测试 EmbeddingGenerator 的功能, 包括:
- 批量嵌入生成
- 异步嵌入生成
- 嵌入结果缓存
- 错误处理
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

try:
    from llama_index.core.schema import TextNode
    from llama_index.core.embeddings import BaseEmbedding

    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False
    TextNode = None  # type: ignore[assignment, misc]
    BaseEmbedding = None  # type: ignore[assignment, misc]

from src.infrastructure.indexing.embedding_generator import (
    EmbeddingGenerator,
    EmbeddingCache,
    EmbeddingError,
)


@pytest.fixture
def mock_embedding_model():
    """创建模拟的 embedding 模型"""
    if not LLAMA_INDEX_AVAILABLE:
        pytest.skip("LlamaIndex not available")

    async def mock_aget_text_embeddings(texts):
        """模拟异步方法"""
        return [[0.1] * 384, [0.2] * 384]

    # 使用AsyncMock包装异步函数，以便可以调用assert_called_once等
    from unittest.mock import AsyncMock

    model = MagicMock(spec=BaseEmbedding)
    model.get_text_embeddings = MagicMock(
        return_value=[[0.1] * 384, [0.2] * 384]
    )
    model.aget_text_embeddings = AsyncMock(side_effect=mock_aget_text_embeddings)
    return model


@pytest.fixture
def mock_langchain_embedding():
    """创建模拟的 LangChain embedding 模型"""
    langchain_model = MagicMock()
    langchain_model.embed_documents = MagicMock(
        return_value=[[0.1] * 384, [0.2] * 384]
    )
    langchain_model.embed_query = MagicMock(return_value=[0.1] * 384)
    return langchain_model


@pytest.fixture
def sample_nodes():
    """创建示例 Node 列表"""
    if not LLAMA_INDEX_AVAILABLE:
        pytest.skip("LlamaIndex not available")

    return [
        TextNode(text="这是第一个测试文本", metadata={"source": "test1"}),
        TextNode(text="这是第二个测试文本", metadata={"source": "test2"}),
    ]


class TestEmbeddingCache:
    """测试 EmbeddingCache 类"""

    def test_cache_init(self):
        """测试缓存初始化"""
        cache = EmbeddingCache(max_size=100)
        assert cache.max_size == 100
        assert cache.size() == 0

    def test_cache_set_and_get(self):
        """测试缓存设置和获取"""
        cache = EmbeddingCache(max_size=100)
        text = "测试文本"
        embedding = [0.1] * 384

        # 设置缓存
        cache.set(text, embedding)

        # 获取缓存
        result = cache.get(text)
        assert result == embedding
        assert cache.size() == 1

    def test_cache_miss(self):
        """测试缓存未命中"""
        cache = EmbeddingCache(max_size=100)
        text = "测试文本"

        # 获取不存在的缓存
        result = cache.get(text)
        assert result is None

    def test_cache_hash_consistency(self):
        """测试缓存哈希一致性"""
        cache = EmbeddingCache(max_size=100)
        text = "测试文本"
        embedding = [0.1] * 384

        # 设置缓存
        cache.set(text, embedding)

        # 使用相同文本获取缓存
        result = cache.get(text)
        assert result == embedding

    def test_cache_clear(self):
        """测试清空缓存"""
        cache = EmbeddingCache(max_size=100)
        text = "测试文本"
        embedding = [0.1] * 384

        cache.set(text, embedding)
        assert cache.size() == 1

        cache.clear()
        assert cache.size() == 0
        assert cache.get(text) is None

    def test_cache_eviction(self):
        """测试缓存淘汰策略"""
        cache = EmbeddingCache(max_size=2)

        # 添加两个条目
        cache.set("text1", [0.1] * 384)
        cache.set("text2", [0.2] * 384)
        assert cache.size() == 2

        # 添加第三个条目, 应该触发淘汰
        cache.set("text3", [0.3] * 384)
        assert cache.size() == 2

        # 第一个条目应该被淘汰
        assert cache.get("text1") is None
        assert cache.get("text2") is not None
        assert cache.get("text3") is not None


class TestEmbeddingGenerator:
    """测试 EmbeddingGenerator 类"""

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_init_with_model(self, mock_embedding_model):
        """测试使用提供的模型初始化"""
        generator = EmbeddingGenerator(embedding_model=mock_embedding_model)
        assert generator.embedding_model == mock_embedding_model
        assert generator.enable_cache is True
        assert generator.cache is not None

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    @patch("src.infrastructure.indexing.embedding_generator.get_llm_service")
    def test_init_from_llm_service(
        self, mock_get_llm_service, mock_langchain_embedding
    ):
        """测试从 llm_service 获取模型初始化"""
        # 模拟 llm_service
        mock_service = MagicMock()
        mock_service.get_embedding_model.return_value = mock_langchain_embedding
        mock_get_llm_service.return_value = mock_service

        generator = EmbeddingGenerator()
        assert generator.embedding_model is not None
        assert generator.enable_cache is True

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_init_without_cache(self, mock_embedding_model):
        """测试禁用缓存的初始化"""
        generator = EmbeddingGenerator(
            embedding_model=mock_embedding_model, enable_cache=False
        )
        assert generator.enable_cache is False
        assert generator.cache is None

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_generate_embeddings(self, mock_embedding_model, sample_nodes):
        """测试批量嵌入生成"""
        generator = EmbeddingGenerator(embedding_model=mock_embedding_model)

        result = generator.generate_embeddings(sample_nodes)

        assert len(result) == 2
        assert all(hasattr(node, "embedding") for node in result)
        assert all(node.embedding is not None for node in result)
        mock_embedding_model.get_text_embeddings.assert_called_once()

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_generate_embeddings_with_cache(
        self, mock_embedding_model, sample_nodes
    ):
        """测试带缓存的嵌入生成"""
        generator = EmbeddingGenerator(
            embedding_model=mock_embedding_model, enable_cache=True
        )

        # 第一次生成
        result1 = generator.generate_embeddings(sample_nodes)
        assert len(result1) == 2
        assert mock_embedding_model.get_text_embeddings.call_count == 1

        # 第二次生成(应该使用缓存)
        result2 = generator.generate_embeddings(sample_nodes)
        assert len(result2) == 2
        # 应该只调用一次(缓存命中)
        assert mock_embedding_model.get_text_embeddings.call_count == 1

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_generate_embeddings_empty_list(self, mock_embedding_model):
        """测试空列表的嵌入生成"""
        generator = EmbeddingGenerator(embedding_model=mock_embedding_model)

        result = generator.generate_embeddings([])
        assert result == []
        mock_embedding_model.get_text_embeddings.assert_not_called()

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_generate_embeddings_with_empty_text(
        self, mock_embedding_model
    ):
        """测试包含空文本节点的嵌入生成"""
        if not LLAMA_INDEX_AVAILABLE:
            pytest.skip("LlamaIndex not available")

        generator = EmbeddingGenerator(embedding_model=mock_embedding_model)

        nodes = [
            TextNode(text="有效文本", metadata={"source": "test1"}),
            TextNode(text="", metadata={"source": "test2"}),  # 空文本
            TextNode(text="   ", metadata={"source": "test3"}),  # 空白文本
        ]

        # Mock只返回一个embedding（对应一个有效文本）
        mock_embedding_model.get_text_embeddings.return_value = [[0.1] * 384]

        result = generator.generate_embeddings(nodes)
        # 应该只处理有效文本节点
        assert len(result) == 3  # 所有节点都返回, 但只有有效文本生成嵌入
        
        # 找到有效文本节点（应该有embedding）
        valid_node = next((n for n in result if hasattr(n, "embedding") and n.embedding is not None), None)
        assert valid_node is not None, "应该有一个节点有embedding"
        assert valid_node.text == "有效文本"
        
        # 空文本节点不应该有embedding
        empty_nodes = [n for n in result if n.text == "" or n.text.strip() == ""]
        for node in empty_nodes:
            assert not hasattr(node, "embedding") or node.embedding is None

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_generate_embeddings_error(self, mock_embedding_model, sample_nodes):
        """测试嵌入生成错误处理"""
        generator = EmbeddingGenerator(embedding_model=mock_embedding_model)

        # 模拟嵌入生成失败
        mock_embedding_model.get_text_embeddings.side_effect = Exception(
            "嵌入生成失败"
        )

        with pytest.raises(EmbeddingError) as exc_info:
            generator.generate_embeddings(sample_nodes)

        assert "嵌入生成失败" in str(exc_info.value)

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    @pytest.mark.asyncio
    async def test_agenerate_embeddings(self, mock_embedding_model, sample_nodes):
        """测试异步批量嵌入生成"""
        generator = EmbeddingGenerator(embedding_model=mock_embedding_model)

        result = await generator.agenerate_embeddings(sample_nodes)

        assert len(result) == 2
        assert all(hasattr(node, "embedding") for node in result)
        assert all(node.embedding is not None for node in result)
        mock_embedding_model.aget_text_embeddings.assert_called_once()

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    @pytest.mark.asyncio
    async def test_agenerate_embeddings_fallback(
        self, mock_embedding_model, sample_nodes
    ):
        """测试异步嵌入生成回退到同步方法"""
        # 移除异步方法
        del mock_embedding_model.aget_text_embeddings

        generator = EmbeddingGenerator(embedding_model=mock_embedding_model)

        result = await generator.agenerate_embeddings(sample_nodes)

        assert len(result) == 2
        # 应该回退到同步方法
        mock_embedding_model.get_text_embeddings.assert_called_once()

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    @pytest.mark.asyncio
    async def test_agenerate_embeddings_with_cache(
        self, mock_embedding_model, sample_nodes
    ):
        """测试带缓存的异步嵌入生成"""
        generator = EmbeddingGenerator(
            embedding_model=mock_embedding_model, enable_cache=True
        )

        # 第一次生成
        result1 = await generator.agenerate_embeddings(sample_nodes)
        assert len(result1) == 2
        assert mock_embedding_model.aget_text_embeddings.call_count == 1

        # 第二次生成(应该使用缓存)
        result2 = await generator.agenerate_embeddings(sample_nodes)
        assert len(result2) == 2
        # 应该只调用一次(缓存命中)
        assert mock_embedding_model.aget_text_embeddings.call_count == 1

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_clear_cache(self, mock_embedding_model):
        """测试清空缓存"""
        generator = EmbeddingGenerator(
            embedding_model=mock_embedding_model, enable_cache=True
        )

        # 添加一些缓存
        if generator.cache:
            generator.cache.set("test", [0.1] * 384)
            assert generator.cache.size() > 0

        # 清空缓存
        generator.clear_cache()
        if generator.cache:
            assert generator.cache.size() == 0

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_get_cache_stats(self, mock_embedding_model):
        """测试获取缓存统计信息"""
        generator = EmbeddingGenerator(
            embedding_model=mock_embedding_model, enable_cache=True
        )

        stats = generator.get_cache_stats()
        assert stats["enabled"] is True
        assert "size" in stats
        assert "max_size" in stats

    @pytest.mark.skipif(
        not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available"
    )
    def test_get_cache_stats_disabled(self, mock_embedding_model):
        """测试禁用缓存时的统计信息"""
        generator = EmbeddingGenerator(
            embedding_model=mock_embedding_model, enable_cache=False
        )

        stats = generator.get_cache_stats()
        assert stats["enabled"] is False

