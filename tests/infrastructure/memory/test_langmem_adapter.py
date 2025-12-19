# 生成命令: T016 创建 LangMem 适配器测试
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
LangMem适配器测试

测试LangMem适配器的核心功能:
- 记忆的增删改查
- 语义检索
- 版本管理
- 命名空间隔离
- 元数据管理
"""

from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from src.infrastructure.memory import (
    LangMemAdapter,
    LangMemError,
    MemoryMetadata,
    MemoryQuery,
    MemoryResult,
    MemoryType,
)
from src.shared.exceptions import ValidationError

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_langmem_store():
    """模拟LangGraph Store"""
    mock_store = MagicMock()

    # 模拟put方法
    mock_store.put = MagicMock()

    # 模拟search方法
    mock_item = MagicMock()
    mock_item.key = str(uuid4())
    mock_item.namespace = ("memories", "user_123")
    mock_item.value = {
        "content": "测试记忆内容",
        "metadata": {
            "memory_id": str(uuid4()),
            "memory_type": MemoryType.USER_PREFERENCE.value,
            "created_at": datetime.now().isoformat(),
        },
    }
    mock_item.score = 0.95

    mock_store.search = MagicMock(return_value=[mock_item])

    # 模拟get方法
    mock_store.get = MagicMock(return_value=mock_item)

    # 模拟delete方法
    mock_store.delete = MagicMock()

    return mock_store


@pytest.fixture
def adapter(mock_langmem_store):
    """创建LangMem适配器实例"""
    return LangMemAdapter(store=mock_langmem_store)


@pytest.fixture
def adapter_with_versioning(mock_langmem_store):
    """创建启用版本管理的LangMem适配器实例"""
    return LangMemAdapter(store=mock_langmem_store, enable_versioning=True)


# ============================================================================
# 测试: 初始化
# ============================================================================


def test_adapter_initialization():
    """测试适配器初始化"""
    # 注意: 这个测试需要真实的langmem安装,可能会失败
    try:
        adapter = LangMemAdapter()
        assert adapter.store is not None
        assert adapter.enable_versioning is True
        assert adapter.max_memory_age_days is None
    except ImportError:
        pytest.skip("langmem not available")


def test_adapter_initialization_with_params(mock_langmem_store):
    """测试带参数的适配器初始化"""
    adapter = LangMemAdapter(
        store=mock_langmem_store,
        enable_versioning=False,
        max_memory_age_days=30,
    )
    assert adapter.enable_versioning is False
    assert adapter.max_memory_age_days == 30
    assert adapter.store == mock_langmem_store


# ============================================================================
# 测试: 添加记忆
# ============================================================================


@pytest.mark.asyncio
async def test_add_memory_success(adapter):
    """测试成功添加记忆"""
    memory_id = await adapter.add_memory(
        namespace=("memories", "user_123"),
        content="用户偏好使用技术评估报告模板",
        metadata=MemoryMetadata(
            memory_type=MemoryType.USER_PREFERENCE, tags=["template", "preference"]
        ),
    )

    assert memory_id is not None
    assert isinstance(memory_id, str)
    adapter.store.put.assert_called_once()


@pytest.mark.asyncio
async def test_add_memory_with_dict_metadata(adapter):
    """测试使用字典元数据添加记忆"""
    metadata_dict = {
        "memory_type": MemoryType.USER_PREFERENCE.value,
        "tags": ["test"],
        "custom_field": "custom_value",
    }

    memory_id = await adapter.add_memory(
        namespace=("memories", "user_123"),
        content="测试内容",
        metadata=metadata_dict,
    )

    assert memory_id is not None
    adapter.store.put.assert_called_once()


@pytest.mark.asyncio
async def test_add_memory_empty_namespace(adapter):
    """测试空namespace"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.add_memory(namespace=(), content="测试内容")

    assert "namespace不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_memory_empty_content(adapter):
    """测试空content"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.add_memory(namespace=("memories", "user_123"), content="")

    assert "content不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_add_memory_store_error(adapter):
    """测试存储错误"""
    adapter.store.put.side_effect = Exception("模拟错误")

    with pytest.raises(LangMemError) as exc_info:
        await adapter.add_memory(namespace=("memories", "user_123"), content="测试内容")

    assert "添加记忆失败" in str(exc_info.value)


# ============================================================================
# 测试: 搜索记忆
# ============================================================================


@pytest.mark.asyncio
async def test_search_memories_success(adapter):
    """测试成功搜索记忆"""
    query = MemoryQuery(
        query_text="用户偏好",
        namespace=("memories", "user_123"),
        memory_types=[MemoryType.USER_PREFERENCE],
        limit=5,
    )

    results = await adapter.search_memories(query)

    assert isinstance(results, list)
    assert len(results) > 0
    assert isinstance(results[0], MemoryResult)
    adapter.store.search.assert_called_once()


@pytest.mark.asyncio
async def test_search_memories_empty_query(adapter):
    """测试空查询文本 - 在合理limit范围内应该允许"""
    query = MemoryQuery(query_text="", namespace=("memories", "user_123"), limit=10)

    # 空查询在limit <= 100时应该被允许
    results = await adapter.search_memories(query)
    assert isinstance(results, list)
    adapter.store.search.assert_called_once()


@pytest.mark.asyncio
async def test_search_memories_empty_query_large_limit(adapter):
    """测试空查询文本 - 在大limit情况下应该被拒绝"""
    # 使用最大允许的limit值,但空查询仍应被拒绝
    query = MemoryQuery(query_text="", namespace=("memories", "user_123"), limit=100)

    with pytest.raises(ValidationError) as exc_info:
        await adapter.search_memories(query)

    assert "query_text不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_memories_with_filters(adapter):
    """测试带过滤条件的搜索"""
    # 模拟搜索结果
    mock_item = adapter.store.search.return_value[0]
    mock_item.value["metadata"] = {
        "memory_id": str(uuid4()),
        "memory_type": MemoryType.USER_PREFERENCE.value,
        "tags": ["template"],
        "session_id": "session_123",
        "confidence": 0.9,
        "created_at": datetime.now().isoformat(),
    }

    query = MemoryQuery(
        query_text="用户偏好",
        namespace=("memories", "user_123"),
        memory_types=[MemoryType.USER_PREFERENCE],
        tags=["template"],
        session_id="session_123",
        min_confidence=0.8,
        limit=10,
    )

    results = await adapter.search_memories(query)

    assert len(results) > 0


@pytest.mark.asyncio
async def test_search_memories_filter_mismatch(adapter):
    """测试过滤条件不匹配"""
    # 模拟搜索结果
    mock_item = adapter.store.search.return_value[0]
    mock_item.value["metadata"] = {
        "memory_id": str(uuid4()),
        "memory_type": MemoryType.USER_INTERACTION.value,  # 不匹配
        "created_at": datetime.now().isoformat(),
    }

    query = MemoryQuery(
        query_text="用户偏好",
        namespace=("memories", "user_123"),
        memory_types=[MemoryType.USER_PREFERENCE],  # 期望的类型
    )

    results = await adapter.search_memories(query)

    # 结果应该被过滤掉
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_memories_store_error(adapter):
    """测试搜索时存储错误"""
    adapter.store.search.side_effect = Exception("模拟错误")

    query = MemoryQuery(query_text="测试", namespace=("memories", "user_123"))

    with pytest.raises(LangMemError) as exc_info:
        await adapter.search_memories(query)

    assert "搜索记忆失败" in str(exc_info.value)


# ============================================================================
# 测试: 更新记忆
# ============================================================================


@pytest.mark.asyncio
async def test_update_memory_with_versioning(adapter_with_versioning):
    """测试启用版本管理时的记忆更新"""
    memory_id = str(uuid4())
    namespace = ("memories", "user_123")

    await adapter_with_versioning.update_memory(
        memory_id=memory_id, namespace=namespace, content="更新后的内容"
    )

    # 验证get和put都被调用
    adapter_with_versioning.store.get.assert_called_once_with(
        namespace=namespace, key=memory_id
    )
    adapter_with_versioning.store.put.assert_called()


@pytest.mark.asyncio
async def test_update_memory_without_versioning(adapter):
    """测试未启用版本管理时的记忆更新"""
    adapter.enable_versioning = False
    memory_id = str(uuid4())
    namespace = ("memories", "user_123")

    await adapter.update_memory(
        memory_id=memory_id, namespace=namespace, content="更新后的内容"
    )

    # 应该不调用任何存储操作
    adapter.store.get.assert_not_called()
    adapter.store.put.assert_not_called()


@pytest.mark.asyncio
async def test_update_memory_empty_memory_id(adapter):
    """测试空memory_id"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.update_memory(
            memory_id="", namespace=("memories",), content="新内容"
        )

    assert "memory_id不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_memory_empty_namespace(adapter):
    """测试空namespace"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.update_memory(memory_id="test", namespace=(), content="新内容")

    assert "namespace不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_memory_not_found(adapter_with_versioning):
    """测试更新不存在的记忆"""
    adapter_with_versioning.store.get.return_value = None

    with pytest.raises(LangMemError) as exc_info:
        await adapter_with_versioning.update_memory(
            memory_id=str(uuid4()), namespace=("memories", "user_123"), content="新内容"
        )

    assert "未找到记忆" in str(exc_info.value)


# ============================================================================
# 测试: 删除记忆
# ============================================================================


@pytest.mark.asyncio
async def test_delete_memory(adapter):
    """测试删除记忆"""
    memory_id = str(uuid4())
    namespace = ("memories", "user_123")

    await adapter.delete_memory(memory_id=memory_id, namespace=namespace)

    adapter.store.delete.assert_called_once_with(namespace=namespace, key=memory_id)


@pytest.mark.asyncio
async def test_delete_memory_empty_memory_id(adapter):
    """测试空memory_id"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.delete_memory(memory_id="", namespace=("memories",))

    assert "memory_id不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_memory_empty_namespace(adapter):
    """测试空namespace"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.delete_memory(memory_id="test", namespace=())

    assert "namespace不能为空" in str(exc_info.value)


# ============================================================================
# 测试: 获取命名空间记忆
# ============================================================================


@pytest.mark.asyncio
async def test_get_namespace_memories(adapter):
    """测试获取命名空间所有记忆"""
    namespace = ("memories", "user_123")

    results = await adapter.get_namespace_memories(namespace)

    assert isinstance(results, list)
    adapter.store.search.assert_called_once()


@pytest.mark.asyncio
async def test_get_namespace_memories_with_type_filter(adapter):
    """测试按类型过滤命名空间记忆"""
    namespace = ("memories", "user_123")

    await adapter.get_namespace_memories(
        namespace=namespace,
        memory_types=[MemoryType.USER_PREFERENCE, MemoryType.USER_INTERACTION],
    )

    # 验证search被调用
    adapter.store.search.assert_called_once()


@pytest.mark.asyncio
async def test_get_namespace_memories_empty_namespace(adapter):
    """测试空namespace"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.get_namespace_memories(namespace=())

    assert "namespace不能为空" in str(exc_info.value)


# ============================================================================
# 测试: 获取记忆历史
# ============================================================================


@pytest.mark.asyncio
async def test_get_memory_history(adapter_with_versioning):
    """测试获取记忆演进历史"""
    # 模拟记忆链: v1 -> v2 -> v3
    memory_id_v3 = str(uuid4())
    memory_id_v2 = str(uuid4())
    memory_id_v1 = str(uuid4())
    namespace = ("memories", "user_123")

    # 模拟多个记忆项
    mock_items = []
    for i, (mid, pid) in enumerate(
        [
            (memory_id_v3, memory_id_v2),
            (memory_id_v2, memory_id_v1),
            (memory_id_v1, None),
        ],
        1,
    ):
        mock_item = MagicMock()
        mock_item.key = mid
        mock_item.namespace = namespace
        mock_item.value = {
            "content": f"版本{i}",
            "metadata": {
                "version": i,
                "parent_memory_id": pid,
            },
        }
        mock_items.append(mock_item)

    adapter_with_versioning.store.search.return_value = mock_items

    history = await adapter_with_versioning.get_memory_history(
        memory_id=memory_id_v3, namespace=namespace
    )

    # 历史应该按版本升序排列
    assert len(history) == 3
    assert history[0].memory_id == memory_id_v1
    assert history[1].memory_id == memory_id_v2
    assert history[2].memory_id == memory_id_v3


@pytest.mark.asyncio
async def test_get_memory_history_versioning_disabled(adapter):
    """测试未启用版本管理时获取历史"""
    adapter.enable_versioning = False

    history = await adapter.get_memory_history(
        memory_id=str(uuid4()), namespace=("memories",)
    )

    # 应该返回空列表
    assert history == []


@pytest.mark.asyncio
async def test_get_memory_history_empty_memory_id(adapter):
    """测试空memory_id"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.get_memory_history(memory_id="", namespace=("memories",))

    assert "memory_id不能为空" in str(exc_info.value)


@pytest.mark.asyncio
async def test_get_memory_history_empty_namespace(adapter):
    """测试空namespace"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.get_memory_history(memory_id="test", namespace=())

    assert "namespace不能为空" in str(exc_info.value)


# ============================================================================
# 测试: 清空命名空间记忆
# ============================================================================


@pytest.mark.asyncio
async def test_clear_namespace_memories(adapter):
    """测试清空命名空间记忆"""
    namespace = ("memories", "user_123")

    await adapter.clear_namespace_memories(namespace)

    # 验证search被调用获取所有记忆
    adapter.store.search.assert_called()


@pytest.mark.asyncio
async def test_clear_namespace_memories_empty_namespace(adapter):
    """测试空namespace"""
    with pytest.raises(ValidationError) as exc_info:
        await adapter.clear_namespace_memories(namespace=())

    assert "namespace不能为空" in str(exc_info.value)


# ============================================================================
# 测试: 过滤逻辑
# ============================================================================


def test_match_filters_memory_type(adapter):
    """测试记忆类型过滤"""
    metadata = {"memory_type": MemoryType.USER_PREFERENCE.value}

    query = MemoryQuery(
        query_text="测试",
        memory_types=[MemoryType.USER_PREFERENCE],
    )

    assert adapter._match_filters(metadata, query) is True

    query.memory_types = [MemoryType.USER_INTERACTION]
    assert adapter._match_filters(metadata, query) is False


def test_match_filters_tags(adapter):
    """测试标签过滤"""
    metadata = {"tags": ["template", "preference"]}

    query = MemoryQuery(
        query_text="测试",
        tags=["template"],
    )

    assert adapter._match_filters(metadata, query) is True

    query.tags = ["nonexistent"]
    assert adapter._match_filters(metadata, query) is False


def test_match_filters_session_id(adapter):
    """测试会话ID过滤"""
    metadata = {"session_id": "session_123"}

    query = MemoryQuery(
        query_text="测试",
        session_id="session_123",
    )

    assert adapter._match_filters(metadata, query) is True

    query.session_id = "session_456"
    assert adapter._match_filters(metadata, query) is False


def test_match_filters_confidence(adapter):
    """测试置信度过滤"""
    metadata = {"confidence": 0.9}

    query = MemoryQuery(
        query_text="测试",
        min_confidence=0.8,
    )

    assert adapter._match_filters(metadata, query) is True

    query.min_confidence = 0.95
    assert adapter._match_filters(metadata, query) is False


def test_match_filters_age(adapter):
    """测试记忆年龄过滤"""
    adapter.max_memory_age_days = 30

    # 新记忆
    metadata = {"created_at": datetime.now().isoformat()}
    query = MemoryQuery(query_text="测试")
    assert adapter._match_filters(metadata, query) is True

    # 旧记忆
    from datetime import timedelta

    old_date = datetime.now() - timedelta(days=60)
    metadata = {"created_at": old_date.isoformat()}
    assert adapter._match_filters(metadata, query) is False


# ============================================================================
# 测试: MemoryMetadata数据类
# ============================================================================


def test_memory_metadata_creation():
    """测试MemoryMetadata创建"""
    metadata = MemoryMetadata(
        memory_type=MemoryType.USER_PREFERENCE,
        session_id="session_123",
        tags=["test"],
        confidence=0.9,
    )

    assert metadata.memory_type == MemoryType.USER_PREFERENCE
    assert metadata.session_id == "session_123"
    assert metadata.tags == ["test"]
    assert metadata.confidence == 0.9
    assert metadata.version == 1


# ============================================================================
# 测试: MemoryEntry模型
# ============================================================================


def test_memory_entry_creation():
    """测试MemoryEntry创建"""
    from src.infrastructure.memory.langmem_adapter import MemoryEntry

    entry = MemoryEntry(
        namespace=("memories", "user_123"),
        content="测试记忆",
        metadata={"memory_type": MemoryType.USER_PREFERENCE.value},
    )

    assert entry.namespace == ("memories", "user_123")
    assert entry.content == "测试记忆"
    assert entry.memory_id is not None


def test_memory_entry_get_memory_type():
    """测试获取记忆类型"""
    from src.infrastructure.memory.langmem_adapter import MemoryEntry

    entry = MemoryEntry(
        namespace=("memories", "user_123"),
        content="测试记忆",
        metadata={"memory_type": MemoryType.USER_PREFERENCE.value},
    )

    memory_type = entry.get_memory_type()
    assert memory_type == MemoryType.USER_PREFERENCE


# ============================================================================
# 测试: MemoryQuery模型验证
# ============================================================================


def test_memory_query_validation():
    """测试MemoryQuery验证"""
    # 有效查询
    query = MemoryQuery(
        query_text="测试",
        namespace=("memories", "user_123"),
        limit=10,
    )
    assert query.limit == 10

    # limit超出范围
    with pytest.raises(Exception):  # Pydantic会抛出验证错误
        MemoryQuery(query_text="测试", limit=1000)  # 超过100


# ============================================================================
# 测试: MemoryResult模型
# ============================================================================


def test_memory_result_creation():
    """测试MemoryResult创建"""
    result = MemoryResult(
        memory_id=str(uuid4()),
        namespace=("memories", "user_123"),
        content="测试内容",
        metadata={},
        relevance_score=0.95,
    )

    assert result.relevance_score == 0.95
    assert result.content == "测试内容"
    assert result.namespace == ("memories", "user_123")


# ============================================================================
# 测试: LangMemError异常
# ============================================================================


def test_langmem_error_creation():
    """测试LangMemError创建"""
    error = LangMemError(
        message="测试错误",
        operation="add_memory",
        memory_id="test_id",
    )

    assert error.message == "测试错误"
    assert error.details["operation"] == "add_memory"
    assert error.details["memory_id"] == "test_id"
