"""
文档预处理日志配置模块

统一接入项目的异常体系和日志体系,为预处理流程提供结构化日志配置。
支持领域特定的日志格式、过滤器和处理器。

生成命令: /speckit.implement T040
生成时间: 2025-12-17
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import contextlib
import json
import logging
import sys
from datetime import datetime
from typing import Any

from src.shared.utils.logging import JSONFormatter, StructuredFormatter, get_logger


class PreprocessingLogFilter(logging.Filter):
    """预处理日志过滤器,用于添加领域特定的上下文信息"""

    def __init__(self, preprocessing_step: str | None = None):
        super().__init__()
        self.preprocessing_step = preprocessing_step

    def filter(self, record: logging.LogRecord) -> bool:
        # 添加预处理步骤信息
        if self.preprocessing_step:
            record.preprocessing_step = self.preprocessing_step

        # 添加时间戳(如果不存在)
        if not hasattr(record, "timestamp"):
            record.timestamp = datetime.now().timestamp()

        # 添加进程ID和线程ID
        if not hasattr(record, "process_id"):
            record.process_id = record.process
        if not hasattr(record, "thread_id"):
            record.thread_id = record.thread

        return True


class PreprocessingStructuredFormatter(StructuredFormatter):
    """预处理专用的结构化日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        """
        将预处理相关字段注入到 StructuredFormatter 使用的 extra_fields 中,
        确保这些字段出现在最终的结构化日志里。
        """
        # 预处理特定字段列表
        preprocessing_fields = [
            "preprocessing_step",
            "action",
            "file_path",
            "file_format",
            "file_size_mb",
            "batch_id",
            "segment_index",
            "total_segments",
            "model_name",
            "processing_time_seconds",
            "document_length",
            "estimated_tokens",
            "pages_extracted",
            "images_extracted",
            "tables_extracted",
            "original_length",
            "cleaned_length",
            "reduction_ratio",
            "pipeline_stage",
            "output_documents_count",
            "error_code",
            "error_type",
            "api_endpoint",
            "output_path",
            "timestamp",
            "process_id",
            "thread_id",
        ]

        # 确保基础上下文字段存在
        if not hasattr(record, "timestamp"):
            record.timestamp = datetime.now().timestamp()
        if not hasattr(record, "process_id"):
            record.process_id = record.process
        if not hasattr(record, "thread_id"):
            record.thread_id = record.thread

        # 汇总到 extra_fields,StructuredFormatter 会把它们展开到顶层
        extra = getattr(record, "extra_fields", {}) or {}
        for field in preprocessing_fields:
            value = getattr(record, field, None)
            extra[field] = value
        record.extra_fields = extra

        return super().format(record)


class PreprocessingJSONFormatter(JSONFormatter):
    """预处理专用的JSON日志格式化器"""

    def __init__(self):
        super().__init__()
        # 预处理特定的字段列表
        self.preprocessing_fields = [
            "preprocessing_step",
            "action",
            "file_path",
            "file_format",
            "file_size_mb",
            "batch_id",
            "segment_index",
            "total_segments",
            "model_name",
            "processing_time_seconds",
            "document_length",
            "estimated_tokens",
            "pages_extracted",
            "images_extracted",
            "tables_extracted",
            "original_length",
            "cleaned_length",
            "reduction_ratio",
            "pipeline_stage",
            "output_documents_count",
            "error_code",
            "error_type",
            "api_endpoint",
            "output_path",
            "timestamp",
            "process_id",
            "thread_id",
        ]

    def format(self, record: logging.LogRecord) -> str:
        """
        直接生成包含预处理字段的 JSON 日志。

        测试期望可以通过 log_data['preprocessing_step'] 等顶层键
        访问预处理相关字段,因此这里不依赖父类的 fields 嵌套结构,
        而是显式构造完整的 JSON 对象。
        """
        # 基础字段
        log_data: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # 预处理特定字段(全部提升为顶层键)
        for field in self.preprocessing_fields:
            log_data[field] = getattr(record, field, None)

        return json.dumps(log_data, ensure_ascii=False)


def setup_preprocessing_logging(
    level: str = "INFO",
    format_type: str = "structured",
    log_file: str | None = None,
    enable_console: bool = True,
    preprocessing_steps: list[str] | None = None,
) -> None:
    """
    设置预处理模块的日志配置

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: 日志格式类型 (simple, detailed, structured, json)
        log_file: 日志文件路径(可选)
        enable_console: 是否启用控制台输出
        preprocessing_steps: 预处理步骤列表,用于创建特定的日志记录器
    """
    # 创建根日志记录器
    root_logger = logging.getLogger("src.infrastructure.preprocessing")
    root_logger.setLevel(getattr(logging, level.upper()))

    # 清除现有处理器
    root_logger.handlers.clear()

    # 选择格式化器
    if format_type == "json":
        formatter = PreprocessingJSONFormatter()
    elif format_type == "structured":
        formatter = PreprocessingStructuredFormatter()
    elif format_type == "detailed":
        formatter = StructuredFormatter()
    else:  # simple
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # 控制台处理器
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(PreprocessingLogFilter())
        root_logger.addHandler(console_handler)

    # 文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.addFilter(PreprocessingLogFilter())
        root_logger.addHandler(file_handler)

    # 为特定预处理步骤创建专门的日志记录器
    if preprocessing_steps:
        for step in preprocessing_steps:
            step_logger = logging.getLogger(f"src.infrastructure.preprocessing.{step}")
            step_logger.setLevel(getattr(logging, level.upper()))
            # 继承根日志记录器的处理器
            step_logger.parent = root_logger


def get_preprocessing_logger(
    name: str,
    preprocessing_step: str | None = None,
    level: str | None = None,
) -> logging.Logger:
    """
    获取预处理专用的日志记录器

    Args:
        name: 日志记录器名称
        preprocessing_step: 预处理步骤名称
        level: 日志级别(可选)

    Returns:
        配置好的日志记录器
    """
    logger = get_logger(name)

    # 添加预处理步骤过滤器
    if preprocessing_step:
        logger.addFilter(PreprocessingLogFilter(preprocessing_step))

    # 设置日志级别
    if level:
        logger.setLevel(getattr(logging, level.upper()))

    return logger


class PreprocessingLoggerAdapter(logging.LoggerAdapter):
    """预处理日志适配器,用于自动添加上下文信息"""

    def __init__(
        self,
        logger: logging.Logger,
        extra: dict[str, Any] | None = None,
        preprocessing_step: str | None = None,
        file_path: str | None = None,
        batch_id: str | None = None,
        **kwargs,
    ):
        super().__init__(logger, extra or {})
        self.preprocessing_step = preprocessing_step
        self.file_path = file_path
        self.batch_id = batch_id

        # 动态添加所有额外的属性
        for key, value in kwargs.items():
            setattr(self, key, value)

        # 更新 extra 字典
        self.extra.update(kwargs)

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple:
        # 添加预处理特定的上下文信息
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        # 添加预处理步骤
        if self.preprocessing_step:
            kwargs["extra"]["preprocessing_step"] = self.preprocessing_step

        # 添加文件路径
        if self.file_path:
            kwargs["extra"]["file_path"] = self.file_path

        # 添加批次ID
        if self.batch_id:
            kwargs["extra"]["batch_id"] = self.batch_id

        # 合并额外的上下文信息
        kwargs["extra"].update(self.extra)

        return msg, kwargs

    def with_context(self, **context) -> "PreprocessingLoggerAdapter":
        """
        创建带有额外上下文的新适配器

        Args:
            **context: 额外的上下文信息

        Returns:
            新的日志适配器实例
        """
        new_extra = self.extra.copy()
        new_extra.update(context)

        # 创建新的适配器,包含所有当前属性和新上下文
        new_adapter = PreprocessingLoggerAdapter(
            self.logger,
            new_extra,
            self.preprocessing_step,
            self.file_path,
            self.batch_id,
            **context,
        )

        return new_adapter

    # ---- 协调器结构化日志便捷方法 ----

    def log_coordinator_stage_start(self, file_path: str, stage: str, **kwargs) -> None:
        """记录预处理协调器阶段开始的结构化日志."""
        self.info(
            "预处理阶段开始: %s",
            stage,
            extra={
                "preprocessing_step": "preprocessor_coordinator",
                "action": "stage_start",
                "file_path": file_path,
                "pipeline_stage": stage,
                **kwargs,
            },
        )

    def log_coordinator_stage_success(
        self,
        file_path: str,
        stage: str,
        processing_time_seconds: float,
        output_documents_count: int,
        **kwargs,
    ) -> None:
        """记录预处理协调器阶段成功的结构化日志."""
        self.info(
            "预处理阶段成功: %s",
            stage,
            extra={
                "preprocessing_step": "preprocessor_coordinator",
                "action": "stage_success",
                "file_path": file_path,
                "pipeline_stage": stage,
                "processing_time_seconds": round(processing_time_seconds, 2),
                "output_documents_count": output_documents_count,
                **kwargs,
            },
        )

    def log_coordinator_success(
        self,
        file_path: str,
        total_processing_time_seconds: float,
        pipeline_stages_completed: list[str],
        final_documents_count: int | None = None,
        **kwargs,
    ) -> None:
        """记录预处理协调器整体成功的结构化日志."""
        self.info(
            "文档预处理协调器完成",
            extra={
                "preprocessing_step": "preprocessor_coordinator",
                "action": "success",
                "file_path": file_path,
                "total_processing_time_seconds": round(
                    total_processing_time_seconds, 2
                ),
                "pipeline_stages_completed": pipeline_stages_completed,
                "final_documents_count": final_documents_count,
                **kwargs,
            },
        )

    def log_coordinator_error(
        self,
        error: Exception,
        file_path: str,
        stage: str | None = None,
        **kwargs,
    ) -> None:
        """记录预处理协调器错误的结构化日志."""
        self.error(
            "预处理协调器错误: %s",
            error,
            extra={
                "preprocessing_step": "preprocessor_coordinator",
                "action": "error",
                "file_path": file_path,
                "pipeline_stage": stage,
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                **kwargs,
            },
        )

    # ---- MinerU 结构化日志便捷方法 ----

    def log_mineru_start(
        self,
        file_path: str,
        file_format: str,
        file_size_mb: float,
        batch_id: str | None = None,
        **kwargs,
    ) -> None:
        """记录 MinerU 处理开始的结构化日志."""
        self.info(
            "MinerU文档解析开始",
            extra={
                "preprocessing_step": "mineru_adapter",
                "action": "start",
                "file_path": file_path,
                "file_format": file_format,
                "file_size_mb": round(file_size_mb, 2),
                "batch_id": batch_id,
                **kwargs,
            },
        )

    def log_mineru_success(
        self,
        file_path: str,
        batch_id: str,
        processing_time_seconds: float,
        pages_extracted: int,
        images_extracted: int,
        tables_extracted: int,
        output_path: str,
        **kwargs,
    ) -> None:
        """记录 MinerU 处理成功的结构化日志."""
        self.info(
            "MinerU文档解析成功",
            extra={
                "preprocessing_step": "mineru_adapter",
                "action": "success",
                "file_path": file_path,
                "batch_id": batch_id,
                "processing_time_seconds": round(processing_time_seconds, 2),
                "pages_extracted": pages_extracted,
                "images_extracted": images_extracted,
                "tables_extracted": tables_extracted,
                "output_path": output_path,
                **kwargs,
            },
        )

    def log_mineru_error(
        self,
        error: Exception,
        file_path: str,
        batch_id: str | None = None,
        **kwargs,
    ) -> None:
        """记录 MinerU 处理错误的结构化日志."""
        self.error(
            "MinerU文档解析失败: %s",
            error,
            extra={
                "preprocessing_step": "mineru_adapter",
                "action": "error",
                "file_path": file_path,
                "batch_id": batch_id,
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                **kwargs,
            },
        )

    # ---- LLM 广告清洗结构化日志便捷方法 ----

    def log_llm_cleaning_start(
        self,
        file_path: str,
        document_length: int,
        estimated_tokens: int,
        segments_count: int,
        model_name: str,
        **kwargs,
    ) -> None:
        """记录 LLM 广告清洗开始的结构化日志."""
        self.info(
            "LLM广告清洗开始",
            extra={
                "preprocessing_step": "llm_ad_remover",
                "action": "start",
                "file_path": file_path,
                "document_length": document_length,
                "estimated_tokens": estimated_tokens,
                "segments_count": segments_count,
                "model_name": model_name,
                **kwargs,
            },
        )

    def log_llm_segment_start(
        self,
        file_path: str,
        segment_index: int,
        total_segments: int,
        segment_length: int,
        estimated_tokens: int,
        **kwargs,
    ) -> None:
        """记录 LLM 段落处理开始的结构化日志."""
        self.info(
            "LLM清洗段落开始: %d/%d",
            segment_index + 1,
            total_segments,
            extra={
                "preprocessing_step": "llm_ad_remover",
                "action": "segment_start",
                "file_path": file_path,
                "segment_index": segment_index,
                "total_segments": total_segments,
                "segment_length": segment_length,
                "estimated_tokens": estimated_tokens,
                **kwargs,
            },
        )

    def log_llm_segment_success(
        self,
        file_path: str,
        segment_index: int,
        total_segments: int,
        processing_time_seconds: float,
        original_length: int,
        cleaned_length: int,
        reduction_ratio: float,
        **kwargs,
    ) -> None:
        """记录 LLM 段落处理成功的结构化日志."""
        self.info(
            "LLM清洗段落成功: %d/%d",
            segment_index + 1,
            total_segments,
            extra={
                "preprocessing_step": "llm_ad_remover",
                "action": "segment_success",
                "file_path": file_path,
                "segment_index": segment_index,
                "total_segments": total_segments,
                "processing_time_seconds": round(processing_time_seconds, 2),
                "original_length": original_length,
                "cleaned_length": cleaned_length,
                "reduction_ratio": round(reduction_ratio, 4),
                **kwargs,
            },
        )

    def log_llm_cleaning_success(
        self,
        file_path: str,
        total_processing_time_seconds: float,
        total_segments: int,
        original_length: int,
        cleaned_length: int,
        overall_reduction_ratio: float,
        model_name: str,
        **kwargs,
    ) -> None:
        """记录 LLM 广告清洗完成的结构化日志."""
        self.info(
            "LLM广告清洗完成",
            extra={
                "preprocessing_step": "llm_ad_remover",
                "action": "success",
                "file_path": file_path,
                "total_processing_time_seconds": round(
                    total_processing_time_seconds, 2
                ),
                "total_segments": total_segments,
                "original_length": original_length,
                "cleaned_length": cleaned_length,
                "overall_reduction_ratio": round(overall_reduction_ratio, 4),
                "model_name": model_name,
                **kwargs,
            },
        )


def create_mineru_logger(
    file_path: str | None = None, batch_id: str | None = None, **kwargs
) -> PreprocessingLoggerAdapter:
    """
    创建MinerU适配器专用的日志记录器

    Args:
        file_path: 文件路径
        batch_id: 批次ID
        **kwargs: 额外的上下文信息

    Returns:
        配置好的日志适配器
    """
    logger = get_preprocessing_logger("src.infrastructure.preprocessing.mineru_adapter")
    return PreprocessingLoggerAdapter(
        logger,
        preprocessing_step="mineru_adapter",
        file_path=file_path,
        batch_id=batch_id,
        **kwargs,
    )


def create_llm_remover_logger(
    file_path: str | None = None,
    segment_index: int | None = None,
    total_segments: int | None = None,
    model_name: str | None = None,
    **kwargs,
) -> PreprocessingLoggerAdapter:
    """
    创建LLM广告清洗器专用的日志记录器

    Args:
        file_path: 文件路径
        segment_index: 段落索引
        total_segments: 总段落数
        model_name: 模型名称
        **kwargs: 额外的上下文信息

    Returns:
        配置好的日志适配器
    """
    logger = get_preprocessing_logger("src.infrastructure.preprocessing.llm_ad_remover")
    return PreprocessingLoggerAdapter(
        logger,
        preprocessing_step="llm_ad_remover",
        file_path=file_path,
        segment_index=segment_index,
        total_segments=total_segments,
        model_name=model_name,
        **kwargs,
    )


def create_coordinator_logger(
    file_path: str | None = None, pipeline_stage: str | None = None, **kwargs
) -> PreprocessingLoggerAdapter:
    """
    创建预处理协调器专用的日志记录器

    Args:
        file_path: 文件路径
        pipeline_stage: 管线阶段
        **kwargs: 额外的上下文信息

    Returns:
        配置好的日志适配器
    """
    logger = get_preprocessing_logger("src.infrastructure.preprocessing.preprocessor")
    return PreprocessingLoggerAdapter(
        logger,
        preprocessing_step="preprocessor_coordinator",
        file_path=file_path,
        pipeline_stage=pipeline_stage,
        **kwargs,
    )


# 预处理步骤常量
class PreprocessingStep:
    """预处理步骤常量"""

    MINERU_ADAPTER = "mineru_adapter"
    LLM_AD_REMOVER = "llm_ad_remover"
    PREPROCESSOR_COORDINATOR = "preprocessor_coordinator"
    FORMAT_DETECTION = "format_detection"
    FILE_VALIDATION = "file_validation"
    DOCUMENT_LOADING = "document_loading"
    CONTENT_CLEANING = "content_cleaning"
    METADATA_PROCESSING = "metadata_processing"
    QUALITY_REPORTING = "quality_reporting"


# 预处理动作常量
class PreprocessingAction:
    """预处理动作常量"""

    START = "start"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    RETRY = "retry"
    SKIP = "skip"
    SEGMENT_START = "segment_start"
    SEGMENT_SUCCESS = "segment_success"
    SEGMENT_ERROR = "segment_error"
    STAGE_START = "stage_start"
    STAGE_SUCCESS = "stage_success"
    STAGE_ERROR = "stage_error"


# 默认配置
DEFAULT_PREPROCESSING_LOGGING_CONFIG = {
    "level": "INFO",
    "format_type": "structured",
    "enable_console": True,
    "preprocessing_steps": [
        PreprocessingStep.MINERU_ADAPTER,
        PreprocessingStep.LLM_AD_REMOVER,
        PreprocessingStep.PREPROCESSOR_COORDINATOR,
    ],
}


def initialize_preprocessing_logging(config: dict[str, Any] | None = None) -> None:
    """
    初始化预处理日志系统

    Args:
        config: 日志配置字典,如果为None则使用默认配置
    """
    if config is None:
        config = DEFAULT_PREPROCESSING_LOGGING_CONFIG

    setup_preprocessing_logging(**config)


# 在模块导入时自动初始化
with contextlib.suppress(Exception):
    initialize_preprocessing_logging()
