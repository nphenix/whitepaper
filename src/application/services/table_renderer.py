"""
表格渲染服务

该模块实现表格到Markdown/HTML的渲染功能,确保草稿内表格可读.
用于T176任务:表格→Markdown/HTML渲染功能.

生成命令: /speckit.implement T176
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import re
from typing import Any

import markdown
from markdown.extensions import tables

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class TableRenderer:
    """
    表格渲染器

    提供表格到Markdown/HTML的转换功能,确保表格在草稿中可读.
    支持:
    - Markdown表格格式转换
    - HTML表格渲染
    - 不规范表格格式的容错处理
    - 表格样式增强
    """

    def __init__(self):
        """初始化表格渲染器"""
        # 配置Markdown解析器(仅用于表格)
        self.md = markdown.Markdown(extensions=["tables"])

        logger.debug(f"初始化 {self.__class__.__name__}")

    def render_table_to_html(
        self, table_content: str, add_styles: bool = True
    ) -> str:
        """
        将表格内容渲染为HTML格式

        Args:
            table_content: 表格内容(Markdown格式或其他格式)
            add_styles: 是否添加样式类

        Returns:
            HTML格式的表格
        """
        # 如果已经是HTML表格,直接返回
        if table_content.strip().startswith("<table"):
            return self._enhance_html_table(table_content, add_styles)

        # 尝试解析为Markdown表格
        markdown_table = self._normalize_table_format(table_content)

        # 转换为HTML
        self.md.reset()
        html = self.md.convert(markdown_table)

        # 增强HTML表格
        if add_styles:
            html = self._enhance_html_table(html, add_styles)

        return html

    def render_table_to_markdown(
        self, table_data: list[list[str]] | dict[str, list[Any]]
    ) -> str:
        """
        将表格数据转换为Markdown格式

        Args:
            table_data: 表格数据,可以是:
                - 二维列表: [[header1, header2], [row1_col1, row1_col2], ...]
                - 字典: {"header1": [val1, val2], "header2": [val1, val2]}

        Returns:
            Markdown格式的表格字符串
        """
        if isinstance(table_data, dict):
            # 字典格式: 键为列名,值为列数据列表
            headers = list(table_data.keys())
            rows: list[list[str]] = []

            # 确定行数
            max_rows = max(len(v) for v in table_data.values()) if table_data else 0

            # 构建行数据
            for i in range(max_rows):
                row = [str(table_data[header][i]) if i < len(table_data[header]) else "" for header in headers]
                rows.append(row)

            # 构建Markdown表格
            markdown_lines = []
            # 表头
            markdown_lines.append("| " + " | ".join(headers) + " |")
            # 分隔线
            markdown_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            # 数据行
            for row in rows:
                markdown_lines.append("| " + " | ".join(row) + " |")

            return "\n".join(markdown_lines)

        elif isinstance(table_data, list) and table_data:
            # 二维列表格式
            if not table_data[0]:
                return ""

            # 第一行作为表头
            headers = [str(cell) for cell in table_data[0]]
            markdown_lines = []

            # 表头
            markdown_lines.append("| " + " | ".join(headers) + " |")
            # 分隔线
            markdown_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

            # 数据行
            for row in table_data[1:]:
                row_cells = [str(cell) if cell is not None else "" for cell in row]
                # 确保行长度与表头一致
                while len(row_cells) < len(headers):
                    row_cells.append("")
                markdown_lines.append("| " + " | ".join(row_cells[: len(headers)]) + " |")

            return "\n".join(markdown_lines)

        else:
            logger.warning("不支持的表格数据格式")
            return ""

    def _normalize_table_format(self, table_content: str) -> str:
        """
        规范化表格格式

        处理不规范的表格格式,确保能够正确解析.

        Args:
            table_content: 原始表格内容

        Returns:
            规范化后的Markdown表格
        """
        lines = table_content.strip().split("\n")
        normalized_lines: list[str] = []

        for line in lines:
            line = line.strip()

            # 跳过空行
            if not line:
                continue

            # 如果行中包含管道符,可能是表格行
            if "|" in line:
                # 确保行首和行尾有管道符
                if not line.startswith("|"):
                    line = "| " + line
                if not line.endswith("|"):
                    line = line + " |"

                normalized_lines.append(line)
            else:
                # 如果不是表格行,尝试转换为表格行
                # 按空格或制表符分割
                cells = re.split(r"\s{2,}|\t", line)
                if len(cells) > 1:
                    normalized_lines.append("| " + " | ".join(cells) + " |")

        # 如果没有找到表格行,返回空
        if not normalized_lines:
            return ""

        # 检查是否有分隔线
        has_separator = any(
            re.match(r"^\|[\s\-:]+\|", line) for line in normalized_lines
        )

        # 如果没有分隔线,在第二行添加
        if not has_separator and len(normalized_lines) > 0:
            # 计算列数
            first_line = normalized_lines[0]
            col_count = first_line.count("|") - 1
            if col_count > 0:
                separator = "| " + " | ".join(["---"] * col_count) + " |"
                normalized_lines.insert(1, separator)

        return "\n".join(normalized_lines)

    def _enhance_html_table(self, html: str, add_styles: bool) -> str:
        """
        增强HTML表格(添加样式类)

        Args:
            html: HTML表格字符串
            add_styles: 是否添加样式类

        Returns:
            增强后的HTML
        """
        if not add_styles:
            return html

        # 为表格添加样式类
        html = re.sub(
            r"<table>",
            '<table class="rendered-table">',
            html,
            flags=re.IGNORECASE,
        )

        # 确保表格有合适的结构
        # 如果表格没有thead,尝试从第一行创建thead
        if "<thead>" not in html.lower() and "<tr>" in html.lower():
            # 找到第一个tr标签
            html = re.sub(
                r"(<table[^>]*>)\s*(<tr>)",
                r'\1<thead>\2',
                html,
                count=1,
                flags=re.IGNORECASE,
            )
            # 找到第一个</tr>后添加</thead>和<tbody>
            html = re.sub(
                r"(</tr>)\s*(<tr>)",
                r'\1</thead><tbody>\2',
                html,
                count=1,
                flags=re.IGNORECASE,
            )
            # 在最后一个</tr>后添加</tbody>
            html = re.sub(
                r"(</tr>)\s*(</table>)",
                r'\1</tbody>\2',
                html,
                flags=re.IGNORECASE,
            )

        return html

    def extract_tables_from_markdown(self, markdown_content: str) -> list[str]:
        """
        从Markdown内容中提取表格

        Args:
            markdown_content: Markdown格式的内容

        Returns:
            表格字符串列表
        """
        tables: list[str] = []
        lines = markdown_content.split("\n")
        current_table: list[str] = []
        in_table = False

        for line in lines:
            stripped = line.strip()

            # 检测表格行(包含管道符)
            if "|" in stripped and stripped.count("|") >= 2:
                if not in_table:
                    in_table = True
                    current_table = []

                current_table.append(line)

                # 检查是否是分隔线
                if re.match(r"^\|[\s\-:]+\|", stripped):
                    # 分隔线,继续收集
                    continue
            else:
                # 不是表格行
                if in_table:
                    # 结束当前表格
                    if current_table:
                        tables.append("\n".join(current_table))
                    current_table = []
                    in_table = False

        # 处理最后一个表格
        if in_table and current_table:
            tables.append("\n".join(current_table))

        return tables

    def render_markdown_with_tables(
        self, markdown_content: str, enhance_tables: bool = True
    ) -> str:
        """
        渲染包含表格的Markdown内容

        提取表格,增强渲染,然后替换回原内容.

        Args:
            markdown_content: Markdown格式的内容
            enhance_tables: 是否增强表格渲染

        Returns:
            渲染后的内容(表格已转换为HTML)
        """
        if not enhance_tables:
            return markdown_content

        # 提取所有表格
        tables = self.extract_tables_from_markdown(markdown_content)

        # 如果没有表格,直接返回
        if not tables:
            return markdown_content

        # 替换每个表格为增强后的HTML
        result = markdown_content
        for table in tables:
            html_table = self.render_table_to_html(table, add_styles=True)
            # 转义HTML中的特殊字符,避免在Markdown中解析
            # 这里我们直接替换,因为表格已经转换为HTML
            result = result.replace(table, html_table, 1)

        return result

    def get_table_css_styles(self) -> str:
        """
        获取表格CSS样式

        Returns:
            CSS样式字符串
        """
        return """
        .rendered-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: #fff;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .rendered-table thead {
            background-color: #f5f5f5;
        }
        .rendered-table th {
            padding: 12px 15px;
            text-align: left;
            font-weight: bold;
            border-bottom: 2px solid #ddd;
            color: #333;
        }
        .rendered-table td {
            padding: 10px 15px;
            border-bottom: 1px solid #eee;
            color: #666;
        }
        .rendered-table tbody tr:hover {
            background-color: #f9f9f9;
        }
        .rendered-table tbody tr:nth-child(even) {
            background-color: #fafafa;
        }
        .rendered-table tbody tr:last-child td {
            border-bottom: none;
        }
        """

