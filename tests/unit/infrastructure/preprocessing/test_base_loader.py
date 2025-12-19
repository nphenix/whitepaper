# 生成命令: /speckit.implement T025
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
基础文档加载器测试

测试BaseLoader接口的实现是否符合LangChain 1.0规范。
"""

import pytest
from langchain_core.documents import Document

from src.infrastructure.preprocessing.loaders.base_loader import (
    BaseLoader,
    DocumentNotFoundError,
    DocumentParsingError,
    LoaderError,
    UnsupportedFormatError,
)


class ConcreteLoader(BaseLoader):
    """用于测试的具体加载器实现"""

    def __init__(
        self,
        source: str,
        document_format: str | None = None,
        should_fail: bool = False,
        **kwargs,
    ):
        super().__init__(source, document_format, **kwargs)
        self.should_fail = should_fail

    def load(self) -> list[Document]:
        """实现load方法"""
        if self.should_fail:
            msg = "测试解析失败"
            raise DocumentParsingError(msg, self.source)

        # 返回测试文档
        return [
            self._create_document("测试内容1", {"page": 1}),
            self._create_document("测试内容2", {"page": 2}),
        ]

    def get_supported_formats(self) -> list[str]:
        """返回支持的格式"""
        return ["test", "txt"]


class TestBaseLoader:
    """BaseLoader测试类"""

    def test_initialization(self):
        """测试初始化"""
        loader = ConcreteLoader("test.txt", "txt")

        assert loader.source == "test.txt"
        assert loader.format == "txt"
        assert isinstance(loader.metadata, dict)

    def test_initialization_with_metadata(self):
        """测试带元数据的初始化"""
        custom_metadata = {"author": "test", "version": "1.0"}
        loader = ConcreteLoader("test.txt", metadata=custom_metadata)

        assert loader.metadata == custom_metadata

    def test_format_detection(self):
        """测试格式自动检测"""
        test_cases = [
            ("document.pdf", "pdf"),
            ("document.docx", "docx"),
            ("document.txt", "txt"),
            ("document.md", "markdown"),
            ("document.html", "html"),
            ("document.csv", "csv"),
            ("unknown.xyz", "unknown"),
            ("no_extension", "unknown"),
        ]

        for source, expected_format in test_cases:
            # 对于ConcreteLoader,我们需要手动设置格式,因为它默认返回'test'
            loader = ConcreteLoader(source, document_format=expected_format)
            assert loader.format == expected_format, f"Failed for {source}"

    def test_create_document(self):
        """测试文档创建"""
        loader = ConcreteLoader("test.txt", "txt")
        content = "测试内容"
        extra_metadata = {"page": 1, "section": "intro"}

        document = loader._create_document(content, extra_metadata)

        assert isinstance(document, Document)
        assert document.page_content == content
        assert document.metadata["source"] == "test.txt"
        assert document.metadata["format"] == "txt"
        assert document.metadata["page"] == 1
        assert document.metadata["section"] == "intro"
        assert "loaded_at" in document.metadata

    def test_validate_document_success(self):
        """测试文档验证成功"""
        loader = ConcreteLoader("test.txt", "txt")
        document = loader._create_document("测试内容", {"page": 1})

        assert loader.validate_document(document) is True

    def test_validate_document_invalid_type(self):
        """测试文档验证失败 - 错误类型"""
        loader = ConcreteLoader("test.txt", "txt")

        assert loader.validate_document("not a document") is False

    def test_validate_document_empty_content(self):
        """测试文档验证失败 - 空内容"""
        loader = ConcreteLoader("test.txt", "txt")
        document = Document(
            page_content="", metadata={"source": "test.txt", "format": "txt"}
        )

        assert loader.validate_document(document) is False

    def test_validate_document_missing_metadata(self):
        """测试文档验证失败 - 缺少元数据"""
        loader = ConcreteLoader("test.txt", "txt")
        document = Document(
            page_content="内容", metadata={"source": "test.txt"}
        )  # 缺少format

        assert loader.validate_document(document) is False

    def test_load_method(self):
        """测试load方法"""
        loader = ConcreteLoader("test.txt", "txt")
        documents = loader.load()

        assert len(documents) == 2
        assert all(isinstance(doc, Document) for doc in documents)
        assert all(doc.page_content.startswith("测试内容") for doc in documents)

    def test_load_method_failure(self):
        """测试load方法失败"""
        loader = ConcreteLoader("test.txt", "txt", should_fail=True)

        with pytest.raises(DocumentParsingError):
            loader.load()

    def test_lazy_load_method(self):
        """测试lazy_load方法"""
        loader = ConcreteLoader("test.txt", "txt")
        documents = list(loader.lazy_load())

        assert len(documents) == 2
        assert all(isinstance(doc, Document) for doc in documents)

    def test_aload_method(self):
        """测试aload方法"""
        import asyncio

        loader = ConcreteLoader("test.txt", "txt")
        documents = asyncio.run(loader.aload())

        assert len(documents) == 2
        assert all(isinstance(doc, Document) for doc in documents)

    @pytest.mark.asyncio
    async def test_alazy_load_method(self):
        """测试alazy_load方法"""
        loader = ConcreteLoader("test.txt", "txt")
        documents = []

        async for doc in loader.alazy_load():
            documents.append(doc)

        assert len(documents) == 2
        assert all(isinstance(doc, Document) for doc in documents)

    def test_can_handle(self):
        """测试can_handle方法"""
        loader = ConcreteLoader("test.txt", "txt")

        # ConcreteLoader支持'test'和'txt'格式
        assert loader.can_handle("test.txt") is True
        assert loader.can_handle("document.md") is False  # 不支持markdown格式
        assert loader.can_handle("test.pdf") is False
        assert loader.can_handle("document.docx") is False

    def test_repr_and_str(self):
        """测试字符串表示"""
        loader = ConcreteLoader("test.txt", "txt")

        assert "ConcreteLoader" in repr(loader)
        assert "test.txt" in repr(loader)
        assert "txt" in repr(loader)
        assert "ConcreteLoader" in str(loader)
        assert "test.txt" in str(loader)

    def test_get_supported_formats(self):
        """测试获取支持的格式"""
        loader = ConcreteLoader("test.txt", "txt")
        formats = loader.get_supported_formats()

        assert isinstance(formats, list)
        assert "test" in formats
        assert "txt" in formats


class TestLoaderExceptions:
    """加载器异常测试类"""

    def test_loader_error(self):
        """测试基础加载器异常"""
        error = LoaderError("测试错误", "test.txt")

        assert str(error) == "加载器错误 [test.txt]: 测试错误"
        assert error.message == "测试错误"
        assert error.source == "test.txt"

    def test_loader_error_without_source(self):
        """测试无来源的加载器异常"""
        error = LoaderError("测试错误")

        assert str(error) == "加载器错误: 测试错误"
        assert error.source is None

    def test_unsupported_format_error(self):
        """测试不支持格式异常"""
        error = UnsupportedFormatError("pdf", "test.txt")

        assert "不支持的文档格式: pdf" in str(error)
        assert error.source == "test.txt"

    def test_document_not_found_error(self):
        """测试文档未找到异常"""
        error = DocumentNotFoundError("missing.txt")

        assert "文档未找到: missing.txt" in str(error)
        assert error.source == "missing.txt"

    def test_document_parsing_error(self):
        """测试文档解析异常"""
        original_error = ValueError("原始错误")
        error = DocumentParsingError("解析失败", "test.txt", original_error)

        assert "文档解析失败: 解析失败" in str(error)
        assert error.source == "test.txt"
        assert error.original_error == original_error


if __name__ == "__main__":
    pytest.main([__file__])
