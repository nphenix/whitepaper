"""
DocumentChunk领域模型单元测试

测试文档块的创建、验证和业务方法。
"""

import uuid
import time
from datetime import datetime

import pytest

from src.domain.knowledge_base import ChunkType, DocumentChunk


class TestDocumentChunk:
    """DocumentChunk领域模型测试类"""

    def test_create_document_chunk_basic(self):
        """测试创建基本文档块"""
        # 准备测试数据
        document_id = uuid.uuid4()
        chunk_index = 0
        content = "这是一个测试文档块的内容。"
        start_position = 0
        end_position = 20
        section_path = "1.1"
        section_title = "引言"

        # 创建文档块
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            start_position=start_position,
            end_position=end_position,
            section_path=section_path,
            section_title=section_title
        )

        # 验证基本属性
        assert chunk.document_id == document_id
        assert chunk.chunk_index == chunk_index
        assert chunk.content == content
        assert chunk.start_position == start_position
        assert chunk.end_position == end_position
        assert chunk.section_path == section_path
        assert chunk.section_title == section_title
        assert chunk.chunk_type == ChunkType.PARAGRAPH  # 默认值

        # 验证时间字段
        assert isinstance(chunk.created_at, datetime)

    def test_create_document_chunk_with_type(self):
        """测试创建带类型的文档块"""
        document_id = uuid.uuid4()
        
        # 创建标题类型的文档块
        heading_chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=0,
            content="# 第一章",
            start_position=0,
            end_position=10,
            section_path="1",
            chunk_type=ChunkType.HEADING
        )

        assert heading_chunk.chunk_type == ChunkType.HEADING
        assert heading_chunk.is_heading_chunk() is True
        assert heading_chunk.is_paragraph_chunk() is False

        # 创建表格类型的文档块
        table_chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=1,
            content="| 列1 | 列2 |\n|-----|-----|\n| 值1 | 值2 |",
            start_position=11,
            end_position=50,
            section_path="1.1",
            chunk_type=ChunkType.TABLE
        )

        assert table_chunk.chunk_type == ChunkType.TABLE
        assert table_chunk.is_table_chunk() is True
        assert table_chunk.is_code_chunk() is False

    def test_validate_content_not_empty(self):
        """验证内容不能为空"""
        document_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="文档块内容不能为空"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="",
                start_position=0,
                end_position=0,
                section_path="1"
            )

        with pytest.raises(ValueError, match="文档块内容不能为空"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="   ",
                start_position=0,
                end_position=3,
                section_path="1"
            )

    def test_validate_chunk_index_non_negative(self):
        """验证块索引必须非负"""
        document_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="块索引必须非负"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=-1,
                content="测试内容",
                start_position=0,
                end_position=10,
                section_path="1"
            )

    def test_validate_positions_non_negative(self):
        """验证位置必须非负"""
        document_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="位置必须非负"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="测试内容",
                start_position=-1,
                end_position=10,
                section_path="1"
            )

        with pytest.raises(ValueError, match="位置必须非负"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="测试内容",
                start_position=0,
                end_position=-1,
                section_path="1"
            )

    def test_validate_position_relationship(self):
        """验证位置关系"""
        document_id = uuid.uuid4()
        
        with pytest.raises(ValueError, match="起始位置.*必须小于结束位置"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="测试内容",
                start_position=10,
                end_position=10,
                section_path="1"
            )

        with pytest.raises(ValueError, match="起始位置.*必须小于结束位置"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="测试内容",
                start_position=10,
                end_position=5,
                section_path="1"
            )

    def test_validate_section_path_format(self):
        """验证章节路径格式"""
        document_id = uuid.uuid4()
        
        # 有效的章节路径
        valid_paths = ["1", "1.1", "1.2.3", "10.20.30"]
        for path in valid_paths:
            chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="测试内容",
                start_position=0,
                end_position=10,
                section_path=path
            )
            assert chunk.section_path == path

        # 无效的章节路径
        invalid_paths = ["1.", ".1", "1..2", "a.b.c", "1.2a.3"]
        for path in invalid_paths:
            with pytest.raises(ValueError, match="章节路径格式无效"):
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=0,
                    content="测试内容",
                    start_position=0,
                    end_position=10,
                    section_path=path
                )
        
        # 空字符串和空格字符串测试（单独处理，因为错误消息不同）
        with pytest.raises(ValueError, match="章节路径不能为空"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="测试内容",
                start_position=0,
                end_position=10,
                section_path=""
            )
        
        with pytest.raises(ValueError, match="章节路径不能为空"):
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                content="测试内容",
                start_position=0,
                end_position=10,
                section_path="   "
            )

    def test_get_content_length(self):
        """测试获取内容长度"""
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="这是一个测试内容",
            start_position=0,
            end_position=20,
            section_path="1"
        )

        assert chunk.get_content_length() == 8  # "这是一个测试内容"的字符数（去除空格后）

    def test_get_content_word_count(self):
        """测试获取内容词数"""
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="This is a test content with some words.",
            start_position=0,
            end_position=50,
            section_path="1"
        )

        assert chunk.get_content_word_count() == 8  # 英文单词数

        # 测试中文内容
        chinese_chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="这是一个包含中文的测试内容，用来测试词数统计功能。",
            start_position=0,
            end_position=50,
            section_path="1"
        )

        # 中文词数统计基于英文单词模式，所以结果可能不同
        # 这里我们验证方法能正常工作，而不是精确的词数
        word_count = chinese_chunk.get_content_word_count()
        assert isinstance(word_count, int)
        assert word_count > 0

    def test_get_section_depth(self):
        """测试获取章节深度"""
        test_cases = [
            ("1", 1),
            ("1.1", 2),
            ("1.2.3", 3),
            ("10.20.30.40", 4)
        ]

        for section_path, expected_depth in test_cases:
            chunk = DocumentChunk(
                document_id=uuid.uuid4(),
                chunk_index=0,
                content="测试内容",
                start_position=0,
                end_position=10,
                section_path=section_path
            )
            assert chunk.get_section_depth() == expected_depth

    def test_get_parent_section_path(self):
        """测试获取父章节路径"""
        # 无父章节
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="测试内容",
            start_position=0,
            end_position=10,
            section_path="1"
        )
        assert chunk.get_parent_section_path() is None

        # 有父章节
        chunk_with_parent = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="测试内容",
            start_position=0,
            end_position=10,
            section_path="1.2.3"
        )
        assert chunk_with_parent.get_parent_section_path() == "1.2"

    def test_is_type_methods(self):
        """测试类型检查方法"""
        # 测试段落块
        paragraph_chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="这是一个段落。",
            start_position=0,
            end_position=10,
            section_path="1",
            chunk_type=ChunkType.PARAGRAPH
        )
        assert paragraph_chunk.is_paragraph_chunk() is True
        assert paragraph_chunk.is_heading_chunk() is False
        assert paragraph_chunk.is_table_chunk() is False
        assert paragraph_chunk.is_code_chunk() is False

        # 测试标题块
        heading_chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="# 标题",
            start_position=0,
            end_position=10,
            section_path="1",
            chunk_type=ChunkType.HEADING
        )
        assert heading_chunk.is_heading_chunk() is True
        assert heading_chunk.is_paragraph_chunk() is False

        # 测试表格块
        table_chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="| 表格 | 内容 |",
            start_position=0,
            end_position=10,
            section_path="1",
            chunk_type=ChunkType.TABLE
        )
        assert table_chunk.is_table_chunk() is True
        assert table_chunk.is_paragraph_chunk() is False

        # 测试代码块
        code_chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="print('Hello, World!')",
            start_position=0,
            end_position=10,
            section_path="1",
            chunk_type=ChunkType.CODE
        )
        assert code_chunk.is_code_chunk() is True
        assert code_chunk.is_paragraph_chunk() is False

    def test_add_and_get_metadata(self):
        """测试元数据添加和获取功能"""
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="测试内容",
            start_position=0,
            end_position=10,
            section_path="1"
        )

        # 添加元数据
        chunk.add_metadata("key1", "value1")
        chunk.add_metadata("key2", 123)
        chunk.add_metadata("key3", {"nested": "data"})

        # 获取元数据
        assert chunk.get_metadata("key1") == "value1"
        assert chunk.get_metadata("key2") == 123
        assert chunk.get_metadata("key3") == {"nested": "data"}
        assert chunk.get_metadata("nonexistent") is None
        assert chunk.get_metadata("nonexistent", "default") == "default"

    def test_has_metadata(self):
        """测试检查元数据是否存在"""
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="测试内容",
            start_position=0,
            end_position=10,
            section_path="1",
            metadata={"existing": "value"}
        )

        assert chunk.has_metadata("existing") is True
        assert chunk.has_metadata("nonexistent") is False

    def test_get_position_info(self):
        """测试获取位置信息"""
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=5,
            content="测试内容",
            start_position=100,
            end_position=150,
            section_path="1.2.3"
        )

        position_info = chunk.get_position_info()
        
        assert position_info["start_position"] == 100
        assert position_info["end_position"] == 150
        assert position_info["length"] == 50
        assert position_info["chunk_index"] == 5

    def test_get_section_info(self):
        """测试获取章节信息"""
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="测试内容",
            start_position=0,
            end_position=10,
            section_path="1.2.3",
            section_title="测试章节"
        )

        section_info = chunk.get_section_info()
        
        assert section_info["section_path"] == "1.2.3"
        assert section_info["section_title"] == "测试章节"
        assert section_info["section_depth"] == 3
        assert section_info["parent_section_path"] == "1.2"

    def test_get_content_preview(self):
        """测试获取内容预览"""
        short_content = "短内容"
        long_content = "这是一个很长的内容，用来测试预览功能，当内容超过指定长度时应该被截断。"

        # 短内容测试
        short_chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content=short_content,
            start_position=0,
            end_position=len(short_content),
            section_path="1"
        )
        assert short_chunk.get_content_preview() == short_content
        assert short_chunk.get_content_preview(10) == short_content

        # 长内容测试
        long_chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content=long_content,
            start_position=0,
            end_position=len(long_content),
            section_path="1"
        )
        preview = long_chunk.get_content_preview(20)
        assert len(preview) <= 23  # 20字符 + "..."
        assert preview.endswith("...")
        assert long_content.startswith(preview[:-3])

    def test_contains_keyword(self):
        """测试检查内容是否包含关键词"""
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content="This is a test content with keyword.",
            start_position=0,
            end_position=50,
            section_path="1"
        )

        # 测试包含关键词
        assert chunk.contains_keyword("test") is True
        assert chunk.contains_keyword("keyword") is True
        assert chunk.contains_keyword("Test") is True  # 默认不区分大小写

        # 测试不包含关键词
        assert chunk.contains_keyword("nonexistent") is False
        assert chunk.contains_keyword("") is False

        # 测试区分大小写
        assert chunk.contains_keyword("Test", case_sensitive=False) is True
        assert chunk.contains_keyword("Test", case_sensitive=True) is False

    def test_get_keyword_positions(self):
        """测试获取关键词在内容中的位置列表"""
        content = "test is a Test, and another test."
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            chunk_index=0,
            content=content,
            start_position=0,
            end_position=len(content),
            section_path="1"
        )

        # 测试关键词位置
        positions = chunk.get_keyword_positions("test")
        assert len(positions) == 3  # 找到3个test（包括大写的Test，因为默认不区分大小写）
        assert positions[0] == 0
        assert positions[1] == 10  # "Test"的位置
        assert positions[2] == 28  # 最后一个test的位置

        # 测试区分大小写
        positions_case_sensitive = chunk.get_keyword_positions("test", case_sensitive=True)
        assert len(positions_case_sensitive) == 2  # 只有2个小写的test
        assert positions_case_sensitive[0] == 0
        assert positions_case_sensitive[1] == 28
        
        # 测试大写关键词
        positions_upper = chunk.get_keyword_positions("Test", case_sensitive=True)
        assert len(positions_upper) == 1  # 只有一个大写的Test
        assert positions_upper[0] == 10

        # 测试不存在的关键词
        positions_nonexistent = chunk.get_keyword_positions("nonexistent")
        assert len(positions_nonexistent) == 0

        # 测试空关键词
        positions_empty = chunk.get_keyword_positions("")
        assert len(positions_empty) == 0

    def test_to_dict(self):
        """测试转换为字典"""
        document_id = uuid.uuid4()
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=0,
            content="测试内容",
            start_position=0,
            end_position=10,
            section_path="1.1",
            section_title="测试章节",
            chunk_type=ChunkType.HEADING,
            metadata={"test": "value"}
        )

        chunk_dict = chunk.to_dict()

        # 验证字典内容
        assert chunk_dict["id"] == str(chunk.id)
        assert chunk_dict["document_id"] == str(document_id)
        assert chunk_dict["chunk_index"] == 0
        assert chunk_dict["content"] == "测试内容"
        assert chunk_dict["start_position"] == 0
        assert chunk_dict["end_position"] == 10
        assert chunk_dict["section_path"] == "1.1"
        assert chunk_dict["section_title"] == "测试章节"
        assert chunk_dict["chunk_type"] == ChunkType.HEADING.value
        assert chunk_dict["created_at"] is not None
        assert chunk_dict["metadata"] == {"test": "value"}

    def test_content_stripping(self):
        """测试内容自动去除前后空格"""
        document_id = uuid.uuid4()
        
        # 测试内容去除前后空格
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=0,
            content="  测试内容  ",
            start_position=0,
            end_position=12,
            section_path="1"
        )
        
        assert chunk.content == "测试内容"
        assert chunk.start_position == 0
        assert chunk.end_position == 12  # 位置不变，只处理内容

    def test_section_path_stripping(self):
        """测试章节路径去除前后空格"""
        document_id = uuid.uuid4()
        
        # 测试章节路径去除前后空格
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=0,
            content="测试内容",
            start_position=0,
            end_position=10,
            section_path="  1.2.3  "
        )
        
        assert chunk.section_path == "1.2.3"

    def test_default_metadata(self):
        """测试默认元数据"""
        document_id = uuid.uuid4()
        
        chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=0,
            content="测试内容",
            start_position=0,
            end_position=10,
            section_path="1"
        )
        
        assert chunk.metadata == {}
        assert chunk.has_metadata("any_key") is False

    def test_chunk_type_enum(self):
        """测试块类型枚举"""
        assert ChunkType.PARAGRAPH.value == "PARAGRAPH"
        assert ChunkType.HEADING.value == "HEADING"
        assert ChunkType.LIST_ITEM.value == "LIST_ITEM"
        assert ChunkType.TABLE.value == "TABLE"
        assert ChunkType.CODE.value == "CODE"
        assert ChunkType.QUOTE.value == "QUOTE"
        assert ChunkType.IMAGE.value == "IMAGE"
        assert ChunkType.OTHER.value == "OTHER"