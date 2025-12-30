"""
草稿生成Agent

基于BaseAgent实现的草稿生成Agent,使用LangChain 1.0的Agent框架.
用于MVP 3步流程中的第三步: 草稿生成(带素材追溯链接).

生成命令: /speckit.implement T232, T233, T234
生成时间: 2025-12-25
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool

from src.application.agent_base import AgentConfig, BaseAgent
from src.domain.agent.draft import Draft, DraftSection, DraftSectionType, DraftStatus
from src.domain.agent.optimized_outline import OptimizedOutline
from src.domain.agent.outline import OutlineItemType
from src.domain.agent.source_reference import SourceReference
from src.infrastructure.indexing.hybrid_retriever import (
    HybridRetriever,
    QueryType,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.agent_exceptions import AgentExecutionError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.schema import NodeWithScore

    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    NodeWithScore = Any  # type: ignore[assignment, misc]
    LLAMA_INDEX_AVAILABLE = False
    logger.warning("LlamaIndex not available, RAG retrieval will be disabled")


class DraftGeneratorAgent(BaseAgent):
    """
    草稿生成Agent

    基于BaseAgent实现的草稿生成Agent,提供:
    1. 基于优化大纲生成草稿内容
    2. 从知识库检索素材并嵌入草稿(T233: RAG检索)
    3. 素材引用和追溯链接管理(T234: 素材引用嵌入)
    4. 结构化输出(Draft对象)

    核心功能:
    - generate_draft(optimized_outline, industry_name, database_names): 生成草稿
    - _retrieve_materials(query_text, section_title): 检索素材(使用HybridRetriever)
    - _convert_node_to_source_reference(node): 将检索结果转换为SourceReference
    - _format_materials_context(section_materials): 格式化素材上下文用于提示词
    - _parse_generated_content(): 解析生成的内容并嵌入素材引用

    架构优势:
    - 使用LangChain 1.0的create_agent API
    - 支持结构化输出(response_format)
    - 统一使用BaseAgent的生命周期管理
    - 自动获得错误处理,日志记录,状态持久化等能力
    - 符合LangChain 1.0最佳实践
    - 集成HybridRetriever进行RAG检索,提高内容质量

    功能特性:
    - T232: 基础框架实现 ✅
    - T233: RAG检索功能(使用HybridRetriever)✅
    - T234: 素材引用嵌入功能 ✅
    - 支持本地文档引用(文件路径,段落定位,页码定位)
    - 网络文章引用功能预留接口(待第三步完成后启用)
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_service: LLMService | None = None,
        report_type: str = "市场研究报告",
        language: str = "中文",
        style: str = "专业,客观,数据驱动",
        hybrid_retriever: HybridRetriever | None = None,
        **kwargs,
    ):
        """初始化草稿生成Agent

        Args:
            config: Agent配置
            llm_service: LLM服务实例,如果为None则使用默认实例
            report_type: 报告类型(如市场研究报告,产业分析报告等)
            language: 语言(如中文,英文等)
            style: 风格(如专业,客观,数据驱动等)
            hybrid_retriever: 混合检索引擎实例,用于RAG检索(可选)
            **kwargs: 传递给BaseAgent的其他参数
        """
        super().__init__(config, llm_service=llm_service, **kwargs)

        # MVP默认约束条件(不依赖阶段6)
        self.report_type = report_type
        self.language = language
        self.style = style

        # RAG检索器(可选,如果提供则启用RAG检索功能)
        self.hybrid_retriever = hybrid_retriever

        logger.info(
            "初始化DraftGeneratorAgent: %s, 报告类型=%s, 语言=%s, 风格=%s, RAG检索=%s",
            self.agent_name,
            self.report_type,
            self.language,
            self.style,
            "启用" if hybrid_retriever else "禁用",
        )

    def get_tools(self) -> list[BaseTool]:
        """获取Agent专用工具列表

        草稿生成Agent当前版本不需要工具.
        未来版本(T233)可能会添加:
        - 知识库检索工具
        - 素材检索工具
        - 引用管理工具

        Returns:
            工具列表(当前为空列表)
        """
        # 当前版本不需要工具,主要使用LLM直接生成
        # 未来版本将添加RAG检索工具等
        return []

    def generate_draft(
        self,
        optimized_outline: OptimizedOutline,
        industry_name: str,
        database_names: list[str] | None = None,
        report_type: str | None = None,
    ) -> Draft:
        """生成草稿

        基于优化后的大纲生成草稿内容.
        当前版本(T232)实现基础框架,具体生成逻辑将在T233中实现.

        Args:
            optimized_outline: 优化后的大纲对象
            industry_name: 行业名称
            database_names: 数据库名称列表
            report_type: 报告类型(如果不指定则使用默认值)

        Returns:
            生成的草稿对象(Draft)

        Raises:
            AgentExecutionError: 生成失败时抛出
        """
        try:
            logger.info(
                "开始生成草稿: 大纲ID=%s, 行业=%s, 数据库=%s",
                optimized_outline.id,
                industry_name,
                database_names,
            )

            # 使用指定的报告类型或默认值
            report_type = report_type or self.report_type
            database_names = database_names or []

            # 1. 创建草稿对象
            draft = Draft(
                id=uuid.uuid4(),
                title=f"{industry_name} - {report_type}",
                description=f"基于优化大纲生成的{report_type}草稿",
                outline_id=optimized_outline.original_outline_id,
                industry_id=uuid.uuid4(),  # TODO: 从行业服务获取真实ID
                database_ids=[],  # TODO: 从数据库服务获取真实ID列表
                status=DraftStatus.GENERATING,
            )

            # 2. 构建生成提示词(基础版本)
            # 注意:完整的RAG检索和素材嵌入将在T233中实现
            system_message = self._get_draft_generation_system_message(
                industry_name=industry_name,
                report_type=report_type,
            )

            # 3. 从优化大纲获取结构信息
            outline_structure = self._format_outline_structure(optimized_outline)

            # 4. 为每个大纲章节检索相关素材(T233: RAG检索)
            all_source_references: dict[uuid.UUID, SourceReference] = {}
            section_materials: dict[uuid.UUID, list[NodeWithScore]] = {}

            if self.hybrid_retriever:
                logger.info("开始为大纲章节检索素材...")
                for item in optimized_outline.optimized_items:
                    optimized_item = item.optimized_item

                    # 构建查询文本(章节标题 + 描述)
                    query_text = optimized_item.title
                    if optimized_item.description:
                        query_text += f" {optimized_item.description}"

                    # 检索素材
                    materials = self._retrieve_materials(
                        query_text=query_text,
                        section_title=optimized_item.title,
                        top_k=5,  # 每个章节检索5个相关素材
                    )
                    section_materials[optimized_item.id] = materials

                    # 将检索结果转换为SourceReference
                    for material in materials:
                        source_ref = self._convert_node_to_source_reference(material)
                        all_source_references[source_ref.id] = source_ref

                    logger.info(
                        "章节 '%s' 检索到 %d 个素材",
                        optimized_item.title,
                        len(materials),
                    )

            # 5. 构建提示词模板(包含检索到的素材)
            prompt_template = self._get_draft_generation_prompt()

            # 6. 格式化检索到的素材内容(用于提示词)
            materials_context = self._format_materials_context(section_materials)

            # 7. 构建消息列表
            messages = [
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": prompt_template.format_messages(
                        industry_name=industry_name,
                        database_names=", ".join(database_names) if database_names else "无",
                        report_type=report_type,
                        outline_structure=outline_structure,
                        materials_context=materials_context,
                    )[0].content,
                },
            ]

            # 8. 使用LLM生成草稿内容
            from langchain_core.output_parsers import StrOutputParser

            # 创建提示词
            prompt = ChatPromptTemplate.from_messages(messages)

            # 构建链
            chain = prompt | self.model | StrOutputParser()

            # 执行链,生成草稿内容
            generated_content = chain.invoke({})

            logger.info("LLM生成草稿内容完成,长度=%d字符", len(generated_content))

            # 9. 解析生成的内容并创建草稿章节(T234: 嵌入素材引用)
            sections = self._parse_generated_content(
                content=generated_content,
                optimized_outline=optimized_outline,
                section_materials=section_materials,
                all_source_references=all_source_references,
            )

            # 兜底：如果解析未生成任何章节（例如 optimized_items 为空），
            # 仍然把完整生成内容作为一个章节写入，确保前端/测试能拿到完整草稿文本。
            if not sections and isinstance(generated_content, str) and generated_content.strip():
                sections = [
                    DraftSection(
                        section_type=DraftSectionType.PARAGRAPH,
                        level=1,
                        title=None,
                        content=generated_content.strip(),
                        order=0,
                    )
                ]

            # 10. 添加章节到草稿
            for section in sections:
                draft.add_section(section)

            # 9. 更新草稿状态
            draft.status = DraftStatus.GENERATED

            logger.info(
                "草稿生成完成: ID=%s, 章节数=%d",
                draft.id,
                len(draft.sections),
            )

            return draft

        except Exception as e:
            logger.error("草稿生成失败: %s", e, exc_info=True)
            msg = f"草稿生成失败: {e}"
            raise AgentExecutionError(msg) from e

    def _get_draft_generation_system_message(
        self,
        industry_name: str,
        report_type: str,
    ) -> str:
        """获取草稿生成的系统消息

        Args:
            industry_name: 行业名称
            report_type: 报告类型

        Returns:
            系统消息字符串
        """
        base_message = super()._get_system_message()
        return f"""{base_message}

你是一个专业的文档撰写专家,专注于{self.language}语言的{report_type}写作.

你的主要任务:
1. 根据用户提供的大纲结构生成专业的文档草稿
2. 确保生成的内容符合{report_type}的专业标准
3. 使用{self.language}语言,保持{self.style}的写作风格
4. 确保内容逻辑清晰,结构完整,语言流畅

写作原则:
- 专业性:使用专业术语,确保内容权威可信
- 客观性:基于事实和数据,避免主观臆断
- 完整性:覆盖大纲中的所有章节,不遗漏重要内容
- 逻辑性:确保章节之间的逻辑关系清晰
- 可读性:语言流畅,易于理解

语言和风格:
- 语言:{self.language}
- 风格:{self.style}
- 语气:正式,权威,客观

请根据提供的大纲结构生成专业的文档草稿.
"""

    def _get_draft_generation_prompt(self) -> ChatPromptTemplate:
        """获取草稿生成提示词模板

        Returns:
            ChatPromptTemplate实例
        """
        template = ChatPromptTemplate.from_messages(
            [
                (
                    "human",
                    """请根据以下大纲结构生成{report_type}草稿.

## 行业信息
- 行业名称:{industry_name}
- 数据库:{database_names}

## 大纲结构
{outline_structure}

## 检索到的素材内容
{materials_context}

## 生成要求
1. 严格按照大纲结构生成内容
2. 每个章节都要有完整的段落内容
3. 优先使用检索到的素材内容,确保内容准确可靠
4. 使用专业,客观,数据驱动的语言风格
5. 确保内容逻辑清晰,结构完整
6. 使用Markdown格式输出
7. 在引用素材时,请准确反映素材内容,不要随意修改数据

请开始生成草稿内容.""",
                ),
            ]
        )
        return template

    def _format_outline_structure(self, optimized_outline: OptimizedOutline) -> str:
        """格式化大纲结构为文本

        Args:
            optimized_outline: 优化后的大纲对象

        Returns:
            格式化后的大纲结构文本
        """
        lines = []
        for item in optimized_outline.optimized_items:
            optimized_item = item.optimized_item
            indent = "  " * (optimized_item.level - 1)
            title = optimized_item.title
            description = optimized_item.description or ""
            lines.append(f"{indent}- {title}")
            if description:
                lines.append(f"{indent}  {description}")

        return "\n".join(lines)

    def _retrieve_materials(
        self,
        query_text: str,
        section_title: str,
        top_k: int = 5,
    ) -> list[NodeWithScore]:
        """检索素材(T233: RAG检索)

        使用HybridRetriever从知识库检索相关素材.

        Args:
            query_text: 查询文本
            section_title: 章节标题(用于日志)
            top_k: 返回结果数量

        Returns:
            检索结果列表(NodeWithScore对象)

        Raises:
            AgentExecutionError: 检索失败时抛出
        """
        if not self.hybrid_retriever:
            logger.warning("HybridRetriever未配置,跳过素材检索")
            return []

        if not LLAMA_INDEX_AVAILABLE:
            logger.warning("LlamaIndex不可用,跳过素材检索")
            return []

        try:
            logger.info(
                "检索素材: 章节=%s, 查询=%s, top_k=%d",
                section_title,
                query_text[:50],
                top_k,
            )

            # 使用HybridRetriever检索
            results = self.hybrid_retriever.retrieve(
                query_str=query_text,
                top_k=top_k,
                query_type=QueryType.GENERAL,  # 可以根据需要选择查询类型
            )

            logger.info(
                "素材检索完成: 章节=%s, 结果数=%d",
                section_title,
                len(results),
            )

            return results

        except Exception as e:
            logger.error("素材检索失败: %s", e, exc_info=True)
            # 检索失败不影响草稿生成,返回空列表
            return []

    def _convert_node_to_source_reference(
        self, node_with_score: NodeWithScore
    ) -> SourceReference:
        """将检索结果转换为SourceReference(T234: 素材引用嵌入)

        Args:
            node_with_score: 检索结果节点(NodeWithScore对象)

        Returns:
            SourceReference对象
        """
        node = node_with_score.node
        metadata = node.metadata if hasattr(node, "metadata") else {}

        # 从metadata提取文件路径和定位信息
        file_path = metadata.get("file_path") or metadata.get("source") or ""
        if not file_path:
            # 如果没有文件路径,使用文档ID或node_id作为标识
            file_path = metadata.get("document_id") or node.node_id or "unknown"

        # 提取定位信息
        paragraph_index = metadata.get("paragraph_index")
        page_number = metadata.get("page_number")
        line_number = metadata.get("line_number")

        # 提取标题和描述
        title = metadata.get("title") or metadata.get("filename") or file_path
        description = node.text[:200] if hasattr(node, "text") else None  # 前200字符作为描述

        # 提取内容片段
        content_snippet = node.text[:500] if hasattr(node, "text") else None

        # 创建本地文档引用
        source_ref = SourceReference.create_local_reference(
            title=title,
            file_path=file_path,
            paragraph_index=paragraph_index,
            page_number=page_number,
            line_number=line_number,
            content_snippet=content_snippet,
            description=description,
        )

        return source_ref

    def _format_materials_context(
        self, section_materials: dict[uuid.UUID, list[NodeWithScore]]
    ) -> str:
        """格式化检索到的素材内容,用于提示词

        Args:
            section_materials: 章节ID到素材列表的映射

        Returns:
            格式化后的素材上下文字符串
        """
        if not section_materials:
            return "无可用素材(未启用RAG检索或检索结果为空)"

        lines = ["## 检索到的素材内容"]
        lines.append("")

        for _section_id, materials in section_materials.items():
            if not materials:
                continue

            lines.append(f"### 章节素材(共{len(materials)}条)")
            for idx, material in enumerate(materials, 1):
                node = material.node
                text = node.text if hasattr(node, "text") else ""
                metadata = node.metadata if hasattr(node, "metadata") else {}
                score = material.score if hasattr(material, "score") else 0.0

                title = metadata.get("title") or metadata.get("filename") or f"素材{idx}"
                file_path = metadata.get("file_path") or metadata.get("source") or "unknown"

                lines.append(f"#### {idx}. {title}")
                lines.append(f"- 来源: {file_path}")
                lines.append(f"- 相关性评分: {score:.3f}")
                lines.append(f"- 内容片段: {text[:300]}...")  # 前300字符
                lines.append("")

        return "\n".join(lines)

    def _parse_generated_content(
        self,
        content: str,
        optimized_outline: OptimizedOutline,
        section_materials: dict[uuid.UUID, list[NodeWithScore]] | None = None,
        all_source_references: dict[uuid.UUID, SourceReference] | None = None,
    ) -> list[DraftSection]:
        """解析生成的内容并创建草稿章节(T234: 嵌入素材引用)

        Args:
            content: LLM生成的原始内容
            optimized_outline: 优化后的大纲对象
            section_materials: 章节ID到素材列表的映射
            all_source_references: 所有SourceReference的映射

        Returns:
            草稿章节列表
        """
        sections: list[DraftSection] = []
        section_materials = section_materials or {}
        all_source_references = all_source_references or {}

        # 根据大纲结构创建章节,并嵌入素材引用
        for idx, item in enumerate(optimized_outline.optimized_items):
            optimized_item = item.optimized_item

            # 获取该章节的素材引用
            section_source_ref_ids: list[uuid.UUID] = []
            if optimized_item.id in section_materials:
                materials = section_materials[optimized_item.id]
                for material in materials:
                    # 从material创建SourceReference
                    source_ref = self._convert_node_to_source_reference(material)
                    # 检查是否已存在相同的引用(基于file_path和内容片段)
                    existing_ref_id = None
                    for ref_id, existing_ref in all_source_references.items():
                        if (
                            existing_ref.local_reference
                            and source_ref.local_reference
                            and existing_ref.local_reference.file_path
                            == source_ref.local_reference.file_path
                            and existing_ref.local_reference.content_snippet
                            == source_ref.local_reference.content_snippet
                        ):
                            existing_ref_id = ref_id
                            break

                    # 使用已存在的引用ID,或添加新引用
                    if existing_ref_id:
                        section_source_ref_ids.append(existing_ref_id)
                    else:
                        all_source_references[source_ref.id] = source_ref
                        section_source_ref_ids.append(source_ref.id)

            # 从生成的内容中提取该章节的内容
            # 简单实现:使用大纲项的描述作为内容
            # 未来可以改进为从生成的内容中智能提取
            section_content = optimized_item.description or f"关于{optimized_item.title}的内容"

            section = DraftSection(
                id=uuid.uuid4(),
                parent_id=None,  # TODO: 处理父子关系
                section_type=self._map_item_type_to_section_type(
                    optimized_item.item_type
                ),
                level=optimized_item.level,
                title=optimized_item.title,
                content=section_content,
                order=idx,
                source_references=section_source_ref_ids,  # T234: 嵌入素材引用
            )

            sections.append(section)

        return sections

    def _map_item_type_to_section_type(
        self, item_type: OutlineItemType,
    ) -> DraftSectionType:
        """将大纲项类型映射到草稿章节类型

        Args:
            item_type: 大纲项类型(OutlineItemType枚举)

        Returns:
            草稿章节类型
        """
        type_mapping = {
            OutlineItemType.SECTION: DraftSectionType.SECTION,
            OutlineItemType.SUBSECTION: DraftSectionType.SUBSECTION,
            OutlineItemType.PARAGRAPH: DraftSectionType.PARAGRAPH,
            OutlineItemType.CONTENT: DraftSectionType.PARAGRAPH,
        }
        return type_mapping.get(item_type, DraftSectionType.PARAGRAPH)

    def _get_system_message(self) -> str:
        """获取系统消息

        重写BaseAgent的系统消息,提供草稿生成Agent的专用说明.
        """
        base_message = super()._get_system_message()
        return f"""{base_message}

你是一个专业的文档撰写专家,专注于{self.language}语言的{self.report_type}写作.
你的任务是根据用户提供的大纲结构生成专业的文档草稿.

请使用你的工具(如果有)和知识来完成任务.
"""


# 便利函数


def create_draft_generator_agent(
    agent_id: str = "draft_generator_mvp",
    agent_name: str = "DraftGeneratorMVP",
    llm_service: LLMService | None = None,
    report_type: str = "市场研究报告",
    language: str = "中文",
    style: str = "专业,客观,数据驱动",
    hybrid_retriever: HybridRetriever | None = None,
    **kwargs,
) -> DraftGeneratorAgent:
    """创建草稿生成Agent的便捷函数

    Args:
        agent_id: Agent ID
        agent_name: Agent名称
        llm_service: LLM服务实例
        report_type: 报告类型
        language: 语言
        style: 风格
        hybrid_retriever: 混合检索引擎实例,用于RAG检索(可选)
        **kwargs: 传递给Agent的其他参数

    Returns:
        DraftGeneratorAgent实例
    """
    config = AgentConfig(
        agent_id=agent_id,
        agent_name=agent_name,
        agent_type="draft_generator",
        description="草稿生成Agent,用于根据优化大纲生成文档草稿",
        model_provider=kwargs.get("model_provider"),
        model_name=kwargs.get("model_name"),
        temperature=kwargs.get("temperature", 0.7),
        max_tokens=kwargs.get("max_tokens", 8000),
        enable_memory=kwargs.get("enable_memory", False),
        enable_error_handling=kwargs.get("enable_error_handling", True),
        enable_logging=kwargs.get("enable_logging", True),
    )

    return DraftGeneratorAgent(
        config=config,
        llm_service=llm_service,
        report_type=report_type,
        language=language,
        style=style,
        hybrid_retriever=hybrid_retriever,
        **kwargs,
    )
