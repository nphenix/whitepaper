"""
草稿素材追溯显示服务

该模块实现草稿中素材追溯显示功能,在草稿中标记引用的素材来源.
支持Markdown/HTML格式渲染,用于MVP 3步流程中的第四步: 草稿生成(带素材追溯链接).

当前版本仅支持本地文章,网络文章功能待第三步完成后启用.
"""

# 生成命令: /speckit.implement T237
# 生成时间: 2025-12-25
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from enum import Enum

from src.application.services.local_document_link_service import (
    LocalDocumentLinkService,
)
from src.domain.agent.draft import Draft, DraftSection
from src.domain.agent.source_reference import SourceReference
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class ReferenceFormat(str, Enum):
    """引用格式枚举"""

    FOOTNOTE = "footnote"  # 脚注格式
    INLINE = "inline"  # 内联格式
    BRACKET = "bracket"  # 括号格式
    ENDNOTE = "endnote"  # 尾注格式


class RenderFormat(str, Enum):
    """渲染格式枚举"""

    MARKDOWN = "markdown"  # Markdown格式
    HTML = "html"  # HTML格式
    PLAIN = "plain"  # 纯文本格式


class DraftSourceTraceService:
    """
    草稿素材追溯显示服务

    提供在草稿中标记引用的素材来源的功能,支持Markdown/HTML格式渲染.
    当前版本仅支持本地文章,网络文章功能待第三步完成后启用.
    """

    def __init__(
        self,
        link_service: LocalDocumentLinkService | None = None,
        reference_format: ReferenceFormat = ReferenceFormat.FOOTNOTE,
    ) -> None:
        """
        初始化草稿素材追溯显示服务

        Args:
            link_service: 本地文章链接服务(可选)
            reference_format: 引用格式(默认脚注格式)
        """
        self.link_service = link_service or LocalDocumentLinkService()
        self.reference_format = reference_format

    def render_section_with_references(
        self,
        section: DraftSection,
        source_references: dict[uuid.UUID, SourceReference],
        render_format: RenderFormat = RenderFormat.MARKDOWN,
    ) -> str:
        """
        渲染带引用标记的章节内容

        Args:
            section: 草稿章节
            source_references: 信息源引用字典(ID -> SourceReference)
            render_format: 渲染格式

        Returns:
            渲染后的章节内容(包含引用标记)
        """
        if not section.has_source_references():
            # 如果没有引用,直接返回原内容
            return section.content

        # 获取章节的所有引用
        ref_ids = section.source_references
        references = [
            source_references.get(ref_id)
            for ref_id in ref_ids
            if ref_id in source_references
        ]
        # 过滤掉None值
        references = [ref for ref in references if ref is not None]

        if not references:
            return section.content

        # 根据渲染格式生成引用标记
        if render_format == RenderFormat.MARKDOWN:
            return self._render_markdown(section.content, references)
        elif render_format == RenderFormat.HTML:
            return self._render_html(section.content, references)
        else:
            return self._render_plain(section.content, references)

    def _render_markdown(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """
        渲染Markdown格式的引用标记

        Args:
            content: 原始内容
            references: 引用列表

        Returns:
            Markdown格式的内容(包含引用标记)
        """
        if self.reference_format == ReferenceFormat.FOOTNOTE:
            return self._render_markdown_footnote(content, references)
        elif self.reference_format == ReferenceFormat.INLINE:
            return self._render_markdown_inline(content, references)
        elif self.reference_format == ReferenceFormat.BRACKET:
            return self._render_markdown_bracket(content, references)
        else:
            return self._render_markdown_footnote(content, references)

    def _render_markdown_footnote(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """渲染Markdown脚注格式"""
        result = content
        footnotes = []

        for i, ref in enumerate(references, start=1):
            # 在内容末尾添加脚注标记
            footnote_marker = f"[^{i}]"
            result += f" {footnote_marker}"

            # 生成脚注内容
            footnote_content = self._format_reference_markdown(ref, i)
            footnotes.append(footnote_content)

        # 添加脚注部分
        if footnotes:
            result += "\n\n" + "\n".join(footnotes)

        return result

    def _render_markdown_inline(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """渲染Markdown内联格式"""
        result = content
        inline_refs = []

        for ref in references:
            inline_ref = self._format_reference_markdown_inline(ref)
            inline_refs.append(inline_ref)

        # 在内容末尾添加内联引用
        if inline_refs:
            result += " (" + ", ".join(inline_refs) + ")"

        return result

    def _render_markdown_bracket(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """渲染Markdown括号格式"""
        result = content
        ref_numbers = []

        for i, _ref in enumerate(references, start=1):
            ref_numbers.append(str(i))

        # 在内容末尾添加引用编号
        if ref_numbers:
            result += f" [{', '.join(ref_numbers)}]"

        # 添加引用列表
        ref_list = []
        for i, ref in enumerate(references, start=1):
            ref_item = self._format_reference_markdown_list(ref, i)
            ref_list.append(ref_item)

        if ref_list:
            result += "\n\n**参考文献:**\n" + "\n".join(ref_list)

        return result

    def _format_reference_markdown(
        self, reference: SourceReference, number: int
    ) -> str:
        """
        格式化单个引用的Markdown脚注

        Args:
            reference: 信息源引用
            number: 引用编号

        Returns:
            Markdown格式的脚注字符串
        """
        if reference.is_local_document() and reference.local_reference:
            local_ref = reference.local_reference
            self.link_service.create_link_from_local_reference(
                local_ref, scheme="file"
            )
            location = local_ref.get_location_string()

            # 生成脚注格式: [^1]: 标题 (位置) - 文件路径
            return (
                f"[^{number}]: {reference.title}"
                f" ({location}) - {local_ref.get_display_path()}"
            )
        else:
            # 网络文章引用(当前版本不支持)
            return f"[^{number}]: {reference.title} (网络文章 - 待第三步完成后启用)"

    def _format_reference_markdown_inline(
        self, reference: SourceReference
    ) -> str:
        """
        格式化单个引用的Markdown内联格式

        Args:
            reference: 信息源引用

        Returns:
            Markdown格式的内联引用字符串
        """
        if reference.is_local_document() and reference.local_reference:
            local_ref = reference.local_reference
            location = local_ref.get_location_string()
            return f"{reference.title} ({location})"
        else:
            return f"{reference.title} (网络文章 - 待第三步完成后启用)"

    def _format_reference_markdown_list(
        self, reference: SourceReference, number: int
    ) -> str:
        """
        格式化单个引用的Markdown列表格式

        Args:
            reference: 信息源引用
            number: 引用编号

        Returns:
            Markdown格式的列表项字符串
        """
        if reference.is_local_document() and reference.local_reference:
            local_ref = reference.local_reference
            link_url = self.link_service.create_link_from_local_reference(
                local_ref, scheme="file"
            )
            location = local_ref.get_location_string()

            return (
                f"{number}. {reference.title} ({location}) - "
                f"[{local_ref.get_display_path()}]({link_url})"
            )
        else:
            return (
                f"{number}. {reference.title} (网络文章 - 待第三步完成后启用)"
            )

    def _render_html(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """
        渲染HTML格式的引用标记

        Args:
            content: 原始内容
            references: 引用列表

        Returns:
            HTML格式的内容(包含引用标记)
        """
        if self.reference_format == ReferenceFormat.FOOTNOTE:
            return self._render_html_footnote(content, references)
        elif self.reference_format == ReferenceFormat.INLINE:
            return self._render_html_inline(content, references)
        elif self.reference_format == ReferenceFormat.BRACKET:
            return self._render_html_bracket(content, references)
        else:
            return self._render_html_footnote(content, references)

    def _render_html_footnote(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """渲染HTML脚注格式"""
        result = content
        footnotes = []

        for i, ref in enumerate(references, start=1):
            # 在内容末尾添加脚注标记
            footnote_id = f"footnote-{i}"
            footnote_marker = (
                f'<sup><a href="#{footnote_id}" id="footnote-ref-{i}">'
                f"[{i}]</a></sup>"
            )
            result += f" {footnote_marker}"

            # 生成脚注内容
            footnote_content = self._format_reference_html(ref, i, footnote_id)
            footnotes.append(footnote_content)

        # 添加脚注部分
        if footnotes:
            result += '\n<div class="footnotes">\n<ol>\n'
            result += "\n".join(footnotes)
            result += "\n</ol>\n</div>"

        return result

    def _render_html_inline(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """渲染HTML内联格式"""
        result = content
        inline_refs = []

        for ref in references:
            inline_ref = self._format_reference_html_inline(ref)
            inline_refs.append(inline_ref)

        # 在内容末尾添加内联引用
        if inline_refs:
            result += ' <span class="inline-references">('
            result += ", ".join(inline_refs)
            result += ")</span>"

        return result

    def _render_html_bracket(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """渲染HTML括号格式"""
        result = content
        ref_numbers = []

        for i, _ref in enumerate(references, start=1):
            ref_numbers.append(str(i))

        # 在内容末尾添加引用编号
        if ref_numbers:
            result += f' <span class="reference-numbers">[{", ".join(ref_numbers)}]</span>'

        # 添加引用列表
        ref_list = []
        for i, ref in enumerate(references, start=1):
            ref_item = self._format_reference_html_list(ref, i)
            ref_list.append(ref_item)

        if ref_list:
            result += '\n<div class="references">\n<h3>参考文献</h3>\n<ol>\n'
            result += "\n".join(ref_list)
            result += "\n</ol>\n</div>"

        return result

    def _format_reference_html(
        self, reference: SourceReference, number: int, footnote_id: str
    ) -> str:
        """
        格式化单个引用的HTML脚注

        Args:
            reference: 信息源引用
            number: 引用编号
            footnote_id: 脚注ID

        Returns:
            HTML格式的脚注字符串
        """
        if reference.is_local_document() and reference.local_reference:
            local_ref = reference.local_reference
            link_url = self.link_service.create_link_from_local_reference(
                local_ref, scheme="file"
            )
            location = local_ref.get_location_string()

            return (
                f'<li id="{footnote_id}">'
                f'<a href="#footnote-ref-{number}">↑</a> '
                f"{reference.title} ({location}) - "
                f'<a href="{link_url}">{local_ref.get_display_path()}</a>'
                f"</li>"
            )
        else:
            return (
                f'<li id="{footnote_id}">'
                f'<a href="#footnote-ref-{number}">↑</a> '
                f"{reference.title} (网络文章 - 待第三步完成后启用)"
                f"</li>"
            )

    def _format_reference_html_inline(self, reference: SourceReference) -> str:
        """
        格式化单个引用的HTML内联格式

        Args:
            reference: 信息源引用

        Returns:
            HTML格式的内联引用字符串
        """
        if reference.is_local_document() and reference.local_reference:
            local_ref = reference.local_reference
            location = local_ref.get_location_string()
            return f'<span class="reference">{reference.title} ({location})</span>'
        else:
            return (
                '<span class="reference">'
                f"{reference.title} (网络文章 - 待第三步完成后启用)"
                "</span>"
            )

    def _format_reference_html_list(
        self, reference: SourceReference, number: int
    ) -> str:
        """
        格式化单个引用的HTML列表格式

        Args:
            reference: 信息源引用
            number: 引用编号

        Returns:
            HTML格式的列表项字符串
        """
        # 交付物参考文献：仅展示标题，避免暴露本地路径 / (未知位置) 噪声
        if reference.is_local_document():
            title = (reference.title or "").strip() or "未知文档"
            return f"<li>{title}</li>"
        else:
            return (
                f"<li>{reference.title} (网络文章 - 待第三步完成后启用)</li>"
            )

    def _render_plain(
        self, content: str, references: list[SourceReference]
    ) -> str:
        """
        渲染纯文本格式的引用标记

        Args:
            content: 原始内容
            references: 引用列表

        Returns:
            纯文本格式的内容(包含引用标记)
        """
        result = content
        ref_list = []

        for i, ref in enumerate(references, start=1):
            if ref.is_local_document() and ref.local_reference:
                local_ref = ref.local_reference
                location = local_ref.get_location_string()
                ref_list.append(
                    f"{i}. {ref.title} ({location}) - {local_ref.get_display_path()}"
                )
            else:
                ref_list.append(
                    f"{i}. {ref.title} (网络文章 - 待第三步完成后启用)"
                )

        if ref_list:
            result += "\n\n参考文献:\n" + "\n".join(ref_list)

        return result

    def render_draft_with_references(
        self,
        draft: Draft,
        source_references: dict[uuid.UUID, SourceReference],
        render_format: RenderFormat = RenderFormat.MARKDOWN,
    ) -> str:
        """
        渲染整个草稿(包含所有章节的引用标记)

        Args:
            draft: 草稿对象
            source_references: 信息源引用字典(ID -> SourceReference)
            render_format: 渲染格式

        Returns:
            渲染后的草稿内容(包含所有引用标记)
        """
        sections_content = []

        for section in draft.sections:
            section_content = self.render_section_with_references(
                section, source_references, render_format
            )
            sections_content.append(section_content)

        return "\n\n".join(sections_content)

    def set_reference_format(self, format: ReferenceFormat) -> None:
        """
        设置引用格式

        Args:
            format: 引用格式
        """
        self.reference_format = format


# 便利函数

def create_draft_source_trace_service(
    link_service: LocalDocumentLinkService | None = None,
    reference_format: ReferenceFormat = ReferenceFormat.FOOTNOTE,
) -> DraftSourceTraceService:
    """
    创建草稿素材追溯显示服务的便捷函数

    Args:
        link_service: 本地文章链接服务(可选)
        reference_format: 引用格式

    Returns:
        DraftSourceTraceService实例
    """
    return DraftSourceTraceService(
        link_service=link_service, reference_format=reference_format
    )

