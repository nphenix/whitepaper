"""
前端适配层核心模块

提供全局服务实例、依赖注入函数和数据库初始化功能.
所有子模块共享此核心配置.

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

import json
import uuid
from datetime import UTC
from typing import TYPE_CHECKING, Any

from src.application.services.document_service import DocumentService
from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.application.services.draft_service import DraftService
from src.shared.config.llm_service import LLMService
from src.shared.utils.logging import get_logger

if TYPE_CHECKING:
    from src.infrastructure.indexing.hybrid_retriever import HybridRetriever

# 获取日志器
logger = get_logger(__name__)

# 全局服务实例
_outline_optimization_service: OutlineOptimizationService | None = None
_industry_selection_service: IndustrySelectionService | None = None
_document_service: DocumentService | None = None
_llm_service: LLMService | None = None
_draft_service: DraftService | None = None

# 来源存储适配器(使用数据库)
_source_adapter: Any | None = None

# 工作流状态存储适配器(使用数据库)
_workflow_adapter: Any | None = None


def _ensure_outline_sources_table_exists():
    """确保outline_sources表存在，如果不存在则创建"""
    from src.infrastructure.storage.sqlite.connection import get_connection_manager

    connection_manager = get_connection_manager()

    try:
        # 检查表是否存在
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='outline_sources'"
            )
            if cursor.fetchone():
                return  # 表已存在
    except Exception:
        pass  # 如果检查失败，尝试创建表

    # 表不存在，创建表
    try:
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            # 创建表（使用迁移007中的表结构）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS outline_sources (
                    id TEXT PRIMARY KEY,
                    outline_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    source_id TEXT,
                    source_data TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (outline_id) REFERENCES outlines(id) ON DELETE CASCADE
                )
            """)
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outline_sources_outline_id ON outline_sources(outline_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outline_sources_source_type ON outline_sources(source_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_outline_sources_created_at ON outline_sources(created_at)")
            conn.commit()
            logger.info("自动创建outline_sources表（表不存在）")
    except Exception as e:
        logger.warning("自动创建outline_sources表失败: %s", e)
        # 不抛出异常，让后续代码处理


def _ensure_workflow_status_table_exists():
    """确保 workflow_status 表存在，如果不存在则创建（兼容未执行迁移的环境）"""
    from src.infrastructure.storage.sqlite.connection import get_connection_manager

    connection_manager = get_connection_manager()

    try:
        # 检查表是否存在
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_status'"
            )
            if cursor.fetchone():
                return  # 表已存在
    except Exception:
        pass  # 如果检查失败，尝试创建表

    # 表不存在，创建表（使用迁移008中的表结构）
    try:
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_status (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL UNIQUE,
                    current_status TEXT NOT NULL,
                    step1_status TEXT DEFAULT 'pending',
                    step2_status TEXT DEFAULT 'pending',
                    step3_status TEXT DEFAULT 'pending',
                    step4_status TEXT DEFAULT 'pending',
                    step_data TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_status_workflow_id ON workflow_status(workflow_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_status_current_status ON workflow_status(current_status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_status_updated_at ON workflow_status(updated_at)"
            )
            conn.commit()
            logger.info("自动创建workflow_status表（表不存在）")
    except Exception as e:
        logger.warning("自动创建workflow_status表失败: %s", e)
        # 不抛出异常，让后续代码处理


def get_source_adapter():
    """获取来源存储适配器实例"""
    global _source_adapter
    if _source_adapter is None:
        from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
        from src.infrastructure.storage.sqlite.connection import get_connection_manager

        # 确保表存在
        _ensure_outline_sources_table_exists()

        _source_adapter = SQLiteAdapter(
            table_name="outline_sources",
            connection_manager=get_connection_manager(),
            id_field="id",
            created_at_field="created_at",
            updated_at_field="updated_at",
        )
    return _source_adapter


def get_workflow_adapter():
    """获取工作流状态存储适配器实例"""
    global _workflow_adapter
    if _workflow_adapter is None:
        from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
        from src.infrastructure.storage.sqlite.connection import get_connection_manager

        # 确保表存在（兼容未执行迁移的环境）
        _ensure_workflow_status_table_exists()

        _workflow_adapter = SQLiteAdapter(
            table_name="workflow_status",
            connection_manager=get_connection_manager(),
            id_field="id",
            created_at_field="created_at",
            updated_at_field="updated_at",
        )
    return _workflow_adapter


def get_outline_optimization_service() -> OutlineOptimizationService:
    """获取大纲优化服务实例"""
    global _outline_optimization_service
    if _outline_optimization_service is None:
        _outline_optimization_service = OutlineOptimizationService()
    return _outline_optimization_service


def get_industry_selection_service() -> IndustrySelectionService:
    """获取行业选择服务实例"""
    global _industry_selection_service
    if _industry_selection_service is None:
        _industry_selection_service = IndustrySelectionService()
    return _industry_selection_service


def get_document_service() -> DocumentService:
    """获取文档服务实例"""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service


def get_llm_service() -> LLMService:
    """获取LLM服务实例"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def get_draft_service() -> DraftService:
    """获取草稿服务实例（复用实例，避免轮询时反复初始化/打印日志）"""
    global _draft_service
    if _draft_service is None:
        _draft_service = DraftService()
    return _draft_service


__all__ = [
    "_outline_optimization_service",
    "_industry_selection_service",
    "_document_service",
    "_llm_service",
    "_source_adapter",
    "_workflow_adapter",
    "_ensure_outline_sources_table_exists",
    "get_source_adapter",
    "get_workflow_adapter",
    "get_outline_optimization_service",
    "get_industry_selection_service",
    "get_document_service",
    "get_llm_service",
    "get_draft_service",
]
