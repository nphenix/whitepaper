"""
预处理文档领域模型测试

该模块包含PreprocessedDocument领域模型的单元测试。
"""

# 生成命令: /speckit.implement T024
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import timedelta

import pytest

from src.domain.document.preprocessed_document import (
    CleaningLevel,
    PreprocessedDocument,
    ProcessingStatus,
)


class TestPreprocessedDocument:
    """PreprocessedDocument模型测试类"""

    def test_create_preprocessed_document(self):
        """测试创建预处理文档"""
        doc_id = uuid.uuid4()
        content_hash = "abc123def456"

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="这是处理后的文档内容",
            original_content_hash=content_hash,
            cleaning_level=CleaningLevel.STANDARD,
            processing_steps=["text_cleaning", "format_normalization"],
            original_length=100,
            processed_length=80,
        )

        assert doc.original_document_id == doc_id
        assert doc.content == "这是处理后的文档内容"
        assert doc.original_content_hash == content_hash
        assert doc.processing_status == ProcessingStatus.PENDING
        assert doc.cleaning_level == CleaningLevel.STANDARD
        assert doc.processing_steps == ["text_cleaning", "format_normalization"]
        assert doc.original_length == 100
        assert doc.processed_length == 80
        assert doc.compression_ratio == 0.8

    def test_content_validation(self):
        """测试内容验证"""
        doc_id = uuid.uuid4()

        # 测试空内容
        with pytest.raises(ValueError, match="预处理后的内容不能为空"):
            PreprocessedDocument(
                original_document_id=doc_id,
                content="",
                original_content_hash="abc123",
                cleaning_level=CleaningLevel.BASIC,
                processing_steps=["clean"],
                original_length=10,
                processed_length=8,
            )

        # 测试只有空白字符的内容
        with pytest.raises(ValueError, match="预处理后的内容不能为空"):
            PreprocessedDocument(
                original_document_id=doc_id,
                content="   \n\t  ",
                original_content_hash="abc123",
                cleaning_level=CleaningLevel.BASIC,
                processing_steps=["clean"],
                original_length=10,
                processed_length=8,
            )

    def test_hash_validation(self):
        """测试哈希值验证"""
        doc_id = uuid.uuid4()

        # 测试空哈希
        with pytest.raises(ValueError, match="原始内容哈希值无效"):
            PreprocessedDocument(
                original_document_id=doc_id,
                content="内容",
                original_content_hash="",
                cleaning_level=CleaningLevel.BASIC,
                processing_steps=["clean"],
                original_length=10,
                processed_length=8,
            )

        # 测试过短的哈希
        with pytest.raises(ValueError, match="原始内容哈希值无效"):
            PreprocessedDocument(
                original_document_id=doc_id,
                content="内容",
                original_content_hash="abc",
                cleaning_level=CleaningLevel.BASIC,
                processing_steps=["clean"],
                original_length=10,
                processed_length=8,
            )

    def test_processing_steps_validation(self):
        """测试处理步骤验证"""
        doc_id = uuid.uuid4()

        # 测试空处理步骤
        with pytest.raises(ValueError, match="处理步骤列表不能为空"):
            PreprocessedDocument(
                original_document_id=doc_id,
                content="内容",
                original_content_hash="abc123def456",
                cleaning_level=CleaningLevel.BASIC,
                processing_steps=[],
                original_length=10,
                processed_length=8,
            )

    def test_length_consistency_validation(self):
        """测试长度一致性验证"""
        doc_id = uuid.uuid4()

        # 测试处理后长度大于原始长度
        with pytest.raises(ValueError, match="处理后内容长度不能大于原始内容长度"):
            PreprocessedDocument(
                original_document_id=doc_id,
                content="内容",
                original_content_hash="abc123def456",
                cleaning_level=CleaningLevel.BASIC,
                processing_steps=["clean"],
                original_length=10,
                processed_length=15,
            )

    def test_start_processing(self):
        """测试开始处理"""
        doc_id = uuid.uuid4()

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="内容",
            original_content_hash="abc123def456",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=10,
            processed_length=8,
        )

        # 测试开始处理
        doc.start_processing()
        assert doc.processing_status == ProcessingStatus.PROCESSING
        assert doc.started_at is not None

        # 测试重复开始处理
        with pytest.raises(ValueError, match="只有待处理的文档可以开始处理"):
            doc.start_processing()

    def test_complete_processing_success(self):
        """测试成功完成处理"""
        doc_id = uuid.uuid4()

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="内容",
            original_content_hash="abc123def456",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=10,
            processed_length=8,
        )

        doc.start_processing()
        doc.complete_processing(quality_score=0.9)

        assert doc.processing_status == ProcessingStatus.COMPLETED
        assert doc.completed_at is not None
        assert doc.quality_score == 0.9
        assert doc.error_message is None

    def test_complete_processing_failure(self):
        """测试处理失败"""
        doc_id = uuid.uuid4()

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="内容",
            original_content_hash="abc123def456",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=10,
            processed_length=8,
        )

        doc.start_processing()
        doc.complete_processing(error_message="处理失败: 格式错误")

        assert doc.processing_status == ProcessingStatus.FAILED
        assert doc.completed_at is not None
        assert doc.error_message == "处理失败: 格式错误"
        assert doc.quality_score is None

    def test_add_processing_step(self):
        """测试添加处理步骤"""
        doc_id = uuid.uuid4()

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="内容",
            original_content_hash="abc123def456",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=10,
            processed_length=8,
        )

        # 添加新步骤
        doc.add_processing_step("normalize", {"param": "value"})
        assert "normalize" in doc.processing_steps

        # 添加步骤元数据
        metadata = doc.get_processing_metadata("normalize")
        assert metadata == {"param": "value"}

        # 重复添加相同步骤
        doc.add_processing_step("normalize", {"param2": "value2"})
        assert doc.processing_steps.count("normalize") == 1

        # 元数据应该被合并
        metadata = doc.get_processing_metadata("normalize")
        assert metadata == {"param": "value", "param2": "value2"}

    def test_metadata_operations(self):
        """测试元数据操作"""
        doc_id = uuid.uuid4()

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="内容",
            original_content_hash="abc123def456",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=10,
            processed_length=8,
        )

        # 添加和获取元数据
        doc.add_metadata("author", "测试作者")
        assert doc.get_metadata("author") == "测试作者"
        assert doc.get_metadata("nonexistent", "default") == "default"

    def test_processing_duration(self):
        """测试处理持续时间"""
        doc_id = uuid.uuid4()

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="内容",
            original_content_hash="abc123def456",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=10,
            processed_length=8,
        )

        # 未开始处理
        assert doc.get_processing_duration() is None

        # 开始处理但未完成
        doc.start_processing()
        assert doc.get_processing_duration() is None

        # 完成处理
        # 手动设置完成时间为开始时间后5秒
        doc.completed_at = doc.started_at + timedelta(seconds=5)
        assert doc.get_processing_duration() == 5.0

    def test_content_summary(self):
        """测试内容摘要"""
        doc_id = uuid.uuid4()

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="这是一段较长的文档内容, 用于测试摘要功能",
            original_content_hash="abc123def456",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=30,
            processed_length=25,
        )

        # 短内容应该完整返回
        short_summary = doc.get_content_summary(50)
        assert short_summary == "这是一段较长的文档内容, 用于测试摘要功能"

        # 长内容应该截断
        long_summary = doc.get_content_summary(10)
        assert long_summary == "这是一段较长的文档内..."

    def test_status_check_methods(self):
        """测试状态检查方法"""
        doc_id = uuid.uuid4()

        doc = PreprocessedDocument(
            original_document_id=doc_id,
            content="内容",
            original_content_hash="abc123def456",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=10,
            processed_length=8,
        )

        # 初始状态
        assert doc.is_processed() is False
        assert doc.is_failed() is False
        assert doc.is_processing() is False

        # 处理中状态
        doc.start_processing()
        assert doc.is_processed() is False
        assert doc.is_failed() is False
        assert doc.is_processing() is True

        # 完成状态
        doc.complete_processing()
        assert doc.is_processed() is True
        assert doc.is_failed() is False
        assert doc.is_processing() is False

        # 失败状态
        doc2 = PreprocessedDocument(
            original_document_id=uuid.uuid4(),
            content="内容2",
            original_content_hash="def456abc123",
            cleaning_level=CleaningLevel.BASIC,
            processing_steps=["clean"],
            original_length=10,
            processed_length=8,
        )
        doc2.start_processing()
        doc2.complete_processing(error_message="错误")
        assert doc2.is_processed() is False
        assert doc2.is_failed() is True
        assert doc2.is_processing() is False
