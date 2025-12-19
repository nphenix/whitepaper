# 生成命令: T014 NetworkX 图存储适配器和图管理器
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
NetworkX 图管理器单元测试
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.storage.networkx.graph_manager import (
    NetworkXGraphManager,
    create_graph_manager,
    get_graph_manager,
)
from src.shared.exceptions.storage_exceptions import NetworkXError

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """创建一个事件循环实例用于整个测试会话"""
    loop = asyncio.new_event_loop()
    yield loop
    # 确保所有异步任务完成
    loop.close()


class TestNetworkXGraphManager:
    """NetworkX 图管理器测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    @pytest.fixture
    def graph_manager(self, temp_dir):
        """图管理器实例"""
        manager = NetworkXGraphManager(
            data_directory=temp_dir,
            default_graph_name="test_graph",
            default_graph_type="DiGraph",
            auto_save=False,  # 测试时禁用自动保存
            enable_persistence=True,
            file_format="gml",
        )
        yield manager
        # 确保测试结束时关闭所有连接
        try:
            # 先尝试同步关闭
            manager.close()
            # 如果还有异步连接,尝试异步关闭
            if manager._async_graphs:
                try:
                    # 尝试获取当前事件循环
                    try:
                        loop = asyncio.get_running_loop()
                        # 如果事件循环正在运行,我们不能在这里同步等待
                        loop.create_task(manager.aclose())
                        logger.debug("已安排异步图管理器关闭任务")
                    except RuntimeError:
                        # 没有运行中的事件循环,尝试创建一个新的来关闭连接
                        try:
                            asyncio.run(manager.aclose())
                        except RuntimeError:
                            # 如果无法创建事件循环,至少清空连接池
                            logger.warning(
                                "无法创建事件循环来关闭异步图管理器,清空连接池"
                            )
                            manager._async_graphs.clear()
                except Exception as e:
                    # 如果无法关闭异步连接,至少清空连接池
                    logger.warning(f"关闭异步图管理器时出错: {e},清空连接池")
                    manager._async_graphs.clear()
        except Exception as e:
            # 忽略关闭时的错误,但记录警告
            logger.warning(f"关闭图管理器时出错: {e}")

    def test_init(self, temp_dir):
        """测试初始化"""
        manager = NetworkXGraphManager(
            data_directory=temp_dir,
            default_graph_name="test_graph",
            default_graph_type="Graph",
            auto_save=True,
            auto_save_interval=60,
            enable_persistence=True,
            file_format="json",
        )

        assert manager.data_directory == temp_dir
        assert manager.default_graph_name == "test_graph"
        assert manager.default_graph_type == "Graph"
        assert manager.auto_save is True
        assert manager.auto_save_interval == 60
        assert manager.enable_persistence is True
        assert manager.file_format == "json"

    def test_init_with_defaults(self):
        """测试使用默认值初始化"""
        with patch(
            "src.infrastructure.storage.networkx.graph_manager.get_config"
        ) as mock_get_config:
            mock_config = MagicMock()
            mock_config.database.networkx_data_directory = "data/networkx"
            mock_config.database.networkx_default_graph_name = "default_graph"
            mock_get_config.return_value = mock_config

            manager = NetworkXGraphManager()

            assert manager.data_directory == Path("data/networkx")
            assert manager.default_graph_name == "default_graph"
            assert manager.default_graph_type == "DiGraph"  # 默认值
            assert manager.auto_save is True  # 默认值
            assert manager.enable_persistence is True  # 默认值
            assert manager.file_format == "gml"  # 默认值

    def test_ensure_data_directory(self, temp_dir):
        """测试确保数据目录存在"""
        NetworkXGraphManager(data_directory=temp_dir / "subdir")

        # 目录应该已创建
        assert (temp_dir / "subdir").exists()

    def test_get_graph_path(self, graph_manager):
        """测试获取图文件路径"""
        path = graph_manager._get_graph_path("test_graph")

        assert path == graph_manager.data_directory / "test_graph.gml"

    def test_create_graph(self, graph_manager):
        """测试创建图"""
        # 测试不同类型的图
        graph = graph_manager._create_graph("Graph")
        import networkx as nx

        assert isinstance(graph, nx.Graph)

        graph = graph_manager._create_graph("DiGraph")
        assert isinstance(graph, nx.DiGraph)

        graph = graph_manager._create_graph("MultiGraph")
        assert isinstance(graph, nx.MultiGraph)

        graph = graph_manager._create_graph("MultiDiGraph")
        assert isinstance(graph, nx.MultiDiGraph)

    def test_create_graph_invalid_type(self, graph_manager):
        """测试创建不支持的图类型"""
        with pytest.raises(NetworkXError):
            graph_manager._create_graph("InvalidGraph")

    def test_load_graph_not_exists(self, graph_manager):
        """测试加载不存在的图"""
        graph = graph_manager._load_graph("nonexistent", "DiGraph")

        import networkx as nx

        assert isinstance(graph, nx.DiGraph)
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0

    def test_save_and_load_graph(self, graph_manager):
        """测试保存和加载图"""
        import networkx as nx

        # 创建图
        graph = nx.DiGraph()
        graph.add_node("node1", name="Node 1")
        graph.add_node("node2", name="Node 2")
        graph.add_edge("node1", "node2", relationship="connected_to")

        # 保存图
        graph_manager._save_graph("test_graph", graph)

        # 验证文件存在
        graph_path = graph_manager._get_graph_path("test_graph")
        assert graph_path.exists()

        # 加载图
        loaded_graph = graph_manager._load_graph("test_graph", "DiGraph")

        # 验证加载的图
        assert isinstance(loaded_graph, nx.DiGraph)
        assert len(loaded_graph.nodes) == 2
        assert len(loaded_graph.edges) == 1
        assert "node1" in loaded_graph.nodes
        assert "node2" in loaded_graph.nodes
        assert loaded_graph.has_edge("node1", "node2")

    def test_get_graph(self, graph_manager):
        """测试获取图"""
        with graph_manager.get_graph("test_graph", "DiGraph") as graph:
            import networkx as nx

            assert isinstance(graph, nx.DiGraph)

            # 添加节点和边
            graph.add_node("node1", name="Node 1")
            graph.add_node("node2", name="Node 2")
            graph.add_edge("node1", "node2", relationship="connected_to")

        # 再次获取图,应该是同一个实例
        with graph_manager.get_graph("test_graph", "DiGraph") as graph:
            assert len(graph.nodes) == 2
            assert len(graph.edges) == 1
            assert "node1" in graph.nodes
            assert "node2" in graph.nodes
            assert graph.has_edge("node1", "node2")

    def test_get_graph_with_defaults(self, graph_manager):
        """测试使用默认值获取图"""
        with graph_manager.get_graph() as graph:
            import networkx as nx

            assert isinstance(graph, nx.DiGraph)  # 默认类型

    @pytest.mark.asyncio
    async def test_get_async_graph(self, graph_manager):
        """测试异步获取图"""
        async with graph_manager.get_async_graph("test_graph", "DiGraph") as graph:
            import networkx as nx

            assert isinstance(graph, nx.DiGraph)

            # 添加节点和边
            graph.add_node("node1", name="Node 1")
            graph.add_node("node2", name="Node 2")
            graph.add_edge("node1", "node2", relationship="connected_to")

        # 再次获取图,应该是同一个实例
        async with graph_manager.get_async_graph("test_graph", "DiGraph") as graph:
            assert len(graph.nodes) == 2
            assert len(graph.edges) == 1
            assert "node1" in graph.nodes
            assert "node2" in graph.nodes
            assert graph.has_edge("node1", "node2")

    @pytest.mark.asyncio
    async def test_get_async_graph_with_defaults(self, graph_manager):
        """测试使用默认值异步获取图"""
        async with graph_manager.get_async_graph() as graph:
            import networkx as nx

            assert isinstance(graph, nx.DiGraph)  # 默认类型

    def test_list_graphs(self, graph_manager):
        """测试列出图"""
        # 创建几个图
        with graph_manager.get_graph("graph1", "DiGraph") as graph:
            graph.add_node("node1")

        with graph_manager.get_graph("graph2", "Graph") as graph:
            graph.add_node("node1")

        # 列出图
        graph_names = graph_manager.list_graphs()

        assert "graph1" in graph_names
        assert "graph2" in graph_names

    @pytest.mark.asyncio
    async def test_list_graphs_async(self, graph_manager):
        """测试异步列出图"""
        # 创建几个图
        async with graph_manager.get_async_graph("graph1", "DiGraph") as graph:
            graph.add_node("node1")

        async with graph_manager.get_async_graph("graph2", "Graph") as graph:
            graph.add_node("node1")

        # 列出图
        graph_names = await graph_manager.list_graphs_async()

        assert "graph1" in graph_names
        assert "graph2" in graph_names

    def test_delete_graph(self, graph_manager):
        """测试删除图"""
        # 创建图
        with graph_manager.get_graph("test_graph", "DiGraph") as graph:
            graph.add_node("node1")

        # 验证图存在
        graph_names = graph_manager.list_graphs()
        assert "test_graph" in graph_names

        # 删除图
        result = graph_manager.delete_graph("test_graph")

        assert result is True

        # 验证图已删除
        graph_names = graph_manager.list_graphs()
        assert "test_graph" not in graph_names

    def test_delete_nonexistent_graph(self, graph_manager):
        """测试删除不存在的图"""
        result = graph_manager.delete_graph("nonexistent")

        assert result is True  # 删除操作总是返回成功

    @pytest.mark.asyncio
    async def test_delete_graph_async(self, graph_manager):
        """测试异步删除图"""
        # 创建图
        async with graph_manager.get_async_graph("test_graph", "DiGraph") as graph:
            graph.add_node("node1")

        # 验证图存在
        graph_names = await graph_manager.list_graphs_async()
        assert "test_graph" in graph_names

        # 删除图
        result = await graph_manager.delete_graph_async("test_graph")

        assert result is True

        # 验证图已删除
        graph_names = await graph_manager.list_graphs_async()
        assert "test_graph" not in graph_names

    def test_save_graph(self, graph_manager):
        """测试保存图"""
        # 创建图
        with graph_manager.get_graph("test_graph", "DiGraph") as graph:
            graph.add_node("node1", name="Node 1")
            graph.add_node("node2", name="Node 2")
            graph.add_edge("node1", "node2", relationship="connected_to")

        # 保存图
        result = graph_manager.save_graph("test_graph")

        assert result is True

        # 验证文件存在
        graph_path = graph_manager._get_graph_path("test_graph")
        assert graph_path.exists()

    def test_save_all_graphs(self, graph_manager):
        """测试保存所有图"""
        # 创建几个图
        with graph_manager.get_graph("graph1", "DiGraph") as graph:
            graph.add_node("node1")

        with graph_manager.get_graph("graph2", "Graph") as graph:
            graph.add_node("node1")

        # 保存所有图
        result = graph_manager.save_graph()

        assert result is True

        # 验证文件存在
        assert graph_manager._get_graph_path("graph1").exists()
        assert graph_manager._get_graph_path("graph2").exists()

    @pytest.mark.asyncio
    async def test_save_graph_async(self, graph_manager):
        """测试异步保存图"""
        # 创建图
        async with graph_manager.get_async_graph("test_graph", "DiGraph") as graph:
            graph.add_node("node1", name="Node 1")
            graph.add_node("node2", name="Node 2")
            graph.add_edge("node1", "node2", relationship="connected_to")

        # 保存图
        result = await graph_manager.save_graph_async("test_graph")

        assert result is True

        # 验证文件存在
        graph_path = graph_manager._get_graph_path("test_graph")
        assert graph_path.exists()

    @pytest.mark.asyncio
    async def test_save_all_graphs_async(self, graph_manager):
        """测试异步保存所有图"""
        # 创建几个图
        async with graph_manager.get_async_graph("graph1", "DiGraph") as graph:
            graph.add_node("node1")

        async with graph_manager.get_async_graph("graph2", "Graph") as graph:
            graph.add_node("node1")

        # 保存所有图
        result = await graph_manager.save_graph_async()

        assert result is True

        # 验证文件存在
        assert graph_manager._get_graph_path("graph1").exists()
        assert graph_manager._get_graph_path("graph2").exists()

    def test_get_graph_info(self, graph_manager):
        """测试获取图信息"""
        # 创建图
        with graph_manager.get_graph("test_graph", "DiGraph") as graph:
            graph.add_node("node1", name="Node 1")
            graph.add_node("node2", name="Node 2")
            graph.add_edge("node1", "node2", relationship="connected_to")
            graph.graph["description"] = "Test Graph"

        # 获取图信息
        info = graph_manager.get_graph_info("test_graph")

        assert info["name"] == "test_graph"
        assert info["type"] == "DiGraph"
        assert info["is_directed"] is True
        assert info["is_multigraph"] is False
        assert info["node_count"] == 2
        assert info["edge_count"] == 1
        assert info["attributes"]["description"] == "Test Graph"
        assert info["data_directory"] == str(graph_manager.data_directory)
        assert info["file_format"] == "gml"
        assert info["auto_save"] is False
        assert info["enable_persistence"] is True

    @pytest.mark.asyncio
    async def test_get_graph_info_async(self, graph_manager):
        """测试异步获取图信息"""
        # 创建图
        async with graph_manager.get_async_graph("test_graph", "DiGraph") as graph:
            graph.add_node("node1", name="Node 1")
            graph.add_node("node2", name="Node 2")
            graph.add_edge("node1", "node2", relationship="connected_to")
            graph.graph["description"] = "Test Graph"

        # 获取图信息
        info = await graph_manager.get_graph_info_async("test_graph")

        assert info["name"] == "test_graph"
        assert info["type"] == "DiGraph"
        assert info["is_directed"] is True
        assert info["is_multigraph"] is False
        assert info["node_count"] == 2
        assert info["edge_count"] == 1
        assert info["attributes"]["description"] == "Test Graph"
        assert info["data_directory"] == str(graph_manager.data_directory)
        assert info["file_format"] == "gml"
        assert info["auto_save"] is False
        assert info["enable_persistence"] is True

    def test_get_graph_info_with_defaults(self, graph_manager):
        """测试使用默认值获取图信息"""
        # 创建图
        with graph_manager.get_graph() as graph:
            graph.add_node("node1", name="Node 1")

        # 获取图信息
        info = graph_manager.get_graph_info()

        assert info["name"] == graph_manager.default_graph_name

    def test_get_connection_info(self, graph_manager):
        """测试获取连接信息"""
        info = graph_manager.get_connection_info()

        assert info["data_directory"] == str(graph_manager.data_directory)
        assert info["default_graph_name"] == graph_manager.default_graph_name
        assert info["default_graph_type"] == graph_manager.default_graph_type
        assert info["auto_save"] == graph_manager.auto_save
        assert info["auto_save_interval"] == graph_manager.auto_save_interval
        assert info["enable_persistence"] == graph_manager.enable_persistence
        assert info["file_format"] == graph_manager.file_format
        assert isinstance(info["sync_graphs"], list)
        assert isinstance(info["async_graphs"], list)

    def test_context_manager(self, temp_dir):
        """测试上下文管理器"""
        with NetworkXGraphManager(data_directory=temp_dir) as manager:
            # 使用管理器
            with manager.get_graph("test_graph", "DiGraph") as graph:
                graph.add_node("node1")

        # 管理器应该已关闭
        assert len(manager._graphs) == 0

    @pytest.mark.asyncio
    async def test_async_context_manager(self, temp_dir):
        """测试异步上下文管理器"""
        async with NetworkXGraphManager(data_directory=temp_dir) as manager:
            # 使用管理器
            async with manager.get_async_graph("test_graph", "DiGraph") as graph:
                graph.add_node("node1")

        # 管理器应该已关闭
        assert len(manager._async_graphs) == 0

    def test_auto_save_timer(self, temp_dir):
        """测试自动保存定时器"""
        manager = NetworkXGraphManager(
            data_directory=temp_dir,
            auto_save=True,
            auto_save_interval=1,  # 1秒
        )

        # 定时器应该已启动
        assert manager._auto_save_timer is not None

        # 关闭管理器
        manager.close()

        # 定时器应该已停止
        assert manager._auto_save_timer is None


class TestGraphManagerFunctions:
    """图管理器函数测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_get_graph_manager(self, temp_dir):
        """测试获取全局图管理器实例"""
        with patch(
            "src.infrastructure.storage.networkx.graph_manager.NetworkXGraphManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # 重置全局变量
            import src.infrastructure.storage.networkx.graph_manager as gm_module

            gm_module._graph_manager = None

            manager = get_graph_manager()

            assert manager == mock_manager
            mock_manager_class.assert_called_once()

    def test_get_graph_manager_singleton(self, temp_dir):
        """测试全局图管理器单例"""
        with patch(
            "src.infrastructure.storage.networkx.graph_manager.NetworkXGraphManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager

            # 重置全局变量
            import src.infrastructure.storage.networkx.graph_manager as gm_module

            gm_module._graph_manager = None

            # 第一次调用
            manager1 = get_graph_manager()
            # 第二次调用
            manager2 = get_graph_manager()

            # 应该返回同一个实例
            assert manager1 is manager2
            mock_manager_class.assert_called_once()

    def test_create_graph_manager(self, temp_dir):
        """测试创建新的图管理器实例"""
        manager = create_graph_manager(
            data_directory=temp_dir,
            default_graph_name="custom_graph",
            default_graph_type="Graph",
            auto_save=False,
        )

        assert isinstance(manager, NetworkXGraphManager)
        assert manager.data_directory == temp_dir
        assert manager.default_graph_name == "custom_graph"
        assert manager.default_graph_type == "Graph"
        assert manager.auto_save is False
