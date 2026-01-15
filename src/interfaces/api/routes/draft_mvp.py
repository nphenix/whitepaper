"""
草稿生成API路由

实现草稿的生成,查询,更新,删除,质量评估等API接口.
使用T232-T234草稿生成Agent, T238A质量评估服务, 调用draft_mvp_schemas定义的Schema.

生成命令: /speckit.implement T239
生成时间: 2025-12-25
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)

from src.application.agents.draft_generator_mvp import (
    create_draft_generator_agent,
)
from src.application.services.draft_quality_assessor import (
    create_draft_quality_assessor,
)
from src.application.services.industry_selection_service import (
    IndustrySelectionService,
)
from src.application.services.outline_optimization_service import (
    OutlineOptimizationService,
)
from src.domain.agent.draft import Draft, DraftStatus
from src.infrastructure.indexing.hybrid_retriever import HybridRetriever
from src.interfaces.api.schemas.draft_mvp_schemas import (
    DeleteResponse,
    DraftDetailResponse,
    DraftGenerateRequest,
    DraftGenerateResponse,
    DraftHTMLExportRequest,
    DraftHTMLExportResponse,
    DraftListResponse,
    DraftQualityAssessmentRequest,
    DraftQualityAssessmentResponse,
    DraftResponse,
    DraftSectionResponse,
    DraftUpdateRequest,
    DraftUpdateResponse,
    ErrorResponse,
    ImprovementSuggestionResponse,
    QualityScoreResponse,
    SortBy,
    SortOrder,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.base_exceptions import ResourceNotFoundError
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/drafts", tags=["草稿管理"])

# 全局服务实例
_outline_optimization_service: OutlineOptimizationService | None = None
_industry_selection_service: IndustrySelectionService | None = None
_llm_service: LLMService | None = None
# 注意：_hybrid_retriever 已移除，现在使用 get_hybrid_retriever() 函数动态创建

# 草稿服务(使用数据库存储)
_draft_service: Any | None = None


def get_outline_optimization_service() -> OutlineOptimizationService:
    """获取大纲优化服务实例

    Returns:
        OutlineOptimizationService: 大纲优化服务实例
    """
    global _outline_optimization_service
    if _outline_optimization_service is None:
        _outline_optimization_service = OutlineOptimizationService()
    return _outline_optimization_service


def get_industry_selection_service() -> IndustrySelectionService:
    """获取行业选择服务实例

    Returns:
        IndustrySelectionService: 行业选择服务实例
    """
    global _industry_selection_service
    if _industry_selection_service is None:
        _industry_selection_service = IndustrySelectionService()
    return _industry_selection_service


def get_llm_service() -> LLMService:
    """获取LLM服务实例

    Returns:
        LLMService: LLM服务实例
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service


def get_hybrid_retriever(knowledge_base_id: str | list[str] | None = None) -> HybridRetriever:
    """获取混合检索引擎实例

    与 frontend_adapter.py 中的实现保持一致，支持 knowledge_base_id 参数。

    Args:
        knowledge_base_id: 知识库ID（可选）。支持以下形式：
                          - str: 单个知识库ID
                          - list[str]: 多个知识库ID，将创建 MultiKBHybridRetriever
                          - None: 使用默认配置（向后兼容）

    Returns:
        HybridRetriever 或 MultiKBHybridRetriever: 混合检索引擎实例

    Raises:
        ImportError: 如果LlamaIndex未安装
        HybridRetrieverError: 如果初始化失败（如配置错误、索引构建器创建失败等）
        ValueError: 如果参数无效

    Note:
        - 如果提供了单个 knowledge_base_id：
          - 向量索引collection: kb_{knowledge_base_id}_vector
          - BM25索引文件: 优先使用 ./data/bm25_index/kb_kb_*.json；
            ./data/bm25_index/kb_{knowledge_base_id}.pkl 属于历史/废弃命名，仅作为兜底兼容。
          - 元数据索引表: kb_{knowledge_base_id}_metadata
        - 如果提供了多个 knowledge_base_id 列表：
          - 为每个ID创建独立的 HybridRetriever
          - 使用 MultiKBHybridRetriever 包装，查询时并行检索并融合结果
        - 如果不提供 knowledge_base_id（向后兼容），使用默认配置
        - 如果初始化失败，会抛出异常而不是返回None，确保问题能被及时发现
    """
    import json
    import re
    from pathlib import Path

    from src.infrastructure.indexing.bm25_index import BM25IndexBuilder
    from src.infrastructure.indexing.hybrid_retriever import HybridRetriever, HybridRetrieverError
    from src.infrastructure.indexing.metadata_index import MetadataIndexBuilder
    from src.infrastructure.indexing.multi_kb_retriever import MultiKBHybridRetriever
    from src.infrastructure.indexing.vector_index import VectorIndexBuilder
    from src.infrastructure.storage.chroma.connection import get_chroma_connection_manager
    from src.infrastructure.storage.sqlite.connection import get_sqlite_connection_manager
    from src.shared.config.llm_service import get_llm_service

    # 只接受形如 kb_<hex> 的知识库ID；其它（尤其是 UUID 带 "-"）一律视为“未指定”，走默认自动发现。
    # 背景：outline.database_ids 是业务层“行业数据库/数据集”UUID，不等同于知识库ID；若误传会导致
    # metadata 表名包含 "-" 从而触发 SQLite "near '-': syntax error"。
    _KB_ID_RE = re.compile(r"^kb_[0-9a-f]{16,}$", re.IGNORECASE)

    def _is_valid_kb_id(value: str) -> bool:
        return bool(value) and bool(_KB_ID_RE.match(value.strip()))

    def _find_latest_legacy_bm25_index_path() -> str | None:
        """兼容旧索引命名：

        兜底时从 ./data/bm25_index/kb_kb_*.json 选择“documents 数最多”的一个（更可能是多文档合并索引），
        再用 mtime 破同；返回对应 .pkl 路径。
        """
        try:
            bm25_dir = Path("./data/bm25_index")
            if not bm25_dir.exists():
                return None
            candidates = list(bm25_dir.glob("kb_kb_*.json"))
            if not candidates:
                return None

            scored: list[tuple[int, float, Path]] = []
            for jf in candidates:
                doc_count = 0
                try:
                    data = json.loads(jf.read_text(encoding="utf-8"))
                    docs = data.get("documents") or []
                    if isinstance(docs, list):
                        doc_count = len(docs)
                except Exception:
                    doc_count = 0
                try:
                    mtime = float(jf.stat().st_mtime)
                except Exception:
                    mtime = 0.0
                scored.append((doc_count, mtime, jf))

            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            best = scored[0][2]
            return str(best).replace(".json", ".pkl")
        except Exception:
            return None

    def _find_bm25_index_for_kb(kb_id: str) -> str:
        """为指定知识库查找 BM25 索引文件"""
        # 优先使用新格式 kb_{kb_id}.json
        pkl_path = f"./data/bm25_index/kb_{kb_id}.pkl"
        json_path = pkl_path.replace('.pkl', '.json')

        if Path(json_path).exists():
            logger.debug("找到新格式 BM25 索引: %s", json_path)
            return pkl_path  # 返回 pkl 路径（BM25IndexBuilder 会自动查找 json）

        if Path(pkl_path).exists():
            logger.debug("找到旧格式 BM25 索引: %s", pkl_path)
            return pkl_path

        # 回退到最新的旧索引
        legacy_path = _find_latest_legacy_bm25_index_path()
        if legacy_path:
            logger.info("知识库 %s 未找到专用索引，回退到: %s", kb_id, legacy_path)
            return legacy_path

        logger.warning("知识库 %s 没有任何 BM25 索引可用", kb_id)
        return pkl_path  # 返回一个不存在的路径，让 BM25IndexBuilder 处理

    # 处理 knowledge_base_id 参数
    if knowledge_base_id is None:
        kb_ids: list[str] = []
        single_id: str | None = None
    elif isinstance(knowledge_base_id, str):
        if not _is_valid_kb_id(knowledge_base_id):
            logger.warning(
                "忽略非法 knowledge_base_id（将走默认自动发现）: %s",
                knowledge_base_id,
            )
            kb_ids = []
            single_id = None
            knowledge_base_id = None
        else:
            kb_ids = []
            single_id = knowledge_base_id.strip()
    else:
        # 列表形式
        raw_ids = knowledge_base_id
        valid_ids = [x.strip() for x in raw_ids if isinstance(x, str) and _is_valid_kb_id(x)]
        invalid_ids = [x for x in raw_ids if not (isinstance(x, str) and _is_valid_kb_id(x))]
        if invalid_ids:
            logger.warning(
                "忽略非法 knowledge_base_id 列表项（将仅使用合法项/或走默认自动发现）: %s",
                invalid_ids,
            )
        kb_ids = valid_ids
        single_id = kb_ids[0] if len(kb_ids) == 1 else None
        if not kb_ids:
            knowledge_base_id = None

    # 多个知识库：创建 MultiKBHybridRetriever
    if len(kb_ids) > 1:
        logger.info("检测到多个知识库，创建 MultiKBHybridRetriever: kb_count=%d", len(kb_ids))

        retrievers: list[HybridRetriever] = []
        failed_kbs: list[str] = []

        for kb_id in kb_ids:
            try:
                logger.debug("为知识库 %s 创建 HybridRetriever", kb_id)
                retriever = get_hybrid_retriever(kb_id)
                retrievers.append(retriever)
            except Exception as e:
                logger.warning("知识库 %s 的 HybridRetriever 创建失败: %s", kb_id, e)
                failed_kbs.append(kb_id)

        if not retrievers:
            error_msg = f"所有知识库 HybridRetriever 创建失败: {failed_kbs}"
            logger.error(error_msg)
            # 回退到默认配置
            logger.warning("回退到默认配置")
            return get_hybrid_retriever(None)

        if failed_kbs:
            logger.warning("部分知识库创建失败: %s", failed_kbs)

        return MultiKBHybridRetriever(retrievers=retrievers)

    # 默认兜底：如果未提供 knowledge_base_id，且没有显式 kb_ids，则尝试自动发现 Chroma 中已有 kb_*_vector 集合
    # 背景：常见离线/批处理流程会生成多个 kb_kb_xxx_*（每个 KB 对应一个 PDF），但 outline_sources 未维护。
    # 此时单库检索会“永远只有一个来源文件”。这里用 MultiKB 兜底恢复多来源召回。
    if knowledge_base_id is None and not kb_ids:
        try:
            cm = get_chroma_connection_manager()
            collections = cm.list_collections()
            names: list[str] = []
            for c in collections:
                n = getattr(c, "name", None)
                if isinstance(n, str) and n:
                    names.append(n)
                else:
                    s = str(c)
                    if s:
                        names.append(s)

            discovered: list[str] = []
            for name in names:
                if name == "whitepaper_documents":
                    continue
                if isinstance(name, str) and name.startswith("kb_") and name.endswith("_vector"):
                    kb_id = name[len("kb_") : -len("_vector")]
                    if kb_id:
                        discovered.append(kb_id)

            seen: set[str] = set()
            discovered = [x for x in discovered if not (x in seen or seen.add(x))]
            if discovered:
                logger.info("默认检索：自动发现可用知识库: kb_count=%d", len(discovered))
                if len(discovered) == 1:
                    return get_hybrid_retriever(discovered[0])
                return get_hybrid_retriever(discovered)
        except Exception:
            pass

    # 单个知识库或默认配置
    if knowledge_base_id:
        # 使用指定的 knowledge_base_id 创建索引构建器
        # 注意：knowledge_base_id 已经是 kb_doc_xxx 格式
        # 使用与 knowledge_base_helper.py 中完全一致的命名规则
        vector_collection_name = f"kb_{single_id}_vector"
        bm25_index_path = _find_bm25_index_for_kb(single_id)
        metadata_table_name = f"kb_{single_id}_metadata"

        logger.info(
            "使用知识库ID创建索引构建器: kb_id=%s, vector_collection=%s, bm25_path=%s, metadata_table=%s",
            single_id,
            vector_collection_name,
            bm25_index_path,
            metadata_table_name
        )

        # 确保BM25索引目录存在
        bm25_dir = Path(bm25_index_path).parent
        bm25_dir.mkdir(parents=True, exist_ok=True)

        # 检查BM25索引文件是否存在
        bm25_json_path = bm25_index_path.replace('.pkl', '.json')
        bm25_pkl_exists = Path(bm25_index_path).exists()
        bm25_json_exists = Path(bm25_json_path).exists()
        logger.debug(
            "BM25索引文件检查: pkl_path=%s (存在=%s), json_path=%s (存在=%s)",
            bm25_index_path,
            bm25_pkl_exists,
            bm25_json_path,
            bm25_json_exists
        )

        try:
            vector_builder = VectorIndexBuilder(
                collection_name=vector_collection_name,
                connection_manager=get_chroma_connection_manager(),
            )
            bm25_builder = BM25IndexBuilder(index_path=bm25_index_path)
            # 初始化后检查BM25索引状态
            try:
                bm25_stats = bm25_builder.get_stats()
                logger.info(
                    "BM25索引构建器初始化完成: is_built=%s, documents_count=%d, index_path=%s",
                    bm25_stats.get("is_built", False),
                    bm25_stats.get("documents_count", 0),
                    bm25_stats.get("index_path", "unknown")
                )
            except Exception as e:
                logger.warning("获取BM25索引状态失败: %s", e)
            metadata_builder = MetadataIndexBuilder(
                table_name=metadata_table_name,
                connection_manager=get_sqlite_connection_manager(),
            )
        except Exception as e:
            error_msg = (
                f"无法创建索引构建器（knowledge_base_id={single_id}）: {e}. "
                "请检查知识库是否已正确创建，以及索引配置是否正确。"
            )
            logger.error(error_msg, exc_info=True)
            raise HybridRetrieverError(error_msg) from e
    else:
        # 向后兼容：使用默认配置
        logger.info(
            "未提供 knowledge_base_id，使用默认配置创建索引构建器（whitepaper_documents collection）。"
        )
        try:
            vector_builder = VectorIndexBuilder()
            # 默认配置：优先选择已存在的旧版本 BM25 索引（kb_kb_*.json），避免退回 default.pkl 导致"未构建"。
            default_bm25_path = _find_latest_legacy_bm25_index_path() or "./data/bm25_index/default.pkl"
            Path(default_bm25_path).parent.mkdir(parents=True, exist_ok=True)
            bm25_builder = BM25IndexBuilder(index_path=default_bm25_path)
            # 检查默认BM25索引状态
            try:
                bm25_stats = bm25_builder.get_stats()
                logger.info(
                    "默认BM25索引状态: is_built=%s, documents_count=%d, index_path=%s",
                    bm25_stats.get("is_built", False),
                    bm25_stats.get("documents_count", 0),
                    bm25_stats.get("index_path", "unknown")
                )
            except Exception as e:
                logger.debug("获取默认BM25索引状态失败: %s", e)
            metadata_builder = MetadataIndexBuilder()
        except Exception as e:
            error_msg = (
                f"无法创建默认索引构建器: {e}. "
                "请检查系统配置和依赖是否正确安装。"
            )
            logger.error(error_msg, exc_info=True)
            raise HybridRetrieverError(error_msg) from e

    try:
        retriever = HybridRetriever(
            vector_index_builder=vector_builder,
            bm25_index_builder=bm25_builder,
            metadata_index_builder=metadata_builder,
            llm_service=get_llm_service(),
        )
        logger.info("HybridRetriever 初始化成功: kb_id=%s", single_id or "默认")
        return retriever
    except HybridRetrieverError:
        # HybridRetriever自己抛出的异常，直接向上抛出
        raise
    except Exception as e:
        error_msg = (
            f"HybridRetriever 初始化失败（knowledge_base_id={single_id or '默认'}）: {e}. "
            "请检查索引构建器配置和依赖是否正确。"
        )
        logger.error(error_msg, exc_info=True)
        raise HybridRetrieverError(error_msg) from e


def get_draft_service():
    """获取草稿服务实例

    Returns:
        DraftService: 草稿服务实例
    """
    global _draft_service
    if _draft_service is None:
        from src.application.services.draft_service import DraftService
        _draft_service = DraftService()
    return _draft_service


def _handle_route_exception(e: Exception, operation: str) -> HTTPException:
    """处理路由异常,根据异常类型返回适当的HTTP状态码

    Args:
        e: 异常对象
        operation: 操作名称,用于日志

    Returns:
        HTTPException: HTTP异常对象
    """
    if isinstance(e, ResourceNotFoundError):
        logger.warning("%s: %s", operation, e)
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    else:
        logger.exception("%s异常: %s", operation, e)
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{operation}失败: {e}",
        )


def _convert_draft_to_response(draft: Draft) -> DraftResponse:
    """将草稿对象转换为响应格式

    Args:
        draft: 草稿对象

    Returns:
        DraftResponse: 草稿响应对象
    """
    sections = [
        DraftSectionResponse(
            id=section.id,
            parent_id=section.parent_id,
            section_type=section.section_type,
            level=section.level,
            title=section.title,
            content=section.content,
            order=section.order,
            source_references=section.source_references,
            metadata=section.metadata,
        )
        for section in draft.sections
    ]

    return DraftResponse(
        id=draft.id,
        title=draft.title,
        description=draft.description,
        outline_id=draft.outline_id,
        industry_id=draft.industry_id,
        database_ids=draft.database_ids,
        status=draft.status,
        sections=sections,
        current_version=draft.current_version,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        metadata=draft.metadata,
    )


@router.post(
    "/generate",
    response_model=DraftGenerateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "大纲或行业不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="生成草稿",
    description="基于优化大纲生成草稿内容,使用DraftGeneratorAgent进行生成",
)
async def generate_draft_endpoint(
    request: DraftGenerateRequest,
    outline_service: OutlineOptimizationService = Depends(
        get_outline_optimization_service
    ),
    industry_service: IndustrySelectionService = Depends(
        get_industry_selection_service
    ),
    llm_service: LLMService = Depends(get_llm_service),
) -> DraftGenerateResponse:
    """
    生成草稿接口

    Args:
        request: 生成草稿请求
        outline_service: 大纲优化服务
        industry_service: 行业选择服务
        llm_service: LLM服务

    Returns:
        DraftGenerateResponse: 生成结果

    Raises:
        HTTPException: 生成失败时抛出
    """
    try:
        # 1. 验证优化大纲是否存在
        optimized_outline = outline_service.get_optimized_outline_by_id(
            str(request.optimized_outline_id)
        )
        if not optimized_outline:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"优化大纲不存在: {request.optimized_outline_id}",
            )

        # 2. 验证行业是否存在
        industry = industry_service.get_industry_by_id(str(request.industry_id))
        if not industry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"行业不存在: {request.industry_id}",
            )

        # 3. 获取行业名称
        industry_name = industry.name

        # 4. 获取数据库名称列表
        database_names = []
        if request.database_ids:
            for db_id in request.database_ids:
                database = industry_service.get_database_by_id(str(db_id))
                if database:
                    database_names.append(database.name)

        # 5. 获取知识库ID（从原始大纲ID）
        knowledge_base_id: str | list[str] | None = None
        try:
            # 从优化大纲中获取原始大纲ID
            original_outline_id = str(optimized_outline.original_outline_id)
            # 尝试从原始大纲ID获取知识库ID（支持多 uploaded_file）
            from src.interfaces.api.routes.frontend_adapter.chat_routes import (
                _get_knowledge_base_ids_from_outline_id,
            )
            kb_ids = _get_knowledge_base_ids_from_outline_id(original_outline_id)
            if kb_ids:
                knowledge_base_id = kb_ids if len(kb_ids) > 1 else kb_ids[0]
                logger.info(
                    "从原始大纲ID=%s获取到knowledge_base_id=%s",
                    original_outline_id,
                    knowledge_base_id,
                )
            else:
                logger.info("未找到原始大纲ID=%s关联的知识库，将使用默认知识库配置", original_outline_id)
        except Exception as e:
            logger.warning("获取知识库ID失败，将使用默认配置: %s", e)

        # 6. 创建草稿生成Agent
        hybrid_retriever = get_hybrid_retriever(knowledge_base_id=knowledge_base_id)
        agent = create_draft_generator_agent(
            llm_service=llm_service,
            report_type=request.report_type,
            language=request.language,
            style=request.style,
            hybrid_retriever=hybrid_retriever,
        )

        # 7. 生成草稿
        draft = agent.generate_draft(
            optimized_outline=optimized_outline,
            industry_name=industry_name,
            database_names=database_names,
            report_type=request.report_type,
        )

        # 8. 保存草稿到数据库
        # 使用固定的测试用户ID(后续版本将从认证中获取)
        test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        draft_service = get_draft_service()
        draft_service.save_draft(draft, test_user_id)

        # 9. 转换为响应格式
        draft_response = _convert_draft_to_response(draft)

        logger.info("草稿生成成功: %s (ID: %s)", draft.title, draft.id)

        return DraftGenerateResponse(
            draft=draft_response,
            draft_id=str(draft.id),
            title=draft.title,
            status=draft.status.value if hasattr(draft.status, "value") else str(draft.status),
            total_sections=len(draft.sections),
            created_at=draft.created_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("生成草稿异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成草稿失败: {e}",
        )


@router.get(
    "/{draft_id}",
    response_model=DraftDetailResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="获取草稿详情",
    description="根据草稿ID获取草稿详细信息",
)
async def get_draft_detail_endpoint(
    draft_id: str,
) -> DraftDetailResponse:
    """
    获取草稿详情接口

    Args:
        draft_id: 草稿ID

    Returns:
        DraftDetailResponse: 草稿详情

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        # 从数据库获取草稿
        draft_service = get_draft_service()
        draft = draft_service.get_draft(draft_id)

        # 转换为响应格式
        draft_response = _convert_draft_to_response(draft)

        # 获取统计信息
        statistics = draft.get_statistics()

        return DraftDetailResponse(
            draft=draft_response,
            statistics=statistics,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取草稿详情异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取草稿详情失败: {e}",
        )


@router.get(
    "",
    response_model=DraftListResponse,
    responses={
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="获取草稿列表",
    description="获取草稿列表,支持筛选和分页",
)
async def list_drafts_endpoint(
    outline_id: str | None = Query(None, description="大纲ID(筛选)"),
    industry_id: str | None = Query(None, description="行业ID(筛选)"),
    status_filter: str | None = Query(None, alias="status", description="状态(筛选)"),
    page: int = Query(1, ge=1, description="页码(从1开始)"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    sort_by: SortBy = Query(SortBy.CREATED_AT, description="排序字段"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="排序方向"),
) -> DraftListResponse:
    """
    获取草稿列表接口

    Args:
        outline_id: 大纲ID(筛选)
        industry_id: 行业ID(筛选)
        status_filter: 状态(筛选)
        page: 页码
        page_size: 每页数量
        sort_by: 排序字段
        sort_order: 排序方向

    Returns:
        DraftListResponse: 草稿列表
    """
    try:
        # 从数据库获取草稿列表
        draft_service = get_draft_service()

        # 构建过滤条件
        outline_uuid = uuid.UUID(outline_id) if outline_id else None
        industry_uuid = uuid.UUID(industry_id) if industry_id else None
        status_enum = DraftStatus(status_filter) if status_filter else None

        filtered_drafts = draft_service.list_drafts(
            outline_id=outline_uuid,
            industry_id=industry_uuid,
            status=status_enum,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        # 排序
        reverse = sort_order == SortOrder.DESC
        if sort_by == SortBy.TITLE:
            filtered_drafts.sort(key=lambda d: d.title, reverse=reverse)
        elif sort_by == SortBy.CREATED_AT:
            filtered_drafts.sort(key=lambda d: d.created_at, reverse=reverse)
        elif sort_by == SortBy.UPDATED_AT:
            filtered_drafts.sort(key=lambda d: d.updated_at, reverse=reverse)
        elif sort_by == SortBy.STATUS:
            filtered_drafts.sort(
                key=lambda d: d.status.value if hasattr(d.status, "value") else str(d.status),
                reverse=reverse,
            )

        # 分页
        total = len(filtered_drafts)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_drafts = filtered_drafts[start:end]

        # 转换为响应格式
        draft_responses = [
            _convert_draft_to_response(draft) for draft in paginated_drafts
        ]

        total_pages = (total + page_size - 1) // page_size

        return DraftListResponse(
            drafts=draft_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.exception("获取草稿列表异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取草稿列表失败: {e}",
        )


@router.put(
    "/{draft_id}",
    response_model=DraftUpdateResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="更新草稿",
    description="更新草稿的基本信息(标题,描述,状态等)",
)
async def update_draft_endpoint(
    draft_id: str,
    request: DraftUpdateRequest,
) -> DraftUpdateResponse:
    """
    更新草稿接口

    Args:
        draft_id: 草稿ID
        request: 更新请求

    Returns:
        DraftUpdateResponse: 更新结果

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        # 从数据库获取草稿
        draft_service = get_draft_service()
        draft = draft_service.get_draft(draft_id)

        # 更新字段
        if request.title is not None:
            draft.title = request.title
        if request.description is not None:
            draft.description = request.description
        if request.status is not None:
            draft.update_status(request.status)

        # 保存更新到数据库
        # 使用固定的测试用户ID(后续版本将从认证中获取)
        test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        draft_service = get_draft_service()
        draft_service.save_draft(draft, test_user_id)

        # 转换为响应格式
        draft_response = _convert_draft_to_response(draft)

        logger.info("草稿更新成功: %s (ID: %s)", draft.title, draft.id)

        return DraftUpdateResponse(
            draft=draft_response,
            updated_at=draft.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新草稿异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新草稿失败: {e}",
        )


@router.delete(
    "/{draft_id}",
    response_model=DeleteResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="删除草稿",
    description="根据草稿ID删除草稿",
)
async def delete_draft_endpoint(
    draft_id: str,
) -> DeleteResponse:
    """
    删除草稿接口

    Args:
        draft_id: 草稿ID

    Returns:
        DeleteResponse: 删除结果

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        # 从数据库获取草稿
        draft_service = get_draft_service()
        draft = draft_service.get_draft(draft_id)

        # 删除草稿
        draft_service = get_draft_service()
        draft_service.delete_draft(draft_id)

        logger.info("草稿删除成功: %s (ID: %s)", draft.title, draft_id)

        return DeleteResponse(
            success=True,
            message="草稿删除成功",
            draft_id=draft_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除草稿异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除草稿失败: {e}",
        )


@router.post(
    "/{draft_id}/assess-quality",
    response_model=DraftQualityAssessmentResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="评估草稿质量",
    description="评估草稿的结构完整度,数据引用完整性,逻辑一致性等",
)
async def assess_draft_quality_endpoint(
    draft_id: str,
    request: DraftQualityAssessmentRequest,
    llm_service: LLMService = Depends(get_llm_service),
) -> DraftQualityAssessmentResponse:
    """
    评估草稿质量接口

    Args:
        draft_id: 草稿ID
        request: 评估请求
        llm_service: LLM服务

    Returns:
        DraftQualityAssessmentResponse: 评估结果

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        # 从数据库获取草稿
        draft_service = get_draft_service()
        draft = draft_service.get_draft(draft_id)

        # 创建质量评估服务
        assessor = create_draft_quality_assessor(llm_service=llm_service)

        # 评估草稿质量
        # 注意:当前版本暂时不传递source_references,后续版本将实现
        result = assessor.assess_quality(
            draft=draft,
            source_references=None,
            use_llm=request.use_llm,
        )

        # 转换为响应格式
        dimension_scores = [
            QualityScoreResponse(
                dimension=score.dimension,
                score=score.score,
                description=score.description,
            )
            for score in result.dimension_scores
        ]

        improvement_suggestions = [
            ImprovementSuggestionResponse(
                dimension=suggestion.dimension,
                priority=suggestion.priority,
                suggestion=suggestion.suggestion,
                affected_sections=suggestion.affected_sections,
            )
            for suggestion in result.improvement_suggestions
        ]

        logger.info("草稿质量评估完成: %s (ID: %s, 评分: %.2f)", draft.title, draft_id, result.overall_score)

        return DraftQualityAssessmentResponse(
            overall_score=result.overall_score,
            dimension_scores=dimension_scores,
            improvement_suggestions=improvement_suggestions,
            summary=result.summary,
            details=result.details,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("评估草稿质量异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"评估草稿质量失败: {e}",
        )


@router.post(
    "/export-html",
    response_model=DraftHTMLExportResponse,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="导出草稿为HTML",
    description="将草稿导出为HTML文件（包含图表渲染和附录数据）",
)
async def export_draft_html_endpoint(
    request: DraftHTMLExportRequest,
) -> DraftHTMLExportResponse:
    """
    导出草稿为HTML接口

    Args:
        request: HTML导出请求

    Returns:
        DraftHTMLExportResponse: 导出结果

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        from src.application.services.html_export_service import HTMLExportService

        # 创建HTML导出服务
        export_service = HTMLExportService()

        # 导出草稿为HTML
        file_path = export_service.export_draft_to_html(
            draft_id=str(request.draft_id) if request.draft_id else None,
            outline_id=str(request.outline_id) if request.outline_id else None,
            output_dir=request.output_dir,
            filename=request.filename,
            datajson_dir=request.datajson_dir,
            include_appendix=request.include_appendix,
        )

        # 获取草稿信息
        draft_service = export_service.draft_service
        draft_id_str = None
        outline_id_str = None
        if request.draft_id:
            draft = draft_service.get_draft(request.draft_id)
            draft_id_str = str(draft.id)
            outline_id_str = str(draft.outline_id)
        elif request.outline_id:
            drafts = draft_service.list_drafts(outline_id=request.outline_id)
            if drafts:
                draft = drafts[0]
                draft_id_str = str(draft.id)
                outline_id_str = str(draft.outline_id)

        logger.info("草稿HTML导出成功: file_path=%s", file_path)

        return DraftHTMLExportResponse(
            success=True,
            message="HTML导出成功",
            draft_id=draft_id_str,
            outline_id=outline_id_str,
            file_path=str(file_path),
            file_url=None,  # 后续版本可以支持文件URL
        )

    except ResourceNotFoundError as e:
        logger.warning("草稿不存在: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"草稿不存在: {e}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("导出草稿为HTML异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"导出草稿为HTML失败: {e}",
        )


@router.get(
    "/{draft_id}/html",
    response_class=Response,
    responses={
        404: {"model": ErrorResponse, "description": "草稿不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="获取草稿HTML内容",
    description="获取草稿的HTML内容（不写入文件，直接返回HTML字符串）",
)
async def get_draft_html_content_endpoint(
    draft_id: str,
    outline_id: str | None = Query(None, description="大纲ID（如果draft_id不存在时使用）"),
    datajson_dir: str | None = Query(None, description="datajson目录路径（可选）"),
    include_appendix: bool = Query(True, description="是否包含附录数据表格"),
) -> Response:
    """
    获取草稿HTML内容接口

    Args:
        draft_id: 草稿ID
        outline_id: 大纲ID（可选，如果draft_id不存在时使用）
        datajson_dir: datajson目录路径（可选）
        include_appendix: 是否包含附录数据表格

    Returns:
        Response: HTML内容响应

    Raises:
        HTTPException: 草稿不存在时抛出
    """
    try:
        from src.application.services.html_export_service import HTMLExportService

        # 创建HTML导出服务
        export_service = HTMLExportService()

        # 生成HTML内容
        html_content = export_service.generate_html_content(
            draft_id=draft_id if draft_id else None,
            outline_id=outline_id,
            datajson_dir=datajson_dir,
            include_appendix=include_appendix,
        )

        logger.info("获取草稿HTML内容成功: draft_id=%s", draft_id)

        return Response(content=html_content, media_type="text/html; charset=utf-8")

    except ResourceNotFoundError as e:
        logger.warning("草稿不存在: %s", e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"草稿不存在: {e}",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取草稿HTML内容异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取草稿HTML内容失败: {e}",
        )

