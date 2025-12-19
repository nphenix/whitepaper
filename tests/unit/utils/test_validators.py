# 生成命令: T011 通用工具函数实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
验证器模块单元测试
"""

import os
import tempfile

import pytest

from src.shared.utils.validators import (
    EMAIL_RULE,
    NON_EMPTY_STRING_RULE,
    PHONE_CN_RULE,
    POSITIVE_INTEGER_RULE,
    POSITIVE_NUMBER_RULE,
    URL_RULE,
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


class TestValidateEmail:
    """测试邮箱验证"""

    def test_valid_emails(self):
        """测试有效邮箱"""
        valid_emails = [
            "test@example.com",
            "user.name@domain.co.uk",
            "user+tag@example.org",
            "user123@test-domain.com",
            "test.email.with+symbol@example.com",
        ]

        for email in valid_emails:
            assert validate_email(email) is True

    def test_invalid_emails(self):
        """测试无效邮箱"""
        invalid_emails = [
            "",
            None,
            "invalid-email",
            "@example.com",
            "test@",
            "test@example",
            "test@.com",
            "test space@example.com",
        ]

        for email in invalid_emails:
            assert validate_email(email) is False

        # 单独测试连续点的邮箱
        assert validate_email("test..test@example.com") is False


class TestValidateUrl:
    """测试URL验证"""

    def test_valid_urls(self):
        """测试有效URL"""
        valid_urls = [
            "https://www.example.com",
            "http://example.com",
            "https://subdomain.example.com/path",
            "https://example.com:8080/path?query=value",
            "http://localhost:3000",
        ]

        for url in valid_urls:
            assert validate_url(url) is True

    def test_invalid_urls(self):
        """测试无效URL"""
        invalid_urls = [
            "",
            None,
            "not-a-url",
            "ftp://example.com",  # 默认只允许http/https
            "example.com",
            "://missing-protocol.com",
        ]

        for url in invalid_urls:
            assert validate_url(url) is False

    def test_custom_schemes(self):
        """测试自定义协议"""
        url = "ftp://example.com"
        assert validate_url(url) is False
        assert validate_url(url, schemes=["http", "https", "ftp"]) is True


class TestValidatePhoneNumber:
    """测试电话号码验证"""

    def test_valid_chinese_phones(self):
        """测试有效中国手机号"""
        valid_phones = [
            "13812345678",
            "15987654321",
            "18612345678",
            "13012345678",  # 130开头是有效的
        ]

        for phone in valid_phones:
            assert validate_phone_number(phone, "CN") is True

    def test_invalid_chinese_phones(self):
        """测试无效中国手机号"""
        invalid_phones = [
            "",
            None,
            "12812345678",  # 12开头无效
            "1381234567",  # 位数不够
            "138123456789",  # 位数过多
            "12345678901",  # 不符合手机号规则
            "abc12345678",  # 包含字母
        ]

        for phone in invalid_phones:
            assert validate_phone_number(phone, "CN") is False


class TestValidatePasswordStrength:
    """测试密码强度验证"""

    def test_strong_password(self):
        """测试强密码"""
        password = "StrongP@ssw0rd!"
        result = validate_password_strength(password)

        assert result["valid"] is True
        assert result["score"] == 5
        assert len(result["issues"]) == 0

    def test_weak_password(self):
        """测试弱密码"""
        password = "weak"
        result = validate_password_strength(password)

        assert result["valid"] is False
        assert result["score"] < 4
        assert len(result["issues"]) > 0

    def test_password_issues(self):
        """测试密码问题详情"""
        password = "password123"  # 缺少大写字母和特殊字符
        result = validate_password_strength(password)

        assert result["valid"] is False
        assert result["score"] == 3  # 长度、小写字母、数字
        assert "密码应包含大写字母" in result["issues"]
        assert "密码应包含特殊字符" in result["issues"]


class TestValidateFilePath:
    """测试文件路径验证"""

    def test_existing_file(self):
        """测试存在的文件"""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            result = validate_file_path(temp_path, must_exist=True)
            assert result["valid"] is True
            assert result["exists"] is True
            assert result["is_file"] is True
            assert result["is_directory"] is False
        finally:
            os.unlink(temp_path)

    def test_non_existing_file(self):
        """测试不存在的文件"""
        non_existent = "/path/to/non/existent/file.txt"
        result = validate_file_path(non_existent, must_exist=True)

        assert result["valid"] is False
        assert "文件不存在" in result["error"]

    def test_file_with_extension_filter(self):
        """测试文件扩展名过滤"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # 允许的扩展名
            result = validate_file_path(
                temp_path, must_exist=True, allowed_extensions=[".txt", ".md"]
            )
            assert result["valid"] is True

            # 不允许的扩展名
            result = validate_file_path(
                temp_path, must_exist=True, allowed_extensions=[".pdf", ".doc"]
            )
            assert result["valid"] is False
            assert "不支持的文件扩展名" in result["error"]
        finally:
            os.unlink(temp_path)

    def test_invalid_path(self):
        """测试无效路径"""
        result = validate_file_path("")
        assert result["valid"] is False
        assert "文件路径不能为空" in result["error"]


class TestValidateJsonString:
    """测试JSON字符串验证"""

    def test_valid_json(self):
        """测试有效JSON"""
        valid_jsons = ['{"key": "value"}', '["item1", "item2"]', "123", "true", "null"]

        for json_str in valid_jsons:
            result = validate_json_string(json_str)
            assert result["valid"] is True
            assert "parsed" in result

    def test_invalid_json(self):
        """测试无效JSON"""
        invalid_jsons = [
            "",
            '{"key": value}',  # 缺少引号
            '{"key": "value"',  # 缺少闭合括号
            "not a json",
        ]

        for json_str in invalid_jsons:
            result = validate_json_string(json_str)
            assert result["valid"] is False
            assert "error" in result


class TestValidateDateString:
    """测试日期字符串验证"""

    def test_valid_dates(self):
        """测试有效日期"""
        valid_dates = ["2025-12-08", "2023-01-01", "1999-12-31"]

        for date_str in valid_dates:
            result = validate_date_string(date_str)
            assert result["valid"] is True
            assert "parsed_date" in result

    def test_invalid_dates(self):
        """测试无效日期"""
        invalid_dates = [
            "",
            "2025-13-01",  # 无效月份
            "2025-02-30",  # 无效日期
            "2025/12/08",  # 错误格式
            "25-12-2025",  # 错误格式
        ]

        for date_str in invalid_dates:
            result = validate_date_string(date_str)
            assert result["valid"] is False
            assert "error" in result

    def test_custom_format(self):
        """测试自定义日期格式"""
        date_str = "08/12/2025"
        result = validate_date_string(date_str, date_format="%d/%m/%Y")
        assert result["valid"] is True


class TestValidateNumericRange:
    """测试数值范围验证"""

    def test_valid_range(self):
        """测试有效范围"""
        result = validate_numeric_range(50, min_val=0, max_val=100)
        assert result["valid"] is True
        assert result["value"] == 50.0
        assert result["in_range"] is True

    def test_out_of_range(self):
        """测试超出范围"""
        result = validate_numeric_range(150, min_val=0, max_val=100)
        assert result["valid"] is False
        assert len(result["issues"]) > 0
        assert "值不能大于" in result["issues"][0]

    def test_string_conversion(self):
        """测试字符串转换"""
        result = validate_numeric_range("75.5", min_val=0, max_val=100)
        assert result["valid"] is True
        assert result["value"] == 75.5

    def test_invalid_conversion(self):
        """测试无效转换"""
        result = validate_numeric_range("not a number")
        assert result["valid"] is False
        assert "无法转换为数值" in result["error"]


class TestValidateStringLength:
    """测试字符串长度验证"""

    def test_valid_length(self):
        """测试有效长度"""
        result = validate_string_length("hello", min_length=3, max_length=10)
        assert result["valid"] is True
        assert result["length"] == 5
        assert result["is_empty"] is False

    def test_too_short(self):
        """测试过短"""
        result = validate_string_length("hi", min_length=3)
        assert result["valid"] is False
        assert "字符串长度不能少于" in result["issues"][0]

    def test_too_long(self):
        """测试过长"""
        result = validate_string_length("this is too long", max_length=10)
        assert result["valid"] is False
        assert "字符串长度不能超过" in result["issues"][0]

    def test_empty_string(self):
        """测试空字符串"""
        result = validate_string_length("", allow_empty=False)
        assert result["valid"] is False
        assert "字符串不能为空" in result["issues"][0]
        assert result["is_empty"] is True


class TestValidateRegexPattern:
    """测试正则表达式验证"""

    def test_valid_pattern(self):
        """测试有效模式匹配"""
        pattern = r"^\d{3}-\d{2}-\d{4}$"  # SSN格式
        result = validate_regex_pattern("123-45-6789", pattern)
        assert result["valid"] is True
        assert result["match"] == "123-45-6789"

    def test_invalid_pattern(self):
        """测试无效模式匹配"""
        pattern = r"^\d{3}-\d{2}-\d{4}$"
        result = validate_regex_pattern("invalid", pattern)
        assert result["valid"] is False
        assert result["match"] is None

    def test_invalid_regex(self):
        """测试无效正则表达式"""
        pattern = r"[invalid"  # 缺少闭合括号
        result = validate_regex_pattern("test", pattern)
        assert result["valid"] is False
        assert "正则表达式错误" in result["error"]


class TestValidateBusinessRules:
    """测试业务规则验证"""

    def test_valid_business_rules(self):
        """测试有效业务规则"""
        data = {"email": "test@example.com", "age": 25, "name": "John Doe"}

        rules = {
            "email": EMAIL_RULE,
            "age": lambda x: isinstance(x, int) and x >= 18,
            "name": NON_EMPTY_STRING_RULE,
        }

        result = validate_business_rules(data, rules)
        assert result["valid"] is True
        assert result["total_fields"] == 3
        assert result["valid_fields"] == 3

    def test_invalid_business_rules(self):
        """测试无效业务规则"""
        data = {"email": "invalid-email", "age": 15, "name": ""}

        rules = {
            "email": EMAIL_RULE,
            "age": lambda x: isinstance(x, int) and x >= 18,
            "name": NON_EMPTY_STRING_RULE,
        }

        result = validate_business_rules(data, rules)
        assert result["valid"] is False
        assert result["valid_fields"] == 0

        # 检查字段结果
        field_results = result["field_results"]
        assert field_results["email"]["valid"] is False
        assert field_results["age"]["valid"] is False
        assert field_results["name"]["valid"] is False

    def test_exception_in_rule(self):
        """测试规则中的异常"""
        data = {"field": "value"}

        def failing_rule(x):
            msg = "Rule error"
            raise ValueError(msg)

        rules = {"field": failing_rule}

        result = validate_business_rules(data, rules)
        assert result["valid"] is False
        assert "error" in result["field_results"]["field"]


class TestPresetRules:
    """测试预设规则"""

    def test_email_rule(self):
        """测试邮箱规则"""
        assert EMAIL_RULE("test@example.com") is True
        assert EMAIL_RULE("invalid") is False

    def test_url_rule(self):
        """测试URL规则"""
        assert URL_RULE("https://example.com") is True
        assert URL_RULE("not-url") is False

    def test_phone_cn_rule(self):
        """测试中国手机号规则"""
        assert PHONE_CN_RULE("13812345678") is True
        assert PHONE_CN_RULE("12345678901") is False

    def test_non_empty_string_rule(self):
        """测试非空字符串规则"""
        assert NON_EMPTY_STRING_RULE("hello") is True
        assert NON_EMPTY_STRING_RULE("") is False
        assert NON_EMPTY_STRING_RULE("   ") is False
        assert NON_EMPTY_STRING_RULE(None) is False

    def test_positive_number_rule(self):
        """测试正数规则"""
        assert POSITIVE_NUMBER_RULE(5) is True
        assert POSITIVE_NUMBER_RULE(5.5) is True
        assert POSITIVE_NUMBER_RULE(0) is False
        assert POSITIVE_NUMBER_RULE(-1) is False

    def test_positive_integer_rule(self):
        """测试正整数规则"""
        assert POSITIVE_INTEGER_RULE(5) is True
        assert POSITIVE_INTEGER_RULE(5.5) is False
        assert POSITIVE_INTEGER_RULE(0) is False
        assert POSITIVE_INTEGER_RULE(-1) is False


if __name__ == "__main__":
    pytest.main([__file__])
