"""
前端适配层路由

提供前端期望的 API 接口,适配前端代码库(TTsending)的调用方式.
统一响应格式:{ success: bool, data?: any, error?: string }
内部调用后端现有服务(/api/v1/*)

此模块已被重构为子模块结构，以符合 constitution.md 中 P1 规则的
代码质量守则（单个源文件不得超过 4000 行）。

历史版本保留用于向后兼容。新代码应使用子模块导入。

生成命令: /speckit.implement T249
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
重构时间: 2026-01-10
"""

# 为了向后兼容，保留原始路由导出
# 新代码应直接从子模块导入
from . import (
    analysis_routes,
    chat_routes,
    core,
    document_routes,
    draft_routes,
    feedback_routes,
    history_routes,
    outline_routes,
    source_routes,
    workflow_routes,
)

from .analysis_routes import router as analysis_router
from .chat_routes import router as chat_router
from .core import (
    _ensure_outline_sources_table_exists,
    _source_adapter,
    _workflow_adapter,
    get_document_service,
    get_industry_selection_service,
    get_llm_service,
    get_outline_optimization_service,
    get_source_adapter,
    get_workflow_adapter,
)
from .document_routes import router as document_router
from .draft_routes import router as draft_router
from .feedback_routes import router as feedback_router
from .history_routes import router as history_router
from .outline_routes import router as outline_router
from .source_routes import router as source_router
from .workflow_routes import router as workflow_router

# 创建主路由器
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["前端适配层"])

# 注册所有子模块路由
router.include_router(outline_router)
router.include_router(document_router)
router.include_router(draft_router)
router.include_router(source_router)
router.include_router(history_router)
router.include_router(chat_router)
router.include_router(workflow_router)
router.include_router(feedback_router)
router.include_router(analysis_router)

# 导出向后兼容的符号
__all__ = [
    # 路由
    "router",
    # 子模块
    "analysis_routes",
    "chat_routes",
    "core",
    "document_routes",
    "draft_routes",
    "feedback_routes",
    "history_routes",
    "outline_routes",
    "source_routes",
    "workflow_routes",
    # 子路由
    "analysis_router",
    "chat_router",
    "document_router",
    "draft_router",
    "feedback_router",
    "history_router",
    "outline_router",
    "source_router",
    "workflow_router",
    # 核心函数和变量（向后兼容）
    "_ensure_outline_sources_table_exists",
    "_source_adapter",
    "_workflow_adapter",
    "get_document_service",
    "get_industry_selection_service",
    "get_llm_service",
    "get_outline_optimization_service",
    "get_source_adapter",
    "get_workflow_adapter",
]
