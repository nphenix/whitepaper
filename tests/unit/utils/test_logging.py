# 生成命令: T011 通用工具函数实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
日志模块单元测试
"""

import builtins
import contextlib
import json
import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from src.shared.utils.logging import (
    JSONFormatter,
    LogFormat,
    LoggerManager,
    LogLevel,
    StructuredFormatter,
    agent_logger,
    api_logger,
    app_logger,
    get_logger,
    log_error,
    log_performance,
    log_structured,
    storage_logger,
)


class TestLogLevel:
    """测试日志级别枚举"""

    def test_log_level_values(self):
        """测试日志级别值"""
        assert LogLevel.DEBUG.value == logging.DEBUG
        assert LogLevel.INFO.value == logging.INFO
        assert LogLevel.WARNING.value == logging.WARNING
        assert LogLevel.ERROR.value == logging.ERROR
        assert LogLevel.CRITICAL.value == logging.CRITICAL


class TestLogFormat:
    """测试日志格式枚举"""

    def test_log_format_values(self):
        """测试日志格式值"""
        assert LogFormat.SIMPLE.value == "simple"
        assert LogFormat.DETAILED.value == "detailed"
        assert LogFormat.STRUCTURED.value == "structured"
        assert LogFormat.JSON.value == "json"


class TestStructuredFormatter:
    """测试结构化格式化器"""

    def test_format_basic_log(self):
        """测试基本日志格式化"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test_logger"
        assert "timestamp" in parsed
        assert "module" in parsed
        assert "function" in parsed
        assert "line" in parsed

    def test_format_with_exception(self):
        """测试包含异常的日志格式化"""
        formatter = StructuredFormatter()

        try:
            msg = "Test error"
            raise ValueError(msg)
        except Exception:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=True,
            )
            record.exc_info = (ValueError, ValueError("Test error"), None)

            result = formatter.format(record)
            parsed = json.loads(result)

            assert "exception" in parsed


class TestJSONFormatter:
    """测试JSON格式化器"""

    def test_format_basic_log(self):
        """测试基本日志格式化"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        parsed = json.loads(result)

        assert parsed["level"] == "info"
        assert parsed["message"] == "Test message"
        assert parsed["logger"] == "test_logger"
        assert "@timestamp" in parsed
        assert "source" in parsed
        assert parsed["source"]["module"] == "test"

    def test_format_with_extra_fields(self):
        """测试包含额外字段的日志格式化"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.user_id = "12345"
        record.request_id = "abc-123"

        result = formatter.format(record)
        parsed = json.loads(result)

        assert "fields" in parsed
        assert parsed["fields"]["user_id"] == "12345"
        assert parsed["fields"]["request_id"] == "abc-123"


class TestLoggerManager:
    """测试日志管理器"""

    def setup_method(self):
        """测试前设置"""
        # 重置日志管理器状态
        LoggerManager._loggers.clear()
        LoggerManager._configured = False

    def teardown_method(self):
        """测试后清理"""
        # 清理日志管理器状态
        LoggerManager._loggers.clear()
        LoggerManager._configured = False

    def test_configure_logging_default(self):
        """测试默认日志配置"""
        LoggerManager.configure_logging()

        assert LoggerManager._configured is True

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

    def test_configure_logging_with_file(self):
        """测试配置文件日志"""
        temp_dir = tempfile.mkdtemp()
        try:
            log_file = os.path.join(temp_dir, "test.log")

            LoggerManager.configure_logging(
                level=LogLevel.DEBUG, log_file=log_file, console_output=False
            )

            # 测试日志文件是否创建
            logger = LoggerManager.get_logger("test")
            logger.info("Test message")

            # 等待日志写入
            import time

            time.sleep(0.1)

            # 手动刷新日志处理器
            for handler in logger.handlers:
                handler.flush()

            assert os.path.exists(log_file)
        finally:
            # 手动清理
            import shutil

            with contextlib.suppress(builtins.BaseException):
                shutil.rmtree(temp_dir)

    def test_get_logger(self):
        """测试获取日志器"""
        logger1 = LoggerManager.get_logger("test_logger")
        logger2 = LoggerManager.get_logger("test_logger")
        logger3 = LoggerManager.get_logger("another_logger")

        # 测试单例模式
        assert logger1 is logger2
        assert logger1 is not logger3

        # 测试日志器名称
        assert logger1.name == "test_logger"
        assert logger3.name == "another_logger"

    def test_get_logger_auto_configure(self):
        """测试自动配置日志器"""
        # 不预先配置,直接获取日志器
        logger = LoggerManager.get_logger("auto_test")

        # 应该自动配置
        assert LoggerManager._configured is True
        assert isinstance(logger, logging.Logger)


class TestConvenienceFunctions:
    """测试便捷函数"""

    def setup_method(self):
        """测试前设置"""
        LoggerManager._loggers.clear()
        LoggerManager._configured = False

    def teardown_method(self):
        """测试后清理"""
        LoggerManager._loggers.clear()
        LoggerManager._configured = False

    def test_get_logger_function(self):
        """测试get_logger便捷函数"""
        logger = get_logger("test_convenience")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_convenience"

    def test_log_structured(self):
        """测试结构化日志记录"""
        logger = get_logger("test_structured")

        with patch.object(logger, "log") as mock_log:
            log_structured(
                logger,
                LogLevel.INFO,
                "Test structured log",
                user_id="123",
                action="test",
            )

            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            assert args[0] == LogLevel.INFO.value
            assert args[1] == "Test structured log"
            assert "extra" in kwargs
            assert kwargs["extra"]["extra_fields"]["user_id"] == "123"
            assert kwargs["extra"]["extra_fields"]["action"] == "test"

    def test_log_performance(self):
        """测试性能日志记录"""
        logger = get_logger("test_performance")

        with patch.object(logger, "log") as mock_log:
            log_performance(logger, "test_operation", 1.5, param1="value1")

            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            assert args[0] == LogLevel.INFO.value
            assert "Performance: test_operation" in args[1]

            extra_fields = kwargs["extra"]["extra_fields"]
            assert extra_fields["operation"] == "test_operation"
            assert extra_fields["duration_seconds"] == 1.5
            assert extra_fields["duration_ms"] == 1500.0
            assert extra_fields["param1"] == "value1"

    def test_log_error(self):
        """测试错误日志记录"""
        logger = get_logger("test_error")
        error = ValueError("Test error")

        with patch.object(logger, "log") as mock_log:
            log_error(logger, error, "Test context", user_id="123")

            mock_log.assert_called_once()
            args, kwargs = mock_log.call_args
            assert args[0] == LogLevel.ERROR.value
            assert "Error: ValueError: Test error" in args[1]
            assert "Test context" in args[1]

            extra_fields = kwargs["extra"]["extra_fields"]
            assert extra_fields["error_type"] == "ValueError"
            assert extra_fields["error_message"] == "Test error"
            assert extra_fields["context"] == "Test context"
            assert extra_fields["user_id"] == "123"

    def test_predefined_loggers(self):
        """测试预定义的日志器"""
        assert isinstance(app_logger, logging.Logger)
        assert app_logger.name == "whitepaper.app"

        assert isinstance(agent_logger, logging.Logger)
        assert agent_logger.name == "whitepaper.agent"

        assert isinstance(storage_logger, logging.Logger)
        assert storage_logger.name == "whitepaper.storage"

        assert isinstance(api_logger, logging.Logger)
        assert api_logger.name == "whitepaper.api"


if __name__ == "__main__":
    pytest.main([__file__])
