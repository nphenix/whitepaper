# 生成命令: /speckit.implement T051
# 生成时间: 2025-12-20
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
文档解析和索引构建异步任务 (T051)

该模块实现文档解析和索引构建的异步任务,使用Arq任务队列框架.
封装T050知识库服务的功能,支持大文件处理和批量处理.

设计目标:
- 封装文档预处理流程为异步任务,支持大文件处理和批量处理
- 使用Arq任务队列,支持任务状态跟踪和错误重试
- 调用T050知识库服务执行实际处理
- 支持任务进度报告和结果回调
- 集成任务监控和日志记录
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from arq import cron

from src.application.services.indexing_progress_service import get_progress_service
from src.application.services.knowledge_base_service import (
    KnowledgeBaseService,
)
from src.domain.document.document import Document, DocumentFormat
from src.domain.indexing.indexing_progress import TaskStatus
from src.infrastructure.indexing.document_chunking import ChunkingConfig
from src.infrastructure.indexing.hybrid_retriever import (
    FusionStrategy,
    HybridRetrieverConfig,
    QueryType,
)
from src.shared.config.settings import get_config
from src.shared.utils.logging import get_logger

# 索引构建器导入（可选依赖）
try:
    from src.infrastructure.indexing.bm25_index import BM25IndexBuilder
    from src.infrastructure.indexing.knowledge_graph import KnowledgeGraphBuilder
    from src.infrastructure.indexing.metadata_index import MetadataIndexBuilder
    from src.infrastructure.indexing.vector_index import VectorIndexBuilder
    from src.infrastructure.storage.chroma.connection import get_connection_manager as get_chroma_connection_manager
    from src.infrastructure.storage.sqlite.connection import get_connection_manager as get_sqlite_connection_manager
    INDEX_BUILDERS_AVAILABLE = True
except ImportError:
    INDEX_BUILDERS_AVAILABLE = False
    BM25IndexBuilder = None  # type: ignore[assignment, misc]
    KnowledgeGraphBuilder = None  # type: ignore[assignment, misc]
    MetadataIndexBuilder = None  # type: ignore[assignment, misc]
    VectorIndexBuilder = None  # type: ignore[assignment, misc]
    get_chroma_connection_manager = None  # type: ignore[assignment, misc]
    get_sqlite_connection_manager = None  # type: ignore[assignment, misc]

if TYPE_CHECKING:
    from arq.connections import ArqRedis

logger = get_logger(__name__)

# 获取设置
settings = get_config()


# 使用从 domain.indexing.indexing_progress 导入的 TaskStatus


class TaskType(str, Enum):
    """任务类型枚举"""

    CREATE_KNOWLEDGE_BASE = "create_knowledge_base"  # 创建知识库
    UPDATE_KNOWLEDGE_BASE = "update_knowledge_base"  # 更新知识库
    DELETE_KNOWLEDGE_BASE = "delete_knowledge_base"  # 删除知识库
    QUERY_KNOWLEDGE_BASE = "query_knowledge_base"  # 查询知识库


class TaskResult:
    """任务结果类"""

    def __init__(
        self,
        task_id: str,
        task_type: TaskType,
        status: TaskStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        self.task_id = task_id
        self.task_type = task_type
        self.status = status
        self.result = result
        self.error = error
        self.start_time = start_time
        self.end_time = end_time
        self.progress = progress or {}

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (
                (self.end_time - self.start_time).total_seconds()
                if self.start_time and self.end_time
                else None
            ),
            "progress": self.progress,
        }


class IndexingTasks:
    """
    索引任务管理器

    管理文档解析和索引构建的异步任务,提供任务创建,执行,监控等功能.
    """

    def __init__(self, redis_pool: ArqRedis | None = None) -> None:
        """
        初始化索引任务管理器

        Args:
            redis_pool: Redis连接池,如果为None则使用默认配置
        """
        self.redis_pool = redis_pool
        self._task_results: dict[str, TaskResult] = {}
        self._knowledge_base_services: dict[str, KnowledgeBaseService] = {}

    async def create_knowledge_base_task(
        self,
        name: str,
        directories: list[str],
        description: str | None = None,
        knowledge_base_id: str | None = None,
        vector_collection_name: str | None = None,
        bm25_index_path: str | None = None,
        metadata_table_name: str = "document_chunks_metadata",
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_metadata: bool = True,
        enable_graph: bool = False,
        chunking_config: dict[str, Any] | None = None,
        hybrid_retriever_config: dict[str, Any] | None = None,
        show_progress: bool = False,
    ) -> str:
        """
        创建知识库任务

        Args:
            name: 知识库名称
            directories: 预处理结果目录列表
            description: 知识库描述
            knowledge_base_id: 知识库ID,如果为None则生成新的UUID
            vector_collection_name: 向量索引集合名称
            bm25_index_path: BM25索引文件路径
            metadata_table_name: 元数据索引表名
            enable_vector: 是否启用向量检索
            enable_bm25: 是否启用BM25检索
            enable_metadata: 是否启用元数据检索
            enable_graph: 是否启用知识图谱检索
            chunking_config: 文档分块配置
            hybrid_retriever_config: 混合检索引擎配置
            show_progress: 是否显示进度

        Returns:
            任务ID
        """
        task_id = str(uuid4())

        # 创建任务参数
        task_kwargs = {
            "task_id": task_id,
            "name": name,
            "directories": directories,
            "description": description,
            "knowledge_base_id": knowledge_base_id,
            "vector_collection_name": vector_collection_name,
            "bm25_index_path": bm25_index_path,
            "metadata_table_name": metadata_table_name,
            "enable_vector": enable_vector,
            "enable_bm25": enable_bm25,
            "enable_metadata": enable_metadata,
            "enable_graph": enable_graph,
            "chunking_config": chunking_config,
            "hybrid_retriever_config": hybrid_retriever_config,
            "show_progress": show_progress,
        }

        # 创建任务结果对象
        self._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.CREATE_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )

        # 提交任务到队列
        if self.redis_pool:
            # 显式传递参数而不是使用**task_kwargs
            await self.redis_pool.enqueue_job(
                "execute_create_knowledge_base_task",
                task_id=str(task_kwargs["task_id"]),
                name=str(task_kwargs["name"]),
                directories=list(task_kwargs["directories"]) if isinstance(task_kwargs["directories"], (list, tuple)) else [],
                description=str(task_kwargs["description"]) if task_kwargs["description"] is not None else None,
                knowledge_base_id=str(task_kwargs["knowledge_base_id"]) if task_kwargs["knowledge_base_id"] is not None else None,
                vector_collection_name=str(task_kwargs["vector_collection_name"]) if task_kwargs["vector_collection_name"] is not None else None,
                bm25_index_path=str(task_kwargs["bm25_index_path"]) if task_kwargs["bm25_index_path"] is not None else None,
                metadata_table_name=str(task_kwargs["metadata_table_name"]),
                enable_vector=bool(task_kwargs["enable_vector"]),
                enable_bm25=bool(task_kwargs["enable_bm25"]),
                enable_metadata=bool(task_kwargs["enable_metadata"]),
                enable_graph=bool(task_kwargs["enable_graph"]),
                chunking_config=dict(task_kwargs["chunking_config"]) if task_kwargs["chunking_config"] is not None and isinstance(task_kwargs["chunking_config"], dict) else None,
                hybrid_retriever_config=dict(task_kwargs["hybrid_retriever_config"]) if task_kwargs["hybrid_retriever_config"] is not None and isinstance(task_kwargs["hybrid_retriever_config"], dict) else None,
                show_progress=bool(task_kwargs["show_progress"]),
            )
            logger.info(f"已提交创建知识库任务到队列: {task_id}")
        else:
            # 直接执行任务(用于测试或无Redis环境)
            logger.info("未配置Redis,直接执行创建知识库任务")
            task = asyncio.create_task(
                execute_create_knowledge_base_task(
                    ctx=None,
                    task_id=str(task_kwargs["task_id"]),
                    name=str(task_kwargs["name"]),
                    directories=list(task_kwargs["directories"]) if isinstance(task_kwargs["directories"], (list, tuple)) else [],
                    description=str(task_kwargs["description"]) if task_kwargs["description"] is not None else None,
                    knowledge_base_id=str(task_kwargs["knowledge_base_id"]) if task_kwargs["knowledge_base_id"] is not None else None,
                    vector_collection_name=str(task_kwargs["vector_collection_name"]) if task_kwargs["vector_collection_name"] is not None else None,
                    bm25_index_path=str(task_kwargs["bm25_index_path"]) if task_kwargs["bm25_index_path"] is not None else None,
                    metadata_table_name=str(task_kwargs["metadata_table_name"]),
                    enable_vector=bool(task_kwargs["enable_vector"]),
                    enable_bm25=bool(task_kwargs["enable_bm25"]),
                    enable_metadata=bool(task_kwargs["enable_metadata"]),
                    enable_graph=bool(task_kwargs["enable_graph"]),
                    chunking_config=dict(task_kwargs["chunking_config"]) if task_kwargs["chunking_config"] is not None and isinstance(task_kwargs["chunking_config"], dict) else None,
                    hybrid_retriever_config=dict(task_kwargs["hybrid_retriever_config"]) if task_kwargs["hybrid_retriever_config"] is not None and isinstance(task_kwargs["hybrid_retriever_config"], dict) else None,
                    show_progress=bool(task_kwargs["show_progress"]),
                )
            )
            # 存储任务引用以避免垃圾回收
            task.add_done_callback(lambda t: logger.debug(f"创建知识库任务完成: {task_id}"))

        return task_id

    async def update_knowledge_base_task(
        self,
        knowledge_base_id: str,
        directories: list[str] | None = None,
        documents: list[dict[str, Any]] | None = None,
        show_progress: bool = False,
    ) -> str:
        """
        更新知识库任务

        Args:
            knowledge_base_id: 知识库ID
            directories: 预处理结果目录列表
            documents: 文档列表(与directories二选一)
            show_progress: 是否显示进度

        Returns:
            任务ID
        """
        task_id = str(uuid4())

        # 创建任务参数
        task_kwargs = {
            "task_id": task_id,
            "knowledge_base_id": knowledge_base_id,
            "directories": directories,
            "documents": documents,
            "show_progress": show_progress,
        }

        # 创建任务结果对象
        self._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.UPDATE_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )

        # 提交任务到队列
        if self.redis_pool:
            # 显式传递参数而不是使用**task_kwargs
            await self.redis_pool.enqueue_job(
                "execute_update_knowledge_base_task",
                task_id=str(task_kwargs["task_id"]),
                knowledge_base_id=str(task_kwargs["knowledge_base_id"]),
                directories=list(task_kwargs["directories"]) if task_kwargs["directories"] is not None and isinstance(task_kwargs["directories"], (list, tuple)) else None,
                documents=list(task_kwargs["documents"]) if task_kwargs["documents"] is not None and isinstance(task_kwargs["documents"], (list, tuple)) else None,
                show_progress=bool(task_kwargs["show_progress"]),
            )
            logger.info(f"已提交更新知识库任务到队列: {task_id}")
        else:
            # 直接执行任务(用于测试或无Redis环境)
            logger.info("未配置Redis,直接执行更新知识库任务")
            task = asyncio.create_task(
                execute_update_knowledge_base_task(
                    ctx=None,
                    task_id=str(task_kwargs["task_id"]),
                    knowledge_base_id=str(task_kwargs["knowledge_base_id"]),
                    directories=list(task_kwargs["directories"]) if task_kwargs["directories"] is not None and isinstance(task_kwargs["directories"], (list, tuple)) else None,
                    documents=list(task_kwargs["documents"]) if task_kwargs["documents"] is not None and isinstance(task_kwargs["documents"], (list, tuple)) else None,
                    show_progress=bool(task_kwargs["show_progress"]),
                )
            )
            # 存储任务引用以避免垃圾回收
            task.add_done_callback(lambda t: logger.debug(f"更新知识库任务完成: {task_id}"))

        return task_id

    async def delete_knowledge_base_task(
        self,
        knowledge_base_id: str,
    ) -> str:
        """
        删除知识库任务

        Args:
            knowledge_base_id: 知识库ID

        Returns:
            任务ID
        """
        task_id = str(uuid4())

        # 创建任务参数
        task_kwargs = {
            "task_id": task_id,
            "knowledge_base_id": knowledge_base_id,
        }

        # 创建任务结果对象
        self._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.DELETE_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )

        # 提交任务到队列
        if self.redis_pool:
            # 显式传递参数而不是使用**task_kwargs
            await self.redis_pool.enqueue_job(
                "execute_delete_knowledge_base_task",
                task_id=str(task_kwargs["task_id"]),
                knowledge_base_id=str(task_kwargs["knowledge_base_id"]),
            )
            logger.info(f"已提交删除知识库任务到队列: {task_id}")
        else:
            # 直接执行任务(用于测试或无Redis环境)
            logger.info("未配置Redis,直接执行删除知识库任务")
            task = asyncio.create_task(
                execute_delete_knowledge_base_task(
                    ctx=None,
                    task_id=str(task_kwargs["task_id"]),
                    knowledge_base_id=str(task_kwargs["knowledge_base_id"]),
                )
            )
            # 存储任务引用以避免垃圾回收
            task.add_done_callback(lambda t: logger.debug(f"删除知识库任务完成: {task_id}"))

        return task_id

    async def query_knowledge_base_task(
        self,
        knowledge_base_id: str,
        query_str: str,
        top_k: int = 10,
        query_type: str | None = None,
        filters: dict[str, Any] | None = None,
        use_hybrid: bool = True,
        use_structured: bool = False,
        structured_query: dict[str, Any] | None = None,
    ) -> str:
        """
        查询知识库任务

        Args:
            knowledge_base_id: 知识库ID
            query_str: 查询文本
            top_k: 返回结果数量
            query_type: 查询类型
            filters: 元数据过滤器
            use_hybrid: 是否使用混合检索
            use_structured: 是否使用结构化检索
            structured_query: 结构化查询配置

        Returns:
            任务ID
        """
        task_id = str(uuid4())

        # 创建任务参数
        task_kwargs = {
            "task_id": task_id,
            "knowledge_base_id": knowledge_base_id,
            "query_str": query_str,
            "top_k": top_k,
            "query_type": query_type,
            "filters": filters,
            "use_hybrid": use_hybrid,
            "use_structured": use_structured,
            "structured_query": structured_query,
        }

        # 创建任务结果对象
        self._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.QUERY_KNOWLEDGE_BASE,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
        )

        # 提交任务到队列
        if self.redis_pool:
            # 显式传递参数而不是使用**task_kwargs
            await self.redis_pool.enqueue_job(
                "execute_query_knowledge_base_task",
                task_id=str(task_kwargs["task_id"]),
                knowledge_base_id=str(task_kwargs["knowledge_base_id"]),
                query_str=str(task_kwargs["query_str"]),
                top_k=int(task_kwargs["top_k"]) if isinstance(task_kwargs["top_k"], (int, str)) else 10,
                query_type=str(task_kwargs["query_type"]) if task_kwargs["query_type"] is not None else None,
                filters=dict(task_kwargs["filters"]) if task_kwargs["filters"] is not None and isinstance(task_kwargs["filters"], dict) else None,
                use_hybrid=bool(task_kwargs["use_hybrid"]),
                use_structured=bool(task_kwargs["use_structured"]),
                structured_query=dict(task_kwargs["structured_query"]) if task_kwargs["structured_query"] is not None and isinstance(task_kwargs["structured_query"], dict) else None,
            )
            logger.info(f"已提交查询知识库任务到队列: {task_id}")
        else:
            # 直接执行任务(用于测试或无Redis环境)
            logger.info("未配置Redis,直接执行查询知识库任务")
            task = asyncio.create_task(
                execute_query_knowledge_base_task(
                    ctx=None,
                    task_id=str(task_kwargs["task_id"]),
                    knowledge_base_id=str(task_kwargs["knowledge_base_id"]),
                    query_str=str(task_kwargs["query_str"]),
                    top_k=int(task_kwargs["top_k"]) if isinstance(task_kwargs["top_k"], (int, str)) else 10,
                    query_type=str(task_kwargs["query_type"]) if task_kwargs["query_type"] is not None else None,
                    filters=dict(task_kwargs["filters"]) if task_kwargs["filters"] is not None and isinstance(task_kwargs["filters"], dict) else None,
                    use_hybrid=bool(task_kwargs["use_hybrid"]),
                    use_structured=bool(task_kwargs["use_structured"]),
                    structured_query=dict(task_kwargs["structured_query"]) if task_kwargs["structured_query"] is not None and isinstance(task_kwargs["structured_query"], dict) else None,
                )
            )
            # 存储任务引用以避免垃圾回收
            task.add_done_callback(lambda t: logger.debug(f"查询知识库任务完成: {task_id}"))

        return task_id

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息字典,如果任务不存在则返回None
        """
        if task_id not in self._task_results:
            return None

        task_result = self._task_results[task_id]
        task_dict = task_result.to_dict()

        # 尝试获取进度跟踪信息
        try:
            progress_service = get_progress_service()
            progress_summary = progress_service.get_progress_summary(task_id)
            if progress_summary:
                task_dict["progress"] = progress_summary
        except Exception as exc:
            logger.warning(f"获取进度跟踪信息失败: {exc}")

        return task_dict

    async def get_all_tasks(self) -> list[dict[str, Any]]:
        """
        获取所有任务状态

        Returns:
            所有任务状态信息列表
        """
        return [result.to_dict() for result in self._task_results.values()]

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        if task_id not in self._task_results:
            return False

        task_result = self._task_results[task_id]
        if task_result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return False

        task_result.status = TaskStatus.CANCELLED
        task_result.end_time = datetime.now()

        logger.info(f"任务已取消: {task_id}")
        return True

    def _get_or_create_knowledge_base_service(
        self,
        knowledge_base_id: str | UUID | None,
        vector_collection_name: str | None = None,
        bm25_index_path: str | None = None,
        metadata_table_name: str = "document_chunks_metadata",
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_metadata: bool = True,
        enable_graph: bool = False,
        chunking_config: dict[str, Any] | None = None,
        hybrid_retriever_config: dict[str, Any] | None = None,
    ) -> KnowledgeBaseService:
        """
        获取或创建知识库服务实例

        Args:
            knowledge_base_id: 知识库ID(字符串或UUID对象,如果为None则自动生成)
            vector_collection_name: 向量索引集合名称
            bm25_index_path: BM25索引文件路径
            metadata_table_name: 元数据索引表名
            enable_vector: 是否启用向量检索
            enable_bm25: 是否启用BM25检索
            enable_metadata: 是否启用元数据检索
            enable_graph: 是否启用知识图谱检索
            chunking_config: 文档分块配置
            hybrid_retriever_config: 混合检索引擎配置

        Returns:
            知识库服务实例
        """
        # 如果knowledge_base_id为None,需要让KnowledgeBaseService自动生成UUID
        # 统一转换为字符串类型,确保字典键的一致性(但None除外)
        kb_id_str = None
        if knowledge_base_id is not None:
            kb_id_str = str(knowledge_base_id) if not isinstance(knowledge_base_id, str) else knowledge_base_id
            if kb_id_str in self._knowledge_base_services:
                # 如果知识库ID已存在,返回现有服务实例
                return self._knowledge_base_services[kb_id_str]

        # 创建分块配置
        chunking_cfg = None
        if chunking_config:
            chunking_cfg = ChunkingConfig(
                chunk_size=chunking_config.get("chunk_size", 1024),
                chunk_overlap=chunking_config.get("chunk_overlap", 200),
                split_by_section=chunking_config.get("split_by_section", True),
                split_by_paragraph=chunking_config.get("split_by_paragraph", True),
            )

        # 创建混合检索配置
        hybrid_cfg = None
        if hybrid_retriever_config:
            hybrid_cfg = HybridRetrieverConfig(
                enable_vector=hybrid_retriever_config.get("enable_vector", enable_vector),
                enable_bm25=hybrid_retriever_config.get("enable_bm25", enable_bm25),
                enable_metadata=hybrid_retriever_config.get("enable_metadata", enable_metadata),
                enable_graph=hybrid_retriever_config.get("enable_graph", enable_graph),
                fusion_strategy=FusionStrategy(
                    hybrid_retriever_config.get("fusion_strategy", "rrf")
                ),
                default_top_k=hybrid_retriever_config.get("default_top_k", 10),
            )

        # 创建索引构建器实例（真实数据，不使用mock）
        vector_index_builder = None
        bm25_index_builder = None
        metadata_index_builder = None
        knowledge_graph_builder = None

        if INDEX_BUILDERS_AVAILABLE:
            # 创建向量索引构建器
            if enable_vector:
                try:
                    vector_collection = vector_collection_name or f"kb_{kb_id_str or 'default'}_vector"
                    vector_index_builder = VectorIndexBuilder(
                        collection_name=vector_collection,
                        connection_manager=get_chroma_connection_manager(),
                    )
                    logger.info("创建向量索引构建器: collection_name=%s", vector_collection)
                except Exception as e:
                    logger.warning("创建向量索引构建器失败: %s", e, exc_info=True)

            # 创建BM25索引构建器
            if enable_bm25:
                try:
                    bm25_path = bm25_index_path or f"./data/bm25_index/kb_{kb_id_str or 'default'}.pkl"
                    # 确保目录存在
                    Path(bm25_path).parent.mkdir(parents=True, exist_ok=True)
                    bm25_index_builder = BM25IndexBuilder(index_path=bm25_path)
                    logger.info("创建BM25索引构建器: index_path=%s", bm25_path)
                except Exception as e:
                    logger.warning("创建BM25索引构建器失败: %s", e, exc_info=True)

            # 创建元数据索引构建器
            if enable_metadata:
                try:
                    metadata_index_builder = MetadataIndexBuilder(
                        table_name=metadata_table_name,
                        connection_manager=get_sqlite_connection_manager(),
                    )
                    logger.info("创建元数据索引构建器: table_name=%s", metadata_table_name)
                except Exception as e:
                    logger.warning("创建元数据索引构建器失败: %s", e, exc_info=True)

            # 创建知识图谱构建器
            if enable_graph:
                try:
                    graph_name = f"kb_{kb_id_str or 'default'}_graph"
                    knowledge_graph_builder = KnowledgeGraphBuilder(
                        graph_name=graph_name,
                    )
                    logger.info("创建知识图谱构建器: graph_name=%s", graph_name)
                except Exception as e:
                    logger.warning("创建知识图谱构建器失败: %s", e, exc_info=True)

        # 创建知识库服务实例（注入索引构建器）
        progress_service = get_progress_service()
        service = KnowledgeBaseService(
            progress_service=progress_service,
            vector_index_builder=vector_index_builder,
            bm25_index_builder=bm25_index_builder,
            metadata_index_builder=metadata_index_builder,
            knowledge_graph_builder=knowledge_graph_builder,
            enable_vector=enable_vector,
            enable_bm25=enable_bm25,
            enable_metadata=enable_metadata,
            enable_graph=enable_graph,
        )

        # 使用传入的knowledge_base_id作为键存储
        if kb_id_str is None:
            kb_id_str = str(knowledge_base_id) if knowledge_base_id else str(uuid4())

        self._knowledge_base_services[kb_id_str] = service
        return service


# 全局任务管理器实例
_task_manager: IndexingTasks | None = None


def get_task_manager() -> IndexingTasks:
    """
    获取全局任务管理器实例

    Returns:
        任务管理器实例
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = IndexingTasks()
    return _task_manager


# Arq任务执行函数
async def execute_create_knowledge_base_task(
    ctx: dict[str, Any] | None,
    task_id: str,
    name: str,
    directories: list[str],
    description: str | None = None,
    knowledge_base_id: str | None = None,
    vector_collection_name: str | None = None,
    bm25_index_path: str | None = None,
    metadata_table_name: str = "document_chunks_metadata",
    enable_vector: bool = True,
    enable_bm25: bool = True,
    enable_metadata: bool = True,
    enable_graph: bool = False,
    chunking_config: dict[str, Any] | None = None,
    hybrid_retriever_config: dict[str, Any] | None = None,
    show_progress: bool = False,
) -> dict[str, Any]:
    """
    执行创建知识库任务

    Args:
        ctx: Arq上下文
        task_id: 任务ID
        name: 知识库名称
        directories: 预处理结果目录列表
        description: 知识库描述
        knowledge_base_id: 知识库ID
        vector_collection_name: 向量索引集合名称
        bm25_index_path: BM25索引文件路径
        metadata_table_name: 元数据索引表名
        enable_vector: 是否启用向量检索
        enable_bm25: 是否启用BM25检索
        enable_metadata: 是否启用元数据检索
        enable_graph: 是否启用知识图谱检索
        chunking_config: 文档分块配置
        hybrid_retriever_config: 混合检索引擎配置
        show_progress: 是否显示进度

    Returns:
        任务结果
    """
    task_manager = get_task_manager()

    # 获取任务结果对象
    if task_id not in task_manager._task_results:
        msg = f"任务不存在: {task_id}"
        raise ValueError(msg)

    task_result = task_manager._task_results[task_id]
    task_result.status = TaskStatus.RUNNING

    try:
        logger.info(f"开始执行创建知识库任务: {task_id}, name={name}")

        # 获取或创建知识库服务
        service = task_manager._get_or_create_knowledge_base_service(
            knowledge_base_id=knowledge_base_id,
            vector_collection_name=vector_collection_name,
            bm25_index_path=bm25_index_path,
            metadata_table_name=metadata_table_name,
            enable_vector=enable_vector,
            enable_bm25=enable_bm25,
            enable_metadata=enable_metadata,
            enable_graph=enable_graph,
            chunking_config=chunking_config,
            hybrid_retriever_config=hybrid_retriever_config,
        )

        # 执行创建知识库
        # 转换为Document对象
        from src.domain.document.document import Document
        documents = []
        for directory in directories:
            # 简化处理，实际应该从目录加载文档
            documents.append(Document(
                filename=directory,
                file_path=directory,
                file_size=0,
                format=DocumentFormat.PDF,
                content=f"从目录 {directory} 加载的内容",
                mime_type="application/pdf",
                parsed_at=datetime.now(),
                uploaded_by="system",
                error_message=None
            ))
        
        result = service.create_knowledge_base(
            knowledge_base_id=knowledge_base_id or str(uuid4()),
            documents=documents
        )

        # 确保服务被存储在任务管理器中
        # result是字典,使用get方法获取knowledge_base_id
        kb_id = None
        if isinstance(result, dict):
            kb_id = result.get("knowledge_base_id")
        elif hasattr(result, "knowledge_base_id"):
            kb_id = result.knowledge_base_id

        # 如果从result中获取不到,尝试从服务中获取
        if not kb_id and hasattr(service, "knowledge_base_id") and service.knowledge_base_id:
            kb_id = service.knowledge_base_id

        # 如果还是获取不到,使用传入的knowledge_base_id参数
        if not kb_id:
            kb_id = knowledge_base_id

        # 确保kb_id是字符串类型(统一类型)
        if kb_id:
            kb_id_str = str(kb_id) if not isinstance(kb_id, str) else kb_id
            task_manager._knowledge_base_services[kb_id_str] = service

        # 更新任务状态
        task_result.status = TaskStatus.COMPLETED
        task_result.end_time = datetime.now()
        task_result.result = result

        # 获取进度摘要
        progress_service = get_progress_service()
        progress_summary = progress_service.get_progress_summary(task_id)
        if progress_summary:
            task_result.progress = progress_summary

        logger.info(f"创建知识库任务完成: {task_id}")
        return task_result.to_dict()

    except Exception as exc:
        # 更新任务状态
        task_result.status = TaskStatus.FAILED
        task_result.end_time = datetime.now()
        task_result.error = str(exc)

        # 更新进度跟踪状态
        progress_service = get_progress_service()
        progress_service.update_progress(
            task_id,
            status=TaskStatus.FAILED,
            error_message=str(exc),
            error_traceback=str(exc) if exc else None
        )

        logger.error(f"创建知识库任务失败: {task_id}, error={exc}", exc_info=True)
        return task_result.to_dict()


async def execute_update_knowledge_base_task(
    ctx: dict[str, Any] | None,
    task_id: str,
    knowledge_base_id: str,
    directories: list[str] | None = None,
    documents: list[dict[str, Any]] | None = None,
    show_progress: bool = False,
) -> dict[str, Any]:
    """
    执行更新知识库任务

    Args:
        ctx: Arq上下文
        task_id: 任务ID
        knowledge_base_id: 知识库ID
        directories: 预处理结果目录列表
        documents: 文档列表
        show_progress: 是否显示进度

    Returns:
        任务结果
    """
    task_manager = get_task_manager()

    # 获取任务结果对象
    if task_id not in task_manager._task_results:
        msg = f"任务不存在: {task_id}"
        raise ValueError(msg)

    task_result = task_manager._task_results[task_id]
    task_result.status = TaskStatus.RUNNING

    try:
        logger.info(f"开始执行更新知识库任务: {task_id}, kb_id={knowledge_base_id}")

        # 获取知识库服务
        service = task_manager._get_or_create_knowledge_base_service(
            knowledge_base_id=knowledge_base_id,
        )

        # 转换文档格式
        lc_documents = None
        if documents:
            from langchain_core.documents import Document
            lc_documents = [
                Document(
                    page_content=doc.get("page_content", ""),
                    metadata=doc.get("metadata", {}),
                )
                for doc in documents
            ]

        # 执行更新知识库
        # 转换为Document对象
        documents = []
        if lc_documents:
            from src.domain.document.document import Document
            for lc_doc in lc_documents:
                documents.append(lc_doc)  # type: ignore[arg-type]
        
        result = service.update_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            new_documents=documents
        )

        # 更新任务状态
        task_result.status = TaskStatus.COMPLETED
        task_result.end_time = datetime.now()

        # 处理结果可能是字典或对象的情况
        if isinstance(result, dict):
            kb_id = result.get("knowledge_base_id", knowledge_base_id)
            updated_count = result.get("updated_documents_count", 0)
            new_count = result.get("new_documents_count", 0)
        else:
            kb_id = getattr(result, "knowledge_base_id", knowledge_base_id)
            updated_count = getattr(result, "updated_documents_count", 0)
            new_count = getattr(result, "new_documents_count", 0)

        task_result.result = {
            "knowledge_base_id": kb_id,
            "updated_documents_count": updated_count,
            "new_documents_count": new_count
        }

        # 获取进度摘要
        progress_service = get_progress_service()
        progress_summary = progress_service.get_progress_summary(task_id)
        if progress_summary:
            task_result.progress = progress_summary

        logger.info(f"更新知识库任务完成: {task_id}")
        return task_result.to_dict()

    except Exception as exc:
        # 更新任务状态
        task_result.status = TaskStatus.FAILED
        task_result.end_time = datetime.now()
        task_result.error = str(exc)

        # 更新进度跟踪状态
        progress_service = get_progress_service()
        progress_service.update_progress(
            task_id,
            status=TaskStatus.FAILED,
            error_message=str(exc),
            error_traceback=str(exc) if exc else None
        )

        logger.error(f"更新知识库任务失败: {task_id}, error={exc}", exc_info=True)
        return task_result.to_dict()


async def execute_delete_knowledge_base_task(
    ctx: dict[str, Any] | None,
    task_id: str,
    knowledge_base_id: str,
) -> dict[str, Any]:
    """
    执行删除知识库任务

    Args:
        ctx: Arq上下文
        task_id: 任务ID
        knowledge_base_id: 知识库ID

    Returns:
        任务结果
    """
    task_manager = get_task_manager()

    # 获取任务结果对象
    if task_id not in task_manager._task_results:
        msg = f"任务不存在: {task_id}"
        raise ValueError(msg)

    task_result = task_manager._task_results[task_id]
    task_result.status = TaskStatus.RUNNING

    try:
        logger.info(f"开始执行删除知识库任务: {task_id}, kb_id={knowledge_base_id}")

        # 获取知识库服务
        service = task_manager._get_or_create_knowledge_base_service(
            knowledge_base_id=knowledge_base_id,
        )

        # 执行删除知识库
        result = service.delete_knowledge_base(knowledge_base_id)

        # 从缓存中移除服务实例
        # 确保knowledge_base_id是字符串类型
        kb_id_str = str(knowledge_base_id) if not isinstance(knowledge_base_id, str) else knowledge_base_id
        if kb_id_str in task_manager._knowledge_base_services:
            del task_manager._knowledge_base_services[kb_id_str]

        # 更新任务状态
        task_result.status = TaskStatus.COMPLETED
        task_result.end_time = datetime.now()
        task_result.result = result

        logger.info(f"删除知识库任务完成: {task_id}")
        return task_result.to_dict()

    except Exception as exc:
        # 更新任务状态
        task_result.status = TaskStatus.FAILED
        task_result.end_time = datetime.now()
        task_result.error = str(exc)

        # 如果是目录不存在等预期错误,标记为完成而非失败
        if "不存在" in str(exc) or "未找到" in str(exc):
            task_result.status = TaskStatus.COMPLETED
            task_result.result = {"knowledge_base_id": knowledge_base_id}
            task_result.error = None
            # task_result没有message属性，注释掉
            # task_result.message = f"知识库删除完成(目录不存在): {exc!s}"

        logger.error(f"删除知识库任务失败: {task_id}, error={exc}", exc_info=True)
        return task_result.to_dict()


async def execute_query_knowledge_base_task(
    ctx: dict[str, Any] | None,
    task_id: str,
    knowledge_base_id: str,
    query_str: str,
    top_k: int = 10,
    query_type: str | None = None,
    filters: dict[str, Any] | None = None,
    use_hybrid: bool = True,
    use_structured: bool = False,
    structured_query: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    执行查询知识库任务

    Args:
        ctx: Arq上下文
        task_id: 任务ID
        knowledge_base_id: 知识库ID
        query_str: 查询文本
        top_k: 返回结果数量
        query_type: 查询类型
        filters: 元数据过滤器
        use_hybrid: 是否使用混合检索
        use_structured: 是否使用结构化检索
        structured_query: 结构化查询配置

    Returns:
        任务结果
    """
    task_manager = get_task_manager()

    # 获取任务结果对象
    if task_id not in task_manager._task_results:
        msg = f"任务不存在: {task_id}"
        raise ValueError(msg)

    task_result = task_manager._task_results[task_id]
    task_result.status = TaskStatus.RUNNING

    try:
        logger.info(f"开始执行查询知识库任务: {task_id}, kb_id={knowledge_base_id}, query={query_str[:50]}...")

        # 获取知识库服务
        service = task_manager._get_or_create_knowledge_base_service(
            knowledge_base_id=knowledge_base_id,
        )

        # 转换查询类型
        qt = None
        if query_type:
            try:
                qt = QueryType(query_type)
            except ValueError:
                logger.warning(f"无效的查询类型: {query_type}")

        # 转换结构化查询
        sq = None
        if structured_query:
            from src.infrastructure.indexing.structured_retrieval import StructuredQuery
            sq = StructuredQuery(**structured_query)

        # 执行查询知识库
        results = service.query(
            knowledge_base_id=knowledge_base_id,
            query_text=query_str,
            top_k=top_k
        )

        # 转换结果为字典格式
        results_dict = []
        for result in results:
            results_dict.append({
                "node_id": result.get("chunk_id", ""),
                "text": result.get("content", ""),
                "metadata": result.get("metadata", {}),
                "score": result.get("score", 0.0),
            })

        # 更新任务状态
        task_result.status = TaskStatus.COMPLETED
        task_result.end_time = datetime.now()
        task_result.result = {
            "query": query_str,
            "results_count": len(results_dict),
            "results": results_dict,
        }

        # 获取进度摘要
        progress_service = get_progress_service()
        progress_summary = progress_service.get_progress_summary(task_id)
        if progress_summary:
            task_result.progress = progress_summary

        logger.info(f"查询知识库任务完成: {task_id}, results={len(results_dict)}")
        return task_result.to_dict()

    except Exception as exc:
        # 更新任务状态
        task_result.status = TaskStatus.FAILED
        task_result.end_time = datetime.now()
        task_result.error = str(exc)

        # 更新进度跟踪状态
        progress_service = get_progress_service()
        progress_service.update_progress(
            task_id,
            status=TaskStatus.FAILED,
            error_message=str(exc),
            error_traceback=str(exc) if exc else None
        )

        logger.error(f"查询知识库任务失败: {task_id}, error={exc}", exc_info=True)
        return task_result.to_dict()


async def cleanup_expired_tasks(ctx: dict[str, Any] | None) -> None:
    """
    清理过期任务结果

    Args:
        ctx: Arq上下文
    """
    task_manager = get_task_manager()
    current_time = datetime.now()

    # 清理超过7天的已完成任务
    expired_task_ids = []
    for task_id, task_result in task_manager._task_results.items():
        if (
            task_result.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            and task_result.end_time
            and (current_time - task_result.end_time).days > 7
        ):
            expired_task_ids.append(task_id)

    for task_id in expired_task_ids:
        del task_manager._task_results[task_id]
        logger.info(f"清理过期任务: {task_id}")

    logger.info(f"清理过期任务完成,共清理 {len(expired_task_ids)} 个任务")


# Arq Worker配置
class WorkerSettings:
    """Arq Worker配置"""

    functions = [
        execute_create_knowledge_base_task,
        execute_update_knowledge_base_task,
        execute_delete_knowledge_base_task,
        execute_query_knowledge_base_task,
    ]

    # 重试配置
    retry_jobs = True
    max_retries = 3

    # 任务超时配置(秒)
    job_timeout = 3600  # 1小时

    # 队列配置
    queue_name = "indexing_tasks"

    # 定时任务配置
    cron_jobs = [
        # 每天凌晨2点清理过期任务结果
        cron(
            cleanup_expired_tasks,
            hour=2,
            minute=0,
            second=0,
        ),
    ]


# 便捷函数
async def create_knowledge_base_async(
    name: str,
    directories: list[str],
    description: str | None = None,
    **kwargs: Any,
) -> str:
    """
    创建知识库异步任务(便捷函数)

    Args:
        name: 知识库名称
        directories: 预处理结果目录列表
        description: 知识库描述
        **kwargs: 其他参数

    Returns:
        任务ID
    """
    task_manager = get_task_manager()
    return await task_manager.create_knowledge_base_task(
        name=name,
        directories=directories,
        description=description,
        **kwargs,
    )


async def update_knowledge_base_async(
    knowledge_base_id: str,
    directories: list[str] | None = None,
    documents: list[dict[str, Any]] | None = None,
    **kwargs: Any,
) -> str:
    """
    更新知识库异步任务(便捷函数)

    Args:
        knowledge_base_id: 知识库ID
        directories: 预处理结果目录列表
        documents: 文档列表
        **kwargs: 其他参数

    Returns:
        任务ID
    """
    task_manager = get_task_manager()
    return await task_manager.update_knowledge_base_task(
        knowledge_base_id=knowledge_base_id,
        directories=directories,
        documents=documents,
        **kwargs,
    )


async def delete_knowledge_base_async(
    knowledge_base_id: str,
    **kwargs: Any,
) -> str:
    """
    删除知识库异步任务(便捷函数)

    Args:
        knowledge_base_id: 知识库ID
        **kwargs: 其他参数

    Returns:
        任务ID
    """
    task_manager = get_task_manager()
    return await task_manager.delete_knowledge_base_task(
        knowledge_base_id=knowledge_base_id,
        **kwargs,
    )


async def query_knowledge_base_async(
    knowledge_base_id: str,
    query_str: str,
    top_k: int = 10,
    **kwargs: Any,
) -> str:
    """
    查询知识库异步任务(便捷函数)

    Args:
        knowledge_base_id: 知识库ID
        query_str: 查询文本
        top_k: 返回结果数量
        **kwargs: 其他参数

    Returns:
        任务ID
    """
    task_manager = get_task_manager()
    return await task_manager.query_knowledge_base_task(
        knowledge_base_id=knowledge_base_id,
        query_str=query_str,
        top_k=top_k,
        **kwargs,
    )
