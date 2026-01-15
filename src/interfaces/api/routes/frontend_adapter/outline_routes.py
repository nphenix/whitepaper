"""
大纲相关API路由模块

提供大纲创建和优化相关接口:
- POST /api/outline: 创建大纲
- POST /api/polish-outline: 优化大纲文本

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

import json
import queue
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.application.agents.outline_optimizer_mvp import (
    create_outline_optimizer_agent,
)
from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.domain.agent.outline import (
    create_outline_from_text as domain_create_outline_from_text,
)
from src.interfaces.api.error_handlers import (
    create_error_response_from_exception,
    handle_errors,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    OutlineCreateRequest,
    OutlinePolishRequest,
    create_error_response,
    create_success_response,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.base_exceptions import ResourceNotFoundError
from src.shared.utils.logging import get_logger

from .core import (
    get_industry_selection_service,
    get_llm_service,
    get_outline_optimization_service,
)

# 获取日志器
logger = get_logger(__name__)

# 创建路由器（不带 /api 前缀，由主路由器统一添加）
router = APIRouter(tags=["大纲管理"])


@router.post(
    "/outline",
    response_model=dict[str, Any],
    summary="创建大纲",
    description="从文本创建大纲(前端适配接口)",
)
async def create_outline(
    request: OutlineCreateRequest,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
    industry_service: IndustrySelectionService = Depends(get_industry_selection_service),
) -> dict[str, Any]:
    """
    创建大纲接口(前端适配)

    映射到:POST /api/v1/outlines/create-from-text

    Args:
        request: 创建大纲请求
        outline_service: 大纲优化服务
        industry_service: 行业选择服务

    Returns:
        统一响应格式:{ success: bool, outlineId: str, ... }
    """
    try:
        # 从配置中获取行业ID和数据库ID(如果提供)
        config = request.config or {}
        industry_id = config.get("industry_id")
        database_ids = config.get("database_ids", [])

        selected_industry = None

        # 如果没有提供行业ID,使用默认行业(优先查找"储能"行业)
        if not industry_id:
            logger.info("未提供行业ID,开始查找默认行业")
            # 获取所有激活的行业
            try:
                industries = industry_service.get_industries(is_active=True, sort_by="sort_order", sort_order="asc")
            except Exception as e:
                logger.error("获取行业列表失败: %s", e, exc_info=True)
                return create_error_response(
                    "获取行业列表失败",
                    "系统无法获取可用行业列表,请稍后重试或联系管理员"
                )

            if not industries:
                logger.warning("系统中没有可用的行业")
                return create_error_response(
                    "未找到可用行业",
                    "系统中尚未配置任何行业,请联系管理员添加行业信息"
                )

            # 优先查找"储能"行业
            energy_storage_industry = None
            for industry in industries:
                industry_name = industry.get("name", "")
                # 检查是否包含"储能"关键词(支持中英文)
                if "储能" in industry_name or "energy" in industry_name.lower() or "storage" in industry_name.lower():
                    energy_storage_industry = industry
                    logger.info("找到储能行业: %s (ID: %s)", industry_name, industry.get("id"))
                    break

            if energy_storage_industry:
                selected_industry = energy_storage_industry
                industry_id = selected_industry["id"]
                logger.info("使用储能行业作为默认行业: %s", selected_industry.get("name"))
            else:
                # 如果没有找到储能行业,使用第一个可用行业
                selected_industry = industries[0]
                industry_id = selected_industry["id"]
                logger.info("未找到储能行业,使用第一个可用行业: %s (ID: %s)",
                           selected_industry.get("name"), industry_id)
        else:
            # 验证行业是否存在
            try:
                selected_industry = industry_service.get_industry_by_id(str(industry_id))
                logger.info("使用指定的行业: %s (ID: %s)", selected_industry.get("name"), industry_id)
            except ResourceNotFoundError:
                logger.warning("指定的行业不存在: %s", industry_id)
                return create_error_response(
                    f"行业不存在: {industry_id}",
                    "请检查行业ID是否正确,或使用有效的行业ID"
                )
            except Exception as e:
                logger.error("获取行业信息失败: %s", e, exc_info=True)
                return create_error_response(
                    "获取行业信息失败",
                    f"无法验证行业ID {industry_id},请稍后重试"
                )

        # 处理数据库ID:如果未提供,使用行业关联的默认数据库
        database_uuid_list = []
        if database_ids:
            # 转换提供的数据库ID列表
            for db_id in database_ids:
                try:
                    database_uuid_list.append(uuid.UUID(str(db_id)))
                except ValueError:
                    logger.warning("无效的数据库ID格式: %s,将跳过", db_id)
            logger.info("使用提供的数据库ID列表: %d 个数据库", len(database_uuid_list))
        else:
            # 如果未提供数据库ID,从行业关联的数据库中获取默认数据库
            try:
                industry_databases = industry_service.get_industry_databases(
                    industry_id=str(industry_id),
                    is_active=True,
                    sort_by="sort_order",
                    sort_order="asc"
                )

                if industry_databases:
                    # 使用第一个数据库作为默认值
                    default_database = industry_databases[0]
                    database_uuid_list.append(uuid.UUID(default_database["id"]))
                    logger.info("未提供数据库ID,使用行业关联的默认数据库: %s (ID: %s)",
                               default_database.get("name"), default_database["id"])
                else:
                    logger.warning("行业 %s 没有关联的数据库,将使用空数据库列表", industry_id)
            except Exception as e:
                logger.error("获取行业关联数据库失败: %s", e, exc_info=True)
                # 不阻止创建大纲,只是记录警告
                logger.warning("无法获取行业关联的数据库,将使用空数据库列表")

        # 简化流程：直接从用户润色后的文本生成大纲模板
        # 不再调用LLM规范化，不再解析Outline对象，直接生成纯大纲模板
        original_outline_text = request.outlineText

        # 生成大纲ID
        outline_id = str(uuid.uuid4())
        logger.info("开始生成大纲模板: outline_id=%s", outline_id)

        # 简单格式化：保留所有内容，做基本清理
        lines = original_outline_text.split('\n')
        cleaned_lines = []
        for line in lines:
            # 移除行尾空白，但保留空行（用于段落分隔）
            stripped_line = line.rstrip()
            # 跳过完全空白的行（但保留单个空行用于分隔）
            if stripped_line or line.strip() == '':
                cleaned_lines.append(stripped_line)
            else:
                # 连续空行只保留一个
                if cleaned_lines and cleaned_lines[-1] != '':
                    cleaned_lines.append('')

        # 生成大纲模板内容
        template_content = '\n'.join(cleaned_lines)
        template_content = template_content.strip() + '\n'

        # 注意：不再添加"附录：图转Json呈现"章节
        # 原因：
        # 1. 这个章节会被 LLM 处理，但 LLM 无法生成有意义的内容
        # 2. HTML 渲染器 (html_renderer.py) 已有 _generate_appendix_html 方法，
        #    会自动从 datajson 目录读取图表数据并生成附录表格
        # 3. html_renderer.py 的 _should_skip_section 会过滤掉"图转Json"章节

        # 确定模板保存路径
        output_dir = Path("data/output/drafts")
        output_dir.mkdir(parents=True, exist_ok=True)

        template_filename = f"outline_template_{outline_id}.md"
        template_path = output_dir / template_filename

        # 保存模板文件
        try:
            template_path.write_text(template_content, encoding='utf-8')
            logger.info(
                "大纲模板生成成功: 路径=%s, 标题数量=%d",
                template_path,
                len(cleaned_lines)
            )
        except Exception as e:
            logger.error("保存大纲模板失败: %s", e, exc_info=True)
            return create_error_response(
                "保存大纲模板失败",
                f"无法保存大纲模板: {e!s}"
            )

        # 同步落库 outline（关键：后续草稿保存 drafts/outlines 外键校验、来源关联、状态轮询都依赖 outlines 表）
        # 说明：此前仅写入 outline_template_<id>.md 不落库，会导致：
        # - DraftService.save_draft 触发 outlines 外键/存在性校验失败（草稿“生成了但查不到”）
        # - /api/sources 返回 0（无法通过 outline_id 关联上传文件/知识库）
        # - 生成草稿时出现 "Outline不存在" 警告并走大量回退逻辑
        try:
            # 优先使用前端传入的 title，否则从文本首行推断
            outline_title = None
            if isinstance(config, dict):
                outline_title = config.get("title")
            if not outline_title:
                # 取首个非空行作为标题（去掉常见的 markdown 标题符号）
                first_non_empty = next((ln.strip() for ln in cleaned_lines if ln.strip()), "临时大纲")
                outline_title = first_non_empty.lstrip("#").strip() or "临时大纲"

            # 解析文本为 Outline 结构并保存
            outline_obj = domain_create_outline_from_text(
                title=str(outline_title),
                text=template_content,
                industry_id=uuid.UUID(str(industry_id)),
                database_ids=database_uuid_list,
            )
            outline_obj.id = uuid.UUID(outline_id)
            outline_service.save_outline(outline_obj)
            logger.info("大纲已落库: outline_id=%s, title=%s", outline_id, outline_title)
        except Exception as e:
            # 不阻断：模板文件已生成，允许前端继续；但会影响 drafts/sources 等功能
            logger.warning("大纲落库失败(将继续返回模板): outline_id=%s, error=%s", outline_id, e, exc_info=True)

        # 返回成功响应
        return create_success_response(
            data={
                "outlineId": outline_id,
                "templatePath": str(template_path),  # 返回模板文件路径
                "titleCount": len([line for line in cleaned_lines if line.startswith('#')]),  # 返回标题数量
            }
        )

    except Exception as e:
        logger.exception("创建大纲异常: %s", e)
        return create_error_response_from_exception(e)


@router.post(
    "/polish-outline",
    response_model=dict[str, Any],
    summary="优化大纲文本",
    description="使用AI优化大纲文本(前端适配接口)",
)
async def polish_outline(
    request: OutlinePolishRequest,
    http_request: Request,
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
    industry_service: IndustrySelectionService = Depends(get_industry_selection_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> Any:
    """
    优化大纲文本接口(前端适配)

    注意:此接口直接优化文本,不创建大纲记录

    Args:
        request: 优化请求
        outline_service: 大纲优化服务
        industry_service: 行业选择服务
        llm_service: LLM服务

    Returns:
        统一响应格式:{ success: bool, polishedOutline: str }
    """
    try:
        # 方案C：支持真正的流式响应（SSE）
        # - 前端通过 `Accept: text/event-stream` 或 `?stream=1` 启用
        # - 兼容旧客户端：未启用时仍返回 JSON
        accept = (http_request.headers.get("accept") or "").lower()
        want_stream = (
            "text/event-stream" in accept
            or http_request.query_params.get("stream") in {"1", "true", "yes"}
        )

        if want_stream:
            from langchain_core.messages import HumanMessage, SystemMessage

            model = llm_service.get_chat_model()

            system_prompt = (
                "你是一位资深行业研究白皮书编辑与结构化写作专家。"
                "你的任务是对用户提供的白皮书大纲进行润色与结构优化："
                "保持原意不偏题，增强层次逻辑与专业性，修正标题表达，补足必要章节。"
                "请直接输出优化后的大纲文本（使用清晰的Markdown层级结构），不要输出任何解释。"
            )

            user_prompt = (
                "请对以下大纲进行AI润色优化，输出优化后的大纲：\n\n"
                f"{request.outlineText}"
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            q: queue.Queue[tuple[str, str]] = queue.Queue()

            def _worker():
                try:
                    for chunk in model.stream(messages):
                        text = getattr(chunk, "content", None)
                        if text:
                            q.put(("delta", text))
                    q.put(("done", ""))
                except Exception as e:  # pragma: no cover (网络/供应商异常)
                    q.put(("error", str(e)))

            threading.Thread(target=_worker, daemon=True).start()

            def _sse(event: str, payload: dict[str, Any]) -> bytes:
                return (
                    f"event: {event}\n"
                    f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                ).encode("utf-8")

            def _iter_events():
                # 先立刻发一个 started，避免"毫无响应"的体验
                yield _sse("status", {"state": "started"})

                full_text = ""
                last_activity = time.time()

                while True:
                    try:
                        event, data = q.get(timeout=1.0)
                    except queue.Empty:
                        # 心跳：确保前端"inactivity timeout"能被持续重置
                        yield b": ping\n\n"
                        continue

                    last_activity = time.time()

                    if event == "delta":
                        full_text += data
                        yield _sse("delta", {"text": data})
                        continue
                    if event == "error":
                        yield _sse("error", {"message": data})
                        return
                    if event == "done":
                        yield _sse("done", {"polishedOutline": full_text})
                        return

                    # 未知事件：忽略
                    if time.time() - last_activity > 600:
                        yield _sse(
                            "error",
                            {"message": "AI优化超时：长时间无输出，请稍后重试"},
                        )
                        return

            return StreamingResponse(
                _iter_events(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )

        # 获取默认行业
        industries = industry_service.get_industries()
        if not industries:
            return create_error_response("未找到可用行业")

        default_industry = industries[0]
        industry_id = uuid.UUID(default_industry["id"])

        # 创建临时大纲用于优化
        outline = domain_create_outline_from_text(
            title="临时大纲",
            text=request.outlineText,
            industry_id=industry_id,
            database_ids=[],
        )

        # 获取行业名称
        industry_name = default_industry.get("name", "储能行业")

        # 创建大纲优化Agent
        agent = create_outline_optimizer_agent(
            llm_service=llm_service,
            report_type="市场研究报告",
        )

        # 优化大纲
        optimized_outline = agent.optimize_outline(
            outline=outline,
            industry_name=industry_name,
            database_names=[],
            report_type="市场研究报告",
        )

        # 将优化后的大纲转换为文本格式
        # 简单实现:将大纲项转换为文本
        polished_lines = []
        for item in optimized_outline.optimized_items:
            if item.optimized_item:
                indent = "  " * (item.optimized_item.level - 1)
                polished_lines.append(f"{indent}{item.optimized_item.title}")
                if item.optimized_item.description:
                    polished_lines.append(f"{indent}  {item.optimized_item.description}")

        polished_text = "\n".join(polished_lines) if polished_lines else request.outlineText

        return create_success_response(
            data={"polishedOutline": polished_text}
        )

    except Exception as e:
        logger.exception("优化大纲异常: %s", e)
        return create_error_response_from_exception(e)


__all__ = ["router"]
