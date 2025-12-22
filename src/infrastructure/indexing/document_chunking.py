"""
文档分块策略实现 (T052)

该模块实现文档分块策略, 使用 LlamaIndex 的 SentenceSplitter 进行句子级分块,
并在此基础上支持按章节和段落进行分块, 保留丰富的分块元数据。

设计目标:
- 使用 ``llama_index.core.node_parser.SentenceSplitter`` 进行句子级分块
- 支持按章节分块(保留章节路径信息)
- 支持按段落分块(保留段落结构信息)
- 支持自定义块大小和重叠策略
- 保留分块元数据(章节路径、段落索引、文档位置等)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import Node, TextNode

    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 llama-index 时触发
    logger.warning(
        "LlamaIndex not available, document chunking with SentenceSplitter will be disabled"
    )
    SentenceSplitter = Any  # type: ignore[assignment]
    Node = Any  # type: ignore[assignment]
    TextNode = Any  # type: ignore[assignment]
    LLAMA_INDEX_AVAILABLE = False


class ChunkingError(Exception):
    """文档分块异常基类"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 简单字符串表示
        return f"文档分块错误: {self.message}"


@dataclass(slots=True)
class ChunkingConfig:
    """
    文档分块配置

    Attributes:
        chunk_size: 单个块的最大字符数
        chunk_overlap: 相邻块之间的重叠字符数
        split_by_section: 是否在语义上按章节对块进行组织(保留 section_path)
        split_by_paragraph: 是否为每个段落分配段落索引(paragraph_index)
    """

    chunk_size: int = 1024
    chunk_overlap: int = 200
    split_by_section: bool = True
    split_by_paragraph: bool = True

    def __post_init__(self) -> None:
        if self.chunk_size <= 0:
            msg = f"chunk_size 必须为正整数, 当前值: {self.chunk_size}"
            raise ValueError(msg)
        if self.chunk_overlap < 0:
            msg = f"chunk_overlap 不能为负数, 当前值: {self.chunk_overlap}"
            raise ValueError(msg)
        if self.chunk_overlap >= self.chunk_size:
            msg = (
                f"chunk_overlap({self.chunk_overlap}) 必须小于 chunk_size({self.chunk_size})"
            )
            raise ValueError(msg)


class DocumentChunkingStrategy:
    """
    文档分块策略

    使用 SentenceSplitter 对 LlamaIndex Node 进行句子级分块, 并在此基础上
    保留章节路径和段落索引等元数据, 便于后续索引和检索。

    典型用法:
        >>> strategy = DocumentChunkingStrategy()
        >>> chunked_nodes = strategy.chunk_nodes(nodes)
    """

    # 被视为“段落类”元素的 element_type 值(来自 MarkdownParser)
    _PARAGRAPH_LIKE_ELEMENT_TYPES = {
        "paragraph",
        "list_item",
        "list",
        "table",
        "code_block",
        "quote",
    }

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        if not LLAMA_INDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not available. Please install llama-index package to "
                "use DocumentChunkingStrategy."
            )

        self.config = config or ChunkingConfig()
        self._splitter = SentenceSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
        )

        logger.debug(
            "初始化 %s: chunk_size=%s, chunk_overlap=%s, "
            "split_by_section=%s, split_by_paragraph=%s",
            self.__class__.__name__,
            self.config.chunk_size,
            self.config.chunk_overlap,
            self.config.split_by_section,
            self.config.split_by_paragraph,
        )

    def chunk_nodes(self, nodes: list[Node]) -> list[Node]:
        """
        对 LlamaIndex Node 列表进行分块

        分块策略:
        - 使用 SentenceSplitter 进行句子级分块
        - 为每个分块保留原始节点的元数据
        - 保留章节路径(section_path)、章节标题(section_title)
        - 为段落类元素生成 paragraph_index
        - 为每个分块生成 chunk_index (文档内全局序号) 和
          chunk_index_in_node (在原始节点内的序号)

        Args:
            nodes: 由 MarkdownParser 等组件生成的 LlamaIndex Node 列表

        Returns:
            分块后的 Node 列表
        """
        if not nodes:
            logger.warning("空的 Node 列表, 不执行分块")
            return []

        chunked_nodes: list[Node] = []

        # 每个章节的段落计数器: section_path -> 段落计数
        section_paragraph_counters: dict[str, int] = defaultdict(int)

        # 文档级别的块序号(全局)
        global_chunk_index = 0

        for node_index, node in enumerate(nodes):
            # Node.text 是 TextNode 的标准接口
            text = getattr(node, "text", None)
            if not text or not str(text).strip():
                logger.debug("跳过空文本节点: node_index=%s", node_index)
                continue

            base_metadata: dict[str, Any] = dict(getattr(node, "metadata", {}) or {})
            section_path = str(base_metadata.get("section_path", ""))
            section_title = base_metadata.get("section_title")

            element_type_raw = base_metadata.get("element_type", "")
            element_type = (
                str(element_type_raw).lower() if element_type_raw is not None else ""
            )

            # 计算段落索引
            paragraph_index: int | None = None
            if self.config.split_by_paragraph and (
                not element_type or element_type in self._PARAGRAPH_LIKE_ELEMENT_TYPES
            ):
                key = section_path or "root"
                section_paragraph_counters[key] += 1
                paragraph_index = section_paragraph_counters[key]

            # 使用 SentenceSplitter 进行句子级分块
            try:
                split_texts = self._splitter.split_text(str(text))
            except Exception as exc:  # pragma: no cover - 保护性分支
                logger.error("使用 SentenceSplitter 分块失败: %s", exc, exc_info=True)
                raise ChunkingError(f"SentenceSplitter 分块失败: {exc}") from exc

            if not split_texts:
                logger.debug("SentenceSplitter 返回空结果, 保留原始节点: node_index=%s", node_index)
                chunked_nodes.append(node)
                continue

            for chunk_index_in_node, chunk_text in enumerate(split_texts):
                if not chunk_text or not str(chunk_text).strip():
                    continue

                # 基于原始元数据构造块级元数据
                chunk_metadata: dict[str, Any] = dict(base_metadata)

                # 章节信息(按章节分块时保持清晰的章节路径)
                if self.config.split_by_section and section_path:
                    chunk_metadata.setdefault("section_path", section_path)
                if section_title:
                    chunk_metadata.setdefault("section_title", section_title)

                # 段落和位置相关元数据
                chunk_metadata["chunk_index"] = global_chunk_index
                chunk_metadata["chunk_index_in_node"] = chunk_index_in_node
                chunk_metadata["original_node_index"] = node_index

                if paragraph_index is not None:
                    # 段落级索引(在所属章节内的段落序号)
                    chunk_metadata.setdefault("paragraph_index", paragraph_index)

                # 创建新的 TextNode, 保留与 DocumentConverter 一致的类型
                chunk_node = TextNode(
                    text=str(chunk_text),
                    metadata=chunk_metadata,
                )
                chunked_nodes.append(chunk_node)
                global_chunk_index += 1

        logger.info(
            "文档分块完成: 原始节点数=%s, 分块后节点数=%s, chunk_size=%s, overlap=%s",
            len(nodes),
            len(chunked_nodes),
            self.config.chunk_size,
            self.config.chunk_overlap,
        )

        return chunked_nodes


