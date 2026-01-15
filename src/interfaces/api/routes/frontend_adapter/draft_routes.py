"""
草稿生成API路由模块

提供草稿获取和生成相关接口:
- GET /api/draft/{draft_id}: 获取草稿
- POST /api/generate-draft/{outline_id}: 生成草稿

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import StreamingResponse

from src.application.agents.draft_generator_mvp import (
    create_draft_generator_agent,
)
from src.application.agents.outline_optimizer_mvp import (
    create_outline_optimizer_agent,
)
from src.application.services.draft_service import DraftService
from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.interfaces.api.error_handlers import (
    create_error_response_from_exception,
)
from src.interfaces.api.routes.outline_frontend import (
    _convert_to_optimized_outline,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    DraftGenerateRequest,
    create_error_response,
    create_success_response,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.base_exceptions import (
    ResourceNotFoundError,
)
from src.shared.utils.logging import get_logger

from .core import (
    get_draft_service,
    get_industry_selection_service,
    get_llm_service,
    get_outline_optimization_service,
    get_workflow_adapter,
)

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(tags=["草稿管理"])

def _try_read_md_template(outline_id: str) -> str | None:
    """
    md 驱动流程兜底：如果 drafts 表不落库/为空，但文件系统已有 outline_template_<id>.md，
    则直接读取作为 draft 内容返回，避免前端轮询时反复打 drafts 查询。
    """
    if not outline_id:
        return None
    try:
        from src.shared.config.settings import _find_project_root

        project_root = _find_project_root()
        md_template = (
            project_root
            / "data"
            / "output"
            / "drafts"
            / f"outline_template_{outline_id}.md"
        )
        if not md_template.exists():
            return None
        content = md_template.read_text(encoding="utf-8", errors="ignore")
        if isinstance(content, str) and content.strip():
            return content
        return None
    except Exception:
        return None

def _sse(event: str, payload: dict[str, Any]) -> bytes:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
    ).encode("utf-8")


@router.get(
    "/draft/{outline_id}/events",
    summary="订阅草稿生成状态（SSE）",
    description="使用 Server-Sent Events 推送草稿生成进度与完成结果，前端可用 EventSource 订阅。",
)
async def draft_events(
    outline_id: str,
    request: Request,
    draft_service: DraftService = Depends(get_draft_service),
) -> StreamingResponse:
    """
    SSE 事件约定：
    - event: status -> { state, task_id?, progress? }
    - event: done   -> { outline_id, draft_id?, draft, html_file_path? }
    - event: error  -> { message, outline_id }
    - heartbeat: ": ping\\n\\n"
    """
    from src.shared.exceptions.base_exceptions import ResourceNotFoundError

    async def _iter_events():
        # 连接建立：建议前端重连间隔
        yield b"retry: 2000\n\n"
        yield _sse("status", {"state": "connected", "outline_id": outline_id})

        start = time.time()
        # SSE 连接保持上限：尽量覆盖真实草稿生成时长（草稿生成可能远超 10 分钟）
        # 优先使用队列 job_timeout（默认 3600s），并做兜底。
        try:
            from src.shared.config.settings import get_config

            cfg = get_config()
            job_timeout = int(getattr(getattr(cfg, "queue", None), "job_timeout", 3600) or 3600)
        except Exception:
            job_timeout = 3600
        max_wait_seconds = max(job_timeout + 600, 1800)  # 至少 30min，默认约 70min

        # 即便 state 不变，也需要定期发送 status，避免前端“长时间无事件”误判超时
        status_resend_interval_seconds = 3.0
        last_status_sent_at = 0.0
        last_sent: tuple[str, str | None] | None = None  # (state, task_id)

        # 轮询内部状态：间隔尽量小（1s），但只做轻量检查
        while True:
            if await request.is_disconnected():
                return

            # 0) 注意：不要把 outline_template_<outline_id>.md 误判为“草稿已完成”。
            # 该文件在创建大纲时就会生成，若在这里直接 done，会导致 SSE 立即结束，
            # 前端误判“执行完成/中断”，并可能触发重复的 generate-draft 请求。
            #
            # 草稿完成的判定应以：
            # - drafts 表中已写入 draft 且 content 非空
            # - 或 workflow_status.step4_status=completed 且随后 drafts 可读取
            # - 或任务管理器状态为 completed
            # 为准。

            # 1) 如果草稿已落库且有内容，直接 done
            try:
                draft = draft_service.get_latest_draft_for_outline(outline_id)
                draft_content = draft.get_content()
                if isinstance(draft_content, str) and draft_content.strip():
                    html_file_path = None
                    # 尝试从 workflow_status.step_data 读取 html_file_path（如果有）
                    try:
                        workflow_adapter = get_workflow_adapter()
                        rows = workflow_adapter.list(filters={"workflow_id": outline_id}, limit=1)
                        if rows:
                            row = rows[0]
                            step_data_raw = row.get("step_data") or "{}"
                            step_data = (
                                json.loads(step_data_raw)
                                if isinstance(step_data_raw, str)
                                else (step_data_raw or {})
                            )
                            if isinstance(step_data, dict):
                                html_file_path = step_data.get("html_file_path")
                    except Exception:
                        pass

                    yield _sse(
                        "done",
                        {
                            "state": "completed",
                            "outline_id": outline_id,
                            "draft_id": str(draft.id),
                            "draft": draft_content,
                            "html_file_path": html_file_path,
                        },
                    )
                    return
            except ResourceNotFoundError:
                pass
            except Exception:
                # 不阻断 SSE：继续往下走 status/兜底逻辑
                pass

            # 2) 任务状态（内存态）：查 DraftTasks
            task_state: str | None = None
            task_id: str | None = None
            progress: dict[str, Any] | None = None
            try:
                from src.infrastructure.tasks.draft_tasks_mvp import get_draft_task_manager

                task_manager = get_draft_task_manager()
                all_tasks = await task_manager.get_all_tasks()
                for t in all_tasks:
                    st = (t.get("status") or "").lower()
                    if st not in ("pending", "running", "completed", "failed", "cancelled"):
                        continue
                    r = t.get("result") or {}
                    p = t.get("progress") or {}
                    oid = r.get("outline_id") or p.get("outline_id")
                    if oid == outline_id:
                        task_state = st
                        task_id = t.get("task_id")
                        progress = p if isinstance(p, dict) else None
                        break
            except Exception:
                pass

            # 3) workflow_status（持久化兜底）：API 重启后仍可知状态
            if not task_state:
                try:
                    workflow_adapter = get_workflow_adapter()
                    rows = workflow_adapter.list(filters={"workflow_id": outline_id}, limit=1)
                    if rows:
                        row = rows[0]
                        step4_status = (row.get("step4_status") or "").lower()
                        step_data_raw = row.get("step_data") or "{}"
                        step_data = (
                            json.loads(step_data_raw)
                            if isinstance(step_data_raw, str)
                            else (step_data_raw or {})
                        )
                        if step4_status in ("pending", "running"):
                            task_state = "running"
                            task_id = step_data.get("draft_task_id") if isinstance(step_data, dict) else None
                        elif step4_status in ("failed", "cancelled"):
                            msg = None
                            if isinstance(step_data, dict):
                                msg = step_data.get("error")
                                task_id = step_data.get("draft_task_id")
                            yield _sse(
                                "error",
                                {
                                    "state": step4_status,
                                    "outline_id": outline_id,
                                    "task_id": task_id,
                                    "message": msg or "草稿生成失败",
                                },
                            )
                            return
                        elif step4_status == "completed":
                            # completed 但 draft 尚未读到：继续等下一轮（draft_service 读到后会 done）
                            task_state = "completed"
                            if isinstance(step_data, dict):
                                task_id = step_data.get("draft_task_id")
                except Exception:
                    pass

            # 4) 推送状态（去重）
            state_to_send = task_state or "running"
            key = (state_to_send, task_id)
            now = time.time()
            should_resend = (now - last_status_sent_at) >= status_resend_interval_seconds
            if (last_sent != key) or should_resend:
                yield _sse(
                    "status",
                    {
                        "state": state_to_send,
                        "outline_id": outline_id,
                        "task_id": task_id,
                        "progress": progress,
                    },
                )
                last_sent = key
                last_status_sent_at = now

            # 心跳：保持连接活跃
            yield b": ping\n\n"

            if time.time() - start > max_wait_seconds:
                # 避免前端把“连接周期结束”误判为“草稿生成失败”：
                # 这里直接结束 SSE，让浏览器按 retry 策略自动重连，继续订阅。
                return

            await asyncio.sleep(1.0)

    return StreamingResponse(
        _iter_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/draft/{draft_id}",
    response_model=dict[str, Any],
    summary="获取草稿",
    description="根据ID获取草稿内容(前端适配接口)",
)
async def get_draft(
    draft_id: str,
    draft_service: DraftService = Depends(get_draft_service),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取草稿接口(前端适配)

    映射到:GET /api/v1/drafts/{draft_id}

    Args:
        draft_id: 草稿ID

    Returns:
        统一响应格式:{ success: bool, draft: str, sources: {...} }
    """
    try:
        # 轮询场景优化：
        # - 前端通常传入 outline_id 轮询生成状态（而不是 draft_id）
        # - 若任务仍在 RUNNING，优先返回 RUNNING，避免每次轮询都做数据库/模板解析
        has_running_task = False
        running_task_id: str | None = None
        try:
            from src.infrastructure.tasks.draft_tasks_mvp import get_draft_task_manager

            task_manager = get_draft_task_manager()
            all_tasks = await task_manager.get_all_tasks()
            for task in all_tasks:
                if task.get("status") in ("pending", "running"):
                    result = task.get("result") or {}
                    progress = task.get("progress") or {}
                    outline_match = result.get("outline_id") or progress.get("outline_id")
                    if outline_match == draft_id:
                        has_running_task = True
                        running_task_id = task.get("task_id")
                        logger.info(
                            "草稿生成中: outline_id=%s, task_id=%s, 任务状态=RUNNING",
                            draft_id,
                            running_task_id,
                        )
                        break
        except Exception as e:
            logger.debug("检查草稿生成任务状态失败: %s", e)

        if has_running_task:
            return create_success_response(
                data={
                    "draft": "",
                    "sources": {},
                    "status": "RUNNING",
                    "task_id": running_task_id,
                },
                message="草稿生成中",
            )

        # 从数据库获取草稿（如果 draft_id 真的是 draft.id，这里会直接命中）
        try:
            draft = draft_service.get_draft(draft_id)
        except ResourceNotFoundError:
            # md 驱动兜底：如果并不落 drafts 表，但文件系统已有 outline_template_<id>.md，
            # 直接返回内容，避免前端轮询 /draft/{outline_id} 时反复查询 drafts 表。
            md_content = _try_read_md_template(draft_id)
            if md_content:
                return create_success_response(
                    data={
                        "draft": md_content,
                        "sources": {},
                        "status": "COMPLETED",
                        "task_id": None,
                    },
                    message="已从Markdown模板获取草稿",
                )

            # 兼容：前端可能传入 optimized_outline_id 或 original outline_id。
            # 我们统一构造候选 outline_id 列表，用于：
            # - 查 DraftTasks 运行状态（内存态）
            # - 查 workflow_status 持久化状态（重启后兜底）
            # - 查 drafts.outline_id（真正的草稿记录）
            candidate_outline_ids: list[str] = []
            if draft_id:
                candidate_outline_ids.append(draft_id)
            try:
                # 先判断 draft_id 是否就是 outline_id：
                # - outlines 中存在该记录，或
                # - 存在对应的 md 模板文件（md 驱动流程可能不落库 optimized_outlines）
                #
                # 这样可以避免轮询 /draft/{outline_id} 时反复触发 get_optimized_outline 的 warning。
                is_outline_id = False
                # 优先走“文件存在”判断（轻量），避免每次轮询都触发 outline_service.get_outline()
                try:
                    from src.shared.config.settings import _find_project_root

                    project_root = _find_project_root()
                    md_template = (
                        project_root
                        / "data"
                        / "output"
                        / "drafts"
                        / f"outline_template_{draft_id}.md"
                    )
                    if md_template.exists():
                        is_outline_id = True
                except Exception:
                    pass

                if not is_outline_id:
                    # 再尝试 outlines 表存在性（可能是 DB 驱动的 outline）
                    try:
                        outline_service.get_outline(draft_id)
                        is_outline_id = True
                    except Exception:
                        pass

                if not is_outline_id:
                    # 如果 draft_id 恰好是 optimized_outline_id，则映射到 original_outline_id
                    oo = outline_service.get_optimized_outline(draft_id)
                    od = (oo or {}).get("optimized_outline") or {}
                    original_id = od.get("original_outline_id") or od.get("outline_id")
                    if original_id:
                        original_id = str(original_id)
                        if original_id not in candidate_outline_ids:
                            candidate_outline_ids.insert(0, original_id)
            except ResourceNotFoundError:
                pass
            except Exception as e:
                logger.debug("解析 optimized_outline_id -> original_outline_id 失败: %s", e)

            # 兼容前端行为：传入的是 outline_id，而不是 draft_id
            # 关键：如果该 outline_id 当前仍在后台生成草稿中，不能返回旧草稿，
            # 否则前端/测试会误以为生成完成，进而提前导出 HTML（拿到旧草稿内容）。
            # 再次检查（此时 candidate_outline_ids 可能包含 original_outline_id）
            try:
                from src.infrastructure.tasks.draft_tasks_mvp import get_draft_task_manager

                task_manager = get_draft_task_manager()
                all_tasks = await task_manager.get_all_tasks()
                for task in all_tasks:
                    if task.get("status") in ("pending", "running"):
                        result = task.get("result") or {}
                        progress = task.get("progress") or {}
                        outline_match = result.get("outline_id") or progress.get("outline_id")
                        if outline_match in candidate_outline_ids:
                            running_task_id = task.get("task_id")
                            logger.info(
                                "草稿生成中: outline_id=%s, task_id=%s, 任务状态=RUNNING",
                                draft_id,
                                running_task_id,
                            )
                            return create_success_response(
                                data={
                                    "draft": "",
                                    "sources": {},
                                    "status": "RUNNING",
                                    "task_id": running_task_id,
                                },
                                message="草稿生成中",
                            )
            except Exception as e:
                logger.debug("检查草稿生成任务状态失败: %s", e)

            # 持久化兜底：如果 API 重启导致内存任务丢失，使用 workflow_status 判断 step4 是否仍在进行
            try:
                workflow_adapter = get_workflow_adapter()
                for oid in candidate_outline_ids:
                    rows = workflow_adapter.list(filters={"workflow_id": oid}, limit=1)
                    if not rows:
                        continue
                    row = rows[0]
                    step4_status = (row.get("step4_status") or "").lower()
                    step_data_raw = row.get("step_data") or "{}"
                    try:
                        step_data = (
                            json.loads(step_data_raw)
                            if isinstance(step_data_raw, str)
                            else (step_data_raw or {})
                        )
                    except Exception:
                        step_data = {}

                    task_id = step_data.get("draft_task_id")
                    if step4_status in ("pending", "running"):
                        logger.info(
                            "草稿生成中(持久化状态): outline_id=%s, task_id=%s, step4_status=%s",
                            oid,
                            task_id,
                            step4_status,
                        )
                        return create_success_response(
                            data={
                                "draft": "",
                                "sources": {},
                                "status": "RUNNING",
                                "task_id": task_id,
                            },
                            message="草稿生成中",
                        )

                    if step4_status in ("failed", "cancelled"):
                        err = step_data.get("error") or "草稿生成失败"
                        logger.warning(
                            "草稿生成失败(持久化状态): outline_id=%s, task_id=%s, step4_status=%s, error=%s",
                            oid,
                            task_id,
                            step4_status,
                            err,
                        )
                        return create_success_response(
                            data={
                                "draft": "",
                                "sources": {},
                                "status": "FAILED",
                                "task_id": task_id,
                                "error": err,
                            },
                            message="草稿生成失败",
                        )

                    if step4_status == "completed":
                        # 优先用持久化的 draft_id 直接取草稿
                        persisted_draft_id = step_data.get("draft_id")
                        if persisted_draft_id:
                            try:
                                draft = draft_service.get_draft(str(persisted_draft_id))
                                draft_content = draft.get_content()
                                return create_success_response(
                                    data={"draft": draft_content, "sources": {}}
                                )
                            except Exception:
                                pass
            except Exception as e:
                logger.debug("检查workflow_status失败(不影响主流程): %s", e)

            try:
                # 用候选 outline_id 依次尝试（解决传入 optimized_outline_id 的情况）
                draft = None
                for oid in candidate_outline_ids:
                    try:
                        draft = draft_service.get_latest_draft_for_outline(oid)
                        break
                    except ResourceNotFoundError:
                        continue
                if not draft:
                    raise ResourceNotFoundError(
                        "草稿不存在", resource_type="Draft", resource_id=draft_id
                    )
                logger.info(
                    "按outline_id获取到最新草稿: outline_id=%s, draft_id=%s, title=%s",
                    draft_id,
                    draft.id,
                    draft.title
                )
            except ResourceNotFoundError:
                # 草稿可能仍在后台生成中：这里不能返回 success=false，
                # 否则前端会把它当作"致命错误"直接停止轮询。
                # 草稿可能仍在后台生成中或确实不存在
                # 注意：已经通过 DraftTasks 检查了是否有运行中的任务
                logger.warning(
                    "草稿不存在且无运行中的任务(含持久化兜底): input_id=%s, candidate_outline_ids=%s。"
                    "可能原因：1) 草稿生成失败；2) ID不匹配；3) 草稿尚未生成",
                    draft_id,
                    candidate_outline_ids,
                )

                # 这里不能返回 success=false，
                # 否则前端会把它当作"致命错误"直接停止轮询。
                return create_success_response(
                    data={"draft": "", "sources": {}, "status": "RUNNING"},
                    message="草稿不存在或生成中",
                )

        # 获取草稿内容
        draft_content = draft.get_content()

        # 获取来源信息(如果有)- 从数据库获取
        try:
            # 尝试从数据库获取来源(通过草稿ID关联,这里需要根据实际数据模型调整)
            # 注意:当前实现中,来源是关联到大纲的,不是草稿
            # 如果需要关联到草稿,需要扩展数据模型
            sources = {}
        except Exception:
            sources = {}

        return create_success_response(
            data={
                "draft": draft_content,
                "sources": sources,
            }
        )

    except Exception as e:
        logger.exception("获取草稿异常: %s", e)
        return create_error_response_from_exception(e)


@router.post(
    "/generate-draft/{outline_id}",
    response_model=dict[str, Any],
    summary="生成草稿",
    description="基于大纲生成草稿(前端适配接口)",
)
async def generate_draft(
    outline_id: str,
    request: DraftGenerateRequest | None = Body(None, description="生成草稿请求(可选)"),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
    industry_service: IndustrySelectionService = Depends(get_industry_selection_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """
    生成草稿接口(前端适配)

    映射到:POST /api/v1/drafts/generate

    完整流程:
    1. 获取大纲信息
    2. 查找优化后的大纲(从优化历史中获取最新的)
    3. 如果大纲未优化,返回明确错误提示
    4. 从大纲记录中获取 industry_id 和 database_ids
    5. 从请求参数或配置中获取 report_type, language, style
    6. 调用草稿生成Agent生成草稿
    7. 转换响应格式为前端期望的格式

    Args:
        outline_id: 大纲ID
        request: 生成草稿请求(可选,包含配置信息)
        outline_service: 大纲优化服务
        industry_service: 行业选择服务
        llm_service: LLM服务

    Returns:
        统一响应格式:{ success: bool, data: { draft: str } }
    """
    try:
        from src.application.agents.draft_generator_mvp import (
            create_draft_generator_agent,
        )
        from src.interfaces.api.routes.outline_frontend import (
            _convert_to_optimized_outline,
        )
        from src.shared.exceptions.base_exceptions import (
            ResourceNotFoundError,
        )

        # 获取配置信息(从请求参数或使用默认值)
        config = (request.config or {}) if request else {}
        report_type = config.get("report_type", "市场研究报告")
        language = config.get("language", "zh-CN")
        style = config.get("style", "专业")

        # 1. 获取大纲信息
        try:
            outline_result = outline_service.get_outline(outline_id)
        except ResourceNotFoundError:
            logger.warning("大纲不存在: %s", outline_id)
            return create_error_response(
                f"大纲不存在: {outline_id}",
                "请检查大纲ID是否正确"
            )
        except Exception as e:
            logger.error("获取大纲失败: %s", e, exc_info=True)
            return create_error_response(
                "获取大纲失败",
                str(e)
            )

        outline_data = outline_result["outline"]
        industry_id = uuid.UUID(outline_data["industry_id"])

        # 解析数据库ID列表
        database_ids = []
        database_ids_str = outline_data.get("database_ids")
        if database_ids_str:
            if isinstance(database_ids_str, str):
                try:
                    import json
                    database_ids = [uuid.UUID(db_id) for db_id in json.loads(database_ids_str)]
                except (json.JSONDecodeError, ValueError, TypeError):
                    logger.warning("解析数据库ID列表失败: %s", database_ids_str)
                    database_ids = []
            elif isinstance(database_ids_str, list):
                database_ids = [uuid.UUID(str(db_id)) for db_id in database_ids_str]

        # 2. 查找优化后的大纲(从优化历史中获取最新的)
        try:
            optimization_history = outline_service.get_optimization_history(outline_id)
        except Exception as e:
            logger.error("获取优化历史失败: %s", e, exc_info=True)
            return create_error_response(
                "获取优化历史失败",
                str(e)
            )

        def _convert_legacy_optimized_result(result: dict[str, Any]) -> Any:
            """兼容旧表结构：从 optimized_outlines.optimized_structure 解析 OptimizedOutline。"""
            from src.domain.agent.optimized_outline import (
                OptimizationChangeType,
                OptimizedOutline,
                OptimizedOutlineItem,
            )
            from src.domain.agent.outline import OutlineItem, OutlineItemType

            optimized_outline_data = result.get("optimized_outline", {}) or {}
            original_id_str = optimized_outline_data.get("original_outline_id") or optimized_outline_data.get("outline_id")
            if not original_id_str:
                raise ValueError("legacy optimized_outlines 缺少 original_outline_id/outline_id")

            optimized_structure = optimized_outline_data.get("optimized_structure")
            if optimized_structure is None:
                raise ValueError("legacy optimized_outlines 缺少 optimized_structure")

            # optimized_structure 可能是 JSON 字符串或已解析对象
            if isinstance(optimized_structure, str):
                try:
                    optimized_structure = json.loads(optimized_structure)
                except json.JSONDecodeError as e:
                    raise ValueError(f"optimized_structure JSON解析失败: {e}") from e

            if not isinstance(optimized_structure, list):
                raise ValueError("optimized_structure 必须为 list")

            def _safe_item_type(v: str | None) -> OutlineItemType:
                if not v:
                    return OutlineItemType.SECTION
                try:
                    return OutlineItemType(v)
                except Exception:
                    return OutlineItemType.SECTION

            def _safe_change_type(v: str | None) -> OptimizationChangeType:
                if not v:
                    return OptimizationChangeType.NONE
                try:
                    return OptimizationChangeType(v)
                except Exception:
                    return OptimizationChangeType.NONE

            optimized_items: list[OptimizedOutlineItem] = []

            def walk(nodes: list[dict[str, Any]], parent_optimized_item_id: uuid.UUID | None = None) -> None:
                for node in nodes:
                    optimized_item_id_str = node.get("optimized_item_id") or node.get("optimizedItemId")
                    if not optimized_item_id_str:
                        optimized_item_id = uuid.uuid4()
                    else:
                        # 尝试解析为 UUID，如果失败则生成新的
                        try:
                            optimized_item_id = uuid.UUID(str(optimized_item_id_str))
                        except ValueError:
                            # 不是有效的 UUID，生成新的
                            optimized_item_id = uuid.uuid4()
                            logger.debug(
                                "optimized_item_id 不是有效UUID，生成新ID: %s -> %s",
                                optimized_item_id_str,
                                optimized_item_id
                            )

                    outline_item = OutlineItem(
                        id=optimized_item_id,
                        parent_id=parent_optimized_item_id,
                        item_type=_safe_item_type(node.get("item_type")),
                        level=int(node.get("level") or 1),
                        title=str(node.get("title") or ""),
                        description=node.get("description"),
                        order=int(node.get("order") or 0),
                    )

                    suggestions = node.get("optimization_suggestions") or []
                    if isinstance(suggestions, str):
                        try:
                            suggestions = json.loads(suggestions)
                        except Exception:
                            suggestions = []

                    # 尝试解析 node.id 为 UUID，失败则生成新的
                    node_id_str = node.get("id")
                    if node_id_str:
                        try:
                            node_uuid = uuid.UUID(str(node_id_str))
                        except ValueError:
                            node_uuid = uuid.uuid4()
                            logger.debug(
                                "node.id 不是有效UUID，生成新ID: %s -> %s",
                                node_id_str,
                                node_uuid
                            )
                    else:
                        node_uuid = uuid.uuid4()

                    optimized_items.append(
                        OptimizedOutlineItem(
                            id=node_uuid,
                            original_outline_id=uuid.UUID(str(original_id_str)),
                            original_item_id=None,
                            original_item=None,
                            optimized_item=outline_item,
                            change_type=_safe_change_type(node.get("change_type")),
                            change_description=node.get("change_description"),
                            optimization_reason=node.get("optimization_reason"),
                            optimization_suggestions=suggestions if isinstance(suggestions, list) else [],
                            is_accepted=bool(node.get("is_accepted", False)),
                            user_feedback=node.get("user_feedback"),
                            metadata=node.get("metadata") if isinstance(node.get("metadata"), dict) else {},
                        )
                    )

                    children = node.get("children") or []
                    if isinstance(children, list) and children:
                        walk(children, parent_optimized_item_id=optimized_item_id)

            walk(optimized_structure, parent_optimized_item_id=None)

            return OptimizedOutline(
                id=uuid.UUID(str(optimized_outline_data.get("id"))) if optimized_outline_data.get("id") else uuid.uuid4(),
                original_outline_id=uuid.UUID(str(original_id_str)),
                optimized_items=optimized_items,
                summary=None,
                is_accepted=bool(optimized_outline_data.get("is_accepted", False)),
                user_feedback=optimized_outline_data.get("user_feedback"),
                optimization_status=optimized_outline_data.get("optimization_status", "PENDING"),
                metadata={},
            )

        optimized_outline = None
        optimized_outline_id = None

        if not optimization_history:
            # 没有优化历史：自动优化一次（不再硬失败，避免前端降级到 mock）
            logger.warning("大纲 %s 没有优化历史，将自动优化后继续生成草稿", outline_id)

            try:
                from src.domain.agent.outline import Outline, OutlineStatus

                # 自动优化需要 industry_name / database_names（提前计算，避免依赖后续流程）
                try:
                    industry = industry_service.get_industry_by_id(str(industry_id))
                    industry_name = industry["name"]
                except Exception as e:
                    raise ValueError(f"获取行业信息失败: {e}") from e

                database_names = []
                if database_ids:
                    for db_id in database_ids:
                        try:
                            database = industry_service.get_database_by_id(str(db_id))
                            if database:
                                database_names.append(database["name"])
                        except Exception:
                            continue

                structure = outline_data.get("structure")
                if isinstance(structure, str):
                    try:
                        structure = json.loads(structure)
                    except json.JSONDecodeError:
                        structure = []
                if not isinstance(structure, list):
                    structure = []

                outline_obj = Outline.create_from_structure(
                    title=outline_data.get("title", "白皮书草稿"),
                    structure=structure,
                    industry_id=industry_id,
                    database_ids=database_ids,
                    description=outline_data.get("description"),
                )
                outline_obj.id = uuid.UUID(outline_data["id"])
                try:
                    outline_obj.status = OutlineStatus(outline_data.get("status", "DRAFT"))
                except Exception:
                    pass

                optimizer_agent = create_outline_optimizer_agent(
                    llm_service=llm_service,
                    report_type=report_type,
                )
                optimized_outline = optimizer_agent.optimize_outline(
                    outline=outline_obj,
                    industry_name=industry_name,
                    database_names=database_names,
                    report_type=report_type,
                )
                optimized_outline_id = str(optimized_outline.id)

                # 尽力保存优化历史（旧表结构可能只能保存主记录）
                try:
                    outline_service.save_optimized_outline(optimized_outline)
                except Exception as save_err:
                    logger.warning("自动保存优化历史失败(不影响生成草稿): %s", save_err)
            except Exception as auto_opt_err:
                logger.error("自动优化失败: %s", auto_opt_err, exc_info=True)
                return create_error_response(
                    "大纲未优化且自动优化失败",
                    str(auto_opt_err),
                )

        if optimized_outline is None:
            # 使用最新的优化后大纲(按创建时间排序,取最后一个)
            latest_optimization = optimization_history[-1]
            optimized_outline_id = latest_optimization["optimized_outline"]["id"]

            # 3. 获取优化后的大纲对象
            try:
                optimized_outline_result = outline_service.get_optimized_outline(optimized_outline_id)
                # 关键：将“数据库结构”转换为领域模型 OptimizedOutline，供草稿生成（含MD模板驱动）使用
                optimized_outline = _convert_to_optimized_outline(optimized_outline_result)
                logger.info(
                    "获取优化后大纲: optimized_outline_id=%s",
                    optimized_outline_id
                )
            except Exception as e:
                # 预期的回退逻辑：尝试从 legacy 表结构解析（旧数据可能使用旧表结构）
                logger.warning(
                    "从新表结构获取优化后大纲失败，尝试从 legacy 表结构解析: optimized_outline_id=%s, 错误=%s",
                    optimized_outline_id,
                    e
                )
                # 尝试从 legacy 表结构解析
                try:
                    optimized_outline = _convert_legacy_optimized_result(latest_optimization)
                    logger.info(
                        "从 legacy 表结构解析优化后大纲成功: optimized_outline_id=%s",
                        optimized_outline_id
                    )
                except Exception as convert_err:
                    logger.error("从 legacy 表结构解析优化后大纲失败: %s", convert_err, exc_info=True)
                    return create_error_response(
                        "获取优化后大纲失败",
                        f"无法获取或解析优化后大纲: {e}"
                    )

        # 4. 获取行业名称和数据库名称
        try:
            industry = industry_service.get_industry_by_id(str(industry_id))
            industry_name = industry["name"]
        except Exception as e:
            logger.error("获取行业信息失败: %s", e, exc_info=True)
            return create_error_response(
                "获取行业信息失败",
                str(e)
            )

        database_names = []
        if database_ids:
            for db_id in database_ids:
                try:
                    database = industry_service.get_database_by_id(str(db_id))
                    if database:
                        database_names.append(database["name"])
                except Exception:
                    logger.warning("获取数据库信息失败: %s", db_id)

        logger.info(
            "开始生成草稿: outline_id=%s, optimized_outline_id=%s, industry=%s, database_count=%d",
            outline_id,
            optimized_outline_id,
            industry_name,
            len(database_names)
        )

        # 5. 启动异步草稿生成任务（对齐前端轮询 /api/draft/{outlineId} 的正式流程）
        try:
            from src.infrastructure.tasks.draft_tasks_mvp import get_draft_task_manager

            task_manager = get_draft_task_manager()

            # 避免重复启动：如果已有 pending/running 的任务，直接返回该任务信息
            try:
                all_tasks = await task_manager.get_all_tasks()
                for task in all_tasks:
                    if task.get("status") in ("pending", "running"):
                        result = task.get("result") or {}
                        if (result.get("outline_id") == outline_id) or (
                            result.get("optimized_outline_id") == optimized_outline_id
                        ):
                            return create_success_response(
                                data={
                                    "status": "RUNNING",
                                    "task_id": task.get("task_id"),
                                    "outline_id": outline_id,
                                },
                                message="草稿生成任务已在运行中",
                            )
            except Exception:
                # 如果任务列表读取失败，不影响继续创建新任务
                pass

            task_id = await task_manager.generate_draft_task(
                optimized_outline_id=str(optimized_outline.id),
                outline_id=str(uuid.UUID(outline_id)),
                industry_id=str(industry_id),
                database_ids=[str(x) for x in database_ids] if database_ids else [],
                report_type=report_type,
                language=language,
                style=style,
            )

            logger.info(
                "已启动草稿生成任务: outline_id=%s, optimized_outline_id=%s, task_id=%s",
                outline_id,
                optimized_outline_id,
                task_id,
            )

            # 立即返回，让前端继续轮询 /api/draft/{outlineId}
            return create_success_response(
                data={
                    "status": "STARTED",
                    "task_id": task_id,
                    "outline_id": outline_id,
                    "optimized_outline_id": optimized_outline_id,
                },
                message="草稿生成任务已启动",
            )

        except Exception as e:
            logger.exception("启动草稿生成任务失败: %s", e)
            return create_error_response("草稿生成失败", str(e))

    except Exception as e:
        logger.exception("生成草稿异常: %s", e)
        return create_error_response_from_exception(e)


__all__ = ["router"]
