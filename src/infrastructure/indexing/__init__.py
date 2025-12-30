"""
索引构建模块

该包包含与索引相关的基础设施组件, 包括:
- 文档分块策略(T052): 使用LlamaIndex SentenceSplitter实现按章节/段落的分块
- 检索块与合成块分离策略(T062): 实现双层分块策略,优化RAG性能
- 向量嵌入生成器(T053): 使用LlamaIndex集成LangChain embedding模型,支持批量嵌入和缓存
- 向量索引构建器(T046): 使用LlamaIndex VectorStoreIndex和ChromaVectorStore构建向量索引
- BM25索引构建器(T047): 使用rank-bm25库实现BM25算法,支持关键词检索
- 元数据索引构建器(T048): 使用SQLite存储元数据索引,支持结构化查询
- 知识图谱构建器(T049): 使用LLM进行实体关系提取,并将结果存储到NetworkX图数据库中
- 混合检索引擎(T061): 融合向量检索,BM25检索,元数据检索和知识图谱检索,使用RRF算法融合结果
- 结构化检索增强(T063): 支持章节路径检索,文档层级检索,元数据过滤,混合查询和结果排序
"""

from src.infrastructure.indexing.bm25_index import (
    BM25IndexBuilder,
    BM25IndexError,
)
from src.infrastructure.indexing.document_chunking import (
    ChunkingError,
    DocumentChunkingStrategy,
)
from src.infrastructure.indexing.embedding_generator import (
    EmbeddingCache,
    EmbeddingError,
    EmbeddingGenerator,
    LangChainEmbeddingAdapter,
)
from src.infrastructure.indexing.hybrid_retriever import (
    FusionStrategy,
    HybridRetriever,
    HybridRetrieverConfig,
    HybridRetrieverError,
    QueryType,
    RetrievalWeights,
)
from src.infrastructure.indexing.knowledge_graph import (
    EntityType,
    ExtractedEntity,
    ExtractedRelation,
    KnowledgeGraphBuilder,
    KnowledgeGraphError,
    RelationType,
)
from src.infrastructure.indexing.metadata_index import (
    MetadataIndexBuilder,
    MetadataIndexError,
)
from src.infrastructure.indexing.retrieval_composition_splitter import (
    ChunkMapping,
    RetrievalCompositionConfig,
    RetrievalCompositionSplitter,
    RetrievalCompositionSplitterError,
)
from src.infrastructure.indexing.structured_retrieval import (
    DocumentLevel,
    HybridStructuredQuery,
    SortOrder,
    StructuredQuery,
    StructuredRetrievalError,
    StructuredRetriever,
)
from src.infrastructure.indexing.vector_index import (
    VectorIndexBuilder,
    VectorIndexError,
)

__all__ = [
    "BM25IndexBuilder",
    "BM25IndexError",
    "ChunkMapping",
    "ChunkingError",
    "DocumentChunkingStrategy",
    "DocumentLevel",
    "EmbeddingCache",
    "EmbeddingError",
    "EmbeddingGenerator",
    "EntityType",
    "ExtractedEntity",
    "ExtractedRelation",
    "FusionStrategy",
    "HybridRetriever",
    "HybridRetrieverConfig",
    "HybridRetrieverError",
    "HybridStructuredQuery",
    "KnowledgeGraphBuilder",
    "KnowledgeGraphError",
    "LangChainEmbeddingAdapter",
    "MetadataIndexBuilder",
    "MetadataIndexError",
    "QueryType",
    "RelationType",
    "RetrievalCompositionConfig",
    "RetrievalCompositionSplitter",
    "RetrievalCompositionSplitterError",
    "RetrievalWeights",
    "SortOrder",
    "StructuredQuery",
    "StructuredRetrievalError",
    "StructuredRetriever",
    "VectorIndexBuilder",
    "VectorIndexError",
]


