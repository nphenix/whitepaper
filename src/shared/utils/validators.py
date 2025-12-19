# 生成命令: T011 通用工具函数实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
输入验证函数模块

提供各种输入验证函数, 包括数据格式验证、业务规则验证等。
支持字符串、数字、邮箱、URL、文件路径等多种数据类型的验证。
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ValidationError(Exception):
    """验证错误异常"""


def validate_email(email: str) -> bool:
    """验证邮箱格式

    Args:
        email: 邮箱地址

    Returns:
        是否为有效邮箱格式
    """
    if not email or not isinstance(email, str):
        return False

    # 更严格的邮箱验证, 不允许连续的点
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    email = email.strip()

    # 检查是否有连续的点
    if ".." in email:
        return False

    return bool(re.match(pattern, email))


def validate_url(url: str, schemes: list[str] | None = None) -> bool:
    """验证URL格式

    Args:
        url: URL地址
        schemes: 允许的协议列表, 默认为 ['http', 'https']

    Returns:
        是否为有效URL格式
    """
    if not url or not isinstance(url, str):
        return False

    if schemes is None:
        schemes = ["http", "https"]

    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in schemes and bool(parsed.netloc)
    except Exception:
        return False


def validate_phone_number(phone: str, country_code: str = "CN") -> bool:
    """验证电话号码格式

    Args:
        phone: 电话号码
        country_code: 国家代码, 默认为CN(中国)

    Returns:
        是否为有效电话号码格式
    """
    if not phone or not isinstance(phone, str):
        return False

    phone = phone.strip().replace(" ", "").replace("-", "")

    if country_code == "CN":
        # 中国手机号码: 1开头, 第二位3-9, 共11位
        pattern = r"^1[3-9]\d{9}$"
        return bool(re.match(pattern, phone))

    # 可以扩展其他国家的电话号码验证规则
    return False


def validate_password_strength(password: str) -> dict[str, Any]:
    """验证密码强度

    Args:
        password: 密码字符串

    Returns:
        包含验证结果和详细信息的字典
    """
    if not password or not isinstance(password, str):
        return {"valid": False, "score": 0, "issues": ["密码不能为空"]}

    issues = []
    score = 0

    # 长度检查
    if len(password) >= 8:
        score += 1
    else:
        issues.append("密码长度至少8位")

    # 包含大写字母
    if re.search(r"[A-Z]", password):
        score += 1
    else:
        issues.append("密码应包含大写字母")

    # 包含小写字母
    if re.search(r"[a-z]", password):
        score += 1
    else:
        issues.append("密码应包含小写字母")

    # 包含数字
    if re.search(r"\d", password):
        score += 1
    else:
        issues.append("密码应包含数字")

    # 包含特殊字符
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    else:
        issues.append("密码应包含特殊字符")

    return {
        "valid": score >= 4 and len(issues) == 0,
        "score": score,
        "max_score": 5,
        "issues": issues,
    }


def validate_file_path(
    file_path: str,
    *,
    must_exist: bool = False,
    allowed_extensions: list[str] | None = None,
) -> dict[str, Any]:
    """验证文件路径

    Args:
        file_path: 文件路径
        must_exist: 文件是否必须存在
        allowed_extensions: 允许的文件扩展名列表

    Returns:
        包含验证结果的字典
    """
    if not file_path or not isinstance(file_path, str):
        return {"valid": False, "error": "文件路径不能为空"}

    try:
        path = Path(file_path)

        # 检查路径格式是否合法
        if not path or not str(path).strip():
            return {"valid": False, "error": "文件路径格式无效"}

        # 检查文件是否存在
        if must_exist and not path.exists():
            return {"valid": False, "error": f"文件不存在: {file_path}"}

        # 检查文件扩展名
        if allowed_extensions and path.exists():
            ext = path.suffix.lower()
            if ext not in [e.lower() for e in allowed_extensions]:
                return {
                    "valid": False,
                    "error": f"不支持的文件扩展名: {ext}, 支持的扩展名: {allowed_extensions}",
                }

        return {
            "valid": True,
            "path": str(path.absolute()),
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else None,
            "is_directory": path.is_dir() if path.exists() else None,
            "extension": path.suffix.lower() if path.exists() else None,
        }

    except Exception as e:
        return {"valid": False, "error": f"路径验证失败: {e!s}"}


def validate_json_string(json_str: str) -> dict[str, Any]:
    """验证JSON字符串格式

    Args:
        json_str: JSON字符串

    Returns:
        包含验证结果的字典
    """
    if not json_str or not isinstance(json_str, str):
        return {"valid": False, "error": "JSON字符串不能为空"}

    try:
        parsed = json.loads(json_str)
        return {"valid": True, "parsed": parsed, "type": type(parsed).__name__}
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "error": f"JSON格式错误: {e!s}",
            "line": e.lineno,
            "column": e.colno,
        }


def validate_date_string(
    date_str: str, date_format: str = "%Y-%m-%d"
) -> dict[str, Any]:
    """验证日期字符串格式

    Args:
        date_str: 日期字符串
        date_format: 日期格式, 默认为 '%Y-%m-%d'

    Returns:
        包含验证结果的字典
    """
    if not date_str or not isinstance(date_str, str):
        return {"valid": False, "error": "日期字符串不能为空"}

    try:
        parsed_date = datetime.strptime(date_str.strip(), date_format)
        return {
            "valid": True,
            "parsed_date": parsed_date,
            "formatted": parsed_date.strftime(date_format),
        }
    except ValueError as e:
        return {
            "valid": False,
            "error": f"日期格式错误: {e!s}",
            "expected_format": date_format,
        }


def validate_numeric_range(
    value: int | float | str,
    min_val: float | None = None,
    max_val: float | None = None,
) -> dict[str, Any]:
    """验证数值范围

    Args:
        value: 要验证的数值
        min_val: 最小值
        max_val: 最大值

    Returns:
        包含验证结果的字典
    """
    try:
        # 尝试转换为数值
        num_value = float(value.strip()) if isinstance(value, str) else float(value)

        issues = []

        if min_val is not None and num_value < min_val:
            issues.append(f"值不能小于 {min_val}")

        if max_val is not None and num_value > max_val:
            issues.append(f"值不能大于 {max_val}")

        return {
            "valid": len(issues) == 0,
            "value": num_value,
            "issues": issues,
            "in_range": len(issues) == 0,
        }

    except (ValueError, TypeError):
        return {"valid": False, "error": f"无法转换为数值: {value}"}


def validate_string_length(
    value: Any,
    min_length: int | None = None,
    max_length: int | None = None,
    *,
    allow_empty: bool = True,
) -> dict[str, Any]:
    """验证字符串长度

    Args:
        value: 要验证的字符串
        min_length: 最小长度
        max_length: 最大长度
        allow_empty: 是否允许空字符串

    Returns:
        包含验证结果的字典
    """
    if not isinstance(value, str):
        return {"valid": False, "error": "值必须是字符串"}

    length = len(value)
    issues = []

    if not allow_empty and length == 0:
        issues.append("字符串不能为空")

    if min_length is not None and length < min_length:
        issues.append(f"字符串长度不能少于 {min_length} 个字符")

    if max_length is not None and length > max_length:
        issues.append(f"字符串长度不能超过 {max_length} 个字符")

    return {
        "valid": len(issues) == 0,
        "length": length,
        "issues": issues,
        "is_empty": length == 0,
    }


def validate_regex_pattern(value: Any, pattern: str, flags: int = 0) -> dict[str, Any]:
    """使用正则表达式验证字符串

    Args:
        value: 要验证的字符串
        pattern: 正则表达式模式
        flags: 正则表达式标志

    Returns:
        包含验证结果的字典
    """
    if not isinstance(value, str):
        return {"valid": False, "error": "值必须是字符串"}

    try:
        compiled_pattern = re.compile(pattern, flags)
        match = compiled_pattern.match(value)

        return {
            "valid": match is not None,
            "pattern": pattern,
            "match": match.group(0) if match else None,
            "groups": match.groups() if match else None,
        }

    except re.error as e:
        return {"valid": False, "error": f"正则表达式错误: {e!s}"}


def validate_business_rules(data: Any, rules: Any) -> dict[str, Any]:
    """验证业务规则

    Args:
        data: 要验证的数据字典
        rules: 业务规则字典, 键为字段名, 值为验证函数

    Returns:
        包含验证结果的字典
    """
    if not isinstance(data, dict):
        return {"valid": False, "error": "数据必须是字典格式"}

    if not isinstance(rules, dict):
        return {"valid": False, "error": "规则必须是字典格式"}

    results = {}
    all_valid = True

    for field, rule_func in rules.items():
        field_value = data.get(field)

        try:
            is_valid = rule_func(field_value)
            results[field] = {"valid": is_valid, "value": field_value}

            if not is_valid:
                all_valid = False

        except Exception as e:
            results[field] = {"valid": False, "value": field_value, "error": str(e)}
            all_valid = False

    return {
        "valid": all_valid,
        "field_results": results,
        "total_fields": len(rules),
        "valid_fields": sum(1 for r in results.values() if r["valid"]),
    }


# 常用验证规则预设


def email_rule(x: Any) -> bool:
    """邮箱验证规则"""
    return validate_email(x)


def url_rule(x: Any) -> bool:
    """URL验证规则"""
    return validate_url(x)


def phone_cn_rule(x: Any) -> bool:
    """中国手机号验证规则"""
    return validate_phone_number(x, "CN")


def non_empty_string_rule(x: Any) -> bool:
    """非空字符串验证规则"""
    return isinstance(x, str) and len(x.strip()) > 0


def positive_number_rule(x: Any) -> bool:
    """正数验证规则"""
    return isinstance(x, (int, float)) and x > 0


def positive_integer_rule(x: Any) -> bool:
    """正整数验证规则"""
    return isinstance(x, int) and x > 0


# 向后兼容的别名
EMAIL_RULE = email_rule
URL_RULE = url_rule
PHONE_CN_RULE = phone_cn_rule
NON_EMPTY_STRING_RULE = non_empty_string_rule
POSITIVE_NUMBER_RULE = positive_number_rule
POSITIVE_INTEGER_RULE = positive_integer_rule
