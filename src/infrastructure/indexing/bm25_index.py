# 生成命令: /speckit.implement T047
# 生成时间: 2025-12-20
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
BM25索引构建器实现 (T047)

该模块实现BM25索引构建功能,使用rank-bm25库实现BM25算法,
支持文档索引构建,查询,更新,删除等功能.

设计目标:
- 使用rank-bm25库实现BM25算法
- 支持从LlamaIndex Node对象构建BM25索引
- 集成T052文档分块策略,支持分块后的文档索引
- 支持元数据过滤和结构化查询(章节路径,文档层级等)
- 实现索引的持久化存储(使用JSON格式)
- 支持索引更新,删除,查询等完整功能
- 实现完善的错误处理和日志记录
"""

from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Any, cast

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
    BaseNode = Any  # type: ignore
    NodeWithScore = Any  # type: ignore
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

    使用rank-bm25库实现BM25算法,支持文档索引构建,查询,更新,删除等功能.
    索引数据可以持久化存储,支持增量更新.

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
            index_path: 索引文件路径,如果为None则不持久化
            k1: BM25参数k1,控制词频饱和度
            b: BM25参数b,控制文档长度归一化程度
            epsilon: BM25参数epsilon,用于IDF下界

        Raises:
            ImportError: 如果rank-bm25未安装
            BM25IndexError: 如果初始化失败
        """
        if not BM25_AVAILABLE:
            msg = (
                "rank-bm25 is not available. Please install rank-bm25 package to "
                "use BM25IndexBuilder."
            )
            raise ImportError(
                msg
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

        # 尝试加载现有索引（检查.pkl和.json格式）
        if self.index_path:
            json_path = self.index_path.replace('.pkl', '.json')
            pkl_exists = os.path.exists(self.index_path)
            json_exists = os.path.exists(json_path)

            logger.debug(
                "检查BM25索引文件: pkl_path=%s (存在=%s), json_path=%s (存在=%s)",
                self.index_path,
                pkl_exists,
                json_path,
                json_exists
            )

            # 如果.json文件存在，优先加载JSON格式
            if json_exists:
                try:
                    self.load_index()
                    if self._bm25_index is None:
                        logger.error(
                            "BM25索引文件存在但加载后索引为空: path=%s, documents_count=%d, document_texts_count=%d",
                            json_path,
                            len(self._documents),
                            len(self._document_texts)
                        )
                        raise BM25IndexError(
                            f"BM25索引文件存在但加载失败: path={json_path}, "
                            f"documents_count={len(self._documents)}, document_texts_count={len(self._document_texts)}"
                        )
                    else:
                        logger.info(
                            "BM25索引加载完成: path=%s, documents_count=%d, is_built=%s",
                            json_path,
                            len(self._documents),
                            self._bm25_index is not None
                        )
                except BM25IndexError:
                    raise
                except Exception as e:
                    logger.error(
                        "BM25索引加载失败: path=%s, error=%s",
                        json_path,
                        e,
                        exc_info=True
                    )
                    raise BM25IndexError(f"加载BM25索引失败: {e}") from e
            # 如果只有.pkl文件存在，尝试加载
            elif pkl_exists:
                try:
                    self.load_index()
                    if self._bm25_index is None:
                        raise BM25IndexError(
                            f"BM25索引(pkl格式)加载后为空: {self.index_path}"
                        )
                except BM25IndexError:
                    raise
                except Exception as e:
                    logger.error(
                        "BM25索引(pkl)加载失败: path=%s, error=%s",
                        self.index_path,
                        e,
                        exc_info=True
                    )
                    raise BM25IndexError(f"加载BM25索引失败: {e}") from e
            else:
                logger.debug(
                    "BM25索引文件不存在，将需要构建新索引: pkl=%s, json=%s",
                    self.index_path,
                    json_path
                )

    def _tokenize(self, text: str) -> list[str]:
        """
        文本分词

        使用改进的分词策略,支持中英文混合文本,并生成n-gram以提高匹配率.

        Args:
            text: 输入文本

        Returns:
            分词结果列表
        """
        # 简单的空格分词,可以根据需要替换为更复杂的分词器
        # 例如:jieba分词(中文)或nltk(英文)
        # 对于中文文本,我们需要更好的分词策略
        import re

        # 移除标点符号并分词
        # 支持中英文混合文本
        # 将非字母数字字符替换为空格
        text = re.sub(r"[^\w\s]", " ", text.lower())
        # 分词并过滤空字符串
        tokens = [token for token in text.split() if token.strip()]

        # 如果没有分出任何词,尝试按字符分词
        if not tokens and text:
            # 对于中文,按字符分词
            tokens = list(text.replace(" ", ""))

        # 对于中文文本,我们生成多种token以提高匹配率
        all_tokens = []
        for token in tokens:
            # 添加原始token
            all_tokens.append(token)

            # 如果token长度大于1且包含中文字符,则按字符分词
            if len(token) > 1 and any("\u4e00" <= char <= "\u9fff" for char in token):
                # 添加单个字符
                all_tokens.extend(list(token))

                # 添加2-gram和3-gram(连续的2个和3个字符)
                chars = list(token)
                for i in range(len(chars) - 1):
                    # 2-gram
                    all_tokens.append("".join(chars[i:i+2]))

                for i in range(len(chars) - 2):
                    # 3-gram
                    all_tokens.append("".join(chars[i:i+3]))

        return all_tokens

    def _calculate_stats(self) -> None:
        """
        计算索引统计信息

        计算词汇表大小和平均文档长度.
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

        从节点列表构建BM25索引.

        Args:
            nodes: LlamaIndex Node列表
            show_progress: 是否显示进度

        Raises:
            BM25IndexError: 如果构建索引失败
        """
        if not nodes:
            error_msg = "必须提供nodes"
            logger.error(f"BM25索引构建失败: {error_msg}")
            raise ValueError(error_msg)

        index_path = self.index_path or "None"
        logger.info(f"开始构建BM25索引: nodes_count={len(nodes)}, index_path={index_path}")

        try:
            # 重置索引数据
            self._documents = []
            self._document_texts = []
            self._metadata = []

            skipped_nodes = 0
            processed_nodes = 0

            # 处理每个节点
            for i, node in enumerate(nodes):
                # 获取节点文本
                text = getattr(node, "text", "")
                if not text or not str(text).strip():
                    logger.debug("跳过空文本节点: node_index=%s", i)
                    skipped_nodes += 1
                    continue

                # 获取元数据
                metadata = dict(getattr(node, "metadata", {}) or {})
                node_id = getattr(node, "id_", f"node_{i}")

                # 添加到索引数据
                self._documents.append(node)
                self._document_texts.append(str(text))
                self._metadata.append(metadata)
                processed_nodes += 1

                if show_progress and (i + 1) % 100 == 0:
                    logger.info("已处理 %s/%s 个节点", i + 1, len(nodes))

            logger.debug(
                f"BM25索引节点处理完成: total={len(nodes)}, processed={processed_nodes}, skipped={skipped_nodes}"
            )

            if processed_nodes == 0:
                error_msg = "没有有效的文档可以构建BM25索引（所有节点文本为空）"
                logger.error(f"BM25索引构建失败: {error_msg}")
                raise BM25IndexError(error_msg)

            # 构建BM25索引
            logger.debug(f"开始分词文档: documents_count={len(self._document_texts)}")
            tokenized_docs = [self._tokenize(doc) for doc in self._document_texts]

            logger.debug(
                f"分词完成: documents_count={len(tokenized_docs)}, "
                f"avg_tokens_per_doc={sum(len(d) for d in tokenized_docs) / len(tokenized_docs) if tokenized_docs else 0:.2f}"
            )

            self._bm25_index = BM25Okapi(
                corpus=tokenized_docs,
                k1=self.k1,
                b=self.b,
                epsilon=self.epsilon,
            )

            logger.debug("BM25Okapi索引对象创建完成")

            # 计算统计信息
            self._calculate_stats()

            # 持久化索引
            if self.index_path:
                logger.debug(f"开始保存BM25索引: index_path={self.index_path}")
                self.save_index()
                logger.info(f"BM25索引已保存: index_path={self.index_path}")
            else:
                logger.warning("BM25索引路径未设置，不会持久化")

            logger.info(
                "BM25索引构建完成: processed_nodes=%s, vocab_size=%s, avg_doc_length=%s, index_path=%s",
                processed_nodes,
                self._vocab_size,
                self._avg_doc_length,
                self.index_path or "None",
            )

        except BM25IndexError:
            raise
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
            查询结果列表(NodeWithScore对象)

        Raises:
            BM25IndexError: 如果查询失败
        """
        if not query_str:
            error_msg = "必须提供query_str"
            raise ValueError(error_msg)

        # Lazy-load: builder 可能早于索引文件生成/更新而初始化，导致 _bm25_index 为空。
        # 如果磁盘上已有索引文件，尽量在 query 时自动加载一次，避免上层流程因“未构建”而报错。
        if self._bm25_index is None and self.index_path:
            try:
                json_path = self.index_path.replace(".pkl", ".json")
                if os.path.exists(self.index_path) or os.path.exists(json_path):
                    logger.info(
                        "BM25索引未初始化，尝试在查询时加载索引: index_path=%s, json_path=%s",
                        self.index_path,
                        json_path,
                    )
                    self.load_index()
            except Exception as exc:
                # load_index 已会记录更详细日志；这里统一包装为 BM25IndexError
                raise BM25IndexError(f"查询前加载BM25索引失败: {exc}") from exc

        if self._bm25_index is None:
            error_msg = "索引未构建,请先调用build_index方法"
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
                # 如果有正分数,只返回正分数的结果;否则返回top_k个结果(即使分数为0)
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
                    # 如果LlamaIndex不可用,返回简单的元组
                    result = cast("NodeWithScore", (node, float(scores[doc_idx])))

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
            for i, (node, metadata) in enumerate(zip(self._documents, self._metadata, strict=True)):
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
        保存索引到文件（使用JSON格式）

        使用JSON格式保存索引数据，避免pickle的安全风险。
        将TextNode对象转换为可JSON序列化的字典格式。

        Raises:
            BM25IndexError: 如果保存失败
        """
        if not self.index_path:
            return

        try:
            # 确保目录存在
            index_dir = Path(self.index_path).parent
            if index_dir:
                index_dir.mkdir(parents=True, exist_ok=True)

            # 将节点转换为可JSON序列化的格式
            serialized_documents = []
            for node in self._documents:
                # 提取基本属性
                node_data = {
                    "text": getattr(node, "text", ""),
                    "metadata": dict(getattr(node, "metadata", {}) or {}),
                    "node_id": getattr(node, "node_id", None),
                }
                
                # 处理embedding向量（如果有）
                embedding = getattr(node, "embedding", None)
                if embedding is not None:
                    # 尝试转换为列表（支持numpy数组和list）
                    try:
                        node_data["embedding"] = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
                    except (TypeError, ValueError):
                        # 如果无法转换，保存为None
                        node_data["embedding"] = None
                else:
                    node_data["embedding"] = None
                
                serialized_documents.append(node_data)

            # 准备保存数据（JSON格式）
            save_data = {
                "documents": serialized_documents,
                "document_texts": self._document_texts,
                "metadata": self._metadata,
                "vocab_size": self._vocab_size,
                "avg_doc_length": self._avg_doc_length,
                "k1": self.k1,
                "b": self.b,
                "epsilon": self.epsilon,
                "format_version": "2.0",  # 标识新的JSON格式版本
            }

            # 保存到JSON文件
            json_path = self.index_path.replace('.pkl', '.json')
            with open(json_path, "w", encoding="utf-8") as f:
                import json
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            logger.info("BM25索引保存成功: path=%s, documents_count=%s", 
                       json_path, len(serialized_documents))

        except Exception as exc:
            error_msg = f"保存BM25索引失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise BM25IndexError(error_msg) from exc

    def load_index(self) -> None:
        """
        从JSON文件加载索引

        兼容旧格式（pickle）和新格式（JSON）。
        加载时重建TextNode对象。

        Raises:
            BM25IndexError: 如果加载失败
        """
        if not self.index_path:
            logger.debug("BM25索引路径未设置,跳过加载")
            return

        # 计算JSON格式的路径（优先使用新格式）
        json_path = self.index_path.replace('.pkl', '.json')

        # 确定要加载的文件路径
        json_path_to_load: str | None = None
        is_json_format = False

        if os.path.exists(json_path):
            # JSON格式存在
            json_path_to_load = json_path
            is_json_format = True
            logger.debug("找到BM25索引文件(JSON格式): %s", json_path)
        elif os.path.exists(self.index_path):
            # 旧pickle格式
            json_path_to_load = self.index_path
            is_json_format = False
            logger.debug("找到BM25索引文件(旧pickle格式): %s", self.index_path)
        else:
            # 索引文件不存在，这是正常情况（索引尚未构建）
            logger.debug("BM25索引文件不存在,跳过加载: pkl=%s, json=%s",
                        self.index_path, json_path)
            return

        # 检查文件是否为空
        file_size = Path(json_path_to_load).stat().st_size
        if file_size == 0:
            logger.warning("BM25索引文件为空,跳过加载: path=%s", json_path_to_load)
            return

        try:
            import json
            from llama_index.core.schema import TextNode

            save_data: dict[str, Any]

            if is_json_format:
                # 加载JSON格式
                with open(json_path_to_load, "r", encoding="utf-8") as f:
                    save_data = json.load(f)
            else:
                # 尝试加载旧pickle格式
                raw = Path(json_path_to_load).read_bytes()
                if raw[:1] == b"\x80":
                    # 旧pickle格式（不再支持，直接跳过）
                    logger.warning(
                        "BM25索引文件为旧版pickle格式,跳过加载: path=%s",
                        json_path_to_load
                    )
                    return
                else:
                    # 尝试作为JSON加载（兼容）
                    save_data = json.loads(raw.decode("utf-8"))

            # 恢复基本数据
            self._document_texts = save_data.get("document_texts", [])
            self._metadata = save_data.get("metadata", [])
            self._vocab_size = save_data.get("vocab_size", 0)
            self._avg_doc_length = save_data.get("avg_doc_length", 0.0)
            self.k1 = save_data.get("k1", self.k1)
            self.b = save_data.get("b", self.b)
            self.epsilon = save_data.get("epsilon", self.epsilon)

            # 重建TextNode对象
            self._documents = []
            serialized_docs = save_data.get("documents", [])

            for doc_data in serialized_docs:
                try:
                    # 创建TextNode
                    node = TextNode(
                        text=doc_data.get("text", ""),
                        metadata=doc_data.get("metadata", {}),
                    )

                    # 设置node_id
                    node_id = doc_data.get("node_id")
                    if node_id:
                        # TextNode的node_id是只读的，需要通过内部属性设置
                        object.__setattr__(node, 'node_id', node_id)

                    # 恢复embedding（如果有）
                    embedding = doc_data.get("embedding")
                    if embedding is not None:
                        try:
                            import numpy as np
                            embedding_array = np.array(embedding)
                            object.__setattr__(node, 'embedding', embedding_array)
                        except (TypeError, ValueError):
                            # 如果无法转换为numpy数组，忽略embedding
                            pass

                    self._documents.append(node)
                except Exception as e:
                    logger.warning(
                        "重建文档节点失败,跳过: doc_index=%s, error=%s",
                        len(self._documents),
                        str(e),
                    )
                    continue

            # 重建BM25索引
            if self._document_texts:
                try:
                    tokenized_docs = [self._tokenize(doc) for doc in self._document_texts]
                    self._bm25_index = BM25Okapi(
                        corpus=tokenized_docs,
                        k1=self.k1,
                        b=self.b,
                        epsilon=self.epsilon,
                    )
                    logger.info(
                        "BM25索引加载成功: path=%s, documents_count=%s, format=%s, vocab_size=%s",
                        json_path_to_load,
                        len(self._documents),
                        "JSON" if is_json_format else "legacy",
                        len(tokenized_docs[0]) if tokenized_docs else 0
                    )
                except Exception as build_exc:
                    logger.error(
                        "重建BM25索引对象失败: path=%s, documents_count=%d, document_texts_count=%d, error=%s",
                        json_path_to_load,
                        len(self._documents),
                        len(self._document_texts),
                        build_exc,
                        exc_info=True
                    )
                    # 即使重建失败，也保留已加载的数据，但_bm25_index为None
                    self._bm25_index = None
                    raise BM25IndexError(f"重建BM25索引对象失败: {build_exc}") from build_exc
            else:
                logger.warning(
                    "BM25索引加载后document_texts为空: path=%s, documents_count=%d",
                    json_path_to_load,
                    len(self._documents)
                )
                self._bm25_index = None
                # 如果document_texts为空，说明加载有问题，抛出异常
                raise BM25IndexError(
                    f"BM25索引加载后document_texts为空: path={json_path_to_load}, "
                    f"documents_count={len(self._documents)}"
                )

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
