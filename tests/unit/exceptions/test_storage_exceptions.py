# 生成命令: T010 自定义异常类实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
存储异常类单元测试
"""

from src.shared.exceptions.storage_exceptions import (
    BackupError,
    CacheError,
    ChromaError,
    CustomConnectionError,
    CustomIndexError,
    DataIntegrityError,
    MigrationError,
    NetworkXError,
    QueryError,
    SQLiteError,
    StorageError,
    TransactionError,
)


class TestStorageError:
    """测试存储基础异常类"""

    def test_basic_storage_error(self):
        """测试基本存储错误"""
        error = StorageError("Storage operation failed")
        assert error.message == "Storage operation failed"
        assert isinstance(error, Exception)

    def test_storage_error_with_details(self):
        """测试带详细信息的存储错误"""
        error = StorageError(
            "Storage operation failed",
            storage_type="SQLite",
            connection_string="sqlite:///database.db",
        )

        assert error.message == "Storage operation failed"
        assert error.details["storage_type"] == "SQLite"
        assert error.details["connection_string"] == "sqlite://***"

    def test_mask_connection_string(self):
        """测试连接字符串脱敏"""
        error = StorageError(
            "Storage operation failed",
            connection_string="postgresql://user:password@localhost:5432/db",
        )

        assert error.details["connection_string"] == "postgresql://***"

    def test_mask_connection_string_no_protocol(self):
        """测试无协议的连接字符串脱敏"""
        error = StorageError(
            "Storage operation failed", connection_string="local_file.db"
        )

        assert error.details["connection_string"] == "***"


class TestCustomConnectionError:
    """测试连接错误异常"""

    def test_basic_connection_error(self):
        """测试基本连接错误"""
        error = CustomConnectionError("Connection failed")
        assert error.message == "Connection failed"
        assert isinstance(error, StorageError)

    def test_connection_error_with_details(self):
        """测试带详细信息的连接错误"""
        error = CustomConnectionError(
            "Connection failed", host="localhost", port=5432, timeout=30.0
        )

        assert error.message == "Connection failed"
        assert error.details["host"] == "localhost"
        assert error.details["port"] == 5432
        assert error.details["timeout"] == 30.0


class TestQueryError:
    """测试查询错误异常"""

    def test_basic_query_error(self):
        """测试基本查询错误"""
        error = QueryError("Query failed")
        assert error.message == "Query failed"
        assert isinstance(error, StorageError)

    def test_query_error_with_details(self):
        """测试带详细信息的查询错误"""
        error = QueryError(
            "Query failed",
            query="SELECT * FROM users WHERE password = 'secret'",
            query_params={"user_id": 123},
        )

        assert error.message == "Query failed"
        assert "password = ***" in error.details["query"]
        assert error.details["query_params"] == {"user_id": 123}

    def test_mask_query(self):
        """测试查询语句脱敏"""
        error = QueryError(
            "Query failed",
            query="INSERT INTO users (name, password, token) VALUES ('test', 'secret', 'abc123')",
        )

        masked_query = error.details["query"]
        # 对于INSERT语句,VALUES中的值应该被脱敏
        assert "VALUES (***, ***, ***)" in masked_query
        # 字段名应该保持不变
        assert "password" in masked_query
        assert "token" in masked_query
        assert "key" not in masked_query  # 不应该匹配不存在的字段


class TestTransactionError:
    """测试事务错误异常"""

    def test_basic_transaction_error(self):
        """测试基本事务错误"""
        error = TransactionError("Transaction failed")
        assert error.message == "Transaction failed"
        assert isinstance(error, StorageError)

    def test_transaction_error_with_details(self):
        """测试带详细信息的事务错误"""
        error = TransactionError(
            "Transaction failed", transaction_id="tx_001", operation="commit"
        )

        assert error.message == "Transaction failed"
        assert error.details["transaction_id"] == "tx_001"
        assert error.details["operation"] == "commit"


class TestDataIntegrityError:
    """测试数据完整性错误异常"""

    def test_basic_data_integrity_error(self):
        """测试基本数据完整性错误"""
        error = DataIntegrityError("Data integrity violation")
        assert error.message == "Data integrity violation"
        assert isinstance(error, StorageError)

    def test_data_integrity_error_with_details(self):
        """测试带详细信息的数据完整性错误"""
        error = DataIntegrityError(
            "Data integrity violation",
            constraint="unique_email",
            table="users",
            record_id=123,
        )

        assert error.message == "Data integrity violation"
        assert error.details["constraint"] == "unique_email"
        assert error.details["table"] == "users"
        assert error.details["record_id"] == 123


class TestSQLiteError:
    """测试SQLite错误异常"""

    def test_basic_sqlite_error(self):
        """测试基本SQLite错误"""
        error = SQLiteError("SQLite operation failed")
        assert error.message == "SQLite operation failed"
        assert isinstance(error, StorageError)
        assert error.details["storage_type"] == "SQLite"

    def test_sqlite_error_with_details(self):
        """测试带详细信息的SQLite错误"""
        error = SQLiteError(
            "SQLite operation failed",
            database_path="/path/to/database.db",
            sqlite_error_code=19,  # SQLITE_CONSTRAINT
        )

        assert error.message == "SQLite operation failed"
        assert error.details["storage_type"] == "SQLite"
        assert error.details["database_path"] == "/path/to/database.db"
        assert error.details["sqlite_error_code"] == 19


class TestChromaError:
    """测试Chroma错误异常"""

    def test_basic_chroma_error(self):
        """测试基本Chroma错误"""
        error = ChromaError("Chroma operation failed")
        assert error.message == "Chroma operation failed"
        assert isinstance(error, StorageError)
        assert error.details["storage_type"] == "Chroma"

    def test_chroma_error_with_details(self):
        """测试带详细信息的Chroma错误"""
        error = ChromaError(
            "Chroma operation failed",
            collection_name="documents",
            embedding_function="text-embedding-ada-002",
            vector_dimension=1536,
        )

        assert error.message == "Chroma operation failed"
        assert error.details["storage_type"] == "Chroma"
        assert error.details["collection_name"] == "documents"
        assert error.details["embedding_function"] == "text-embedding-ada-002"
        assert error.details["vector_dimension"] == 1536


class TestNetworkXError:
    """测试NetworkX错误异常"""

    def test_basic_networkx_error(self):
        """测试基本NetworkX错误"""
        error = NetworkXError("NetworkX operation failed")
        assert error.message == "NetworkX operation failed"
        assert isinstance(error, StorageError)
        assert error.details["storage_type"] == "NetworkX"

    def test_networkx_error_with_details(self):
        """测试带详细信息的NetworkX错误"""
        error = NetworkXError(
            "NetworkX operation failed",
            graph_type="DiGraph",
            node_id="node_001",
            edge=("node_001", "node_002"),
        )

        assert error.message == "NetworkX operation failed"
        assert error.details["storage_type"] == "NetworkX"
        assert error.details["graph_type"] == "DiGraph"
        assert error.details["node_id"] == "node_001"
        assert error.details["edge"] == ("node_001", "node_002")


class TestMigrationError:
    """测试迁移错误异常"""

    def test_basic_migration_error(self):
        """测试基本迁移错误"""
        error = MigrationError("Migration failed")
        assert error.message == "Migration failed"
        assert isinstance(error, StorageError)

    def test_migration_error_with_details(self):
        """测试带详细信息的迁移错误"""
        error = MigrationError(
            "Migration failed",
            migration_version="v1.0.0",
            from_version="v0.9.0",
            to_version="v1.0.0",
        )

        assert error.message == "Migration failed"
        assert error.details["migration_version"] == "v1.0.0"
        assert error.details["from_version"] == "v0.9.0"
        assert error.details["to_version"] == "v1.0.0"


class TestBackupError:
    """测试备份错误异常"""

    def test_basic_backup_error(self):
        """测试基本备份错误"""
        error = BackupError("Backup failed")
        assert error.message == "Backup failed"
        assert isinstance(error, StorageError)

    def test_backup_error_with_details(self):
        """测试带详细信息的备份错误"""
        error = BackupError(
            "Backup failed", backup_path="/path/to/backup.tar.gz", backup_type="full"
        )

        assert error.message == "Backup failed"
        assert error.details["backup_path"] == "/path/to/backup.tar.gz"
        assert error.details["backup_type"] == "full"


class TestCustomIndexError:
    """测试索引错误异常"""

    def test_basic_index_error(self):
        """测试基本索引错误"""
        error = CustomIndexError("Index operation failed")
        assert error.message == "Index operation failed"
        assert isinstance(error, StorageError)

    def test_index_error_with_details(self):
        """测试带详细信息的索引错误"""
        error = CustomIndexError(
            "Index operation failed",
            index_name="email_index",
            index_type="btree",
            indexed_field="email",
        )

        assert error.message == "Index operation failed"
        assert error.details["index_name"] == "email_index"
        assert error.details["index_type"] == "btree"
        assert error.details["indexed_field"] == "email"


class TestCacheError:
    """测试缓存错误异常"""

    def test_basic_cache_error(self):
        """测试基本缓存错误"""
        error = CacheError("Cache operation failed")
        assert error.message == "Cache operation failed"
        assert isinstance(error, StorageError)
        assert error.details["storage_type"] == "Cache"

    def test_cache_error_with_details(self):
        """测试带详细信息的缓存错误"""
        error = CacheError(
            "Cache operation failed", cache_key="user:123", cache_type="redis", ttl=3600
        )

        assert error.message == "Cache operation failed"
        assert error.details["storage_type"] == "Cache"
        assert error.details["cache_key"] == "user:123"
        assert error.details["cache_type"] == "redis"
        assert error.details["ttl"] == 3600
