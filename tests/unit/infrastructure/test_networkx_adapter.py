# 生成命令: T014 NetworkX 图存储适配器和图管理器
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
NetworkX 适配器单元测试
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.storage.networkx.adapter import (
    NetworkXAdapter,
    create_adapter,
)
from src.infrastructure.storage.networkx.graph_manager import NetworkXGraphManager
from src.shared.exceptions.storage_exceptions import NetworkXError

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def event_loop():
    """创建一个事件循环实例用于整个测试会话"""
    loop = asyncio.new_event_loop()
    yield loop
    # 确保所有异步任务完成
    loop.close()


class TestNetworkXAdapter:
    """NetworkX 适配器测试类"""

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
            auto_save=False,  # 测试时禁用自动保存
            enable_persistence=True,
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

    @pytest.fixture
    def adapter(self, graph_manager):
        """适配器实例"""
        return NetworkXAdapter(
            graph_name="test_graph",
            graph_manager=graph_manager,
            graph_type="DiGraph",
        )

    def test_init(self, graph_manager):
        """测试初始化"""
        adapter = NetworkXAdapter(
            graph_name="users",
            graph_manager=graph_manager,
            graph_type="Graph",
            auto_create_graph=True,
        )

        assert adapter.graph_name == "users"
        assert adapter.graph_manager == graph_manager
        assert adapter.graph_type == "Graph"
        assert adapter.auto_create_graph is True

    def test_init_with_default_graph_manager(self, temp_dir):
        """测试使用默认图管理器初始化"""
        with patch(
            "src.infrastructure.storage.networkx.adapter.get_graph_manager"
        ) as mock_get_manager:
            mock_manager = NetworkXGraphManager(data_directory=temp_dir)
            mock_get_manager.return_value = mock_manager

            adapter = NetworkXAdapter(graph_name="test")

            assert adapter.graph_manager == mock_manager
            mock_get_manager.assert_called_once()

    def test_add_node(self, adapter):
        """测试添加节点"""
        result = adapter.add_node(
            "node1",
            name="Test Node",
            description="Test Description",
            type="entity",
        )

        assert result is True

        # 验证节点已添加
        node_data = adapter.get_node("node1")
        assert node_data is not None
        assert node_data["id"] == "node1"
        assert node_data["name"] == "Test Node"
        assert node_data["description"] == "Test Description"
        assert node_data["type"] == "entity"
        assert "created_at" in node_data
        assert "updated_at" in node_data

    def test_add_node_error(self, adapter):
        """测试添加节点错误"""
        # 模拟图管理器抛出异常
        with patch.object(adapter.graph_manager, "get_graph") as mock_get_graph:
            mock_graph = MagicMock()
            mock_graph.add_node.side_effect = Exception("Graph error")
            mock_get_graph.return_value.__enter__.return_value = mock_graph

            with pytest.raises(NetworkXError):
                adapter.add_node("node1")

    @pytest.mark.asyncio
    async def test_add_node_async(self, adapter):
        """测试异步添加节点"""
        result = await adapter.add_node_async(
            "node1",
            name="Test Node",
            description="Test Description",
            type="entity",
        )

        assert result is True

        # 验证节点已添加
        node_data = await adapter.get_node_async("node1")
        assert node_data is not None
        assert node_data["id"] == "node1"
        assert node_data["name"] == "Test Node"
        assert node_data["description"] == "Test Description"
        assert node_data["type"] == "entity"
        assert "created_at" in node_data
        assert "updated_at" in node_data

    def test_add_edge(self, adapter):
        """测试添加边"""
        # 先添加节点
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")

        # 添加边
        result = adapter.add_edge(
            "node1",
            "node2",
            relationship="connected_to",
            weight=1.0,
        )

        assert result is True

        # 验证边已添加
        edge_data = adapter.get_edge("node1", "node2")
        assert edge_data is not None
        assert edge_data["source"] == "node1"
        assert edge_data["target"] == "node2"
        assert edge_data["relationship"] == "connected_to"
        assert edge_data["weight"] == 1.0
        assert "created_at" in edge_data
        assert "updated_at" in edge_data

    @pytest.mark.asyncio
    async def test_add_edge_async(self, adapter):
        """测试异步添加边"""
        # 先添加节点
        await adapter.add_node_async("node1", name="Node 1")
        await adapter.add_node_async("node2", name="Node 2")

        # 添加边
        result = await adapter.add_edge_async(
            "node1",
            "node2",
            relationship="connected_to",
            weight=1.0,
        )

        assert result is True

        # 验证边已添加
        edge_data = await adapter.get_edge_async("node1", "node2")
        assert edge_data is not None
        assert edge_data["source"] == "node1"
        assert edge_data["target"] == "node2"
        assert edge_data["relationship"] == "connected_to"
        assert edge_data["weight"] == 1.0
        assert "created_at" in edge_data
        assert "updated_at" in edge_data

    def test_get_node(self, adapter):
        """测试获取节点"""
        # 添加节点
        adapter.add_node("node1", name="Test Node", type="entity")

        # 获取节点
        node_data = adapter.get_node("node1")

        assert node_data is not None
        assert node_data["id"] == "node1"
        assert node_data["name"] == "Test Node"
        assert node_data["type"] == "entity"

    def test_get_node_not_found(self, adapter):
        """测试获取不存在的节点"""
        node_data = adapter.get_node("nonexistent")

        assert node_data is None

    @pytest.mark.asyncio
    async def test_get_node_async(self, adapter):
        """测试异步获取节点"""
        # 添加节点
        await adapter.add_node_async("node1", name="Test Node", type="entity")

        # 获取节点
        node_data = await adapter.get_node_async("node1")

        assert node_data is not None
        assert node_data["id"] == "node1"
        assert node_data["name"] == "Test Node"
        assert node_data["type"] == "entity"

    def test_get_edge(self, adapter):
        """测试获取边"""
        # 添加节点和边
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")
        adapter.add_edge("node1", "node2", relationship="connected_to")

        # 获取边
        edge_data = adapter.get_edge("node1", "node2")

        assert edge_data is not None
        assert edge_data["source"] == "node1"
        assert edge_data["target"] == "node2"
        assert edge_data["relationship"] == "connected_to"

    def test_get_edge_not_found(self, adapter):
        """测试获取不存在的边"""
        edge_data = adapter.get_edge("nonexistent1", "nonexistent2")

        assert edge_data is None

    @pytest.mark.asyncio
    async def test_get_edge_async(self, adapter):
        """测试异步获取边"""
        # 添加节点和边
        await adapter.add_node_async("node1", name="Node 1")
        await adapter.add_node_async("node2", name="Node 2")
        await adapter.add_edge_async("node1", "node2", relationship="connected_to")

        # 获取边
        edge_data = await adapter.get_edge_async("node1", "node2")

        assert edge_data is not None
        assert edge_data["source"] == "node1"
        assert edge_data["target"] == "node2"
        assert edge_data["relationship"] == "connected_to"

    def test_update_node(self, adapter):
        """测试更新节点"""
        # 添加节点
        adapter.add_node("node1", name="Test Node", type="entity")

        # 更新节点
        result = adapter.update_node(
            "node1", name="Updated Node", description="New Description"
        )

        assert result is True

        # 验证更新
        node_data = adapter.get_node("node1")
        assert node_data["name"] == "Updated Node"
        assert node_data["description"] == "New Description"
        assert node_data["type"] == "entity"  # 原有属性保持不变
        assert "updated_at" in node_data

    def test_update_node_not_found(self, adapter):
        """测试更新不存在的节点"""
        result = adapter.update_node("nonexistent", name="Updated Node")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_node_async(self, adapter):
        """测试异步更新节点"""
        # 添加节点
        await adapter.add_node_async("node1", name="Test Node", type="entity")

        # 更新节点
        result = await adapter.update_node_async(
            "node1", name="Updated Node", description="New Description"
        )

        assert result is True

        # 验证更新
        node_data = await adapter.get_node_async("node1")
        assert node_data["name"] == "Updated Node"
        assert node_data["description"] == "New Description"
        assert node_data["type"] == "entity"  # 原有属性保持不变
        assert "updated_at" in node_data

    def test_update_edge(self, adapter):
        """测试更新边"""
        # 添加节点和边
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")
        adapter.add_edge("node1", "node2", relationship="connected_to", weight=1.0)

        # 更新边
        result = adapter.update_edge(
            "node1", "node2", weight=2.0, description="Updated Edge"
        )

        assert result is True

        # 验证更新
        edge_data = adapter.get_edge("node1", "node2")
        assert edge_data["relationship"] == "connected_to"  # 原有属性保持不变
        assert edge_data["weight"] == 2.0
        assert edge_data["description"] == "Updated Edge"
        assert "updated_at" in edge_data

    def test_update_edge_not_found(self, adapter):
        """测试更新不存在的边"""
        result = adapter.update_edge("nonexistent1", "nonexistent2", weight=2.0)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_edge_async(self, adapter):
        """测试异步更新边"""
        # 添加节点和边
        await adapter.add_node_async("node1", name="Node 1")
        await adapter.add_node_async("node2", name="Node 2")
        await adapter.add_edge_async(
            "node1", "node2", relationship="connected_to", weight=1.0
        )

        # 更新边
        result = await adapter.update_edge_async(
            "node1", "node2", weight=2.0, description="Updated Edge"
        )

        assert result is True

        # 验证更新
        edge_data = await adapter.get_edge_async("node1", "node2")
        assert edge_data["relationship"] == "connected_to"  # 原有属性保持不变
        assert edge_data["weight"] == 2.0
        assert edge_data["description"] == "Updated Edge"
        assert "updated_at" in edge_data

    def test_remove_node(self, adapter):
        """测试删除节点"""
        # 添加节点
        adapter.add_node("node1", name="Test Node")

        # 删除节点
        result = adapter.remove_node("node1")

        assert result is True

        # 验证节点已删除
        node_data = adapter.get_node("node1")
        assert node_data is None

    def test_remove_node_not_found(self, adapter):
        """测试删除不存在的节点"""
        result = adapter.remove_node("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_node_async(self, adapter):
        """测试异步删除节点"""
        # 添加节点
        await adapter.add_node_async("node1", name="Test Node")

        # 删除节点
        result = await adapter.remove_node_async("node1")

        assert result is True

        # 验证节点已删除
        node_data = await adapter.get_node_async("node1")
        assert node_data is None

    def test_remove_edge(self, adapter):
        """测试删除边"""
        # 添加节点和边
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")
        adapter.add_edge("node1", "node2", relationship="connected_to")

        # 删除边
        result = adapter.remove_edge("node1", "node2")

        assert result is True

        # 验证边已删除
        edge_data = adapter.get_edge("node1", "node2")
        assert edge_data is None

    def test_remove_edge_not_found(self, adapter):
        """测试删除不存在的边"""
        result = adapter.remove_edge("nonexistent1", "nonexistent2")

        assert result is False

    @pytest.mark.asyncio
    async def test_remove_edge_async(self, adapter):
        """测试异步删除边"""
        # 添加节点和边
        await adapter.add_node_async("node1", name="Node 1")
        await adapter.add_node_async("node2", name="Node 2")
        await adapter.add_edge_async("node1", "node2", relationship="connected_to")

        # 删除边
        result = await adapter.remove_edge_async("node1", "node2")

        assert result is True

        # 验证边已删除
        edge_data = await adapter.get_edge_async("node1", "node2")
        assert edge_data is None

    def test_get_neighbors(self, adapter):
        """测试获取邻居节点"""
        # 创建一个简单的图: node1 -> node2, node1 -> node3
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")
        adapter.add_node("node3", name="Node 3")
        adapter.add_edge("node1", "node2", relationship="connected_to")
        adapter.add_edge("node1", "node3", relationship="connected_to")

        # 获取邻居
        neighbors = adapter.get_neighbors("node1")

        assert len(neighbors) == 2
        assert "node2" in neighbors
        assert "node3" in neighbors

    def test_get_neighbors_not_found(self, adapter):
        """测试获取不存在节点的邻居"""
        neighbors = adapter.get_neighbors("nonexistent")

        assert neighbors == []

    @pytest.mark.asyncio
    async def test_get_neighbors_async(self, adapter):
        """测试异步获取邻居节点"""
        # 创建一个简单的图: node1 -> node2, node1 -> node3
        await adapter.add_node_async("node1", name="Node 1")
        await adapter.add_node_async("node2", name="Node 2")
        await adapter.add_node_async("node3", name="Node 3")
        await adapter.add_edge_async("node1", "node2", relationship="connected_to")
        await adapter.add_edge_async("node1", "node3", relationship="connected_to")

        # 获取邻居
        neighbors = await adapter.get_neighbors_async("node1")

        assert len(neighbors) == 2
        assert "node2" in neighbors
        assert "node3" in neighbors

    def test_find_path(self, adapter):
        """测试查找路径"""
        # 创建一个简单的图: node1 -> node2 -> node3
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")
        adapter.add_node("node3", name="Node 3")
        adapter.add_edge("node1", "node2", relationship="connected_to")
        adapter.add_edge("node2", "node3", relationship="connected_to")

        # 查找路径
        path = adapter.find_path("node1", "node3")

        assert path is not None
        assert len(path) == 3
        assert path[0] == "node1"
        assert path[1] == "node2"
        assert path[2] == "node3"

    def test_find_path_not_found(self, adapter):
        """测试查找不存在的路径"""
        # 创建两个不连通的节点
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")

        # 查找路径
        path = adapter.find_path("node1", "node2")

        assert path is None

    @pytest.mark.asyncio
    async def test_find_path_async(self, adapter):
        """测试异步查找路径"""
        # 创建一个简单的图: node1 -> node2 -> node3
        await adapter.add_node_async("node1", name="Node 1")
        await adapter.add_node_async("node2", name="Node 2")
        await adapter.add_node_async("node3", name="Node 3")
        await adapter.add_edge_async("node1", "node2", relationship="connected_to")
        await adapter.add_edge_async("node2", "node3", relationship="connected_to")

        # 查找路径
        path = await adapter.find_path_async("node1", "node3")

        assert path is not None
        assert len(path) == 3
        assert path[0] == "node1"
        assert path[1] == "node2"
        assert path[2] == "node3"

    def test_find_shortest_path(self, adapter):
        """测试查找最短路径"""
        # 创建一个图: node1 -> node2 -> node3, node1 -> node3 (直接连接)
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")
        adapter.add_node("node3", name="Node 3")
        adapter.add_edge("node1", "node2", relationship="connected_to", weight=1.0)
        adapter.add_edge("node2", "node3", relationship="connected_to", weight=1.0)
        adapter.add_edge("node1", "node3", relationship="connected_to", weight=3.0)

        # 查找最短路径(无权重)
        path, length = adapter.find_shortest_path("node1", "node3")

        assert path is not None
        assert len(path) == 2  # 直接路径更短
        assert path[0] == "node1"
        assert path[1] == "node3"
        assert length == 1  # 一条边

        # 查找最短路径(带权重)
        path, length = adapter.find_shortest_path(
            "node1", "node3", weight_attribute="weight"
        )

        assert path is not None
        assert len(path) == 3  # 权重路径更短
        assert path[0] == "node1"
        assert path[1] == "node2"
        assert path[2] == "node3"
        assert length == 2.0  # 1.0 + 1.0

    def test_find_shortest_path_not_found(self, adapter):
        """测试查找不存在的最短路径"""
        # 创建两个不连通的节点
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")

        # 查找最短路径
        result = adapter.find_shortest_path("node1", "node2")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_shortest_path_async(self, adapter):
        """测试异步查找最短路径"""
        # 创建一个图: node1 -> node2 -> node3, node1 -> node3 (直接连接)
        await adapter.add_node_async("node1", name="Node 1")
        await adapter.add_node_async("node2", name="Node 2")
        await adapter.add_node_async("node3", name="Node 3")
        await adapter.add_edge_async(
            "node1", "node2", relationship="connected_to", weight=1.0
        )
        await adapter.add_edge_async(
            "node2", "node3", relationship="connected_to", weight=1.0
        )
        await adapter.add_edge_async(
            "node1", "node3", relationship="connected_to", weight=3.0
        )

        # 查找最短路径(无权重)
        path, length = await adapter.find_shortest_path_async("node1", "node3")

        assert path is not None
        assert len(path) == 2  # 直接路径更短
        assert path[0] == "node1"
        assert path[1] == "node3"
        assert length == 1  # 一条边

        # 查找最短路径(带权重)
        path, length = await adapter.find_shortest_path_async(
            "node1", "node3", weight_attribute="weight"
        )

        assert path is not None
        assert len(path) == 3  # 权重路径更短
        assert path[0] == "node1"
        assert path[1] == "node2"
        assert path[2] == "node3"
        assert length == 2.0  # 1.0 + 1.0

    def test_list_nodes(self, adapter):
        """测试列出节点"""
        # 添加多个节点
        for i in range(5):
            adapter.add_node(f"node{i}", name=f"Node {i}", type="entity")

        # 列出所有节点
        all_nodes = adapter.list_nodes()
        assert len(all_nodes) == 5

        # 带过滤条件
        filtered_nodes = adapter.list_nodes(filters={"type": "entity"})
        assert len(filtered_nodes) == 5

        # 带限制
        limited_nodes = adapter.list_nodes(limit=3)
        assert len(limited_nodes) == 3

    @pytest.mark.asyncio
    async def test_list_nodes_async(self, adapter):
        """测试异步列出节点"""
        # 添加多个节点
        for i in range(5):
            await adapter.add_node_async(f"node{i}", name=f"Node {i}", type="entity")

        # 列出所有节点
        all_nodes = await adapter.list_nodes_async()
        assert len(all_nodes) == 5

        # 带过滤条件
        filtered_nodes = await adapter.list_nodes_async(filters={"type": "entity"})
        assert len(filtered_nodes) == 5

        # 带限制
        limited_nodes = await adapter.list_nodes_async(limit=3)
        assert len(limited_nodes) == 3

    def test_list_edges(self, adapter):
        """测试列出边"""
        # 添加节点和边
        for i in range(3):
            adapter.add_node(f"node{i}", name=f"Node {i}")

        for i in range(2):
            adapter.add_edge(f"node{i}", f"node{i + 1}", relationship="connected_to")

        # 列出所有边
        all_edges = adapter.list_edges()
        assert len(all_edges) == 2

        # 带过滤条件
        filtered_edges = adapter.list_edges(filters={"relationship": "connected_to"})
        assert len(filtered_edges) == 2

        # 带限制
        limited_edges = adapter.list_edges(limit=1)
        assert len(limited_edges) == 1

    @pytest.mark.asyncio
    async def test_list_edges_async(self, adapter):
        """测试异步列出边"""
        # 添加节点和边
        for i in range(3):
            await adapter.add_node_async(f"node{i}", name=f"Node {i}")

        for i in range(2):
            await adapter.add_edge_async(
                f"node{i}", f"node{i + 1}", relationship="connected_to"
            )

        # 列出所有边
        all_edges = await adapter.list_edges_async()
        assert len(all_edges) == 2

        # 带过滤条件
        filtered_edges = await adapter.list_edges_async(
            filters={"relationship": "connected_to"}
        )
        assert len(filtered_edges) == 2

        # 带限制
        limited_edges = await adapter.list_edges_async(limit=1)
        assert len(limited_edges) == 1

    def test_count_nodes(self, adapter):
        """测试统计节点数量"""
        # 添加节点
        for i in range(5):
            adapter.add_node(f"node{i}", name=f"Node {i}")

        # 统计节点
        count = adapter.count_nodes()
        assert count == 5

    @pytest.mark.asyncio
    async def test_count_nodes_async(self, adapter):
        """测试异步统计节点数量"""
        # 添加节点
        for i in range(5):
            await adapter.add_node_async(f"node{i}", name=f"Node {i}")

        # 统计节点
        count = await adapter.count_nodes_async()
        assert count == 5

    def test_count_edges(self, adapter):
        """测试统计边数量"""
        # 添加节点和边
        for i in range(3):
            adapter.add_node(f"node{i}", name=f"Node {i}")

        for i in range(2):
            adapter.add_edge(f"node{i}", f"node{i + 1}", relationship="connected_to")

        # 统计边
        count = adapter.count_edges()
        assert count == 2

    @pytest.mark.asyncio
    async def test_count_edges_async(self, adapter):
        """测试异步统计边数量"""
        # 添加节点和边
        for i in range(3):
            await adapter.add_node_async(f"node{i}", name=f"Node {i}")

        for i in range(2):
            await adapter.add_edge_async(
                f"node{i}", f"node{i + 1}", relationship="connected_to"
            )

        # 统计边
        count = await adapter.count_edges_async()
        assert count == 2

    def test_get_graph_info(self, adapter):
        """测试获取图信息"""
        # 添加节点和边
        adapter.add_node("node1", name="Node 1")
        adapter.add_node("node2", name="Node 2")
        adapter.add_edge("node1", "node2", relationship="connected_to")

        # 获取图信息
        info = adapter.get_graph_info()

        assert info["name"] == "test_graph"
        assert info["node_count"] == 2
        assert info["edge_count"] == 1
        assert info["is_directed"] is True
        assert info["is_multigraph"] is False

    @pytest.mark.asyncio
    async def test_get_graph_info_async(self, adapter):
        """测试异步获取图信息"""
        # 添加节点和边
        await adapter.add_node_async("node1", name="Node 1")
        await adapter.add_node_async("node2", name="Node 2")
        await adapter.add_edge_async("node1", "node2", relationship="connected_to")

        # 获取图信息
        info = await adapter.get_graph_info_async()

        assert info["name"] == "test_graph"
        assert info["node_count"] == 2
        assert info["edge_count"] == 1
        assert info["is_directed"] is True
        assert info["is_multigraph"] is False


class TestAdapterFunctions:
    """适配器函数测试类"""

    @pytest.fixture
    def temp_dir(self):
        """临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield Path(d)

    def test_create_adapter(self, temp_dir):
        """测试创建适配器"""
        graph_manager = NetworkXGraphManager(data_directory=temp_dir)

        adapter = create_adapter(
            graph_name="users",
            graph_manager=graph_manager,
            graph_type="Graph",
        )

        assert isinstance(adapter, NetworkXAdapter)
        assert adapter.graph_name == "users"
        assert adapter.graph_manager == graph_manager
        assert adapter.graph_type == "Graph"

    def test_create_adapter_with_default_manager(self, temp_dir):
        """测试使用默认图管理器创建适配器"""
        with patch(
            "src.infrastructure.storage.networkx.adapter.get_graph_manager"
        ) as mock_get_manager:
            mock_manager = NetworkXGraphManager(data_directory=temp_dir)
            mock_get_manager.return_value = mock_manager

            adapter = create_adapter(graph_name="users")

            assert adapter.graph_manager == mock_manager
            mock_get_manager.assert_called_once()
