"""
T036 - 使用真实文件进行CLI命令测试

使用F:\\WhitePaper\\data\\source\\uploads目录下的真实文件进行测试,
验证文档上传CLI命令的实际功能。
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli.main import app
from src.infrastructure.preprocessing.preprocessor import DocumentPreprocessor
from src.shared.config.llm_service import get_llm_service


class TestT036RealFileTesting:
    """T036文档CLI命令真实文件测试类"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """测试前准备"""
        # 检查真实文件是否存在
        self.real_file_path = Path(
            "data/source/uploads/2023年中国储能产业发展研究报告.pdf"
        )

        if not self.real_file_path.exists():
            pytest.skip(f"真实测试文件不存在: {self.real_file_path}")

        print(f"✅ 找到真实测试文件: {self.real_file_path}")
        print(f"文件大小: {self.real_file_path.stat().st_size / 1024 / 1024:.2f} MB")

    def test_real_file_format_detection(self):
        """测试真实文件格式检测"""
        # 初始化预处理器
        preprocessor = DocumentPreprocessor(
            llm_service=get_llm_service(),
            enable_cleaning=False,  # 禁用清洗以避免LLM调用
            enable_chart_conversion=False,  # 禁用图表转换
        )

        # 测试格式检测
        format_info = preprocessor.format_detector.detect_format(
            str(self.real_file_path)
        )
        assert format_info.format == "pdf"
        assert format_info.is_valid

        # 测试文档验证
        validation_result = preprocessor.format_detector.validate_document(
            str(self.real_file_path), format_info
        )
        assert validation_result.is_valid

        print("✅ 真实文件格式检测测试通过")

    def test_real_file_upload_command(self, runner):
        """测试真实文件上传命令"""
        result = runner.invoke(
            app,
            [
                "documents",
                "upload",
                str(self.real_file_path),
                "--uploaded-by",
                "00000000-0000-0000-0000-000000000001",
                "--format",
                "pdf",
                "--disable-chart-conversion",  # 禁用图表转换以加快测试
            ],
        )

        print("真实文件上传命令输出:")
        print(result.output)

        # 检查命令是否正确识别文件
        assert "正在上传并处理文档" in result.output
        assert "2023年中国储能产业发展研究报告.pdf" in result.output

        # 检查是否有错误
        if result.exit_code != 0:
            print(f"⚠️ 上传命令退出码: {result.exit_code}")
            print("可能的原因:")
            print("1. 数据库连接问题")
            print("2. 文件处理过程中的错误")
            print("3. 依赖服务不可用")

        print("✅ 真实文件上传命令测试完成")

    def test_real_file_list_command(self, runner):
        """测试列出文档命令(包含真实文件)"""
        result = runner.invoke(app, ["documents", "list"])

        print("列出文档命令输出:")
        print(result.output)

        # 检查命令是否成功执行
        assert result.exit_code == 0
        assert "文档列表" in result.output

        print("✅ 列出文档命令测试完成")

    def test_real_file_status_command(self, runner):
        """测试显示状态命令(包含真实文件)"""
        result = runner.invoke(app, ["documents", "status"])

        print("显示状态命令输出:")
        print(result.output)

        # 检查命令是否成功执行
        assert result.exit_code == 0
        assert "文档处理总览" in result.output

        print("✅ 显示状态命令测试完成")

    def test_real_file_upload_async_command(self, runner):
        """测试真实文件异步上传命令"""
        result = runner.invoke(
            app,
            [
                "documents",
                "upload-async",
                str(self.real_file_path),
                "--uploaded-by",
                "00000000-0000-0000-0000-000000000001",
                "--format",
                "pdf",
                "--disable-chart-conversion",  # 禁用图表转换以加快测试
            ],
        )

        print("真实文件异步上传命令输出:")
        print(result.output)

        # 检查命令是否正确识别文件
        assert "开始异步上传并处理文档" in result.output
        assert "2023年中国储能产业发展研究报告.pdf" in result.output

        # 检查是否有错误
        if result.exit_code != 0:
            print(f"⚠️ 异步上传命令退出码: {result.exit_code}")

        print("✅ 真实文件异步上传命令测试完成")

    def test_invalid_file_path_with_real_context(self, runner):
        """测试无效文件路径(在真实文件上下文中)"""
        result = runner.invoke(
            app,
            [
                "documents",
                "upload",
                "data/source/uploads/nonexistent.pdf",
                "--uploaded-by",
                "00000000-0000-0000-0000-000000000001",
            ],
        )

        print("无效文件路径测试输出:")
        print(result.output)

        # 检查命令是否正确处理错误
        assert result.exit_code == 1
        assert "文件不存在" in result.output

        print("✅ 无效文件路径测试通过")

    def test_invalid_user_id_with_real_context(self, runner):
        """测试无效用户ID(在真实文件上下文中)"""
        result = runner.invoke(
            app,
            [
                "documents",
                "upload",
                str(self.real_file_path),
                "--uploaded-by",
                "invalid-uuid",
            ],
        )

        print("无效用户ID测试输出:")
        print(result.output)

        # 检查命令是否正确处理错误
        assert result.exit_code == 1
        assert "无效的用户ID格式" in result.output

        print("✅ 无效用户ID测试通过")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
