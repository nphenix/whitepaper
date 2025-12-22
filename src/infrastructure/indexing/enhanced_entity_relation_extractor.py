# 生成命令: T054 知识图谱实体和关系提取增强模块
# 生成时间: 2025-01-27
# 来源: docs/development/t054-task-re-evaluation.md

"""
增强的实体关系提取器 (T054)

该模块作为T049知识图谱构建器的增强插件，提供以下增强功能：
1. Few-shot Learning支持：提供示例引导LLM理解任务
2. 混合提取方法：LLM + spaCy NER混合提取
3. 质量保证机制：提取结果验证、一致性检查、置信度评估

设计目标:
- 作为T049的增强插件，提供互补功能
- 可以独立使用，也可以与T049配合使用
- 支持领域特定的Few-shot示例库
- 实现混合提取方法提升准确率
- 提供质量保证机制确保提取质量

参考最佳实践:
- llm-kg-frameworks-and-patterns.md - LLM知识图谱构建最佳实践
- DeepKE-LLM设计模式
- LangChain 1.0最佳实践
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.infrastructure.indexing.knowledge_graph import (
    EntityType,
    ExtractedEntity,
    ExtractedRelation,
    KnowledgeGraphBuilder,
    RelationType,
)
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.schema import BaseNode
    LLAMA_INDEX_AVAILABLE = True
except ImportError:  # pragma: no cover
    logger.warning(
        "LlamaIndex not available, enhanced extractor will be disabled"
    )
    BaseNode = Any  # type: ignore[assignment, misc]
    LLAMA_INDEX_AVAILABLE = False

# spaCy导入（可选）
try:
    import spacy
    from spacy import displacy
    SPACY_AVAILABLE = True
except ImportError:  # pragma: no cover
    SPACY_AVAILABLE = False
    logger.warning(
        "spaCy not available, NER validation will be disabled. "
        "Install spaCy and Chinese model: pip install spacy && python -m spacy download zh_core_web_sm"
    )


class ValidationResult(BaseModel):
    """验证结果"""

    is_valid: bool = Field(description="是否通过验证")
    errors: list[str] = Field(default_factory=list, description="验证错误列表")
    warnings: list[str] = Field(default_factory=list, description="验证警告列表")
    confidence_score: float = Field(
        default=1.0, description="置信度分数（0.0-1.0）"
    )


@dataclass
class FewShotExample:
    """Few-shot示例"""

    text: str
    entities: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    domain: str | None = None  # 领域标识（如"energy_storage"）


class EnhancedEntityRelationExtractor:
    """
    增强的实体关系提取器

    提供Few-shot Learning、混合提取方法（LLM + spaCy NER）、质量验证等增强功能。

    典型用法:
        >>> extractor = EnhancedEntityRelationExtractor(
        ...     few_shot_examples_path="data/few_shot_examples.json",
        ...     enable_spacy=True
        ... )
        >>> entities, relations = extractor.extract_entities_enhanced(text)
        >>> validation = extractor.validate_extraction(entities, relations)
    """

    def __init__(
        self,
        few_shot_examples_path: str | Path | None = None,
        domain: str | None = None,
        llm_service: LLMService | None = None,
        enable_spacy: bool = True,
        spacy_model: str = "zh_core_web_sm",
        max_entities_per_chunk: int = 10,
        max_relations_per_chunk: int = 10,
    ) -> None:
        """
        初始化增强提取器

        Args:
            few_shot_examples_path: Few-shot示例库JSON文件路径
            domain: 领域标识（如"energy_storage"），用于加载领域特定示例
            llm_service: LLM服务，如果为None则使用全局实例
            enable_spacy: 是否启用spaCy NER验证
            spacy_model: spaCy模型名称（默认中文模型）
            max_entities_per_chunk: 每个块最多提取的实体数量
            max_relations_per_chunk: 每个块最多提取的关系数量
        """
        if not LLAMA_INDEX_AVAILABLE:
            raise ImportError(
                "LlamaIndex is not available. Please install llama-index package to "
                "use EnhancedEntityRelationExtractor."
            )

        self.llm_service = llm_service or get_llm_service()
        self.domain = domain
        self.max_entities_per_chunk = max_entities_per_chunk
        self.max_relations_per_chunk = max_relations_per_chunk

        # 加载Few-shot示例库
        self.few_shot_examples: list[FewShotExample] = []
        if few_shot_examples_path:
            self._load_few_shot_examples(few_shot_examples_path, domain)

        # 初始化spaCy（如果启用）
        self.enable_spacy = enable_spacy and SPACY_AVAILABLE
        self.spacy_nlp = None
        if self.enable_spacy:
            try:
                self.spacy_nlp = spacy.load(spacy_model)
                logger.info("spaCy模型加载成功: %s", spacy_model)
            except OSError:
                logger.warning(
                    "spaCy模型 %s 未安装，NER验证将被禁用。"
                    "请运行: python -m spacy download %s",
                    spacy_model,
                    spacy_model,
                )
                self.enable_spacy = False
                self.spacy_nlp = None

        logger.debug(
            "初始化 %s: domain=%s, enable_spacy=%s, few_shot_count=%s",
            self.__class__.__name__,
            domain,
            self.enable_spacy,
            len(self.few_shot_examples),
        )

    def _load_few_shot_examples(
        self,
        examples_path: str | Path,
        domain: str | None = None,
    ) -> None:
        """
        加载Few-shot示例库

        Args:
            examples_path: 示例库JSON文件路径
            domain: 领域标识，用于过滤示例
        """
        try:
            path = Path(examples_path)
            if not path.exists():
                logger.warning("Few-shot示例库文件不存在: %s", examples_path)
                return

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 解析示例数据
            examples_data = data.get("examples", [])
            if domain:
                # 过滤领域特定示例
                examples_data = [
                    ex for ex in examples_data
                    if ex.get("domain") == domain or ex.get("domain") is None
                ]

            for ex_data in examples_data:
                example = FewShotExample(
                    text=ex_data.get("text", ""),
                    entities=ex_data.get("entities", []),
                    relations=ex_data.get("relations", []),
                    domain=ex_data.get("domain"),
                )
                self.few_shot_examples.append(example)

            logger.info(
                "加载Few-shot示例: 总数=%s, 领域=%s, 实际加载=%s",
                len(data.get("examples", [])),
                domain,
                len(self.few_shot_examples),
            )

        except Exception as exc:
            logger.error("加载Few-shot示例库失败: %s", exc, exc_info=True)
            self.few_shot_examples = []

    def extract_entities_enhanced(
        self,
        text: str,
        node: BaseNode | None = None,
    ) -> list[ExtractedEntity]:
        """
        使用混合方法提取实体（LLM + spaCy NER）

        Args:
            text: 文本内容
            node: LlamaIndex Node对象（可选）

        Returns:
            提取的实体列表
        """
        # 1. 使用LLM提取实体（带Few-shot示例）
        llm_entities = self._extract_entities_with_llm(text, node)

        # 2. 使用spaCy NER提取实体（如果启用）
        spacy_entities = []
        if self.enable_spacy and self.spacy_nlp:
            spacy_entities = self._extract_entities_with_spacy(text)

        # 3. 融合结果
        entities = self._merge_entity_results(llm_entities, spacy_entities)

        # 4. 质量验证
        validation = self.validate_entities(entities)
        if not validation.is_valid:
            logger.warning(
                "实体提取验证失败: errors=%s, warnings=%s",
                validation.errors,
                validation.warnings,
            )

        return entities

    def extract_relations_enhanced(
        self,
        text: str,
        entities: list[ExtractedEntity],
        node: BaseNode | None = None,
    ) -> list[ExtractedRelation]:
        """
        使用混合方法提取关系

        Args:
            text: 文本内容
            entities: 已提取的实体列表
            node: LlamaIndex Node对象（可选）

        Returns:
            提取的关系列表
        """
        if not entities or len(entities) < 2:
            return []

        # 1. 使用LLM提取关系（带Few-shot示例）
        relations = self._extract_relations_with_llm(text, entities, node)

        # 2. 质量验证
        validation = self.validate_relations(relations, entities)
        if not validation.is_valid:
            logger.warning(
                "关系提取验证失败: errors=%s, warnings=%s",
                validation.errors,
                validation.warnings,
            )

        return relations

    def _extract_entities_with_llm(
        self,
        text: str,
        node: BaseNode | None = None,
    ) -> list[ExtractedEntity]:
        """使用LLM提取实体（带Few-shot示例）"""
        # 构建带Few-shot示例的提示词
        prompt = self._build_entity_extraction_prompt_with_fewshot(text)

        # 获取LLM模型实例
        llm = self.llm_service.get_chat_model()

        # 使用结构化输出提取实体
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(
                    content="你是一个专业的实体提取助手，能够从文本中准确提取实体信息。"
                ),
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
                        entity_type=entity_data.get(
                            "type", EntityType.OTHER
                        ),
                        description=entity_data.get("description"),
                        aliases=entity_data.get("aliases", []),
                        properties=entity_data.get("properties", {}),
                        confidence=entity_data.get("confidence", 1.0),
                    )
                    if entity.name:
                        entities.append(entity)
                except Exception as exc:
                    logger.warning(
                        "解析实体失败: %s, error=%s", entity_data, exc
                    )
                    continue

            return entities

        except Exception as exc:
            logger.error("LLM实体提取失败: %s", exc, exc_info=True)
            return []

    def _extract_entities_with_spacy(self, text: str) -> list[ExtractedEntity]:
        """使用spaCy NER提取实体"""
        if not self.spacy_nlp:
            return []

        try:
            doc = self.spacy_nlp(text)
            entities = []

            for ent in doc.ents:
                # 将spaCy的实体类型映射到我们的EntityType
                entity_type = self._map_spacy_label_to_entity_type(ent.label_)

                entity = ExtractedEntity(
                    name=ent.text.strip(),
                    entity_type=entity_type,
                    description=None,
                    aliases=[],
                    properties={"spacy_label": ent.label_},
                    confidence=0.8,  # spaCy的默认置信度
                )
                entities.append(entity)

            return entities

        except Exception as exc:
            logger.error("spaCy实体提取失败: %s", exc, exc_info=True)
            return []

    def _map_spacy_label_to_entity_type(self, spacy_label: str) -> EntityType:
        """将spaCy的实体标签映射到EntityType"""
        label_mapping = {
            "PERSON": EntityType.PERSON,
            "ORG": EntityType.ORGANIZATION,
            "GPE": EntityType.LOCATION,
            "LOC": EntityType.LOCATION,
            "EVENT": EntityType.EVENT,
            "DATE": EntityType.TIME,
            "TIME": EntityType.TIME,
        }
        return label_mapping.get(spacy_label, EntityType.OTHER)

    def _merge_entity_results(
        self,
        llm_entities: list[ExtractedEntity],
        spacy_entities: list[ExtractedEntity],
    ) -> list[ExtractedEntity]:
        """
        融合LLM和spaCy的提取结果

        策略：
        1. 优先使用LLM提取的实体（更准确）
        2. 使用spaCy结果验证和补充
        3. 对于LLM提取但spaCy未识别的实体，降低置信度
        4. 对于spaCy识别但LLM未提取的实体，作为补充（降低置信度）
        """
        if not spacy_entities:
            return llm_entities

        # 创建实体名称到实体的映射
        llm_entity_map = {e.name.lower(): e for e in llm_entities}
        spacy_entity_map = {e.name.lower(): e for e in spacy_entities}

        merged_entities = []

        # 1. 添加LLM提取的实体（优先）
        for entity in llm_entities:
            entity_lower = entity.name.lower()
            # 检查spaCy是否也识别了这个实体
            if entity_lower in spacy_entity_map:
                # 两者都识别，提高置信度
                entity.confidence = min(1.0, entity.confidence + 0.1)
            else:
                # LLM识别但spaCy未识别，稍微降低置信度
                entity.confidence = max(0.5, entity.confidence - 0.1)

            merged_entities.append(entity)

        # 2. 添加spaCy识别但LLM未提取的实体（作为补充）
        for entity in spacy_entities:
            entity_lower = entity.name.lower()
            if entity_lower not in llm_entity_map:
                # spaCy识别但LLM未提取，降低置信度
                entity.confidence = 0.6
                merged_entities.append(entity)

        return merged_entities

    def _extract_relations_with_llm(
        self,
        text: str,
        entities: list[ExtractedEntity],
        node: BaseNode | None = None,
    ) -> list[ExtractedRelation]:
        """使用LLM提取关系（带Few-shot示例）"""
        # 构建带Few-shot示例的提示词
        entity_names = [e.name for e in entities]
        prompt = self._build_relation_extraction_prompt_with_fewshot(
            text, entity_names
        )

        # 获取LLM模型实例
        llm = self.llm_service.get_chat_model()

        # 使用结构化输出提取关系
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(
                    content="你是一个专业的关系提取助手，能够从文本中准确提取实体之间的关系。"
                ),
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
                        relation_type=relation_data.get(
                            "relation", RelationType.RELATED_TO
                        ),
                        description=relation_data.get("description"),
                        confidence=relation_data.get("confidence", 1.0),
                    )
                    if relation.source_entity and relation.target_entity:
                        relations.append(relation)
                except Exception as exc:
                    logger.warning(
                        "解析关系失败: %s, error=%s", relation_data, exc
                    )
                    continue

            return relations

        except Exception as exc:
            logger.error("LLM关系提取失败: %s", exc, exc_info=True)
            return []

    def _build_entity_extraction_prompt_with_fewshot(self, text: str) -> str:
        """构建带Few-shot示例的实体提取提示词"""
        entity_types = ", ".join([e.value for e in EntityType])

        # 构建Few-shot示例部分
        few_shot_section = ""
        if self.few_shot_examples:
            few_shot_section = "\n\n示例:\n"
            for i, example in enumerate(self.few_shot_examples[:3], 1):  # 最多3个示例
                few_shot_section += f"\n示例 {i}:\n"
                few_shot_section += f"文本: {example.text[:200]}...\n"
                few_shot_section += f"提取的实体: {json.dumps(example.entities, ensure_ascii=False, indent=2)}\n"

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

{few_shot_section}

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

    def _build_relation_extraction_prompt_with_fewshot(
        self,
        text: str,
        entity_names: list[str],
    ) -> str:
        """构建带Few-shot示例的关系提取提示词"""
        relation_types = ", ".join([r.value for r in RelationType])
        entity_list = ", ".join(entity_names)

        # 构建Few-shot示例部分
        few_shot_section = ""
        if self.few_shot_examples:
            few_shot_section = "\n\n示例:\n"
            for i, example in enumerate(self.few_shot_examples[:3], 1):  # 最多3个示例
                few_shot_section += f"\n示例 {i}:\n"
                few_shot_section += f"文本: {example.text[:200]}...\n"
                few_shot_section += f"提取的关系: {json.dumps(example.relations, ensure_ascii=False, indent=2)}\n"

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

{few_shot_section}

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
        brace_count = 0
        start_idx = text.find("{")
        if start_idx >= 0:
            for i in range(start_idx, len(text)):
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[start_idx : i + 1]
                        try:
                            result = json.loads(json_str)
                            if isinstance(result, dict) and "entities" in result:
                                entities = result.get("entities", [])
                                if isinstance(entities, list):
                                    return entities
                        except json.JSONDecodeError:
                            pass
                        break

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
        brace_count = 0
        start_idx = text.find("{")
        if start_idx >= 0:
            for i in range(start_idx, len(text)):
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[start_idx : i + 1]
                        try:
                            result = json.loads(json_str)
                            if isinstance(result, dict) and "relations" in result:
                                relations = result.get("relations", [])
                                if isinstance(relations, list):
                                    return relations
                        except json.JSONDecodeError:
                            pass
                        break

        return []

    def validate_entities(
        self, entities: list[ExtractedEntity]
    ) -> ValidationResult:
        """
        验证实体提取结果

        Args:
            entities: 提取的实体列表

        Returns:
            验证结果
        """
        errors = []
        warnings = []
        confidence_scores = []

        for entity in entities:
            # 1. 实体名称合理性检查
            if not entity.name or len(entity.name.strip()) == 0:
                errors.append(f"实体名称为空")
                continue

            if len(entity.name) > 100:
                warnings.append(f"实体名称过长: {entity.name[:50]}...")

            # 2. 实体类型验证
            if not isinstance(entity.entity_type, (EntityType, str)):
                errors.append(f"实体类型无效: {entity.name}")

            # 3. 置信度检查
            if entity.confidence < 0.0 or entity.confidence > 1.0:
                warnings.append(
                    f"实体置信度超出范围: {entity.name}, confidence={entity.confidence}"
                )
                entity.confidence = max(0.0, min(1.0, entity.confidence))

            confidence_scores.append(entity.confidence)

        # 计算平均置信度
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 1.0
        )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            confidence_score=avg_confidence,
        )

    def validate_relations(
        self,
        relations: list[ExtractedRelation],
        entities: list[ExtractedEntity],
    ) -> ValidationResult:
        """
        验证关系提取结果

        Args:
            relations: 提取的关系列表
            entities: 已提取的实体列表

        Returns:
            验证结果
        """
        errors = []
        warnings = []
        confidence_scores = []

        # 创建实体名称集合（用于快速查找）
        entity_names = {e.name for e in entities}

        for relation in relations:
            # 1. 关系完整性检查
            if not relation.source_entity or not relation.target_entity:
                errors.append("关系缺少源实体或目标实体")
                continue

            # 2. 实体-关系匹配验证
            if relation.source_entity not in entity_names:
                errors.append(
                    f"关系的源实体不存在: {relation.source_entity}"
                )

            if relation.target_entity not in entity_names:
                errors.append(
                    f"关系的目标实体不存在: {relation.target_entity}"
                )

            # 3. 关系类型一致性检查
            if not isinstance(relation.relation_type, (RelationType, str)):
                errors.append(f"关系类型无效: {relation.relation_type}")

            # 4. 置信度检查
            if relation.confidence < 0.0 or relation.confidence > 1.0:
                warnings.append(
                    f"关系置信度超出范围: {relation.source_entity} -> {relation.target_entity}, "
                    f"confidence={relation.confidence}"
                )
                relation.confidence = max(0.0, min(1.0, relation.confidence))

            confidence_scores.append(relation.confidence)

        # 计算平均置信度
        avg_confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else 1.0
        )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            confidence_score=avg_confidence,
        )

    def validate_extraction(
        self,
        entities: list[ExtractedEntity],
        relations: list[ExtractedRelation],
    ) -> ValidationResult:
        """
        验证完整的提取结果（实体+关系）

        Args:
            entities: 提取的实体列表
            relations: 提取的关系列表

        Returns:
            验证结果
        """
        # 验证实体
        entity_validation = self.validate_entities(entities)

        # 验证关系
        relation_validation = self.validate_relations(relations, entities)

        # 合并验证结果
        all_errors = entity_validation.errors + relation_validation.errors
        all_warnings = entity_validation.warnings + relation_validation.warnings

        # 计算综合置信度
        combined_confidence = (
            entity_validation.confidence_score + relation_validation.confidence_score
        ) / 2.0

        return ValidationResult(
            is_valid=len(all_errors) == 0,
            errors=all_errors,
            warnings=all_warnings,
            confidence_score=combined_confidence,
        )


class EnhancedKnowledgeGraphBuilder(KnowledgeGraphBuilder):
    """
    增强的知识图谱构建器

    继承T049的KnowledgeGraphBuilder，集成T054的增强功能：
    - Few-shot Learning支持
    - spaCy NER混合提取
    - 质量验证机制

    典型用法:
        >>> builder = EnhancedKnowledgeGraphBuilder(
        ...     graph_name="knowledge_graph",
        ...     few_shot_examples_path="data/few_shot_examples/entity_relation_examples.json",
        ...     domain="energy_storage",
        ...     enable_spacy=True
        ... )
        >>> nodes = [TextNode(text="示例文本", metadata={"section_path": "1.2"})]
        >>> builder.build_from_nodes(nodes)
    """

    def __init__(
        self,
        graph_name: str = "knowledge_graph",
        graph_adapter=None,  # NetworkXAdapter类型，避免循环导入
        llm_service: LLMService | None = None,
        max_entities_per_chunk: int = 10,
        max_relations_per_chunk: int = 10,
        few_shot_examples_path: str | Path | None = None,
        domain: str | None = None,
        enable_spacy: bool = True,
        spacy_model: str = "zh_core_web_sm",
    ) -> None:
        """
        初始化增强的知识图谱构建器

        Args:
            graph_name: 图名称，用于标识不同的知识图谱
            graph_adapter: NetworkX适配器，如果为None则创建新实例
            llm_service: LLM服务，如果为None则使用全局实例
            max_entities_per_chunk: 每个块最多提取的实体数量
            max_relations_per_chunk: 每个块最多提取的关系数量
            few_shot_examples_path: Few-shot示例库JSON文件路径
            domain: 领域标识（如"energy_storage"），用于加载领域特定示例
            enable_spacy: 是否启用spaCy NER验证
            spacy_model: spaCy模型名称（默认中文模型）
        """
        # 调用父类初始化
        super().__init__(
            graph_name=graph_name,
            graph_adapter=graph_adapter,
            llm_service=llm_service,
            max_entities_per_chunk=max_entities_per_chunk,
            max_relations_per_chunk=max_relations_per_chunk,
        )

        # 初始化增强提取器
        self.enhanced_extractor = EnhancedEntityRelationExtractor(
            few_shot_examples_path=few_shot_examples_path,
            domain=domain,
            llm_service=llm_service,
            enable_spacy=enable_spacy,
            spacy_model=spacy_model,
            max_entities_per_chunk=max_entities_per_chunk,
            max_relations_per_chunk=max_relations_per_chunk,
        )

        logger.info(
            "初始化增强知识图谱构建器: graph_name=%s, domain=%s, enable_spacy=%s",
            graph_name,
            domain,
            enable_spacy,
        )

    def _extract_from_node(
        self,
        node: BaseNode,
    ) -> tuple[list[ExtractedEntity], list[ExtractedRelation]]:
        """
        从单个Node中提取实体和关系（使用增强提取器）

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

        # 使用增强提取器提取实体和关系
        try:
            entities = self.enhanced_extractor.extract_entities_enhanced(
                text_content, node
            )
            relations = self.enhanced_extractor.extract_relations_enhanced(
                text_content, entities, node
            )

            # 记录验证结果
            validation = self.enhanced_extractor.validate_extraction(
                entities, relations
            )
            if not validation.is_valid:
                logger.warning(
                    "提取结果验证失败: errors=%s, warnings=%s, confidence=%s",
                    validation.errors,
                    validation.warnings,
                    validation.confidence_score,
                )

            return entities, relations

        except Exception as exc:
            logger.error(
                "增强提取失败: node_id=%s, error=%s",
                getattr(node, "node_id", "unknown"),
                exc,
                exc_info=True,
            )
            # 降级到父类的原始提取方法
            logger.info("降级到基础提取方法")
            return super()._extract_from_node(node)

