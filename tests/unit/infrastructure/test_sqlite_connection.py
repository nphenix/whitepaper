# 生成命令: T012 SQLite 数据库适配器和连接管理
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
SQLite 连接管理器单元测试
"""

import asyncio
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.infrastructure.storage.sqlite.connection import (
    SQLiteConnectionManager,
    create_connection_manager,
    get_connection_manager,
)
from src.shared.exceptions.storage_exceptions import (
    CustomConnectionError,
    SQLiteError,
    TransactionError,
)


class TestSQLiteConnectionManager:
    """SQLite 连接管理器测试类"""

    @pytest.fixture
    def temp_db_path(self):
        """临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            yield Path(f.name)
        # 清理临时文件
        Path(f.name).unlink(missing_ok=True)

    @pytest.fixture
    def connection_manager(self, temp_db_path):
        """连接管理器实例"""
        return SQLiteConnectionManager(
            database_path=temp_db_path,
            pool_size=5,
            max_overflow=10,
        )

    def test_init_default_config(self):
        """测试默认配置初始化"""
        with patch(
            "src.infrastructure.storage.sqlite.connection.get_config"
        ) as mock_config:
            mock_config.return_value.database.sqlite_db_path = "./test.db"
            mock_config.return_value.database.sqlite_pool_size = 10
            mock_config.return_value.database.sqlite_max_overflow = 20

            manager = SQLiteConnectionManager()

            assert manager.database_path == Path("./test.db")
            assert manager.pool_size == 10
            assert manager.max_overflow == 20
            assert manager.enable_wal is True
            assert manager.enable_foreign_keys is True
            assert manager.timeout == 30.0

    def test_init_custom_config(self, temp_db_path):
        """测试自定义配置初始化"""
        manager = SQLiteConnectionManager(
            database_path=temp_db_path,
            pool_size=3,
            max_overflow=5,
            enable_wal=False,
            enable_foreign_keys=False,
            timeout=60.0,
        )

        assert manager.database_path == temp_db_path
        assert manager.pool_size == 3
        assert manager.max_overflow == 5
        assert manager.enable_wal is False
        assert manager.enable_foreign_keys is False
        assert manager.timeout == 60.0

    def test_ensure_database_directory(self, connection_manager):
        """测试确保数据库目录存在"""
        # 使用不存在的目录路径
        non_existent_dir = Path(tempfile.mkdtemp()) / "subdir" / "test.db"
        manager = SQLiteConnectionManager(database_path=non_existent_dir)

        # 调用方法确保目录创建
        manager._ensure_database_directory()

        # 验证目录已创建
        assert non_existent_dir.parent.exists()

        # 清理
        non_existent_dir.parent.parent.rmdir()
        non_existent_dir.parent.rmdir()

    def test_configure_connection(self, connection_manager):
        """测试连接配置"""
        with connection_manager.get_connection() as conn:
            # 验证 WAL 模式
            result = conn.execute("PRAGMA journal_mode").fetchone()
            assert result[0] == "wal"

            # 验证外键约束
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1

            # 验证行工厂
            assert conn.row_factory == sqlite3.Row

    def test_get_connection(self, connection_manager):
        """测试获取连接"""
        with connection_manager.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)

            # 测试基本操作
            result = conn.execute("SELECT 1").fetchone()
            assert result[0] == 1

    def test_get_connection_error(self):
        """测试连接错误"""
        # 使用无效路径
        invalid_path = Path("/invalid/path/test.db")
        manager = SQLiteConnectionManager(database_path=invalid_path)

        with pytest.raises(CustomConnectionError), manager.get_connection():
            pass

    def test_transaction_success(self, connection_manager):
        """测试事务成功"""
        with connection_manager.transaction() as cursor:
            # 创建测试表
            cursor.execute(
                "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
            )

            # 插入数据
            cursor.execute("INSERT INTO test_table (name) VALUES (?)", ("test_name",))

            # 验证数据
            cursor.execute("SELECT COUNT(*) FROM test_table")
            count = cursor.fetchone()[0]
            assert count == 1

    def test_transaction_rollback(self, connection_manager):
        """测试事务回滚"""
        with connection_manager.get_connection() as conn:
            # 创建测试表
            conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
            conn.commit()

        # 模拟事务失败
        try:
            with connection_manager.transaction() as cursor:
                cursor.execute(
                    "INSERT INTO test_table (name) VALUES (?)", ("test_name",)
                )
                # 故意抛出异常
                msg = "Test error"
                raise ValueError(msg)
        except TransactionError:
            pass

        # 验证数据已回滚
        with connection_manager.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM test_table")
            count = cursor.fetchone()[0]
            assert count == 0

    def test_execute_query(self, connection_manager):
        """测试执行查询"""
        with connection_manager.get_connection() as conn:
            # 创建测试表
            conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO test_table (name) VALUES (?)", ("test_name",))
            conn.commit()

        # 执行查询
        result = connection_manager.execute_query(
            "SELECT * FROM test_table WHERE name = ?",
            ("test_name",),
            fetch_one=True,
        )

        assert result is not None
        assert result["name"] == "test_name"

    def test_execute_query_error(self, connection_manager):
        """测试查询错误"""
        with pytest.raises(SQLiteError):
            connection_manager.execute_query("INVALID SQL")

    @pytest.mark.asyncio
    async def test_get_async_connection(self, connection_manager):
        """测试获取异步连接"""
        async with connection_manager.get_async_connection() as conn:
            assert hasattr(conn, "execute")

            # 测试基本操作
            cursor = await conn.execute("SELECT 1")
            result = await cursor.fetchone()
            assert result[0] == 1

    @pytest.mark.asyncio
    async def test_async_transaction_success(self, connection_manager):
        """测试异步事务成功"""
        async with connection_manager.async_transaction() as cursor:
            # 创建测试表
            await cursor.execute(
                "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
            )

            # 插入数据
            await cursor.execute(
                "INSERT INTO test_table (name) VALUES (?)", ("test_name",)
            )

            # 验证数据
            await cursor.execute("SELECT COUNT(*) FROM test_table")
            count = (await cursor.fetchone())[0]
            assert count == 1

    @pytest.mark.asyncio
    async def test_async_transaction_rollback(self, connection_manager):
        """测试异步事务回滚"""
        async with connection_manager.get_async_connection() as conn:
            # 创建测试表
            await conn.execute(
                "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
            )
            await conn.commit()

        # 模拟事务失败
        try:
            async with connection_manager.async_transaction() as cursor:
                await cursor.execute(
                    "INSERT INTO test_table (name) VALUES (?)", ("test_name",)
                )
                # 故意抛出异常
                msg = "Test error"
                raise ValueError(msg)
        except TransactionError:
            pass

        # 验证数据已回滚
        async with connection_manager.get_async_connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM test_table")
            count = (await cursor.fetchone())[0]
            assert count == 0

    @pytest.mark.asyncio
    async def test_execute_async_query(self, connection_manager):
        """测试执行异步查询"""
        async with connection_manager.get_async_connection() as conn:
            # 创建测试表
            await conn.execute(
                "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
            )
            await conn.execute(
                "INSERT INTO test_table (name) VALUES (?)", ("test_name",)
            )
            await conn.commit()

        # 执行查询
        result = await connection_manager.execute_async_query(
            "SELECT * FROM test_table WHERE name = ?",
            ("test_name",),
            fetch_one=True,
        )

        assert result is not None
        assert result["name"] == "test_name"

    @pytest.mark.asyncio
    async def test_execute_async_query_error(self, connection_manager):
        """测试异步查询错误"""
        with pytest.raises(SQLiteError):
            await connection_manager.execute_async_query("INVALID SQL")

    def test_close_connection(self, connection_manager):
        """测试关闭连接"""
        # 获取连接
        with connection_manager.get_connection() as conn:
            thread_id = conn.connection.thread_id()

        # 关闭连接
        connection_manager.close_connection(thread_id)

        # 验证连接已从池中移除
        assert thread_id not in connection_manager._sync_pool

    @pytest.mark.asyncio
    async def test_close_async_connection(self, connection_manager):
        """测试关闭异步连接"""
        # 获取连接ID
        connection_id = f"async_{id(asyncio.current_task())}"

        # 获取连接
        async with connection_manager.get_async_connection():
            pass

        # 关闭连接
        await connection_manager.close_async_connection(connection_id)

        # 验证连接已从池中移除
        assert connection_id not in connection_manager._async_pool

    def test_close_all_connections(self, connection_manager):
        """测试关闭所有连接"""
        # 获取多个连接
        with connection_manager.get_connection():
            with connection_manager.get_connection():
                assert len(connection_manager._sync_pool) >= 1

        # 关闭所有连接
        connection_manager.close_all_connections()

        # 验证所有连接已关闭
        assert len(connection_manager._sync_pool) == 0

    @pytest.mark.asyncio
    async def test_close_all_async_connections(self, connection_manager):
        """测试关闭所有异步连接"""
        # 获取多个连接
        async with connection_manager.get_async_connection():
            async with connection_manager.get_async_connection():
                assert len(connection_manager._async_pool) >= 1

        # 关闭所有连接
        await connection_manager.close_all_async_connections()

        # 验证所有连接已关闭
        assert len(connection_manager._async_pool) == 0

    def test_get_connection_info(self, connection_manager):
        """测试获取连接信息"""
        info = connection_manager.get_connection_info()

        assert "database_path" in info
        assert "pool_size" in info
        assert "max_overflow" in info
        assert "enable_wal" in info
        assert "enable_foreign_keys" in info
        assert "timeout" in info
        assert "sync_connections" in info
        assert "async_connections" in info

        assert info["pool_size"] == 5
        assert info["max_overflow"] == 10
        assert info["enable_wal"] is True
        assert info["enable_foreign_keys"] is True
        assert info["timeout"] == 30.0

    def test_context_manager(self, connection_manager):
        """测试上下文管理器"""
        with connection_manager as manager:
            assert manager == connection_manager

        # 验证连接已关闭
        assert len(connection_manager._sync_pool) == 0

    @pytest.mark.asyncio
    async def test_async_context_manager(self, connection_manager):
        """测试异步上下文管理器"""
        async with connection_manager as manager:
            assert manager == connection_manager

        # 验证连接已关闭
        assert len(connection_manager._async_pool) == 0


class TestConnectionManagerFunctions:
    """连接管理器函数测试类"""

    def test_get_connection_manager(self):
        """测试获取全局连接管理器"""
        # 清理全局实例
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._connection_manager = None

        # 第一次调用应该创建新实例
        manager1 = get_connection_manager()
        assert isinstance(manager1, SQLiteConnectionManager)

        # 第二次调用应该返回同一实例
        manager2 = get_connection_manager()
        assert manager1 is manager2

    def test_create_connection_manager(self, temp_db_path):
        """测试创建新的连接管理器实例"""
        manager = create_connection_manager(
            database_path=temp_db_path,
            pool_size=3,
            max_overflow=5,
        )

        assert isinstance(manager, SQLiteConnectionManager)
        assert manager.database_path == temp_db_path
        assert manager.pool_size == 3
        assert manager.max_overflow == 5
