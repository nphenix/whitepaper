# 生成命令: /speckit.implement T038
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
文档格式识别和验证模块

该模块提供文档格式识别和验证功能,支持PDF,DOCX格式(HTML已暂停).
基于LangChain 1.0最佳实践实现,为预处理协调器提供统一的格式检测接口.

功能特性:
- 支持PDF,DOCX格式识别
- 验证文件格式与扩展名匹配
- 验证文件大小和基本完整性
- 提供统一的格式检测接口
- 集成python-magic和filetype库进行深度检测
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import magic

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False
    logging.warning("python-magic未安装,将使用基础文件扩展名检测")

try:
    import filetype

    FILETYPE_AVAILABLE = True
except ImportError:
    FILETYPE_AVAILABLE = False
    logging.warning("filetype未安装,将使用基础文件扩展名检测")


logger = logging.getLogger(__name__)


@dataclass
class FormatInfo:
    """文档格式信息"""

    format: str  # 格式名称:pdf, docx等
    mime_type: str | None = None  # MIME类型
    extension: str | None = None  # 文件扩展名
    is_valid: bool = True  # 格式是否有效
    file_size: int | None = None  # 文件大小(字节)
    confidence: float = 1.0  # 检测置信度
    details: dict[str, Any] | None = None  # 额外详情


@dataclass
class ValidationResult:
    """验证结果"""

    is_valid: bool  # 是否通过验证
    errors: list[str]  # 错误列表
    warnings: list[str]  # 警告列表
    format_info: FormatInfo | None = None  # 格式信息


class FormatDetector:
    """
    文档格式检测器

    提供统一的文档格式识别和验证功能,支持多种检测策略.
    优先使用python-magic和filetype进行深度检测,回退到扩展名检测.
    """

    # 支持的格式配置
    SUPPORTED_FORMATS = {
        "pdf": {
            "mime_types": ["application/pdf"],
            "extensions": [".pdf"],
            "max_size": 100 * 1024 * 1024,  # 100MB
            "magic_signatures": [b"%PDF-"],
        },
        "docx": {
            "mime_types": [
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/zip",
            ],
            "extensions": [".docx"],
            "max_size": 50 * 1024 * 1024,  # 50MB
            "magic_signatures": [b"PK\x03\x04"],  # ZIP格式
        },
    }

    def __init__(self, enable_deep_detection: bool = True):
        """
        初始化格式检测器

        Args:
            enable_deep_detection: 是否启用深度检测(python-magic/filetype)
        """
        self.enable_deep_detection = enable_deep_detection
        self._init_detection_libs()

    def _init_detection_libs(self) -> None:
        """初始化检测库"""
        if self.enable_deep_detection:
            if MAGIC_AVAILABLE:
                try:
                    # 尝试初始化magic库
                    magic.Magic(mime=True)
                    logger.debug("python-magic库初始化成功")
                except Exception as e:
                    logger.warning(f"python-magic库初始化失败: {e}")

            if FILETYPE_AVAILABLE:
                logger.debug("filetype库可用")

    def detect_format(self, file_path: str) -> FormatInfo:
        """
        检测文档格式

        Args:
            file_path: 文件路径

        Returns:
            FormatInfo: 检测到的格式信息
        """
        if not os.path.exists(file_path):
            msg = f"文件不存在: {file_path}"
            raise FileNotFoundError(msg)

        # 获取文件基本信息
        file_stat = os.stat(file_path)
        file_size = file_stat.st_size
        file_ext = Path(file_path).suffix.lower()

        # 基础格式信息
        format_info = FormatInfo(
            format="unknown",
            extension=file_ext,
            file_size=file_size,
            details={"file_path": file_path},
        )

        # 尝试深度检测
        if self.enable_deep_detection:
            deep_result = self._deep_detect_format(file_path)
            if deep_result.format != "unknown":
                format_info = deep_result
                format_info.extension = file_ext
                format_info.file_size = file_size
                format_info.details = {
                    "file_path": file_path,
                    **(deep_result.details or {}),
                }

        # 如果深度检测失败,使用扩展名检测
        if format_info.format == "unknown":
            ext_result = self._detect_by_extension(file_ext)
            format_info.format = ext_result.format
            format_info.mime_type = ext_result.mime_type
            format_info.confidence = 0.7  # 扩展名检测置信度较低

        # 验证格式是否支持
        format_info.is_valid = format_info.format in self.SUPPORTED_FORMATS

        logger.debug(
            f"格式检测结果: {format_info.format}, "
            f"置信度: {format_info.confidence}, "
            f"文件大小: {file_size}"
        )

        return format_info

    def _deep_detect_format(self, file_path: str) -> FormatInfo:
        """
        深度检测文档格式

        Args:
            file_path: 文件路径

        Returns:
            FormatInfo: 检测到的格式信息
        """
        format_info = FormatInfo(format="unknown", confidence=0.0)

        # 尝试使用python-magic
        if MAGIC_AVAILABLE:
            try:
                mime_type = magic.Magic(mime=True).from_file(file_path)
                file_type = magic.Magic().from_file(file_path)

                format_info.mime_type = mime_type
                format_info.details = {
                    "mime_type": mime_type,
                    "file_type": file_type,
                    "detection_method": "python-magic",
                }

                # 根据MIME类型推断格式
                detected_format = self._mime_to_format(mime_type)
                if detected_format:
                    format_info.format = detected_format
                    format_info.confidence = 0.95
                    return format_info

            except Exception as e:
                logger.warning(f"python-magic检测失败: {e}")

        # 尝试使用filetype
        if FILETYPE_AVAILABLE:
            try:
                kind = filetype.guess(file_path)
                if kind:
                    format_info.mime_type = kind.mime
                    format_info.details = {
                        "mime_type": kind.mime,
                        "extension": kind.extension,
                        "detection_method": "filetype",
                    }

                    # 根据filetype结果推断格式
                    detected_format = self._filetype_to_format(kind.extension)
                    if detected_format:
                        format_info.format = detected_format
                        format_info.confidence = 0.9
                        return format_info

            except Exception as e:
                logger.warning(f"filetype检测失败: {e}")

        return format_info

    def _detect_by_extension(self, extension: str) -> FormatInfo:
        """
        根据文件扩展名检测格式

        Args:
            extension: 文件扩展名

        Returns:
            FormatInfo: 检测到的格式信息
        """
        extension_map = {
            ".pdf": ("pdf", "application/pdf"),
            ".docx": (
                "docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        }

        if extension in extension_map:
            format_name, mime_type = extension_map[extension]
            return FormatInfo(
                format=format_name,
                mime_type=mime_type,
                extension=extension,
                confidence=0.7,
                details={"detection_method": "extension"},
            )

        return FormatInfo(
            format="unknown",
            extension=extension,
            confidence=0.5,
            details={"detection_method": "extension"},
        )

    def _mime_to_format(self, mime_type: str) -> str | None:
        """
        根据MIME类型推断格式

        Args:
            mime_type: MIME类型

        Returns:
            Optional[str]: 格式名称,如果无法识别则返回None
        """
        mime_to_format = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
            "application/zip": "docx",  # DOCX是ZIP格式
        }

        return mime_to_format.get(mime_type)

    def _filetype_to_format(self, filetype_ext: str) -> str | None:
        """
        根据filetype扩展名推断格式

        Args:
            filetype_ext: filetype检测到的扩展名

        Returns:
            Optional[str]: 格式名称,如果无法识别则返回None
        """
        filetype_to_format = {
            "pdf": "pdf",
            "docx": "docx",
        }

        return filetype_to_format.get(filetype_ext)

    def validate_document(
        self, file_path: str, format_info: FormatInfo | None = None
    ) -> ValidationResult:
        """
        验证文档

        Args:
            file_path: 文件路径
            format_info: 格式信息,如果未提供则自动检测

        Returns:
            ValidationResult: 验证结果
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 检测格式信息
        if format_info is None:
            try:
                format_info = self.detect_format(file_path)
            except Exception as e:
                return ValidationResult(
                    is_valid=False, errors=[f"格式检测失败: {e!s}"], warnings=[]
                )

        # 检查文件是否存在
        if not os.path.exists(file_path):
            errors.append(f"文件不存在: {file_path}")
            return ValidationResult(
                is_valid=False, errors=errors, warnings=warnings, format_info=format_info
            )

        # 检查文件大小
        file_size: int = int(format_info.file_size or 0)
        if file_size == 0:
            errors.append("文件为空")
        elif file_size < 0:
            errors.append("文件大小无效")

        # 检查格式是否支持
        if format_info.format not in self.SUPPORTED_FORMATS:
            errors.append(f"不支持的格式: {format_info.format}")
        else:
            # 检查格式特定限制
            format_config = self.SUPPORTED_FORMATS[format_info.format]
            max_size = format_config["max_size"]

            if file_size > max_size:
                errors.append(f"文件大小超出限制: {file_size} > {max_size} bytes")

            # 检查扩展名匹配
            if format_info.extension:
                expected_extensions = format_config["extensions"]
                if format_info.extension not in expected_extensions:
                    warnings.append(
                        f"扩展名不匹配: {format_info.extension}, "
                        f"期望: {expected_extensions}"
                    )

            # 检查文件头签名(如果支持深度检测)
            if self.enable_deep_detection and file_size > 0:
                try:
                    with open(file_path, "rb") as f:
                        header = f.read(16)

                    signatures = format_config.get("magic_signatures", [])
                    if signatures and not any(
                        header.startswith(sig) for sig in signatures
                    ):
                        warnings.append("文件头签名不匹配,可能已损坏")

                except Exception as e:
                    warnings.append(f"无法读取文件头进行验证: {e}")

        # 检查文件权限
        if not os.access(file_path, os.R_OK):
            errors.append("文件不可读")

        is_valid = len(errors) == 0

        result = ValidationResult(
            is_valid=is_valid, errors=errors, warnings=warnings, format_info=format_info
        )

        logger.debug(
            f"文档验证结果: {is_valid}, 错误: {len(errors)}, 警告: {len(warnings)}"
        )

        return result

    def get_supported_formats(self) -> list[str]:
        """
        获取支持的格式列表

        Returns:
            List[str]: 支持的格式列表
        """
        return list(self.SUPPORTED_FORMATS.keys())

    def get_format_info(self, format_name: str) -> dict[str, Any] | None:
        """
        获取格式的详细信息

        Args:
            format_name: 格式名称

        Returns:
            Optional[Dict[str, Any]]: 格式信息,如果格式不支持则返回None
        """
        return self.SUPPORTED_FORMATS.get(format_name)

    def is_format_supported(self, format_name: str) -> bool:
        """
        检查格式是否支持

        Args:
            format_name: 格式名称

        Returns:
            bool: 是否支持该格式
        """
        return format_name in self.SUPPORTED_FORMATS


# 便捷函数
def detect_document_format(
    file_path: str, enable_deep_detection: bool = True
) -> FormatInfo:
    """
    便捷函数:检测文档格式

    Args:
        file_path: 文件路径
        enable_deep_detection: 是否启用深度检测

    Returns:
        FormatInfo: 格式信息
    """
    detector = FormatDetector(enable_deep_detection)
    return detector.detect_format(file_path)


def validate_document(
    file_path: str, enable_deep_detection: bool = True
) -> ValidationResult:
    """
    便捷函数:验证文档

    Args:
        file_path: 文件路径
        enable_deep_detection: 是否启用深度检测

    Returns:
        ValidationResult: 验证结果
    """
    detector = FormatDetector(enable_deep_detection)
    return detector.validate_document(file_path)
