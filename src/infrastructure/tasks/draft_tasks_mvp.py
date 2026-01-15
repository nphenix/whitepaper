"""
草稿生成异步任务 (T241)

该模块实现草稿生成的异步任务,使用Arq任务队列框架.
封装T232-T234草稿生成Agent的功能,支持异步生成和状态跟踪.

生成命令: /speckit.implement T241
生成时间: 2025-12-25
来源: specs/001-multi-agent-doc-system/tasks.md

设计目标:
- 封装草稿生成流程为异步任务,支持长时间运行的任务
- 使用Arq任务队列,支持任务状态跟踪和错误重试
- 调用T232-T234草稿生成Agent执行实际生成
- 支持任务进度报告和结果回调
- 集成任务监控和日志记录
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from src.application.agents.draft_generator_mvp import (
    create_draft_generator_agent,
)
from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.domain.agent.draft import DraftStatus
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.agent_exceptions import AgentExecutionError
from src.shared.utils.logging import get_logger

if TYPE_CHECKING:
    from arq.connections import ArqRedis

    from src.infrastructure.indexing.hybrid_retriever import HybridRetriever

logger = get_logger(__name__)

# --- workflow_status 持久化：让 API 重启/多进程情况下仍能看到 step4 任务状态 ---


def _ensure_workflow_status_table_exists() -> None:
    """确保 workflow_status 表存在（兼容未执行迁移的环境）"""
    from src.infrastructure.storage.sqlite.connection import get_connection_manager

    cm = get_connection_manager()
    try:
        with cm.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_status'"
            )
            if cursor.fetchone():
                return
    except Exception:
        pass

    try:
        with cm.get_connection() as conn:
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


def _upsert_workflow_status(
    workflow_id: str,
    *,
    current_status: str | None = None,
    step4_status: str | None = None,
    step_data_patch: dict[str, Any] | None = None,
) -> None:
    """写入/更新 workflow_status（draft 生成任务状态的持久化兜底）"""
    try:
        import json

        from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
        from src.infrastructure.storage.sqlite.connection import get_connection_manager

        _ensure_workflow_status_table_exists()
        repo = SQLiteAdapter(
            table_name="workflow_status",
            connection_manager=get_connection_manager(),
            id_field="id",
            created_at_field="created_at",
            updated_at_field="updated_at",
        )

        existing = repo.list(filters={"workflow_id": workflow_id}, limit=1)
        now = datetime.utcnow().isoformat()

        if existing:
            row = dict(existing[0])
            row["updated_at"] = now
            if current_status:
                row["current_status"] = current_status
            if step4_status:
                row["step4_status"] = step4_status

            if step_data_patch:
                step_data_raw = row.get("step_data") or "{}"
                try:
                    step_data = (
                        json.loads(step_data_raw)
                        if isinstance(step_data_raw, str)
                        else (step_data_raw or {})
                    )
                except Exception:
                    step_data = {}
                if not isinstance(step_data, dict):
                    step_data = {}
                step_data.update(step_data_patch)
                row["step_data"] = json.dumps(step_data, ensure_ascii=False)

            repo.update(row["id"], row)
            return

        row = {
            "id": str(uuid4()),
            "workflow_id": workflow_id,
            "current_status": current_status or "step3_sources_selected",
            "step1_status": "pending",
            "step2_status": "pending",
            "step3_status": "pending",
            "step4_status": step4_status or "pending",
            "step_data": json.dumps(step_data_patch or {}, ensure_ascii=False),
            "created_at": now,
            "updated_at": now,
        }
        repo.create(row)
    except Exception as e:
        logger.debug("写入workflow_status失败(不影响主流程): %s", e)


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 待处理
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class TaskType(str, Enum):
    """任务类型枚举"""

    GENERATE_DRAFT = "generate_draft"  # 生成草稿


class TaskResult:
    """任务结果类"""

    def __init__(
        self,
        task_id: str,
        task_type: TaskType,
        status: TaskStatus,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        progress: dict[str, Any] | None = None,
    ) -> None:
        self.task_id = task_id
        self.task_type = task_type
        self.status = status
        self.result = result
        self.error = error
        self.start_time = start_time
        self.end_time = end_time
        self.progress = progress or {}

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (
                (self.end_time - self.start_time).total_seconds()
                if self.start_time and self.end_time
                else None
            ),
            "progress": self.progress,
        }


class DraftTasks:
    """
    草稿生成任务管理器

    管理草稿生成的异步任务,提供任务创建,执行,监控等功能.
    """

    def __init__(self, redis_pool: ArqRedis | None = None) -> None:
        """
        初始化草稿生成任务管理器

        Args:
            redis_pool: Redis连接池,如果为None则使用默认配置
        """
        self.redis_pool = redis_pool
        self._task_results: dict[str, TaskResult] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}  # 存储运行中的asyncio任务引用（用于无Redis模式）
        self._outline_service: OutlineOptimizationService | None = None
        self._industry_service: IndustrySelectionService | None = None
        self._llm_service: LLMService | None = None

    def _get_outline_service(self) -> OutlineOptimizationService:
        """获取大纲优化服务实例"""
        if self._outline_service is None:
            # 使用具体实现类而不是抽象基类
            from src.application.services.outline_optimization_service import OutlineOptimizationService
            self._outline_service = OutlineOptimizationService()  # type: ignore[abstract]
        return self._outline_service

    def _get_industry_service(self) -> IndustrySelectionService:
        """获取行业选择服务实例"""
        if self._industry_service is None:
            # 使用具体实现类而不是抽象基类
            from src.application.services.industry_selection_service import IndustrySelectionService
            self._industry_service = IndustrySelectionService()  # type: ignore[abstract]
        return self._industry_service

    def _get_llm_service(self) -> LLMService:
        """获取LLM服务实例"""
        if self._llm_service is None:
            self._llm_service = LLMService()
        return self._llm_service

    async def generate_draft_task(
        self,
        optimized_outline_id: str,
        industry_id: str,
        outline_id: str | None = None,
        database_ids: list[str] | None = None,
        report_type: str | None = None,
        language: str | None = None,
        style: str | None = None,
        hybrid_retriever: HybridRetriever | None = None,
    ) -> str:
        """
        创建草稿生成任务

        Args:
            optimized_outline_id: 优化后的大纲ID
            industry_id: 行业ID
            database_ids: 数据库ID列表
            report_type: 报告类型
            language: 报告语言
            style: 写作风格
            hybrid_retriever: 混合检索引擎实例(可选)

        Returns:
            任务ID
        """
        task_id = str(uuid4())

        # 创建任务参数
        task_kwargs = {
            "task_id": task_id,
            "optimized_outline_id": optimized_outline_id,
            "outline_id": outline_id,
            "industry_id": industry_id,
            "database_ids": database_ids or [],
            "report_type": report_type,
            "language": language,
            "style": style,
        }

        # 创建任务结果对象
        self._task_results[task_id] = TaskResult(
            task_id=task_id,
            task_type=TaskType.GENERATE_DRAFT,
            status=TaskStatus.PENDING,
            start_time=datetime.now(),
            # 关键：让轮询方能在 PENDING/RUNNING 阶段就按 outline_id 识别任务
            result={
                "outline_id": outline_id,
                "optimized_outline_id": optimized_outline_id,
            },
        )

        # 持久化：让 API 重启后仍能知道 step4 正在生成（避免轮询误判“无运行任务”）
        if outline_id:
            _upsert_workflow_status(
                str(outline_id),
                current_status="step3_sources_selected",
                step4_status="pending",
                step_data_patch={
                    "draft_task_id": task_id,
                    "optimized_outline_id": optimized_outline_id,
                },
            )

        # 提交任务到队列
        if self.redis_pool:
            # 显式传递参数而不是使用**task_kwargs
            await self.redis_pool.enqueue_job(
                "execute_generate_draft_task",
                task_id=task_kwargs["task_id"],
                optimized_outline_id=str(task_kwargs["optimized_outline_id"]) if task_kwargs["optimized_outline_id"] else None,
                outline_id=str(task_kwargs["outline_id"]) if task_kwargs["outline_id"] else None,
                industry_id=str(task_kwargs["industry_id"]) if task_kwargs["industry_id"] else None,
                database_ids=task_kwargs["database_ids"],
                report_type=task_kwargs["report_type"],
                language=task_kwargs["language"],
                style=task_kwargs["style"],
            )
            logger.info(f"已提交草稿生成任务到队列: {task_id}")
        else:
            # 直接执行任务(用于测试或无Redis环境)
            logger.info("未配置Redis,直接执行草稿生成任务")
            task = asyncio.create_task(
                execute_generate_draft_task(
                    ctx=None,
                    task_id=str(task_kwargs["task_id"]),
                    optimized_outline_id=str(task_kwargs["optimized_outline_id"]) if task_kwargs["optimized_outline_id"] else None,
                    outline_id=str(task_kwargs["outline_id"]) if task_kwargs["outline_id"] else None,
                    industry_id=str(task_kwargs["industry_id"]) if task_kwargs["industry_id"] else None,
                    database_ids=task_kwargs["database_ids"],
                    report_type=str(task_kwargs["report_type"]) if task_kwargs["report_type"] else None,
                    language=str(task_kwargs["language"]) if task_kwargs["language"] else None,
                    style=str(task_kwargs["style"]) if task_kwargs["style"] else None,
                )
            )
            # 存储任务引用以避免垃圾回收，并支持取消
            self._running_tasks[task_id] = task
            task.add_done_callback(
                lambda t, tid=task_id: (
                    self._running_tasks.pop(tid, None),
                    logger.debug(f"草稿生成任务完成: {tid}")
                )
            )
            logger.info(f"已创建草稿生成任务: task_id={task_id}")

        return task_id

    async def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息字典,如果任务不存在则返回None
        """
        if task_id not in self._task_results:
            return None

        task_result = self._task_results[task_id]
        return task_result.to_dict()

    async def get_all_tasks(self) -> list[dict[str, Any]]:
        """
        获取所有任务状态

        Returns:
            所有任务状态信息列表
        """
        return [result.to_dict() for result in self._task_results.values()]

    def get_running_task_ids(self) -> list[str]:
        """
        获取正在运行的任务ID列表（仅无Redis模式）

        Returns:
            运行中的任务ID列表
        """
        return [
            task_id for task_id, task in self._running_tasks.items()
            if not task.done()
        ]

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        if task_id not in self._task_results:
            return False

        task_result = self._task_results[task_id]
        if task_result.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ]:
            return False

        # 尝试取消正在运行的asyncio任务
        if task_id in self._running_tasks:
            asyncio_task = self._running_tasks[task_id]
            if not asyncio_task.done():
                try:
                    asyncio_task.cancel()
                    logger.info(f"已发送取消信号到任务: task_id={task_id}")
                except Exception as cancel_err:
                    logger.warning(f"取消任务失败: task_id={task_id}, error={cancel_err}")

        task_result.status = TaskStatus.CANCELLED
        task_result.end_time = datetime.now()
        task_result.error = "任务被用户取消"

        logger.info(f"任务已取消: {task_id}")
        return True


# 全局任务管理器实例
_task_manager: DraftTasks | None = None


def get_draft_task_manager() -> DraftTasks:
    """
    获取全局草稿生成任务管理器实例

    Returns:
        任务管理器实例
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = DraftTasks()
    return _task_manager


# Arq任务执行函数
async def execute_generate_draft_task(
    ctx: dict[str, Any] | None,
    task_id: str,
    optimized_outline_id: str,
    outline_id: str | None,
    industry_id: str,
    database_ids: list[str] | None = None,
    report_type: str | None = None,
    language: str | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    """
    执行草稿生成任务

    Args:
        ctx: Arq上下文
        task_id: 任务ID
        optimized_outline_id: 优化后的大纲ID
        industry_id: 行业ID
        database_ids: 数据库ID列表
        report_type: 报告类型
        language: 报告语言
        style: 写作风格

    Returns:
        任务结果
    """
    task_manager = get_draft_task_manager()

    # 获取任务结果对象
    task_result = task_manager._task_results.get(task_id)
    if not task_result:
        error_msg = f"任务不存在: {task_id}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        # 更新任务状态为运行中
        task_result.status = TaskStatus.RUNNING
        task_result.progress = {"stage": "初始化", "progress": 0}

        logger.info(f"开始执行草稿生成任务: {task_id}")

        # 持久化 RUNNING（让 API 重启后仍可见）
        if outline_id:
            _upsert_workflow_status(
                str(outline_id),
                current_status="step3_sources_selected",
                step4_status="pending",
                step_data_patch={
                    "draft_task_id": task_id,
                    "optimized_outline_id": optimized_outline_id,
                },
            )

        # 1. 获取大纲优化服务
        outline_service = task_manager._get_outline_service()

        # 优先按 optimized_outline_id 从数据库读取；若不存在，则回退到：
        # - 使用 outline_id 的优化历史（可能由 md 模板“模拟生成”，不落库 optimized_outlines）
        # 这样可以避免 “优化大纲不存在” 导致整条生成链路失败。
        from src.interfaces.api.routes.outline_frontend import _convert_to_optimized_outline
        from src.shared.exceptions.base_exceptions import ResourceNotFoundError

        try:
            optimized_outline_result = outline_service.get_optimized_outline(optimized_outline_id)
            optimized_outline = _convert_to_optimized_outline(optimized_outline_result)
        except ResourceNotFoundError:
            if not outline_id:
                msg = f"优化大纲不存在且缺少 outline_id，无法回退: optimized_outline_id={optimized_outline_id}"
                raise ValueError(msg)

            history = outline_service.get_optimization_history(str(outline_id))
            if not history:
                msg = (
                    f"优化大纲不存在且无优化历史，无法回退: optimized_outline_id={optimized_outline_id}, outline_id={outline_id}"
                )
                raise ValueError(msg)

            latest = history[-1]
            legacy_result = {
                "optimized_outline": latest.get("optimized_outline") or {},
                "items": latest.get("items") or [],
                "summary": latest.get("summary"),
            }
            optimized_outline = _convert_to_optimized_outline(legacy_result)
            logger.warning(
                "optimized_outline_id 不存在，已从优化历史/模板回退构建 OptimizedOutline: optimized_outline_id=%s, outline_id=%s",
                optimized_outline_id,
                outline_id,
            )

        task_result.progress = {"stage": "获取大纲", "progress": 20}

        # 2. 获取行业选择服务
        industry_service = task_manager._get_industry_service()
        industry = industry_service.get_industry_by_id(industry_id)
        if not industry:
            msg = f"行业不存在: {industry_id}"
            raise ValueError(msg)

        # 兼容：industry 可能是领域对象/ORM对象，也可能是 dict
        if isinstance(industry, dict):
            industry_name = str(industry.get("name") or industry.get("title") or industry.get("industry_name") or "未知行业")
        else:
            # 确保industry有name属性（避免 str(industry) 变成 "{'id':...,'name':...}" 这种 dict 字符串）
            industry_name = getattr(industry, "name", None) or getattr(industry, "title", None) or str(industry)

        task_result.progress = {"stage": "获取行业信息", "progress": 40}

        # 3. 获取数据库名称列表
        database_names = []
        if database_ids:
            for db_id in database_ids:
                database = industry_service.get_database_by_id(db_id)
                if database:
                    if isinstance(database, dict):
                        db_name = database.get("name") or database.get("title") or database.get("database_name")
                        database_names.append(str(db_name or database))
                    else:
                        database_names.append(
                            getattr(database, "name", None)
                            or getattr(database, "title", None)
                            or str(database)
                        )

        task_result.progress = {"stage": "获取数据库信息", "progress": 60}

        # 4. 创建草稿生成Agent
        llm_service = task_manager._get_llm_service()
        # 获取 HybridRetriever 实例
        hybrid_retriever = None
        try:
            # 优先从 outline_id 推导 knowledge_base_id（与前端 chat RAG 一致）：
            # - 通过 outline_sources 中的 uploaded_file source_id(document_id)
            # - 生成 kb_doc_{document_uuid.hex[:16]}
            #
            # 注意：outline.database_ids 通常是“行业数据库/数据集”ID（UUID），并不一定等同于 knowledge_base_id。
            outline_lookup_id = outline_id or str(optimized_outline.original_outline_id)

            knowledge_base_id: str | None = None
            try:
                from src.interfaces.api.routes.frontend_adapter.chat_routes import (
                    _get_knowledge_base_ids_from_outline_id,
                )

                kb_ids = _get_knowledge_base_ids_from_outline_id(str(outline_lookup_id))
                if kb_ids:
                    knowledge_base_id = kb_ids if len(kb_ids) > 1 else kb_ids[0]
            except Exception as e:
                logger.debug("从outline_id推导knowledge_base_id失败（将尝试回退路径）: %s", e)

            # 重要：不要把 outline.database_ids（通常是“行业数据库/数据集”的 UUID）误当作 knowledge_base_id。
            # 否则会生成类似 kb_<uuid-with-dashes>_metadata 的表名，SQLite 会因 "-" 语法错误而失败。
            #
            # 如果 outline_id 无法推导出 kb_id（outline_sources 未维护 / 未上传文件），
            # 这里保持 knowledge_base_id=None，让下游 get_hybrid_retriever 走“自动发现可用 KB”兜底策略。

            # 无论是否推导出 knowledge_base_id，都尝试创建检索器：
            # - kb_id 存在：使用对应的 kb_{knowledge_base_id}_vector / kb_{knowledge_base_id} bm25 等
            # - kb_id 不存在：走默认索引/默认 collection（满足“前端不走来源选择/上传也要能召回”的正式交付需求）
            #
            # 说明：get_hybrid_retriever 支持 knowledge_base_id=None；此前这里没调用导致 hybrid_retriever=None，
            # DraftGeneratorAgent 会视为“禁用RAG”，从而出现你反馈的“生成过程没用RAG/BM25”。
            from src.interfaces.api.routes.draft_mvp import get_hybrid_retriever

            hybrid_retriever = get_hybrid_retriever(knowledge_base_id=knowledge_base_id)
            logger.info(
                "HybridRetriever 初始化成功: kb_id=%s",
                knowledge_base_id or "默认",
            )
        except ImportError as imp_err:
            logger.warning("无法导入 HybridRetriever 相关模块: %s", imp_err)
        except Exception as retriever_err:
            logger.warning("初始化 HybridRetriever 失败，将跳过素材检索: %s", retriever_err)

        # 确保参数类型正确
        agent = create_draft_generator_agent(
            llm_service=llm_service,
            report_type=report_type or "行业白皮书",
            language=language or "中文",
            style=style or "专业",
            hybrid_retriever=hybrid_retriever,
        )

        task_result.progress = {"stage": "创建生成Agent", "progress": 80}

        # 5. 生成草稿
        # 注意：agent.generate_draft 是同步方法，在 Arq/async 环境中直接调用会检测到运行中的事件循环并失败。
        # 统一通过工作线程执行，避免阻塞事件循环并规避该保护逻辑。
        draft = await asyncio.to_thread(
            agent.generate_draft,
            optimized_outline=optimized_outline,  # type: ignore[arg-type]
            industry_name=industry_name,
            database_names=database_names,
            report_type=report_type,
        )

        # 更新草稿状态为已生成
        draft.update_status(DraftStatus.GENERATED)

        task_result.progress = {"stage": "生成完成", "progress": 100}

        # 6. 落库保存草稿 + 自动导出 HTML（对齐正式流程的轮询/交付）
        html_file_path = None
        try:
            from src.application.services.draft_service import DraftService

            # 使用固定的测试用户ID(后续版本将从认证中获取)
            test_user_id = "00000000-0000-0000-0000-000000000001"
            DraftService().save_draft(draft, test_user_id)
        except Exception as save_err:
            logger.warning("草稿生成完成但保存到数据库失败: %s", save_err, exc_info=True)

        try:
            from src.application.services.html_export_service import HTMLExportService

            html_file_path = HTMLExportService().export_draft_to_html(
                draft=draft,
                output_dir="data/output/final",
                include_appendix=True,
                overwrite_latest=True,
            )
        except Exception as export_err:
            logger.warning("草稿生成完成但HTML导出失败: %s", export_err, exc_info=True)

        # 7. 构建任务结果
        end_time = datetime.now()
        task_result.status = TaskStatus.COMPLETED
        task_result.end_time = end_time

        task_result.result = {
            "draft_id": str(draft.id),
            "draft_title": draft.title,
            "draft_status": draft.status.value,
            "total_sections": len(draft.sections),
            "outline_id": outline_id or str(optimized_outline.original_outline_id),
            "optimized_outline_id": optimized_outline_id,
            "html_file_path": str(html_file_path) if html_file_path else None,
            "created_at": draft.created_at.isoformat(),
        }

        # 持久化 COMPLETED（轮询端可从 workflow_status.step_data 兜底拿到 draft_id/html_file_path）
        workflow_id = outline_id or str(optimized_outline.original_outline_id)
        _upsert_workflow_status(
            str(workflow_id),
            current_status="step4_generated",
            step4_status="completed",
            step_data_patch={
                "draft_task_id": task_id,
                "draft_id": str(draft.id),
                "html_file_path": str(html_file_path) if html_file_path else None,
                "optimized_outline_id": optimized_outline_id,
            },
        )

        logger.info(
            f"草稿生成任务完成: {task_id}, 草稿ID: {draft.id}, 标题: {draft.title}"
        )

        return task_result.to_dict()

    except AgentExecutionError as e:
        # Agent执行错误
        error_msg = f"草稿生成Agent执行失败: {e}"
        logger.error(f"{error_msg}, 任务ID: {task_id}")
        end_time = datetime.now()
        task_result.status = TaskStatus.FAILED
        task_result.end_time = end_time
        task_result.error = error_msg
        if outline_id:
            _upsert_workflow_status(
                str(outline_id),
                current_status="step4_failed",
                step4_status="failed",
                step_data_patch={"draft_task_id": task_id, "error": error_msg},
            )
        return task_result.to_dict()

    except asyncio.CancelledError:
        # 任务被取消
        logger.info(f"草稿生成任务被取消: task_id={task_id}")
        end_time = datetime.now()
        task_result.status = TaskStatus.CANCELLED
        task_result.end_time = end_time
        task_result.error = "任务被取消"
        if outline_id:
            _upsert_workflow_status(
                str(outline_id),
                current_status="step4_cancelled",
                step4_status="cancelled",
                step_data_patch={"draft_task_id": task_id, "error": "任务被取消"},
            )
        return task_result.to_dict()

    except Exception as e:
        # 其他错误
        error_msg = f"草稿生成任务执行失败: {e}"
        logger.exception(f"{error_msg}, 任务ID: {task_id}")
        end_time = datetime.now()
        task_result.status = TaskStatus.FAILED
        task_result.end_time = end_time
        task_result.error = error_msg
        if outline_id:
            _upsert_workflow_status(
                str(outline_id),
                current_status="step4_failed",
                step4_status="failed",
                step_data_patch={"draft_task_id": task_id, "error": error_msg},
            )
        return task_result.to_dict()


# Arq Worker配置
class WorkerSettings:
    """Arq Worker配置"""

    functions = [
        execute_generate_draft_task,
    ]

    # 重试配置
    retry_jobs = True
    max_retries = 3

    # 任务超时配置(秒)
    job_timeout = 3600  # 1小时

    # 队列配置
    queue_name = "draft_tasks"


# 便捷函数
async def generate_draft_async(
    optimized_outline_id: str,
    industry_id: str,
    outline_id: str | None = None,
    database_ids: list[str] | None = None,
    report_type: str | None = None,
    language: str | None = None,
    style: str | None = None,
    redis_pool: ArqRedis | None = None,
) -> str:
    """
    异步生成草稿的便捷函数

    Args:
        optimized_outline_id: 优化后的大纲ID
        industry_id: 行业ID
        database_ids: 数据库ID列表
        report_type: 报告类型
        language: 报告语言
        style: 写作风格
        redis_pool: Redis连接池(可选)

    Returns:
        任务ID
    """
    task_manager = DraftTasks(redis_pool=redis_pool)
    return await task_manager.generate_draft_task(
        optimized_outline_id=optimized_outline_id,
        industry_id=industry_id,
        outline_id=outline_id,
        database_ids=database_ids,
        report_type=report_type,
        language=language,
        style=style,
    )

