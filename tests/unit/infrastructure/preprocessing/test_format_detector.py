# 生成命令: /speckit.implement T038
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
格式检测器单元测试

测试文档格式识别和验证功能,确保format_detector模块正常工作。
"""

import os
import tempfile
import unittest

import pytest

from src.infrastructure.preprocessing.format_detector import (
    FormatDetector,
    FormatInfo,
    ValidationResult,
    detect_document_format,
    validate_document,
)


class TestFormatDetector(unittest.TestCase):
    """格式检测器测试类"""

    def setUp(self):
        """测试前准备"""
        self.detector = FormatDetector(enable_deep_detection=False)
        self.deep_detector = FormatDetector(enable_deep_detection=True)

        # 使用现有测试文档
        self.pdf_file = "F:/WhitePaper/data/temp/uploads/2022储能产业研究白皮书.pdf"
        self.docx_file = "F:/WhitePaper/data/temp/uploads/新型储能发展现状及长时储能在电力系统的应用前景展望.docx"

        # 创建临时目录用于其他测试
        self.temp_dir = tempfile.mkdtemp()

        # 创建测试文件
        self.temp_pdf_file = os.path.join(self.temp_dir, "test.pdf")
        self.temp_docx_file = os.path.join(self.temp_dir, "test.docx")
        self.temp_txt_file = os.path.join(self.temp_dir, "test.txt")
        self.temp_unknown_file = os.path.join(self.temp_dir, "test.unknown")

        # 创建PDF文件(简单PDF头)
        with open(self.temp_pdf_file, "wb") as f:
            f.write(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n")

        # 创建DOCX文件(ZIP格式头)
        with open(self.temp_docx_file, "wb") as f:
            f.write(b"PK\x03\x04\n")

        # 创建文本文件
        with open(self.temp_txt_file, "w") as f:
            f.write("这是一个测试文本文件")

        # 创建未知格式文件
        with open(self.temp_unknown_file, "wb") as f:
            f.write(b"unknown format content")

    def tearDown(self):
        """测试后清理"""
        # 删除临时文件
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_format_by_extension_pdf(self):
        """测试通过扩展名检测PDF格式"""
        format_info = self.detector.detect_format(self.pdf_file)

        assert format_info.format == "pdf"
        assert format_info.extension == ".pdf"
        assert format_info.is_valid
        assert format_info.file_size > 0
        assert format_info.confidence <= 1.0

    def test_detect_format_by_extension_docx(self):
        """测试通过扩展名检测DOCX格式"""
        format_info = self.detector.detect_format(self.docx_file)

        assert format_info.format == "docx"
        assert format_info.extension == ".docx"
        assert format_info.is_valid
        assert format_info.file_size > 0

    def test_detect_format_unknown_extension(self):
        """测试未知扩展名"""
        format_info = self.detector.detect_format(self.temp_unknown_file)

        assert format_info.format == "unknown"
        assert format_info.extension == ".unknown"
        assert not format_info.is_valid
        assert format_info.confidence < 1.0

    def test_detect_format_nonexistent_file(self):
        """测试不存在的文件"""
        with pytest.raises(FileNotFoundError):
            self.detector.detect_format("/nonexistent/file.pdf")

    def test_validate_valid_pdf(self):
        """测试验证有效的PDF文件"""
        result = self.detector.validate_document(self.pdf_file)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.format_info is not None
        assert result.format_info.format == "pdf"

    def test_validate_valid_docx(self):
        """测试验证有效的DOCX文件"""
        result = self.detector.validate_document(self.docx_file)

        assert result.is_valid
        assert len(result.errors) == 0
        assert result.format_info is not None
        assert result.format_info.format == "docx"

    def test_validate_unsupported_format(self):
        """测试验证不支持的格式"""
        result = self.detector.validate_document(self.temp_txt_file)

        assert not result.is_valid
        assert len(result.errors) > 0
        assert "不支持的格式" in result.errors[0]

    def test_validate_nonexistent_file(self):
        """测试验证不存在的文件"""
        result = self.detector.validate_document("/nonexistent/file.pdf")

        assert not result.is_valid
        assert len(result.errors) > 0
        assert "文件不存在" in result.errors[0]

    def test_validate_empty_file(self):
        """测试验证空文件"""
        empty_file = os.path.join(self.temp_dir, "empty.pdf")
        with open(empty_file, "wb"):
            pass  # 创建空文件

        result = self.detector.validate_document(empty_file)

        assert not result.is_valid
        assert "文件为空" in result.errors

    def test_get_supported_formats(self):
        """测试获取支持的格式列表"""
        formats = self.detector.get_supported_formats()

        assert isinstance(formats, list)
        assert "pdf" in formats
        assert "docx" in formats

    def test_is_format_supported(self):
        """测试检查格式是否支持"""
        assert self.detector.is_format_supported("pdf")
        assert self.detector.is_format_supported("docx")
        assert not self.detector.is_format_supported("txt")
        assert not self.detector.is_format_supported("unknown")

    def test_get_format_info(self):
        """测试获取格式信息"""
        pdf_info = self.detector.get_format_info("pdf")

        assert pdf_info is not None
        assert "mime_types" in pdf_info
        assert "extensions" in pdf_info
        assert "max_size" in pdf_info

        unknown_info = self.detector.get_format_info("unknown")
        assert unknown_info is None

    def test_deep_detection_with_real_files(self):
        """测试使用真实文件进行深度检测"""
        # 使用真实PDF文件测试深度检测
        pdf_format_info = self.deep_detector.detect_format(self.pdf_file)

        assert pdf_format_info.format == "pdf"
        assert pdf_format_info.extension == ".pdf"
        assert pdf_format_info.is_valid
        assert pdf_format_info.file_size > 0

        # 使用真实DOCX文件测试深度检测
        docx_format_info = self.deep_detector.detect_format(self.docx_file)

        assert docx_format_info.format == "docx"
        assert docx_format_info.extension == ".docx"
        assert docx_format_info.is_valid
        assert docx_format_info.file_size > 0

    def test_mime_to_format(self):
        """测试MIME类型到格式的转换"""
        # 测试PDF
        pdf_format = self.detector._mime_to_format("application/pdf")
        assert pdf_format == "pdf"

        # 测试DOCX
        docx_format = self.detector._mime_to_format(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert docx_format == "docx"

        # 测试未知MIME
        unknown_format = self.detector._mime_to_format("application/unknown")
        assert unknown_format is None

    def test_filetype_to_format(self):
        """测试filetype扩展名到格式的转换"""
        # 测试PDF
        pdf_format = self.detector._filetype_to_format("pdf")
        assert pdf_format == "pdf"

        # 测试DOCX
        docx_format = self.detector._filetype_to_format("docx")
        assert docx_format == "docx"

        # 测试未知扩展名
        unknown_format = self.detector._filetype_to_format("unknown")
        assert unknown_format is None

    def test_detect_by_extension(self):
        """测试通过扩展名检测格式"""
        # 测试PDF
        pdf_info = self.detector._detect_by_extension(".pdf")
        assert pdf_info.format == "pdf"
        assert pdf_info.mime_type == "application/pdf"
        assert pdf_info.extension == ".pdf"

        # 测试DOCX
        docx_info = self.detector._detect_by_extension(".docx")
        assert docx_info.format == "docx"
        assert (
            docx_info.mime_type
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert docx_info.extension == ".docx"

        # 测试未知扩展名
        unknown_info = self.detector._detect_by_extension(".unknown")
        assert unknown_info.format == "unknown"
        assert unknown_info.extension == ".unknown"
        assert unknown_info.confidence == 0.5

    def test_validate_file_size_limit(self):
        """测试文件大小限制验证"""
        # 创建超过大小限制的PDF文件
        large_file = os.path.join(self.temp_dir, "large.pdf")
        with open(large_file, "wb") as f:
            f.write(b"%PDF-1.4\n" + b"x" * (200 * 1024 * 1024))  # 200MB

        result = self.detector.validate_document(large_file)

        assert not result.is_valid
        assert "文件大小超出限制" in " ".join(result.errors)

    def test_validate_extension_mismatch(self):
        """测试扩展名不匹配警告"""
        # 创建PDF内容但扩展名为.docx的文件
        mismatch_file = os.path.join(self.temp_dir, "mismatch.docx")
        with open(mismatch_file, "wb") as f:
            f.write(b"%PDF-1.4\n")

        result = self.deep_detector.validate_document(mismatch_file)

        # 应该检测为PDF但扩展名为.docx,产生警告
        assert result.is_valid  # 仍然有效,但有警告
        assert len(result.warnings) > 0
        warning_text = " ".join(result.warnings)
        assert "扩展名不匹配" in warning_text


class TestFormatDetectorConvenienceFunctions(unittest.TestCase):
    """便捷函数测试类"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()

        # 创建测试PDF文件
        self.pdf_file = os.path.join(self.temp_dir, "test.pdf")
        with open(self.pdf_file, "wb") as f:
            f.write(b"%PDF-1.4\n")

    def tearDown(self):
        """测试后清理"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_document_format_function(self):
        """测试便捷的格式检测函数"""
        format_info = detect_document_format(self.pdf_file)

        assert isinstance(format_info, FormatInfo)
        assert format_info.format == "pdf"

    def test_validate_document_function(self):
        """测试便捷的验证函数"""
        result = validate_document(self.pdf_file)

        assert isinstance(result, ValidationResult)
        assert result.is_valid
        assert result.format_info is not None

    def test_convenience_functions_with_deep_detection(self):
        """测试便捷函数启用深度检测"""
        format_info = detect_document_format(self.pdf_file, enable_deep_detection=True)
        result = validate_document(self.pdf_file, enable_deep_detection=True)

        assert isinstance(format_info, FormatInfo)
        assert isinstance(result, ValidationResult)
        assert result.format_info is not None


if __name__ == "__main__":
    unittest.main()
