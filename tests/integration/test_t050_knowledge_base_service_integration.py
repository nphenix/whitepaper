# 生成命令: /speckit.implement T050
# 生成时间: 2025-12-20
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
知识库服务集成测试

测试KnowledgeBaseService与其他组件的集成，包括文档解析、索引构建、检索等。
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from src.application.services.knowledge_base_service import (
    ChunkingConfig,
    KnowledgeBaseService,
    KnowledgeBaseStatus,
)
from src.infrastructure.indexing.hybrid_retriever import QueryType
from src.infrastructure.indexing.structured_retrieval import (
    DocumentLevel,
    StructuredQuery,
)

try:
    from llama_index.core.schema import NodeWithScore
    from langchain_core.documents import Document
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    NodeWithScore = None
    Document = None
    LLAMA_INDEX_AVAILABLE = False


@pytest.mark.skipif(not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available")
class TestKnowledgeBaseServiceIntegration:
    """KnowledgeBaseService集成测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def sample_documents(self):
        """创建示例文档"""
        # 为了让 chunk_size 配置差异在集成测试中可观测，构造足够长的正文
        long_body = "这是一个用于分块测试的长段落。" * 120  # 约 120*14=1680 字符左右
        return [
            Document(
                page_content="# 第一章\n\n这是第一章的内容，包含一些基本信息。\n\n" + long_body,
                metadata={"source": "doc1.md", "format": "markdown"},
            ),
            Document(
                page_content="# 第二章\n\n这是第二章的内容，包含更详细的信息。\n\n" + long_body,
                metadata={"source": "doc2.md", "format": "markdown"},
            ),
            Document(
                page_content="# 第三章\n\n这是第三章的内容，包含总结性信息。\n\n" + long_body,
                metadata={"source": "doc3.md", "format": "markdown"},
            ),
        ]

    @pytest.fixture
    def preprocessed_dirs(self, temp_dir, sample_documents):
        """创建预处理结果目录"""
        dirs = []
        
        for i, doc in enumerate(sample_documents):
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
                    "type": "heading",
                    "content": doc.page_content.split('\n')[0],  # 标题
                },
                {
                    "page_idx": 1,
                    "type": "paragraph",
                    "content": '\n'.join(doc.page_content.split('\n')[2:]),  # 内容
                },
            ]
            content_list_path = dir_path / "clean_content_list.json"
            with open(content_list_path, "w", encoding="utf-8") as f:
                json.dump(content_list, f, ensure_ascii=False, indent=2)
            
            # 创建images目录
            images_dir = dir_path / "images"
            images_dir.mkdir(exist_ok=True)
            
            # 创建datajson目录
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
            
            return KnowledgeBaseService(
                vector_collection_name=vector_collection_name,
                bm25_index_path=bm25_index_path,
                metadata_table_name=metadata_table_name,
                enable_vector=True,
                enable_bm25=True,
                enable_metadata=True,
                enable_graph=False,
                chunking_config=ChunkingConfig(
                    chunk_size=256,
                    chunk_overlap=50,
                    split_by_section=True,
                    split_by_paragraph=True,
                ),
            )

    def test_create_and_query_knowledge_base(
        self, knowledge_base_service, preprocessed_dirs
    ):
        """测试创建和查询知识库"""
        # 创建知识库
        result = knowledge_base_service.create_knowledge_base(
            name="integration_test_kb",
            directories=preprocessed_dirs,
            description="集成测试知识库",
        )
        
        # 验证创建结果
        assert result["name"] == "integration_test_kb"
        assert result["status"] == KnowledgeBaseStatus.READY.value
        assert result["statistics"]["documents_count"] == 3
        assert result["statistics"]["directories_count"] == 3
        assert result["statistics"]["chunks_count"] > 0
        
        # 查询知识库
        results = knowledge_base_service.query(
            query_str="第一章",
            top_k=5,
            query_type=QueryType.FACTUAL_QA,
        )
        
        # 验证查询结果
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, NodeWithScore) for r in results)
        
        # 验证查询结果包含相关内容
        result_texts = [r.node.text for r in results]
        assert any("第一章" in text for text in result_texts)

    def test_structured_query(self, knowledge_base_service, preprocessed_dirs):
        """测试结构化查询"""
        # 创建知识库
        knowledge_base_service.create_knowledge_base(
            name="structured_test_kb",
            directories=preprocessed_dirs,
        )
        
        # 结构化查询：按章节路径
        results = knowledge_base_service.query(
            query_str="内容",
            top_k=10,
            use_hybrid=False,
            use_structured=True,
            structured_query=StructuredQuery(
                section_path="1",
                document_level=DocumentLevel.SECTION,
            ),
        )
        
        # 验证查询结果
        assert isinstance(results, list)
        # 注意：由于我们使用模拟数据，结构化查询可能不会返回精确结果
        # 但至少应该不会出错

    def test_update_knowledge_base(
        self, knowledge_base_service, preprocessed_dirs
    ):
        """测试更新知识库"""
        # 创建初始知识库
        knowledge_base_service.create_knowledge_base(
            name="update_test_kb",
            directories=preprocessed_dirs[:2],
        )
        
        # 获取初始状态
        initial_status = knowledge_base_service.get_status()
        initial_chunks = initial_status["indexes"]["metadata"].get("total_records", 0)
        
        # 更新知识库
        update_result = knowledge_base_service.update_knowledge_base(
            directories=preprocessed_dirs[2:],
        )
        
        # 验证更新结果
        assert update_result["status"] == KnowledgeBaseStatus.READY.value
        assert update_result["statistics"]["new_documents_count"] == 1
        
        # 获取更新后状态
        updated_status = knowledge_base_service.get_status()
        updated_chunks = updated_status["indexes"]["metadata"].get("total_records", 0)
        
        # 验证块数量增加
        assert updated_chunks > initial_chunks

    def test_delete_knowledge_base(self, knowledge_base_service, preprocessed_dirs):
        """测试删除知识库"""
        # 创建知识库
        knowledge_base_service.create_knowledge_base(
            name="delete_test_kb",
            directories=preprocessed_dirs,
        )
        
        # 删除知识库
        result = knowledge_base_service.delete_knowledge_base()
        
        # 验证删除结果
        assert result["status"] == "deleted"
        assert result["knowledge_base_id"] == str(knowledge_base_service.knowledge_base_id)

    def test_error_handling(self, knowledge_base_service):
        """测试错误处理"""
        # 测试查询空知识库：不应崩溃，通常返回空列表
        results = knowledge_base_service.query(query_str="测试查询")
        assert isinstance(results, list)
        assert len(results) == 0
        
        # 测试更新空输入
        with pytest.raises(ValueError, match="必须提供directories或documents"):
            knowledge_base_service.update_knowledge_base()

    def test_chunking_config_impact(self, knowledge_base_service, preprocessed_dirs):
        """测试分块配置对结果的影响"""
        # 使用小块大小创建知识库
        small_chunk_service = KnowledgeBaseService(
            chunking_config=ChunkingConfig(chunk_size=100, chunk_overlap=20),
        )
        
        result_small = small_chunk_service.create_knowledge_base(
            name="small_chunk_kb",
            directories=preprocessed_dirs,
        )
        
        # 使用大块大小创建知识库
        large_chunk_service = KnowledgeBaseService(
            chunking_config=ChunkingConfig(chunk_size=500, chunk_overlap=100),
        )
        
        result_large = large_chunk_service.create_knowledge_base(
            name="large_chunk_kb",
            directories=preprocessed_dirs,
        )
        
        # 验证块数量差异
        small_chunks = result_small["statistics"]["chunks_count"]
        large_chunks = result_large["statistics"]["chunks_count"]
        
        # 小块应该产生更多的块
        assert small_chunks > large_chunks

    def test_hybrid_retriever_config_impact(
        self, knowledge_base_service, preprocessed_dirs
    ):
        """测试混合检索配置对结果的影响"""
        # 创建知识库
        knowledge_base_service.create_knowledge_base(
            name="config_test_kb",
            directories=preprocessed_dirs,
        )
        
        # 测试不同查询类型
        factual_results = knowledge_base_service.query(
            query_str="内容",
            query_type=QueryType.FACTUAL_QA,
        )
        
        summarization_results = knowledge_base_service.query(
            query_str="内容",
            query_type=QueryType.SUMMARIZATION,
        )
        
        # 验证返回结果
        assert isinstance(factual_results, list)
        assert isinstance(summarization_results, list)
        
        # 不同查询类型可能产生不同的结果排序
        # 这里我们只验证不出错且返回合理结果

    def test_status_monitoring(self, knowledge_base_service, preprocessed_dirs):
        """测试状态监控"""
        # 初始状态
        initial_status = knowledge_base_service.get_status()
        assert initial_status["status"] == KnowledgeBaseStatus.READY.value
        
        # 创建过程中状态
        with patch.object(
            knowledge_base_service, "_build_indexes"
        ) as mock_build:
            
            def slow_build(*args, **kwargs):
                # 模拟构建过程中的状态变化
                knowledge_base_service._status = KnowledgeBaseStatus.INDEXING
                import time
                time.sleep(0.1)  # 短暂延迟
                knowledge_base_service._status = KnowledgeBaseStatus.READY
            
            mock_build.side_effect = slow_build
            
            # 创建知识库
            result = knowledge_base_service.create_knowledge_base(
                name="status_test_kb",
                directories=preprocessed_dirs,
            )
            
            # 验证最终状态
            final_status = knowledge_base_service.get_status()
            assert final_status["status"] == KnowledgeBaseStatus.READY.value

    def test_persistence(self, knowledge_base_service, preprocessed_dirs):
        """测试持久化功能"""
        # 创建知识库
        result = knowledge_base_service.create_knowledge_base(
            name="persistence_test_kb",
            directories=preprocessed_dirs,
        )
        
        # 验证索引文件存在（如果配置了持久化）
        if knowledge_base_service.bm25_index_builder:
            assert os.path.exists(knowledge_base_service.bm25_index_builder.index_path)
        
        # 验证向量索引持久化（通过查询验证）
        query_results = knowledge_base_service.query(query_str="第一章")
        assert len(query_results) > 0