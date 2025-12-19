# 生成命令: /speckit.implement T025
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
基础文档加载器接口

该模块定义了文档加载器的基础接口,兼容LangChain 1.0的BaseLoader接口。
所有具体的文档加载器实现都必须继承此基类并实现相应方法。

参考LangChain 1.0最佳实践:
- 使用langchain_core.documents.Document作为标准文档格式
- 实现load()方法返回List[Document]
- 可选实现lazy_load()方法支持流式加载
- 元数据必须包含source和format字段
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Any

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class BaseLoader(ABC):
    """
    基础文档加载器抽象基类

    该类定义了所有文档加载器必须实现的核心接口,兼容LangChain 1.0规范。
    提供了同步和异步加载能力,支持批量处理和流式处理。

    所有继承此基类的加载器都必须:
    1. 实现load()方法,返回List[Document]
    2. 确保Document对象包含必要的元数据字段
    3. 可选实现lazy_load()方法支持大文件流式处理
    """

    def __init__(self, source: str, document_format: str | None = None, **kwargs):
        """
        初始化基础加载器

        Args:
            source: 文档来源路径或标识符
            document_format: 文档格式,如果未提供则尝试自动检测
            **kwargs: 额外的参数,包括metadata等
        """
        self.source = source
        self.format = document_format or self._detect_format(source)
        self.metadata = kwargs.get("metadata", {})

        # 记录初始化信息
        logger.debug(
            f"初始化 {self.__class__.__name__}: source={source}, format={self.format}"
        )

    @abstractmethod
    def load(self) -> list[Document]:
        """
        加载文档并返回Document列表

        这是所有加载器必须实现的核心方法。
        返回的Document对象必须包含:
        - page_content: 文档文本内容
        - metadata: 至少包含source和format字段的元数据

        Returns:
            List[Document]: 加载的文档列表

        Raises:
            Exception: 加载过程中出现的任何错误
        """

    def lazy_load(self) -> Iterator[Document]:
        """
        懒加载文档,支持流式处理

        默认实现调用load()方法并迭代返回结果。
        对于大文件处理,建议重写此方法以实现真正的流式处理。

        Yields:
            Document: 单个文档对象

        Raises:
            Exception: 加载过程中出现的任何错误
        """
        yield from self.load()

    async def aload(self) -> list[Document]:
        """
        异步加载文档

        默认实现是同步调用load()方法。
        对于支持异步的加载器,建议重写此方法。

        Returns:
            List[Document]: 加载的文档列表
        """
        return self.load()

    async def alazy_load(self) -> AsyncIterator[Document]:
        """
        异步懒加载文档

        默认实现是同步调用lazy_load()方法。
        对于支持异步流式处理的加载器,建议重写此方法。

        Yields:
            Document: 单个文档对象
        """
        for document in self.lazy_load():
            yield document

    def _detect_format(self, source: str) -> str:
        """
        根据文件路径检测文档格式

        Args:
            source: 文档来源路径

        Returns:
            str: 检测到的格式,如果无法检测则返回'unknown'
        """
        if "." not in source:
            return "unknown"

        extension = source.split(".")[-1].lower()
        format_mapping = {
            "pdf": "pdf",
            "docx": "docx",
            "doc": "doc",
            "txt": "txt",  # 修改为txt格式,与ConcreteLoader支持的格式一致
            "text": "text",
            "test": "test",  # 添加test扩展名支持
            "md": "markdown",
            "html": "html",
            "htm": "html",
            "xlsx": "xlsx",
            "xls": "xls",
            "csv": "csv",
        }

        return format_mapping.get(extension, "unknown")

    def _create_document(
        self, page_content: str, metadata: dict[str, Any] | None = None
    ) -> Document:
        """
        创建标准格式的Document对象

        确保所有Document都包含必要的元数据字段。

        Args:
            page_content: 文档文本内容
            metadata: 额外的元数据信息

        Returns:
            Document: 标准格式的文档对象
        """
        # 合并基础元数据和额外元数据
        base_metadata = {
            "source": self.source,
            "format": self.format,
            "loaded_at": datetime.now().isoformat(),
        }

        # 添加自定义元数据
        if metadata:
            base_metadata.update(metadata)

        # 添加初始化时传入的元数据
        if self.metadata:
            base_metadata.update(self.metadata)

        return Document(page_content=page_content, metadata=base_metadata)

    def validate_document(self, document: Document) -> bool:
        """
        验证Document对象是否符合规范

        Args:
            document: 要验证的Document对象

        Returns:
            bool: 验证是否通过
        """
        if not isinstance(document, Document):
            logger.error(f"文档对象类型错误: {type(document)}")
            return False

        if not document.page_content:
            logger.error("文档内容为空")
            return False

        if not document.metadata:
            logger.error("文档元数据为空")
            return False

        required_fields = ["source", "format"]
        for field in required_fields:
            if field not in document.metadata:
                logger.error(f"文档元数据缺少必需字段: {field}")
                return False

        return True

    def get_supported_formats(self) -> list[str]:
        """
        获取支持的文档格式列表

        Returns:
            List[str]: 支持的格式列表
        """
        # 子类应该重写此方法
        return []

    def can_handle(self, source: str) -> bool:
        """
        检查是否能处理指定的文档

        Args:
            source: 文档来源路径

        Returns:
            bool: 是否能处理该文档
        """
        detected_format = self._detect_format(source)
        supported_formats = self.get_supported_formats()
        logger.debug(f"检测格式: {detected_format}, 支持格式: {supported_formats}")
        return detected_format in supported_formats

    def __repr__(self) -> str:
        """返回对象的字符串表示"""
        return (
            f"{self.__class__.__name__}(source='{self.source}', format='{self.format}')"
        )

    def __str__(self) -> str:
        """返回对象的用户友好字符串表示"""
        return f"{self.__class__.__name__}: {self.source}"


class LoaderError(Exception):
    """文档加载器异常基类"""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        original_error: Exception | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.source = source
        self.original_error = original_error

    def __str__(self) -> str:
        if self.source:
            return f"加载器错误 [{self.source}]: {self.message}"
        return f"加载器错误: {self.message}"


class UnsupportedFormatError(LoaderError):
    """不支持的文档格式异常"""

    def __init__(self, file_format: str, source: str | None = None):
        message = f"不支持的文档格式: {file_format}"
        super().__init__(message, source)


class DocumentNotFoundError(LoaderError):
    """文档未找到异常"""

    def __init__(self, source: str):
        message = f"文档未找到: {source}"
        super().__init__(message, source)


class DocumentParsingError(LoaderError):
    """文档解析异常"""

    def __init__(
        self,
        message: str,
        source: str | None = None,
        original_error: Exception | None = None,
    ):
        full_message = f"文档解析失败: {message}"
        super().__init__(full_message, source, original_error)
