"""
引用信息嵌入服务

该模块实现引用信息嵌入功能,在草稿内容中嵌入引用标记,使其可读、可审计、可追溯.
用于T087任务: 实现引用信息嵌入功能.

生成命令: /speckit.implement T087
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import re
import uuid
from enum import Enum

from src.domain.agent.draft import Draft, DraftSection
from src.domain.agent.source_reference import SourceReference
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class CitationFormat(str, Enum):
    """引用格式枚举"""

    BRACKET = "bracket"  # 括号格式 [1], [2]
    FOOTNOTE = "footnote"  # 脚注格式 [^1], [^2]
    INLINE = "inline"  # 内联格式 (作者, 年份)
    NUMBER = "number"  # 数字格式 ¹, ², ³


class CitationEmbedder:
    """
    引用信息嵌入服务

    在草稿内容中嵌入引用标记,使其可读、可审计、可追溯.
    支持多种引用格式,用于对外演示"引用链路".
    """

    def __init__(self, citation_format: CitationFormat = CitationFormat.BRACKET) -> None:
        """
        初始化引用嵌入服务

        Args:
            citation_format: 引用格式(默认括号格式)
        """
        self.citation_format = citation_format

    def embed_citations_in_draft(
        self,
        draft: Draft,
        source_references: dict[uuid.UUID, SourceReference],
    ) -> Draft:
        """
        在草稿中嵌入引用信息（全局去重版）

        为每个章节的内容添加引用标记，并在草稿末尾生成唯一的参考文献列表。
        同一文档在多个章节被引用时，参考文献列表中只显示一次。

        Args:
            draft: 草稿对象
            source_references: 信息源引用字典(ID -> SourceReference)

        Returns:
            嵌入引用信息后的草稿对象
        """
        logger.info(
            "开始嵌入引用信息: 草稿ID=%s, 原始引用数=%d",
            draft.id,
            len(source_references),
        )

        if not source_references:
            logger.info("无引用信息需要嵌入")
            return draft

        # 1. 收集所有唯一的引用（基于 file_path 去重）
        unique_refs: dict[str, tuple[uuid.UUID, SourceReference]] = {}
        for ref_id, ref in source_references.items():
            # 构建唯一键：优先使用 file_path，其次使用 title
            if ref.is_local_document() and ref.local_reference:
                key = ref.local_reference.file_path or ref.title or str(ref_id)
            else:
                key = str(ref_id)

            # 只保留第一个出现的引用（按章节顺序）
            if key not in unique_refs:
                unique_refs[key] = (ref_id, ref)

        logger.info("去重后的唯一引用数: %d", len(unique_refs))

        # 2. 构建全局编号映射 (UUID -> global_number)
        # 使用 ref_id（去重后保留的第一个引用的 UUID）作为键，而非 SourceReference 对象
        global_number_map: dict[uuid.UUID, int] = {}
        for i, (key, (ref_id, ref)) in enumerate(unique_refs.items()):
            global_number_map[ref_id] = i + 1

        # 3. 为每个章节嵌入引用标记（使用全局编号）
        for section in draft.sections:
            if section.has_source_references():
                # 获取该章节的引用
                ref_ids = section.source_references
                references = [
                    source_references.get(ref_id)
                    for ref_id in ref_ids
                    if ref_id in source_references
                ]
                references = [ref for ref in references if ref is not None]

                if references:
                    # 使用全局编号嵌入引用
                    embedded_content = self._embed_with_global_numbers(
                        section.content, references, global_number_map
                    )
                    section.update_content(embedded_content)

                    logger.debug(
                        "章节 '%s' 已嵌入引用标记",
                        section.title or "无标题",
                    )

        # 4. 在草稿末尾添加唯一的参考文献列表
        # 找到最后一个有内容的章节，在其末尾添加参考文献
        last_section_with_content = None
        for section in reversed(draft.sections):
            if section.content and section.content.strip():
                last_section_with_content = section
                break

        if last_section_with_content and unique_refs:
            # 生成去重后的参考文献列表
            ref_list = []
            for i, (key, (ref_id, ref)) in enumerate(unique_refs.items()):
                ref_item = self._format_reference_for_list(ref, i + 1)
                ref_list.append(ref_item)

            ref_list_html = "\n\n**参考文献:**\n" + "\n".join(ref_list)

            # 追加到最后一个章节的内容末尾
            updated_content = last_section_with_content.content + ref_list_html
            last_section_with_content.update_content(updated_content)
            logger.info("已在草稿末尾添加去重后的参考文献列表")

        # 5. 将引用信息存储到草稿元数据中,供后续追溯使用
        # 存储去重后的引用信息
        deduplicated_refs = {ref_id: ref.to_dict() for key, (ref_id, ref) in unique_refs.items()}
        draft.add_metadata("source_references", deduplicated_refs)
        # 保留原始引用数的元数据
        draft.add_metadata("original_reference_count", len(source_references))

        logger.info("引用信息嵌入完成: 草稿ID=%s, 最终引用数=%d", draft.id, len(unique_refs))

        return draft

    def _embed_with_global_numbers(
        self,
        content: str,
        references: list[SourceReference],
        global_number_map: dict[uuid.UUID, int],
    ) -> str:
        """
        使用全局编号嵌入引用标记

        Args:
            content: 原始内容
            references: 引用列表
            global_number_map: 全局编号映射

        Returns:
            嵌入引用标记后的内容
        """
        if not references:
            return content

        # 根据引用格式生成标记
        if self.citation_format == CitationFormat.BRACKET:
            return self._embed_bracket_with_global_numbers(content, references, global_number_map)
        elif self.citation_format == CitationFormat.FOOTNOTE:
            return self._embed_footnote_with_global_numbers(content, references, global_number_map)
        elif self.citation_format == CitationFormat.INLINE:
            return self._embed_inline_with_global_numbers(content, references, global_number_map)
        elif self.citation_format == CitationFormat.NUMBER:
            return self._embed_number_with_global_numbers(content, references, global_number_map)
        else:
            return self._embed_bracket_with_global_numbers(content, references, global_number_map)

    def _embed_bracket_with_global_numbers(
        self,
        content: str,
        references: list[SourceReference],
        global_number_map: dict[uuid.UUID, int],
    ) -> str:
        """
        使用全局编号嵌入括号格式的引用标记 [1], [2]

        Args:
            content: 原始内容
            references: 引用列表
            global_number_map: 全局编号映射

        Returns:
            嵌入引用标记后的内容
        """
        # 检测是否已有内联引用格式 [来源:文件名]
        inline_source_pattern = r'\[来源:[^\]]+\]'
        has_inline_citations = bool(re.search(inline_source_pattern, content))

        if has_inline_citations:
            # 如果已有内联引用，不添加任何内容（参考文献列表已在草稿级别统一添加）
            return content

        # 获取全局编号（使用 ref.id 查询）
        ref_numbers = [str(global_number_map.get(ref.id, i + 1)) for i, ref in enumerate(references)]

        # 在内容末尾添加引用标记
        citation_marker = f"[{', '.join(ref_numbers)}]"

        return f"{content} {citation_marker}"

    def _embed_footnote_with_global_numbers(
        self,
        content: str,
        references: list[SourceReference],
        global_number_map: dict[uuid.UUID, int],
    ) -> str:
        """
        使用全局编号嵌入脚注格式的引用标记 [^1], [^2]

        Args:
            content: 原始内容
            references: 引用列表
            global_number_map: 全局编号映射

        Returns:
            嵌入引用标记后的内容
        """
        result = content
        for ref in references:
            footnote_marker = f"[^{global_number_map.get(ref.id, 1)}]"
            result += f" {footnote_marker}"

        return result

    def _embed_inline_with_global_numbers(
        self,
        content: str,
        references: list[SourceReference],
        global_number_map: dict[uuid.UUID, int],
    ) -> str:
        """
        使用全局编号嵌入内联格式的引用 (标题, 位置)

        Args:
            content: 原始内容
            references: 引用列表
            global_number_map: 全局编号映射

        Returns:
            嵌入引用标记后的内容
        """
        inline_refs = []
        for ref in references:
            # 使用全局编号格式化（使用 ref.id 查询）
            number = global_number_map.get(ref.id, 1)
            inline_ref = self._format_reference_for_inline(ref).replace(
                str(number), str(number)
            )
            inline_refs.append(inline_ref)

        if inline_refs:
            result = f"{content} ({', '.join(inline_refs)})"
        else:
            result = content

        return result

    def _embed_number_with_global_numbers(
        self,
        content: str,
        references: list[SourceReference],
        global_number_map: dict[uuid.UUID, int],
    ) -> str:
        """
        使用全局编号嵌入数字格式的引用 ¹, ², ³

        Args:
            content: 原始内容
            references: 引用列表
            global_number_map: 全局编号映射

        Returns:
            嵌入引用标记后的内容
        """
        result = content
        superscript_map = {0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹"}

        for ref in references:
            # 使用 ref.id 查询全局编号
            number = global_number_map.get(ref.id, 1)
            # 转换为上标
            if number < 10:
                superscript = superscript_map.get(number, f"[{number}]")
            else:
                superscript = f"[{number}]"
            result += superscript

        return result

    def _embed_citations_in_content(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """
        在内容中嵌入引用标记

        Args:
            content: 原始内容
            references: 引用列表

        Returns:
            嵌入引用标记后的内容
        """
        if not references:
            return content

        # 根据引用格式生成标记
        if self.citation_format == CitationFormat.BRACKET:
            return self._embed_bracket_citations(content, references)
        elif self.citation_format == CitationFormat.FOOTNOTE:
            return self._embed_footnote_citations(content, references)
        elif self.citation_format == CitationFormat.INLINE:
            return self._embed_inline_citations(content, references)
        elif self.citation_format == CitationFormat.NUMBER:
            return self._embed_number_citations(content, references)
        else:
            # 默认使用括号格式
            return self._embed_bracket_citations(content, references)

    def _embed_bracket_citations(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """
        嵌入括号格式的引用标记 [1], [2], [3]

        Args:
            content: 原始内容
            references: 引用列表

        Returns:
            嵌入引用标记后的内容
        """
        # 检测是否已有内联引用格式 [来源:文件名]
        inline_source_pattern = r'\[来源:[^\]]+\]'
        has_inline_citations = bool(re.search(inline_source_pattern, content))
        
        if has_inline_citations:
            # 如果已有内联引用，只添加参考文献列表，不重复添加
            ref_list = []
            for i, ref in enumerate(references, start=1):
                ref_item = self._format_reference_for_list(ref, i)
                ref_list.append(ref_item)
            
            if ref_list:
                result = f"{content}\n\n**参考文献:**\n" + "\n".join(ref_list)
            else:
                result = content
            return result

        # 原有的逻辑：没有内联引用时，在末尾添加
        # 生成引用编号列表
        ref_numbers = [str(i + 1) for i in range(len(references))]

        # 在内容末尾添加引用标记
        citation_marker = f"[{', '.join(ref_numbers)}]"
        result = f"{content} {citation_marker}"

        # 添加参考文献列表
        ref_list = []
        for i, ref in enumerate(references, start=1):
            ref_item = self._format_reference_for_list(ref, i)
            ref_list.append(ref_item)

        if ref_list:
            result += "\n\n**参考文献:**\n" + "\n".join(ref_list)

        return result

    def _embed_footnote_citations(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """
        嵌入脚注格式的引用标记 [^1], [^2], [^3]

        Args:
            content: 原始内容
            references: 引用列表

        Returns:
            嵌入引用标记后的内容
        """
        result = content
        footnotes = []

        for i, ref in enumerate(references, start=1):
            # 在内容末尾添加脚注标记
            footnote_marker = f"[^{i}]"
            result += f" {footnote_marker}"

            # 生成脚注内容
            footnote_content = self._format_reference_for_footnote(ref, i)
            footnotes.append(footnote_content)

        # 添加脚注部分
        if footnotes:
            result += "\n\n" + "\n".join(footnotes)

        return result

    def _embed_inline_citations(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """
        嵌入内联格式的引用标记 (标题, 位置)

        Args:
            content: 原始内容
            references: 引用列表

        Returns:
            嵌入引用标记后的内容
        """
        inline_refs = []

        for ref in references:
            inline_ref = self._format_reference_for_inline(ref)
            inline_refs.append(inline_ref)

        # 在内容末尾添加内联引用
        if inline_refs:
            result = f"{content} ({', '.join(inline_refs)})"
        else:
            result = content

        return result

    def _embed_number_citations(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """
        嵌入数字格式的引用标记 ¹, ², ³

        Args:
            content: 原始内容
            references: 引用列表

        Returns:
            嵌入引用标记后的内容
        """
        # 生成上标数字标记
        superscript_map = {
            1: "¹",
            2: "²",
            3: "³",
            4: "⁴",
            5: "⁵",
            6: "⁶",
            7: "⁷",
            8: "⁸",
            9: "⁹",
            10: "¹⁰",
        }

        result = content
        superscripts = []

        for i, ref in enumerate(references, start=1):
            if i <= 10:
                superscript = superscript_map.get(i, f"[{i}]")
            else:
                superscript = f"[{i}]"
            superscripts.append(superscript)
            result += superscript

        # 添加参考文献列表
        ref_list = []
        for i, ref in enumerate(references, start=1):
            superscript = superscript_map.get(i, f"[{i}]") if i <= 10 else f"[{i}]"
            ref_item = f"{superscript} {self._format_reference_for_list(ref, i)}"
            ref_list.append(ref_item)

        if ref_list:
            result += "\n\n**参考文献:**\n" + "\n".join(ref_list)

        return result

    def _format_reference_for_list(
        self, reference: SourceReference, number: int
    ) -> str:
        """
        格式化引用为列表格式

        Args:
            reference: 信息源引用
            number: 引用编号

        Returns:
            格式化后的引用字符串
        """
        # 用户交付偏好：参考文献列表保持“干净可读”。
        # - 本地文档：仅展示标题（保留序号），不展示(未知位置)与本地路径（clean.md/pdf 等）。
        # - 网络文章：保留占位提示（第三步启用）。
        if reference.is_local_document():
            title = (reference.title or "").strip() or "未知文档"
            return f"{number}. {title}"
        else:
            return f"{number}. {reference.title} (网络文章 - 待第三步完成后启用)"

    def _format_reference_for_footnote(
        self, reference: SourceReference, number: int
    ) -> str:
        """
        格式化引用为脚注格式

        Args:
            reference: 信息源引用
            number: 引用编号

        Returns:
            格式化后的脚注字符串
        """
        if reference.is_local_document():
            title = (reference.title or "").strip() or "未知文档"
            return f"[^{number}]: {title}"
        else:
            return (
                f"[^{number}]: {reference.title} "
                "(网络文章 - 待第三步完成后启用)"
            )

    def _format_reference_for_inline(self, reference: SourceReference) -> str:
        """
        格式化引用为内联格式

        Args:
            reference: 信息源引用

        Returns:
            格式化后的内联引用字符串
        """
        if reference.is_local_document() and reference.local_reference:
            local_ref = reference.local_reference
            location = local_ref.get_location_string()
            return f"{reference.title} ({location})"
        else:
            return f"{reference.title} (网络文章 - 待第三步完成后启用)"

    def get_citation_trace_info(
        self,
        draft: Draft,
        source_references: dict[uuid.UUID, SourceReference] | None = None,
    ) -> dict[str, any]:
        """
        获取引用追溯信息

        用于对外演示"引用链路",提供可审计、可追溯的引用信息.

        Args:
            draft: 草稿对象
            source_references: 信息源引用字典(如果为None,则从草稿元数据中获取)

        Returns:
            引用追溯信息字典,包含:
            - total_citations: 总引用数
            - citations_by_section: 按章节分组的引用
            - citation_details: 详细的引用信息
        """
        # 从草稿元数据中获取引用信息(如果未提供)
        if source_references is None:
            refs_data = draft.get_metadata("source_references", {})
            source_references = {}
            for ref_id_str, ref_data in refs_data.items():
                try:
                    ref_id = uuid.UUID(ref_id_str)
                    # 从字典重建SourceReference对象
                    from src.domain.agent.source_reference import (
                        LocalDocumentReference,
                        SourceReference,
                        SourceReferenceType,
                    )

                    if ref_data.get("reference_type") == "LOCAL_DOCUMENT":
                        local_ref_data = ref_data.get("local_reference", {})
                        local_ref = LocalDocumentReference(**local_ref_data)
                        source_references[ref_id] = SourceReference(
                            id=ref_id,
                            reference_type=SourceReferenceType.LOCAL_DOCUMENT,
                            title=ref_data.get("title", ""),
                            description=ref_data.get("description"),
                            local_reference=local_ref,
                            web_reference=None,
                        )
                except Exception as e:
                    logger.warning("无法解析引用信息: %s, 错误: %s", ref_id_str, e)

        # 统计引用信息
        total_citations = len(source_references)
        citations_by_section: dict[str, list[dict[str, any]]] = {}
        citation_details: dict[str, dict[str, any]] = {}

        for section in draft.sections:
            if section.has_source_references():
                section_citations = []
                for ref_id in section.source_references:
                    if ref_id in source_references:
                        ref = source_references[ref_id]
                        citation_info = {
                            "id": str(ref_id),
                            "title": ref.title,
                            "description": ref.description,
                            "location": ref.get_location_info(),
                            "link": ref.get_display_link(),
                            "traceable": ref.is_traceable(),
                            "can_jump": ref.can_jump_to_source(),
                        }
                        section_citations.append(citation_info)
                        citation_details[str(ref_id)] = citation_info

                if section_citations:
                    section_key = section.title or f"Section-{section.id}"
                    citations_by_section[section_key] = section_citations

        return {
            "total_citations": total_citations,
            "citations_by_section": citations_by_section,
            "citation_details": citation_details,
        }

