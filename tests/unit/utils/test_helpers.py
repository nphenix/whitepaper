# 生成命令: T011 通用工具函数实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
辅助函数模块单元测试
"""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from src.shared.utils.helpers import (
    batch_process,
    cache_result,
    calculate_file_hash,
    calculate_string_hash,
    chunk_list,
    clean_whitespace,
    deep_merge_dict,
    ensure_directory,
    extract_emails,
    extract_numbers,
    extract_urls,
    flatten_dict,
    format_duration,
    format_file_size,
    generate_timestamp_id,
    generate_unique_id,
    get_env_var,
    measure_time,
    normalize_text,
    retry_on_exception,
    safe_filename,
    safe_json_dumps,
    safe_json_loads,
    truncate_text,
)


class TestGenerateUniqueId:
    """测试唯一ID生成"""

    def test_generate_unique_id_default(self):
        """测试默认唯一ID生成"""
        id1 = generate_unique_id()
        id2 = generate_unique_id()

        assert id1 != id2
        assert isinstance(id1, str)
        assert len(id1) == 36  # UUID length

    def test_generate_unique_id_with_prefix_suffix(self):
        """测试带前缀和后缀的唯一ID生成"""
        id_with_prefix = generate_unique_id(prefix="test_")
        id_with_suffix = generate_unique_id(suffix="_end")
        id_with_both = generate_unique_id(prefix="start_", suffix="_end")

        assert id_with_prefix.startswith("test_")
        assert id_with_suffix.endswith("_end")
        assert id_with_both.startswith("start_")
        assert id_with_both.endswith("_end")

    def test_generate_timestamp_id(self):
        """测试时间戳ID生成"""
        id1 = generate_timestamp_id()
        time.sleep(0.001)  # 确保时间差
        id2 = generate_timestamp_id()

        assert id1 != id2
        assert isinstance(id1, str)
        assert "_" in id1

        # 检查格式:timestamp_randomsuffix
        parts1 = id1.split("_")
        parts2 = id2.split("_")
        assert len(parts1) == 2
        assert len(parts2) == 2
        assert parts1[0].isdigit()
        assert parts2[0].isdigit()


class TestCalculateHash:
    """测试哈希计算"""

    def test_calculate_string_hash(self):
        """测试字符串哈希计算"""
        text = "Hello, World!"
        hash_md5 = calculate_string_hash(text, "md5")
        hash_sha1 = calculate_string_hash(text, "sha1")

        assert isinstance(hash_md5, str)
        assert isinstance(hash_sha1, str)
        assert hash_md5 != hash_sha1
        assert len(hash_md5) == 32  # MD5 length
        assert len(hash_sha1) == 40  # SHA1 length

    def test_calculate_file_hash(self):
        """测试文件哈希计算"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("Test content for hashing")
            temp_path = temp_file.name

        try:
            hash_md5 = calculate_file_hash(temp_path, "md5")
            hash_sha256 = calculate_file_hash(temp_path, "sha256")

            assert isinstance(hash_md5, str)
            assert isinstance(hash_sha256, str)
            assert hash_md5 != hash_sha256
            assert len(hash_md5) == 32
            assert len(hash_sha256) == 64
        finally:
            Path(temp_path).unlink()

    def test_calculate_file_hash_nonexistent(self):
        """测试不存在文件的哈希计算"""
        result = calculate_file_hash("/nonexistent/file.txt")
        assert result is None


class TestTextProcessing:
    """测试文本处理"""

    def test_normalize_text(self):
        """测试文本标准化"""
        # 测试不同形式的Unicode字符
        text = "café"  # 使用组合字符
        normalized = normalize_text(text, "NFKC")
        assert isinstance(normalized, str)

        # 测试空字符串
        assert normalize_text("") == ""
        assert normalize_text(None) == ""

    def test_clean_whitespace(self):
        """测试空白字符清理"""
        text = "  Hello   \n  World  \t  "

        # 不保留换行符
        result = clean_whitespace(text, preserve_line_breaks=False)
        assert result == "Hello World"

        # 保留换行符
        result = clean_whitespace(text, preserve_line_breaks=True)
        assert result == "Hello\nWorld"

    def test_truncate_text(self):
        """测试文本截断"""
        text = "This is a long text that needs to be truncated"

        # 基本截断
        result = truncate_text(text, 20)
        assert len(result) <= 20
        assert result.endswith("...")

        # 单词边界截断
        result = truncate_text(text, 20, word_boundary=True)
        assert result == "This is a long..."

        # 不需要截断
        result = truncate_text("Short text", 20)
        assert result == "Short text"

    def test_extract_numbers(self):
        """测试数字提取"""
        text = "The price is $19.99, discount 10%, and 1.5e3 items"
        numbers = extract_numbers(text)

        assert 19.99 in numbers
        assert 10.0 in numbers
        assert 1500.0 in numbers  # 1.5e3

    def test_extract_emails(self):
        """测试邮箱提取"""
        text = "Contact us at support@example.com or admin@test.org"
        emails = extract_emails(text)

        assert "support@example.com" in emails
        assert "admin@test.org" in emails

    def test_extract_urls(self):
        """测试URL提取"""
        text = "Visit https://example.com or http://test.org/path"
        urls = extract_urls(text)

        assert "https://example.com" in urls
        assert "http://test.org/path" in urls


class TestFileUtilities:
    """测试文件工具"""

    def test_safe_filename(self):
        """测试安全文件名"""
        # 测试不安全字符
        unsafe = "file<>:/\\|?*name.txt"
        safe = safe_filename(unsafe)
        assert "<" not in safe
        assert ">" not in safe
        assert ":" not in safe
        assert '"' not in safe
        assert "/" not in safe
        assert "\\" not in safe
        assert "|" not in safe
        assert "?" not in safe
        assert "*" not in safe

        # 测试空文件名
        assert safe_filename("") == "unnamed"

        # 测试过长文件名
        long_name = "a" * 300
        safe = safe_filename(long_name)
        assert len(safe) <= 255

    def test_format_file_size(self):
        """测试文件大小格式化"""
        assert format_file_size(0) == "0 B"
        assert format_file_size(1024) == "1.0 KB"
        assert format_file_size(1024 * 1024) == "1.0 MB"
        assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"
        assert format_file_size(1536) == "1.5 KB"

    def test_format_duration(self):
        """测试时间长度格式化"""
        assert format_duration(0.5) == "500ms"
        assert format_duration(30) == "30.0s"
        assert format_duration(90) == "1m30s"
        assert format_duration(3661) == "1h1m"


class TestDictUtilities:
    """测试字典工具"""

    def test_deep_merge_dict(self):
        """测试深度合并字典"""
        dict1 = {"a": 1, "b": {"x": 1, "y": 2}, "c": 3}
        dict2 = {"b": {"y": 3, "z": 4}, "d": 4}

        result = deep_merge_dict(dict1, dict2)

        assert result["a"] == 1
        assert result["c"] == 3
        assert result["d"] == 4
        assert result["b"]["x"] == 1  # 来自dict1
        assert result["b"]["y"] == 3  # 来自dict2
        assert result["b"]["z"] == 4  # 来自dict2

    def test_flatten_dict(self):
        """测试字典扁平化"""
        nested = {"a": 1, "b": {"x": 2, "y": {"z": 3}}, "c": 4}

        result = flatten_dict(nested)

        assert result["a"] == 1
        assert result["b.x"] == 2
        assert result["b.y.z"] == 3
        assert result["c"] == 4


class TestDecorators:
    """测试装饰器"""

    def test_retry_on_exception(self):
        """测试重试装饰器"""
        call_count = 0

        @retry_on_exception(max_attempts=3, delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                msg = "Test error"
                raise ValueError(msg)
            return "success"

        result = failing_function()
        assert result == "success"
        assert call_count == 3

    def test_retry_on_exception_exhausted(self):
        """测试重试装饰器失败"""

        @retry_on_exception(max_attempts=2, delay=0.01)
        def always_failing_function():
            msg = "Always fails"
            raise ValueError(msg)

        with pytest.raises(ValueError, match="Always fails"):
            always_failing_function()

    def test_cache_result(self):
        """测试结果缓存装饰器"""
        call_count = 0

        @cache_result(ttl_seconds=0.1)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # 第一次调用
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # 第二次调用(应该从缓存获取)
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # 没有增加

        # 等待缓存过期
        time.sleep(0.2)
        result3 = expensive_function(5)
        assert result3 == 10
        assert call_count == 2  # 重新计算

    def test_measure_time(self):
        """测试时间测量装饰器"""

        @measure_time
        def test_function():
            time.sleep(0.1)
            return "result"

        result, duration = test_function()
        assert result == "result"
        assert 0.1 <= duration < 0.2


class TestUtilities:
    """测试其他工具函数"""

    def test_ensure_directory(self):
        """测试确保目录存在"""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new" / "subdir"
            path = ensure_directory(new_dir)

            assert isinstance(path, Path)
            assert path.exists()
            assert path.is_dir()

    def test_safe_json_loads(self):
        """测试安全JSON解析"""
        # 有效JSON
        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}

        # 无效JSON
        result = safe_json_loads("invalid json", {"default": "value"})
        assert result == {"default": "value"}

        # None输入
        result = safe_json_loads(None)
        assert result is None

    def test_safe_json_dumps(self):
        """测试安全JSON序列化"""
        # 可序列化对象
        result = safe_json_dumps({"key": "value"})
        assert json.loads(result) == {"key": "value"}

        # 不可序列化对象
        class Unserializable:
            pass

        result = safe_json_dumps(Unserializable(), '{"default": "value"}')
        # 结果应该是对象的字符串表示,而不是默认值
        assert "Unserializable object" in result

    def test_chunk_list(self):
        """测试列表分块"""
        lst = [1, 2, 3, 4, 5, 6, 7]

        # 正常分块
        chunks = chunk_list(lst, 3)
        assert chunks == [[1, 2, 3], [4, 5, 6], [7]]

        # 块大小为0
        chunks = chunk_list(lst, 0)
        assert chunks == [lst]

        # 块大小大于列表长度
        chunks = chunk_list(lst, 10)
        assert chunks == [lst]

    def test_batch_process(self):
        """测试批量处理"""
        items = [1, 2, 3, 4, 5]

        def process_item(x):
            return x * 2

        progress_calls = []

        def progress_callback(current, total):
            progress_calls.append((current, total))

        results = batch_process(
            items, process_item, batch_size=2, progress_callback=progress_callback
        )

        assert results == [2, 4, 6, 8, 10]
        assert len(progress_calls) == 3  # 5 items / batch_size 2 = 3 batches
        assert progress_calls[-1] == (5, 5)  # 最后一次应该是完成状态

    def test_get_env_var(self):
        """测试环境变量获取"""
        # 设置测试环境变量
        os.environ["TEST_STRING"] = "test_value"
        os.environ["TEST_INT"] = "42"
        os.environ["TEST_FLOAT"] = "3.14"
        os.environ["TEST_BOOL"] = "true"
        os.environ["TEST_LIST"] = "a,b,c"

        try:
            # 字符串
            assert get_env_var("TEST_STRING") == "test_value"
            assert get_env_var("NON_EXISTENT", "default") == "default"

            # 整数
            assert get_env_var("TEST_INT", var_type=int) == 42

            # 浮点数
            assert get_env_var("TEST_FLOAT", var_type=float) == 3.14

            # 布尔值
            assert get_env_var("TEST_BOOL", var_type=bool) is True
            # 设置TEST_FALSE环境变量
            os.environ["TEST_FALSE"] = "false"
            assert get_env_var("TEST_FALSE", var_type=bool) is False

            # 列表
            assert get_env_var("TEST_LIST", var_type=list) == ["a", "b", "c"]

        finally:
            # 清理环境变量
            for key in [
                "TEST_STRING",
                "TEST_INT",
                "TEST_FLOAT",
                "TEST_BOOL",
                "TEST_FALSE",
                "TEST_LIST",
            ]:
                if key in os.environ:
                    del os.environ[key]


if __name__ == "__main__":
    pytest.main([__file__])
