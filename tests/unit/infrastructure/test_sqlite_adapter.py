# 生成命令: T012 SQLite 数据库适配器和连接管理
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
SQLite 适配器单元测试
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.storage.sqlite.adapter import (
    SQLiteAdapter,
    create_adapter,
)
from src.infrastructure.storage.sqlite.connection import SQLiteConnectionManager
from src.shared.exceptions.storage_exceptions import (
    QueryError,
    SQLiteError,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """创建一个事件循环实例用于整个测试会话"""
    loop = asyncio.new_event_loop()
    yield loop
    # 确保所有异步任务完成
    loop.close()


class TestSQLiteAdapter:
    """SQLite 适配器测试类"""

    @pytest.fixture
    def temp_db_path(self):
        """临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield Path(f.name)
        # 清理临时文件
        try:
            Path(f.name).unlink(missing_ok=True)
        except PermissionError:
            # Windows上文件可能被锁定,忽略错误
            pass

    @pytest.fixture
    def connection_manager(self, temp_db_path):
        """连接管理器实例"""
        manager = SQLiteConnectionManager(database_path=temp_db_path)
        yield manager
        # 确保测试结束时关闭所有连接
        try:
            # 先尝试同步关闭(这会关闭同步连接)
            manager.close()
            # 如果还有异步连接,尝试异步关闭
            if manager._async_pool:
                try:
                    # 尝试获取当前事件循环
                    try:
                        loop = asyncio.get_running_loop()
                        # 如果事件循环正在运行,我们不能在这里同步等待
                        # 创建一个任务来关闭连接(不等待完成)
                        # 注意:这不会等待任务完成,但会安排它执行
                        loop.create_task(manager.aclose())
                        logger.debug("已安排异步连接关闭任务")
                    except RuntimeError:
                        # 没有运行中的事件循环,尝试创建一个新的来关闭连接
                        try:
                            asyncio.run(manager.aclose())
                        except RuntimeError:
                            # 如果无法创建事件循环,至少清空连接池
                            logger.warning("无法创建事件循环来关闭异步连接,清空连接池")
                            manager._async_pool.clear()
                except Exception as e:
                    # 如果无法关闭异步连接,至少清空连接池
                    logger.warning(f"关闭异步连接时出错: {e},清空连接池")
                    manager._async_pool.clear()
        except Exception as e:
            # 忽略关闭时的错误,但记录警告
            logger.warning(f"关闭连接管理器时出错: {e}")

    @pytest.fixture
    def adapter(self, connection_manager):
        """适配器实例"""
        return SQLiteAdapter(
            table_name="test_table",
            connection_manager=connection_manager,
        )

    @pytest.fixture
    def setup_table(self, adapter):
        """设置测试表"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
        adapter.execute_custom_query(create_table_query, fetch_all=False)
        return adapter

    def test_init(self, connection_manager):
        """测试初始化"""
        adapter = SQLiteAdapter(
            table_name="users",
            connection_manager=connection_manager,
            id_field="user_id",
            created_at_field="created",
            updated_at_field="updated",
        )

        assert adapter.table_name == "users"
        assert adapter.connection_manager == connection_manager
        assert adapter.id_field == "user_id"
        assert adapter.created_at_field == "created"
        assert adapter.updated_at_field == "updated"

    def test_init_with_default_connection_manager(self, temp_db_path):
        """测试使用默认连接管理器初始化"""
        with patch(
            "src.infrastructure.storage.sqlite.adapter.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = SQLiteConnectionManager(database_path=temp_db_path)
            mock_get_manager.return_value = mock_manager

            adapter = SQLiteAdapter(table_name="test")

            assert adapter.connection_manager == mock_manager
            mock_get_manager.assert_called_once()

    def test_build_insert_query(self, adapter):
        """测试构建插入查询"""
        data = {"name": "test", "description": "test description"}
        query, params = adapter._build_insert_query(data)

        assert "INSERT INTO test_table" in query
        assert "name" in query
        assert "description" in query
        assert "created_at" in query
        assert "updated_at" in query
        assert len(params) == 4  # name, description, created_at, updated_at
        assert "test" in params
        assert "test description" in params

    def test_build_update_query(self, adapter):
        """测试构建更新查询"""
        data = {"name": "updated", "description": "updated description"}
        query, params = adapter._build_update_query(1, data)

        assert "UPDATE test_table SET" in query
        assert "name = ?" in query
        assert "description = ?" in query
        assert "updated_at = ?" in query
        assert "WHERE id = ?" in query
        assert len(params) == 4  # name, description, updated_at, id
        assert "updated" in params
        assert "updated description" in params
        assert 1 in params

    def test_build_select_query(self, adapter):
        """测试构建查询语句"""
        # 基本查询
        query, params = adapter._build_select_query()
        assert query == "SELECT * FROM test_table"
        assert params == ()

        # 带过滤条件的查询
        filters = {"name": "test", "description": "desc"}
        query, params = adapter._build_select_query(filters)
        assert "WHERE name = ? AND description = ?" in query
        assert params == ("test", "desc")

        # 带限制和排序的查询
        query, params = adapter._build_select_query(filters, limit=10, order_by="name")
        assert "WHERE name = ? AND description = ?" in query
        assert "ORDER BY name" in query
        assert "LIMIT 10" in query
        assert params == ("test", "desc")

    def test_row_to_dict(self, adapter):
        """测试行数据转换为字典"""
        # 测试 SQLite Row 对象
        mock_row = MagicMock()
        mock_row.keys.return_value = ["id", "name"]
        mock_row.__getitem__.side_effect = lambda key: {"id": 1, "name": "test"}[key]

        result = adapter._row_to_dict(mock_row)
        assert result == {"id": 1, "name": "test"}

        # 测试 None
        result = adapter._row_to_dict(None)
        assert result == {}

        # 测试普通元组
        result = adapter._row_to_dict((1, "test"))
        assert result == {"column_0": 1, "column_1": "test"}

    def test_create(self, setup_table):
        """测试创建记录"""
        adapter = setup_table
        data = {"name": "test_name", "description": "test_description"}

        result = adapter.create(data)

        assert result["name"] == "test_name"
        assert result["description"] == "test_description"
        assert "id" in result
        assert "created_at" in result
        assert "updated_at" in result

    def test_create_with_existing_timestamps(self, setup_table):
        """测试创建记录(已有时间戳)"""
        adapter = setup_table
        data = {
            "name": "test_name",
            "description": "test_description",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-01T00:00:00",
        }

        result = adapter.create(data)

        assert result["name"] == "test_name"
        assert result["description"] == "test_description"
        assert result["created_at"] == "2023-01-01T00:00:00"
        assert result["updated_at"] == "2023-01-01T00:00:00"

    def test_create_error(self, setup_table):
        """测试创建记录错误"""
        adapter = setup_table
        # 缺少必需字段
        data = {"description": "test_description"}

        with pytest.raises(SQLiteError):
            adapter.create(data)

    @pytest.mark.asyncio
    async def test_create_async(self, setup_table):
        """测试异步创建记录"""
        adapter = setup_table
        data = {"name": "test_name", "description": "test_description"}

        result = await adapter.create_async(data)

        assert result["name"] == "test_name"
        assert result["description"] == "test_description"
        assert "id" in result
        assert "created_at" in result
        assert "updated_at" in result

    def test_get_by_id(self, setup_table):
        """测试根据ID获取记录"""
        adapter = setup_table

        # 先创建记录
        data = {"name": "test_name", "description": "test_description"}
        created = adapter.create(data)
        record_id = created["id"]

        # 获取记录
        result = adapter.get_by_id(record_id)

        assert result is not None
        assert result["id"] == record_id
        assert result["name"] == "test_name"
        assert result["description"] == "test_description"

    def test_get_by_id_not_found(self, setup_table):
        """测试根据ID获取不存在的记录"""
        adapter = setup_table

        result = adapter.get_by_id(999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_async(self, setup_table):
        """测试异步根据ID获取记录"""
        adapter = setup_table

        # 先创建记录
        data = {"name": "test_name", "description": "test_description"}
        created = await adapter.create_async(data)
        record_id = created["id"]

        # 获取记录
        result = await adapter.get_by_id_async(record_id)

        assert result is not None
        assert result["id"] == record_id
        assert result["name"] == "test_name"
        assert result["description"] == "test_description"

    def test_update(self, setup_table):
        """测试更新记录"""
        adapter = setup_table

        # 先创建记录
        data = {"name": "test_name", "description": "test_description"}
        created = adapter.create(data)
        record_id = created["id"]

        # 更新记录
        update_data = {"name": "updated_name", "description": "updated_description"}
        result = adapter.update(record_id, update_data)

        assert result is not None
        assert result["id"] == record_id
        assert result["name"] == "updated_name"
        assert result["description"] == "updated_description"
        assert "updated_at" in result

    def test_update_not_found(self, setup_table):
        """测试更新不存在的记录"""
        adapter = setup_table

        update_data = {"name": "updated_name", "description": "updated_description"}
        result = adapter.update(999, update_data)

        assert result is None

    @pytest.mark.asyncio
    async def test_update_async(self, setup_table):
        """测试异步更新记录"""
        adapter = setup_table

        # 先创建记录
        data = {"name": "test_name", "description": "test_description"}
        created = await adapter.create_async(data)
        record_id = created["id"]

        # 更新记录
        update_data = {"name": "updated_name", "description": "updated_description"}
        result = await adapter.update_async(record_id, update_data)

        assert result is not None
        assert result["id"] == record_id
        assert result["name"] == "updated_name"
        assert result["description"] == "updated_description"
        assert "updated_at" in result

    def test_delete(self, setup_table):
        """测试删除记录"""
        adapter = setup_table

        # 先创建记录
        data = {"name": "test_name", "description": "test_description"}
        created = adapter.create(data)
        record_id = created["id"]

        # 删除记录
        result = adapter.delete(record_id)

        assert result is True

        # 验证记录已删除
        deleted_record = adapter.get_by_id(record_id)
        assert deleted_record is None

    def test_delete_not_found(self, setup_table):
        """测试删除不存在的记录"""
        adapter = setup_table

        result = adapter.delete(999)

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_async(self, setup_table):
        """测试异步删除记录"""
        adapter = setup_table

        # 先创建记录
        data = {"name": "test_name", "description": "test_description"}
        created = await adapter.create_async(data)
        record_id = created["id"]

        # 删除记录
        result = await adapter.delete_async(record_id)

        assert result is True

        # 验证记录已删除
        deleted_record = await adapter.get_by_id_async(record_id)
        assert deleted_record is None

    def test_list(self, setup_table):
        """测试列出记录"""
        adapter = setup_table

        # 创建多条记录
        for i in range(5):
            data = {"name": f"test_name_{i}", "description": f"test_description_{i}"}
            adapter.create(data)

        # 获取所有记录
        all_records = adapter.list()
        assert len(all_records) == 5

        # 带过滤条件
        filtered_records = adapter.list(filters={"name": "test_name_1"})
        assert len(filtered_records) == 1
        assert filtered_records[0]["name"] == "test_name_1"

        # 带限制
        limited_records = adapter.list(limit=3)
        assert len(limited_records) == 3

        # 带排序
        ordered_records = adapter.list(order_by="name DESC")
        assert ordered_records[0]["name"] == "test_name_4"

    @pytest.mark.asyncio
    async def test_list_async(self, setup_table):
        """测试异步列出记录"""
        adapter = setup_table

        # 创建多条记录
        for i in range(5):
            data = {"name": f"test_name_{i}", "description": f"test_description_{i}"}
            await adapter.create_async(data)

        # 获取所有记录
        all_records = await adapter.list_async()
        assert len(all_records) == 5

        # 带过滤条件
        filtered_records = await adapter.list_async(filters={"name": "test_name_1"})
        assert len(filtered_records) == 1
        assert filtered_records[0]["name"] == "test_name_1"

    def test_count(self, setup_table):
        """测试统计记录数量"""
        adapter = setup_table

        # 创建记录
        for i in range(5):
            data = {"name": f"test_name_{i}", "description": f"test_description_{i}"}
            adapter.create(data)

        # 统计所有记录
        count = adapter.count()
        assert count == 5

        # 带过滤条件统计
        filtered_count = adapter.count(filters={"name": "test_name_1"})
        assert filtered_count == 1

    @pytest.mark.asyncio
    async def test_count_async(self, setup_table):
        """测试异步统计记录数量"""
        adapter = setup_table

        # 创建记录
        for i in range(5):
            data = {"name": f"test_name_{i}", "description": f"test_description_{i}"}
            await adapter.create_async(data)

        # 统计所有记录
        count = await adapter.count_async()
        assert count == 5

        # 带过滤条件统计
        filtered_count = await adapter.count_async(filters={"name": "test_name_1"})
        assert filtered_count == 1

    def test_exists(self, setup_table):
        """测试检查记录是否存在"""
        adapter = setup_table

        # 先创建记录
        data = {"name": "test_name", "description": "test_description"}
        created = adapter.create(data)
        record_id = created["id"]

        # 检查存在的记录
        exists = adapter.exists(record_id)
        assert exists is True

        # 检查不存在的记录
        not_exists = adapter.exists(999)
        assert not_exists is False

    @pytest.mark.asyncio
    async def test_exists_async(self, setup_table):
        """测试异步检查记录是否存在"""
        adapter = setup_table

        # 先创建记录
        data = {"name": "test_name", "description": "test_description"}
        created = await adapter.create_async(data)
        record_id = created["id"]

        # 检查存在的记录
        exists = await adapter.exists_async(record_id)
        assert exists is True

        # 检查不存在的记录
        not_exists = await adapter.exists_async(999)
        assert not_exists is False

    def test_bulk_create(self, setup_table):
        """测试批量创建记录"""
        adapter = setup_table

        # 准备数据
        data_list = [
            {"name": "test_name_1", "description": "test_description_1"},
            {"name": "test_name_2", "description": "test_description_2"},
            {"name": "test_name_3", "description": "test_description_3"},
        ]

        # 批量创建
        results = adapter.bulk_create(data_list)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["name"] == f"test_name_{i + 1}"
            assert result["description"] == f"test_description_{i + 1}"
            assert "id" in result
            assert "created_at" in result
            assert "updated_at" in result

    def test_bulk_create_empty(self, setup_table):
        """测试批量创建空列表"""
        adapter = setup_table

        results = adapter.bulk_create([])
        assert results == []

    @pytest.mark.asyncio
    async def test_bulk_create_async(self, setup_table):
        """测试异步批量创建记录"""
        adapter = setup_table

        # 准备数据
        data_list = [
            {"name": "test_name_1", "description": "test_description_1"},
            {"name": "test_name_2", "description": "test_description_2"},
            {"name": "test_name_3", "description": "test_description_3"},
        ]

        # 批量创建
        results = await adapter.bulk_create_async(data_list)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["name"] == f"test_name_{i + 1}"
            assert result["description"] == f"test_description_{i + 1}"
            assert "id" in result
            assert "created_at" in result
            assert "updated_at" in result

    def test_execute_custom_query(self, setup_table):
        """测试执行自定义查询"""
        adapter = setup_table

        # 创建记录
        data = {"name": "test_name", "description": "test_description"}
        adapter.create(data)

        # 执行自定义查询
        result = adapter.execute_custom_query(
            "SELECT * FROM test_table WHERE name = ?",
            ("test_name",),
            fetch_one=True,
        )

        assert result is not None
        assert result["name"] == "test_name"

        # 执行返回多条记录的查询
        results = adapter.execute_custom_query(
            "SELECT * FROM test_table",
            fetch_all=True,
        )

        assert len(results) >= 1

        # 执行不返回结果的查询
        adapter.execute_custom_query(
            "INSERT INTO test_table (name, description) VALUES (?, ?)",
            ("another_name", "another_description"),
            fetch_all=False,
        )

        # 验证插入成功
        count = adapter.count()
        assert count >= 2

    def test_execute_custom_query_error(self, setup_table):
        """测试执行自定义查询错误"""
        adapter = setup_table

        with pytest.raises(QueryError):
            adapter.execute_custom_query("INVALID SQL")

    @pytest.mark.asyncio
    async def test_execute_custom_query_async(self, setup_table):
        """测试异步执行自定义查询"""
        adapter = setup_table

        # 创建记录
        data = {"name": "test_name", "description": "test_description"}
        await adapter.create_async(data)

        # 执行自定义查询
        result = await adapter.execute_custom_query_async(
            "SELECT * FROM test_table WHERE name = ?",
            ("test_name",),
            fetch_one=True,
        )

        assert result is not None
        assert result["name"] == "test_name"

        # 执行返回多条记录的查询
        results = await adapter.execute_custom_query_async(
            "SELECT * FROM test_table",
            fetch_all=True,
        )

        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_execute_custom_query_async_error(self, setup_table):
        """测试异步执行自定义查询错误"""
        adapter = setup_table

        with pytest.raises(QueryError):
            await adapter.execute_custom_query_async("INVALID SQL")

    def test_get_table_info(self, setup_table):
        """测试获取表信息"""
        adapter = setup_table

        # 创建一些记录
        for i in range(3):
            data = {"name": f"test_name_{i}", "description": f"test_description_{i}"}
            adapter.create(data)

        # 获取表信息
        info = adapter.get_table_info()

        assert info["table_name"] == "test_table"
        assert info["record_count"] == 3
        assert info["id_field"] == "id"
        assert info["created_at_field"] == "created_at"
        assert info["updated_at_field"] == "updated_at"
        assert len(info["columns"]) > 0

        # 检查列信息
        column_names = [col["name"] for col in info["columns"]]
        assert "id" in column_names
        assert "name" in column_names
        assert "description" in column_names
        assert "created_at" in column_names
        assert "updated_at" in column_names

    @pytest.mark.asyncio
    async def test_get_table_info_async(self, setup_table):
        """测试异步获取表信息"""
        adapter = setup_table

        # 创建一些记录
        for i in range(3):
            data = {"name": f"test_name_{i}", "description": f"test_description_{i}"}
            await adapter.create_async(data)

        # 获取表信息
        info = await adapter.get_table_info_async()

        assert info["table_name"] == "test_table"
        assert info["record_count"] == 3
        assert info["id_field"] == "id"
        assert info["created_at_field"] == "created_at"
        assert info["updated_at_field"] == "updated_at"
        assert len(info["columns"]) > 0


class TestAdapterFunctions:
    """适配器函数测试类"""

    @pytest.fixture
    def temp_db_path(self):
        """临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield Path(f.name)
        # 清理临时文件
        try:
            Path(f.name).unlink(missing_ok=True)
        except PermissionError:
            # Windows上文件可能被锁定,忽略错误
            pass

    def test_create_adapter(self, temp_db_path):
        """测试创建适配器"""
        connection_manager = SQLiteConnectionManager(database_path=temp_db_path)

        adapter = create_adapter(
            table_name="users",
            connection_manager=connection_manager,
            id_field="user_id",
        )

        assert isinstance(adapter, SQLiteAdapter)
        assert adapter.table_name == "users"
        assert adapter.connection_manager == connection_manager
        assert adapter.id_field == "user_id"

    def test_create_adapter_with_default_manager(self, temp_db_path):
        """测试使用默认连接管理器创建适配器"""
        with patch(
            "src.infrastructure.storage.sqlite.adapter.get_connection_manager"
        ) as mock_get_manager:
            mock_manager = SQLiteConnectionManager(database_path=temp_db_path)
            mock_get_manager.return_value = mock_manager

            adapter = create_adapter(table_name="users")

            assert adapter.connection_manager == mock_manager
            mock_get_manager.assert_called_once()
