# 生成命令: /speckit.implement T026-MinerU
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
MinerU PDF文档加载器

该模块实现了基于MinerU在线服务的PDF文档加载器,继承BaseLoader接口,
使用T026A-MinerU实现的服务适配器调用MinerU服务进行PDF解析。

功能特性:
- 继承BaseLoader接口,兼容LangChain 1.0规范
- 使用MinerU适配器进行PDF解析
- MinerU自动去除非主体内容(页眉、页脚、脚注、页码),输出结构化内容
- 支持服务配置(API Token等)通过环境变量配置
- 支持异步处理,避免阻塞主流程
- 完整的Document对象元数据规范
- 可选实现lazy_load()方法,支持按页流式加载(处理大文件)

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
)
from src.shared.config.settings import AppConfig
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class MinerUPDFLoader(BaseLoader):
    """
    MinerU PDF文档加载器

    使用MinerU在线服务进行PDF文档解析,自动去除非主体内容(页眉、页脚、脚注、页码),
    输出结构化内容。继承BaseLoader接口,完全兼容LangChain 1.0规范。

    最佳实践:
    1. 使用服务适配器模式,通过MinerUAdapter调用MinerU服务
    2. 统一返回LangChain Document对象
    3. 包含完整的元数据(来源、页码、处理时间等)
    4. 支持异步处理和错误重试
    5. 支持按页流式加载(大文件处理)

    示例:
        >>> loader = MinerUPDFLoader('document.pdf')
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
        **kwargs,
    ):
        """
        初始化MinerU PDF加载器

        Args:
            source: PDF文件路径
            adapter: MinerU适配器实例,如果为None则自动创建
            config: 应用配置对象,如果为None则使用默认配置
            **kwargs: 额外的参数,包括metadata等

        Raises:
            DocumentNotFoundError: 文件不存在时抛出
            MinerUAdapterError: 适配器初始化失败时抛出
        """
        # 调用父类初始化
        super().__init__(source, document_format="pdf", **kwargs)

        # 验证文件存在
        path = Path(source)
        if not path.exists():
            raise DocumentNotFoundError(source)

        if not path.is_file():
            msg = f"路径不是文件: {source}"
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

        logger.debug(f"MinerU PDF加载器初始化完成: source={source}")

    def load(self) -> list[Document]:
        """
        加载PDF文档并返回Document列表

        这是所有加载器必须实现的核心方法。
        使用MinerU适配器调用MinerU服务进行PDF解析,自动去除非主体内容,
        返回LangChain Document对象列表。

        Returns:
            List[Document]: 加载的文档列表,每个Document包含:
                - page_content: PDF文档文本内容(已去除页眉、页脚、脚注、页码)
                - metadata: 文档元数据(source, format, pipeline, processed_at, total_pages等)

        Raises:
            DocumentParsingError: 解析失败时抛出
            LoaderError: 加载过程中出现的其他错误
        """
        try:
            logger.info(f"开始加载PDF文档: {self.source}")

            # 使用适配器提取文档内容
            documents = self.adapter.extract(self.source, file_format="pdf")

            # 验证返回的文档
            if not documents:
                logger.warning(f"MinerU返回空文档列表: {self.source}")
                # 返回一个空内容的Document,而不是空列表
                documents = [
                    self._create_document(
                        page_content="",
                        metadata={
                            "pipeline": "mineru",
                            "total_pages": 0,
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
                        "format": "pdf",
                        "pipeline": "mineru",
                        "processed_at": datetime.now().isoformat(),
                    }
                )

                # 验证文档
                if not self.validate_document(doc):
                    logger.warning(f"文档验证失败,但继续处理: {self.source}")

            logger.info(
                f"成功加载PDF文档: {self.source}, "
                f"文档数={len(documents)}, "
                f"总页数={documents[0].metadata.get('total_pages', 'unknown') if documents else 'unknown'}"
            )

            return documents

        except MinerUAdapterError as e:
            error_msg = f"MinerU适配器错误: {self.source}"
            logger.error(error_msg, exc_info=True)
            raise DocumentParsingError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

        except Exception as e:
            error_msg = f"加载PDF文档失败: {self.source}"
            logger.error(error_msg, exc_info=True)
            raise LoaderError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

    def lazy_load(self) -> Iterator[Document]:
        """
        懒加载PDF文档,支持按页流式加载

        用于处理大文件,避免一次性加载所有页面到内存。
        默认实现调用load()方法并迭代返回结果。
        对于大文件,可以考虑按页分割返回多个Document。

        Yields:
            Document: 单个文档对象

        Raises:
            DocumentParsingError: 解析失败时抛出
            LoaderError: 加载过程中出现的其他错误
        """
        try:
            logger.info(f"开始懒加载PDF文档: {self.source}")

            # 先加载所有文档
            documents = self.load()

            # 如果文档内容较大,可以考虑按页分割
            # 这里先简单返回所有文档
            yield from documents

            logger.info(f"懒加载PDF文档完成: {self.source}")

        except Exception as e:
            error_msg = f"懒加载PDF文档失败: {self.source}"
            logger.error(error_msg, exc_info=True)
            raise LoaderError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

    async def aload(self) -> list[Document]:
        """
        异步加载PDF文档

        使用MinerU适配器的异步方法进行文档提取,避免阻塞主流程。

        Returns:
            List[Document]: 加载的文档列表

        Raises:
            DocumentParsingError: 解析失败时抛出
            LoaderError: 加载过程中出现的其他错误
        """
        try:
            logger.info(f"开始异步加载PDF文档: {self.source}")

            # 使用适配器的异步方法提取文档内容
            documents = await self.adapter.aextract(self.source, file_format="pdf")

            # 验证返回的文档
            if not documents:
                logger.warning(f"MinerU返回空文档列表: {self.source}")
                # 返回一个空内容的Document,而不是空列表
                documents = [
                    self._create_document(
                        page_content="",
                        metadata={
                            "pipeline": "mineru",
                            "total_pages": 0,
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
                        "format": "pdf",
                        "pipeline": "mineru",
                        "processed_at": datetime.now().isoformat(),
                    }
                )

                # 验证文档
                if not self.validate_document(doc):
                    logger.warning(f"文档验证失败,但继续处理: {self.source}")

            logger.info(
                f"成功异步加载PDF文档: {self.source}, "
                f"文档数={len(documents)}, "
                f"总页数={documents[0].metadata.get('total_pages', 'unknown') if documents else 'unknown'}"
            )

            return documents

        except MinerUAdapterError as e:
            error_msg = f"MinerU适配器错误: {self.source}"
            logger.error(error_msg, exc_info=True)
            raise DocumentParsingError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

        except Exception as e:
            error_msg = f"异步加载PDF文档失败: {self.source}"
            logger.error(error_msg, exc_info=True)
            raise LoaderError(
                error_msg,
                source=self.source,
                original_error=e,
            ) from e

    async def alazy_load(self) -> AsyncIterator[Document]:
        """
        异步懒加载PDF文档

        使用异步方法进行流式加载,支持大文件处理。

        Yields:
            Document: 单个文档对象

        Raises:
            DocumentParsingError: 解析失败时抛出
            LoaderError: 加载过程中出现的其他错误
        """
        try:
            logger.info(f"开始异步懒加载PDF文档: {self.source}")

            # 先异步加载所有文档
            documents = await self.aload()

            # 迭代返回文档
            for doc in documents:
                yield doc

            logger.info(f"异步懒加载PDF文档完成: {self.source}")

        except Exception as e:
            error_msg = f"异步懒加载PDF文档失败: {self.source}"
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
            List[str]: 支持的格式列表,MinerU PDF加载器仅支持PDF格式
        """
        return ["pdf"]

    def can_handle(self, source: str) -> bool:
        """
        检查是否能处理指定的文档

        Args:
            source: 文档来源路径

        Returns:
            bool: 是否能处理该文档(检查是否为PDF格式)
        """
        detected_format = self._detect_format(source)
        return detected_format == "pdf"
