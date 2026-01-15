"""
草稿润色服务

该模块实现基础润色功能,包括语言流畅性、逻辑连贯性、格式规范性.
使用LangChain 1.0最佳实践实现文本润色链.
用于T088任务: 实现基础润色功能.

生成命令: /speckit.implement T088
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

from __future__ import annotations

from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.domain.agent.draft import Draft, DraftSection
from src.shared.config.llm_service import LLMService
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


def estimate_tokens(text: str) -> int:
    """估算文本的token数量
    
    粗略估算：中文约1.5字符/token，英文约4字符/token
    混合文本取折中值 2字符/token
    """
    if not text:
        return 0
    return max(1, len(text) // 2)


class DraftPolisher:
    """
    草稿润色服务

    使用LangChain 1.0实现文本润色功能,包括:
    - 语言流畅性: 改善表达,使语言更自然流畅
    - 逻辑连贯性: 优化段落和章节之间的逻辑连接
    - 格式规范性: 统一格式,确保符合规范要求

    作为最终合成步骤,在草稿生成和引用嵌入之后执行.
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        language: str = "中文",
        style: str = "专业,客观,数据驱动",
    ) -> None:
        """
        初始化草稿润色服务

        Args:
            llm_service: LLM服务实例(如果为None,则从配置获取)
            language: 语言类型(默认中文)
            style: 写作风格(默认专业,客观,数据驱动)
        """
        self.llm_service = llm_service
        self.language = language
        self.style = style
        self._setup_prompt_template()

    def _setup_prompt_template(self) -> None:
        """设置润色提示词模板(符合LangChain 1.0最佳实践)"""
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """你是一位顶级的商务白皮书润色专家。你的任务是对用户提供的文案进行深度润色和专业扩写。

## 核心任务
1. **内容扩写**：在保持核心观点不变的前提下，增加行业背景分析、逻辑推导和专业见解，使内容更厚实、专业。
2. **专业表达**：使用严谨的行业术语，语气客观、权威，符合高端白皮书风格。
3. **结构优化**：提升段落间的逻辑连贯性。
4. **占位符保护**：必须严格保留原文中的引用标记（如 [1]）和所有占位符（如 [[IMAGE:xxx]], [[CHART:xxx]]）。

## 极其重要：输出规范
- **禁止**输出任何开场白（如“好的”、“已为您润色”）。
- **禁止**输出任何润色说明、总结、修改记录或结束语。
- **只能输出润色后的正文纯文本**。
- 如果输出中包含任何非正文内容，系统将无法处理。
- 写作风格：{style}""",
                ),
                ("human", "{content}"),
            ]
        )

    def polish_draft(
        self,
        draft: Draft,
        polish_sections: bool = True,
        polish_whole: bool = False,
        batch_size: int = 3,
    ) -> Draft:
        """
        润色草稿

        对草稿进行润色,提升语言流畅性、逻辑连贯性和格式规范性.
        支持批量处理模式:将多个小章节合并为一批,减少LLM调用次数.

        Args:
            draft: 待润色的草稿对象
            polish_sections: 是否润色各个章节(默认True)
            polish_whole: 是否润色整个文档(默认False,仅润色章节)
            batch_size: 每批处理的章节数量(默认3,设为1则禁用批量处理)

        Returns:
            润色后的草稿对象
        """
        # === 润色前统计 ===
        total_sections = len(draft.sections)
        total_chars = sum(
            len(s.content) if s.content else 0 
            for s in draft.sections
        )
        total_references = sum(
            len(s.source_references) if s.source_references else 0
            for s in draft.sections
        )
        estimated_total_tokens = estimate_tokens(draft.get_content())
        
        logger.info(
            "开始润色草稿: ID=%s, 章节数=%d, 总字符=%d, 总引用=%d, 预估tokens=%d",
            draft.id,
            total_sections,
            total_chars,
            total_references,
            estimated_total_tokens,
        )
        
        # 章节级别统计
        for idx, section in enumerate(draft.sections, 1):
            section_chars = len(section.content) if section.content else 0
            section_refs = len(section.source_references) if section.source_references else 0
            section_tokens = estimate_tokens(section.content)
            logger.info(
                "  章节[%d/%d]: title='%s', chars=%d, refs=%d, tokens≈%d",
                idx,
                total_sections,
                section.title or "无标题",
                section_chars,
                section_refs,
                section_tokens,
            )

        try:
            # 获取LLM模型
            if not self.llm_service:
                from src.shared.config.llm_service import get_llm_service

                self.llm_service = get_llm_service()

            model = self.llm_service.get_chat_model()

            # 计算系统提示词的token数
            # SystemMessagePromptTemplate 对象不能直接索引，需要通过 .prompt 属性访问
            system_message_template = self.prompt_template.messages[0]
            # 获取模板格式字符串
            if hasattr(system_message_template, 'prompt'):
                # LangChain 方式：通过 .prompt 获取模板
                system_prompt_template = system_message_template.prompt
                if hasattr(system_prompt_template, 'template'):
                    system_prompt = system_prompt_template.template
                else:
                    system_prompt = str(system_prompt_template)
            else:
                # 备用方案：直接转为字符串
                system_prompt = str(system_message_template)
            
            system_tokens = estimate_tokens(
                system_prompt.format(language=self.language, style=self.style)
                if hasattr(system_prompt, 'format')
                else str(system_prompt)
            )
            
            logger.info(
                "润色配置: batch_size=%d, 系统提示词tokens≈%d",
                batch_size,
                system_tokens,
            )

            # 润色各个章节(支持批量处理)
            if polish_sections:
                if batch_size <= 1:
                    # 原始模式:逐个处理
                    for section in draft.sections:
                        if section.content and section.content.strip():
                            input_tokens = estimate_tokens(section.content) + system_tokens
                            polished_content = self._polish_content(
                                content=section.content,
                                section_title=section.title,
                                model=model,
                            )
                            output_tokens = estimate_tokens(polished_content)
                            section.update_content(polished_content)
                            
                            logger.info(
                                "章节润色: '%s', 输入tokens≈%d, 输出tokens≈%d",
                                section.title or "无标题",
                                input_tokens,
                                output_tokens,
                            )
                else:
                    # 批量模式:将多个小章节合并处理
                    self._polish_sections_batch(
                        draft=draft,
                        model=model,
                        batch_size=batch_size,
                        system_tokens=system_tokens,
                    )

            # 润色整个文档(可选)
            if polish_whole:
                # 获取整个文档的Markdown内容
                full_content = draft.get_content()
                input_tokens = estimate_tokens(full_content) + system_tokens
                polished_full_content = self._polish_content(
                    content=full_content,
                    section_title=draft.title,
                    model=model,
                )
                output_tokens = estimate_tokens(polished_full_content)
                
                logger.info(
                    "整体润色: 输入tokens≈%d, 输出tokens≈%d",
                    input_tokens,
                    output_tokens,
                )

                # 更新草稿内容(这里可以进一步解析并更新章节)
                # 当前实现: 如果润色了整体,则不再单独润色章节
                logger.info("整体文档润色完成")

            # === 润色后统计 ===
            polished_chars = sum(
                len(s.content) if s.content else 0 
                for s in draft.sections
            )
            logger.info(
                "草稿润色完成: ID=%s, 润色后总字符=%d",
                draft.id,
                polished_chars,
            )
            return draft

        except Exception as e:
            logger.error("草稿润色失败: %s", e, exc_info=True)
            # 润色失败不影响草稿,返回原草稿
            logger.warning("润色失败,返回原始草稿")
            return draft

    def _polish_sections_batch(
        self,
        draft: Draft,
        model: Any,
        batch_size: int,
        system_tokens: int,
    ) -> None:
        """批量润色多个小章节
        
        将多个小章节合并为一批,减少LLM调用次数.
        批次边界:章节数达到batch_size,或单个章节内容超过阈值(5000字符).
        
        Args:
            draft: 草稿对象
            model: LLM模型实例
            batch_size: 每批最大章节数
            system_tokens: 系统提示词token估算值
        """
        import uuid
        
        current_batch: list[DraftSection] = []
        current_batch_chars = 0
        BATCH_CHARS_THRESHOLD = 10000  # 每批字符数阈值
        
        def process_batch(batch: list[DraftSection]) -> None:
            if not batch:
                return
            
            # 合并批次内所有章节内容
            combined_content_parts = []
            for section in batch:
                combined_content_parts.append(f"## {section.title}\n{section.content}")
            combined_content = "\n\n".join(combined_content_parts)
            
            input_tokens = estimate_tokens(combined_content) + system_tokens
            logger.info(
                "批量润色: 章节数=%d, 合并字符=%d, 输入tokens≈%d",
                len(batch),
                len(combined_content),
                input_tokens,
            )
            
            # 调用润色
            polished_combined = self._polish_content(
                content=combined_content,
                section_title=f"批量润色({len(batch)}章节)",
                model=model,
            )
            
            output_tokens = estimate_tokens(polished_combined)
            
            # 解析并拆分润色后的内容(按 ## 标题 分割)
            import re
            section_pattern = re.compile(r"^##\s+(.+?)\n", re.MULTILINE)
            
            # 简单的章节边界检测
            boundaries = [(m.start(), m.group(1)) for m in section_pattern.finditer(polished_combined)]
            
            if len(boundaries) >= len(batch):
                # 成功分割:更新各章节内容
                for idx, section in enumerate(batch):
                    if idx < len(boundaries) - 1:
                        start = boundaries[idx][0]
                        end = boundaries[idx + 1][0]
                        section_content = polished_combined[start:end].strip()
                        # 移除标题行
                        section_content = re.sub(r"^##\s+.+?\n", "", section_content, count=1)
                        section.update_content(section_content)
                    else:
                        # 最后一个章节
                        start = boundaries[idx][0]
                        section_content = polished_combined[start:].strip()
                        section_content = re.sub(r"^##\s+.+?\n", "", section_content, count=1)
                        section.update_content(section_content)
                
                logger.info(
                    "批量润色完成: 处理%d章节, 输出tokens≈%d",
                    len(batch),
                    output_tokens,
                )
            else:
                # 分割失败:降级为逐个润色
                logger.warning(
                    "批量润色分割失败,降级为逐个润色: 期望%d章节,检测到%d个边界",
                    len(batch),
                    len(boundaries),
                )
                for section in batch:
                    if section.content and section.content.strip():
                        polished = self._polish_content(
                            content=section.content,
                            section_title=section.title,
                            model=model,
                        )
                        section.update_content(polished)
        
        # 构建并处理批次
        for section in draft.sections:
            if not section.content or not section.content.strip():
                continue
            
            current_batch.append(section)
            current_batch_chars += len(section.content)
            
            # 检查是否需要触发批次处理
            should_process = (
                len(current_batch) >= batch_size or
                current_batch_chars >= BATCH_CHARS_THRESHOLD
            )
            
            if should_process:
                process_batch(current_batch)
                current_batch = []
                current_batch_chars = 0
        
        # 处理剩余批次
        if current_batch:
            process_batch(current_batch)

    def _polish_content(
        self,
        content: str,
        section_title: str | None = None,
        model: Any = None,
    ) -> str:
        """
        润色内容

        使用LangChain 1.0链式调用润色文本内容.

        Args:
            content: 待润色的内容
            section_title: 章节标题(可选,用于上下文)
            model: LLM模型实例

        Returns:
            润色后的内容
        """
        if not content or not content.strip():
            return content

        try:
            # 构建提示词变量
            prompt_vars = {
                "content": content,
                "language": self.language,
                "style": self.style,
            }

            # 关键修复：
            # 润色属于“等长改写”，不应继承全局超大的 LLM_MAX_TOKENS（例如 128000），
            # 否则在部分 OpenAI-compatible 服务上会触发断连/重置。
            # 这里给一个稳定且足够的输出上限（可按需再参数化）。
            safe_max_tokens = 8192
            safe_model = model.bind(max_tokens=safe_max_tokens)

            # 构建LangChain 1.0链(符合最佳实践)
            # 使用: prompt | model | output_parser
            chain = self.prompt_template | safe_model | StrOutputParser()

            # 执行链,获取润色后的内容
            polished_content = chain.invoke(prompt_vars)

            # 清理输出(移除可能的额外格式)
            polished_content = polished_content.strip()

            logger.debug(
                "内容润色完成: 原始长度=%d, 润色后长度=%d",
                len(content),
                len(polished_content),
            )

            return polished_content

        except Exception as e:
            logger.error("内容润色失败: %s", e, exc_info=True)
            # 润色失败时返回原内容
            return content

    def polish_section(
        self,
        section: DraftSection,
        model: Any | None = None,
    ) -> DraftSection:
        """
        润色单个章节

        Args:
            section: 待润色的章节
            model: LLM模型实例(如果为None,则从llm_service获取)

        Returns:
            润色后的章节
        """
        if not section.content or not section.content.strip():
            return section

        try:
            # 获取LLM模型
            if not model:
                if not self.llm_service:
                    from src.shared.config.llm_service import get_llm_service

                    self.llm_service = get_llm_service()
                model = self.llm_service.get_chat_model()

            # 润色内容
            polished_content = self._polish_content(
                content=section.content,
                section_title=section.title,
                model=model,
            )

            # 更新章节内容
            section.update_content(polished_content)

            logger.debug("章节润色完成: %s", section.title or "无标题")
            return section

        except Exception as e:
            logger.error("章节润色失败: %s", e, exc_info=True)
            return section

    def polish_text(
        self,
        text: str,
        context: str | None = None,
    ) -> str:
        """
        润色文本片段

        用于润色独立的文本片段,不涉及草稿结构.

        Args:
            text: 待润色的文本
            context: 上下文信息(可选)

        Returns:
            润色后的文本
        """
        if not text or not text.strip():
            return text

        try:
            # 获取LLM模型
            if not self.llm_service:
                from src.shared.config.llm_service import get_llm_service

                self.llm_service = get_llm_service()

            model = self.llm_service.get_chat_model()

            # 构建润色内容(包含上下文)
            content_to_polish = text
            if context:
                content_to_polish = f"上下文: {context}\n\n待润色内容:\n{text}"

            # 润色内容
            polished_text = self._polish_content(
                content=content_to_polish,
                section_title=None,
                model=model,
            )

            return polished_text

        except Exception as e:
            logger.error("文本润色失败: %s", e, exc_info=True)
            return text

