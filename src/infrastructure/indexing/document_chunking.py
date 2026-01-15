"""
文档分块策略实现 (T052)

该模块实现文档分块策略, 使用 LlamaIndex 的 SentenceSplitter 进行句子级分块,
并在此基础上支持按章节和段落进行分块, 保留丰富的分块元数据.

同时提供基于语义的分块策略(SemanticChunkingStrategy), 能够在保持最小分块大小的
同时在语义边界处分割, 提高检索精度.

设计目标:
- 使用 ``llama_index.core.node_parser.SentenceSplitter`` 进行句子级分块
- 支持按章节分块(保留章节路径信息)
- 支持按段落分块(保留段落结构信息)
- 支持语义分块(在语义边界分割, 保持最小块大小)
- 支持自定义块大小和重叠策略
- 保留分块元数据(章节路径,段落索引,文档位置等)
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
    SentenceSplitter = Any  # type: ignore
    Node = Any  # type: ignore
    TextNode = Any  # type: ignore
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
        chunking_mode: 分块模式，可选值: "fixed"(固定大小), "semantic"(语义分块)
        min_chunk_size: 最小分块大小(语义分块模式有效)，确保召回率
        max_chunk_size: 最大分块大小(语义分块模式有效)，防止块过大
    """

    chunk_size: int = 1024
    chunk_overlap: int = 200
    split_by_section: bool = True
    split_by_paragraph: bool = True
    chunking_mode: str = "semantic"  # 默认使用语义分块
    min_chunk_size: int = 1000  # 最小分块大小，确保召回率
    max_chunk_size: int = 2048  # 最大分块大小，防止块过大

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
        if self.chunking_mode not in ("fixed", "semantic"):
            msg = f"chunking_mode 必须为 'fixed' 或 'semantic', 当前值: {self.chunking_mode}"
            raise ValueError(msg)
        if self.min_chunk_size <= 0:
            msg = f"min_chunk_size 必须为正整数, 当前值: {self.min_chunk_size}"
            raise ValueError(msg)
        if self.max_chunk_size <= 0:
            msg = f"max_chunk_size 必须为正整数, 当前值: {self.max_chunk_size}"
            raise ValueError(msg)
        if self.min_chunk_size > self.max_chunk_size:
            msg = f"min_chunk_size({self.min_chunk_size}) 不能大于 max_chunk_size({self.max_chunk_size})"
            raise ValueError(msg)


class DocumentChunkingStrategy:
    """
    文档分块策略

    使用 SentenceSplitter 对 LlamaIndex Node 进行句子级分块, 并在此基础上
    保留章节路径和段落索引等元数据, 便于后续索引和检索.

    典型用法:
        >>> strategy = DocumentChunkingStrategy()
        >>> chunked_nodes = strategy.chunk_nodes(nodes)
    """

    # 被视为"段落类"元素的 element_type 值(来自 MarkdownParser)
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
            msg = (
                "LlamaIndex is not available. Please install llama-index package to "
                "use DocumentChunkingStrategy."
            )
            raise ImportError(
                msg
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
        - 保留章节路径(section_path),章节标题(section_title)
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
                msg = f"SentenceSplitter 分块失败: {exc}"
                raise ChunkingError(msg) from exc

            if not split_texts:
                logger.debug("SentenceSplitter 返回空结果, 保留原始节点: node_index=%s", node_index)
                # 确保保留的原始节点也有 original_node_index 设置
                if hasattr(node, "metadata") and node.metadata:
                    node.metadata["original_node_index"] = node_index
                else:
                    # 如果节点没有 metadata，创建一个
                    node.metadata = {"original_node_index": node_index}
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
                chunked_nodes.append(chunk_node)  # type: ignore[arg-type]
                global_chunk_index += 1

        logger.info(
            "文档分块完成: 原始节点数=%s, 分块后节点数=%s, chunk_size=%s, overlap=%s",
            len(nodes),
            len(chunked_nodes),
            self.config.chunk_size,
            self.config.chunk_overlap,
        )

        return chunked_nodes


class SemanticChunkingStrategy:
    """
    基于语义的分块策略

    该策略旨在解决固定大小分块的局限性，通过以下方式提高检索质量:
    1. 在语义边界(段落、章节、子章节)处分割
    2. 保持最小分块大小(默认1000字符)，确保召回率
    3. 智能合并小段落以达到最小大小
    4. 在语义中断点处分割大段落

    分块逻辑:
    - 首先识别文档中的语义单元(段落、章节标题、列表、表格等)
    - 将连续的小段落合并以达到最小分块大小
    - 对于大于最大分块大小的段落，在子标题或逻辑中断处分割
    - 保持相邻块之间的上下文连续性

    典型用法:
        >>> config = ChunkingConfig(
        ...     chunking_mode="semantic",
        ...     min_chunk_size=1000,
        ...     max_chunk_size=2048,
        ...     chunk_overlap=200,
        ... )
        >>> strategy = SemanticChunkingStrategy(config)
        >>> chunks = strategy.chunk_nodes(nodes)
    """

    # 被视为"段落类"元素的 element_type 值
    _PARAGRAPH_LIKE_ELEMENT_TYPES = {
        "paragraph",
        "list_item",
        "list",
        "table",
        "code_block",
        "quote",
    }

    # 被视为"标题类"元素的 element_type 值
    _HEADING_ELEMENT_TYPES = {
        "heading",
        "section_title",
    }

    def __init__(self, config: ChunkingConfig | None = None) -> None:
        if not LLAMA_INDEX_AVAILABLE:
            msg = (
                "LlamaIndex is not available. Please install llama-index package to "
                "use SemanticChunkingStrategy."
            )
            raise ImportError(msg)

        self.config = config or ChunkingConfig()

        # 验证配置
        if self.config.chunking_mode != "semantic":
            logger.warning(
                "SemanticChunkingStrategy 需要 chunking_mode='semantic', "
                "当前值: %s, 已自动调整",
                self.config.chunking_mode,
            )
            self.config.chunking_mode = "semantic"

        logger.debug(
            "初始化 %s: min_chunk_size=%s, max_chunk_size=%s, chunk_overlap=%s, "
            "split_by_section=%s",
            self.__class__.__name__,
            self.config.min_chunk_size,
            self.config.max_chunk_size,
            self.config.chunk_overlap,
            self.config.split_by_section,
        )

    def chunk_nodes(self, nodes: list[Node]) -> list[Node]:
        """
        对 LlamaIndex Node 列表进行语义分块

        分块策略:
        1. 将节点按语义单元分组(章节内连续的相关内容)
        2. 合并小单元以达到最小分块大小
        3. 必要时在语义边界处分割大单元
        4. 保留章节路径、段落索引等元数据

        Args:
            nodes: 由 MarkdownParser 等组件生成的 LlamaIndex Node 列表

        Returns:
            分块后的 Node 列表
        """
        if not nodes:
            logger.warning("空的 Node 列表, 不执行分块")
            return []

        # 步骤1: 将节点组织为语义单元
        semantic_units = self._group_into_semantic_units(nodes)

        if not semantic_units:
            logger.warning("无法构建语义单元, 降级到 SentenceSplitter")
            return self._fallback_chunk(nodes)

        # 步骤2: 对语义单元进行分块
        chunks = self._chunk_semantic_units(semantic_units)

        logger.info(
            "语义分块完成: 原始节点数=%s, 分块后节点数=%s, 语义单元数=%s",
            len(nodes),
            len(chunks),
            len(semantic_units),
        )

        return chunks

    def _group_into_semantic_units(self, nodes: list[Node]) -> list[dict[str, Any]]:
        """
        将节点组织为语义单元

        语义单元是文档中具有连贯主题的内容块，通常包含:
        - 一个标题(可选)
        - 一个或多个段落
        - 相关的列表、表格等

        Args:
            nodes: 原始节点列表

        Returns:
            语义单元列表，每个单元包含 nodes、metadata、text 等信息
        """
        semantic_units: list[dict[str, Any]] = []
        current_unit: dict[str, Any] = {
            "nodes": [],
            "text": "",
            "section_path": "",
            "section_title": "",
            "heading_text": "",
        }
        current_heading_level = float("inf")

        def _extract_image_files_from_text(t: str) -> list[str]:
            """从 markdown 文本中提取 images/<file> 引用，作为 images.files 的兜底来源。"""
            import re

            text = t or ""
            # 支持 ![](images/xxx.jpg) / ![alt](images/xxx.png) / ![](./images/xxx)
            pat = re.compile(r"!\\[[^\\]]*\\]\\((?:\\./)?images/([^\\)]+)\\)")
            files: list[str] = []
            for m in pat.finditer(text):
                fn = (m.group(1) or "").strip()
                if fn:
                    files.append(fn)
            # 去重保持顺序
            seen: set[str] = set()
            out: list[str] = []
            for f in files:
                if f in seen:
                    continue
                seen.add(f)
                out.append(f)
            return out

        for node in nodes:
            text = getattr(node, "text", None)
            if not text or not str(text).strip():
                continue

            metadata = dict(getattr(node, "metadata", {}) or {})
            element_type = str(metadata.get("element_type", "")).lower()
            section_path = str(metadata.get("section_path", ""))
            section_title = metadata.get("section_title")
            heading_level = metadata.get("heading_level", float("inf"))

            # 检测是否是标题节点
            is_heading = (
                element_type in self._HEADING_ELEMENT_TYPES
                or heading_level != float("inf")
            )

            if is_heading:
                # 如果当前单元已经有内容，保存它并开始新单元
                if current_unit["nodes"]:
                    semantic_units.append(current_unit)
                    current_unit = {
                        "nodes": [],
                        "text": "",
                        "section_path": section_path,
                        "section_title": section_title or "",
                        "heading_text": str(text).strip(),
                    }
                    current_heading_level = heading_level
                else:
                    # 更新当前单元的标题信息
                    current_unit["section_path"] = section_path
                    current_unit["section_title"] = section_title or ""
                    current_unit["heading_text"] = str(text).strip()
                    current_heading_level = heading_level
            else:
                # 累积内容
                current_unit["nodes"].append(node)
                if current_unit["text"]:
                    current_unit["text"] += "\n\n"
                current_unit["text"] += str(text).strip()
                
                # 如果当前单元还没有section_path，从节点中获取（第一个非标题节点可能包含章节信息）
                if not current_unit.get("section_path") and section_path:
                    current_unit["section_path"] = section_path
                if not current_unit.get("section_title") and section_title:
                    current_unit["section_title"] = section_title
                
                # 保留第一个节点的图片和图表信息到语义单元
                if not current_unit.get("images") and "images" in metadata:
                    current_unit["images"] = metadata["images"]
                if not current_unit.get("charts") and "charts" in metadata:
                    current_unit["charts"] = metadata["charts"]

                # 兜底：如果元数据里没有 images，但正文包含 markdown 图片引用，则提取成 images.files
                if not current_unit.get("images"):
                    extracted = _extract_image_files_from_text(current_unit.get("text", ""))
                    if extracted:
                        current_unit["images"] = {"count": len(extracted), "files": extracted}
                # 保留文档级别的元数据
                for key in ["document_id", "document_name", "file_path", "filename", "source"]:
                    if key not in current_unit and key in metadata:
                        current_unit[key] = metadata[key]

        # 保存最后一个单元
        if current_unit["nodes"]:
            semantic_units.append(current_unit)

        return semantic_units

    def _chunk_semantic_units(self, semantic_units: list[dict[str, Any]]) -> list[Node]:
        """
        对语义单元进行分块

        策略:
        - 如果单元大小在 [min_chunk_size, max_chunk_size] 之间，保持不变
        - 如果单元太小，尝试与相邻单元合并
        - 如果单元太大，在语义边界处分割

        Args:
            semantic_units: 语义单元列表

        Returns:
            分块后的 Node 列表
        """
        chunks: list[Node] = []
        global_chunk_index = 0

        i = 0
        while i < len(semantic_units):
            unit = semantic_units[i]
            unit_text = unit["text"]
            unit_size = len(unit_text)

            # 情况1: 单元大小合适，直接作为一块
            if self.config.min_chunk_size <= unit_size <= self.config.max_chunk_size:
                chunk = self._create_chunk_node(unit, global_chunk_index, 0)
                chunks.append(chunk)
                global_chunk_index += 1
                i += 1

            # 情况2: 单元太小，尝试向后合并
            elif unit_size < self.config.min_chunk_size:
                merged_text = unit_text
                merged_nodes = list(unit["nodes"])
                merged_unit = unit

                # 尝试合并后续单元直到达到最小大小
                j = i + 1
                while j < len(semantic_units) and len(merged_text) < self.config.min_chunk_size:
                    next_unit = semantic_units[j]
                    merged_text += "\n\n" + next_unit["text"]
                    merged_nodes.extend(next_unit["nodes"])

                    # 如果合并后超出最大大小，只合并到最大大小
                    if len(merged_text) > self.config.max_chunk_size:
                        # 从下一个单元中截取需要的部分
                        remaining = self.config.max_chunk_size - len(merged_text) + len(next_unit["text"])
                        if remaining > 0 and remaining < len(next_unit["text"]):
                            # 分割下一个单元，保留部分用于当前块
                            excess_text = next_unit["text"][remaining:]
                            excess_nodes = next_unit["nodes"]

                            # 更新下一个单元，去除已合并的内容
                            next_unit["text"] = excess_text
                            # 保留元数据但调整内容
                            merged_unit = {
                                "nodes": merged_nodes,
                                "text": merged_text[:self.config.max_chunk_size],
                                "section_path": unit["section_path"],
                                "section_title": unit["section_title"],
                                "heading_text": unit["heading_text"],
                            }
                        break
                    j += 1

                chunk = self._create_chunk_node(merged_unit, global_chunk_index, 0)
                chunks.append(chunk)
                global_chunk_index += 1

                # 如果j没有移动，仍需要处理下一个单元
                if j == i + 1:
                    i = j
                else:
                    i = j - 1 if j > i + 1 else i + 1

            # 情况3: 单元太大，需要在语义边界处分割
            else:  # unit_size > self.config.max_chunk_size
                # 使用 SentenceSplitter 进行粗分割
                splitter = SentenceSplitter(
                    chunk_size=self.config.max_chunk_size,
                    chunk_overlap=self.config.chunk_overlap,
                )
                split_texts = splitter.split_text(unit_text)

                for chunk_index_in_unit, chunk_text in enumerate(split_texts):
                    if not chunk_text.strip():
                        continue

                    # 创建元数据，保留图片和图表信息
                    chunk_metadata = {
                        "section_path": unit.get("section_path", ""),
                        "section_title": unit.get("section_title", ""),
                        "heading_text": unit.get("heading_text", ""),
                        "chunk_index": global_chunk_index,
                        "chunk_index_in_node": chunk_index_in_unit,
                    }
                    
                    # 从语义单元中提取并保留重要元数据（图片、图表等）
                    # 优先从语义单元中获取（已在 _group_into_semantic_units 中收集）
                    if unit.get("images"):
                        chunk_metadata["images"] = unit["images"]
                    if unit.get("charts"):
                        chunk_metadata["charts"] = unit["charts"]
                    for key in ["document_id", "document_name", "file_path", "filename", "source"]:
                        if key in unit:
                            chunk_metadata[key] = unit[key]
                    
                    # 如果语义单元中没有section_path，尝试从原始节点中获取
                    if not chunk_metadata.get("section_path") and unit.get("nodes"):
                        first_node = unit["nodes"][0]
                        first_metadata = dict(getattr(first_node, "metadata", {}) or {})
                        if "section_path" in first_metadata and first_metadata["section_path"]:
                            chunk_metadata["section_path"] = first_metadata["section_path"]
                        if not chunk_metadata.get("section_title") and "section_title" in first_metadata:
                            chunk_metadata["section_title"] = first_metadata["section_title"]
                    
                    # 如果语义单元中没有，尝试从原始节点中获取其他元数据
                    if unit.get("nodes"):
                        first_node = unit["nodes"][0]
                        first_metadata = dict(getattr(first_node, "metadata", {}) or {})
                        
                        # 保留图片信息（如果语义单元中没有）
                        if "images" not in chunk_metadata and "images" in first_metadata:
                            chunk_metadata["images"] = first_metadata["images"]
                        
                        # 保留图表信息（如果语义单元中没有）
                        if "charts" not in chunk_metadata and "charts" in first_metadata:
                            chunk_metadata["charts"] = first_metadata["charts"]
                        
                        # 保留文档级别的元数据（如果语义单元中没有）
                        for key in ["document_id", "document_name", "file_path", "filename", "source"]:
                            if key not in chunk_metadata and key in first_metadata:
                                chunk_metadata[key] = first_metadata[key]

                    chunk_node = TextNode(
                        text=chunk_text.strip(),
                        metadata=chunk_metadata,
                    )
                    chunks.append(chunk_node)
                    global_chunk_index += 1

                i += 1

        # 应用重叠
        if self.config.chunk_overlap > 0 and len(chunks) > 1:
            chunks = self._apply_overlap(chunks)

        return chunks

    def _create_chunk_node(
        self,
        unit: dict[str, Any],
        chunk_index: int,
        chunk_index_in_node: int
    ) -> TextNode:
        """创建分块节点"""
        metadata: dict[str, Any] = {
            "section_path": unit.get("section_path", ""),
            "chunk_index": chunk_index,
            "chunk_index_in_node": chunk_index_in_node,
        }

        if unit.get("section_title"):
            metadata["section_title"] = unit["section_title"]

        if unit.get("heading_text"):
            metadata["heading_text"] = unit["heading_text"]

        # 从语义单元中提取并保留重要元数据（图片、图表等）
        # 优先从语义单元中获取（已在 _group_into_semantic_units 中收集）
        if unit.get("images"):
            metadata["images"] = unit["images"]
        if unit.get("charts"):
            metadata["charts"] = unit["charts"]
        for key in ["document_id", "document_name", "file_path", "filename", "source"]:
            if key in unit:
                metadata[key] = unit[key]

        # 从原始节点中提取并保留其他重要元数据
        if unit.get("nodes"):
            first_node = unit["nodes"][0]
            first_metadata = dict(getattr(first_node, "metadata", {}) or {})
            
            # 如果语义单元中没有section_path，尝试从节点中获取
            if not metadata.get("section_path") and "section_path" in first_metadata and first_metadata["section_path"]:
                metadata["section_path"] = first_metadata["section_path"]
            if not metadata.get("section_title") and "section_title" in first_metadata:
                metadata["section_title"] = first_metadata["section_title"]
            
            # 添加段落索引
            paragraph_index = first_metadata.get("paragraph_index")
            if paragraph_index is not None:
                metadata["paragraph_index"] = paragraph_index
            
            # 如果语义单元中没有图片/图表信息，尝试从节点中获取
            if "images" not in metadata and "images" in first_metadata:
                metadata["images"] = first_metadata["images"]
            if "charts" not in metadata and "charts" in first_metadata:
                metadata["charts"] = first_metadata["charts"]
            
            # 保留文档级别的元数据（如果语义单元中没有）
            for key in ["document_id", "document_name", "file_path", "filename", "source"]:
                if key not in metadata and key in first_metadata:
                    metadata[key] = first_metadata[key]
            
            # 保留其他重要元数据（如 element_type, heading_level 等）
            for key in ["element_type", "heading_level", "document_title_from_content"]:
                if key in first_metadata:
                    metadata[key] = first_metadata[key]

        return TextNode(
            text=unit["text"][:self.config.max_chunk_size],
            metadata=metadata,
        )

    def _apply_overlap(self, chunks: list[Node]) -> list[Node]:
        """
        在相邻块之间应用重叠

        Args:
            chunks: 分块后的节点列表

        Returns:
            带重叠的节点列表
        """
        if self.config.chunk_overlap <= 0 or len(chunks) < 2:
            return chunks

        overlapped_chunks: list[Node] = []
        overlap_chars = self.config.chunk_overlap

        for i, chunk in enumerate(chunks):
            chunk_text = getattr(chunk, "text", "")

            if i > 0 and len(chunk_text) > overlap_chars:
                # 从前一个块获取重叠内容
                prev_chunk = chunks[i - 1]
                prev_text = getattr(prev_chunk, "text", "")
                overlap_text = prev_text[-overlap_chars:]

                # 确保重叠内容是完整的句子或段落
                # 在中文中，寻找句号、问号、感叹号等标点
                for sep in ["。", "！", "？", "。 ", "\n\n", "\n"]:
                    sep_pos = overlap_text.rfind(sep)
                    if sep_pos > overlap_chars // 2:  # 确保有足够的重叠
                        overlap_text = overlap_text[sep_pos + len(sep):]
                        break

                # 合并重叠内容和新块
                combined_text = overlap_text + "\n\n" + chunk_text
                new_metadata = dict(getattr(chunk, "metadata", {}) or {})
                new_metadata["overlap_from_previous"] = True

                new_node = TextNode(text=combined_text, metadata=new_metadata)
                overlapped_chunks.append(new_node)
            else:
                overlapped_chunks.append(chunk)

        return overlapped_chunks

    def _fallback_chunk(self, nodes: list[Node]) -> list[Node]:
        """
        降级到 SentenceSplitter 分块

        当语义分块失败时使用
        """
        logger.warning("语义分块失败, 降级到 SentenceSplitter")
        strategy = DocumentChunkingStrategy(
            ChunkingConfig(
                chunk_size=self.config.max_chunk_size,
                chunk_overlap=self.config.chunk_overlap,
            )
        )
        return strategy.chunk_nodes(nodes)


