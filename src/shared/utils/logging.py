# 生成命令: T011 通用工具函数实现
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
日志配置和格式化工具模块

提供统一的日志配置,结构化日志记录和日志级别管理功能.
支持控制台,文件等多种输出格式, 便于调试和监控.
"""

import contextlib
import json
import logging
import sys
from datetime import datetime
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, ClassVar


class LogLevel(Enum):
    """日志级别枚举"""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class LogFormat(Enum):
    """日志格式枚举"""

    SIMPLE = "simple"
    DETAILED = "detailed"
    STRUCTURED = "structured"
    JSON = "json"


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为结构化JSON"""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 添加额外字段
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data, ensure_ascii=False)


class JSONFormatter(logging.Formatter):
    """JSON格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON"""
        log_data = {
            "@timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname.lower(),
            "message": record.getMessage(),
            "logger": record.name,
            "source": {
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            },
        }

        # 添加异常信息
        if record.exc_info:
            log_data["error"] = {
                "type": (
                    record.exc_info[0].__name__ if record.exc_info[0] else "Unknown"
                ),
                "message": str(record.exc_info[1]) if record.exc_info[1] else "",
                "stack_trace": self.formatException(record.exc_info),
            }

        # 添加额外字段
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
            }:
                extra_fields[key] = value

        if extra_fields:
            log_data["fields"] = extra_fields

        return json.dumps(log_data, ensure_ascii=False)


class LoggerManager:
    """日志管理器"""

    _loggers: ClassVar[dict[str, logging.Logger]] = {}
    _configured: ClassVar[bool] = False

    @classmethod
    def configure_logging(
        cls,
        level: LogLevel | str = LogLevel.INFO,
        format_type: LogFormat | str = LogFormat.DETAILED,
        log_file: str | None = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        *,
        console_output: bool = True,
    ) -> None:
        """配置全局日志设置

        Args:
            level: 日志级别
            format_type: 日志格式类型
            log_file: 日志文件路径(可选)
            max_file_size: 日志文件最大大小(字节)
            backup_count: 备份文件数量
            console_output: 是否输出到控制台
        """
        if isinstance(level, str):
            level = LogLevel[level.upper()]
        if isinstance(format_type, str):
            format_type = LogFormat[format_type.upper()]

        # 如果已经配置过, 直接返回
        if cls._configured:
            return

        # 获取根日志器
        root_logger = logging.getLogger()

        # 在pytest环境下, 避免干预其日志捕获配置
        # pytest 在启动时会为根日志器安装自己的handler, 用于捕获日志输出.
        # 如果我们在这里清理或关闭这些handler, 会导致类似
        # 'ValueError: I/O operation on closed file' 或 'OSError: [WinError 6] 句柄无效'.
        if "pytest" in sys.modules and root_logger.handlers:
            cls._configured = True
            return

        # 正常应用运行时才配置自己的日志处理器
        root_logger.setLevel(level.value)

        # 清除现有处理器(此时不在pytest环境下, 不会影响测试框架的捕获)
        root_logger.handlers.clear()

        # 创建格式化器
        formatter = cls._create_formatter(format_type)

        # 添加控制台处理器
        if console_output:
            # 使用默认的 StreamHandler (输出到当前 sys.stderr)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            console_handler.setLevel(level.value)

            # 尝试设置控制台输出编码为UTF-8(如果支持)
            if hasattr(console_handler.stream, "reconfigure"):
                with contextlib.suppress(Exception):
                    console_handler.stream.reconfigure(
                        encoding="utf-8", errors="replace"
                    )
            root_logger.addHandler(console_handler)

        # 添加文件处理器
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level.value)
            root_logger.addHandler(file_handler)

        cls._configured = True

    @classmethod
    def _create_formatter(cls, format_type: LogFormat) -> logging.Formatter:
        """创建日志格式化器"""
        if format_type == LogFormat.SIMPLE:
            return logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        elif format_type == LogFormat.DETAILED:
            return logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - "
                "%(module)s:%(funcName)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        if format_type == LogFormat.STRUCTURED:
            return StructuredFormatter()
        if format_type == LogFormat.JSON:
            return JSONFormatter()
        # 理论上 LogFormat 已覆盖所有枚举值,此处为前向兼容的兜底
        return logging.Formatter(  # type: ignore[unreachable]
            "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """获取日志器实例

        Args:
            name: 日志器名称, 通常使用 __name__

        Returns:
            日志器实例
        """
        if name not in cls._loggers:
            logger = logging.getLogger(name)
            cls._loggers[name] = logger

            # 如果未配置全局日志, 使用默认配置
            if not cls._configured:
                cls.configure_logging()

        return cls._loggers[name]


def get_logger(name: str) -> logging.Logger:
    """获取日志器实例的便捷函数

    Args:
        name: 日志器名称, 通常使用 __name__

    Returns:
        日志器实例
    """
    return LoggerManager.get_logger(name)


def log_structured(
    logger: logging.Logger, level: LogLevel | str, message: str, **extra_fields: Any
) -> None:
    """记录结构化日志

    Args:
        logger: 日志器实例
        level: 日志级别
        message: 日志消息
        **extra_fields: 额外的结构化字段
    """
    if isinstance(level, str):
        level = LogLevel[level.upper()]

    # 创建带有额外字段的日志记录
    extra = {"extra_fields": extra_fields}
    logger.log(level.value, message, extra=extra)


def log_performance(
    logger: logging.Logger, operation: str, duration: float, **metadata: Any
) -> None:
    """记录性能日志

    Args:
        logger: 日志器实例
        operation: 操作名称
        duration: 执行时间(秒)
        **metadata: 额外的元数据
    """
    log_structured(
        logger,
        LogLevel.INFO,
        f"Performance: {operation}",
        operation=operation,
        duration_seconds=duration,
        duration_ms=duration * 1000,
        **metadata,
    )


def log_error(
    logger: logging.Logger,
    error: Exception,
    context: str | None = None,
    **extra_fields: Any,
) -> None:
    """记录错误日志

    Args:
        logger: 日志器实例
        error: 异常对象
        context: 错误上下文描述
        **extra_fields: 额外的结构化字段
    """
    message = f"Error: {type(error).__name__}: {error!s}"
    if context:
        message = f"{context} - {message}"

    log_structured(
        logger,
        LogLevel.ERROR,
        message,
        error_type=type(error).__name__,
        error_message=str(error),
        context=context,
        **extra_fields,
    )


# 预配置的日志器
app_logger = get_logger("whitepaper.app")
agent_logger = get_logger("whitepaper.agent")
storage_logger = get_logger("whitepaper.storage")
api_logger = get_logger("whitepaper.api")
