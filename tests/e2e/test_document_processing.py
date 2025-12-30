"""
文档处理测试

测试文档上传和处理功能，通过浏览器操作。
"""

import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.e2e.utils.page_objects import SourceSelectionPage
from tests.e2e.utils.api_helper import (
    check_backend_health,
    wait_for_document_processing,
    compute_stable_filename,
)


@pytest.mark.e2e
@pytest.mark.browser
class TestDocumentProcessing:
    """文档处理测试类"""
    
    def test_upload_pdf_file(
        self,
        page: Page,
        test_pdf_file: Path,
    ):
        """测试上传PDF文件"""
        if not check_backend_health():
            pytest.skip("后端服务不可用，跳过测试")
        
        # 导航到来源选择页面
        source_page = SourceSelectionPage(page)
        source_page.goto()
        
        # 上传文件
        source_page.upload_file(str(test_pdf_file))
        
        # 等待上传请求发送
        page.wait_for_timeout(3000)
        
        # 验证上传成功（根据实际UI实现调整）
        # 可能显示成功提示、文件列表更新等
        error_messages = page.locator("text=/错误|失败|error|failed/i").all()
        assert len(error_messages) == 0, f"文件上传失败: {[msg.text_content() for msg in error_messages]}"
        
        # 等待文档处理完成（包括图表转JSON等处理）
        stable_filename = compute_stable_filename(str(test_pdf_file))
        assert wait_for_document_processing(
            stable_filename, timeout=1800, poll_interval=10
        ), f"文档处理超时或失败（包含图表转JSON），stable_filename={stable_filename}"
    
    def test_upload_invalid_file_format(
        self,
        page: Page,
        tmp_path: Path,
    ):
        """测试上传无效文件格式
        
        注意：后端实际支持的格式是 pdf, docx, html
        txt 虽然在 API Schema 中定义了，但实际处理不支持
        使用 .exe 作为无效格式进行测试
        """
        if not check_backend_health():
            pytest.skip("后端服务不可用，跳过测试")
        
        # 创建一个无效格式的文件（使用 .exe 作为完全不被支持的格式）
        invalid_file = tmp_path / "test.exe"
        invalid_file.write_bytes(b"MZ\x90\x00")  # 写入一些二进制数据模拟可执行文件
        
        source_page = SourceSelectionPage(page)
        source_page.goto()
        
        # 尝试上传无效格式文件
        # 注意：应明确失败（前端会展示 upload-error，page object 会抛异常）
        with pytest.raises(Exception):
            source_page.upload_file(str(invalid_file))
        # 等待处理完成或失败（无效格式可能会更快失败）
        page.wait_for_timeout(3000)
        
        # 验证应该显示错误提示（根据实际UI实现调整）
        # 可能显示错误消息、文件处理失败等
        # 如果前端有格式验证，可能会直接拒绝；如果没有，会在后端处理时失败
        error_messages = page.locator("text=/错误|失败|error|failed|不支持|invalid|格式/i").all()
        # 如果没有错误提示，至少应该验证文件没有被成功处理
        # （这个测试的主要目的是确保系统不会静默接受无效格式）
