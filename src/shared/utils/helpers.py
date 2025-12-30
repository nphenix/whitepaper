# 生成命令: T011 通用工具函数实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
通用辅助函数模块

提供各种通用的辅助函数, 包括字符串处理,文件操作,日期时间处理等.
这些函数可以在项目的各个层中复用, 提高代码的一致性和可维护性.
"""

import hashlib
import json
import os
import re
import time
import unicodedata
import uuid
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any


def generate_unique_id(prefix: str = "", suffix: str = "") -> str:
    """生成唯一ID

    Args:
        prefix: ID前缀
        suffix: ID后缀

    Returns:
        唯一ID字符串
    """
    unique_id = str(uuid.uuid4())
    return f"{prefix}{unique_id}{suffix}" if prefix or suffix else unique_id


def generate_timestamp_id() -> str:
    """生成基于时间戳的ID

    Returns:
        时间戳ID字符串
    """
    timestamp = int(time.time() * 1000)  # 毫秒级时间戳
    random_suffix = uuid.uuid4().hex[:8]
    return f"{timestamp}_{random_suffix}"


def calculate_file_hash(file_path: str, algorithm: str = "md5") -> str | None:
    """计算文件哈希值

    Args:
        file_path: 文件路径
        algorithm: 哈希算法, 支持 'md5', 'sha1', 'sha256'

    Returns:
        文件哈希值, 计算失败返回None
    """
    try:
        hash_obj = hashlib.new(algorithm)
        with Path(file_path).open("rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        return hash_obj.hexdigest()
    except Exception:
        return None


def calculate_string_hash(text: str, algorithm: str = "md5") -> str:
    """计算字符串哈希值

    Args:
        text: 字符串内容
        algorithm: 哈希算法, 支持 'md5', 'sha1', 'sha256'

    Returns:
        字符串哈希值
    """
    hash_obj = hashlib.new(algorithm)
    hash_obj.update(text.encode("utf-8"))
    return hash_obj.hexdigest()


def normalize_text(text: str, form: str = "NFKC") -> str:
    """标准化Unicode文本

    Args:
        text: 输入文本
        form: 标准化形式, 支持 'NFC', 'NFD', 'NFKC', 'NFKD'

    Returns:
        标准化后的文本
    """
    if not text:
        return ""

    return unicodedata.normalize(form, text)  # type: ignore[arg-type]


def clean_whitespace(text: str, *, preserve_line_breaks: bool = False) -> str:
    """清理文本中的空白字符

    Args:
        text: 输入文本
        preserve_line_breaks: 是否保留换行符

    Returns:
        清理后的文本
    """
    if not text:
        return ""

    if preserve_line_breaks:
        # 保留换行符, 清理其他空白
        lines = text.split("\n")
        cleaned_lines = [re.sub(r"\s+", " ", line.strip()) for line in lines]
        return "\n".join(cleaned_lines)
    else:
        # 清理所有空白字符
        return re.sub(r"\s+", " ", text.strip())


def truncate_text(
    text: str, max_length: int, suffix: str = "...", *, word_boundary: bool = True
) -> str:
    """截断文本

    Args:
        text: 输入文本
        max_length: 最大长度
        suffix: 截断后缀
        word_boundary: 是否在单词边界截断

    Returns:
        截断后的文本
    """
    if not text or len(text) <= max_length:
        return text

    if word_boundary:
        # 在单词边界截断
        truncated = text[: max_length - len(suffix)]
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space]
        return truncated + suffix
    else:
        # 直接截断
        return text[: max_length - len(suffix)] + suffix


def extract_numbers(text: str) -> list[float]:
    """从文本中提取数字

    Args:
        text: 输入文本

    Returns:
        提取的数字列表
    """
    if not text:
        return []

    # 匹配整数,小数,科学计数法
    pattern = r"-?\d+\.?\d*(?:[eE][+-]?\d+)?"
    matches = re.findall(pattern, text)

    numbers = []
    for match in matches:
        try:
            numbers.append(float(match))
        except ValueError:
            continue

    return numbers


def extract_emails(text: str) -> list[str]:
    """从文本中提取邮箱地址

    Args:
        text: 输入文本

    Returns:
        提取的邮箱地址列表
    """
    if not text:
        return []

    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    return re.findall(pattern, text)


def extract_urls(text: str) -> list[str]:
    """从文本中提取URL

    Args:
        text: 输入文本

    Returns:
        提取的URL列表
    """
    if not text:
        return []

    # 匹配http/https URL
    pattern = r"https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?"
    return re.findall(pattern, text)


def safe_filename(filename: str) -> str:
    """生成安全的文件名

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名
    """
    if not filename:
        return "unnamed"

    # 移除或替换不安全的字符
    safe_chars = re.sub(r'[<>:"/\\|?*]', "_", filename)
    safe_chars = safe_chars.strip(". ")

    # 限制长度
    if len(safe_chars) > 255:
        path = Path(safe_chars)
        name = path.stem
        ext = path.suffix
        safe_chars = name[: 255 - len(ext)] + ext

    return safe_chars or "unnamed"


def format_file_size(size_bytes: int) -> str:
    """格式化文件大小

    Args:
        size_bytes: 文件大小(字节)

    Returns:
        格式化后的文件大小字符串
    """
    if size_bytes == 0:
        return "0 B"

    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)

    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1

    return f"{size:.1f} {size_names[i]}"


def format_duration(seconds: float) -> str:
    """格式化时间长度

    Args:
        seconds: 秒数

    Returns:
        格式化后的时间字符串
    """
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m{secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h{minutes}m"


def deep_merge_dict(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """深度合并两个字典

    Args:
        dict1: 第一个字典
        dict2: 第二个字典

    Returns:
        合并后的字典
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dict(result[key], value)
        else:
            result[key] = value

    return result


def flatten_dict(
    d: dict[str, Any], parent_key: str = "", sep: str = "."
) -> dict[str, Any]:
    """扁平化嵌套字典

    Args:
        d: 嵌套字典
        parent_key: 父键名
        sep: 分隔符

    Returns:
        扁平化后的字典
    """
    items: list[tuple[str, Any]] = []

    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))

    return dict(items)


def retry_on_exception(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟时间(秒)
        backoff: 退避倍数
        exceptions: 需要重试的异常类型
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        break

                    time.sleep(current_delay)
                    current_delay *= backoff

            if last_exception is not None:
                raise last_exception
            else:
                msg = "All attempts failed but no exception was captured"
                raise RuntimeError(msg)

        return wrapper

    return decorator


def cache_result(ttl_seconds: int = 300) -> Callable:
    """简单结果缓存装饰器

    Args:
        ttl_seconds: 缓存生存时间(秒)
    """
    cache: dict[
        tuple[str, tuple[Any, ...], frozenset[tuple[str, Any]]], tuple[Any, float]
    ] = {}

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # 生成缓存键
            cache_key = (func.__name__, args, frozenset(kwargs.items()))

            # 检查缓存
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl_seconds:
                    return result

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache[cache_key] = (result, time.time())

            return result

        return wrapper

    return decorator


def ensure_directory(directory: str | Path) -> Path:
    """确保目录存在

    Args:
        directory: 目录路径

    Returns:
        Path对象
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_json_loads(json_str: str, default: Any = None) -> Any:
    """安全的JSON解析

    Args:
        json_str: JSON字符串
        default: 解析失败时的默认值

    Returns:
        解析结果或默认值
    """
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """安全的JSON序列化

    Args:
        obj: 要序列化的对象
        default: 序列化失败时的默认值

    Returns:
        JSON字符串或默认值
    """
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return default


def chunk_list(lst: list[Any], chunk_size: int) -> list[list[Any]]:
    """将列表分块

    Args:
        lst: 输入列表
        chunk_size: 块大小

    Returns:
        分块后的列表
    """
    if chunk_size <= 0:
        return [lst]

    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def batch_process(
    items: list[Any],
    process_func: Callable[[Any], Any],
    batch_size: int = 100,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[Any]:
    """批量处理列表项

    Args:
        items: 要处理的项目列表
        process_func: 处理函数
        batch_size: 批次大小
        progress_callback: 进度回调函数

    Returns:
        处理结果列表
    """
    results = []
    total_items = len(items)

    for i in range(0, total_items, batch_size):
        batch = items[i : i + batch_size]
        batch_results = [process_func(item) for item in batch]
        results.extend(batch_results)

        if progress_callback:
            progress_callback(min(i + batch_size, total_items), total_items)

    return results


def measure_time(func: Callable) -> Callable:
    """测量函数执行时间的装饰器"""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> tuple[Any, float]:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result, time.time() - start_time
        except Exception as e:
            return e, time.time() - start_time

    return wrapper


def get_env_var(name: str, default: Any = None, var_type: type = str) -> Any:
    """获取环境变量并进行类型转换

    Args:
        name: 环境变量名
        default: 默认值
        var_type: 变量类型

    Returns:
        环境变量值或默认值
    """
    value = os.getenv(name)

    if value is None:
        return default

    try:
        if var_type is bool:
            return value.lower() in ("true", "1", "yes", "on")
        elif var_type is int:
            return int(value)
        elif var_type is float:
            return float(value)
        elif var_type is list:
            return [item.strip() for item in value.split(",")]
        else:
            return var_type(value)
    except (ValueError, TypeError):
        return default
