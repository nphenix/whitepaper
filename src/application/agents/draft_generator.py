"""
草稿生成Agent

基于BaseAgent实现的草稿生成Agent,使用LangChain 1.0的create_agent API.
遵循LangChain 1.0最佳实践:
- 使用create_agent API而非简单链式调用
- 支持结构化输出
- 集成RAG检索工具
- 支持引用信息嵌入

用于用户故事6: 草稿生成(带素材追溯链接).

生成命令: /speckit.implement T085
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool, StructuredTool

from src.application.agent_base import AgentConfig, BaseAgent
from src.application.services.outline_normalizer import OutlineNormalizerService
from src.domain.agent.draft import Draft, DraftSection, DraftSectionType, DraftStatus
from src.domain.agent.outline import Outline, OutlineItem
from src.domain.agent.source_reference import SourceReference
from src.infrastructure.indexing.hybrid_retriever import (
    HybridRetriever,
    QueryType,
)
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.agent_exceptions import (
    AgentConfigurationError,
    AgentExecutionError,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

try:
    from llama_index.core.schema import NodeWithScore

    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    NodeWithScore = Any  # type: ignore[assignment, misc]
    LLAMA_INDEX_AVAILABLE = False
    logger.warning("LlamaIndex not available, RAG retrieval will be disabled")


def create_retrieve_materials_tool(
    hybrid_retriever: HybridRetriever | None,
) -> BaseTool | None:
    """创建素材检索工具

    Args:
        hybrid_retriever: 混合检索引擎实例

    Returns:
        LangChain工具实例,如果retriever为None则返回None
    """
    if not hybrid_retriever:
        return None

    if not LLAMA_INDEX_AVAILABLE:
        return None

    def retrieve_materials(
        query_text: str,
        section_title: str = "",
        top_k: int = 5,
    ) -> dict[str, Any]:
        """从知识库检索相关素材

        使用HybridRetriever从本地知识库检索与查询相关的素材内容.

        Args:
            query_text: 查询文本(章节标题或描述)
            section_title: 章节标题(用于日志记录)
            top_k: 返回结果数量(默认5)

        Returns:
            检索结果字典,包含materials列表和metadata
        """
        try:
            logger.info(
                "检索素材: 章节=%s, 查询=%s, top_k=%d",
                section_title or "未知",
                query_text[:50],
                top_k,
            )

            # 使用HybridRetriever检索
            results = hybrid_retriever.retrieve(
                query_str=query_text,
                top_k=top_k,
                query_type=QueryType.GENERAL,
            )

            # 转换为字典格式
            materials = []
            for result in results:
                node = result.node
                metadata = node.metadata if hasattr(node, "metadata") else {}
                score = result.score if hasattr(result, "score") else 0.0

                materials.append({
                    "text": node.text if hasattr(node, "text") else "",
                    "metadata": metadata,
                    "score": score,
                })

            logger.info(
                "素材检索完成: 章节=%s, 结果数=%d",
                section_title or "未知",
                len(materials),
            )

            return {
                "materials": materials,
                "count": len(materials),
                "query": query_text,
                "success": True,
            }

        except Exception as e:
            error_msg = (
                f"素材检索失败: {e}. "
                f"查询文本: {query_text[:100]}. "
                "请检查知识库是否正确索引,以及HybridRetriever配置是否正确."
            )
            logger.error(error_msg, exc_info=True)
            # 抛出异常而不是返回失败标记
            raise AgentExecutionError(error_msg) from e

    return StructuredTool.from_function(
        func=retrieve_materials,
        name="retrieve_materials",
        description="""从本地知识库检索相关素材内容.

使用场景:
- 在生成草稿内容时,需要检索相关的素材来支撑内容生成
- 确保生成的内容有证据支撑,而非泛泛而谈

输入参数:
- query_text: 查询文本(章节标题或描述)
- section_title: 章节标题(可选,用于日志记录)
- top_k: 返回结果数量(默认5,最多10)

输出:
- materials: 检索到的素材列表,每个素材包含text、metadata和score
- count: 素材数量
- query: 查询文本
- success: 是否成功

注意:
- 仅从本地知识库检索,不访问网络数据源
- 返回的素材按相关性评分排序""",
    )


class DraftGeneratorAgent(BaseAgent):
    """
    草稿生成Agent

    基于BaseAgent实现的草稿生成Agent,使用LangChain 1.0的create_agent API.
    提供:
    1. 基于大纲生成草稿内容
    2. 从本地知识库检索素材并嵌入草稿(RAG检索)
    3. 素材引用和追溯链接管理
    4. 结构化输出(Draft对象)

    核心功能:
    - generate_draft(outline, industry_name, database_names): 生成草稿
    - 使用create_agent API,支持工具调用和结构化输出
    - 集成RAG检索工具,自动检索相关素材
    - 自动嵌入引用信息,确保内容可追溯

    架构优势:
    - 使用LangChain 1.0的create_agent API(符合最佳实践)
    - 支持结构化输出(response_format)
    - 统一使用BaseAgent的生命周期管理
    - 自动获得错误处理,日志记录,状态持久化等能力
    - 集成HybridRetriever进行RAG检索,提高内容质量

    功能特性:
    - 支持本地知识库RAG检索(不访问网络数据)
    - 自动生成引用信息(可读、可审计、可追溯)
    - 支持多种报告类型和语言风格
    - 生成结构化Draft对象,包含章节和引用信息
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

        # MVP默认约束条件
        self.report_type = report_type
        self.language = language
        self.style = style

        # RAG检索器(必需,用于从本地知识库检索素材)
        if not hybrid_retriever:
            error_msg = (
                "DraftGeneratorAgent需要HybridRetriever实例进行RAG检索. "
                "请提供hybrid_retriever参数,或确保知识库已正确初始化."
            )
            logger.error(error_msg)
            raise AgentConfigurationError(error_msg)
        self.hybrid_retriever = hybrid_retriever

        # 检查LlamaIndex是否可用
        if not LLAMA_INDEX_AVAILABLE:
            error_msg = (
                "LlamaIndex未安装,无法使用RAG检索功能. "
                "请安装llama-index包: pip install llama-index"
            )
            logger.error(error_msg)
            raise AgentConfigurationError(error_msg)

        logger.info(
            "初始化DraftGeneratorAgent: %s, 报告类型=%s, 语言=%s, 风格=%s, RAG检索=启用",
            self.agent_name,
            self.report_type,
            self.language,
            self.style,
        )

    def get_tools(self) -> list[BaseTool]:
        """获取Agent专用工具列表

        草稿生成Agent的工具:
        - retrieve_materials: 从本地知识库检索相关素材

        Returns:
            工具列表

        Raises:
            AgentConfigurationError: 如果无法创建检索工具
        """
        tools: list[BaseTool] = []

        # 添加素材检索工具(必需)
        retrieve_tool = create_retrieve_materials_tool(self.hybrid_retriever)
        if not retrieve_tool:
            error_msg = (
                "无法创建retrieve_materials工具. "
                "请检查HybridRetriever是否正确初始化,以及LlamaIndex是否正确安装."
            )
            logger.error(error_msg)
            raise AgentConfigurationError(error_msg)
        tools.append(retrieve_tool)
        logger.info("已添加素材检索工具")

        return tools

    def generate_draft(
        self,
        outline: Outline,
        industry_name: str,
        database_names: list[str] | None = None,
        report_type: str | None = None,
    ) -> Draft:
        """生成草稿

        基于大纲生成草稿内容,使用LangChain 1.0的create_agent API.
        自动检索相关素材并嵌入引用信息.

        Args:
            outline: 大纲对象
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
                outline.id,
                industry_name,
                database_names,
            )

            # 使用指定的报告类型或默认值
            report_type = report_type or self.report_type
            database_names = database_names or []

            # 1. 规范化/补全大纲(T086A:轻量大纲规范化/补全)
            logger.info("执行大纲规范化: 报告类型=%s", report_type)
            normalizer = OutlineNormalizerService(llm_service=self.llm_service)
            normalized_outline = normalizer.normalize(outline)
            logger.info(
                "大纲规范化完成: 原始项数=%d, 规范化后项数=%d",
                len(outline.items),
                len(normalized_outline.items),
            )

            # 2. 创建草稿对象
            draft = Draft(
                id=uuid.uuid4(),
                title=f"{industry_name} - {report_type}",
                description=f"基于大纲生成的{report_type}草稿",
                outline_id=outline.id,
                industry_id=uuid.uuid4(),  # TODO: 从行业服务获取真实ID
                database_ids=[],  # TODO: 从数据库服务获取真实ID列表
                status=DraftStatus.GENERATING,
            )

            # 3. 格式化大纲结构(使用规范化后的大纲)
            outline_structure = self._format_outline_structure(normalized_outline)

            # 4. 构建生成提示词
            system_message = self._get_draft_generation_system_message(
                industry_name=industry_name,
                report_type=report_type,
            )

            user_message = self._get_draft_generation_user_message(
                industry_name=industry_name,
                database_names=database_names,
                report_type=report_type,
                outline_structure=outline_structure,
            )

            # 5. 使用Agent生成草稿内容
            # 注意:这里使用Agent的invoke方法,Agent会自动调用工具(如retrieve_materials)
            try:
                response = self.agent.invoke(
                    {
                        "messages": [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": user_message},
                        ]
                    }
                )
            except AgentExecutionError:
                # 如果是AgentExecutionError(可能是检索失败),直接抛出
                raise
            except Exception as e:
                error_msg = (
                    f"Agent调用失败: {e}. "
                    "请检查Agent配置、LLM服务连接以及工具是否正确初始化."
                )
                logger.error(error_msg, exc_info=True)
                raise AgentExecutionError(error_msg) from e

            # 6. 提取生成的内容和工具调用信息
            generated_content = self._extract_content_from_response(response)
            tool_calls_info = self._extract_tool_calls_from_response(response)

            logger.info(
                "Agent生成草稿内容完成,长度=%d字符,工具调用次数=%d",
                len(generated_content),
                len(tool_calls_info),
            )

            # 检查是否使用了检索工具(必需)
            retrieve_calls = [
                tc for tc in tool_calls_info
                if tc.get("tool_name") == "retrieve_materials"
            ]
            if not retrieve_calls:
                error_msg = (
                    "Agent未使用retrieve_materials工具进行RAG检索. "
                    "生成的内容缺少证据支撑,不符合要求. "
                    "请检查Agent的提示词是否正确配置,以及工具是否可用."
                )
                logger.error(error_msg)
                raise AgentExecutionError(error_msg)

            # 检查检索工具调用是否成功
            for call in retrieve_calls:
                result = call.get("result")
                if isinstance(result, dict) and not result.get("success", True):
                    error_msg = result.get("error", "未知错误")
                    full_error = (
                        f"RAG检索工具调用失败: {error_msg}. "
                        "请检查知识库索引状态和HybridRetriever配置."
                    )
                    logger.error(full_error)
                    raise AgentExecutionError(full_error)

            # 7. 从工具调用中提取检索到的素材并创建引用
            source_references = self._create_source_references_from_tool_calls(
                tool_calls_info
            )
            if not source_references:
                error_msg = (
                    "未创建任何信息源引用. "
                    "RAG检索可能未返回有效结果,或检索结果格式不正确. "
                    "请检查知识库内容和检索工具配置."
                )
                logger.error(error_msg)
                raise AgentExecutionError(error_msg)

            logger.info("成功创建%d个信息源引用", len(source_references))

            # 7.5 从source_references中提取document_ids,用于后续加载rag_media_manifest
            database_ids = self._extract_database_ids_from_references(source_references)
            draft.database_ids = database_ids
            logger.info("已设置draft.database_ids: %s", database_ids)

            # 8. 验证生成的内容不为空
            if not generated_content or not generated_content.strip():
                error_msg = (
                    "Agent生成的内容为空. "
                    "请检查Agent配置、提示词设置以及LLM服务是否正常工作."
                )
                logger.error(error_msg)
                raise AgentExecutionError(error_msg)

            # 9. 解析生成的内容并创建草稿章节(使用规范化后的大纲)
            sections = self._parse_generated_content(
                content=generated_content,
                outline=normalized_outline,
                source_references=source_references,
            )

            # 验证解析结果不为空
            if not sections:
                error_msg = (
                    "无法从生成的内容中解析出章节. "
                    "生成的内容可能格式不正确,或与大纲结构不匹配. "
                    f"生成内容长度: {len(generated_content)}字符. "
                    "请检查Agent的输出格式是否符合Markdown规范."
                )
                logger.error(error_msg)
                raise AgentExecutionError(error_msg)

            # 10. 添加章节到草稿
            for section in sections:
                draft.add_section(section)

            # 11. 将引用信息存储到草稿元数据中(供后续使用)
            draft.add_metadata("source_references", {
                str(ref_id): ref.to_dict() for ref_id, ref in source_references.items()
            })
            logger.info("已创建%d个信息源引用", len(source_references))

            # 12. 更新草稿状态
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
        tool_instruction = ""
        if self.hybrid_retriever:
            tool_instruction = """
重要:你必须使用retrieve_materials工具检索素材!
- 在生成每个章节内容前,必须调用retrieve_materials工具检索相关素材
- 使用章节标题或描述作为查询文本进行检索
- 基于检索到的素材内容生成章节,确保内容有证据支撑
- 不要凭空生成内容,必须基于检索到的素材
- 如果检索结果为空,可以基于你的知识生成,但要明确说明缺少素材
"""
        return f"""{base_message}

你是一个专业的文档撰写专家,专注于{self.language}语言的{report_type}写作.

你的主要任务:
1. 根据用户提供的大纲结构生成专业的文档草稿
2. 使用retrieve_materials工具从本地知识库检索相关素材(必须使用!)
3. 确保生成的内容符合{report_type}的专业标准
4. 使用{self.language}语言,保持{self.style}的写作风格
5. 确保内容逻辑清晰,结构完整,语言流畅

写作原则:
- 专业性:使用专业术语,确保内容权威可信
- 客观性:基于事实和数据,避免主观臆断
- 完整性:覆盖大纲中的所有章节,不遗漏重要内容
- 逻辑性:确保章节之间的逻辑关系清晰
- 可读性:语言流畅,易于理解
- 证据性:所有内容必须基于检索到的素材,确保有证据支撑

语言和风格:
- 语言:{self.language}
- 风格:{self.style}
- 语气:正式,权威,客观

{tool_instruction}

输出格式要求:
- 使用Markdown格式输出
- 严格按照大纲结构组织内容
- 每个章节使用对应的标题层级(## 一级标题, ### 二级标题等)
- 章节内容要完整,包含多个段落
- 在内容中自然地引用检索到的素材,不要生硬地插入引用标记

请根据提供的大纲结构生成专业的文档草稿.
"""

    def _get_draft_generation_user_message(
        self,
        industry_name: str,
        database_names: list[str],
        report_type: str,
        outline_structure: str,
    ) -> str:
        """获取草稿生成的用户消息

        Args:
            industry_name: 行业名称
            database_names: 数据库名称列表
            report_type: 报告类型
            outline_structure: 格式化后的大纲结构

        Returns:
            用户消息字符串
        """
        return f"""请根据以下大纲结构生成{report_type}草稿.

## 行业信息
- 行业名称: {industry_name}
- 数据库: {', '.join(database_names) if database_names else '无'}

## 大纲结构
{outline_structure}

## 生成要求
1. 严格按照大纲结构生成内容
2. 每个章节都要有完整的段落内容
3. 使用retrieve_materials工具检索相关素材,确保内容有证据支撑
4. 优先使用检索到的素材内容,确保内容准确可靠
5. 使用专业,客观,数据驱动的语言风格
6. 确保内容逻辑清晰,结构完整
7. 使用Markdown格式输出
8. 在引用素材时,请准确反映素材内容,不要随意修改数据

请开始生成草稿内容."""

    def _format_outline_structure(self, outline: Outline) -> str:
        """格式化大纲结构为文本

        Args:
            outline: 大纲对象

        Returns:
            格式化后的大纲结构文本
        """
        lines = []
        for item in outline.items:
            indent = "  " * (item.level - 1)
            title = item.title
            description = item.description or ""
            lines.append(f"{indent}- {title}")
            if description:
                lines.append(f"{indent}  {description}")

        return "\n".join(lines)

    def _extract_content_from_response(self, response: Any) -> str:
        """从Agent响应中提取内容

        Args:
            response: Agent的响应对象

        Returns:
            提取的内容字符串
        """
        # Agent响应可能是多种格式,需要适配
        if isinstance(response, dict):
            # 如果响应是字典,尝试提取messages或content
            if "messages" in response:
                messages = response["messages"]
                # 查找最后一个AI消息(非工具调用消息)
                for msg in reversed(messages):
                    if hasattr(msg, "content") and msg.content:
                        # 跳过工具调用消息
                        if hasattr(msg, "type") and msg.type == "tool":
                            continue
                        return str(msg.content)
                    elif isinstance(msg, dict):
                        if msg.get("type") == "tool":
                            continue
                        content = msg.get("content", "")
                        if content:
                            return str(content)
            elif "content" in response:
                return response["content"]
            elif "output" in response:
                return response["output"]
        elif hasattr(response, "content"):
            return response.content
        elif hasattr(response, "messages"):
            messages = response.messages
            # 查找最后一个AI消息
            for msg in reversed(messages):
                if hasattr(msg, "content") and msg.content:
                    if hasattr(msg, "type") and msg.type == "tool":
                        continue
                    return str(msg.content)

        # 如果无法提取,转换为字符串
        return str(response)

    def _extract_tool_calls_from_response(self, response: Any) -> list[dict[str, Any]]:
        """从Agent响应中提取工具调用信息

        Args:
            response: Agent的响应对象

        Returns:
            工具调用信息列表,每个元素包含tool_name和result
        """
        tool_calls = []

        # 从响应中提取工具调用信息
        messages = []
        if isinstance(response, dict):
            messages = response.get("messages", [])
        elif hasattr(response, "messages"):
            messages = response.messages

        # 遍历消息,查找工具调用
        for msg in messages:
            # 处理工具调用消息
            if hasattr(msg, "type"):
                if msg.type == "tool":
                    # 工具调用结果
                    tool_name = getattr(msg, "name", None) or getattr(msg, "tool", None)
                    tool_result = getattr(msg, "content", None) or getattr(msg, "result", None)
                    if tool_name and tool_result:
                        tool_calls.append({
                            "tool_name": tool_name,
                            "result": tool_result,
                            "message": msg,
                        })
                elif msg.type == "tool_use":
                    # 工具调用请求(某些格式)
                    tool_name = getattr(msg, "name", None)
                    tool_input = getattr(msg, "input", None)
                    if tool_name:
                        tool_calls.append({
                            "tool_name": tool_name,
                            "input": tool_input,
                            "message": msg,
                        })
            elif isinstance(msg, dict):
                if msg.get("type") == "tool":
                    tool_calls.append({
                        "tool_name": msg.get("name") or msg.get("tool"),
                        "result": msg.get("content") or msg.get("result"),
                        "message": msg,
                    })

        return tool_calls

    def _parse_generated_content(
        self,
        content: str,
        outline: Outline,
        source_references: dict[uuid.UUID, "SourceReference"] | None = None,
    ) -> list[DraftSection]:
        """解析生成的内容并创建草稿章节

        Args:
            content: LLM生成的原始内容
            outline: 大纲对象
            source_references: 信息源引用字典(ID -> SourceReference)

        Returns:
            草稿章节列表
        """
        from src.domain.agent.source_reference import SourceReference

        sections: list[DraftSection] = []
        source_references = source_references or {}

        # 尝试从生成的内容中提取章节内容
        # 使用简单的Markdown解析:查找标题和对应的内容
        content_sections = self._extract_sections_from_markdown(content, outline)

        # 根据大纲结构创建章节
        for idx, item in enumerate(outline.items):
            # 尝试从生成的内容中提取该章节的内容
            section_content = content_sections.get(item.title)
            if not section_content:
                # 如果找不到,尝试使用描述或默认内容
                section_content = item.description or f"关于{item.title}的内容"

            # 为该章节查找相关的引用
            section_ref_ids: list[uuid.UUID] = []
            # 简单匹配:如果章节标题或内容与引用相关,则关联引用
            # 更精确的匹配可以在后续版本中实现
            for ref_id, ref in source_references.items():
                # 检查引用是否与当前章节相关
                if self._is_reference_relevant_to_section(ref, item, section_content):
                    section_ref_ids.append(ref_id)

            section = DraftSection(
                id=uuid.uuid4(),
                parent_id=None,  # TODO: 处理父子关系
                section_type=self._map_item_type_to_section_type(item.item_type),
                level=item.level,
                title=item.title,
                content=section_content,
                order=idx,
                source_references=section_ref_ids,
            )

            sections.append(section)

        return sections

    def _extract_sections_from_markdown(
        self, content: str, outline: Outline
    ) -> dict[str, str]:
        """从Markdown内容中提取章节内容

        Args:
            content: Markdown格式的内容
            outline: 大纲对象

        Returns:
            章节标题到内容的映射字典
        """
        import re

        sections: dict[str, str] = {}

        # 按行分割内容
        lines = content.split("\n")
        current_section: str | None = None
        current_content: list[str] = []

        for line in lines:
            # 检查是否是标题行(以#开头)
            title_match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if title_match:
                # 保存上一个章节
                if current_section and current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                # 开始新章节
                title = title_match.group(2).strip()
                current_section = title
                current_content = []
            elif current_section:
                # 添加到当前章节内容
                current_content.append(line)

        # 保存最后一个章节
        if current_section and current_content:
            sections[current_section] = "\n".join(current_content).strip()

        # 如果无法从Markdown中提取,尝试模糊匹配大纲项标题
        if not sections:
            for item in outline.items:
                # 在内容中查找包含标题的段落
                title_lower = item.title.lower()
                content_lower = content.lower()
                if title_lower in content_lower:
                    # 找到标题位置,提取后续内容(简单实现)
                    idx = content_lower.find(title_lower)
                    if idx >= 0:
                        # 提取标题后的内容(最多500字符)
                        section_text = content[idx:idx + 500].strip()
                        sections[item.title] = section_text

        return sections

    def _is_reference_relevant_to_section(
        self,
        ref: "SourceReference",
        item: "OutlineItem",
        section_content: str,
    ) -> bool:
        """检查引用是否与章节相关

        Args:
            ref: 信息源引用
            item: 大纲项
            section_content: 章节内容

        Returns:
            是否相关
        """
        # 简单实现:检查引用标题或描述中是否包含章节关键词
        # 更精确的匹配可以在后续版本中实现
        keywords = [item.title.lower()]
        if item.description:
            keywords.extend(item.description.lower().split())

        ref_text = (ref.title + " " + (ref.description or "")).lower()
        content_text = section_content.lower()

        # 检查引用文本或内容中是否包含关键词
        for keyword in keywords:
            if len(keyword) > 2:  # 忽略太短的关键词
                if keyword in ref_text or keyword in content_text:
                    return True

        return False

    def _map_item_type_to_section_type(
        self, item_type: Any,
    ) -> DraftSectionType:
        """将大纲项类型映射到草稿章节类型

        Args:
            item_type: 大纲项类型

        Returns:
            草稿章节类型
        """
        from src.domain.agent.outline import OutlineItemType

        type_mapping = {
            OutlineItemType.SECTION: DraftSectionType.SECTION,
            OutlineItemType.SUBSECTION: DraftSectionType.SUBSECTION,
            OutlineItemType.PARAGRAPH: DraftSectionType.PARAGRAPH,
            OutlineItemType.CONTENT: DraftSectionType.PARAGRAPH,
        }
        return type_mapping.get(item_type, DraftSectionType.PARAGRAPH)

    def _create_source_references_from_tool_calls(
        self, tool_calls_info: list[dict[str, Any]]
    ) -> dict[uuid.UUID, "SourceReference"]:
        """从工具调用信息中创建信息源引用

        Args:
            tool_calls_info: 工具调用信息列表

        Returns:
            信息源引用字典(ID -> SourceReference)
        """
        from src.domain.agent.source_reference import (
            SourceReference,
            SourceReferenceType,
        )

        source_references: dict[uuid.UUID, SourceReference] = {}

        # 查找retrieve_materials工具的调用结果
        for tool_call in tool_calls_info:
            tool_name = tool_call.get("tool_name", "")
            if tool_name == "retrieve_materials":
                result = tool_call.get("result")
                if isinstance(result, dict):
                    materials = result.get("materials", [])
                    for material in materials:
                        # 从material创建SourceReference
                        ref = self._convert_material_to_source_reference(material)
                        if ref:
                            source_references[ref.id] = ref

        return source_references

    def _convert_material_to_source_reference(
        self, material: dict[str, Any]
    ) -> "SourceReference | None":
        """将检索到的素材转换为信息源引用

        Args:
            material: 素材字典,包含text、metadata和score

        Returns:
            信息源引用对象,如果转换失败则返回None
        """
        from src.domain.agent.source_reference import (
            LocalDocumentReference,
            SourceReference,
            SourceReferenceType,
        )

        try:
            metadata = material.get("metadata", {})
            text = material.get("text", "")

            # 提取文件路径
            file_path = metadata.get("filename") or metadata.get("file_path") or metadata.get("source")
            if not file_path:
                # 尝试从其他元数据字段提取
                file_path = metadata.get("document_id", "unknown")

            # 提取其他定位信息
            page_number = metadata.get("page") or metadata.get("page_number")
            if isinstance(page_number, str):
                try:
                    page_number = int(page_number)
                except ValueError:
                    page_number = None

            # 创建本地文档引用
            local_ref = LocalDocumentReference(
                file_path=str(file_path),
                paragraph_index=None,
                page_number=page_number,
                line_number=None,
                content_snippet=text[:200] if text else None,  # 前200字符作为片段
            )

            # 创建信息源引用
            title = metadata.get("title") or metadata.get("filename") or file_path
            description = text[:500] if text else None  # 前500字符作为描述

            ref = SourceReference(
                reference_type=SourceReferenceType.LOCAL_DOCUMENT,
                title=str(title),
                description=description,
                local_reference=local_ref,
                web_reference=None,
            )

            return ref

        except Exception as e:
            logger.warning("转换素材为引用失败: %s", e, exc_info=True)
            return None

    def _extract_database_ids_from_references(
        self, source_references: dict[uuid.UUID, "SourceReference"]
    ) -> list[uuid.UUID]:
        """从source_references中提取document_ids

        从LocalDocumentReference的file_path中提取document_id。
        file_path格式: data/cleaned/documents/{doc_id}/... 或包含doc_id的路径

        Args:
            source_references: 信息源引用字典

        Returns:
            document_id UUID列表
        """
        import re
        
        database_ids: list[uuid.UUID] = []
        seen_ids: set[str] = set()
        
        for ref_id, ref in source_references.items():
            if ref.local_reference and ref.local_reference.file_path:
                file_path = ref.local_reference.file_path
                
                # 尝试从路径中提取document_id
                # 格式: data/cleaned/documents/{doc_id}/... 或 .../{doc_id}/...
                doc_id_patterns = [
                    r"data/cleaned/documents/([a-f0-9-]{36})",  # UUID格式
                    r"data/cleaned/documents/([a-f0-9-]{8}-[a-f0-9-]{4}-[a-f0-9-]{4}-[a-f0-9-]{4}-[a-f0-9-12})",  # 标准UUID
                ]
                
                for pattern in doc_id_patterns:
                    match = re.search(pattern, file_path)
                    if match:
                        doc_id_str = match.group(1)
                        if doc_id_str not in seen_ids:
                            try:
                                doc_id = uuid.UUID(doc_id_str)
                                database_ids.append(doc_id)
                                seen_ids.add(doc_id_str)
                                logger.debug("从引用中提取document_id: %s", doc_id_str)
                            except ValueError:
                                pass
                            break
        
        logger.info("从%d个source_references中提取到%d个document_ids",
                   len(source_references), len(database_ids))
        return database_ids

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
    agent_id: str = "draft_generator",
    agent_name: str = "DraftGenerator",
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
        description="草稿生成Agent,用于根据大纲生成文档草稿",
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

