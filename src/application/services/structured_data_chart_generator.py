"""
结构化数据图表生成服务

该模块实现从文本中提取结构化数据并生成图表DSL配置的功能.
用于T177任务:可结构化数据自动抽取→图表DSL生成.

生成命令: /speckit.implement T177
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
import re
import uuid
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from src.domain.agent.chart_config import ChartConfig, ChartType
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class StructuredDataChartGenerator:
    """
    结构化数据图表生成器

    从文本内容中提取结构化数据(表格、列表等),识别数据模式,
    并使用LLM生成图表DSL配置(ECharts配置).

    用于补充没有datajson的场景.
    """

    def __init__(self, llm_service: LLMService | None = None):
        """
        初始化结构化数据图表生成器

        Args:
            llm_service: LLM服务实例,如果为None则使用全局实例
        """
        self.llm_service = llm_service or get_llm_service()

        # 获取LLM模型
        try:
            self.model = self.llm_service.get_chart_to_json_chat_model()
            logger.info("成功获取图表生成模型")
        except Exception as e:
            logger.error("获取图表生成模型失败: %s", e)
            self.model = None

        logger.debug(f"初始化 {self.__class__.__name__}")

    def extract_structured_data(
        self, content: str
    ) -> list[dict[str, Any]]:
        """
        从文本内容中提取结构化数据

        支持提取:
        - Markdown表格
        - 列表数据
        - 键值对数据

        Args:
            content: 文本内容

        Returns:
            结构化数据列表,每个元素包含:
            - type: 数据类型(table/list/key_value)
            - data: 数据内容
            - position: 在原文中的位置信息
        """
        structured_data: list[dict[str, Any]] = []

        # 1. 提取Markdown表格
        tables = self._extract_markdown_tables(content)
        for i, table in enumerate(tables):
            structured_data.append(
                {
                    "type": "table",
                    "data": table,
                    "position": {"index": i, "type": "table"},
                }
            )

        # 2. 提取列表数据
        lists = self._extract_list_data(content)
        for i, list_data in enumerate(lists):
            structured_data.append(
                {
                    "type": "list",
                    "data": list_data,
                    "position": {"index": i, "type": "list"},
                }
            )

        # 3. 提取键值对数据
        key_values = self._extract_key_value_data(content)
        for i, kv_data in enumerate(key_values):
            structured_data.append(
                {
                    "type": "key_value",
                    "data": kv_data,
                    "position": {"index": i, "type": "key_value"},
                }
            )

        logger.info(f"从内容中提取了 {len(structured_data)} 个结构化数据项")

        return structured_data

    def _extract_markdown_tables(self, content: str) -> list[dict[str, Any]]:
        """
        提取Markdown表格

        Args:
            content: 文本内容

        Returns:
            表格数据列表
        """
        tables: list[dict[str, Any]] = []
        lines = content.split("\n")
        current_table: list[str] = []
        in_table = False

        for line in lines:
            stripped = line.strip()

            # 检测表格行
            if "|" in stripped and stripped.count("|") >= 2:
                if not in_table:
                    in_table = True
                    current_table = []

                current_table.append(line)

                # 检查是否是分隔线
                if re.match(r"^\|[\s\-:]+\|", stripped):
                    continue
            else:
                if in_table:
                    if current_table:
                        # 解析表格
                        table_data = self._parse_markdown_table(
                            "\n".join(current_table)
                        )
                        if table_data:
                            tables.append(table_data)
                    current_table = []
                    in_table = False

        # 处理最后一个表格
        if in_table and current_table:
            table_data = self._parse_markdown_table("\n".join(current_table))
            if table_data:
                tables.append(table_data)

        return tables

    def _parse_markdown_table(self, table_text: str) -> dict[str, Any] | None:
        """
        解析Markdown表格

        Args:
            table_text: Markdown表格文本

        Returns:
            解析后的表格数据,格式: {"headers": [...], "rows": [[...], ...]}
        """
        lines = [line.strip() for line in table_text.split("\n") if line.strip()]

        if len(lines) < 2:
            return None

        # 第一行是表头
        headers = [
            cell.strip() for cell in lines[0].split("|")[1:-1] if cell.strip()
        ]

        # 跳过分隔线,处理数据行
        rows: list[list[str]] = []
        for line in lines[1:]:
            # 跳过分隔线
            if re.match(r"^\|[\s\-:]+\|", line):
                continue

            cells = [cell.strip() for cell in line.split("|")[1:-1]]
            if cells:
                rows.append(cells)

        if not headers or not rows:
            return None

        return {"headers": headers, "rows": rows}

    def _extract_list_data(self, content: str) -> list[dict[str, Any]]:
        """
        提取列表数据

        支持有序列表和无序列表,提取包含数值的列表项.

        Args:
            content: 文本内容

        Returns:
            列表数据列表
        """
        lists: list[dict[str, Any]] = []
        lines = content.split("\n")

        current_list: list[str] = []
        in_list = False

        for line in lines:
            stripped = line.strip()

            # 检测列表项(有序或无序)
            list_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.+)$", stripped)
            if list_match:
                if not in_list:
                    in_list = True
                    current_list = []

                item_text = list_match.group(3).strip()
                current_list.append(item_text)
            else:
                if in_list:
                    if current_list:
                        # 尝试提取数值数据
                        list_data = self._parse_list_for_chart_data(current_list)
                        if list_data:
                            lists.append(list_data)
                    current_list = []
                    in_list = False

        # 处理最后一个列表
        if in_list and current_list:
            list_data = self._parse_list_for_chart_data(current_list)
            if list_data:
                lists.append(list_data)

        return lists

    def _parse_list_for_chart_data(
        self, list_items: list[str]
    ) -> dict[str, Any] | None:
        """
        解析列表项,提取可用于图表的数据

        Args:
            list_items: 列表项文本列表

        Returns:
            解析后的数据,格式: {"items": [{"label": "...", "value": ...}, ...]}
        """
        chart_items: list[dict[str, Any]] = []

        for item in list_items:
            # 尝试提取标签和数值
            # 格式: "标签: 数值" 或 "标签 (数值)" 或 "标签 数值"
            patterns = [
                r"^(.+?):\s*([\d.]+)\s*(.*)$",  # "标签: 数值 单位"
                r"^(.+?)\s*\(([\d.]+)\s*(.*?)\)$",  # "标签 (数值 单位)"
                r"^(.+?)\s+([\d.]+)\s*(.*)$",  # "标签 数值 单位"
            ]

            for pattern in patterns:
                match = re.match(pattern, item)
                if match:
                    label = match.group(1).strip()
                    value_str = match.group(2).strip()
                    unit = match.group(3).strip() if len(match.groups()) > 2 else ""

                    try:
                        value = float(value_str)
                        chart_items.append(
                            {"label": label, "value": value, "unit": unit}
                        )
                        break
                    except ValueError:
                        continue

        if not chart_items:
            return None

        return {"items": chart_items}

    def _extract_key_value_data(self, content: str) -> list[dict[str, Any]]:
        """
        提取键值对数据

        支持格式:
        - "键: 值"
        - "键 = 值"
        - "键 值"

        Args:
            content: 文本内容

        Returns:
            键值对数据列表
        """
        key_values: list[dict[str, Any]] = []
        lines = content.split("\n")

        current_kv: list[dict[str, str]] = []
        in_kv_section = False

        for line in lines:
            stripped = line.strip()

            # 检测键值对
            patterns = [
                r"^(.+?):\s*(.+)$",  # "键: 值"
                r"^(.+?)=\s*(.+)$",  # "键 = 值"
                r"^(.+?)\s+([\d.]+)\s*(.*)$",  # "键 数值 单位"
            ]

            matched = False
            for pattern in patterns:
                match = re.match(pattern, stripped)
                if match:
                    key = match.group(1).strip()
                    value_str = match.group(2).strip()
                    unit = (
                        match.group(3).strip()
                        if len(match.groups()) > 2
                        else ""
                    )

                    # 尝试解析为数值
                    try:
                        value = float(value_str)
                        current_kv.append({"key": key, "value": value, "unit": unit})
                        in_kv_section = True
                        matched = True
                        break
                    except ValueError:
                        # 不是数值,跳过
                        pass

            if not matched and in_kv_section:
                # 结束当前键值对区域
                if current_kv:
                    key_values.append({"items": current_kv})
                current_kv = []
                in_kv_section = False

        # 处理最后一个键值对区域
        if in_kv_section and current_kv:
            key_values.append({"items": current_kv})

        return key_values

    def generate_chart_config_from_data(
        self,
        draft_id: uuid.UUID,
        structured_data: dict[str, Any],
        chart_type_hint: str | None = None,
    ) -> ChartConfig | None:
        """
        从结构化数据生成图表配置

        使用LLM分析数据模式,识别合适的图表类型,并生成ECharts配置.

        Args:
            draft_id: 草稿ID
            structured_data: 结构化数据
            chart_type_hint: 图表类型提示(可选)

        Returns:
            图表配置对象,如果生成失败则返回None
        """
        if not self.model:
            logger.warning("LLM模型不可用,无法生成图表配置")
            return None

        try:
            # 准备提示词
            system_message = self._get_chart_generation_system_message()
            user_message = self._format_data_for_llm(structured_data, chart_type_hint)

            # 调用LLM
            messages = [
                SystemMessage(content=system_message),
                HumanMessage(content=user_message),
            ]

            prompt = ChatPromptTemplate.from_messages(messages)
            chain = prompt | self.model | StrOutputParser()

            response = chain.invoke({})

            # 解析响应
            chart_config_data = self._parse_llm_response(response)

            if not chart_config_data:
                logger.warning("LLM响应解析失败")
                return None

            # 创建图表配置
            chart_type = self._parse_chart_type(
                chart_config_data.get("chart_type", "OTHER")
            )

            chart_config = ChartConfig.create_from_data_source(
                draft_id=draft_id,
                chart_type=chart_type,
                data_source=structured_data,
                title=chart_config_data.get("title"),
                description=chart_config_data.get("description"),
            )

            # 设置DSL配置
            echarts_config = chart_config_data.get("echarts_config", {})
            chart_config.update_dsl_config({"option": echarts_config})

            logger.info(
                f"成功生成图表配置: 类型={chart_type.value}, 标题={chart_config.title}"
            )

            return chart_config

        except Exception as e:
            logger.error(f"生成图表配置失败: {e}", exc_info=True)
            return None

    def _get_chart_generation_system_message(self) -> str:
        """获取图表生成的系统提示词"""
        return """你是一个专业的图表生成助手.请根据提供的结构化数据,分析数据模式,识别合适的图表类型,并生成ECharts配置.

**你的任务**:
1. 分析数据结构,识别最适合的图表类型(柱状图、折线图、饼图等)
2. 提取数据中的标签、数值、单位等信息
3. 生成完整的ECharts配置JSON

**输出要求**:
- 请返回有效的JSON格式
- JSON结构:
{
  "chart_type": "bar" | "line" | "pie" | "scatter" | "table",
  "title": "图表标题",
  "description": "图表描述",
  "echarts_config": {
    // 完整的ECharts option配置
  }
}

**图表类型选择指南**:
- 柱状图(bar): 适合分类数据对比
- 折线图(line): 适合趋势数据
- 饼图(pie): 适合比例数据
- 散点图(scatter): 适合相关性数据
- 表格(table): 适合复杂数据展示

请确保生成的ECharts配置是完整且可用的."""

    def _format_data_for_llm(
        self, structured_data: dict[str, Any], chart_type_hint: str | None
    ) -> str:
        """
        格式化数据供LLM使用

        Args:
            structured_data: 结构化数据
            chart_type_hint: 图表类型提示

        Returns:
            格式化的提示词
        """
        data_type = structured_data.get("type", "unknown")
        data_content = structured_data.get("data", {})

        prompt = f"""请根据以下结构化数据生成图表配置:

**数据类型**: {data_type}

**数据内容**:
{json.dumps(data_content, ensure_ascii=False, indent=2)}
"""

        if chart_type_hint:
            prompt += f"\n**图表类型提示**: {chart_type_hint}"

        prompt += "\n\n请分析数据并生成合适的ECharts配置."

        return prompt

    def _parse_llm_response(self, response: str) -> dict[str, Any] | None:
        """
        解析LLM响应

        Args:
            response: LLM响应文本

        Returns:
            解析后的配置数据
        """
        try:
            # 尝试直接解析JSON
            return json.loads(response.strip())
        except json.JSONDecodeError:
            # 尝试提取JSON代码块
            json_match = re.search(r"```json\s*(\{.*?\})\s*```", response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # 尝试提取大括号内的JSON
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.warning(f"无法解析LLM响应: {response[:200]}")
            return None

    def _parse_chart_type(self, chart_type_str: str) -> ChartType:
        """解析图表类型字符串为ChartType枚举"""
        chart_type_str_lower = chart_type_str.lower()

        if "bar" in chart_type_str_lower:
            return ChartType.BAR
        elif "line" in chart_type_str_lower:
            return ChartType.LINE
        elif "pie" in chart_type_str_lower:
            return ChartType.PIE
        elif "scatter" in chart_type_str_lower:
            return ChartType.SCATTER
        elif "table" in chart_type_str_lower:
            return ChartType.TABLE
        else:
            return ChartType.OTHER

