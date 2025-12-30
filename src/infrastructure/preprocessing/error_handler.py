"""
文档预处理错误处理模块

为文档预处理流程提供统一的错误处理和结构化日志记录.
包含领域特定的结构化日志字段,用于关键预处理步骤:
- MinerU适配器
- 预处理协调器
- LLMAdRemover

生成命令: /speckit.implement T040
生成时间: 2025-12-17
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import time
from typing import Any

from src.shared.exceptions.base_exceptions import (
    BaseApplicationError,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class PreprocessingError(BaseApplicationError):
    """文档预处理专用异常基类"""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
        preprocessing_step: str | None = None,
        file_path: str | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            original_error=original_error,
            **kwargs,
        )
        self.preprocessing_step = preprocessing_step
        self.file_path = file_path


class MinerUAdapterError(PreprocessingError):
    """MinerU适配器专用异常"""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
        file_path: str | None = None,
        batch_id: str | None = None,
        api_endpoint: str | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            original_error=original_error,
            preprocessing_step="mineru_adapter",
            file_path=file_path,
            **kwargs,
        )
        self.batch_id = batch_id
        self.api_endpoint = api_endpoint


class MinerUAPIError(MinerUAdapterError):
    """MinerU API调用异常"""


class MinerUConfigError(MinerUAdapterError):
    """MinerU配置错误"""


class MinerUFileError(MinerUAdapterError):
    """MinerU文件处理错误"""


class LLMAdRemoverError(PreprocessingError):
    """LLM广告清洗器专用异常"""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
        file_path: str | None = None,
        segment_index: int | None = None,
        total_segments: int | None = None,
        model_name: str | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            original_error=original_error,
            preprocessing_step="llm_ad_remover",
            file_path=file_path,
            **kwargs,
        )
        self.segment_index = segment_index
        self.total_segments = total_segments
        self.model_name = model_name


class PreprocessorCoordinatorError(PreprocessingError):
    """预处理协调器专用异常"""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict[str, Any] | None = None,
        original_error: Exception | None = None,
        file_path: str | None = None,
        pipeline_stage: str | None = None,
        **kwargs,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            details=details,
            original_error=original_error,
            preprocessing_step="preprocessor_coordinator",
            file_path=file_path,
            **kwargs,
        )
        self.pipeline_stage = pipeline_stage


class PreprocessingErrorHandler:
    """文档预处理错误处理器"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def log_mineru_start(
        self,
        file_path: str,
        file_format: str,
        file_size_mb: float,
        batch_id: str | None = None,
        **kwargs,
    ) -> None:
        """记录MinerU处理开始的结构化日志"""
        self.logger.info(
            "MinerU文档解析开始",
            extra={
                "preprocessing_step": "mineru_adapter",
                "action": "start",
                "file_path": file_path,
                "file_format": file_format,
                "file_size_mb": round(file_size_mb, 2),
                "batch_id": batch_id,
                "timestamp": time.time(),
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
        """记录MinerU处理成功的结构化日志"""
        self.logger.info(
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
                "timestamp": time.time(),
                **kwargs,
            },
        )

    def log_mineru_error(
        self,
        error: MinerUAdapterError | Exception,
        file_path: str,
        batch_id: str | None = None,
        **kwargs,
    ) -> None:
        """记录MinerU处理错误的结构化日志"""
        if isinstance(error, MinerUAdapterError):
            error_details = {
                "preprocessing_step": error.preprocessing_step,
                "action": "error",
                "error_code": error.error_code,
                "error_message": str(error),
                "file_path": file_path,
                "batch_id": batch_id or error.batch_id,
                "api_endpoint": error.api_endpoint,
                "timestamp": time.time(),
                **kwargs,
            }
            if error.details:
                error_details.update(error.details)
        else:
            error_details = {
                "preprocessing_step": "mineru_adapter",
                "action": "error",
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                "file_path": file_path,
                "batch_id": batch_id,
                "timestamp": time.time(),
                **kwargs,
            }

        self.logger.error("MinerU文档解析失败: %s", error, extra=error_details)

    def log_llm_cleaning_start(
        self,
        file_path: str,
        document_length: int,
        estimated_tokens: int,
        segments_count: int,
        model_name: str,
        **kwargs,
    ) -> None:
        """记录LLM清洗开始的结构化日志"""
        self.logger.info(
            "LLM广告清洗开始",
            extra={
                "preprocessing_step": "llm_ad_remover",
                "action": "start",
                "file_path": file_path,
                "document_length": document_length,
                "estimated_tokens": estimated_tokens,
                "segments_count": segments_count,
                "model_name": model_name,
                "timestamp": time.time(),
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
        """记录LLM段落处理开始的结构化日志"""
        self.logger.info(
            "LLM清洗段落开始: %d/%d",
            extra={
                "preprocessing_step": "llm_ad_remover",
                "action": "segment_start",
                "file_path": file_path,
                "segment_index": segment_index,
                "total_segments": total_segments,
                "segment_length": segment_length,
                "estimated_tokens": estimated_tokens,
                "timestamp": time.time(),
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
        """记录LLM段落处理成功的结构化日志"""
        self.logger.info(
            "LLM清洗段落成功: %d/%d",
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
                "timestamp": time.time(),
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
        """记录LLM清洗完成的结构化日志"""
        self.logger.info(
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
                "timestamp": time.time(),
                **kwargs,
            },
        )

    def log_llm_cleaning_error(
        self,
        error: LLMAdRemoverError | Exception,
        file_path: str,
        segment_index: int | None = None,
        total_segments: int | None = None,
        **kwargs,
    ) -> None:
        """记录LLM清洗错误的结构化日志"""
        if isinstance(error, LLMAdRemoverError):
            error_details = {
                "preprocessing_step": error.preprocessing_step,
                "action": "error",
                "error_code": error.error_code,
                "error_message": str(error),
                "file_path": file_path,
                "segment_index": segment_index or error.segment_index,
                "total_segments": total_segments or error.total_segments,
                "model_name": error.model_name,
                "timestamp": time.time(),
                **kwargs,
            }
            if error.details:
                error_details.update(error.details)
        else:
            error_details = {
                "preprocessing_step": "llm_ad_remover",
                "action": "error",
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                "file_path": file_path,
                "segment_index": segment_index,
                "total_segments": total_segments,
                "timestamp": time.time(),
                **kwargs,
            }

        self.logger.error("LLM广告清洗失败: %s", error, extra=error_details)

    def log_coordinator_start(
        self, file_path: str, file_format: str, pipeline_stages: list[str], **kwargs
    ) -> None:
        """记录预处理协调器开始的结构化日志"""
        self.logger.info(
            "文档预处理协调器开始",
            extra={
                "preprocessing_step": "preprocessor_coordinator",
                "action": "start",
                "file_path": file_path,
                "file_format": file_format,
                "pipeline_stages": pipeline_stages,
                "timestamp": time.time(),
                **kwargs,
            },
        )

    def log_coordinator_stage_start(self, file_path: str, stage: str, **kwargs) -> None:
        """记录预处理协调器阶段开始的结构化日志"""
        self.logger.info(
            "预处理阶段开始: %s",
            extra={
                "preprocessing_step": "preprocessor_coordinator",
                "action": "stage_start",
                "file_path": file_path,
                "pipeline_stage": stage,
                "timestamp": time.time(),
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
        """记录预处理协调器阶段成功的结构化日志"""
        self.logger.info(
            "预处理阶段成功: %s",
            extra={
                "preprocessing_step": "preprocessor_coordinator",
                "action": "stage_success",
                "file_path": file_path,
                "pipeline_stage": stage,
                "processing_time_seconds": round(processing_time_seconds, 2),
                "output_documents_count": output_documents_count,
                "timestamp": time.time(),
                **kwargs,
            },
        )

    def log_coordinator_success(
        self,
        file_path: str,
        total_processing_time_seconds: float,
        pipeline_stages_completed: list[str],
        final_documents_count: int,
        **kwargs,
    ) -> None:
        """记录预处理协调器完成的结构化日志"""
        self.logger.info(
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
                "timestamp": time.time(),
                **kwargs,
            },
        )

    def log_coordinator_error(
        self,
        error: PreprocessorCoordinatorError | Exception,
        file_path: str,
        stage: str | None = None,
        **kwargs,
    ) -> None:
        """记录预处理协调器错误的结构化日志"""
        if isinstance(error, PreprocessorCoordinatorError):
            error_details = {
                "preprocessing_step": error.preprocessing_step,
                "action": "error",
                "error_code": error.error_code,
                "error_message": str(error),
                "file_path": file_path,
                "pipeline_stage": stage or error.pipeline_stage,
                "timestamp": time.time(),
                **kwargs,
            }
            if error.details:
                error_details.update(error.details)
        else:
            error_details = {
                "preprocessing_step": "preprocessor_coordinator",
                "action": "error",
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                "file_path": file_path,
                "pipeline_stage": stage,
                "timestamp": time.time(),
                **kwargs,
            }

        self.logger.error("文档预处理协调器失败: %s", error, extra=error_details)

    def map_mineru_error(
        self,
        original_error: Exception,
        file_path: str,
        batch_id: str | None = None,
        api_endpoint: str | None = None,
        **kwargs,
    ) -> MinerUAdapterError:
        """将MinerU底层错误映射为项目自定义异常"""
        error_str = str(original_error).lower()

        # API认证错误
        if any(
            keyword in error_str
            for keyword in ["401", "unauthorized", "authentication", "api key"]
        ):
            return MinerUAdapterError(
                message="MinerU API认证失败,请检查API Key配置",
                error_code="MINERU_AUTH_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                batch_id=batch_id,
                api_endpoint=api_endpoint,
                **kwargs,
            )

        # 文件格式错误
        if any(
            keyword in error_str
            for keyword in ["format", "unsupported", "invalid file"]
        ):
            return MinerUAdapterError(
                message="MinerU不支持的文件格式",
                error_code="MINERU_FORMAT_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                batch_id=batch_id,
                api_endpoint=api_endpoint,
                **kwargs,
            )

        # 文件大小超限
        if any(keyword in error_str for keyword in ["size", "too large", "limit"]):
            return MinerUAdapterError(
                message="MinerU文件大小超过限制",
                error_code="MINERU_SIZE_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                batch_id=batch_id,
                api_endpoint=api_endpoint,
                **kwargs,
            )

        # 网络连接错误
        if any(
            keyword in error_str
            for keyword in ["connection", "network", "timeout", "ssl"]
        ):
            return MinerUAdapterError(
                message="MinerU网络连接错误",
                error_code="MINERU_NETWORK_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                batch_id=batch_id,
                api_endpoint=api_endpoint,
                **kwargs,
            )

        # 服务器错误
        if any(
            keyword in error_str
            for keyword in ["500", "502", "503", "504", "server error"]
        ):
            return MinerUAdapterError(
                message="MinerU服务器错误",
                error_code="MINERU_SERVER_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                batch_id=batch_id,
                api_endpoint=api_endpoint,
                **kwargs,
            )

        # 任务处理失败
        if any(
            keyword in error_str
            for keyword in ["failed", "processing error", "parse error"]
        ):
            return MinerUAdapterError(
                message="MinerU文档处理失败",
                error_code="MINERU_PROCESSING_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                batch_id=batch_id,
                api_endpoint=api_endpoint,
                **kwargs,
            )

        # 默认错误
        return MinerUAdapterError(
            message="MinerU未知错误",
            error_code="MINERU_UNKNOWN_ERROR",
            details={"original_error": str(original_error)},
            original_error=original_error,
            file_path=file_path,
            batch_id=batch_id,
            api_endpoint=api_endpoint,
            **kwargs,
        )

    def map_llm_error(
        self,
        original_error: Exception,
        file_path: str,
        segment_index: int | None = None,
        total_segments: int | None = None,
        model_name: str | None = None,
        **kwargs,
    ) -> LLMAdRemoverError:
        """将LLM底层错误映射为项目自定义异常"""
        error_str = str(original_error).lower()

        # Token超限错误
        if any(
            keyword in error_str for keyword in ["token", "context length", "maximum"]
        ):
            return LLMAdRemoverError(
                message="LLM Token数量超过限制",
                error_code="LLM_TOKEN_LIMIT",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                segment_index=segment_index,
                total_segments=total_segments,
                model_name=model_name,
                **kwargs,
            )

        # API并发限制
        if any(
            keyword in error_str
            for keyword in ["429", "rate limit", "too many requests", "并发"]
        ):
            return LLMAdRemoverError(
                message="LLM API并发限制",
                error_code="LLM_RATE_LIMIT",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                segment_index=segment_index,
                total_segments=total_segments,
                model_name=model_name,
                **kwargs,
            )

        # API认证错误
        if any(
            keyword in error_str
            for keyword in ["401", "unauthorized", "authentication", "api key"]
        ):
            return LLMAdRemoverError(
                message="LLM API认证失败",
                error_code="LLM_AUTH_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                segment_index=segment_index,
                total_segments=total_segments,
                model_name=model_name,
                **kwargs,
            )

        # 网络连接错误
        if any(
            keyword in error_str for keyword in ["connection", "network", "timeout"]
        ):
            return LLMAdRemoverError(
                message="LLM网络连接错误",
                error_code="LLM_NETWORK_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                segment_index=segment_index,
                total_segments=total_segments,
                model_name=model_name,
                **kwargs,
            )

        # 模型不可用
        if any(
            keyword in error_str for keyword in ["model", "unavailable", "not found"]
        ):
            return LLMAdRemoverError(
                message="LLM模型不可用",
                error_code="LLM_MODEL_UNAVAILABLE",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                segment_index=segment_index,
                total_segments=total_segments,
                model_name=model_name,
                **kwargs,
            )

        # 默认错误
        return LLMAdRemoverError(
            message="LLM未知错误",
            error_code="LLM_UNKNOWN_ERROR",
            details={"original_error": str(original_error)},
            original_error=original_error,
            file_path=file_path,
            segment_index=segment_index,
            total_segments=total_segments,
            model_name=model_name,
            **kwargs,
        )

    def map_coordinator_error(
        self,
        original_error: Exception,
        file_path: str,
        stage: str | None = None,
        **kwargs,
    ) -> PreprocessorCoordinatorError:
        """将预处理协调器底层错误映射为项目自定义异常"""
        error_str = str(original_error).lower()

        # 格式检测错误
        if any(
            keyword in error_str for keyword in ["format", "detection", "unsupported"]
        ):
            return PreprocessorCoordinatorError(
                message="文档格式检测失败",
                error_code="FORMAT_DETECTION_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                pipeline_stage=stage,
                **kwargs,
            )

        # 文件验证错误
        if any(
            keyword in error_str for keyword in ["validation", "invalid", "corrupted"]
        ):
            return PreprocessorCoordinatorError(
                message="文档验证失败",
                error_code="VALIDATION_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                pipeline_stage=stage,
                **kwargs,
            )

        # 文件系统错误
        if any(
            keyword in error_str
            for keyword in ["file", "directory", "permission", "disk"]
        ):
            return PreprocessorCoordinatorError(
                message="文件系统错误",
                error_code="FILESYSTEM_ERROR",
                details={"original_error": str(original_error)},
                original_error=original_error,
                file_path=file_path,
                pipeline_stage=stage,
                **kwargs,
            )

        # 默认错误
        return PreprocessorCoordinatorError(
            message="预处理协调器未知错误",
            error_code="COORDINATOR_UNKNOWN_ERROR",
            details={"original_error": str(original_error)},
            original_error=original_error,
            file_path=file_path,
            pipeline_stage=stage,
            **kwargs,
        )


# 全局错误处理器实例
preprocessing_error_handler = PreprocessingErrorHandler()
