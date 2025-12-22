# 生成命令: /speckit.implement T062
# 生成时间: 2025-12-19
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
检索块与合成块分离策略 (T062)

该模块实现检索块与合成块分离策略，遵循LlamaIndex最佳实践，优化RAG性能。
通过双层分块策略，解耦检索块与合成块，提高检索精度和生成质量。

设计目标:
- 检索块: 较小的块（如256字符），用于语义检索，优化检索精度
- 合成块: 较大的块（如1024字符），用于生成上下文，提供足够的上下文
- 映射关系: 建立检索块与合成块的映射关系，检索时使用检索块，生成时使用对应的合成块
- 元数据保留: 在两个层级都保留章节路径、文档位置等元数据

参考LlamaIndex最佳实践:
- https://docs.llamaindex.org.cn/en/stable/optimizing/production_rag/
- 解耦检索块与合成块，优化RAG性能
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import Node, TextNode

    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 llama-index 时触发
    logger.warning(
        "LlamaIndex not available, retrieval-composition splitter will be disabled"
    )
    SentenceSplitter = Any  # type: ignore[assignment]
    Node = Any  # type: ignore[assignment]
    TextNode = Any  # type: ignore[assignment]
    LLAMA_INDEX_AVAILABLE = False


class RetrievalCompositionSplitterError(Exception):
    """检索块与合成块分离异常基类"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 简单字符串表示
        return f"检索块与合成块分离错误: {self.message}"


@dataclass(slots=True)
class RetrievalCompositionConfig:
    """
    检索块与合成块分离配置

    Attributes:
        retrieval_chunk_size: 检索块的最大字符数（较小的块，用于语义检索）
        retrieval_chunk_overlap: 检索块之间的重叠字符数
        composition_chunk_size: 合成块的最大字符数（较大的块，用于生成上下文）
        composition_chunk_overlap: 合成块之间的重叠字符数
        mapping_strategy: 映射策略，决定如何建立检索块与合成块的映射关系
            - "overlap": 基于重叠区域映射（默认）
            - "containment": 基于包含关系映射
            - "nearest": 基于最近距离映射
    """

    retrieval_chunk_size: int = 256
    retrieval_chunk_overlap: int = 50
    composition_chunk_size: int = 1024
    composition_chunk_overlap: int = 200
    mapping_strategy: str = "overlap"

    def __post_init__(self) -> None:
        """验证配置参数"""
        if self.retrieval_chunk_size <= 0:
            msg = f"retrieval_chunk_size 必须为正整数, 当前值: {self.retrieval_chunk_size}"
            raise ValueError(msg)
        if self.composition_chunk_size <= 0:
            msg = f"composition_chunk_size 必须为正整数, 当前值: {self.composition_chunk_size}"
            raise ValueError(msg)
        if self.retrieval_chunk_overlap < 0:
            msg = (
                f"retrieval_chunk_overlap 不能为负数, 当前值: {self.retrieval_chunk_overlap}"
            )
            raise ValueError(msg)
        if self.composition_chunk_overlap < 0:
            msg = (
                f"composition_chunk_overlap 不能为负数, 当前值: {self.composition_chunk_overlap}"
            )
            raise ValueError(msg)
        if self.retrieval_chunk_overlap >= self.retrieval_chunk_size:
            msg = (
                f"retrieval_chunk_overlap({self.retrieval_chunk_overlap}) "
                f"必须小于 retrieval_chunk_size({self.retrieval_chunk_size})"
            )
            raise ValueError(msg)
        if self.composition_chunk_overlap >= self.composition_chunk_size:
            msg = (
                f"composition_chunk_overlap({self.composition_chunk_overlap}) "
                f"必须小于 composition_chunk_size({self.composition_chunk_size})"
            )
            raise ValueError(msg)
        if self.retrieval_chunk_size >= self.composition_chunk_size:
            msg = (
                f"retrieval_chunk_size({self.retrieval_chunk_size}) "
                f"必须小于 composition_chunk_size({self.composition_chunk_size})"
            )
            raise ValueError(msg)
        if self.mapping_strategy not in {"overlap", "containment", "nearest"}:
            msg = (
                f"mapping_strategy 必须是 'overlap', 'containment' 或 'nearest', "
                f"当前值: {self.mapping_strategy}"
            )
            raise ValueError(msg)


@dataclass(slots=True)
class ChunkMapping:
    """
    检索块与合成块的映射关系

    Attributes:
        retrieval_node_id: 检索块节点ID
        composition_node_id: 合成块节点ID
        mapping_type: 映射类型（overlap/containment/nearest）
        overlap_ratio: 重叠比例（0-1之间）
    """

    retrieval_node_id: str
    composition_node_id: str
    mapping_type: str
    overlap_ratio: float = 0.0


class RetrievalCompositionSplitter:
    """
    检索块与合成块分离器

    实现双层分块策略，将文档分为检索块和合成块，并建立两者之间的映射关系。
    检索时使用检索块进行语义检索，生成时使用对应的合成块提供上下文。

    典型用法:
        >>> splitter = RetrievalCompositionSplitter()
        >>> retrieval_nodes, composition_nodes, mappings = splitter.split_nodes(nodes)
        >>> # 检索时使用 retrieval_nodes
        >>> # 生成时根据 mappings 找到对应的 composition_nodes
    """

    def __init__(
        self, config: RetrievalCompositionConfig | None = None
    ) -> None:
        """
        初始化分离器

        Args:
            config: 检索块与合成块分离配置，如果为None则使用默认配置
        """
        if not LLAMA_INDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not available. Please install llama-index package to "
                "use RetrievalCompositionSplitter."
            )

        self.config = config or RetrievalCompositionConfig()

        # 创建检索块分割器（较小的块）
        self._retrieval_splitter = SentenceSplitter(
            chunk_size=self.config.retrieval_chunk_size,
            chunk_overlap=self.config.retrieval_chunk_overlap,
        )

        # 创建合成块分割器（较大的块）
        self._composition_splitter = SentenceSplitter(
            chunk_size=self.config.composition_chunk_size,
            chunk_overlap=self.config.composition_chunk_overlap,
        )

        logger.debug(
            "初始化 %s: retrieval_chunk_size=%s, composition_chunk_size=%s, "
            "mapping_strategy=%s",
            self.__class__.__name__,
            self.config.retrieval_chunk_size,
            self.config.composition_chunk_size,
            self.config.mapping_strategy,
        )

    def split_nodes(
        self, nodes: list[Node]
    ) -> tuple[list[Node], list[Node], list[ChunkMapping]]:
        """
        对节点列表进行检索块与合成块分离

        生成两层分块：
        1. 检索块：较小的块，用于语义检索
        2. 合成块：较大的块，用于生成上下文
        3. 映射关系：建立检索块与合成块的映射

        Args:
            nodes: LlamaIndex Node对象列表

        Returns:
            Tuple[检索块列表, 合成块列表, 映射关系列表]

        Raises:
            RetrievalCompositionSplitterError: 如果分块失败
        """
        if not nodes:
            logger.warning("空的 Node 列表, 不执行分块")
            return [], [], []

        # 第一步：生成合成块（较大的块，用于生成上下文）
        composition_nodes = self._create_composition_nodes(nodes)

        # 第二步：生成检索块（较小的块，用于语义检索）
        retrieval_nodes = self._create_retrieval_nodes(nodes)

        # 第三步：建立映射关系
        mappings = self._build_mappings(
            retrieval_nodes, composition_nodes, nodes
        )

        logger.info(
            "检索块与合成块分离完成: 原始节点数=%s, 检索块数=%s, "
            "合成块数=%s, 映射关系数=%s",
            len(nodes),
            len(retrieval_nodes),
            len(composition_nodes),
            len(mappings),
        )

        return retrieval_nodes, composition_nodes, mappings

    def _create_composition_nodes(self, nodes: list[Node]) -> list[Node]:
        """
        创建合成块（较大的块，用于生成上下文）

        Args:
            nodes: 原始节点列表

        Returns:
            合成块节点列表
        """
        composition_nodes: list[Node] = []
        global_composition_index = 0

        for node_index, node in enumerate(nodes):
            text = getattr(node, "text", None)
            if not text or not str(text).strip():
                logger.debug("跳过空文本节点: node_index=%s", node_index)
                continue

            base_metadata: dict[str, Any] = dict(
                getattr(node, "metadata", {}) or {}
            )

            # 使用合成块分割器进行分块
            try:
                split_texts = self._composition_splitter.split_text(str(text))
            except Exception as exc:  # pragma: no cover - 保护性分支
                logger.error("合成块分块失败: %s", exc, exc_info=True)
                raise RetrievalCompositionSplitterError(
                    f"合成块分块失败: {exc}"
                ) from exc

            if not split_texts:
                logger.debug(
                    "合成块分割器返回空结果, 保留原始节点: node_index=%s",
                    node_index,
                )
                # 如果分块失败，保留原始节点作为合成块
                composition_node = self._create_composition_node(
                    node, base_metadata, global_composition_index, node_index
                )
                composition_nodes.append(composition_node)
                global_composition_index += 1
                continue

            # 为每个合成块创建节点
            for chunk_index_in_node, chunk_text in enumerate(split_texts):
                if not chunk_text or not str(chunk_text).strip():
                    continue

                composition_node = self._create_composition_node(
                    node,
                    base_metadata,
                    global_composition_index,
                    node_index,
                    chunk_text,
                    chunk_index_in_node,
                )
                composition_nodes.append(composition_node)
                global_composition_index += 1

        return composition_nodes

    def _create_retrieval_nodes(self, nodes: list[Node]) -> list[Node]:
        """
        创建检索块（较小的块，用于语义检索）

        Args:
            nodes: 原始节点列表

        Returns:
            检索块节点列表
        """
        retrieval_nodes: list[Node] = []
        global_retrieval_index = 0

        for node_index, node in enumerate(nodes):
            text = getattr(node, "text", None)
            if not text or not str(text).strip():
                logger.debug("跳过空文本节点: node_index=%s", node_index)
                continue

            base_metadata: dict[str, Any] = dict(
                getattr(node, "metadata", {}) or {}
            )

            # 使用检索块分割器进行分块
            try:
                split_texts = self._retrieval_splitter.split_text(str(text))
            except Exception as exc:  # pragma: no cover - 保护性分支
                logger.error("检索块分块失败: %s", exc, exc_info=True)
                raise RetrievalCompositionSplitterError(
                    f"检索块分块失败: {exc}"
                ) from exc

            if not split_texts:
                logger.debug(
                    "检索块分割器返回空结果, 保留原始节点: node_index=%s",
                    node_index,
                )
                # 如果分块失败，保留原始节点作为检索块
                retrieval_node = self._create_retrieval_node(
                    node, base_metadata, global_retrieval_index, node_index
                )
                retrieval_nodes.append(retrieval_node)
                global_retrieval_index += 1
                continue

            # 为每个检索块创建节点
            for chunk_index_in_node, chunk_text in enumerate(split_texts):
                if not chunk_text or not str(chunk_text).strip():
                    continue

                retrieval_node = self._create_retrieval_node(
                    node,
                    base_metadata,
                    global_retrieval_index,
                    node_index,
                    chunk_text,
                    chunk_index_in_node,
                )
                retrieval_nodes.append(retrieval_node)
                global_retrieval_index += 1

        return retrieval_nodes

    def _create_composition_node(
        self,
        original_node: Node,
        base_metadata: dict[str, Any],
        global_index: int,
        original_node_index: int,
        chunk_text: str | None = None,
        chunk_index_in_node: int | None = None,
    ) -> Node:
        """
        创建合成块节点

        Args:
            original_node: 原始节点
            base_metadata: 基础元数据
            global_index: 全局索引
            original_node_index: 原始节点索引
            chunk_text: 分块文本（如果为None则使用原始节点文本）
            chunk_index_in_node: 在原始节点内的分块索引

        Returns:
            合成块节点
        """
        # 构建合成块元数据
        composition_metadata: dict[str, Any] = dict(base_metadata)
        composition_metadata["chunk_type"] = "composition"
        composition_metadata["composition_index"] = global_index
        composition_metadata["original_node_index"] = original_node_index

        if chunk_index_in_node is not None:
            composition_metadata["chunk_index_in_node"] = chunk_index_in_node

        # 生成节点ID
        node_id = f"composition_{global_index}_{str(uuid4())[:8]}"
        composition_metadata["node_id"] = node_id

        # 使用分块文本或原始文本
        text_content = (
            str(chunk_text) if chunk_text is not None else getattr(original_node, "text", "")
        )

        return TextNode(
            text=text_content,
            id_=node_id,
            metadata=composition_metadata,
        )

    def _create_retrieval_node(
        self,
        original_node: Node,
        base_metadata: dict[str, Any],
        global_index: int,
        original_node_index: int,
        chunk_text: str | None = None,
        chunk_index_in_node: int | None = None,
    ) -> Node:
        """
        创建检索块节点

        Args:
            original_node: 原始节点
            base_metadata: 基础元数据
            global_index: 全局索引
            original_node_index: 原始节点索引
            chunk_text: 分块文本（如果为None则使用原始节点文本）
            chunk_index_in_node: 在原始节点内的分块索引

        Returns:
            检索块节点
        """
        # 构建检索块元数据
        retrieval_metadata: dict[str, Any] = dict(base_metadata)
        retrieval_metadata["chunk_type"] = "retrieval"
        retrieval_metadata["retrieval_index"] = global_index
        retrieval_metadata["original_node_index"] = original_node_index

        if chunk_index_in_node is not None:
            retrieval_metadata["chunk_index_in_node"] = chunk_index_in_node

        # 生成节点ID
        node_id = f"retrieval_{global_index}_{str(uuid4())[:8]}"
        retrieval_metadata["node_id"] = node_id

        # 使用分块文本或原始文本
        text_content = (
            str(chunk_text) if chunk_text is not None else getattr(original_node, "text", "")
        )

        return TextNode(
            text=text_content,
            id_=node_id,
            metadata=retrieval_metadata,
        )

    def _build_mappings(
        self,
        retrieval_nodes: list[Node],
        composition_nodes: list[Node],
        original_nodes: list[Node],
    ) -> list[ChunkMapping]:
        """
        建立检索块与合成块的映射关系

        根据配置的映射策略，建立检索块与合成块之间的映射关系。

        Args:
            retrieval_nodes: 检索块节点列表
            composition_nodes: 合成块节点列表
            original_nodes: 原始节点列表（用于确定位置关系）

        Returns:
            映射关系列表
        """
        mappings: list[ChunkMapping] = []

        if self.config.mapping_strategy == "overlap":
            mappings = self._build_overlap_mappings(
                retrieval_nodes, composition_nodes
            )
        elif self.config.mapping_strategy == "containment":
            mappings = self._build_containment_mappings(
                retrieval_nodes, composition_nodes
            )
        elif self.config.mapping_strategy == "nearest":
            mappings = self._build_nearest_mappings(
                retrieval_nodes, composition_nodes, original_nodes
            )

        logger.debug(
            "建立映射关系: 策略=%s, 映射数=%s",
            self.config.mapping_strategy,
            len(mappings),
        )

        return mappings

    def _build_overlap_mappings(
        self, retrieval_nodes: list[Node], composition_nodes: list[Node]
    ) -> list[ChunkMapping]:
        """
        基于重叠区域建立映射关系

        对于每个检索块，找到与其有最大重叠的合成块。

        Args:
            retrieval_nodes: 检索块节点列表
            composition_nodes: 合成块节点列表

        Returns:
            映射关系列表
        """
        mappings: list[ChunkMapping] = []

        for retrieval_node in retrieval_nodes:
            retrieval_text = getattr(retrieval_node, "text", "")
            retrieval_id = getattr(retrieval_node, "id_", "")

            if not retrieval_text or not retrieval_id:
                continue

            best_composition: Node | None = None
            best_overlap_ratio = 0.0

            # 找到重叠度最高的合成块
            for composition_node in composition_nodes:
                composition_text = getattr(composition_node, "text", "")
                composition_id = getattr(composition_node, "id_", "")

                if not composition_text or not composition_id:
                    continue

                # 计算重叠比例（简单的文本重叠计算）
                overlap_ratio = self._calculate_text_overlap(
                    retrieval_text, composition_text
                )

                if overlap_ratio > best_overlap_ratio:
                    best_overlap_ratio = overlap_ratio
                    best_composition = composition_node

            # 如果找到重叠的合成块，创建映射
            if best_composition and best_overlap_ratio > 0:
                composition_id = getattr(best_composition, "id_", "")
                mapping = ChunkMapping(
                    retrieval_node_id=retrieval_id,
                    composition_node_id=composition_id,
                    mapping_type="overlap",
                    overlap_ratio=best_overlap_ratio,
                )
                mappings.append(mapping)

        return mappings

    def _build_containment_mappings(
        self, retrieval_nodes: list[Node], composition_nodes: list[Node]
    ) -> list[ChunkMapping]:
        """
        基于包含关系建立映射关系

        对于每个检索块，找到包含它的合成块。

        Args:
            retrieval_nodes: 检索块节点列表
            composition_nodes: 合成块节点列表

        Returns:
            映射关系列表
        """
        mappings: list[ChunkMapping] = []

        for retrieval_node in retrieval_nodes:
            retrieval_text = getattr(retrieval_node, "text", "")
            retrieval_id = getattr(retrieval_node, "id_", "")

            if not retrieval_text or not retrieval_id:
                continue

            # 找到包含检索块的合成块
            for composition_node in composition_nodes:
                composition_text = getattr(composition_node, "text", "")
                composition_id = getattr(composition_node, "id_", "")

                if not composition_text or not composition_id:
                    continue

                # 检查检索块是否被合成块包含
                if retrieval_text in composition_text:
                    mapping = ChunkMapping(
                        retrieval_node_id=retrieval_id,
                        composition_node_id=composition_id,
                        mapping_type="containment",
                        overlap_ratio=1.0,
                    )
                    mappings.append(mapping)
                    break  # 找到第一个包含的合成块即可

        return mappings

    def _build_nearest_mappings(
        self,
        retrieval_nodes: list[Node],
        composition_nodes: list[Node],
        original_nodes: list[Node],
    ) -> list[ChunkMapping]:
        """
        基于最近距离建立映射关系

        根据原始节点的位置关系，找到最近的合成块。

        Args:
            retrieval_nodes: 检索块节点列表
            composition_nodes: 合成块节点列表
            original_nodes: 原始节点列表

        Returns:
            映射关系列表
        """
        mappings: list[ChunkMapping] = []

        # 构建索引：原始节点索引 -> 合成块节点
        composition_by_original: dict[int, list[Node]] = {}
        for composition_node in composition_nodes:
            original_index = composition_node.metadata.get(
                "original_node_index", -1
            )
            if original_index >= 0:
                if original_index not in composition_by_original:
                    composition_by_original[original_index] = []
                composition_by_original[original_index].append(composition_node)

        # 为每个检索块找到最近的合成块
        for retrieval_node in retrieval_nodes:
            retrieval_id = getattr(retrieval_node, "id_", "")
            original_index = retrieval_node.metadata.get(
                "original_node_index", -1
            )

            if not retrieval_id or original_index < 0:
                continue

            # 优先使用相同原始节点的合成块
            if original_index in composition_by_original:
                composition_node = composition_by_original[original_index][0]
                composition_id = getattr(composition_node, "id_", "")
                mapping = ChunkMapping(
                    retrieval_node_id=retrieval_id,
                    composition_node_id=composition_id,
                    mapping_type="nearest",
                    overlap_ratio=1.0,
                )
                mappings.append(mapping)
                continue

            # 如果找不到相同原始节点的合成块，使用最近的
            # 这里简化处理，使用第一个合成块
            if composition_nodes:
                composition_node = composition_nodes[0]
                composition_id = getattr(composition_node, "id_", "")
                mapping = ChunkMapping(
                    retrieval_node_id=retrieval_id,
                    composition_node_id=composition_id,
                    mapping_type="nearest",
                    overlap_ratio=0.5,  # 默认重叠比例
                )
                mappings.append(mapping)

        return mappings

    def _calculate_text_overlap(self, text1: str, text2: str) -> float:
        """
        计算两个文本的重叠比例

        使用简单的字符重叠计算，返回0-1之间的重叠比例。

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            重叠比例（0-1之间）
        """
        if not text1 or not text2:
            return 0.0

        # 简单的重叠计算：计算公共子串的长度比例
        # 这里使用简化的方法：计算较短的文本在较长文本中的出现比例
        shorter = text1 if len(text1) < len(text2) else text2
        longer = text2 if len(text1) < len(text2) else text1

        # 计算重叠字符数（简单的子串匹配）
        overlap_chars = 0
        for i in range(len(shorter)):
            if i < len(longer) and shorter[i] == longer[i]:
                overlap_chars += 1

        if len(shorter) == 0:
            return 0.0

        return overlap_chars / len(shorter)

    def get_composition_nodes_for_retrieval(
        self, retrieval_node_ids: list[str], mappings: list[ChunkMapping]
    ) -> list[str]:
        """
        根据检索块ID获取对应的合成块ID列表

        用于检索后，根据检索到的检索块，找到对应的合成块用于生成上下文。

        Args:
            retrieval_node_ids: 检索块ID列表
            mappings: 映射关系列表

        Returns:
            合成块ID列表（去重）
        """
        composition_ids: set[str] = set()

        # 构建检索块ID到合成块ID的映射
        retrieval_to_composition: dict[str, str] = {}
        for mapping in mappings:
            retrieval_to_composition[
                mapping.retrieval_node_id
            ] = mapping.composition_node_id

        # 根据检索块ID查找对应的合成块ID
        for retrieval_id in retrieval_node_ids:
            if retrieval_id in retrieval_to_composition:
                composition_ids.add(
                    retrieval_to_composition[retrieval_id]
                )

        return list(composition_ids)

