# 生成命令: T013 Chroma 向量存储适配器和连接管理
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
Chroma 适配器测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.storage.chroma.adapter import (
    BaseVectorRepository,
    ChromaAdapter,
)
from src.shared.exceptions.storage_exceptions import ChromaError


class TestBaseVectorRepository:
    """基础向量仓储接口测试类"""

    def test_interface_methods(self):
        """测试接口方法定义"""
        # 确保所有抽象方法都已定义
        abstract_methods = BaseVectorRepository.__abstractmethods__
        expected_methods = {
            "add",
            "get",
            "query",
            "update",
            "delete",
            "count",
        }

        assert abstract_methods == expected_methods


class TestChromaAdapter:
    """Chroma 适配器测试类"""

    def test_init_with_default_values(self):
        """测试使用默认值初始化"""
        with (
            patch(
                "src.infrastructure.storage.chroma.adapter.get_connection_manager"
            ) as mock_manager,
            patch(
                "src.infrastructure.storage.chroma.adapter.get_config"
            ) as mock_config,
        ):
            # 模拟连接管理器
            mock_manager_instance = MagicMock()
            mock_manager.return_value = mock_manager_instance

            # 模拟配置
            mock_config.return_value.embedding.provider = "dashscope"

            with patch(
                "src.infrastructure.storage.chroma.adapter.embedding_functions.DefaultEmbeddingFunction"
            ) as mock_embedding:
                mock_embedding.return_value = MagicMock()

                adapter = ChromaAdapter()

                assert adapter.collection_name is None
                assert adapter.connection_manager == mock_manager_instance
                assert adapter.auto_create_collection is True
                assert adapter.embedding_function == mock_embedding.return_value

    def test_init_with_custom_values(self):
        """测试使用自定义值初始化"""
        mock_manager = MagicMock()
        mock_embedding = MagicMock()

        adapter = ChromaAdapter(
            collection_name="test_collection",
            connection_manager=mock_manager,
            embedding_function=mock_embedding,
            auto_create_collection=False,
        )

        assert adapter.collection_name == "test_collection"
        assert adapter.connection_manager == mock_manager
        assert adapter.auto_create_collection is False
        assert adapter.embedding_function == mock_embedding

    def test_get_default_embedding_function_dashscope(self):
        """测试获取默认嵌入函数 - 阿里云百炼"""
        with (
            patch(
                "src.infrastructure.storage.chroma.adapter.get_config"
            ) as mock_config,
            patch(
                "src.infrastructure.storage.chroma.adapter.embedding_functions.DefaultEmbeddingFunction"
            ) as mock_embedding,
        ):
            # 模拟配置
            mock_config.return_value.embedding.provider = "dashscope"
            mock_embedding.return_value = MagicMock()

            adapter = ChromaAdapter()
            embedding_function = adapter._get_default_embedding_function()

            assert embedding_function == mock_embedding.return_value

    def test_get_default_embedding_function_openai(self):
        """测试获取默认嵌入函数 - OpenAI"""
        with (
            patch(
                "src.infrastructure.storage.chroma.adapter.get_config"
            ) as mock_config,
            patch(
                "src.infrastructure.storage.chroma.adapter.embedding_functions.OpenAIEmbeddingFunction"
            ) as mock_embedding,
        ):
            # 模拟配置
            mock_config.return_value.embedding.provider = "openai"
            mock_config.return_value.embedding.api_key = "test_key"
            mock_config.return_value.embedding.model_name = "text-embedding-ada-002"
            mock_embedding.return_value = MagicMock()

            adapter = ChromaAdapter()
            # 重置 mock,因为构造函数已经调用了一次
            mock_embedding.reset_mock()
            embedding_function = adapter._get_default_embedding_function()

            assert embedding_function == mock_embedding.return_value
            mock_embedding.assert_called_once_with(
                api_key="test_key",
                model_name="text-embedding-ada-002",
            )

    def test_add_with_embeddings(self):
        """测试添加向量 - 提供向量"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        metadatas = [{"title": "doc1"}, {"title": "doc2"}]

        result = adapter.add(ids, embeddings, metadatas)

        assert result == ids
        mock_collection.add.assert_called_once_with(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=None,
        )
        # 检查是否添加了时间戳
        for metadata in metadatas:
            assert "created_at" in metadata

    def test_add_with_documents(self):
        """测试添加向量 - 提供文档"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        documents = ["doc1", "doc2"]

        result = adapter.add(ids, documents=documents)

        assert result == ids
        mock_collection.add.assert_called_once()
        _args, kwargs = mock_collection.add.call_args

        assert kwargs["ids"] == ids
        assert kwargs["documents"] == documents
        assert kwargs["embeddings"] is None
        # 检查是否添加了时间戳
        for metadata in kwargs["metadatas"]:
            assert "created_at" in metadata

    def test_add_validation_error_empty_ids(self):
        """测试添加向量 - ID列表为空"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="ID列表不能为空"):
            adapter.add([])

    def test_add_validation_error_no_embeddings_or_documents(self):
        """测试添加向量 - 没有提供向量或文档"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="必须提供向量或文档"):
            adapter.add(["id1"])

    def test_add_validation_error_mismatched_embeddings(self):
        """测试添加向量 - 向量数量与ID数量不匹配"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="向量数量必须与ID数量相同"):
            adapter.add(["id1", "id2"], embeddings=[[0.1, 0.2]])

    def test_add_validation_error_mismatched_documents(self):
        """测试添加向量 - 文档数量与ID数量不匹配"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="文档数量必须与ID数量相同"):
            adapter.add(["id1", "id2"], documents=["doc1"])

    def test_add_validation_error_mismatched_metadatas(self):
        """测试添加向量 - 元数据数量与ID数量不匹配"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="元数据数量必须与ID数量相同"):
            adapter.add(
                ["id1", "id2"],
                embeddings=[[0.1, 0.2], [0.3, 0.4]],
                metadatas=[{"title": "doc1"}],
            )

    @pytest.mark.asyncio
    async def test_add_async_with_embeddings(self):
        """测试异步添加向量 - 提供向量"""
        mock_manager = MagicMock()
        mock_collection = AsyncMock()
        mock_manager.get_async_collection.return_value.__aenter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        metadatas = [{"title": "doc1"}, {"title": "doc2"}]

        result = await adapter.add_async(ids, embeddings, metadatas)

        assert result == ids
        mock_collection.add.assert_called_once_with(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=None,
        )
        # 检查是否添加了时间戳
        for metadata in metadatas:
            assert "created_at" in metadata

    def test_get(self):
        """测试获取向量"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "ids": ["id1", "id2"],
            "metadatas": [{"title": "doc1"}, {"title": "doc2"}],
        }
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        result = adapter.get(ids=["id1", "id2"], where={"title": "doc1"}, limit=10)

        assert result["ids"] == ["id1", "id2"]
        assert len(result["metadatas"]) == 2
        mock_collection.get.assert_called_once_with(
            ids=["id1", "id2"],
            where={"title": "doc1"},
            limit=10,
            offset=None,
        )

    @pytest.mark.asyncio
    async def test_get_async(self):
        """测试异步获取向量"""
        mock_manager = MagicMock()
        mock_collection = AsyncMock()
        mock_collection.get.return_value = {
            "ids": ["id1", "id2"],
            "metadatas": [{"title": "doc1"}, {"title": "doc2"}],
        }
        mock_manager.get_async_collection.return_value.__aenter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        result = await adapter.get_async(
            ids=["id1", "id2"], where={"title": "doc1"}, limit=10
        )

        assert result["ids"] == ["id1", "id2"]
        assert len(result["metadatas"]) == 2
        mock_collection.get.assert_called_once_with(
            ids=["id1", "id2"],
            where={"title": "doc1"},
            limit=10,
            offset=None,
        )

    def test_query_with_embeddings(self):
        """测试查询向量 - 提供查询向量"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [[{"title": "doc1"}, {"title": "doc2"}]],
        }
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        query_embeddings = [[0.1, 0.2, 0.3]]
        result = adapter.query(
            query_embeddings=query_embeddings, n_results=5, where={"type": "test"}
        )

        assert result["ids"] == [["id1", "id2"]]
        assert result["distances"] == [[0.1, 0.2]]
        mock_collection.query.assert_called_once_with(
            query_embeddings=query_embeddings,
            query_texts=None,
            n_results=5,
            where={"type": "test"},
            include=["metadatas", "documents", "distances"],
        )

    def test_query_with_texts(self):
        """测试查询向量 - 提供查询文本"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [[{"title": "doc1"}, {"title": "doc2"}]],
        }
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        query_texts = ["query text"]
        result = adapter.query(query_texts=query_texts, n_results=5)

        assert result["ids"] == [["id1", "id2"]]
        mock_collection.query.assert_called_once_with(
            query_embeddings=None,
            query_texts=query_texts,
            n_results=5,
            where=None,
            include=["metadatas", "documents", "distances"],
        )

    def test_query_validation_error_no_query(self):
        """测试查询向量 - 没有提供查询向量或文本"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="必须提供查询向量或查询文本"):
            adapter.query()

    def test_query_validation_error_both_query(self):
        """测试查询向量 - 同时提供查询向量和文本"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="不能同时提供查询向量和查询文本"):
            adapter.query(query_embeddings=[[0.1, 0.2]], query_texts=["query"])

    @pytest.mark.asyncio
    async def test_query_async_with_embeddings(self):
        """测试异步查询向量 - 提供查询向量"""
        mock_manager = MagicMock()
        mock_collection = AsyncMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [[{"title": "doc1"}, {"title": "doc2"}]],
        }
        mock_manager.get_async_collection.return_value.__aenter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        query_embeddings = [[0.1, 0.2, 0.3]]
        result = await adapter.query_async(
            query_embeddings=query_embeddings, n_results=5
        )

        assert result["ids"] == [["id1", "id2"]]
        mock_collection.query.assert_called_once_with(
            query_embeddings=query_embeddings,
            query_texts=None,
            n_results=5,
            where=None,
            include=["metadatas", "documents", "distances"],
        )

    def test_update(self):
        """测试更新向量"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        metadatas = [{"title": "doc1"}, {"title": "doc2"}]

        result = adapter.update(ids, embeddings, metadatas)

        assert result is True
        mock_collection.update.assert_called_once()
        _args, kwargs = mock_collection.update.call_args

        assert kwargs["ids"] == ids
        assert kwargs["embeddings"] == embeddings
        # 检查是否添加了时间戳
        for metadata in kwargs["metadatas"]:
            assert "updated_at" in metadata

    def test_update_validation_error_empty_ids(self):
        """测试更新向量 - ID列表为空"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="ID列表不能为空"):
            adapter.update([])

    def test_update_validation_error_no_data(self):
        """测试更新向量 - 没有提供任何数据"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="必须提供向量、元数据或文档"):
            adapter.update(["id1"])

    @pytest.mark.asyncio
    async def test_update_async(self):
        """测试异步更新向量"""
        mock_manager = MagicMock()
        mock_collection = AsyncMock()
        mock_manager.get_async_collection.return_value.__aenter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]

        result = await adapter.update_async(ids, embeddings)

        assert result is True
        mock_collection.update.assert_called_once()
        _args, kwargs = mock_collection.update.call_args

        assert kwargs["ids"] == ids
        assert kwargs["embeddings"] == embeddings
        # 检查是否添加了时间戳
        for metadata in kwargs["metadatas"]:
            assert "updated_at" in metadata

    def test_delete_with_ids(self):
        """测试删除向量 - 提供ID"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        result = adapter.delete(ids=ids)

        assert result is True
        mock_collection.delete.assert_called_once_with(
            ids=ids, where=None, where_document=None
        )

    def test_delete_with_where(self):
        """测试删除向量 - 提供过滤条件"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        where = {"type": "test"}
        result = adapter.delete(where=where)

        assert result is True
        mock_collection.delete.assert_called_once_with(
            ids=None, where=where, where_document=None
        )

    def test_delete_validation_error_no_criteria(self):
        """测试删除向量 - 没有提供删除条件"""
        adapter = ChromaAdapter()

        with pytest.raises(ValueError, match="必须提供ID、过滤条件或文档过滤条件"):
            adapter.delete()

    @pytest.mark.asyncio
    async def test_delete_async(self):
        """测试异步删除向量"""
        mock_manager = MagicMock()
        mock_collection = AsyncMock()
        mock_manager.get_async_collection.return_value.__aenter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        result = await adapter.delete_async(ids=ids)

        assert result is True
        mock_collection.delete.assert_called_once_with(
            ids=ids, where=None, where_document=None
        )

    def test_count(self):
        """测试统计向量数量"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        result = adapter.count()

        assert result == 100
        mock_collection.count.assert_called_once()

    @pytest.mark.asyncio
    async def test_count_async(self):
        """测试异步统计向量数量"""
        mock_manager = MagicMock()
        mock_collection = AsyncMock()
        mock_collection.count.return_value = 100
        mock_manager.get_async_collection.return_value.__aenter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        result = await adapter.count_async()

        assert result == 100
        mock_collection.count.assert_called_once()

    def test_upsert(self):
        """测试插入或更新向量"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]

        result = adapter.upsert(ids, embeddings)

        assert result == ids
        mock_collection.upsert.assert_called_once()
        _args, kwargs = mock_collection.upsert.call_args

        assert kwargs["ids"] == ids
        assert kwargs["embeddings"] == embeddings
        # 检查是否添加了时间戳
        for metadata in kwargs["metadatas"]:
            assert "created_at" in metadata
            assert "updated_at" in metadata

    @pytest.mark.asyncio
    async def test_upsert_async(self):
        """测试异步插入或更新向量"""
        mock_manager = MagicMock()
        mock_collection = AsyncMock()
        mock_manager.get_async_collection.return_value.__aenter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        ids = ["id1", "id2"]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]

        result = await adapter.upsert_async(ids, embeddings)

        assert result == ids
        mock_collection.upsert.assert_called_once()
        _args, kwargs = mock_collection.upsert.call_args

        assert kwargs["ids"] == ids
        assert kwargs["embeddings"] == embeddings
        # 检查是否添加了时间戳
        for metadata in kwargs["metadatas"]:
            assert "created_at" in metadata
            assert "updated_at" in metadata

    def test_get_collection_info(self):
        """测试获取集合信息"""
        mock_manager = MagicMock()
        mock_manager.get_collection_info.return_value = {
            "name": "test_collection",
            "count": 100,
        }

        adapter = ChromaAdapter(connection_manager=mock_manager)

        result = adapter.get_collection_info()

        assert result["name"] == "test_collection"
        assert result["count"] == 100
        mock_manager.get_collection_info.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_get_collection_info_async(self):
        """测试异步获取集合信息"""
        mock_manager = AsyncMock()
        mock_manager.get_collection_info_async.return_value = {
            "name": "test_collection",
            "count": 100,
        }

        adapter = ChromaAdapter(connection_manager=mock_manager)

        result = await adapter.get_collection_info_async()

        assert result["name"] == "test_collection"
        assert result["count"] == 100
        mock_manager.get_collection_info_async.assert_called_once_with(None)

    def test_peek(self):
        """测试查看样本数据"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.peek.return_value = {
            "ids": ["id1", "id2"],
            "documents": ["doc1", "doc2"],
        }
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        result = adapter.peek(limit=5)

        assert result["ids"] == ["id1", "id2"]
        mock_collection.peek.assert_called_once_with(limit=5)

    @pytest.mark.asyncio
    async def test_peek_async(self):
        """测试异步查看样本数据"""
        mock_manager = MagicMock()
        mock_collection = AsyncMock()
        mock_collection.peek.return_value = {
            "ids": ["id1", "id2"],
            "documents": ["doc1", "doc2"],
        }
        mock_manager.get_async_collection.return_value.__aenter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        result = await adapter.peek_async(limit=5)

        assert result["ids"] == ["id1", "id2"]
        mock_collection.peek.assert_called_once_with(limit=5)

    def test_chroma_error_handling(self):
        """测试Chroma错误处理"""
        mock_manager = MagicMock()
        mock_collection = MagicMock()
        mock_collection.add.side_effect = Exception("Chroma error")
        mock_manager.get_collection.return_value.__enter__.return_value = (
            mock_collection
        )

        adapter = ChromaAdapter(connection_manager=mock_manager)

        with pytest.raises(ChromaError):
            adapter.add(["id1"], embeddings=[[0.1, 0.2]])


class TestGlobalFunctions:
    """全局函数测试类"""

    def test_create_adapter(self):
        """测试创建适配器"""
        mock_embedding = MagicMock()

        with patch(
            "src.infrastructure.storage.chroma.adapter.ChromaAdapter"
        ) as mock_adapter:
            mock_adapter.return_value = MagicMock()

            from src.infrastructure.storage.chroma.adapter import create_adapter

            adapter = create_adapter(
                collection_name="test_collection",
                embedding_function=mock_embedding,
            )

            mock_adapter.assert_called_once_with(
                collection_name="test_collection",
                connection_manager=None,
                embedding_function=mock_embedding,
            )
            assert adapter == mock_adapter.return_value
