"""
文档领域模型

该模块包含文档相关的领域模型定义, 包括原始文档和预处理后的文档.
"""

from .document import Document, DocumentFormat, DocumentStatus
from .preprocessed_document import (
    CleaningLevel,
    PreprocessedDocument,
    ProcessingStatus,
)

__all__ = [
    "CleaningLevel",
    "Document",
    "DocumentFormat",
    "DocumentStatus",
    "PreprocessedDocument",
    "ProcessingStatus",
]
