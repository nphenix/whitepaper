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
        )

        # 提交任务到队列
        if self.redis_pool:
            # 显式传递参数而不是使用**task_kwargs
            await self.redis_pool.enqueue_job(
                "execute_generate_draft_task",
                task_id=task_kwargs["task_id"],
                optimized_outline_id=str(task_kwargs["optimized_outline_id"]) if task_kwargs["optimized_outline_id"] else None,
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
                    industry_id=str(task_kwargs["industry_id"]) if task_kwargs["industry_id"] else None,
                    database_ids=task_kwargs["database_ids"],
                    report_type=str(task_kwargs["report_type"]) if task_kwargs["report_type"] else None,
                    language=str(task_kwargs["language"]) if task_kwargs["language"] else None,
                    style=str(task_kwargs["style"]) if task_kwargs["style"] else None,
                )
            )
            # 存储任务引用以避免垃圾回收
            task.add_done_callback(lambda t: logger.debug(f"草稿生成任务完成: {task_id}"))

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

        task_result.status = TaskStatus.CANCELLED
        task_result.end_time = datetime.now()

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

        # 1. 获取大纲优化服务
        outline_service = task_manager._get_outline_service()
        # 使用正确的方法名
        optimized_outline = outline_service.get_optimized_outline(optimized_outline_id)
        if not optimized_outline:
            msg = f"优化大纲不存在: {optimized_outline_id}"
            raise ValueError(msg)

        task_result.progress = {"stage": "获取大纲", "progress": 20}

        # 2. 获取行业选择服务
        industry_service = task_manager._get_industry_service()
        industry = industry_service.get_industry_by_id(industry_id)
        if not industry:
            msg = f"行业不存在: {industry_id}"
            raise ValueError(msg)

        # 确保industry有name属性
        industry_name = getattr(industry, 'name', str(industry))

        task_result.progress = {"stage": "获取行业信息", "progress": 40}

        # 3. 获取数据库名称列表
        database_names = []
        if database_ids:
            for db_id in database_ids:
                database = industry_service.get_database_by_id(db_id)
                if database:
                    database_names.append(getattr(database, 'name', str(database)))

        task_result.progress = {"stage": "获取数据库信息", "progress": 60}

        # 4. 创建草稿生成Agent
        llm_service = task_manager._get_llm_service()
        # TODO: 从配置或服务中获取HybridRetriever实例
        hybrid_retriever = None
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
        draft = agent.generate_draft(
            optimized_outline=optimized_outline,  # type: ignore[arg-type]
            industry_name=industry_name,
            database_names=database_names,
            report_type=report_type,
        )

        # 更新草稿状态为已生成
        draft.update_status(DraftStatus.GENERATED)

        task_result.progress = {"stage": "生成完成", "progress": 100}

        # 6. 构建任务结果
        end_time = datetime.now()
        task_result.status = TaskStatus.COMPLETED
        task_result.end_time = end_time
        task_result.result = {
            "draft_id": str(draft.id),
            "draft_title": draft.title,
            "draft_status": draft.status.value,
            "total_sections": len(draft.sections),
            "created_at": draft.created_at.isoformat(),
        }

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
        return task_result.to_dict()

    except Exception as e:
        # 其他错误
        error_msg = f"草稿生成任务执行失败: {e}"
        logger.exception(f"{error_msg}, 任务ID: {task_id}")
        end_time = datetime.now()
        task_result.status = TaskStatus.FAILED
        task_result.end_time = end_time
        task_result.error = error_msg
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
        database_ids=database_ids,
        report_type=report_type,
        language=language,
        style=style,
    )

