"""
知识库管理API路由

实现知识库的创建、更新、删除、查询等API接口。
使用T050知识库服务，调用knowledge_base_schemas定义的Schema。

生成命令: /speckit.implement T055
生成时间: 2025-12-21
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from src.application.services.knowledge_base_service import (
    KnowledgeBaseService,
    KnowledgeBaseServiceError,
    KnowledgeBaseStatus,
)
from src.infrastructure.indexing.hybrid_retriever import (
    FusionStrategy,
    QueryType,
)
from src.infrastructure.indexing.structured_retrieval import (
    DocumentLevel,
    SortOrder,
    StructuredQuery,
)
from src.interfaces.api.schemas.knowledge_base_schemas import (
    CreateKnowledgeBaseRequest,
    CreateKnowledgeBaseResponse,
    DeleteKnowledgeBaseResponse,
    ErrorResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseStatusResponse,
    QueryKnowledgeBaseRequest,
    QueryKnowledgeBaseResponse,
    QueryResult,
    UpdateKnowledgeBaseRequest,
    UpdateKnowledgeBaseResponse,
    create_error_response,
    create_success_response,
)
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/knowledge-base", tags=["知识库"])

# 全局知识库服务实例缓存
_knowledge_base_services: Dict[str, KnowledgeBaseService] = {}


def get_knowledge_base_service(knowledge_base_id: str) -> KnowledgeBaseService:
    """获取知识库服务实例
    
    Args:
        knowledge_base_id: 知识库ID
        
    Returns:
        KnowledgeBaseService: 知识库服务实例
        
    Raises:
        HTTPException: 如果知识库不存在
    """
    if knowledge_base_id not in _knowledge_base_services:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"知识库不存在: {knowledge_base_id}",
        )
    return _knowledge_base_services[knowledge_base_id]


@router.post(
    "/create",
    response_model=CreateKnowledgeBaseResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="创建知识库",
    description="从预处理结果目录创建知识库，执行完整的解析→索引→检索流程",
)
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
) -> CreateKnowledgeBaseResponse:
    """
    创建知识库接口
    
    Args:
        request: 创建知识库请求
        
    Returns:
        CreateKnowledgeBaseResponse: 创建结果
        
    Raises:
        HTTPException: 创建失败时抛出
    """
    try:
        # 验证目录是否存在
        for directory in request.directories:
            if not Path(directory).exists():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"目录不存在: {directory}",
                )
        
        # 生成知识库ID
        knowledge_base_id = str(uuid.uuid4())
        
        # 创建知识库服务实例
        from src.infrastructure.indexing.document_chunking import ChunkingConfig
        from src.infrastructure.indexing.hybrid_retriever import HybridRetrieverConfig
        
        chunking_config = ChunkingConfig(
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap,
            split_by_section=request.split_by_section,
            split_by_paragraph=request.split_by_paragraph,
        )
        
        hybrid_retriever_config = HybridRetrieverConfig(
            enable_vector=request.enable_vector,
            enable_bm25=request.enable_bm25,
            enable_metadata=request.enable_metadata,
            enable_graph=request.enable_graph,
            fusion_strategy=FusionStrategy.RRF,
            default_top_k=10,
        )
        
        service = KnowledgeBaseService(
            knowledge_base_id=knowledge_base_id,
            vector_collection_name=request.vector_collection_name,
            bm25_index_path=request.bm25_index_path,
            enable_vector=request.enable_vector,
            enable_bm25=request.enable_bm25,
            enable_metadata=request.enable_metadata,
            enable_graph=request.enable_graph,
            chunking_config=chunking_config,
            hybrid_retriever_config=hybrid_retriever_config,
        )
        
        # 缓存服务实例
        _knowledge_base_services[knowledge_base_id] = service
        
        # 创建知识库
        result = service.create_knowledge_base(
            name=request.name,
            directories=request.directories,
            description=request.description,
            show_progress=request.show_progress,
        )
        
        # 获取状态信息
        status_info = service.get_status()
        
        # 构建配置信息
        from src.interfaces.api.schemas.knowledge_base_schemas import (
            ChunkingConfig as SchemaChunkingConfig,
            HybridRetrieverConfig as SchemaHybridRetrieverConfig,
            IndexStatistics,
            KnowledgeBaseConfig,
        )
        
        chunking_config_schema = SchemaChunkingConfig(
            chunk_size=status_info["config"]["chunking"]["chunk_size"],
            chunk_overlap=status_info["config"]["chunking"]["chunk_overlap"],
            split_by_section=status_info["config"]["chunking"]["split_by_section"],
            split_by_paragraph=status_info["config"]["chunking"]["split_by_paragraph"],
        )
        
        hybrid_retriever_config_schema = SchemaHybridRetrieverConfig(
            enable_vector=status_info["config"]["hybrid_retriever"]["enable_vector"],
            enable_bm25=status_info["config"]["hybrid_retriever"]["enable_bm25"],
            enable_metadata=status_info["config"]["hybrid_retriever"]["enable_metadata"],
            enable_graph=status_info["config"]["hybrid_retriever"]["enable_graph"],
            fusion_strategy=FusionStrategy(status_info["config"]["hybrid_retriever"]["fusion_strategy"]),
            default_top_k=status_info["config"]["hybrid_retriever"]["default_top_k"],
        )
        
        config_schema = KnowledgeBaseConfig(
            chunking=chunking_config_schema,
            hybrid_retriever=hybrid_retriever_config_schema,
        )
        
        indexes_schema = IndexStatistics(
            vector=status_info["indexes"]["vector"],
            bm25=status_info["indexes"]["bm25"],
            metadata=status_info["indexes"]["metadata"],
        )
        
        # 构建知识库响应
        kb_response = KnowledgeBaseResponse(
            knowledge_base_id=result["knowledge_base_id"],
            name=result["name"],
            description=result.get("description"),
            status=KnowledgeBaseStatus(result["status"]),
            created_at=result["created_at"],
            updated_at=result.get("updated_at"),
            config=config_schema,
            indexes=indexes_schema,
        )
        
        return CreateKnowledgeBaseResponse(
            knowledge_base=kb_response,
            statistics=result["statistics"],
            message="知识库创建成功",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("创建知识库异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="创建知识库失败",
        ) from e


@router.put(
    "/{knowledge_base_id}/update",
    response_model=UpdateKnowledgeBaseResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "知识库不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="更新知识库",
    description="添加新的文档或目录到现有知识库",
)
async def update_knowledge_base(
    knowledge_base_id: str,
    request: UpdateKnowledgeBaseRequest,
) -> UpdateKnowledgeBaseResponse:
    """
    更新知识库接口
    
    Args:
        knowledge_base_id: 知识库ID
        request: 更新知识库请求
        
    Returns:
        UpdateKnowledgeBaseResponse: 更新结果
        
    Raises:
        HTTPException: 更新失败时抛出
    """
    try:
        # 获取知识库服务实例
        service = get_knowledge_base_service(knowledge_base_id)
        
        # 验证目录是否存在
        if request.directories:
            for directory in request.directories:
                if not Path(directory).exists():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"目录不存在: {directory}",
                    )
        
        # 更新知识库
        result = service.update_knowledge_base(
            directories=request.directories,
            show_progress=request.show_progress,
        )
        
        return UpdateKnowledgeBaseResponse(
            knowledge_base_id=result["knowledge_base_id"],
            status=KnowledgeBaseStatus(result["status"]),
            updated_at=result["updated_at"],
            statistics=result["statistics"],
            message="知识库更新成功",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新知识库异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新知识库失败",
        ) from e


@router.delete(
    "/{knowledge_base_id}/delete",
    response_model=DeleteKnowledgeBaseResponse,
    responses={
        404: {"model": ErrorResponse, "description": "知识库不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="删除知识库",
    description="删除知识库及其所有索引和数据",
)
async def delete_knowledge_base(
    knowledge_base_id: str,
) -> DeleteKnowledgeBaseResponse:
    """
    删除知识库接口
    
    Args:
        knowledge_base_id: 知识库ID
        
    Returns:
        DeleteKnowledgeBaseResponse: 删除结果
        
    Raises:
        HTTPException: 删除失败时抛出
    """
    try:
        # 获取知识库服务实例
        service = get_knowledge_base_service(knowledge_base_id)
        
        # 删除知识库
        result = service.delete_knowledge_base()
        
        # 从缓存中移除
        if knowledge_base_id in _knowledge_base_services:
            del _knowledge_base_services[knowledge_base_id]
        
        return DeleteKnowledgeBaseResponse(
            knowledge_base_id=result["knowledge_base_id"],
            status=result["status"],
            deleted_at=result["deleted_at"],
            message="知识库删除成功",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除知识库异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除知识库失败",
        ) from e


@router.post(
    "/{knowledge_base_id}/query",
    response_model=QueryKnowledgeBaseResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "知识库不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="查询知识库",
    description="在知识库中检索相关文档，支持混合查询和结构化查询",
)
async def query_knowledge_base(
    knowledge_base_id: str,
    request: QueryKnowledgeBaseRequest,
) -> QueryKnowledgeBaseResponse:
    """
    查询知识库接口
    
    Args:
        knowledge_base_id: 知识库ID
        request: 查询请求
        
    Returns:
        QueryKnowledgeBaseResponse: 查询结果
        
    Raises:
        HTTPException: 查询失败时抛出
    """
    try:
        # 获取知识库服务实例
        service = get_knowledge_base_service(knowledge_base_id)
        
        # 构建结构化查询
        structured_query = None
        if request.use_structured or request.section_path or request.document_level:
            structured_query = StructuredQuery(
                section_path=request.section_path,
                document_level=request.document_level,
                filters=request.filters,
                sort_by=request.sort_by,
                sort_order=request.sort_order,
            )
        
        # 查询知识库
        import time
        start_time = time.time()
        
        results = service.query(
            query_str=request.query,
            top_k=request.top_k,
            query_type=request.query_type,
            filters=request.filters,
            use_hybrid=request.use_hybrid,
            use_structured=request.use_structured,
            structured_query=structured_query,
        )
        
        query_time = time.time() - start_time
        
        # 转换结果
        query_results = []
        for result in results:
            query_results.append(
                QueryResult(
                    node_id=result.node.node_id,
                    content=result.node.text,
                    score=result.score if hasattr(result, 'score') else 0.0,
                    metadata=result.node.metadata,
                )
            )
        
        return QueryKnowledgeBaseResponse(
            knowledge_base_id=knowledge_base_id,
            query=request.query,
            results=query_results,
            total_results=len(query_results),
            query_time=query_time,
            message="查询成功",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("查询知识库异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="查询知识库失败",
        ) from e


@router.get(
    "/{knowledge_base_id}/status",
    response_model=KnowledgeBaseStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "知识库不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="获取知识库状态",
    description="获取知识库的状态、配置和统计信息",
)
async def get_knowledge_base_status(
    knowledge_base_id: str,
) -> KnowledgeBaseStatusResponse:
    """
    获取知识库状态接口
    
    Args:
        knowledge_base_id: 知识库ID
        
    Returns:
        KnowledgeBaseStatusResponse: 知识库状态
        
    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取知识库服务实例
        service = get_knowledge_base_service(knowledge_base_id)
        
        # 获取状态信息
        status_info = service.get_status()
        
        # 构建配置信息
        from src.interfaces.api.schemas.knowledge_base_schemas import (
            ChunkingConfig as SchemaChunkingConfig,
            HybridRetrieverConfig as SchemaHybridRetrieverConfig,
            IndexStatistics,
            KnowledgeBaseConfig,
        )
        
        chunking_config_schema = SchemaChunkingConfig(
            chunk_size=status_info["config"]["chunking"]["chunk_size"],
            chunk_overlap=status_info["config"]["chunking"]["chunk_overlap"],
            split_by_section=status_info["config"]["chunking"]["split_by_section"],
            split_by_paragraph=status_info["config"]["chunking"]["split_by_paragraph"],
        )
        
        hybrid_retriever_config_schema = SchemaHybridRetrieverConfig(
            enable_vector=status_info["config"]["hybrid_retriever"]["enable_vector"],
            enable_bm25=status_info["config"]["hybrid_retriever"]["enable_bm25"],
            enable_metadata=status_info["config"]["hybrid_retriever"]["enable_metadata"],
            enable_graph=status_info["config"]["hybrid_retriever"]["enable_graph"],
            fusion_strategy=FusionStrategy(status_info["config"]["hybrid_retriever"]["fusion_strategy"]),
            default_top_k=status_info["config"]["hybrid_retriever"]["default_top_k"],
        )
        
        config_schema = KnowledgeBaseConfig(
            chunking=chunking_config_schema,
            hybrid_retriever=hybrid_retriever_config_schema,
        )
        
        indexes_schema = IndexStatistics(
            vector=status_info["indexes"]["vector"],
            bm25=status_info["indexes"]["bm25"],
            metadata=status_info["indexes"]["metadata"],
        )
        
        return KnowledgeBaseStatusResponse(
            knowledge_base_id=status_info["knowledge_base_id"],
            status=KnowledgeBaseStatus(status_info["status"]),
            processing_status=status_info["processing_status"],
            progress_info=status_info["progress_info"],
            indexes=indexes_schema,
            config=config_schema,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取知识库状态异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取知识库状态失败",
        ) from e


@router.get(
    "/list",
    response_model=Dict[str, Any],
    responses={
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="列出所有知识库",
    description="获取系统中所有知识库的列表和基本信息",
)
async def list_knowledge_bases() -> Dict[str, Any]:
    """
    列出所有知识库接口
    
    Returns:
        Dict[str, Any]: 知识库列表
        
    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 构建知识库列表
        kb_list = []
        for kb_id, service in _knowledge_base_services.items():
            status_info = service.get_status()
            kb_list.append({
                "knowledge_base_id": kb_id,
                "status": status_info["status"],
                "indexes": {
                    "vector": status_info["indexes"]["vector"] is not None,
                    "bm25": status_info["indexes"]["bm25"] is not None,
                    "metadata": status_info["indexes"]["metadata"] is not None,
                },
            })
        
        return create_success_response(
            message="获取知识库列表成功",
            data={
                "knowledge_bases": kb_list,
                "total": len(kb_list),
            },
        )
        
    except Exception as e:
        logger.exception("列出知识库异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="列出知识库失败",
        ) from e