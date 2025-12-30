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
from typing import Any

from src.application.services.indexing_progress_service import IndexingProgressService
from src.domain.document.document import Document, DocumentFormat
from src.domain.document.preprocessed_document import (
    CleaningLevel,
    PreprocessedDocument,
)
from src.domain.knowledge_base.document_chunk import DocumentChunk
from src.domain.knowledge_base.knowledge_entry import KnowledgeEntry
from src.shared.utils.logging import get_logger

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


class KnowledgeBaseService:
    """知识库服务"""

    def __init__(self, progress_service: IndexingProgressService):
        """
        初始化知识库服务

        Args:
            progress_service: 索引进度服务
        """
        self.progress_service = progress_service
        self._knowledge_bases: dict[str, dict[str, Any]] = {}
        self._logger = KnowledgeBaseLogger()

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

            # 模拟查询过程
            # 在实际实现中,这里会使用向量索引或其他检索方法
            results = []
            for i, chunk in enumerate(knowledge_base["chunks"][:top_k]):
                results.append({
                    "chunk_id": chunk.id,
                    "content": chunk.content[:200] + "..." if len(chunk.content) > 200 else chunk.content,
                    "score": 1.0 - i * 0.1,  # 模拟相似度分数
                    "metadata": chunk.metadata
                })

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
        try:
            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=len(documents),
                stage="loading_documents"
            )

            loaded_documents = []
            for i, doc in enumerate(documents):
                try:
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

                        self._logger.log_progress_update(
                            operation_id=operation_id,
                            knowledge_base_id=knowledge_base_id,
                            current=i + 1,
                            total=len(documents),
                            stage="loading_documents",
                            document_id=str(domain_doc.id)
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
                            raise DocumentLoadError(
                                msg,
                                document_path=doc.file_path,
                                details={"document_id": str(doc.id)}
                            )

                        loaded_documents.append(doc)

                        self._logger.log_progress_update(
                            operation_id=operation_id,
                            knowledge_base_id=knowledge_base_id,
                            current=i + 1,
                            total=len(documents),
                            stage="loading_documents",
                            document_id=str(doc.id)
                        )

                except Exception as e:
                    if isinstance(e, DocumentLoadError):
                        raise
                    doc_id = getattr(doc, "id", getattr(doc, "page_content", "unknown")[:50])
                    msg = f"加载文档失败: {doc_id}"
                    raise DocumentLoadError(
                        msg,
                        document_path=str(getattr(doc, "file_path", getattr(doc, "metadata", {}).get("source", "unknown"))),
                        details={"original_error": str(e)}
                    )

            return loaded_documents

        except Exception as e:
            if isinstance(e, DocumentLoadError):
                raise
            msg = "文档加载过程失败"
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
        try:
            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=len(documents),
                stage="parsing_documents"
            )

            preprocessed_documents = []
            for i, doc in enumerate(documents):
                try:
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

                    self._logger.log_progress_update(
                        operation_id=operation_id,
                        knowledge_base_id=knowledge_base_id,
                        current=i + 1,
                        total=len(documents),
                        stage="parsing_documents",
                        document_id=str(doc.id)
                    )

                except Exception as e:
                    if isinstance(e, DocumentParseError):
                        raise
                    msg = f"解析文档失败: {doc.id}"
                    raise DocumentParseError(
                        msg,
                        document_id=str(doc.id),
                        details={"original_error": str(e)}
                    )

            return preprocessed_documents

        except Exception as e:
            if isinstance(e, DocumentParseError):
                raise
            msg = "文档解析过程失败"
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
        try:
            total_chunks_estimate = sum(len(doc.content) // chunk_size + 1 for doc in preprocessed_documents)

            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=total_chunks_estimate,
                stage="chunking_documents"
            )

            chunks = []
            chunk_id = 0

            for doc in preprocessed_documents:
                try:
                    # 模拟文档分块过程
                    content = doc.content
                    for i in range(0, len(content), chunk_size - chunk_overlap):
                        chunk_content = content[i:i + chunk_size]

                        chunk = DocumentChunk(
                            id=uuid.uuid4(),
                            document_id=doc.id,
                            chunk_index=i // (chunk_size - chunk_overlap),
                            content=chunk_content,
                            start_position=i,
                            end_position=min(i + chunk_size, len(content)),
                            section_path="1",  # 默认章节路径
                            metadata={
                                "document_id": str(doc.id),
                                "document_title": doc.title,
                                "source": "knowledge_base_service"
                            }
                        )

                        chunks.append(chunk)
                        chunk_id += 1

                        self._logger.log_progress_update(
                            operation_id=operation_id,
                            knowledge_base_id=knowledge_base_id,
                            current=len(chunks),
                            total=total_chunks_estimate,
                            stage="chunking_documents",
                            document_id=str(doc.id),
                            chunk_index=chunk.chunk_index
                        )

                except Exception as e:
                    msg = f"分块文档失败: {doc.id}"
                    raise DocumentParseError(
                        msg,
                        document_id=str(doc.id),
                        details={"original_error": str(e)}
                    )

            return chunks

        except Exception as e:
            if isinstance(e, DocumentParseError):
                raise
            msg = "文档分块过程失败"
            raise DocumentParseError(
                msg,
                details={"original_error": str(e)}
            )

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
            索引字典

        Raises:
            IndexBuildError: 索引构建失败时抛出
        """
        try:
            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=3,  # 假设有3种索引类型
                stage="building_indexes"
            )

            indexes = {}

            # 模拟构建向量索引
            try:
                indexes["vector_index"] = {
                    "type": "vector",
                    "size": len(chunks),
                    "dimension": 768,  # 模拟向量维度
                    "created_at": datetime.now()
                }

                self._logger.log_progress_update(
                    operation_id=operation_id,
                    knowledge_base_id=knowledge_base_id,
                    current=1,
                    total=3,
                    stage="building_indexes",
                    index_type="vector"
                )

            except Exception as e:
                msg = "构建向量索引失败"
                raise IndexBuildError(
                    msg,
                    index_type="vector",
                    details={"original_error": str(e)}
                )

            # 模拟构建全文索引
            try:
                indexes["fulltext_index"] = {
                    "type": "fulltext",
                    "size": len(chunks),
                    "created_at": datetime.now()
                }

                self._logger.log_progress_update(
                    operation_id=operation_id,
                    knowledge_base_id=knowledge_base_id,
                    current=2,
                    total=3,
                    stage="building_indexes",
                    index_type="fulltext"
                )

            except Exception as e:
                msg = "构建全文索引失败"
                raise IndexBuildError(
                    msg,
                    index_type="fulltext",
                    details={"original_error": str(e)}
                )

            # 模拟构建元数据索引
            try:
                indexes["metadata_index"] = {
                    "type": "metadata",
                    "size": len(chunks),
                    "created_at": datetime.now()
                }

                self._logger.log_progress_update(
                    operation_id=operation_id,
                    knowledge_base_id=knowledge_base_id,
                    current=3,
                    total=3,
                    stage="building_indexes",
                    index_type="metadata"
                )

            except Exception as e:
                msg = "构建元数据索引失败"
                raise IndexBuildError(
                    msg,
                    index_type="metadata",
                    details={"original_error": str(e)}
                )

            return indexes

        except Exception as e:
            if isinstance(e, IndexBuildError):
                raise
            msg = "索引构建过程失败"
            raise IndexBuildError(
                msg,
                details={"original_error": str(e)}
            )

    def _update_indexes(
        self,
        chunks: list[DocumentChunk],
        operation_id: str,
        knowledge_base_id: str
    ) -> dict[str, Any]:
        """
        更新索引

        Args:
            chunks: 文档块列表
            operation_id: 操作ID
            knowledge_base_id: 知识库ID

        Returns:
            更新后的索引字典

        Raises:
            IndexBuildError: 索引更新失败时抛出
        """
        try:
            self._logger.log_progress_update(
                operation_id=operation_id,
                knowledge_base_id=knowledge_base_id,
                current=0,
                total=3,  # 假设有3种索引类型
                stage="updating_indexes"
            )

            indexes = {}

            # 模拟更新向量索引
            try:
                indexes["vector_index"] = {
                    "type": "vector",
                    "size": len(chunks),
                    "dimension": 768,
                    "updated_at": datetime.now()
                }

                self._logger.log_progress_update(
                    operation_id=operation_id,
                    knowledge_base_id=knowledge_base_id,
                    current=1,
                    total=3,
                    stage="updating_indexes",
                    index_type="vector"
                )

            except Exception as e:
                msg = "更新向量索引失败"
                raise IndexBuildError(
                    msg,
                    index_type="vector",
                    details={"original_error": str(e)}
                )

            # 模拟更新全文索引
            try:
                indexes["fulltext_index"] = {
                    "type": "fulltext",
                    "size": len(chunks),
                    "updated_at": datetime.now()
                }

                self._logger.log_progress_update(
                    operation_id=operation_id,
                    knowledge_base_id=knowledge_base_id,
                    current=2,
                    total=3,
                    stage="updating_indexes",
                    index_type="fulltext"
                )

            except Exception as e:
                msg = "更新全文索引失败"
                raise IndexBuildError(
                    msg,
                    index_type="fulltext",
                    details={"original_error": str(e)}
                )

            # 模拟更新元数据索引
            try:
                indexes["metadata_index"] = {
                    "type": "metadata",
                    "size": len(chunks),
                    "updated_at": datetime.now()
                }

                self._logger.log_progress_update(
                    operation_id=operation_id,
                    knowledge_base_id=knowledge_base_id,
                    current=3,
                    total=3,
                    stage="updating_indexes",
                    index_type="metadata"
                )

            except Exception as e:
                msg = "更新元数据索引失败"
                raise IndexBuildError(
                    msg,
                    index_type="metadata",
                    details={"original_error": str(e)}
                )

            return indexes

        except Exception as e:
            if isinstance(e, IndexBuildError):
                raise
            msg = "索引更新过程失败"
            raise IndexBuildError(
                msg,
                details={"original_error": str(e)}
            )

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
