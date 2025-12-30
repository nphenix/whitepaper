"""
知识库领域模型模块

该模块包含知识库相关的领域模型, 包括知识库条目,文档块等.
"""

from .document_chunk import ChunkType, DocumentChunk
from .knowledge_entry import EntrySourceType, KnowledgeEntry

__all__ = [
    "ChunkType",
    "DocumentChunk",
    "EntrySourceType",
    "KnowledgeEntry",
]
