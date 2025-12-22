"""
T060 预处理结果读取器测试

测试预处理结果读取器的功能。
"""

import json
import tempfile
from pathlib import Path

import pytest
from langchain_core.documents import Document

from src.infrastructure.parsing.loaders.preprocessed_document_reader import (
    PreprocessedDocumentReader,
)


class TestPreprocessedDocumentReader:
    """PreprocessedDocumentReader测试类"""

    def test_load_clean_md(self):
        """测试读取clean.md文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建测试目录结构
            test_dir = Path(tmpdir) / "test_doc" / "extracted"
            test_dir.mkdir(parents=True, exist_ok=True)

            # 创建clean.md文件
            clean_md = test_dir / "clean.md"
            clean_md.write_text("# 测试文档\n\n这是测试内容。", encoding="utf-8")

            # 创建读取器并加载
            reader = PreprocessedDocumentReader(source=str(test_dir))
            documents = reader.load()

            assert len(documents) == 1
            assert documents[0].page_content == "# 测试文档\n\n这是测试内容。"
            assert documents[0].metadata["source"] == str(test_dir)
            assert documents[0].metadata["preprocessed"] is True

    def test_load_with_content_list(self):
        """测试读取clean_content_list.json"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_doc" / "extracted"
            test_dir.mkdir(parents=True, exist_ok=True)

            # 创建clean.md
            clean_md = test_dir / "clean.md"
            clean_md.write_text("# 测试", encoding="utf-8")

            # 创建clean_content_list.json
            content_list = [
                {"type": "text", "text": "测试", "page_idx": 0},
                {"type": "header", "text": "标题", "page_idx": 0},
            ]
            content_list_file = test_dir / "clean_content_list.json"
            content_list_file.write_text(
                json.dumps(content_list, ensure_ascii=False), encoding="utf-8"
            )

            reader = PreprocessedDocumentReader(source=str(test_dir))
            documents = reader.load()

            assert len(documents) == 1
            assert "content_list" in documents[0].metadata
            assert len(documents[0].metadata["content_list"]) == 2

    def test_load_with_images(self):
        """测试关联图片信息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_doc" / "extracted"
            test_dir.mkdir(parents=True, exist_ok=True)

            # 创建clean.md
            clean_md = test_dir / "clean.md"
            clean_md.write_text("# 测试", encoding="utf-8")

            # 创建images目录和文件
            images_dir = test_dir / "images"
            images_dir.mkdir()
            (images_dir / "image1.jpg").write_bytes(b"fake image data")
            (images_dir / "image2.png").write_bytes(b"fake image data")

            reader = PreprocessedDocumentReader(
                source=str(test_dir), include_images=True
            )
            documents = reader.load()

            assert len(documents) == 1
            assert "images" in documents[0].metadata
            assert documents[0].metadata["images"]["count"] == 2
            assert len(documents[0].metadata["images"]["files"]) == 2

    def test_load_with_charts(self):
        """测试关联图表JSON信息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_doc" / "extracted"
            test_dir.mkdir(parents=True, exist_ok=True)

            # 创建clean.md
            clean_md = test_dir / "clean.md"
            clean_md.write_text("# 测试", encoding="utf-8")

            # 创建datajson目录和文件
            datajson_dir = test_dir / "datajson"
            datajson_dir.mkdir()
            chart1 = datajson_dir / "chart1.json"
            chart1.write_text(
                json.dumps({"type": "bar", "data": [1, 2, 3]}), encoding="utf-8"
            )

            reader = PreprocessedDocumentReader(
                source=str(test_dir), include_charts=True
            )
            documents = reader.load()

            assert len(documents) == 1
            assert "charts" in documents[0].metadata
            assert documents[0].metadata["charts"]["count"] == 1
            assert len(documents[0].metadata["charts"]["charts"]) == 1

    def test_load_missing_clean_md(self):
        """测试缺少clean.md文件的情况"""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir) / "test_doc" / "extracted"
            test_dir.mkdir(parents=True, exist_ok=True)

            reader = PreprocessedDocumentReader(source=str(test_dir))

            from src.infrastructure.preprocessing.loaders.base_loader import (
                DocumentNotFoundError,
            )

            with pytest.raises(DocumentNotFoundError):
                reader.load()

    def test_load_from_multiple_directories(self):
        """测试批量加载多个目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建两个测试目录
            dir1 = Path(tmpdir) / "doc1" / "extracted"
            dir1.mkdir(parents=True, exist_ok=True)
            (dir1 / "clean.md").write_text("# 文档1", encoding="utf-8")

            dir2 = Path(tmpdir) / "doc2" / "extracted"
            dir2.mkdir(parents=True, exist_ok=True)
            (dir2 / "clean.md").write_text("# 文档2", encoding="utf-8")

            documents = PreprocessedDocumentReader.load_from_multiple_directories(
                [str(dir1), str(dir2)]
            )

            assert len(documents) == 2
            assert documents[0].page_content == "# 文档1"
            assert documents[1].page_content == "# 文档2"

