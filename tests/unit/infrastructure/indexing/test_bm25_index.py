"""
BM25索引构建器单元测试 (T047)

测试BM25索引构建器的各项功能，包括索引构建、查询、更新、删除等。
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.infrastructure.indexing.bm25_index import BM25IndexBuilder, BM25IndexError
from src.shared.exceptions.storage_exceptions import StorageError

try:
    from llama_index.core.schema import TextNode, NodeWithScore
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False


class TestBM25IndexBuilder(unittest.TestCase):
    """BM25索引构建器测试类"""

    def setUp(self) -> None:
        """测试前准备"""
        # 创建临时目录
        self.temp_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.temp_dir, "test_bm25_index.pkl")

        # 创建测试节点
        self.test_nodes = []
        if LLAMA_INDEX_AVAILABLE:
            self.test_nodes = [
                TextNode(
                    text="储能技术是新能源领域的重要组成部分",
                    metadata={"section_path": "1.1", "document_id": "doc1"},
                ),
                TextNode(
                    text="锂电池是目前最主流的储能技术",
                    metadata={"section_path": "1.2", "document_id": "doc1"},
                ),
                TextNode(
                    text="储能系统在电力调峰中发挥重要作用",
                    metadata={"section_path": "2.1", "document_id": "doc2"},
                ),
                TextNode(
                    text="抽水蓄能是目前最成熟的储能技术",
                    metadata={"section_path": "2.2", "document_id": "doc2"},
                ),
            ]

    def tearDown(self) -> None:
        """测试后清理"""
        # 清理临时文件
        if os.path.exists(self.index_path):
            os.remove(self.index_path)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_init_with_path(self) -> None:
        """测试使用路径初始化"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        self.assertEqual(builder.index_path, self.index_path)
        self.assertEqual(builder.k1, 1.2)
        self.assertEqual(builder.b, 0.75)
        self.assertEqual(builder.epsilon, 0.25)

    def test_init_without_path(self) -> None:
        """测试不使用路径初始化"""
        builder = BM25IndexBuilder()
        self.assertIsNone(builder.index_path)
        self.assertEqual(builder.k1, 1.2)
        self.assertEqual(builder.b, 0.75)
        self.assertEqual(builder.epsilon, 0.25)

    def test_init_with_custom_params(self) -> None:
        """测试使用自定义参数初始化"""
        builder = BM25IndexBuilder(
            index_path=self.index_path,
            k1=1.5,
            b=0.8,
            epsilon=0.3,
        )
        self.assertEqual(builder.k1, 1.5)
        self.assertEqual(builder.b, 0.8)
        self.assertEqual(builder.epsilon, 0.3)

    def test_tokenize(self) -> None:
        """测试分词功能"""
        builder = BM25IndexBuilder()
        text = "储能技术是新能源领域的重要组成部分"
        tokens = builder._tokenize(text)
        
        # 验证基本功能：应该包含原始文本
        self.assertIn("储能技术是新能源领域的重要组成部分", tokens)
        
        # 验证单字符token存在
        single_chars = ["储", "能", "技", "术", "是", "新", "能", "源", "领", "域", "的", "重", "要", "组", "成", "部", "分"]
        for char in single_chars:
            self.assertIn(char, tokens, f"单字符 '{char}' 应该存在于tokens中")
        
        # 验证2-gram存在（相邻的两个字符）
        # 文本字符序列：储(0)、能(1)、技(2)、术(3)、是(4)、新(5)、能(6)、源(7)、领(8)、域(9)、的(10)、重(11)、要(12)、组(13)、成(14)、部(15)、分(16)
        bigrams = [
            "储能",  # 0-1
            "能技",  # 1-2
            "技术",  # 2-3
            "术是",  # 3-4
            "是新",  # 4-5
            "新能",  # 5-6
            "能源",  # 6-7
            "源领",  # 7-8
            "领域",  # 8-9
            "域的",  # 9-10
            "的重",  # 10-11
            "重要",  # 11-12
            "要组",  # 12-13
            "组成",  # 13-14
            "成部",  # 14-15
            "部分",  # 15-16
        ]
        for bigram in bigrams:
            self.assertIn(bigram, tokens, f"2-gram '{bigram}' 应该存在于tokens中")
        
        # 验证3-gram存在（相邻的三个字符）
        trigrams = [
            "储能技",  # 0-2
            "能技术",  # 1-3
            "技术是",  # 2-4
            "术是新",  # 3-5
            "是新能",  # 4-6
            "新能源",  # 5-7
            "能源领",  # 6-8
            "源领域",  # 7-9
            "领域的",  # 8-10
            "域的重",  # 9-11
            "的重要",  # 10-12
            "重要组",  # 11-13
            "要组成",  # 12-14
            "组成部",  # 13-15
            "成部分",  # 14-16
        ]
        for trigram in trigrams:
            self.assertIn(trigram, tokens, f"3-gram '{trigram}' 应该存在于tokens中")
        
        # 验证tokens数量合理（应该包含原始词、单字符、2-gram、3-gram）
        # 至少应该有原始词 + 17个单字符 + 16个2-gram + 15个3-gram = 49个token
        self.assertGreaterEqual(len(tokens), 40, "tokens数量应该足够多")

    def test_calculate_stats(self) -> None:
        """测试统计信息计算"""
        builder = BM25IndexBuilder()
        builder._document_texts = [
            "储能技术是新能源",
            "锂电池是主流技术",
            "储能系统很重要",
        ]
        builder._calculate_stats()
        self.assertGreater(builder._vocab_size, 0)
        self.assertGreater(builder._avg_doc_length, 0)

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_build_index(self) -> None:
        """测试构建索引"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        builder.build_index(self.test_nodes)

        # 验证索引数据
        self.assertEqual(len(builder._documents), len(self.test_nodes))
        self.assertEqual(len(builder._document_texts), len(self.test_nodes))
        self.assertEqual(len(builder._metadata), len(self.test_nodes))
        self.assertIsNotNone(builder._bm25_index)
        self.assertGreater(builder._vocab_size, 0)
        self.assertGreater(builder._avg_doc_length, 0)

        # 验证文件已创建
        self.assertTrue(os.path.exists(self.index_path))

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_build_index_empty_nodes(self) -> None:
        """测试构建空节点列表的索引"""
        builder = BM25IndexBuilder()
        with self.assertRaises(ValueError) as context:
            builder.build_index([])
        self.assertIn("必须提供nodes", str(context.exception))

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_query(self) -> None:
        """测试查询索引"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        builder.build_index(self.test_nodes)

        # 查询储能相关内容
        results = builder.query("储能技术", top_k=2)
        self.assertLessEqual(len(results), 2)
        self.assertGreater(len(results), 0)

        # 验证结果类型
        for result in results:
            if LLAMA_INDEX_AVAILABLE:
                self.assertIsInstance(result, NodeWithScore)
                self.assertIsNotNone(result.node)
                self.assertIsInstance(result.score, float)
                self.assertGreaterEqual(result.score, 0)

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_query_empty_string(self) -> None:
        """测试查询空字符串"""
        builder = BM25IndexBuilder()
        builder.build_index(self.test_nodes)
        with self.assertRaises(ValueError) as context:
            builder.query("")
        self.assertIn("必须提供query_str", str(context.exception))

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_query_without_build(self) -> None:
        """测试未构建索引时查询"""
        builder = BM25IndexBuilder()
        with self.assertRaises(BM25IndexError) as context:
            builder.query("储能技术")
        self.assertIn("索引未构建", str(context.exception))

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_query_with_filters(self) -> None:
        """测试带过滤器的查询"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        builder.build_index(self.test_nodes)

        # 查询特定文档的内容
        results = builder.query(
            "储能技术",
            top_k=10,
            filters={"document_id": "doc1"},
        )
        for result in results:
            if LLAMA_INDEX_AVAILABLE:
                doc_id = result.node.metadata.get("document_id")
            else:
                doc_id = result[0].metadata.get("document_id")
            self.assertEqual(doc_id, "doc1")

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_add_documents(self) -> None:
        """测试添加文档"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        builder.build_index(self.test_nodes[:2])  # 先构建2个节点

        # 添加新节点
        new_nodes = self.test_nodes[2:]
        original_count = len(builder._documents)
        builder.add_documents(new_nodes)

        # 验证添加结果
        self.assertEqual(len(builder._documents), original_count + len(new_nodes))
        self.assertIsNotNone(builder._bm25_index)

        # 验证文件已更新
        self.assertTrue(os.path.exists(self.index_path))

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_delete_documents_by_ids(self) -> None:
        """测试按ID删除文档"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        builder.build_index(self.test_nodes)

        # 删除指定ID的文档
        if LLAMA_INDEX_AVAILABLE:
            node_ids = [self.test_nodes[0].node_id, self.test_nodes[2].node_id]
        else:
            node_ids = ["node_0", "node_2"]
        
        deleted_count = builder.delete_documents(node_ids=node_ids)
        self.assertEqual(deleted_count, 2)
        self.assertEqual(len(builder._documents), len(self.test_nodes) - 2)

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_delete_documents_by_filters(self) -> None:
        """测试按过滤器删除文档"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        builder.build_index(self.test_nodes)

        # 删除特定文档的所有内容
        deleted_count = builder.delete_documents(
            filters={"document_id": "doc1"}
        )
        self.assertEqual(deleted_count, 2)  # doc1有2个节点
        self.assertEqual(len(builder._documents), len(self.test_nodes) - 2)

    def test_delete_documents_no_params(self) -> None:
        """测试删除文档时未提供参数"""
        builder = BM25IndexBuilder()
        with self.assertRaises(ValueError) as context:
            builder.delete_documents()
        self.assertIn("必须提供node_ids或filters", str(context.exception))

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_save_and_load_index(self) -> None:
        """测试保存和加载索引"""
        # 构建并保存索引
        builder1 = BM25IndexBuilder(index_path=self.index_path)
        builder1.build_index(self.test_nodes)
        original_stats = builder1.get_stats()

        # 创建新实例并加载索引
        builder2 = BM25IndexBuilder(index_path=self.index_path)
        loaded_stats = builder2.get_stats()

        # 验证加载的数据
        self.assertEqual(loaded_stats["documents_count"], original_stats["documents_count"])
        self.assertEqual(loaded_stats["vocab_size"], original_stats["vocab_size"])
        self.assertEqual(loaded_stats["avg_doc_length"], original_stats["avg_doc_length"])
        self.assertIsNotNone(builder2._bm25_index)

    def test_save_index_without_path(self) -> None:
        """测试不指定路径时保存索引"""
        builder = BM25IndexBuilder()  # 未指定路径
        if LLAMA_INDEX_AVAILABLE:
            builder.build_index(self.test_nodes)
        # 应该不抛出异常，只是不保存
        builder.save_index()  # 应该静默处理

    def test_load_index_without_path(self) -> None:
        """测试不指定路径时加载索引"""
        builder = BM25IndexBuilder()  # 未指定路径
        # 应该不抛出异常，只是不加载
        builder.load_index()  # 应该静默处理

    def test_load_nonexistent_index(self) -> None:
        """测试加载不存在的索引"""
        builder = BM25IndexBuilder(index_path="/nonexistent/path/index.pkl")
        # 应该不抛出异常，只是不加载
        builder.load_index()  # 应该静默处理

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_get_stats(self) -> None:
        """测试获取统计信息"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        builder.build_index(self.test_nodes)

        stats = builder.get_stats()
        self.assertEqual(stats["documents_count"], len(self.test_nodes))
        self.assertGreater(stats["vocab_size"], 0)
        self.assertGreater(stats["avg_doc_length"], 0)
        self.assertEqual(stats["index_path"], self.index_path)
        self.assertEqual(stats["k1"], 1.2)
        self.assertEqual(stats["b"], 0.75)
        self.assertEqual(stats["epsilon"], 0.25)
        self.assertTrue(stats["is_built"])

    def test_get_stats_empty_index(self) -> None:
        """测试空索引的统计信息"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        stats = builder.get_stats()
        self.assertEqual(stats["documents_count"], 0)
        self.assertEqual(stats["vocab_size"], 0)
        self.assertEqual(stats["avg_doc_length"], 0.0)
        self.assertEqual(stats["index_path"], self.index_path)
        self.assertEqual(stats["k1"], 1.2)
        self.assertEqual(stats["b"], 0.75)
        self.assertEqual(stats["epsilon"], 0.25)
        self.assertFalse(stats["is_built"])

    @patch("src.infrastructure.indexing.bm25_index.BM25_AVAILABLE", False)
    def test_init_without_bm25_library(self) -> None:
        """测试未安装rank-bm25库时的初始化"""
        with self.assertRaises(ImportError) as context:
            BM25IndexBuilder()
        self.assertIn("rank-bm25 is not available", str(context.exception))

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_integration_with_document_chunking(self) -> None:
        """测试与文档分块策略的集成"""
        from src.infrastructure.indexing.document_chunking import (
            DocumentChunkingStrategy,
            ChunkingConfig,
        )

        # 创建分块策略
        config = ChunkingConfig(chunk_size=100, chunk_overlap=20)
        chunking_strategy = DocumentChunkingStrategy(config)

        # 分块测试节点
        large_text = "储能技术是新能源领域的重要组成部分。" * 20  # 创建长文本
        large_node = TextNode(text=large_text, metadata={"document_id": "large_doc"})
        chunked_nodes = chunking_strategy.chunk_nodes([large_node])

        # 构建BM25索引
        builder = BM25IndexBuilder(index_path=self.index_path)
        builder.build_index(chunked_nodes)

        # 验证分块后的索引
        self.assertGreater(len(builder._documents), 1)  # 应该有多个分块
        self.assertIsNotNone(builder._bm25_index)

        # 查询测试
        results = builder.query("储能技术", top_k=5)
        self.assertGreater(len(results), 0)

    @unittest.skipUnless(LLAMA_INDEX_AVAILABLE, "LlamaIndex not available")
    def test_error_handling_in_build_index(self) -> None:
        """测试构建索引时的错误处理"""
        builder = BM25IndexBuilder(index_path=self.index_path)
        
        # 创建无效节点（没有text属性）
        invalid_nodes = [type("InvalidNode", (), {})]  # 创建没有text属性的节点
        
        with self.assertRaises(BM25IndexError):
            builder.build_index(invalid_nodes)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()