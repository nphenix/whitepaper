"""
文档解析模块

该模块提供文档解析和格式转换功能,支持将LangChain Document转换为LlamaIndex Node.
"""

from src.infrastructure.parsing.document_converter import (
    LangChainDocumentToNodeConverter,
)
from src.infrastructure.parsing.html_parser import (
    HTMLElement,
    HTMLElementType,
    HTMLParser,
    HTMLParsingError,
    InvalidHTMLError,
)
from src.infrastructure.parsing.markdown_parser import (
    ElementType,
    InvalidMarkdownError,
    MarkdownElement,
    MarkdownParser,
    MarkdownParsingError,
    SectionContext,
)

__all__ = [
    "ElementType",
    "HTMLElement",
    "HTMLElementType",
    "HTMLParser",
    "HTMLParsingError",
    "InvalidHTMLError",
    "InvalidMarkdownError",
    "LangChainDocumentToNodeConverter",
    "MarkdownElement",
    "MarkdownParser",
    "MarkdownParsingError",
    "SectionContext",
]

