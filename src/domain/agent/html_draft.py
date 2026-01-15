"""
最终HTML文稿领域模型

该模块定义了最终HTML文稿的数据结构，包括章节、引用、图表占位符、附录数据表等。
用于T090任务：创建"最终HTML文稿"Schema/数据结构。

生成命令: /speckit.implement T090
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.domain.agent.chart_config import ChartConfig, ChartType
from src.domain.agent.draft import Draft, DraftSection, DraftSectionType
from src.domain.agent.source_reference import SourceReference


class HTMLSection(BaseModel):
    """
    HTML文稿章节模型

    表示HTML文稿中的一个章节，包含标题、内容、层级、引用等信息。
    """

    # 基本字段
    id: str = Field(..., description="章节唯一标识")
    parent_id: str | None = Field(None, description="父级章节ID")
    section_type: str = Field(..., description="章节类型")
    level: int = Field(1, ge=1, le=6, description="章节层级(1=一级标题, 2=二级标题, ...)")

    # 内容字段
    title: str | None = Field(None, description="章节标题")
    content: str = Field(..., description="章节内容(HTML格式)")
    order: int = Field(0, ge=0, description="同级项中的排序顺序")

    # 引用信息
    citation_ids: list[str] = Field(
        default_factory=list, description="关联的引用ID列表"
    )

    # 图表占位符
    chart_placeholders: list[str] = Field(
        default_factory=list, description="章节中的图表占位符列表(如: [[CHART:xxx]])"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证内容不能为空"""
        if not v or not v.strip():
            error_msg = "章节内容不能为空"
            raise ValueError(error_msg)
        return v.strip()

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class HTMLCitation(BaseModel):
    """
    HTML文稿引用模型

    表示HTML文稿中的一个引用，包含引用标题、描述、来源等信息。
    """

    # 基本字段
    id: str = Field(..., description="引用唯一标识")
    citation_number: int = Field(..., ge=1, description="引用编号(用于显示)")
    reference_type: str = Field(..., description="引用类型(LOCAL_DOCUMENT/WEB_ARTICLE)")

    # 引用内容
    title: str = Field(..., description="引用标题")
    description: str | None = Field(None, description="引用描述/摘要")

    # 来源信息
    source_path: str | None = Field(None, description="来源路径(文件路径或URL)")
    location_info: str | None = Field(None, description="定位信息(如: 第3页, 第2段)")

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class HTMLChartPlaceholder(BaseModel):
    """
    HTML文稿图表占位符模型

    表示HTML文稿中的一个图表占位符，包含图表ID、位置、类型等信息。
    """

    # 基本字段
    chart_id: str = Field(..., description="图表ID")
    placeholder_string: str = Field(..., description="占位符字符串(如: [[CHART:xxx]])")
    position: int = Field(0, ge=0, description="在文稿中的位置索引")

    # 图表信息
    chart_type: str = Field(..., description="图表类型(BAR/LINE/PIE/SCATTER/TABLE/OTHER)")
    title: str | None = Field(None, description="图表标题")
    description: str | None = Field(None, description="图表描述")

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class HTMLAppendixDataTable(BaseModel):
    """
    HTML文稿附录数据表模型

    表示HTML文稿附录中的一个数据表，包含图表数据、原始JSON等信息。
    """

    # 基本字段
    chart_id: str = Field(..., description="关联的图表ID")
    index: int = Field(..., ge=1, description="附录项索引(从1开始)")

    # 图表信息
    chart_title: str = Field(..., description="图表标题")
    chart_type: str = Field(..., description="图表类型")
    source_file: str | None = Field(None, description="数据来源文件路径")

    # 数据表格
    table_data: list[dict[str, Any]] = Field(
        default_factory=list, description="数据表格数据(行数据列表)"
    )
    table_headers: list[str] = Field(
        default_factory=list, description="数据表格表头"
    )

    # 原始JSON数据
    raw_json: dict[str, Any] = Field(
        default_factory=dict, description="原始JSON数据(用于可折叠展示)"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True


class HTMLDraft(BaseModel):
    """
    最终HTML文稿领域模型

    表示一个完整的HTML文稿，包含章节、引用、图表占位符、附录数据表等所有信息。
    用于API响应、数据验证和文档生成。
    """

    # 基本字段
    draft_id: str = Field(..., description="草稿ID")
    title: str = Field(..., description="文稿标题")
    description: str | None = Field(None, description="文稿描述")

    # 关联字段
    outline_id: str = Field(..., description="关联的大纲ID")
    industry_id: str = Field(..., description="所属行业ID")

    # 章节列表
    sections: list[HTMLSection] = Field(
        default_factory=list, description="章节列表"
    )

    # 引用列表
    citations: list[HTMLCitation] = Field(
        default_factory=list, description="引用列表"
    )

    # 图表占位符列表
    chart_placeholders: list[HTMLChartPlaceholder] = Field(
        default_factory=list, description="图表占位符列表"
    )

    # 附录数据表列表
    appendix_tables: list[HTMLAppendixDataTable] = Field(
        default_factory=list, description="附录数据表列表"
    )

    # 统计信息
    total_sections: int = Field(0, ge=0, description="总章节数")
    total_citations: int = Field(0, ge=0, description="总引用数")
    total_charts: int = Field(0, ge=0, description="总图表数")

    # 时间字段
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """验证标题不能为空"""
        if not v or not v.strip():
            error_msg = "文稿标题不能为空"
            raise ValueError(error_msg)
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    def get_section_by_id(self, section_id: str) -> HTMLSection | None:
        """
        根据ID获取章节

        Args:
            section_id: 章节ID

        Returns:
            章节对象(如果找到)
        """
        for section in self.sections:
            if section.id == section_id:
                return section
        return None

    def get_citation_by_id(self, citation_id: str) -> HTMLCitation | None:
        """
        根据ID获取引用

        Args:
            citation_id: 引用ID

        Returns:
            引用对象(如果找到)
        """
        for citation in self.citations:
            if citation.id == citation_id:
                return citation
        return None

    def get_chart_placeholder_by_id(self, chart_id: str) -> HTMLChartPlaceholder | None:
        """
        根据ID获取图表占位符

        Args:
            chart_id: 图表ID

        Returns:
            图表占位符对象(如果找到)
        """
        for placeholder in self.chart_placeholders:
            if placeholder.chart_id == chart_id:
                return placeholder
        return None

    def get_appendix_table_by_chart_id(self, chart_id: str) -> HTMLAppendixDataTable | None:
        """
        根据图表ID获取附录数据表

        Args:
            chart_id: 图表ID

        Returns:
            附录数据表对象(如果找到)
        """
        for table in self.appendix_tables:
            if table.chart_id == chart_id:
                return table
        return None

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "draft_id": self.draft_id,
            "title": self.title,
            "description": self.description,
            "outline_id": self.outline_id,
            "industry_id": self.industry_id,
            "sections": [section.model_dump() for section in self.sections],
            "citations": [citation.model_dump() for citation in self.citations],
            "chart_placeholders": [
                placeholder.model_dump() for placeholder in self.chart_placeholders
            ],
            "appendix_tables": [table.model_dump() for table in self.appendix_tables],
            "total_sections": self.total_sections,
            "total_citations": self.total_citations,
            "total_charts": self.total_charts,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }


# === 转换函数 ===


def create_html_draft_from_draft(
    draft: Draft,
    chart_configs: list[ChartConfig] | None = None,
    source_references: dict[uuid.UUID, SourceReference] | None = None,
) -> HTMLDraft:
    """
    从Draft创建HTMLDraft

    将Draft领域模型转换为HTMLDraft模型，包括章节、引用、图表占位符等。

    Args:
        draft: 草稿领域模型对象
        chart_configs: 图表配置列表(可选)
        source_references: 信息源引用字典(ID -> SourceReference)(可选)

    Returns:
        HTMLDraft对象
    """
    # 转换章节
    html_sections: list[HTMLSection] = []
    for section in draft.sections:
        # 提取图表占位符
        chart_placeholders: list[str] = []
        import re

        placeholder_pattern = r"\[\[CHART:[^\]]+\]\]"
        matches = re.findall(placeholder_pattern, section.content)
        chart_placeholders.extend(matches)

        html_section = HTMLSection(
            id=str(section.id),
            parent_id=str(section.parent_id) if section.parent_id else None,
            section_type=section.section_type.value
            if hasattr(section.section_type, "value")
            else str(section.section_type),
            level=section.level,
            title=section.title,
            content=section.content,  # 注意: 这里假设content已经是HTML格式，实际可能需要转换
            order=section.order,
            citation_ids=[str(ref_id) for ref_id in section.source_references],
            chart_placeholders=chart_placeholders,
            metadata=section.metadata,
        )
        html_sections.append(html_section)

    # 转换引用
    html_citations: list[HTMLCitation] = []
    if source_references:
        citation_number = 1
        for ref_id, source_ref in source_references.items():
            # 获取来源路径和定位信息
            source_path = source_ref.get_display_link()
            location_info = source_ref.get_location_info()

            html_citation = HTMLCitation(
                id=str(ref_id),
                citation_number=citation_number,
                reference_type=source_ref.reference_type.value
                if hasattr(source_ref.reference_type, "value")
                else str(source_ref.reference_type),
                title=source_ref.title,
                description=source_ref.description,
                source_path=source_path,
                location_info=location_info,
                metadata=source_ref.metadata,
            )
            html_citations.append(html_citation)
            citation_number += 1

    # 转换图表占位符
    html_chart_placeholders: list[HTMLChartPlaceholder] = []
    if chart_configs:
        for i, chart_config in enumerate(chart_configs):
            html_placeholder = HTMLChartPlaceholder(
                chart_id=str(chart_config.id),
                placeholder_string=chart_config.get_placeholder_string(),
                position=chart_config.placeholder_position,
                chart_type=chart_config.chart_type.value
                if hasattr(chart_config.chart_type, "value")
                else str(chart_config.chart_type),
                title=chart_config.title,
                description=chart_config.description,
                metadata=chart_config.metadata,
            )
            html_chart_placeholders.append(html_placeholder)

    # 转换附录数据表
    html_appendix_tables: list[HTMLAppendixDataTable] = []
    if chart_configs:
        for i, chart_config in enumerate(chart_configs, 1):
            # 提取表格数据
            table_data: list[dict[str, Any]] = []
            table_headers: list[str] = []

            chart_data = chart_config.data_source.get("chart_data", [])
            if chart_data:
                # 根据图表类型确定表头
                if chart_config.chart_type == ChartType.PIE:
                    table_headers = ["标签", "数值", "单位"]
                    for item in chart_data:
                        if isinstance(item, dict) and "_chart_separator" not in item:
                            table_data.append({
                                "标签": item.get("label", ""),
                                "数值": item.get("value", ""),
                                "单位": item.get("unit", ""),
                            })
                elif chart_config.chart_type in [ChartType.BAR, ChartType.LINE]:
                    table_headers = ["类别", "数值", "单位"]
                    for item in chart_data:
                        if isinstance(item, dict) and "_chart_separator" not in item:
                            table_data.append({
                                "类别": item.get("category", ""),
                                "数值": item.get("value", ""),
                                "单位": item.get("unit", ""),
                            })
                else:
                    # 其他类型: 使用所有字段作为表头
                    if chart_data and isinstance(chart_data[0], dict):
                        keys = [
                            k
                            for k in chart_data[0].keys()
                            if k != "_chart_separator"
                        ]
                        table_headers = keys
                        for item in chart_data:
                            if isinstance(item, dict) and "_chart_separator" not in item:
                                row_data = {key: item.get(key, "") for key in keys}
                                table_data.append(row_data)

            html_appendix_table = HTMLAppendixDataTable(
                chart_id=str(chart_config.id),
                index=i,
                chart_title=chart_config.title or f"图表 {i}",
                chart_type=chart_config.chart_type.value
                if hasattr(chart_config.chart_type, "value")
                else str(chart_config.chart_type),
                source_file=chart_config.source_file,
                table_data=table_data,
                table_headers=table_headers,
                raw_json=chart_config.data_source,
                metadata=chart_config.metadata,
            )
            html_appendix_tables.append(html_appendix_table)

    # 创建HTMLDraft对象
    html_draft = HTMLDraft(
        draft_id=str(draft.id),
        title=draft.title,
        description=draft.description,
        outline_id=str(draft.outline_id),
        industry_id=str(draft.industry_id),
        sections=html_sections,
        citations=html_citations,
        chart_placeholders=html_chart_placeholders,
        appendix_tables=html_appendix_tables,
        total_sections=len(html_sections),
        total_citations=len(html_citations),
        total_charts=len(html_chart_placeholders),
        created_at=draft.created_at,
        updated_at=draft.updated_at,
        metadata=draft.metadata,
    )

    return html_draft

