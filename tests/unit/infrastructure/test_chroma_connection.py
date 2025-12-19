# 生成命令: T013 Chroma 向量存储适配器和连接管理
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
Chroma 连接管理器测试
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.infrastructure.storage.chroma.connection import (
    ChromaConnectionManager,
    create_connection_manager,
    get_connection_manager,
)
from src.shared.exceptions.storage_exceptions import (
    CustomConnectionError,
)


class TestChromaConnectionManager:
    """Chroma 连接管理器测试类"""

    def test_init_with_default_values(self):
        """测试使用默认值初始化"""
        with patch(
            "src.infrastructure.storage.chroma.connection.get_config"
        ) as mock_config:
            # 模拟配置
            mock_config.return_value.database.chroma_db_path = "data/chroma"
            mock_config.return_value.database.chroma_collection_name = "test_collection"
            mock_config.return_value.database.chroma_persist_directory = "data/chroma"

            manager = ChromaConnectionManager()

            assert manager.db_path.name == "chroma"
            assert manager.collection_name == "test_collection"
            assert manager.persist_directory == "data/chroma"
            assert manager.timeout == 30.0

    def test_init_with_custom_values(self):
        """测试使用自定义值初始化"""
        manager = ChromaConnectionManager(
            db_path="custom/path",
            collection_name="custom_collection",
            persist_directory="custom/persist",
            host="localhost",
            port=8000,
            timeout=60.0,
        )

        assert str(manager.db_path) == "custom\\path"
        assert manager.collection_name == "custom_collection"
        assert str(manager.persist_directory) == "custom\\persist"
        assert manager.host == "localhost"
        assert manager.port == 8000
        assert manager.timeout == 60.0

    def test_ensure_database_directory(self):
        """测试确保数据库目录存在"""
        with (
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.mkdir") as mock_mkdir,
        ):
            manager = ChromaConnectionManager(persist_directory="test/path")
            manager._ensure_database_directory()

            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("chromadb.PersistentClient")
    def test_get_sync_client_local(self, mock_client):
        """测试获取同步本地客户端"""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager(db_path="test/path")
        client = manager._get_sync_client()

        assert client == mock_client_instance
        mock_client.assert_called_once()

    @patch("chromadb.HttpClient")
    def test_get_sync_client_remote(self, mock_client):
        """测试获取同步远程客户端"""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager(host="localhost", port=8000)
        client = manager._get_sync_client()

        assert client == mock_client_instance
        mock_client.assert_called_once_with(
            host="localhost",
            port=8000,
            ssl=False,
            settings=manager._get_client_settings(),
        )

    @patch("chromadb.PersistentClient")
    @pytest.mark.asyncio
    async def test_get_async_client_local(self, mock_client):
        """测试获取异步本地客户端"""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager(db_path="test/path")
        client = await manager._get_async_client()

        assert client == mock_client_instance
        mock_client.assert_called_once()

    @patch("chromadb.HttpClient")
    @pytest.mark.asyncio
    async def test_get_async_client_remote(self, mock_client):
        """测试获取异步远程客户端"""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager(host="localhost", port=8000)
        client = await manager._get_async_client()

        assert client == mock_client_instance
        mock_client.assert_called_once_with(
            host="localhost",
            port=8000,
            ssl=False,
            settings=manager._get_client_settings(),
        )

    @patch("chromadb.PersistentClient")
    def test_get_sync_client_connection_error(self, mock_client):
        """测试同步客户端连接错误"""
        mock_client.side_effect = Exception("Connection failed")

        manager = ChromaConnectionManager()

        with pytest.raises(CustomConnectionError):
            manager._get_sync_client()

    @patch("chromadb.PersistentClient")
    @pytest.mark.asyncio
    async def test_get_async_client_connection_error(self, mock_client):
        """测试异步客户端连接错误"""
        mock_client.side_effect = Exception("Connection failed")

        manager = ChromaConnectionManager()

        with pytest.raises(CustomConnectionError):
            await manager._get_async_client()

    @patch("chromadb.PersistentClient")
    def test_get_collection_existing(self, mock_client):
        """测试获取现有集合"""
        mock_collection = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager()

        with manager.get_collection("test_collection") as collection:
            assert collection == mock_collection

        mock_client_instance.get_collection.assert_called_once_with(
            name="test_collection", embedding_function=None
        )

    @patch("chromadb.PersistentClient")
    def test_get_collection_new(self, mock_client):
        """测试创建新集合"""
        mock_collection = MagicMock()
        mock_client_instance = MagicMock()
        # 第一次调用 get_collection 抛出异常(集合不存在)
        mock_client_instance.get_collection.side_effect = Exception(
            "Collection not found"
        )
        mock_client_instance.create_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager()

        with manager.get_collection("test_collection") as collection:
            assert collection == mock_collection

        mock_client_instance.create_collection.assert_called_once_with(
            name="test_collection", embedding_function=None
        )

    @patch("chromadb.PersistentClient")
    @pytest.mark.asyncio
    async def test_get_async_collection_existing(self, mock_client):
        """测试获取现有异步集合"""
        mock_collection = AsyncMock()
        mock_client_instance = AsyncMock()
        mock_client_instance.get_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager()

        async with manager.get_async_collection("test_collection") as collection:
            assert collection == mock_collection

        mock_client_instance.get_collection.assert_called_once_with(
            name="test_collection", embedding_function=None
        )

    @patch("chromadb.PersistentClient")
    @pytest.mark.asyncio
    async def test_get_async_collection_new(self, mock_client):
        """测试创建新异步集合"""
        mock_collection = AsyncMock()
        mock_client_instance = AsyncMock()
        # 第一次调用 get_collection 抛出异常(集合不存在)
        mock_client_instance.get_collection.side_effect = Exception(
            "Collection not found"
        )
        mock_client_instance.create_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager()

        async with manager.get_async_collection("test_collection") as collection:
            assert collection == mock_collection

        mock_client_instance.create_collection.assert_called_once_with(
            name="test_collection", embedding_function=None
        )

    @patch("chromadb.PersistentClient")
    def test_list_collections(self, mock_client):
        """测试列出集合"""
        mock_collection1 = MagicMock()
        mock_collection1.name = "collection1"
        mock_collection2 = MagicMock()
        mock_collection2.name = "collection2"
        mock_client_instance = MagicMock()
        mock_client_instance.list_collections.return_value = [
            mock_collection1,
            mock_collection2,
        ]
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager()
        collections = manager.list_collections()

        assert collections == ["collection1", "collection2"]
        mock_client_instance.list_collections.assert_called_once()

    @patch("chromadb.PersistentClient")
    @pytest.mark.asyncio
    async def test_list_collections_async(self, mock_client):
        """测试异步列出集合"""
        mock_collection1 = MagicMock()
        mock_collection1.name = "collection1"
        mock_collection2 = MagicMock()
        mock_collection2.name = "collection2"
        mock_client_instance = AsyncMock()
        mock_client_instance.list_collections.return_value = [
            mock_collection1,
            mock_collection2,
        ]
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager()
        collections = await manager.list_collections_async()

        assert collections == ["collection1", "collection2"]
        mock_client_instance.list_collections.assert_called_once()

    @patch("chromadb.PersistentClient")
    def test_delete_collection(self, mock_client):
        """测试删除集合"""
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager()
        result = manager.delete_collection("test_collection")

        assert result is True
        mock_client_instance.delete_collection.assert_called_once_with(
            name="test_collection"
        )

    @patch("chromadb.PersistentClient")
    @pytest.mark.asyncio
    async def test_delete_collection_async(self, mock_client):
        """测试异步删除集合"""
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager()
        result = await manager.delete_collection_async("test_collection")

        assert result is True
        mock_client_instance.delete_collection.assert_called_once_with(
            name="test_collection"
        )

    @patch("chromadb.PersistentClient")
    def test_get_collection_info(self, mock_client):
        """测试获取集合信息"""
        mock_collection = MagicMock()
        mock_collection.count.return_value = 100
        mock_collection.metadata = {"type": "test"}
        mock_collection._embedding_function = MagicMock()
        mock_collection._embedding_function.__class__.__name__ = "TestEmbedding"
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager(persist_directory="test/path")
        with patch.object(manager, "get_collection") as mock_get_collection:
            mock_get_collection.return_value.__enter__.return_value = mock_collection

            info = manager.get_collection_info("test_collection")

            assert info["name"] == "test_collection"
            assert info["count"] == 100
            assert info["metadata"] == {"type": "test"}
            assert info["embedding_function"]["type"] == "TestEmbedding"
            assert info["is_persistent"] is True
            assert info["persist_directory"] == "test\\path"

    @patch("chromadb.PersistentClient")
    @pytest.mark.asyncio
    async def test_get_collection_info_async(self, mock_client):
        """测试异步获取集合信息"""
        mock_collection = AsyncMock()
        mock_collection.count.return_value = 100
        mock_collection.metadata = {"type": "test"}
        mock_collection._embedding_function = MagicMock()
        mock_collection._embedding_function.__class__.__name__ = "TestEmbedding"
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance

        manager = ChromaConnectionManager(persist_directory="test/path")
        with patch.object(manager, "get_async_collection") as mock_get_collection:
            mock_get_collection.return_value.__aenter__.return_value = mock_collection

            info = await manager.get_collection_info_async("test_collection")

            assert info["name"] == "test_collection"
            assert info["count"] == 100
            assert info["metadata"] == {"type": "test"}
            assert info["embedding_function"]["type"] == "TestEmbedding"
            assert info["is_persistent"] is True
            assert info["persist_directory"] == "test\\path"

    def test_get_connection_info(self):
        """测试获取连接信息"""
        manager = ChromaConnectionManager(
            db_path="test/path",
            collection_name="test_collection",
            host="localhost",
            port=8000,
        )

        info = manager.get_connection_info()

        assert info["db_path"] == "test\\path"
        assert info["collection_name"] == "test_collection"
        assert info["host"] == "localhost"
        assert info["port"] == 8000
        assert info["timeout"] == 30.0
        assert info["sync_collections"] == []
        assert info["async_collections"] == []
        assert info["has_sync_client"] is False
        assert info["has_async_client"] is False

    def test_close(self):
        """测试关闭连接"""
        manager = ChromaConnectionManager()
        manager._sync_client = MagicMock()
        manager._collections = {"test": MagicMock()}

        manager.close()

        assert manager._sync_client is None
        assert manager._collections == {}

    @pytest.mark.asyncio
    async def test_aclose(self):
        """测试异步关闭连接"""
        manager = ChromaConnectionManager()
        manager._async_client = MagicMock()
        manager._async_collections = {"test": MagicMock()}

        await manager.aclose()

        assert manager._async_client is None
        assert manager._async_collections == {}

    def test_context_manager(self):
        """测试上下文管理器"""
        manager = ChromaConnectionManager()
        manager._sync_client = MagicMock()
        manager._collections = {"test": MagicMock()}

        with manager:
            pass

        assert manager._sync_client is None
        assert manager._collections == {}

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        """测试异步上下文管理器"""
        manager = ChromaConnectionManager()
        manager._async_client = MagicMock()
        manager._async_collections = {"test": MagicMock()}

        async with manager:
            pass

        assert manager._async_client is None
        assert manager._async_collections == {}


class TestGlobalFunctions:
    """全局函数测试类"""

    @patch("src.infrastructure.storage.chroma.connection._connection_manager")
    def test_get_connection_manager_existing(self, mock_manager):
        """测试获取现有连接管理器"""
        # mock_manager 已经是 patch 装饰器提供的 mock 对象
        # 直接使用它,不需要重新赋值

        manager = get_connection_manager()

        assert manager == mock_manager

    @patch("src.infrastructure.storage.chroma.connection._connection_manager", None)
    @patch("src.infrastructure.storage.chroma.connection.ChromaConnectionManager")
    def test_get_connection_manager_new(self, mock_chroma_manager):
        """测试创建新连接管理器"""
        mock_chroma_manager.return_value = MagicMock()

        get_connection_manager()

        mock_chroma_manager.assert_called_once_with(
            db_path="data/chroma",
            collection_name="whitepaper_documents",
            persist_directory="data/chroma",
        )

    @patch("src.infrastructure.storage.chroma.connection.ChromaConnectionManager")
    def test_create_connection_manager(self, mock_chroma_manager):
        """测试创建连接管理器"""
        mock_chroma_manager.return_value = MagicMock()

        manager = create_connection_manager(
            db_path="custom/path",
            collection_name="custom_collection",
            persist_directory="custom/persist",
        )

        mock_chroma_manager.assert_called_once_with(
            db_path="custom/path",
            collection_name="custom_collection",
            persist_directory="custom/persist",
        )
        assert manager == mock_chroma_manager.return_value
