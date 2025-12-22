# 生成命令: /speckit.implement T050
# 生成时间: 2025-12-20
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
知识库服务单元测试

测试KnowledgeBaseService类的核心功能，包括知识库创建、更新、删除、查询等操作。
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from src.application.services.knowledge_base_service import (
    ChunkingConfig,
    KnowledgeBaseService,
    KnowledgeBaseServiceError,
    KnowledgeBaseStatus,
    ProcessingStatus,
)
from src.infrastructure.indexing.document_chunking import DocumentChunkingStrategy
from src.infrastructure.indexing.hybrid_retriever import (
    FusionStrategy,
    HybridRetrieverConfig,
    QueryType,
    RetrievalWeights,
)
from src.infrastructure.indexing.structured_retrieval import (
    DocumentLevel,
    SortOrder,
    StructuredQuery,
)

try:
    from llama_index.core.schema import NodeWithScore, TextNode
    from langchain_core.documents import Document
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    NodeWithScore = MagicMock
    TextNode = MagicMock
    Document = MagicMock
    LLAMA_INDEX_AVAILABLE = False


class TestKnowledgeBaseService:
    """KnowledgeBaseService测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def mock_documents(self):
        """创建模拟文档"""
        return [
            Document(
                page_content="这是第一个测试文档的内容。",
                metadata={"source": "test1.md", "format": "markdown"},
            ),
            Document(
                page_content="这是第二个测试文档的内容。",
                metadata={"source": "test2.md", "format": "markdown"},
            ),
        ]

    @pytest.fixture
    def mock_preprocessed_dirs(self, temp_dir, mock_documents):
        """创建模拟预处理结果目录"""
        dirs = []
        
        for i, doc in enumerate(mock_documents):
            # 创建目录
            dir_path = Path(temp_dir) / f"doc_{i+1}_extracted"
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # 创建clean.md文件
            clean_md_path = dir_path / "clean.md"
            with open(clean_md_path, "w", encoding="utf-8") as f:
                f.write(doc.page_content)
            
            # 创建clean_content_list.json文件
            content_list = [
                {
                    "page_idx": 0,
                    "type": "paragraph",
                    "content": doc.page_content,
                }
            ]
            content_list_path = dir_path / "clean_content_list.json"
            with open(content_list_path, "w", encoding="utf-8") as f:
                json.dump(content_list, f, ensure_ascii=False, indent=2)
            
            # 创建images目录（可选）
            images_dir = dir_path / "images"
            images_dir.mkdir(exist_ok=True)
            
            # 创建datajson目录（可选）
            datajson_dir = dir_path / "datajson"
            datajson_dir.mkdir(exist_ok=True)
            
            dirs.append(str(dir_path))
        
        return dirs

    @pytest.fixture
    def knowledge_base_service(self, temp_dir):
        """创建知识库服务实例"""
        with patch("src.application.services.knowledge_base_service.get_llm_service"):
            vector_collection_name = f"test_vector_{uuid4().hex[:8]}"
            bm25_index_path = os.path.join(temp_dir, f"test_bm25_{uuid4().hex[:8]}.pkl")
            metadata_table_name = f"test_metadata_{uuid4().hex[:8]}"
            
            # 根据LlamaIndex是否可用来配置
            enable_vector = LLAMA_INDEX_AVAILABLE
            
            return KnowledgeBaseService(
                vector_collection_name=vector_collection_name,
                bm25_index_path=bm25_index_path,
                metadata_table_name=metadata_table_name,
                enable_vector=enable_vector,
                enable_bm25=True,
                enable_metadata=True,
                enable_graph=False,
                chunking_config=ChunkingConfig(chunk_size=512, chunk_overlap=50),
                hybrid_retriever_config=HybridRetrieverConfig(
                    enable_vector=enable_vector,
                    enable_bm25=True,
                    enable_metadata=True,
                    enable_graph=False,
                    fusion_strategy=FusionStrategy.RRF,
                    default_top_k=10,
                ),
            )

    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        with patch("src.application.services.knowledge_base_service.get_llm_service"):
            service = KnowledgeBaseService()
            
            assert service.knowledge_base_id is not None
            # 向量索引构建器可能为None（如果LlamaIndex不可用）
            if LLAMA_INDEX_AVAILABLE:
                assert service.vector_index_builder is not None
            assert service.bm25_index_builder is not None
            assert service.metadata_index_builder is not None
            assert service.hybrid_retriever is not None
            assert service.structured_retriever is not None
            assert service._status == KnowledgeBaseStatus.READY

    def test_init_with_custom_config(self, temp_dir):
        """测试使用自定义配置初始化"""
        with patch("src.application.services.knowledge_base_service.get_llm_service"):
            vector_collection_name = "custom_vector"
            bm25_index_path = os.path.join(temp_dir, "custom_bm25.pkl")
            metadata_table_name = "custom_metadata"
            
            service = KnowledgeBaseService(
                knowledge_base_id=uuid4(),
                vector_collection_name=vector_collection_name,
                bm25_index_path=bm25_index_path,
                metadata_table_name=metadata_table_name,
                enable_vector=False,
                enable_bm25=True,  # 至少启用一种检索
                enable_metadata=True,  # 至少启用一种检索
                enable_graph=True,
            )
            
            assert service.vector_index_builder is None
            assert service.bm25_index_builder is not None
            assert service.metadata_index_builder is not None
            assert service._status == KnowledgeBaseStatus.READY

    @patch("src.application.services.knowledge_base_service.LLAMA_INDEX_AVAILABLE", False)
    def test_init_without_llamaindex(self):
        """测试没有LlamaIndex时的初始化"""
        with pytest.raises(ImportError, match="LlamaIndex is not available"):
            KnowledgeBaseService()

    def test_create_knowledge_base(self, knowledge_base_service, mock_preprocessed_dirs):
        """测试创建知识库"""
        result = knowledge_base_service.create_knowledge_base(
            name="test_kb",
            directories=mock_preprocessed_dirs,
            description="测试知识库",
        )
        
        # 验证返回结果
        assert result["name"] == "test_kb"
        assert result["description"] == "测试知识库"
        assert result["status"] == KnowledgeBaseStatus.READY.value
        assert result["statistics"]["documents_count"] == 2
        assert result["statistics"]["directories_count"] == 2
        # 向量索引状态取决于LlamaIndex是否可用
        assert result["indexes"]["vector"] == LLAMA_INDEX_AVAILABLE
        assert result["indexes"]["bm25"] is True
        assert result["indexes"]["metadata"] is True

    def test_create_knowledge_base_with_documents(
        self, knowledge_base_service, mock_documents, mock_preprocessed_dirs
    ):
        """测试使用文档列表创建知识库"""
        # 模拟解析和分块过程
        with patch.object(
            knowledge_base_service, "_parse_documents"
        ) as mock_parse, patch.object(
            knowledge_base_service, "_chunk_documents"
        ) as mock_chunk:
            
            # 设置模拟返回值
            # 注意：LlamaIndex启用时，VectorStoreIndex/Chroma 会对节点进行JSON序列化，
            # 因此这里必须返回真实的 BaseNode（例如 TextNode），不能用 MagicMock。
            parsed_nodes = [
                TextNode(
                    text=doc.page_content,
                    metadata={"source": doc.metadata.get("source", "test.md")},
                )
                for doc in mock_documents
            ]
            chunked_nodes = [
                TextNode(
                    text=node.text,
                    metadata={**(node.metadata or {}), "chunk_index": i},
                )
                for i, node in enumerate(parsed_nodes)
            ]
            mock_parse.return_value = parsed_nodes
            mock_chunk.return_value = chunked_nodes
            
            # 使用update_knowledge_base方法来测试documents参数
            result = knowledge_base_service.update_knowledge_base(
                documents=mock_documents,
            )
            
            # 验证调用
            mock_parse.assert_called_once()
            mock_chunk.assert_called_once()

    def test_create_knowledge_base_error_status(self, knowledge_base_service):
        """测试错误状态下创建知识库"""
        # 设置错误状态
        knowledge_base_service._status = KnowledgeBaseStatus.ERROR
        
        with pytest.raises(
            KnowledgeBaseServiceError, match="知识库状态不正确"
        ):
            knowledge_base_service.create_knowledge_base(
                name="test_kb",
                directories=[],
            )

    def test_update_knowledge_base(
        self, knowledge_base_service, mock_preprocessed_dirs
    ):
        """测试更新知识库"""
        # 先创建知识库
        knowledge_base_service.create_knowledge_base(
            name="test_kb",
            directories=mock_preprocessed_dirs[:1],
        )
        
        # 更新知识库
        result = knowledge_base_service.update_knowledge_base(
            directories=mock_preprocessed_dirs[1:],
        )
        
        # 验证返回结果
        assert result["status"] == KnowledgeBaseStatus.READY.value
        assert result["statistics"]["new_documents_count"] == 1

    def test_update_knowledge_base_with_documents(
        self, knowledge_base_service, mock_documents, mock_preprocessed_dirs
    ):
        """测试使用文档列表更新知识库"""
        # 先创建知识库
        knowledge_base_service.create_knowledge_base(
            name="test_kb",
            directories=mock_preprocessed_dirs[:1],
        )
        
        # 模拟解析和分块过程
        with patch.object(
            knowledge_base_service, "_parse_documents"
        ) as mock_parse, patch.object(
            knowledge_base_service, "_chunk_documents"
        ) as mock_chunk:
            
            # 设置模拟返回值
            parsed_nodes = [
                TextNode(
                    text=mock_documents[1].page_content,
                    metadata={"source": mock_documents[1].metadata.get("source", "test2.md")},
                )
            ]
            chunked_nodes = [
                TextNode(
                    text=parsed_nodes[0].text,
                    metadata={**(parsed_nodes[0].metadata or {}), "chunk_index": 0},
                )
            ]
            mock_parse.return_value = parsed_nodes
            mock_chunk.return_value = chunked_nodes
            
            # 更新知识库
            result = knowledge_base_service.update_knowledge_base(
                documents=mock_documents[1:],
            )
            
            # 验证调用
            mock_parse.assert_called_once()
            mock_chunk.assert_called_once()

    def test_update_knowledge_base_no_input(self, knowledge_base_service):
        """测试没有输入时更新知识库"""
        with pytest.raises(ValueError, match="必须提供directories或documents"):
            knowledge_base_service.update_knowledge_base()

    def test_delete_knowledge_base(self, knowledge_base_service, temp_dir):
        """测试删除知识库"""
        # 创建BM25索引文件
        bm25_index_path = os.path.join(temp_dir, "test_bm25.pkl")
        with open(bm25_index_path, "w") as f:
            f.write("dummy content")
        
        # 重新初始化服务以使用创建的索引文件
        with patch("src.application.services.knowledge_base_service.get_llm_service"):
            service = KnowledgeBaseService(
                bm25_index_path=bm25_index_path,
            )
        
        # 删除知识库
        result = service.delete_knowledge_base()
        
        # 验证返回结果
        assert result["status"] == "deleted"
        assert result["knowledge_base_id"] == str(service.knowledge_base_id)

    def test_query_knowledge_base(self, knowledge_base_service, mock_preprocessed_dirs):
        """测试查询知识库"""
        # 先创建知识库
        knowledge_base_service.create_knowledge_base(
            name="test_kb",
            directories=mock_preprocessed_dirs,
        )
        
        # 模拟检索结果
        with patch.object(
            knowledge_base_service.hybrid_retriever, "retrieve"
        ) as mock_retrieve:
            
            mock_retrieve.return_value = [
                NodeWithScore(node=TextNode(text="mock1"), score=0.8),
                NodeWithScore(node=TextNode(text="mock2"), score=0.6),
            ]
            
            # 查询知识库
            results = knowledge_base_service.query(
                query_str="测试查询",
                top_k=5,
                query_type=QueryType.FACTUAL_QA,
            )
            
            # 验证调用和结果
            mock_retrieve.assert_called_once_with(
                query_str="测试查询",
                top_k=5,
                query_type=QueryType.FACTUAL_QA,
                filters=None,
            )
            assert len(results) == 2

    def test_query_knowledge_base_structured(
        self, knowledge_base_service, mock_preprocessed_dirs
    ):
        """测试结构化查询知识库"""
        # 先创建知识库
        knowledge_base_service.create_knowledge_base(
            name="test_kb",
            directories=mock_preprocessed_dirs,
        )
        
        # 模拟结构化检索结果
        with patch.object(
            knowledge_base_service.structured_retriever, "retrieve_hybrid"
        ) as mock_retrieve:
            
            mock_retrieve.return_value = [
                NodeWithScore(node=TextNode(text="mock_structured"), score=0.8),
            ]
            
            # 结构化查询
            results = knowledge_base_service.query(
                query_str="测试查询",
                top_k=5,
                use_hybrid=False,
                use_structured=True,
                structured_query=StructuredQuery(
                    section_path="1.2",
                    document_level=DocumentLevel.SECTION,
                ),
            )
            
            # 验证调用和结果
            mock_retrieve.assert_called_once()
            assert len(results) == 1

    def test_query_knowledge_base_empty_query(self, knowledge_base_service):
        """测试空查询字符串"""
        with pytest.raises(ValueError, match="查询文本不能为空"):
            knowledge_base_service.query(query_str="")

    def test_query_knowledge_base_error_status(self, knowledge_base_service):
        """测试错误状态下查询知识库"""
        # 设置错误状态
        knowledge_base_service._status = KnowledgeBaseStatus.ERROR
        
        with pytest.raises(
            KnowledgeBaseServiceError, match="知识库状态不正确"
        ):
            knowledge_base_service.query(query_str="测试查询")

    def test_get_status(self, knowledge_base_service):
        """测试获取知识库状态"""
        status = knowledge_base_service.get_status()
        
        # 验证状态信息
        assert "knowledge_base_id" in status
        assert "status" in status
        assert "indexes" in status
        assert "config" in status
        
        # 验证配置信息
        config = status["config"]
        assert "chunking" in config
        assert "hybrid_retriever" in config
        
        # 验证分块配置
        chunking = config["chunking"]
        assert chunking["chunk_size"] == 512
        assert chunking["chunk_overlap"] == 50
        
        # 验证混合检索配置
        hybrid = config["hybrid_retriever"]
        assert hybrid["enable_vector"] == LLAMA_INDEX_AVAILABLE
        assert hybrid["enable_bm25"] is True
        assert hybrid["enable_metadata"] is True
        assert hybrid["enable_graph"] is False

    def test_create_from_config(self, temp_dir):
        """测试从配置创建知识库服务"""
        config = {
            "knowledge_base_id": str(uuid4()),
            "vector_collection_name": "config_vector",
            "bm25_index_path": os.path.join(temp_dir, "config_bm25.pkl"),
            "metadata_table_name": "config_metadata",
            "enable_vector": True,
            "enable_bm25": True,
            "enable_metadata": True,
            "enable_graph": False,
            "chunking_config": {
                "chunk_size": 256,
                "chunk_overlap": 25,
                "split_by_section": False,
                "split_by_paragraph": True,
            },
            "hybrid_retriever_config": {
                "enable_vector": True,
                "enable_bm25": True,
                "enable_metadata": True,
                "enable_graph": False,
                "fusion_strategy": "weighted_sum",
                "default_top_k": 20,
            },
        }
        
        with patch("src.application.services.knowledge_base_service.get_llm_service"):
            service = KnowledgeBaseService.create_from_config(config)
            
            # 验证配置应用
            assert str(service.knowledge_base_id) == config["knowledge_base_id"]
            assert service.chunking_config.chunk_size == 256
            assert service.chunking_config.chunk_overlap == 25
            assert service.chunking_config.split_by_section is False
            assert service.chunking_config.split_by_paragraph is True
            
            # 验证混合检索配置
            hybrid_config = service.hybrid_retriever_config
            assert hybrid_config.fusion_strategy == FusionStrategy.WEIGHTED_SUM
            assert hybrid_config.default_top_k == 20

    def test_load_documents_error(self, knowledge_base_service):
        """测试加载文档错误处理"""
        with patch.object(
            knowledge_base_service, "_load_documents"
        ) as mock_load:
            
            # 模拟加载失败
            mock_load.side_effect = Exception("加载失败")
            
            with pytest.raises(KnowledgeBaseServiceError, match="创建知识库失败"):
                knowledge_base_service.create_knowledge_base(
                    name="test_kb",
                    directories=["invalid_dir"],
                )

    def test_parse_documents_error(self, knowledge_base_service, mock_preprocessed_dirs):
        """测试解析文档错误处理"""
        with patch.object(
            knowledge_base_service, "_parse_documents"
        ) as mock_parse:
            
            # 模拟解析失败
            mock_parse.side_effect = Exception("解析失败")
            
            with pytest.raises(KnowledgeBaseServiceError, match="创建知识库失败"):
                knowledge_base_service.create_knowledge_base(
                    name="test_kb",
                    directories=mock_preprocessed_dirs,
                )

    def test_chunk_documents_error(self, knowledge_base_service, mock_preprocessed_dirs):
        """测试分块错误处理"""
        with patch.object(
            knowledge_base_service, "_chunk_documents"
        ) as mock_chunk:
            
            # 模拟分块失败
            mock_chunk.side_effect = Exception("分块失败")
            
            with pytest.raises(KnowledgeBaseServiceError, match="创建知识库失败"):
                knowledge_base_service.create_knowledge_base(
                    name="test_kb",
                    directories=mock_preprocessed_dirs,
                )

    def test_build_indexes_error(self, knowledge_base_service, mock_preprocessed_dirs):
        """测试构建索引错误处理"""
        with patch.object(
            knowledge_base_service, "_build_indexes"
        ) as mock_build:
            
            # 模拟构建失败
            mock_build.side_effect = Exception("构建失败")
            
            with pytest.raises(KnowledgeBaseServiceError, match="创建知识库失败"):
                knowledge_base_service.create_knowledge_base(
                    name="test_kb",
                    directories=mock_preprocessed_dirs,
                )

    def test_query_error(self, knowledge_base_service, mock_preprocessed_dirs):
        """测试查询错误处理"""
        # 先创建知识库
        knowledge_base_service.create_knowledge_base(
            name="test_kb",
            directories=mock_preprocessed_dirs,
        )
        
        # 模拟检索失败
        with patch.object(
            knowledge_base_service.hybrid_retriever, "retrieve"
        ) as mock_retrieve:
            
            mock_retrieve.side_effect = Exception("检索失败")
            
            with pytest.raises(KnowledgeBaseServiceError, match="查询知识库失败"):
                knowledge_base_service.query(query_str="测试查询")

    @pytest.mark.skipif(not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available")
    def test_end_to_end_workflow(self, knowledge_base_service, mock_preprocessed_dirs):
        """测试端到端工作流程"""
        # 创建知识库
        create_result = knowledge_base_service.create_knowledge_base(
            name="end_to_end_test_kb",
            directories=mock_preprocessed_dirs,
            description="端到端测试知识库",
        )
        
        assert create_result["status"] == KnowledgeBaseStatus.READY.value
        assert create_result["statistics"]["documents_count"] == 2
        
        # 查询知识库
        query_results = knowledge_base_service.query(
            query_str="测试",
            top_k=5,
        )
        
        # 验证查询结果（可能为空，但不应该出错）
        assert isinstance(query_results, list)
        
        # 获取状态
        status = knowledge_base_service.get_status()
        assert status["status"] == KnowledgeBaseStatus.READY.value
        
        # 更新知识库
        update_result = knowledge_base_service.update_knowledge_base(
            directories=mock_preprocessed_dirs[:1],
        )
        
        assert update_result["status"] == KnowledgeBaseStatus.READY.value
        assert update_result["statistics"]["new_documents_count"] == 1
        
        # 删除知识库
        delete_result = knowledge_base_service.delete_knowledge_base()
        assert delete_result["status"] == "deleted"

    def test_end_to_end_workflow_without_llamaindex(self, knowledge_base_service, mock_preprocessed_dirs):
        """测试没有LlamaIndex时的端到端工作流程"""
        if LLAMA_INDEX_AVAILABLE:
            pytest.skip("LlamaIndex is available, use the other test")
            
        # 创建知识库
        create_result = knowledge_base_service.create_knowledge_base(
            name="end_to_end_test_kb_no_llamaindex",
            directories=mock_preprocessed_dirs,
            description="端到端测试知识库（无LlamaIndex）",
        )
        
        assert create_result["status"] == KnowledgeBaseStatus.READY.value
        assert create_result["statistics"]["documents_count"] == 2
        assert create_result["indexes"]["vector"] is False
        assert create_result["indexes"]["bm25"] is True
        assert create_result["indexes"]["metadata"] is True
        
        # 查询知识库（应该只使用BM25和元数据检索）
        query_results = knowledge_base_service.query(
            query_str="测试",
            top_k=5,
        )
        
        # 验证查询结果（可能为空，但不应该出错）
        assert isinstance(query_results, list)
        
        # 获取状态
        status = knowledge_base_service.get_status()
        assert status["status"] == KnowledgeBaseStatus.READY.value
        
        # 更新知识库
        update_result = knowledge_base_service.update_knowledge_base(
            directories=mock_preprocessed_dirs[:1],
        )
        
        assert update_result["status"] == KnowledgeBaseStatus.READY.value
        assert update_result["statistics"]["new_documents_count"] == 1
        
        # 删除知识库
        delete_result = knowledge_base_service.delete_knowledge_base()
        assert delete_result["status"] == "deleted"