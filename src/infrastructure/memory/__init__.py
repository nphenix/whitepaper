# 生成命令: T016 创建 LangMem 适配器模块
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
记忆管理模块

提供 LangMem 和 LangGraph Checkpointer 的统一接口。

主要组件:
    - LangMemAdapter: 长期记忆管理适配器
    - CheckpointerManager: 工作记忆管理器
    - MemoryMetadata: 记忆元数据
    - MemoryQuery: 记忆查询
    - MemoryResult: 记忆结果
    - MemoryType: 记忆类型枚举
    - LangMemError: 记忆系统错误异常

使用示例:
    from src.infrastructure.memory import LangMemAdapter, MemoryType

    adapter = LangMemAdapter()
    await adapter.add_memory(
        namespace=('memories', 'user_123'),
        content='用户偏好使用技术评估报告模板',
        metadata=MemoryMetadata(memory_type=MemoryType.USER_PREFERENCE)
    )
"""

from .checkpointer import (
    CheckpointerConfig,
    CheckpointerHelper,
    CheckpointerManager,
    create_checkpointer,
    get_checkpointer_manager,
)
from .langmem_adapter import (
    LangMemAdapter,
    LangMemError,
    MemoryEntry,
    MemoryMetadata,
    MemoryQuery,
    MemoryResult,
    MemoryType,
)

__all__ = [
    "CheckpointerConfig",
    "CheckpointerHelper",
    "CheckpointerManager",
    "LangMemAdapter",
    "LangMemError",
    "MemoryEntry",
    "MemoryMetadata",
    "MemoryQuery",
    "MemoryResult",
    "MemoryType",
    "create_checkpointer",
    "get_checkpointer_manager",
]
