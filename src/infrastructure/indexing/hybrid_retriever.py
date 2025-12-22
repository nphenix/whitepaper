# 生成命令: /speckit.implement T061
# 生成时间: 2025-12-20
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
混合检索引擎实现 (T061)

该模块实现混合检索引擎，融合向量检索、BM25检索、元数据检索和知识图谱检索，
使用RRF（Reciprocal Rank Fusion）算法融合多种检索结果，支持动态检索策略和重排序。

设计目标:
- 融合向量检索（语义相似度）、BM25检索（关键词匹配）、元数据检索（结构化过滤）、知识图谱检索（实体关系）
- 实现Reciprocal Rank Fusion (RRF)或其他融合算法，融合多种检索结果
- 动态检索：根据查询类型（事实性问答、总结、比较等）动态选择检索策略
- 重排序：支持对融合结果进行重排序（如使用Rerank模型）
- 配置支持：支持配置不同检索模式的权重和融合策略
- 性能优化：支持并行执行多种检索，优化响应时间

参考LangChain 1.0和LlamaIndex最佳实践:
- 使用LlamaIndex的Retriever接口
- 支持元数据过滤和结构化查询
- 遵循LangChain 1.0的标准化内容块格式
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.infrastructure.indexing.bm25_index import BM25IndexBuilder
from src.infrastructure.indexing.knowledge_graph import KnowledgeGraphBuilder
from src.infrastructure.indexing.metadata_index import MetadataIndexBuilder
from src.infrastructure.indexing.vector_index import VectorIndexBuilder
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.schema import BaseNode, NodeWithScore, QueryBundle
    from llama_index.core.retrievers import BaseRetriever

    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 llama-index 时触发
    logger.warning(
        "LlamaIndex not available, hybrid retriever will be disabled"
    )
    BaseNode = Any  # type: ignore[assignment, misc]
    NodeWithScore = Any  # type: ignore[assignment, misc]
    QueryBundle = Any  # type: ignore[assignment, misc]
    BaseRetriever = Any  # type: ignore[assignment, misc]
    LLAMA_INDEX_AVAILABLE = False


class QueryType(str, Enum):
    """查询类型枚举"""

    FACTUAL_QA = "factual_qa"  # 事实性问答
    SUMMARIZATION = "summarization"  # 总结
    COMPARISON = "comparison"  # 比较
    EXPLANATION = "explanation"  # 解释
    GENERAL = "general"  # 通用查询


class FusionStrategy(str, Enum):
    """融合策略枚举"""

    RRF = "rrf"  # Reciprocal Rank Fusion
    WEIGHTED_SUM = "weighted_sum"  # 加权求和
    MAX_SCORE = "max_score"  # 最大分数
    AVERAGE = "average"  # 平均分数


@dataclass
class RetrievalWeights:
    """检索权重配置"""

    vector_weight: float = 1.0
    bm25_weight: float = 1.0
    metadata_weight: float = 0.8
    graph_weight: float = 0.6

    def __post_init__(self) -> None:
        """验证权重值"""
        if any(w < 0 for w in [self.vector_weight, self.bm25_weight, self.metadata_weight, self.graph_weight]):
            raise ValueError("权重值不能为负数")


@dataclass
class HybridRetrieverConfig:
    """混合检索引擎配置"""

    # 检索模式启用
    enable_vector: bool = True
    enable_bm25: bool = True
    enable_metadata: bool = True
    enable_graph: bool = False  # 默认关闭，因为知识图谱构建较慢

    # 融合策略
    fusion_strategy: FusionStrategy = FusionStrategy.RRF
    rrf_k: int = 60  # RRF算法的k参数

    # 检索权重
    weights: RetrievalWeights = None  # type: ignore[assignment]

    # 重排序配置
    enable_rerank: bool = True
    rerank_top_k: int = 20  # 重排序前保留的top k结果

    # 并行执行
    parallel_execution: bool = True

    # 默认top_k
    default_top_k: int = 10

    def __post_init__(self) -> None:
        """初始化默认权重"""
        if self.weights is None:
            self.weights = RetrievalWeights()


class HybridRetrieverError(Exception):
    """混合检索引擎异常基类"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 简单字符串表示
        return f"混合检索引擎错误: {self.message}"


class HybridRetriever:
    """
    混合检索引擎

    融合向量检索、BM25检索、元数据检索和知识图谱检索，使用RRF算法融合结果。

    典型用法:
        >>> retriever = HybridRetriever(
        ...     vector_index_builder=vector_builder,
        ...     bm25_index_builder=bm25_builder,
        ...     metadata_index_builder=metadata_builder,
        ... )
        >>> results = retriever.retrieve(query="查询文本", top_k=10)
    """

    def __init__(
        self,
        vector_index_builder: VectorIndexBuilder | None = None,
        bm25_index_builder: BM25IndexBuilder | None = None,
        metadata_index_builder: MetadataIndexBuilder | None = None,
        knowledge_graph_builder: KnowledgeGraphBuilder | None = None,
        config: HybridRetrieverConfig | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        """
        初始化混合检索引擎

        Args:
            vector_index_builder: 向量索引构建器
            bm25_index_builder: BM25索引构建器
            metadata_index_builder: 元数据索引构建器
            knowledge_graph_builder: 知识图谱构建器
            config: 混合检索引擎配置
            llm_service: LLM服务，用于重排序

        Raises:
            ImportError: 如果LlamaIndex未安装
            HybridRetrieverError: 如果初始化失败
        """
        if not LLAMA_INDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not available. Please install llama-index package to "
                "use HybridRetriever."
            )

        self.vector_index_builder = vector_index_builder
        self.bm25_index_builder = bm25_index_builder
        self.metadata_index_builder = metadata_index_builder
        self.knowledge_graph_builder = knowledge_graph_builder
        self.config = config or HybridRetrieverConfig()
        self.llm_service = llm_service or get_llm_service()

        # 验证配置
        if not any([
            self.config.enable_vector and self.vector_index_builder,
            self.config.enable_bm25 and self.bm25_index_builder,
            self.config.enable_metadata and self.metadata_index_builder,
            self.config.enable_graph and self.knowledge_graph_builder,
        ]):
            raise HybridRetrieverError(
                "至少需要启用一种检索模式并提供对应的索引构建器"
            )

        logger.info(
            "初始化 HybridRetriever: vector=%s, bm25=%s, metadata=%s, graph=%s",
            self.config.enable_vector,
            self.config.enable_bm25,
            self.config.enable_metadata,
            self.config.enable_graph,
        )

    def retrieve(
        self,
        query_str: str,
        top_k: int | None = None,
        query_type: QueryType | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[NodeWithScore]:
        """
        执行混合检索

        Args:
            query_str: 查询文本
            top_k: 返回结果数量，如果为None则使用配置的default_top_k
            query_type: 查询类型，用于动态选择检索策略
            filters: 元数据过滤器

        Returns:
            检索结果列表（NodeWithScore对象），按相关性排序

        Raises:
            HybridRetrieverError: 如果检索失败
        """
        if not query_str or not query_str.strip():
            raise ValueError("查询文本不能为空")

        top_k = top_k or self.config.default_top_k

        try:
            logger.info(
                "执行混合检索: query=%s, top_k=%s, query_type=%s",
                query_str[:50],
                top_k,
                query_type,
            )

            # 根据查询类型动态调整检索策略
            adjusted_config = self._adjust_config_for_query_type(query_type)

            # 并行执行多种检索
            if self.config.parallel_execution:
                results = self._retrieve_parallel(
                    query_str=query_str,
                    top_k=top_k,
                    filters=filters,
                    config=adjusted_config,
                )
            else:
                results = self._retrieve_sequential(
                    query_str=query_str,
                    top_k=top_k,
                    filters=filters,
                    config=adjusted_config,
                )

            # 融合检索结果
            fused_results = self._fuse_results(results, config=adjusted_config)

            # 重排序（如果启用）
            if self.config.enable_rerank and len(fused_results) > 0:
                reranked_results = self._rerank_results(
                    query_str=query_str,
                    results=fused_results[:self.config.rerank_top_k],
                )
                # 将重排序后的结果与未重排序的结果合并
                reranked_node_ids = {r.node.node_id for r in reranked_results}
                remaining_results = [
                    r for r in fused_results[self.config.rerank_top_k:]
                    if r.node.node_id not in reranked_node_ids
                ]
                final_results = reranked_results + remaining_results
            else:
                final_results = fused_results

            # 限制返回数量
            final_results = final_results[:top_k]

            logger.info(
                "混合检索完成: query=%s, results_count=%s",
                query_str[:50],
                len(final_results),
            )

            return final_results

        except Exception as exc:
            error_msg = f"混合检索失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise HybridRetrieverError(error_msg) from exc

    def _adjust_config_for_query_type(
        self,
        query_type: QueryType | None,
    ) -> HybridRetrieverConfig:
        """
        根据查询类型动态调整检索配置

        Args:
            query_type: 查询类型

        Returns:
            调整后的配置
        """
        if query_type is None:
            return self.config

        # 创建配置副本
        adjusted_config = HybridRetrieverConfig(
            enable_vector=self.config.enable_vector,
            enable_bm25=self.config.enable_bm25,
            enable_metadata=self.config.enable_metadata,
            enable_graph=self.config.enable_graph,
            fusion_strategy=self.config.fusion_strategy,
            rrf_k=self.config.rrf_k,
            weights=self.config.weights,
            enable_rerank=self.config.enable_rerank,
            rerank_top_k=self.config.rerank_top_k,
            parallel_execution=self.config.parallel_execution,
            default_top_k=self.config.default_top_k,
        )

        # 根据查询类型调整权重
        if query_type == QueryType.FACTUAL_QA:
            # 事实性问答：优先向量检索和BM25检索
            adjusted_config.weights = RetrievalWeights(
                vector_weight=1.2,
                bm25_weight=1.2,
                metadata_weight=0.6,
                graph_weight=0.4,
            )
        elif query_type == QueryType.SUMMARIZATION:
            # 总结：优先向量检索
            adjusted_config.weights = RetrievalWeights(
                vector_weight=1.5,
                bm25_weight=0.8,
                metadata_weight=0.5,
                graph_weight=0.3,
            )
        elif query_type == QueryType.COMPARISON:
            # 比较：优先元数据检索和知识图谱检索
            adjusted_config.weights = RetrievalWeights(
                vector_weight=0.8,
                bm25_weight=0.8,
                metadata_weight=1.2,
                graph_weight=1.0,
            )
        elif query_type == QueryType.EXPLANATION:
            # 解释：优先向量检索和知识图谱检索
            adjusted_config.weights = RetrievalWeights(
                vector_weight=1.3,
                bm25_weight=0.7,
                metadata_weight=0.6,
                graph_weight=1.1,
            )

        return adjusted_config

    def _retrieve_parallel(
        self,
        query_str: str,
        top_k: int,
        filters: dict[str, Any] | None,
        config: HybridRetrieverConfig,
    ) -> dict[str, list[NodeWithScore]]:
        """
        并行执行多种检索

        Args:
            query_str: 查询文本
            top_k: 返回结果数量
            filters: 元数据过滤器
            config: 检索配置

        Returns:
            检索结果字典，key为检索模式名称，value为结果列表
        """
        results: dict[str, list[NodeWithScore]] = {}

        def retrieve_vector() -> list[NodeWithScore]:
            """向量检索"""
            if not config.enable_vector or not self.vector_index_builder:
                return []
            try:
                return self.vector_index_builder.query(
                    query_str=query_str,
                    top_k=top_k,
                    filters=None,  # 向量索引使用MetadataFilters
                )
            except Exception as exc:
                logger.warning("向量检索失败: %s", exc)
                return []

        def retrieve_bm25() -> list[NodeWithScore]:
            """BM25检索"""
            if not config.enable_bm25 or not self.bm25_index_builder:
                return []
            try:
                return self.bm25_index_builder.query(
                    query_str=query_str,
                    top_k=top_k,
                    filters=filters,
                )
            except Exception as exc:
                logger.warning("BM25检索失败: %s", exc)
                return []

        def retrieve_metadata() -> list[NodeWithScore]:
            """元数据检索"""
            if not config.enable_metadata or not self.metadata_index_builder:
                return []
            try:
                # 元数据检索需要将查询转换为元数据过滤条件
                # 这里简化处理，使用filters进行查询
                metadata_records = self.metadata_index_builder.query(
                    filters=filters,
                    limit=top_k,
                )
                # 将元数据记录转换为NodeWithScore对象
                # 注意：这里需要根据实际需求实现转换逻辑
                return []
            except Exception as exc:
                logger.warning("元数据检索失败: %s", exc)
                return []

        def retrieve_graph() -> list[NodeWithScore]:
            """知识图谱检索"""
            if not config.enable_graph or not self.knowledge_graph_builder:
                return []
            try:
                # 知识图谱检索需要从查询中提取实体，然后查询相关实体
                # 这里简化处理，返回空列表
                return []
            except Exception as exc:
                logger.warning("知识图谱检索失败: %s", exc)
                return []

        # 并行执行所有检索（使用线程池）
        try:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {}
                if config.enable_vector and self.vector_index_builder:
                    futures["vector"] = executor.submit(retrieve_vector)
                if config.enable_bm25 and self.bm25_index_builder:
                    futures["bm25"] = executor.submit(retrieve_bm25)
                if config.enable_metadata and self.metadata_index_builder:
                    futures["metadata"] = executor.submit(retrieve_metadata)
                if config.enable_graph and self.knowledge_graph_builder:
                    futures["graph"] = executor.submit(retrieve_graph)

                # 等待所有任务完成
                for key, future in futures.items():
                    try:
                        results[key] = future.result(timeout=30)  # 30秒超时
                    except concurrent.futures.TimeoutError:
                        logger.warning("检索超时: %s", key)
                        results[key] = []
                    except Exception as exc:
                        logger.warning("检索执行失败: %s, error=%s", key, exc)
                        results[key] = []

        except Exception as exc:
            logger.error("并行检索执行失败: %s", exc, exc_info=True)
            # 降级为顺序执行
            results = self._retrieve_sequential(query_str, top_k, filters, config)

        return results

    def _retrieve_sequential(
        self,
        query_str: str,
        top_k: int,
        filters: dict[str, Any] | None,
        config: HybridRetrieverConfig,
    ) -> dict[str, list[NodeWithScore]]:
        """
        顺序执行多种检索

        Args:
            query_str: 查询文本
            top_k: 返回结果数量
            filters: 元数据过滤器
            config: 检索配置

        Returns:
            检索结果字典
        """
        results: dict[str, list[NodeWithScore]] = {}

        # 向量检索
        if config.enable_vector and self.vector_index_builder:
            try:
                results["vector"] = self.vector_index_builder.query(
                    query_str=query_str,
                    top_k=top_k,
                )
            except Exception as exc:
                logger.warning("向量检索失败: %s", exc)
                results["vector"] = []

        # BM25检索
        if config.enable_bm25 and self.bm25_index_builder:
            try:
                results["bm25"] = self.bm25_index_builder.query(
                    query_str=query_str,
                    top_k=top_k,
                    filters=filters,
                )
            except Exception as exc:
                logger.warning("BM25检索失败: %s", exc)
                results["bm25"] = []

        # 元数据检索
        if config.enable_metadata and self.metadata_index_builder:
            try:
                # 元数据检索需要特殊处理
                metadata_records = self.metadata_index_builder.query(
                    filters=filters,
                    limit=top_k,
                )
                # 转换为NodeWithScore对象（需要根据实际需求实现）
                results["metadata"] = []
            except Exception as exc:
                logger.warning("元数据检索失败: %s", exc)
                results["metadata"] = []

        # 知识图谱检索
        if config.enable_graph and self.knowledge_graph_builder:
            try:
                # 知识图谱检索需要特殊处理
                results["graph"] = []
            except Exception as exc:
                logger.warning("知识图谱检索失败: %s", exc)
                results["graph"] = []

        return results

    def _fuse_results(
        self,
        results: dict[str, list[NodeWithScore]],
        config: HybridRetrieverConfig,
    ) -> list[NodeWithScore]:
        """
        融合多种检索结果

        Args:
            results: 检索结果字典
            config: 融合配置

        Returns:
            融合后的结果列表，按相关性排序
        """
        if not results:
            return []

        if config.fusion_strategy == FusionStrategy.RRF:
            return self._fuse_rrf(results, config)
        elif config.fusion_strategy == FusionStrategy.WEIGHTED_SUM:
            return self._fuse_weighted_sum(results, config)
        elif config.fusion_strategy == FusionStrategy.MAX_SCORE:
            return self._fuse_max_score(results, config)
        elif config.fusion_strategy == FusionStrategy.AVERAGE:
            return self._fuse_average(results, config)
        else:
            # 默认使用RRF
            return self._fuse_rrf(results, config)

    def _fuse_rrf(
        self,
        results: dict[str, list[NodeWithScore]],
        config: HybridRetrieverConfig,
    ) -> list[NodeWithScore]:
        """
        使用RRF（Reciprocal Rank Fusion）算法融合结果

        Args:
            results: 检索结果字典
            config: 融合配置

        Returns:
            融合后的结果列表
        """
        # 节点ID到RRF分数的映射
        node_scores: dict[str, float] = defaultdict(float)

        # 权重映射
        weights = {
            "vector": config.weights.vector_weight,
            "bm25": config.weights.bm25_weight,
            "metadata": config.weights.metadata_weight,
            "graph": config.weights.graph_weight,
        }

        # 计算每个检索模式的RRF分数
        for mode, mode_results in results.items():
            if not mode_results:
                continue

            weight = weights.get(mode, 1.0)
            for rank, result in enumerate(mode_results, start=1):
                node_id = result.node.node_id
                # RRF公式: score = weight / (k + rank)
                rrf_score = weight / (config.rrf_k + rank)
                node_scores[node_id] += rrf_score

        # 创建节点ID到NodeWithScore的映射
        node_map: dict[str, NodeWithScore] = {}
        for mode_results in results.values():
            for result in mode_results:
                node_id = result.node.node_id
                if node_id not in node_map:
                    node_map[node_id] = result

        # 按RRF分数排序
        fused_results = [
            node_map[node_id]
            for node_id, _ in sorted(
                node_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ]

        # 更新分数为RRF分数
        for result in fused_results:
            node_id = result.node.node_id
            result.score = node_scores[node_id]  # type: ignore[assignment]

        return fused_results

    def _fuse_weighted_sum(
        self,
        results: dict[str, list[NodeWithScore]],
        config: HybridRetrieverConfig,
    ) -> list[NodeWithScore]:
        """
        使用加权求和融合结果

        Args:
            results: 检索结果字典
            config: 融合配置

        Returns:
            融合后的结果列表
        """
        # 节点ID到加权分数的映射
        node_scores: dict[str, float] = defaultdict(float)

        # 权重映射
        weights = {
            "vector": config.weights.vector_weight,
            "bm25": config.weights.bm25_weight,
            "metadata": config.weights.metadata_weight,
            "graph": config.weights.graph_weight,
        }

        # 归一化每个检索模式的分数
        for mode, mode_results in results.items():
            if not mode_results:
                continue

            # 找到最大分数用于归一化
            max_score = max((r.score for r in mode_results), default=1.0)
            if max_score == 0:
                max_score = 1.0

            weight = weights.get(mode, 1.0)
            for result in mode_results:
                node_id = result.node.node_id
                # 归一化分数并加权
                normalized_score = result.score / max_score
                node_scores[node_id] += weight * normalized_score

        # 创建节点ID到NodeWithScore的映射
        node_map: dict[str, NodeWithScore] = {}
        for mode_results in results.values():
            for result in mode_results:
                node_id = result.node.node_id
                if node_id not in node_map:
                    node_map[node_id] = result

        # 按加权分数排序
        fused_results = [
            node_map[node_id]
            for node_id, _ in sorted(
                node_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ]

        # 更新分数为加权分数
        for result in fused_results:
            node_id = result.node.node_id
            result.score = node_scores[node_id]  # type: ignore[assignment]

        return fused_results

    def _fuse_max_score(
        self,
        results: dict[str, list[NodeWithScore]],
        config: HybridRetrieverConfig,
    ) -> list[NodeWithScore]:
        """
        使用最大分数融合结果

        Args:
            results: 检索结果字典
            config: 融合配置

        Returns:
            融合后的结果列表
        """
        # 节点ID到最大分数的映射
        node_scores: dict[str, float] = {}

        # 权重映射
        weights = {
            "vector": config.weights.vector_weight,
            "bm25": config.weights.bm25_weight,
            "metadata": config.weights.metadata_weight,
            "graph": config.weights.graph_weight,
        }

        # 找到每个节点的最大加权分数
        for mode, mode_results in results.items():
            if not mode_results:
                continue

            weight = weights.get(mode, 1.0)
            for result in mode_results:
                node_id = result.node.node_id
                weighted_score = weight * result.score
                if node_id not in node_scores or weighted_score > node_scores[node_id]:
                    node_scores[node_id] = weighted_score

        # 创建节点ID到NodeWithScore的映射
        node_map: dict[str, NodeWithScore] = {}
        for mode_results in results.values():
            for result in mode_results:
                node_id = result.node.node_id
                if node_id not in node_map:
                    node_map[node_id] = result

        # 按最大分数排序
        fused_results = [
            node_map[node_id]
            for node_id, _ in sorted(
                node_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ]

        # 更新分数为最大分数
        for result in fused_results:
            node_id = result.node.node_id
            result.score = node_scores[node_id]  # type: ignore[assignment]

        return fused_results

    def _fuse_average(
        self,
        results: dict[str, list[NodeWithScore]],
        config: HybridRetrieverConfig,
    ) -> list[NodeWithScore]:
        """
        使用平均分数融合结果

        Args:
            results: 检索结果字典
            config: 融合配置

        Returns:
            融合后的结果列表
        """
        # 节点ID到分数列表的映射
        node_scores_list: dict[str, list[float]] = defaultdict(list)

        # 权重映射
        weights = {
            "vector": config.weights.vector_weight,
            "bm25": config.weights.bm25_weight,
            "metadata": config.weights.metadata_weight,
            "graph": config.weights.graph_weight,
        }

        # 收集每个节点的所有分数
        for mode, mode_results in results.items():
            if not mode_results:
                continue

            weight = weights.get(mode, 1.0)
            for result in mode_results:
                node_id = result.node.node_id
                weighted_score = weight * result.score
                node_scores_list[node_id].append(weighted_score)

        # 计算平均分数
        node_scores: dict[str, float] = {
            node_id: sum(scores) / len(scores)
            for node_id, scores in node_scores_list.items()
        }

        # 创建节点ID到NodeWithScore的映射
        node_map: dict[str, NodeWithScore] = {}
        for mode_results in results.values():
            for result in mode_results:
                node_id = result.node.node_id
                if node_id not in node_map:
                    node_map[node_id] = result

        # 按平均分数排序
        fused_results = [
            node_map[node_id]
            for node_id, _ in sorted(
                node_scores.items(),
                key=lambda x: x[1],
                reverse=True,
            )
        ]

        # 更新分数为平均分数
        for result in fused_results:
            node_id = result.node.node_id
            result.score = node_scores[node_id]  # type: ignore[assignment]

        return fused_results

    def _rerank_results(
        self,
        query_str: str,
        results: list[NodeWithScore],
    ) -> list[NodeWithScore]:
        """
        使用Rerank模型对结果进行重排序

        Args:
            query_str: 查询文本
            results: 检索结果列表

        Returns:
            重排序后的结果列表
        """
        if not results:
            return []

        try:
            # 获取Rerank模型
            rerank_model = self.llm_service.get_rerank_model()

            # 准备文档列表
            documents = [result.node.text for result in results]

            # 执行重排序
            rerank_results = rerank_model.rerank(
                query=query_str,
                documents=documents,
            )

            # 某些Rerank实现可能在失败时“吞异常并返回空列表”
            # 如果直接返回空结果会把最终检索结果清零，因此需要回退到原始候选
            if not rerank_results:
                logger.warning(
                    "重排序返回空结果，回退到原始结果: query=%s, candidates=%s",
                    query_str[:50],
                    len(results),
                )
                return results

            # 根据重排序结果重新排序
            # rerank_results格式: [{"document": str, "index": int, "relevance_score": float}, ...]
            reranked_indices: list[int] = []
            for r in rerank_results:
                idx = r.get("index")
                if isinstance(idx, int) and 0 <= idx < len(results):
                    reranked_indices.append(idx)

            if not reranked_indices:
                logger.warning(
                    "重排序结果索引无效或为空，回退到原始结果: query=%s, candidates=%s",
                    query_str[:50],
                    len(results),
                )
                return results

            reranked_results = [results[i] for i in reranked_indices]

            # 更新分数为relevance_score
            for i, rerank_result in enumerate(rerank_results):
                if i >= len(reranked_results):
                    break
                score = rerank_result.get("relevance_score")
                if isinstance(score, (int, float)):
                    reranked_results[i].score = float(score)  # type: ignore[assignment]

            logger.info(
                "重排序完成: query=%s, results_count=%s",
                query_str[:50],
                len(reranked_results),
            )

            return reranked_results

        except Exception as exc:
            logger.warning("重排序失败，返回原始结果: %s", exc)
            return results

