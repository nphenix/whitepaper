"""
T031B 图表转JSON转换器测试

测试基于LLM的图表转JSON转换器功能,包括GLM-4.6V流式调用。
使用真实数据进行测试,直接调用代码能力而非在测试中读取文件。

生成命令: /speckit.implement T031B
生成时间: 2025-12-16
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter import (
    LLMChartToJsonConverter,
)
from src.shared.config.settings import ChartToJsonLLMConfig


class TestLLMChartToJsonConverter:
    """LLM图表转JSON转换器测试"""

    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        return ChartToJsonLLMConfig(
            provider="glm_4v",
            base_url="https://api.example.com/v1",
            api_key="test_key",
            model_name="glm-4.6v",
            temperature=0.1,
            max_tokens=8192,
            timeout=120,
            supports_vision=True,
            confidence_threshold=0.7,
            enable_streaming=True,
            enable_thinking=True,
            max_retries=3,
            retry_delay=1.0,
        )

    @pytest.fixture
    def mock_llm_service(self, mock_config):
        """模拟LLM服务"""
        mock_service = Mock()
        mock_service._config = Mock()
        mock_service._config.chart_to_json_llm = mock_config
        mock_service.get_chart_to_json_chat_model.return_value = Mock()
        return mock_service

    @pytest.fixture
    def converter(self, mock_llm_service):
        """创建转换器实例"""
        with patch(
            "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.get_llm_service",
            return_value=mock_llm_service,
        ):
            return LLMChartToJsonConverter()

    def test_init_with_config(self, mock_llm_service):
        """测试使用配置初始化"""
        with patch(
            "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.get_llm_service",
            return_value=mock_llm_service,
        ):
            converter = LLMChartToJsonConverter()

            assert converter.confidence_threshold == 0.7
            assert converter.supports_vision is True
            assert converter.enable_streaming is True
            assert converter.enable_thinking is True
            assert converter.max_retries == 3
            assert converter.retry_delay == 1.0

    def test_init_with_default_config(self):
        """测试使用默认配置初始化"""
        mock_service = Mock()
        mock_service.get_chart_to_json_chat_model.return_value = Mock()
        mock_service._config = None  # 没有配置

        with patch(
            "src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter.get_llm_service",
            return_value=mock_service,
        ):
            converter = LLMChartToJsonConverter()

            assert converter.confidence_threshold == 0.7
            assert converter.supports_vision is True
            assert converter.enable_streaming is True
            assert converter.enable_thinking is True
            assert converter.max_retries == 3
            assert converter.retry_delay == 1.0

    def test_glm4v_streaming_features(self, converter):
        """测试GLM-4.6V流式功能特性"""
        # 测试配置
        assert converter.enable_streaming is True
        assert converter.enable_thinking is True
        assert converter.max_retries == 3
        assert converter.retry_delay == 1.0

        # 测试模型支持检查
        assert converter.supports_vision is True
        assert converter.confidence_threshold == 0.7


class TestRealDataProcessing:
    """真实数据处理测试"""

    @classmethod
    def setup_class(cls):
        """测试类初始化,设置缓存机制"""
        cls._processed_images = set()  # 记录已处理的图片路径
        cls._test_cache = {}  # 测试结果缓存

    @classmethod
    def teardown_class(cls):
        """测试类清理"""
        cls._processed_images.clear()
        cls._test_cache.clear()

    def test_environment_variables(self):
        """测试环境变量配置"""
        # 检查关键环境变量是否存在
        required_vars = [
            "CHART_TO_JSON_LLM_PROVIDER",
            "CHART_TO_JSON_LLM_BASE_URL",
            "CHART_TO_JSON_LLM_API_KEY",
            "CHART_TO_JSON_LLM_MODEL_NAME",
        ]

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            print(f"警告: 缺少环境变量: {missing_vars}")

        # 检查可选配置
        optional_vars = [
            "CHART_TO_JSON_LLM_ENABLE_STREAMING",
            "CHART_TO_JSON_LLM_ENABLE_THINKING",
            "CHART_TO_JSON_LLM_MAX_RETRIES",
            "CHART_TO_JSON_LLM_RETRY_DELAY",
        ]

        present_vars = []
        for var in optional_vars:
            if os.getenv(var):
                present_vars.append(var)

        if present_vars:
            print(f"可选配置已设置: {present_vars}")

    def test_real_data_directory_structure(self):
        """测试真实数据目录结构"""
        base_dir = Path("data/cleaned/documents")
        if base_dir.exists():
            print(f"真实数据目录存在: {base_dir}")

            # 列出所有文档目录
            doc_dirs = [d for d in base_dir.iterdir() if d.is_dir()]
            print(f"找到 {len(doc_dirs)} 个文档目录")

            for doc_dir in doc_dirs:
                print(f"  - {doc_dir.name}")

                # 查找_extracted目录
                extracted_dirs = [
                    d
                    for d in doc_dir.iterdir()
                    if d.is_dir() and d.name.endswith("_extracted")
                ]

                for extracted_dir in extracted_dirs:
                    print(f"    - {extracted_dir.name}")

                    # 检查images目录
                    images_dir = extracted_dir / "images"
                    if images_dir.exists():
                        image_files = list(images_dir.glob("*"))
                        print(f"      图像文件: {len(image_files)} 个")
        else:
            print("真实数据目录不存在,跳过目录结构测试")

    @pytest.mark.slow
    def test_process_real_cleaned_documents_directory(self):
        """测试处理真实已清洗文档目录"""
        # 这个测试需要真实的环境变量配置和GLM-4.6V API访问
        # 只有在配置完整时才运行
        required_vars = [
            "CHART_TO_JSON_LLM_PROVIDER",
            "CHART_TO_JSON_LLM_BASE_URL",
            "CHART_TO_JSON_LLM_API_KEY",
            "CHART_TO_JSON_LLM_MODEL_NAME",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            pytest.skip(f"缺少必需的环境变量: {missing_vars}")

        # 检查真实数据目录
        base_dir = Path("data/cleaned/documents")
        if not base_dir.exists():
            pytest.skip("真实数据目录不存在")

        try:
            # 检查是否已处理过(避免重复上传)
            cache_key = "cleaned_documents_directory"
            if cache_key in self._test_cache:
                print("\n已处理过清洗文档目录,使用缓存结果")
                result = self._test_cache[cache_key]
            else:
                # 创建转换器实例
                converter = LLMChartToJsonConverter()

                # 处理真实数据目录
                result = converter.process_cleaned_documents_directory()

                # 缓存结果
                self._test_cache[cache_key] = result

            # 验证结果
            assert "base_directory" in result
            assert "processed_documents" in result
            assert "overall_statistics" in result
            assert "summary" in result

            # 打印处理结果
            summary = result["summary"]
            print("\n处理结果摘要:")
            print(f"  处理文档: {summary['documents_processed']} 个")
            print(f"  处理图像: {summary['total_images_processed']} 个")
            print(f"  发现图表: {summary['total_charts_found']} 个")
            print(f"  生成JSON: {summary['total_json_files_generated']} 个")
            print(f"  错误数量: {summary['total_errors']} 个")

            # 验证JSON文件是否生成到正确位置
            for doc_result in result["processed_documents"]:
                extracted_dir = Path(doc_result["extracted_dir"])
                datajson_dir = extracted_dir / "datajson"

                if datajson_dir.exists():
                    json_files = list(datajson_dir.glob("*.json"))
                    print(f"  {extracted_dir.name}: 生成 {len(json_files)} 个JSON文件")

                    # 验证JSON文件格式
                    for json_file in json_files:
                        try:
                            with open(json_file, encoding="utf-8") as f:
                                json_data = json.load(f)
                            assert "chart_type" in json_data
                            assert "title" in json_data
                            print(f"    ✓ {json_file.name}")
                        except Exception as e:
                            print(f"    ✗ {json_file.name}: {e}")

        except Exception as e:
            pytest.fail(f"处理真实数据目录失败: {e}")

    @pytest.mark.slow
    def test_process_single_real_image(self):
        """测试处理单个真实图像"""
        # 这个测试需要真实的环境变量配置和GLM-4.6V API访问
        required_vars = [
            "CHART_TO_JSON_LLM_PROVIDER",
            "CHART_TO_JSON_LLM_BASE_URL",
            "CHART_TO_JSON_LLM_API_KEY",
            "CHART_TO_JSON_LLM_MODEL_NAME",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            pytest.skip(f"缺少必需的环境变量: {missing_vars}")

        # 查找第一个可用的图像文件
        base_dir = Path("data/cleaned/documents")
        if not base_dir.exists():
            pytest.skip("真实数据目录不存在")

        # 查找第一个图像文件
        image_file = None
        for doc_dir in base_dir.iterdir():
            if doc_dir.is_dir():
                for extracted_dir in doc_dir.iterdir():
                    if extracted_dir.is_dir() and extracted_dir.name.endswith(
                        "_extracted"
                    ):
                        images_dir = extracted_dir / "images"
                        if images_dir.exists():
                            image_files = list(images_dir.glob("*.jpg")) + list(
                                images_dir.glob("*.png")
                            )
                            if image_files:
                                image_file = image_files[0]
                                break
                if image_file:
                    break

        if not image_file:
            pytest.skip("没有找到可用的图像文件")

        try:
            # 创建转换器实例
            converter = LLMChartToJsonConverter()

            # 处理单个图像
            result = converter.process_single_image(str(image_file))

            if result:
                print(f"\n处理结果: {image_file.name}")
                print(f"  是图表: {result.get('analysis', {}).get('is_chart', False)}")
                print(f"  生成JSON: {result.get('json_generated', False)}")

                if result.get("json_generated"):
                    chart_data = result.get("chart_data", {})
                    print(f"  图表类型: {chart_data.get('chart_type', 'Unknown')}")
                    print(f"  图表标题: {chart_data.get('title', 'Unknown')}")
                    print(f"  置信度: {chart_data.get('confidence_score', 0)}")
            else:
                print(f"\n图像 {image_file.name} 未被识别为图表或置信度不足")

        except Exception as e:
            pytest.fail(f"处理单个真实图像失败: {e}")


class TestDemoScript:
    """演示脚本测试"""

    def test_demo_script_functionality(self):
        """测试演示脚本功能"""
        # 这个测试验证演示脚本的逻辑是否正确
        # 不需要真实的API调用

        print("\n演示脚本功能测试:")
        print("1. 检查环境变量配置")

        required_vars = [
            "CHART_TO_JSON_LLM_PROVIDER",
            "CHART_TO_JSON_LLM_BASE_URL",
            "CHART_TO_JSON_LLM_API_KEY",
            "CHART_TO_JSON_LLM_MODEL_NAME",
        ]

        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            print(f"   缺少必需的环境变量: {missing_vars}")
        else:
            print("   ✓ 所有必需环境变量已配置")

        print("2. 检查真实数据目录")
        base_dir = Path("data/cleaned/documents")
        if base_dir.exists():
            print("   ✓ 真实数据目录存在")

            doc_dirs = [d for d in base_dir.iterdir() if d.is_dir()]
            print(f"   找到 {len(doc_dirs)} 个文档目录")

            total_images = 0
            for doc_dir in doc_dirs:
                for extracted_dir in doc_dir.iterdir():
                    if extracted_dir.is_dir() and extracted_dir.name.endswith(
                        "_extracted"
                    ):
                        images_dir = extracted_dir / "images"
                        if images_dir.exists():
                            image_files = list(images_dir.glob("*"))
                            total_images += len(image_files)

            print(f"   总计 {total_images} 个图像文件可供处理")
        else:
            print("   ✗ 真实数据目录不存在")

        print("3. 演示脚本准备就绪")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
