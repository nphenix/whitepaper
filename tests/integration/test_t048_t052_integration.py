"""
T048元数据索引构建器与T052文档分块策略集成测试

验证MetadataIndexBuilder能够正确处理DocumentChunkingStrategy输出的Node对象，
并构建有效的元数据索引。
"""

import json
import pytest
from unittest.mock import Mock, patch

from src.infrastructure.indexing.document_chunking import (
    DocumentChunkingStrategy,
    ChunkingConfig,
    ChunkingError,
)
from src.infrastructure.indexing.metadata_index import (
    MetadataIndexBuilder,
    MetadataIndexError,
)
from src.shared.exceptions.storage_exceptions import SQLiteError


class TestT048T052Integration:
    """T048与T052集成测试类"""

    @pytest.fixture
    def sample_nodes(self):
        """创建示例Node对象，模拟MarkdownParser的输出"""
        nodes = []
        
        # 创建第一个章节的节点
        node1 = Mock()
        node1.text = "这是第一章的内容。包含多个句子，用于测试分块功能。"
        node1.metadata = {
            "document_id": "doc_1",
            "section_path": "1",
            "section_title": "第一章",
            "element_type": "paragraph",
            "source": "test.pdf",
            "format": "pdf",
            "pipeline": "mineru",
            "processed_at": "2025-12-20T05:00:00",
            "total_pages": 10,
        }
        nodes.append(node1)
        
        # 创建第二个章节的节点
        node2 = Mock()
        node2.text = "这是第二章的内容。同样包含多个句子，用于验证分块策略的正确性。"
        node2.metadata = {
            "document_id": "doc_1",
            "section_path": "2",
            "section_title": "第二章",
            "element_type": "paragraph",
            "source": "test.pdf",
            "format": "pdf",
            "pipeline": "mineru",
            "processed_at": "2025-12-20T05:00:00",
            "total_pages": 10,
        }
        nodes.append(node2)
        
        # 创建一个标题节点
        node3 = Mock()
        node3.text = "重要标题"
        node3.metadata = {
            "document_id": "doc_1",
            "section_path": "2.1",
            "section_title": "第二章第一节",
            "element_type": "heading",
            "source": "test.pdf",
            "format": "pdf",
            "pipeline": "mineru",
            "processed_at": "2025-12-20T05:00:00",
            "total_pages": 10,
        }
        nodes.append(node3)
        
        return nodes

    @pytest.fixture
    def chunking_config(self):
        """创建分块配置"""
        return ChunkingConfig(
            chunk_size=100,
            chunk_overlap=20,
            split_by_section=True,
            split_by_paragraph=True,
        )

    @pytest.fixture
    def metadata_index(self):
        """创建元数据索引构建器实例"""
        with patch("src.infrastructure.indexing.metadata_index.SQLiteAdapter"):
            return MetadataIndexBuilder("test_metadata")

    def test_chunking_strategy_output_structure(self, sample_nodes, chunking_config):
        """测试文档分块策略输出的结构是否符合预期"""
        with patch("src.infrastructure.indexing.document_chunking.LLAMA_INDEX_AVAILABLE", True):
            with patch("src.infrastructure.indexing.document_chunking.SentenceSplitter") as mock_splitter:
                # 模拟分块结果
                mock_splitter.return_value.split_text.side_effect = [
                    ["这是第一章的内容。", "包含多个句子，用于测试分块功能。"],
                    ["这是第二章的内容。", "同样包含多个句子，", "用于验证分块策略的正确性。"],
                    ["重要标题"],
                ]
                
                strategy = DocumentChunkingStrategy(chunking_config)
                chunked_nodes = strategy.chunk_nodes(sample_nodes)
                
                # 验证分块结果
                assert len(chunked_nodes) == 6  # 2 + 3 + 1
                
                # 验证第一个分块的元数据
                first_chunk = chunked_nodes[0]
                assert first_chunk.metadata["document_id"] == "doc_1"
                assert first_chunk.metadata["section_path"] == "1"
                assert first_chunk.metadata["section_title"] == "第一章"
                assert first_chunk.metadata["element_type"] == "paragraph"
                assert first_chunk.metadata["chunk_index"] == 0
                assert first_chunk.metadata["chunk_index_in_node"] == 0
                assert first_chunk.metadata["original_node_index"] == 0
                assert first_chunk.metadata["paragraph_index"] == 1
                
                # 验证第二个分块的元数据
                second_chunk = chunked_nodes[1]
                assert second_chunk.metadata["document_id"] == "doc_1"
                assert second_chunk.metadata["section_path"] == "1"
                assert second_chunk.metadata["paragraph_index"] == 1  # 同一段落
                assert second_chunk.metadata["chunk_index"] == 1
                assert second_chunk.metadata["chunk_index_in_node"] == 1

    def test_metadata_index_builder_with_chunked_nodes(self, sample_nodes, chunking_config, metadata_index):
        """测试元数据索引构建器处理分块后的Node对象"""
        with patch("src.infrastructure.indexing.document_chunking.LLAMA_INDEX_AVAILABLE", True):
            with patch("src.infrastructure.indexing.document_chunking.SentenceSplitter") as mock_splitter:
                # 模拟分块结果
                mock_splitter.return_value.split_text.side_effect = [
                    ["这是第一章的内容。", "包含多个句子，用于测试分块功能。"],
                    ["这是第二章的内容。", "同样包含多个句子，", "用于验证分块策略的正确性。"],
                    ["重要标题"],
                ]
                
                # 执行分块
                strategy = DocumentChunkingStrategy(chunking_config)
                chunked_nodes = strategy.chunk_nodes(sample_nodes)
                
                # 模拟索引构建
                with patch.object(metadata_index, "_ensure_initialized"):
                    with patch.object(metadata_index.adapter, "bulk_create") as mock_bulk_create:
                        mock_bulk_create.return_value = [
                            {"id": i, "node_id": f"chunk_{i}"} for i in range(len(chunked_nodes))
                        ]
                        
                        # 构建元数据索引
                        result = metadata_index.build_index(chunked_nodes)
                        
                        # 验证结果
                        assert len(result) == 6
                        mock_bulk_create.assert_called_once()
                        
                        # 验证传递给bulk_create的记录
                        call_args = mock_bulk_create.call_args[0][0]
                        assert len(call_args) == 6
                        
                        # 验证第一个记录的元数据
                        first_record = call_args[0]
                        assert first_record["document_id"] == "doc_1"
                        assert first_record["section_path"] == "1"
                        assert first_record["element_type"] == "paragraph"
                        assert first_record["chunk_index"] == 0
                        assert first_record["paragraph_index"] == 1
                        assert "metadata_json" in first_record
                        
                        # 验证JSON元数据
                        metadata_json = json.loads(first_record["metadata_json"])
                        assert metadata_json["document_id"] == "doc_1"
                        assert metadata_json["section_path"] == "1"

    def test_query_chunked_content_by_section(self, sample_nodes, chunking_config, metadata_index):
        """测试按章节查询分块后的内容"""
        with patch("src.infrastructure.indexing.document_chunking.LLAMA_INDEX_AVAILABLE", True):
            with patch("src.infrastructure.indexing.document_chunking.SentenceSplitter") as mock_splitter:
                # 模拟分块结果
                mock_splitter.return_value.split_text.side_effect = [
                    ["这是第一章的内容。", "包含多个句子，用于测试分块功能。"],
                    ["这是第二章的内容。", "同样包含多个句子，", "用于验证分块策略的正确性。"],
                    ["重要标题"],
                ]
                
                # 执行分块
                strategy = DocumentChunkingStrategy(chunking_config)
                chunked_nodes = strategy.chunk_nodes(sample_nodes)
                
                # 模拟查询
                with patch.object(metadata_index, "query") as mock_query:
                    mock_query.return_value = [
                        {"id": 1, "section_path": "1", "chunk_index": 0},
                        {"id": 2, "section_path": "1", "chunk_index": 1},
                    ]
                    
                    # 查询第一章的内容
                    result = metadata_index.query_by_section_path("1")
                    
                    assert len(result) == 2
                    mock_query.assert_called_once_with(
                        filters={"section_path": "1"}, order_by="chunk_index"
                    )

    def test_query_chunked_content_by_element_type(self, sample_nodes, chunking_config, metadata_index):
        """测试按元素类型查询分块后的内容"""
        with patch("src.infrastructure.indexing.document_chunking.LLAMA_INDEX_AVAILABLE", True):
            with patch("src.infrastructure.indexing.document_chunking.SentenceSplitter") as mock_splitter:
                # 模拟分块结果
                mock_splitter.return_value.split_text.side_effect = [
                    ["这是第一章的内容。", "包含多个句子，用于测试分块功能。"],
                    ["这是第二章的内容。", "同样包含多个句子，", "用于验证分块策略的正确性。"],
                    ["重要标题"],
                ]
                
                # 执行分块
                strategy = DocumentChunkingStrategy(chunking_config)
                chunked_nodes = strategy.chunk_nodes(sample_nodes)
                
                # 模拟查询
                with patch.object(metadata_index, "query") as mock_query:
                    mock_query.return_value = [
                        {"id": 1, "element_type": "heading", "section_path": "2.1"},
                    ]
                    
                    # 查询标题类型的内容
                    result = metadata_index.query_by_element_type("heading")
                    
                    assert len(result) == 1
                    assert result[0]["element_type"] == "heading"
                    assert result[0]["section_path"] == "2.1"
                    mock_query.assert_called_once_with(
                        filters={"element_type": "heading"}, limit=None, order_by="chunk_index"
                    )

    def test_query_chunked_content_by_chunk_range(self, sample_nodes, chunking_config, metadata_index):
        """测试按块范围查询分块后的内容"""
        with patch("src.infrastructure.indexing.document_chunking.LLAMA_INDEX_AVAILABLE", True):
            with patch("src.infrastructure.indexing.document_chunking.SentenceSplitter") as mock_splitter:
                # 模拟分块结果
                mock_splitter.return_value.split_text.side_effect = [
                    ["这是第一章的内容。", "包含多个句子，用于测试分块功能。"],
                    ["这是第二章的内容。", "同样包含多个句子，", "用于验证分块策略的正确性。"],
                    ["重要标题"],
                ]
                
                # 执行分块
                strategy = DocumentChunkingStrategy(chunking_config)
                chunked_nodes = strategy.chunk_nodes(sample_nodes)
                
                # 模拟查询
                with patch.object(metadata_index, "_ensure_initialized"):
                    with patch.object(metadata_index.adapter, "execute_custom_query") as mock_execute:
                        mock_execute.return_value = [
                            {"id": 2, "chunk_index": 2, "section_path": "2"},
                            {"id": 3, "chunk_index": 3, "section_path": "2"},
                        ]
                        
                        # 查询第2-4块的内容
                        result = metadata_index.query_by_chunk_range(2, 4)
                        
                        assert len(result) == 2
                        mock_execute.assert_called_once()
                        
                        # 验证SQL查询参数
                        query_call = mock_execute.call_args[0]
                        assert "chunk_index >= ?" in query_call[0]
                        assert "chunk_index <= ?" in query_call[0]
                        assert query_call[1] == (2, 4)

    def test_error_handling_in_integration(self, sample_nodes, chunking_config, metadata_index):
        """测试集成过程中的错误处理"""
        with patch("src.infrastructure.indexing.document_chunking.LLAMA_INDEX_AVAILABLE", True):
            with patch("src.infrastructure.indexing.document_chunking.SentenceSplitter") as mock_splitter:
                # 模拟分块失败
                mock_splitter.return_value.split_text.side_effect = Exception("分块失败")
                
                strategy = DocumentChunkingStrategy(chunking_config)
                
                # 验证分块错误
                with pytest.raises(ChunkingError):
                    strategy.chunk_nodes(sample_nodes)
                
                # 模拟索引构建失败
                with patch.object(metadata_index, "_ensure_initialized"):
                    with patch.object(metadata_index.adapter, "bulk_create") as mock_bulk_create:
                        mock_bulk_create.side_effect = SQLiteError("数据库错误")
                        
                        # 创建一个简单的节点列表用于测试
                        simple_node = Mock()
                        simple_node.id_ = "test_node"
                        simple_node.text = "测试内容"
                        simple_node.metadata = {"test": "metadata"}
                        
                        with pytest.raises(MetadataIndexError):
                            metadata_index.build_index([simple_node])

    def test_end_to_end_integration_workflow(self, sample_nodes, chunking_config, metadata_index):
        """测试端到端集成工作流"""
        with patch("src.infrastructure.indexing.document_chunking.LLAMA_INDEX_AVAILABLE", True):
            with patch("src.infrastructure.indexing.document_chunking.SentenceSplitter") as mock_splitter:
                # 模拟分块结果
                mock_splitter.return_value.split_text.side_effect = [
                    ["这是第一章的内容。", "包含多个句子，用于测试分块功能。"],
                    ["这是第二章的内容。", "同样包含多个句子，", "用于验证分块策略的正确性。"],
                    ["重要标题"],
                ]
                
                # 1. 执行文档分块
                strategy = DocumentChunkingStrategy(chunking_config)
                chunked_nodes = strategy.chunk_nodes(sample_nodes)
                
                # 2. 构建元数据索引
                with patch.object(metadata_index, "_ensure_initialized"):
                    with patch.object(metadata_index.adapter, "bulk_create") as mock_bulk_create:
                        mock_bulk_create.return_value = [
                            {"id": i, "node_id": f"chunk_{i}"} for i in range(len(chunked_nodes))
                        ]
                        
                        index_result = metadata_index.build_index(chunked_nodes)
                        assert len(index_result) == 6
                        
                        # 3. 查询索引
                        with patch.object(metadata_index, "query") as mock_query:
                            mock_query.return_value = [
                                {"id": 1, "section_path": "1", "element_type": "paragraph"},
                                {"id": 2, "section_path": "1", "element_type": "paragraph"},
                            ]
                            
                            # 按章节查询
                            section_result = metadata_index.query_by_section_path("1")
                            assert len(section_result) == 2
                            
                            # 按元素类型查询
                            with patch.object(metadata_index, "query") as mock_query_type:
                                mock_query_type.return_value = [
                                    {"id": 6, "element_type": "heading", "section_path": "2.1"},
                                ]
                                
                                type_result = metadata_index.query_by_element_type("heading")
                                assert len(type_result) == 1
                                assert type_result[0]["element_type"] == "heading"
                                
                        # 4. 更新元数据
                        with patch.object(metadata_index, "get_by_node_id") as mock_get:
                            with patch.object(metadata_index.adapter, "update") as mock_update:
                                mock_get.return_value = {
                                    "id": 1,
                                    "node_id": "chunk_0",
                                    "metadata": {"original": "metadata"},
                                    "metadata_json": '{"original": "metadata"}'
                                }
                                mock_update.return_value = {
                                    "id": 1,
                                    "node_id": "chunk_0",
                                    "metadata_json": '{"original": "metadata", "updated": "field"}'
                                }
                                
                                update_result = metadata_index.update_metadata(
                                    "chunk_0", {"updated": "field"}
                                )
                                assert update_result is not None
                                assert update_result["node_id"] == "chunk_0"


if __name__ == "__main__":
    pytest.main([__file__])