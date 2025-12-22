# 生成命令: /speckit.implement T047
# 生成时间: 2025-12-20
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
BM25索引构建器实现 (T047)

该模块实现BM25索引构建功能，使用rank-bm25库实现BM25算法，
支持文档索引构建、查询、更新、删除等功能。

设计目标:
- 使用rank-bm25库实现BM25算法
- 支持从LlamaIndex Node对象构建BM25索引
- 集成T052文档分块策略，支持分块后的文档索引
- 支持元数据过滤和结构化查询（章节路径、文档层级等）
- 实现索引的持久化存储（使用JSON格式）
- 支持索引更新、删除、查询等完整功能
- 实现完善的错误处理和日志记录
"""

from __future__ import annotations

import json
import math
import os
import pickle
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, cast

from src.shared.exceptions.storage_exceptions import StorageError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 rank-bm25 时触发
    logger.warning(
        "rank-bm25 not available, BM25 index builder will be disabled"
    )
    BM25_AVAILABLE = False

try:
    from llama_index.core.schema import BaseNode, NodeWithScore
    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 llama-index 时触发
    logger.warning(
        "LlamaIndex not available, BM25 index builder will have limited functionality"
    )
    BaseNode = Any  # type: ignore[assignment, misc]
    NodeWithScore = Any  # type: ignore[assignment, misc]
    LLAMA_INDEX_AVAILABLE = False


class BM25IndexError(Exception):
    """BM25索引异常基类"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 简单字符串表示
        return f"BM25索引错误: {self.message}"


class BM25IndexBuilder:
    """
    BM25索引构建器

    使用rank-bm25库实现BM25算法，支持文档索引构建、查询、更新、删除等功能。
    索引数据可以持久化存储，支持增量更新。

    典型用法:
        >>> builder = BM25IndexBuilder(index_path="./data/bm25_index.pkl")
        >>> nodes = [TextNode(text="示例文本", metadata={"section_path": "1.2"})]
        >>> builder.build_index(nodes)
        >>> results = builder.query(query="查询文本", top_k=5)
    """

    def __init__(
        self,
        index_path: str | None = None,
        k1: float = 1.2,
        b: float = 0.75,
        epsilon: float = 0.25,
    ) -> None:
        """
        初始化BM25索引构建器

        Args:
            index_path: 索引文件路径，如果为None则不持久化
            k1: BM25参数k1，控制词频饱和度
            b: BM25参数b，控制文档长度归一化程度
            epsilon: BM25参数epsilon，用于IDF下界

        Raises:
            ImportError: 如果rank-bm25未安装
            BM25IndexError: 如果初始化失败
        """
        if not BM25_AVAILABLE:
            raise ImportError(
                "rank-bm25 is not available. Please install rank-bm25 package to "
                "use BM25IndexBuilder."
            )

        self.index_path = index_path
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon

        # 索引数据
        self._bm25_index: BM25Okapi | None = None
        self._documents: list[BaseNode] = []
        self._document_texts: list[str] = []
        self._metadata: list[dict[str, Any]] = []

        # 统计信息
        self._vocab_size = 0
        self._avg_doc_length = 0.0

        logger.info(
            "初始化 BM25IndexBuilder: index_path=%s, k1=%s, b=%s, epsilon=%s",
            self.index_path,
            self.k1,
            self.b,
            self.epsilon,
        )

        # 尝试加载现有索引
        if self.index_path and os.path.exists(self.index_path):
            self.load_index()

    def _tokenize(self, text: str) -> list[str]:
        """
        文本分词

        使用改进的分词策略，支持中英文混合文本，并生成n-gram以提高匹配率。

        Args:
            text: 输入文本

        Returns:
            分词结果列表
        """
        # 简单的空格分词，可以根据需要替换为更复杂的分词器
        # 例如：jieba分词（中文）或nltk（英文）
        # 对于中文文本，我们需要更好的分词策略
        import re
        
        # 移除标点符号并分词
        # 支持中英文混合文本
        # 将非字母数字字符替换为空格
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        # 分词并过滤空字符串
        tokens = [token for token in text.split() if token.strip()]
        
        # 如果没有分出任何词，尝试按字符分词
        if not tokens and text:
            # 对于中文，按字符分词
            tokens = list(text.replace(' ', ''))
        
        # 对于中文文本，我们生成多种token以提高匹配率
        all_tokens = []
        for token in tokens:
            # 添加原始token
            all_tokens.append(token)
            
            # 如果token长度大于1且包含中文字符，则按字符分词
            if len(token) > 1 and any('\u4e00' <= char <= '\u9fff' for char in token):
                # 添加单个字符
                all_tokens.extend(list(token))
                
                # 添加2-gram和3-gram（连续的2个和3个字符）
                chars = list(token)
                for i in range(len(chars) - 1):
                    # 2-gram
                    all_tokens.append(''.join(chars[i:i+2]))
                    
                for i in range(len(chars) - 2):
                    # 3-gram
                    all_tokens.append(''.join(chars[i:i+3]))
        
        return all_tokens

    def _calculate_stats(self) -> None:
        """
        计算索引统计信息

        计算词汇表大小和平均文档长度。
        """
        if not self._document_texts:
            self._vocab_size = 0
            self._avg_doc_length = 0.0
            return

        # 计算词汇表大小
        all_tokens = []
        for doc_text in self._document_texts:
            tokens = self._tokenize(doc_text)
            all_tokens.extend(tokens)

        self._vocab_size = len(set(all_tokens))

        # 计算平均文档长度
        doc_lengths = [len(self._tokenize(doc)) for doc in self._document_texts]
        self._avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0

        logger.debug(
            "计算索引统计信息: vocab_size=%s, avg_doc_length=%s",
            self._vocab_size,
            self._avg_doc_length,
        )

    def build_index(
        self,
        nodes: list[BaseNode],
        show_progress: bool = False,
    ) -> None:
        """
        构建BM25索引

        从节点列表构建BM25索引。

        Args:
            nodes: LlamaIndex Node列表
            show_progress: 是否显示进度

        Raises:
            BM25IndexError: 如果构建索引失败
        """
        if not nodes:
            error_msg = "必须提供nodes"
            raise ValueError(error_msg)

        try:
            logger.info("开始构建BM25索引: nodes_count=%s", len(nodes))

            # 重置索引数据
            self._documents = []
            self._document_texts = []
            self._metadata = []

            # 处理每个节点
            for i, node in enumerate(nodes):
                # 获取节点文本
                text = getattr(node, "text", "")
                if not text or not str(text).strip():
                    logger.debug("跳过空文本节点: node_index=%s", i)
                    continue

                # 获取元数据
                metadata = dict(getattr(node, "metadata", {}) or {})

                # 添加到索引数据
                self._documents.append(node)
                self._document_texts.append(str(text))
                self._metadata.append(metadata)

                if show_progress and (i + 1) % 100 == 0:
                    logger.info("已处理 %s/%s 个节点", i + 1, len(nodes))

            # 构建BM25索引
            tokenized_docs = [self._tokenize(doc) for doc in self._document_texts]
            self._bm25_index = BM25Okapi(
                corpus=tokenized_docs,
                k1=self.k1,
                b=self.b,
                epsilon=self.epsilon,
            )

            # 计算统计信息
            self._calculate_stats()

            # 持久化索引
            if self.index_path:
                self.save_index()

            logger.info(
                "BM25索引构建完成: nodes_count=%s, vocab_size=%s, avg_doc_length=%s",
                len(self._documents),
                self._vocab_size,
                self._avg_doc_length,
            )

        except Exception as exc:
            error_msg = f"构建BM25索引失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise BM25IndexError(error_msg) from exc

    def query(
        self,
        query_str: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[NodeWithScore]:
        """
        查询BM25索引

        Args:
            query_str: 查询文本
            top_k: 返回结果数量
            filters: 元数据过滤器

        Returns:
            查询结果列表（NodeWithScore对象）

        Raises:
            BM25IndexError: 如果查询失败
        """
        if not query_str:
            error_msg = "必须提供query_str"
            raise ValueError(error_msg)

        if self._bm25_index is None:
            error_msg = "索引未构建，请先调用build_index方法"
            raise BM25IndexError(error_msg)

        try:
            # 分词查询
            query_tokens = self._tokenize(query_str)

            # 执行BM25查询
            scores = self._bm25_index.get_scores(query_tokens)
            doc_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

            # 构建结果
            results: list[NodeWithScore] = []
            # 检查是否有正分数
            has_positive_scores = any(scores[i] > 0 for i in doc_indices[:top_k])
            
            for doc_idx in doc_indices[:top_k]:
                # 如果有正分数，只返回正分数的结果；否则返回top_k个结果（即使分数为0）
                if has_positive_scores and scores[doc_idx] <= 0:
                    break

                node = self._documents[doc_idx]
                metadata = self._metadata[doc_idx]

                # 应用元数据过滤器
                if filters:
                    match = True
                    for key, value in filters.items():
                        if metadata.get(key) != value:
                            match = False
                            break
                    if not match:
                        continue

                # 创建NodeWithScore对象
                if LLAMA_INDEX_AVAILABLE:
                    result = NodeWithScore(
                        node=node,
                        score=float(scores[doc_idx]),
                    )
                else:
                    # 如果LlamaIndex不可用，返回简单的元组
                    result = cast(NodeWithScore, (node, float(scores[doc_idx])))

                results.append(result)

            logger.info(
                "查询BM25索引成功: query=%s, results_count=%s",
                query_str[:50] if query_str else "",
                len(results),
            )

            return results

        except Exception as exc:
            error_msg = f"查询BM25索引失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise BM25IndexError(error_msg) from exc

    def add_documents(
        self,
        nodes: list[BaseNode],
    ) -> None:
        """
        向索引中添加文档

        Args:
            nodes: 要添加的节点列表

        Raises:
            BM25IndexError: 如果添加失败
        """
        if not nodes:
            return

        try:
            logger.info("向BM25索引添加文档: nodes_count=%s", len(nodes))

            # 处理每个节点
            for node in nodes:
                # 获取节点文本
                text = getattr(node, "text", "")
                if not text or not str(text).strip():
                    continue

                # 获取元数据
                metadata = dict(getattr(node, "metadata", {}) or {})

                # 添加到索引数据
                self._documents.append(node)
                self._document_texts.append(str(text))
                self._metadata.append(metadata)

            # 重建索引
            tokenized_docs = [self._tokenize(doc) for doc in self._document_texts]
            self._bm25_index = BM25Okapi(
                corpus=tokenized_docs,
                k1=self.k1,
                b=self.b,
                epsilon=self.epsilon,
            )

            # 重新计算统计信息
            self._calculate_stats()

            # 持久化索引
            if self.index_path:
                self.save_index()

            logger.info(
                "向BM25索引添加文档完成: total_nodes=%s, new_nodes=%s",
                len(self._documents),
                len(nodes),
            )

        except Exception as exc:
            error_msg = f"向BM25索引添加文档失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise BM25IndexError(error_msg) from exc

    def delete_documents(
        self,
        node_ids: list[str] | None = None,
        filters: dict[str, Any] | None = None,
    ) -> int:
        """
        从索引中删除文档

        Args:
            node_ids: 节点ID列表
            filters: 元数据过滤器

        Returns:
            删除的文档数量

        Raises:
            BM25IndexError: 如果删除失败
        """
        if not node_ids and not filters:
            error_msg = "必须提供node_ids或filters"
            raise ValueError(error_msg)

        try:
            logger.info(
                "从BM25索引删除文档: node_ids_count=%s, has_filters=%s",
                len(node_ids) if node_ids else 0,
                filters is not None,
            )

            # 找出要删除的文档索引
            to_delete_indices = []
            for i, (node, metadata) in enumerate(zip(self._documents, self._metadata)):
                should_delete = False

                # 按节点ID删除
                if node_ids:
                    node_id = getattr(node, "node_id", None)
                    if node_id and str(node_id) in node_ids:
                        should_delete = True

                # 按元数据过滤器删除
                if filters and not should_delete:
                    match = True
                    for key, value in filters.items():
                        if metadata.get(key) != value:
                            match = False
                            break
                    if match:
                        should_delete = True

                if should_delete:
                    to_delete_indices.append(i)

            # 删除文档
            for i in reversed(to_delete_indices):  # 从后往前删除
                del self._documents[i]
                del self._document_texts[i]
                del self._metadata[i]

            # 重建索引
            if self._document_texts:
                tokenized_docs = [self._tokenize(doc) for doc in self._document_texts]
                self._bm25_index = BM25Okapi(
                    corpus=tokenized_docs,
                    k1=self.k1,
                    b=self.b,
                    epsilon=self.epsilon,
                )
            else:
                self._bm25_index = None

            # 重新计算统计信息
            self._calculate_stats()

            # 持久化索引
            if self.index_path:
                self.save_index()

            logger.info(
                "从BM25索引删除文档完成: deleted_count=%s, remaining_count=%s",
                len(to_delete_indices),
                len(self._documents),
            )

            return len(to_delete_indices)

        except Exception as exc:
            error_msg = f"从BM25索引删除文档失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise BM25IndexError(error_msg) from exc

    def save_index(self) -> None:
        """
        保存索引到文件

        Raises:
            BM25IndexError: 如果保存失败
        """
        if not self.index_path:
            return

        try:
            # 确保目录存在
            index_dir = os.path.dirname(self.index_path)
            if index_dir:
                os.makedirs(index_dir, exist_ok=True)

            # 准备保存数据
            save_data = {
                "documents": self._documents,
                "document_texts": self._document_texts,
                "metadata": self._metadata,
                "vocab_size": self._vocab_size,
                "avg_doc_length": self._avg_doc_length,
                "k1": self.k1,
                "b": self.b,
                "epsilon": self.epsilon,
            }

            # 保存到文件
            with open(self.index_path, "wb") as f:
                pickle.dump(save_data, f)

            logger.info("BM25索引保存成功: path=%s", self.index_path)

        except Exception as exc:
            error_msg = f"保存BM25索引失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise BM25IndexError(error_msg) from exc

    def load_index(self) -> None:
        """
        从文件加载索引

        Raises:
            BM25IndexError: 如果加载失败
        """
        if not self.index_path or not os.path.exists(self.index_path):
            return

        try:
            # 检查文件是否为空
            if os.path.getsize(self.index_path) == 0:
                logger.warning("BM25索引文件为空，跳过加载: path=%s", self.index_path)
                return

            # 从文件加载数据
            with open(self.index_path, "rb") as f:
                try:
                    save_data = pickle.load(f)
                except (EOFError, pickle.UnpicklingError) as e:
                    # 文件损坏或为空，记录警告并跳过加载
                    logger.warning(
                        "BM25索引文件损坏或格式不正确，跳过加载: path=%s, error=%s",
                        self.index_path,
                        str(e),
                    )
                    return

            # 恢复数据
            self._documents = save_data.get("documents", [])
            self._document_texts = save_data.get("document_texts", [])
            self._metadata = save_data.get("metadata", [])
            self._vocab_size = save_data.get("vocab_size", 0)
            self._avg_doc_length = save_data.get("avg_doc_length", 0.0)
            self.k1 = save_data.get("k1", self.k1)
            self.b = save_data.get("b", self.b)
            self.epsilon = save_data.get("epsilon", self.epsilon)

            # 重建BM25索引
            if self._document_texts:
                tokenized_docs = [self._tokenize(doc) for doc in self._document_texts]
                self._bm25_index = BM25Okapi(
                    corpus=tokenized_docs,
                    k1=self.k1,
                    b=self.b,
                    epsilon=self.epsilon,
                )
            else:
                self._bm25_index = None

            logger.info("BM25索引加载成功: path=%s, documents_count=%s", self.index_path, len(self._documents))

        except Exception as exc:
            error_msg = f"加载BM25索引失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise BM25IndexError(error_msg) from exc

    def get_stats(self) -> dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            统计信息字典
        """
        return {
            "documents_count": len(self._documents),
            "vocab_size": self._vocab_size,
            "avg_doc_length": self._avg_doc_length,
            "index_path": self.index_path,
            "k1": self.k1,
            "b": self.b,
            "epsilon": self.epsilon,
            "is_built": self._bm25_index is not None,
        }