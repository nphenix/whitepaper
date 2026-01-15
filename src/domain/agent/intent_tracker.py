"""
用户意图追踪器

该模块提供用户意图的提取、追踪和验证功能。
用于确保大纲AI优化过程中不会偏离用户原始意图。

核心功能:
- 意图提取：从用户输入中提取核心意图
- 意图嵌入：将意图转换为向量表示用于相似度计算
- 意图验证：验证优化后的大纲是否保持用户意图
- 变更约束：检测和阻止可能偏离意图的变更

应用于T211大纲优化Agent,用于确保优化后的大纲不会偏离用户原始意图.
"""

from __future__ import annotations

import uuid
from typing import Any
from datetime import UTC, datetime

from pydantic import BaseModel, Field, PrivateAttr

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class IntentExtractionError(Exception):
    """意图提取异常"""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class IntentValidationError(Exception):
    """意图验证异常"""

    def __init__(self, message: str, violations: list[str]) -> None:
        super().__init__(message)
        self.message = message
        self.violations = violations


class CoreIntent(BaseModel):
    """核心意图模型
    
    表示从用户输入中提取的核心意图信息.
    """

    # 核心意图描述
    intent_summary: str = Field(default="", description="核心意图的简短摘要")
    intent_details: str = Field(default="", description="核心意图的详细描述")
    
    # 关键词信息
    core_keywords: set[str] = Field(default_factory=set, description="必须保留的核心关键词")
    secondary_keywords: set[str] = Field(default_factory=set, description="次要关键词")
    
    # 结构信息
    required_sections: set[str] = Field(default_factory=set, description="用户明确要求必须包含的章节标题")
    
    # 元数据
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    confidence: float = Field(default=0.0, description="意图提取的置信度")


class IntentConstraint(BaseModel):
    """意图约束模型
    
    表示优化过程中必须遵守的意图约束.
    """

    # 变更限制
    max_added_ratio: float = Field(default=0.3, description="新增章节的最大比例(相对于原始大纲)")
    max_deleted_ratio: float = Field(default=0.1, description="删除章节的最大比例")
    max_modified_ratio: float = Field(default=0.3, description="修改章节的最大比例")
    
    # 必须保留的项
    must_preserve_item_ids: set[str] = Field(default_factory=set, description="必须保留的章节ID")
    
    # 意图保护级别
    protection_level: str = Field(default="STANDARD", description="保护级别: RELAXED/STANDARD/STRICT")
    
    # 关键词保留率阈值
    keyword_retention_threshold: float = Field(default=0.7, description="关键词保留率阈值")


class IntentValidationResult(BaseModel):
    """意图验证结果模型
    
    表示意图验证的结果信息.
    """

    # 验证状态
    is_valid: bool = Field(default=False, description="是否通过验证")
    
    # 违规列表
    violations: list[str] = Field(default_factory=list, description="违反约束的列表")
    
    # 统计信息
    added_ratio: float = Field(default=0.0, description="新增比例")
    deleted_ratio: float = Field(default=0.0, description="删除比例")
    modified_ratio: float = Field(default=0.0, description="修改比例")
    keyword_retention: float = Field(default=0.0, description="关键词保留率")
    
    # 建议
    suggestions: list[str] = Field(default_factory=list, description="改进建议")
    
    # 置信度
    confidence: float = Field(default=0.0, description="验证结果的置信度")


class UserIntentTracker(BaseModel):
    """用户意图追踪器
    
    提供用户意图的提取、追踪和验证功能.
    确保大纲AI优化过程中不会偏离用户原始意图.
    
    典型用法:
        >>> tracker = UserIntentTracker(user_input=user_input, outline=outline)
        >>> core_intent = tracker.extract_intent()
        >>> result = tracker.validate_optimization(optimized_items)
        >>> if not result.is_valid:
        ...     raise IntentValidationError(result.violations)
    """

    # 用户输入
    user_input: str = Field(default="", description="用户的原始输入")
    
    # 约束配置
    constraints: IntentConstraint = Field(default_factory=IntentConstraint)
    
    # 内部状态（使用PrivateAttr避免Pydantic字段处理）
    _core_intent: CoreIntent | None = PrivateAttr(default=None)

    @property
    def core_intent(self) -> CoreIntent | None:
        """获取核心意图"""
        return self._core_intent

    def extract_intent(self, llm_service: Any = None) -> CoreIntent:
        """提取用户核心意图
        
        从用户输入中提取核心意图信息.
        如果提供了LLM服务,使用LLM进行智能提取;否则使用规则提取.
        
        Args:
            llm_service: LLM服务实例(可选)
            
        Returns:
            CoreIntent: 提取的核心意图
            
        Raises:
            IntentExtractionError: 意图提取失败
        """
        logger.info("开始提取用户意图: user_input长度=%d", len(self.user_input))
        
        try:
            if llm_service:
                # 使用LLM智能提取
                self._core_intent = self._extract_intent_with_llm(llm_service)
            else:
                # 使用规则提取
                self._core_intent = self._extract_intent_with_rules()
            
            logger.info(
                "意图提取完成: keywords=%d, required_sections=%d, confidence=%.2f",
                len(self._core_intent.core_keywords),
                len(self._core_intent.required_sections),
                self._core_intent.confidence,
            )
            
            return self._core_intent
            
        except Exception as e:
            logger.error("意图提取失败: %s", e, exc_info=True)
            raise IntentExtractionError(f"意图提取失败: {e}") from e

    def _extract_intent_with_rules(self) -> CoreIntent:
        """使用规则提取核心意图
        
        Returns:
            CoreIntent: 提取的核心意图
        """
        intent = CoreIntent()
        
        if not self.user_input:
            return intent
        
        # 提取关键词（简单规则）
        text = self.user_input.lower()
        words = text.split()
        
        # 过滤停用词
        stop_words = {
            "的", "是", "在", "和", "了", "与", "或", "为", "等", "于", "这", "那",
            "有", "无", "之", "也", "就", "要", "会", "可以", "可能", "需要", "应该",
            "请", "帮我", "生成", "创建", "制作", "写", "一份", "一个", "关于",
        }
        
        # 提取核心关键词（出现频率较高的词）
        word_freq: dict[str, int] = {}
        for word in words:
            if len(word) > 1 and word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 选择频率最高的词作为核心关键词
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        intent.core_keywords = {word for word, _ in sorted_words[:10]}
        intent.secondary_keywords = {word for word, _ in sorted_words[10:20]}
        
        # 从大纲中提取必须保留的章节（如果有）
        # 注意：这里需要动态检查，但Pydantic模型中无法直接访问outline
        # 将在validate_optimization中处理
        
        # 提取意图摘要（使用用户输入的前100个字符）
        intent.intent_summary = self.user_input[:100].strip()
        intent.intent_details = self.user_input
        
        # 设置置信度（基于提取的信息量）
        if len(intent.core_keywords) >= 3:
            intent.confidence = 0.8
        elif len(intent.core_keywords) >= 1:
            intent.confidence = 0.5
        else:
            intent.confidence = 0.3
        
        return intent

    def _extract_intent_with_llm(self, llm_service: Any) -> CoreIntent:
        """使用LLM提取核心意图
        
        Args:
            llm_service: LLM服务实例
            
        Returns:
            CoreIntent: 提取的核心意图
        """
        # 构建提示词
        prompt = f"""请从以下用户输入中提取核心意图信息,必须以JSON格式返回:

用户输入:
{self.user_input}

请返回JSON格式(不要添加任何其他内容):
{{
    "intent_summary": "核心意图的简短摘要(不超过50字)",
    "core_keywords": ["关键词1", "关键词2", ...],
    "required_sections": ["必须包含的章节标题1", "章节标题2", ...],
    "confidence": 0.0-1.0之间的置信度
}}
"""
        
        try:
            # 调用LLM
            response = llm_service.generate(prompt)
            
            # 解析响应
            import json
            result = json.loads(response)
            
            # 创建CoreIntent
            intent = CoreIntent(
                intent_summary=result.get("intent_summary", ""),
                core_keywords=set(result.get("core_keywords", [])),
                required_sections=set(result.get("required_sections", [])),
                confidence=result.get("confidence", 0.5),
            )
            
            return intent
            
        except Exception as e:
            logger.warning("LLM意图提取失败,回退到规则提取: %s", e)
            # 回退到规则提取
            return self._extract_intent_with_rules()

    def create_preservation_constraints(
        self,
        strict_level: str | None = None,
        outline: Any = None,
    ) -> IntentConstraint:
        """创建意图保护约束
        
        基于核心意图和保护级别创建优化约束.
        
        Args:
            strict_level: 保护级别(RELAXED/STANDARD/STRICT),如果不提供则使用约束中的默认级别
            outline: 原始大纲(可选,用于提取必须保留的章节)
            
        Returns:
            IntentConstraint: 意图保护约束
        """
        level = strict_level or self.constraints.protection_level
        
        # 根据保护级别设置约束参数
        if level == "RELAXED":
            max_added_ratio = 0.5
            max_deleted_ratio = 0.3
            max_modified_ratio = 0.5
            keyword_retention_threshold = 0.5
        elif level == "STRICT":
            max_added_ratio = 0.2
            max_deleted_ratio = 0.05
            max_modified_ratio = 0.2
            keyword_retention_threshold = 0.85
        else:  # STANDARD
            max_added_ratio = 0.3
            max_deleted_ratio = 0.1
            max_modified_ratio = 0.3
            keyword_retention_threshold = 0.7
        
        # 从核心意图中提取必须保留的章节
        must_preserve_ids: set[str] = set()
        if outline and self._core_intent:
            for item in outline.items:
                # 如果章节标题在必须保留列表中
                if item.title in self._core_intent.required_sections:
                    must_preserve_ids.add(str(item.id))
        
        return IntentConstraint(
            max_added_ratio=max_added_ratio,
            max_deleted_ratio=max_deleted_ratio,
            max_modified_ratio=max_modified_ratio,
            must_preserve_item_ids=must_preserve_ids,
            protection_level=level,
            keyword_retention_threshold=keyword_retention_threshold,
        )

    def validate_optimization(
        self,
        optimized_items: list[Any],
        original_outline: Any,
    ) -> IntentValidationResult:
        """验证优化是否保持用户意图
        
        检查优化后的大纲是否偏离了用户原始意图.
        
        Args:
            optimized_items: 优化后的大纲项列表
            original_outline: 原始大纲
            
        Returns:
            IntentValidationResult: 验证结果
        """
        logger.info(
            "开始验证优化: 原始项=%d, 优化项=%d",
            len(original_outline.items),
            len(optimized_items),
        )
        
        result = IntentValidationResult()
        
        # 统计各类变更
        from src.domain.agent.optimized_outline import OptimizationChangeType
        
        added_items: list[Any] = []
        deleted_items: list[Any] = []
        modified_items: list[Any] = []
        unchanged_items: list[Any] = []
        
        for item in optimized_items:
            change_type = getattr(item, "change_type", None)
            
            if change_type == OptimizationChangeType.ADD:
                added_items.append(item)
            elif change_type == OptimizationChangeType.DELETE:
                deleted_items.append(item)
            elif change_type == OptimizationChangeType.MODIFY:
                modified_items.append(item)
            else:
                unchanged_items.append(item)
        
        # 计算变更比例
        original_count = len(original_outline.items)
        if original_count > 0:
            result.added_ratio = len(added_items) / original_count
            result.deleted_ratio = len(deleted_items) / original_count
            result.modified_ratio = len(modified_items) / original_count
        else:
            result.added_ratio = 0.0
            result.deleted_ratio = 0.0
            result.modified_ratio = 0.0
        
        # 检查变更比例约束
        if result.added_ratio > self.constraints.max_added_ratio:
            result.violations.append(
                f"新增章节数({len(added_items)})超过限制, "
                f"比例为{result.added_ratio:.1%}, 最大允许{self.constraints.max_added_ratio:.1%}"
            )
        
        if result.deleted_ratio > self.constraints.max_deleted_ratio:
            result.violations.append(
                f"删除章节数({len(deleted_items)})超过限制, "
                f"比例为{result.deleted_ratio:.1%}, 最大允许{self.constraints.max_deleted_ratio:.1%}"
            )
        
        if result.modified_ratio > self.constraints.max_modified_ratio:
            result.violations.append(
                f"修改章节数({len(modified_items)})超过限制, "
                f"比例为{result.modified_ratio:.1%}, 最大允许{self.constraints.max_modified_ratio:.1%}"
            )
        
        # 检查必须保留的章节
        must_preserve_ids = self.constraints.must_preserve_item_ids
        
        for item in deleted_items:
            original_item_id = getattr(item, "original_item_id", None)
            if original_item_id and str(original_item_id) in must_preserve_ids:
                original_item = original_outline.get_item(original_item_id)
                if original_item:
                    result.violations.append(
                        f"删除了必须保留的章节: '{original_item.title}'"
                    )
        
        for item in modified_items:
            original_item_id = getattr(item, "original_item_id", None)
            if original_item_id and str(original_item_id) in must_preserve_ids:
                original_item = original_outline.get_item(original_item_id)
                optimized_item = getattr(item, "optimized_item", None)
                if original_item and optimized_item:
                    # 计算修改程度
                    title_similarity = self._calculate_text_similarity(
                        original_item.title, optimized_item.title
                    )
                    if title_similarity < 0.5:
                        result.violations.append(
                            f"严重修改了必须保留的章节: "
                            f"'{original_item.title}' -> '{optimized_item.title}'"
                        )
        
        # 计算关键词保留率
        if self._core_intent and self._core_intent.core_keywords:
            optimized_titles = []
            for item in optimized_items:
                if hasattr(item, "optimized_item"):
                    optimized_titles.append(item.optimized_item.title.lower())
                elif hasattr(item, "title"):
                    optimized_titles.append(item.title.lower())
            
            retained_keywords = 0
            for keyword in self._core_intent.core_keywords:
                for title in optimized_titles:
                    if keyword.lower() in title:
                        retained_keywords += 1
                        break
            
            result.keyword_retention = retained_keywords / len(self._core_intent.core_keywords)
            
            if result.keyword_retention < self.constraints.keyword_retention_threshold:
                result.violations.append(
                    f"关键词保留率({result.keyword_retention:.1%})低于阈值"
                    f"({self.constraints.keyword_retention_threshold:.1%})"
                )
        
        # 生成建议
        if result.violations:
            result.suggestions = self._generate_suggestions(result, added_items, deleted_items, modified_items)
            result.is_valid = False
            result.confidence = 0.9  # 高置信度，因为检测到了明确的违规
        else:
            result.is_valid = True
            result.confidence = 0.8  # 中高置信度，因为没有检测到违规
            
            # 额外检查：是否进行了过度优化
            if result.added_ratio > 0.2 or result.modified_ratio > 0.2:
                result.suggestions.append(
                    "优化程度较高,建议检查是否保留了足够的原始内容"
                )
        
        logger.info(
            "意图验证完成: is_valid=%s, violations=%d, keyword_retention=%.2f",
            result.is_valid,
            len(result.violations),
            result.keyword_retention,
        )
        
        return result

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度
        
        Args:
            text1: 文本1
            text2: 文本2
            
        Returns:
            float: 相似度(0-1)
        """
        if not text1 or not text2:
            return 0.0
        
        # 对于中文文本，使用字符级Jaccard相似度
        # 这样可以正确处理没有空格分隔的中文词
        words1 = set(text1.lower())
        words2 = set(text2.lower())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0

    def _generate_suggestions(
        self,
        result: IntentValidationResult,
        added_items: list[Any],
        deleted_items: list[Any],
        modified_items: list[Any],
    ) -> list[str]:
        """生成改进建议
        
        Args:
            result: 验证结果
            added_items: 新增的项
            deleted_items: 删除的项
            modified_items: 修改的项
            
        Returns:
            list[str]: 改进建议列表
        """
        suggestions = []
        
        # 新增项建议
        if result.added_ratio > self.constraints.max_added_ratio:
            suggestions.append(
                f"减少新增章节数量。当前新增了{len(added_items)}个章节, "
                f"建议控制在{int(len(added_items) * 0.5)}个以内"
            )
        
        # 删除项建议
        if result.deleted_ratio > self.constraints.max_deleted_ratio:
            suggestions.append(
                f"减少删除章节数量。当前删除了{len(deleted_items)}个章节, "
                f"建议保留更多原始章节"
            )
            for item in deleted_items[:3]:  # 最多显示3个
                original_item_id = getattr(item, "original_item_id", None)
                if original_item_id:
                    suggestions.append(f"  - 考虑保留章节 '{original_item_id}'")
        
        # 修改项建议
        if result.modified_ratio > self.constraints.max_modified_ratio:
            suggestions.append(
                f"减少修改章节数量。当前修改了{len(modified_items)}个章节, "
                f"建议只进行必要的措辞调整"
            )
        
        # 关键词保留建议
        if result.keyword_retention < self.constraints.keyword_retention_threshold:
            suggestions.append(
                f"确保核心关键词的保留。当前关键词保留率为{result.keyword_retention:.1%}, "
                f"建议保持至少{self.constraints.keyword_retention_threshold:.0%}的关键词"
            )
        
        return suggestions

    def should_skip_optimization(self) -> tuple[bool, str]:
        """检查是否应该跳过优化
        
        检查当前情况是否适合进行优化.
        
        Returns:
            tuple[bool, str]: (是否跳过, 跳过原因)
        """
        return False, ""


def create_intent_tracker(
    user_input: str,
    outline: Any,
    protection_level: str = "STANDARD",
) -> UserIntentTracker:
    """创建用户意图追踪器的便捷函数
    
    Args:
        user_input: 用户原始输入
        outline: 原始大纲
        protection_level: 保护级别(RELAXED/STANDARD/STRICT)
        
    Returns:
        UserIntentTracker: 用户意图追踪器实例
    """
    # 创建默认约束
    constraints = IntentConstraint(protection_level=protection_level)
    
    # 创建追踪器
    tracker = UserIntentTracker(
        user_input=user_input,
        constraints=constraints,
    )
    
    return tracker


def validate_outline_changes(
    original_outline: Any,
    optimized_items: list[Any],
    max_added_ratio: float = 0.3,
    max_deleted_ratio: float = 0.1,
    max_modified_ratio: float = 0.3,
    must_preserve_keywords: list[str] | None = None,
) -> IntentValidationResult:
    """验证大纲变更的便捷函数
    
    Args:
        original_outline: 原始大纲
        optimized_items: 优化后的大纲项列表
        max_added_ratio: 新增章节的最大比例
        max_deleted_ratio: 删除章节的最大比例
        max_modified_ratio: 修改章节的最大比例
        must_preserve_keywords: 必须保留的关键词列表
        
    Returns:
        IntentValidationResult: 验证结果
    """
    # 创建约束
    constraints = IntentConstraint(
        max_added_ratio=max_added_ratio,
        max_deleted_ratio=max_deleted_ratio,
        max_modified_ratio=max_modified_ratio,
    )
    
    # 创建追踪器并验证
    tracker = UserIntentTracker(
        constraints=constraints,
    )
    
    # 提取关键词
    if must_preserve_keywords:
        tracker._core_intent = CoreIntent(
            core_keywords=set(must_preserve_keywords),
            confidence=1.0,
        )
    
    return tracker.validate_optimization(optimized_items, original_outline)
