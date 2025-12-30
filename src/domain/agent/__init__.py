"""
Agent领域模型包

该包包含与Agent相关的领域模型,包括行业,大纲,优化大纲,草稿等模型.
"""

# 生成命令: /speckit.implement T200
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

from .industry import Industry, IndustryCategory
from .optimized_outline import (
    OptimizationChangeType,
    OptimizationSummary,
    OptimizedOutline,
    OptimizedOutlineItem,
    create_optimized_outline_from_outline,
)
from .outline import (
    Outline,
    OutlineItem,
    OutlineItemType,
    OutlineStatus,
    OutlineVersion,
    create_outline_from_structure,
    create_outline_from_text,
)
from .source_reference import (
    LocalDocumentReference,
    SourceReference,
    SourceReferenceType,
    WebArticleReference,
)

__all__ = [
    "Industry",
    "IndustryCategory",
    "LocalDocumentReference",
    "OptimizationChangeType",
    "OptimizationSummary",
    "OptimizedOutline",
    "OptimizedOutlineItem",
    "Outline",
    "OutlineItem",
    "OutlineItemType",
    "OutlineStatus",
    "OutlineVersion",
    "SourceReference",
    "SourceReferenceType",
    "WebArticleReference",
    "create_optimized_outline_from_outline",
    "create_outline_from_structure",
    "create_outline_from_text",
]
