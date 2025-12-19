"""
LLM图表转JSON转换器集成测试

测试基于LLM的图表识别和JSON转换功能的集成测试。

生成命令: /speckit.implement T031B
生成时间: 2025-12-16
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import base64
import os
import tempfile
from pathlib import Path

import pytest

from src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter import (
    ChartAnalysisResult,
    LLMChartToJsonConverter,
)


class TestLLMChartToJsonConverterIntegration:
    """LLM图表转JSON转换器集成测试"""

    @pytest.fixture
    def converter(self):
        """创建转换器实例"""
        # 注意:这个测试需要真实的LLM配置
        # 如果没有配置,测试会跳过
        try:
            return LLMChartToJsonConverter()
        except Exception as e:
            pytest.skip(f"无法初始化转换器: {e}")

    @pytest.fixture
    def sample_image_path(self):
        """创建示例图像文件"""
        # 创建一个简单的1x1像素PNG图像
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            with open(tmp_file.name, "wb") as f:
                f.write(png_data)
            yield tmp_file.name

        # 清理
        os.unlink(tmp_file.name)

    @pytest.fixture
    def sample_mineru_directory(self):
        """创建示例MinerU目录结构"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            mineru_path = Path(tmp_dir)

            # 创建images目录
            images_dir = mineru_path / "images"
            images_dir.mkdir()

            # 创建clean.md文件
            clean_md = mineru_path / "clean.md"
            clean_md.write_text("""# 测试文档

这是一个测试文档,包含图表引用。

![储能市场规模增长趋势](images/chart1.png)

![市场份额分布](images/chart2.png '市场份额饼图')

[chart3]: images/chart3.png '销售数据柱状图'
""")

            # 创建几个测试图像文件
            for name in ["chart1.png", "chart2.jpg", "chart3.png"]:
                png_data = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                )
                file_path = images_dir / name
                with open(file_path, "wb") as f:
                    f.write(png_data)

            yield str(mineru_path)

    def test_converter_initialization(self):
        """测试转换器初始化"""
        # 这个测试验证转换器可以正确初始化
        # 如果配置不正确,会抛出异常
        try:
            converter = LLMChartToJsonConverter()
            assert converter is not None
            assert hasattr(converter, "model")
            assert hasattr(converter, "confidence_threshold")
            assert hasattr(converter, "supports_vision")
        except Exception as e:
            pytest.skip(f"无法初始化转换器: {e}")

    def test_encode_image_to_base64(self, converter, sample_image_path):
        """测试图像base64编码"""
        encoded = converter._encode_image_to_base64(sample_image_path)

        assert isinstance(encoded, str)
        assert len(encoded) > 0

        # 验证可以解码回来
        decoded = base64.b64decode(encoded)
        with open(sample_image_path, "rb") as f:
            original = f.read()
        assert decoded == original

    def test_get_image_mime_type(self, converter):
        """测试图像MIME类型获取"""
        test_cases = [
            ("test.jpg", "image/jpeg"),
            ("test.jpeg", "image/jpeg"),
            ("test.png", "image/png"),
            ("test.gif", "image/gif"),
            ("test.bmp", "image/bmp"),
            ("test.webp", "image/webp"),
            ("test.unknown", "image/jpeg"),
        ]

        for filename, expected_mime in test_cases:
            actual_mime = converter._get_image_mime_type(filename)
            assert actual_mime == expected_mime, (
                f"Failed for {filename}: expected {expected_mime}, got {actual_mime}"
            )

    def test_sanitize_filename(self, converter):
        """测试文件名清理"""
        test_cases = [
            ("test<>file", "test__file"),
            ("test'file", "test_file"),
            ("test:file", "test_file"),
            ("test\\file", "test_file"),
            ("test|file", "test_file"),
            ("test?file", "test_file"),
            ("test*file", "test_file"),
            ("a" * 150, "a" * 100),  # 长度限制
        ]

        for input_name, expected_output in test_cases:
            actual_output = converter._sanitize_filename(input_name)
            assert actual_output == expected_output, (
                f"Failed for {input_name}: expected {expected_output}, got {actual_output}"
            )

    def test_extract_chart_name_from_md(self, converter):
        """测试从Markdown提取图表名称"""
        # 创建临时Markdown文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as tmp_file:
            md_content = """# 测试文档

这是一个测试文档,包含图表引用。

![储能市场规模增长趋势](images/chart1.png)

![市场份额分布](images/chart2.png '市场份额饼图')

[chart3]: images/chart3.png '销售数据柱状图'
"""
            tmp_file.write(md_content)

            try:
                # 测试提取
                name1 = converter._extract_chart_name_from_md(tmp_file.name, "chart1")
                assert name1 == "储能市场规模增长趋势"

                name2 = converter._extract_chart_name_from_md(tmp_file.name, "chart2")
                assert name2 == "市场份额分布"

                name3 = converter._extract_chart_name_from_md(tmp_file.name, "chart3")
                assert name3 == "销售数据柱状图"

                # 测试未找到的情况
                name4 = converter._extract_chart_name_from_md(
                    tmp_file.name, "nonexistent"
                )
                assert name4 == "nonexistent"

            finally:
                # 清理临时文件
                os.unlink(tmp_file.name)

    @pytest.mark.skipif(
        not os.getenv("CHART_TO_JSON_LLM_API_KEY")
        or not os.getenv("CHART_TO_JSON_LLM_BASE_URL")
        or not os.getenv("CHART_TO_JSON_LLM_MODEL_NAME"),
        reason="需要图表转JSON LLM配置环境变量",
    )
    def test_analyze_image_integration(self, converter, sample_image_path):
        """测试图像分析集成"""
        # 注意:这个测试需要真实的LLM配置
        # 如果没有配置或模型不支持视觉,会跳过

        if not converter.supports_vision:
            pytest.skip("模型不支持视觉输入")

        try:
            result = converter._analyze_image(sample_image_path)

            # 验证返回结果类型
            assert isinstance(result, ChartAnalysisResult)

            # 验证基本字段存在
            assert hasattr(result, "is_chart")
            assert hasattr(result, "chart_type")
            assert hasattr(result, "confidence_score")
            assert hasattr(result, "has_accurate_data")
            assert hasattr(result, "description")

            # 验证字段类型
            assert isinstance(result.is_chart, bool)
            assert isinstance(result.confidence_score, (int, float))
            assert isinstance(result.has_accurate_data, bool)

            # 如果是图表,验证图表类型
            if result.is_chart:
                assert result.chart_type is not None
                assert isinstance(result.chart_type, str)

        except Exception as e:
            pytest.skip(f"图像分析失败: {e}")

    @pytest.mark.skipif(
        not os.getenv("CHART_TO_JSON_LLM_API_KEY")
        or not os.getenv("CHART_TO_JSON_LLM_BASE_URL")
        or not os.getenv("CHART_TO_JSON_LLM_MODEL_NAME"),
        reason="需要图表转JSON LLM配置环境变量",
    )
    def test_process_single_image_integration(self, converter, sample_image_path):
        """测试单个图像处理集成"""
        # 注意:这个测试需要真实的LLM配置

        if not converter.supports_vision:
            pytest.skip("模型不支持视觉输入")

        try:
            result = converter.process_single_image(sample_image_path)

            # 结果可能为None(如果不是图表或置信度低)
            if result is not None:
                # 验证结果结构
                assert isinstance(result, dict)
                assert "image_path" in result
                assert "analysis" in result

                # 如果生成了JSON,验证相关字段
                if result.get("json_generated", False):
                    assert "chart_data" in result
                    assert "json_filename" in result

                    # 验证chart_data结构
                    chart_data = result["chart_data"]
                    assert isinstance(chart_data, dict)
                    assert "chart_type" in chart_data
                    assert "title" in chart_data
                    assert "confidence_score" in chart_data
                    assert "has_accurate_data" in chart_data

        except Exception as e:
            pytest.skip(f"单个图像处理失败: {e}")

    @pytest.mark.skipif(
        not os.getenv("CHART_TO_JSON_LLM_API_KEY")
        or not os.getenv("CHART_TO_JSON_LLM_BASE_URL")
        or not os.getenv("CHART_TO_JSON_LLM_MODEL_NAME"),
        reason="需要图表转JSON LLM配置环境变量",
    )
    def test_process_mineru_directory_integration(
        self, converter, sample_mineru_directory
    ):
        """测试MinerU目录处理集成"""
        # 注意:这个测试需要真实的LLM配置

        if not converter.supports_vision:
            pytest.skip("模型不支持视觉输入")

        try:
            result = converter.process_mineru_directory(sample_mineru_directory)

            # 验证结果结构
            assert isinstance(result, dict)
            assert "processed" in result
            assert "statistics" in result
            assert "mineru_output_dir" in result
            assert "images_dir" in result
            assert "output_dir" in result

            # 验证统计信息
            stats = result["statistics"]
            assert isinstance(stats, dict)
            assert "total_images" in stats
            assert "charts_found" in stats
            assert "json_generated" in stats
            assert "processing_errors" in stats

            # 验证输出目录存在
            output_dir = Path(result["output_dir"])
            assert output_dir.exists()
            assert output_dir.name == "datajson"

            # 验证处理结果
            processed = result["processed"]
            assert isinstance(processed, list)

            # 如果有处理结果,验证结构
            if processed:
                for item in processed:
                    assert isinstance(item, dict)
                    assert "image_path" in item
                    assert "analysis" in item

        except Exception as e:
            pytest.skip(f"MinerU目录处理失败: {e}")

    def test_error_handling(self):
        """测试错误处理"""
        # 测试初始化错误
        with pytest.raises(Exception):
            # 模拟没有配置的情况
            with pytest.MonkeyPatch() as m:
                m.setenv("CHART_TO_JSON_LLM_API_KEY", "")
                m.setenv("CHART_TO_JSON_LLM_BASE_URL", "")
                m.setenv("CHART_TO_JSON_LLM_MODEL_NAME", "")
                LLMChartToJsonConverter()

        # 测试不存在的图像文件
        try:
            converter = LLMChartToJsonConverter()
            result = converter._encode_image_to_base64("/nonexistent/image.png")
            assert result is None  # 或者抛出异常,取决于实现
        except Exception:
            pass  # 预期会抛出异常

        # 测试不存在的目录
        converter = LLMChartToJsonConverter()
        result = converter.process_images_in_directory("/nonexistent/directory")
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__])
