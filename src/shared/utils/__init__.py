# 生成命令: T011 通用工具函数实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
共享工具函数模块

提供通用的工具函数, 包括日志记录、输入验证、辅助功能等。
这些函数可以在项目的各个层中复用, 提高代码的一致性和可维护性。
"""

# 导入日志相关
# 导入辅助函数
from .helpers import (
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
from .logging import (
    LogFormat,
    LoggerManager,
    LogLevel,
    agent_logger,
    api_logger,
    app_logger,
    get_logger,
    log_error,
    log_performance,
    log_structured,
    storage_logger,
)

# 导入验证相关
from .validators import (
    EMAIL_RULE,
    NON_EMPTY_STRING_RULE,
    PHONE_CN_RULE,
    POSITIVE_INTEGER_RULE,
    POSITIVE_NUMBER_RULE,
    URL_RULE,
    ValidationError,
    validate_business_rules,
    validate_date_string,
    validate_email,
    validate_file_path,
    validate_json_string,
    validate_numeric_range,
    validate_password_strength,
    validate_phone_number,
    validate_regex_pattern,
    validate_string_length,
    validate_url,
)

# 版本信息
__version__ = "1.0.0"

# 导出的公共接口
__all__ = [
    "EMAIL_RULE",
    "NON_EMPTY_STRING_RULE",
    "PHONE_CN_RULE",
    "POSITIVE_INTEGER_RULE",
    "POSITIVE_NUMBER_RULE",
    "URL_RULE",
    "LogFormat",
    "LogLevel",
    "LoggerManager",
    "ValidationError",
    "__version__",
    "agent_logger",
    "api_logger",
    "app_logger",
    "batch_process",
    "cache_result",
    "calculate_file_hash",
    "calculate_string_hash",
    "chunk_list",
    "clean_whitespace",
    "deep_merge_dict",
    "ensure_directory",
    "extract_emails",
    "extract_numbers",
    "extract_urls",
    "flatten_dict",
    "format_duration",
    "format_file_size",
    "generate_timestamp_id",
    "generate_unique_id",
    "get_env_var",
    "get_logger",
    "log_error",
    "log_performance",
    "log_structured",
    "normalize_text",
    "retry_on_exception",
    "safe_filename",
    "safe_json_dumps",
    "safe_json_loads",
    "storage_logger",
    "truncate_text",
    "validate_business_rules",
    "validate_date_string",
    "validate_email",
    "validate_file_path",
    "validate_json_string",
    "validate_numeric_range",
    "validate_password_strength",
    "validate_phone_number",
    "validate_regex_pattern",
    "validate_string_length",
    "validate_url",
]
