"""
知识库相关API Schema

定义知识库创建,更新,查询等API的请求和响应Schema.
使用Pydantic进行数据验证.

生成命令: /speckit.implement T055
生成时间: 2025-12-21
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar

from pydantic import BaseModel, Field, field_validator


class KnowledgeBaseStatus(str, Enum):
    """知识库状态枚举"""

    INITIALIZING = "initializing"  # 初始化中
    READY = "ready"  # 就绪
    INDEXING = "indexing"  # 索引中
    ERROR = "error"  # 错误
    UPDATING = "updating"  # 更新中


class QueryType(str, Enum):
    """查询类型枚举"""

    FACTUAL = "factual"  # 事实性问答
    SUMMARY = "summary"  # 总结
    COMPARISON = "comparison"  # 比较
    EXPLANATION = "explanation"  # 解释
    GENERAL = "general"  # 通用


class FusionStrategy(str, Enum):
    """融合策略枚举"""

    RRF = "rrf"  # Reciprocal Rank Fusion
    WEIGHTED_SUM = "weighted_sum"  # 加权求和
    MAX_SCORE = "max_score"  # 最大分数
    AVERAGE = "average"  # 平均分数


class DocumentLevel(str, Enum):
    """文档级别枚举"""

    DOCUMENT = "document"  # 文档级别
    SECTION = "section"  # 章节级别
    PARAGRAPH = "paragraph"  # 段落级别


class SortOrder(str, Enum):
    """排序顺序枚举"""

    ASC = "asc"  # 升序
    DESC = "desc"  # 降序


# === 请求Schema ===

class CreateKnowledgeBaseRequest(BaseModel):
    """创建知识库请求"""

    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    directories: list[str] = Field(
        ..., min_items=1, max_items=50, description="预处理结果目录列表"
    )
    description: str | None = Field(
        None, max_length=500, description="知识库描述"
    )
    vector_collection_name: str | None = Field(
        None, max_length=100, description="向量索引集合名称"
    )
    bm25_index_path: str | None = Field(
        None, max_length=255, description="BM25索引文件路径"
    )
    enable_vector: bool = Field(default=True, description="是否启用向量检索")
    enable_bm25: bool = Field(default=True, description="是否启用BM25检索")
    enable_metadata: bool = Field(default=True, description="是否启用元数据检索")
    enable_graph: bool = Field(default=False, description="是否启用知识图谱检索")
    chunk_size: int = Field(default=1024, ge=100, le=4096, description="分块大小")
    chunk_overlap: int = Field(default=200, ge=0, le=1024, description="分块重叠大小")
    split_by_section: bool = Field(default=True, description="是否按章节分块")
    split_by_paragraph: bool = Field(default=True, description="是否按段落分块")
    show_progress: bool = Field(default=False, description="是否显示进度")

    @field_validator("directories")
    @classmethod
    def validate_directories(cls, v: list[str]) -> list[str]:
        """验证目录列表"""
        # 去重
        unique_dirs = list(set(v))
        if len(unique_dirs) != len(v):
            msg = "目录列表中存在重复项"
            raise ValueError(msg)
        return unique_dirs


class UpdateKnowledgeBaseRequest(BaseModel):
    """更新知识库请求"""

    directories: list[str] | None = Field(
        None, min_items=1, max_items=50, description="预处理结果目录列表"
    )
    show_progress: bool = Field(default=False, description="是否显示进度")

    @field_validator("directories")
    @classmethod
    def validate_directories(cls, v: list[str] | None) -> list[str] | None:
        """验证目录列表"""
        if v is None:
            return v
        # 去重
        unique_dirs = list(set(v))
        if len(unique_dirs) != len(v):
            msg = "目录列表中存在重复项"
            raise ValueError(msg)
        return unique_dirs


class QueryKnowledgeBaseRequest(BaseModel):
    """查询知识库请求"""

    query: str = Field(..., min_length=1, max_length=1000, description="查询文本")
    top_k: int = Field(default=10, ge=1, le=100, description="返回结果数量")
    query_type: QueryType | None = Field(None, description="查询类型")
    filters: dict[str, Any] | None = Field(None, description="元数据过滤器")
    use_hybrid: bool = Field(default=True, description="是否使用混合检索")
    use_structured: bool = Field(default=False, description="是否使用结构化检索")
    section_path: str | None = Field(None, description="章节路径")
    document_level: DocumentLevel | None = Field(None, description="文档级别")
    sort_by: str | None = Field(None, description="排序字段")
    sort_order: SortOrder = Field(default=SortOrder.DESC, description="排序顺序")

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """验证过滤器"""
        if v is None:
            return v
        # 限制过滤器大小
        if len(str(v)) > 2000:  # 2KB限制
            msg = "过滤器过大,最多支持2KB"
            raise ValueError(msg)
        return v


class StructuredQueryRequest(BaseModel):
    """结构化查询请求"""

    section_path: str | None = Field(None, description="章节路径")
    document_level: DocumentLevel | None = Field(None, description="文档级别")
    filters: dict[str, Any] | None = Field(None, description="元数据过滤器")
    sort_by: str | None = Field(None, description="排序字段")
    sort_order: SortOrder = Field(default=SortOrder.DESC, description="排序顺序")

    @field_validator("filters")
    @classmethod
    def validate_filters(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """验证过滤器"""
        if v is None:
            return v
        # 限制过滤器大小
        if len(str(v)) > 2000:  # 2KB限制
            msg = "过滤器过大,最多支持2KB"
            raise ValueError(msg)
        return v


# === 响应Schema ===

class IndexStatistics(BaseModel):
    """索引统计信息"""

    vector: dict[str, Any] | None = Field(None, description="向量索引统计")
    bm25: dict[str, Any] | None = Field(None, description="BM25索引统计")
    metadata: dict[str, Any] | None = Field(None, description="元数据索引统计")


class ChunkingConfig(BaseModel):
    """分块配置"""

    chunk_size: int = Field(..., description="分块大小")
    chunk_overlap: int = Field(..., description="分块重叠大小")
    split_by_section: bool = Field(..., description="是否按章节分块")
    split_by_paragraph: bool = Field(..., description="是否按段落分块")


class HybridRetrieverConfig(BaseModel):
    """混合检索器配置"""

    enable_vector: bool = Field(..., description="是否启用向量检索")
    enable_bm25: bool = Field(..., description="是否启用BM25检索")
    enable_metadata: bool = Field(..., description="是否启用元数据检索")
    enable_graph: bool = Field(..., description="是否启用知识图谱检索")
    fusion_strategy: FusionStrategy = Field(..., description="融合策略")
    default_top_k: int = Field(..., description="默认返回结果数量")


class KnowledgeBaseConfig(BaseModel):
    """知识库配置"""

    chunking: ChunkingConfig = Field(..., description="分块配置")
    hybrid_retriever: HybridRetrieverConfig = Field(..., description="混合检索器配置")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""

    knowledge_base_id: str = Field(..., description="知识库ID")
    name: str = Field(..., description="知识库名称")
    description: str | None = Field(None, description="知识库描述")
    status: KnowledgeBaseStatus = Field(..., description="知识库状态")
    created_at: str = Field(..., description="创建时间")
    updated_at: str | None = Field(None, description="更新时间")
    config: KnowledgeBaseConfig = Field(..., description="知识库配置")
    indexes: IndexStatistics = Field(..., description="索引统计信息")

    class Config:
        """Pydantic配置"""

        json_encoders: ClassVar[dict[type, Any]] = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


class CreateKnowledgeBaseResponse(BaseModel):
    """创建知识库响应"""

    knowledge_base: KnowledgeBaseResponse = Field(..., description="知识库信息")
    statistics: dict[str, Any] = Field(..., description="创建统计信息")
    message: str = Field(..., description="响应消息")


class UpdateKnowledgeBaseResponse(BaseModel):
    """更新知识库响应"""

    knowledge_base_id: str = Field(..., description="知识库ID")
    status: KnowledgeBaseStatus = Field(..., description="知识库状态")
    updated_at: str = Field(..., description="更新时间")
    statistics: dict[str, Any] = Field(..., description="更新统计信息")
    message: str = Field(..., description="响应消息")


class DeleteKnowledgeBaseResponse(BaseModel):
    """删除知识库响应"""

    knowledge_base_id: str = Field(..., description="知识库ID")
    status: str = Field(..., description="删除状态")
    deleted_at: str = Field(..., description="删除时间")
    message: str = Field(..., description="响应消息")


class QueryResult(BaseModel):
    """查询结果项"""

    node_id: str = Field(..., description="节点ID")
    content: str = Field(..., description="内容")
    score: float = Field(..., description="相关性分数")
    metadata: dict[str, Any] = Field(..., description="元数据")


class QueryKnowledgeBaseResponse(BaseModel):
    """查询知识库响应"""

    knowledge_base_id: str = Field(..., description="知识库ID")
    query: str = Field(..., description="查询文本")
    results: list[QueryResult] = Field(..., description="查询结果")
    total_results: int = Field(..., description="总结果数")
    query_time: float = Field(..., description="查询耗时(秒)")
    message: str = Field(..., description="响应消息")


class KnowledgeBaseStatusResponse(BaseModel):
    """知识库状态响应"""

    knowledge_base_id: str = Field(..., description="知识库ID")
    status: KnowledgeBaseStatus = Field(..., description="知识库状态")
    processing_status: dict[str, Any] = Field(..., description="处理状态")
    progress_info: dict[str, Any] = Field(..., description="进度信息")
    indexes: IndexStatistics = Field(..., description="索引统计信息")
    config: KnowledgeBaseConfig = Field(..., description="知识库配置")


class ErrorResponse(BaseModel):
    """错误响应"""

    error: bool = Field(default=True, description="是否为错误")
    error_code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: dict[str, Any] | None = Field(None, description="错误详情")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="错误时间")
    path: str | None = Field(None, description="请求路径")


# === 便捷函数 ===

def create_error_response(
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    path: str | None = None,
) -> ErrorResponse:
    """创建错误响应

    Args:
        error_code: 错误代码
        message: 错误消息
        details: 错误详情
        path: 请求路径

    Returns:
        ErrorResponse: 错误响应对象
    """
    return ErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        path=path,
    )


def create_success_response(
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """创建成功响应

    Args:
        message: 成功消息
        data: 响应数据

    Returns:
        Dict[str, Any]: 成功响应字典
    """
    response = {
        "success": True,
        "message": message,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if data:
        response["data"] = data
    return response
