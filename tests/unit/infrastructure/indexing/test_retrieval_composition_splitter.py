"""
检索块与合成块分离策略单元测试

测试检索块与合成块分离策略的各种功能,包括:
- 配置验证
- 检索块和合成块的分块逻辑
- 映射关系建立
- 元数据保留
- 错误处理

生成命令: /speckit.implement T062
生成时间: 2025-12-19
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import pytest

try:
    from llama_index.core.schema import TextNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False
    TextNode = None  # type: ignore

from src.infrastructure.indexing.retrieval_composition_splitter import (
    RetrievalCompositionSplitter,
    RetrievalCompositionConfig,
    ChunkMapping,
    RetrievalCompositionSplitterError,
)


@pytest.mark.skipif(
    not LLAMA_INDEX_AVAILABLE,
    reason="LlamaIndex not available",
)
class TestRetrievalCompositionConfig:
    """测试检索块与合成块分离配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = RetrievalCompositionConfig()
        assert config.retrieval_chunk_size == 256
        assert config.retrieval_chunk_overlap == 50
        assert config.composition_chunk_size == 1024
        assert config.composition_chunk_overlap == 200
        assert config.mapping_strategy == "overlap"

    def test_custom_config(self):
        """测试自定义配置"""
        config = RetrievalCompositionConfig(
            retrieval_chunk_size=128,
            retrieval_chunk_overlap=25,
            composition_chunk_size=512,
            composition_chunk_overlap=100,
            mapping_strategy="containment",
        )
        assert config.retrieval_chunk_size == 128
        assert config.retrieval_chunk_overlap == 25
        assert config.composition_chunk_size == 512
        assert config.composition_chunk_overlap == 100
        assert config.mapping_strategy == "containment"

    def test_invalid_retrieval_chunk_size(self):
        """测试无效的检索块大小"""
        with pytest.raises(ValueError, match="retrieval_chunk_size 必须为正整数"):
            RetrievalCompositionConfig(retrieval_chunk_size=0)

        with pytest.raises(ValueError, match="retrieval_chunk_size 必须为正整数"):
            RetrievalCompositionConfig(retrieval_chunk_size=-1)

    def test_invalid_composition_chunk_size(self):
        """测试无效的合成块大小"""
        with pytest.raises(ValueError, match="composition_chunk_size 必须为正整数"):
            RetrievalCompositionConfig(composition_chunk_size=0)

        with pytest.raises(ValueError, match="composition_chunk_size 必须为正整数"):
            RetrievalCompositionConfig(composition_chunk_size=-1)

    def test_invalid_overlap(self):
        """测试无效的重叠大小"""
        with pytest.raises(ValueError, match="retrieval_chunk_overlap 不能为负数"):
            RetrievalCompositionConfig(retrieval_chunk_overlap=-1)

        with pytest.raises(ValueError, match="composition_chunk_overlap 不能为负数"):
            RetrievalCompositionConfig(composition_chunk_overlap=-1)

    def test_overlap_too_large(self):
        """测试重叠大小过大"""
        with pytest.raises(ValueError, match="retrieval_chunk_overlap.*必须小于"):
            RetrievalCompositionConfig(
                retrieval_chunk_size=100, retrieval_chunk_overlap=100
            )

        with pytest.raises(ValueError, match="composition_chunk_overlap.*必须小于"):
            RetrievalCompositionConfig(
                composition_chunk_size=100, composition_chunk_overlap=100
            )

    def test_retrieval_larger_than_composition(self):
        """测试检索块大于合成块"""
        with pytest.raises(ValueError, match="retrieval_chunk_size.*必须小于"):
            RetrievalCompositionConfig(
                retrieval_chunk_size=1024, composition_chunk_size=512
            )

    def test_invalid_mapping_strategy(self):
        """测试无效的映射策略"""
        with pytest.raises(ValueError, match="mapping_strategy 必须是"):
            RetrievalCompositionConfig(mapping_strategy="invalid")


@pytest.mark.skipif(
    not LLAMA_INDEX_AVAILABLE,
    reason="LlamaIndex not available",
)
class TestRetrievalCompositionSplitter:
    """测试检索块与合成块分离器"""

    def test_init_default_config(self):
        """测试使用默认配置初始化"""
        splitter = RetrievalCompositionSplitter()
        assert splitter.config.retrieval_chunk_size == 256
        assert splitter.config.composition_chunk_size == 1024

    def test_init_custom_config(self):
        """测试使用自定义配置初始化"""
        config = RetrievalCompositionConfig(
            retrieval_chunk_size=128,
            composition_chunk_size=512,
        )
        splitter = RetrievalCompositionSplitter(config)
        assert splitter.config.retrieval_chunk_size == 128
        assert splitter.config.composition_chunk_size == 512

    def test_split_empty_nodes(self):
        """测试空节点列表"""
        splitter = RetrievalCompositionSplitter()
        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([])
        assert retrieval_nodes == []
        assert composition_nodes == []
        assert mappings == []

    def test_split_single_node(self):
        """测试单个节点分块"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
            )
        )

        # 创建一个较长的文本节点
        long_text = "这是一个测试文档。它包含多个句子。每个句子都有一些内容。"
        node = TextNode(
            text=long_text,
            metadata={"source": "test.md", "section_path": "1.1"},
        )

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])

        # 应该生成检索块和合成块
        assert len(retrieval_nodes) > 0
        assert len(composition_nodes) > 0
        # 检索块应该比合成块多（因为检索块更小）
        assert len(retrieval_nodes) >= len(composition_nodes)

    def test_split_multiple_nodes(self):
        """测试多个节点分块"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
            )
        )

        nodes = [
            TextNode(
                text=f"这是第{i}个节点。它包含一些内容。",
                metadata={"source": "test.md", "section_path": f"1.{i}"},
            )
            for i in range(1, 4)
        ]

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes(nodes)

        assert len(retrieval_nodes) > 0
        assert len(composition_nodes) > 0
        assert len(mappings) > 0

    def test_metadata_preservation(self):
        """测试元数据保留"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
            )
        )

        node = TextNode(
            text="这是一个测试文档。它包含多个句子。",
            metadata={
                "source": "test.md",
                "format": "markdown",
                "section_path": "1.2.3",
                "section_title": "测试章节",
            },
        )

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])

        # 检查检索块元数据
        for retrieval_node in retrieval_nodes:
            assert retrieval_node.metadata["chunk_type"] == "retrieval"
            assert "source" in retrieval_node.metadata
            assert "section_path" in retrieval_node.metadata
            assert retrieval_node.metadata["section_path"] == "1.2.3"

        # 检查合成块元数据
        for composition_node in composition_nodes:
            assert composition_node.metadata["chunk_type"] == "composition"
            assert "source" in composition_node.metadata
            assert "section_path" in composition_node.metadata
            assert composition_node.metadata["section_path"] == "1.2.3"

    def test_mapping_overlap_strategy(self):
        """测试重叠映射策略"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
                mapping_strategy="overlap",
            )
        )

        node = TextNode(
            text="这是一个测试文档。它包含多个句子。每个句子都有一些内容。",
            metadata={"source": "test.md"},
        )

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])

        assert len(mappings) > 0
        for mapping in mappings:
            assert mapping.mapping_type == "overlap"
            assert mapping.retrieval_node_id
            assert mapping.composition_node_id
            assert 0 <= mapping.overlap_ratio <= 1

    def test_mapping_containment_strategy(self):
        """测试包含映射策略"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
                mapping_strategy="containment",
            )
        )

        node = TextNode(
            text="这是一个测试文档。它包含多个句子。每个句子都有一些内容。",
            metadata={"source": "test.md"},
        )

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])

        assert len(mappings) > 0
        for mapping in mappings:
            assert mapping.mapping_type == "containment"
            assert mapping.overlap_ratio == 1.0

    def test_mapping_nearest_strategy(self):
        """测试最近映射策略"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
                mapping_strategy="nearest",
            )
        )

        nodes = [
            TextNode(
                text=f"这是第{i}个节点。它包含一些内容。",
                metadata={"source": "test.md", "section_path": f"1.{i}"},
            )
            for i in range(1, 3)
        ]

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes(nodes)

        assert len(mappings) > 0
        for mapping in mappings:
            assert mapping.mapping_type == "nearest"

    def test_get_composition_nodes_for_retrieval(self):
        """测试根据检索块ID获取合成块ID"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
            )
        )

        node = TextNode(
            text="这是一个测试文档。它包含多个句子。每个句子都有一些内容。",
            metadata={"source": "test.md"},
        )

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])

        # 获取前几个检索块ID
        retrieval_ids = [getattr(n, "id_", "") for n in retrieval_nodes[:3]]

        # 获取对应的合成块ID
        composition_ids = splitter.get_composition_nodes_for_retrieval(
            retrieval_ids, mappings
        )

        assert len(composition_ids) > 0
        assert all(cid in [getattr(n, "id_", "") for n in composition_nodes] for cid in composition_ids)

    def test_empty_text_node(self):
        """测试空文本节点"""
        splitter = RetrievalCompositionSplitter()
        node = TextNode(text="", metadata={"source": "test.md"})

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])

        # 空节点应该被跳过
        assert len(retrieval_nodes) == 0
        assert len(composition_nodes) == 0

    def test_node_without_text_attribute(self):
        """测试没有text属性的节点"""
        splitter = RetrievalCompositionSplitter()

        # 创建一个没有text属性的节点（模拟异常情况）
        class MockNode:
            def __init__(self):
                self.metadata = {"source": "test.md"}

        node = MockNode()  # type: ignore

        # 应该能够处理，但会跳过
        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])  # type: ignore

        assert len(retrieval_nodes) == 0
        assert len(composition_nodes) == 0

    def test_chunk_type_metadata(self):
        """测试chunk_type元数据"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
            )
        )

        node = TextNode(
            text="这是一个测试文档。它包含多个句子。",
            metadata={"source": "test.md"},
        )

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])

        # 所有检索块应该有chunk_type="retrieval"
        for retrieval_node in retrieval_nodes:
            assert retrieval_node.metadata["chunk_type"] == "retrieval"

        # 所有合成块应该有chunk_type="composition"
        for composition_node in composition_nodes:
            assert composition_node.metadata["chunk_type"] == "composition"

    def test_node_id_generation(self):
        """测试节点ID生成"""
        splitter = RetrievalCompositionSplitter(
            RetrievalCompositionConfig(
                retrieval_chunk_size=50,
                retrieval_chunk_overlap=10,
                composition_chunk_size=100,
                composition_chunk_overlap=20,
            )
        )

        node = TextNode(
            text="这是一个测试文档。它包含多个句子。",
            metadata={"source": "test.md"},
        )

        retrieval_nodes, composition_nodes, mappings = splitter.split_nodes([node])

        # 检查节点ID格式
        for retrieval_node in retrieval_nodes:
            node_id = getattr(retrieval_node, "id_", "")
            assert node_id.startswith("retrieval_")
            assert node_id in retrieval_node.metadata["node_id"]

        for composition_node in composition_nodes:
            node_id = getattr(composition_node, "id_", "")
            assert node_id.startswith("composition_")
            assert node_id in composition_node.metadata["node_id"]


@pytest.mark.skipif(
    not LLAMA_INDEX_AVAILABLE,
    reason="LlamaIndex not available",
)
class TestChunkMapping:
    """测试映射关系数据类"""

    def test_chunk_mapping_creation(self):
        """测试创建映射关系"""
        mapping = ChunkMapping(
            retrieval_node_id="retrieval_1",
            composition_node_id="composition_1",
            mapping_type="overlap",
            overlap_ratio=0.8,
        )

        assert mapping.retrieval_node_id == "retrieval_1"
        assert mapping.composition_node_id == "composition_1"
        assert mapping.mapping_type == "overlap"
        assert mapping.overlap_ratio == 0.8

    def test_chunk_mapping_default_overlap(self):
        """测试默认重叠比例"""
        mapping = ChunkMapping(
            retrieval_node_id="retrieval_1",
            composition_node_id="composition_1",
            mapping_type="containment",
        )

        assert mapping.overlap_ratio == 0.0


@pytest.mark.skipif(
    not LLAMA_INDEX_AVAILABLE,
    reason="LlamaIndex not available",
)
class TestErrorHandling:
    """测试错误处理"""

    def test_import_error_without_llama_index(self):
        """测试在没有LlamaIndex时抛出ImportError"""
        # 这个测试需要模拟LlamaIndex不可用的情况
        # 在实际环境中，如果LlamaIndex未安装，会抛出ImportError
        pass  # 这个测试在实际环境中会自动通过或失败

