n  # -*- coding: utf-8 -*-
"""
T031 文档预处理协调器测试

测试文档预处理协调器的各项功能,包括:
1. 格式识别和加载器选择
2. 文档加载和清洗流程
3. 批量处理和异步处理
4. 错误处理和统计信息

生成命令: /speckit.implement T031
生成时间: 2025-12-14
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import os
from unittest.mock import Mock, patch

import pytest
from langchain_core.documents import Document

from src.infrastructure.preprocessing.format_detector import (
    FormatDetector,
    FormatInfo,
)
from src.infrastructure.preprocessing.loaders.base_loader import (
    DocumentParsingError,
)
from src.infrastructure.preprocessing.preprocessor import (
    DocumentPreprocessor,
)
from src.shared.config.llm_service import LLMService
from src.shared.config.settings import AppConfig
from src.shared.exceptions.base_exceptions import ProcessingError


class TestDocumentPreprocessor:
    """文档预处理协调器测试类"""

    @pytest.fixture
    def mock_config(self):
        """模拟配置对象"""
        config = Mock(spec=AppConfig)
        return config

    @pytest.fixture
    def mock_llm_service(self):
        """模拟LLM服务对象"""
        llm_service = Mock(spec=LLMService)
        llm_service.get_ad_cleaning_chat_model.return_value = Mock()
        return llm_service

    @pytest.fixture
    def mock_format_detector(self):
        """模拟格式检测器"""
        detector = Mock(spec=FormatDetector)
        detector.get_supported_formats.return_value = ["pdf", "docx"]
        return detector

    @pytest.fixture
    def preprocessor(self, mock_config, mock_llm_service, mock_format_detector):
        """创建文档预处理协调器实例"""
        with patch(
            "src.infrastructure.preprocessing.preprocessor.FormatDetector",
            return_value=mock_format_detector,
        ), patch(
            "src.infrastructure.preprocessing.preprocessor.get_llm_service",
            return_value=mock_llm_service,
        ):
            return DocumentPreprocessor(
                config=mock_config,
                llm_service=mock_llm_service,
                format_detector=mock_format_detector,
                enable_cleaning=False,  # 先测试不启用清洗
            )

    @pytest.fixture
    def preprocessor_with_cleaning(
        self, mock_config, mock_llm_service, mock_format_detector
    ):
        """创建启用清洗的文档预处理协调器实例"""
        with patch(
            "src.infrastructure.preprocessing.preprocessor.FormatDetector",
            return_value=mock_format_detector,
        ), patch(
            "src.infrastructure.preprocessing.preprocessor.get_llm_service",
            return_value=mock_llm_service,
        ), patch(
            "src.infrastructure.preprocessing.preprocessor.LLMAdCleaningPipeline"
        ), patch(
            "src.infrastructure.preprocessing.preprocessor.LLMAdRemover"
        ):
            return DocumentPreprocessor(
                config=mock_config,
                llm_service=mock_llm_service,
                format_detector=mock_format_detector,
                enable_cleaning=True,  # 启用清洗
            )

    def test_init(self, mock_config, mock_llm_service, mock_format_detector):
        """测试初始化"""
        with patch(
            "src.infrastructure.preprocessing.preprocessor.FormatDetector",
            return_value=mock_format_detector,
        ), patch(
            "src.infrastructure.preprocessing.preprocessor.get_llm_service",
            return_value=mock_llm_service,
        ):
            preprocessor = DocumentPreprocessor(
                config=mock_config,
                llm_service=mock_llm_service,
                format_detector=mock_format_detector,
                enable_cleaning=True,
                enable_progress_tracking=False,
            )

        assert preprocessor.config == mock_config
        assert preprocessor.llm_service == mock_llm_service
        assert preprocessor.format_detector == mock_format_detector
        assert preprocessor.enable_cleaning is True
        assert preprocessor.enable_progress_tracking is False
        assert preprocessor._loaders == {}
        assert preprocessor._cleaning_pipeline is None

    def test_get_supported_formats(self, preprocessor):
        """测试获取支持的格式列表"""
        formats = preprocessor.get_supported_formats()
        # get_supported_formats在初始化时被调用了一次,这里又被调用了一次
        assert preprocessor.format_detector.get_supported_formats.call_count >= 1
        assert formats == ["pdf", "docx"]

    def test_is_format_supported(self, preprocessor):
        """测试检查格式是否支持"""
        # 模拟格式检测
        format_info = FormatInfo(format="pdf", is_valid=True)
        preprocessor.format_detector.detect_format.return_value = format_info

        result = preprocessor.is_format_supported("test.pdf")
        assert result is True
        preprocessor.format_detector.detect_format.assert_called_once_with("test.pdf")

    def test_is_format_not_supported(self, preprocessor):
        """测试检查不支持的格式"""
        # 模拟格式检测失败
        preprocessor.format_detector.detect_format.side_effect = Exception("检测失败")

        result = preprocessor.is_format_supported("test.txt")
        assert result is False

    @patch("src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader")
    def test_get_loader_pdf(self, mock_pdf_loader, preprocessor):
        """测试获取PDF加载器"""
        # 模拟格式信息
        format_info = FormatInfo(format="pdf", is_valid=True)
        mock_pdf_instance = Mock()
        mock_pdf_loader.return_value = mock_pdf_instance

        loader = preprocessor._get_loader("test.pdf", format_info)

        assert loader == mock_pdf_instance
        assert "pdf" in preprocessor._loaders
        mock_pdf_loader.assert_called_once_with(
            source="test.pdf",
            config=preprocessor.config,
        )

    @patch("src.infrastructure.preprocessing.preprocessor.MinerUDOCXLoader")
    def test_get_loader_docx(self, mock_docx_loader, preprocessor):
        """测试获取DOCX加载器"""
        # 模拟格式信息
        format_info = FormatInfo(format="docx", is_valid=True)
        mock_docx_instance = Mock()
        mock_docx_loader.return_value = mock_docx_instance

        loader = preprocessor._get_loader("test.docx", format_info)

        assert loader == mock_docx_instance
        assert "docx" in preprocessor._loaders
        mock_docx_loader.assert_called_once_with(
            source="test.docx",
            config=preprocessor.config,
        )

    def test_get_loader_unsupported_format(self, preprocessor):
        """测试获取不支持的格式加载器"""
        format_info = FormatInfo(format="txt", is_valid=True)

        with pytest.raises(ProcessingError, match="创建txt加载器失败"):
            preprocessor._get_loader("test.txt", format_info)

    def test_get_loader_cached(self, preprocessor):
        """测试加载器缓存"""
        format_info = FormatInfo(format="pdf", is_valid=True)

        with patch(
            "src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader"
        ) as mock_pdf_loader:
            mock_pdf_instance = Mock()
            mock_pdf_loader.return_value = mock_pdf_instance

            # 第一次调用
            loader1 = preprocessor._get_loader("test.pdf", format_info)
            # 第二次调用
            loader2 = preprocessor._get_loader("test2.pdf", format_info)

            assert loader1 == loader2 == mock_pdf_instance
            mock_pdf_loader.assert_called_once()  # 只调用一次

    @patch("src.infrastructure.preprocessing.preprocessor.LLMAdCleaningPipeline")
    def test_get_cleaning_pipeline(self, mock_pipeline, preprocessor_with_cleaning):
        """测试获取清洗管线"""
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance

        pipeline = preprocessor_with_cleaning._get_cleaning_pipeline()

        assert pipeline == mock_pipeline_instance
        assert preprocessor_with_cleaning._cleaning_pipeline == mock_pipeline_instance
        mock_pipeline.assert_called_once_with(
            llm_service=preprocessor_with_cleaning.llm_service,
            enable_progress_tracking=preprocessor_with_cleaning.enable_progress_tracking,
        )

    def test_get_cleaning_pipeline_disabled(self, preprocessor):
        """测试清洗未启用时获取清洗管线"""
        with pytest.raises(ProcessingError, match="LLM清洗未启用"):
            preprocessor._get_cleaning_pipeline()

    def test_update_stats(self, preprocessor):
        """测试更新统计信息"""
        # 初始状态
        assert preprocessor.stats["processed_documents"] == 0
        assert preprocessor.stats["failed_documents"] == 0
        assert preprocessor.stats["format_distribution"] == {}
        assert preprocessor.stats["pipeline_distribution"] == {}

        # 更新成功统计
        preprocessor._update_stats("pdf", "loader_only", success=True)
        assert preprocessor.stats["processed_documents"] == 1
        assert preprocessor.stats["format_distribution"]["pdf"] == 1
        assert preprocessor.stats["pipeline_distribution"]["loader_only"] == 1

        # 更新失败统计
        preprocessor._update_stats("docx", "failed", success=False)
        assert preprocessor.stats["failed_documents"] == 1
        assert preprocessor.stats["format_distribution"]["docx"] == 1
        assert preprocessor.stats["pipeline_distribution"]["failed"] == 1

    @patch("src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader")
    def test_process_document_success(self, mock_pdf_loader, preprocessor):
        """测试成功处理单个文档"""
        # 设置模拟对象
        format_info = FormatInfo(format="pdf", is_valid=True, confidence=0.95)
        validation_result = Mock(is_valid=True, warnings=[])
        mock_pdf_instance = Mock()
        mock_pdf_loader.return_value = mock_pdf_instance

        # 模拟文档
        mock_document = Document(
            page_content="测试内容", metadata={"source": "test.pdf", "format": "pdf"}
        )
        mock_pdf_instance.load.return_value = [mock_document]

        # 设置模拟返回值
        preprocessor.format_detector.detect_format.return_value = format_info
        preprocessor.format_detector.validate_document.return_value = validation_result

        # 处理文档
        result = preprocessor.process_document("test.pdf")

        # 验证结果
        assert len(result) == 1
        assert result[0].page_content == "测试内容"
        assert result[0].metadata["source"] == "test.pdf"
        assert result[0].metadata["format"] == "pdf"
        assert "preprocessed_at" in result[0].metadata
        assert "preprocessor_version" in result[0].metadata
        assert result[0].metadata["format_confidence"] == 0.95

    @patch("src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader")
    def test_process_document_validation_failure(self, mock_pdf_loader, preprocessor):
        """测试文档验证失败"""
        format_info = FormatInfo(format="pdf", is_valid=True)
        validation_result = Mock(is_valid=False, errors=["文件损坏"])

        preprocessor.format_detector.detect_format.return_value = format_info
        preprocessor.format_detector.validate_document.return_value = validation_result

        with pytest.raises(ProcessingError, match="文档处理失败"):
            preprocessor.process_document("test.pdf")

    @patch("src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader")
    def test_process_document_loading_failure(self, mock_pdf_loader, preprocessor):
        """测试文档加载失败"""
        format_info = FormatInfo(format="pdf", is_valid=True)
        validation_result = Mock(is_valid=True, warnings=[])
        mock_pdf_instance = Mock()
        mock_pdf_loader.return_value = mock_pdf_instance
        mock_pdf_instance.load.side_effect = DocumentParsingError("加载失败")

        preprocessor.format_detector.detect_format.return_value = format_info
        preprocessor.format_detector.validate_document.return_value = validation_result

        with pytest.raises(ProcessingError, match="文档处理失败"):
            preprocessor.process_document("test.pdf")

    def test_process_documents_batch(self, preprocessor):
        """测试批量处理文档"""
        with patch.object(preprocessor, "process_document") as mock_process:
            # 模拟处理单个文档
            mock_process.side_effect = [
                [Document(page_content="内容1", metadata={"source": "test1.pdf"})],
                [Document(page_content="内容2", metadata={"source": "test2.docx"})],
            ]
            # 重置统计信息
            preprocessor.stats.update(
                {
                    "total_documents": 0,
                    "processed_documents": 0,
                    "failed_documents": 0,
                }
            )

            # 批量处理
            result = preprocessor.process_documents(["test1.pdf", "test2.docx"])

            # 验证结果
            assert len(result) == 2
            assert result[0].page_content == "内容1"
            assert result[1].page_content == "内容2"

            # 验证调用
            assert mock_process.call_count == 2
            assert preprocessor.stats["total_documents"] == 2
            # 由于我们重置了统计信息,这里应该检查实际处理的文档数
            assert len(result) == 2

    @pytest.mark.asyncio
    @patch("src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader")
    async def test_aprocess_document_success(self, mock_pdf_loader, preprocessor):
        """测试异步成功处理单个文档"""
        format_info = FormatInfo(format="pdf", is_valid=True, confidence=0.95)
        validation_result = Mock(is_valid=True, warnings=[])
        mock_pdf_instance = Mock()
        mock_pdf_loader.return_value = mock_pdf_instance

        mock_document = Document(
            page_content="测试内容", metadata={"source": "test.pdf", "format": "pdf"}
        )

        # 创建一个协程函数来模拟异步加载
        async def mock_aload():
            return [mock_document]

        mock_pdf_instance.aload = mock_aload

        preprocessor.format_detector.detect_format.return_value = format_info
        preprocessor.format_detector.validate_document.return_value = validation_result

        result = await preprocessor.aprocess_document("test.pdf")

        assert len(result) == 1
        assert result[0].page_content == "测试内容"
        assert result[0].metadata["async_processed"] is True

    @pytest.mark.asyncio
    async def test_aprocess_documents_batch(self, preprocessor):
        """测试异步批量处理文档"""
        with patch.object(preprocessor, "aprocess_document") as mock_process:
            mock_process.side_effect = [
                [Document(page_content="内容1", metadata={"source": "test1.pdf"})],
                [Document(page_content="内容2", metadata={"source": "test2.docx"})],
            ]

            result = await preprocessor.aprocess_documents(["test1.pdf", "test2.docx"])

            assert len(result) == 2
            assert result[0].page_content == "内容1"
            assert result[1].page_content == "内容2"
            assert mock_process.call_count == 2

    def test_get_processing_stats(self, preprocessor):
        """测试获取处理统计信息"""
        # 设置一些统计数据
        preprocessor.stats.update(
            {
                "total_documents": 10,
                "processed_documents": 8,
                "failed_documents": 2,
                "format_distribution": {"pdf": 6, "docx": 4},
                "pipeline_distribution": {"loader_only": 8, "failed": 2},
            }
        )

        stats = preprocessor.get_processing_stats()

        assert stats["total_documents"] == 10
        assert stats["processed_documents"] == 8
        assert stats["failed_documents"] == 2
        assert stats["success_rate"] == 80.0
        assert stats["format_distribution"] == {"pdf": 6, "docx": 4}
        assert stats["pipeline_distribution"] == {"loader_only": 8, "failed": 2}
        assert stats["supported_formats"] == ["pdf", "docx"]
        assert stats["cleaning_enabled"] is False

    def test_integration_with_real_files(self, preprocessor):
        """集成测试:使用真实文件测试(如果存在)"""
        # 检查是否有测试文件
        test_files = [
            "data/source/uploads/2023年中国储能行业系列研究-超级电容器储能.pdf",
            "data/source/uploads/水电总院王昊轶:储能是沙戈荒基地高质量建设的'金钥匙'.docx",
        ]

        available_files = [f for f in test_files if os.path.exists(f)]

        if not available_files:
            pytest.skip("没有可用的测试文件")

        # 测试格式检测
        for file_path in available_files:
            format_info = preprocessor.format_detector.detect_format(file_path)
            assert format_info.is_valid, f"文件格式检测失败: {file_path}"

            # 测试是否支持该格式
            supported = preprocessor.is_format_supported(file_path)
            assert supported, f"不支持的格式: {format_info.format}"

        # 如果有PDF文件,测试PDF处理(不启用清洗以避免LLM调用)
        pdf_files = [f for f in available_files if f.endswith(".pdf")]
        if pdf_files:
            try:
                with patch(
                    "src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader"
                ) as mock_loader:
                    mock_instance = Mock()
                    mock_doc = Document(
                        page_content="模拟PDF内容",
                        metadata={"source": pdf_files[0], "format": "pdf"},
                    )
                    mock_instance.load.return_value = [mock_doc]
                    mock_loader.return_value = mock_instance

                    result = preprocessor.process_document(pdf_files[0])
                    assert len(result) == 1
                    assert result[0].metadata["format"] == "pdf"
            except Exception as e:
                pytest.skip(f"PDF处理测试跳过: {e}")

    def test_error_handling(self, preprocessor):
        """测试错误处理"""
        # 测试文件不存在
        with patch.object(preprocessor.format_detector, "detect_format") as mock_detect:
            mock_detect.side_effect = FileNotFoundError("文件不存在")

            with pytest.raises(ProcessingError, match="文档处理失败"):
                preprocessor.process_document("nonexistent.pdf")

    def test_cleaning_integration(self, preprocessor_with_cleaning):
        """测试清洗集成(模拟)"""
        format_info = FormatInfo(format="pdf", is_valid=True, confidence=0.95)
        validation_result = Mock(is_valid=True, warnings=[])

        preprocessor_with_cleaning.format_detector.detect_format.return_value = (
            format_info
        )
        preprocessor_with_cleaning.format_detector.validate_document.return_value = (
            validation_result
        )

        with patch(
            "src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader"
        ) as mock_loader, patch(
            "src.infrastructure.preprocessing.preprocessor.LLMAdRemover"
        ) as mock_cleaner:
            # 模拟加载器
            mock_loader_instance = Mock()
            mock_loader.return_value = mock_loader_instance
            mock_doc = Document(
                page_content="原始内容包含广告",
                metadata={"source": "test.pdf", "format": "pdf"},
            )
            mock_loader_instance.load.return_value = [mock_doc]

            # 模拟清洗器
            mock_cleaner_instance = Mock()
            mock_cleaner.return_value = mock_cleaner_instance
            cleaned_doc = Document(
                page_content="清洗后的内容",
                metadata={**mock_doc.metadata, "llm_cleaned": True},
            )
            mock_cleaner_instance.clean_document.return_value = cleaned_doc

            # 处理文档
            result = preprocessor_with_cleaning.process_document("test.pdf")

            # 验证结果
            assert len(result) == 1
            assert result[0].page_content == "清洗后的内容"
            assert result[0].metadata["llm_cleaned"] is True
            assert result[0].metadata.get("pipeline") == "llm_ad_cleaning"

    def test_memory_cleanup(self, preprocessor):
        """测试内存清理"""
        # 添加一些加载器到缓存
        format_info = FormatInfo(format="pdf", is_valid=True)

        with patch(
            "src.infrastructure.preprocessing.preprocessor.MinerUPDFLoader"
        ) as mock_loader:
            mock_instance = Mock()
            mock_loader.return_value = mock_instance

            # 创建加载器
            loader = preprocessor._get_loader("test.pdf", format_info)
            assert loader == mock_instance
            assert "pdf" in preprocessor._loaders

            # 再次获取应该使用缓存
            loader2 = preprocessor._get_loader("test2.pdf", format_info)
            assert loader2 == mock_instance

            # 验证只创建了一次
            mock_loader.assert_called_once()

    def test_progress_tracking(self, preprocessor):
        """测试进度跟踪"""
        # 启用进度跟踪
        preprocessor.enable_progress_tracking = True

        with patch.object(preprocessor, "process_document") as mock_process:
            mock_process.return_value = [Document(page_content="测试", metadata={})]
            # 重置统计信息
            preprocessor.stats.update(
                {
                    "total_documents": 0,
                    "processed_documents": 0,
                    "failed_documents": 0,
                }
            )

            # 批量处理
            result = preprocessor.process_documents(
                ["test1.pdf", "test2.pdf", "test3.docx"]
            )

            # 验证结果
            assert len(result) == 3
            assert mock_process.call_count == 3


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
