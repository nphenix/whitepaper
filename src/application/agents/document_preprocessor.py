"""
文档预处理Agent

基于BaseAgent实现的文档预处理Agent,使用LangChain 1.0的Agent框架和工具系统.
集成T031预处理协调器,T030A-LLM-AdRemover和T031B图表转JSON转换器.

生成命令: /speckit.implement T032
生成时间: 2025-12-17
来源: specs/001-multi-agent-doc-system/tasks.md
"""

from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_core.tools import BaseTool, StructuredTool

from src.application.agent_base import AgentConfig, BaseAgent
from src.infrastructure.preprocessing.cleaners.llm_ad_remover import LLMAdRemover
from src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter import (
    LLMChartToJsonConverter,
)
from src.infrastructure.preprocessing.preprocessor import DocumentPreprocessor
from src.shared.config.llm_service import LLMService
from src.shared.exceptions.agent_exceptions import AgentExecutionError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


def create_clean_document_tool(ad_remover: LLMAdRemover) -> BaseTool:
    """创建文档清洗工具

    Args:
        ad_remover: LLMAdRemover实例

    Returns:
        LangChain工具实例
    """

    def clean_document(
        document_content: str,
        document_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """清洗文档内容

        使用LLM智能识别并删除广告内容,目录,图表目录等无意义信息.
        保留所有图片链接信息,文档主体内容和章节结构.

        Args:
            document_content: 文档内容(Markdown格式)
            document_metadata: 文档元数据(可选)

        Returns:
            清洗结果字典,包含cleaned_content和metadata
        """
        try:
            # 创建Document对象
            doc = Document(
                page_content=document_content,
                metadata=document_metadata or {},
            )

            # 使用LLMAdRemover清洗
            cleaned_doc = ad_remover.clean_document(doc)

            return {
                "cleaned_content": cleaned_doc.page_content,
                "metadata": cleaned_doc.metadata,
                "success": True,
            }
        except Exception as e:
            logger.error("文档清洗失败: %s", e)
            return {
                "cleaned_content": document_content,
                "metadata": document_metadata or {},
                "success": False,
                "error": str(e),
            }

    return StructuredTool.from_function(
        func=clean_document,
        name="clean_document",
        description="""清洗文档内容,使用LLM智能识别并删除:
- 广告内容
- 目录
- 图表目录
- 其他无意义信息

保留内容:
- 所有图片链接信息(![](images/xxx.jpg)格式)
- 文档主体内容
- 章节结构

输入:document_content(Markdown格式的文档内容)和可选的document_metadata
输出:清洗后的文档内容和元数据""",
    )


def create_chart_to_json_tool(converter: LLMChartToJsonConverter) -> BaseTool:
    """创建图表转JSON工具

    Args:
        converter: LLMChartToJsonConverter实例

    Returns:
        LangChain工具实例
    """

    def convert_charts_to_json(
        document_directory: str,
    ) -> dict[str, Any]:
        """将文档目录中的图表转换为JSON格式

        扫描文档目录中的images/文件夹,识别所有图片文件.
        使用LLM对每个图片进行分析,判断是否为图表.
        对于识别为图表的图片,将其转换为JSON格式.

        Args:
            document_directory: 文档目录路径(T031处理后的输出目录,MinerU输出目录)

        Returns:
            转换结果字典,包含统计信息和处理结果
        """
        try:
            # 调用转换器处理MinerU目录
            result = converter.process_mineru_directory(document_directory)

            return {
                "success": True,
                "total_images": result.get("total_images", 0),
                "charts_identified": result.get("charts_identified", 0),
                "charts_converted": result.get("charts_converted", 0),
                "failed_images": result.get("failed_images", 0),
                "output_directory": result.get("output_directory", ""),
                "processing_time": result.get("processing_time", 0),
            }
        except Exception as e:
            logger.error("图表转JSON失败: %s", e)
            return {
                "success": False,
                "error": str(e),
            }

    return StructuredTool.from_function(
        func=convert_charts_to_json,
        name="convert_charts_to_json",
        description="""将文档目录中的图表转换为JSON格式.

功能:
1. 扫描文档目录中的images/文件夹,识别所有图片文件
2. 使用LLM对每个图片进行分析,判断是否为图表
3. 对于识别为具有准确坐标数据的图表,将其转换为JSON格式
4. JSON文件保存到datajson/目录中,文件名使用图表的中文名称

输入:document_directory(T031处理后的输出目录路径)
输出:转换统计信息(成功/失败数量,处理时间等)""",
    )


class DocumentPreprocessorAgent(BaseAgent):
    """
    文档预处理Agent

    基于BaseAgent实现的文档预处理Agent,提供:
    1. 文档加载和处理(集成T031预处理协调器)
    2. 文档清洗(封装LLMAdRemover为工具)
    3. 图表转JSON(封装LLMChartToJsonConverter为工具,可选)

    核心功能:
    - load_and_process(file_path, format): 加载并处理文档(完整流程)
    - process_document(document): 处理单个Document对象
    - process_documents(documents): 批量处理Document列表

    架构优势:
    - 保持LLMAdRemover和LLMChartToJsonConverter的独立性
    - 统一使用BaseAgent的生命周期管理
    - 自动获得错误处理,日志记录,状态持久化等能力
    - 符合LangChain 1.0最佳实践(工具化设计模式)
    """

    def __init__(
        self,
        config: AgentConfig,
        llm_service: LLMService | None = None,
        preprocessor: DocumentPreprocessor | None = None,
        ad_remover: LLMAdRemover | None = None,
        chart_converter: LLMChartToJsonConverter | None = None,
        *,
        enable_chart_conversion: bool = True,
        **kwargs,
    ):
        """初始化文档预处理Agent

        Args:
            config: Agent配置
            llm_service: LLM服务实例,如果为None则使用默认实例
            preprocessor: 文档预处理协调器实例,如果为None则创建新实例
            ad_remover: LLMAdRemover实例,如果为None则创建新实例
            chart_converter: LLMChartToJsonConverter实例,如果为None则创建新实例
            enable_chart_conversion: 是否启用图表转换功能,默认为True
            **kwargs: 传递给BaseAgent的其他参数
        """
        super().__init__(config, llm_service=llm_service, **kwargs)

        # 初始化组件
        self.llm_service = llm_service or self.llm_service
        self.preprocessor = preprocessor or DocumentPreprocessor(
            llm_service=self.llm_service
        )
        self.ad_remover = ad_remover or LLMAdRemover(llm_service=self.llm_service)
        self.chart_converter = (
            chart_converter
            if chart_converter is not None
            else (
                LLMChartToJsonConverter(llm_service=self.llm_service)
                if enable_chart_conversion
                else None
            )
        )
        self.enable_chart_conversion = enable_chart_conversion

        logger.info(
            "初始化DocumentPreprocessorAgent: %s, 图表转换=%s",
            self.agent_name,
            "启用" if self.enable_chart_conversion else "禁用",
        )

    def get_tools(self) -> list[BaseTool]:
        """获取Agent专用工具列表

        返回:
            - clean_document_tool: 文档清洗工具(封装LLMAdRemover)
            - convert_charts_to_json_tool: 图表转JSON工具(如果启用)

        Returns:
            工具列表
        """
        tools = []

        # 1. 文档清洗工具
        clean_tool = create_clean_document_tool(self.ad_remover)
        tools.append(clean_tool)
        logger.debug("已添加文档清洗工具")

        # 2. 图表转JSON工具(如果启用)
        if self.enable_chart_conversion and self.chart_converter:
            chart_tool = create_chart_to_json_tool(self.chart_converter)
            tools.append(chart_tool)
            logger.debug("已添加图表转JSON工具")

        return tools

    def _get_system_message(self) -> str:
        """获取系统消息

        重写BaseAgent的系统消息,提供文档预处理Agent的专用说明.
        """
        base_message = super()._get_system_message()
        return f"""{base_message}

你是一个专业的文档预处理Agent,负责处理各种格式的文档(PDF,DOCX等).

你的主要任务:
1. 加载文档:根据文档格式自动选择对应的加载器(MinerU PDF/DOCX加载器)
2. 清洗文档:使用clean_document工具清洗文档内容,去除广告,目录等无意义信息
3. 图表转换:使用convert_charts_to_json工具将文档中的图表转换为JSON格式(如果启用)

处理流程:
1. 接收文档路径或Document对象
2. 自动识别文档格式
3. 使用加载器加载文档内容
4. 使用clean_document工具清洗文档
5. 使用convert_charts_to_json工具转换图表(如果启用)
6. 返回处理后的Document列表

注意事项:
- 必须保留所有图片链接信息(![](images/xxx.jpg)格式)
- 必须保留文档主体内容和章节结构
- 图表转换是可选的,根据配置决定是否执行
"""

    def load_and_process(
        self,
        file_path: str,
        doc_format: str | None = None,
    ) -> list[Document]:
        """加载并处理文档(完整流程)

        这是文档预处理的完整流程,包括:
        1. 格式识别(如果未指定format)
        2. 加载器加载(MinerU PDF/DOCX加载器)
        3. LLM清洗(使用clean_document工具)
        4. 图表转换(如果启用,使用convert_charts_to_json工具)

        Args:
            file_path: 文档文件路径
            doc_format: 文档格式(可选,如果不指定则自动识别)

        Returns:
            处理后的Document列表

        Raises:
            AgentExecutionError: 处理失败时抛出
        """
        try:
            logger.info("开始加载并处理文档: %s", file_path)

            # 使用T031预处理协调器处理文档
            documents = self.preprocessor.process_document(file_path)

            # 如果启用图表转换,处理图表
            if self.enable_chart_conversion and self.chart_converter:
                try:
                    # 获取输出目录(从preprocessor获取)
                    output_dir = getattr(self.preprocessor, "output_dir", None)
                    if output_dir:
                        # 构建文档输出目录路径
                        doc_name = Path(file_path).stem
                        base_output_dir = Path(output_dir)
                        # MinerU 输出目录名可能在 stem 后附加后缀（例如 hash/版本），不能假设严格等于 stem
                        candidate_output_dirs: list[Path] = []
                        stem_dir = base_output_dir / doc_name
                        if stem_dir.exists():
                            candidate_output_dirs.append(stem_dir)
                        candidate_output_dirs.extend(
                            sorted(
                                [
                                    p
                                    for p in base_output_dir.glob(f"{doc_name}*")
                                    if p.is_dir()
                                ]
                            )
                        )

                        def _has_existing_json(target_dir: Path) -> bool:
                            datajson_dir = target_dir / "datajson"
                            return datajson_dir.exists() and any(datajson_dir.rglob("*.json"))

                        # 1) 如果已存在 datajson/*.json，说明图转JSON已执行过（T031 预处理器内部也会做一次）
                        #    避免在 Agent 层重复执行导致“看起来一直在转/重复烧 LLM”。
                        if any(_has_existing_json(p) for p in candidate_output_dirs):
                            logger.info("检测到图表JSON已存在，跳过Agent层重复图表转JSON: %s", doc_name)
                        else:
                            # 2) 选择一个包含 images/ 的 MinerU 输出目录进行转换
                            target_dir: Path | None = None
                            for candidate_dir in candidate_output_dirs:
                                if (candidate_dir / "images").exists():
                                    target_dir = candidate_dir
                                    break
                                # 兼容：候选目录下可能还有 *_extracted 子目录
                                for p in candidate_dir.glob("**/*extracted*"):
                                    if p.is_dir() and (p / "images").exists():
                                        target_dir = p
                                        break
                                if target_dir is not None:
                                    break

                            if target_dir is not None:
                                if _has_existing_json(target_dir):
                                    logger.info(
                                        "检测到图表JSON已存在，跳过图表转JSON: %s",
                                        target_dir,
                                    )
                                else:
                                    logger.info("开始转换图表: %s", target_dir)
                                    self.chart_converter.process_mineru_directory(str(target_dir))
                                    logger.info("图表转换完成: %s", target_dir)
                            else:
                                searched = (
                                    [str(p) for p in candidate_output_dirs]
                                    if candidate_output_dirs
                                    else [str(base_output_dir)]
                                )
                                logger.warning(
                                    "未找到包含images的MinerU目录(已搜索): %s", ", ".join(searched)
                                )
                    else:
                        logger.warning("未配置输出目录,跳过图表转换")
                except Exception as e:
                    logger.warning("图表转换失败,继续处理: %s", e)

            logger.info("文档处理完成: %s, 文档数=%d", file_path, len(documents))
            return documents

        except Exception as e:
            logger.error("加载并处理文档失败: %s, 错误: %s", file_path, e)
            msg = f"文档处理失败: {e}"
            raise AgentExecutionError(msg) from e

    def process_document(self, document: Document) -> Document:
        """处理单个Document对象

        对单个Document对象进行清洗处理.

        Args:
            document: 要处理的Document对象

        Returns:
            处理后的Document对象

        Raises:
            AgentExecutionError: 处理失败时抛出
        """
        try:
            logger.info(
                "开始处理Document: %s", document.metadata.get("source", "unknown")
            )

            # 使用LLMAdRemover清洗
            cleaned_doc = self.ad_remover.clean_document(document)

            # 更新元数据
            cleaned_doc.metadata.update(
                {
                    "processed_at": cleaned_doc.metadata.get("processed_at"),
                    "cleaned": True,
                }
            )

            logger.info(
                "Document处理完成: %s", cleaned_doc.metadata.get("source", "unknown")
            )
            return cleaned_doc

        except Exception as e:
            logger.error("处理Document失败: %s", e)
            msg = f"Document处理失败: {e}"
            raise AgentExecutionError(msg) from e

    def process_documents(self, documents: list[Document]) -> list[Document]:
        """批量处理Document列表

        对Document列表进行批量清洗处理.

        Args:
            documents: 要处理的Document列表

        Returns:
            处理后的Document列表

        Raises:
            AgentExecutionError: 处理失败时抛出
        """
        try:
            logger.info("开始批量处理Document列表: %d个文档", len(documents))

            processed_documents = []
            for i, doc in enumerate(documents):
                try:
                    processed_doc = self.process_document(doc)
                    processed_documents.append(processed_doc)
                    logger.debug("处理进度: %d/%d", i + 1, len(documents))
                except Exception as e:
                    logger.warning("处理Document %d失败,跳过: %s", i + 1, e)
                    # 失败时保留原始文档
                    processed_documents.append(doc)

            logger.info("批量处理完成: %d个文档", len(processed_documents))
            return processed_documents

        except Exception as e:
            logger.error("批量处理Document列表失败: %s", e)
            msg = f"批量处理失败: {e}"
            raise AgentExecutionError(msg) from e
