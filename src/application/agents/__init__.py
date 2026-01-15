"""Agent实现

包含各种具体的Agent实现.
"""

from src.application.agents.document_preprocessor import DocumentPreprocessorAgent
from src.application.agents.draft_generator import (
    DraftGeneratorAgent,
    create_draft_generator_agent,
)
from src.application.agents.draft_generator_mvp import (
    DraftGeneratorAgent as DraftGeneratorAgentMVP,
    create_draft_generator_agent as create_draft_generator_agent_mvp,
)
from src.application.agents.outline_optimization_prompts import (
    OutlineOptimizationPrompts,
    get_outline_optimization_prompt,
    get_outline_optimization_system_message,
)
from src.application.agents.outline_optimizer_mvp import OutlineOptimizerAgent

__all__ = [
    "DocumentPreprocessorAgent",
    "DraftGeneratorAgent",
    "DraftGeneratorAgentMVP",
    "OutlineOptimizationPrompts",
    "OutlineOptimizerAgent",
    "create_draft_generator_agent",
    "create_draft_generator_agent_mvp",
    "get_outline_optimization_prompt",
    "get_outline_optimization_system_message",
]
