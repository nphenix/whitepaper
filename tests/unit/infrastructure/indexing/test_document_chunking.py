"""
T052 文档分块策略单元测试

测试文档分块策略的各种功能,包括:
- 配置验证
- 句子级分块逻辑
- 章节路径保留
- 段落索引生成
- 元数据保留
- 错误处理

生成命令: /speckit.implement T052
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

from src.infrastructure.indexing.document_chunking import (
    DocumentChunkingStrategy,
    ChunkingConfig,
    ChunkingError,
)


@pytest.mark.skipif(
    not LLAMA_INDEX_AVAILABLE,
    reason="LlamaIndex not available",
)
class TestChunkingConfig:
    """测试文档分块配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = ChunkingConfig()
        assert config.chunk_size == 1024
        assert config.chunk_overlap == 200
        assert config.split_by_section is True
        assert config.split_by_paragraph is True

    def test_custom_config(self):
        """测试自定义配置"""
        config = ChunkingConfig(
            chunk_size=512,
            chunk_overlap=100,
            split_by_section=False,
            split_by_paragraph=False,
        )
        assert config.chunk_size == 512
        assert config.chunk_overlap == 100
        assert config.split_by_section is False
        assert config.split_by_paragraph is False

    def test_invalid_chunk_size_zero(self):
        """测试无效的chunk_size (0)"""
        with pytest.raises(ValueError, match="chunk_size 必须为正整数"):
            ChunkingConfig(chunk_size=0)

    def test_invalid_chunk_size_negative(self):
        """测试无效的chunk_size (负数)"""
        with pytest.raises(ValueError, match="chunk_size 必须为正整数"):
            ChunkingConfig(chunk_size=-1)

    def test_invalid_chunk_overlap_negative(self):
        """测试无效的chunk_overlap (负数)"""
        with pytest.raises(ValueError, match="chunk_overlap 不能为负数"):
            ChunkingConfig(chunk_overlap=-1)

    def test_overlap_too_large(self):
        """测试overlap大于等于chunk_size"""
        with pytest.raises(ValueError, match="chunk_overlap.*必须小于"):
            ChunkingConfig(chunk_size=100, chunk_overlap=100)

        with pytest.raises(ValueError, match="chunk_overlap.*必须小于"):
            ChunkingConfig(chunk_size=100, chunk_overlap=150)


@pytest.mark.skipif(
    not LLAMA_INDEX_AVAILABLE,
    reason="LlamaIndex not available",
)
class TestDocumentChunkingStrategy:
    """测试文档分块策略"""

    def test_init_default_config(self):
        """测试使用默认配置初始化"""
        strategy = DocumentChunkingStrategy()
        assert strategy.config.chunk_size == 1024
        assert strategy.config.chunk_overlap == 200
        assert strategy.config.split_by_section is True
        assert strategy.config.split_by_paragraph is True

    def test_init_custom_config(self):
        """测试使用自定义配置初始化"""
        config = ChunkingConfig(
            chunk_size=512,
            chunk_overlap=100,
            split_by_section=False,
            split_by_paragraph=False,
        )
        strategy = DocumentChunkingStrategy(config)
        assert strategy.config.chunk_size == 512
        assert strategy.config.chunk_overlap == 100
        assert strategy.config.split_by_section is False
        assert strategy.config.split_by_paragraph is False

    def test_chunk_empty_nodes(self):
        """测试空节点列表"""
        strategy = DocumentChunkingStrategy()
        result = strategy.chunk_nodes([])
        assert result == []

    def test_chunk_single_node_small_text(self):
        """测试单个小文本节点（不需要分块）"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=1000))
        
        node = TextNode(
            text="这是一个简短的文本。",
            metadata={"source": "test.md", "format": "markdown"},
        )
        
        result = strategy.chunk_nodes([node])
        assert len(result) == 1
        assert result[0].text == "这是一个简短的文本。"
        assert result[0].metadata["source"] == "test.md"
        assert result[0].metadata["format"] == "markdown"
        assert "chunk_index" in result[0].metadata
        assert result[0].metadata["chunk_index"] == 0

    def test_chunk_single_node_large_text(self):
        """测试单个大文本节点（需要分块）"""
        # 创建一个超过chunk_size的长文本
        long_text = "这是一个很长的文本。" * 100  # 约800字符
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        node = TextNode(
            text=long_text,
            metadata={"source": "test.md", "format": "markdown"},
        )
        
        result = strategy.chunk_nodes([node])
        assert len(result) > 1  # 应该被分成多个块
        assert all("chunk_index" in chunk.metadata for chunk in result)
        assert all("chunk_index_in_node" in chunk.metadata for chunk in result)
        assert all("original_node_index" in chunk.metadata for chunk in result)
        
        # 检查chunk_index是连续的
        chunk_indices = [chunk.metadata["chunk_index"] for chunk in result]
        assert chunk_indices == list(range(len(result)))

    def test_chunk_preserves_section_path(self):
        """测试保留章节路径"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        node = TextNode(
            text="这是第一章的内容。" * 20,
            metadata={
                "source": "test.md",
                "format": "markdown",
                "section_path": "1",
                "section_title": "第一章",
            },
        )
        
        result = strategy.chunk_nodes([node])
        assert len(result) > 0
        for chunk in result:
            assert chunk.metadata.get("section_path") == "1"
            assert chunk.metadata.get("section_title") == "第一章"

    def test_chunk_generates_paragraph_index(self):
        """测试生成段落索引"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        # 创建多个段落类节点
        nodes = [
            TextNode(
                text=f"这是第{i+1}段的内容。" * 20,
                metadata={
                    "source": "test.md",
                    "format": "markdown",
                    "section_path": "1",
                    "element_type": "paragraph",
                },
            )
            for i in range(3)
        ]
        
        result = strategy.chunk_nodes(nodes)
        assert len(result) > 0
        
        # 检查段落索引是否正确生成
        paragraph_indices = [
            chunk.metadata.get("paragraph_index")
            for chunk in result
            if "paragraph_index" in chunk.metadata
        ]
        assert len(paragraph_indices) > 0
        # 段落索引应该从1开始
        assert min(paragraph_indices) >= 1

    def test_chunk_multiple_nodes(self):
        """测试多个节点分块"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        nodes = [
            TextNode(
                text=f"节点{i}的内容。" * 20,
                metadata={
                    "source": f"test_{i}.md",
                    "format": "markdown",
                },
            )
            for i in range(3)
        ]
        
        result = strategy.chunk_nodes(nodes)
        assert len(result) > 0
        
        # 检查所有块都有正确的元数据
        for chunk in result:
            assert "chunk_index" in chunk.metadata
            assert "original_node_index" in chunk.metadata
            assert chunk.metadata["original_node_index"] in [0, 1, 2]

    def test_chunk_preserves_all_metadata(self):
        """测试保留所有元数据"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        node = TextNode(
            text="测试内容。" * 30,
            metadata={
                "source": "test.md",
                "format": "markdown",
                "page": 1,
                "processed_at": "2025-12-19T10:00:00",
                "custom_field": "custom_value",
            },
        )
        
        result = strategy.chunk_nodes([node])
        assert len(result) > 0
        
        # 检查所有原始元数据都被保留
        for chunk in result:
            assert chunk.metadata.get("source") == "test.md"
            assert chunk.metadata.get("format") == "markdown"
            assert chunk.metadata.get("page") == 1
            assert chunk.metadata.get("processed_at") == "2025-12-19T10:00:00"
            assert chunk.metadata.get("custom_field") == "custom_value"

    def test_chunk_skips_empty_nodes(self):
        """测试跳过空文本节点"""
        strategy = DocumentChunkingStrategy()
        
        nodes = [
            TextNode(text="正常内容。", metadata={"source": "test.md"}),
            TextNode(text="", metadata={"source": "test2.md"}),  # 空文本
            TextNode(text="   ", metadata={"source": "test3.md"}),  # 只有空白
            TextNode(text="另一个正常内容。", metadata={"source": "test4.md"}),
        ]
        
        result = strategy.chunk_nodes(nodes)
        # 应该只处理非空节点
        assert len(result) > 0
        # 检查所有结果都有内容
        assert all(chunk.text.strip() for chunk in result)

    def test_chunk_with_different_section_paths(self):
        """测试不同章节路径的节点"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        nodes = [
            TextNode(
                text="第一章内容。" * 20,
                metadata={
                    "section_path": "1",
                    "section_title": "第一章",
                    "element_type": "paragraph",
                },
            ),
            TextNode(
                text="第二章内容。" * 20,
                metadata={
                    "section_path": "2",
                    "section_title": "第二章",
                    "element_type": "paragraph",
                },
            ),
        ]
        
        result = strategy.chunk_nodes(nodes)
        assert len(result) > 0
        
        # 检查章节路径是否正确保留
        section_paths = set(chunk.metadata.get("section_path") for chunk in result)
        assert "1" in section_paths
        assert "2" in section_paths

    def test_chunk_without_section_path(self):
        """测试没有章节路径的节点"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        node = TextNode(
            text="没有章节的内容。" * 20,
            metadata={
                "source": "test.md",
                "format": "markdown",
            },
        )
        
        result = strategy.chunk_nodes([node])
        assert len(result) > 0
        
        # 没有section_path时，paragraph_index应该使用"root"作为key
        for chunk in result:
            # 应该仍然有chunk_index等基本元数据
            assert "chunk_index" in chunk.metadata

    def test_chunk_with_non_paragraph_element_types(self):
        """测试非段落类元素类型"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        # 测试不同类型的元素
        nodes = [
            TextNode(
                text="段落内容。" * 20,
                metadata={
                    "element_type": "paragraph",
                    "section_path": "1",
                },
            ),
            TextNode(
                text="表格内容。" * 20,
                metadata={
                    "element_type": "table",
                    "section_path": "1",
                },
            ),
            TextNode(
                text="代码块内容。" * 20,
                metadata={
                    "element_type": "code_block",
                    "section_path": "1",
                },
            ),
        ]
        
        result = strategy.chunk_nodes(nodes)
        assert len(result) > 0
        
        # 段落类元素应该有paragraph_index
        paragraph_chunks = [
            chunk for chunk in result
            if chunk.metadata.get("element_type") == "paragraph"
        ]
        if paragraph_chunks:
            assert any("paragraph_index" in chunk.metadata for chunk in paragraph_chunks)

    def test_chunk_split_by_section_disabled(self):
        """测试禁用按章节分块"""
        strategy = DocumentChunkingStrategy(
            ChunkingConfig(chunk_size=200, chunk_overlap=50, split_by_section=False)
        )
        
        node = TextNode(
            text="测试内容。" * 20,
            metadata={
                "section_path": "1",
                "section_title": "第一章",
            },
        )
        
        result = strategy.chunk_nodes([node])
        assert len(result) > 0
        
        # 即使split_by_section=False，section_path仍然会被保留（因为来自原始元数据）
        # 但不会强制设置
        for chunk in result:
            # section_path可能仍然存在（来自原始元数据），但不强制要求
            assert "chunk_index" in chunk.metadata

    def test_chunk_split_by_paragraph_disabled(self):
        """测试禁用按段落分块"""
        strategy = DocumentChunkingStrategy(
            ChunkingConfig(chunk_size=200, chunk_overlap=50, split_by_paragraph=False)
        )
        
        node = TextNode(
            text="测试内容。" * 20,
            metadata={
                "section_path": "1",
                "element_type": "paragraph",
            },
        )
        
        result = strategy.chunk_nodes([node])
        assert len(result) > 0
        
        # 当split_by_paragraph=False时，不应该有paragraph_index
        for chunk in result:
            assert "paragraph_index" not in chunk.metadata

    def test_chunk_index_continuity(self):
        """测试chunk_index的连续性"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        nodes = [
            TextNode(
                text=f"节点{i}的内容。" * 20,
                metadata={"source": f"test_{i}.md"},
            )
            for i in range(3)
        ]
        
        result = strategy.chunk_nodes(nodes)
        assert len(result) > 0
        
        # 检查chunk_index是连续的，从0开始
        chunk_indices = sorted([chunk.metadata["chunk_index"] for chunk in result])
        assert chunk_indices == list(range(len(result)))

    def test_chunk_index_in_node(self):
        """测试chunk_index_in_node的正确性"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        # 创建一个会被分成多个块的节点
        long_text = "这是一个很长的文本。" * 50
        node = TextNode(
            text=long_text,
            metadata={"source": "test.md"},
        )
        
        result = strategy.chunk_nodes([node])
        assert len(result) > 1
        
        # 检查chunk_index_in_node从0开始，连续递增
        chunk_indices_in_node = [
            chunk.metadata["chunk_index_in_node"] for chunk in result
        ]
        assert chunk_indices_in_node == list(range(len(result)))

    def test_chunk_original_node_index(self):
        """测试original_node_index的正确性"""
        strategy = DocumentChunkingStrategy(ChunkingConfig(chunk_size=200, chunk_overlap=50))
        
        nodes = [
            TextNode(
                text=f"节点{i}的内容。" * 20,
                metadata={"source": f"test_{i}.md"},
            )
            for i in range(3)
        ]
        
        result = strategy.chunk_nodes(nodes)
        assert len(result) > 0
        
        # 检查original_node_index是否正确
        for chunk in result:
            original_index = chunk.metadata["original_node_index"]
            assert original_index in [0, 1, 2]
            # 验证chunk来自正确的原始节点
            assert chunk.metadata.get("source") == f"test_{original_index}.md"

