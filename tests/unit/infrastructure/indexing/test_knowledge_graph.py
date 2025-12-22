"""
知识图谱构建器测试 (T049)

测试知识图谱构建器的核心功能，包括实体提取、关系提取、图存储等。
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.indexing.knowledge_graph import (
    EntityType,
    ExtractedEntity,
    ExtractedRelation,
    KnowledgeGraphBuilder,
    KnowledgeGraphError,
    RelationType,
)

try:
    from llama_index.core.schema import TextNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False
    TextNode = MagicMock  # type: ignore[assignment, misc]


@pytest.fixture
def mock_llm_service():
    """创建模拟的LLM服务"""
    service = MagicMock()
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "entities": [
            {
                "name": "锂离子电池",
                "type": "ENERGY_STORAGE_TECHNOLOGY",
                "description": "一种电化学储能技术",
                "confidence": 0.9,
            }
        ],
        "relations": [
            {
                "source": "锂离子电池",
                "target": "储能系统",
                "relation": "IS_A",
                "description": "锂离子电池是储能系统的一种",
                "confidence": 0.9,
            }
        ],
    })
    mock_llm.invoke.return_value = mock_response
    service.get_chat_model.return_value = mock_llm
    return service


@pytest.fixture
def mock_graph_adapter():
    """创建模拟的NetworkX适配器"""
    adapter = MagicMock()
    adapter.add_node.return_value = True
    adapter.add_edge.return_value = True
    adapter.get_node.return_value = {"id": "test-id", "name": "test"}
    adapter.get_edge.return_value = None
    adapter.list_nodes.return_value = []
    adapter.list_edges.return_value = []
    adapter.get_neighbors.return_value = []
    adapter.count_nodes.return_value = 0
    adapter.count_edges.return_value = 0
    adapter.get_graph_info.return_value = {}
    return adapter


@pytest.fixture
def knowledge_graph_builder(mock_llm_service, mock_graph_adapter):
    """创建知识图谱构建器实例"""
    return KnowledgeGraphBuilder(
        graph_name="test_graph",
        graph_adapter=mock_graph_adapter,
        llm_service=mock_llm_service,
        max_entities_per_chunk=10,
        max_relations_per_chunk=10,
    )


@pytest.mark.skipif(not LLAMA_INDEX_AVAILABLE, reason="LlamaIndex not available")
class TestKnowledgeGraphBuilder:
    """知识图谱构建器测试类"""

    def test_init(self, knowledge_graph_builder):
        """测试初始化"""
        assert knowledge_graph_builder.graph_name == "test_graph"
        assert knowledge_graph_builder.max_entities_per_chunk == 10
        assert knowledge_graph_builder.max_relations_per_chunk == 10

    def test_init_without_llamaindex(self):
        """测试在没有LlamaIndex时初始化应该失败"""
        with patch("src.infrastructure.indexing.knowledge_graph.LLAMA_INDEX_AVAILABLE", False):
            with pytest.raises(ImportError):
                KnowledgeGraphBuilder()

    def test_build_from_empty_nodes(self, knowledge_graph_builder):
        """测试从空节点列表构建"""
        result = knowledge_graph_builder.build_from_nodes([])
        assert result["entities_count"] == 0
        assert result["relations_count"] == 0
        assert result["nodes_processed"] == 0

    def test_build_from_nodes(self, knowledge_graph_builder, mock_llm_service):
        """测试从节点列表构建知识图谱"""
        # 创建测试节点
        node = TextNode(
            text="锂离子电池是一种电化学储能技术，广泛应用于储能系统中。",
            metadata={"section_path": "1.2", "source_document_id": "doc1"},
        )

        # 模拟LLM响应
        mock_llm = mock_llm_service.get_chat_model.return_value
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "entities": [
                {
                    "name": "锂离子电池",
                    "type": "ENERGY_STORAGE_TECHNOLOGY",
                    "description": "一种电化学储能技术",
                    "confidence": 0.9,
                },
                {
                    "name": "储能系统",
                    "type": "ENERGY_STORAGE_DEVICE",
                    "description": "储能设备系统",
                    "confidence": 0.9,
                },
            ],
        })
        mock_llm.invoke.return_value = mock_response

        # 构建知识图谱
        result = knowledge_graph_builder.build_from_nodes([node])

        # 验证结果
        assert result["entities_count"] > 0
        assert result["nodes_processed"] == 1

    def test_extract_entities(self, knowledge_graph_builder, mock_llm_service):
        """测试实体提取"""
        node = TextNode(
            text="锂离子电池是一种电化学储能技术。",
            metadata={"section_path": "1.2"},
        )

        # 模拟LLM响应
        mock_llm = mock_llm_service.get_chat_model.return_value
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "entities": [
                {
                    "name": "锂离子电池",
                    "type": "ENERGY_STORAGE_TECHNOLOGY",
                    "description": "一种电化学储能技术",
                    "confidence": 0.9,
                }
            ],
        })
        mock_llm.invoke.return_value = mock_response

        entities, relations = knowledge_graph_builder._extract_from_node(node)

        assert len(entities) > 0
        assert entities[0].name == "锂离子电池"
        assert entities[0].entity_type == EntityType.ENERGY_STORAGE_TECHNOLOGY

    def test_extract_relations(self, knowledge_graph_builder, mock_llm_service):
        """测试关系提取"""
        node = TextNode(
            text="锂离子电池是储能系统的一种。",
            metadata={"section_path": "1.2"},
        )

        # 先提取实体
        entities = [
            ExtractedEntity(
                name="锂离子电池",
                entity_type=EntityType.ENERGY_STORAGE_TECHNOLOGY,
            ),
            ExtractedEntity(
                name="储能系统",
                entity_type=EntityType.ENERGY_STORAGE_DEVICE,
            ),
        ]

        # 模拟LLM响应
        mock_llm = mock_llm_service.get_chat_model.return_value
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "relations": [
                {
                    "source": "锂离子电池",
                    "target": "储能系统",
                    "relation": "IS_A",
                    "description": "锂离子电池是储能系统的一种",
                    "confidence": 0.9,
                }
            ],
        })
        mock_llm.invoke.return_value = mock_response

        relations = knowledge_graph_builder._extract_relations(
            "锂离子电池是储能系统的一种。",
            node,
            entities,
        )

        assert len(relations) > 0
        assert relations[0].source_entity == "锂离子电池"
        assert relations[0].target_entity == "储能系统"
        assert relations[0].relation_type == RelationType.IS_A

    def test_add_entity_to_graph(self, knowledge_graph_builder, mock_graph_adapter):
        """测试添加实体到图"""
        entity = ExtractedEntity(
            name="锂离子电池",
            entity_type=EntityType.ENERGY_STORAGE_TECHNOLOGY,
            description="一种电化学储能技术",
        )
        node = TextNode(
            text="锂离子电池是一种电化学储能技术。",
            metadata={"section_path": "1.2"},
        )

        entity_id = knowledge_graph_builder._add_entity_to_graph(entity, node)

        assert entity_id is not None
        mock_graph_adapter.add_node.assert_called_once()
        assert "锂离子电池" in knowledge_graph_builder._entity_name_to_id

    def test_add_relation_to_graph(self, knowledge_graph_builder, mock_graph_adapter):
        """测试添加关系到图"""
        # 先添加实体
        entity1 = ExtractedEntity(
            name="锂离子电池",
            entity_type=EntityType.ENERGY_STORAGE_TECHNOLOGY,
        )
        entity2 = ExtractedEntity(
            name="储能系统",
            entity_type=EntityType.ENERGY_STORAGE_DEVICE,
        )
        node = TextNode(
            text="锂离子电池是储能系统的一种。",
            metadata={"section_path": "1.2"},
        )

        entity1_id = knowledge_graph_builder._add_entity_to_graph(entity1, node)
        entity2_id = knowledge_graph_builder._add_entity_to_graph(entity2, node)

        # 添加关系
        relation = ExtractedRelation(
            source_entity="锂离子电池",
            target_entity="储能系统",
            relation_type=RelationType.IS_A,
        )

        knowledge_graph_builder._add_relation_to_graph(relation, node)

        mock_graph_adapter.add_edge.assert_called_once()

    def test_get_entities_by_type(self, knowledge_graph_builder, mock_graph_adapter):
        """测试根据类型查询实体"""
        mock_graph_adapter.list_nodes.return_value = [
            {"id": "1", "name": "锂离子电池", "entity_type": "ENERGY_STORAGE_TECHNOLOGY"},
        ]

        entities = knowledge_graph_builder.get_entities_by_type(
            EntityType.ENERGY_STORAGE_TECHNOLOGY,
        )

        assert len(entities) > 0
        mock_graph_adapter.list_nodes.assert_called_once()

    def test_get_relations_by_type(self, knowledge_graph_builder, mock_graph_adapter):
        """测试根据类型查询关系"""
        mock_graph_adapter.list_edges.return_value = [
            {
                "source": "1",
                "target": "2",
                "relation_type": "IS_A",
            },
        ]

        relations = knowledge_graph_builder.get_relations_by_type(RelationType.IS_A)

        assert len(relations) > 0
        mock_graph_adapter.list_edges.assert_called_once()

    def test_get_entity_neighbors(self, knowledge_graph_builder, mock_graph_adapter):
        """测试获取实体邻居"""
        # 设置实体映射
        knowledge_graph_builder._entity_name_to_id["锂离子电池"] = "entity1"

        mock_graph_adapter.get_neighbors.return_value = ["entity2"]
        mock_graph_adapter.get_node.return_value = {
            "id": "entity2",
            "name": "储能系统",
        }

        neighbors = knowledge_graph_builder.get_entity_neighbors("锂离子电池")

        assert len(neighbors) > 0
        mock_graph_adapter.get_neighbors.assert_called_once()

    def test_get_stats(self, knowledge_graph_builder, mock_graph_adapter):
        """测试获取统计信息"""
        mock_graph_adapter.count_nodes.return_value = 10
        mock_graph_adapter.count_edges.return_value = 5
        mock_graph_adapter.get_graph_info.return_value = {"name": "test_graph"}

        stats = knowledge_graph_builder.get_stats()

        assert stats["node_count"] == 10
        assert stats["edge_count"] == 5
        assert stats["graph_name"] == "test_graph"

    def test_entity_disambiguation(self, knowledge_graph_builder, mock_graph_adapter):
        """测试实体消歧"""
        entity = ExtractedEntity(
            name="锂离子电池",
            entity_type=EntityType.ENERGY_STORAGE_TECHNOLOGY,
        )
        node = TextNode(
            text="锂离子电池是一种电化学储能技术。",
            metadata={"section_path": "1.2"},
        )

        # 第一次添加
        entity_id1 = knowledge_graph_builder._add_entity_to_graph(entity, node)

        # 第二次添加相同名称的实体（应该更新而不是创建新节点）
        entity_id2 = knowledge_graph_builder._add_entity_to_graph(entity, node)

        assert entity_id1 == entity_id2
        # 应该调用update_node而不是add_node
        assert mock_graph_adapter.update_node.called

    def test_parse_entities_from_text(self, knowledge_graph_builder):
        """测试从文本中解析实体（降级方案）"""
        text = '{"entities": [{"name": "锂离子电池", "type": "ENERGY_STORAGE_TECHNOLOGY"}]}'

        entities = knowledge_graph_builder._parse_entities_from_text(text)

        assert len(entities) > 0
        assert entities[0]["name"] == "锂离子电池"

    def test_parse_relations_from_text(self, knowledge_graph_builder):
        """测试从文本中解析关系（降级方案）"""
        text = '{"relations": [{"source": "锂离子电池", "target": "储能系统", "relation": "IS_A"}]}'

        relations = knowledge_graph_builder._parse_relations_from_text(text)

        assert len(relations) > 0
        assert relations[0]["source"] == "锂离子电池"

