"""
提示词管理模块

该模块提供统一的提示词模板管理,用于各种Agent的提示词生成.
遵循LangChain 1.0最佳实践,使用ChatPromptTemplate和结构化输出.
"""

# 生成命令: /speckit.implement T211A
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

from src.shared.prompts.outline_optimization_prompts import (
    OutlineOptimizationPrompts,
)

__all__ = [
    "OutlineOptimizationPrompts",
]
