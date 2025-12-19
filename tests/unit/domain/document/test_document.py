"""
Document领域模型单元测试

测试Document类的创建、验证和方法功能。
"""

# 生成命令: /speckit.implement T023
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import datetime

import pytest

from src.domain.document.document import Document, DocumentFormat, DocumentStatus


class TestDocument:
    """Document类测试用例"""

    def test_document_creation_with_minimal_fields(self):
        """测试使用最小必需字段创建文档"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        assert doc.filename == "test.pdf"
        assert doc.file_path == "/path/to/test.pdf"
        assert doc.file_size == 1024
        assert doc.format == DocumentFormat.PDF
        assert doc.uploaded_by == user_id
        assert doc.status == DocumentStatus.PENDING
        assert doc.mime_type is None
        assert doc.parsed_at is None
        assert doc.error_message is None
        assert doc.metadata == {}
        assert isinstance(doc.id, uuid.UUID)
        assert isinstance(doc.uploaded_at, datetime)

    def test_document_creation_with_all_fields(self):
        """测试使用所有字段创建文档"""
        user_id = uuid.uuid4()
        metadata = {"title": "测试文档", "author": "测试作者"}
        uploaded_at = datetime.utcnow()

        doc = Document(
            id=uuid.uuid4(),
            filename="test.docx",
            file_path="/path/to/test.docx",
            file_size=2048,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            format=DocumentFormat.DOCX,
            uploaded_at=uploaded_at,
            parsed_at=datetime.utcnow(),
            uploaded_by=user_id,
            status=DocumentStatus.INDEXED,
            metadata=metadata,
        )

        assert doc.filename == "test.docx"
        assert doc.file_path == "/path/to/test.docx"
        assert doc.file_size == 2048
        assert (
            doc.mime_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert doc.format == DocumentFormat.DOCX
        assert doc.uploaded_by == user_id
        assert doc.status == DocumentStatus.INDEXED
        assert doc.metadata == metadata
        assert doc.uploaded_at == uploaded_at
        assert doc.parsed_at is not None

    def test_document_validation_empty_filename(self):
        """测试空文件名验证"""
        user_id = uuid.uuid4()

        with pytest.raises(ValueError, match="文件名不能为空"):
            Document(
                filename="",
                file_path="/path/to/test.pdf",
                file_size=1024,
                format=DocumentFormat.PDF,
                uploaded_by=user_id,
            )

        with pytest.raises(ValueError, match="文件名不能为空"):
            Document(
                filename="   ",
                file_path="/path/to/test.pdf",
                file_size=1024,
                format=DocumentFormat.PDF,
                uploaded_by=user_id,
            )

    def test_document_validation_empty_file_path(self):
        """测试空文件路径验证"""
        user_id = uuid.uuid4()

        with pytest.raises(ValueError, match="文件路径不能为空"):
            Document(
                filename="test.pdf",
                file_path="",
                file_size=1024,
                format=DocumentFormat.PDF,
                uploaded_by=user_id,
            )

    def test_document_validation_negative_file_size(self):
        """测试负文件大小验证"""
        user_id = uuid.uuid4()

        with pytest.raises(ValueError):
            Document(
                filename="test.pdf",
                file_path="/path/to/test.pdf",
                file_size=-1,
                format=DocumentFormat.PDF,
                uploaded_by=user_id,
            )

    def test_document_validation_zero_file_size(self):
        """测试零文件大小验证"""
        user_id = uuid.uuid4()

        with pytest.raises(ValueError):
            Document(
                filename="test.pdf",
                file_path="/path/to/test.pdf",
                file_size=0,
                format=DocumentFormat.PDF,
                uploaded_by=user_id,
            )

    def test_document_validation_mime_type_pdf(self):
        """测试PDF文档的MIME类型验证"""
        user_id = uuid.uuid4()

        # 正确的MIME类型
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            mime_type="application/pdf",
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )
        assert doc.mime_type == "application/pdf"

        # 错误的MIME类型
        with pytest.raises(ValueError, match="MIME类型.*与文档格式.*不匹配"):
            Document(
                filename="test.pdf",
                file_path="/path/to/test.pdf",
                file_size=1024,
                mime_type="text/html",
                format=DocumentFormat.PDF,
                uploaded_by=user_id,
            )

    def test_document_validation_mime_type_html(self):
        """测试HTML文档的MIME类型验证"""
        user_id = uuid.uuid4()

        # 正确的MIME类型
        doc1 = Document(
            filename="test.html",
            file_path="/path/to/test.html",
            file_size=1024,
            mime_type="text/html",
            format=DocumentFormat.HTML,
            uploaded_by=user_id,
        )
        assert doc1.mime_type == "text/html"

        doc2 = Document(
            filename="test.html",
            file_path="/path/to/test.html",
            file_size=1024,
            mime_type="application/xhtml+xml",
            format=DocumentFormat.HTML,
            uploaded_by=user_id,
        )
        assert doc2.mime_type == "application/xhtml+xml"

        # 错误的MIME类型
        with pytest.raises(ValueError, match="MIME类型.*与文档格式.*不匹配"):
            Document(
                filename="test.html",
                file_path="/path/to/test.html",
                file_size=1024,
                mime_type="application/pdf",
                format=DocumentFormat.HTML,
                uploaded_by=user_id,
            )

    def test_document_validation_mime_type_docx(self):
        """测试DOCX文档的MIME类型验证"""
        user_id = uuid.uuid4()

        # 正确的MIME类型
        doc = Document(
            filename="test.docx",
            file_path="/path/to/test.docx",
            file_size=1024,
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            format=DocumentFormat.DOCX,
            uploaded_by=user_id,
        )
        assert (
            doc.mime_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

        # 错误的MIME类型
        with pytest.raises(ValueError, match="MIME类型.*与文档格式.*不匹配"):
            Document(
                filename="test.docx",
                file_path="/path/to/test.docx",
                file_size=1024,
                mime_type="application/pdf",
                format=DocumentFormat.DOCX,
                uploaded_by=user_id,
            )

    def test_update_status_to_indexed(self):
        """测试更新状态为INDEXED"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        assert doc.status == DocumentStatus.PENDING
        assert doc.parsed_at is None

        doc.update_status(DocumentStatus.INDEXED)

        assert doc.status == DocumentStatus.INDEXED
        assert doc.error_message is None
        assert doc.parsed_at is not None

    def test_update_status_to_failed(self):
        """测试更新状态为FAILED"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        error_msg = "解析失败"
        doc.update_status(DocumentStatus.FAILED, error_msg)

        assert doc.status == DocumentStatus.FAILED
        assert doc.error_message == error_msg

    def test_update_status_to_failed_without_error_message(self):
        """测试更新状态为FAILED但不提供错误信息"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        with pytest.raises(ValueError, match="状态为FAILED时必须提供错误信息"):
            doc.update_status(DocumentStatus.FAILED)

    def test_update_status_to_indexed_with_error_message(self):
        """测试更新状态为INDEXED但提供错误信息"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        with pytest.raises(ValueError, match="状态为INDEXED时不能提供错误信息"):
            doc.update_status(DocumentStatus.INDEXED, "错误信息")

    def test_add_metadata(self):
        """测试添加元数据"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        assert doc.metadata == {}

        doc.add_metadata("title", "测试文档")
        doc.add_metadata("author", "测试作者")

        assert doc.metadata == {"title": "测试文档", "author": "测试作者"}

    def test_get_metadata(self):
        """测试获取元数据"""
        user_id = uuid.uuid4()
        metadata = {"title": "测试文档", "author": "测试作者"}
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
            metadata=metadata,
        )

        assert doc.get_metadata("title") == "测试文档"
        assert doc.get_metadata("author") == "测试作者"
        assert doc.get_metadata("nonexistent") is None
        assert doc.get_metadata("nonexistent", "default") == "default"

    def test_is_processed(self):
        """测试文档是否已处理完成"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        assert not doc.is_processed()

        doc.update_status(DocumentStatus.INDEXED)
        assert doc.is_processed()

    def test_is_failed(self):
        """测试文档处理是否失败"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        assert not doc.is_failed()

        doc.update_status(DocumentStatus.FAILED, "错误信息")
        assert doc.is_failed()

    def test_is_processing(self):
        """测试文档是否正在处理中"""
        user_id = uuid.uuid4()
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
        )

        assert not doc.is_processing()

        doc.update_status(DocumentStatus.PARSING)
        assert doc.is_processing()

    def test_document_serialization(self):
        """测试文档序列化"""
        user_id = uuid.uuid4()
        metadata = {"title": "测试文档", "author": "测试作者"}
        doc = Document(
            filename="test.pdf",
            file_path="/path/to/test.pdf",
            file_size=1024,
            mime_type="application/pdf",
            format=DocumentFormat.PDF,
            uploaded_by=user_id,
            metadata=metadata,
        )

        # 测试转换为字典
        doc_dict = doc.dict()
        assert doc_dict["filename"] == "test.pdf"
        assert doc_dict["format"] == "pdf"
        assert doc_dict["status"] == "pending"

        # 测试JSON序列化
        doc_json = doc.json()
        assert isinstance(doc_json, str)
        assert "test.pdf" in doc_json

    def test_document_format_enum(self):
        """测试文档格式枚举"""
        assert DocumentFormat.PDF.value == "pdf"
        assert DocumentFormat.HTML.value == "html"
        assert DocumentFormat.DOCX.value == "docx"

    def test_document_status_enum(self):
        """测试文档状态枚举"""
        assert DocumentStatus.PENDING.value == "pending"
        assert DocumentStatus.PARSING.value == "parsing"
        assert DocumentStatus.INDEXED.value == "indexed"
        assert DocumentStatus.FAILED.value == "failed"
