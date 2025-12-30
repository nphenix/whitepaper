# 生成命令: T010 自定义异常类实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
存储相关异常类模块

提供各种存储系统的异常处理, 包括SQLite,Chroma,NetworkX等.
"""

from typing import Any

from .base_exceptions import BaseApplicationError


class StorageError(BaseApplicationError):
    """存储基础异常类

    所有存储相关异常的基类.
    """

    def __init__(
        self,
        message: str,
        storage_type: str | None = None,
        connection_string: str | None = None,
        **kwargs,
    ):
        """初始化存储错误

        Args:
            message: 错误消息
            storage_type: 存储类型(如SQLite,Chroma,NetworkX)
            connection_string: 连接字符串(脱敏处理)
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if storage_type:
            self.details["storage_type"] = storage_type
        if connection_string:
            # 脱敏处理连接字符串, 隐藏敏感信息
            self.details["connection_string"] = self._mask_connection_string(
                connection_string
            )

    def _mask_connection_string(self, connection_string: str) -> str:
        """脱敏处理连接字符串

        Args:
            connection_string: 原始连接字符串

        Returns:
            脱敏后的连接字符串
        """
        # 简单的脱敏逻辑, 隐藏密码等敏感信息
        if "://" in connection_string:
            parts = connection_string.split("://")
            if len(parts) == 2:
                return f"{parts[0]}://***"
        return "***"


class CustomConnectionError(StorageError):
    """连接错误异常

    当无法连接到存储系统时抛出.
    """

    def __init__(
        self,
        message: str,
        host: str | None = None,
        port: int | None = None,
        timeout: float | None = None,
        **kwargs,
    ):
        """初始化连接错误

        Args:
            message: 错误消息
            host: 主机地址
            port: 端口号
            timeout: 超时时间
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if host:
            self.details["host"] = host
        if port:
            self.details["port"] = port
        if timeout:
            self.details["timeout"] = timeout


class QueryError(StorageError):
    """查询错误异常

    当存储查询执行失败时抛出.
    """

    def __init__(
        self,
        message: str,
        query: str | None = None,
        query_params: dict[str, Any] | None = None,
        **kwargs,
    ):
        """初始化查询错误

        Args:
            message: 错误消息
            query: 查询语句(脱敏处理)
            query_params: 查询参数
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if query:
            # 脱敏处理查询语句, 隐藏敏感信息
            self.details["query"] = self._mask_query(query)
        if query_params:
            self.details["query_params"] = query_params

    def _mask_query(self, query: str) -> str:
        """脱敏处理查询语句

        Args:
            query: 原始查询语句

        Returns:
            脱敏后的查询语句
        """
        # 简单的脱敏逻辑, 隐藏敏感信息
        import re

        # 隐藏密码相关的字段(WHERE子句中的赋值)
        masked_query = re.sub(
            r"(password\s*=\s*)['']?[^'',\s)]+['']?",
            r"\1***",
            query,
            flags=re.IGNORECASE,
        )
        masked_query = re.sub(
            r"(token\s*=\s*)['']?[^'',\s)]+['']?",
            r"\1***",
            masked_query,
            flags=re.IGNORECASE,
        )
        masked_query = re.sub(
            r"(key\s*=\s*)['']?[^'',\s)]+['']?",
            r"\1***",
            masked_query,
            flags=re.IGNORECASE,
        )

        # 隐藏INSERT语句中的敏感字段值
        # 更简单的处理: 如果INSERT语句包含敏感字段, 则将VALUES中的所有值替换为***
        if re.search(
            r"INSERT\s+INTO\s+\w+\s*\([^)]*\b(password|token|key)\b[^)]*\)",
            query,
            flags=re.IGNORECASE,
        ):
            # 找到VALUES部分并替换其中的值
            values_pattern = r"(VALUES\s*\([^)]*\))"
            values_match = re.search(values_pattern, masked_query, flags=re.IGNORECASE)
            if values_match:
                values_part = values_match.group(1)
                # 将VALUES中的所有值替换为***
                masked_values = re.sub(
                    r"['']?[^'',\s)]+['']?(?=\s*[,\)])", "***", values_part
                )
                masked_query = masked_query.replace(values_part, masked_values)

        return masked_query


class TransactionError(StorageError):
    """事务错误异常

    当事务操作失败时抛出.
    """

    def __init__(
        self,
        message: str,
        transaction_id: str | None = None,
        operation: str | None = None,
        **kwargs,
    ):
        """初始化事务错误

        Args:
            message: 错误消息
            transaction_id: 事务ID
            operation: 事务操作类型
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if transaction_id:
            self.details["transaction_id"] = transaction_id
        if operation:
            self.details["operation"] = operation


class DataIntegrityError(StorageError):
    """数据完整性错误异常

    当数据完整性约束被违反时抛出.
    """

    def __init__(
        self,
        message: str,
        constraint: str | None = None,
        table: str | None = None,
        record_id: str | int | None = None,
        **kwargs,
    ):
        """初始化数据完整性错误

        Args:
            message: 错误消息
            constraint: 违反的约束名称
            table: 表名
            record_id: 记录ID
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if constraint:
            self.details["constraint"] = constraint
        if table:
            self.details["table"] = table
        if record_id is not None:
            self.details["record_id"] = record_id


class SQLiteError(StorageError):
    """SQLite存储错误异常

    当SQLite操作失败时抛出.
    """

    def __init__(
        self,
        message: str,
        database_path: str | None = None,
        sqlite_error_code: int | None = None,
        **kwargs,
    ):
        """初始化SQLite错误

        Args:
            message: 错误消息
            database_path: 数据库文件路径
            sqlite_error_code: SQLite错误代码
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, storage_type="SQLite", **kwargs)
        if database_path:
            self.details["database_path"] = database_path
        if sqlite_error_code is not None:
            self.details["sqlite_error_code"] = sqlite_error_code


class ChromaError(StorageError):
    """Chroma向量存储错误异常

    当Chroma向量存储操作失败时抛出.
    """

    def __init__(
        self,
        message: str,
        collection_name: str | None = None,
        embedding_function: str | None = None,
        vector_dimension: int | None = None,
        **kwargs,
    ):
        """初始化Chroma错误

        Args:
            message: 错误消息
            collection_name: 集合名称
            embedding_function: 嵌入函数名称
            vector_dimension: 向量维度
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, storage_type="Chroma", **kwargs)
        if collection_name:
            self.details["collection_name"] = collection_name
        if embedding_function:
            self.details["embedding_function"] = embedding_function
        if vector_dimension is not None:
            self.details["vector_dimension"] = vector_dimension


class NetworkXError(StorageError):
    """NetworkX图存储错误异常

    当NetworkX图操作失败时抛出.
    """

    def __init__(
        self,
        message: str,
        graph_type: str | None = None,
        node_id: str | int | None = None,
        edge: tuple | None = None,
        **kwargs,
    ):
        """初始化NetworkX错误

        Args:
            message: 错误消息
            graph_type: 图类型
            node_id: 节点ID
            edge: 边元组
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, storage_type="NetworkX", **kwargs)
        if graph_type:
            self.details["graph_type"] = graph_type
        if node_id is not None:
            self.details["node_id"] = node_id
        if edge:
            self.details["edge"] = edge


class MigrationError(StorageError):
    """数据迁移错误异常

    当数据迁移操作失败时抛出.
    """

    def __init__(
        self,
        message: str,
        migration_version: str | None = None,
        from_version: str | None = None,
        to_version: str | None = None,
        **kwargs,
    ):
        """初始化迁移错误

        Args:
            message: 错误消息
            migration_version: 迁移版本
            from_version: 源版本
            to_version: 目标版本
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if migration_version:
            self.details["migration_version"] = migration_version
        if from_version:
            self.details["from_version"] = from_version
        if to_version:
            self.details["to_version"] = to_version


class BackupError(StorageError):
    """备份错误异常

    当备份操作失败时抛出.
    """

    def __init__(
        self,
        message: str,
        backup_path: str | None = None,
        backup_type: str | None = None,
        **kwargs,
    ):
        """初始化备份错误

        Args:
            message: 错误消息
            backup_path: 备份路径
            backup_type: 备份类型
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if backup_path:
            self.details["backup_path"] = backup_path
        if backup_type:
            self.details["backup_type"] = backup_type


class CustomIndexError(StorageError):
    """索引错误异常

    当索引操作失败时抛出.
    """

    def __init__(
        self,
        message: str,
        index_name: str | None = None,
        index_type: str | None = None,
        indexed_field: str | None = None,
        **kwargs,
    ):
        """初始化索引错误

        Args:
            message: 错误消息
            index_name: 索引名称
            index_type: 索引类型
            indexed_field: 索引字段
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if index_name:
            self.details["index_name"] = index_name
        if index_type:
            self.details["index_type"] = index_type
        if indexed_field:
            self.details["indexed_field"] = indexed_field


class CacheError(StorageError):
    """缓存错误异常

    当缓存操作失败时抛出.
    """

    def __init__(
        self,
        message: str,
        cache_key: str | None = None,
        cache_type: str | None = None,
        ttl: int | None = None,
        **kwargs,
    ):
        """初始化缓存错误

        Args:
            message: 错误消息
            cache_key: 缓存键
            cache_type: 缓存类型
            ttl: 生存时间(秒)
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, storage_type="Cache", **kwargs)
        if cache_key:
            self.details["cache_key"] = cache_key
        if cache_type:
            self.details["cache_type"] = cache_type
        if ttl is not None:
            self.details["ttl"] = ttl
