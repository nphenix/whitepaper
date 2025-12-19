# 生成命令: /speckit.implement T027
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
MinerU DOCX文档加载器

该模块实现了基于MinerU在线服务的DOCX文档加载器,继承BaseLoader接口,
使用T026A-MinerU实现的服务适配器调用MinerU服务处理DOCX文档。

功能特性:
- 继承BaseLoader接口,兼容LangChain 1.0规范
- 使用MinerU适配器进行DOCX解析
- MinerU自动去除非主体内容,支持多模态内容提取(文本、公式、表格、图表等)
- 降级方案:python-docx库(当MinerU服务不可用时自动降级)
- 支持服务配置(API Token等)通过环境变量配置
- 支持异步处理,避免阻塞主流程
- 完整的Document对象元数据规范
- 可选实现lazy_load()方法,支持按段落流式加载(处理大文件)

参考文档:
- LangChain 1.0集成最佳实践: docs/development/phase3-framework-evaluation.md
- MinerU API文档: https://mineru.net/apiManage/docs
"""

from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from pathlib import Path

from langchain_core.documents import Document

from src.infrastructure.preprocessing.loaders.base_loader import (
    BaseLoader,
    DocumentNotFoundError,
    DocumentParsingError,
    LoaderError,
)
from src.infrastructure.preprocessing.loaders.mineru_adapter import (
    MinerUAdapter,
    MinerUAdapterError,
    MinerUAPIError,
)
from src.shared.config.settings import AppConfig, get_config
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class MinerUDOCXLoader(BaseLoader):
    """
    MinerU DOCX文档加载器

    使用MinerU在线服务进行DOCX文档解析,自动去除非主体内容,
    支持多模态内容提取(文本、公式、表格、图表等)。继承BaseLoader接口,
    完全兼容LangChain 1.0规范。

    降级方案:
    当MinerU服务不可用时,自动降级使用python-docx库进行DOCX解析。
    降级后的文档质量可能较低,但能保证基本功能可用。

    最佳实践:
    1. 使用服务适配器模式,通过MinerUAdapter调用MinerU服务
    2. 统一返回LangChain Document对象
    3. 包含完整的元数据(来源、段落数、处理时间等)
    4. 支持异步处理和错误重试
    5. 支持降级方案,提高可用性
    6. 支持按段落流式加载(大文件处理)

    示例:
        >>> loader = MinerUDOCXLoader('document.docx')
        >>> documents = loader.load()
        >>> for doc in documents:
        ...     print(doc.page_content)
        ...     print(doc.metadata)
    """

    def __init__(
        self,
        source: str,
        adapter: MinerUAdapter | None = None,
        config: AppConfig | None = None,
        enable_fallback: bool = True,
        **kwargs,
    ):
        """
        初始化MinerU DOCX加载器

        Args:
            source: DOCX文件路径
            adapter: MinerU适配器实例,如果为None则自动创建
            config: 应用配置对象,如果为None则使用默认配置
            enable_fallback: 是否启用python-docx降级方案,默认为True
            **kwargs: 额外的参数,包括metadata等

        Raises:
            DocumentNotFoundError: 文件不存在时抛出
            MinerUAdapterError: 适配器初始化失败时抛出
        """
        # 调用父类初始化
        super().__init__(source, document_format="docx", **kwargs)

        # 验证文件存在
        path = Path(source)
        if not path.exists():
            raise DocumentNotFoundError(source)

        if not path.is_file():
            msg = f"路径不是文件: {source}"
            raise DocumentNotFoundError(msg)

        # 检查文件扩展名
        if path.suffix.lower() != ".docx":
            msg = f"文件格式不正确,期望DOCX格式: {source}"
            raise DocumentNotFoundError(msg)

        # 初始化适配器
        try:
            self.adapter = adapter or MinerUAdapter(config=config)
        except Exception as e:
            logger.error(f"初始化MinerU适配器失败: {e}", exc_info=True)
            msg = f"初始化MinerU适配器失败: {e}"
            raise MinerUAdapterError(
                msg,
                error_code="ADAPTER_INIT_ERROR",
                original_error=e,
            ) from e

        self.enable_fallback = enable_fallback
        self.config = config or get_config()

        logger.debug(
            f"MinerU DOCX加载器初始化完成: source={source}, "
            f"enable_fallback={enable_fallback}"
        )

    def _load_with_python_docx(self) -> list[Document]:
        """
        使用python-docx库作为降级方案加载DOCX文档

        Returns:
            List[Document]: 加载的文档列表

        Raises:
            DocumentParsingError: 解析失败时抛出
        """
        try:
            import docx

            logger.info(f"使用python-docx降级方案加载DOCX文档: {self.source}")

            # 加载DOCX文档
            doc = docx.Document(self.source)

            # 提取所有段落文本
            paragraphs = []
            for para in doc.paragraphs:
                if para.text.strip():
                    paragraphs.append(para.text.strip())

            # 提取表格内容
            table_count = 0
            for table in doc.tables:
                table_count += 1
                for row in table.rows:
                    row_text = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_text.append(cell.text.strip())
                    if row_text:
                        paragraphs.append(" | ".join(row_text))

            # 合并所有内容
            page_content = "\n".join(paragraphs)

            # 构建元数据
            metadata = {
                "source": self.source,
                "format": "docx",
                "pipeline": "python-docx",
                "paragraphs": len(paragraphs),
                "table_count": table_count,
                "processed_at": datetime.now().isoformat(),
                "fallback": True,
                "fallback_reason": "MinerU服务不可用或失败",
            }

            # 创建Document对象
            document = self._create_document(
                page_content=page_content, metadata=metadata
            )

            logger.info(
                f"python-docx降级方案加载成功: {self.source}, "
                f"段落数={metadata['paragraphs']}, "
                f"表格数={table_count}"
            )

            return [document]

        except ImportError:
            error_msg = "python-docx库未安装,无法使用降级方案"
            logger.error(error_msg)
            raise DocumentParsingError(
                error_msg,
                source=self.source,
                original_error=None,
            )
        except Exception as e:
            error_msg = f"python-docx降级方案加载失败: {self.source}"
            logger.error(error_msg, exc_info=True)
            raise DocumentParsingError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

    def load(self) -> list[Document]:
        """
        加载DOCX文档并返回Document列表

        这是所有加载器必须实现的核心方法。
        优先使用MinerU服务进行解析,如果失败且启用降级方案,
        则自动降级使用python-docx库。

        Returns:
            List[Document]: 加载的文档列表,每个Document包含:
                - page_content: DOCX文档文本内容(已去除非主体内容)
                - metadata: 文档元数据(source, format, pipeline, processed_at, paragraphs等)

        Raises:
            DocumentParsingError: 解析失败时抛出
            LoaderError: 加载过程中出现的其他错误
        """
        try:
            logger.info(f"开始加载DOCX文档: {self.source}")

            # 尝试使用MinerU适配器提取文档内容
            try:
                documents = self.adapter.extract(self.source, file_format="docx")
            except (MinerUAPIError, MinerUAdapterError) as e:
                # MinerU服务失败,检查是否启用降级方案
                if self.enable_fallback:
                    logger.warning(
                        f"MinerU服务调用失败,启用python-docx降级方案: {self.source}, "
                        f"错误: {e}"
                    )
                    return self._load_with_python_docx()
                else:
                    # 未启用降级方案,直接抛出异常
                    error_msg = f"MinerU服务调用失败且未启用降级方案: {self.source}"
                    logger.error(error_msg, exc_info=True)
                    raise DocumentParsingError(
                        error_msg,
                        source=self.source,
                        original_error=e,
                    ) from e

            # 验证返回的文档
            if not documents:
                logger.warning(f"MinerU返回空文档列表: {self.source}")
                # 如果启用降级方案,尝试使用python-docx
                if self.enable_fallback:
                    logger.info("MinerU返回空内容,尝试使用python-docx降级方案")
                    return self._load_with_python_docx()

                # 返回一个空内容的Document,而不是空列表
                documents = [
                    self._create_document(
                        page_content="",
                        metadata={
                            "pipeline": "mineru",
                            "paragraphs": 0,
                            "warning": "MinerU返回空内容",
                        },
                    )
                ]

            # 确保所有文档都包含必需的元数据字段
            for doc in documents:
                # 更新元数据,确保包含所有必需字段
                doc.metadata.update(
                    {
                        "source": self.source,
                        "format": "docx",
                        "pipeline": doc.metadata.get("pipeline", "mineru"),
                        "processed_at": datetime.now().isoformat(),
                    }
                )

                # 如果没有段落数,尝试计算
                if "paragraphs" not in doc.metadata:
                    # 简单计算:按换行符分割
                    paragraph_count = len(
                        [p for p in doc.page_content.split("\n") if p.strip()]
                    )
                    doc.metadata["paragraphs"] = paragraph_count

                # 验证文档
                if not self.validate_document(doc):
                    logger.warning(f"文档验证失败,但继续处理: {self.source}")

            logger.info(
                f"成功加载DOCX文档: {self.source}, "
                f"文档数={len(documents)}, "
                f"管道={documents[0].metadata.get('pipeline', 'unknown') if documents else 'unknown'}, "
                f"段落数={documents[0].metadata.get('paragraphs', 'unknown') if documents else 'unknown'}"
            )

            return documents

        except DocumentParsingError:
            # 重新抛出DocumentParsingError
            raise
        except MinerUAdapterError as e:
            error_msg = f"MinerU适配器错误: {self.source}"
            logger.error(error_msg, exc_info=True)
            # 如果启用降级方案,尝试使用python-docx
            if self.enable_fallback:
                logger.warning(
                    f"MinerU适配器错误,启用python-docx降级方案: {self.source}"
                )
                return self._load_with_python_docx()

            raise DocumentParsingError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e
        except Exception as e:
            error_msg = f"加载DOCX文档失败: {self.source}"
            logger.error(error_msg, exc_info=True)
            # 如果启用降级方案,尝试使用python-docx
            if self.enable_fallback:
                logger.warning(f"加载失败,尝试使用python-docx降级方案: {self.source}")
                try:
                    return self._load_with_python_docx()
                except Exception:
                    logger.error(
                        f"python-docx降级方案也失败: {self.source}",
                        exc_info=True,
                    )
                    # 两个方案都失败,抛出原始错误
                    raise LoaderError(
                        error_msg,
                        source=self.source,
                        original_error=e,
                    ) from e

            raise LoaderError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

    def lazy_load(self) -> Iterator[Document]:
        """
        懒加载DOCX文档,支持按段落流式加载

        用于处理大文件,避免一次性加载所有段落到内存。
        默认实现调用load()方法并迭代返回结果。
        对于大文件,可以考虑按段落分割返回多个Document。

        Yields:
            Document: 单个文档对象

        Raises:
            DocumentParsingError: 解析失败时抛出
            LoaderError: 加载过程中出现的其他错误
        """
        try:
            logger.info(f"开始懒加载DOCX文档: {self.source}")

            # 先加载所有文档
            documents = self.load()

            # 迭代返回文档
            yield from documents

            logger.info(f"懒加载DOCX文档完成: {self.source}")

        except Exception as e:
            error_msg = f"懒加载DOCX文档失败: {self.source}"
            logger.error(error_msg, exc_info=True)
            raise LoaderError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

    async def aload(self) -> list[Document]:
        """
        异步加载DOCX文档

        使用MinerU适配器的异步方法进行文档提取,避免阻塞主流程。
        如果MinerU服务失败且启用降级方案,则在异步上下文中同步调用python-docx。

        Returns:
            List[Document]: 加载的文档列表

        Raises:
            DocumentParsingError: 解析失败时抛出
            LoaderError: 加载过程中出现的其他错误
        """
        try:
            logger.info(f"开始异步加载DOCX文档: {self.source}")

            # 尝试使用适配器的异步方法提取文档内容
            try:
                documents = await self.adapter.aextract(self.source, file_format="docx")
            except (MinerUAPIError, MinerUAdapterError) as e:
                # MinerU服务失败,检查是否启用降级方案
                if self.enable_fallback:
                    logger.warning(
                        f"MinerU异步服务调用失败,启用python-docx降级方案: {self.source}, "
                        f"错误: {e}"
                    )
                    # 在异步上下文中同步调用python-docx(因为python-docx不支持异步)
                    return self._load_with_python_docx()
                else:
                    # 未启用降级方案,直接抛出异常
                    error_msg = f"MinerU异步服务调用失败且未启用降级方案: {self.source}"
                    logger.error(error_msg, exc_info=True)
                    raise DocumentParsingError(
                        error_msg,
                        source=self.source,
                        original_error=e,
                    ) from e

            # 验证返回的文档
            if not documents:
                logger.warning(f"MinerU异步返回空文档列表: {self.source}")
                # 如果启用降级方案,尝试使用python-docx
                if self.enable_fallback:
                    logger.info("MinerU异步返回空内容,尝试使用python-docx降级方案")
                    return self._load_with_python_docx()

                # 返回一个空内容的Document,而不是空列表
                documents = [
                    self._create_document(
                        page_content="",
                        metadata={
                            "pipeline": "mineru",
                            "paragraphs": 0,
                            "warning": "MinerU返回空内容",
                        },
                    )
                ]

            # 确保所有文档都包含必需的元数据字段
            for doc in documents:
                # 更新元数据,确保包含所有必需字段
                doc.metadata.update(
                    {
                        "source": self.source,
                        "format": "docx",
                        "pipeline": doc.metadata.get("pipeline", "mineru"),
                        "processed_at": datetime.now().isoformat(),
                    }
                )

                # 如果没有段落数,尝试计算
                if "paragraphs" not in doc.metadata:
                    # 简单计算:按换行符分割
                    paragraph_count = len(
                        [p for p in doc.page_content.split("\n") if p.strip()]
                    )
                    doc.metadata["paragraphs"] = paragraph_count

                # 验证文档
                if not self.validate_document(doc):
                    logger.warning(f"文档验证失败,但继续处理: {self.source}")

            logger.info(
                f"成功异步加载DOCX文档: {self.source}, "
                f"文档数={len(documents)}, "
                f"管道={documents[0].metadata.get('pipeline', 'unknown') if documents else 'unknown'}, "
                f"段落数={documents[0].metadata.get('paragraphs', 'unknown') if documents else 'unknown'}"
            )

            return documents

        except DocumentParsingError:
            # 重新抛出DocumentParsingError
            raise
        except MinerUAdapterError as e:
            error_msg = f"MinerU适配器错误: {self.source}"
            logger.error(error_msg, exc_info=True)
            # 如果启用降级方案,尝试使用python-docx
            if self.enable_fallback:
                logger.warning(
                    f"MinerU适配器错误,启用python-docx降级方案: {self.source}"
                )
                return self._load_with_python_docx()

            raise DocumentParsingError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e
        except Exception as e:
            error_msg = f"异步加载DOCX文档失败: {self.source}"
            logger.error(error_msg, exc_info=True)
            # 如果启用降级方案,尝试使用python-docx
            if self.enable_fallback:
                logger.warning(
                    f"异步加载失败,尝试使用python-docx降级方案: {self.source}"
                )
                try:
                    return self._load_with_python_docx()
                except Exception:
                    logger.error(
                        f"python-docx降级方案也失败: {self.source}",
                        exc_info=True,
                    )
                    # 两个方案都失败,抛出原始错误
                    raise LoaderError(
                        error_msg,
                        source=self.source,
                        original_error=e,
                    ) from e

            raise LoaderError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

    async def alazy_load(self) -> AsyncIterator[Document]:
        """
        异步懒加载DOCX文档

        使用异步方法进行流式加载,支持大文件处理。

        Yields:
            Document: 单个文档对象

        Raises:
            DocumentParsingError: 解析失败时抛出
            LoaderError: 加载过程中出现的其他错误
        """
        try:
            logger.info(f"开始异步懒加载DOCX文档: {self.source}")

            # 先异步加载所有文档
            documents = await self.aload()

            # 迭代返回文档
            for doc in documents:
                yield doc

            logger.info(f"异步懒加载DOCX文档完成: {self.source}")

        except Exception as e:
            error_msg = f"异步懒加载DOCX文档失败: {self.source}"
            logger.error(error_msg, exc_info=True)
            raise LoaderError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

    def get_supported_formats(self) -> list[str]:
        """
        获取支持的文档格式列表

        Returns:
            List[str]: 支持的格式列表,MinerU DOCX加载器仅支持DOCX格式
        """
        return ["docx"]

    def can_handle(self, source: str) -> bool:
        """
        检查是否能处理指定的文档

        Args:
            source: 文档来源路径

        Returns:
            bool: 是否能处理该文档(检查是否为DOCX格式)
        """
        detected_format = self._detect_format(source)
        return detected_format == "docx"
