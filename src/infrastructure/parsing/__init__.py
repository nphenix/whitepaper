"""
文档解析模块

该模块提供文档解析和格式转换功能，支持将LangChain Document转换为LlamaIndex Node。
"""

from src.infrastructure.parsing.document_converter import (
    LangChainDocumentToNodeConverter,
)
from src.infrastructure.parsing.html_parser import (
    HTMLParser,
    HTMLParsingError,
    InvalidHTMLError,
    HTMLElementType,
    HTMLElement,
)
from src.infrastructure.parsing.markdown_parser import (
    MarkdownParser,
    MarkdownParsingError,
    InvalidMarkdownError,
    ElementType,
    MarkdownElement,
    SectionContext,
)

__all__ = [
    "LangChainDocumentToNodeConverter",
    "HTMLParser",
    "HTMLParsingError",
    "InvalidHTMLError",
    "HTMLElementType",
    "HTMLElement",
    "MarkdownParser",
    "MarkdownParsingError",
    "InvalidMarkdownError",
    "ElementType",
    "MarkdownElement",
    "SectionContext",
]

