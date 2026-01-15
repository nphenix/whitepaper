"""
图表配置领域模型

该模块定义了图表配置的领域模型, 包括图表类型,数据源,DSL配置等.
用于MVP流程中的草稿生成阶段,支持图表在HTML交付物中的渲染.
"""

# 生成命令: /speckit.implement T172
# 生成时间: 2025-01-XX
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ChartType(str, Enum):
    """图表类型枚举"""

    BAR = "BAR"                    # 柱状图
    LINE = "LINE"                  # 折线图
    PIE = "PIE"                    # 饼图
    SCATTER = "SCATTER"            # 散点图
    TABLE = "TABLE"                # 表格
    OTHER = "OTHER"                 # 其他类型


class ChartConfig(BaseModel):
    """
    图表配置领域模型

    表示草稿中的一个图表配置,包含图表类型,数据源,DSL配置等信息.
    用于在HTML交付物中渲染图表,支持ECharts等图表库.
    """

    # 基本字段
    id: uuid.UUID = Field(default_factory=uuid.uuid4, description="图表配置唯一标识")
    draft_id: uuid.UUID = Field(..., description="关联的草稿ID")

    # 图表类型
    chart_type: ChartType = Field(..., description="图表类型")

    # 数据源(从检索数据中识别的结构化内容)
    data_source: dict[str, Any] = Field(
        default_factory=dict, description="数据源(JSON格式的结构化内容)"
    )

    # 图表DSL配置(如ECharts JSON)
    dsl_config: dict[str, Any] = Field(
        default_factory=dict, description="图表DSL配置(如ECharts JSON)"
    )

    # 占位符位置
    placeholder_position: int = Field(0, description="在文稿中的占位符位置")

    # 是否可编辑
    is_editable: bool = Field(True, description="是否可编辑")

    # 图表标题和描述(可选)
    title: str | None = Field(None, description="图表标题")
    description: str | None = Field(None, description="图表描述")

    # 数据来源信息(可选,用于附录展示)
    source_file: str | None = Field(None, description="数据来源文件路径(如datajson/*.json)")
    source_metadata: dict[str, Any] = Field(
        default_factory=dict, description="数据来源元数据"
    )

    # 时间字段
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="更新时间"
    )

    # 扩展元数据
    metadata: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")

    @field_validator("placeholder_position")
    @classmethod
    def validate_placeholder_position(cls, v: int) -> int:
        """验证占位符位置"""
        if v < 0:
            error_msg = "占位符位置不能为负数"
            raise ValueError(error_msg)
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        """验证标题"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        """验证描述"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @field_validator("source_file")
    @classmethod
    def validate_source_file(cls, v: str | None) -> str | None:
        """验证来源文件路径"""
        if v is None:
            return None
        return v.strip() if v.strip() else None

    @model_validator(mode="after")
    def validate_consistency(self) -> "ChartConfig":
        """验证字段一致性"""
        # 验证data_source是有效的字典结构
        if not isinstance(self.data_source, dict):
            error_msg = "data_source必须是字典类型"
            raise ValueError(error_msg)

        # 验证dsl_config是有效的字典结构
        if not isinstance(self.dsl_config, dict):
            error_msg = "dsl_config必须是字典类型"
            raise ValueError(error_msg)

        return self

    def is_bar_chart(self) -> bool:
        """
        检查是否为柱状图

        Returns:
            是否为柱状图
        """
        return self.chart_type == ChartType.BAR

    def is_line_chart(self) -> bool:
        """
        检查是否为折线图

        Returns:
            是否为折线图
        """
        return self.chart_type == ChartType.LINE

    def is_pie_chart(self) -> bool:
        """
        检查是否为饼图

        Returns:
            是否为饼图
        """
        return self.chart_type == ChartType.PIE

    def is_scatter_chart(self) -> bool:
        """
        检查是否为散点图

        Returns:
            是否为散点图
        """
        return self.chart_type == ChartType.SCATTER

    def is_table(self) -> bool:
        """
        检查是否为表格

        Returns:
            是否为表格
        """
        return self.chart_type == ChartType.TABLE

    def is_other_type(self) -> bool:
        """
        检查是否为其他类型

        Returns:
            是否为其他类型
        """
        return self.chart_type == ChartType.OTHER

    def get_placeholder_string(self) -> str:
        """
        获取占位符字符串

        Returns:
            格式化的占位符字符串(如: [[CHART:<id>]])
        """
        return f"[[CHART:{self.id}]]"

    def get_placeholder_string_by_index(self, index: int) -> str:
        """
        通过索引获取占位符字符串

        Args:
            index: 图表索引

        Returns:
            格式化的占位符字符串(如: [[CHART:<index>]])
        """
        return f"[[CHART:{index}]]"

    def update_data_source(self, data_source: dict[str, Any]) -> None:
        """
        更新数据源

        Args:
            data_source: 新的数据源
        """
        if not isinstance(data_source, dict):
            error_msg = "data_source必须是字典类型"
            raise ValueError(error_msg)

        if self.data_source != data_source:
            self.data_source = data_source
            self._touch()

    def update_dsl_config(self, dsl_config: dict[str, Any]) -> None:
        """
        更新DSL配置

        Args:
            dsl_config: 新的DSL配置
        """
        if not isinstance(dsl_config, dict):
            error_msg = "dsl_config必须是字典类型"
            raise ValueError(error_msg)

        if self.dsl_config != dsl_config:
            self.dsl_config = dsl_config
            self._touch()

    def update_chart_type(self, chart_type: ChartType) -> None:
        """
        更新图表类型

        Args:
            chart_type: 新的图表类型
        """
        if self.chart_type != chart_type:
            self.chart_type = chart_type
            self._touch()

    def update_title(self, title: str | None) -> None:
        """
        更新图表标题

        Args:
            title: 新标题
        """
        new_title = title.strip() if title else None
        if self.title != new_title:
            self.title = new_title
            self._touch()

    def update_description(self, description: str | None) -> None:
        """
        更新图表描述

        Args:
            description: 新描述
        """
        new_description = description.strip() if description else None
        if self.description != new_description:
            self.description = new_description
            self._touch()

    def set_placeholder_position(self, position: int) -> None:
        """
        设置占位符位置

        Args:
            position: 新的占位符位置
        """
        if position < 0:
            error_msg = "占位符位置不能为负数"
            raise ValueError(error_msg)

        if self.placeholder_position != position:
            self.placeholder_position = position
            self._touch()

    def set_editable(self, editable: bool) -> None:
        """
        设置是否可编辑

        Args:
            editable: 是否可编辑
        """
        if self.is_editable != editable:
            self.is_editable = editable
            self._touch()

    def add_metadata(self, key: str, value: Any) -> None:
        """
        添加元数据

        Args:
            key: 元数据键
            value: 元数据值
        """
        current_value = self.metadata.get(key)
        if current_value != value:
            new_metadata = self.metadata.copy()
            new_metadata[key] = value
            self.metadata = new_metadata
            self._touch()

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        获取元数据

        Args:
            key: 元数据键
            default: 默认值

        Returns:
            元数据值
        """
        return self.metadata.get(key, default)

    def remove_metadata(self, key: str) -> bool:
        """
        移除元数据

        Args:
            key: 要移除的元数据键

        Returns:
            是否成功移除(键存在)
        """
        if key in self.metadata:
            new_metadata = self.metadata.copy()
            del new_metadata[key]
            self.metadata = new_metadata
            self._touch()
            return True
        return False

    def get_echarts_config(self) -> dict[str, Any]:
        """
        获取ECharts配置(从dsl_config中提取或生成)

        Returns:
            ECharts配置字典
        """
        # 如果dsl_config已经包含ECharts配置,直接返回
        if "option" in self.dsl_config:
            return self.dsl_config["option"]

        # 否则,根据chart_type和data_source生成基础配置
        base_config: dict[str, Any] = {
            "title": {
                "text": self.title or "图表",
                "left": "center",
            },
            "tooltip": {
                "trigger": "axis" if self.chart_type in [ChartType.BAR, ChartType.LINE] else "item",
            },
            "legend": {
                "show": True,
                "left": "center",
            },
        }

        # 根据图表类型添加特定配置
        if self.chart_type == ChartType.BAR:
            base_config["xAxis"] = {"type": "category", "data": []}
            base_config["yAxis"] = {"type": "value"}
            base_config["series"] = [{"type": "bar", "data": []}]
        elif self.chart_type == ChartType.LINE:
            base_config["xAxis"] = {"type": "category", "data": []}
            base_config["yAxis"] = {"type": "value"}
            base_config["series"] = [{"type": "line", "data": []}]
        elif self.chart_type == ChartType.PIE:
            base_config["series"] = [{"type": "pie", "data": []}]
        elif self.chart_type == ChartType.SCATTER:
            base_config["xAxis"] = {"type": "value"}
            base_config["yAxis"] = {"type": "value"}
            base_config["series"] = [{"type": "scatter", "data": []}]

        # 合并data_source中的数据
        if self.data_source:
            # 这里可以根据data_source的实际结构填充配置
            # 具体实现取决于data_source的格式
            pass

        return base_config

    def has_data(self) -> bool:
        """
        检查是否有数据

        Returns:
            是否有数据
        """
        return bool(self.data_source) or bool(self.dsl_config)

    def get_display_name(self) -> str:
        """
        获取显示名称

        Returns:
            格式化的显示名称
        """
        chart_type_value = (
            self.chart_type.value
            if hasattr(self.chart_type, "value")
            else str(self.chart_type)
        )
        if self.title:
            return f"{self.title} ({chart_type_value})"
        return f"图表 ({chart_type_value})"

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典

        Returns:
            包含所有字段信息的字典
        """
        return {
            "id": str(self.id),
            "draft_id": str(self.draft_id),
            "chart_type": self.chart_type.value
            if hasattr(self.chart_type, "value")
            else self.chart_type,
            "data_source": self.data_source,
            "dsl_config": self.dsl_config,
            "placeholder_position": self.placeholder_position,
            "is_editable": self.is_editable,
            "title": self.title,
            "description": self.description,
            "source_file": self.source_file,
            "source_metadata": self.source_metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    def _touch(self) -> None:
        """更新时间戳"""
        import time

        time.sleep(0.001)  # 确保时间戳不同
        self.updated_at = datetime.now(UTC)

    @classmethod
    def create_from_data_source(
        cls,
        draft_id: uuid.UUID,
        chart_type: ChartType,
        data_source: dict[str, Any],
        title: str | None = None,
        description: str | None = None,
        source_file: str | None = None,
        placeholder_position: int = 0,
    ) -> "ChartConfig":
        """
        从数据源创建图表配置

        Args:
            draft_id: 关联的草稿ID
            chart_type: 图表类型
            data_source: 数据源
            title: 图表标题
            description: 图表描述
            source_file: 数据来源文件路径
            placeholder_position: 占位符位置

        Returns:
            图表配置对象
        """
        # 生成基础DSL配置
        dsl_config: dict[str, Any] = {}

        return cls(
            draft_id=draft_id,
            chart_type=chart_type,
            data_source=data_source,
            dsl_config=dsl_config,
            placeholder_position=placeholder_position,
            is_editable=True,
            title=title,
            description=description,
            source_file=source_file,
        )

    @classmethod
    def create_from_dsl_config(
        cls,
        draft_id: uuid.UUID,
        chart_type: ChartType,
        dsl_config: dict[str, Any],
        title: str | None = None,
        description: str | None = None,
        placeholder_position: int = 0,
    ) -> "ChartConfig":
        """
        从DSL配置创建图表配置

        Args:
            draft_id: 关联的草稿ID
            chart_type: 图表类型
            dsl_config: DSL配置(如ECharts JSON)
            title: 图表标题
            description: 图表描述
            placeholder_position: 占位符位置

        Returns:
            图表配置对象
        """
        return cls(
            draft_id=draft_id,
            chart_type=chart_type,
            data_source={},
            dsl_config=dsl_config,
            placeholder_position=placeholder_position,
            is_editable=True,
            title=title,
            description=description,
        )

    class Config:
        """Pydantic配置"""

        use_enum_values = True
        populate_by_name = True
        json_encoders = {
            uuid.UUID: str,
            datetime: lambda v: v.isoformat() if v else None,
        }


# 便利函数


def create_chart_config_from_data_source(
    draft_id: uuid.UUID,
    chart_type: ChartType,
    data_source: dict[str, Any],
    title: str | None = None,
    description: str | None = None,
    source_file: str | None = None,
    placeholder_position: int = 0,
) -> ChartConfig:
    """
    从数据源创建图表配置的便捷函数

    Args:
        draft_id: 关联的草稿ID
        chart_type: 图表类型
        data_source: 数据源
        title: 图表标题
        description: 图表描述
        source_file: 数据来源文件路径
        placeholder_position: 占位符位置

    Returns:
        图表配置对象
    """
    return ChartConfig.create_from_data_source(
        draft_id=draft_id,
        chart_type=chart_type,
        data_source=data_source,
        title=title,
        description=description,
        source_file=source_file,
        placeholder_position=placeholder_position,
    )


def create_chart_config_from_dsl_config(
    draft_id: uuid.UUID,
    chart_type: ChartType,
    dsl_config: dict[str, Any],
    title: str | None = None,
    description: str | None = None,
    placeholder_position: int = 0,
) -> ChartConfig:
    """
    从DSL配置创建图表配置的便捷函数

    Args:
        draft_id: 关联的草稿ID
        chart_type: 图表类型
        dsl_config: DSL配置
        title: 图表标题
        description: 图表描述
        placeholder_position: 占位符位置

    Returns:
        图表配置对象
    """
    return ChartConfig.create_from_dsl_config(
        draft_id=draft_id,
        chart_type=chart_type,
        dsl_config=dsl_config,
        title=title,
        description=description,
        placeholder_position=placeholder_position,
    )

