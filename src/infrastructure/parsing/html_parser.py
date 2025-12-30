# 生成命令: /speckit.implement T044
# 生成时间: 2025-12-22
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
HTML解析器

该模块实现HTML解析器,处理阶段5信息源爬取任务(T220-T224)获取的网页HTML内容.
提取网页正文内容,去除导航,广告,页眉页脚等无关内容,提取结构化信息,
并转换为LlamaIndex Node对象列表.

参考LlamaIndex最佳实践:
- 使用llama_index.core.schema.Node作为节点格式
- 保留完整的元数据信息,包括章节路径,结构信息等
- 支持结构化检索(章节路径,文档层级)
- 提取网页标题,URL,发布时间等元数据

参考文档:
- BeautifulSoup4: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
- readability-lxml: https://github.com/buriy/python-readability
- trafilatura: https://trafilatura.readthedocs.io/
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.infrastructure.parsing.document_converter import (
    LangChainDocumentToNodeConverter,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from bs4 import BeautifulSoup, Tag
    BS4_AVAILABLE = True
except ImportError:
    logger.warning("BeautifulSoup4 not available, HTML parsing will be disabled")
    BS4_AVAILABLE = False
    BeautifulSoup = None  # type: ignore
    Tag = None  # type: ignore

try:
    from readability import Document as ReadabilityDocument
    READABILITY_AVAILABLE = True
except ImportError:
    logger.warning("readability-lxml not available, readability extraction will be disabled")
    READABILITY_AVAILABLE = False
    ReadabilityDocument = None

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    logger.warning("trafilatura not available, trafilatura extraction will be disabled")
    TRAFILATURA_AVAILABLE = False
    trafilatura = None  # type: ignore

try:
    from llama_index.core.schema import Node, TextNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    logger.warning("LlamaIndex not available, Node creation will be disabled")
    LLAMA_INDEX_AVAILABLE = False
    Node = Any  # type: ignore
    TextNode = Any  # type: ignore


class HTMLElementType(Enum):
    """HTML元素类型枚举"""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    LINK = "link"
    IMAGE = "image"
    QUOTE = "quote"
    CODE = "code"
    OTHER = "other"


@dataclass
class HTMLElement:
    """HTML元素数据类"""
    element_type: HTMLElementType
    content: str
    level: int | None = None  # 标题级别 (1-6)
    tag_name: str | None = None  # HTML标签名
    metadata: dict[str, Any] | None = None


@dataclass
class SectionContext:
    """章节上下文数据类"""
    path: str  # 章节路径,如 "1.2.3"
    title: str  # 章节标题
    level: int  # 标题级别
    parent_path: str | None = None  # 父章节路径


class HTMLParser:
    """
    HTML解析器

    解析HTML内容,提取正文内容,去除导航,广告,页眉页脚等无关内容,
    提取结构化信息,并转换为LlamaIndex Node对象列表.

    功能特性:
    - 提取网页正文内容(使用BeautifulSoup4,readability-lxml或trafilatura)
    - 去除HTML标签,脚本,样式等无关内容
    - 提取结构化元素(标题,段落,列表,表格等)
    - 根据标题层次自动生成章节路径(如"1.2.3")
    - 提取网页标题,URL,发布时间等元数据
    - 输出LlamaIndex Node对象列表

    示例:
        >>> parser = HTMLParser()
        >>> nodes = parser.parse_html(
        ...     html_content="<html>...</html>",
        ...     url="https://example.com/article",
        ... )
        >>> for node in nodes:
        ...     print(node.text)
        ...     print(node.metadata.get("section_path"))
    """

    def __init__(
        self,
        use_readability: bool = True,
        use_trafilatura: bool = False,
        preserve_metadata: bool = True,
    ):
        """
        初始化HTML解析器

        Args:
            use_readability: 是否使用readability-lxml提取正文,默认为True
            use_trafilatura: 是否使用trafilatura提取正文(优先级高于readability),默认为False
            preserve_metadata: 是否保留所有元数据,默认为True
        """
        if not BS4_AVAILABLE:
            msg = "BeautifulSoup4 is not available. Please install beautifulsoup4 package."
            raise ImportError(
                msg
            )

        if not LLAMA_INDEX_AVAILABLE:
            msg = "LlamaIndex is not available. Please install llama-index package."
            raise ImportError(
                msg
            )

        self.use_readability = use_readability and READABILITY_AVAILABLE
        self.use_trafilatura = use_trafilatura and TRAFILATURA_AVAILABLE
        self.preserve_metadata = preserve_metadata

        # 初始化转换器
        self.converter = LangChainDocumentToNodeConverter(
            preserve_metadata=preserve_metadata,
        )

        logger.debug(
            f"初始化 {self.__class__.__name__}: "
            f"use_readability={self.use_readability}, "
            f"use_trafilatura={self.use_trafilatura}"
        )

    def parse_html(
        self,
        html_content: str,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Node]:
        """
        解析HTML内容

        提取正文内容,提取结构化信息,并转换为LlamaIndex Node对象列表.

        Args:
            html_content: HTML内容字符串
            url: 网页URL(可选,用于提取元数据)
            metadata: 可选的元数据字典,会与提取的元数据合并

        Returns:
            List[Node]: LlamaIndex Node对象列表

        Raises:
            ValueError: 如果HTML内容无效
        """
        if not html_content:
            logger.warning("HTML内容为空")
            return []

        # 提取正文内容和元数据
        soup, extracted_metadata = self._extract_main_content(html_content, url)

        # 合并元数据
        if metadata:
            extracted_metadata.update(metadata)

        # 确保关键元数据存在
        if url:
            extracted_metadata["url"] = url
            extracted_metadata["source"] = url

        extracted_metadata["format"] = "html"

        # 解析结构化元素(从BeautifulSoup对象提取)
        elements = self._extract_elements_from_soup(soup)

        # 生成章节路径
        section_contexts = self._build_section_contexts(elements)

        # 创建Node对象
        nodes = self._create_nodes_from_elements(
            elements,
            section_contexts,
            extracted_metadata,
        )

        logger.info(
            f"解析HTML完成: url={url}, "
            f"elements={len(elements)}, "
            f"sections={len(section_contexts)}, "
            f"nodes={len(nodes)}"
        )

        return nodes

    def parse_html_file(
        self,
        file_path: str | Path,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[Node]:
        """
        从HTML文件解析

        Args:
            file_path: HTML文件路径
            url: 网页URL(可选)
            metadata: 可选的元数据字典

        Returns:
            List[Node]: LlamaIndex Node对象列表
        """
        path = Path(file_path)
        if not path.exists():
            msg = f"HTML文件不存在: {file_path}"
            raise FileNotFoundError(msg)

        with open(path, encoding="utf-8") as f:
            html_content = f.read()

        # 如果没有提供URL,使用文件路径
        if not url:
            url = str(path.absolute())

        return self.parse_html(html_content, url, metadata)

    def _extract_main_content(
        self,
        html_content: str,
        url: str | None = None,
    ) -> tuple[BeautifulSoup, dict[str, Any]]:
        """
        提取HTML正文内容和元数据

        使用trafilatura,readability-lxml或BeautifulSoup4提取正文内容,
        并提取网页标题,URL,发布时间等元数据.

        Args:
            html_content: HTML内容字符串
            url: 网页URL(可选)

        Returns:
            Tuple[BeautifulSoup, Dict[str, Any]]: (清理后的BeautifulSoup对象, 元数据字典)
        """
        metadata: dict[str, Any] = {}
        soup = BeautifulSoup(html_content, "html.parser")

        # 提取元数据
        title_elem = soup.find("title")
        if title_elem:
            metadata["title"] = title_elem.get_text(strip=True)

        # 尝试提取Open Graph或meta标签的标题
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            metadata["title"] = og_title.get("content")

        # 提取描述
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content"):
            metadata["description"] = meta_desc.get("content")

        # 提取发布时间
        time_elem = soup.find("time")
        if time_elem:
            pub_time = time_elem.get("datetime") or time_elem.get_text(strip=True)
            if pub_time:
                metadata["publish_date"] = pub_time

        # 优先使用trafilatura(如果可用且启用)- 返回纯文本
        if self.use_trafilatura:
            try:
                extracted = trafilatura.extract(
                    html_content,
                    url=url,
                    include_comments=False,
                    include_tables=True,
                    include_images=False,
                    include_links=True,
                )
                if extracted:
                    # trafilatura提取的元数据
                    metadata_dict = trafilatura.extract_metadata(html_content)
                    if metadata_dict:
                        metadata.update({
                            "title": metadata_dict.title or metadata.get("title"),
                            "author": metadata_dict.author,
                            "date": str(metadata_dict.date) if metadata_dict.date else None,
                            "categories": metadata_dict.categories,
                            "tags": metadata_dict.tags,
                            "description": metadata_dict.description or metadata.get("description"),
                        })
                    # trafilatura返回纯文本,我们需要重新解析为HTML结构
                    # 为了保持结构化信息,我们使用BeautifulSoup降级方案
                    logger.debug("trafilatura提取成功,但使用BeautifulSoup保持结构")
            except Exception as e:
                logger.warning(f"trafilatura提取失败,尝试其他方法: {e}")

        # 使用readability-lxml(如果可用且启用)
        if self.use_readability and not self.use_trafilatura:
            try:
                doc = ReadabilityDocument(html_content)
                main_content_html = doc.summary()
                if main_content_html:
                    # 使用提取的HTML片段创建新的soup
                    soup = BeautifulSoup(main_content_html, "html.parser")
            except Exception as e:
                logger.warning(f"readability提取失败,使用完整HTML: {e}")

        # 移除脚本,样式,导航,广告等无关内容
        for tag in soup.find_all(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # 移除常见的广告和无关类
        for tag in soup.find_all(class_=re.compile(r"(ad|advertisement|sidebar|comment|footer|header|nav|menu)", re.I)):
            tag.decompose()

        # 如果使用了readability或trafilatura,soup已经是清理后的内容
        # 否则尝试找到正文容器
        if not (self.use_readability or self.use_trafilatura):
            article = soup.find("article")
            if article:
                # 使用article作为新的根
                soup = BeautifulSoup(str(article), "html.parser")
            else:
                main = soup.find("main")
                if main:
                    soup = BeautifulSoup(str(main), "html.parser")

        return soup, metadata

    def _extract_elements_from_soup(self, soup: BeautifulSoup) -> list[HTMLElement]:
        """
        从BeautifulSoup对象中提取结构化元素

        遍历HTML DOM树,提取标题,段落,列表等结构化元素.

        Args:
            soup: BeautifulSoup对象

        Returns:
            List[HTMLElement]: 结构化元素列表
        """
        elements: list[HTMLElement] = []

        # 查找body或根元素
        root = soup.find("body") or soup

        # 遍历所有子节点
        for element in root.descendants:
            if not isinstance(element, Tag):
                continue

            tag_name = element.name.lower()

            # 标题处理 (h1-h6)
            if tag_name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                text = element.get_text(strip=True)
                if text:
                    level = int(tag_name[1])
                    elements.append(
                        HTMLElement(
                            element_type=HTMLElementType.HEADING,
                            content=text,
                            level=level,
                            tag_name=tag_name,
                        )
                    )

            # 段落处理
            elif tag_name == "p":
                text = element.get_text(strip=True)
                if text:
                    elements.append(
                        HTMLElement(
                            element_type=HTMLElementType.PARAGRAPH,
                            content=text,
                            tag_name=tag_name,
                        )
                    )

            # 列表处理
            elif tag_name in ["ul", "ol"]:
                list_items = element.find_all("li", recursive=False)
                for li in list_items:
                    text = li.get_text(strip=True)
                    if text:
                        elements.append(
                            HTMLElement(
                                element_type=HTMLElementType.LIST_ITEM,
                                content=text,
                                tag_name="li",
                                metadata={
                                    "list_type": "ordered" if tag_name == "ol" else "unordered",
                                },
                            )
                        )

            # 引用处理
            elif tag_name in ["blockquote", "q"]:
                text = element.get_text(strip=True)
                if text:
                    elements.append(
                        HTMLElement(
                            element_type=HTMLElementType.QUOTE,
                            content=text,
                            tag_name=tag_name,
                        )
                    )

            # 代码块处理
            elif tag_name in ["pre", "code"]:
                text = element.get_text(strip=False)  # 保留换行
                if text:
                    elements.append(
                        HTMLElement(
                            element_type=HTMLElementType.CODE,
                            content=text,
                            tag_name=tag_name,
                        )
                    )

            # 表格处理
            elif tag_name == "table":
                # 提取表格文本内容(简化处理)
                text = element.get_text(separator="\n", strip=True)
                if text:
                    elements.append(
                        HTMLElement(
                            element_type=HTMLElementType.TABLE,
                            content=text,
                            tag_name=tag_name,
                        )
                    )

        # 如果没有提取到任何元素,降级为提取所有文本
        if not elements:
            text = root.get_text(separator="\n", strip=True)
            if text:
                # 按空行分割为段落
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                for para in paragraphs:
                    elements.append(
                        HTMLElement(
                            element_type=HTMLElementType.PARAGRAPH,
                            content=para,
                            tag_name="p",
                        )
                    )

        return elements

    def _build_section_contexts(
        self,
        elements: list[HTMLElement],
    ) -> list[SectionContext]:
        """
        根据标题元素构建章节上下文

        Args:
            elements: HTML元素列表

        Returns:
            List[SectionContext]: 章节上下文列表
        """
        section_contexts: list[SectionContext] = []
        section_stack: list[SectionContext] = []  # 用于跟踪章节层级

        for element in elements:
            if element.element_type == HTMLElementType.HEADING and element.level:
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

    def _get_section_context_for_element(
        self,
        element: HTMLElement,
        elements: list[HTMLElement],
        section_contexts: list[SectionContext],
    ) -> SectionContext | None:
        """
        获取指定元素对应的章节上下文

        Args:
            element: HTML元素
            elements: HTML元素列表
            section_contexts: 章节上下文列表

        Returns:
            SectionContext | None: 章节上下文,如果不存在则返回None
        """
        # 找到所有标题元素及其对应的章节上下文
        heading_to_context: dict[int, SectionContext] = {}
        context_idx = 0

        for i, elem in enumerate(elements):
            if elem.element_type == HTMLElementType.HEADING and context_idx < len(section_contexts):
                heading_to_context[i] = section_contexts[context_idx]
                context_idx += 1

        # 找到元素之前最近的标题
        element_idx = elements.index(element)
        closest_heading_idx = -1
        for heading_idx in sorted(heading_to_context.keys(), reverse=True):
            if heading_idx <= element_idx:
                closest_heading_idx = heading_idx
                break

        if closest_heading_idx >= 0:
            return heading_to_context[closest_heading_idx]

        return None

    def _create_nodes_from_elements(
        self,
        elements: list[HTMLElement],
        section_contexts: list[SectionContext],
        document_metadata: dict[str, Any],
    ) -> list[Node]:
        """
        从HTML元素创建LlamaIndex Node对象

        Args:
            elements: HTML元素列表
            section_contexts: 章节上下文列表
            document_metadata: 文档元数据

        Returns:
            List[Node]: LlamaIndex Node对象列表
        """
        nodes: list[Node] = []

        for element in elements:
            # 跳过标题元素(标题信息已包含在章节上下文中)
            if element.element_type == HTMLElementType.HEADING:
                continue

            # 获取对应的章节上下文
            section_context = self._get_section_context_for_element(
                element,
                elements,
                section_contexts,
            )

            # 构建节点元数据
            node_metadata: dict[str, Any] = {
                "element_type": element.element_type.value,
            }

            if element.tag_name:
                node_metadata["tag_name"] = element.tag_name

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
                # 保留原始元数据,但覆盖冲突字段
                for key, value in document_metadata.items():
                    if key not in node_metadata:
                        node_metadata[key] = value

            # 创建LangChain Document(用于转换)
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


class HTMLParsingError(Exception):
    """HTML解析异常基类"""

    def __init__(
        self,
        message: str,
        url: str | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.url = url
        self.original_error = original_error

    def __str__(self) -> str:
        if self.url:
            return f"HTML解析错误 [{self.url}]: {self.message}"
        return f"HTML解析错误: {self.message}"


class InvalidHTMLError(HTMLParsingError):
    """无效HTML文档异常"""

    def __init__(self, url: str | None = None):
        message = "HTML文档无效或无法解析"
        super().__init__(message, url)

