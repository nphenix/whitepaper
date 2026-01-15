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
from .chart_config import (
    ChartConfig,
    ChartType,
    create_chart_config_from_data_source,
    create_chart_config_from_dsl_config,
)
from .draft import (
    Draft,
    DraftSection,
    DraftSectionType,
    DraftStatus,
    DraftVersion,
    create_draft_from_outline,
)
from .html_draft import (
    HTMLAppendixDataTable,
    HTMLCitation,
    HTMLChartPlaceholder,
    HTMLDraft,
    HTMLSection,
    create_html_draft_from_draft,
)
from .source_reference import (
    LocalDocumentReference,
    SourceReference,
    SourceReferenceType,
    WebArticleReference,
)

__all__ = [
    "ChartConfig",
    "ChartType",
    "Draft",
    "DraftSection",
    "DraftSectionType",
    "DraftStatus",
    "DraftVersion",
    "HTMLAppendixDataTable",
    "HTMLCitation",
    "HTMLChartPlaceholder",
    "HTMLDraft",
    "HTMLSection",
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
    "create_chart_config_from_data_source",
    "create_chart_config_from_dsl_config",
    "create_draft_from_outline",
    "create_html_draft_from_draft",
    "create_optimized_outline_from_outline",
    "create_outline_from_structure",
    "create_outline_from_text",
]
