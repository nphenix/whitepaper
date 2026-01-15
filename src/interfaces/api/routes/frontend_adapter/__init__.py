"""
前端适配层路由模块

提供前端期望的 API 接口,适配前端代码库(TTsending)的调用方式.
按功能域拆分为多个子模块:
- core: 核心配置和依赖注入函数
- outline_routes: 大纲相关API (create_outline, polish_outline)
- document_routes: 文档处理API (upload_file, get_vector_data_status)
- draft_routes: 草稿生成API (get_draft, generate_draft)
- source_routes: 来源管理API (save_sources, get_sources)
- history_routes: 历史记录API (get_history)
- chat_routes: 聊天API (chat)
- workflow_routes: 工作流API (get_workflow_status, update_workflow_step)
- feedback_routes: 反馈模块 (submit_feedback)
- analysis_routes: 分析模块 (analyze_whitepaper)

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

from fastapi import APIRouter

# 创建主路由器（统一添加 /api 前缀）
router = APIRouter(prefix="/api", tags=["前端适配层"])

# 导入所有子模块路由
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

# 注册所有子模块路由到主路由器
router.include_router(outline_routes.router)
router.include_router(document_routes.router)
router.include_router(draft_routes.router)
router.include_router(source_routes.router)
router.include_router(history_routes.router)
router.include_router(chat_routes.router)
router.include_router(workflow_routes.router)
router.include_router(feedback_routes.router)
router.include_router(analysis_routes.router)

__all__ = [
    "router",
    "core",
    "outline_routes",
    "document_routes",
    "draft_routes",
    "source_routes",
    "history_routes",
    "chat_routes",
    "workflow_routes",
    "feedback_routes",
    "analysis_routes",
]
