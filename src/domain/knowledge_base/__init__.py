"""
知识库领域模型模块

该模块包含知识库相关的领域模型, 包括知识库条目、文档块等。
"""

from .knowledge_entry import EntrySourceType, KnowledgeEntry
from .document_chunk import ChunkType, DocumentChunk

__all__ = [
    "EntrySourceType",
    "KnowledgeEntry",
    "ChunkType",
    "DocumentChunk",
]
