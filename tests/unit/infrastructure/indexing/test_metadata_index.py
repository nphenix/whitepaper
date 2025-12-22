"""
元数据索引构建器单元测试 (T048)

测试MetadataIndexBuilder类的各项功能，包括索引构建、查询、更新和删除操作。
"""

import json
import pytest
from unittest.mock import Mock, patch

from src.infrastructure.indexing.metadata_index import (
    MetadataIndexBuilder,
    MetadataIndexError,
)
from src.shared.exceptions.storage_exceptions import SQLiteError

# 模拟LlamaIndex Node对象
class MockNode:
    """模拟LlamaIndex Node对象"""
    
    def __init__(
        self,
        id_: str,
        text: str,
        metadata: dict = None,
    ):
        self.id_ = id_
        self.text = text
        self.metadata = metadata or {}


class TestMetadataIndexBuilder:
    """元数据索引构建器测试类"""

    @pytest.fixture
    def metadata_index(self):
        """创建元数据索引构建器实例"""
        with patch("src.infrastructure.indexing.metadata_index.SQLiteAdapter"):
            return MetadataIndexBuilder("test_metadata")

    @pytest.fixture
    def sample_nodes(self):
        """创建示例Node对象列表"""
        return [
            MockNode(
                id_="node_1",
                text="这是第一个测试节点的内容",
                metadata={
                    "document_id": "doc_1",
                    "chunk_index": 0,
                    "chunk_index_in_node": 0,
                    "original_node_index": 0,
                    "section_path": "1.1",
                    "section_title": "第一章第一节",
                    "paragraph_index": 1,
                    "element_type": "paragraph",
                    "source": "test.pdf",
                    "format": "pdf",
                    "pipeline": "mineru",
                    "processed_at": "2025-12-20T05:00:00",
                    "total_pages": 10,
                },
            ),
            MockNode(
                id_="node_2",
                text="这是第二个测试节点的内容",
                metadata={
                    "document_id": "doc_1",
                    "chunk_index": 1,
                    "chunk_index_in_node": 0,
                    "original_node_index": 1,
                    "section_path": "1.2",
                    "section_title": "第一章第二节",
                    "paragraph_index": 2,
                    "element_type": "paragraph",
                    "source": "test.pdf",
                    "format": "pdf",
                    "pipeline": "mineru",
                    "processed_at": "2025-12-20T05:00:00",
                    "total_pages": 10,
                },
            ),
            MockNode(
                id_="node_3",
                text="这是第三个测试节点的内容",
                metadata={
                    "document_id": "doc_2",
                    "chunk_index": 0,
                    "chunk_index_in_node": 0,
                    "original_node_index": 0,
                    "section_path": "2.1",
                    "section_title": "第二章第一节",
                    "element_type": "heading",
                    "source": "test2.pdf",
                    "format": "pdf",
                    "pipeline": "mineru",
                    "processed_at": "2025-12-20T05:00:00",
                    "total_pages": 5,
                },
            ),
        ]

    def test_init(self):
        """测试初始化"""
        with patch("src.infrastructure.indexing.metadata_index.SQLiteAdapter"):
            builder = MetadataIndexBuilder("test_table")
            assert builder.table_name == "test_table"
            assert builder.adapter is not None
            assert builder._initialized is False

    def test_ensure_initialized(self, metadata_index):
        """测试表初始化"""
        with patch.object(metadata_index.adapter, "execute_custom_query") as mock_execute:
            metadata_index._ensure_initialized()
            assert metadata_index._initialized is True
            # 验证表创建SQL被执行
            assert mock_execute.call_count >= 2  # 表创建 + 至少一个索引创建

    def test_extract_metadata_from_node(self, metadata_index, sample_nodes):
        """测试从Node对象提取元数据"""
        node = sample_nodes[0]
        metadata = metadata_index._extract_metadata_from_node(node)

        assert metadata["node_id"] == "node_1"
        assert metadata["document_id"] == "doc_1"
        assert metadata["chunk_index"] == 0
        assert metadata["section_path"] == "1.1"
        assert metadata["section_title"] == "第一章第一节"
        assert metadata["element_type"] == "paragraph"
        assert metadata["content_length"] == len(node.text)
        assert metadata["source"] == "test.pdf"
        assert "metadata_json" in metadata

        # 验证JSON元数据包含原始信息
        parsed_metadata = json.loads(metadata["metadata_json"])
        assert parsed_metadata["document_id"] == "doc_1"
        assert parsed_metadata["section_path"] == "1.1"

    def test_build_index_empty_nodes(self, metadata_index):
        """测试构建空节点列表的索引"""
        with patch.object(metadata_index, "_ensure_initialized"):
            result = metadata_index.build_index([])
            assert result == []

    def test_build_index_success(self, metadata_index, sample_nodes):
        """测试成功构建索引"""
        with patch.object(metadata_index, "_ensure_initialized") as mock_init:
            with patch.object(metadata_index.adapter, "bulk_create") as mock_bulk_create:
                mock_bulk_create.return_value = [
                    {"id": 1, "node_id": "node_1"},
                    {"id": 2, "node_id": "node_2"},
                    {"id": 3, "node_id": "node_3"},
                ]

                result = metadata_index.build_index(sample_nodes)

                assert len(result) == 3
                mock_init.assert_called_once()
                mock_bulk_create.assert_called_once()

                # 验证传递给bulk_create的记录格式
                call_args = mock_bulk_create.call_args[0][0]
                assert len(call_args) == 3
                assert call_args[0]["node_id"] == "node_1"
                assert call_args[1]["node_id"] == "node_2"
                assert call_args[2]["node_id"] == "node_3"

    def test_build_index_with_extraction_error(self, metadata_index, sample_nodes):
        """测试构建索引时提取元数据出错"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index, "_extract_metadata_from_node") as mock_extract:
                mock_extract.side_effect = [Exception("提取错误"), None, None]
                with patch.object(metadata_index.adapter, "bulk_create") as mock_bulk_create:
                    mock_bulk_create.return_value = [{"id": 1}]

                    result = metadata_index.build_index(sample_nodes)

                    # 应该只处理2个成功提取的节点
                    assert len(result) == 1
                    assert mock_extract.call_count == 3

    def test_query_no_filters(self, metadata_index):
        """测试无过滤条件的查询"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "list") as mock_list:
                mock_list.return_value = [
                    {"id": 1, "node_id": "node_1", "metadata_json": '{"test": "value"}'}
                ]

                result = metadata_index.query()

                assert len(result) == 1
                assert result[0]["node_id"] == "node_1"
                assert "metadata" in result[0]
                assert result[0]["metadata"]["test"] == "value"

    def test_query_with_filters(self, metadata_index):
        """测试带过滤条件的查询"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "list") as mock_list:
                mock_list.return_value = [{"id": 1, "node_id": "node_1"}]

                filters = {"document_id": "doc_1", "section_path": "1.1"}
                result = metadata_index.query(filters=filters)

                assert len(result) == 1
                mock_list.assert_called_once_with(
                    filters=filters, limit=None, order_by=None
                )

    def test_query_with_metadata_filter(self, metadata_index):
        """测试元数据字段过滤"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "list") as mock_list:
                mock_list.return_value = [{"id": 1, "node_id": "node_1"}]

                filters = {"metadata.custom_field": "custom_value"}
                result = metadata_index.query(filters=filters)

                # 验证元数据过滤器被正确转换
                call_args = mock_list.call_args[1]
                processed_filters = call_args["filters"]
                assert "metadata_json" in processed_filters
                assert "custom_value" in processed_filters["metadata_json"]

    def test_query_by_section_path_exact(self, metadata_index):
        """测试按章节路径精确查询"""
        with patch.object(metadata_index, "query") as mock_query:
            mock_query.return_value = [{"id": 1, "section_path": "1.1"}]

            result = metadata_index.query_by_section_path("1.1", exact_match=True)

            assert len(result) == 1
            mock_query.assert_called_once_with(
                filters={"section_path": "1.1"}, order_by="chunk_index"
            )

    def test_query_by_section_path_prefix(self, metadata_index):
        """测试按章节路径前缀查询"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "execute_custom_query") as mock_execute:
                mock_execute.return_value = [{"id": 1, "section_path": "1.1.1"}]

                result = metadata_index.query_by_section_path("1.1", exact_match=False)

                assert len(result) == 1
                # 验证自定义查询被调用
                mock_execute.assert_called_once()
                query_call = mock_execute.call_args[0]
                assert "1.1%" in query_call[1]  # LIKE模式

    def test_query_by_element_type(self, metadata_index):
        """测试按元素类型查询"""
        with patch.object(metadata_index, "query") as mock_query:
            mock_query.return_value = [{"id": 1, "element_type": "paragraph"}]

            result = metadata_index.query_by_element_type("paragraph", limit=10)

            assert len(result) == 1
            mock_query.assert_called_once_with(
                filters={"element_type": "paragraph"}, limit=10, order_by="chunk_index"
            )

    def test_query_by_document_id(self, metadata_index):
        """测试按文档ID查询"""
        with patch.object(metadata_index, "query") as mock_query:
            mock_query.return_value = [{"id": 1, "document_id": "doc_1"}]

            result = metadata_index.query_by_document_id("doc_1")

            assert len(result) == 1
            mock_query.assert_called_once_with(
                filters={"document_id": "doc_1"}, order_by="chunk_index"
            )

    def test_query_by_chunk_range(self, metadata_index):
        """测试按块范围查询"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "execute_custom_query") as mock_execute:
                mock_execute.return_value = [{"id": 1, "chunk_index": 1}]

                result = metadata_index.query_by_chunk_range(1, 5)

                assert len(result) == 1
                # 验证自定义查询被调用
                mock_execute.assert_called_once()
                query_call = mock_execute.call_args[0]
                assert "chunk_index >= ?" in query_call[0]
                assert "chunk_index <= ?" in query_call[0]
                assert query_call[1] == (1, 5)  # 参数

    def test_query_by_chunk_range_with_document_id(self, metadata_index):
        """测试按块范围和文档ID查询"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "execute_custom_query") as mock_execute:
                mock_execute.return_value = [{"id": 1, "chunk_index": 1}]

                result = metadata_index.query_by_chunk_range(1, 5, document_id="doc_1")

                assert len(result) == 1
                query_call = mock_execute.call_args[0]
                assert "document_id = ?" in query_call[0]
                assert query_call[1] == (1, 5, "doc_1")  # 参数

    def test_get_by_node_id_exists(self, metadata_index):
        """测试根据节点ID获取存在的记录"""
        with patch.object(metadata_index.adapter, "get_by_id") as mock_get:
            mock_get.return_value = {
                "id": 1,
                "node_id": "node_1",
                "metadata_json": '{"test": "value"}'
            }

            result = metadata_index.get_by_node_id("node_1")

            assert result is not None
            assert result["node_id"] == "node_1"
            assert "metadata" in result
            assert result["metadata"]["test"] == "value"

    def test_get_by_node_id_not_exists(self, metadata_index):
        """测试根据节点ID获取不存在的记录"""
        with patch.object(metadata_index.adapter, "get_by_id") as mock_get:
            mock_get.return_value = None

            result = metadata_index.get_by_node_id("nonexistent")

            assert result is None

    def test_update_metadata_success(self, metadata_index):
        """测试成功更新元数据"""
        with patch.object(metadata_index, "get_by_node_id") as mock_get:
            with patch.object(metadata_index.adapter, "update") as mock_update:
                # 模拟现有记录
                mock_get.return_value = {
                    "id": 1,
                    "node_id": "node_1",
                    "metadata": {"existing": "value"},
                    "metadata_json": '{"existing": "value"}'
                }

                # 模拟更新后的记录
                mock_update.return_value = {
                    "id": 1,
                    "node_id": "node_1",
                    "metadata_json": '{"existing": "value", "new": "field"}'
                }

                result = metadata_index.update_metadata(
                    "node_1", {"new": "field", "section_path": "1.2"}
                )

                assert result is not None
                assert result["node_id"] == "node_1"
                assert "metadata" in result
                assert result["metadata"]["new"] == "field"
                assert result["metadata"]["existing"] == "value"

                # 验证更新调用
                update_call = mock_update.call_args[0][1]
                assert "new" in update_call["metadata_json"]
                assert update_call["section_path"] == "1.2"

    def test_update_metadata_not_exists(self, metadata_index):
        """测试更新不存在的节点元数据"""
        with patch.object(metadata_index, "get_by_node_id") as mock_get:
            mock_get.return_value = None

            result = metadata_index.update_metadata("nonexistent", {"new": "field"})

            assert result is None

    def test_delete_by_node_id_success(self, metadata_index):
        """测试成功删除节点记录"""
        with patch.object(metadata_index.adapter, "delete") as mock_delete:
            mock_delete.return_value = True

            result = metadata_index.delete_by_node_id("node_1")

            assert result is True
            mock_delete.assert_called_once_with("node_1")

    def test_delete_by_node_id_not_exists(self, metadata_index):
        """测试删除不存在的节点记录"""
        with patch.object(metadata_index.adapter, "delete") as mock_delete:
            mock_delete.return_value = False

            result = metadata_index.delete_by_node_id("nonexistent")

            assert result is False

    def test_delete_by_document_id_success(self, metadata_index):
        """测试成功删除文档的所有记录"""
        with patch.object(metadata_index.adapter, "connection_manager") as mock_conn:
            mock_cursor = Mock()
            mock_cursor.rowcount = 3
            mock_conn.transaction.return_value.__enter__.return_value = mock_cursor

            result = metadata_index.delete_by_document_id("doc_1")

            assert result == 3
            # 验证SQL查询
            sql_call = mock_cursor.execute.call_args[0][0]
            assert "DELETE FROM" in sql_call
            assert "WHERE document_id = ?" in sql_call

    def test_get_stats(self, metadata_index):
        """测试获取索引统计信息"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "get_table_info") as mock_table_info:
                with patch.object(metadata_index.adapter, "execute_custom_query") as mock_execute:
                    # 模拟表信息
                    mock_table_info.return_value = {
                        "record_count": 10,
                        "columns": [{"name": "id"}, {"name": "node_id"}],
                    }

                    # 模拟统计查询结果
                    mock_execute.side_effect = [
                        [{"document_id": "doc_1", "count": 5}],
                        [{"section_path": "1.1", "count": 3}],
                        [{"element_type": "paragraph", "count": 7}],
                    ]

                    result = metadata_index.get_stats()

                    assert result["table_name"] == "test_metadata"
                    assert result["total_records"] == 10
                    assert len(result["documents"]) == 1
                    assert result["documents"][0]["document_id"] == "doc_1"
                    assert len(result["top_sections"]) == 1
                    assert result["top_sections"][0]["section_path"] == "1.1"
                    assert len(result["element_types"]) == 1
                    assert result["element_types"][0]["element_type"] == "paragraph"

    def test_rebuild_index(self, metadata_index, sample_nodes):
        """测试重建索引"""
        with patch.object(metadata_index, "_ensure_initialized") as mock_init:
            with patch.object(metadata_index, "build_index") as mock_build:
                with patch.object(metadata_index.adapter, "execute_custom_query") as mock_execute:
                    mock_build.return_value = [{"id": 1, "node_id": "node_1"}]

                    result = metadata_index.rebuild_index(sample_nodes)

                    # 验证表被删除
                    drop_call = mock_execute.call_args_list[0]
                    assert "DROP TABLE" in drop_call[0][0]

                    # 验证表被重新初始化
                    assert mock_init.call_count == 2  # 一次在rebuild开始，一次在build_index中

                    # 验证索引被重新构建
                    mock_build.assert_called_once_with(sample_nodes)
                    assert len(result) == 1

    def test_create_adapter_static_method(self):
        """测试静态创建方法"""
        with patch("src.infrastructure.indexing.metadata_index.SQLiteAdapter"):
            adapter = MetadataIndexBuilder.create_adapter(
                "static_table", connection_manager=None
            )
            assert adapter.table_name == "static_table"
            assert adapter.adapter is not None

    def test_error_handling_in_build_index(self, metadata_index, sample_nodes):
        """测试构建索引时的错误处理"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "bulk_create") as mock_bulk_create:
                mock_bulk_create.side_effect = SQLiteError("数据库错误")

                with pytest.raises(MetadataIndexError):
                    metadata_index.build_index(sample_nodes)

    def test_error_handling_in_query(self, metadata_index):
        """测试查询时的错误处理"""
        with patch.object(metadata_index, "_ensure_initialized"):
            with patch.object(metadata_index.adapter, "list") as mock_list:
                mock_list.side_effect = SQLiteError("数据库错误")

                with pytest.raises(MetadataIndexError):
                    metadata_index.query()

    def test_error_handling_in_update(self, metadata_index):
        """测试更新时的错误处理"""
        with patch.object(metadata_index, "get_by_node_id") as mock_get:
            mock_get.return_value = {"id": 1, "metadata": {}}
            with patch.object(metadata_index.adapter, "update") as mock_update:
                mock_update.side_effect = SQLiteError("数据库错误")

                with pytest.raises(MetadataIndexError):
                    metadata_index.update_metadata("node_1", {"new": "field"})

    def test_error_handling_in_delete(self, metadata_index):
        """测试删除时的错误处理"""
        with patch.object(metadata_index.adapter, "delete") as mock_delete:
            mock_delete.side_effect = SQLiteError("数据库错误")

            with pytest.raises(MetadataIndexError):
                metadata_index.delete_by_node_id("node_1")


if __name__ == "__main__":
    pytest.main([__file__])