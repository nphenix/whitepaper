# 生成命令: T016 创建 LangMem 适配器 (官方最佳实践版本)
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
LangMem 适配器

基于 LangChain 1.0 官方最佳实践实现的长期记忆管理适配器。

重要更新 (符合官方规范):
    ✅ 使用 namespace 而非 user_id 进行记忆隔离
    ✅ 集成 LangGraph Store (InMemoryStore/AsyncPostgresStore)
    ✅ 配置向量索引 (embedding model)
    ✅ 支持语义检索
    ✅ 提供统一的记忆管理接口

Architecture:
    - 基于 LangGraph Store 作为存储后端
    - 使用 namespace 实现多用户/多场景记忆隔离
    - 配置向量嵌入模型进行语义检索
    - 提供统一的记忆管理接口

兼容性说明:
    本实现兼容 langmem 0.0.30 版本
    使用 LangGraph Store 架构而非旧的 Client API

Reference:
    - LangMem: https://github.com/langchain-ai/langmem
    - LangGraph: https://langchain-ai.github.io/langgraph/
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from src.shared.config.llm_service import get_llm_service
from src.shared.config.settings import get_config
from src.shared.exceptions import BaseApplicationError, ValidationError
from src.shared.utils.logging import get_logger

# LangMem 和 LangGraph Store 导入
try:
    from langgraph.store.memory import InMemoryStore
    from langmem import create_manage_memory_tool, create_search_memory_tool

    LANGMEM_AVAILABLE = True
except ImportError:
    LANGMEM_AVAILABLE = False
    InMemoryStore: type[Any] = Any  # type: ignore[assignment]
    create_manage_memory_tool: type[Any] = Any  # type: ignore[assignment]
    create_search_memory_tool: type[Any] = Any  # type: ignore[assignment]

# 初始化日志记录器
logger = get_logger(__name__)


class LangMemError(BaseApplicationError):
    """记忆系统错误异常"""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        memory_id: str | None = None,
        **kwargs: Any,
    ):
        """初始化记忆错误

        Args:
            message: 错误消息
            operation: 失败的操作
            memory_id: 相关的记忆ID
            **kwargs: 传递给基类的其他参数
        """
        super().__init__(message, **kwargs)
        if operation:
            self.details["operation"] = operation
        if memory_id:
            self.details["memory_id"] = memory_id


class MemoryType(str, Enum):
    """记忆类型枚举

    定义不同类型的记忆条目,用于分类和检索。
    """

    USER_INTERACTION = "user_interaction"
    OPERATION_HABIT = "operation_habit"
    OPTIMIZATION_STRATEGY = "optimization_strategy"
    USER_PREFERENCE = "user_preference"
    DOCUMENT_RECOGNITION = "document_recognition"
    PROMPT_OPTIMIZATION = "prompt_optimization"
    INTENT_RECOGNITION = "intent_recognition"
    FEEDBACK = "feedback"
    SYSTEM_EVENT = "system_event"
    OTHER = "other"


@dataclass
class MemoryMetadata:
    """记忆元数据"""

    memory_type: MemoryType
    session_id: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    confidence: float | None = None
    version: int = 1
    parent_memory_id: str | None = None
    source: str | None = None
    importance: float = 0.5


class MemoryEntry(BaseModel):
    """记忆条目模型

    使用 namespace 作为记忆隔离标识, 符合 LangGraph Store 架构。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    memory_id: str = Field(default_factory=lambda: str(uuid4()))
    namespace: tuple[str, ...] = Field(description="命名空间元组")
    content: str = Field(description="记忆内容")
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_memory_type(self) -> MemoryType:
        """获取记忆类型"""
        memory_type_str = self.metadata.get("memory_type", MemoryType.OTHER.value)
        try:
            return MemoryType(memory_type_str)
        except ValueError:
            return MemoryType.OTHER


class MemoryQuery(BaseModel):
    """记忆查询模型"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    query_text: str = Field(description="查询文本")
    namespace: tuple[str, ...] | None = Field(default=None, description="命名空间")
    memory_types: list[MemoryType] | None = Field(default=None)
    tags: list[str] | None = Field(default=None)
    session_id: str | None = Field(default=None)
    limit: int = Field(default=10, gt=0, le=100)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class MemoryResult(BaseModel):
    """记忆检索结果"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    memory_id: str = Field(description="记忆ID")
    namespace: tuple[str, ...] = Field(description="命名空间")
    content: str = Field(description="记忆内容")
    metadata: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = Field(description="相关性评分", ge=0.0, le=1.0)
    created_at: datetime | None = Field(default=None)


class LangMemAdapter:
    """LangMem 适配器

    封装LangMem和LangGraph Store,提供统一的记忆管理接口。

    官方推荐架构:
        from langgraph.store.memory import InMemoryStore
        store = InMemoryStore(index={
            'dims': 1024,  # 阿里百炼 text-embedding-v4 维度为 1024
            'embed': 'dashscope:text-embedding-v4'  # 使用项目统一配置
        })

    当前实现:
        使用 LangGraph Store 作为存储后端
        使用 namespace 实现记忆隔离
        提供完整的增删改查接口
        集成项目统一的 embedding 配置 (阿里百炼 text-embedding-v4)

    Features:
        - 记忆条目的增删改查
        - 基于语义的记忆检索
        - 记忆版本管理和演进跟踪
        - 命名空间级别的记忆隔离
        - 记忆元数据管理

    Usage:
        >>> adapter = LangMemAdapter()
        >>> await adapter.add_memory(
        ...     namespace=('memories', 'user_123'),
        ...     content='用户偏好使用技术评估报告模板',
        ...     metadata=MemoryMetadata(memory_type=MemoryType.USER_PREFERENCE)
        ... )
    """

    def __init__(
        self,
        store: InMemoryStore | None = None,
        *,
        enable_versioning: bool = True,
        max_memory_age_days: int | None = None,
        config: Any = None,
    ) -> None:
        """初始化LangMem适配器

        Args:
            store: LangGraph Store实例 (如果不提供,将使用项目统一配置创建)
            enable_versioning: 是否启用记忆版本管理
            max_memory_age_days: 记忆最大保留天数
            config: 配置对象 (如果不提供,将自动加载)
        """
        if not LANGMEM_AVAILABLE:
            error_msg = (
                "langmem is not installed. Please install it with: pip install langmem"
            )
            raise ImportError(error_msg)

        # 加载配置
        self.config = config or get_config()

        # 创建或使用提供的 Store
        if store is None:
            # 使用项目统一的 embedding 配置
            embedding_config = self.config.embedding
            logger.info(
                "使用项目统一 embedding 配置创建 LangGraph Store",
                extra={
                    "provider": embedding_config.provider,
                    "model": embedding_config.model_name,
                    "dimension": embedding_config.dimension,
                },
            )

            # 创建 InMemoryStore 配置向量索引
            # 使用 T009 中的嵌入模型服务
            if embedding_config.provider == "dashscope":
                # 对于 DashScope, 我们需要创建一个自定义的嵌入函数
                self.llm_service = get_llm_service()
                embedding_model = self.llm_service.get_embedding_model("dashscope")

                # 创建一个包装函数, 使 DashScope 嵌入模型兼容 LangGraph Store
                def dashscope_embed(texts: list[str]) -> list[list[float]]:
                    # 使用T009集成接口的嵌入方法
                    result = embedding_model.embed_documents(texts)
                    return result  # type: ignore[no-any-return]

                # 配置向量索引, 使用自定义嵌入函数
                self.store = InMemoryStore(
                    index={
                        "dims": embedding_config.dimension,
                        "embed": dashscope_embed,
                    }
                )
            else:
                # 对于其他提供商, 使用标准格式
                self.store = InMemoryStore(
                    index={
                        "dims": embedding_config.dimension,
                        "embed": f"{embedding_config.provider}:{embedding_config.model_name}",
                    }
                )

            # 记录 embedding 配置信息
            self.embedding_provider = embedding_config.provider
            self.embedding_model = embedding_config.model_name
            self.embedding_dimension = embedding_config.dimension
        else:
            self.store = store
            self.embedding_provider = "custom"
            self.embedding_model = "unknown"
            self.embedding_dimension = 0

        self.enable_versioning = enable_versioning
        self.max_memory_age_days = max_memory_age_days

        # 创建记忆管理工具 (使用默认namespace)
        # 注意: langmem工具会自动使用全局store或通过其他方式配置
        # 这里创建工具用于Agent集成, 实际存储操作通过适配器方法进行
        default_namespace = ("memories",)
        try:
            # 尝试创建工具, 如果API不支持store参数则使用默认方式
            self.manage_memory_tool = create_manage_memory_tool(
                namespace=default_namespace
            )
            self.search_memory_tool = create_search_memory_tool(
                namespace=default_namespace
            )
        except TypeError:
            # 如果API不支持某些参数, 使用最简方式
            self.manage_memory_tool = create_manage_memory_tool()
            self.search_memory_tool = create_search_memory_tool()

        logger.info(
            "LangMem适配器初始化完成",
            extra={
                "enable_versioning": enable_versioning,
                "max_memory_age_days": max_memory_age_days,
                "embedding_provider": self.embedding_provider,
                "embedding_model": self.embedding_model,
                "embedding_dimension": self.embedding_dimension,
            },
        )

    async def add_memory(
        self,
        namespace: tuple[str, ...],
        content: str,
        metadata: MemoryMetadata | dict[str, Any] | None = None,
    ) -> str:
        """添加新记忆

        Args:
            namespace: 命名空间元组
            content: 记忆内容
            metadata: 记忆元数据

        Returns:
            记忆ID
        """
        if not namespace:
            error_msg = "namespace不能为空"
            raise ValidationError(error_msg, field_name="namespace")

        if not content or not content.strip():
            error_msg = "content不能为空"
            raise ValidationError(error_msg, field_name="content")

        try:
            memory_id = str(uuid4())
            memory_metadata: dict[str, Any] = {
                "memory_id": memory_id,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            if isinstance(metadata, MemoryMetadata):
                memory_metadata.update(
                    {
                        "memory_type": metadata.memory_type.value,
                        "session_id": metadata.session_id,
                        "category": metadata.category,
                        "tags": metadata.tags,
                        "confidence": metadata.confidence,
                        "version": metadata.version,
                        "parent_memory_id": metadata.parent_memory_id,
                        "source": metadata.source,
                        "importance": metadata.importance,
                    }
                )
            elif isinstance(metadata, dict):
                memory_metadata.update(metadata)

            # 使用 LangGraph Store API 存储记忆
            self.store.put(
                namespace=namespace,
                key=memory_id,
                value={
                    "content": content,
                    "metadata": memory_metadata,
                },
            )

            logger.info(
                "添加记忆成功: memory_id=%s, namespace=%s",
                memory_id,
                namespace,
                extra={"memory_id": memory_id, "namespace": namespace},
            )

            return memory_id

        except Exception as e:
            error_msg = f"添加记忆失败: {e}"
            logger.exception("添加记忆失败: %s", e)
            raise LangMemError(
                error_msg, operation="add_memory", original_error=e
            ) from e

    async def search_memories(self, query: MemoryQuery) -> list[MemoryResult]:
        """搜索记忆"""
        # 对于获取所有记忆的操作, 允许空查询文本
        if not query.query_text or not query.query_text.strip():
            # 空查询只有在limit < 100时才允许(获取所有记忆的合理范围)
            if query.limit < 100:
                # 使用空字符串进行搜索, 获取所有记忆
                pass
            else:
                error_msg = "query_text不能为空"
                raise ValidationError(error_msg, field_name="query_text")

        try:
            # 使用 LangGraph Store API 搜索记忆
            # 使用查询中指定的namespace, 如果没有则使用默认namespace
            search_namespace = query.namespace or ("memories",)
            items = self.store.search(
                search_namespace,
                query=query.query_text,
                limit=query.limit,
            )

            results: list[MemoryResult] = []
            for item in items:
                metadata = item.value.get("metadata", {})
                content = item.value.get("content", "")

                if not self._match_filters(metadata, query):
                    continue

                result = MemoryResult(
                    memory_id=item.key,
                    namespace=item.namespace,
                    content=content,
                    metadata=metadata,
                    relevance_score=float(
                        item.score
                        if hasattr(item, "score") and item.score is not None
                        else 0.0
                    ),
                    created_at=(
                        datetime.fromisoformat(metadata["created_at"])
                        if "created_at" in metadata
                        else None
                    ),
                )
                results.append(result)

            logger.info(
                "搜索记忆完成: query=%s, results=%s", query.query_text, len(results)
            )

            return results

        except Exception as e:
            error_msg = f"搜索记忆失败: {e}"
            logger.exception("搜索记忆失败: %s", e)
            raise LangMemError(
                error_msg, operation="search_memories", original_error=e
            ) from e

    async def update_memory(
        self,
        memory_id: str,
        namespace: tuple[str, ...],
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """更新记忆 (通过版本管理实现)"""
        if not memory_id or not memory_id.strip():
            error_msg = "memory_id不能为空"
            raise ValidationError(error_msg, field_name="memory_id")

        if not namespace:
            error_msg = "namespace不能为空"
            raise ValidationError(error_msg, field_name="namespace")

        try:
            if self.enable_versioning:
                # 获取原记忆
                item = self.store.get(namespace=namespace, key=memory_id)
                if not item:
                    error_msg = f"未找到记忆: memory_id={memory_id}"
                    raise LangMemError(
                        error_msg,
                        operation="update_memory",
                        memory_id=memory_id,
                    )

                old_content = item.value.get("content", "")
                old_metadata = item.value.get("metadata", {})

                # 构建新版本
                new_metadata = old_metadata.copy()
                if metadata:
                    new_metadata.update(metadata)

                current_version = new_metadata.get("version", 1)
                new_metadata["version"] = current_version + 1
                new_metadata["parent_memory_id"] = memory_id
                new_metadata["updated_at"] = datetime.now().isoformat()

                new_content = content if content else old_content
                new_memory_id = str(uuid4())

                # 存储新版本
                self.store.put(
                    namespace=namespace,
                    key=new_memory_id,
                    value={
                        "content": new_content,
                        "metadata": new_metadata,
                    },
                )

                logger.info("更新记忆成功(版本管理): memory_id=%s", memory_id)
            else:
                logger.warning("版本管理未启用,更新操作被跳过")

        except LangMemError:
            raise
        except Exception as e:
            error_msg = f"更新记忆失败: {e}"
            logger.exception("更新记忆失败: %s", e)
            raise LangMemError(
                error_msg,
                operation="update_memory",
                memory_id=memory_id,
                original_error=e,
            ) from e

    async def delete_memory(self, memory_id: str, namespace: tuple[str, ...]) -> None:
        """删除记忆"""
        if not memory_id or not memory_id.strip():
            error_msg = "memory_id不能为空"
            raise ValidationError(error_msg, field_name="memory_id")

        if not namespace:
            error_msg = "namespace不能为空"
            raise ValidationError(error_msg, field_name="namespace")

        try:
            # 使用 LangGraph Store API 删除记忆
            self.store.delete(namespace=namespace, key=memory_id)

            logger.info(
                "删除记忆成功: memory_id=%s, namespace=%s",
                memory_id,
                namespace,
                extra={"memory_id": memory_id, "namespace": namespace},
            )

        except Exception as e:
            error_msg = f"删除记忆失败: {e}"
            logger.exception("删除记忆失败: %s", e)
            raise LangMemError(
                error_msg,
                operation="delete_memory",
                memory_id=memory_id,
                original_error=e,
            ) from e

    async def get_namespace_memories(
        self,
        namespace: tuple[str, ...],
        memory_types: list[MemoryType] | None = None,
        limit: int = 100,
    ) -> list[MemoryResult]:
        """获取命名空间的所有记忆"""
        if not namespace:
            error_msg = "namespace不能为空"
            raise ValidationError(error_msg, field_name="namespace")

        try:
            # 使用空查询获取所有记忆
            query = MemoryQuery(
                query_text="*",  # 使用通配符而不是空字符串
                namespace=namespace,
                memory_types=memory_types,
                limit=min(limit, 100),  # 确保不超过最大限制
            )

            results = await self.search_memories(query)

            logger.info(
                "获取命名空间记忆完成: namespace=%s, count=%s", namespace, len(results)
            )

            return results

        except Exception as e:
            error_msg = f"获取命名空间记忆失败: {e}"
            logger.exception("获取命名空间记忆失败: %s", e)
            raise LangMemError(
                error_msg, operation="get_namespace_memories", original_error=e
            ) from e

    async def get_memory_history(
        self, memory_id: str, namespace: tuple[str, ...]
    ) -> list[MemoryResult]:
        """获取记忆的演进历史"""
        if not self.enable_versioning:
            logger.warning("版本管理未启用")
            return []

        if not memory_id or not memory_id.strip():
            error_msg = "memory_id不能为空"
            raise ValidationError(error_msg, field_name="memory_id")

        if not namespace:
            error_msg = "namespace不能为空"
            raise ValidationError(error_msg, field_name="namespace")

        try:
            all_memories = await self.get_namespace_memories(namespace, limit=100)

            history: list[MemoryResult] = []
            current_id: str | None = memory_id

            while current_id:
                current_memory = None
                for m in all_memories:
                    if m.memory_id == current_id:
                        current_memory = m
                        break

                if not current_memory:
                    break

                history.append(current_memory)
                current_id = current_memory.metadata.get("parent_memory_id")

            history.reverse()

            logger.info(
                "获取记忆历史完成: memory_id=%s, versions=%s", memory_id, len(history)
            )

            return history

        except Exception as e:
            error_msg = f"获取记忆历史失败: {e}"
            logger.exception("获取记忆历史失败: %s", e)
            raise LangMemError(
                error_msg,
                operation="get_memory_history",
                memory_id=memory_id,
                original_error=e,
            ) from e

    def _match_filters(self, metadata: dict[str, Any], query: MemoryQuery) -> bool:
        """检查元数据是否匹配查询过滤条件"""
        # 检查记忆类型
        if query.memory_types:
            memory_type_str = metadata.get("memory_type")
            if memory_type_str:
                try:
                    memory_type = MemoryType(memory_type_str)
                    if memory_type not in query.memory_types:
                        return False
                except ValueError:
                    return False

        # 检查标签
        if query.tags:
            memory_tags = metadata.get("tags", [])
            if not any(tag in memory_tags for tag in query.tags):
                return False

        # 检查会话ID
        if query.session_id and metadata.get("session_id") != query.session_id:
            return False

        # 检查置信度
        if query.min_confidence is not None:
            confidence = metadata.get("confidence")
            if confidence is None or confidence < query.min_confidence:
                return False

        # 检查记忆年龄
        if self.max_memory_age_days is not None:
            created_at_str = metadata.get("created_at")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    age_days = (datetime.now() - created_at).days
                    if age_days > self.max_memory_age_days:
                        return False
                except (ValueError, TypeError):
                    pass

        return True

    async def clear_namespace_memories(self, namespace: tuple[str, ...]) -> None:
        """清空命名空间的所有记忆"""
        if not namespace:
            error_msg = "namespace不能为空"
            raise ValidationError(error_msg, field_name="namespace")

        try:
            # 获取所有记忆
            memories = await self.get_namespace_memories(namespace, limit=100)

            # 删除所有记忆
            for memory in memories:
                await self.delete_memory(memory.memory_id, namespace)

            logger.info(
                "清空命名空间记忆完成: namespace=%s, count=%s", namespace, len(memories)
            )

        except Exception as e:
            error_msg = f"清空命名空间记忆失败: {e}"
            logger.exception("清空命名空间记忆失败: %s", e)
            raise LangMemError(
                error_msg, operation="clear_namespace_memories", original_error=e
            ) from e

    def get_memory_tools(self, namespace: tuple[str, ...] | None = None) -> list[Any]:
        """获取记忆管理工具列表,供Agent使用

        基于LangChain 1.0和LangMem最佳实践,返回记忆管理工具。
        这些工具可以直接传递给create_agent使用。

        Args:
            namespace: 命名空间元组,如果为None则使用默认namespace ('memories',)

        Returns:
            记忆工具列表,包含manage_memory_tool和search_memory_tool

        Examples:
            >>> adapter = LangMemAdapter()
            >>> tools = adapter.get_memory_tools(namespace=('user', 'user_123'))
            >>> agent = create_agent(
            ...     model=model,
            ...     tools=tools,
            ...     system_prompt='You can manage memories using the provided tools.'
            ... )
        """
        if not LANGMEM_AVAILABLE:
            logger.warning("LangMem不可用,无法创建记忆工具")
            return []

        try:
            if namespace is None:
                namespace = ("memories",)

            # 为指定namespace创建工具
            manage_tool = create_manage_memory_tool(namespace=namespace)
            search_tool = create_search_memory_tool(namespace=namespace)

            tools = [manage_tool, search_tool]

            logger.info(
                "创建记忆工具成功: namespace=%s, count=%s", namespace, len(tools)
            )

            return tools

        except Exception as e:
            logger.exception("创建记忆工具失败: %s", e)
            # 如果创建失败,返回默认工具
            return [self.manage_memory_tool, self.search_memory_tool]

    def create_memory_tools_for_namespace(
        self, namespace: tuple[str, ...]
    ) -> list[Any]:
        """为指定namespace创建记忆工具(便捷方法)

        Args:
            namespace: 命名空间元组

        Returns:
            记忆工具列表
        """
        return self.get_memory_tools(namespace=namespace)
