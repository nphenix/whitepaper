# 生成命令: T058 - 添加错误处理和日志记录
# 生成时间: 2025-12-21
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
知识库服务

提供知识库的创建,更新,查询和删除功能,包括文档解析,索引构建和检索功能.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.application.services.indexing_progress_service import IndexingProgressService
from src.domain.document.document import Document, DocumentFormat
from src.domain.document.preprocessed_document import (
    CleaningLevel,
    PreprocessedDocument,
)
from src.domain.knowledge_base.document_chunk import DocumentChunk
from src.domain.knowledge_base.knowledge_entry import KnowledgeEntry
from src.shared.utils.logging import get_logger

# 类型检查时导入，避免循环依赖
if TYPE_CHECKING:
    from src.shared.config.llm_service import LLMService

# 索引构建器导入（可选依赖）
try:
    from src.infrastructure.indexing.bm25_index import BM25IndexBuilder
    from src.infrastructure.indexing.knowledge_graph import KnowledgeGraphBuilder
    from src.infrastructure.indexing.metadata_index import MetadataIndexBuilder
    from src.infrastructure.indexing.vector_index import VectorIndexBuilder
    INDEX_BUILDERS_AVAILABLE = True
except ImportError:
    INDEX_BUILDERS_AVAILABLE = False
    BM25IndexBuilder = None  # type: ignore[assignment, misc]
    KnowledgeGraphBuilder = None  # type: ignore[assignment, misc]
    MetadataIndexBuilder = None  # type: ignore[assignment, misc]
    VectorIndexBuilder = None  # type: ignore[assignment, misc]

# LlamaIndex导入（用于节点转换）
try:
    from llama_index.core.schema import Node, TextNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False
    Node = None  # type: ignore[assignment, misc]
    TextNode = None  # type: ignore[assignment, misc]

logger = get_logger(__name__)


# 自定义异常类
class KnowledgeBaseServiceError(Exception):
    """知识库服务基础异常"""
    def __init__(self, message: str, error_code: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}


class DocumentLoadError(KnowledgeBaseServiceError):
    """文档加载错误"""
    def __init__(self, message: str, document_path: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, "DOCUMENT_LOAD_ERROR", details)
        self.document_path = document_path


class DocumentParseError(KnowledgeBaseServiceError):
    """文档解析错误"""
    def __init__(self, message: str, document_id: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, "DOCUMENT_PARSE_ERROR", details)
        self.document_id = document_id


class IndexBuildError(KnowledgeBaseServiceError):
    """索引构建错误"""
    def __init__(self, message: str, index_type: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, "INDEX_BUILD_ERROR", details)
        self.index_type = index_type


class QueryError(KnowledgeBaseServiceError):
    """查询错误"""
    def __init__(self, message: str, query: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, "QUERY_ERROR", details)
        self.query = query


class ResourceError(KnowledgeBaseServiceError):
    """资源错误"""
    def __init__(self, message: str, resource_type: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, "RESOURCE_ERROR", details)
        self.resource_type = resource_type


class ConfigurationError(KnowledgeBaseServiceError):
    """配置错误"""
    def __init__(self, message: str, config_key: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, "CONFIGURATION_ERROR", details)
        self.config_key = config_key


class ConcurrencyError(KnowledgeBaseServiceError):
    """并发错误"""
    def __init__(self, message: str, operation_id: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, "CONCURRENCY_ERROR", details)
        self.operation_id = operation_id


class KnowledgeBaseLogger:
    """知识库服务专用日志记录器"""

    # LogRecord保留字段列表
    LOG_RECORD_RESERVED_FIELDS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message"
    }

    @staticmethod
    def log_operation_start(
        operation_id: str,
        operation_type: str,
        knowledge_base_id: str,
        **kwargs
    ) -> None:
        """记录操作开始"""
        # 过滤掉可能与LogRecord冲突的键
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in KnowledgeBaseLogger.LOG_RECORD_RESERVED_FIELDS}

        logger.info(
            "操作开始",
            extra={
                "operation_id": operation_id,
                "operation_type": operation_type,
                "knowledge_base_id": knowledge_base_id,
                "status": "started",
                **filtered_kwargs
            }
        )

    @staticmethod
    def log_operation_success(
        operation_id: str,
        operation_type: str,
        knowledge_base_id: str,
        duration_ms: int,
        **kwargs
    ) -> None:
        """记录操作成功"""
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in KnowledgeBaseLogger.LOG_RECORD_RESERVED_FIELDS}

        logger.info(
            "操作成功",
            extra={
                "operation_id": operation_id,
                "operation_type": operation_type,
                "knowledge_base_id": knowledge_base_id,
                "status": "success",
                "duration_ms": duration_ms,
                **filtered_kwargs
            }
        )

    @staticmethod
    def log_operation_error(
        operation_id: str,
        operation_type: str,
        knowledge_base_id: str,
        error: Exception,
        duration_ms: int,
        **kwargs
    ) -> None:
        """记录操作错误"""
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in KnowledgeBaseLogger.LOG_RECORD_RESERVED_FIELDS}

        logger.error(
            f"操作失败: {error!s}",
            extra={
                "operation_id": operation_id,
                "operation_type": operation_type,
                "knowledge_base_id": knowledge_base_id,
                "status": "error",
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                "duration_ms": duration_ms,
                **filtered_kwargs
            }
        )

    @staticmethod
    def log_performance_metrics(
        operation_type: str,
        knowledge_base_id: str,
        metrics: dict[str, Any]
    ) -> None:
        """记录性能指标"""
        filtered_metrics = {k: v for k, v in metrics.items() if k not in KnowledgeBaseLogger.LOG_RECORD_RESERVED_FIELDS}

        logger.info(
            "性能指标",
            extra={
                "operation_type": operation_type,
                "knowledge_base_id": knowledge_base_id,
                "metrics": filtered_metrics
            }
        )

    @staticmethod
    def log_progress_update(
        operation_id: str,
        knowledge_base_id: str,
        current: int,
        total: int,
        stage: str,
        **kwargs
    ) -> None:
        """记录进度更新"""
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in KnowledgeBaseLogger.LOG_RECORD_RESERVED_FIELDS}

        logger.info(
            f"进度更新: {current}/{total}",
            extra={
                "operation_id": operation_id,
                "knowledge_base_id": knowledge_base_id,
                "progress_current": current,
                "progress_total": total,
                "progress_percentage": round((current / total) * 100, 2) if total > 0 else 0,
                "stage": stage,
                **filtered_kwargs
            }
        )

    @staticmethod
    def debug(message: str, *args, **kwargs) -> None:
        """记录调试日志

        Args:
            message: 调试消息
            *args: 位置参数，用于格式化消息
            **kwargs: 额外的上下文参数
        """
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in KnowledgeBaseLogger.LOG_RECORD_RESERVED_FIELDS}

        logger.debug(
            message,
            *args,
            extra=filtered_kwargs
        )

    @staticmethod
    def info(message: str, *args, **kwargs) -> None:
        """记录信息日志

        Args:
            message: 信息消息
            *args: 位置参数，用于格式化消息
            **kwargs: 额外的上下文参数
        """
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in KnowledgeBaseLogger.LOG_RECORD_RESERVED_FIELDS}

        logger.info(
            message,
            *args,
            extra=filtered_kwargs
        )

    @staticmethod
    def warning(message: str, *args, **kwargs) -> None:
        """记录警告日志

        Args:
            message: 警告消息
            *args: 位置参数，用于格式化消息
            **kwargs: 额外的上下文参数
        """
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in KnowledgeBaseLogger.LOG_RECORD_RESERVED_FIELDS}

        logger.warning(
            message,
            *args,
            extra=filtered_kwargs
        )


class KnowledgeBaseService:
    """知识库服务"""

    def __init__(
        self,
        progress_service: IndexingProgressService,
        vector_index_builder: VectorIndexBuilder | None = None,
        bm25_index_builder: BM25IndexBuilder | None = None,
        metadata_index_builder: MetadataIndexBuilder | None = None,
        knowledge_graph_builder: KnowledgeGraphBuilder | None = None,
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_metadata: bool = True,
        enable_graph: bool = False,
        llm_service: "LLMService | None" = None,
    ):
        """
        初始化知识库服务

        Args:
            progress_service: 索引进度服务
            vector_index_builder: 向量索引构建器（可选）
            bm25_index_builder: BM25索引构建器（可选）
            metadata_index_builder: 元数据索引构建器（可选）
            knowledge_graph_builder: 知识图谱构建器（可选）
            enable_vector: 是否启用向量索引（默认True）
            enable_bm25: 是否启用BM25索引（默认True）
            enable_metadata: 是否启用元数据索引（默认True）
            enable_graph: 是否启用知识图谱索引（默认False）
            llm_service: LLM服务实例（可选，用于Rerank模型）
        """
        self.progress_service = progress_service
        self._knowledge_bases: dict[str, dict[str, Any]] = {}
        self._logger = KnowledgeBaseLogger()
        
        # 索引构建器（依赖注入）
        self.vector_index_builder = vector_index_builder
        self.bm25_index_builder = bm25_index_builder
        self.metadata_index_builder = metadata_index_builder
        self.knowledge_graph_builder = knowledge_graph_builder
        
        # LLM服务（依赖注入，用于Rerank模型）
        self.llm_service = llm_service
        
        # 索引启用配置
        self.enable_vector = enable_vector
        self.enable_bm25 = enable_bm25
        self.enable_metadata = enable_metadata
        self.enable_graph = enable_graph
        
        logger.info(
            "初始化KnowledgeBaseService: vector=%s, bm25=%s, metadata=%s, graph=%s, llm_service=%s",
            self.enable_vector and self.vector_index_builder is not None,
            self.enable_bm25 and self.bm25_index_builder is not None,
            self.enable_metadata and self.metadata_index_builder is not None,
            self.enable_graph and self.knowledge_graph_builder is not None,
            self.llm_service is not None,
        )

    def create_knowledge_base(
        self,
        knowledge_base_id: str,
        documents: list[Document],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        **kwargs
    ) -> dict[str, Any]:
        """
        创建知识库

        Args:
            knowledge_base_id: 知识库ID
            documents: 文档列表
            chunk_size: 文档块大小
            chunk_overlap: 文档块重叠大小
            **kwargs: 其他参数

        Returns:
            创建的知识库信息

        Raises:
            KnowledgeBaseServiceError: 创建失败时抛出
        """
        operation_id = str(uuid.uuid4())
        start_time = datetime.now()

        self._logger.log_operation_start(
            operation_id=operation_id,
            operation_type="create_knowledge_base",
            knowledge_base_id=knowledge_base_id,
            document_count=len(documents),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

        try:
            # 检查知识库是否已存在
            if knowledge_base_id in self._knowledge_bases:
                msg = f"知识库已存在: {knowledge_base_id}"
                raise ConcurrencyError(
                    msg,
                    operation_id=operation_id
                )

            # 加载文档
            documents = self._load_documents(documents, operation_id, knowledge_base_id)

            # 解析文档
            preprocessed_documents = self._parse_documents(documents, operation_id, knowledge_base_id)

            # 分块文档
            chunks = self._chunk_documents(preprocessed_documents, chunk_size, chunk_overlap, operation_id, knowledge_base_id)

            # 构建索引
            indexes = self._build_indexes(chunks, operation_id, knowledge_base_id)

            # 创建知识库条目
            knowledge_entries = self._create_knowledge_entries(chunks, operation_id, knowledge_base_id)

            # 保存知识库
            self._knowledge_bases[knowledge_base_id] = {
                "id": knowledge_base_id,
                "documents": documents,
                "preprocessed_documents": preprocessed_documents,
                "chunks": chunks,
                "indexes": indexes,
                "knowledge_entries": knowledge_entries,
                "created_at": start_time,
                "updated_at": start_time
            }

            # 记录成功
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._logger.log_operation_success(
                operation_id=operation_id,
                operation_type="create_knowledge_base",
                knowledge_base_id=knowledge_base_id,
                duration_ms=duration_ms,
                document_count=len(documents),
                chunk_count=len(chunks),
                index_count=len(indexes)
            )

            return {
                "id": knowledge_base_id,
                "document_count": len(documents),
                "chunk_count": len(chunks),
                "index_count": len(indexes),
                "created_at": start_time
            }

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._logger.log_operation_error(
                operation_id=operation_id,
                operation_type="create_knowledge_base",
                knowledge_base_id=knowledge_base_id,
                error=e,
                duration_ms=duration_ms
            )
            raise

    def update_knowledge_base(
        self,
        knowledge_base_id: str,
        new_documents: list[Document] | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        更新知识库

        Args:
            knowledge_base_id: 知识库ID
            new_documents: 新增文档列表
            **kwargs: 其他参数

        Returns:
            更新后的知识库信息

        Raises:
            KnowledgeBaseServiceError: 更新失败时抛出
        """
        operation_id = str(uuid.uuid4())
        start_time = datetime.now()

        self._logger.log_operation_start(
            operation_id=operation_id,
            operation_type="update_knowledge_base",
            knowledge_base_id=knowledge_base_id,
            new_document_count=len(new_documents) if new_documents else 0
        )

        try:
            # 检查知识库是否存在
            if knowledge_base_id not in self._knowledge_bases:
                msg = f"知识库不存在: {knowledge_base_id}"
                raise ResourceError(
                    msg,
                    resource_type="knowledge_base"
                )

            knowledge_base = self._knowledge_bases[knowledge_base_id]

            # 如果有新文档,则处理新文档
            if new_documents:
                # 加载新文档
                loaded_documents = self._load_documents(new_documents, operation_id, knowledge_base_id)

                # 解析新文档
                preprocessed_documents = self._parse_documents(loaded_documents, operation_id, knowledge_base_id)

                # 分块新文档
                chunk_size = kwargs.get("chunk_size", 1000)
                chunk_overlap = kwargs.get("chunk_overlap", 200)
                new_chunks = self._chunk_documents(preprocessed_documents, chunk_size, chunk_overlap, operation_id, knowledge_base_id)

                # 更新索引
                self._update_indexes(knowledge_base["chunks"] + new_chunks, operation_id, knowledge_base_id)

                # 创建知识库条目
                new_knowledge_entries = self._create_knowledge_entries(new_chunks, operation_id, knowledge_base_id)

                # 更新知识库
                knowledge_base["documents"].extend(loaded_documents)
                knowledge_base["preprocessed_documents"].extend(preprocessed_documents)
                knowledge_base["chunks"].extend(new_chunks)
                knowledge_base["knowledge_entries"].extend(new_knowledge_entries)
                knowledge_base["updated_at"] = datetime.now()

            # 记录成功
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._logger.log_operation_success(
                operation_id=operation_id,
                operation_type="update_knowledge_base",
                knowledge_base_id=knowledge_base_id,
                duration_ms=duration_ms,
                total_document_count=len(knowledge_base["documents"]),
                total_chunk_count=len(knowledge_base["chunks"])
            )

            return {
                "id": knowledge_base_id,
                "document_count": len(knowledge_base["documents"]),
                "chunk_count": len(knowledge_base["chunks"]),
                "updated_at": knowledge_base["updated_at"]
            }

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._logger.log_operation_error(
                operation_id=operation_id,
                operation_type="update_knowledge_base",
                knowledge_base_id=knowledge_base_id,
                error=e,
                duration_ms=duration_ms
            )
            raise

    def query(
        self,
        knowledge_base_id: str,
        query_text: str,
        top_k: int = 5,
        **kwargs
    ) -> list[dict[str, Any]]:
        """
        查询知识库

        Args:
            knowledge_base_id: 知识库ID
            query_text: 查询文本
            top_k: 返回结果数量
            **kwargs: 其他参数

        Returns:
            查询结果列表

        Raises:
            KnowledgeBaseServiceError: 查询失败时抛出
        """
        operation_id = str(uuid.uuid4())
        start_time = datetime.now()

        self._logger.log_operation_start(
            operation_id=operation_id,
            operation_type="query",
            knowledge_base_id=knowledge_base_id,
            query_text=query_text,
            top_k=top_k
        )

        try:
            # 检查知识库是否存在
            if knowledge_base_id not in self._knowledge_bases:
                msg = f"知识库不存在: {knowledge_base_id}"
                raise ResourceError(
                    msg,
                    resource_type="knowledge_base"
                )

            knowledge_base = self._knowledge_bases[knowledge_base_id]

            # 执行真实的检索查询（支持混合检索）
            # 根据最佳实践，保留完整内容以确保语义不被截断
            results = self._execute_hybrid_retrieval(
                knowledge_base=knowledge_base,
                query_text=query_text,
                top_k=top_k,
                **kwargs
            )

            # 记录成功
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._logger.log_operation_success(
                operation_id=operation_id,
                operation_type="query",
                knowledge_base_id=knowledge_base_id,
                duration_ms=duration_ms,
                result_count=len(results),
                query_text=query_text
            )

            return results

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._logger.log_operation_error(
                operation_id=operation_id,
                operation_type="query",
                knowledge_base_id=knowledge_base_id,
                error=e,
                duration_ms=duration_ms,
                query_text=query_text
            )
            raise

    def _execute_hybrid_retrieval(
        self,
        knowledge_base: dict[str, Any],
        query_text: str,
        top_k: int = 5,
        **kwargs
    ) -> list[dict[str, Any]]:
        """
        执行混合检索（遵循RAG最佳实践）

        根据最佳实践，实现混合检索策略：
        1. 向量检索：用于语义理解和泛化匹配
        2. BM25检索：用于精确关键词匹配
        3. 结果融合：结合两种检索结果，提升召回质量
        4. 保留完整内容：避免语义截断，确保生成时有足够的上下文

        Args:
            knowledge_base: 知识库数据
            query_text: 查询文本
            top_k: 返回结果数量
            **kwargs: 其他参数（如检索权重、评分阈值等）

        Returns:
            检索结果列表，每个结果包含完整内容
        """
        import math

        # 提取知识库组件
        chunks = knowledge_base["chunks"]
        indexes = knowledge_base.get("indexes", {})

        # 获取检索参数
        vector_weight = kwargs.get("vector_weight", 0.6)  # 向量检索权重
        bm25_weight = kwargs.get("bm25_weight", 0.4)      # BM25检索权重
        score_threshold = kwargs.get("score_threshold", 0.0)  # 评分阈值
        enable_rerank = kwargs.get("enable_rerank", True)      # 是否启用重排序

        # 如果没有构建索引或索引为空，使用简单的相似度计算作为后备
        if not indexes or not chunks:
            logger.warning("知识库没有构建索引，使用简单的相似度计算")
            return self._simple_similarity_retrieval(
                chunks=chunks,
                query_text=query_text,
                top_k=top_k
            )

        # 初始化检索结果容器
        all_results: dict[str, dict[str, Any]] = {}

        # 执行向量检索（如果启用）
        vector_index_data = indexes.get("vector_index")
        if vector_index_data and self.enable_vector:
            try:
                vector_results = self._vector_retrieval(
                    vector_index_data=vector_index_data,
                    chunks=chunks,
                    query_text=query_text,
                    top_k=top_k * 2  # 多检索一些用于后续融合
                )
                for result in vector_results:
                    chunk_id = str(result["chunk_id"])
                    if chunk_id not in all_results:
                        all_results[chunk_id] = result
                    else:
                        # 合并分数（加权平均）
                        existing = all_results[chunk_id]
                        existing["score"] = (
                            existing["score"] * vector_weight + result["score"] * vector_weight
                        )
                        existing["retrieval_methods"].append("vector")
            except Exception as e:
                logger.error("向量检索失败: %s", e, exc_info=True)

        # 执行BM25检索（如果启用）
        bm25_index_data = indexes.get("bm25_index")
        if bm25_index_data and self.enable_bm25:
            try:
                bm25_results = self._bm25_retrieval(
                    bm25_index_data=bm25_index_data,
                    chunks=chunks,
                    query_text=query_text,
                    top_k=top_k * 2  # 多检索一些用于后续融合
                )
                for result in bm25_results:
                    chunk_id = str(result["chunk_id"])
                    if chunk_id not in all_results:
                        all_results[chunk_id] = result
                    else:
                        # 合并分数（加权平均）
                        existing = all_results[chunk_id]
                        existing["score"] = (
                            existing["score"] * bm25_weight + result["score"] * bm25_weight
                        )
                        existing["retrieval_methods"].append("bm25")
            except Exception as e:
                logger.error("BM25检索失败: %s", e, exc_info=True)

        # 如果没有任何检索结果，使用简单的相似度计算
        if not all_results:
            logger.warning("混合检索没有返回结果，使用简单的相似度计算")
            return self._simple_similarity_retrieval(
                chunks=chunks,
                query_text=query_text,
                top_k=top_k
            )

        # 转换为列表并按分数排序
        results = list(all_results.values())
        results.sort(key=lambda x: x["score"], reverse=True)

        # 应用评分阈值过滤
        if score_threshold > 0:
            results = [r for r in results if r["score"] >= score_threshold]

        # 重排序（如果启用）
        if enable_rerank and len(results) > top_k:
            results = self._rerank_results(
                results=results[:top_k * 2],  # 取更多结果进行重排序
                query_text=query_text,
                top_k=top_k
            )

        # 返回最终结果（限制数量）
        final_results = results[:top_k]

        logger.info(
            "混合检索完成: 查询='%s', 检索到=%d, 返回=%d",
            query_text[:50],
            len(results),
            len(final_results)
        )

        return final_results

    def _vector_retrieval(
        self,
        vector_index_data: dict[str, Any],
        chunks: list,
        query_text: str,
        top_k: int = 10
    ) -> list[dict[str, Any]]:
        """
        执行向量检索

        Args:
            vector_index_data: 向量索引数据
            chunks: 文档块列表
            query_text: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        results = []
        vector_index = vector_index_data.get("index")

        if vector_index is None:
            logger.warning("向量索引为空")
            return results

        try:
            # 使用向量索引进行检索
            if hasattr(vector_index, "similarity_search"):
                # LlamaIndex向量索引
                search_results = vector_index.similarity_search(query_text, k=top_k)

                for rank, node in enumerate(search_results):
                    # 从node中提取信息
                    node_text = getattr(node, "text", "") or str(node)
                    node_id = getattr(node, "id_", "") or str(getattr(node, "id", ""))

                    # 找到对应的chunk
                    chunk = self._find_chunk_by_id(chunks, node_id)
                    if chunk:
                        # 计算相似度分数（LlamaIndex返回的是距离，需要转换）
                        score = 1.0 - (rank * 0.1)  # 简化的分数计算

                        results.append({
                            "chunk_id": chunk.id,
                            "content": chunk.content,  # 保留完整内容，不截断
                            "score": score,
                            "metadata": chunk.metadata,
                            "retrieval_methods": ["vector"],
                            "node_text": node_text[:100] if node_text else ""  # 预览用
                        })
            else:
                # 降级到简单的相似度计算
                logger.warning("向量索引不支持similarity_search，使用简单检索")
                results = self._simple_similarity_retrieval(chunks, query_text, top_k)

        except Exception as e:
            logger.error("向量检索执行失败: %s", e, exc_info=True)
            # 降级到简单的相似度计算
            results = self._simple_similarity_retrieval(chunks, query_text, top_k)

        return results

    def _bm25_retrieval(
        self,
        bm25_index_data: dict[str, Any],
        chunks: list,
        query_text: str,
        top_k: int = 10
    ) -> list[dict[str, Any]]:
        """
        执行BM25检索

        Args:
            bm25_index_data: BM25索引数据
            chunks: 文档块列表
            query_text: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        results = []
        bm25_index = bm25_index_data.get("builder")

        if bm25_index is None:
            logger.warning("BM25索引构建器为空")
            return results

        try:
            # 使用BM25索引进行检索
            if hasattr(bm25_index, "search"):
                # 自定义BM25索引
                search_results = bm25_index.search(query_text, top_k=top_k)

                for rank, (node_id, score) in enumerate(search_results):
                    # 找到对应的chunk
                    chunk = self._find_chunk_by_id(chunks, node_id)
                    if chunk:
                        results.append({
                            "chunk_id": chunk.id,
                            "content": chunk.content,  # 保留完整内容，不截断
                            "score": score,
                            "metadata": chunk.metadata,
                            "retrieval_methods": ["bm25"]
                        })
            elif hasattr(bm25_index, "search_with_scores"):
                # LlamaIndex BM25索引
                search_results = bm25_index.search_with_scores(query_text, k=top_k)

                for rank, (node, score) in enumerate(search_results):
                    node_text = getattr(node, "text", "") or str(node)
                    node_id = getattr(node, "id_", "") or str(getattr(node, "id", ""))

                    chunk = self._find_chunk_by_id(chunks, node_id)
                    if chunk:
                        results.append({
                            "chunk_id": chunk.id,
                            "content": chunk.content,  # 保留完整内容，不截断
                            "score": float(score),
                            "metadata": chunk.metadata,
                            "retrieval_methods": ["bm25"]
                        })
            else:
                # 降级到简单的BM25计算
                logger.warning("BM25索引不支持搜索方法，使用简单检索")
                results = self._simple_bm25_retrieval(chunks, query_text, top_k)

        except Exception as e:
            logger.error("BM25检索执行失败: %s", e, exc_info=True)
            # 降级到简单的BM25计算
            results = self._simple_bm25_retrieval(chunks, query_text, top_k)

        return results

    def _simple_similarity_retrieval(
        self,
        chunks: list,
        query_text: str,
        top_k: int = 5
    ) -> list[dict[str, Any]]:
        """
        简单的相似度检索（后备方案）

        使用字符级Jaccard相似度作为后备检索方法

        Args:
            chunks: 文档块列表
            query_text: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        if not chunks:
            return []

        # 计算查询文本的特征
        query_features = self._extract_text_features(query_text)

        results = []
        for i, chunk in enumerate(chunks):
            # 计算相似度分数
            chunk_features = self._extract_text_features(chunk.content)
            similarity = self._calculate_jaccard_similarity(query_features, chunk_features)

            results.append({
                "chunk_id": chunk.id,
                "content": chunk.content,  # 保留完整内容，不截断
                "score": similarity,
                "metadata": chunk.metadata,
                "retrieval_methods": ["simple_similarity"]
            })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]

    def _simple_bm25_retrieval(
        self,
        chunks: list,
        query_text: str,
        top_k: int = 10
    ) -> list[dict[str, Any]]:
        """
        简单的BM25检索（后备方案）

        使用词频和位置信息计算BM25分数

        Args:
            chunks: 文档块列表
            query_text: 查询文本
            top_k: 返回结果数量

        Returns:
            检索结果列表
        """
        import math

        if not chunks or not query_text.strip():
            return []

        # 分词
        query_terms = query_text.lower().split()
        if not query_terms:
            return []

        results = []
        total_docs = len(chunks)
        avg_doc_len = sum(len(chunk.content.split()) for chunk in chunks) / total_docs if total_docs > 0 else 1

        for chunk in chunks:
            doc_terms = chunk.content.lower().split()
            doc_len = len(doc_terms)

            if doc_len == 0:
                continue

            # 计算BM25分数（简化版）
            score = 0.0
            for term in query_terms:
                term_freq = doc_terms.count(term)
                if term_freq > 0:
                    # 简化BM25公式
                    idf = math.log(total_docs / (1 + sum(1 for c in chunks if term in c.content.lower())))
                    tf = (term_freq * (1.5 + 1)) / (term_freq + 1.5 * (1 - 0.75 + 0.75 * doc_len / avg_doc_len))
                    score += idf * tf

            if score > 0:
                results.append({
                    "chunk_id": chunk.id,
                    "content": chunk.content,  # 保留完整内容，不截断
                    "score": score,
                    "metadata": chunk.metadata,
                    "retrieval_methods": ["simple_bm25"]
                })

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)

        return results[:top_k]

    def _rerank_results(
        self,
        results: list[dict[str, Any]],
        query_text: str,
        top_k: int = 5
    ) -> list[dict[str, Any]]:
        """
        对检索结果进行重排序

        优先使用配置的Rerank模型进行重排序，如果模型不可用则降级到简单规则方法。

        Args:
            results: 检索结果列表
            query_text: 查询文本
            top_k: 返回结果数量

        Returns:
            重排序后的结果列表
        """
        if not results:
            return []

        # 检查 llm_service 是否可用
        if self.llm_service is None:
            raise ValueError(
                "Rerank 模型不可用：KnowledgeBaseService 未注入 llm_service。"
                "请在创建 KnowledgeBaseService 时传入 LLMService 实例，"
                "或在 .env 文件中配置 RERANK_PROVIDER、RERANK_API_KEY 等参数。"
            )
        
        # 获取 Rerank 模型（让异常传播出去）
        rerank_model = self.llm_service.get_rerank_model()
        logger.debug("获取到Rerank模型: %s", type(rerank_model).__name__)

        # 如果有Rerank模型，使用模型进行重排序
        if rerank_model:
            try:
                # 准备文档列表
                documents = [result.get("content", "") for result in results]

                # 执行重排序
                rerank_result = rerank_model.rerank(
                    query=query_text,
                    documents=documents,
                    top_n=min(top_k * 2, len(results))  # 取更多候选
                )

                if rerank_result and len(rerank_result) > 0:
                    # 映射重排序结果到原始结果
                    reranked_results = []
                    for r in rerank_result:
                        idx = r.get("index")
                        score = r.get("relevance_score", 0.0)

                        if isinstance(idx, int) and 0 <= idx < len(results):
                            # 复制原始结果，更新分数
                            reranked_item = dict(results[idx])
                            reranked_item["rerank_score"] = score
                            reranked_item["rerank_details"] = {
                                "rerank_model": type(rerank_model).__name__,
                                "relevance_score": score
                            }
                            reranked_results.append(reranked_item)

                    if reranked_results:
                        # 按重排序分数排序
                        reranked_results.sort(
                            key=lambda x: x.get("rerank_score", 0.0),
                            reverse=True
                        )

                        logger.debug(
                            "Rerank模型重排序完成: query=%s, input=%d, output=%d",
                            query_text[:50],
                            len(results),
                            len(reranked_results)
                        )

                        return reranked_results[:top_k]

                # 如果重排序返回空结果，降级到规则方法
                logger.warning(
                    "Rerank模型返回空结果，降级到规则方法: query=%s",
                    query_text[:50]
                )

            except Exception as e:
                logger.warning(
                    "Rerank模型执行失败，降级到规则方法: query=%s, error=%s",
                    query_text[:50],
                    e
                )

        # 降级：使用简单规则方法
        logger.debug(
            "使用简单规则方法进行重排序: query=%s, results=%d",
            query_text[:50],
            len(results)
        )

        # 计算更精细的相似度分数
        query_features = self._extract_text_features(query_text)

        for result in results:
            content = result.get("content", "")
            content_features = self._extract_text_features(content)

            # 综合考虑多个因素
            jaccard_sim = self._calculate_jaccard_similarity(query_features, content_features)
            keyword_match = self._calculate_keyword_match(query_text, content)
            length_penalty = self._calculate_length_penalty(content)

            # 综合评分（可以调整权重）
            result["rerank_score"] = (
                jaccard_sim * 0.4 +
                keyword_match * 0.4 +
                length_penalty * 0.2
            )
            result["rerank_details"] = {
                "method": "rule_based",
                "jaccard": jaccard_sim,
                "keyword_match": keyword_match,
                "length_penalty": length_penalty
            }

        # 按重排序分数排序
        results.sort(key=lambda x: x.get("rerank_score", x["score"]), reverse=True)

        return results[:top_k]

    def _find_chunk_by_id(
        self,
        chunks: list,
        chunk_id: str
    ) -> Any:
        """
        根据ID查找文档块

        Args:
            chunks: 文档块列表
            chunk_id: 块ID

        Returns:
            找到的文档块，如果未找到则返回None
        """
        # 尝试多种ID格式匹配
        for chunk in chunks:
            if str(chunk.id) == chunk_id:
                return chunk

            # 尝试匹配metadata中的chunk_id
            if chunk.metadata and str(chunk.metadata.get("chunk_id", "")) == chunk_id:
                return chunk

            # 尝试匹配node_id
            if chunk.metadata and str(chunk.metadata.get("node_id", "")) == chunk_id:
                return chunk

        return None

    def _extract_text_features(self, text: str) -> set[str]:
        """
        提取文本特征（用于相似度计算）

        Args:
            text: 输入文本

        Returns:
            文本特征集合
        """
        if not text:
            return set()

        # 转换为小写并提取词干
        words = text.lower().split()
        # 过滤停用词和短词
        stop_words = {"的", "是", "在", "和", "了", "与", "或", "为", "等", "于", "这", "那", "有", "无", "之"}
        features = {word for word in words if len(word) > 1 and word not in stop_words}

        return features

    def _calculate_jaccard_similarity(
        self,
        features1: set[str],
        features2: set[str]
    ) -> float:
        """
        计算Jaccard相似度

        Args:
            features1: 特征集合1
            features2: 特征集合2

        Returns:
            Jaccard相似度分数
        """
        if not features1 or not features2:
            return 0.0

        intersection = len(features1 & features2)
        union = len(features1 | features2)

        return intersection / union if union > 0 else 0.0

    def _calculate_keyword_match(
        self,
        query_text: str,
        content: str
    ) -> float:
        """
        计算关键词匹配度

        Args:
            query_text: 查询文本
            content: 文档内容

        Returns:
            关键词匹配度分数
        """
        if not query_text or not content:
            return 0.0

        query_keywords = set(query_text.lower().split())
        content_words = set(content.lower().split())

        if not query_keywords:
            return 0.0

        matches = len(query_keywords & content_words)
        return matches / len(query_keywords)

    def _calculate_length_penalty(self, content: str) -> float:
        """
        计算内容长度惩罚

        避免过短或过长的内容块

        Args:
            content: 文档内容

        Returns:
            长度惩罚分数
        """
        word_count = len(content.split())

        if word_count < 10:
            # 太短的内容价值较低
            return 0.3 + 0.07 * word_count
        elif word_count > 2000:
            #  太长的内容可能包含太多无关信息
            return max(0.5, 1.0 - (word_count - 2000) / 5000)
        else:
            # 合适的长度
            return 0.9

    def delete_knowledge_base(self, knowledge_base_id: str) -> bool:
        """
        删除知识库

        Args:
            knowledge_base_id: 知识库ID

        Returns:
            是否删除成功

        Raises:
            KnowledgeBaseServiceError: 删除失败时抛出
        """
        operation_id = str(uuid.uuid4())
        start_time = datetime.now()

        self._logger.log_operation_start(
            operation_id=operation_id,
            operation_type="delete_knowledge_base",
            knowledge_base_id=knowledge_base_id
        )

        try:
            # 检查知识库是否存在
            if knowledge_base_id not in self._knowledge_bases:
                msg = f"知识库不存在: {knowledge_base_id}"
                raise ResourceError(
                    msg,
                    resource_type="knowledge_base"
                )

            # 删除知识库
            del self._knowledge_bases[knowledge_base_id]

            # 记录成功
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._logger.log_operation_success(
                operation_id=operation_id,
                operation_type="delete_knowledge_base",
                knowledge_base_id=knowledge_base_id,
                duration_ms=duration_ms
            )

            return True

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            self._logger.log_operation_error(
                operation_id=operation_id,
                operation_type="delete_knowledge_base",
                knowledge_base_id=knowledge_base_id,
                error=e,
                duration_ms=duration_ms
            )
            raise

    def _load_documents(
        self,
        documents: list[Document],
        operation_id: str,
        knowledge_base_id: str
    ) -> list[Document]:
        """
        加载文档

        Args:
            documents: 文档列表(可以是领域模型Document或langchain_core.documents.Document)
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Returns:
            加载的文档列表(领域模型Document)

        Raises:
            DocumentLoadError: 文档加载失败时抛出
        """
        self._logger.info(
            f"[KB-{knowledge_base_id}] 开始加载文档: documents_count={len(documents)}, operation_id={operation_id}"
        )

        try:
            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=len(documents),
                stage="loading_documents"
            )

            loaded_documents = []
            failed_documents = []

            for i, doc in enumerate(documents):
                try:
                    doc_id_str = str(getattr(doc, "id", "unknown"))
                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] 正在加载文档 {i+1}/{len(documents)}: doc_id={doc_id_str}"
                    )

                    # 处理langchain_core.documents.Document
                    from langchain_core.documents import Document as LangChainDocument

                    if isinstance(doc, LangChainDocument):
                        # 从LangChain Document提取内容
                        doc_content = doc.page_content
                        doc_metadata = doc.metadata

                        # 获取文件名和路径
                        filename = doc_metadata.get("source", "unknown")
                        if isinstance(filename, Path):
                            filename = filename.name
                        elif "/" in filename or "\\" in filename:
                            filename = Path(filename).name

                        file_path = doc_metadata.get("source", "")
                        file_size = len(doc_content.encode("utf-8"))
                        doc_format = doc_metadata.get("format", "PDF")

                        # 转换为领域模型Document
                        domain_doc = Document(
                            filename=filename,
                            file_path=file_path,
                            file_size=file_size,
                            format=DocumentFormat.PDF if doc_format.lower() == "pdf" else DocumentFormat.HTML,
                            content=doc_content,
                            metadata=doc_metadata
                        )

                        loaded_documents.append(domain_doc)

                        self._logger.debug(
                            f"[KB-{knowledge_base_id}] 文档加载成功: doc_id={domain_doc.id}, "
                            f"filename={filename}, file_size={file_size}, content_length={len(doc_content)}"
                        )

                        self._logger.log_progress_update(
                            operation_id=operation_id,
                            knowledge_base_id=knowledge_base_id,
                            current=i + 1,
                            total=len(documents),
                            stage="loading_documents",
                            document_id=str(domain_doc.id),
                            filename=filename
                        )
                    else:
                        # 处理领域模型Document
                        doc_content = doc.get_metadata("content", "")
                        if not doc_content and hasattr(doc, "content"):
                            doc_content = doc.content
                            if doc_content:
                                doc.add_metadata("content", doc_content)

                        if not doc_content:
                            msg = f"文档内容为空: {doc.filename}"
                            self._logger.error(
                                f"[KB-{knowledge_base_id}] 文档内容为空: doc_id={doc_id_str}, filename={doc.filename}"
                            )
                            raise DocumentLoadError(
                                msg,
                                document_path=doc.file_path,
                                details={"document_id": str(doc.id)}
                            )

                        loaded_documents.append(doc)

                        self._logger.debug(
                            f"[KB-{knowledge_base_id}] 领域模型文档加载成功: doc_id={doc_id_str}, "
                            f"filename={doc.filename}, file_size={doc.file_size}"
                        )

                        self._logger.log_progress_update(
                            operation_id=operation_id,
                            knowledge_base_id=knowledge_base_id,
                            current=i + 1,
                            total=len(documents),
                            stage="loading_documents",
                            document_id=str(doc.id),
                            filename=doc.filename
                        )

                except Exception as e:
                    if isinstance(e, DocumentLoadError):
                        raise
                    doc_id = getattr(doc, "id", getattr(doc, "page_content", "unknown")[:50])
                    msg = f"加载文档失败: {doc_id}"
                    self._logger.error(
                        f"[KB-{knowledge_base_id}] 加载文档失败: doc_id={doc_id}, error={str(e)}",
                        exc_info=True
                    )
                    failed_documents.append({
                        "doc_id": str(doc_id),
                        "error": str(e),
                        "document_path": str(getattr(doc, "file_path", getattr(doc, "metadata", {}).get("source", "unknown")))
                    })
                    raise DocumentLoadError(
                        msg,
                        document_path=str(getattr(doc, "file_path", getattr(doc, "metadata", {}).get("source", "unknown"))),
                        details={"original_error": str(e)}
                    )

            # 汇总日志
            self._logger.info(
                f"[KB-{knowledge_base_id}] 文档加载完成: "
                f"total={len(documents)}, success={len(loaded_documents)}, failed={len(failed_documents)}"
            )

            if failed_documents:
                self._logger.warning(
                    f"[KB-{knowledge_base_id}] 部分文档加载失败: {failed_documents}"
                )

            return loaded_documents

        except Exception as e:
            if isinstance(e, DocumentLoadError):
                raise
            msg = "文档加载过程失败"
            self._logger.error(
                f"[KB-{knowledge_base_id}] 文档加载过程失败: error={str(e)}",
                exc_info=True
            )
            raise DocumentLoadError(
                msg,
                details={"original_error": str(e)}
            )

    def _parse_documents(
        self,
        documents: list[Document],
        operation_id: str,
        knowledge_base_id: str
    ) -> list[PreprocessedDocument]:
        """
        解析文档

        Args:
            documents: 文档列表
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Returns:
            解析后的文档列表

        Raises:
            DocumentParseError: 文档解析失败时抛出
        """
        self._logger.info(
            f"[KB-{knowledge_base_id}] 开始解析文档: documents_count={len(documents)}, operation_id={operation_id}"
        )

        try:
            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=len(documents),
                stage="parsing_documents"
            )

            preprocessed_documents = []
            failed_documents = []

            for i, doc in enumerate(documents):
                try:
                    doc_id_str = str(getattr(doc, "id", "unknown"))
                    doc_filename = getattr(doc, "filename", "unknown")
                    doc_content_length = len(getattr(doc, "content", "") or "")

                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] 正在解析文档 {i+1}/{len(documents)}: "
                        f"doc_id={doc_id_str}, filename={doc_filename}, content_length={doc_content_length}"
                    )

                    # 获取文档内容
                    if hasattr(doc, "content") and doc.content:
                        doc_content = doc.content
                    elif hasattr(doc, "get_metadata"):
                        doc_content = doc.get_metadata("content", f"默认内容: {doc.filename}")
                    else:
                        doc_content = f"默认内容: {doc.filename}"

                    # 获取文档标题
                    if hasattr(doc, "filename"):
                        doc_title = doc.filename
                    elif hasattr(doc, "metadata") and "source" in doc.metadata:
                        source = doc.metadata["source"]
                        if isinstance(source, Path):
                            doc_title = source.name
                        else:
                            doc_title = Path(source).name if source else "unknown"
                    else:
                        doc_title = "unknown"

                    preprocessed_doc = PreprocessedDocument(
                        id=doc.id,
                        original_document_id=doc.id,
                        title=doc_title,
                        content=doc_content,
                        original_content_hash=str(hash(doc_content) % 1000000000),  # 简单哈希
                        cleaning_level=CleaningLevel.BASIC,
                        processing_steps=["content_extraction"],
                        original_length=len(doc_content),
                        processed_length=len(doc_content),
                        metadata=doc.metadata if hasattr(doc, "metadata") else {}
                    )

                    preprocessed_documents.append(preprocessed_doc)

                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] 文档解析成功: doc_id={doc_id_str}, "
                        f"title={doc_title}, content_length={len(doc_content)}, "
                        f"processed_length={preprocessed_doc.processed_length}"
                    )

                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=i + 1,
                        total=len(documents),
                        stage="parsing_documents",
                        document_id=str(doc.id),
                        filename=doc_filename,
                        content_length=len(doc_content)
                    )

                except Exception as e:
                    if isinstance(e, DocumentParseError):
                        raise
                    doc_id = getattr(doc, "id", "unknown")
                    doc_filename = getattr(doc, "filename", "unknown")
                    msg = f"解析文档失败: {doc_id}"
                    self._logger.error(
                        f"[KB-{knowledge_base_id}] 解析文档失败: doc_id={doc_id}, "
                        f"filename={doc_filename}, error={str(e)}",
                        exc_info=True
                    )
                    failed_documents.append({
                        "doc_id": str(doc_id),
                        "filename": doc_filename,
                        "error": str(e)
                    })
                    raise DocumentParseError(
                        msg,
                        document_id=str(doc.id),
                        details={"original_error": str(e)}
                    )

            # 汇总日志
            total_content_length = sum(len(doc.content) for doc in preprocessed_documents)
            self._logger.info(
                f"[KB-{knowledge_base_id}] 文档解析完成: "
                f"total={len(documents)}, success={len(preprocessed_documents)}, "
                f"failed={len(failed_documents)}, total_content_length={total_content_length}"
            )

            if failed_documents:
                self._logger.warning(
                    f"[KB-{knowledge_base_id}] 部分文档解析失败: {failed_documents}"
                )

            return preprocessed_documents

        except Exception as e:
            if isinstance(e, DocumentParseError):
                raise
            msg = "文档解析过程失败"
            self._logger.error(
                f"[KB-{knowledge_base_id}] 文档解析过程失败: error={str(e)}",
                exc_info=True
            )
            raise DocumentParseError(
                msg,
                details={"original_error": str(e)}
            )

    def _chunk_documents(
        self,
        preprocessed_documents: list[PreprocessedDocument],
        chunk_size: int,
        chunk_overlap: int,
        operation_id: str,
        knowledge_base_id: str
    ) -> list[DocumentChunk]:
        """
        分块文档

        使用 DocumentChunkingStrategy 进行句子级分块，保留文档结构信息。

        Args:
            preprocessed_documents: 预处理文档列表
            chunk_size: 块大小
            chunk_overlap: 块重叠大小
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Returns:
            文档块列表

        Raises:
            DocumentParseError: 文档分块失败时抛出
        """
        self._logger.info(
            f"[KB-{knowledge_base_id}] 开始分块文档: documents_count={len(preprocessed_documents)}, "
            f"chunk_size={chunk_size}, chunk_overlap={chunk_overlap}, operation_id={operation_id}"
        )

        try:
            # 检查 LlamaIndex 可用性
            if not LLAMA_INDEX_AVAILABLE:
                # 降级到简单字符级分块
                logger.warning("LlamaIndex不可用，使用简单字符级分块")
                self._logger.warning(
                    f"[KB-{knowledge_base_id}] LlamaIndex不可用，降级到简单字符级分块"
                )
                return self._chunk_documents_simple(
                    preprocessed_documents, chunk_size, chunk_overlap, operation_id, knowledge_base_id
                )

            # 导入必要的模块
            from src.infrastructure.indexing.document_chunking import (
                ChunkingConfig,
                DocumentChunkingStrategy,
            )
            from src.infrastructure.parsing.markdown_parser import MarkdownParser

            # 创建分块配置
            chunking_config = ChunkingConfig(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                split_by_section=True,
                split_by_paragraph=True,
                chunking_mode="semantic",  # 使用语义分块
                min_chunk_size=1000,  # 最小分块大小，确保召回率
                max_chunk_size=2048,  # 最大分块大小
            )

            # 根据分块模式选择策略
            if chunking_config.chunking_mode == "semantic":
                from src.infrastructure.indexing.document_chunking import (
                    SemanticChunkingStrategy,
                )
                chunking_strategy = SemanticChunkingStrategy(config=chunking_config)
                logger.info(
                    "使用语义分块策略: min_chunk_size=%s, max_chunk_size=%s",
                    chunking_config.min_chunk_size,
                    chunking_config.max_chunk_size,
                )
                self._logger.info(
                    f"[KB-{knowledge_base_id}] 使用语义分块策略: "
                    f"min_chunk_size={chunking_config.min_chunk_size}, "
                    f"max_chunk_size={chunking_config.max_chunk_size}"
                )
            else:
                chunking_strategy = DocumentChunkingStrategy(config=chunking_config)
                self._logger.info(
                    f"[KB-{knowledge_base_id}] 使用文档分块策略"
                )

            # 创建 Markdown 解析器
            markdown_parser = MarkdownParser(
                include_images=True,
                include_charts=True,
                preserve_metadata=True,
            )

            all_chunks: list[DocumentChunk] = []
            total_processed = 0
            failed_documents = []

            for doc_index, doc in enumerate(preprocessed_documents):
                try:
                    doc_id_str = str(doc.id)
                    doc_title = doc.title or "unknown"
                    doc_content_length = len(doc.content)

                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] 正在分块文档 {doc_index+1}/{len(preprocessed_documents)}: "
                        f"doc_id={doc_id_str}, title={doc_title}, content_length={doc_content_length}"
                    )

                    # 构建文档元数据
                    doc_metadata = {
                        "document_id": str(doc.id),
                        "document_title": doc.title or "unknown",
                        "source": "knowledge_base_service",
                        "original_document_id": str(doc.original_document_id),
                        "format": "markdown",  # PreprocessedDocument 通常是 Markdown 格式
                    }

                    # 合并 PreprocessedDocument 的元数据
                    if doc.metadata:
                        doc_metadata.update(doc.metadata)

                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] 文档元数据: doc_id={doc_id_str}, "
                        f"metadata_keys={list(doc_metadata.keys())}"
                    )

                    # 将 Markdown 内容解析为 Node 对象
                    nodes = markdown_parser.parse_from_markdown_string(
                        markdown_content=doc.content,
                        metadata=doc_metadata,
                    )

                    if not nodes:
                        self._logger.warning(
                            f"[KB-{knowledge_base_id}] 文档解析后没有节点，跳过: doc_id={doc_id_str}"
                        )
                        logger.warning(f"文档 {doc.id} 解析后没有节点，跳过")
                        continue

                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] Markdown解析完成: doc_id={doc_id_str}, nodes_count={len(nodes)}"
                    )

                    # 使用 DocumentChunkingStrategy 进行分块
                    chunked_nodes = chunking_strategy.chunk_nodes(nodes)

                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] 分块完成: doc_id={doc_id_str}, chunked_nodes_count={len(chunked_nodes)}"
                    )

                    # 将分块后的 Node 转换为 DocumentChunk
                    doc_chunks = self._nodes_to_chunks(
                        chunked_nodes=chunked_nodes,
                        document_id=doc.id,
                        document_content=doc.content,
                    )

                    all_chunks.extend(doc_chunks)
                    total_processed += 1

                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] 文档分块成功: doc_id={doc_id_str}, "
                        f"chunks_count={len(doc_chunks)}, total_chunks={len(all_chunks)}"
                    )

                    # 更新进度
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=len(all_chunks),
                        total=len(preprocessed_documents),  # 粗略估计
                        stage="chunking_documents",
                        document_id=str(doc.id),
                        document_index=doc_index,
                        chunks_count=len(doc_chunks)
                    )

                except Exception as e:
                    doc_id_str = str(doc.id)
                    doc_title = doc.title or "unknown"
                    logger.error(f"分块文档失败: {doc.id}, 错误: {e}", exc_info=True)
                    self._logger.error(
                        f"[KB-{knowledge_base_id}] 分块文档失败: doc_id={doc_id_str}, "
                        f"title={doc_title}, error={str(e)}",
                        exc_info=True
                    )
                    failed_documents.append({
                        "doc_id": doc_id_str,
                        "title": doc_title,
                        "error": str(e)
                    })
                    msg = f"分块文档失败: {doc.id}"
                    raise DocumentParseError(
                        msg,
                        document_id=str(doc.id),
                        details={"original_error": str(e)}
                    )

            # 汇总日志
            total_content_length = sum(len(doc.content) for doc in preprocessed_documents)
            avg_chunks_per_doc = len(all_chunks) / total_processed if total_processed > 0 else 0

            self._logger.info(
                f"[KB-{knowledge_base_id}] 文档分块完成: "
                f"documents_processed={total_processed}, documents_failed={len(failed_documents)}, "
                f"total_chunks={len(all_chunks)}, avg_chunks_per_doc={avg_chunks_per_doc:.2f}, "
                f"chunk_size={chunk_size}, overlap={chunk_overlap}"
            )

            if failed_documents:
                self._logger.warning(
                    f"[KB-{knowledge_base_id}] 部分文档分块失败: {failed_documents}"
                )

            logger.info(
                f"文档分块完成: 文档数={total_processed}, 总块数={len(all_chunks)}, "
                f"chunk_size={chunk_size}, overlap={chunk_overlap}"
            )

            return all_chunks

        except Exception as e:
            if isinstance(e, DocumentParseError):
                raise
            msg = "文档分块过程失败"
            self._logger.error(
                f"[KB-{knowledge_base_id}] 文档分块过程失败: error={str(e)}",
                exc_info=True
            )
            raise DocumentParseError(
                msg,
                details={"original_error": str(e)}
            )

    def _chunk_documents_simple(
        self,
        preprocessed_documents: list[PreprocessedDocument],
        chunk_size: int,
        chunk_overlap: int,
        operation_id: str,
        knowledge_base_id: str
    ) -> list[DocumentChunk]:
        """
        简单字符级分块（降级方案，当 LlamaIndex 不可用时使用）

        Args:
            preprocessed_documents: 预处理文档列表
            chunk_size: 块大小
            chunk_overlap: 块重叠大小
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Returns:
            文档块列表
        """
        total_chunks_estimate = sum(len(doc.content) // chunk_size + 1 for doc in preprocessed_documents)

        self._logger.log_progress_update(
            operation_id=operation_id,
            knowledge_base_id=knowledge_base_id,
            current=0,
            total=total_chunks_estimate,
            stage="chunking_documents"
        )

        chunks = []
        for doc in preprocessed_documents:
            content = doc.content
            for i in range(0, len(content), chunk_size - chunk_overlap):
                chunk_content = content[i:i + chunk_size]

                # 构建元数据，优先使用 doc.metadata 中的字段
                doc_meta = doc.metadata if hasattr(doc, "metadata") and doc.metadata else {}
                chunk_metadata = {
                    "document_id": str(doc.id),
                    "document_title": doc.title,
                    "source": doc_meta.get("source") or doc_meta.get("file_path") or "knowledge_base_service",
                    "file_path": doc_meta.get("file_path") or doc_meta.get("source") or "",
                    "filename": doc_meta.get("filename") or doc_meta.get("source_title") or doc.title or "",
                    "chunking_method": "simple_char_level",
                }
                # 合并 doc.metadata 中的其他字段
                for k, v in doc_meta.items():
                    if k not in chunk_metadata:
                        chunk_metadata[k] = v
                
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc.id,
                    chunk_index=i // (chunk_size - chunk_overlap),
                    content=chunk_content,
                    start_position=i,
                    end_position=min(i + chunk_size, len(content)),
                    section_path="1",  # 默认章节路径
                    metadata=chunk_metadata,
                )

                chunks.append(chunk)

                self._logger.log_progress_update(
                    operation_id=operation_id,
                    knowledge_base_id=knowledge_base_id,
                    current=len(chunks),
                    total=total_chunks_estimate,
                    stage="chunking_documents",
                    document_id=str(doc.id),
                    chunk_index=chunk.chunk_index
                )

        return chunks

    def _nodes_to_chunks(
        self,
        chunked_nodes: list[Any],
        document_id: uuid.UUID,
        document_content: str,
    ) -> list[DocumentChunk]:
        """
        将分块后的 LlamaIndex Node 对象转换为 DocumentChunk 对象

        Args:
            chunked_nodes: 分块后的 Node 对象列表
            document_id: 文档ID
            document_content: 原始文档内容（用于计算位置）

        Returns:
            DocumentChunk 对象列表
        """
        if not LLAMA_INDEX_AVAILABLE:
            msg = "LlamaIndex不可用，无法转换Node到DocumentChunk"
            raise ImportError(msg)

        chunks: list[DocumentChunk] = []
        from src.domain.knowledge_base.document_chunk import ChunkType

        # 用于计算位置偏移的累计长度
        content_offset = 0

        for chunk_index, node in enumerate(chunked_nodes):
            # 提取 Node 的文本内容
            node_text = getattr(node, "text", "") or str(node)
            if not node_text or not node_text.strip():
                continue

            # 提取元数据
            node_metadata = dict(getattr(node, "metadata", {}) or {})

            # 提取章节信息
            section_path = str(node_metadata.get("section_path", "")) or "1"
            section_title = node_metadata.get("section_title")

            # 提取块索引（如果存在）
            node_chunk_index = node_metadata.get("chunk_index", chunk_index)

            # 计算在原始文档中的位置
            # 注意：由于分块后无法精确计算位置，我们使用近似值
            start_position = content_offset
            end_position = content_offset + len(node_text)
            content_offset = end_position  # 为下一个块更新偏移

            # 提取元素类型并转换为 ChunkType
            element_type = node_metadata.get("element_type", "").lower()
            chunk_type = ChunkType.PARAGRAPH
            if element_type == "heading":
                chunk_type = ChunkType.HEADING
            elif element_type == "table":
                chunk_type = ChunkType.TABLE
            elif element_type == "code_block":
                chunk_type = ChunkType.CODE
            elif element_type == "list" or element_type == "list_item":
                chunk_type = ChunkType.LIST

            # 构建扩展元数据
            chunk_metadata = {
                "document_id": str(document_id),
                "source": "knowledge_base_service",
                "chunking_method": "sentence_level_with_document_chunking_strategy",
                "paragraph_index": node_metadata.get("paragraph_index"),
                "chunk_index_in_node": node_metadata.get("chunk_index_in_node"),
                "original_node_index": node_metadata.get("original_node_index"),
                "element_type": element_type,
            }

            # 合并 Node 的其他元数据（排除已使用的字段）
            excluded_keys = {
                "chunk_index", "section_path", "section_title", "document_id",
                "chunk_index_in_node", "original_node_index", "paragraph_index", "element_type"
            }
            for key, value in node_metadata.items():
                if key not in excluded_keys:
                    chunk_metadata[key] = value

            # 创建 DocumentChunk
            chunk = DocumentChunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=node_chunk_index,
                content=node_text.strip(),
                start_position=start_position,
                end_position=end_position,
                section_path=section_path,
                section_title=section_title,
                chunk_type=chunk_type,
                metadata=chunk_metadata,
            )

            chunks.append(chunk)

        return chunks

    def _chunks_to_nodes(self, chunks: list[DocumentChunk]) -> list[Any]:
        """
        将DocumentChunk转换为LlamaIndex BaseNode

        Args:
            chunks: 文档块列表

        Returns:
            LlamaIndex Node对象列表

        Raises:
            ImportError: 如果LlamaIndex未安装
        """
        if not LLAMA_INDEX_AVAILABLE:
            msg = "LlamaIndex is not available. Please install llama-index package."
            raise ImportError(msg)

        self._logger.debug(f"开始转换DocumentChunk到Node: chunks_count={len(chunks)}")

        # 批量获取文档信息（document_id -> (file_path, filename)）
        # 注意：数据库 documents 表没有 title 列，只有 filename / file_path。
        # 这里用 filename 作为"可展示的文档标题"，用于后续引用展示。
        document_info_map: dict[str, tuple[str, str]] = {}
        document_ids_found = set()

        if chunks:
            # 获取所有唯一的document_id
            document_ids = list(set(str(chunk.document_id) for chunk in chunks))
            self._logger.debug(f"需要查询的文档ID数量: {len(document_ids)}")

            # 批量查询文档信息
            try:
                from src.infrastructure.storage.sqlite.connection import get_connection_manager
                cm = get_connection_manager()
                with cm.get_connection() as conn:
                    cursor = conn.cursor()
                    placeholders = ",".join(["?"] * len(document_ids))
                    query = f"SELECT id, file_path, filename FROM documents WHERE id IN ({placeholders})"
                    cursor.execute(query, document_ids)
                    for row in cursor.fetchall():
                        doc_id, file_path, filename = row
                        document_info_map[doc_id] = (file_path or "", filename or "")
                        document_ids_found.add(doc_id)

                self._logger.debug(
                    f"批量查询文档信息成功: query_count={len(document_ids)}, "
                    f"found_count={len(document_info_map)}"
                )
            except Exception as e:
                self._logger.warning(f"批量查询文档信息失败: {e}, 将逐个查询")
                # 降级：逐个查询
                for chunk in chunks:
                    doc_id = str(chunk.document_id)
                    if doc_id not in document_info_map:
                        try:
                            from src.infrastructure.storage.sqlite.connection import get_connection_manager
                            cm = get_connection_manager()
                            with cm.get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "SELECT file_path, filename FROM documents WHERE id = ?",
                                    (doc_id,)
                                )
                                row = cursor.fetchone()
                                if row:
                                    document_info_map[doc_id] = (row[0] or "", row[1] or "")
                                    document_ids_found.add(doc_id)
                                else:
                                    document_info_map[doc_id] = ("", "")
                        except Exception as query_error:
                            self._logger.warning(f"查询文档信息失败: doc_id={doc_id}, error={query_error}")
                            document_info_map[doc_id] = ("", "")

        # 记录未找到的文档ID
        all_doc_ids = set(str(chunk.document_id) for chunk in chunks)
        missing_doc_ids = all_doc_ids - document_ids_found
        if missing_doc_ids:
            self._logger.warning(f"以下文档ID在数据库中未找到: {missing_doc_ids}")

        nodes = []
        skipped_chunks = 0

        for chunk_index, chunk in enumerate(chunks):
            doc_id = str(chunk.document_id)
            db_file_path, db_filename = document_info_map.get(doc_id, ("", ""))

            # 优先从 chunk.metadata 获取 file_path/filename（由上游 LangChain Document 传递）
            # 这样即使 documents 表为空，也能正确显示来源
            chunk_meta = chunk.metadata or {}

            # 文件路径优先级：chunk.metadata.file_path > chunk.metadata.source > documents表 > 空
            file_path = (
                chunk_meta.get("file_path")
                or chunk_meta.get("source")
                or db_file_path
                or ""
            )

            # 文件名优先级：chunk.metadata.filename > chunk.metadata.source_title > documents表 > 从路径推断
            filename = (
                chunk_meta.get("filename")
                or chunk_meta.get("source_title")
                or chunk_meta.get("original_pdf_filename")
                or db_filename
                or ""
            )
            # 如果仍无 filename，尝试从 file_path 推断
            if not filename and file_path:
                try:
                    from pathlib import Path
                    filename = Path(file_path).name
                except Exception:
                    pass

            # 构建元数据
            metadata: dict[str, Any] = {
                "chunk_id": str(chunk.id),
                "document_id": doc_id,
                "file_path": file_path,  # 添加文件路径
                "document_title": filename,  # 用 filename 作为可展示标题
                "filename": filename,
                "chunk_index": chunk.chunk_index,
                "section_path": chunk.section_path,
                "chunk_type": chunk.chunk_type.value if hasattr(chunk.chunk_type, "value") else str(chunk.chunk_type),
                "start_position": chunk.start_position,
                "end_position": chunk.end_position,
                "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
            }

            # 添加章节标题（如果有）
            if chunk.section_title:
                metadata["section_title"] = chunk.section_title

            # 合并扩展元数据（但不覆盖已设置的 file_path/filename）
            if chunk.metadata:
                for k, v in chunk.metadata.items():
                    if k not in metadata or not metadata[k]:
                        metadata[k] = v

            # 创建TextNode
            node = TextNode(
                text=chunk.content,
                id_=str(chunk.id),
                metadata=metadata,
            )
            nodes.append(node)

        self._logger.debug(
            f"转换DocumentChunk到Node完成: chunks_count={len(chunks)}, "
            f"nodes_count={len(nodes)}, skipped={skipped_chunks}, "
            f"documents_with_info={len(document_info_map)}"
        )
        return nodes

    def _build_indexes(
        self,
        chunks: list[DocumentChunk],
        operation_id: str,
        knowledge_base_id: str
    ) -> dict[str, Any]:
        """
        构建索引

        Args:
            chunks: 文档块列表
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Returns:
            索引字典，包含索引构建器实例

        Raises:
            IndexBuildError: 索引构建失败时抛出
        """
        self._logger.info(
            f"[KB-{knowledge_base_id}] 开始构建索引: chunks_count={len(chunks)}, "
            f"operation_id={operation_id}, enable_vector={self.enable_vector}, "
            f"enable_bm25={self.enable_bm25}, enable_metadata={self.enable_metadata}, "
            f"enable_graph={self.enable_graph}"
        )

        try:
            # 将DocumentChunk转换为LlamaIndex Node
            nodes = self._chunks_to_nodes(chunks)
            if not nodes:
                self._logger.warning(
                    f"[KB-{knowledge_base_id}] 没有有效的节点可以构建索引: chunks_count={len(chunks)}"
                )
                logger.warning("没有有效的节点可以构建索引")
                return {}

            self._logger.info(
                f"[KB-{knowledge_base_id}] 节点转换完成: chunks_count={len(chunks)}, nodes_count={len(nodes)}"
            )

            # 计算需要构建的索引类型数量
            index_count = sum([
                self.enable_vector and self.vector_index_builder is not None,
                self.enable_bm25 and self.bm25_index_builder is not None,
                self.enable_metadata and self.metadata_index_builder is not None,
                self.enable_graph and self.knowledge_graph_builder is not None,
            ])

            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=index_count,
                stage="building_indexes"
            )

            indexes: dict[str, Any] = {}
            current_index = 0
            failed_indexes = []

            # 构建向量索引
            if self.enable_vector and self.vector_index_builder:
                try:
                    self._logger.info(
                        f"[KB-{knowledge_base_id}] 开始构建向量索引: nodes_count={len(nodes)}"
                    )
                    logger.info("开始构建向量索引: nodes=%d", len(nodes))
                    vector_index = self.vector_index_builder.build_index(
                        nodes=nodes,
                        show_progress=False
                    )
                    indexes["vector_index"] = {
                        "type": "vector",
                        "builder": self.vector_index_builder,
                        "index": vector_index,
                        "size": len(nodes),
                        "created_at": datetime.now()
                    }
                    current_index += 1
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=current_index,
                        total=index_count,
                        stage="building_indexes",
                        index_type="vector"
                    )
                    self._logger.info(
                        f"[KB-{knowledge_base_id}] 向量索引构建完成: nodes_count={len(nodes)}"
                    )
                    logger.info("向量索引构建完成")
                except Exception as e:
                    self._logger.error(
                        f"[KB-{knowledge_base_id}] 构建向量索引失败: error={str(e)}",
                        exc_info=True
                    )
                    logger.error("构建向量索引失败: %s", e, exc_info=True)
                    failed_indexes.append({"type": "vector", "error": str(e)})
                    msg = "构建向量索引失败"
                    raise IndexBuildError(
                        msg,
                        index_type="vector",
                        details={"original_error": str(e)}
                    ) from e

            # 构建BM25索引
            if self.enable_bm25 and self.bm25_index_builder:
                try:
                    self._logger.info(
                        f"[KB-{knowledge_base_id}] 开始构建BM25索引: nodes_count={len(nodes)}"
                    )
                    logger.info("开始构建BM25索引: nodes=%d", len(nodes))
                    self.bm25_index_builder.build_index(
                        nodes=nodes,
                        show_progress=False
                    )

                    # 验证BM25索引是否构建成功
                    bm25_stats = self.bm25_index_builder.get_stats()
                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] BM25索引构建统计: {bm25_stats}"
                    )
                    if not bm25_stats.get("is_built") or bm25_stats.get("documents_count", 0) == 0:
                        logger.error(
                            "BM25索引构建验证失败: is_built=%s, documents_count=%s",
                            bm25_stats.get("is_built"),
                            bm25_stats.get("documents_count")
                        )
                        self._logger.error(
                            f"[KB-{knowledge_base_id}] BM25索引构建验证失败: "
                            f"is_built={bm25_stats.get('is_built')}, "
                            f"documents_count={bm25_stats.get('documents_count')}"
                        )
                        raise IndexBuildError(
                            "BM25索引构建失败：索引为空或未正确构建",
                            index_type="bm25",
                            details={"bm25_stats": bm25_stats}
                        )

                    indexes["bm25_index"] = {
                        "type": "bm25",
                        "builder": self.bm25_index_builder,
                        "size": bm25_stats.get("documents_count", len(nodes)),
                        "stats": bm25_stats,
                        "created_at": datetime.now()
                    }
                    current_index += 1
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=current_index,
                        total=index_count,
                        stage="building_indexes",
                        index_type="bm25"
                    )
                    self._logger.info(
                        f"[KB-{knowledge_base_id}] BM25索引构建完成: "
                        f"documents_count={bm25_stats.get('documents_count')}, "
                        f"vocab_size={bm25_stats.get('vocab_size')}"
                    )
                    logger.info("BM25索引构建完成: documents_count=%d", bm25_stats.get("documents_count"))
                except IndexBuildError:
                    raise
                except Exception as e:
                    self._logger.error(
                        f"[KB-{knowledge_base_id}] 构建BM25索引失败: error={str(e)}",
                        exc_info=True
                    )
                    logger.error("构建BM25索引失败: %s", e, exc_info=True)
                    failed_indexes.append({"type": "bm25", "error": str(e)})
                    msg = "构建BM25索引失败"
                    raise IndexBuildError(
                        msg,
                        index_type="bm25",
                        details={"original_error": str(e)}
                    ) from e

            # 构建元数据索引
            if self.enable_metadata and self.metadata_index_builder:
                try:
                    self._logger.info(
                        f"[KB-{knowledge_base_id}] 开始构建元数据索引: nodes_count={len(nodes)}"
                    )
                    logger.info("开始构建元数据索引: nodes=%d", len(nodes))
                    created_records = self.metadata_index_builder.build_index(nodes=nodes)

                    # 验证元数据索引是否构建成功
                    self._logger.debug(
                        f"[KB-{knowledge_base_id}] 元数据索引构建完成: created_records_count={len(created_records) if created_records else 0}"
                    )
                    if not created_records or len(created_records) == 0:
                        logger.error(
                            "元数据索引构建验证失败: created_records_count=%d, nodes_count=%d",
                            len(created_records) if created_records else 0,
                            len(nodes)
                        )
                        self._logger.error(
                            f"[KB-{knowledge_base_id}] 元数据索引构建验证失败: "
                            f"created_records_count={len(created_records) if created_records else 0}, "
                            f"nodes_count={len(nodes)}"
                        )
                        raise IndexBuildError(
                            "元数据索引构建失败：没有创建任何记录",
                            index_type="metadata",
                            details={"created_records_count": len(created_records) if created_records else 0}
                        )

                    indexes["metadata_index"] = {
                        "type": "metadata",
                        "builder": self.metadata_index_builder,
                        "size": len(created_records),
                        "created_at": datetime.now()
                    }
                    current_index += 1
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=current_index,
                        total=index_count,
                        stage="building_indexes",
                        index_type="metadata"
                    )
                    self._logger.info(
                        f"[KB-{knowledge_base_id}] 元数据索引构建完成: records_count={len(created_records)}"
                    )
                    logger.info("元数据索引构建完成: records_count=%d", len(created_records))
                except IndexBuildError:
                    raise
                except Exception as e:
                    self._logger.error(
                        f"[KB-{knowledge_base_id}] 构建元数据索引失败: error={str(e)}",
                        exc_info=True
                    )
                    logger.error("构建元数据索引失败: %s", e, exc_info=True)
                    failed_indexes.append({"type": "metadata", "error": str(e)})
                    msg = "构建元数据索引失败"
                    raise IndexBuildError(
                        msg,
                        index_type="metadata",
                        details={"original_error": str(e)}
                    ) from e

            # 构建知识图谱索引
            if self.enable_graph and self.knowledge_graph_builder:
                try:
                    self._logger.info(
                        f"[KB-{knowledge_base_id}] 开始构建知识图谱索引: nodes_count={len(nodes)}"
                    )
                    logger.info("开始构建知识图谱索引: nodes=%d", len(nodes))
                    graph_result = self.knowledge_graph_builder.build_from_nodes(
                        nodes=nodes,
                        show_progress=False
                    )
                    indexes["knowledge_graph"] = {
                        "type": "knowledge_graph",
                        "builder": self.knowledge_graph_builder,
                        "size": len(nodes),
                        "stats": graph_result,
                        "created_at": datetime.now()
                    }
                    current_index += 1
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=current_index,
                        total=index_count,
                        stage="building_indexes",
                        index_type="knowledge_graph"
                    )
                    self._logger.info(
                        f"[KB-{knowledge_base_id}] 知识图谱索引构建完成: stats={graph_result}"
                    )
                    logger.info("知识图谱索引构建完成")
                except Exception as e:
                    self._logger.error(
                        f"[KB-{knowledge_base_id}] 构建知识图谱索引失败: error={str(e)}",
                        exc_info=True
                    )
                    logger.error("构建知识图谱索引失败: %s", e, exc_info=True)
                    failed_indexes.append({"type": "knowledge_graph", "error": str(e)})
                    msg = "构建知识图谱索引失败"
                    raise IndexBuildError(
                        msg,
                        index_type="knowledge_graph",
                        details={"original_error": str(e)}
                    ) from e

            # 汇总日志
            self._logger.info(
                f"[KB-{knowledge_base_id}] 索引构建完成: "
                f"index_types_built={len(indexes)}, index_types_failed={len(failed_indexes)}, "
                f"nodes_count={len(nodes)}, total_index_count={index_count}"
            )
            logger.info("索引构建完成: 索引类型数=%d, 节点数=%d", len(indexes), len(nodes))

            if failed_indexes:
                self._logger.warning(
                    f"[KB-{knowledge_base_id}] 部分索引构建失败: {failed_indexes}"
                )

            return indexes

        except Exception as e:
            if isinstance(e, IndexBuildError):
                raise
            self._logger.error(
                f"[KB-{knowledge_base_id}] 索引构建过程失败: error={str(e)}",
                exc_info=True
            )
            logger.error("索引构建过程失败: %s", e, exc_info=True)
            msg = "索引构建过程失败"
            raise IndexBuildError(
                msg,
                details={"original_error": str(e)}
            ) from e

    def _update_indexes(
        self,
        chunks: list[DocumentChunk],
        operation_id: str,
        knowledge_base_id: str
    ) -> dict[str, Any]:
        """
        更新索引（增量添加新节点）

        Args:
            chunks: 文档块列表（新增的块）
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Returns:
            更新后的索引字典

        Raises:
            IndexBuildError: 索引更新失败时抛出
        """
        try:
            # 将DocumentChunk转换为LlamaIndex Node
            nodes = self._chunks_to_nodes(chunks)
            if not nodes:
                logger.warning("没有有效的节点可以更新索引")
                return {}

            # 计算需要更新的索引类型数量
            index_count = sum([
                self.enable_vector and self.vector_index_builder is not None,
                self.enable_bm25 and self.bm25_index_builder is not None,
                self.enable_metadata and self.metadata_index_builder is not None,
                self.enable_graph and self.knowledge_graph_builder is not None,
            ])

            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=index_count,
                stage="updating_indexes"
            )

            indexes: dict[str, Any] = {}
            current_index = 0

            # 更新向量索引
            if self.enable_vector and self.vector_index_builder:
                try:
                    logger.info("开始更新向量索引: nodes=%d", len(nodes))
                    node_ids = self.vector_index_builder.insert(nodes=nodes)
                    indexes["vector_index"] = {
                        "type": "vector",
                        "builder": self.vector_index_builder,
                        "added_count": len(node_ids),
                        "updated_at": datetime.now()
                    }
                    current_index += 1
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=current_index,
                        total=index_count,
                        stage="updating_indexes",
                        index_type="vector"
                    )
                    logger.info("向量索引更新完成: 添加节点数=%d", len(node_ids))
                except Exception as e:
                    logger.error("更新向量索引失败: %s", e, exc_info=True)
                    msg = "更新向量索引失败"
                    raise IndexBuildError(
                        msg,
                        index_type="vector",
                        details={"original_error": str(e)}
                    ) from e

            # 更新BM25索引
            if self.enable_bm25 and self.bm25_index_builder:
                try:
                    logger.info("开始更新BM25索引: nodes=%d", len(nodes))
                    self.bm25_index_builder.add_documents(nodes=nodes)
                    indexes["bm25_index"] = {
                        "type": "bm25",
                        "builder": self.bm25_index_builder,
                        "added_count": len(nodes),
                        "updated_at": datetime.now()
                    }
                    current_index += 1
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=current_index,
                        total=index_count,
                        stage="updating_indexes",
                        index_type="bm25"
                    )
                    logger.info("BM25索引更新完成: 添加节点数=%d", len(nodes))
                except Exception as e:
                    logger.error("更新BM25索引失败: %s", e, exc_info=True)
                    msg = "更新BM25索引失败"
                    raise IndexBuildError(
                        msg,
                        index_type="bm25",
                        details={"original_error": str(e)}
                    ) from e

            # 更新元数据索引（使用build_index，因为bulk_create支持增量添加）
            if self.enable_metadata and self.metadata_index_builder:
                try:
                    logger.info("开始更新元数据索引: nodes=%d", len(nodes))
                    records = self.metadata_index_builder.build_index(nodes=nodes)
                    indexes["metadata_index"] = {
                        "type": "metadata",
                        "builder": self.metadata_index_builder,
                        "added_count": len(records),
                        "updated_at": datetime.now()
                    }
                    current_index += 1
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=current_index,
                        total=index_count,
                        stage="updating_indexes",
                        index_type="metadata"
                    )
                    logger.info("元数据索引更新完成: 添加记录数=%d", len(records))
                except Exception as e:
                    logger.error("更新元数据索引失败: %s", e, exc_info=True)
                    msg = "更新元数据索引失败"
                    raise IndexBuildError(
                        msg,
                        index_type="metadata",
                        details={"original_error": str(e)}
                    ) from e

            # 更新知识图谱索引（build_from_nodes支持增量添加）
            if self.enable_graph and self.knowledge_graph_builder:
                try:
                    logger.info("开始更新知识图谱索引: nodes=%d", len(nodes))
                    graph_result = self.knowledge_graph_builder.build_from_nodes(
                        nodes=nodes,
                        show_progress=False
                    )
                    indexes["knowledge_graph"] = {
                        "type": "knowledge_graph",
                        "builder": self.knowledge_graph_builder,
                        "added_count": len(nodes),
                        "stats": graph_result,
                        "updated_at": datetime.now()
                    }
                    current_index += 1
                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=current_index,
                        total=index_count,
                        stage="updating_indexes",
                        index_type="knowledge_graph"
                    )
                    logger.info("知识图谱索引更新完成")
                except Exception as e:
                    logger.error("更新知识图谱索引失败: %s", e, exc_info=True)
                    msg = "更新知识图谱索引失败"
                    raise IndexBuildError(
                        msg,
                        index_type="knowledge_graph",
                        details={"original_error": str(e)}
                    ) from e

            logger.info("索引更新完成: 索引类型数=%d, 节点数=%d", len(indexes), len(nodes))
            return indexes

        except Exception as e:
            if isinstance(e, IndexBuildError):
                raise
            logger.error("索引更新过程失败: %s", e, exc_info=True)
            msg = "索引更新过程失败"
            raise IndexBuildError(
                msg,
                details={"original_error": str(e)}
            ) from e

    def _create_knowledge_entries(
        self,
        chunks: list[DocumentChunk],
        operation_id: str,
        knowledge_base_id: str
    ) -> list[KnowledgeEntry]:
        """
        创建知识库条目

        Args:
            chunks: 文档块列表
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Returns:
            知识库条目列表
        """
        try:
            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=len(chunks),
                stage="creating_knowledge_entries"
            )

            knowledge_entries = []

            for i, chunk in enumerate(chunks):
                # 模拟创建知识库条目
                entry = KnowledgeEntry(
                    id=uuid.uuid4(),
                    title=f"知识条目: {chunk.id}",
                    summary=chunk.content[:100] if len(chunk.content) > 100 else chunk.content,
                    document_id=chunk.document_id,
                    chunk_id=chunk.id,
                    content=chunk.content,
                    metadata=chunk.metadata,
                    created_at=datetime.now()
                )

                knowledge_entries.append(entry)

                self._logger.log_progress_update(
                    operation_id=operation_id,
                    knowledge_base_id=knowledge_base_id,
                    current=i + 1,
                    total=len(chunks),
                    stage="creating_knowledge_entries",
                    chunk_id=chunk.id
                )

            return knowledge_entries

        except Exception as e:
            msg = "创建知识库条目失败"
            raise KnowledgeBaseServiceError(
                msg,
                details={"original_error": str(e)}
            )

    def _initialize_components(self, operation_id: str, knowledge_base_id: str) -> None:
        """
        初始化组件

        Args:
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Raises:
            ConfigurationError: 组件初始化失败时抛出
        """
        try:
            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=1,
                stage="initializing_components"
            )

            # 模拟组件初始化
            # 在实际实现中,这里会初始化各种组件,如向量数据库,索引等

            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=1,
                total=1,
                stage="initializing_components"
            )

        except Exception as e:
            msg = "组件初始化失败"
            raise ConfigurationError(
                msg,
                details={"original_error": str(e)}
            )

    def get_knowledge_base_info(self, knowledge_base_id: str) -> dict[str, Any] | None:
        """
        获取知识库信息

        Args:
            knowledge_base_id: 知识库ID

        Returns:
            知识库信息,如果不存在则返回None
        """
        if knowledge_base_id not in self._knowledge_bases:
            return None

        kb = self._knowledge_bases[knowledge_base_id]
        return {
            "id": kb["id"],
            "document_count": len(kb["documents"]),
            "chunk_count": len(kb["chunks"]),
            "index_count": len(kb["indexes"]),
            "created_at": kb["created_at"],
            "updated_at": kb["updated_at"]
        }

    def list_knowledge_bases(self) -> list[dict[str, Any]]:
        """
        列出所有知识库

        Returns:
            知识库信息列表
        """
        return [
            self.get_knowledge_base_info(kb_id)
            for kb_id in self._knowledge_bases
        ]
