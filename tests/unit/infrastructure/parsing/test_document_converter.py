"""
T059 Document格式转换适配器测试

测试LangChain Document到LlamaIndex Node的转换功能。
"""

import pytest
from langchain_core.documents import Document

from src.infrastructure.parsing.document_converter import (
    ConversionError,
    LangChainDocumentToNodeConverter,
)


class TestLangChainDocumentToNodeConverter:
    """LangChainDocumentToNodeConverter测试类"""

    def test_convert_document_basic(self):
        """测试基本Document转换"""
        converter = LangChainDocumentToNodeConverter()

        document = Document(
            page_content="测试内容",
            metadata={"source": "test.md", "format": "markdown"},
        )

        try:
            node = converter.convert_document(document)
            assert node is not None
            assert hasattr(node, "text")
            assert node.text == "测试内容"
            assert hasattr(node, "metadata")
            assert node.metadata["source"] == "test.md"
            assert node.metadata["format"] == "markdown"
        except ImportError:
            pytest.skip("LlamaIndex not installed")

    def test_convert_documents_batch(self):
        """测试批量Document转换"""
        converter = LangChainDocumentToNodeConverter()

        documents = [
            Document(
                page_content=f"内容 {i}",
                metadata={"source": f"test_{i}.md", "format": "markdown"},
            )
            for i in range(3)
        ]

        try:
            nodes = converter.convert_documents(documents)
            assert len(nodes) == 3
            for i, node in enumerate(nodes):
                assert node.text == f"内容 {i}"
                assert node.metadata["source"] == f"test_{i}.md"
        except ImportError:
            pytest.skip("LlamaIndex not installed")

    def test_preserve_metadata(self):
        """测试元数据保留"""
        converter = LangChainDocumentToNodeConverter(preserve_metadata=True)

        document = Document(
            page_content="测试内容",
            metadata={
                "source": "test.md",
                "format": "markdown",
                "page": 1,
                "processed_at": "2025-12-19T10:00:00",
            },
        )

        try:
            node = converter.convert_document(document)
            assert "source" in node.metadata
            assert "format" in node.metadata
            assert "page" in node.metadata
            assert "processed_at" in node.metadata
        except ImportError:
            pytest.skip("LlamaIndex not installed")

    def test_custom_node_id_generator(self):
        """测试自定义节点ID生成器"""
        def custom_id_gen(doc: Document) -> str:
            return f"custom_{doc.metadata.get('source', 'unknown')}"

        converter = LangChainDocumentToNodeConverter(
            node_id_generator=custom_id_gen
        )

        document = Document(
            page_content="测试内容",
            metadata={"source": "test.md", "format": "markdown"},
        )

        try:
            node = converter.convert_document(document)
            assert node.id_ == "custom_test.md"
        except ImportError:
            pytest.skip("LlamaIndex not installed")

    def test_invalid_document(self):
        """测试无效Document处理"""
        converter = LangChainDocumentToNodeConverter()

        with pytest.raises(ValueError):
            converter.convert_document("not a document")  # type: ignore

