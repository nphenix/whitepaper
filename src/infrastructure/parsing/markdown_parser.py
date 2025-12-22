# 生成命令: /speckit.implement T064
# 生成时间: 2025-12-19
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
Markdown解析器

该模块实现Markdown解析器，从阶段3预处理结果读取Markdown文档，
提取结构化信息（章节、段落、标题层次、列表、表格等），
并转换为LlamaIndex Node对象列表。

参考LlamaIndex最佳实践:
- 使用llama_index.core.schema.Node作为节点格式
- 保留完整的元数据信息，包括章节路径、结构信息等
- 支持结构化检索（章节路径、文档层级）
- 关联图片和图表JSON资源信息

参考文档:
- LlamaIndex最佳实践: https://docs.llamaindex.org.cn/en/stable/optimizing/production_rag/
- Markdown解析: https://python-markdown.github.io/
"""

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.infrastructure.parsing.document_converter import (
    LangChainDocumentToNodeConverter,
)
from src.infrastructure.parsing.loaders.preprocessed_document_reader import (
    PreprocessedDocumentReader,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    import markdown
    from markdown.extensions import tables, codehilite, fenced_code
    MARKDOWN_AVAILABLE = True
except ImportError:
    logger.warning("markdown library not available, Markdown parsing will be disabled")
    MARKDOWN_AVAILABLE = False
    markdown = None  # type: ignore

try:
    from llama_index.core.schema import Node, TextNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    logger.warning("LlamaIndex not available, Node creation will be disabled")
    LLAMA_INDEX_AVAILABLE = False
    Node = Any
    TextNode = Any


class ElementType(Enum):
    """Markdown元素类型枚举"""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    IMAGE = "image"
    LINK = "link"
    QUOTE = "quote"
    HR = "horizontal_rule"


@dataclass
class MarkdownElement:
    """Markdown元素数据类"""
    element_type: ElementType
    content: str
    level: int | None = None  # 标题级别 (1-6)
    start_line: int = 0
    end_line: int = 0
    metadata: dict[str, Any] | None = None


@dataclass
class SectionContext:
    """章节上下文数据类"""
    path: str  # 章节路径，如 "1.2.3"
    title: str  # 章节标题
    level: int  # 标题级别
    parent_path: str | None = None  # 父章节路径


class MarkdownParser:
    """
    Markdown解析器

    解析Markdown内容，提取结构化信息，并转换为LlamaIndex Node对象列表。
    支持提取标题层次、段落、列表、表格、代码块等结构信息。

    功能特性:
    - 解析Markdown文档，提取结构化元素
    - 根据标题层次自动生成章节路径（如"1.2.3"）
    - 提取段落、列表、表格、代码块等元素
    - 关联图片和图表JSON信息
    - 保留完整的元数据信息
    - 输出LlamaIndex Node对象列表

    示例:
        >>> parser = MarkdownParser()
        >>> nodes = parser.parse_from_preprocessed_dir(
        ...     source="data/cleaned/documents/doc1/extracted_dir"
        ... )
        >>> for node in nodes:
        ...     print(node.text)
        ...     print(node.metadata.get("section_path"))
    """

    def __init__(
        self,
        include_images: bool = True,
        include_charts: bool = True,
        preserve_metadata: bool = True,
    ):
        """
        初始化Markdown解析器

        Args:
            include_images: 是否在元数据中包含图片信息，默认为True
            include_charts: 是否在元数据中包含图表JSON信息，默认为True
            preserve_metadata: 是否保留所有元数据，默认为True
        """
        if not MARKDOWN_AVAILABLE:
            raise ImportError(
                "markdown library is not available. Please install markdown package."
            )

        if not LLAMA_INDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not available. Please install llama-index package."
            )

        self.include_images = include_images
        self.include_charts = include_charts
        self.preserve_metadata = preserve_metadata

        # 初始化转换器
        self.converter = LangChainDocumentToNodeConverter(
            preserve_metadata=preserve_metadata,
        )

        # 配置Markdown解析器
        self.md = markdown.Markdown(
            extensions=[
                "tables",  # 表格支持
                "codehilite",  # 代码高亮
                "fenced_code",  # 代码块
                "nl2br",  # 换行处理
            ],
        )

        logger.debug(
            f"初始化 {self.__class__.__name__}: "
            f"include_images={include_images}, include_charts={include_charts}"
        )

    def parse_from_preprocessed_dir(
        self,
        source: str,
    ) -> list[Node]:
        """
        从预处理结果目录解析Markdown文档

        使用T060预处理结果读取器读取文档，解析Markdown内容，
        提取结构化信息，并转换为LlamaIndex Node对象列表。

        Args:
            source: 预处理结果目录路径（data/cleaned/documents/{doc_name}/{extracted_dir}/）

        Returns:
            List[Node]: LlamaIndex Node对象列表

        Raises:
            ValueError: 如果source无效
            ImportError: 如果依赖库未安装
        """
        # 使用T060读取器读取预处理结果
        reader = PreprocessedDocumentReader(
            source=source,
            include_images=self.include_images,
            include_charts=self.include_charts,
        )

        documents = reader.load()
        if not documents:
            logger.warning(f"预处理结果目录中没有找到文档: {source}")
            return []

        # 解析每个Document
        all_nodes = []
        for document in documents:
            try:
                nodes = self.parse_document(document)
                all_nodes.extend(nodes)
            except Exception as e:
                logger.error(
                    f"解析Document时出错: {e}",
                    exc_info=True,
                )
                continue

        logger.info(
            f"成功解析预处理结果: source={source}, "
            f"documents={len(documents)}, nodes={len(all_nodes)}"
        )

        return all_nodes

    def parse_document(self, document: Document) -> list[Node]:
        """
        解析单个Document对象

        解析Document中的Markdown内容，提取结构化信息，
        并根据结构信息创建多个Node对象。

        Args:
            document: LangChain Document对象（包含Markdown内容）

        Returns:
            List[Node]: LlamaIndex Node对象列表

        Raises:
            ValueError: 如果Document无效
        """
        if not isinstance(document, Document):
            raise ValueError(f"Expected Document object, got {type(document)}")

        markdown_content = document.page_content
        if not markdown_content:
            logger.warning("Document has empty page_content")
            return []

        # 提取结构化元素
        elements = self._extract_elements(markdown_content)

        # 生成章节路径
        section_contexts = self._build_section_contexts(elements)

        # 创建Node对象
        nodes = self._create_nodes_from_elements(
            elements,
            section_contexts,
            document.metadata,
        )

        logger.debug(
            f"解析Document完成: elements={len(elements)}, "
            f"sections={len(section_contexts)}, nodes={len(nodes)}"
        )

        return nodes

    def _extract_elements(self, markdown_content: str) -> list[MarkdownElement]:
        """
        从Markdown内容中提取结构化元素

        Args:
            markdown_content: Markdown文档内容

        Returns:
            List[MarkdownElement]: 结构化元素列表
        """
        elements: list[MarkdownElement] = []
        lines = markdown_content.split("\n")
        current_element: MarkdownElement | None = None
        current_list_items: list[str] = []
        in_code_block = False
        code_block_language = ""
        code_block_content: list[str] = []

        for line_idx, line in enumerate(lines):
            stripped = line.strip()

            # 代码块处理
            if stripped.startswith("```"):
                if in_code_block:
                    # 结束代码块
                    code_content = "\n".join(code_block_content)
                    elements.append(
                        MarkdownElement(
                            element_type=ElementType.CODE_BLOCK,
                            content=code_content,
                            start_line=current_element.start_line if current_element else line_idx,
                            end_line=line_idx,
                            metadata={
                                "language": code_block_language,
                                "line_count": len(code_block_content),
                            },
                        )
                    )
                    in_code_block = False
                    code_block_content = []
                    code_block_language = ""
                    current_element = None
                else:
                    # 开始代码块
                    in_code_block = True
                    code_block_language = stripped[3:].strip() or "text"
                    code_block_content = []
                    current_element = MarkdownElement(
                        element_type=ElementType.CODE_BLOCK,
                        content="",
                        start_line=line_idx,
                        end_line=line_idx,
                    )
                continue

            if in_code_block:
                code_block_content.append(line)
                continue

            # 标题处理
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                # 保存当前元素
                if current_element:
                    current_element.end_line = line_idx - 1
                    elements.append(current_element)
                    current_element = None

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                elements.append(
                    MarkdownElement(
                        element_type=ElementType.HEADING,
                        content=title,
                        level=level,
                        start_line=line_idx,
                        end_line=line_idx,
                        metadata={
                            "heading_level": level,
                            "heading_text": title,
                        },
                    )
                )
                continue

            # 表格处理（Markdown表格以|开头）
            if stripped.startswith("|") and "|" in stripped[1:]:
                if current_element and current_element.element_type == ElementType.TABLE:
                    current_element.content += "\n" + line
                    current_element.end_line = line_idx
                else:
                    if current_element:
                        elements.append(current_element)
                    current_element = MarkdownElement(
                        element_type=ElementType.TABLE,
                        content=line,
                        start_line=line_idx,
                        end_line=line_idx,
                    )
                continue

            # 列表项处理
            list_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.+)$", stripped)
            if list_match:
                # 保存当前段落或列表
                if current_element and current_element.element_type != ElementType.LIST_ITEM:
                    if current_element.element_type == ElementType.PARAGRAPH:
                        elements.append(current_element)
                    current_element = None

                current_list_items.append(list_match.group(3).strip())
                if not current_element:
                    current_element = MarkdownElement(
                        element_type=ElementType.LIST_ITEM,
                        content="",
                        start_line=line_idx,
                        end_line=line_idx,
                        metadata={
                            "list_type": "ordered" if list_match.group(2)[-1] == "." else "unordered",
                        },
                    )
                else:
                    current_element.content = "\n".join(current_list_items)
                    current_element.end_line = line_idx
                continue

            # 引用处理
            if stripped.startswith(">"):
                if current_element and current_element.element_type == ElementType.QUOTE:
                    current_element.content += "\n" + stripped[1:].strip()
                    current_element.end_line = line_idx
                else:
                    if current_element:
                        elements.append(current_element)
                    current_element = MarkdownElement(
                        element_type=ElementType.QUOTE,
                        content=stripped[1:].strip(),
                        start_line=line_idx,
                        end_line=line_idx,
                    )
                continue

            # 水平线处理
            if re.match(r"^[-*_]{3,}$", stripped):
                if current_element:
                    elements.append(current_element)
                elements.append(
                    MarkdownElement(
                        element_type=ElementType.HR,
                        content="",
                        start_line=line_idx,
                        end_line=line_idx,
                    )
                )
                current_element = None
                continue

            # 图片处理
            image_match = re.search(r"!\[([^\]]*)\]\(([^)]+)\)", line)
            if image_match:
                # 图片作为内联元素，添加到当前段落或创建新段落
                if current_element and current_element.element_type == ElementType.PARAGRAPH:
                    current_element.content += "\n" + line
                    current_element.end_line = line_idx
                else:
                    if current_element:
                        elements.append(current_element)
                    current_element = MarkdownElement(
                        element_type=ElementType.PARAGRAPH,
                        content=line,
                        start_line=line_idx,
                        end_line=line_idx,
                        metadata={
                            "contains_image": True,
                            "image_alt": image_match.group(1),
                            "image_url": image_match.group(2),
                        },
                    )
                continue

            # 空行处理
            if not stripped:
                # 结束当前段落或列表
                if current_element:
                    if current_element.element_type == ElementType.LIST_ITEM:
                        current_element.content = "\n".join(current_list_items)
                        elements.append(current_element)
                        current_list_items = []
                    elif current_element.element_type == ElementType.TABLE:
                        # 表格遇到空行时保存表格
                        elements.append(current_element)
                    else:
                        elements.append(current_element)
                    current_element = None
                continue

            # 普通段落处理
            if current_element and current_element.element_type == ElementType.PARAGRAPH:
                current_element.content += "\n" + line
                current_element.end_line = line_idx
            elif current_element and current_element.element_type == ElementType.TABLE:
                # 表格结束，开始新段落
                elements.append(current_element)
                current_element = MarkdownElement(
                    element_type=ElementType.PARAGRAPH,
                    content=line,
                    start_line=line_idx,
                    end_line=line_idx,
                )
            else:
                # 结束列表，开始新段落
                if current_element and current_element.element_type == ElementType.LIST_ITEM:
                    current_element.content = "\n".join(current_list_items)
                    elements.append(current_element)
                    current_list_items = []
                current_element = MarkdownElement(
                    element_type=ElementType.PARAGRAPH,
                    content=line,
                    start_line=line_idx,
                    end_line=line_idx,
                )

        # 保存最后一个元素
        if current_element:
            if current_element.element_type == ElementType.LIST_ITEM:
                current_element.content = "\n".join(current_list_items)
            current_element.end_line = len(lines) - 1
            elements.append(current_element)

        # 处理未关闭的代码块
        if in_code_block and code_block_content:
            elements.append(
                MarkdownElement(
                    element_type=ElementType.CODE_BLOCK,
                    content="\n".join(code_block_content),
                    start_line=current_element.start_line if current_element else len(lines) - 1,
                    end_line=len(lines) - 1,
                    metadata={
                        "language": code_block_language,
                        "line_count": len(code_block_content),
                    },
                )
            )

        return elements

    def _build_section_contexts(
        self,
        elements: list[MarkdownElement],
    ) -> list[SectionContext]:
        """
        根据标题元素构建章节上下文

        Args:
            elements: Markdown元素列表

        Returns:
            List[SectionContext]: 章节上下文列表
        """
        section_contexts: list[SectionContext] = []
        section_stack: list[SectionContext] = []  # 用于跟踪章节层级

        for element in elements:
            if element.element_type == ElementType.HEADING and element.level:
                level = element.level
                title = element.content

                # 移除比当前级别更深的章节
                while section_stack and section_stack[-1].level >= level:
                    section_stack.pop()

                # 构建章节路径
                if not section_stack:
                    # 顶级章节
                    section_path = str(len([s for s in section_contexts if s.level == level]) + 1)
                else:
                    # 子章节
                    parent = section_stack[-1]
                    sibling_count = len([
                        s for s in section_contexts
                        if s.parent_path == parent.path and s.level == level
                    ])
                    section_path = f"{parent.path}.{sibling_count + 1}"

                context = SectionContext(
                    path=section_path,
                    title=title,
                    level=level,
                    parent_path=section_stack[-1].path if section_stack else None,
                )

                section_contexts.append(context)
                section_stack.append(context)

        return section_contexts

    def _get_section_context_for_line(
        self,
        line_number: int,
        elements: list[MarkdownElement],
        section_contexts: list[SectionContext],
    ) -> SectionContext | None:
        """
        获取指定行号对应的章节上下文

        Args:
            line_number: 行号（0-based）
            elements: Markdown元素列表
            section_contexts: 章节上下文列表

        Returns:
            SectionContext | None: 章节上下文，如果不存在则返回None
        """
        # 找到所有标题元素及其对应的章节上下文
        heading_to_context: dict[int, SectionContext] = {}
        context_idx = 0

        for element in elements:
            if element.element_type == ElementType.HEADING and context_idx < len(section_contexts):
                heading_to_context[element.start_line] = section_contexts[context_idx]
                context_idx += 1

        # 找到行号之前最近的标题
        closest_heading_line = -1
        for heading_line in sorted(heading_to_context.keys(), reverse=True):
            if heading_line <= line_number:
                closest_heading_line = heading_line
                break

        if closest_heading_line >= 0:
            return heading_to_context[closest_heading_line]

        return None

    def _create_nodes_from_elements(
        self,
        elements: list[MarkdownElement],
        section_contexts: list[SectionContext],
        document_metadata: dict[str, Any],
    ) -> list[Node]:
        """
        从Markdown元素创建LlamaIndex Node对象

        Args:
            elements: Markdown元素列表
            section_contexts: 章节上下文列表
            document_metadata: 原始Document的元数据

        Returns:
            List[Node]: LlamaIndex Node对象列表
        """
        nodes: list[Node] = []
        section_idx = 0

        for element in elements:
            # 跳过标题元素（标题信息已包含在章节上下文中）
            if element.element_type == ElementType.HEADING:
                continue

            # 跳过水平线
            if element.element_type == ElementType.HR:
                continue

            # 获取对应的章节上下文
            section_context = self._get_section_context_for_line(
                element.start_line,
                elements,
                section_contexts,
            )

            # 构建节点元数据
            node_metadata: dict[str, Any] = {
                "element_type": element.element_type.value,
                "start_line": element.start_line,
                "end_line": element.end_line,
                "line_count": element.end_line - element.start_line + 1,
            }

            # 添加章节信息
            if section_context:
                node_metadata["section_path"] = section_context.path
                node_metadata["section_title"] = section_context.title
                node_metadata["section_level"] = section_context.level
                if section_context.parent_path:
                    node_metadata["parent_section_path"] = section_context.parent_path

            # 添加元素特定的元数据
            if element.metadata:
                node_metadata.update(element.metadata)

            # 合并原始文档元数据
            if self.preserve_metadata and document_metadata:
                # 保留原始元数据，但覆盖冲突字段
                for key, value in document_metadata.items():
                    if key not in node_metadata:
                        node_metadata[key] = value

            # 特别处理图片和图表信息（确保关联资源信息）
            if self.include_images and "images" in document_metadata:
                node_metadata["images"] = document_metadata["images"]

            if self.include_charts and "charts" in document_metadata:
                node_metadata["charts"] = document_metadata["charts"]

            # 创建LangChain Document（用于转换）
            document = Document(
                page_content=element.content,
                metadata=node_metadata,
            )

            # 转换为LlamaIndex Node
            try:
                node = self.converter.convert_document(document)
                nodes.append(node)
            except Exception as e:
                logger.error(
                    f"转换Document为Node时出错: {e}",
                    exc_info=True,
                )
                continue

        return nodes

    def parse_from_markdown_string(
        self,
        markdown_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Node]:
        """
        从Markdown字符串解析（便捷方法）

        Args:
            markdown_content: Markdown文档内容
            metadata: 可选的元数据字典

        Returns:
            List[Node]: LlamaIndex Node对象列表
        """
        document = Document(
            page_content=markdown_content,
            metadata=metadata or {},
        )

        return self.parse_document(document)


class MarkdownParsingError(Exception):
    """Markdown解析异常基类"""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.source = source
        self.original_error = original_error

    def __str__(self) -> str:
        if self.source:
            return f"Markdown解析错误 [{self.source}]: {self.message}"
        return f"Markdown解析错误: {self.message}"


class InvalidMarkdownError(MarkdownParsingError):
    """无效Markdown文档异常"""

    def __init__(self, source: str | None = None):
        message = "Markdown文档无效或无法解析"
        super().__init__(message, source)

