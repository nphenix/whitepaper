# 记忆系统基础设施模块

本模块提供长期记忆管理能力,基于LangMem实现。

## 概述

记忆系统是多Agent协作文档处理系统的核心组件之一,负责存储和检索用户交互历史、操作习惯、优化策略等长期记忆。

### 架构设计

记忆系统采用**工作记忆/长期记忆分离**架构:

- **长期记忆 (LangMem)**: 存储用户交互历史、操作习惯、优化策略等 (`langmem_adapter.py`)
- **工作记忆 (LangGraph Checkpointer)**: 存储Agent执行状态,支持工作流恢复 (`checkpointer.py`)

本模块同时实现长期记忆和工作记忆两部分。

### ⚠️ 重要说明：官方最佳实践

根据 LangMem 官方文档（https://github.com/langchain-ai/langmem），推荐的最佳实践是：

1. **使用 namespace 而非 user_id**
   ```python
   # 官方推荐
   namespace = ("user", "user_123")
   ```

2. **集成 LangGraph Store**
   ```python
   from langgraph.store.memory import InMemoryStore
   store = InMemoryStore(index={"dims": 1024, "embed": "dashscope:text-embedding-v4"})
   ```

3. **使用 Tool 模式**
   ```python
   from langmem import create_manage_memory_tool, create_search_memory_tool
   ```

**当前实现**：
- ✅ **集成项目统一 embedding 配置**：使用 `阿里百炼 text-embedding-v4` (维度: **1024** - 以 .env 为准)
- 为了向后兼容和简化使用，当前实现使用 `user_id` 作为记忆隔离标识
- 直接使用 `langmem.Client` (适配 langmem 0.0.3)
- 未来可升级到完整的 Store + Tool 模式

**升级路径**：参见本文档末尾的"升级到官方最佳实践"章节。

### 核心功能

1. **记忆条目管理**: 增删改查操作
2. **语义检索**: 基于自然语言查询相关记忆
3. **版本管理**: 记录记忆的演进历史
4. **用户隔离**: 每个用户独立的记忆空间
5. **元数据管理**: 丰富的元数据支持分类和过滤

## 组件说明

### LangMemAdapter

LangMem适配器是记忆系统的核心类,封装了LangMem客户端的所有功能。

#### 主要特性

- ✅ 记忆条目的增删改查
- ✅ 基于语义的记忆检索
- ✅ 记忆版本管理和演进跟踪
- ✅ 用户级别的记忆隔离
- ✅ 记忆元数据管理
- ✅ 记忆过滤和排序
- ✅ 记忆年龄管理

#### 记忆类型 (MemoryType)

系统定义了以下记忆类型:

| 类型 | 说明 | 示例 |
|------|------|------|
| USER_INTERACTION | 用户交互历史 | 用户上传了一个PDF文档 |
| OPERATION_HABIT | 操作习惯 | 用户习惯使用技术评估报告模板 |
| OPTIMIZATION_STRATEGY | 优化策略 | 对于储能行业,优先检索政策文档 |
| USER_PREFERENCE | 用户偏好 | 用户偏好生成中文报告 |
| DOCUMENT_RECOGNITION | 文档识别记录 | PDF解析错误率为5% |
| PROMPT_OPTIMIZATION | 提示词优化 | 优化后的大纲生成提示词 |
| INTENT_RECOGNITION | 意图识别 | 用户意图是生成市场研究报告 |
| FEEDBACK | 用户反馈 | 用户对检索结果的反馈 |
| SYSTEM_EVENT | 系统事件 | 系统完成了文档索引构建 |
| OTHER | 其他 | 其他类型的记忆 |

## 使用示例

### 基础使用

```python
from src.infrastructure.memory import LangMemAdapter, MemoryType, MemoryQuery, MemoryMetadata

# 创建适配器实例
adapter = LangMemAdapter()

# 添加记忆
memory_id = await adapter.add_memory(
    user_id="user_123",
    content="用户偏好使用技术评估报告模板",
    metadata=MemoryMetadata(
        memory_type=MemoryType.USER_PREFERENCE,
        tags=["template", "preference"],
        importance=0.8
    )
)

# 搜索记忆
results = await adapter.search_memories(
    query=MemoryQuery(
        query_text="用户喜欢什么模板?",
        user_id="user_123",
        memory_types=[MemoryType.USER_PREFERENCE],
        limit=5
    )
)

# 遍历结果
for result in results:
    print(f"记忆: {result.content}")
    print(f"相关性: {result.relevance_score}")
```

### 记忆版本管理

```python
# 启用版本管理
adapter = LangMemAdapter(enable_versioning=True)

# 添加初始记忆
memory_id = await adapter.add_memory(
    user_id="user_123",
    content="用户偏好生成10页的报告",
    metadata=MemoryMetadata(memory_type=MemoryType.USER_PREFERENCE)
)

# 更新记忆 (将创建新版本)
await adapter.update_memory(
    memory_id=memory_id,
    user_id="user_123",
    content="用户偏好生成15页的报告"
)

# 获取记忆演进历史
history = await adapter.get_memory_history(
    memory_id=memory_id,
    user_id="user_123"
)

# 查看所有版本
for i, version in enumerate(history):
    print(f"版本 {i+1}: {version.content}")
```

### 用户交互记录

```python
# 记录用户交互
await adapter.add_memory(
    user_id="user_123",
    content="用户上传了储能行业白皮书PDF文档,文件大小2.5MB",
    metadata=MemoryMetadata(
        memory_type=MemoryType.USER_INTERACTION,
        session_id="session_456",
        tags=["upload", "pdf", "energy_storage"],
        category="document_upload"
    )
)

# 记录系统事件
await adapter.add_memory(
    user_id="user_123",
    content="系统成功完成文档解析,识别出156个段落,准确率98%",
    metadata=MemoryMetadata(
        memory_type=MemoryType.SYSTEM_EVENT,
        session_id="session_456",
        confidence=0.98,
        source="document_parser"
    )
)
```

### 提示词优化记录

```python
# 记录优化后的提示词
await adapter.add_memory(
    user_id="system",  # 系统级记忆
    content=(
        "优化后的大纲生成提示词: "
        "请根据用户输入的大纲和行业背景,分析结构完整性..."
    ),
    metadata=MemoryMetadata(
        memory_type=MemoryType.PROMPT_OPTIMIZATION,
        tags=["outline", "optimization"],
        version=2,
        parent_memory_id="previous_prompt_id",
        confidence=0.85
    )
)

# 检索最优提示词
results = await adapter.search_memories(
    query=MemoryQuery(
        query_text="大纲生成的最佳提示词",
        memory_types=[MemoryType.PROMPT_OPTIMIZATION],
        min_confidence=0.8,
        limit=1
    )
)
```

### 高级查询

```python
# 多条件查询
query = MemoryQuery(
    query_text="用户对储能行业的偏好",
    user_id="user_123",
    memory_types=[
        MemoryType.USER_PREFERENCE,
        MemoryType.OPERATION_HABIT
    ],
    tags=["energy_storage"],
    session_id="session_456",
    min_confidence=0.7,
    limit=10
)

results = await adapter.search_memories(query)
```

### 获取用户所有记忆

```python
# 获取用户所有记忆
all_memories = await adapter.get_user_memories(
    user_id="user_123",
    memory_types=[MemoryType.USER_PREFERENCE, MemoryType.USER_INTERACTION],
    limit=100
)

# 按重要性排序
sorted_memories = sorted(
    all_memories,
    key=lambda m: m.metadata.get("importance", 0.5),
    reverse=True
)
```

### 记忆清理

```python
# 设置记忆最大保留期限
adapter = LangMemAdapter(max_memory_age_days=90)

# 清空用户记忆
await adapter.clear_user_memories(user_id="user_123")
```

## 集成示例

### 与Agent集成

```python
from src.application.agents import StructureOptimizationAgent
from src.infrastructure.memory import LangMemAdapter, MemoryType, MemoryQuery

class StructureOptimizationAgentWithMemory(StructureOptimizationAgent):
    def __init__(self, memory_adapter: LangMemAdapter):
        super().__init__()
        self.memory = memory_adapter
    
    async def optimize_outline(self, user_id: str, outline: str) -> dict:
        # 检索用户偏好
        preferences = await self.memory.search_memories(
            query=MemoryQuery(
                query_text="用户的报告偏好和风格要求",
                user_id=user_id,
                memory_types=[MemoryType.USER_PREFERENCE],
                limit=5
            )
        )
        
        # 基于偏好优化大纲
        optimized_outline = await super().optimize_outline(outline)
        
        # 记录优化结果
        await self.memory.add_memory(
            user_id=user_id,
            content=f"系统为用户优化了大纲,新增了{len(optimized_outline['new_sections'])}个章节",
            metadata=MemoryMetadata(
                memory_type=MemoryType.SYSTEM_EVENT,
                tags=["outline", "optimization"]
            )
        )
        
        return optimized_outline
```

### 与用户服务集成

```python
from src.application.services import UserService
from src.infrastructure.memory import LangMemAdapter, MemoryType

class UserService:
    def __init__(self, memory_adapter: LangMemAdapter):
        self.memory = memory_adapter
    
    async def get_user_preferences(self, user_id: str) -> dict:
        """获取用户偏好摘要"""
        memories = await self.memory.search_memories(
            query=MemoryQuery(
                query_text="用户偏好和习惯",
                user_id=user_id,
                memory_types=[
                    MemoryType.USER_PREFERENCE,
                    MemoryType.OPERATION_HABIT
                ],
                limit=20
            )
        )
        
        # 聚合偏好
        preferences = {
            "report_type": None,
            "language": None,
            "avg_length": None,
            "favorite_templates": []
        }
        
        for memory in memories:
            # 从记忆中提取偏好信息
            # ... 实现偏好提取逻辑
            pass
        
        return preferences
```

## 性能考虑

### 批量操作

```python
# 批量添加记忆
async def batch_add_memories(adapter: LangMemAdapter, memories: list[dict]) -> list[str]:
    memory_ids = []
    for memory_data in memories:
        memory_id = await adapter.add_memory(**memory_data)
        memory_ids.append(memory_id)
    return memory_ids
```

### 缓存策略

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedLangMemAdapter(LangMemAdapter):
    def __init__(self, *args, cache_ttl_seconds: int = 300, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache: dict[str, tuple[datetime, list]] = {}
    
    async def search_memories(self, query: MemoryQuery) -> list[MemoryResult]:
        # 生成缓存键
        cache_key = f"{query.user_id}:{query.query_text}:{query.memory_types}"
        
        # 检查缓存
        if cache_key in self._cache:
            cached_time, cached_results = self._cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                return cached_results
        
        # 执行查询
        results = await super().search_memories(query)
        
        # 更新缓存
        self._cache[cache_key] = (datetime.now(), results)
        
        return results
```

## 错误处理

```python
from src.infrastructure.memory import LangMemAdapter, MemoryError, ValidationError

async def safe_add_memory(adapter: LangMemAdapter, **kwargs):
    try:
        memory_id = await adapter.add_memory(**kwargs)
        return memory_id
    except ValidationError as e:
        print(f"验证错误: {e.message}")
        print(f"字段: {e.details.get('field_name')}")
        return None
    except MemoryError as e:
        print(f"记忆操作失败: {e.message}")
        print(f"操作: {e.details.get('operation')}")
        return None
    except Exception as e:
        print(f"未知错误: {str(e)}")
        return None
```

## 最佳实践

### 1. 记忆内容设计

记忆内容应该是**自然语言描述**,而不是原始数据:

```python
# ✅ 好的实践
await adapter.add_memory(
    user_id="user_123",
    content="用户偏好使用技术评估报告模板,报告长度通常为15-20页"
)

# ❌ 不好的实践
await adapter.add_memory(
    user_id="user_123",
    content='{"template": "tech_eval", "pages": [15, 20]}'
)
```

### 2. 元数据使用

充分利用元数据进行分类和过滤:

```python
metadata = MemoryMetadata(
    memory_type=MemoryType.USER_PREFERENCE,
    category="report_generation",
    tags=["template", "length", "tech_eval"],
    importance=0.8,
    confidence=0.9,
    source="user_input"
)
```

### 3. 版本管理

对于需要追踪演进的记忆,启用版本管理:

```python
adapter = LangMemAdapter(enable_versioning=True)
```

### 4. 记忆清理

定期清理过期记忆:

```python
adapter = LangMemAdapter(max_memory_age_days=90)
```

### 5. 用户隔离

确保用户记忆的隔离性:

```python
# 始终传递user_id
results = await adapter.search_memories(
    query=MemoryQuery(
        query_text="...",
        user_id=user_id  # 必需
    )
)
```

## 数据模型

### MemoryEntry

```python
{
    "memory_id": "uuid-string",
    "user_id": "user_123",
    "content": "用户偏好使用技术评估报告模板",
    "metadata": {
        "memory_type": "user_preference",
        "category": "report_generation",
        "tags": ["template", "preference"],
        "confidence": 0.9,
        "version": 1,
        "importance": 0.8,
        "created_at": "2025-12-08T10:00:00",
        "updated_at": "2025-12-08T10:00:00"
    }
}
```

### MemoryResult

```python
{
    "memory_id": "uuid-string",
    "user_id": "user_123",
    "content": "用户偏好使用技术评估报告模板",
    "metadata": {...},
    "relevance_score": 0.95,
    "created_at": "2025-12-08T10:00:00"
}
```

## 依赖

- `langmem>=0.0.3`: LangMem客户端
- `pydantic>=2.5.2`: 数据验证
- `python-dotenv>=1.0.0`: 环境变量管理

## 相关任务

- ✅ T016: 创建 LangMem 适配器 (长期记忆)
- ✅ T017: 创建 LangGraph Checkpointer 配置 (工作记忆)
- ⏳ T108: 创建记忆服务 (应用层)
- ⏳ T109-T112: 记忆系统功能实现

## 升级到官方最佳实践

如果需要升级到LangMem官方推荐的架构，请参考以下步骤：

### 1. 安装依赖

```bash
pip install langgraph langmem
```

### 2. 使用 Store + Tool 模式

```python
from langgraph.store.memory import InMemoryStore
from langgraph.prebuilt import create_react_agent
from langmem import create_manage_memory_tool, create_search_memory_tool

# 创建Store (使用项目统一的 embedding 配置)
store = InMemoryStore(
    index={
        "dims": 1024,  # 阿里百炼 text-embedding-v4 维度为 1024 (.env 实际配置)
        "embed": "dashscope:text-embedding-v4",  # 使用阿里百炼 embedding
    }
)

# 创建Memory Tools
memory_tools = [
    create_manage_memory_tool(namespace=("memories",)),
    create_search_memory_tool(namespace=("memories",)),
]

# 创建Agent并集成记忆
agent = create_react_agent(
    model="anthropic:claude-3-5-sonnet-latest",
    tools=memory_tools,
    store=store,
)

# 使用
agent.invoke({"messages": [{"role": "user", "content": "记住我喜欢深色模式"}]})
```

**重要**: 
- ✅ 使用 `dashscope:text-embedding-v4` 而非 `openai:text-embedding-3-small`
- ✅ 维度设置为 `1024` ⚠️ **以 .env 实际配置为准**（阿里百炼 text-embedding-v4）
- ✅ 确保已在 `.env` 中配置 `EMBEDDING_API_KEY`

**重要**: 
- ✅ 使用 `dashscope:text-embedding-v4` 而非 `openai:text-embedding-3-small`
- ✅ 维度设置为 `1024` ⚠️ **以 .env 实际配置为准**（阿里百炼 text-embedding-v4）
- ✅ 确保已在 `.env` 中配置 `EMBEDDING_API_KEY`

### 3. 生产环境存储

生产环境推荐使用持久化存储：

```python
from langgraph.store.postgres import AsyncPostgresStore

store = AsyncPostgresStore(
    connection_string="postgresql://user:pass@localhost/db",
    index={
        "dims": 1024,  # 阿里百炼 text-embedding-v4 维度 (以 .env 为准)
        "embed": "dashscope:text-embedding-v4"  # 使用项目统一 embedding
    },
)
```

### 4. 使用 namespace 隔离

```python
# 为不同用户创建独立的namespace
user_namespace = ("user", user_id)
create_manage_memory_tool(namespace=user_namespace)
create_search_memory_tool(namespace=user_namespace)
```

## 参考资料

- [LangMem GitHub](https://github.com/langchain-ai/langmem) ⭐ 官方文档
- [LangMem Hot Path Quickstart](https://github.com/langchain-ai/langmem#hot-path-quickstart)
- [LangGraph Store](https://langchain-ai.github.io/langgraph/how-tos/persistence/)
- [LangGraph Checkpointer API](https://langchain-ai.github.io/langgraph/reference/checkpoints/) ⭐ 官方文档
- [LangChain Documentation](https://python.langchain.com/)
- [项目规范文档](../../../specs/001-multi-agent-doc-system/)

---

## 工作记忆 (LangGraph Checkpointer)

### 概述

工作记忆基于LangGraph Checkpointer实现，用于存储Agent执行状态，支持工作流的持久化、恢复和断点续传。

### 核心功能

1. **状态持久化**: 保存Agent执行过程中的状态快照
2. **工作流恢复**: 从检查点恢复执行，支持断点续传
3. **多存储后端**: 支持内存、SQLite、PostgreSQL等存储
4. **线程安全**: 支持多线程并发访问
5. **版本管理**: 追踪检查点的演进历史
6. **自动清理**: 定期清理过期的检查点

### 支持的存储后端

| 存储类型 | 适用场景 | 优点 | 缺点 |
|---------|---------|------|------|
| MemorySaver | 测试、开发 | 快速、简单 | 不持久化、进程重启后丢失 |
| SqliteSaver | 生产、中小型部署 | 轻量、易用、线程安全 | 单机存储 |
| AsyncSqliteSaver | 异步应用、高并发 | 异步I/O、高性能 | 单机存储 |
| PostgresSaver | 大型生产环境 | 高可用、分布式 | 需要额外部署 |

### 使用示例

#### 1. 基础使用 - 内存存储

```python
from src.infrastructure.memory import create_checkpointer
from langgraph.graph import StateGraph

# 创建内存存储（适用于测试）
saver = create_checkpointer("memory")

# 编译图并启用checkpointer
graph = StateGraph(...).compile(checkpointer=saver)

# 执行时指定thread_id
result = graph.invoke(
    {"input": "Hello"},
    {"configurable": {"thread_id": "thread-1"}}
)
```

#### 2. SQLite存储 - 同步版本

```python
from src.infrastructure.memory import CheckpointerManager
from langgraph.graph import StateGraph

manager = CheckpointerManager()

# 使用上下文管理器（推荐）
with manager.create_sqlite_saver() as saver:
    graph = StateGraph(...).compile(checkpointer=saver)
    
    # 首次执行
    result = graph.invoke(
        {"input": "Step 1"},
        {"configurable": {"thread_id": "thread-1"}}
    )
    
    # 继续执行（从检查点恢复）
    result = graph.invoke(
        {"input": "Step 2"},
        {"configurable": {"thread_id": "thread-1"}}
    )
```

#### 3. SQLite存储 - 异步版本

```python
from src.infrastructure.memory import CheckpointerManager
from langgraph.graph import StateGraph

manager = CheckpointerManager()

async def main():
    # 使用异步上下文管理器
    async with manager.create_async_sqlite_saver() as saver:
        graph = StateGraph(...).compile(checkpointer=saver)
        
        # 异步执行
        result = await graph.ainvoke(
            {"input": "Hello"},
            {"configurable": {"thread_id": "thread-1"}}
        )
        
        return result

import asyncio
asyncio.run(main())
```

#### 4. 默认配置使用

```python
from src.infrastructure.memory import get_checkpointer_manager

# 获取全局管理器
manager = get_checkpointer_manager()

# 根据配置自动选择存储后端
saver = manager.create_default_saver()

graph = StateGraph(...).compile(checkpointer=saver)
```

#### 5. 清理过期检查点

```python
from src.infrastructure.memory import CheckpointerManager, CheckpointerHelper

manager = CheckpointerManager()

with manager.create_sqlite_saver() as saver:
    # 清理24小时前的检查点
    deleted_count = CheckpointerHelper.cleanup_old_checkpoints(
        saver,
        ttl_seconds=86400  # 24小时
    )
    
    print(f"清理了 {deleted_count} 个过期检查点")
    
    # 清理特定线程的检查点
    deleted_count = CheckpointerHelper.cleanup_old_checkpoints(
        saver,
        ttl_seconds=3600,  # 1小时
        thread_id="thread-1"
    )
```

### 与Agent集成

#### LangGraph Agent示例

```python
from langgraph.graph import StateGraph, END
from src.infrastructure.memory import create_checkpointer
from typing import TypedDict, Annotated
import operator

# 定义状态
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    step: int

# 定义节点函数
def process_step(state: AgentState) -> AgentState:
    return {
        "messages": [f"处理步骤 {state['step']}"],
        "step": state["step"] + 1
    }

def should_continue(state: AgentState) -> str:
    if state["step"] > 3:
        return "end"
    return "continue"

# 构建图
builder = StateGraph(AgentState)
builder.add_node("process", process_step)
builder.set_entry_point("process")
builder.add_conditional_edges(
    "process",
    should_continue,
    {
        "continue": "process",
        "end": END
    }
)

# 启用checkpointer
saver = create_checkpointer("sqlite")
graph = builder.compile(checkpointer=saver)

# 执行
config = {"configurable": {"thread_id": "agent-1"}}
result = graph.invoke({"messages": [], "step": 1}, config)
```

#### 断点续传示例

```python
from src.infrastructure.memory import CheckpointerManager
from langgraph.graph import StateGraph

manager = CheckpointerManager()

with manager.create_sqlite_saver() as saver:
    graph = StateGraph(...).compile(checkpointer=saver)
    
    # 第一次执行（可能中断）
    try:
        result = graph.invoke(
            {"input": "开始处理"},
            {"configurable": {"thread_id": "task-1"}}
        )
    except Exception as e:
        print(f"执行中断: {e}")
    
    # 稍后恢复执行
    result = graph.invoke(
        {"input": "继续处理"},
        {"configurable": {"thread_id": "task-1"}}  # 使用相同的thread_id
    )
```

### 配置说明

Checkpointer配置位于`.env`文件中的`AGENT_*`配置项：

```env
# Agent配置
AGENT_CHECKPOINT_TYPE=sqlite  # 存储类型: memory, sqlite
AGENT_CHECKPOINT_DB_PATH=./storage/sqlite/checkpoints.db  # SQLite数据库路径
AGENT_CHECKPOINT_TTL=86400  # 检查点保留时间（秒），默认24小时
```

### 最佳实践

#### 1. 使用上下文管理器

```python
# ✅ 推荐：使用上下文管理器自动管理资源
with manager.create_sqlite_saver() as saver:
    graph = StateGraph(...).compile(checkpointer=saver)
    result = graph.invoke(...)

# ❌ 不推荐：手动管理可能导致资源泄漏
saver = manager.create_default_saver()
graph = StateGraph(...).compile(checkpointer=saver)
# 忘记关闭连接
```

#### 2. 合理设置thread_id

```python
# ✅ 为每个独立的工作流使用唯一的thread_id
config1 = {"configurable": {"thread_id": f"user-{user_id}-task-{task_id}"}}
config2 = {"configurable": {"thread_id": f"batch-{batch_id}"}}

# ❌ 不要在不同工作流中使用相同的thread_id
```

#### 3. 定期清理检查点

```python
# ✅ 在后台任务中定期清理过期检查点
from apscheduler.schedulers.background import BackgroundScheduler

def cleanup_job():
    with manager.create_sqlite_saver() as saver:
        CheckpointerHelper.cleanup_old_checkpoints(saver, ttl_seconds=86400)

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_job, 'interval', hours=24)
scheduler.start()
```

#### 4. 错误处理

```python
from src.shared.exceptions import StorageConnectionError, StorageOperationError

try:
    with manager.create_sqlite_saver() as saver:
        graph = StateGraph(...).compile(checkpointer=saver)
        result = graph.invoke(...)
except StorageConnectionError as e:
    logger.error(f"数据库连接失败: {e}")
except StorageOperationError as e:
    logger.error(f"操作失败: {e}")
```

#### 5. 测试环境使用内存存储

```python
import os

# 根据环境选择存储类型
if os.getenv("ENVIRONMENT") == "testing":
    saver = create_checkpointer("memory")
else:
    saver = create_checkpointer("sqlite")
```

### 性能优化

#### 1. WAL模式

SQLite存储自动启用WAL模式以提高并发性能：

```python
# 已在SqliteSaver创建时自动配置
conn.execute("PRAGMA journal_mode=WAL")
```

#### 2. 批量操作

```python
# 批量处理时使用相同的checkpointer实例
with manager.create_sqlite_saver() as saver:
    graph = StateGraph(...).compile(checkpointer=saver)
    
    for item in batch:
        result = graph.invoke(
            item,
            {"configurable": {"thread_id": f"batch-{item.id}"}}
        )
```

#### 3. 异步处理

```python
# 高并发场景使用异步版本
async with manager.create_async_sqlite_saver() as saver:
    graph = StateGraph(...).compile(checkpointer=saver)
    
    tasks = [
        graph.ainvoke(item, {"configurable": {"thread_id": f"task-{i}"}})
        for i, item in enumerate(items)
    ]
    
    results = await asyncio.gather(*tasks)
```

### 故障排查

#### 问题1: 数据库锁定

```python
# 症状: database is locked 错误
# 解决: 启用WAL模式（已默认启用）或使用异步版本
async with manager.create_async_sqlite_saver() as saver:
    ...
```

#### 问题2: 检查点过多导致性能下降

```python
# 症状: 查询变慢
# 解决: 定期清理过期检查点
CheckpointerHelper.cleanup_old_checkpoints(saver, ttl_seconds=3600)
```

#### 问题3: 进程重启后状态丢失

```python
# 症状: 使用MemorySaver导致状态丢失
# 解决: 生产环境使用SQLite或PostgreSQL
saver = create_checkpointer("sqlite")  # 而非 "memory"
```

### 数据结构

#### Checkpoint结构

```python
{
    "v": 1,  # 格式版本
    "id": "checkpoint-uuid",  # 唯一ID
    "ts": "2025-12-08T10:00:00",  # 时间戳
    "channel_values": {  # 通道值
        "messages": [...],
        "state": {...}
    },
    "channel_versions": {  # 通道版本
        "messages": "v1",
        "state": "v2"
    },
    "versions_seen": {  # 节点已见版本
        "node_1": {"messages": "v1"}
    }
}
```

#### CheckpointMetadata结构

```python
{
    "source": "loop",  # 来源: input, loop, update, fork
    "step": 1,  # 步骤编号
    "parents": {  # 父检查点
        "node_1": "parent-checkpoint-id"
    }
}
```
