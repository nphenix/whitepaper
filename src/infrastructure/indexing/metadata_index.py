"""
元数据索引构建器 (T048)

该模块实现基于SQLite的元数据索引构建器，用于对分块后的Node对象进行元数据索引。
支持元数据过滤和结构化查询，与T052文档分块策略集成。

设计目标:
- 使用SQLite存储元数据索引
- 支持从LlamaIndex Node对象构建索引
- 支持元数据过滤和结构化查询
- 集成T052文档分块策略
- 提供完整的索引管理功能（构建、查询、更新、删除）
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from src.shared.utils.logging import get_logger
from src.shared.exceptions.storage_exceptions import DataIntegrityError, QueryError, SQLiteError

try:
    from llama_index.core.schema import Node, TextNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 llama-index 时触发
    logger.warning(
        "LlamaIndex not available, metadata indexing with Node objects will be disabled"
    )
    Node = Any  # type: ignore[assignment]
    TextNode = Any  # type: ignore[assignment]
    LLAMA_INDEX_AVAILABLE = False

from ..storage.sqlite.adapter import SQLiteAdapter

logger = get_logger(__name__)


class MetadataIndexError(Exception):
    """元数据索引异常基类"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 简单字符串表示
        return f"元数据索引错误: {self.message}"


class MetadataIndexBuilder:
    """
    元数据索引构建器

    使用SQLite存储元数据索引，支持从LlamaIndex Node对象构建索引，
    提供元数据过滤和结构化查询功能。

    典型用法:
        >>> builder = MetadataIndexBuilder("document_chunks")
        >>> builder.build_index(nodes)
        >>> results = builder.query(filters={"section_path": "1.2"})
    """

    def __init__(
        self,
        table_name: str = "document_chunks_metadata",
        connection_manager=None,
    ) -> None:
        """
        初始化元数据索引构建器

        Args:
            table_name: 索引表名
            connection_manager: SQLite连接管理器，如果为None则使用默认实例
        """
        self.table_name = table_name
        self.adapter = SQLiteAdapter(table_name, connection_manager)
        self._initialized = False

        logger.debug(
            "初始化 %s: table=%s",
            self.__class__.__name__,
            table_name,
        )

    def _ensure_initialized(self) -> None:
        """确保索引表已初始化"""
        if not self._initialized:
            self._initialize_table()
            self._initialized = True

    def _initialize_table(self) -> None:
        """初始化索引表结构"""
        try:
            # 创建元数据索引表
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL UNIQUE,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_index_in_node INTEGER NOT NULL,
                original_node_index INTEGER NOT NULL,
                section_path TEXT,
                section_title TEXT,
                paragraph_index INTEGER,
                element_type TEXT,
                content_length INTEGER,
                source TEXT,
                format TEXT,
                pipeline TEXT,
                processed_at TEXT,
                total_pages INTEGER,
                metadata_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """

            # 创建索引以提高查询性能
            create_indexes_sql = [
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_node_id ON {self.table_name} (node_id)",
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_document_id ON {self.table_name} (document_id)",
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_section_path ON {self.table_name} (section_path)",
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_element_type ON {self.table_name} (element_type)",
                f"CREATE INDEX IF NOT EXISTS idx_{self.table_name}_chunk_index ON {self.table_name} (chunk_index)",
            ]

            # 执行表创建
            self.adapter.execute_custom_query(create_table_sql)

            # 执行索引创建
            for index_sql in create_indexes_sql:
                self.adapter.execute_custom_query(index_sql)

            logger.info(f"元数据索引表初始化完成: {self.table_name}")

        except Exception as e:
            error_msg = f"初始化元数据索引表失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def _extract_metadata_from_node(self, node: Node) -> Dict[str, Any]:
        """
        从LlamaIndex Node对象提取元数据

        Args:
            node: LlamaIndex Node对象

        Returns:
            提取的元数据字典
        """
        if not LLAMA_INDEX_AVAILABLE:
            raise MetadataIndexError("LlamaIndex不可用，无法处理Node对象")

        # 获取基础元数据
        metadata = dict(getattr(node, "metadata", {}) or {})

        # 提取核心字段
        extracted = {
            "node_id": getattr(node, "id_", ""),
            "document_id": metadata.get("document_id", ""),
            "chunk_index": metadata.get("chunk_index", 0),
            "chunk_index_in_node": metadata.get("chunk_index_in_node", 0),
            "original_node_index": metadata.get("original_node_index", 0),
            "section_path": metadata.get("section_path"),
            "section_title": metadata.get("section_title"),
            "paragraph_index": metadata.get("paragraph_index"),
            "element_type": metadata.get("element_type"),
            "content_length": len(getattr(node, "text", "")),
            "source": metadata.get("source"),
            "format": metadata.get("format"),
            "pipeline": metadata.get("pipeline"),
            "processed_at": metadata.get("processed_at"),
            "total_pages": metadata.get("total_pages"),
            "metadata_json": json.dumps(metadata, ensure_ascii=False),
        }

        return extracted

    def build_index(self, nodes: List[Node]) -> List[Dict[str, Any]]:
        """
        从LlamaIndex Node列表构建元数据索引

        Args:
            nodes: LlamaIndex Node对象列表

        Returns:
            构建的索引记录列表

        Raises:
            MetadataIndexError: 构建索引失败时抛出
        """
        self._ensure_initialized()

        if not nodes:
            logger.warning("空的Node列表，不构建索引")
            return []

        logger.info(f"开始构建元数据索引，节点数: {len(nodes)}")

        try:
            # 提取所有节点的元数据
            records = []
            for node in nodes:
                try:
                    record = self._extract_metadata_from_node(node)
                    records.append(record)
                except Exception as e:
                    node_id = getattr(node, "id_", "unknown")
                    logger.error(f"提取节点元数据失败: {node_id}, 错误: {e}")
                    continue

            if not records:
                logger.warning("没有有效的元数据记录，不构建索引")
                return []

            # 批量插入记录
            created_records = self.adapter.bulk_create(records)

            logger.info(
                f"元数据索引构建完成: 输入节点数={len(nodes)}, "
                f"成功记录数={len(created_records)}, 表名={self.table_name}"
            )

            return created_records

        except Exception as e:
            error_msg = f"构建元数据索引失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def query(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        查询元数据索引

        Args:
            filters: 过滤条件字典
            limit: 限制返回数量
            order_by: 排序字段

        Returns:
            查询结果列表

        Raises:
            MetadataIndexError: 查询失败时抛出
        """
        self._ensure_initialized()

        try:
            # 处理特殊过滤条件
            processed_filters = {}
            if filters:
                for key, value in filters.items():
                    # 处理JSON字段的查询
                    if key.startswith("metadata."):
                        # 将metadata.field格式的查询转换为JSON查询
                        json_field = key[9:]  # 去掉"metadata."前缀
                        processed_filters[f"metadata_json"] = f"%{json_field}%{value}%"
                    else:
                        processed_filters[key] = value

            records = self.adapter.list(
                filters=processed_filters, limit=limit, order_by=order_by
            )

            # 解析JSON元数据
            for record in records:
                if "metadata_json" in record and record["metadata_json"]:
                    try:
                        metadata = json.loads(record["metadata_json"])
                        record["metadata"] = metadata
                    except json.JSONDecodeError:
                        logger.warning(f"解析JSON元数据失败: {record.get('id')}")
                        record["metadata"] = {}

            logger.debug(f"元数据索引查询完成: 结果数={len(records)}")
            return records

        except Exception as e:
            error_msg = f"查询元数据索引失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def query_by_section_path(
        self, section_path: str, exact_match: bool = True
    ) -> List[Dict[str, Any]]:
        """
        按章节路径查询

        Args:
            section_path: 章节路径
            exact_match: 是否精确匹配，False时使用前缀匹配

        Returns:
            查询结果列表
        """
        if exact_match:
            filters = {"section_path": section_path}
        else:
            # 使用LIKE进行前缀匹配
            filters = {}  # 将在自定义查询中处理

        try:
            if exact_match:
                return self.query(filters=filters, order_by="chunk_index")
            else:
                # 自定义前缀查询
                query = f"""
                SELECT * FROM {self.table_name} 
                WHERE section_path LIKE ? 
                ORDER BY chunk_index
                """
                pattern = f"{section_path}%"
                results = self.adapter.execute_custom_query(
                    query, (pattern,), fetch_all=True
                )

                # 解析JSON元数据
                for record in results:
                    if "metadata_json" in record and record["metadata_json"]:
                        try:
                            metadata = json.loads(record["metadata_json"])
                            record["metadata"] = metadata
                        except json.JSONDecodeError:
                            logger.warning(f"解析JSON元数据失败: {record.get('id')}")
                            record["metadata"] = {}

                return results

        except Exception as e:
            error_msg = f"按章节路径查询失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def query_by_element_type(
        self, element_type: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        按元素类型查询

        Args:
            element_type: 元素类型
            limit: 限制返回数量

        Returns:
            查询结果列表
        """
        filters = {"element_type": element_type}
        return self.query(filters=filters, limit=limit, order_by="chunk_index")

    def query_by_document_id(
        self, document_id: str, order_by: str = "chunk_index"
    ) -> List[Dict[str, Any]]:
        """
        按文档ID查询

        Args:
            document_id: 文档ID
            order_by: 排序字段

        Returns:
            查询结果列表
        """
        filters = {"document_id": document_id}
        return self.query(filters=filters, order_by=order_by)

    def query_by_chunk_range(
        self, start_chunk: int, end_chunk: int, document_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        按块索引范围查询

        Args:
            start_chunk: 起始块索引
            end_chunk: 结束块索引
            document_id: 可选的文档ID过滤

        Returns:
            查询结果列表
        """
        filters = {
            "chunk_index >= ?": start_chunk,
            "chunk_index <= ?": end_chunk,
        }
        if document_id:
            filters["document_id"] = document_id

        # 构建自定义查询
        where_clauses = ["chunk_index >= ?", "chunk_index <= ?"]
        params = [start_chunk, end_chunk]

        if document_id:
            where_clauses.append("document_id = ?")
            params.append(document_id)

        query = f"""
        SELECT * FROM {self.table_name} 
        WHERE {' AND '.join(where_clauses)}
        ORDER BY chunk_index
        """

        try:
            results = self.adapter.execute_custom_query(
                query, tuple(params), fetch_all=True
            )

            # 解析JSON元数据
            for record in results:
                if "metadata_json" in record and record["metadata_json"]:
                    try:
                        metadata = json.loads(record["metadata_json"])
                        record["metadata"] = metadata
                    except json.JSONDecodeError:
                        logger.warning(f"解析JSON元数据失败: {record.get('id')}")
                        record["metadata"] = {}

            return results

        except Exception as e:
            error_msg = f"按块范围查询失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def get_by_node_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        根据节点ID获取记录

        Args:
            node_id: 节点ID

        Returns:
            记录字典，如果不存在则返回None
        """
        record = self.adapter.get_by_id(node_id)
        if record and "metadata_json" in record and record["metadata_json"]:
            try:
                metadata = json.loads(record["metadata_json"])
                record["metadata"] = metadata
            except json.JSONDecodeError:
                logger.warning(f"解析JSON元数据失败: {record.get('id')}")
                record["metadata"] = {}

        return record

    def update_metadata(
        self, node_id: str, metadata_updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        更新节点的元数据

        Args:
            node_id: 节点ID
            metadata_updates: 要更新的元数据

        Returns:
            更新后的记录，如果不存在则返回None
        """
        # 获取现有记录
        existing_record = self.get_by_node_id(node_id)
        if not existing_record:
            logger.warning(f"节点不存在，无法更新元数据: {node_id}")
            return None

        try:
            # 解析现有元数据
            existing_metadata = existing_record.get("metadata", {})
            if isinstance(existing_metadata, str):
                existing_metadata = json.loads(existing_metadata)

            # 更新元数据
            updated_metadata = {**existing_metadata, **metadata_updates}

            # 准备更新数据
            update_data = {
                "metadata_json": json.dumps(updated_metadata, ensure_ascii=False),
                "updated_at": datetime.utcnow().isoformat(),
            }

            # 更新特定字段
            if "section_path" in metadata_updates:
                update_data["section_path"] = metadata_updates["section_path"]
            if "section_title" in metadata_updates:
                update_data["section_title"] = metadata_updates["section_title"]
            if "element_type" in metadata_updates:
                update_data["element_type"] = metadata_updates["element_type"]

            # 执行更新
            updated_record = self.adapter.update(node_id, update_data)

            if updated_record:
                # 解析JSON元数据
                if "metadata_json" in updated_record and updated_record["metadata_json"]:
                    try:
                        metadata = json.loads(updated_record["metadata_json"])
                        updated_record["metadata"] = metadata
                    except json.JSONDecodeError:
                        logger.warning(f"解析JSON元数据失败: {updated_record.get('id')}")
                        updated_record["metadata"] = {}

            logger.info(f"节点元数据更新成功: {node_id}")
            return updated_record

        except Exception as e:
            error_msg = f"更新节点元数据失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def delete_by_node_id(self, node_id: str) -> bool:
        """
        根据节点ID删除记录

        Args:
            node_id: 节点ID

        Returns:
            是否删除成功
        """
        try:
            success = self.adapter.delete(node_id)
            if success:
                logger.info(f"节点记录删除成功: {node_id}")
            else:
                logger.warning(f"节点记录删除失败或不存在: {node_id}")
            return success
        except Exception as e:
            error_msg = f"删除节点记录失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def delete_by_document_id(self, document_id: str) -> int:
        """
        根据文档ID删除所有相关记录

        Args:
            document_id: 文档ID

        Returns:
            删除的记录数
        """
        try:
            query = f"DELETE FROM {self.table_name} WHERE document_id = ?"
            with self.adapter.connection_manager.transaction() as cursor:
                cursor.execute(query, (document_id,))
                deleted_count = cursor.rowcount

            logger.info(f"文档记录删除成功: {document_id}, 删除数量: {deleted_count}")
            return deleted_count

        except Exception as e:
            error_msg = f"删除文档记录失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def get_stats(self) -> Dict[str, Any]:
        """
        获取索引统计信息

        Returns:
            统计信息字典
        """
        try:
            # 基本统计
            table_info = self.adapter.get_table_info()
            stats = {
                "table_name": self.table_name,
                "total_records": table_info.get("record_count", 0),
                "columns": table_info.get("columns", []),
            }

            # 按文档统计
            doc_count_query = f"""
            SELECT document_id, COUNT(*) as count 
            FROM {self.table_name} 
            GROUP BY document_id
            """
            doc_counts = self.adapter.execute_custom_query(
                doc_count_query, fetch_all=True
            )
            stats["documents"] = doc_counts

            # 按章节路径统计
            section_count_query = f"""
            SELECT section_path, COUNT(*) as count 
            FROM {self.table_name} 
            WHERE section_path IS NOT NULL
            GROUP BY section_path
            ORDER BY count DESC
            LIMIT 10
            """
            section_counts = self.adapter.execute_custom_query(
                section_count_query, fetch_all=True
            )
            stats["top_sections"] = section_counts

            # 按元素类型统计
            element_count_query = f"""
            SELECT element_type, COUNT(*) as count 
            FROM {self.table_name} 
            WHERE element_type IS NOT NULL
            GROUP BY element_type
            ORDER BY count DESC
            """
            element_counts = self.adapter.execute_custom_query(
                element_count_query, fetch_all=True
            )
            stats["element_types"] = element_counts

            return stats

        except Exception as e:
            error_msg = f"获取索引统计信息失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def rebuild_index(self, nodes: List[Node]) -> List[Dict[str, Any]]:
        """
        重建索引（先删除现有数据，再构建新索引）

        Args:
            nodes: LlamaIndex Node对象列表

        Returns:
            构建的索引记录列表
        """
        self._ensure_initialized()

        try:
            # 删除现有表
            drop_table_sql = f"DROP TABLE IF EXISTS {self.table_name}"
            self.adapter.execute_custom_query(drop_table_sql)

            # 重新初始化表
            self._initialized = False
            self._ensure_initialized()

            # 构建新索引
            return self.build_index(nodes)

        except Exception as e:
            error_msg = f"重建索引失败: {e}"
            logger.error(error_msg)
            raise MetadataIndexError(error_msg) from e

    def create_adapter(
        table_name: str,
        connection_manager=None,
        **kwargs,
    ) -> "MetadataIndexBuilder":
        """
        创建元数据索引构建器实例

        Args:
            table_name: 表名
            connection_manager: 连接管理器
            **kwargs: 其他参数

        Returns:
            MetadataIndexBuilder: 构建器实例
        """
        return MetadataIndexBuilder(
            table_name=table_name,
            connection_manager=connection_manager,
            **kwargs,
        )