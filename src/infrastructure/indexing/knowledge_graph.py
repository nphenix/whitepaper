# 生成命令: T049 知识图谱构建器
# 生成时间: 2025-12-20
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
知识图谱构建器实现 (T049)

该模块实现知识图谱构建功能，使用LLM进行实体关系提取，并将结果存储到NetworkX图数据库中。

设计目标:
- 使用LLM进行实体和关系提取（必须从T009创建的llm_service获取模型实例）
- 集成NetworkX适配器（T014）存储知识图谱
- 从LlamaIndex Node对象中提取实体和关系
- 支持实体消歧和合并
- 支持通用实体类型和储能产业特定实体类型
- 实现完善的错误处理和日志记录

参考LlamaIndex最佳实践:
- 使用结构化输出（Pydantic模型）确保提取结果格式一致
- 支持批量处理和异步处理
- 遵循LlamaIndex知识图谱提取模式
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from src.infrastructure.storage.networkx.adapter import NetworkXAdapter
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.schema import BaseNode, Node
    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover - 仅在未安装 llama-index 时触发
    logger.warning(
        "LlamaIndex not available, knowledge graph builder will be disabled"
    )
    BaseNode = Any  # type: ignore[assignment, misc]
    Node = Any  # type: ignore[assignment, misc]
    LLAMA_INDEX_AVAILABLE = False


class KnowledgeGraphError(Exception):
    """知识图谱异常基类"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:  # pragma: no cover - 简单字符串表示
        return f"知识图谱错误: {self.message}"


class EntityType(str, Enum):
    """实体类型枚举"""

    # 通用类型
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    CONCEPT = "CONCEPT"
    EVENT = "EVENT"
    LOCATION = "LOCATION"
    TIME = "TIME"
    OTHER = "OTHER"

    # 储能产业特定类型
    ENERGY_STORAGE_TECHNOLOGY = "ENERGY_STORAGE_TECHNOLOGY"
    ENERGY_STORAGE_DEVICE = "ENERGY_STORAGE_DEVICE"
    ENERGY_STORAGE_COMPONENT = "ENERGY_STORAGE_COMPONENT"
    ENERGY_STORAGE_APPLICATION = "ENERGY_STORAGE_APPLICATION"
    ENERGY_STORAGE_PROJECT = "ENERGY_STORAGE_PROJECT"
    ENERGY_STORAGE_STANDARD = "ENERGY_STORAGE_STANDARD"
    ENERGY_STORAGE_POLICY = "ENERGY_STORAGE_POLICY"
    ENERGY_STORAGE_MARKET = "ENERGY_STORAGE_MARKET"
    ENERGY_STORAGE_MATERIAL = "ENERGY_STORAGE_MATERIAL"
    ENERGY_STORAGE_MANUFACTURER = "ENERGY_STORAGE_MANUFACTURER"
    ENERGY_STORAGE_RESEARCH = "ENERGY_STORAGE_RESEARCH"


class RelationType(str, Enum):
    """关系类型枚举（通用关系）"""

    PART_OF = "PART_OF"
    HAS = "HAS"
    IS_A = "IS_A"
    RELATED_TO = "RELATED_TO"
    LOCATED_IN = "LOCATED_IN"
    OCCURS_AT = "OCCURS_AT"
    WORKS_FOR = "WORKS_FOR"
    WORKS_WITH = "WORKS_WITH"
    WORKS_ON = "WORKS_ON"
    MEMBER_OF = "MEMBER_OF"
    OWNS = "OWNS"
    USES = "USES"
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    IMPLEMENTS = "IMPLEMENTS"
    COMPLIES_WITH = "COMPLIES_WITH"
    OTHER = "OTHER"


@dataclass
class ExtractedEntity:
    """提取的实体"""

    name: str
    entity_type: EntityType | str
    description: str | None = None
    aliases: list[str] | None = None
    properties: dict[str, Any] | None = None
    confidence: float = 1.0


@dataclass
class ExtractedRelation:
    """提取的关系"""

    source_entity: str
    target_entity: str
    relation_type: RelationType | str
    description: str | None = None
    confidence: float = 1.0


class EntityExtractionResult(BaseModel):
    """实体提取结果（结构化输出）"""

    entities: list[dict[str, Any]] = Field(
        description="提取的实体列表，每个实体包含name、type、description等字段"
    )


class RelationExtractionResult(BaseModel):
    """关系提取结果（结构化输出）"""

    relations: list[dict[str, Any]] = Field(
        description="提取的关系列表，每个关系包含source、target、relation、description等字段"
    )


class KnowledgeGraphBuilder:
    """
    知识图谱构建器

    使用LLM从LlamaIndex Node对象中提取实体和关系，并将结果存储到NetworkX图数据库中。

    典型用法:
        >>> builder = KnowledgeGraphBuilder(graph_name="knowledge_graph")
        >>> nodes = [TextNode(text="示例文本", metadata={"section_path": "1.2"})]
        >>> builder.build_from_nodes(nodes)
        >>> entities = builder.get_entities_by_type(EntityType.PERSON)
    """

    def __init__(
        self,
        graph_name: str = "knowledge_graph",
        graph_adapter: NetworkXAdapter | None = None,
        llm_service: LLMService | None = None,
        max_entities_per_chunk: int = 10,
        max_relations_per_chunk: int = 10,
    ) -> None:
        """
        初始化知识图谱构建器

        Args:
            graph_name: 图名称，用于标识不同的知识图谱
            graph_adapter: NetworkX适配器，如果为None则创建新实例
            llm_service: LLM服务，如果为None则使用全局实例
            max_entities_per_chunk: 每个块最多提取的实体数量
            max_relations_per_chunk: 每个块最多提取的关系数量
        """
        if not LLAMA_INDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not available. Please install llama-index package to "
                "use KnowledgeGraphBuilder."
            )

        self.graph_name = graph_name
        self.graph_adapter = graph_adapter or NetworkXAdapter(
            graph_name=graph_name,
            graph_type="DiGraph",
        )
        self.llm_service = llm_service or get_llm_service()
        self.max_entities_per_chunk = max_entities_per_chunk
        self.max_relations_per_chunk = max_relations_per_chunk

        # 实体名称到节点ID的映射（用于实体消歧）
        self._entity_name_to_id: dict[str, str] = {}

        logger.debug(
            "初始化 %s: graph_name=%s, max_entities=%s, max_relations=%s",
            self.__class__.__name__,
            graph_name,
            max_entities_per_chunk,
            max_relations_per_chunk,
        )

    def build_from_nodes(
        self,
        nodes: list[BaseNode],
        show_progress: bool = False,
    ) -> dict[str, Any]:
        """
        从LlamaIndex Node列表构建知识图谱

        Args:
            nodes: LlamaIndex Node列表
            show_progress: 是否显示进度

        Returns:
            构建统计信息字典，包含实体数量、关系数量等
        """
        if not nodes:
            logger.warning("空的 Node 列表, 不执行知识图谱构建")
            return {
                "entities_count": 0,
                "relations_count": 0,
                "nodes_processed": 0,
            }

        total_entities = 0
        total_relations = 0
        nodes_processed = 0

        for node in nodes:
            try:
                # 提取实体和关系
                entities, relations = self._extract_from_node(node)

                # 添加到图数据库
                for entity in entities:
                    self._add_entity_to_graph(entity, node)
                    total_entities += 1

                for relation in relations:
                    self._add_relation_to_graph(relation, node)
                    total_relations += 1

                nodes_processed += 1

            except Exception as exc:
                logger.error(
                    "处理节点失败: node_id=%s, error=%s",
                    getattr(node, "node_id", "unknown"),
                    exc,
                    exc_info=True,
                )
                continue

        logger.info(
            "知识图谱构建完成: graph_name=%s, nodes_processed=%s, "
            "entities=%s, relations=%s",
            self.graph_name,
            nodes_processed,
            total_entities,
            total_relations,
        )

        return {
            "entities_count": total_entities,
            "relations_count": total_relations,
            "nodes_processed": nodes_processed,
        }

    def _extract_from_node(
        self,
        node: BaseNode,
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        """
        从单个Node中提取实体和关系

        Args:
            node: LlamaIndex Node对象

        Returns:
            (实体列表, 关系列表) 元组
        """
        # 获取节点文本内容
        text = getattr(node, "text", None)
        if not text or not str(text).strip():
            logger.debug("节点文本为空, 跳过提取")
            return [], []

        text_content = str(text).strip()

        # 使用LLM提取实体和关系
        try:
            entities = self._extract_entities(text_content, node)
            relations = self._extract_relations(text_content, node, entities)
        except Exception as exc:
            logger.error(
                "LLM提取失败: node_id=%s, error=%s",
                getattr(node, "node_id", "unknown"),
                exc,
                exc_info=True,
            )
            return [], []

        return entities, relations

    def _extract_entities(
        self,
        text: str,
        node: BaseNode,
    ) -> list[ExtractedEntity]:
        """
        使用LLM提取实体

        Args:
            text: 文本内容
            node: LlamaIndex Node对象

        Returns:
            提取的实体列表
        """
        # 构建提取提示词
        prompt = self._build_entity_extraction_prompt(text)

        # 获取LLM模型实例
        llm = self.llm_service.get_chat_model()

        # 使用结构化输出提取实体
        try:
            # 构建消息
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="你是一个专业的实体提取助手，能够从文本中准确提取实体信息。"),
                HumanMessage(content=prompt),
            ]

            # 调用LLM
            response = llm.invoke(messages)

            # 解析响应
            if hasattr(response, "content"):
                content = response.content
            elif isinstance(response, str):
                content = response
            else:
                content = str(response)

            # 解析JSON
            try:
                result = json.loads(content)
                entities_data = result.get("entities", [])
            except json.JSONDecodeError:
                # 尝试从文本中提取JSON
                entities_data = self._parse_entities_from_text(content)

            # 转换为ExtractedEntity对象
            entities = []
            for entity_data in entities_data:
                try:
                    entity = ExtractedEntity(
                        name=entity_data.get("name", "").strip(),
                        entity_type=entity_data.get("type", EntityType.OTHER),
                        description=entity_data.get("description"),
                        aliases=entity_data.get("aliases", []),
                        properties=entity_data.get("properties", {}),
                        confidence=entity_data.get("confidence", 1.0),
                    )
                    if entity.name:
                        entities.append(entity)
                except Exception as exc:
                    logger.warning("解析实体失败: %s, error=%s", entity_data, exc)
                    continue

            return entities

        except Exception as exc:
            logger.error("LLM实体提取失败: %s", exc, exc_info=True)
            return []

    def _extract_relations(
        self,
        text: str,
        node: BaseNode,
        entities: list[ExtractedEntity],
    ) -> list[ExtractedRelation]:
        """
        使用LLM提取关系

        Args:
            text: 文本内容
            node: LlamaIndex Node对象
            entities: 已提取的实体列表

        Returns:
            提取的关系列表
        """
        if not entities or len(entities) < 2:
            return []

        # 构建提取提示词
        entity_names = [e.name for e in entities]
        prompt = self._build_relation_extraction_prompt(text, entity_names)

        # 获取LLM模型实例
        llm = self.llm_service.get_chat_model()

        # 使用结构化输出提取关系
        try:
            # 构建消息
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="你是一个专业的关系提取助手，能够从文本中准确提取实体之间的关系。"),
                HumanMessage(content=prompt),
            ]

            # 调用LLM
            response = llm.invoke(messages)

            # 解析响应
            if hasattr(response, "content"):
                content = response.content
            elif isinstance(response, str):
                content = response
            else:
                content = str(response)

            # 解析JSON
            try:
                result = json.loads(content)
                relations_data = result.get("relations", [])
            except json.JSONDecodeError:
                # 尝试从文本中提取JSON
                relations_data = self._parse_relations_from_text(content)

            # 转换为ExtractedRelation对象
            relations = []
            for relation_data in relations_data:
                try:
                    relation = ExtractedRelation(
                        source_entity=relation_data.get("source", "").strip(),
                        target_entity=relation_data.get("target", "").strip(),
                        relation_type=relation_data.get("relation", RelationType.RELATED_TO),
                        description=relation_data.get("description"),
                        confidence=relation_data.get("confidence", 1.0),
                    )
                    if relation.source_entity and relation.target_entity:
                        relations.append(relation)
                except Exception as exc:
                    logger.warning("解析关系失败: %s, error=%s", relation_data, exc)
                    continue

            return relations

        except Exception as exc:
            logger.error("LLM关系提取失败: %s", exc, exc_info=True)
            return []

    def _build_entity_extraction_prompt(self, text: str) -> str:
        """构建实体提取提示词"""
        entity_types = ", ".join([e.value for e in EntityType])
        return f"""请从以下文本中提取所有实体。

要求:
1. 识别所有实体，包括人物、组织机构、概念、事件、地点、时间等
2. 对于储能产业相关文本，优先识别储能产业特定实体类型（如储能技术、储能设备、储能项目等）
3. 每个实体包含以下信息:
   - name: 实体名称（必填）
   - type: 实体类型（必填，从以下类型中选择: {entity_types}）
   - description: 实体描述（可选）
   - aliases: 实体别名列表（可选）
   - properties: 扩展属性（可选，JSON格式）
   - confidence: 提取置信度（0.0-1.0，默认1.0）

4. 最多提取 {self.max_entities_per_chunk} 个实体

输出格式（JSON）:
{{
  "entities": [
    {{
      "name": "实体名称",
      "type": "实体类型",
      "description": "实体描述",
      "aliases": ["别名1", "别名2"],
      "properties": {{}},
      "confidence": 1.0
    }}
  ]
}}

文本内容:
{text}

请直接输出JSON格式，不要包含其他说明文字。"""

    def _build_relation_extraction_prompt(
        self,
        text: str,
        entity_names: list[str],
    ) -> str:
        """构建关系提取提示词"""
        relation_types = ", ".join([r.value for r in RelationType])
        entity_list = ", ".join(entity_names)
        return f"""请从以下文本中提取实体之间的关系。

已识别的实体: {entity_list}

要求:
1. 识别所有实体对之间的关系
2. 关系类型从以下类型中选择: {relation_types}
3. 每个关系包含以下信息:
   - source: 源实体名称（必填）
   - target: 目标实体名称（必填）
   - relation: 关系类型（必填）
   - description: 关系描述（可选）
   - confidence: 提取置信度（0.0-1.0，默认1.0）

4. 最多提取 {self.max_relations_per_chunk} 个关系

输出格式（JSON）:
{{
  "relations": [
    {{
      "source": "源实体名称",
      "target": "目标实体名称",
      "relation": "关系类型",
      "description": "关系描述",
      "confidence": 1.0
    }}
  ]
}}

文本内容:
{text}

请直接输出JSON格式，不要包含其他说明文字。"""

    def _parse_entities_from_text(self, text: str) -> list[dict[str, Any]]:
        """从文本中解析实体（降级方案）"""
        # 首先尝试直接解析整个文本
        try:
            result = json.loads(text.strip())
            if isinstance(result, dict) and "entities" in result:
                entities = result.get("entities", [])
                if isinstance(entities, list):
                    return entities
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

        # 尝试使用正则表达式提取JSON对象
        # 匹配从第一个 { 开始，使用平衡括号匹配完整的JSON对象
        brace_count = 0
        start_idx = text.find('{')
        if start_idx >= 0:
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[start_idx:i + 1]
                        try:
                            result = json.loads(json_str)
                            if isinstance(result, dict) and "entities" in result:
                                entities = result.get("entities", [])
                                if isinstance(entities, list):
                                    return entities
                        except json.JSONDecodeError:
                            pass
                        break

        # 尝试提取entities数组（最后的手段）
        entities_match = re.search(r'"entities"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if entities_match:
            # 尝试解析数组内容
            array_content = entities_match.group(1)
            # 简单的实体对象匹配
            entity_pattern = r'\{"name"\s*:\s*"([^"]+)"[^}]*"type"\s*:\s*"([^"]+)"[^}]*\}'
            entities = []
            for match in re.finditer(entity_pattern, array_content):
                entities.append({
                    "name": match.group(1),
                    "type": match.group(2),
                })
            if entities:
                return entities

        return []

    def _parse_relations_from_text(self, text: str) -> list[dict[str, Any]]:
        """从文本中解析关系（降级方案）"""
        # 首先尝试直接解析整个文本
        try:
            result = json.loads(text.strip())
            if isinstance(result, dict) and "relations" in result:
                relations = result.get("relations", [])
                if isinstance(relations, list):
                    return relations
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

        # 尝试使用正则表达式提取JSON对象
        # 匹配从第一个 { 开始，使用平衡括号匹配完整的JSON对象
        brace_count = 0
        start_idx = text.find('{')
        if start_idx >= 0:
            for i in range(start_idx, len(text)):
                if text[i] == '{':
                    brace_count += 1
                elif text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[start_idx:i + 1]
                        try:
                            result = json.loads(json_str)
                            if isinstance(result, dict) and "relations" in result:
                                relations = result.get("relations", [])
                                if isinstance(relations, list):
                                    return relations
                        except json.JSONDecodeError:
                            pass
                        break

        # 尝试提取relations数组（最后的手段）
        relations_match = re.search(r'"relations"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if relations_match:
            # 尝试解析数组内容
            array_content = relations_match.group(1)
            # 简单的关系对象匹配
            relation_pattern = r'\{"source"\s*:\s*"([^"]+)"[^}]*"target"\s*:\s*"([^"]+)"[^}]*"relation"\s*:\s*"([^"]+)"[^}]*\}'
            relations = []
            for match in re.finditer(relation_pattern, array_content):
                relations.append({
                    "source": match.group(1),
                    "target": match.group(2),
                    "relation": match.group(3),
                })
            if relations:
                return relations

        return []

    def _add_entity_to_graph(
        self,
        entity: ExtractedEntity,
        node: BaseNode,
    ) -> str:
        """
        将实体添加到图数据库

        Args:
            entity: 提取的实体
            node: 来源Node对象

        Returns:
            实体节点ID
        """
        # 实体消歧：检查是否已存在同名实体
        entity_id = self._entity_name_to_id.get(entity.name)
        if entity_id:
            # 更新现有实体
            try:
                node_metadata = getattr(node, "metadata", {}) or {}
                self.graph_adapter.update_node(
                    entity_id,
                    description=entity.description or "",
                    aliases=json.dumps(entity.aliases or []),
                    properties=json.dumps(entity.properties or {}),
                    source_document_id=node_metadata.get("source_document_id"),
                    source_chunk_id=node_metadata.get("chunk_id"),
                    updated_at=node_metadata.get("processed_at"),
                )
                logger.debug("更新现有实体: name=%s, id=%s", entity.name, entity_id)
            except Exception as exc:
                logger.warning("更新实体失败: name=%s, error=%s", entity.name, exc)
            return entity_id

        # 创建新实体节点
        entity_id = str(uuid4())
        node_metadata = getattr(node, "metadata", {}) or {}

        try:
            self.graph_adapter.add_node(
                entity_id,
                name=entity.name,
                entity_type=entity.entity_type.value if isinstance(entity.entity_type, EntityType) else str(entity.entity_type),
                description=entity.description or "",
                aliases=json.dumps(entity.aliases or []),
                properties=json.dumps(entity.properties or {}),
                confidence=entity.confidence,
                source_document_id=node_metadata.get("source_document_id"),
                source_chunk_id=node_metadata.get("chunk_id"),
                source_section_path=node_metadata.get("section_path"),
                created_at=node_metadata.get("processed_at"),
            )

            # 记录实体名称到ID的映射
            self._entity_name_to_id[entity.name] = entity_id
            logger.debug("添加新实体: name=%s, id=%s", entity.name, entity_id)

        except Exception as exc:
            logger.error("添加实体失败: name=%s, error=%s", entity.name, exc)
            raise KnowledgeGraphError(f"添加实体失败: {exc}") from exc

        return entity_id

    def _add_relation_to_graph(
        self,
        relation: ExtractedRelation,
        node: BaseNode,
    ) -> None:
        """
        将关系添加到图数据库

        Args:
            relation: 提取的关系
            node: 来源Node对象
        """
        # 获取源实体和目标实体的ID
        source_id = self._entity_name_to_id.get(relation.source_entity)
        target_id = self._entity_name_to_id.get(relation.target_entity)

        if not source_id or not target_id:
            logger.warning(
                "关系中的实体不存在: source=%s, target=%s",
                relation.source_entity,
                relation.target_entity,
            )
            return

        # 检查关系是否已存在
        existing_edge = self.graph_adapter.get_edge(source_id, target_id)
        if existing_edge:
            logger.debug(
                "关系已存在: source=%s, target=%s",
                relation.source_entity,
                relation.target_entity,
            )
            return

        # 添加关系边
        node_metadata = getattr(node, "metadata", {}) or {}
        try:
            self.graph_adapter.add_edge(
                source_id,
                target_id,
                relation_type=relation.relation_type.value if isinstance(relation.relation_type, RelationType) else str(relation.relation_type),
                description=relation.description or "",
                confidence=relation.confidence,
                source_document_id=node_metadata.get("source_document_id"),
                source_chunk_id=node_metadata.get("chunk_id"),
                source_section_path=node_metadata.get("section_path"),
            )
            logger.debug(
                "添加关系: source=%s, target=%s, relation=%s",
                relation.source_entity,
                relation.target_entity,
                relation.relation_type,
            )
        except Exception as exc:
            logger.error(
                "添加关系失败: source=%s, target=%s, error=%s",
                relation.source_entity,
                relation.target_entity,
                exc,
            )
            raise KnowledgeGraphError(f"添加关系失败: {exc}") from exc

    def get_entities_by_type(
        self,
        entity_type: EntityType | str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        根据实体类型查询实体

        Args:
            entity_type: 实体类型
            limit: 限制返回数量

        Returns:
            实体列表
        """
        entity_type_str = entity_type.value if isinstance(entity_type, EntityType) else str(entity_type)
        filters = {"entity_type": entity_type_str}
        return self.graph_adapter.list_nodes(filters=filters, limit=limit)

    def get_relations_by_type(
        self,
        relation_type: RelationType | str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        根据关系类型查询关系

        Args:
            relation_type: 关系类型
            limit: 限制返回数量

        Returns:
            关系列表
        """
        relation_type_str = relation_type.value if isinstance(relation_type, RelationType) else str(relation_type)
        filters = {"relation_type": relation_type_str}
        return self.graph_adapter.list_edges(filters=filters, limit=limit)

    def get_entity_neighbors(
        self,
        entity_name: str,
        max_depth: int = 1,
    ) -> list[dict[str, Any]]:
        """
        获取实体的邻居节点

        Args:
            entity_name: 实体名称
            max_depth: 最大深度

        Returns:
            邻居节点列表
        """
        entity_id = self._entity_name_to_id.get(entity_name)
        if not entity_id:
            logger.warning("实体不存在: name=%s", entity_name)
            return []

        neighbors = self.graph_adapter.get_neighbors(entity_id)
        return [self.graph_adapter.get_node(nid) for nid in neighbors if self.graph_adapter.get_node(nid)]

    def get_stats(self) -> dict[str, Any]:
        """
        获取知识图谱统计信息

        Returns:
            统计信息字典
        """
        try:
            graph_info = self.graph_adapter.get_graph_info()
            node_count = self.graph_adapter.count_nodes()
            edge_count = self.graph_adapter.count_edges()

            return {
                "graph_name": self.graph_name,
                "node_count": node_count,
                "edge_count": edge_count,
                "graph_info": graph_info,
            }
        except Exception as exc:
            logger.error("获取统计信息失败: %s", exc, exc_info=True)
            raise KnowledgeGraphError(f"获取统计信息失败: {exc}") from exc

