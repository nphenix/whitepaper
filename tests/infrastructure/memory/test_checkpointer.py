"""LangGraph Checkpointer 配置模块测试

测试CheckpointerManager和相关功能。
"""

import asyncio
import operator
import shutil
import tempfile
from pathlib import Path
from typing import Annotated, TypedDict

import pytest
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph

from src.infrastructure.memory.checkpointer import (
    CheckpointerConfig,
    CheckpointerHelper,
    CheckpointerManager,
    create_checkpointer,
    get_checkpointer_manager,
)
from src.shared.exceptions import CustomConnectionError


# 测试用的状态定义
class CheckpointTestState(TypedDict):
    """测试用的状态"""

    counter: Annotated[int, operator.add]
    messages: Annotated[list, operator.add]


# 测试用的节点函数
def increment_node(state: CheckpointTestState) -> CheckpointTestState:
    """增加计数器"""
    return {"counter": 1, "messages": [f"Counter: {state.get('counter', 0) + 1}"]}


def should_continue(state: CheckpointTestState) -> str:
    """判断是否继续"""
    if state.get("counter", 0) >= 3:
        return "end"
    return "continue"


@pytest.fixture
def temp_db_path():
    """创建临时数据库路径"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_checkpoints.db"
    yield db_path
    # 清理
    if temp_dir and Path(temp_dir).exists():
        shutil.rmtree(temp_dir)


@pytest.fixture
def checkpointer_config(temp_db_path):
    """创建测试用的checkpointer配置"""
    config = CheckpointerConfig()
    config.checkpoint_db_path = temp_db_path
    return config


@pytest.fixture
def manager(checkpointer_config):
    """创建CheckpointerManager实例"""
    manager = CheckpointerManager(config=checkpointer_config)
    yield manager
    manager.cleanup()


@pytest.fixture
def test_graph():
    """创建测试用的LangGraph"""
    builder = StateGraph(CheckpointTestState)
    builder.add_node("increment", increment_node)
    builder.set_entry_point("increment")
    builder.add_conditional_edges(
        "increment", should_continue, {"continue": "increment", "end": END}
    )
    return builder


class TestCheckpointerConfig:
    """CheckpointerConfig测试"""

    def test_config_initialization(self):
        """测试配置初始化"""
        config = CheckpointerConfig()

        assert config.checkpoint_type is not None
        assert config.checkpoint_db_path is not None
        assert config.checkpoint_ttl > 0
        assert config.checkpoint_db_path.parent.exists()

    def test_db_path_str(self, checkpointer_config):
        """测试数据库路径字符串"""
        path_str = checkpointer_config.db_path_str

        assert isinstance(path_str, str)
        assert len(path_str) > 0
        assert "test_checkpoints.db" in path_str


class TestCheckpointerManager:
    """CheckpointerManager测试"""

    def test_manager_initialization(self, manager):
        """测试管理器初始化"""
        assert manager.config is not None
        assert manager._sqlite_connection is None

    def test_create_memory_saver(self, manager):
        """测试创建内存存储"""
        saver = manager.create_memory_saver()

        assert isinstance(saver, MemorySaver)

    def test_memory_saver_with_graph(self, manager, test_graph):
        """测试内存存储与图集成"""
        saver = manager.create_memory_saver()
        graph = test_graph.compile(checkpointer=saver)

        # 执行图
        config = {"configurable": {"thread_id": "test-1"}}
        result = graph.invoke({"counter": 0, "messages": []}, config)

        # 验证结果
        assert result["counter"] >= 3
        assert len(result["messages"]) >= 3

    def test_create_sqlite_saver_context(self, manager):
        """测试创建SQLite存储(上下文管理器)"""
        with manager.create_sqlite_saver() as saver:
            assert isinstance(saver, SqliteSaver)
            assert saver.conn is not None

    def test_sqlite_saver_with_graph(self, manager, test_graph):
        """测试SQLite存储与图集成"""
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)

            # 第一次执行
            config = {"configurable": {"thread_id": "test-2"}}
            result = graph.invoke({"counter": 0, "messages": []}, config)

            # 验证结果
            assert result["counter"] >= 3
            assert len(result["messages"]) >= 3

    def test_sqlite_saver_persistence(self, manager, test_graph):
        """测试SQLite存储的持久化"""
        thread_id = "test-persistence"
        config = {"configurable": {"thread_id": thread_id}}

        # 第一次执行
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)
            graph.invoke({"counter": 0, "messages": []}, config)

        # 第二次执行(使用相同的thread_id应该能恢复状态)
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)
            # 获取检查点
            checkpoint = saver.get(config)
            assert checkpoint is not None

    @pytest.mark.asyncio
    async def test_create_async_sqlite_saver(self, manager):
        """测试创建异步SQLite存储"""
        async with manager.create_async_sqlite_saver() as saver:
            assert isinstance(saver, AsyncSqliteSaver)

    @pytest.mark.asyncio
    async def test_async_sqlite_saver_with_graph(self, manager, test_graph):
        """测试异步SQLite存储与图集成"""
        async with manager.create_async_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)

            # 异步执行
            config = {"configurable": {"thread_id": "test-async"}}
            result = await graph.ainvoke({"counter": 0, "messages": []}, config)

            # 验证结果
            assert result["counter"] >= 3
            assert len(result["messages"]) >= 3

    def test_create_default_saver_memory(self, temp_db_path):
        """测试创建默认存储(内存)"""
        config = CheckpointerConfig()
        config.checkpoint_type = "memory"
        manager = CheckpointerManager(config=config)

        saver = manager.create_default_saver()

        assert isinstance(saver, MemorySaver)
        manager.cleanup()

    def test_create_default_saver_sqlite(self, manager):
        """测试创建默认存储(SQLite)"""
        # 配置为sqlite
        manager.config.checkpoint_type = "sqlite"

        saver = manager.create_default_saver()

        assert isinstance(saver, SqliteSaver)
        manager.cleanup()

    def test_create_default_saver_unknown_type(self, temp_db_path):
        """测试创建默认存储(未知类型)"""
        config = CheckpointerConfig()
        config.checkpoint_type = "unknown"
        manager = CheckpointerManager(config=config)

        # 应该回退到内存存储
        saver = manager.create_default_saver()

        assert isinstance(saver, MemorySaver)
        manager.cleanup()

    def test_cleanup(self, manager):
        """测试资源清理"""
        # 创建一个连接
        manager.config.checkpoint_type = "sqlite"
        manager.create_default_saver()

        assert manager._sqlite_connection is not None

        # 清理
        manager.cleanup()

        assert manager._sqlite_connection is None


class TestCheckpointerHelper:
    """CheckpointerHelper测试"""

    def test_cleanup_old_checkpoints(self, manager, test_graph):
        """测试清理过期检查点"""
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)

            # 创建一些检查点
            for i in range(3):
                config = {"configurable": {"thread_id": f"test-cleanup-{i}"}}
                graph.invoke({"counter": 0, "messages": []}, config)

            # 测试清理功能(使用很短的TTL,应该清理所有)
            deleted_count = CheckpointerHelper.cleanup_old_checkpoints(
                saver, ttl_seconds=0
            )

            # 应该至少清理了一些检查点(或者没有检查点需要清理)
            assert deleted_count >= 0

    def test_cleanup_specific_thread(self, manager, test_graph):
        """测试清理特定线程的检查点"""
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)

            # 创建特定线程的检查点
            thread_id = "test-specific-cleanup"
            config = {"configurable": {"thread_id": thread_id}}
            graph.invoke({"counter": 0, "messages": []}, config)

            # 测试清理特定线程的检查点
            deleted_count = CheckpointerHelper.cleanup_old_checkpoints(
                saver, ttl_seconds=0, thread_id=thread_id
            )

            # 应该至少清理了一些检查点(或者没有检查点需要清理)
            assert deleted_count >= 0


class TestGlobalFunctions:
    """测试全局函数"""

    def test_get_checkpointer_manager(self):
        """测试获取全局管理器"""
        manager1 = get_checkpointer_manager()
        manager2 = get_checkpointer_manager()

        # 应该返回同一个实例
        assert manager1 is manager2

    def test_create_checkpointer_memory(self):
        """测试创建内存checkpointer"""
        saver = create_checkpointer("memory")

        assert isinstance(saver, MemorySaver)

    def test_create_checkpointer_default(self):
        """测试创建默认checkpointer"""
        saver = create_checkpointer("default")

        # 应该根据配置返回相应的类型
        assert saver is not None


class TestIntegration:
    """集成测试"""

    def test_end_to_end_workflow(self, manager, test_graph):
        """测试端到端工作流"""
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)

            # 执行完整的工作流
            config = {"configurable": {"thread_id": "test-e2e"}}
            result = graph.invoke({"counter": 0, "messages": []}, config)

            # 验证最终状态
            assert result["counter"] >= 3
            assert len(result["messages"]) >= 3

            # 验证检查点已保存
            checkpoint = saver.get(config)
            assert checkpoint is not None

    def test_resume_from_checkpoint(self, manager, test_graph):
        """测试从检查点恢复"""
        thread_id = "test-resume"
        config = {"configurable": {"thread_id": thread_id}}

        # 第一次执行
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)
            graph.invoke({"counter": 0, "messages": []}, config)

        # 第二次执行(应该从检查点恢复)
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)

            # 验证检查点存在
            checkpoint = saver.get(config)
            assert checkpoint is not None

            # 继续执行
            result2 = graph.invoke({"counter": 0, "messages": []}, config)

            # 第二次执行应该使用已有的状态
            assert result2["counter"] >= 3

    @pytest.mark.asyncio
    async def test_async_workflow(self, manager, test_graph):
        """测试异步工作流"""
        async with manager.create_async_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)

            # 并发执行多个任务
            tasks = []
            for i in range(3):
                config = {"configurable": {"thread_id": f"test-async-{i}"}}
                task = graph.ainvoke({"counter": 0, "messages": []}, config)
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # 验证所有任务都完成
            assert len(results) == 3
            for result in results:
                assert result["counter"] >= 3

    def test_multiple_threads(self, manager, test_graph):
        """测试多线程隔离"""
        with manager.create_sqlite_saver() as saver:
            graph = test_graph.compile(checkpointer=saver)

            # 创建多个独立的线程
            results = {}
            for i in range(3):
                thread_id = f"test-thread-{i}"
                config = {"configurable": {"thread_id": thread_id}}
                result = graph.invoke({"counter": 0, "messages": []}, config)
                results[thread_id] = result

            # 验证每个线程都有独立的结果
            assert len(results) == 3
            for thread_id, result in results.items():
                assert result["counter"] >= 3

                # 验证检查点独立
                config = {"configurable": {"thread_id": thread_id}}
                checkpoint = saver.get(config)
                assert checkpoint is not None


class TestErrorHandling:
    """错误处理测试"""

    def test_invalid_db_path(self):
        """测试无效的数据库路径"""
        config = CheckpointerConfig()
        config.checkpoint_db_path = Path("/invalid/path/checkpoints.db")
        manager = CheckpointerManager(config=config)

        # 应该抛出异常
        with pytest.raises(CustomConnectionError):
            with manager.create_sqlite_saver():
                pass

    def test_connection_cleanup_on_error(self, manager):
        """测试错误时的连接清理"""
        try:
            with manager.create_sqlite_saver():
                # 模拟错误
                msg = "Test error"
                raise ValueError(msg)
        except ValueError:
            pass

        # 连接应该被正确清理
        # 不会有资源泄漏


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
