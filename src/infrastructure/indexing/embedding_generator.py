"""
向量嵌入生成器实现 (T053)

该模块实现向量嵌入生成功能, 使用 LlamaIndex 的 embedding 接口,
集成项目统一的 embedding 模型配置(从 T009 llm_service 获取).

设计目标:
- 使用 ``llama_index.core.embeddings`` 或 ``llama_index.embeddings`` 进行向量嵌入
- 必须从 T009 创建的 llm_service 获取 Embedding 模型实例(阿里百炼 text-embedding-v4)
- 支持批量嵌入生成
- 支持异步嵌入生成(如果模型支持)
- 缓存嵌入结果, 避免重复计算
"""

from __future__ import annotations

import hashlib
from typing import Any

from src.shared.config.llm_service import get_llm_service
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.embeddings import BaseEmbedding
    from llama_index.core.schema import Node, TextNode

    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 llama-index 时触发
    logger.warning(
        "LlamaIndex not available, embedding generation will be disabled"
    )
    BaseEmbedding = Any  # type: ignore[assignment, misc]
    Node = Any  # type: ignore[assignment, misc]
    TextNode = Any  # type: ignore[assignment, misc]
    LLAMA_INDEX_AVAILABLE = False


class EmbeddingError(Exception):
    """向量嵌入异常基类"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 简单字符串表示
        return f"向量嵌入错误: {self.message}"


class LangChainEmbeddingAdapter(BaseEmbedding):
    """
    LangChain Embedding 模型适配器

    将 LangChain 的 embedding 模型包装为 LlamaIndex 的 BaseEmbedding,
    以便在 LlamaIndex 中使用项目统一的 embedding 配置.
    """

    def __init__(
        self,
        langchain_embedding: Any,
        model_name: str = "langchain-embedding",
    ) -> None:
        """
        初始化适配器

        Args:
            langchain_embedding: LangChain embedding 模型实例
            model_name: 模型名称, 用于标识
        """
        if not LLAMA_INDEX_AVAILABLE:
            msg = "LlamaIndex is not available. Please install llama-index package."
            raise ImportError(
                msg
            )

        super().__init__(model_name=model_name)
        self._langchain_embedding = langchain_embedding

        # 尝试获取向量维度
        try:
            # 使用一个测试文本获取维度
            test_embedding = langchain_embedding.embed_query("test")
            self._dimension = len(test_embedding)
        except Exception:
            # 如果失败, 使用默认值
            self._dimension = 1536
            logger.warning(
                "无法自动检测 embedding 维度, 使用默认值: %s", self._dimension
            )

    @property
    def dimension(self) -> int:
        """返回向量维度"""
        return self._dimension

    def _get_query_embedding(self, query: str) -> list[float]:
        """
        获取查询文本的嵌入向量

        Args:
            query: 查询文本

        Returns:
            嵌入向量
        """
        return self._langchain_embedding.embed_query(query)  # type: ignore

    def _get_text_embedding(self, text: str) -> list[float]:
        """
        获取单个文本的嵌入向量

        Args:
            text: 文本内容

        Returns:
            嵌入向量
        """
        return self._langchain_embedding.embed_query(text)  # type: ignore

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        批量获取文本的嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        return self._langchain_embedding.embed_documents(texts)  # type: ignore

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """
        异步获取查询文本的嵌入向量

        Args:
            query: 查询文本

        Returns:
            嵌入向量
        """
        # 检查是否支持异步方法
        if hasattr(self._langchain_embedding, "aembed_query"):
            return await self._langchain_embedding.aembed_query(query)  # type: ignore[no-any-return]
        # 回退到同步方法
        return self._get_query_embedding(query)

    async def _aget_text_embeddings(
        self, texts: list[str]
    ) -> list[list[float]]:
        """
        异步批量获取文本的嵌入向量

        Args:
            texts: 文本列表

        Returns:
            嵌入向量列表
        """
        # 检查是否支持异步方法
        if hasattr(self._langchain_embedding, "aembed_documents"):
            return await self._langchain_embedding.aembed_documents(texts)  # type: ignore[no-any-return]
        # 回退到同步方法
        return self._get_text_embeddings(texts)


class EmbeddingCache:
    """
    嵌入结果缓存

    使用 LRU 缓存策略, 基于文本内容的哈希值进行缓存,
    避免对相同文本重复计算嵌入向量.
    """

    def __init__(self, max_size: int = 1000) -> None:
        """
        初始化嵌入缓存

        Args:
            max_size: 最大缓存条目数
        """
        self.max_size = max_size
        self._cache: dict[str, list[float]] = {}
        logger.debug("初始化嵌入缓存: max_size=%s", max_size)

    def _hash_text(self, text: str) -> str:
        """
        计算文本的哈希值

        Args:
            text: 文本内容

        Returns:
            文本的 SHA256 哈希值(十六进制字符串)
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> list[float] | None:
        """
        从缓存获取嵌入向量

        Args:
            text: 文本内容

        Returns:
            嵌入向量, 如果不存在则返回 None
        """
        text_hash = self._hash_text(text)
        return self._cache.get(text_hash)

    def set(self, text: str, embedding: list[float]) -> None:
        """
        将嵌入向量存入缓存

        Args:
            text: 文本内容
            embedding: 嵌入向量
        """
        if len(self._cache) >= self.max_size:
            # 删除最旧的条目(简单策略: 删除第一个)
            # 注意: 实际应用中可以使用更复杂的 LRU 策略
            first_key = next(iter(self._cache))
            del self._cache[first_key]
            logger.debug("缓存已满, 删除最旧条目: %s", first_key[:8])

        text_hash = self._hash_text(text)
        self._cache[text_hash] = embedding
        logger.debug("缓存嵌入向量: text_hash=%s", text_hash[:8])

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("嵌入缓存已清空")

    def size(self) -> int:
        """
        获取当前缓存大小

        Returns:
            缓存条目数
        """
        return len(self._cache)


class EmbeddingGenerator:
    """
    向量嵌入生成器

    使用 LlamaIndex 的 embedding 接口, 集成项目统一的 embedding 模型配置,
    支持批量嵌入生成,异步嵌入生成和结果缓存.

    典型用法:
        >>> generator = EmbeddingGenerator()
        >>> nodes = [TextNode(text="示例文本")]
        >>> embedded_nodes = generator.generate_embeddings(nodes)
    """

    def __init__(
        self,
        embedding_model: BaseEmbedding | None = None,
        enable_cache: bool = True,
        cache_size: int = 1000,
    ) -> None:
        """
        初始化嵌入生成器

        Args:
            embedding_model: LlamaIndex embedding 模型实例,
                           如果为 None 则从 llm_service 获取
            enable_cache: 是否启用嵌入结果缓存
            cache_size: 缓存最大条目数

        Raises:
            ImportError: 如果 LlamaIndex 未安装
            EmbeddingError: 如果无法获取 embedding 模型
        """
        if not LLAMA_INDEX_AVAILABLE:
            msg = (
                "LlamaIndex is not available. Please install llama-index package to "
                "use EmbeddingGenerator."
            )
            raise ImportError(
                msg
            )

        # 获取 embedding 模型
        if embedding_model is None:
            try:
                # 从 T009 llm_service 获取 embedding 模型(使用 settings.py 统一配置)
                llm_service = get_llm_service()
                langchain_embedding = llm_service.get_embedding_model()

                # 将 LangChain embedding 模型包装为 LlamaIndex BaseEmbedding
                # 使用适配器类, 兼容 LlamaIndex 接口
                # 获取模型名称,如果配置不存在或无效则使用默认值
                model_name = "langchain-embedding"
                if llm_service._config and hasattr(llm_service._config, "embedding"):
                    config_model_name = getattr(
                        llm_service._config.embedding, "model_name", None
                    )
                    if config_model_name and isinstance(config_model_name, str):
                        model_name = config_model_name

                embedding_model = LangChainEmbeddingAdapter(
                    langchain_embedding, model_name=model_name
                )
                logger.info(
                    "从 llm_service 获取 embedding 模型(使用 settings.py 统一配置)并包装为 LlamaIndex BaseEmbedding"
                )
            except Exception as exc:
                error_msg = f"无法获取 embedding 模型: {exc}"
                logger.error(error_msg, exc_info=True)
                raise EmbeddingError(error_msg) from exc

        self.embedding_model = embedding_model
        self.enable_cache = enable_cache
        self.cache = EmbeddingCache(cache_size) if enable_cache else None

        logger.info(
            "初始化 EmbeddingGenerator: enable_cache=%s, cache_size=%s",
            enable_cache,
            cache_size,
        )

    def generate_embeddings(
        self, nodes: list[Node], batch_size: int | None = None
    ) -> list[Node]:
        """
        为 LlamaIndex Node 列表生成嵌入向量

        该方法会:
        1. 检查缓存中是否已有嵌入向量
        2. 对未缓存的节点批量生成嵌入向量
        3. 将嵌入向量设置到节点的 embedding 属性
        4. 更新缓存(如果启用)

        Args:
            nodes: LlamaIndex Node 列表
            batch_size: 批量处理大小, 如果为 None 则使用模型默认值

        Returns:
            已设置嵌入向量的 Node 列表

        Raises:
            EmbeddingError: 如果嵌入生成失败
        """
        if not nodes:
            logger.warning("空的 Node 列表, 不执行嵌入生成")
            return []

        embedded_nodes: list[Node] = []
        nodes_to_embed: list[Node] = []
        node_indices: list[int] = []

        # 检查缓存并收集需要嵌入的节点
        for idx, node in enumerate(nodes):
            text = getattr(node, "text", None)
            if not text or not str(text).strip():
                logger.debug("跳过空文本节点: index=%s", idx)
                embedded_nodes.append(node)
                continue

            text_str = str(text)

            # 检查缓存
            if self.enable_cache and self.cache:
                cached_embedding = self.cache.get(text_str)
                if cached_embedding is not None:
                    # 使用缓存的嵌入向量
                    node.embedding = cached_embedding
                    embedded_nodes.append(node)
                    logger.debug("使用缓存的嵌入向量: index=%s", idx)
                    continue

            # 需要生成嵌入向量
            nodes_to_embed.append(node)
            node_indices.append(idx)

        # 批量生成嵌入向量
        if nodes_to_embed:
            try:
                # 只提取有效文本(非空)
                texts = []
                valid_nodes = []
                for node in nodes_to_embed:
                    text = getattr(node, "text", None)
                    if text and str(text).strip():
                        texts.append(str(text))
                        valid_nodes.append(node)

                if not texts:
                    # 如果没有有效文本, 直接返回所有节点(不设置embedding)
                    embedded_nodes.extend(nodes_to_embed)
                else:
                    # 使用 LlamaIndex embedding 模型的 _get_text_embeddings 方法
                    # 该方法支持批量嵌入生成
                    embeddings = self.embedding_model._get_text_embeddings(texts)

                    # 将嵌入向量设置到节点并更新缓存
                    for node, embedding in zip(valid_nodes, embeddings, strict=True):
                        node.embedding = embedding
                        embedded_nodes.append(node)

                        # 更新缓存
                        if self.enable_cache and self.cache:
                            text_str = str(getattr(node, "text", ""))
                            self.cache.set(text_str, embedding)

                    # 处理无效节点(空文本)
                    for node in nodes_to_embed:
                        if node not in valid_nodes:
                            embedded_nodes.append(node)

                logger.info(
                    "批量生成嵌入向量: 节点数=%s, 缓存命中=%s, 新生成=%s",
                    len(nodes),
                    len(nodes) - len(nodes_to_embed),
                    len(nodes_to_embed),
                )
            except Exception as exc:
                error_msg = f"批量嵌入生成失败: {exc}"
                logger.error(error_msg, exc_info=True)
                raise EmbeddingError(error_msg) from exc

        return embedded_nodes

    async def agenerate_embeddings(
        self, nodes: list[Node], batch_size: int | None = None
    ) -> list[Node]:
        """
        异步为 LlamaIndex Node 列表生成嵌入向量

        如果 embedding 模型支持异步操作, 则使用异步方法;
        否则回退到同步方法.

        Args:
            nodes: LlamaIndex Node 列表
            batch_size: 批量处理大小, 如果为 None 则使用模型默认值

        Returns:
            已设置嵌入向量的 Node 列表

        Raises:
            EmbeddingError: 如果嵌入生成失败
        """
        if not nodes:
            logger.warning("空的 Node 列表, 不执行异步嵌入生成")
            return []

        embedded_nodes: list[Node] = []
        nodes_to_embed: list[Node] = []
        node_indices: list[int] = []

        # 检查缓存并收集需要嵌入的节点
        for idx, node in enumerate(nodes):
            text = getattr(node, "text", None)
            if not text or not str(text).strip():
                logger.debug("跳过空文本节点: index=%s", idx)
                embedded_nodes.append(node)
                continue

            text_str = str(text)

            # 检查缓存
            if self.enable_cache and self.cache:
                cached_embedding = self.cache.get(text_str)
                if cached_embedding is not None:
                    # 使用缓存的嵌入向量
                    node.embedding = cached_embedding
                    embedded_nodes.append(node)
                    logger.debug("使用缓存的嵌入向量: index=%s", idx)
                    continue

            # 需要生成嵌入向量
            nodes_to_embed.append(node)
            node_indices.append(idx)

        # 异步批量生成嵌入向量
        if nodes_to_embed:
            try:
                # 只提取有效文本(非空)
                texts = []
                valid_nodes = []
                for node in nodes_to_embed:
                    text = getattr(node, "text", None)
                    if text and str(text).strip():
                        texts.append(str(text))
                        valid_nodes.append(node)

                if not texts:
                    # 如果没有有效文本, 直接返回所有节点(不设置embedding)
                    embedded_nodes.extend(nodes_to_embed)
                else:
                    # 检查是否支持异步方法
                    if hasattr(self.embedding_model, "aget_text_embeddings"):
                        # 使用异步方法
                        async_method = self.embedding_model.aget_text_embeddings
                        # 检查返回的是否是协程
                        result = async_method(texts)
                        if hasattr(result, "__await__"):
                            embeddings = await result
                        else:
                            # 如果不是协程, 直接使用
                            embeddings = result
                    else:
                        # 回退到同步方法
                        logger.warning(
                            "embedding 模型不支持异步操作, 回退到同步方法"
                        )
                        embeddings = self.embedding_model._get_text_embeddings(texts)

                    # 将嵌入向量设置到节点并更新缓存
                    for node, embedding in zip(valid_nodes, embeddings, strict=True):
                        node.embedding = embedding
                        embedded_nodes.append(node)

                        # 更新缓存
                        if self.enable_cache and self.cache:
                            text_str = str(getattr(node, "text", ""))
                            self.cache.set(text_str, embedding)

                    # 处理无效节点(空文本)
                    for node in nodes_to_embed:
                        if node not in valid_nodes:
                            embedded_nodes.append(node)

                logger.info(
                    "异步批量生成嵌入向量: 节点数=%s, 缓存命中=%s, 新生成=%s",
                    len(nodes),
                    len(nodes) - len(nodes_to_embed),
                    len(nodes_to_embed),
                )
            except Exception as exc:
                error_msg = f"异步批量嵌入生成失败: {exc}"
                logger.error(error_msg, exc_info=True)
                raise EmbeddingError(error_msg) from exc

        return embedded_nodes

    def clear_cache(self) -> None:
        """清空嵌入缓存"""
        if self.cache:
            self.cache.clear()
            logger.info("嵌入缓存已清空")

    def get_cache_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息字典, 包含缓存大小等信息
        """
        if not self.cache:
            return {"enabled": False}

        return {
            "enabled": True,
            "size": self.cache.size(),
            "max_size": self.cache.max_size,
        }

