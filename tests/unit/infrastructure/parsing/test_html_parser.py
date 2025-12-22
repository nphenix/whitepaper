# 生成命令: /speckit.implement T044
# 生成时间: 2025-12-22
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
HTML解析器单元测试

测试HTML解析器的各种功能，包括：
- HTML正文提取
- 结构化元素提取
- 元数据提取
- LlamaIndex Node转换
"""

import pytest
from pathlib import Path

from src.infrastructure.parsing.html_parser import (
    HTMLParser,
    HTMLElementType,
    HTMLParsingError,
    InvalidHTMLError,
)


@pytest.fixture
def html_parser():
    """创建HTML解析器实例"""
    return HTMLParser(use_readability=False, use_trafilatura=False)


@pytest.fixture
def simple_html():
    """简单的HTML内容"""
    return """
    <html>
        <head>
            <title>测试标题</title>
            <meta name="description" content="测试描述">
        </head>
        <body>
            <h1>主标题</h1>
            <p>第一段内容</p>
            <h2>二级标题</h2>
            <p>第二段内容</p>
            <ul>
                <li>列表项1</li>
                <li>列表项2</li>
            </ul>
        </body>
    </html>
    """


@pytest.fixture
def complex_html():
    """复杂的HTML内容"""
    return """
    <html>
        <head>
            <title>复杂测试页面</title>
            <meta property="og:title" content="OG标题">
            <meta name="description" content="这是一个复杂的测试页面">
        </head>
        <body>
            <header>这是页眉</header>
            <nav>导航栏</nav>
            <article>
                <h1>文章标题</h1>
                <p>文章第一段</p>
                <h2>章节1</h2>
                <p>章节1内容</p>
                <h3>子章节1.1</h3>
                <p>子章节1.1内容</p>
                <ol>
                    <li>有序列表项1</li>
                    <li>有序列表项2</li>
                </ol>
                <blockquote>这是一段引用</blockquote>
                <table>
                    <tr><th>列1</th><th>列2</th></tr>
                    <tr><td>数据1</td><td>数据2</td></tr>
                </table>
            </article>
            <aside>侧边栏</aside>
            <footer>页脚</footer>
            <script>console.log('script');</script>
            <style>body { color: red; }</style>
        </body>
    </html>
    """


class TestHTMLParserInit:
    """测试HTML解析器初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        parser = HTMLParser()
        assert parser.preserve_metadata is True

    def test_init_with_options(self):
        """测试带选项初始化"""
        parser = HTMLParser(
            use_readability=False,
            use_trafilatura=False,
            preserve_metadata=False,
        )
        assert parser.use_readability is False
        assert parser.use_trafilatura is False
        assert parser.preserve_metadata is False


class TestHTMLParserExtractMainContent:
    """测试HTML正文提取"""

    def test_extract_simple_html(self, html_parser, simple_html):
        """测试提取简单HTML"""
        soup, metadata = html_parser._extract_main_content(simple_html)
        assert soup is not None
        assert "title" in metadata
        assert metadata["title"] == "测试标题"
        assert "description" in metadata

    def test_extract_complex_html(self, html_parser, complex_html):
        """测试提取复杂HTML"""
        soup, metadata = html_parser._extract_main_content(complex_html)
        assert soup is not None
        assert "title" in metadata
        # OG标题优先
        assert metadata["title"] == "OG标题"
        assert "description" in metadata

    def test_extract_removes_scripts_and_styles(self, html_parser, complex_html):
        """测试移除脚本和样式"""
        soup, _ = html_parser._extract_main_content(complex_html)
        scripts = soup.find_all("script")
        styles = soup.find_all("style")
        assert len(scripts) == 0
        assert len(styles) == 0

    def test_extract_removes_nav_header_footer(self, html_parser, complex_html):
        """测试移除导航、页眉、页脚"""
        soup, _ = html_parser._extract_main_content(complex_html)
        nav = soup.find_all("nav")
        header = soup.find_all("header")
        footer = soup.find_all("footer")
        assert len(nav) == 0
        assert len(header) == 0
        assert len(footer) == 0


class TestHTMLParserExtractElements:
    """测试HTML结构化元素提取"""

    def test_extract_elements_simple(self, html_parser, simple_html):
        """测试提取简单HTML的元素"""
        soup, _ = html_parser._extract_main_content(simple_html)
        elements = html_parser._extract_elements_from_soup(soup)

        # 应该有2个标题、2个段落、2个列表项
        headings = [e for e in elements if e.element_type == HTMLElementType.HEADING]
        paragraphs = [e for e in elements if e.element_type == HTMLElementType.PARAGRAPH]
        list_items = [e for e in elements if e.element_type == HTMLElementType.LIST_ITEM]

        assert len(headings) >= 2
        assert len(paragraphs) >= 2
        assert len(list_items) >= 2

        # 检查第一个标题
        assert headings[0].content == "主标题"
        assert headings[0].level == 1

    def test_extract_elements_complex(self, html_parser, complex_html):
        """测试提取复杂HTML的元素"""
        soup, _ = html_parser._extract_main_content(complex_html)
        elements = html_parser._extract_elements_from_soup(soup)

        # 应该包含各种元素类型
        headings = [e for e in elements if e.element_type == HTMLElementType.HEADING]
        paragraphs = [e for e in elements if e.element_type == HTMLElementType.PARAGRAPH]
        list_items = [e for e in elements if e.element_type == HTMLElementType.LIST_ITEM]
        quotes = [e for e in elements if e.element_type == HTMLElementType.QUOTE]
        tables = [e for e in elements if e.element_type == HTMLElementType.TABLE]

        assert len(headings) >= 3  # h1, h2, h3
        assert len(paragraphs) >= 3
        assert len(list_items) >= 2
        assert len(quotes) >= 1
        assert len(tables) >= 1

    def test_extract_headings_hierarchy(self, html_parser, complex_html):
        """测试提取标题层级"""
        soup, _ = html_parser._extract_main_content(complex_html)
        elements = html_parser._extract_elements_from_soup(soup)

        headings = [e for e in elements if e.element_type == HTMLElementType.HEADING]
        assert headings[0].level == 1
        assert headings[1].level == 2
        assert headings[2].level == 3


class TestHTMLParserBuildSectionContexts:
    """测试章节上下文构建"""

    def test_build_section_contexts(self, html_parser, complex_html):
        """测试构建章节上下文"""
        soup, _ = html_parser._extract_main_content(complex_html)
        elements = html_parser._extract_elements_from_soup(soup)
        section_contexts = html_parser._build_section_contexts(elements)

        assert len(section_contexts) >= 3

        # 检查第一个章节路径
        assert section_contexts[0].path == "1"
        assert section_contexts[0].level == 1

        # 检查第二个章节路径
        assert section_contexts[1].path == "1.1"
        assert section_contexts[1].level == 2
        assert section_contexts[1].parent_path == "1"

        # 检查第三个章节路径
        assert section_contexts[2].path == "1.1.1"
        assert section_contexts[2].level == 3
        assert section_contexts[2].parent_path == "1.1"


class TestHTMLParserParseHTML:
    """测试HTML解析主方法"""

    def test_parse_html_simple(self, html_parser, simple_html):
        """测试解析简单HTML"""
        nodes = html_parser.parse_html(simple_html, url="https://example.com")

        assert len(nodes) > 0

        # 检查节点元数据
        first_node = nodes[0]
        assert first_node.metadata["url"] == "https://example.com"
        assert first_node.metadata["source"] == "https://example.com"
        assert first_node.metadata["format"] == "html"
        assert "title" in first_node.metadata

    def test_parse_html_complex(self, html_parser, complex_html):
        """测试解析复杂HTML"""
        nodes = html_parser.parse_html(
            complex_html,
            url="https://example.com/article",
            metadata={"custom_key": "custom_value"},
        )

        assert len(nodes) > 0

        # 检查自定义元数据
        first_node = nodes[0]
        assert first_node.metadata["custom_key"] == "custom_value"
        assert first_node.metadata["url"] == "https://example.com/article"

    def test_parse_html_with_sections(self, html_parser, complex_html):
        """测试解析带章节的HTML"""
        nodes = html_parser.parse_html(complex_html, url="https://example.com")

        # 检查是否有节点包含章节信息
        nodes_with_sections = [
            n for n in nodes if "section_path" in n.metadata
        ]
        assert len(nodes_with_sections) > 0

        # 检查章节路径格式
        section_paths = [
            n.metadata.get("section_path")
            for n in nodes_with_sections
            if "section_path" in n.metadata
        ]
        assert "1" in section_paths
        assert "1.1" in section_paths

    def test_parse_html_empty_content(self, html_parser):
        """测试解析空内容"""
        nodes = html_parser.parse_html("")
        assert len(nodes) == 0

    def test_parse_html_invalid_html(self, html_parser):
        """测试解析无效HTML"""
        # BeautifulSoup通常能够处理无效HTML，只是返回空结果
        nodes = html_parser.parse_html("<invalid><html>")
        # 应该不抛出异常，可能返回空列表或少量节点
        assert isinstance(nodes, list)


class TestHTMLParserParseHTMLFile:
    """测试从文件解析HTML"""

    def test_parse_html_file(self, html_parser, simple_html, tmp_path):
        """测试从文件解析HTML"""
        html_file = tmp_path / "test.html"
        html_file.write_text(simple_html, encoding="utf-8")

        # 测试不提供URL时使用文件路径
        nodes = html_parser.parse_html_file(str(html_file))

        assert len(nodes) > 0
        assert nodes[0].metadata["source"] == str(html_file.absolute())

    def test_parse_html_file_with_url(self, html_parser, simple_html, tmp_path):
        """测试从文件解析HTML时提供URL"""
        html_file = tmp_path / "test.html"
        html_file.write_text(simple_html, encoding="utf-8")

        # 测试提供URL时使用URL作为source
        nodes = html_parser.parse_html_file(str(html_file), url="https://example.com")

        assert len(nodes) > 0
        assert nodes[0].metadata["source"] == "https://example.com"
        assert nodes[0].metadata["url"] == "https://example.com"

    def test_parse_html_file_not_found(self, html_parser):
        """测试文件不存在的情况"""
        with pytest.raises(FileNotFoundError):
            html_parser.parse_html_file("nonexistent.html")


class TestHTMLParserEdgeCases:
    """测试边界情况"""

    def test_parse_html_with_images(self, html_parser):
        """测试解析包含图片的HTML"""
        html = """
        <html>
            <body>
                <h1>带图片的文章</h1>
                <p>第一段</p>
                <img src="image.jpg" alt="图片描述">
                <p>第二段</p>
            </body>
        </html>
        """
        nodes = html_parser.parse_html(html)
        assert len(nodes) > 0

    def test_parse_html_with_links(self, html_parser):
        """测试解析包含链接的HTML"""
        html = """
        <html>
            <body>
                <h1>带链接的文章</h1>
                <p>这是<a href="https://example.com">链接</a>文本</p>
            </body>
        </html>
        """
        nodes = html_parser.parse_html(html)
        assert len(nodes) > 0

    def test_parse_html_no_structure(self, html_parser):
        """测试解析没有结构的HTML"""
        html = """
        <html>
            <body>
                纯文本内容，没有结构
            </body>
        </html>
        """
        nodes = html_parser.parse_html(html)
        # 应该能够处理，至少返回一些节点
        assert isinstance(nodes, list)


class TestHTMLElementTypes:
    """测试HTML元素类型"""

    def test_element_types_enum(self):
        """测试元素类型枚举"""
        assert HTMLElementType.HEADING.value == "heading"
        assert HTMLElementType.PARAGRAPH.value == "paragraph"
        assert HTMLElementType.LIST.value == "list"
        assert HTMLElementType.LIST_ITEM.value == "list_item"


class TestHTMLParsingErrors:
    """测试HTML解析错误处理"""

    def test_invalid_html_error(self):
        """测试无效HTML错误"""
        error = InvalidHTMLError(url="https://example.com")
        assert "https://example.com" in str(error)
        assert "无效" in str(error) or "invalid" in str(error).lower()

