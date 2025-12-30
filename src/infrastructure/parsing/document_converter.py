# 生成命令: /speckit.implement T059
# 生成时间: 2025-12-19
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
Document格式转换适配器

该模块实现LangChain Document到LlamaIndex Node的转换适配器.
遵循LangChain 1.0和LlamaIndex最佳实践,提供统一的格式转换接口.

参考最佳实践:
- LangChain 1.0: 使用langchain_core.documents.Document作为标准文档格式
- LlamaIndex: 使用llama_index.core.schema.Node作为节点格式
- 保留完整的元数据信息,确保可追溯性
"""

import hashlib
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from langchain_core.documents import Document

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.schema import (
        Node,
        NodeRelationship,
        RelatedNodeInfo,
        TextNode,
    )
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    logger.warning("LlamaIndex not available, Node conversion will be disabled")
    LLAMA_INDEX_AVAILABLE = False
    # 定义占位符类型,避免类型检查错误
    Node = Any  # type: ignore
    TextNode = Any  # type: ignore
    NodeRelationship = Any  # type: ignore
    RelatedNodeInfo = Any  # type: ignore


class LangChainDocumentToNodeConverter:
    """
    LangChain Document到LlamaIndex Node转换器

    将langchain_core.documents.Document转换为llama_index.core.schema.Node,
    保留完整的元数据信息,支持自定义节点ID生成策略.

    功能特性:
    - 支持单个和批量转换
    - 保留所有元数据信息(source,format,page,processed_at等)
    - 支持自定义节点ID生成策略
    - 完善的错误处理和日志记录
    - 遵循LangChain 1.0和LlamaIndex最佳实践

    示例:
        >>> converter = LangChainDocumentToNodeConverter()
        >>> nodes = converter.convert_documents([document1, document2])
        >>> for node in nodes:
        ...     print(node.text)
        ...     print(node.metadata)
    """

    def __init__(
        self,
        node_id_generator: Callable[[Document], str] | None = None,
        preserve_metadata: bool = True,
    ):
        """
        初始化转换器

        Args:
            node_id_generator: 自定义节点ID生成函数,接受Document对象,返回节点ID字符串
                              如果为None,则使用默认的UUID生成策略
            preserve_metadata: 是否保留所有元数据,默认为True
        """
        self.node_id_generator = node_id_generator or self._default_node_id_generator
        self.preserve_metadata = preserve_metadata

        logger.debug(
            f"初始化 {self.__class__.__name__}: "
            f"preserve_metadata={preserve_metadata}, "
            f"custom_id_generator={node_id_generator is not None}"
        )

    def convert_document(self, document: Document) -> Node:
        """
        转换单个Document为Node

        Args:
            document: LangChain Document对象

        Returns:
            Node: LlamaIndex Node对象

        Raises:
            ValueError: 如果Document对象无效
            ImportError: 如果LlamaIndex未安装
        """
        if not LLAMA_INDEX_AVAILABLE:
            msg = "LlamaIndex is not available. Please install llama-index package."
            raise ImportError(msg)

        if not isinstance(document, Document):
            msg = f"Expected Document object, got {type(document)}"
            raise ValueError(msg)

        if not document.page_content:
            logger.warning("Document has empty page_content, creating node with empty text")

        # 生成节点ID
        node_id = self.node_id_generator(document)

        # 提取并处理元数据
        metadata = self._extract_metadata(document)

        # 创建TextNode
        node = TextNode(
            text=document.page_content or "",
            id_=node_id,
            metadata=metadata,
        )

        logger.debug(
            f"转换Document为Node: id={node_id}, "
            f"text_length={len(document.page_content)}, "
            f"metadata_keys={list(metadata.keys())}"
        )

        return node

    def convert_documents(self, documents: list[Document]) -> list[Node]:
        """
        批量转换Document列表为Node列表

        Args:
            documents: Document对象列表

        Returns:
            List[Node]: Node对象列表

        Raises:
            ValueError: 如果Document对象无效
            ImportError: 如果LlamaIndex未安装
        """
        if not LLAMA_INDEX_AVAILABLE:
            msg = "LlamaIndex is not available. Please install llama-index package."
            raise ImportError(msg)

        if not documents:
            logger.warning("Empty documents list provided")
            return []

        nodes = []
        for i, document in enumerate(documents):
            try:
                node = self.convert_document(document)
                nodes.append(node)
            except Exception as e:
                logger.error(
                    f"转换第 {i+1} 个Document时出错: {e}",
                    exc_info=True,
                )
                # 继续处理其他文档,不中断整个流程
                continue

        logger.info(f"成功转换 {len(nodes)}/{len(documents)} 个Document为Node")
        return nodes

    def _extract_metadata(self, document: Document) -> dict[str, Any]:
        """
        提取并处理Document的元数据

        Args:
            document: LangChain Document对象

        Returns:
            Dict[str, Any]: 处理后的元数据字典
        """
        if not self.preserve_metadata:
            return {}

        metadata = document.metadata.copy() if document.metadata else {}

        # 确保关键字段存在
        if "source" not in metadata:
            logger.warning("Document metadata缺少'source'字段")

        if "format" not in metadata:
            logger.warning("Document metadata缺少'format'字段")

        # 保留所有原始元数据,不做过滤
        # LlamaIndex Node的metadata可以包含任意键值对
        return metadata

    def _default_node_id_generator(self, document: Document) -> str:
        """
        默认节点ID生成策略

        使用UUID生成唯一ID,确保每个节点都有唯一的标识符.

        Args:
            document: LangChain Document对象

        Returns:
            str: 节点ID字符串
        """
        # 使用UUID生成唯一ID
        return str(uuid4())

    def _hash_based_node_id_generator(self, document: Document) -> str:
        """
        基于内容哈希的节点ID生成策略

        根据文档内容和元数据生成哈希ID,相同内容的文档会生成相同的ID.
        适用于需要去重的场景.

        Args:
            document: LangChain Document对象

        Returns:
            str: 基于哈希的节点ID字符串
        """
        # 组合内容和关键元数据生成哈希
        content = document.page_content or ""
        source = document.metadata.get("source", "") if document.metadata else ""
        format_type = document.metadata.get("format", "") if document.metadata else ""

        # 生成哈希
        hash_input = f"{source}:{format_type}:{content[:1000]}"  # 限制内容长度避免过长
        hash_value = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:16]

        return f"node_{hash_value}"

    def _source_based_node_id_generator(self, document: Document) -> str:
        """
        基于来源的节点ID生成策略

        根据文档来源路径生成节点ID,适用于需要保持来源关联的场景.

        Args:
            document: LangChain Document对象

        Returns:
            str: 基于来源的节点ID字符串
        """
        source = document.metadata.get("source", "") if document.metadata else ""
        if not source:
            # 如果没有source,回退到UUID
            return str(uuid4())

        # 从source路径生成ID(移除特殊字符,保留路径结构)
        import re
        safe_source = re.sub(r"[^\w\-_./]", "_", source)
        # 添加UUID后缀确保唯一性
        unique_suffix = str(uuid4())[:8]
        return f"node_{safe_source}_{unique_suffix}"


class ConversionError(Exception):
    """文档转换异常基类"""

    def __init__(
        self,
        message: str,
        document: Document | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.document = document
        self.original_error = original_error

    def __str__(self) -> str:
        if self.document:
            source = self.document.metadata.get("source", "unknown") if self.document.metadata else "unknown"
            return f"转换错误 [{source}]: {self.message}"
        return f"转换错误: {self.message}"


class InvalidDocumentError(ConversionError):
    """无效Document对象异常"""

    def __init__(self, document: Document | None = None):
        message = "Document对象无效或缺少必需字段"
        super().__init__(message, document)


class MetadataConversionError(ConversionError):
    """元数据转换异常"""

    def __init__(
        self,
        message: str,
        document: Document | None = None,
        original_error: Exception | None = None,
    ):
        full_message = f"元数据转换失败: {message}"
        super().__init__(full_message, document, original_error)

