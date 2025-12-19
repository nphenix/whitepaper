"""
LLM图表转JSON转换器单元测试

测试基于LLM的图表识别和JSON转换功能。

生成命令: /speckit.implement T031B
生成时间: 2025-12-16
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter import (
    ChartAnalysisResult,
    ChartData,
    LLMChartToJsonConverter,
    LLMChartToJsonError,
)
from src.shared.config.settings import ChartToJsonLLMConfig
from src.shared.exceptions.base_exceptions import ProcessingError


class TestChartAnalysisResult:
    """测试ChartAnalysisResult模型"""

    def test_chart_analysis_result_creation(self):
        """测试图表分析结果创建"""
        result = ChartAnalysisResult(
            is_chart=True,
            chart_type="bar_chart",
            confidence_score=0.85,
            has_accurate_data=True,
            description="柱状图显示销售数据",
        )

        assert result.is_chart is True
        assert result.chart_type == "bar_chart"
        assert result.confidence_score == 0.85
        assert result.has_accurate_data is True
        assert result.description == "柱状图显示销售数据"

    def test_chart_analysis_result_serialization(self):
        """测试图表分析结果序列化"""
        result = ChartAnalysisResult(
            is_chart=False,
            confidence_score=0.3,
            has_accurate_data=False,
            description="不是图表",
        )

        data = result.dict()
        assert data["is_chart"] is False
        assert data["confidence_score"] == 0.3
        assert data["has_accurate_data"] is False


class TestChartData:
    """测试ChartData模型"""

    def test_chart_data_creation(self):
        """测试图表数据创建"""
        data = ChartData(
            chart_type="bar_chart",
            title="月度销售数据",
            x_axis_label="月份",
            y_axis_label="销售额(万元)",
            data_series=[{"name": "2023年", "data": [100, 120, 140, 160, 180]}],
            categories=["1月", "2月", "3月", "4月", "5月"],
            confidence_score=0.9,
            has_accurate_data=True,
        )

        assert data.chart_type == "bar_chart"
        assert data.title == "月度销售数据"
        assert data.x_axis_label == "月份"
        assert data.y_axis_label == "销售额(万元)"
        assert len(data.data_series) == 1
        assert data.data_series[0]["name"] == "2023年"
        assert data.categories == ["1月", "2月", "3月", "4月", "5月"]
        assert data.confidence_score == 0.9
        assert data.has_accurate_data is True

    def test_chart_data_serialization(self):
        """测试图表数据序列化"""
        data = ChartData(
            chart_type="pie_chart",
            title="市场份额分布",
            data_series=[
                {
                    "name": "市场份额",
                    "data": [
                        {"category": "产品A", "value": 40},
                        {"category": "产品B", "value": 35},
                        {"category": "产品C", "value": 25},
                    ],
                }
            ],
            confidence_score=0.85,
            has_accurate_data=True,
        )

        serialized = data.dict()
        assert serialized["chart_type"] == "pie_chart"
        assert serialized["title"] == "市场份额分布"
        assert len(serialized["data_series"]) == 1


class TestLLMChartToJsonConverter:
    """测试LLM图表转JSON转换器"""

    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        return ChartToJsonLLMConfig(
            provider="openai_compatible",
            base_url="https://api.example.com/v1",
            api_key="test-api-key",
            model_name="gpt-4-vision-preview",
            temperature=0.1,
            max_tokens=8192,
            timeout=120,
            supports_vision=True,
            confidence_threshold=0.7,
        )

    @pytest.fixture
    def mock_llm_service(self, mock_config):
        """模拟LLM服务"""
        mock_service = Mock()
        mock_service._config = type("Config", (), {"chart_to_json_llm": mock_config})()
        return mock_service

    @pytest.fixture
    def converter(self, mock_llm_service):
        """创建转换器实例"""
        with patch(
            "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.get_llm_service",
            return_value=mock_llm_service,
        ):
            return LLMChartToJsonConverter(llm_service=mock_llm_service)

    def test_converter_initialization(self, mock_llm_service, mock_config):
        """测试转换器初始化"""
        with patch(
            "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.get_llm_service",
            return_value=mock_llm_service,
        ):
            converter = LLMChartToJsonConverter()

            assert converter.llm_service == mock_llm_service
            assert converter.confidence_threshold == mock_config.confidence_threshold
            assert converter.supports_vision == mock_config.supports_vision

    def test_encode_image_to_base64(self, converter):
        """测试图像base64编码"""
        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            # 写入简单的PNG文件头(1x1像素的透明PNG)
            png_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            with open(tmp_file.name, "wb") as f:
                f.write(png_data)

            # 测试编码
            encoded = converter._encode_image_to_base64(tmp_file.name)

            # 验证编码结果
            assert isinstance(encoded, str)
            assert len(encoded) > 0

            # 验证可以解码回来
            decoded = base64.b64decode(encoded)
            assert decoded == png_data

            # 清理临时文件
            os.unlink(tmp_file.name)

    def test_get_image_mime_type(self, converter):
        """测试图像MIME类型获取"""
        assert converter._get_image_mime_type("test.jpg") == "image/jpeg"
        assert converter._get_image_mime_type("test.jpeg") == "image/jpeg"
        assert converter._get_image_mime_type("test.png") == "image/png"
        assert converter._get_image_mime_type("test.gif") == "image/gif"
        assert converter._get_image_mime_type("test.bmp") == "image/bmp"
        assert converter._get_image_mime_type("test.webp") == "image/webp"
        assert converter._get_image_mime_type("test.unknown") == "image/jpeg"

    def test_sanitize_filename(self, converter):
        """测试文件名清理"""
        # 测试特殊字符替换
        assert converter._sanitize_filename("test<>file") == "test__file"
        assert converter._sanitize_filename("test_file") == "test_file"
        assert converter._sanitize_filename("test:file") == "test_file"
        assert converter._sanitize_filename("test\\file") == "test_file"
        assert converter._sanitize_filename("test|file") == "test_file"
        assert converter._sanitize_filename("test?file") == "test_file"
        assert converter._sanitize_filename("test*file") == "test_file"

        # 测试长度限制
        long_name = "a" * 150
        sanitized = converter._sanitize_filename(long_name)
        assert len(sanitized) == 100

        # 测试控制字符移除
        control_name = "test\x00file\x1f"
        sanitized = converter._sanitize_filename(control_name)
        assert "\x00" not in sanitized
        assert "\x1f" not in sanitized

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

            # 测试提取
            name1 = converter._extract_chart_name_from_md(tmp_file.name, "chart1")
            assert name1 == "储能市场规模增长趋势"

            name2 = converter._extract_chart_name_from_md(tmp_file.name, "chart2")
            assert name2 == "市场份额分布"

            name3 = converter._extract_chart_name_from_md(tmp_file.name, "chart3")
            assert name3 == "销售数据柱状图"

            # 测试未找到的情况
            name4 = converter._extract_chart_name_from_md(tmp_file.name, "nonexistent")
            assert name4 == "nonexistent"

            # 清理临时文件
            os.unlink(tmp_file.name)

    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter._invoke_model_with_retry"
    )
    def test_analyze_image_success(self, mock_invoke, converter):
        """测试图像分析成功"""
        # 模拟模型返回结果
        mock_result = ChartAnalysisResult(
            is_chart=True,
            chart_type="bar_chart",
            confidence_score=0.85,
            has_accurate_data=True,
            description="柱状图显示销售数据",
        )
        mock_invoke.return_value = mock_result

        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            png_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            with open(tmp_file.name, "wb") as f:
                f.write(png_data)

            # 测试分析
            result = converter._analyze_image(tmp_file.name)

            # 验证结果
            assert result.is_chart is True
            assert result.chart_type == "bar_chart"
            assert result.confidence_score == 0.85
            assert result.has_accurate_data is True
            assert result.description == "柱状图显示销售数据"

            # 验证调用参数
            mock_invoke.assert_called_once()
            call_args = mock_invoke.call_args[0]
            assert len(call_args[0]) == 2  # system + user message

            # 清理临时文件
            os.unlink(tmp_file.name)

    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter._invoke_model_with_retry"
    )
    def test_analyze_image_not_chart(self, mock_invoke, converter):
        """测试图像分析结果不是图表"""
        # 模拟模型返回结果
        mock_result = ChartAnalysisResult(
            is_chart=False,
            chart_type=None,
            confidence_score=0.3,
            has_accurate_data=False,
            description="概念图,不是数据图表",
        )
        mock_invoke.return_value = mock_result

        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            png_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            with open(tmp_file.name, "wb") as f:
                f.write(png_data)

            # 测试分析
            result = converter._analyze_image(tmp_file.name)

            # 验证结果
            assert result.is_chart is False
            assert result.chart_type is None
            assert result.confidence_score == 0.3
            assert result.has_accurate_data is False

            # 清理临时文件
            os.unlink(tmp_file.name)

    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter._invoke_model_with_retry"
    )
    def test_analyze_image_no_vision_support(self, mock_invoke, converter):
        """测试不支持视觉输入的情况"""
        # 设置不支持视觉
        converter.supports_vision = False

        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            png_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            with open(tmp_file.name, "wb") as f:
                f.write(png_data)

            # 测试分析
            result = converter._analyze_image(tmp_file.name)

            # 验证结果
            assert result.is_chart is False
            assert result.confidence_score == 0.0
            assert result.has_accurate_data is False
            assert "不支持视觉输入" in result.description

            # 验证没有调用模型
            mock_invoke.assert_not_called()

            # 清理临时文件
            os.unlink(tmp_file.name)

    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter._extract_chart_data"
    )
    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter._analyze_image"
    )
    def test_process_single_image_success(self, mock_analyze, mock_extract, converter):
        """测试单个图像处理成功"""
        # 模拟分析结果
        analysis_result = ChartAnalysisResult(
            is_chart=True,
            chart_type="bar_chart",
            confidence_score=0.85,
            has_accurate_data=True,
            description="柱状图显示销售数据",
        )
        mock_analyze.return_value = analysis_result

        # 模拟数据提取结果
        chart_data = ChartData(
            chart_type="bar_chart",
            title="月度销售数据",
            x_axis_label="月份",
            y_axis_label="销售额(万元)",
            data_series=[{"name": "2023年", "data": [100, 120, 140, 160, 180]}],
            categories=["1月", "2月", "3月", "4月", "5月"],
            confidence_score=0.9,
            has_accurate_data=True,
        )
        mock_extract.return_value = chart_data

        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            png_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            with open(tmp_file.name, "wb") as f:
                f.write(png_data)

            # 测试处理
            result = converter.process_single_image(tmp_file.name)

            # 验证结果
            assert result is not None
            assert result["image_path"] == tmp_file.name
            assert result["json_generated"] is True
            assert result["analysis"]["is_chart"] is True
            assert result["chart_data"]["chart_type"] == "bar_chart"
            assert result["json_filename"] == "月度销售数据.json"

            # 清理临时文件
            os.unlink(tmp_file.name)

    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter._analyze_image"
    )
    def test_process_single_image_not_chart(self, mock_analyze, converter):
        """测试单个图像处理但不是图表"""
        # 模拟分析结果
        analysis_result = ChartAnalysisResult(
            is_chart=False,
            chart_type=None,
            confidence_score=0.3,
            has_accurate_data=False,
            description="概念图,不是数据图表",
        )
        mock_analyze.return_value = analysis_result

        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            png_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            with open(tmp_file.name, "wb") as f:
                f.write(png_data)

            # 测试处理
            result = converter.process_single_image(tmp_file.name)

            # 验证结果
            assert result is None

            # 清理临时文件
            os.unlink(tmp_file.name)

    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter._analyze_image"
    )
    def test_process_single_image_low_confidence(self, mock_analyze, converter):
        """测试单个图像处理但置信度低"""
        # 设置高置信度阈值
        converter.confidence_threshold = 0.9

        # 模拟分析结果
        analysis_result = ChartAnalysisResult(
            is_chart=True,
            chart_type="bar_chart",
            confidence_score=0.7,  # 低于阈值
            has_accurate_data=True,
            description="柱状图显示销售数据",
        )
        mock_analyze.return_value = analysis_result

        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
            png_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            with open(tmp_file.name, "wb") as f:
                f.write(png_data)

            # 测试处理
            result = converter.process_single_image(tmp_file.name)

            # 验证结果
            assert result is None

            # 清理临时文件
            os.unlink(tmp_file.name)

    def test_process_images_in_directory_empty(self, converter):
        """测试处理空目录"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = converter.process_images_in_directory(tmp_dir)

            assert result["statistics"]["total_images"] == 0
            assert result["statistics"]["charts_found"] == 0
            assert result["statistics"]["json_generated"] == 0
            assert len(result["processed"]) == 0

    def test_process_images_in_directory_not_exists(self, converter):
        """测试处理不存在的目录"""
        result = converter.process_images_in_directory("/nonexistent/directory")

        assert "error" in result
        assert "目录不存在" in result["error"]

    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter.process_single_image"
    )
    def test_process_images_in_directory_success(self, mock_process, converter):
        """测试处理目录中的图像成功"""

        # 模拟处理结果
        def side_effect(image_path, md_file_path=None, output_dir=None):
            filename = Path(image_path).stem
            if filename == "chart1":
                return {
                    "image_path": image_path,
                    "json_generated": True,
                    "json_filename": "chart1.json",
                }
            elif filename == "chart2":
                return {
                    "image_path": image_path,
                    "json_generated": False,
                    "reason": "不是图表",
                }
            return None

        mock_process.side_effect = side_effect

        # 创建临时目录和图像文件
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 创建几个测试图像文件
            for name in ["chart1.png", "chart2.jpg", "not_image.txt"]:
                png_data = base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                )
                file_path = Path(tmp_dir) / name
                if name.endswith(".txt"):
                    file_path.write_text("not an image")
                else:
                    with open(file_path, "wb") as f:
                        f.write(png_data)

            # 测试处理
            result = converter.process_images_in_directory(tmp_dir)

            # 验证结果
            assert result["statistics"]["total_images"] == 2  # 只计算图像文件
            assert result["statistics"]["charts_found"] == 1
            assert result["statistics"]["json_generated"] == 1
            assert len(result["processed"]) == 2

    @patch(
        "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.LLMChartToJsonConverter.process_images_in_directory"
    )
    def test_process_mineru_directory_success(self, mock_process, converter):
        """测试处理MinerU目录成功"""
        # 模拟处理结果
        mock_process.return_value = {
            "processed": [
                {
                    "image_path": "images/chart1.png",
                    "json_generated": True,
                    "json_filename": "chart1.json",
                }
            ],
            "statistics": {
                "total_images": 1,
                "charts_found": 1,
                "json_generated": 1,
                "processing_errors": 0,
            },
        }

        # 创建临时MinerU目录结构
        with tempfile.TemporaryDirectory() as tmp_dir:
            mineru_path = Path(tmp_dir)

            # 创建images目录
            images_dir = mineru_path / "images"
            images_dir.mkdir()

            # 创建clean.md文件
            clean_md = mineru_path / "clean.md"
            clean_md.write_text("# 测试文档\n\n![测试图表](images/chart1.png)")

            # 创建一个测试图像
            chart_path = images_dir / "chart1.png"
            png_data = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            with open(chart_path, "wb") as f:
                f.write(png_data)

            # 测试处理
            result = converter.process_mineru_directory(str(mineru_path))

            # 验证结果
            assert result["mineru_output_dir"] == str(mineru_path)
            assert result["clean_md_file"] == str(clean_md)
            assert result["images_dir"] == str(images_dir)
            assert result["output_dir"] is not None  # datajson目录应该被创建
            assert Path(result["output_dir"]).exists()
            assert Path(result["output_dir"]).name == "datajson"

            # 验证调用参数
            mock_process.assert_called_once()
            call_args = mock_process.call_args[0]
            assert call_args[0] == str(images_dir)  # images目录
            assert call_args[1] == str(clean_md)  # clean.md文件
            assert call_args[2] is not None  # 输出目录

    def test_process_mineru_directory_no_images(self, converter):
        """测试处理MinerU目录但没有images目录"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            mineru_path = Path(tmp_dir)

            # 只创建clean.md文件,不创建images目录
            clean_md = mineru_path / "clean.md"
            clean_md.write_text("# 测试文档")

            # 测试处理
            result = converter.process_mineru_directory(str(mineru_path))

            # 验证结果
            assert result["statistics"]["total_images"] == 0
            assert result["statistics"]["charts_found"] == 0
            assert result["statistics"]["json_generated"] == 0


class TestLLMChartToJsonError:
    """测试LLM图表转JSON异常"""

    def test_error_inheritance(self):
        """测试异常继承"""
        error = LLMChartToJsonError("测试错误")
        assert isinstance(error, ProcessingError)
        assert str(error) == "测试错误"


if __name__ == "__main__":
    pytest.main([__file__])
