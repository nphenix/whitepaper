# 生成命令: T010 自定义异常类实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
基础异常类单元测试
"""

from src.shared.exceptions.base_exceptions import (
    BaseApplicationError,
    BusinessLogicError,
    ConfigurationError,
    CustomPermissionError,
    CustomTimeoutError,
    RateLimitError,
    ResourceNotFoundError,
    ValidationError,
)


class TestBaseApplicationError:
    """测试基础应用异常类"""

    def test_basic_initialization(self):
        """测试基本初始化"""
        error = BaseApplicationError("Test message")
        assert error.message == "Test message"
        assert str(error) == "Test message"
        assert error.error_code is None
        assert error.details == {}
        assert error.original_error is None

    def test_full_initialization(self):
        """测试完整初始化"""
        original_error = ValueError("Original error")
        error = BaseApplicationError(
            message="Test message",
            error_code="TEST_001",
            details={"key": "value"},
            original_error=original_error,
        )

        assert error.message == "Test message"
        assert error.error_code == "TEST_001"
        assert error.details == {"key": "value"}
        assert error.original_error == original_error
        assert str(error) == "[TEST_001] Test message"

    def test_to_dict(self):
        """测试转换为字典"""
        original_error = ValueError("Original error")
        error = BaseApplicationError(
            message="Test message",
            error_code="TEST_001",
            details={"key": "value"},
            original_error=original_error,
        )

        result = error.to_dict()
        expected = {
            "error_type": "BaseApplicationError",
            "message": "Test message",
            "error_code": "TEST_001",
            "details": {"key": "value"},
            "original_error": {"type": "ValueError", "message": "Original error"},
        }

        assert result == expected


class TestConfigurationError:
    """测试配置错误异常"""

    def test_basic_configuration_error(self):
        """测试基本配置错误"""
        error = ConfigurationError("Invalid configuration")
        assert error.message == "Invalid configuration"
        assert isinstance(error, BaseApplicationError)

    def test_configuration_error_with_config_key(self):
        """测试带配置键的配置错误"""
        error = ConfigurationError("Invalid configuration", config_key="database_url")

        assert error.message == "Invalid configuration"
        assert error.details["config_key"] == "database_url"


class TestValidationError:
    """测试验证错误异常"""

    def test_basic_validation_error(self):
        """测试基本验证错误"""
        error = ValidationError("Validation failed")
        assert error.message == "Validation failed"
        assert isinstance(error, BaseApplicationError)

    def test_validation_error_with_field_info(self):
        """测试带字段信息的验证错误"""
        error = ValidationError(
            "Invalid email format", field_name="email", field_value="invalid-email"
        )

        assert error.message == "Invalid email format"
        assert error.details["field_name"] == "email"
        assert error.details["field_value"] == "invalid-email"


class TestBusinessLogicError:
    """测试业务逻辑错误异常"""

    def test_basic_business_logic_error(self):
        """测试基本业务逻辑错误"""
        error = BusinessLogicError("Business rule violated")
        assert error.message == "Business rule violated"
        assert isinstance(error, BaseApplicationError)

    def test_business_logic_error_with_rule(self):
        """测试带规则的业务逻辑错误"""
        error = BusinessLogicError(
            "Business rule violated", business_rule="User must be 18 or older"
        )

        assert error.message == "Business rule violated"
        assert error.details["business_rule"] == "User must be 18 or older"


class TestResourceNotFoundError:
    """测试资源未找到错误异常"""

    def test_basic_resource_not_found_error(self):
        """测试基本资源未找到错误"""
        error = ResourceNotFoundError("Resource not found")
        assert error.message == "Resource not found"
        assert isinstance(error, BaseApplicationError)

    def test_resource_not_found_error_with_details(self):
        """测试带详细信息的资源未找到错误"""
        error = ResourceNotFoundError(
            "User not found", resource_type="User", resource_id="123"
        )

        assert error.message == "User not found"
        assert error.details["resource_type"] == "User"
        assert error.details["resource_id"] == "123"


class TestPermissionError:
    """测试权限错误异常"""

    def test_basic_permission_error(self):
        """测试基本权限错误"""
        error = CustomPermissionError("Access denied")
        assert error.message == "Access denied"
        assert isinstance(error, BaseApplicationError)

    def test_permission_error_with_required_permission(self):
        """测试带所需权限的权限错误"""
        error = CustomPermissionError("Access denied", required_permission="admin")

        assert error.message == "Access denied"
        assert error.details["required_permission"] == "admin"


class TestTimeoutError:
    """测试超时错误异常"""

    def test_basic_timeout_error(self):
        """测试基本超时错误"""
        error = CustomTimeoutError("Operation timed out")
        assert error.message == "Operation timed out"
        assert isinstance(error, BaseApplicationError)

    def test_timeout_error_with_details(self):
        """测试带详细信息的超时错误"""
        error = CustomTimeoutError(
            "Operation timed out", timeout_seconds=30.0, operation="database_query"
        )

        assert error.message == "Operation timed out"
        assert error.details["timeout_seconds"] == 30.0
        assert error.details["operation"] == "database_query"


class TestRateLimitError:
    """测试速率限制错误异常"""

    def test_basic_rate_limit_error(self):
        """测试基本速率限制错误"""
        error = RateLimitError("Rate limit exceeded")
        assert error.message == "Rate limit exceeded"
        assert isinstance(error, BaseApplicationError)

    def test_rate_limit_error_with_details(self):
        """测试带详细信息的速率限制错误"""
        error = RateLimitError("Rate limit exceeded", retry_after=60, limit=100)

        assert error.message == "Rate limit exceeded"
        assert error.details["retry_after"] == 60
        assert error.details["limit"] == 100
