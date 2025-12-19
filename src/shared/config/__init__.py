"""配置管理模块

提供统一的配置管理和 LLM 服务。
使用 Pydantic Settings 自动加载环境变量和 .env 文件。
"""

from .llm_service import (
    LLMService,
    get_llm_service,
)
from .settings import (
    AppConfig,
    get_config,
    load_config,
)

# 导出主要类和函数
__all__ = [
    # 配置管理
    "AppConfig",
    # LLM 服务
    "LLMService",
    "get_config",
    "get_llm_service",
    "load_config",
]
