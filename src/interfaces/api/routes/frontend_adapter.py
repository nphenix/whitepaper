"""
前端适配层路由

提供前端期望的 API 接口,适配前端代码库(TTsending)的调用方式.
统一响应格式:{ success: bool, data?: any, error?: string }
内部调用后端现有服务(/api/v1/*)

生成命令: /speckit.implement T249
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse

from src.application.agents.outline_optimizer_mvp import (
    create_outline_optimizer_agent,
)
from src.application.services.document_service import DocumentService
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
    get_feedback_collector,
    handle_errors,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    AnalyzeWhitepaperRequest,
    AnalyzeWhitepaperResponse,
    ChatRequest,
    DraftGenerateRequest,
    HistoryItem,
    OutlineCreateRequest,
    OutlinePolishRequest,
    SourceSelectionRequest,
    UpdateWorkflowStepRequest,
    UserFeedbackRequest,
    create_error_response,
    create_success_response,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.base_exceptions import ResourceNotFoundError
from src.shared.utils.logging import get_logger

if TYPE_CHECKING:
    from src.infrastructure.indexing.hybrid_retriever import HybridRetriever

# 获取日志器
logger = get_logger(__name__)

# 创建路由器 - 使用 /api 前缀(无版本号)
router = APIRouter(prefix="/api", tags=["前端适配层"])

# 全局服务实例
_outline_optimization_service: OutlineOptimizationService | None = None
_industry_selection_service: IndustrySelectionService | None = None
_document_service: DocumentService | None = None
_llm_service: LLMService | None = None

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
        from src.shared.exceptions.base_exceptions import (
            ResourceNotFoundError,
        )

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

        # 从文本创建大纲
        try:
            outline = domain_create_outline_from_text(
                title=config.get("title", "白皮书大纲"),
                text=request.outlineText,
                industry_id=uuid.UUID(str(industry_id)),
                database_ids=database_uuid_list,
                description=config.get("description"),
            )
            logger.info("大纲创建成功: ID=%s, 行业=%s, 数据库数量=%d",
                       outline.id, industry_id, len(database_uuid_list))
        except Exception as e:
            logger.error("创建大纲对象失败: %s", e, exc_info=True)
            return create_error_response(
                "创建大纲失败",
                f"无法从文本创建大纲: {e!s}"
            )

        # 保存大纲
        try:
            outline_service.save_outline(outline)
            outline_id = str(outline.id)
            logger.info("大纲保存成功: ID=%s", outline_id)
        except Exception as e:
            logger.error("保存大纲失败: %s", e, exc_info=True)
            return create_error_response(
                "保存大纲失败",
                f"无法保存大纲到数据库: {e!s}"
            )

        # 生成草稿依赖 optimized_outlines 记录。
        # 这里不再同步调用 LLM 做“自动优化”（会导致 /api/outline 长时间 pending，前端卡在“处理中...”）。
        # 默认策略：直接用当前 outline（通常已由 /api/polish-outline 产生“优化后文本”）构造一个等价的 OptimizedOutline 并落库。
        # 如需强制 LLM 二次优化，可通过 config.auto_optimize_with_llm=true 显式开启。
        try:
            auto_optimize_with_llm = bool(config.get("auto_optimize_with_llm", False))

            if auto_optimize_with_llm:
                from src.application.agents.outline_optimizer_mvp import (
                    create_outline_optimizer_agent,
                )

                industry_name = selected_industry.get("name", "储能行业")
                database_names = []
                for db_id in database_uuid_list:
                    try:
                        database = industry_service.get_database_by_id(str(db_id))
                        if database:
                            database_names.append(database["name"])
                    except Exception as e:
                        logger.warning("获取数据库信息失败: %s, 错误: %s", db_id, e)

                llm_service = get_llm_service()
                agent = create_outline_optimizer_agent(
                    llm_service=llm_service,
                    report_type=config.get("report_type", "市场研究报告"),
                )

                logger.info("开始自动LLM优化大纲: outline_id=%s", outline_id)
                optimized_outline = agent.optimize_outline(
                    outline=outline,
                    industry_name=industry_name,
                    database_names=database_names,
                    report_type=config.get("report_type", "市场研究报告"),
                )
            else:
                # 无 LLM：直接把当前 outline 作为“已优化结果”落库，保证后续生成草稿能找到优化历史
                from src.domain.agent.optimized_outline import (
                    create_optimized_outline_from_outline,
                )

                optimized_items_data = [
                    {
                        "original_item_id": str(item.id),
                        "optimized_item": item.to_dict(),
                        "change_type": "NONE",
                    }
                    for item in outline.items
                ]
                optimized_outline = create_optimized_outline_from_outline(
                    original_outline=outline,
                    optimized_items_data=optimized_items_data,
                )

            outline_service.save_optimized_outline(optimized_outline)
            logger.info(
                "优化后大纲记录已保存: outline_id=%s, optimized_outline_id=%s (llm=%s)",
                outline_id,
                optimized_outline.id,
                auto_optimize_with_llm,
            )
        except Exception as e:
            # 不阻断大纲创建，但记录警告（草稿生成接口会再次尝试 auto-optimize 作为兜底）
            logger.warning(
                "保存优化后大纲记录失败（不影响大纲创建）: outline_id=%s, 错误: %s",
                outline_id,
                e,
                exc_info=True,
            )

        return create_success_response(
            data={
                "outlineId": outline_id,
                "optimizedOutline": request.outlineText,  # 返回原始文本
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
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
    industry_service: IndustrySelectionService = Depends(get_industry_selection_service),
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
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


@router.post(
    "/upload",
    response_model=dict[str, Any],
    summary="上传文件",
    description="上传文档文件(前端适配接口)",
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    document_service: DocumentService = Depends(get_document_service),
) -> dict[str, Any]:
    """
    上传文件接口(前端适配)

    映射到:POST /api/v1/documents/upload

    完整流程:
    1. 保存文件到临时目录
    2. 调用文档服务进行格式识别和预处理
    3. 从数据库获取处理后的文档记录
    4. 转换为前端期望的响应格式

    Args:
        file: 上传的文件
        document_service: 文档服务

    Returns:
        统一响应格式:{ success: bool, data: { file: { filename, path, size } } }
    """
    file_path: Path | None = None
    lock_path: Path | None = None
    try:
        from src.shared.config.settings import get_config
        from src.shared.exceptions.base_exceptions import ProcessingError

        config = get_config()

        # 验证文件大小
        max_file_size = config.document.max_upload_size
        file.file.seek(0, 2)  # 移动到文件末尾
        file_size = file.file.tell()
        file.file.seek(0)  # 重置文件指针

        if file_size > max_file_size:
            logger.warning("文件过大: %s (大小: %d, 限制: %d)", file.filename, file_size, max_file_size)
            return create_error_response(
                f"文件过大,最大允许 {max_file_size} 字节",
                f"文件大小: {file_size} 字节"
            )

        # 保存上传的文件到临时目录
        upload_dir = config.document.upload_temp_dir
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成稳定文件名(基于内容hash)，避免同一文件在 e2e/pytest 重跑时重复触发预处理和LLM调用
        import hashlib

        file_extension = Path(file.filename).suffix if file.filename else ""
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        stable_filename = f"{file_hash[:32]}{file_extension}"
        file_path = upload_dir / stable_filename

        # 保存文件
        try:
            if file_path.exists() and file_path.is_file() and file_path.stat().st_size == len(content):
                logger.info("检测到相同内容文件已存在，复用: %s", file_path)
            else:
                with file_path.open("wb") as f:
                    f.write(content)
                logger.info("文件保存成功: %s -> %s", file.filename, file_path)
        except Exception as e:
            logger.error("保存上传文件失败: %s", e, exc_info=True)
            return create_error_response("保存文件失败", str(e))

        # 使用固定的测试用户ID
        test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        # 处理锁：同一内容文件在处理期间禁止重复触发预处理（解决连接中断/重复点击/pytest 重试导致的重复跑）
        import os
        import time

        lock_path = upload_dir / f"{stable_filename}.processing.lock"
        # 如果锁存在且很久没更新，认为是 stale（例如上次进程异常退出）
        if lock_path.exists():
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > 6 * 3600:  # 6h
                    logger.warning("检测到 stale processing lock，移除: %s (age=%.0fs)", lock_path, age)
                    lock_path.unlink(missing_ok=True)
            except Exception:
                # ignore
                pass

        lock_acquired = False
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"pid={os.getpid()}\nfilename={stable_filename}\n")
            lock_acquired = True
            logger.info("获取 processing lock: %s", lock_path)
        except FileExistsError:
            logger.info("processing lock 已存在，跳过重复处理: %s", lock_path)

        # 如果同一份内容已经有文档记录（处理中或已完成），直接复用记录，避免重复触发预处理/LLM调用
        try:
            existing_rows = document_service.document_repository.list(
                filters={"uploaded_by": str(test_user_id), "filename": stable_filename},
                limit=5,
                order_by="uploaded_at DESC",
            )
            if existing_rows:
                latest = existing_rows[0]
                existing_status = str(latest.get("status", "")).lower()
                # 如果已经在处理/已完成，直接返回；如果 lock 未获取到，也必须返回（避免并发重复处理）
                if (existing_status and existing_status != "failed") or (not lock_acquired):
                    logger.info(
                        "检测到文档记录已存在，跳过重复处理: filename=%s, status=%s, id=%s",
                        stable_filename,
                        existing_status,
                        latest.get("id"),
                    )
                    return create_success_response(
                        data={
                            "file": {
                                "filename": latest.get("filename") or stable_filename,
                                "path": latest.get("file_path") or str(file_path),
                                "size": latest.get("file_size") or file_size,
                            }
                        }
                    )
        except Exception as e:
            # 防御性：复用查询失败不应阻断正常处理流程
            logger.warning("检查重复文档记录失败，将继续处理: %s", e)

        # 如果没有获取到 lock，说明其他请求正在处理；这里直接返回“已接收/处理中”，避免重复跑
        if not lock_acquired:
            return create_success_response(
                data={
                    "file": {
                        "filename": stable_filename,
                        "path": str(file_path),
                        "size": file_size,
                    }
                }
            )

        # 调用文档服务进行完整的文档处理(同步处理)
        try:
            logger.info("开始处理文档: %s", file_path)
            documents = document_service.upload_and_process(
                file_path=str(file_path),
                uploaded_by=test_user_id,
                doc_format=None,  # 自动识别格式
            )
            logger.info("文档处理完成,生成 %d 个文档片段", len(documents))

            # 从数据库获取最新文档记录
            db_documents = document_service.list_documents(
                uploaded_by=test_user_id,
                limit=1,
            )
            if not db_documents:
                logger.error("文档处理完成但未找到文档记录")
                return create_error_response(
                    "文档处理完成但未找到文档记录",
                    "请检查数据库连接或文档服务配置"
                )

            # 获取最新的文档记录
            domain_doc = db_documents[-1]
            logger.info("获取文档记录: ID=%s, filename=%s, status=%s",
                       domain_doc.id, domain_doc.filename, domain_doc.status)

            # 转换为前端期望的响应格式
            return create_success_response(
                data={
                    "file": {
                        "filename": domain_doc.filename,
                        "path": domain_doc.file_path,
                        "size": domain_doc.file_size,
                    }
                }
            )

        except ProcessingError as e:
            # 预期错误：例如用户上传了不支持的文件格式。
            # 不需要打印完整 traceback；同时应返回 4xx，避免前端/调用方误判为成功(HTTP 200)。
            logger.warning("文档处理失败: %s", e)
            return JSONResponse(
                content=create_error_response("文档处理失败", str(e)),
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )
        except Exception as e:
            logger.exception("调用文档服务异常: %s", e)
            return create_error_response(
                "文档处理异常",
                str(e)
            )

    except Exception as e:
        logger.exception("上传文件异常: %s", e)
        return create_error_response_from_exception(e)
    finally:
        # 释放 processing lock
        try:
            if lock_path and lock_path.exists():
                lock_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.get(
    "/draft/{draft_id}",
    response_model=dict[str, Any],
    summary="获取草稿",
    description="根据ID获取草稿内容(前端适配接口)",
)
async def get_draft(
    draft_id: str,
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
        # 从数据库获取草稿
        from src.application.services.draft_service import DraftService

        draft_service = DraftService()
        try:
            draft = draft_service.get_draft(draft_id)
        except ResourceNotFoundError:
            # 兼容前端行为：传入的是 outline_id，而不是 draft_id
            try:
                draft = draft_service.get_latest_draft_for_outline(draft_id)
            except ResourceNotFoundError:
                # 草稿可能仍在后台生成中：这里不能返回 success=false，
                # 否则前端会把它当作“致命错误”直接停止轮询。
                return create_success_response(
                    data={"draft": "", "sources": {}, "status": "RUNNING"},
                    message="草稿生成中",
                )

        # 获取草稿内容
        draft_content = draft.get_content()

        # 获取来源信息(如果有)- 从数据库获取
        get_source_adapter()
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
        import json
        import asyncio

        from src.application.agents.draft_generator_mvp import (
            create_draft_generator_agent,
        )
        from src.interfaces.api.routes.draft_mvp import get_hybrid_retriever
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
                        optimized_item_id = uuid.UUID(str(optimized_item_id_str))

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

                    optimized_items.append(
                        OptimizedOutlineItem(
                            id=uuid.UUID(str(node.get("id"))) if node.get("id") else uuid.uuid4(),
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
                    title=outline_data.get("title", "白皮书大纲"),
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
            except ResourceNotFoundError:
                logger.warning("优化后大纲不存在: %s", optimized_outline_id)
                return create_error_response(
                    f"优化后大纲不存在: {optimized_outline_id}",
                    "请检查优化历史记录"
                )
            except Exception as e:
                logger.error("获取优化后大纲失败: %s", e, exc_info=True)
                return create_error_response(
                    "获取优化后大纲失败",
                    str(e)
                )

            # 转换为 OptimizedOutline 对象：优先新结构，失败则走旧表结构 optimized_structure
            try:
                optimized_outline = _convert_to_optimized_outline(optimized_outline_result)
            except Exception as e:
                logger.warning("转换优化后大纲失败，尝试从 optimized_structure 解析(兼容旧表结构): %s", e)
                try:
                    optimized_outline = _convert_legacy_optimized_result(optimized_outline_result)
                except Exception as legacy_err:
                    logger.error("旧表结构解析优化后大纲失败: %s", legacy_err, exc_info=True)
                    return create_error_response(
                        "转换优化后大纲失败",
                        str(legacy_err),
                    )

        # 4. 验证行业是否存在并获取行业名称
        try:
            industry = industry_service.get_industry_by_id(str(industry_id))
            industry_name = industry["name"]
        except ResourceNotFoundError:
            logger.warning("行业不存在: %s", industry_id)
            return create_error_response(
                f"行业不存在: {industry_id}",
                "请检查大纲关联的行业ID"
            )
        except Exception as e:
            logger.error("获取行业信息失败: %s", e, exc_info=True)
            return create_error_response(
                "获取行业信息失败",
                str(e)
            )

        # 5. 获取数据库名称列表
        database_names = []
        if database_ids:
            for db_id in database_ids:
                try:
                    database = industry_service.get_database_by_id(str(db_id))
                    if database:
                        database_names.append(database["name"])
                except Exception as e:
                    logger.warning("获取数据库信息失败: %s, 错误: %s", db_id, e)
                    # 继续处理其他数据库

        # 6. 获取 HybridRetriever(可能为 None)
        hybrid_retriever: HybridRetriever | None = get_hybrid_retriever()
        if hybrid_retriever is None:
            logger.info("HybridRetriever 未配置,将不使用检索功能")

        # 7. 创建草稿生成Agent
        try:
            agent = create_draft_generator_agent(
                llm_service=llm_service,
                report_type=report_type,
                language=language,
                style=style,
                hybrid_retriever=hybrid_retriever,
            )
            logger.info("草稿生成Agent创建成功: report_type=%s, language=%s, style=%s",
                       report_type, language, style)
        except Exception as e:
            logger.error("创建草稿生成Agent失败: %s", e, exc_info=True)
            return create_error_response(
                "创建草稿生成Agent失败",
                str(e)
            )

        # 8. 后台生成草稿（避免在Windows单worker下阻塞事件循环，导致 /draft 轮询请求无法响应）
        # 说明：
        # - 前端 FinalView 会轮询 /api/draft/{outlineId}
        # - 如果这里同步执行LLM调用，会阻塞整个服务（单事件循环），导致轮询 hang 住
        global _draft_generation_tasks
        if "_draft_generation_tasks" not in globals():
            _draft_generation_tasks = {}

        existing_task = _draft_generation_tasks.get(outline_id)
        if existing_task and not existing_task.done():
            return create_success_response(
                data={"status": "RUNNING"},
                message="草稿生成中(已在后台运行)",
            )

        async def _run_generation() -> None:
            try:
                logger.info(
                    "后台开始生成草稿: outline_id=%s, optimized_outline_id=%s",
                    outline_id,
                    optimized_outline_id,
                )

                # 生成草稿放到线程池执行，避免阻塞事件循环
                draft = await asyncio.to_thread(
                    agent.generate_draft,
                    optimized_outline,
                    industry_name,
                    database_names,
                    report_type,
                )

                logger.info(
                    "后台草稿生成成功: draft_id=%s, title=%s, sections=%d",
                    draft.id,
                    draft.title,
                    len(draft.sections),
                )

                # 保存草稿到数据库（也放到线程执行，避免阻塞）
                from src.application.services.draft_service import DraftService

                test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

                def _save() -> None:
                    DraftService().save_draft(draft, test_user_id)

                await asyncio.to_thread(_save)
                logger.info("后台草稿保存成功: draft_id=%s", draft.id)
            except Exception as e:
                logger.error("后台生成草稿失败: %s", e, exc_info=True)
            finally:
                # 清理任务引用
                try:
                    _draft_generation_tasks.pop(outline_id, None)
                except Exception:
                    pass

        task = asyncio.create_task(_run_generation())
        _draft_generation_tasks[outline_id] = task

        # 立即返回，让前端去轮询 /draft
        return create_success_response(
            data={"status": "STARTED"},
            message="草稿生成已启动(后台运行)",
        )

    except Exception as e:
        logger.exception("生成草稿异常: %s", e)
        return create_error_response_from_exception(e)


@router.post(
    "/sources/{outline_id}",
    response_model=dict[str, Any],
    summary="保存来源选择",
    description="保存用户选择的来源(前端适配接口)",
)
async def save_sources(
    outline_id: str,
    request: SourceSelectionRequest,
) -> dict[str, Any]:
    """
    保存来源选择接口(前端适配)

    支持多种来源类型:
    - 推荐文献(source_type='recommended', source_id=文献ID)
    - 自定义URL(source_type='custom_url', source_id=URL)
    - 上传文件(source_type='uploaded_file', source_id=文件ID)

    来源数据完整性支持:
    - 可选传递 sourceDetails 字段,包含来源的详细信息(title, authors, year等)
    - 如果提供了 sourceDetails,将完整信息存储到 source_data 字段
    - 后续获取来源时,可以显示完整的来源信息,而不是默认值

    请求示例:
    {
        "selectedSources": [1, 2, 3],
        "customUrls": ["https://example.com"],
        "sourceDetails": {
            "1": {
                "title": "文献标题",
                "authors": "作者",
                "year": "2024",
                "domain": "example.com",
                "cited": 100,
                "excerpt": "摘要"
            },
            "https://example.com": {
                "title": "网页标题",
                "url": "https://example.com",
                "domain": "example.com"
            }
        }
    }

    Args:
        outline_id: 大纲ID
        request: 来源选择请求

    Returns:
        统一响应格式:{ success: bool, message?: str }
    """
    try:
        import json
        from datetime import datetime

        from src.shared.exceptions.base_exceptions import (
            ResourceNotFoundError,
        )

        # 验证大纲是否存在
        outline_service = get_outline_optimization_service()
        try:
            outline_service.get_outline(outline_id)
        except ResourceNotFoundError:
            return create_error_response(
                f"大纲不存在: {outline_id}",
                "请检查大纲ID是否正确"
            )

        # 获取来源存储适配器
        source_adapter = get_source_adapter()

        # 删除该大纲的现有来源(先删除后插入,实现更新)
        # 如果表不存在，跳过删除操作
        try:
            existing_sources = source_adapter.list(filters={"outline_id": outline_id})
            for source in existing_sources:
                source_adapter.delete(source["id"])
            logger.info("删除大纲 %s 的现有来源: %d 条", outline_id, len(existing_sources))
        except Exception as e:
            error_str = str(e)
            error_messages = [error_str]
            current_exception = e
            while current_exception.__cause__:
                error_messages.append(str(current_exception.__cause__))
                current_exception = current_exception.__cause__
            all_error_text = " ".join(error_messages).lower()
            
            if "no such table" in all_error_text or "outline_sources" in all_error_text:
                logger.warning("outline_sources表不存在，跳过删除操作。这可能是正常的（表尚未创建）。错误: %s", error_str)
            else:
                logger.warning("删除现有来源失败(继续插入): %s", error_str)

        # 保存推荐文献来源
        saved_count = 0
        now = datetime.now(UTC).isoformat()

        for source_id in request.selectedSources:
            try:
                # 获取来源详细信息(如果提供)
                source_detail = {}
                source_id_str = str(source_id)
                if request.sourceDetails and source_id_str in request.sourceDetails:
                    detail = request.sourceDetails[source_id_str]
                    source_detail = {
                        "title": detail.title,
                        "authors": detail.authors,
                        "year": detail.year,
                        "domain": detail.domain,
                        "cited": detail.cited,
                        "excerpt": detail.excerpt,
                    }
                    # 移除None值
                    source_detail = {k: v for k, v in source_detail.items() if v is not None}
                    logger.debug("获取到来源详细信息: source_id=%s, detail=%s", source_id, source_detail)
                else:
                    logger.debug("未提供来源详细信息: source_id=%s", source_id)

                source_data = {
                    "id": str(uuid.uuid4()),
                    "outline_id": outline_id,
                    "source_type": "recommended",
                    "source_id": source_id_str or "",
                    "source_data": json.dumps(source_detail, ensure_ascii=False) if source_detail else "{}",
                    "created_at": now,
                    "updated_at": now,
                }
                # 确保所有字段都有值，不能是None
                source_data = {k: v if v is not None else "" for k, v in source_data.items()}
                source_adapter.create(source_data)
                saved_count += 1
                logger.debug("保存推荐文献来源成功: source_id=%s, 详细信息=%s", source_id, bool(source_detail))
            except Exception as e:
                error_str = str(e)
                error_messages = [error_str]
                current_exception = e
                while current_exception.__cause__:
                    error_messages.append(str(current_exception.__cause__))
                    current_exception = current_exception.__cause__
                all_error_text = " ".join(error_messages).lower()
                
                if "no such table" in all_error_text or "outline_sources" in all_error_text:
                    logger.warning("outline_sources表不存在，跳过保存推荐文献来源。这可能是正常的（表尚未创建）。错误: %s", error_str)
                elif "syntax error" in all_error_text:
                    logger.warning("保存推荐文献来源失败: SQL语法错误: source_id=%s, 错误: %s", source_id, error_str)
                else:
                    logger.warning("保存推荐文献来源失败: source_id=%s, 错误: %s", source_id, error_str)

        # 保存自定义URL来源
        for url in request.customUrls:
            try:
                # 获取URL来源的详细信息(如果提供)
                url_detail = {}
                if request.sourceDetails and url in request.sourceDetails:
                    detail = request.sourceDetails[url]
                    url_detail = {
                        "title": detail.title,
                        "url": detail.url or url,  # 如果没有提供url字段,使用原始URL
                        "domain": detail.domain,
                        "excerpt": detail.excerpt,
                    }
                    # 移除None值
                    url_detail = {k: v for k, v in url_detail.items() if v is not None}
                    logger.debug("获取到URL来源详细信息: url=%s, detail=%s", url, url_detail)
                else:
                    # 如果没有提供详细信息,至少存储URL本身
                    url_detail = {"url": url}
                    logger.debug("未提供URL来源详细信息,使用默认值: url=%s", url)

                source_data = {
                    "id": str(uuid.uuid4()),
                    "outline_id": outline_id,
                    "source_type": "custom_url",
                    "source_id": url or "",
                    "source_data": json.dumps(url_detail, ensure_ascii=False) if url_detail else "{}",
                    "created_at": now,
                    "updated_at": now,
                }
                # 确保所有字段都有值，不能是None
                source_data = {k: v if v is not None else "" for k, v in source_data.items()}
                source_adapter.create(source_data)
                saved_count += 1
                logger.debug("保存自定义URL来源成功: url=%s, 详细信息=%s", url, bool(url_detail))
            except Exception as e:
                error_str = str(e)
                error_messages = [error_str]
                current_exception = e
                while current_exception.__cause__:
                    error_messages.append(str(current_exception.__cause__))
                    current_exception = current_exception.__cause__
                all_error_text = " ".join(error_messages).lower()
                
                if "no such table" in all_error_text or "outline_sources" in all_error_text:
                    logger.warning("outline_sources表不存在，跳过保存自定义URL来源。这可能是正常的（表尚未创建）。错误: %s", error_str)
                elif "syntax error" in all_error_text:
                    logger.warning("保存自定义URL来源失败: SQL语法错误: url=%s, 错误: %s", url, error_str)
                else:
                    logger.warning("保存自定义URL来源失败: url=%s, 错误: %s", url, error_str)

        logger.info("保存来源成功: outline_id=%s, 保存数量=%d", outline_id, saved_count)

        return create_success_response(
            message=f"成功保存 {saved_count} 个来源"
        )

    except Exception as e:
        logger.exception("保存来源异常: %s", e)
        return create_error_response_from_exception(e)


@router.get(
    "/sources/{outline_id}",
    response_model=dict[str, Any],
    summary="获取来源列表",
    description="获取大纲关联的来源列表(前端适配接口)",
)
async def get_sources(
    outline_id: str,
) -> dict[str, Any]:
    """
    获取来源列表接口(前端适配)

    从数据库获取大纲关联的所有来源,包括:
    - 推荐文献(source_type='recommended')
    - 自定义URL(source_type='custom_url')
    - 上传文件(source_type='uploaded_file')

    Args:
        outline_id: 大纲ID

    Returns:
        统一响应格式:{ success: bool, sources: [...] }

        注意:为了匹配前端期望的格式,直接在根级别返回sources字段
        而不是嵌套在data字段中(与其他接口的格式略有不同)
    """
    try:
        import json

        from src.shared.exceptions.base_exceptions import ResourceNotFoundError

        # 验证大纲是否存在
        outline_service = get_outline_optimization_service()
        try:
            outline_service.get_outline(outline_id)
        except ResourceNotFoundError:
            return create_error_response(
                f"大纲不存在: {outline_id}",
                "请检查大纲ID是否正确"
            )

        # 获取来源存储适配器
        source_adapter = get_source_adapter()

        # 从数据库获取来源列表
        try:
            sources_data = source_adapter.list(
                filters={"outline_id": outline_id},
                order_by="created_at ASC"
            )
        except Exception as e:
            logger.error("从数据库获取来源列表失败: %s", e, exc_info=True)
            return create_error_response(
                "获取来源列表失败",
                str(e)
            )

        # 转换为前端期望的格式
        sources = []
        for source in sources_data:
            source_type = source.get("source_type", "")
            source_id = source.get("source_id", "")

            # 解析额外的JSON数据
            source_data_json = {}
            source_data_str = source.get("source_data", "{}")
            if source_data_str:
                try:
                    source_data_json = json.loads(source_data_str) if isinstance(source_data_str, str) else source_data_str
                except (json.JSONDecodeError, TypeError):
                    source_data_json = {}

            # 根据来源类型构建响应数据
            if source_type == "recommended":
                # 推荐文献:source_id 是文献ID
                sources.append({
                    "id": int(source_id) if source_id.isdigit() else source_id,
                    "type": "recommended",
                    "sourceId": source_id,
                    "title": source_data_json.get("title", f"文献 {source_id}"),
                    "authors": source_data_json.get("authors", ""),
                    "year": source_data_json.get("year", ""),
                    "domain": source_data_json.get("domain", ""),
                    "cited": source_data_json.get("cited", 0),
                    "recommended": True,
                })
            elif source_type == "custom_url":
                # 自定义URL:source_id 是URL
                sources.append({
                    "id": source["id"],
                    "type": "custom_url",
                    "url": source_id,
                    "title": source_data_json.get("title", source_id),
                    "domain": source_data_json.get("domain", ""),
                })
            elif source_type == "uploaded_file":
                # 上传文件:source_id 是文件ID
                sources.append({
                    "id": source["id"],
                    "type": "uploaded_file",
                    "fileId": source_id,
                    "filename": source_data_json.get("filename", f"文件 {source_id}"),
                    "title": source_data_json.get("title", f"文件 {source_id}"),
                })
            else:
                # 未知类型,使用通用格式
                sources.append({
                    "id": source["id"],
                    "type": source_type,
                    "sourceId": source_id,
                    "data": source_data_json,
                })

        logger.info("获取来源列表成功: outline_id=%s, 数量=%d", outline_id, len(sources))

        # 注意:为了匹配前端期望的格式,直接在根级别返回sources字段
        # 前端代码期望: { success: true, sources: [...] }
        # 而不是: { success: true, data: { sources: [...] } }
        return {
            "success": True,
            "sources": sources
        }

    except Exception as e:
        logger.exception("获取来源异常: %s", e)
        return create_error_response_from_exception(e)


# === 历史记录接口 ===


@router.get(
    "/history",
    response_model=dict[str, Any],
    summary="获取历史记录",
    description="获取用户历史大纲列表(前端适配接口)",
)
async def get_history(
    limit: int = Query(50, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    outline_service: OutlineOptimizationService = Depends(get_outline_optimization_service),
) -> dict[str, Any]:
    """
    获取历史记录接口(前端适配)

    获取用户历史大纲列表,包括:
    - 大纲标题,创建时间
    - 草稿状态(是否有草稿)
    - 按时间倒序排列
    - 支持分页

    Args:
        limit: 每页数量(默认50)
        offset: 偏移量(默认0)
        outline_service: 大纲优化服务

    Returns:
        统一响应格式:{ success: bool, data: { history: [...] } }
    """
    try:
        import uuid

        from src.application.services.draft_service import DraftService

        # 1. 获取大纲总数(用于分页信息)
        total_count = outline_service.outline_adapter.count(filters=None)

        # 2. 获取大纲列表(按创建时间倒序)
        # 使用outline_adapter直接查询数据库
        # 注意:SQLiteAdapter的list方法不支持offset,所以需要先获取足够的数据,然后手动分页
        # 为了性能,只获取当前页需要的数据量
        fetch_limit = limit + offset if limit + offset > 0 else None
        outline_records = outline_service.outline_adapter.list(
            filters=None,  # 不过滤,获取所有大纲
            limit=fetch_limit,  # 先获取足够的数据,然后手动分页
            order_by="created_at DESC",  # 按创建时间倒序
        )

        # 手动实现分页(因为SQLiteAdapter不支持offset参数)
        outline_records = outline_records[offset:offset + limit] if offset < len(outline_records) else []

        logger.info("获取大纲列表: 总数=%d, 返回=%d (offset=%d, limit=%d)",
                   total_count, len(outline_records), offset, limit)

        # 3. 获取草稿服务实例
        draft_service = DraftService()

        # 4. 转换为HistoryItem格式,并关联草稿状态
        history_items = []
        for outline_record in outline_records:
            outline_id = outline_record.get("id")
            title = outline_record.get("title", "未命名大纲")
            created_at = outline_record.get("created_at", "")

            # 查询是否有草稿(通过outline_id查询)
            has_draft = False
            try:
                outline_uuid = uuid.UUID(str(outline_id))
                drafts = draft_service.list_drafts(outline_id=outline_uuid, limit=1)
                has_draft = len(drafts) > 0
            except Exception as e:
                logger.warning("查询草稿状态失败: outline_id=%s, error=%s", outline_id, e)
                # 如果查询失败,默认has_draft为False

            history_item = HistoryItem(
                id=str(outline_id),
                title=title,
                date=created_at,
                hasDraft=has_draft,
            )
            history_items.append(history_item)

        logger.info("构建历史记录列表完成: 数量=%d", len(history_items))

        # 5. 返回响应
        return create_success_response(
            data={
                "history": [item.model_dump() for item in history_items],
                "total": total_count,
                "limit": limit,
                "offset": offset,
            }
        )

    except Exception as e:
        logger.exception("获取历史记录异常: %s", e)
        return create_error_response_from_exception(e)


# === 白皮书分析接口 ===


@router.post(
    "/analyze-whitepaper",
    response_model=dict[str, Any],
    summary="分析白皮书",
    description="白皮书质量分析接口(前端适配接口)",
)
async def analyze_whitepaper(
    request: AnalyzeWhitepaperRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """
    白皮书质量分析接口(前端适配)

    支持两种方式提供内容:
    1. 通过draft_id获取草稿内容进行分析
    2. 直接提供content内容进行分析

    分析维度:
    - 内容质量评估(深度,全面性,数据支撑)
    - 结构分析(章节安排,逻辑连贯性)
    - 专业性与可信度评估
    - 改进建议生成
    - 综合评分(1-10分)

    Args:
        request: 分析请求
        llm_service: LLM服务

    Returns:
        统一响应格式:{ success: bool, data: AnalyzeWhitepaperResponse }
    """
    try:
        from datetime import datetime

        from src.application.services.draft_service import DraftService
        from src.application.services.whitepaper_analysis_service import (
            WhitepaperAnalysisService,
        )

        # 获取内容
        content = None
        if request.draft_id:
            # 从草稿获取内容
            try:
                draft_service = DraftService()
                draft = draft_service.get_draft(request.draft_id)
                # 使用DraftService的内部方法将草稿转换为Markdown格式
                content = draft_service._draft_to_markdown(draft)
                logger.info("从草稿获取内容: draft_id=%s, 长度=%d", request.draft_id, len(content))
            except ResourceNotFoundError:
                return create_error_response(
                    f"草稿不存在: {request.draft_id}",
                    "请检查草稿ID是否正确"
                )
        elif request.content:
            # 直接使用提供的内容
            content = request.content
            logger.info("使用提供的白皮书内容,长度=%d", len(content))
        else:
            return create_error_response(
                "缺少白皮书内容",
                "请提供draft_id或content参数"
            )

        # 创建分析服务
        analysis_service = WhitepaperAnalysisService(llm_service=llm_service)

        # 执行分析
        try:
            analysis_result = analysis_service.analyze(content)
        except ValueError as e:
            return create_error_response(
                "分析参数错误",
                str(e)
            )
        except Exception as e:
            logger.error("分析执行失败: %s", e, exc_info=True)
            return create_error_response(
                "分析执行失败",
                str(e)
            )

        # 转换为响应格式
        response_data = AnalyzeWhitepaperResponse(
            content_quality={
                "depth_score": analysis_result.content_quality.get("depth_score", 5.0),
                "comprehensiveness_score": analysis_result.content_quality.get("comprehensiveness_score", 5.0),
                "data_support_score": analysis_result.content_quality.get("data_support_score", 5.0),
                "depth_comment": analysis_result.content_quality.get("depth_comment", ""),
                "comprehensiveness_comment": analysis_result.content_quality.get("comprehensiveness_comment", ""),
                "data_support_comment": analysis_result.content_quality.get("data_support_comment", ""),
            },
            structure_analysis={
                "organization_score": analysis_result.structure_analysis.get("organization_score", 5.0),
                "coherence_score": analysis_result.structure_analysis.get("coherence_score", 5.0),
                "emphasis_score": analysis_result.structure_analysis.get("emphasis_score", 5.0),
                "organization_comment": analysis_result.structure_analysis.get("organization_comment", ""),
                "coherence_comment": analysis_result.structure_analysis.get("coherence_comment", ""),
                "emphasis_comment": analysis_result.structure_analysis.get("emphasis_comment", ""),
            },
            credibility={
                "terminology_score": analysis_result.credibility.get("terminology_score", 5.0),
                "citation_score": analysis_result.credibility.get("citation_score", 5.0),
                "insight_score": analysis_result.credibility.get("insight_score", 5.0),
                "terminology_comment": analysis_result.credibility.get("terminology_comment", ""),
                "citation_comment": analysis_result.credibility.get("citation_comment", ""),
                "insight_comment": analysis_result.credibility.get("insight_comment", ""),
            },
            improvement_suggestions=analysis_result.improvement_suggestions or [],
            overall_score=analysis_result.overall_score,
            summary=analysis_result.summary,
            strengths=analysis_result.strengths or [],
            weaknesses=analysis_result.weaknesses or [],
            timestamp=datetime.now(UTC).isoformat(),
        )

        logger.info("白皮书分析完成,综合评分: %.2f", analysis_result.overall_score)

        return create_success_response(data=response_data.model_dump())

    except Exception as e:
        logger.exception("分析白皮书异常: %s", e)
        return create_error_response_from_exception(e)


# === AI 聊天接口 ===


def get_hybrid_retriever():
    """获取混合检索引擎实例(可选)

    Returns:
        HybridRetriever: 混合检索引擎实例,如果未配置则返回None
    """
    try:
        from src.infrastructure.indexing.bm25_index import BM25IndexBuilder
        from src.infrastructure.indexing.hybrid_retriever import HybridRetriever
        from src.infrastructure.indexing.metadata_index import MetadataIndexBuilder
        from src.infrastructure.indexing.vector_index import VectorIndexBuilder

        # 尝试创建HybridRetriever实例
        # 如果索引未构建,将返回None(降级方案)
        try:
            vector_builder = VectorIndexBuilder()
            bm25_builder = BM25IndexBuilder()
            metadata_builder = MetadataIndexBuilder()

            retriever = HybridRetriever(
                vector_index_builder=vector_builder,
                bm25_index_builder=bm25_builder,
                metadata_index_builder=metadata_builder,
                llm_service=get_llm_service(),
            )
            logger.info("HybridRetriever 初始化成功")
            return retriever
        except Exception as e:
            logger.warning("HybridRetriever 初始化失败(将使用降级方案): %s", e)
            return None
    except ImportError:
        logger.warning("HybridRetriever 不可用(LlamaIndex未安装)")
        return None


@router.post(
    "/chat",
    response_model=dict[str, Any],
    summary="AI 聊天问答",
    description="基于知识库的AI聊天问答接口(前端适配接口)",
)
async def chat(
    request: ChatRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> dict[str, Any]:
    """
    AI 聊天问答接口(前端适配)

    基于知识库的RAG问答,支持:
    - 使用HybridRetriever进行混合检索
    - 可选的上下文记忆(基于outlineId)
    - 错误处理和降级方案
    - 使用ChatPromptTemplate管理提示词(符合LangChain 1.0最佳实践)

    Args:
        request: 聊天请求
        llm_service: LLM服务

    Returns:
        统一响应格式:{ success: bool, response: str, timestamp: str, sources?: [...] }
    """
    # 获取HybridRetriever(可能为None)
    hybrid_retriever = get_hybrid_retriever()

    # 如果请求流式响应,使用流式端点
    if request.stream:
        from src.interfaces.api.routes.frontend_adapter_stream import _chat_stream
        return await _chat_stream(request, llm_service, hybrid_retriever)

    # 非流式响应
    try:
        from datetime import datetime

        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        # 获取LLM模型
        try:
            llm = llm_service.get_chat_model()
        except Exception as e:
            logger.error("获取LLM模型失败: %s", e, exc_info=True)
            return create_error_response(
                "LLM服务不可用",
                "无法获取语言模型,请检查配置"
            )

        # 使用ChatPromptTemplate管理提示词(符合LangChain 1.0最佳实践)
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的文档分析助手,擅长回答关于文档内容的问题.

请根据提供的上下文信息回答问题.如果上下文中没有相关信息,请诚实地说不知道,不要编造答案.

回答要求:
1. 基于提供的上下文信息回答
2. 回答要准确,专业,简洁
3. 如果上下文不足,明确说明
4. 使用中文回答"""),
            MessagesPlaceholder(variable_name="chat_history"),  # 对话历史占位符
            ("human", """上下文信息:
{context}

问题:{input}

请基于上述上下文信息回答问题."""),
        ])

        # 加载对话历史(如果启用)
        chat_history = []
        if request.enableContext and request.outlineId:
            try:
                from src.infrastructure.storage.chat_history import (
                    get_chat_history_manager,
                )
                history_manager = get_chat_history_manager()
                # 加载最近6条消息(3轮对话)
                chat_history = history_manager.load_history(
                    outline_id=request.outlineId,
                    max_messages=6,
                )
                logger.info(
                    "加载对话历史: outline_id=%s, messages_count=%d",
                    request.outlineId,
                    len(chat_history)
                )
            except Exception as e:
                logger.warning("加载对话历史失败: %s,将使用无上下文模式", e)
                chat_history = []

        # 如果有HybridRetriever,使用RAG模式
        if hybrid_retriever:
            try:
                # 执行混合检索
                top_k = request.topK or 5
                logger.info("执行RAG检索: query=%s, top_k=%d", request.message[:50], top_k)

                # 检索相关文档
                retrieved_nodes = hybrid_retriever.retrieve(
                    query_str=request.message,
                    top_k=top_k,
                )

                # 构建上下文
                context_parts = []
                sources_list = []

                for i, node_with_score in enumerate(retrieved_nodes):
                    node = node_with_score.node
                    score = node_with_score.score

                    # 提取文档内容
                    content = node.get_content() if hasattr(node, "get_content") else str(node.text)
                    metadata = node.metadata if hasattr(node, "metadata") else {}

                    context_parts.append(f"[文档{i+1}] {content}")

                    # 构建来源信息
                    source_info = {
                        "index": i + 1,
                        "score": float(score) if score else 0.0,
                        "content": content[:200] + "..." if len(content) > 200 else content,
                    }

                    # 添加元数据
                    if metadata:
                        if "filename" in metadata:
                            source_info["filename"] = metadata["filename"]
                        if "document_id" in metadata:
                            source_info["documentId"] = str(metadata["document_id"])
                        if "page" in metadata:
                            source_info["page"] = metadata["page"]

                    sources_list.append(source_info)

                # 构建完整的上下文
                context = "\n\n".join(context_parts)

                # 使用提示词模板格式化消息
                messages = prompt_template.format_messages(
                    context=context,
                    input=request.message,
                    chat_history=chat_history,
                )

                logger.info("调用LLM生成回答")
                response = llm.invoke(messages)

                # 提取回答内容
                if hasattr(response, "content"):
                    answer = response.content
                else:
                    answer = str(response)

                # 保存对话历史(如果启用)
                if request.enableContext and request.outlineId:
                    try:
                        from src.infrastructure.storage.chat_history import (
                            get_chat_history_manager,
                        )
                        history_manager = get_chat_history_manager()
                        # 保存用户消息
                        history_manager.save_message(
                            outline_id=request.outlineId,
                            role="user",
                            content=request.message,
                        )
                        # 保存助手回复
                        history_manager.save_message(
                            outline_id=request.outlineId,
                            role="assistant",
                            content=answer,
                            metadata={"sources_count": len(sources_list)},
                        )
                        logger.debug("保存对话历史: outline_id=%s", request.outlineId)
                    except Exception as e:
                        logger.warning("保存对话历史失败: %s", e)

                logger.info("RAG问答完成: answer_length=%d, sources_count=%d",
                           len(answer), len(sources_list))

                # 返回响应(匹配前端期望格式)
                response_data = {
                    "response": answer,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
                # 如果有来源信息,添加到响应中
                if sources_list:
                    response_data["sources"] = sources_list

                return create_success_response(data=response_data)

            except Exception as e:
                logger.error("RAG检索失败,使用降级方案: %s", e, exc_info=True)
                # 降级到无RAG模式,并记录原因
                logger.warning("RAG检索失败原因: %s,切换到无RAG模式(知识库不可用)", str(e))
                return await _chat_without_rag(
                    request, llm, prompt_template, chat_history
                )
        else:
            # 没有HybridRetriever,使用无RAG模式
            logger.warning("HybridRetriever不可用,切换到无RAG模式(知识库不可用)")
            return await _chat_without_rag(
                request, llm, prompt_template, chat_history
            )

    except Exception as e:
        logger.exception("聊天接口异常: %s", e)
        return create_error_response_from_exception(e)


async def _chat_without_rag(
    request: ChatRequest,
    llm: Any,
    prompt_template: Any,
    chat_history: list[Any],
) -> dict[str, Any]:
    """无RAG模式的聊天(降级方案)

    Args:
        request: 聊天请求
        llm: LLM模型
        prompt_template: 提示词模板(用于保持接口一致性)
        chat_history: 对话历史

    Returns:
        统一响应格式
    """
    from datetime import datetime

    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    try:
        # 创建无RAG模式的提示词模板
        no_rag_prompt_template = ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的文档分析助手,擅长回答关于文档内容的问题.

⚠️ 重要提示:当前无法访问知识库,请基于你的通用知识回答问题.
如果问题涉及特定文档内容,知识库数据或项目相关信息,请明确告知用户:
"抱歉,当前无法访问知识库,无法获取相关文档信息。请确保知识库已正确配置并已建立索引。"

回答要求:
1. 基于通用知识回答(不涉及特定文档内容)
2. 如果问题涉及项目文档或知识库内容,明确说明无法访问
3. 回答要准确,专业,简洁
4. 使用中文回答"""),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])

        # 使用提示词模板格式化消息(无上下文)
        messages = no_rag_prompt_template.format_messages(
            context="",  # 无上下文
            input=request.message,
            chat_history=chat_history,
        )

        response = llm.invoke(messages)

        # 提取回答
        answer = response.content if hasattr(response, "content") else str(response)

        # 添加明确的提醒信息(确保用户知道当前状态)
        warning_prefix = "⚠️ **知识库不可用提醒**:\n\n"
        warning_suffix = "\n\n---\n\n**注意**:当前无法访问知识库,以上回答基于通用知识.如果问题涉及项目文档或知识库内容,请确保:\n1. 知识库已正确配置\n2. 文档已建立索引\n3. HybridRetriever 服务正常运行"

        # 检查回答中是否已包含相关提示
        has_warning = any(keyword in answer for keyword in [
            "无法访问知识库",
            "知识库不可用",
            "无法获取相关文档",
            "需要访问知识库"
        ])

        if not has_warning:
            # 如果回答中没有相关提示,添加明确的提醒
            answer = f"{warning_prefix}{answer}{warning_suffix}"
        else:
            # 如果回答中已有提示,仍然添加后缀提醒
            answer = f"{answer}\n\n---\n\n**系统提示**:当前处于无RAG模式,无法访问知识库."

        # 保存对话历史(如果启用)
        if request.enableContext and request.outlineId:
            try:
                from src.infrastructure.storage.chat_history import (
                    get_chat_history_manager,
                )
                history_manager = get_chat_history_manager()
                # 保存用户消息
                history_manager.save_message(
                    outline_id=request.outlineId,
                    role="user",
                    content=request.message,
                )
                # 保存助手回复
                history_manager.save_message(
                    outline_id=request.outlineId,
                    role="assistant",
                    content=answer,
                    metadata={"mode": "no_rag"},
                )
                logger.debug("保存对话历史: outline_id=%s", request.outlineId)
            except Exception as e:
                logger.warning("保存对话历史失败: %s", e)

        logger.warning("无RAG模式问答完成(知识库不可用)")

        return create_success_response(
            data={
                "response": answer,
                "timestamp": datetime.now(UTC).isoformat(),
                "warning": "知识库不可用,当前使用无RAG模式",  # 添加警告字段
            }
        )
    except Exception as e:
        logger.error("无RAG模式聊天失败: %s", e, exc_info=True)
        return create_error_response(
            "生成回答失败",
            str(e)
        )


# === 工作流状态管理接口 ===


@router.get(
    "/workflow/{workflow_id}/status",
    response_model=dict[str, Any],
    summary="获取工作流状态",
    description="获取指定工作流的当前状态和步骤进度(前端适配接口)",
)
async def get_workflow_status(
    workflow_id: str,
) -> dict[str, Any]:
    """
    获取工作流状态接口(前端适配)

    从数据库获取工作流的状态信息,包括:
    - 当前状态(current_status)
    - 各步骤的完成状态(step1_status, step2_status, step3_status, step4_status)
    - 步骤数据(step_data,用于数据传递)

    Args:
        workflow_id: 工作流ID(通常是outline_id或draft_id)

    Returns:
        统一响应格式:{ success: bool, data: { workflowId, currentStatus, step1Status, ... } }
    """
    try:
        import json
        from datetime import datetime

        # 获取工作流状态适配器
        workflow_adapter = get_workflow_adapter()

        # 从数据库获取工作流状态
        try:
            workflow_statuses = workflow_adapter.list(
                filters={"workflow_id": workflow_id},
                limit=1
            )
        except Exception as e:
            logger.error("从数据库获取工作流状态失败: %s", e, exc_info=True)
            return create_error_response(
                "获取工作流状态失败",
                str(e)
            )

        # 如果不存在,返回默认状态
        if not workflow_statuses:
            default_status = {
                "workflowId": workflow_id,
                "currentStatus": "step1_selected",  # 默认从第一步开始
                "step1Status": "pending",
                "step2Status": "pending",
                "step3Status": "pending",
                "step4Status": "pending",
                "stepData": {},
                "createdAt": datetime.now(UTC).isoformat(),
                "updatedAt": datetime.now(UTC).isoformat(),
            }
            return create_success_response(data=default_status)

        # 获取第一个(应该只有一个)
        status_data = workflow_statuses[0]

        # 解析step_data(JSON字符串)
        step_data = {}
        step_data_str = status_data.get("step_data", "{}")
        if step_data_str:
            try:
                step_data = json.loads(step_data_str) if isinstance(step_data_str, str) else step_data_str
            except (json.JSONDecodeError, TypeError):
                step_data = {}

        # 转换为前端期望的格式
        response_data = {
            "workflowId": status_data.get("workflow_id", workflow_id),
            "currentStatus": status_data.get("current_status", "step1_selected"),
            "step1Status": status_data.get("step1_status", "pending"),
            "step2Status": status_data.get("step2_status", "pending"),
            "step3Status": status_data.get("step3_status", "pending"),
            "step4Status": status_data.get("step4_status", "pending"),
            "stepData": step_data,
            "createdAt": status_data.get("created_at", ""),
            "updatedAt": status_data.get("updated_at", ""),
        }

        logger.info("获取工作流状态成功: workflow_id=%s, current_status=%s", workflow_id, response_data["currentStatus"])

        return create_success_response(data=response_data)

    except Exception as e:
        logger.exception("获取工作流状态异常: %s", e)
        return create_error_response_from_exception(e)


@router.post(
    "/workflow/{workflow_id}/step/{step_number}",
    response_model=dict[str, Any],
    summary="更新工作流步骤状态",
    description="更新指定工作流的指定步骤状态(前端适配接口)",
)
async def update_workflow_step(
    workflow_id: str,
    step_number: int,
    request: UpdateWorkflowStepRequest,
) -> dict[str, Any]:
    """
    更新工作流步骤状态接口(前端适配)

    支持更新4个步骤的状态:
    - step_number=1: 步骤1(行业和数据库选择)
    - step_number=2: 步骤2(大纲优化)
    - step_number=3: 步骤3(来源选择)
    - step_number=4: 步骤4(草稿生成)

    步骤状态:pending(待处理)或 completed(已完成)

    当步骤状态更新为completed时,会自动更新current_status为对应的状态值:
    - step1 completed -> current_status = "step1_selected"
    - step2 completed -> current_status = "step2_optimized"
    - step3 completed -> current_status = "step3_sources_selected"
    - step4 completed -> current_status = "step4_generated"

    Args:
        workflow_id: 工作流ID(通常是outline_id或draft_id)
        step_number: 步骤编号(1-4)
        request: 更新请求,包含status和可选的stepData

    Returns:
        统一响应格式:{ success: bool, message?: str }
    """
    try:
        import json
        from datetime import datetime

        # 验证步骤编号
        if step_number < 1 or step_number > 4:
            return create_error_response(
                "无效的步骤编号",
                f"步骤编号必须在1-4之间,当前值: {step_number}"
            )

        # 验证状态值
        if request.status not in ["pending", "completed"]:
            return create_error_response(
                "无效的状态值",
                f"状态值必须是 'pending' 或 'completed',当前值: {request.status}"
            )

        # 获取工作流状态适配器
        workflow_adapter = get_workflow_adapter()

        # 从数据库获取现有状态(如果存在)
        try:
            existing_statuses = workflow_adapter.list(
                filters={"workflow_id": workflow_id},
                limit=1
            )
        except Exception as e:
            logger.error("从数据库获取工作流状态失败: %s", e, exc_info=True)
            return create_error_response(
                "获取工作流状态失败",
                str(e)
            )

        now = datetime.now(UTC).isoformat()

        if existing_statuses:
            # 更新现有记录
            status_data = existing_statuses[0]
            status_id = status_data["id"]

            # 更新对应步骤的状态
            step_field = f"step{step_number}_status"
            status_data[step_field] = request.status

            # 如果步骤完成,更新current_status
            if request.status == "completed":
                if step_number == 1:
                    status_data["current_status"] = "step1_selected"
                elif step_number == 2:
                    status_data["current_status"] = "step2_optimized"
                elif step_number == 3:
                    status_data["current_status"] = "step3_sources_selected"
                elif step_number == 4:
                    status_data["current_status"] = "step4_generated"

            # 更新step_data(合并现有数据)
            step_data = {}
            step_data_str = status_data.get("step_data", "{}")
            if step_data_str:
                try:
                    step_data = json.loads(step_data_str) if isinstance(step_data_str, str) else step_data_str
                except (json.JSONDecodeError, TypeError):
                    step_data = {}

            # 合并新的step_data
            if request.stepData:
                step_data.update(request.stepData)

            status_data["step_data"] = json.dumps(step_data, ensure_ascii=False)
            status_data["updated_at"] = now

            # 更新数据库
            try:
                workflow_adapter.update(status_id, status_data)
                logger.info("更新工作流步骤状态成功: workflow_id=%s, step=%d, status=%s",
                           workflow_id, step_number, request.status)
            except Exception as e:
                logger.error("更新工作流状态到数据库失败: %s", e, exc_info=True)
                return create_error_response(
                    "更新工作流状态失败",
                    str(e)
                )
        else:
            # 创建新记录
            # 初始化所有步骤状态为pending
            initial_statuses = {
                "step1_status": "pending",
                "step2_status": "pending",
                "step3_status": "pending",
                "step4_status": "pending",
            }

            # 设置当前步骤的状态
            step_field = f"step{step_number}_status"
            initial_statuses[step_field] = request.status

            # 确定current_status
            if request.status == "completed":
                if step_number == 1:
                    current_status = "step1_selected"
                elif step_number == 2:
                    current_status = "step2_optimized"
                elif step_number == 3:
                    current_status = "step3_sources_selected"
                elif step_number == 4:
                    current_status = "step4_generated"
                else:
                    current_status = "step1_selected"
            else:
                current_status = "step1_selected"

            # 准备step_data
            step_data = request.stepData or {}

            new_status = {
                "id": str(uuid.uuid4()),
                "workflow_id": workflow_id,
                "current_status": current_status,
                "step1_status": initial_statuses["step1_status"],
                "step2_status": initial_statuses["step2_status"],
                "step3_status": initial_statuses["step3_status"],
                "step4_status": initial_statuses["step4_status"],
                "step_data": json.dumps(step_data, ensure_ascii=False),
                "created_at": now,
                "updated_at": now,
            }

            # 创建新记录
            try:
                workflow_adapter.create(new_status)
                logger.info("创建工作流状态成功: workflow_id=%s, step=%d, status=%s",
                           workflow_id, step_number, request.status)
            except Exception as e:
                logger.error("创建工作流状态到数据库失败: %s", e, exc_info=True)
                return create_error_response(
                    "创建工作流状态失败",
                    str(e)
                )

        return create_success_response(
            message=f"步骤{step_number}状态已更新为: {request.status}"
        )

    except Exception as e:
        logger.exception("更新工作流步骤状态异常: %s", e)
        return create_error_response_from_exception(e)


# === 用户反馈收集接口 ===


@router.post(
    "/feedback",
    response_model=dict[str, Any],
    summary="提交用户反馈",
    description="收集用户对错误或功能的反馈(前端适配接口)",
)
@handle_errors(operation_name="提交用户反馈", log_level="info")
async def submit_feedback(
    request: UserFeedbackRequest,
) -> dict[str, Any]:
    """
    提交用户反馈接口(前端适配)

    用于收集用户对错误,功能或体验的反馈,帮助改进系统.

    Args:
        request: 用户反馈请求

    Returns:
        统一响应格式:{ success: bool, message?: str }
    """
    # 获取反馈收集器
    feedback_collector = get_feedback_collector()

    # 收集反馈(用户ID暂时使用固定值,后续版本从认证中获取)
    user_id = None  # TODO: 从认证中获取用户ID

    success = feedback_collector.collect_feedback(
        user_id=user_id,
        error_code=request.error_code,
        error_message=request.error_message,
        user_feedback=request.user_feedback,
        metadata=request.metadata,
    )

    if success:
        logger.info(
            "用户反馈收集成功",
            extra={
                "error_code": request.error_code,
                "feedback_length": len(request.user_feedback),
            },
        )
        return create_success_response(
            message="反馈已成功提交,感谢您的反馈!"
        )
    else:
        logger.warning("用户反馈收集失败")
        return create_error_response(
            "提交反馈失败",
            "无法保存反馈,请稍后重试"
        )

