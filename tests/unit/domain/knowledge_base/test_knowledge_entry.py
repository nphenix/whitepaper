"""
KnowledgeEntry领域模型单元测试

测试知识库条目的领域模型功能,包括字段验证、业务方法和数据源管理。
"""

# 生成命令: /speckit.implement T041
# 生成时间: 2025-12-19
# 来源: specs/001-multi-agent-doc-system/tasks.md

import time
import uuid
from datetime import datetime

import pytest

from src.domain.knowledge_base.knowledge_entry import (
    EntrySourceType,
    KnowledgeEntry,
    SourceReferenceType,
)


class TestEntrySourceType:
    """测试条目来源类型枚举"""

    def test_enum_values(self) -> None:
        """测试枚举值"""
        assert EntrySourceType.UPLOADED_DOCUMENT == "UPLOADED_DOCUMENT"
        assert EntrySourceType.WEB_DATA_SOURCE == "WEB_DATA_SOURCE"


class TestSourceReferenceType:
    """测试来源引用类型枚举"""

    def test_enum_values(self) -> None:
        """测试枚举值"""
        assert SourceReferenceType.DOCUMENT_CHUNK == "DOCUMENT_CHUNK"
        assert SourceReferenceType.WEB_DATA_SOURCE == "WEB_DATA_SOURCE"


class TestKnowledgeEntry:
    """测试KnowledgeEntry领域模型"""

    def test_minimal_creation(self) -> None:
        """测试最小创建条件"""
        # 需要至少一个数据源
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(title="测试条目", document_id=doc_id, chunk_id=chunk_id)

        assert entry.title == "测试条目"
        assert entry.summary is None
        assert entry.tags == []
        assert entry.document_id == doc_id
        assert entry.chunk_id == chunk_id
        assert entry.web_data_source_id is None
        assert entry.source_url is None
        assert entry.source_path is None
        assert entry.metadata == {}
        assert isinstance(entry.id, uuid.UUID)
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.updated_at, datetime)

    def test_full_creation_with_document_source(self) -> None:
        """测试完整创建(文档来源)"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        now = datetime.utcnow()

        entry = KnowledgeEntry(
            title="文档条目",
            summary="这是一个测试摘要",
            tags=["标签1", "标签2"],
            document_id=doc_id,
            chunk_id=chunk_id,
            source_path="/path/to/document.pdf",
            metadata={"key": "value"},
            created_at=now,
            updated_at=now
        )

        assert entry.title == "文档条目"
        assert entry.summary == "这是一个测试摘要"
        assert entry.tags == ["标签1", "标签2"]
        assert entry.document_id == doc_id
        assert entry.chunk_id == chunk_id
        assert entry.web_data_source_id is None
        assert entry.source_url is None
        assert entry.source_path == "/path/to/document.pdf"
        assert entry.metadata == {"key": "value"}
        assert entry.created_at == now
        assert entry.updated_at == now

    def test_full_creation_with_web_source(self) -> None:
        """测试完整创建(网络来源)"""
        web_id = uuid.uuid4()
        now = datetime.utcnow()

        entry = KnowledgeEntry(
            title="网络条目",
            summary="这是一个网络摘要",
            tags=["网络", "测试"],
            web_data_source_id=web_id,
            source_url="https://example.com/article",
            metadata={"author": "测试作者"},
            created_at=now,
            updated_at=now
        )

        assert entry.title == "网络条目"
        assert entry.summary == "这是一个网络摘要"
        assert entry.tags == ["网络", "测试"]
        assert entry.document_id is None
        assert entry.chunk_id is None
        assert entry.web_data_source_id == web_id
        assert entry.source_url == "https://example.com/article"
        assert entry.source_path is None
        assert entry.metadata == {"author": "测试作者"}
        assert entry.created_at == now
        assert entry.updated_at == now

    def test_title_validation(self) -> None:
        """测试标题验证"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()

        # 正常标题
        entry = KnowledgeEntry(title="正常标题", document_id=doc_id, chunk_id=chunk_id)
        assert entry.title == "正常标题"

        # 空标题
        with pytest.raises(ValueError, match="条目标题不能为空"):
            KnowledgeEntry(title="", document_id=doc_id, chunk_id=chunk_id)

        with pytest.raises(ValueError, match="条目标题不能为空"):
            KnowledgeEntry(title="   ", document_id=doc_id, chunk_id=chunk_id)

        # 带空格的标题会被清理
        entry = KnowledgeEntry(title="  带空格标题  ", document_id=doc_id, chunk_id=chunk_id)
        assert entry.title == "带空格标题"

    def test_tags_validation(self) -> None:
        """测试标签验证"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()

        # 正常标签
        entry = KnowledgeEntry(
            title="测试",
            tags=["标签1", "标签2", "标签3"],
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.tags == ["标签1", "标签2", "标签3"]

        # 重复标签会被去重
        entry = KnowledgeEntry(
            title="测试",
            tags=["标签1", "标签2", "标签1", "标签3"],
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.tags == ["标签1", "标签2", "标签3"]

        # 空标签和空字符串会被过滤
        entry = KnowledgeEntry(
            title="测试",
            tags=["标签1", "", "  ", "标签2", "标签3"],
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.tags == ["标签1", "标签2", "标签3"]

        # 带空格的标签会被清理
        entry = KnowledgeEntry(
            title="测试",
            tags=["  标签1  ", " 标签2"],
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.tags == ["标签1", "标签2"]

    def test_source_url_validation(self) -> None:
        """测试来源URL验证"""
        # 正常URL
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=uuid.uuid4(),
            source_url="https://example.com"
        )
        assert entry.source_url == "https://example.com"

        # HTTP URL
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=uuid.uuid4(),
            source_url="http://example.com"
        )
        assert entry.source_url == "http://example.com"

        # 无效URL
        with pytest.raises(ValueError, match="来源URL必须以http://或https://开头"):
            KnowledgeEntry(
                title="测试",
                web_data_source_id=uuid.uuid4(),
                source_url="ftp://example.com"
            )

        with pytest.raises(ValueError, match="来源URL必须以http://或https://开头"):
            KnowledgeEntry(
                title="测试",
                web_data_source_id=uuid.uuid4(),
                source_url="example.com"
            )

        # URL会被清理
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=uuid.uuid4(),
            source_url="  https://example.com  "
        )
        assert entry.source_url == "https://example.com"

    def test_source_relationships_validation(self) -> None:
        """测试来源关系验证"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 有效:只有文档来源
        KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id
        )

        # 有效:只有网络来源
        KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id
        )

        # 无效:有document_id但没有chunk_id
        with pytest.raises(ValueError, match="document_id存在时, chunk_id也必须存在"):
            KnowledgeEntry(
                title="测试",
                document_id=doc_id
            )

        # 无效:有chunk_id但没有document_id
        with pytest.raises(ValueError, match="chunk_id存在时, document_id也必须存在"):
            KnowledgeEntry(
                title="测试",
                chunk_id=chunk_id
            )

        # 无效:同时有文档和网络来源
        with pytest.raises(ValueError, match="不能同时指定上传文档数据源和网络数据源"):
            KnowledgeEntry(
                title="测试",
                document_id=doc_id,
                chunk_id=chunk_id,
                web_data_source_id=web_id
            )

        # 无效:文档来源设置了source_url
        with pytest.raises(ValueError, match="用户上传文档不应设置source_url"):
            KnowledgeEntry(
                title="测试",
                document_id=doc_id,
                chunk_id=chunk_id,
                source_url="https://example.com"
            )

        # 无效:网络来源设置了source_path
        with pytest.raises(ValueError, match="网络数据源不应设置source_path"):
            KnowledgeEntry(
                title="测试",
                web_data_source_id=web_id,
                source_path="/path/to/file.pdf"
            )

    def test_get_source_type(self) -> None:
        """测试获取来源类型"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 文档来源
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.get_source_type() == EntrySourceType.UPLOADED_DOCUMENT

        # 网络来源
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id
        )
        assert entry.get_source_type() == EntrySourceType.WEB_DATA_SOURCE

    def test_is_from_uploaded_document(self) -> None:
        """测试是否来自上传文档"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 文档来源
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.is_from_uploaded_document() is True
        assert entry.is_from_web_data_source() is False

        # 网络来源
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id
        )
        assert entry.is_from_uploaded_document() is False
        assert entry.is_from_web_data_source() is True

    def test_is_from_web_data_source(self) -> None:
        """测试是否来自网络数据源"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 文档来源
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.is_from_web_data_source() is False

        # 网络来源
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id
        )
        assert entry.is_from_web_data_source() is True

    def test_add_tag(self) -> None:
        """测试添加标签"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(title="测试", tags=["标签1"], document_id=doc_id, chunk_id=chunk_id)
        original_updated_at = entry.updated_at

        # 添加小延迟确保时间戳不同
        time.sleep(0.001)

        # 添加新标签
        entry.add_tag("标签2")
        assert "标签2" in entry.tags
        assert "标签1" in entry.tags
        assert entry.updated_at >= original_updated_at

        # 添加重复标签(应该被忽略)
        entry.add_tag("标签1")
        assert entry.tags.count("标签1") == 1

        # 添加空标签(应该被忽略)
        entry.add_tag("")
        entry.add_tag("   ")
        entry.add_tag(None)
        assert "" not in entry.tags
        assert "   " not in entry.tags

    def test_remove_tag(self) -> None:
        """测试移除标签"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(title="测试", tags=["标签1", "标签2", "标签3"], document_id=doc_id, chunk_id=chunk_id)
        original_updated_at = entry.updated_at

        # 添加小延迟确保时间戳不同
        time.sleep(0.001)

        # 移除存在的标签
        result = entry.remove_tag("标签2")
        assert result is True
        assert "标签2" not in entry.tags
        assert "标签1" in entry.tags
        assert "标签3" in entry.tags
        assert entry.updated_at >= original_updated_at

        # 移除不存在的标签
        result = entry.remove_tag("不存在的标签")
        assert result is False
        assert entry.tags == ["标签1", "标签3"]

    def test_add_metadata(self) -> None:
        """测试添加元数据"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(title="测试", document_id=doc_id, chunk_id=chunk_id)
        original_updated_at = entry.updated_at

        # 添加小延迟确保时间戳不同
        time.sleep(0.001)

        # 添加元数据
        entry.add_metadata("key1", "value1")
        assert entry.metadata["key1"] == "value1"
        assert entry.updated_at >= original_updated_at

        # 覆盖元数据
        entry.add_metadata("key1", "new_value")
        assert entry.metadata["key1"] == "new_value"

    def test_get_metadata(self) -> None:
        """测试获取元数据"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(
            title="测试",
            metadata={"key1": "value1", "key2": "value2"},
            document_id=doc_id,
            chunk_id=chunk_id
        )

        # 获取存在的元数据
        assert entry.get_metadata("key1") == "value1"
        assert entry.get_metadata("key2") == "value2"

        # 获取不存在的元数据
        assert entry.get_metadata("key3") is None
        assert entry.get_metadata("key3", "default") == "default"

    def test_update_summary(self) -> None:
        """测试更新摘要"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(title="测试", summary="原始摘要", document_id=doc_id, chunk_id=chunk_id)
        original_updated_at = entry.updated_at

        # 添加小延迟确保时间戳不同
        time.sleep(0.001)

        # 更新摘要
        entry.update_summary("新摘要")
        assert entry.summary == "新摘要"
        assert entry.updated_at >= original_updated_at

        # 设置空摘要
        entry.update_summary("")
        assert entry.summary is None

        # 设置带空格的摘要
        entry.update_summary("  带空格摘要  ")
        assert entry.summary == "带空格摘要"

    def test_get_source_reference(self) -> None:
        """测试获取来源引用"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 文档来源
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id,
            source_path="/path/to/file.pdf"
        )
        ref = entry.get_source_reference()
        assert ref["source_type"] == SourceReferenceType.DOCUMENT_CHUNK.value
        assert ref["document_id"] == str(doc_id)
        assert ref["chunk_id"] == str(chunk_id)
        assert ref["source_path"] == "/path/to/file.pdf"

        # 网络来源
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id,
            source_url="https://example.com"
        )
        ref = entry.get_source_reference()
        assert ref["source_type"] == SourceReferenceType.WEB_DATA_SOURCE.value
        assert ref["web_data_source_id"] == str(web_id)
        assert ref["source_url"] == "https://example.com"

    def test_get_source_url(self) -> None:
        """测试获取来源URL"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 文档来源
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.get_source_url() is None

        # 网络来源
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id,
            source_url="https://example.com"
        )
        assert entry.get_source_url() == "https://example.com"

    def test_get_source_path(self) -> None:
        """测试获取来源文件路径"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 文档来源
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id,
            source_path="/path/to/file.pdf"
        )
        assert entry.get_source_path() == "/path/to/file.pdf"

        # 网络来源
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id
        )
        assert entry.get_source_path() is None

    def test_is_traceable(self) -> None:
        """测试是否可追溯"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 文档来源且有路径
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id,
            source_path="/path/to/file.pdf"
        )
        assert entry.is_traceable() is True

        # 文档来源但无路径
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id
        )
        assert entry.is_traceable() is False

        # 网络来源且有URL
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id,
            source_url="https://example.com"
        )
        assert entry.is_traceable() is True

        # 网络来源但无URL
        entry = KnowledgeEntry(
            title="测试",
            web_data_source_id=web_id
        )
        assert entry.is_traceable() is False

    def test_get_content_preview(self) -> None:
        """测试获取内容预览"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()

        # 无摘要
        entry = KnowledgeEntry(title="测试", document_id=doc_id, chunk_id=chunk_id)
        assert entry.get_content_preview() == ""

        # 短摘要
        entry = KnowledgeEntry(title="测试", summary="短摘要", document_id=doc_id, chunk_id=chunk_id)
        assert entry.get_content_preview() == "短摘要"

        # 长摘要
        long_summary = "这是一个很长的摘要" * 10
        entry = KnowledgeEntry(title="测试", summary=long_summary, document_id=doc_id, chunk_id=chunk_id)
        preview = entry.get_content_preview(50)
        assert len(preview) <= 53  # 50 + "..."
        assert preview.endswith("...")

        # 自定义最大长度
        preview = entry.get_content_preview(20)
        assert len(preview) <= 23  # 20 + "..."

    def test_has_tag(self) -> None:
        """测试是否包含标签"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(title="测试", tags=["标签1", "标签2", "标签3"], document_id=doc_id, chunk_id=chunk_id)

        assert entry.has_tag("标签1") is True
        assert entry.has_tag("标签2") is True
        assert entry.has_tag("标签3") is True
        assert entry.has_tag("不存在的标签") is False

    def test_get_tags_by_prefix(self) -> None:
        """测试获取指定前缀的标签"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(
            title="测试",
            tags=["技术:储能", "技术:电池", "应用:电网", "应用:调频", "其他"],
            document_id=doc_id,
            chunk_id=chunk_id
        )

        tech_tags = entry.get_tags_by_prefix("技术:")
        assert tech_tags == ["技术:储能", "技术:电池"]

        app_tags = entry.get_tags_by_prefix("应用:")
        assert app_tags == ["应用:电网", "应用:调频"]

        other_tags = entry.get_tags_by_prefix("其他")
        assert other_tags == ["其他"]

        empty_tags = entry.get_tags_by_prefix("不存在的:")
        assert empty_tags == []

    def test_merge_metadata(self) -> None:
        """测试合并元数据"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(
            title="测试",
            metadata={"key1": "value1", "key2": "value2"},
            document_id=doc_id,
            chunk_id=chunk_id
        )
        original_updated_at = entry.updated_at

        # 添加小延迟确保时间戳不同
        time.sleep(0.001)

        # 合并新元数据
        entry.merge_metadata({"key2": "new_value2", "key3": "value3"})
        assert entry.metadata["key1"] == "value1"  # 保持原值
        assert entry.metadata["key2"] == "new_value2"  # 覆盖原值
        assert entry.metadata["key3"] == "value3"  # 新增值
        assert entry.updated_at >= original_updated_at

    def test_remove_metadata(self) -> None:
        """测试移除元数据"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        entry = KnowledgeEntry(
            title="测试",
            metadata={"key1": "value1", "key2": "value2", "key3": "value3"},
            document_id=doc_id,
            chunk_id=chunk_id
        )
        original_updated_at = entry.updated_at

        # 添加小延迟确保时间戳不同
        time.sleep(0.001)

        # 移除存在的元数据
        result = entry.remove_metadata("key2")
        assert result is True
        assert "key2" not in entry.metadata
        assert "key1" in entry.metadata
        assert "key3" in entry.metadata
        assert entry.updated_at >= original_updated_at

        # 移除不存在的元数据
        result = entry.remove_metadata("不存在的key")
        assert result is False
        assert entry.metadata == {"key1": "value1", "key3": "value3"}

    def test_set_source_reference(self) -> None:
        """测试设置来源引用"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        # 初始为文档来源
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id,
            source_path="/path/to/file.pdf"
        )
        original_updated_at = entry.updated_at

        # 添加小延迟确保时间戳不同
        time.sleep(0.001)

        # 更改为网络来源
        entry.set_source_reference(
            web_data_source_id=web_id,
            source_url="https://example.com"
        )

        assert entry.document_id is None
        assert entry.chunk_id is None
        assert entry.web_data_source_id == web_id
        assert entry.source_url == "https://example.com"
        assert entry.source_path is None
        assert entry.updated_at >= original_updated_at

        # 更改回文档来源
        new_doc_id = uuid.uuid4()
        new_chunk_id = uuid.uuid4()
        entry.set_source_reference(
            document_id=new_doc_id,
            chunk_id=new_chunk_id,
            source_path="/new/path/to/file.pdf"
        )

        assert entry.document_id == new_doc_id
        assert entry.chunk_id == new_chunk_id
        assert entry.web_data_source_id is None
        assert entry.source_url is None
        assert entry.source_path == "/new/path/to/file.pdf"

    def test_set_source_reference_validation(self) -> None:
        """测试设置来源引用的验证"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        web_id = uuid.uuid4()

        entry = KnowledgeEntry(title="测试", document_id=doc_id, chunk_id=chunk_id)

        # 同时设置文档和网络来源
        with pytest.raises(ValueError, match="不能同时设置文档来源和网络数据源"):
            entry.set_source_reference(
                document_id=doc_id,
                web_data_source_id=web_id
            )

        # 只设置document_id
        with pytest.raises(ValueError, match="设置document_id时,也必须设置chunk_id"):
            entry.set_source_reference(document_id=doc_id)

        # 只设置chunk_id
        with pytest.raises(ValueError, match="设置chunk_id时,也必须设置document_id"):
            entry.set_source_reference(chunk_id=chunk_id)

    def test_model_copy_preserves_validation(self) -> None:
        """测试model_copy保持验证"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()

        # 创建有效条目
        entry = KnowledgeEntry(
            title="测试",
            document_id=doc_id,
            chunk_id=chunk_id,
            tags=["标签1", "标签2"],
            metadata={"key": "value"}
        )

        # 使用model_copy创建副本
        copied_entry = entry.model_copy(update={"title": "副本"})

        # 验证副本保持所有字段
        assert copied_entry.title == "副本"
        assert copied_entry.document_id == doc_id
        assert copied_entry.chunk_id == chunk_id
        assert copied_entry.tags == ["标签1", "标签2"]
        assert copied_entry.metadata == {"key": "value"}
        assert copied_entry.get_source_type() == EntrySourceType.UPLOADED_DOCUMENT

    def test_json_serialization(self) -> None:
        """测试JSON序列化"""
        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        now = datetime.utcnow()

        entry = KnowledgeEntry(
            title="测试条目",
            summary="测试摘要",
            tags=["标签1", "标签2"],
            document_id=doc_id,
            chunk_id=chunk_id,
            metadata={"key": "value"},
            created_at=now,
            updated_at=now
        )

        # 序列化为JSON
        json_data = entry.model_dump()

        # 验证关键字段
        assert json_data["title"] == "测试条目"
        assert json_data["summary"] == "测试摘要"
        assert json_data["tags"] == ["标签1", "标签2"]
        # UUID在序列化时保持为UUID对象,需要手动转换
        assert json_data["document_id"] == doc_id
        assert json_data["chunk_id"] == chunk_id
        assert json_data["metadata"] == {"key": "value"}

        # 从JSON反序列化
        restored_entry = KnowledgeEntry.model_validate(json_data)

        # 验证反序列化结果
        assert restored_entry.title == entry.title
        assert restored_entry.summary == entry.summary
        assert restored_entry.tags == entry.tags
        assert restored_entry.document_id == entry.document_id
        assert restored_entry.chunk_id == entry.chunk_id
        assert restored_entry.metadata == entry.metadata
