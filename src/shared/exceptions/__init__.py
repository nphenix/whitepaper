# 生成命令: T010 自定义异常类实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
自定义异常类模块

提供系统级的统一异常处理, 包括基础异常、Agent异常和存储异常。
"""

# 基础异常类
# Agent相关异常类
from .agent_exceptions import (
    AgentCallbackError,
    AgentConfigurationError,
    AgentError,
    AgentExecutionError,
    AgentInputError,
    AgentMemoryError,
    AgentStateError,
    AgentToolError,
    LangChainError,
    wrap_langchain_error,
)
from .base_exceptions import (
    BaseApplicationError,
    BusinessLogicError,
    ConfigurationError,
    CustomPermissionError,
    CustomTimeoutError,
    RateLimitError,
    ResourceNotFoundError,
    ValidationError,
)

# 存储相关异常类
from .storage_exceptions import (
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

__all__ = [
    "AgentCallbackError",
    "AgentConfigurationError",
    "AgentError",
    "AgentExecutionError",
    "AgentInputError",
    "AgentMemoryError",
    "AgentStateError",
    "AgentToolError",
    "BackupError",
    "BaseApplicationError",
    "BusinessLogicError",
    "CacheError",
    "ChromaError",
    "ConfigurationError",
    "CustomConnectionError",
    "CustomIndexError",
    "CustomPermissionError",
    "CustomTimeoutError",
    "DataIntegrityError",
    "LangChainError",
    "MigrationError",
    "NetworkXError",
    "QueryError",
    "RateLimitError",
    "ResourceNotFoundError",
    "SQLiteError",
    "StorageError",
    "TransactionError",
    "ValidationError",
    "wrap_langchain_error",
]
