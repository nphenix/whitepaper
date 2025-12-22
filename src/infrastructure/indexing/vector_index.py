# 生成命令: /speckit.implement T046
# 生成时间: 2025-12-19
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
向量索引构建器实现 (T046)

该模块实现向量索引构建功能，使用 LlamaIndex 的 VectorStoreIndex 和 ChromaVectorStore，
集成 T013 的 Chroma 适配器，支持索引构建、更新、删除、查询等功能。

设计目标:
- 使用 ``llama_index.core.VectorStoreIndex`` 和 ``llama_index.vector_stores.chroma.ChromaVectorStore``
- 与 T013 实现的 Chroma 适配器集成，使用现有 Chroma 连接和集合管理
- 利用 T013 的 Chroma 适配器实现持久化存储，支持本地和远程 Chroma 服务器
- 使用 ``VectorStoreIndex.from_nodes()`` 或 ``from_documents()`` 构建索引
- 使用 ``StorageContext.from_defaults()`` 配置存储上下文
- 支持元数据过滤和结构化查询（章节路径、文档层级等）
- 必须从 T009 创建的 llm_service 获取 Embedding 模型实例（阿里百炼 text-embedding-v4）
- 实现索引更新、删除、查询等完整功能
- 实现完善的错误处理和日志记录
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from src.infrastructure.indexing.embedding_generator import EmbeddingGenerator
from src.infrastructure.storage.chroma.connection import (
    ChromaConnectionManager,
    get_connection_manager,
)
from src.shared.exceptions.storage_exceptions import ChromaError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.core.schema import BaseNode, Document, NodeWithScore, QueryBundle
    from llama_index.core.vector_stores import (
        MetadataFilter,
        MetadataFilters,
        VectorStoreQuery,
        VectorStoreQueryResult,
    )
    from llama_index.vector_stores.chroma import ChromaVectorStore

    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 llama-index 时触发
    logger.warning(
        "LlamaIndex not available, vector index builder will be disabled"
    )
    VectorStoreIndex = Any  # type: ignore[assignment, misc]
    ChromaVectorStore = Any  # type: ignore[assignment, misc]
    StorageContext = Any  # type: ignore[assignment, misc]
    BaseNode = Any  # type: ignore[assignment, misc]
    Document = Any  # type: ignore[assignment, misc]
    NodeWithScore = Any  # type: ignore[assignment, misc]
    QueryBundle = Any  # type: ignore[assignment, misc]
    VectorStoreQuery = Any  # type: ignore[assignment, misc]
    VectorStoreQueryResult = Any  # type: ignore[assignment, misc]
    MetadataFilter = Any  # type: ignore[assignment, misc]
    MetadataFilters = Any  # type: ignore[assignment, misc]
    LLAMA_INDEX_AVAILABLE = False


class VectorIndexError(Exception):
    """向量索引异常基类"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 简单字符串表示
        return f"向量索引错误: {self.message}"


class VectorIndexBuilder:
    """
    向量索引构建器

    使用 LlamaIndex 的 VectorStoreIndex 和 ChromaVectorStore 构建向量索引，
    集成 T013 的 Chroma 适配器，支持索引构建、更新、删除、查询等功能。

    典型用法:
        >>> builder = VectorIndexBuilder(collection_name="documents")
        >>> nodes = [TextNode(text="示例文本", metadata={"section_path": "1.2"})]
        >>> index = builder.build_index(nodes)
        >>> results = builder.query(query="查询文本", top_k=5)
    """

    def __init__(
        self,
        collection_name: str | None = None,
        connection_manager: ChromaConnectionManager | None = None,
        embedding_generator: EmbeddingGenerator | None = None,
    ) -> None:
        """
        初始化向量索引构建器

        Args:
            collection_name: 集合名称，如果为 None 则使用默认集合
            connection_manager: Chroma 连接管理器，如果为 None 则使用全局实例
            embedding_generator: 嵌入生成器，如果为 None 则创建新实例

        Raises:
            ImportError: 如果 LlamaIndex 未安装
            VectorIndexError: 如果初始化失败
        """
        if not LLAMA_INDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not available. Please install llama-index package to "
                "use VectorIndexBuilder."
            )

        self.collection_name = collection_name or "whitepaper_documents"
        self.connection_manager = connection_manager or get_connection_manager()
        self.embedding_generator = embedding_generator or EmbeddingGenerator()

        # 初始化向量存储和索引
        self._vector_store: ChromaVectorStore | None = None
        self._index: VectorStoreIndex | None = None

        logger.info(
            "初始化 VectorIndexBuilder: collection_name=%s",
            self.collection_name,
        )

    def _get_vector_store(self) -> ChromaVectorStore:
        """
        获取或创建 ChromaVectorStore 实例

        使用连接管理器的配置创建 Chroma 客户端和集合，然后创建 ChromaVectorStore。

        Returns:
            ChromaVectorStore 实例

        Raises:
            VectorIndexError: 如果创建向量存储失败
        """
        if self._vector_store is None:
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings

                # 从连接管理器获取配置信息
                connection_info = self.connection_manager.get_connection_info()

                # 创建 Chroma 设置
                settings = ChromaSettings(
                    allow_reset=True,
                    anonymized_telemetry=False,
                )

                # 配置持久化目录
                if connection_info.get("persist_directory"):
                    settings.persist_directory = connection_info["persist_directory"]
                    settings.is_persistent = True
                else:
                    settings.is_persistent = False

                # 创建 Chroma 客户端
                if connection_info.get("host") and connection_info.get("port"):
                    # 远程连接
                    client = chromadb.HttpClient(
                        host=connection_info["host"],
                        port=connection_info["port"],
                        ssl=connection_info.get("ssl", False),
                        settings=settings,
                    )
                else:
                    # 本地连接
                    db_path = connection_info.get("db_path", "./storage/chroma")
                    client = chromadb.PersistentClient(
                        path=str(db_path),
                        settings=settings,
                    )

                # 获取或创建集合
                try:
                    collection = client.get_collection(name=self.collection_name)
                    logger.debug("获取现有集合: %s", self.collection_name)
                except Exception:
                    # 集合不存在，创建新集合
                    collection = client.create_collection(name=self.collection_name)
                    logger.debug("创建新集合: %s", self.collection_name)

                # 创建 ChromaVectorStore
                self._vector_store = ChromaVectorStore(
                    chroma_collection=collection,
                )

                logger.debug(
                    "创建 ChromaVectorStore: collection_name=%s",
                    self.collection_name,
                )

            except Exception as exc:
                error_msg = f"创建 ChromaVectorStore 失败: {exc}"
                logger.error(error_msg, exc_info=True)
                raise VectorIndexError(error_msg) from exc

        return self._vector_store

    def _clean_nodes_for_serialization(self, nodes: list[BaseNode]) -> list[BaseNode]:
        """
        清理节点元数据中的不可序列化对象（如 MagicMock）和复杂类型

        在测试环境中，节点元数据可能包含 MagicMock 对象，这些对象无法被 JSON 序列化。
        同时，LlamaIndex的ChromaVectorStore要求metadata值必须是基本类型（str, int, float, None）。
        此方法会清理这些对象，确保元数据可以正常序列化。

        Args:
            nodes: 原始节点列表

        Returns:
            清理后的节点列表
        """
        import json
        from unittest.mock import MagicMock

        cleaned_nodes: list[BaseNode] = []

        for node in nodes:
            # 创建节点副本以避免修改原始节点
            if hasattr(node, "metadata") and node.metadata:
                cleaned_metadata: dict[str, Any] = {}
                metadata_changed = False  # 跟踪是否有任何值被转换

                for key, value in node.metadata.items():
                    # 跳过 MagicMock 对象
                    if isinstance(value, MagicMock):
                        logger.debug(
                            "跳过不可序列化的 MagicMock 对象: key=%s, node_id=%s",
                            key,
                            getattr(node, "node_id", "unknown"),
                        )
                        continue

                    # LlamaIndex要求metadata值必须是str, int, float, None
                    # 处理复杂类型：字典、列表等
                    if isinstance(value, (dict, list)):
                        # 将复杂类型转换为JSON字符串
                        try:
                            cleaned_metadata[key] = json.dumps(value, ensure_ascii=False)
                            metadata_changed = True  # 标记为已更改
                            logger.debug(
                                "将复杂类型转换为JSON字符串: key=%s, type=%s, node_id=%s",
                                key,
                                type(value).__name__,
                                getattr(node, "node_id", "unknown"),
                            )
                        except (TypeError, ValueError) as e:
                            # 如果无法序列化，跳过该键值对
                            logger.debug(
                                "跳过不可序列化的元数据: key=%s, type=%s, error=%s, node_id=%s",
                                key,
                                type(value).__name__,
                                str(e),
                                getattr(node, "node_id", "unknown"),
                            )
                            continue
                    elif isinstance(value, (str, int, float)) or value is None:
                        # 基本类型，直接保留
                        cleaned_metadata[key] = value
                    elif isinstance(value, bool):
                        # 布尔值转换为字符串（LlamaIndex可能不支持bool）
                        cleaned_metadata[key] = str(value)
                        metadata_changed = True  # 标记为已更改
                    else:
                        # 其他类型尝试转换为字符串
                        try:
                            cleaned_metadata[key] = str(value)
                            metadata_changed = True  # 标记为已更改
                            logger.debug(
                                "将类型转换为字符串: key=%s, type=%s, node_id=%s",
                                key,
                                type(value).__name__,
                                getattr(node, "node_id", "unknown"),
                            )
                        except Exception:
                            # 如果转换失败，跳过该键值对
                            logger.debug(
                                "跳过无法转换的元数据: key=%s, type=%s, node_id=%s",
                                key,
                                type(value).__name__,
                                getattr(node, "node_id", "unknown"),
                            )
                            continue

                # 如果元数据被清理或更改，创建新节点
                if metadata_changed or len(cleaned_metadata) != len(node.metadata):
                    # 创建新节点，保留原始节点的所有属性
                    from llama_index.core.schema import TextNode

                    cleaned_node = TextNode(
                        text=getattr(node, "text", ""),
                        id_=getattr(node, "node_id", None) or getattr(node, "id_", None),
                        embedding=getattr(node, "embedding", None),
                        metadata=cleaned_metadata,
                    )
                    cleaned_nodes.append(cleaned_node)
                else:
                    cleaned_nodes.append(node)
            else:
                cleaned_nodes.append(node)

        return cleaned_nodes

    def _get_storage_context(self) -> StorageContext:
        """
        获取存储上下文

        Returns:
            StorageContext 实例

        Raises:
            VectorIndexError: 如果创建存储上下文失败
        """
        try:
            vector_store = self._get_vector_store()
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            logger.debug("创建 StorageContext: collection_name=%s", self.collection_name)
            return storage_context

        except Exception as exc:
            error_msg = f"创建 StorageContext 失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise VectorIndexError(error_msg) from exc

    def build_index(
        self,
        nodes: list[BaseNode] | None = None,
        documents: list[Document] | None = None,
        show_progress: bool = False,
    ) -> VectorStoreIndex:
        """
        构建向量索引

        从节点列表或文档列表构建向量索引。如果节点没有嵌入向量，会自动生成。

        Args:
            nodes: LlamaIndex Node 列表，如果为 None 则使用 documents
            documents: LlamaIndex Document 列表，如果为 None 则使用 nodes
            show_progress: 是否显示进度

        Returns:
            VectorStoreIndex 实例

        Raises:
            VectorIndexError: 如果构建索引失败
        """
        if not nodes and not documents:
            error_msg = "必须提供 nodes 或 documents"
            raise ValueError(error_msg)

        if nodes and documents:
            error_msg = "不能同时提供 nodes 和 documents"
            raise ValueError(error_msg)

        try:
            # 如果提供了 documents，转换为 nodes
            if documents:
                # 从 documents 创建 nodes（LlamaIndex 会自动处理）
                nodes = None  # type: ignore[assignment]

            # 确保节点有嵌入向量
            if nodes:
                # 检查节点是否已有嵌入向量
                nodes_without_embedding = [
                    node
                    for node in nodes
                    if not hasattr(node, "embedding") or node.embedding is None
                ]

                if nodes_without_embedding:
                    logger.info(
                        "为 %s 个节点生成嵌入向量",
                        len(nodes_without_embedding),
                    )
                    # 使用嵌入生成器为节点生成嵌入向量
                    nodes = self.embedding_generator.generate_embeddings(nodes)

            # 获取存储上下文
            storage_context = self._get_storage_context()

            # 构建索引
            if nodes:
                # 在 LlamaIndex 0.14.6 中，使用构造函数直接创建索引
                # 注意：需要先清理节点元数据中的不可序列化对象（如 MagicMock）
                cleaned_nodes = self._clean_nodes_for_serialization(nodes)
                self._index = VectorStoreIndex(
                    nodes=cleaned_nodes,
                    storage_context=storage_context,
                    embed_model=self.embedding_generator.embedding_model,
                    show_progress=show_progress,
                )
            else:
                # 使用 documents 构建索引
                self._index = VectorStoreIndex.from_documents(
                    documents=documents,  # type: ignore[arg-type]
                    storage_context=storage_context,
                    embed_model=self.embedding_generator.embedding_model,
                    show_progress=show_progress,
                )

            logger.info(
                "向量索引构建完成: collection_name=%s, nodes_count=%s",
                self.collection_name,
                len(nodes) if nodes else len(documents) if documents else 0,
            )

            return self._index

        except Exception as exc:
            error_msg = f"构建向量索引失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise VectorIndexError(error_msg) from exc

    def get_index(self) -> VectorStoreIndex:
        """
        获取向量索引实例

        Returns:
            VectorStoreIndex 实例

        Raises:
            VectorIndexError: 如果索引不存在
        """
        if self._index is None:
            # 尝试从存储中加载索引
            try:
                # 在 LlamaIndex 0.14.6 中，from_vector_store 不需要 storage_context 参数
                self._index = VectorStoreIndex.from_vector_store(
                    vector_store=self._get_vector_store(),
                    embed_model=self.embedding_generator.embedding_model,
                )

                logger.info("从存储加载向量索引: collection_name=%s", self.collection_name)

            except Exception as exc:
                error_msg = f"加载向量索引失败: {exc}"
                logger.error(error_msg, exc_info=True)
                raise VectorIndexError(error_msg) from exc

        return self._index

    def insert(
        self,
        nodes: list[BaseNode] | None = None,
        documents: list[Document] | None = None,
    ) -> list[str]:
        """
        向索引中插入节点或文档

        Args:
            nodes: LlamaIndex Node 列表
            documents: LlamaIndex Document 列表

        Returns:
            插入的节点 ID 列表

        Raises:
            VectorIndexError: 如果插入失败
        """
        if not nodes and not documents:
            error_msg = "必须提供 nodes 或 documents"
            raise ValueError(error_msg)

        if nodes and documents:
            error_msg = "不能同时提供 nodes 和 documents"
            raise ValueError(error_msg)

        try:
            index = self.get_index()

            # 确保节点有嵌入向量
            if nodes:
                # 清理节点元数据中的不可序列化对象
                nodes = self._clean_nodes_for_serialization(nodes)

                nodes_without_embedding = [
                    node
                    for node in nodes
                    if not hasattr(node, "embedding") or node.embedding is None
                ]

                if nodes_without_embedding:
                    logger.info(
                        "为 %s 个节点生成嵌入向量",
                        len(nodes_without_embedding),
                    )
                    nodes = self.embedding_generator.generate_embeddings(nodes)

                # 插入节点
                index.insert_nodes(nodes)  # type: ignore[arg-type]
                node_ids = [node.node_id for node in nodes]  # type: ignore[union-attr]

                logger.info(
                    "插入节点成功: collection_name=%s, count=%s",
                    self.collection_name,
                    len(nodes),
                )

                return node_ids

            else:
                # 插入文档
                index.insert(documents=documents)  # type: ignore[arg-type]
                # 文档插入后无法直接获取 ID，返回空列表
                logger.info(
                    "插入文档成功: collection_name=%s, count=%s",
                    self.collection_name,
                    len(documents) if documents else 0,
                )

                return []

        except Exception as exc:
            error_msg = f"插入节点或文档失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise VectorIndexError(error_msg) from exc

    def delete(
        self,
        node_ids: list[str] | None = None,
        ref_doc_ids: list[str] | None = None,
        delete_from_docstore: bool = True,
    ) -> None:
        """
        从索引中删除节点或文档

        Args:
            node_ids: 节点 ID 列表
            ref_doc_ids: 文档引用 ID 列表
            delete_from_docstore: 是否从文档存储中删除

        Raises:
            VectorIndexError: 如果删除失败
        """
        if not node_ids and not ref_doc_ids:
            error_msg = "必须提供 node_ids 或 ref_doc_ids"
            raise ValueError(error_msg)

        try:
            index = self.get_index()

            if node_ids:
                index.delete_nodes(node_ids=node_ids, delete_from_docstore=delete_from_docstore)
                logger.info(
                    "删除节点成功: collection_name=%s, count=%s",
                    self.collection_name,
                    len(node_ids),
                )

            if ref_doc_ids:
                index.delete_ref_doc(ref_doc_ids=ref_doc_ids, delete_from_docstore=delete_from_docstore)
                logger.info(
                    "删除文档引用成功: collection_name=%s, count=%s",
                    self.collection_name,
                    len(ref_doc_ids),
                )

        except Exception as exc:
            error_msg = f"删除节点或文档失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise VectorIndexError(error_msg) from exc

    def query(
        self,
        query_str: str | None = None,
        query_embedding: list[float] | None = None,
        top_k: int = 10,
        filters: MetadataFilters | None = None,
        similarity_top_k: int | None = None,
    ) -> list[NodeWithScore]:
        """
        查询向量索引

        Args:
            query_str: 查询文本
            query_embedding: 查询向量（如果提供则直接使用，否则从 query_str 生成）
            top_k: 返回结果数量
            filters: 元数据过滤器
            similarity_top_k: 相似度 top k（如果为 None 则使用 top_k）

        Returns:
            查询结果列表（NodeWithScore 对象）

        Raises:
            VectorIndexError: 如果查询失败
        """
        if not query_str and not query_embedding:
            error_msg = "必须提供 query_str 或 query_embedding"
            raise ValueError(error_msg)

        try:
            index = self.get_index()

            # 如果提供了查询文本但没有查询向量，生成查询向量
            if query_str and not query_embedding:
                query_embedding = self.embedding_generator.embedding_model.get_query_embedding(
                    query_str
                )

            # 构建查询
            query_bundle = QueryBundle(query_str=query_str, embedding=query_embedding)

            # 执行查询
            similarity_top_k = similarity_top_k or top_k
            results = index.as_retriever(
                similarity_top_k=similarity_top_k,
                filters=filters,
            ).retrieve(query_bundle)

            logger.info(
                "查询向量索引成功: collection_name=%s, query=%s, results_count=%s",
                self.collection_name,
                query_str[:50] if query_str else "embedding",
                len(results),
            )

            return results

        except Exception as exc:
            error_msg = f"查询向量索引失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise VectorIndexError(error_msg) from exc

    def query_with_metadata_filter(
        self,
        query_str: str,
        section_path: str | None = None,
        document_id: str | UUID | None = None,
        top_k: int = 10,
    ) -> list[NodeWithScore]:
        """
        使用元数据过滤器查询向量索引

        支持按章节路径、文档 ID 等元数据进行过滤查询。

        Args:
            query_str: 查询文本
            section_path: 章节路径（如 "1.2.3"）
            document_id: 文档 ID
            top_k: 返回结果数量

        Returns:
            查询结果列表（NodeWithScore 对象）

        Raises:
            VectorIndexError: 如果查询失败
        """
        try:
            # 构建元数据过滤器
            filters_list: list[MetadataFilter] = []

            if section_path:
                filters_list.append(
                    MetadataFilter(key="section_path", value=section_path)
                )

            if document_id:
                # 将 UUID 转换为字符串
                doc_id_str = str(document_id) if isinstance(document_id, UUID) else document_id
                filters_list.append(
                    MetadataFilter(key="document_id", value=doc_id_str)
                )

            filters = MetadataFilters(filters=filters_list) if filters_list else None

            # 执行查询
            return self.query(
                query_str=query_str,
                top_k=top_k,
                filters=filters,
            )

        except Exception as exc:
            error_msg = f"使用元数据过滤器查询失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise VectorIndexError(error_msg) from exc

    def get_stats(self) -> dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            统计信息字典
        """
        try:
            # 使用连接管理器获取集合信息
            collection_info = self.connection_manager.get_collection_info(
                self.collection_name
            )

            stats = {
                "collection_name": self.collection_name,
                "vector_count": collection_info.get("count", 0),
                "is_persistent": collection_info.get("is_persistent", False),
                "persist_directory": collection_info.get("persist_directory"),
                "embedding_function": collection_info.get("embedding_function"),
            }

            logger.debug("获取索引统计信息: %s", stats)
            return stats

        except Exception as exc:
            error_msg = f"获取索引统计信息失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise VectorIndexError(error_msg) from exc

