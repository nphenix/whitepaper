"""
草稿生成Agent

基于BaseAgent实现的草稿生成Agent,使用LangChain 1.0的Agent框架.
用于MVP 3步流程中的第三步: 草稿生成(带素材追溯链接).

新增功能（2026-01-09）：
- 支持从MD模板读取章节结构（单一数据源）
- 按章节依次生成内容，避免结构混乱
- 支持并发生成和进度回调
- 简化内容解析逻辑

生成命令: /speckit.implement T232, T233, T234
生成时间: 2025-12-25
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool

from src.application.agent_base import AgentConfig, BaseAgent
from src.application.services.citation_embedder import (
    CitationEmbedder,
    CitationFormat,
)
from src.application.services.draft_polisher import DraftPolisher
from src.application.services.outline_to_markdown_service import (
    OutlineToMarkdownService,
    SectionBlueprint,
)
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
        
        # MD模板服务（新增）
        self.outline_to_markdown_service = OutlineToMarkdownService()

        logger.info(
            "初始化DraftGeneratorAgent: %s, 报告类型=%s, 语言=%s, 风格=%s, RAG检索=%s, MD模板=%s",
            self.agent_name,
            self.report_type,
            self.language,
            self.style,
            "启用" if hybrid_retriever else "禁用",
            "启用"
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
        outline_title: str | None = None,
    ) -> Draft:
        """生成草稿

        基于优化后的大纲生成草稿内容.
        当前版本(T232)实现基础框架,具体生成逻辑将在T233中实现.

        Args:
            optimized_outline: 优化后的大纲对象
            industry_name: 行业名称
            database_names: 数据库名称列表
            report_type: 报告类型(如果不指定则使用默认值)
            outline_title: 大纲标题(如果提供,将作为草稿标题;否则使用默认格式)

        Returns:
            生成的草稿对象(Draft)

        Raises:
            AgentExecutionError: 生成失败时抛出
        """
        try:
            logger.info(
                "开始生成草稿: 大纲ID=%s, 行业=%s, 数据库=%s, 大纲标题=%s",
                optimized_outline.id,
                industry_name,
                database_names,
                outline_title,
            )

            # 优先使用MD模板生成（新增逻辑）
            template_path = self._get_markdown_template_path(optimized_outline)
            if template_path and template_path.exists():
                logger.info(
                    "检测到MD模板，优先使用基于模板的生成方式: 模板=%s",
                    template_path
                )
                logger.info(
                    "MD模板驱动生成上下文: optimized_outline_id=%s, original_outline_id=%s, template=%s",
                    optimized_outline.id,
                    optimized_outline.original_outline_id,
                    template_path,
                )
                # generate_draft 是同步方法：要求在“无运行中的 event loop”的线程里调用。
                # 正式 API 路由应通过 asyncio.to_thread(...) 调用该方法（避免阻塞并避免 loop 冲突）。
                try:
                    running_loop = asyncio.get_running_loop()
                except RuntimeError:
                    running_loop = None

                if running_loop is not None:
                    raise RuntimeError(
                        "generate_draft 是同步方法，检测到运行中的事件循环。"
                        "请在工作线程中调用（例如 asyncio.to_thread），"
                        "或在异步上下文中直接 await generate_draft_from_markdown_template(...)。"
                    )

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        self.generate_draft_from_markdown_template(
                            optimized_outline=optimized_outline,
                            industry_name=industry_name,
                            database_names=database_names,
                        )
                    )
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)

            # 使用指定的报告类型或默认值
            report_type = report_type or self.report_type
            database_names = database_names or []

            # 确定草稿标题:优先使用大纲标题,否则使用默认格式
            if outline_title and outline_title.strip():
                draft_title = outline_title.strip()
            else:
                draft_title = f"{industry_name} - {report_type}"

            # 1. 创建草稿对象
            draft = Draft(
                id=uuid.uuid4(),
                title=draft_title,
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
                logger.info(
                    "开始为大纲章节检索素材: 大纲项数量=%d",
                    len(optimized_outline.optimized_items),
                )
                total_sections = len(optimized_outline.optimized_items)
                # 控制 prompt 体量：只给"关键章节"检索/拼接素材，避免每一小节都塞满导致 prompt 膨胀
                # 经验策略：
                # - level<=3（章节/小节/段落）通常最有信息价值
                # - level>=4 数量多且重复度高，不适合直接塞进提示词
                max_material_section_level = 3
                # 每章最多取多少条素材（再多会显著膨胀且信息重复）
                max_materials_per_section = 8
                # 总体字符预算：限制 materials_context 的规模，避免输入过大挤压输出窗口/触发断连
                # 增加到80000以支持更多完整内容，避免截断导致信息丢失
                materials_char_budget = 80000
                used_material_chars = 0
                # 去重：同一段素材可能被多个章节检索到（或同章多条高度相似切块）
                # 用"来源文件路径 + 归一化后的 snippet"做指纹，尽量避免在 prompt 里重复传递。
                seen_material_fingerprints: set[str] = set()

                # 收集行业关键词（从数据库或配置获取，这里使用占位符）
                # 实际项目中应该从 industry_service 获取
                industry_keywords = database_names if database_names else []
                industry_context = " ".join(industry_keywords)

                # 统计各章节的描述长度，用于智能预算分配
                level_1_2_items = [
                    item for item in optimized_outline.optimized_items
                    if int(getattr(item.optimized_item, "level", 99) or 99) <= 2
                ]
                level_1_2_count = len(level_1_2_items)

                for idx, item in enumerate(optimized_outline.optimized_items, 1):
                    optimized_item = item.optimized_item

                    try:
                        # 只对关键章节检索素材
                        item_level = int(getattr(optimized_item, "level", 99) or 99)
                        if item_level > max_material_section_level:
                            section_materials[optimized_item.id] = []
                            continue

                        logger.debug(
                            "检索章节素材 [%d/%d]: 章节ID=%s, 标题='%s', level=%d",
                            idx,
                            total_sections,
                            optimized_item.id,
                            optimized_item.title,
                            item_level,
                        )

                        # 增强查询文本构建（低成本高效果优化）
                        # 策略：用标题 + 描述 + 行业关键词，提高检索精准度
                        query_parts = [optimized_item.title or ""]

                        # 添加描述（如果有）
                        if optimized_item.description:
                            query_parts.append(optimized_item.description)

                        # 添加行业关键词（如果知道）
                        if industry_context:
                            query_parts.append(industry_context)

                        query_text = " ".join(query_parts)

                        # 检索素材
                        materials = self._retrieve_materials(
                            query_text=query_text,
                            section_title=optimized_item.title,
                            top_k=max(3, max_materials_per_section),  # 先多取一点，后面再按预算/评分裁剪
                        )

                        # 只保留每章 top-N（按 score），并做全局字符预算控制
                        try:
                            materials_sorted = sorted(
                                materials,
                                key=lambda m: float(getattr(m, "score", 0.0) or 0.0),
                                reverse=True,
                            )
                        except Exception:
                            materials_sorted = materials

                        selected: list[NodeWithScore] = []
                        for m in materials_sorted:
                            node = getattr(m, "node", None)
                            text = getattr(node, "text", "") if node is not None else ""
                            score = float(getattr(m, "score", 0.0) or 0.0)
                            
                            # 过滤：不要把图表/表格结构化补充段落传入草稿生成 prompt
                            snippet_lc = (text or "").lower()
                            if (
                                "结构化数据补充" in text
                                or "## 结构化数据补充" in text
                                or "## 图表数据" in text
                                or "## 表格数据" in text
                                or "图表数据" in text
                                or "表格数据" in text
                                or "chart data" in snippet_lc
                                or "table data" in snippet_lc
                            ):
                                continue

                            # 去重指纹（跨章节/同章节）
                            try:
                                metadata = getattr(node, "metadata", {}) if node is not None else {}
                                file_path = str(
                                    (metadata or {}).get("file_path")
                                    or (metadata or {}).get("source")
                                    or (metadata or {}).get("document_id")
                                    or ""
                                )
                            except Exception:
                                file_path = ""

                            # 归一化：压缩空白、去掉常见标点，降低"同一段落不同切块边界"造成的重复
                            normalized = "".join((text or "")[:500].split()).lower()
                            normalized = normalized[:200]  # 避免指纹过大
                            fingerprint = f"{file_path}::{normalized}"
                            if fingerprint in seen_material_fingerprints:
                                continue

                            # 智能预算估算：基于相关性分数动态调整
                            # 高相关性内容（>0.7）给予更多预算，低相关性内容精简
                            if score > 0.7:
                                estimated_length = min(len(text or ""), 2500)
                            elif score > 0.5:
                                estimated_length = min(len(text or ""), 2000)
                            else:
                                estimated_length = min(len(text or ""), 1500)
                            
                            # 固定字段开销（标题/来源/评分/换行等）
                            estimated = estimated_length + 200
                            
                            # 动态预算控制：优先保留高相关性内容
                            # 如果预算不足，尝试移除低相关性内容为新内容腾出空间
                            if used_material_chars + estimated > materials_char_budget:
                                # 如果当前内容相关性很高（>0.7），尝试移除已选中的低相关性内容
                                if score > 0.7 and selected:
                                    # 查找已选中内容中相关性最低的
                                    low_score_items = [
                                        (i, s) for i, s in enumerate(selected)
                                        if float(getattr(s, "score", 0.0) or 0.0) < 0.5
                                    ]
                                    if low_score_items:
                                        # 移除最低相关性的项目
                                        low_score_items.sort(
                                            key=lambda x: float(getattr(x[1], "score", 0.0) or 0.0)
                                        )
                                        removed = selected.pop(low_score_items[0][0])
                                        # 重新计算已用预算（简化处理，使用平均值）
                                        used_material_chars = int(used_material_chars * 0.9)
                                        logger.debug(
                                            "为高相关性内容腾出空间，移除低相关性素材: score=%.3f",
                                            float(getattr(removed, "score", 0.0) or 0.0)
                                        )
                                    
                                    # 如果移除后仍不够，跳过
                                    if used_material_chars + estimated > materials_char_budget:
                                        logger.debug(
                                            "素材预算不足，跳过剩余素材: 已用=%d, 预算=%d, 当前素材估算=%d, score=%.3f",
                                            used_material_chars, materials_char_budget, estimated, score
                                        )
                                        break
                                else:
                                    logger.debug(
                                        "素材预算不足，跳过剩余素材: 已用=%d, 预算=%d, 当前素材估算=%d, score=%.3f",
                                        used_material_chars, materials_char_budget, estimated, score
                                    )
                                    break
                            
                            selected.append(m)
                            used_material_chars += estimated
                            seen_material_fingerprints.add(fingerprint)
                            if len(selected) >= max_materials_per_section:
                                break

                        section_materials[optimized_item.id] = selected

                        # 将检索结果转换为SourceReference
                        source_ref_count = 0
                        for material in selected:
                            try:
                                source_ref = self._convert_node_to_source_reference(
                                    material
                                )
                                all_source_references[source_ref.id] = source_ref
                                source_ref_count += 1
                            except Exception as e:
                                logger.warning(
                                    "转换素材为SourceReference失败: 章节='%s', 错误=%s",
                                    optimized_item.title,
                                    e,
                                )
                                # 继续处理其他素材，不中断流程

                        logger.info(
                            "章节 '%s' 检索完成: 素材数=%d, 引用数=%d",
                            optimized_item.title,
                            len(selected),
                            source_ref_count,
                        )
                    except Exception as e:
                        logger.error(
                            "章节 '%s' 检索素材失败: %s",
                            optimized_item.title,
                            e,
                            exc_info=True,
                        )
                        # 检索失败不影响草稿生成，继续处理下一个章节
                        section_materials[optimized_item.id] = []

                logger.info(
                    "大纲章节素材检索完成: 总章节数=%d, 成功章节数=%d, 总引用数=%d",
                    total_sections,
                    len([m for m in section_materials.values() if m]),
                    len(all_source_references),
                )
                logger.info(
                    "RAG素材 prompt 预算统计: materials_char_budget=%d, used_estimated_chars=%d, max_level=%d, max_per_section=%d",
                    materials_char_budget,
                    used_material_chars,
                    max_material_section_level,
                    max_materials_per_section,
                )
            else:
                logger.warning("HybridRetriever未配置，跳过素材检索")

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

            logger.info("开始调用LLM生成草稿内容...")
            try:
                # 重要：不要再用 ChatPromptTemplate.from_messages(messages) 包装已渲染的文本。
                # 因为 materials_context / outline_structure 里可能包含类似 "{C}"、"{\\circ}" 的花括号内容
                # （例如 LaTeX 或表格），LangChain 会把它们当成模板变量，导致 KeyError。
                #
                # 这里直接用 BaseMessage 列表调用模型，完全绕开模板解析。
                from langchain_core.messages import HumanMessage, SystemMessage

                lc_messages = []
                for m in messages:
                    role = (m.get("role") or "").lower()
                    content = m.get("content") or ""
                    if role == "system":
                        lc_messages.append(SystemMessage(content=content))
                    else:
                        lc_messages.append(HumanMessage(content=content))

                # 关键修复：
                # 1) 显式传递 max_tokens（使用 AgentConfig 的 max_tokens，而不是全局 LLM_MAX_TOKENS）
                # 2) 使用 stream() 以避免长耗时请求在上游空等期间被断连
                max_tokens_override = int(getattr(self.config, "max_tokens", 8000) or 8000)
                logger.info(
                    "执行LLM流式消息调用(无模板解析): max_tokens=%d",
                    max_tokens_override,
                )

                generated_chunks: list[str] = []
                for chunk in self.model.stream(lc_messages, max_tokens=max_tokens_override):
                    # ChatModel.stream 通常返回 AIMessageChunk，含 content 属性
                    chunk_text = getattr(chunk, "content", None)
                    if chunk_text:
                        generated_chunks.append(chunk_text)

                generated_content = "".join(generated_chunks)

                if not generated_content or not isinstance(generated_content, str):
                    logger.warning(
                        "LLM返回内容格式异常: type=%s, content_length=%s",
                        type(generated_content),
                        len(str(generated_content)) if generated_content else 0,
                    )
                    generated_content = str(generated_content) if generated_content else ""

                logger.info(
                    "LLM生成草稿内容完成: 长度=%d字符, 前100字符='%s'",
                    len(generated_content),
                    generated_content[:100] if generated_content else "",
                )
            except Exception as e:
                logger.error("LLM生成草稿内容失败: %s", e, exc_info=True)
                raise AgentExecutionError(f"LLM生成草稿内容失败: {e}") from e

            # 9. 解析生成的内容并创建草稿章节(T234: 嵌入素材引用)
            logger.info("开始解析生成的内容并创建草稿章节...")
            try:
                sections = self._parse_generated_content(
                    content=generated_content,
                    optimized_outline=optimized_outline,
                    section_materials=section_materials,
                    all_source_references=all_source_references,
                )

                logger.debug("内容解析完成: 生成章节数=%d", len(sections))

                # 9.5 基于RAG召回的素材元数据，自动注入图片/图表占位符（不依赖大模型决定位置）
                # 收集源文档路径用于加载图片名称映射
                source_documents: list[dict[str, Any]] = []
                seen_doc_paths: set[str] = set()
                for materials in section_materials.values():
                    for m in materials:
                        node = getattr(m, "node", None)
                        meta = getattr(node, "metadata", {}) if node else {}
                        doc_path = meta.get("file_path") or meta.get("source") or ""
                        if doc_path and doc_path not in seen_doc_paths:
                            seen_doc_paths.add(doc_path)
                            source_documents.append({"file_path": doc_path})

                rag_media_manifest = self._inject_rag_media_placeholders(
                    sections=sections,
                    section_materials=section_materials,
                    source_documents=source_documents if source_documents else None,
                )

                # 9.6 清理LLM生成的错误图片占位符（只保留 _inject_rag_media_placeholders 注入的正确占位符）
                # 收集所有正确的占位符文件名（从manifest中）
                valid_figure_names: set[str] = set()
                if rag_media_manifest:
                    for item in rag_media_manifest:
                        if isinstance(item, dict):
                            figure_name = item.get("figure_name")
                            json_file = item.get("json_file")
                            if figure_name:
                                valid_figure_names.add(figure_name)
                            if json_file:
                                valid_figure_names.add(json_file)
                
                # 清理所有不在valid_figure_names中的图片占位符
                import re
                placeholder_pattern = re.compile(r"\[\[IMAGE:([^\]]+)\]\]")
                cleaned_count = 0
                for section in sections:
                    if not section.content:
                        continue
                    # 查找所有占位符
                    matches = list(placeholder_pattern.finditer(section.content))
                    for match in reversed(matches):  # 从后往前删除，避免索引变化
                        placeholder_filename = match.group(1).strip()
                        # 检查是否在有效列表中
                        if placeholder_filename not in valid_figure_names:
                            # 移除这个占位符（包括前后可能的换行）
                            start_pos = match.start()
                            end_pos = match.end()
                            # 尝试移除占位符前后的空白和换行
                            before = section.content[:start_pos].rstrip()
                            after = section.content[end_pos:].lstrip()
                            # 如果前后都是换行，保留一个换行
                            if before and after:
                                section.content = before + "\n" + after
                            elif before:
                                section.content = before + after
                            elif after:
                                section.content = before + after
                            else:
                                section.content = before + after
                            cleaned_count += 1
                            logger.debug(
                                "清理LLM生成的错误占位符: %s (不在manifest中)",
                                placeholder_filename
                            )
                
                if cleaned_count > 0:
                    logger.info(
                        "清理LLM生成的错误图片占位符完成: 清理数量=%d, 保留的有效占位符=%d",
                        cleaned_count,
                        len(valid_figure_names),
                    )

                # 兜底：如果解析未生成任何章节（例如 optimized_items 为空），
                # 仍然把完整生成内容作为一个章节写入，确保前端/测试能拿到完整草稿文本。
                if not sections and isinstance(generated_content, str) and generated_content.strip():
                    logger.warning(
                        "解析未生成任何章节，使用兜底方案：将完整内容作为单个章节"
                    )
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
                # 策略：确保父级章节在子章节之前添加
                # 使用拓扑排序：先添加所有根章节，再递归添加子章节
                
                # 构建 id -> section 映射
                section_by_id = {s.id: s for s in sections}
                
                # 分离根章节和子章节
                root_sections = [s for s in sections if s.parent_id is None]
                child_sections = [s for s in sections if s.parent_id is not None]
                
                # 根章节按 level 和 order 排序
                root_sections_sorted = sorted(
                    root_sections, 
                    key=lambda s: (s.level or 0, s.order or 0)
                )
                
                # 为子章节创建排序键：递归收集父级链
                def get_sort_key(section: DraftSection) -> tuple:
                    """生成排序键：先按父级链深度，再按父级顺序，最后按自身顺序"""
                    # 递归收集父级链的顺序值
                    parent_orders = []
                    current = section
                    while current.parent_id and current.parent_id in section_by_id:
                        parent = section_by_id[current.parent_id]
                        parent_orders.append(parent.order or 0)
                        current = parent
                    # 倒序排列，使得最近的父级在比较时优先级更高
                    parent_orders = list(reversed(parent_orders))
                    # 如果没有父级链，返回一个很大的值使其排在根章节之后
                    depth = len(parent_orders)
                    return (depth, parent_orders, section.level or 0, section.order or 0)
                
                # 子章节按排序键排序
                child_sections_sorted = sorted(
                    child_sections,
                    key=get_sort_key
                )
                
                # 合并：先根章节，后子章节
                sorted_sections = root_sections_sorted + child_sections_sorted
                
                # 统计信息
                root_count = len(root_sections_sorted)
                child_count = len(child_sections_sorted)
                logger.debug(
                    "章节排序完成: 根章节=%d, 子章节=%d",
                    root_count, child_count
                )
                
                for idx, section in enumerate(sorted_sections, 1):
                    try:
                        draft.add_section(section)
                        logger.debug(
                            "添加章节 [%d/%d]: type=%s, title='%s'%s",
                            idx,
                            len(sorted_sections),
                            getattr(section.section_type, "value", section.section_type),
                            section.title or "无标题",
                            f", parent={section.parent_id}" if section.parent_id else ""
                        )
                    except Exception as e:
                        logger.error(
                            "添加章节失败: 章节索引=%d, 错误=%s",
                            idx,
                            e,
                            exc_info=True,
                        )
                        # 继续处理其他章节，不中断流程

                logger.info("草稿章节创建完成: 总章节数=%d", len(draft.sections))
                if rag_media_manifest:
                    draft.add_metadata("rag_media_manifest", rag_media_manifest)
            except Exception as e:
                logger.error("解析生成内容并创建章节失败: %s", e, exc_info=True)
                raise AgentExecutionError(f"解析生成内容并创建章节失败: {e}") from e

            # 11. 嵌入引用信息(T087: 实现引用信息嵌入功能)
            logger.info("开始嵌入引用信息: 引用数=%d", len(all_source_references))
            try:
                citation_embedder = CitationEmbedder(
                    citation_format=CitationFormat.BRACKET
                )
                draft = citation_embedder.embed_citations_in_draft(
                    draft=draft,
                    source_references=all_source_references,
                )
                logger.info("引用信息嵌入完成: 引用数=%d", len(all_source_references))
            except Exception as e:
                logger.error("嵌入引用信息失败: %s", e, exc_info=True)
                # 引用嵌入失败不影响草稿生成，继续流程
                logger.warning("引用信息嵌入失败，继续生成草稿（不含引用标记）")

            # 11.5 回填 draft.database_ids（用于后续加载 rag_media_manifest / 图片映射）
            # 说明：
            # - 现网问题：MVP 版 Draft 创建时 database_ids 写死为 []，导致 HTML 导出阶段无法根据文档ID加载 manifest，
            #   从而“正文引用图片 ↔ 图转JSON/附录”无法严格对齐。
            # - 规则：从 SourceReference.local_reference.file_path 中提取 UUID（该字段在本地引用里常被写入 doc_id）。
            try:
                import uuid

                extracted: list[uuid.UUID] = []
                seen: set[str] = set()
                for ref in all_source_references.values():
                    lr = getattr(ref, "local_reference", None)
                    fp = getattr(lr, "file_path", None) if lr else None
                    if not fp:
                        continue
                    try:
                        doc_id = uuid.UUID(str(fp))
                    except Exception:
                        continue
                    s = str(doc_id)
                    if s in seen:
                        continue
                    seen.add(s)
                    extracted.append(doc_id)

                if extracted:
                    draft.database_ids = extracted
                    logger.info(
                        "已从source_references回填draft.database_ids: count=%d",
                        len(extracted),
                    )
            except Exception as e:
                logger.debug("回填draft.database_ids失败(不影响主流程): %s", e)

            # 12. 润色草稿(T088: 实现基础润色功能,作为最终合成步骤)
            enable_polish = bool(self.config.get("enable_polish", False))
            if enable_polish:
                logger.info("开始润色草稿(enable_polish=True): 章节数=%d", len(draft.sections))
                try:
                    polisher = DraftPolisher(
                        llm_service=self.llm_service,
                        language=self.language,
                        style=self.style,
                    )
                    batch_size = int(self.config.get("polish_batch_size", 1) or 1)
                    draft = polisher.polish_draft(
                        draft=draft,
                        polish_sections=True,
                        polish_whole=False,
                        batch_size=max(1, batch_size),
                    )
                    logger.info("草稿润色完成: 章节数=%d", len(draft.sections))
                except Exception as e:
                    logger.error("润色草稿失败: %s", e, exc_info=True)
                    # 润色失败不影响草稿生成，继续流程
                    logger.warning("草稿润色失败，使用原始草稿内容")
            else:
                logger.info("跳过草稿润色(enable_polish=False)")

            # 13. 更新草稿状态
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
        """获取草稿生成的系统消息"""
        base_message = super()._get_system_message()
        return f"""{base_message}

你是一个顶级的白皮书撰写专家。你的任务是根据大纲和检索素材生成深度专业报告。

## 极其重要：输出规范
1. **禁止**任何开场白（如“好的”、“生成如下”）。
2. **禁止**任何结尾语、总结或润色说明。
3. **只输出正文内容**。
4. **禁止输出文档的总标题和总描述**，系统会自动添加。直接从第一个章节标题（如 `## 第一章 xxx`）开始输出。
5. **严禁插入任何占位符**：**严禁**在内容中插入任何 `[[IMAGE:...]]` 或 `[[CHART:...]]` 占位符。所有图片和图表占位符将由系统根据知识库中的实际资源自动注入。

语言：{self.language}
风格：{self.style}
"""

    def _get_draft_generation_prompt(self) -> ChatPromptTemplate:
        """获取草稿生成提示词模板"""
        template = ChatPromptTemplate.from_messages(
            [
                (
                    "human",
                    """请根据以下检索到的素材内容，生成{report_type}草稿。

## 行业信息
- 行业名称:{industry_name}

## 大纲结构
{outline_structure}

## 检索到的素材内容（必须深度利用并扩写）
{materials_context}

## 强制要求
1. **严禁输出开场白和结束语**。
2. **严禁重复输出文档总标题**。直接从章节内容开始。
3. **深度扩写**：每个章节必须基于素材进行详尽分析，包含数据支持和逻辑推导。
4. **严禁插入占位符**：**严禁**在内容中插入任何 `[[IMAGE:...]]` 或 `[[CHART:...]]` 占位符。所有图片和图表占位符将由系统根据知识库中的实际资源自动注入。
5. **内联引用**：格式为 [来源:文件名]。
6. **字数限制**：每个章节建议不少于 500 字。

请开始输出报告正文：""",
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
                "检索素材: 章节='%s', 查询='%s', top_k=%d",
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

            if not results:
                logger.warning(
                    "素材检索结果为空: 章节='%s', 查询='%s'",
                    section_title,
                    query_text[:50],
                )
            else:
                # 记录检索结果的详细信息
                scores = [r.score for r in results if hasattr(r, "score")]
                avg_score = sum(scores) / len(scores) if scores else 0.0
                logger.info(
                    "素材检索完成: 章节='%s', 结果数=%d, 平均相关性评分=%.3f",
                    section_title,
                    len(results),
                    avg_score,
                )
                logger.debug(
                    "检索结果详情: 章节='%s', 前3个结果评分=%s",
                    section_title,
                    [f"{r.score:.3f}" for r in results[:3] if hasattr(r, "score")],
                )

            return results

        except Exception as e:
            logger.error(
                "素材检索失败: 章节='%s', 查询='%s', 错误=%s",
                section_title,
                query_text[:50],
                e,
                exc_info=True,
            )
            # 检索失败不影响草稿生成,返回空列表
            logger.warning(
                "素材检索失败，继续生成草稿（不含该章节的检索素材）: 章节='%s'",
                section_title,
            )
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

        # 从metadata提取文件路径/文件名：目标是“引用里显示原始文件名”，避免 knowledge_base_service 等内部标识。
        file_path = metadata.get("file_path") or ""
        filename = metadata.get("filename") or metadata.get("document_title") or ""

        # 兼容旧索引：metadata 里可能只有 source=knowledge_base_service / document_id
        if (not filename) and isinstance(metadata.get("document_id"), str):
            doc_id = str(metadata.get("document_id") or "").strip()
            if doc_id:
                try:
                    from src.infrastructure.storage.sqlite.connection import get_connection_manager

                    cm = get_connection_manager()
                    with cm.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT filename, file_path FROM documents WHERE id = ?", (doc_id,))
                        row = cur.fetchone()
                        if row:
                            filename = filename or (row[0] or "")
                            file_path = file_path or (row[1] or "")
                except Exception:
                    pass

        # file_path 为空时，最后才用 source（有时是内部标识）
        if not file_path:
            src = metadata.get("source") or ""
            if isinstance(src, str) and src.strip() and src.strip() != "knowledge_base_service":
                file_path = src.strip()

        # 若仍没有可展示路径，用 filename 或 doc_id/node_id 兜底
        if not file_path:
            file_path = filename or metadata.get("document_id") or node.node_id or "未知文档"

        # 提取定位信息
        paragraph_index = metadata.get("paragraph_index")
        page_number = metadata.get("page_number")
        line_number = metadata.get("line_number")

        # 提取标题和描述
        # 优先使用从clean_content_list.json text_level=1提取的标题
        title = (
            metadata.get("document_title_from_content")  # 从text_level=1提取的标题
            or metadata.get("title")
            or metadata.get("document_title")  # 文档级标题
            or metadata.get("filename")
            or "未知文档"  # 不再使用file_path作为fallback
        )
        
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

    def _extract_key_content(
        self,
        text: str,
        query_keywords: list[str],
        max_length: int = 2000,
    ) -> str:
        """智能提取关键内容片段
        
        基于查询关键词和内容重要性，智能选择最相关的段落，而不是简单截断。
        
        Args:
            text: 原始文本内容
            query_keywords: 查询关键词列表（用于定位相关段落）
            max_length: 最大长度限制
            
        Returns:
            提取的关键内容片段
        """
        if not text or len(text) <= max_length:
            return text
        
        # 1. 优先提取包含关键词的段落
        import re
        paragraphs = re.split(r'[。\n]+', text)
        keyword_paragraphs = []
        other_paragraphs = []
        
        keywords_lower = [kw.lower() for kw in query_keywords if kw]
        
        for para in paragraphs:
            if not para.strip():
                continue
            para_lower = para.lower()
            # 检查是否包含关键词
            has_keyword = any(kw in para_lower for kw in keywords_lower)
            if has_keyword:
                keyword_paragraphs.append(para)
            else:
                other_paragraphs.append(para)
        
        # 2. 优先选择包含关键词的段落
        selected_paragraphs = []
        current_length = 0
        
        # 先添加包含关键词的段落
        for para in keyword_paragraphs:
            para_with_punct = para + "。"
            if current_length + len(para_with_punct) <= max_length:
                selected_paragraphs.append(para)
                current_length += len(para_with_punct)
            else:
                # 如果还有空间，尝试截取部分
                remaining = max_length - current_length
                if remaining > 100:  # 至少保留100字符才有意义
                    selected_paragraphs.append(para[:remaining] + "...")
                break
        
        # 3. 如果还有空间，添加其他段落（按位置优先，开头和结尾通常更重要）
        if current_length < max_length:
            # 优先选择开头和结尾的段落
            priority_indices = []
            if other_paragraphs:
                # 开头段落
                priority_indices.append(0)
                # 结尾段落
                if len(other_paragraphs) > 1:
                    priority_indices.append(len(other_paragraphs) - 1)
                # 中间段落
                if len(other_paragraphs) > 2:
                    mid = len(other_paragraphs) // 2
                    priority_indices.append(mid)
            
            for idx in priority_indices:
                if idx < len(other_paragraphs):
                    para = other_paragraphs[idx]
                    para_with_punct = para + "。"
                    if current_length + len(para_with_punct) <= max_length:
                        if para not in selected_paragraphs:
                            selected_paragraphs.append(para)
                            current_length += len(para_with_punct)
                    else:
                        remaining = max_length - current_length
                        if remaining > 100:
                            selected_paragraphs.append(para[:remaining] + "...")
                        break
        
        result = "。".join(selected_paragraphs)
        if len(result) < len(text):
            result += "..."
        
        return result[:max_length]
    
    def _format_materials_context(
        self, section_materials: dict[uuid.UUID, list[NodeWithScore]]
    ) -> str:
        """格式化检索到的素材内容,用于提示词

        使用智能内容提取，基于相关性分数和关键词匹配选择关键内容，
        而不是简单的字符截断。

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
                
                # 提取图片/图表信息
                image_info = metadata.get("image_path") or metadata.get("original_image") or ""
                chart_info = metadata.get("chart_id") or ""

                lines.append(f"#### {idx}. {title}")
                lines.append(f"- 来源: {file_path}")
                if image_info:
                    lines.append(f"- 关联图片文件名: {Path(image_info).name}")
                if chart_info:
                    lines.append(f"- 关联图表ID: {chart_info}")
                lines.append(f"- 相关性评分: {score:.3f}")
                
                # 智能提取关键内容：基于相关性分数动态调整长度
                # 高相关性（>0.7）使用更长片段，低相关性使用较短片段
                if score > 0.7:
                    max_content_length = 2500  # 高相关性内容保留更多
                elif score > 0.5:
                    max_content_length = 2000  # 中等相关性
                else:
                    max_content_length = 1500  # 低相关性内容精简
                
                # 从metadata中提取可能的查询关键词
                query_keywords = []
                if metadata.get("section_title"):
                    query_keywords.append(metadata["section_title"])
                if title and title != f"素材{idx}":
                    # 从标题中提取关键词
                    import re
                    keywords = re.findall(r'[\u4e00-\u9fa5]{2,}', title)
                    query_keywords.extend(keywords)
                
                # 使用智能提取而不是简单截断
                content_preview = self._extract_key_content(
                    text=text,
                    query_keywords=query_keywords,
                    max_length=max_content_length,
                )
                
                lines.append(f"- 内容片段: {content_preview}")
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
        import re
        from typing import Optional
        
        sections: list[DraftSection] = []
        section_materials = section_materials or {}
        all_source_references = all_source_references or {}

        logger.info("开始解析LLM生成的草稿内容: 原始内容长度=%d字符", len(content))

        # 构建大纲标题到optimized_item的映射
        outline_item_map: dict[str, uuid.UUID] = {}
        title_variants: dict[str, uuid.UUID] = {}  # 标题变体映射
        for item in optimized_outline.optimized_items:
            optimized_item = item.optimized_item
            if optimized_item.title:
                # 原始标题
                outline_item_map[optimized_item.title] = optimized_item.id
                # 去除编号的标题变体（如"第一章：执行摘要" -> "执行摘要"）
                clean_title = re.sub(r'^[\d一二三四五六七八九十]+[、：:.\s]*', '', optimized_item.title).strip()
                if clean_title and clean_title != optimized_item.title:
                    title_variants[clean_title] = optimized_item.id
                # 带书名号的标题变体
                if optimized_item.title.startswith('《') and optimized_item.title.endswith('》'):
                    title_variants[optimized_item.title[1:-1]] = optimized_item.id

        # 解析Markdown标题结构
        # 支持多种标题格式: ## 标题, ### 标题, #### 标题
        section_pattern = re.compile(
            r'^(#{1,6})\s+(.+?)$',
            re.MULTILINE
        )

        # 查找所有标题位置
        title_positions: list[tuple[int, int, str, int]] = []  # (start, end, title, level)
        for match in section_pattern.finditer(content):
            title = match.group(2).strip()
            level = len(match.group(1))
            title_positions.append((match.start(), match.end(), title, level))

        logger.info("从生成内容中提取到 %d 个标题", len(title_positions))

        # 已使用的标题集合（用于去重）
        used_titles: set[str] = set()

        # 检测生成内容中的重复标题
        title_occurrences: dict[str, int] = {}
        for _, _, title, _ in title_positions:
            title_occurrences[title] = title_occurrences.get(title, 0) + 1

        # 标记重复的标题
        duplicate_titles = {title for title, count in title_occurrences.items() if count > 1}
        if duplicate_titles:
            logger.warning(
                "检测到生成内容中%d个标题重复出现: %s",
                len(duplicate_titles), list(duplicate_titles)[:5]
            )

        # 为每个大纲项尝试找到对应的生成内容
        # 建立大纲项ID到章节ID的映射，用于正确建立父子关系
        outline_to_section_id: dict[uuid.UUID, uuid.UUID] = {}
        
        for idx, item in enumerate(optimized_outline.optimized_items):
            optimized_item = item.optimized_item
            item_title = optimized_item.title or ""

            # 获取该章节的素材引用
            section_source_ref_ids: list[uuid.UUID] = []
            if optimized_item.id in section_materials:
                materials = section_materials[optimized_item.id]
                for material in materials:
                    source_ref = self._convert_node_to_source_reference(material)
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
                    if existing_ref_id:
                        section_source_ref_ids.append(existing_ref_id)
                    else:
                        all_source_references[source_ref.id] = source_ref
                        section_source_ref_ids.append(source_ref.id)

            # 尝试从生成内容中提取对应章节
            section_content: Optional[str] = None
            matched_title: Optional[str] = None

            # 方法1: 精确匹配标题
            if item_title in outline_item_map:
                for pos_idx, (start, end, title, level) in enumerate(title_positions):
                    # 跳过已经使用过的标题（去重）
                    if title in used_titles:
                        continue
                    if title == item_title:
                        # 找到下一个标题的开始位置作为当前章节的结束
                        if pos_idx + 1 < len(title_positions):
                            section_end = title_positions[pos_idx + 1][0]
                        else:
                            section_end = len(content)
                        section_content = content[end:section_end].strip()
                        matched_title = title
                        used_titles.add(title)  # 标记标题已使用
                        break

            # 方法2: 匹配标题变体
            if not section_content and item_title in title_variants:
                variant_title = re.sub(r'^[\d一二三四五六七八九十]+[、：:.\s]*', '', item_title).strip()
                for pos_idx, (start, end, title, level) in enumerate(title_positions):
                    # 跳过已经使用过的标题（去重）
                    if title in used_titles:
                        continue
                    if title == variant_title or title == item_title[1:-1] if (item_title.startswith('《') and item_title.endswith('》')) else False:
                        if pos_idx + 1 < len(title_positions):
                            section_end = title_positions[pos_idx + 1][0]
                        else:
                            section_end = len(content)
                        section_content = content[end:section_end].strip()
                        matched_title = title
                        used_titles.add(title)  # 标记标题已使用
                        break

            # 方法3: 模糊匹配（在标题列表中查找相似的）
            if not section_content:
                for pos_idx, (start, end, title, level) in enumerate(title_positions):
                    # 跳过已经使用过的标题（去重）
                    if title in used_titles:
                        continue
                    # 检查生成内容的标题是否包含大纲项标题的核心词
                    item_keywords = set(re.findall(r'[\w]+', item_title))
                    title_keywords = set(re.findall(r'[\w]+', title))
                    overlap = item_keywords & title_keywords
                    # 如果核心词有50%以上重叠
                    if len(item_keywords) > 0 and len(overlap) / len(item_keywords) >= 0.5:
                        if pos_idx + 1 < len(title_positions):
                            section_end = title_positions[pos_idx + 1][0]
                        else:
                            section_end = len(content)
                        section_content = content[end:section_end].strip()
                        matched_title = title
                        used_titles.add(title)  # 标记标题已使用
                        break

            # 方法4: 降级使用描述（仅当其他方法都失败时）
            if not section_content:
                # 尝试从生成内容中找到包含章节关键词的段落
                keywords = re.findall(r'[\w]{2,}', item_title)
                for keyword in keywords:
                    if len(keyword) < 2:
                        continue
                    keyword_pattern = re.escape(keyword)
                    keyword_matches = list(re.finditer(keyword_pattern, content, re.IGNORECASE))
                    for match in keyword_matches:
                        # 找到关键词周围的上下文
                        start = max(0, match.start() - 100)
                        end = min(len(content), match.end() + 500)
                        context = content[start:end]
                        # 检查是否是段落级别的内容
                        if len(context) > 200 and '。' in context:
                            section_content = context
                            break
                    if section_content:
                        break

            # 如果所有方法都失败，使用原始描述作为fallback
            if not section_content or len(section_content.strip()) < 50:
                logger.warning(
                    "未能为章节 '%s' 找到生成的内容，使用大纲描述（长度=%d）",
                    item_title,
                    len(optimized_item.description or "") if optimized_item.description else 0
                )
                section_content = optimized_item.description or f"关于{item_title}的内容"

            # 创建章节
            section = DraftSection(
                id=uuid.uuid4(),
                # 使用大纲项ID映射到已创建的章节ID，确保父子关系正确
                parent_id=outline_to_section_id.get(optimized_item.parent_id) if optimized_item.parent_id else None,
                section_type=self._map_item_type_to_section_type(
                    optimized_item.item_type
                ),
                level=optimized_item.level,
                title=optimized_item.title,
                content=section_content,
                order=idx,
                source_references=section_source_ref_ids,
                metadata={
                    "outline_item_id": str(optimized_item.id),
                    "outline_item_level": int(optimized_item.level or 1),
                },
            )

            # 章节标题去重：如果已存在相同标题的章节，则跳过
            existing_titles = {s.title for s in sections if s.title}
            if section.title and section.title in existing_titles:
                logger.warning("跳过重复章节: '%s'", section.title)
                continue

            # 额外检查：标题是否在生成内容中重复出现（检测生成内容中的章节重复）
            # 统计生成内容中该标题出现的次数
            content_title_count = content.count(section.title) if section.title else 0
            if section.title and content_title_count > 1:
                logger.warning(
                    "检测到生成内容中章节标题'%s'重复出现%d次，保留第一个",
                    section.title, content_title_count
                )
                # 仍然保留这个章节，因为可能是有意重复的

            sections.append(section)
            
            # 建立大纲项ID到章节ID的映射，用于后续子章节的parent_id引用
            outline_to_section_id[optimized_item.id] = section.id

            if matched_title:
                logger.debug("成功匹配章节: '%s' -> '%s', 内容长度=%d",
                    item_title, matched_title, len(section_content))

        # 检查内容完整性：识别内容过少的章节
        min_content_length = 200  # 最少内容长度阈值
        empty_or_minimal_sections = []
        for section in sections:
            content_length = len(section.content) if section.content else 0
            # 检查是否是仅包含列表或描述的"假内容"
            is_bullet_list_only = (
                section.content.strip().startswith("- ") or
                section.content.strip().startswith("* ") or
                section.content.strip().startswith("• ")
            )
            is_fallback_content = (
                section.content.startswith("关于") and
                section.content.endswith("的内容")
            )

            if content_length < min_content_length or is_fallback_content:
                empty_or_minimal_sections.append({
                    "title": section.title,
                    "content_length": content_length,
                    "is_bullet_list_only": is_bullet_list_only,
                    "is_fallback_content": is_fallback_content,
                })

        if empty_or_minimal_sections:
            logger.warning(
                "发现 %d 个内容不足的章节，开始补充内容: %s",
                len(empty_or_minimal_sections),
                [s["title"] for s in empty_or_minimal_sections]
            )
            
            # 获取可用于补充的上下文内容
            context_content = self._get_supplement_context(optimized_outline)
            
            # 为每个需要补充的章节生成内容
            for section in sections:
                for empty_info in empty_or_minimal_sections:
                    if section.title == empty_info["title"]:
                        # 获取outline_item_id用于从section_materials中提取素材
                        outline_item_id = None
                        if section.metadata and "outline_item_id" in section.metadata:
                            try:
                                outline_item_id = uuid.UUID(str(section.metadata["outline_item_id"]))
                            except Exception:
                                pass

                        # 生成补充内容
                        new_content = self._supplement_section_content(
                            section_title=section.title,
                            subsection_list=[],  # 可以从大纲中获取子节信息
                            context_content=context_content,
                            section_materials=section_materials,
                            outline_item_id=outline_item_id,
                        )

                        if new_content:
                            section.content = new_content
                            logger.info(
                                "成功补充章节内容: '%s', 新内容长度=%d",
                                section.title, len(new_content)
                            )
                        break

        logger.info("草稿内容解析完成: 生成%d个章节, 其中%d个需要补充内容",
            len(sections), len(empty_or_minimal_sections))
        return sections

    def _get_supplement_context(self, optimized_outline: OptimizedOutline) -> str:
        """
        获取可用于补充内容的上下文信息
        
        Args:
            optimized_outline: 优化后的大纲对象
            
        Returns:
            上下文内容字符串
        """
        context_parts = []
        
        # 收集所有章节的素材内容
        for item in optimized_outline.optimized_items:
            if item.optimized_item.description:
                context_parts.append(item.optimized_item.description)
        
        # 从已有的章节内容中提取信息（排除需要补充的章节）
        return "\n\n".join(context_parts[:10])  # 限制上下文长度

    def _supplement_section_content(
        self,
        section_title: str,
        subsection_list: list[str],
        context_content: str,
        section_materials: dict[uuid.UUID, list[NodeWithScore]] | None = None,
        outline_item_id: uuid.UUID | None = None,
    ) -> str:
        """
        为内容不足的章节生成补充内容

        使用 RAG 检索到的真实素材内容，而不是预定义模板。

        Args:
            section_title: 章节标题
            subsection_list: 子节列表
            context_content: 可用的上下文内容
            section_materials: 该章节对应的RAG素材
            outline_item_id: 大纲项ID（用于从 section_materials 中提取素材）

        Returns:
            补充后的内容，如果生成失败则返回空字符串
        """
        import re

        # 从 section_materials 中提取真实素材内容
        actual_material_text = ""
        if section_materials and outline_item_id:
            materials = section_materials.get(outline_item_id, [])
            if materials:
                material_texts = []
                for m in materials:
                    node = getattr(m, "node", None)
                    if node and hasattr(node, "text"):
                        text = node.text
                        # 过滤掉结构化数据补充段落
                        if "结构化数据补充" not in text and "## 结构化数据补充" not in text:
                            material_texts.append(text.strip())
                if material_texts:
                    actual_material_text = "\n\n".join(material_texts[:3])  # 最多使用3条素材

        # 如果有实际素材，使用真实素材内容生成
        if actual_material_text:
            logger.info(
                "使用RAG素材补充章节内容: title='%s', 素材长度=%d",
                section_title,
                len(actual_material_text),
            )

            # 从素材中提取关键信息生成内容
            # 提取关键句子
            sentences = re.findall(r'[^。！？\n]+[。！？]', actual_material_text)
            key_points = []

            # 根据章节标题选择相关句子
            title_keywords = set(re.findall(r'[\w]{2,}', section_title))

            for sent in sentences:
                sent_keywords = set(re.findall(r'[\w]{2,}', sent))
                overlap = title_keywords & sent_keywords
                # 如果有50%以上的关键词重叠，或者句子包含数字（可能是数据）
                if len(title_keywords) > 0 and (len(overlap) / len(title_keywords) >= 0.5 or re.search(r'[\d]+', sent)):
                    key_points.append(sent.strip())
                    if len(key_points) >= 5:  # 最多5个关键点
                        break

            if key_points:
                # 构建基于真实素材的内容
                content_parts = []

                # 根据章节类型生成结构化内容
                if "产业链" in section_title or "技术" in section_title:
                    content_parts.append(f"""<h4>产业概况与发展现状</h4>
<p>{key_points[0] if key_points else actual_material_text[:500]}</p>""")

                    if len(key_points) > 1:
                        content_parts.append(f"""<h4>市场规模与增长趋势</h4>
<p>{"".join(key_points[1:3])}</p>""")

                    if len(key_points) > 3:
                        content_parts.append(f"""<h4>关键技术路线</h4>
<p>{"".join(key_points[3:5])}</p>""")

                elif "投资" in section_title or "市场" in section_title:
                    content_parts.append(f"""<h4>市场规模分析</h4>
<p>{key_points[0] if key_points else actual_material_text[:500]}</p>""")

                    if len(key_points) > 1:
                        content_parts.append(f"""<h4>增长驱动因素</h4>
<p>{"".join(key_points[1:3])}</p>""")

                    if len(key_points) > 3:
                        content_parts.append(f"""<h4>投资机会与风险</h4>
<p>{"".join(key_points[3:5])}</p>""")

                elif "风险" in section_title or "挑战" in section_title:
                    content_parts.append(f"""<h4>主要风险分析</h4>
<p>{key_points[0] if key_points else actual_material_text[:500]}</p>""")

                    if len(key_points) > 1:
                        content_parts.append(f"""<h4>应对策略</h4>
<p>{"".join(key_points[1:3])}</p>""")

                elif "结论" in section_title or "展望" in section_title:
                    content_parts.append(f"""<h4>主要结论</h4>
<p>{key_points[0] if key_points else actual_material_text[:500]}</p>""")

                    if len(key_points) > 1:
                        content_parts.append(f"""<h4>未来展望</h4>
<p>{"".join(key_points[1:3])}</p>""")

                else:
                    # 默认结构
                    content_parts.append(f"<p>{' '.join(key_points[:3])}</p>")

                return "\n\n".join(content_parts)

            # 如果无法提取关键点，直接使用素材内容（截断到合理长度）
            if len(actual_material_text) > 200:
                return f"<p>{actual_material_text[:800]}...</p>"
            else:
                return f"<p>{actual_material_text}</p>"

        # 如果没有素材，使用传入的上下文内容
        if context_content and len(context_content) > 100:
            logger.info(
                "使用上下文内容补充章节: title='%s', 上下文长度=%d",
                section_title,
                len(context_content),
            )
            # 从上下文中提取相关内容
            context_sentences = re.findall(r'[^。！？\n]+[。！？]', context_content)
            relevant_parts = []

            title_keywords = set(re.findall(r'[\w]{2,}', section_title))
            for sent in context_sentences:
                sent_keywords = set(re.findall(r'[\w]{2,}', sent))
                overlap = title_keywords & sent_keywords
                if len(title_keywords) > 0 and len(overlap) / len(title_keywords) >= 0.3:
                    relevant_parts.append(sent.strip())
                    if len(relevant_parts) >= 4:
                        break

            if relevant_parts:
                return f"<p>{' '.join(relevant_parts)}</p>"

        # 最后兜底：使用基于章节标题的通用内容 + LLM生成
        logger.warning(
            "无可用素材为章节生成内容，尝试使用LLM补充: title='%s'",
            section_title,
        )

        # 尝试使用LLM生成内容
        llm_generated_content = self._generate_content_with_llm(
            section_title=section_title,
            context_content=context_content,
        )

        if llm_generated_content:
            logger.info(
                "LLM内容补充成功: title='%s', length=%d",
                section_title,
                len(llm_generated_content)
            )
            return llm_generated_content

        # 如果LLM生成也失败，返回空字符串
        logger.warning(
            "所有内容补充方法均失败: title='%s'",
            section_title,
        )
        return ""

    def _generate_content_with_llm(
        self,
        section_title: str,
        context_content: str,
    ) -> str:
        """
        当RAG素材不足时，使用LLM基于常识和专业判断生成内容

        Args:
            section_title: 章节标题
            context_content: 可用的上下文内容

        Returns:
            生成的内容，如果失败返回空字符串
        """
        import re

        # 1. 检查是否有可用的LLM服务
        if not hasattr(self, 'llm_service') or self.llm_service is None:
            logger.debug("LLM服务不可用，无法使用LLM补充内容")
            return ""

        # 2. 检查LLM模型是否可用
        try:
            model = self.llm_service.get_chat_model()
            if model is None:
                logger.debug("LLM模型不可用")
                return ""
        except Exception as e:
            logger.debug("获取LLM模型失败: %s", e)
            return ""

        # 3. 构建生成提示词
        prompt = f"""你是一位专业的行业研究员和分析师。请根据以下信息，为「{section_title}」章节生成详细内容。

## 可用上下文信息
{context_content if context_content and len(context_content) > 50 else '无可用上下文，请基于行业常识生成专业内容'}

## 要求
1. 生成专业的行业分析内容，包含具体数据、趋势或分析观点
2. 如果缺乏具体数据，请基于行业常识和逻辑推理生成合理内容
3. 使用专业的行业研究语言
4. 内容要详实、专业、数据驱动
5. 直接输出Markdown格式的段落内容，不要包含标题，不要有开场白

## 产出要求
- 字数：300-500字
- 格式：Markdown段落文本，包含<p>标签和必要的列表
- 风格：专业、客观、数据驱动

请直接生成内容："""

        # 4. 调用LLM生成
        try:
            from langchain_core.messages import HumanMessage
            from langchain_core.output_parsers import StrOutputParser

            messages = [HumanMessage(content=prompt)]

            logger.debug(
                "开始调用LLM生成章节内容: title='%s', prompt_length=%d",
                section_title,
                len(prompt)
            )

            generated_content = ""
            for chunk in model.stream(messages, max_tokens=2000):
                chunk_text = getattr(chunk, "content", None)
                if chunk_text:
                    generated_content += chunk_text

            # 5. 清理生成内容
            cleaned_content = self._cleanup_generated_content(generated_content)

            # 6. 确保内容长度合理
            word_count = len(cleaned_content)
            if word_count < 100:
                logger.warning(
                    "LLM生成内容过短: title='%s', length=%d",
                    section_title,
                    word_count
                )
                return ""

            # 7. 包装为HTML格式
            html_content = self._wrap_content_as_html(cleaned_content, section_title)

            logger.info(
                "LLM生成内容成功: title='%s', length=%d",
                section_title,
                len(html_content)
            )

            return html_content

        except Exception as e:
            logger.warning(
                "LLM内容生成失败: title='%s', error=%s",
                section_title,
                e
            )
            return ""

    def _wrap_content_as_html(self, content: str, section_title: str) -> str:
        """
        将文本内容包装为HTML格式

        Args:
            content: 文本内容
            section_title: 章节标题（用于生成适当的子标题）

        Returns:
            HTML格式的内容
        """
        import re

        # 如果内容已经有HTML标签，直接返回
        if "<" in content and ">" in content:
            return content

        # 清理内容
        content = content.strip()

        # 提取段落
        paragraphs = content.split("\n\n")
        html_parts = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # 移除标题（如果有）
            para = re.sub(r'^#+\s*', '', para)
            para = para.strip()

            if not para:
                continue

            # 如果是列表
            if para.startswith("- ") or para.startswith("* "):
                items = para.split("\n")
                list_items = []
                for item in items:
                    item = item.strip().lstrip("-* ")
                    if item:
                        list_items.append(f"<li>{item}</li>")
                if list_items:
                    html_parts.append(f"<ul>{''.join(list_items)}</ul>")
            else:
                # 普通段落
                html_parts.append(f"<p>{para}</p>")

        return "\n".join(html_parts) if html_parts else f"<p>{content}</p>"

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

    def _load_image_caption_map(
        self, source_documents: list[dict[str, Any]]
    ) -> dict[str, str]:
        """从源文档中加载图片文件名到图名的映射

        Args:
            source_documents: 源文档列表

        Returns:
            UUID文件名到图名的映射字典
        """
        import json
        from pathlib import Path

        caption_map: dict[str, str] = {}

        for doc in source_documents:
            doc_path_str = doc.get("file_path") or doc.get("source")
            if not doc_path_str:
                continue

            doc_path = Path(doc_path_str)
            # 查找 clean_content_list.json
            clean_content_list_path = doc_path / "clean_content_list.json"
            if not clean_content_list_path.exists():
                # 也可能在父目录
                clean_content_list_path = doc_path.parent / "clean_content_list.json"

            if not clean_content_list_path.exists():
                continue

            try:
                with open(clean_content_list_path, encoding="utf-8") as f:
                    content_list = json.load(f)

                for item in content_list:
                    if isinstance(item, dict) and item.get("type") == "image":
                        img_path = item.get("img_path", "")
                        img_filename = Path(img_path).name if img_path else ""
                        captions = item.get("image_caption", [])
                        if isinstance(captions, list) and len(captions) > 0:
                            caption = captions[0]
                        elif isinstance(captions, str) and captions:
                            caption = captions
                        else:
                            continue

                        if img_filename and caption:
                            caption_map[img_filename] = caption

                logger.debug(
                    "从 %s 加载图片映射: %d 条",
                    clean_content_list_path.name,
                    len(caption_map),
                )
            except Exception as e:
                logger.warning("加载图片映射失败 %s: %s", clean_content_list_path, e)

        return caption_map

    def _sanitize_figure_name(self, caption: str) -> str:
        """将图 caption 转换为合法的文件名

        Args:
            caption: 图 caption (如 "图1“十四五”以来我国新型储能装机规模情况")

        Returns:
            合法的文件名 (如 "图1_十四五以来我国新型储能装机规模情况.jpg")
        """
        import re

        # 移除不合法字符,保留中文、英文、数字、下划线、连字符
        # 移除引号和其他特殊字符
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", caption)
        # 替换空格和多余空白为下划线
        sanitized = re.sub(r"\s+", "_", sanitized)
        # 移除连续的下划线
        sanitized = re.sub(r"_+", "_", sanitized)
        # 移除首尾的下划线
        sanitized = sanitized.strip("_")
        # 限制长度,避免文件名过长
        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        return sanitized

    def _inject_rag_media_placeholders(
        self,
        sections: list[DraftSection],
        section_materials: dict[uuid.UUID, list[NodeWithScore]],
        source_documents: list[dict[str, Any]] | None = None,
        max_images_per_section: int = 2,
        max_json_per_section: int = 1,
        max_total_images: int = 10,
    ) -> list[dict[str, Any]]:
        """
        基于RAG召回结果的metadata自动注入媒体占位符，并返回媒体清单（供HTML附录使用）。

        仅使用 RAG 召回节点 metadata 中的:
        - images.files (图片文件名列表)
        - charts.charts[].file (图表JSON文件名)

        Args:
            sections: 草稿章节列表
            section_materials: 每个章节对应的RAG召回素材
            source_documents: 源文档列表,用于加载图片名称映射
            max_images_per_section: 每章最多注入图片数
            max_json_per_section: 每章最多注入JSON图表数
            max_total_images: 全局最多注入图片数

        Returns:
            媒体清单列表,每项包含:
            - figure_name: 图名(如"图1_xxx")
            - original_uuid: 原始UUID文件名
            - json_file: 对应的JSON文件名
            - source_file: 来源文件
        """
        import re
        from pathlib import Path

        manifest: list[dict[str, Any]] = []
        # 注意：必须按“真实文件(原始uuid文件名)”去重，而不是按 figure_name 去重。
        # figure_name 可能会因为重名被追加 _1/_2/...，导致同一张图片被重复注入，最终在 HTML 中看起来“只剩几张图反复出现”。
        used_image_uuids: set[str] = set()
        used_image_names: set[str] = set()
        used_json: set[str] = set()

        # 加载图片名称映射
        caption_map: dict[str, str] = {}
        if source_documents:
            caption_map = self._load_image_caption_map(source_documents)
            logger.debug("加载图片映射: %d 条", len(caption_map))

        # 用于跟踪已使用的图名序号,避免重复
        figure_name_counter: dict[str, int] = {}

        # 先扫描已有占位符，避免重复注入
        placeholder_re = re.compile(r"\[\[IMAGE:([^\]]+)\]\]")
        for s in sections:
            for m in placeholder_re.finditer(s.content or ""):
                val = m.group(1).strip()
                if val.lower().endswith(".json"):
                    used_json.add(Path(val).name)
                else:
                    # 这里拿不到 uuid，只能先按“占位符名”避免重复注入同名图
                    used_image_names.add(Path(val).name)

        for section in sections:
            outline_item_id_str = (section.metadata or {}).get("outline_item_id")
            if not outline_item_id_str:
                continue

            try:
                outline_item_id = uuid.UUID(str(outline_item_id_str))
            except Exception:
                continue

            materials = section_materials.get(outline_item_id) or []
            if not materials:
                continue

            candidate_images: list[tuple[str, str, str]] = []  # (uuid_filename, figure_name, source_file)
            candidate_jsons: list[tuple[str, str]] = []  # (filename, source_file)

            for n in materials:
                node = getattr(n, "node", None)
                meta = getattr(node, "metadata", {}) if node else {}
                source_file = Path(str(meta.get("file_path") or meta.get("source") or "")).name
                # VectorIndexBuilder/Chroma 受限于 metadata 必须是“基本类型”，常会把 dict/list 序列化成 JSON 字符串。
                # 为了不重建索引也能正确注入图片，这里同时兼容:
                # - images: dict
                # - images: JSON-string(dict)
                images_meta: dict[str, Any] | None = None
                raw_images_meta = meta.get("images")
                if isinstance(raw_images_meta, dict):
                    images_meta = raw_images_meta
                elif isinstance(raw_images_meta, str) and raw_images_meta.strip().startswith("{"):
                    try:
                        import json as _json

                        parsed = _json.loads(raw_images_meta)
                        if isinstance(parsed, dict):
                            images_meta = parsed
                    except Exception:
                        images_meta = None
                if images_meta:
                    files = images_meta.get("files") or []
                    if isinstance(files, list):
                        for f in files:
                            uuid_filename = Path(str(f)).name
                            if uuid_filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")):
                                # 获取图名
                                caption = caption_map.get(uuid_filename, "")
                                if caption:
                                    # 使用图名作为文件名
                                    figure_name = self._sanitize_figure_name(caption)
                                    # 确保图名唯一,添加序号后缀
                                    if figure_name in figure_name_counter:
                                        figure_name_counter[figure_name] += 1
                                        figure_name = f"{figure_name}_{figure_name_counter[figure_name]}"
                                    else:
                                        figure_name_counter[figure_name] = 0
                                    # 统一使用.jpg扩展名（实际存储的图片都是.jpg格式）
                                    # 移除可能存在的扩展名，然后添加.jpg
                                    figure_name_stem = Path(figure_name).stem
                                    figure_name = f"{figure_name_stem}.jpg"
                                else:
                                    # 如果没有caption,使用UUID文件名，但确保扩展名为.jpg
                                    # 移除原始扩展名，统一使用.jpg
                                    uuid_stem = Path(uuid_filename).stem
                                    figure_name = f"{uuid_stem}.jpg"

                                candidate_images.append((uuid_filename, figure_name, source_file))

                charts_meta: dict[str, Any] | None = None
                raw_charts_meta = meta.get("charts")
                if isinstance(raw_charts_meta, dict):
                    charts_meta = raw_charts_meta
                elif isinstance(raw_charts_meta, str) and raw_charts_meta.strip().startswith("{"):
                    try:
                        import json as _json

                        parsed = _json.loads(raw_charts_meta)
                        if isinstance(parsed, dict):
                            charts_meta = parsed
                    except Exception:
                        charts_meta = None
                if charts_meta:
                    charts = charts_meta.get("charts") or []
                    if isinstance(charts, list):
                        for c in charts:
                            if not isinstance(c, dict):
                                continue
                            jf = c.get("file") or c.get("name")
                            if not jf:
                                continue
                            jname = Path(str(jf)).name
                            if not jname.lower().endswith(".json"):
                                jname = f"{jname}.json"
                            candidate_jsons.append((jname, source_file))

            # 候选去重：同一 uuid 可能从多个召回节点出现，先按 uuid 去重，保留第一个命名
            deduped_candidates: list[tuple[str, str, str]] = []
            seen_uuid_in_section: set[str] = set()
            for uuid_fname, figure_name, src in candidate_images:
                u = Path(uuid_fname).name
                if u in seen_uuid_in_section:
                    continue
                seen_uuid_in_section.add(u)
                deduped_candidates.append((u, figure_name, src))

            images_to_add: list[tuple[str, str, str]] = []
            for uuid_fname, figure_name, src in deduped_candidates:
                # 全局按 uuid 去重，避免同一图片被多次注入（哪怕 figure_name 被加了 _1/_2/...）
                if uuid_fname in used_image_uuids:
                    continue
                # 同名占位符也不重复注入（防止正文已有同名）
                if figure_name in used_image_names:
                    continue

                images_to_add.append((uuid_fname, figure_name, src))
                used_image_uuids.add(uuid_fname)
                used_image_names.add(figure_name)

                if len(images_to_add) >= max_images_per_section:
                    break
                if len(used_image_uuids) >= max_total_images:
                    break

            json_to_add: list[tuple[str, str]] = []
            for jf, src in candidate_jsons:
                if jf in used_json:
                    continue
                json_to_add.append((jf, src))
                used_json.add(jf)
                if len(json_to_add) >= max_json_per_section:
                    break

            if not images_to_add and not json_to_add:
                continue

            # 注入到正文末尾（不影响章节结构）
            # 交付物要求：不要输出“解释性标题/适配说明”等噪声文本，只注入占位符即可。
            # 占位符会在 HTML 导出阶段被替换为实际图片/图表，且附录会基于 manifest 生成数据表格。
            extra_lines: list[str] = [""]
            for uuid_fname, figure_name, _ in images_to_add:
                extra_lines.append(f"[[IMAGE:{figure_name}]]")
            for jf, _ in json_to_add:
                extra_lines.append(f"[[IMAGE:{jf}]]")
            section.content = (section.content.rstrip() + "\n" + "\n".join(extra_lines)).strip()

            # 记录 manifest（仅记录被注入的条目，确保附录严格对应RAG）
            for uuid_fname, figure_name, src in images_to_add:
                manifest.append(
                    {
                        "figure_name": figure_name,
                        "original_uuid": uuid_fname,
                        "json_file": f"{Path(figure_name).stem}.json",
                        "source_file": src,
                    }
                )
            for jf, src in json_to_add:
                manifest.append(
                    {
                        "figure_name": None,
                        "original_uuid": jf,
                        "json_file": jf,
                        "source_file": src,
                    }
                )

        if manifest:
            logger.info(
                "基于RAG召回注入媒体占位符完成: manifest_items=%d, images=%d, json=%d",
                len(manifest),
                len(used_image_uuids),
                len(used_json),
            )
        return manifest

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

    # ==================== 新增方法：基于MD模板的生成逻辑 ====================

    def _get_markdown_template_path(
        self, 
        optimized_outline: OptimizedOutline
    ) -> Path | None:
        """
        获取MD模板文件路径
        
        Args:
            optimized_outline: 优化后的大纲
            
        Returns:
            MD模板路径，如果不存在则返回None
        """
        # 首先从metadata中获取路径（最优：由 outline_optimization_service 写入）
        metadata = optimized_outline.metadata or {}
        template_path_str = (
            metadata.get("markdown_template_path")
            or metadata.get("outline_template_path")
            or metadata.get("md_template_path")
        )
        
        if template_path_str:
            path = Path(template_path_str)
            if path.exists():
                logger.debug("从metadata获取MD模板路径: %s", template_path_str)
                return path
        
        # 尝试自动查找（兼容两种命名来源）：
        # 1) 由优化后大纲保存产生：outline_template_{optimized_outline.id}.md
        # 2) 由“创建大纲模板”产生：outline_template_{original_outline_id}.md（更常见）
        template_path = self.outline_to_markdown_service.get_template_path(outline_id=optimized_outline.id)
        if not template_path:
            template_path = self.outline_to_markdown_service.get_template_path(
                outline_id=optimized_outline.original_outline_id
            )
        
        if template_path:
            logger.debug("自动查找MD模板: %s", template_path)
        
        return template_path

    def _load_blueprints_from_markdown(
        self, 
        template_path: Path
    ) -> list[SectionBlueprint]:
        """
        从MD模板加载章节蓝图
        
        Args:
            template_path: MD模板文件路径
            
        Returns:
            章节蓝图列表
        """
        try:
            blueprints = self.outline_to_markdown_service.parse_markdown_to_blueprints(
                template_path
            )
            logger.info(
                "从MD模板加载章节蓝图: 路径=%s, 章节数=%d",
                template_path,
                len(blueprints)
            )
            if blueprints:
                logger.debug(
                    "章节蓝图预览(前3个): %s",
                    [
                        {
                            "section_id": b.section_id,
                            "title": b.title,
                            "level": b.level,
                            "min_words": b.min_words,
                            "max_words": b.max_words,
                        }
                        for b in blueprints[:3]
                    ],
                )
            return blueprints
        except Exception as e:
            logger.error(
                "从MD模板加载章节蓝图失败: 路径=%s, 错误=%s",
                template_path,
                e
            )
            raise

    def _build_chapter_prompt(
        self,
        blueprint: SectionBlueprint,
        materials_context: str,
        previous_chapters_info: str | None = None,
    ) -> str:
        """
        构建单个章节的生成提示词
        
        提示词与RAG内容的组织顺序（基于最佳实践）：
        1. 首先提供章节信息和生成要求（提示词），给模型明确的指导方向
        2. 然后提供RAG检索到的素材内容，作为知识基础
        3. 最后提供写作要求和其他约束条件
        
        Args:
            blueprint: 章节蓝图（包含prompt字段，来自MD模板中的提示词）
            materials_context: 该章节对应的素材上下文（RAG检索结果）
            previous_chapters_info: 已生成的章节信息（用于避免重复）
            
        Returns:
            提示词字符串
        """
        # 1. 构建章节基本信息
        # 章节长度不再作为硬约束（避免“为了凑字数”稀释质量）
        chapter_info = f"""## 当前章节信息
- 标题：{blueprint.title}"""
        
        # 2. 构建生成要求（提示词）- 优先展示，给模型明确指导
        generation_requirements = ""
        if blueprint.prompt:
            generation_requirements = f"""
## 生成要求（重要：这是内容生成的核心指引）
{blueprint.prompt}

**说明**：以上生成要求是内容生成的指引方向，请基于这些要求深度分析和论述。
生成要求本身不要出现在最终生成的内容中，只作为写作的指导原则。"""
        
        # 3. 构建提示词主体（按照最佳实践：提示词在前，RAG内容在后）
        prompt = f"""你是一位专业的白皮书撰写专家。请根据以下提示词和检索到的素材，生成当前章节的完整内容。

{chapter_info}"""
        
        # 4. 添加生成要求（如果有）- 在RAG素材之前
        if generation_requirements:
            prompt += generation_requirements
        
        # 5. 添加RAG检索到的素材内容 - 作为知识基础
        prompt += f"""

## 相关素材内容（RAG检索结果）
以下是检索到的相关素材，请深度利用并基于这些素材进行扩展：

{materials_context}

**提示**：请充分利用以上素材中的数据和信息，但不要直接复制，而是基于这些素材进行深度分析和扩展。"""
        
        # 6. 添加写作要求和其他约束
        prompt += """

## 写作要求
1. **严格按照生成要求**进行深度分析和论述（如果有生成要求）
2. **深度利用RAG素材**：基于检索到的素材进行扩展，包含数据支持和逻辑推导
3. **内联引用**：使用格式 [来源:文件名] 标注数据来源（必须使用素材中给出的"来源文件名"，禁止写 [来源:素材3] 这类占位符）
4. **禁止生成开场白**：禁止任何开场白（如"好的"、"以下是..."、"根据以上素材"等）
5. **禁止重复标题**：禁止在内容中重复章节标题
6. **内容要求**：详实、专业、数据驱动，符合白皮书风格
7. **提示词处理**：生成要求的内容本身不要出现在生成结果中，只作为写作指引
8. **子章节格式规范**：如果内容需要子章节，请使用 Markdown 格式（### 标题），并保留原有编号格式（如 3.1、3.1.1），不要使用 **粗体** 替代标题，不要省略编号"""
        
        # 7. 添加已生成章节信息（避免重复）
        if previous_chapters_info:
            prompt += f"""

## 已生成章节（请避免内容重复）
{previous_chapters_info}"""
        
        # 8. 最终指示
        prompt += "\n\n请直接生成当前章节的正文内容（不要包含提示词、生成要求等元信息）："
        
        return prompt

    def _get_section_materials_context(
        self,
        blueprint: SectionBlueprint,
        section_materials: dict,
    ) -> str:
        """
        获取单个章节的素材上下文
        
        Args:
            blueprint: 章节蓝图
            section_materials: 所有章节的素材映射
            
        Returns:
            格式化后的素材上下文
        """
        materials = section_materials.get(blueprint.section_id, [])
        
        if not materials:
            return "（无可用素材，请基于常识和专业判断生成内容）"
        
        # 格式化素材内容
        context_parts = []
        for idx, material in enumerate(materials, 1):
            node = getattr(material, "node", None)
            if node is None:
                continue
            
            text = getattr(node, "text", "") or ""
            metadata = getattr(node, "metadata", {}) or {}
            
            # 截取相关片段（固定上限，避免 prompt 爆炸；不再用“字数要求”作为依据）
            max_length = min(len(text), 4000)
            text_preview = text[:max_length] + ("..." if len(text) > max_length else "")

            source_name = self._pick_source_filename(metadata) or metadata.get("filename") or metadata.get("title")
            source_name = str(source_name) if source_name else f"素材{idx}"

            context_parts.append(
                f"【素材{idx}】{source_name}\n"
                f"来源文件名: {source_name}\n"
                f"{text_preview}"
            )
        
        return "\n\n".join(context_parts) if context_parts else "（无可用素材）"

    def _pick_source_filename(self, metadata: dict) -> str | None:
        """
        从检索节点 metadata 中提取最适合用于引用的“来源文件名”。

        优先级（更贴近交付展示）：source_title → filename → file_path/source → title/document_title
        """
        try:
            from pathlib import Path

            # 0) cleaned/documents 的目录名（去噪后）优先：它比 clean.md / uuid 更可读
            source_title = metadata.get("source_title")
            if isinstance(source_title, str) and source_title.strip():
                return source_title.strip()

            # 1) filename（最适合展示）
            filename = metadata.get("filename")
            if filename:
                return Path(str(filename)).name

            # 2) file_path/source：但要避开内部标识与 clean.md
            file_path = metadata.get("file_path") or metadata.get("source")
            if file_path:
                fp = str(file_path).strip()
                if fp and fp != "knowledge_base_service":
                    name = Path(fp).name
                    if name.lower() not in {"clean.md", "clean.txt", "clean.html"}:
                        return name

            title = metadata.get("document_title") or metadata.get("title")
            if title:
                return str(title).strip()
        except Exception:
            return None
        return None

    def _cleanup_generated_content(self, content: str) -> str:
        """
        清理生成的内容
        
        移除开场白、结束语等不需要的部分。
        
        Args:
            content: 原始生成内容
            
        Returns:
            清理后的内容
        """
        if not content:
            return ""
        
        lines = content.strip().split("\n")
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # 跳过明显的开场白
            if stripped in [
                "好的，以下是",
                "以下是生成的内容：",
                "根据以上素材，生成以下内容：",
                "以下是当前章节的内容：",
                "生成内容如下：",
            ]:
                continue
            
            # 跳过只包含标点的行
            if stripped and not all(c in "，。！？、：；""''（）【】《》——…·" for c in stripped):
                cleaned_lines.append(line)
        
        result = "\n".join(cleaned_lines).strip()
        
        # 移除结尾的总结语
        ending_phrases = [
            "以上就是当前章节的内容。",
            "以上是当前章节的全部内容。",
            "本章内容结束。",
        ]
        
        for phrase in ending_phrases:
            if result.endswith(phrase):
                result = result[: -len(phrase)].strip()
        
        return result

    async def _generate_single_chapter(
        self,
        blueprint: SectionBlueprint,
        section_materials: dict,
        previous_chapters: list[DraftSection],
    ) -> DraftSection:
        """
        生成单个章节的内容
        
        Args:
            blueprint: 章节蓝图
            section_materials: 素材映射
            previous_chapters: 已生成的章节列表
            
        Returns:
            生成的章节
        """
        # 获取素材上下文 + 为“来源占位符”准备映射（用于把 [来源:素材3] 自动改写成真实文件名）
        materials = section_materials.get(blueprint.section_id, []) or []
        material_source_map: dict[str, str] = {}
        for idx, material in enumerate(materials, 1):
            node = getattr(material, "node", None)
            meta = getattr(node, "metadata", {}) if node is not None else {}
            if not isinstance(meta, dict):
                meta = {}
            source_name = self._pick_source_filename(meta) or f"素材{idx}"
            material_source_map[f"素材{idx}"] = source_name
            material_source_map[str(idx)] = source_name

        materials_context = self._get_section_materials_context(blueprint, section_materials)
        
        # 构建已生成章节信息（用于避免重复）
        previous_info = None
        if previous_chapters:
            prev_titles = [s.title for s in previous_chapters if s.title]
            if prev_titles:
                previous_info = "已生成的章节：" + "、".join(prev_titles)
        
        # 构建提示词
        prompt = self._build_chapter_prompt(
            blueprint=blueprint,
            materials_context=materials_context,
            previous_chapters_info=previous_info,
        )
        
        import time

        prompt_chars = len(prompt) if prompt else 0
        materials_count = len(materials) if isinstance(materials, list) else 0
        materials_chars = len(materials_context) if materials_context else 0

        logger.debug(
            "生成章节: 标题=%s, prompt_chars=%d, materials_count=%d, materials_chars=%d",
            blueprint.title,
            prompt_chars,
            materials_count,
            materials_chars,
        )
        
        # 调用LLM生成
        try:
            from langchain_core.messages import HumanMessage
            from langchain_core.output_parsers import StrOutputParser
            
            messages = [HumanMessage(content=prompt)]
            
            # max_tokens：保持足够空间生成“结论/行动倡议”这类章节；不再与字数硬绑定
            max_tokens = 8000
            
            generated_content = ""
            t0 = time.monotonic()
            for chunk in self.model.stream(messages, max_tokens=max_tokens):
                chunk_text = getattr(chunk, "content", None)
                if chunk_text:
                    generated_content += chunk_text
            total_s = time.monotonic() - t0
            
            # 清理内容
            cleaned_content = self._cleanup_generated_content(generated_content)

            # 将模型可能生成的“素材N”引用改写为真实来源文件名
            cleaned_content = self._replace_generic_source_markers(
                cleaned_content, material_source_map
            )
            
            # 统计长度（仅用于日志/分析）
            word_count = len(cleaned_content)
            
            # 创建章节对象
            section = DraftSection(
                id=uuid.UUID(blueprint.section_id) if self._is_valid_uuid(blueprint.section_id) else uuid.uuid4(),
                parent_id=uuid.UUID(blueprint.parent_section_id) if (
                    blueprint.parent_section_id and 
                    self._is_valid_uuid(blueprint.parent_section_id)
                ) else None,
                section_type=self._map_item_level_to_section_type(blueprint.level),
                level=blueprint.level,
                title=blueprint.title,
                content=cleaned_content,
                order=blueprint.order,
                source_references=[],
                metadata={
                    "outline_item_id": blueprint.section_id,
                    "source": "md_template",
                    "material_source_map": material_source_map,
                },
            )

            logger.info(
                "章节生成完成: 标题=%s, 字数=%d, 耗时=%.2fs, prompt_chars=%d, materials_count=%d",
                blueprint.title,
                word_count,
                total_s,
                prompt_chars,
                materials_count,
            )
            
            return section
            
        except Exception as e:
            logger.error(
                "章节生成失败: 标题=%s, 错误=%s",
                blueprint.title,
                e
            )
            # 返回失败章节（包含错误信息）
            return DraftSection(
                id=uuid.uuid4(),
                parent_id=uuid.UUID(blueprint.parent_section_id) if (
                    blueprint.parent_section_id and 
                    self._is_valid_uuid(blueprint.parent_section_id)
                ) else None,
                section_type=self._map_item_level_to_section_type(blueprint.level),
                level=blueprint.level,
                title=blueprint.title,
                content=f"[章节生成失败: {e}]",
                order=blueprint.order,
            )

    def _replace_generic_source_markers(
        self, content: str, material_source_map: dict[str, str]
    ) -> str:
        """
        将模型输出中的 [来源:素材N] / [来源: 素材N] 改写为 [来源:<真实文件名>]。
        """
        if not content or not material_source_map:
            return content

        import re

        def _repl(m: re.Match) -> str:
            n = m.group(1)
            src = (
                material_source_map.get(f"素材{n}")
                or material_source_map.get(n)
                or f"素材{n}"
            )
            return f"[来源:{src}]"

        # 兼容中英文冒号与可选空格
        return re.sub(r"\[来源[:：]\s*素材(\d+)\s*\]", _repl, content)

    def _is_valid_uuid(self, value: str) -> bool:
        """检查字符串是否为有效的UUID"""
        try:
            uuid.UUID(value)
            return True
        except (ValueError, AttributeError):
            return False

    def _map_item_level_to_section_type(self, level: int) -> DraftSectionType:
        """将大纲层级映射到章节类型"""
        type_mapping = {
            1: DraftSectionType.SECTION,
            2: DraftSectionType.SECTION,
            3: DraftSectionType.SUBSECTION,
            4: DraftSectionType.SUBSECTION,
            5: DraftSectionType.PARAGRAPH,
            6: DraftSectionType.PARAGRAPH,
        }
        return type_mapping.get(level, DraftSectionType.PARAGRAPH)

    async def _generate_chapter_by_chapter(
        self,
        blueprints: list[SectionBlueprint],
        section_materials: dict,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[DraftSection]:
        """
        按章节依次生成内容（推荐方式）
        
        Args:
            blueprints: 章节蓝图列表
            section_materials: 素材映射
            progress_callback: 进度回调函数(current, total)
            
        Returns:
            生成的章节列表
        """
        sections: list[DraftSection] = []
        total = len(blueprints)
        
        logger.info(
            "开始按章节生成内容: 总章节数=%d",
            total
        )
        
        for idx, blueprint in enumerate(blueprints):
            # 报告进度
            if progress_callback:
                progress_callback(idx + 1, total)
            
            # 生成单个章节
            section = await self._generate_single_chapter(
                blueprint=blueprint,
                section_materials=section_materials,
                previous_chapters=sections,
            )
            sections.append(section)
        
        logger.info(
            "章节生成完成: 成功=%d/%d",
            len(sections),
            total
        )
        
        return sections

    async def generate_draft_from_markdown_template(
        self,
        optimized_outline: OptimizedOutline,
        industry_name: str,
        database_names: list[str] | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> Draft:
        """
        基于MD模板生成草稿（推荐方法）
        
        该方法：
        1. 读取MD模板文件获取章节结构
        2. 为每个章节检索素材
        3. 按章节依次生成内容
        4. 构建草稿对象
        
        Args:
            optimized_outline: 优化后的大纲
            industry_name: 行业名称
            database_names: 数据库名称列表
            progress_callback: 进度回调函数(current, total)
            
        Returns:
            生成的草稿对象
        """
        try:
            logger.info(
                "开始基于MD模板生成草稿: 大纲ID=%s, 行业=%s",
                optimized_outline.id,
                industry_name
            )
            
            # 1. 加载MD模板
            template_path = self._get_markdown_template_path(optimized_outline)
            
            if not template_path or not template_path.exists():
                logger.warning(
                    "MD模板不存在，将使用传统方式生成: 大纲ID=%s",
                    optimized_outline.id
                )
                # 回退到传统方式
                return await self.generate_draft(
                    optimized_outline=optimized_outline,
                    industry_name=industry_name,
                    database_names=database_names,
                )
            
            blueprints = self._load_blueprints_from_markdown(template_path)
            
            if not blueprints:
                logger.error("MD模板中未找到任何章节")
                raise ValueError("MD模板中未找到任何章节")
            
            # 2. 为每个章节检索素材
            all_source_references: dict[uuid.UUID, SourceReference] = {}
            section_materials: dict[str, list[NodeWithScore]] = {}
            
            if self.hybrid_retriever:
                logger.info("开始为章节检索素材: 章节数=%d", len(blueprints))
                
                for blueprint in blueprints:
                    # 构建查询文本
                    query_parts = [blueprint.title]
                    if blueprint.description:
                        query_parts.append(blueprint.description)
                    query_text = " ".join(query_parts)
                    
                    # 检索素材
                    materials = self._retrieve_materials(
                        query_text=query_text,
                        section_title=blueprint.title,
                        top_k=5,
                    )
                    
                    section_materials[blueprint.section_id] = materials
                    
                    # 收集引用
                    for material in materials:
                        try:
                            source_ref = self._convert_node_to_source_reference(material)
                            all_source_references[source_ref.id] = source_ref
                        except Exception as ref_error:
                            logger.warning(
                                "转换素材引用失败: %s",
                                ref_error
                            )
                
                logger.info(
                    "素材检索完成: 总章节=%d, 有素材章节=%d, 总引用=%d",
                    len(blueprints),
                    len([b for b in blueprints if section_materials.get(b.section_id)]),
                    len(all_source_references)
                )
            
            # 3. 按章节生成内容
            sections = await self._generate_chapter_by_chapter(
                blueprints=blueprints,
                section_materials=section_materials,
                progress_callback=progress_callback,
            )

            # 3.5 基于RAG召回的素材元数据，自动注入图片/图表占位符（MD模板路径也需要）
            # 说明：
            # - 当前模板生成分支会生成“纯文本正文”，不会由LLM插入 [[IMAGE:...]]
            # - HTMLRenderer 的“严格补图”依赖 draft.metadata.rag_media_manifest
            # - 若这里不注入，占位符=0 → 导出阶段 referenced_figures 为空 → 图/表附录不会生成
            rag_media_manifest: list[dict[str, Any]] = []
            try:
                # section_materials 在该分支里以 blueprint.section_id(str) 为 key，
                # _inject_rag_media_placeholders 需要 uuid.UUID key；这里做一次转换。
                section_materials_uuid: dict[uuid.UUID, list[NodeWithScore]] = {}
                for sid, mats in (section_materials or {}).items():
                    try:
                        section_materials_uuid[uuid.UUID(str(sid))] = mats
                    except Exception:
                        continue

                # 收集源文档路径用于加载 clean_content_list.json（从而把 hash 图片名映射到“图1xxx”）
                source_documents: list[dict[str, Any]] = []
                seen_doc_paths: set[str] = set()
                from pathlib import Path

                for mats in (section_materials_uuid or {}).values():
                    for m in mats or []:
                        node = getattr(m, "node", None)
                        meta = getattr(node, "metadata", {}) if node else {}
                        if not isinstance(meta, dict):
                            continue
                        # 优先使用 source（通常是 *_extracted 目录）；其次 file_path（通常是 clean.md）
                        p_raw = meta.get("source") or meta.get("file_path") or ""
                        if not p_raw:
                            continue
                        p = Path(str(p_raw))
                        # 如果是文件路径（clean.md），取父目录
                        # 注意：metadata 可能是相对路径，不能依赖 exists() 判断
                        if p.suffix.lower() in {".md", ".txt"}:
                            p = p.parent
                        # 有些 metadata 的 source/file_path 是相对路径，统一用字符串去重即可
                        p_str = str(p)
                        if p_str and p_str not in seen_doc_paths:
                            seen_doc_paths.add(p_str)
                            source_documents.append({"file_path": p_str})

                rag_media_manifest = self._inject_rag_media_placeholders(
                    sections=sections,
                    section_materials=section_materials_uuid,
                    source_documents=source_documents if source_documents else None,
                )

                # 清理模板生成过程中可能混入的“错误占位符”（只保留注入产生的有效占位符）
                if rag_media_manifest:
                    valid_names: set[str] = set()
                    for item in rag_media_manifest:
                        if isinstance(item, dict):
                            fn = item.get("figure_name")
                            jf = item.get("json_file")
                            if isinstance(fn, str) and fn:
                                valid_names.add(fn)
                            if isinstance(jf, str) and jf:
                                valid_names.add(jf)
                    import re

                    placeholder_pattern = re.compile(r"\[\[IMAGE:([^\]]+)\]\]")
                    cleaned_count = 0
                    for s in sections:
                        if not s.content:
                            continue
                        matches = list(placeholder_pattern.finditer(s.content))
                        for match in reversed(matches):
                            placeholder_filename = match.group(1).strip()
                            if placeholder_filename not in valid_names:
                                start_pos = match.start()
                                end_pos = match.end()
                                before = s.content[:start_pos].rstrip()
                                after = s.content[end_pos:].lstrip()
                                if before and after:
                                    s.content = before + "\n" + after
                                else:
                                    s.content = before + after
                                cleaned_count += 1
                    if cleaned_count > 0:
                        logger.info(
                            "MD模板生成：清理无效图片占位符完成: cleaned=%d, valid=%d",
                            cleaned_count,
                            len(valid_names),
                        )
                if rag_media_manifest:
                    logger.info(
                        "MD模板生成：已注入媒体占位符: manifest_items=%d",
                        len(rag_media_manifest),
                    )
            except Exception as e:
                logger.warning(
                    "MD模板生成：注入媒体占位符失败（容错，不影响草稿生成）: %s",
                    e,
                    exc_info=True,
                )
            
            # 4. 构建草稿对象
            # 重要：HTML/导出文件名应严格依托 md 文档结构（尤其是首个 "# " 主标题）
            # 否则会出现 HTML 标题变成“储能行业…”等非 md 主标题的情况。
            md_title: str | None = None
            try:
                raw = template_path.read_text(encoding="utf-8").lstrip("\ufeff").strip()
                for line in raw.splitlines():
                    s = line.strip()
                    if s.startswith("# "):
                        md_title = s[2:].strip()
                        break
            except Exception:
                md_title = None

            draft = Draft(
                id=uuid.uuid4(),
                title=(
                    md_title
                    or optimized_outline.metadata.get("title")
                    or f"{industry_name}市场研究报告"
                ),
                description=optimized_outline.metadata.get("description"),
                outline_id=optimized_outline.original_outline_id,
                industry_id=uuid.uuid4(),
                database_ids=[],
                status=DraftStatus.GENERATING,
            )
            # 记录 md 标题，供后续排查/渲染兜底使用
            try:
                if isinstance(draft.metadata, dict) and md_title:
                    draft.metadata["md_title"] = md_title
                    draft.metadata["outline_template_path"] = str(template_path)
                    draft.metadata["md_template_path"] = str(template_path)
            except Exception:
                pass
            
            # 添加章节（按层级排序）
            sorted_sections = sorted(sections, key=lambda s: (s.level or 1, s.order or 0))
            
            for section in sorted_sections:
                try:
                    draft.add_section(section)
                except Exception as add_error:
                    logger.warning(
                        "添加章节失败: 标题=%s, 错误=%s",
                        section.title,
                        add_error
                    )

            # 注入到草稿 metadata（供 HTMLRenderer 严格补图/附录对齐使用）
            try:
                if rag_media_manifest and isinstance(draft.metadata, dict):
                    draft.metadata["rag_media_manifest"] = rag_media_manifest
            except Exception:
                pass
            
            # 5. 嵌入引用信息
            if all_source_references:
                try:
                    citation_embedder = CitationEmbedder(
                        citation_format=CitationFormat.BRACKET
                    )
                    draft = citation_embedder.embed_citations_in_draft(
                        draft=draft,
                        source_references=all_source_references,
                    )
                except Exception as citation_error:
                    logger.warning(
                        "嵌入引用信息失败: %s",
                        citation_error
                    )
            
            # 6. 更新状态
            draft.status = DraftStatus.GENERATED
            
            logger.info(
                "基于MD模板生成草稿完成: ID=%s, 章节数=%d",
                draft.id,
                len(draft.sections)
            )
            
            return draft
            
        except Exception as e:
            logger.error(
                "基于MD模板生成草稿失败: 大纲ID=%s, 错误=%s",
                optimized_outline.id,
                e
            )
            raise AgentExecutionError(f"基于MD模板生成草稿失败: {e}") from e

    # ==================== 传统方法（保留用于兼容） ====================


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
    # 额外开关（TypedDict 允许扩展字段）
    config["enable_polish"] = bool(kwargs.get("enable_polish", False))
    config["polish_batch_size"] = max(1, int(kwargs.get("polish_batch_size", 1) or 1))

    return DraftGeneratorAgent(
        config=config,
        llm_service=llm_service,
        report_type=report_type,
        language=language,
        style=style,
        hybrid_retriever=hybrid_retriever,
        **kwargs,
    )
