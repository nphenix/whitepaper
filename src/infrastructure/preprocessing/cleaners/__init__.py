"""
文档清洗器模块

该模块包含各种文档清洗器,用于对解析后的文档内容进行进一步清洗和处理。

注意:T028文本清洗器、T029格式标准化器和T030-MinerU噪声去除器已被移除,
现在使用T030A-LLM-AdRemover(基于大模型的智能广告清洗器)作为默认清洗方案。
"""

from .llm_ad_remover import AdCleaningResult, LLMAdRemover

__all__ = [
    "AdCleaningResult",
    "LLMAdRemover",
]
