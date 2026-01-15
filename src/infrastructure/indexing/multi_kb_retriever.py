"""
多知识库混合检索器

支持同时查询多个知识库，并使用 RRF 算法融合检索结果。
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.infrastructure.indexing.hybrid_retriever import (
    HybridRetriever,
    HybridRetrieverConfig,
    NodeWithScore,
)

logger = logging.getLogger(__name__)


class MultiKBHybridRetriever:
    """
    多知识库混合检索器

    包装多个 HybridRetriever 实例，支持同时查询多个知识库。

    典型用法:
        >>> retriever = MultiKBHybridRetriever([
        ...     hybrid_retriever_kb1,
        ...     hybrid_retriever_kb2,
        ... ])
        >>> results = retriever.retrieve(query="查询文本", top_k=10)
    """

    def __init__(
        self,
        retrievers: list[HybridRetriever],
        config: HybridRetrieverConfig | None = None,
        max_workers: int = 4,
    ) -> None:
        """
        初始化多知识库混合检索器

        Args:
            retrievers: HybridRetriever 实例列表，每个对应一个知识库
            config: 混合检索引擎配置
            max_workers: 并行查询的最大线程数

        Raises:
            ValueError: 如果 retrievers 为空列表
        """
        if not retrievers:
            msg = "retrievers 列表不能为空"
            raise ValueError(msg)

        self.retrievers = retrievers
        self.config = config or HybridRetrieverConfig()
        self.max_workers = max_workers
        
        # 用于缓存节点信息
        self._node_cache: dict[str, NodeWithScore] = {}

        logger.info(
            "初始化 MultiKBHybridRetriever: kb_count=%d, max_workers=%d",
            len(retrievers),
            max_workers,
        )

    def retrieve(
        self,
        query_str: str,
        top_k: int | None = None,
        query_type: Any | None = None,
        filters: dict[str, Any] | None = None,
    ) -> list[NodeWithScore]:
        """
        执行多知识库混合检索

        并行查询所有知识库，然后使用 RRF 算法融合结果。

        Args:
            query_str: 查询文本
            top_k: 返回结果数量
            query_type: 查询类型
            filters: 元数据过滤器

        Returns:
            检索结果列表，按相关性排序
        """
        if not query_str or not query_str.strip():
            msg = "查询文本不能为空"
            raise ValueError(msg)

        top_k = top_k or self.config.default_top_k

        # 并行查询所有知识库
        all_results: dict[int, list[NodeWithScore]] = {}

        if self.max_workers > 1 and len(self.retrievers) > 1:
            logger.debug("使用并行查询模式: workers=%d", self.max_workers)
            with ThreadPoolExecutor(max_workers=min(self.max_workers, len(self.retrievers))) as executor:
                futures = {
                    executor.submit(self._safe_retrieve, retriever, query_str, top_k, query_type, filters): idx
                    for idx, retriever in enumerate(self.retrievers)
                }
                for future in futures:
                    kb_idx = futures[future]
                    try:
                        all_results[kb_idx] = future.result()
                    except Exception as e:
                        logger.warning("知识库 %d 查询失败: %s", kb_idx, e)
                        all_results[kb_idx] = []
        else:
            logger.debug("使用顺序查询模式")
            for idx, retriever in enumerate(self.retrievers):
                try:
                    all_results[idx] = self._safe_retrieve(retriever, query_str, top_k, query_type, filters)
                except Exception as e:
                    logger.warning("知识库 %d 查询失败: %s", idx, e)
                    all_results[idx] = []

        # 融合结果
        fused_results = self._fuse_results(all_results, top_k)

        logger.info(
            "多知识库检索完成: query='%s...', kb_count=%d, total_results=%d",
            query_str[:30],
            len(self.retrievers),
            len(fused_results),
        )

        return fused_results

    def _safe_retrieve(
        self,
        retriever: HybridRetriever,
        query_str: str,
        top_k: int,
        query_type: Any | None,
        filters: dict[str, Any] | None,
    ) -> list[NodeWithScore]:
        """安全地执行检索（捕获异常）"""
        try:
            return retriever.retrieve(
                query_str=query_str,
                top_k=top_k,
                query_type=query_type,
                filters=filters,
            )
        except Exception as e:
            logger.debug("检索失败: %s", e)
            return []

    def _fuse_results(
        self,
        all_results: dict[int, list[NodeWithScore]],
        top_k: int,
    ) -> list[NodeWithScore]:
        """
        使用 RRF 算法融合多个知识库的检索结果

        RRF (Reciprocal Rank Fusion): rrf(d) = 1 / (k + rank(d))

        Args:
            all_results: {知识库索引: 结果列表}
            top_k: 返回结果数量

        Returns:
            融合后的结果列表
        """
        # 构建 RRF 分数
        rrf_scores: dict[str, float] = {}
        k = 60  # RRF 常数

        for kb_idx, results in all_results.items():
            for rank, node in enumerate(results, 1):
                node_id = node.node.node_id

                # 计算 RRRF 分数
                rrf_score = 1.0 / (k + rank)

                # 如果节点来自不同知识库，累加分数
                if node_id in rrf_scores:
                    rrf_scores[node_id] += rrf_score
                else:
                    rrf_scores[node_id] = rrf_score

                # 保存节点信息（使用分数最高的那个）
                if node_id not in self._node_cache:
                    self._node_cache[node_id] = node

        # 按 RRF 分数排序
        sorted_results = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # 构建结果列表
        fused_nodes: list[NodeWithScore] = []
        seen_ids = set()

        for node_id, score in sorted_results:
            if len(fused_nodes) >= top_k:
                break

            if node_id in self._node_cache and node_id not in seen_ids:
                node = self._node_cache[node_id]
                # 更新分数为 RRF 融合分数
                fused_nodes.append(
                    NodeWithScore(
                        node=node.node,
                        score=score,
                    )
                )
                seen_ids.add(node_id)

        return fused_nodes

    def __repr__(self) -> str:
        """返回字符串表示"""
        return f"MultiKBHybridRetriever(kb_count={len(self.retrievers)})"


# 辅助函数：创建支持多知识库的 HybridRetriever
def create_multi_kb_hybrid_retriever(
    knowledge_base_ids: list[str],
    config: HybridRetrieverConfig | None = None,
    max_workers: int = 4,
) -> MultiKBHybridRetriever | HybridRetriever:
    """
    创建支持多知识库的混合检索器

    如果只有一个知识库，返回普通的 HybridRetriever；
    如果有多个知识库，返回 MultiKBHybridRetriever。

    Args:
        knowledge_base_ids: 知识库ID列表
        config: 混合检索引擎配置
        max_workers: 并行查询的最大线程数

    Returns:
        HybridRetriever 或 MultiKBHybridRetriever 实例

    Raises:
        HybridRetrieverError: 如果初始化失败
    """
    from src.interfaces.api.routes.draft_mvp import get_hybrid_retriever as get_single_kb_retriever

    if not knowledge_base_ids:
        # 没有指定知识库，使用默认配置
        logger.warning("未提供 knowledge_base_ids，使用默认配置")
        return get_single_kb_retriever(None)

    if len(knowledge_base_ids) == 1:
        # 只有一个知识库，使用普通 HybridRetriever
        logger.info("单知识库模式: kb_id=%s", knowledge_base_ids[0])
        return get_single_kb_retriever(knowledge_base_ids[0])

    # 多个知识库，创建 MultiKBHybridRetriever
    logger.info("多知识库模式: kb_count=%d", len(knowledge_base_ids))

    retrievers: list[HybridRetriever] = []
    failed_kbs: list[str] = []

    for kb_id in knowledge_base_ids:
        try:
            retriever = get_single_kb_retriever(kb_id)
            retrievers.append(retriever)
            logger.debug("成功创建知识库 %s 的检索器", kb_id)
        except Exception as e:
            logger.warning("创建知识库 %s 的检索器失败: %s", kb_id, e)
            failed_kbs.append(kb_id)

    if not retrievers:
        msg = f"所有知识库检索器创建失败: {failed_kbs}"
        logger.error(msg)
        # 尝试回退到默认配置
        logger.warning("回退到默认配置")
        return get_single_kb_retriever(None)

    if failed_kbs:
        logger.warning("部分知识库创建失败: %s", failed_kbs)

    return MultiKBHybridRetriever(
        retrievers=retrievers,
        config=config,
        max_workers=max_workers,
    )
