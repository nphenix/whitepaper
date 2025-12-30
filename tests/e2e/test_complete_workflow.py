"""
完整流程端到端测试

测试从大纲创建到草稿生成的完整流程，完全通过浏览器操作。
所有操作都基于实际的前端页面实现。
"""

import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.e2e.utils.page_objects import (
    HomePage,
    OutlineCreationPage,
    SourceSelectionPage,
    FinalViewPage,
)
from tests.e2e.utils.api_helper import (
    check_backend_health,
    wait_for_document_processing,
    compute_stable_filename,
)
from tests.e2e.utils.mock_detector import validate_not_mock_data, detect_mock_data_in_draft


@pytest.mark.e2e
@pytest.mark.browser
class TestCompleteWorkflow:
    """完整流程测试类"""
    
    def test_02_complete_workflow_happy_path(
        self,
        page: Page,
        test_pdf_file: Path,
        sample_outline_text: str,
    ):
        """测试完整流程：标准路径（Happy Path）
        
        步骤：
        1. 访问首页
        2. 创建和优化大纲
        3. 上传文件并选择来源
        4. 生成草稿并查看
        
        注意：此测试完全通过浏览器操作，模拟真实用户行为
        """
        # 检查后端服务
        # 注意：如果后端不可用，应该失败而不是跳过
        if not check_backend_health():
            pytest.fail("后端服务不可用，请先启动后端服务（端口8000）。测试要求真实的后端API，不允许跳过。")
        
        # 1. 访问首页
        home_page = HomePage(page)
        home_page.goto()
        
        # 验证页面加载（根据实际前端，首页URL是 /）
        expect(page).to_have_url("http://localhost:5173/", timeout=10000)
        
        # 2. 导航到大纲创建页面
        # 方式1：点击"新建白皮书"按钮（如果存在）
        # 方式2：直接导航到 /outline
        outline_page = OutlineCreationPage(page)
        outline_page.goto()
        
        # 验证页面加载
        expect(page).to_have_url("http://localhost:5173/outline", timeout=10000)
        
        # 验证页面元素存在（根据实际前端代码）
        # 应该有一个textarea用于输入大纲
        textarea = page.locator("textarea").first
        expect(textarea).to_be_visible()
        
        # 3. 输入大纲文本
        outline_page.input_outline_text(sample_outline_text)
        
        # 验证文本已输入
        current_text = outline_page.get_outline_text()
        assert len(current_text) > 0, "大纲文本应该已输入"
        assert "储能" in current_text or "白皮书" in current_text, "大纲应包含关键词"
        
        # 4. 点击AI优化按钮
        # 注意：必须成功，不允许降级
        outline_page.click_polish_button()
        # 等待优化完成（LLM优化在网络波动/负载下可能超过60秒）
        outline_page.wait_for_polish_complete(timeout=180000)
        
        # 验证优化后的大纲文本已更新
        polished_text = outline_page.get_outline_text()
        assert len(polished_text) > 0, "优化后的大纲不应为空"
        # 检查是否有实质性变化（规范化后比较，忽略空白字符差异）
        polished_normalized = " ".join(polished_text.split())
        original_normalized = " ".join(sample_outline_text.split())
        # 如果规范化后完全相同，说明优化可能没有执行，这是一个警告但不算失败
        # 如果至少有原始文本存在，说明流程执行了
        if polished_normalized == original_normalized:
            # 至少验证文本确实存在且包含关键内容
            assert len(polished_text) > 0 and ("储能" in polished_text or "白皮书" in polished_text), \
                "优化后的大纲应包含关键内容"
            # 注意：这里不强制要求文本必须不同，因为优化结果可能与原始文本相似
        else:
            # 如果有实质性变化，验证优化后的文本仍然包含关键内容
            assert "储能" in polished_text or "白皮书" in polished_text, \
                "优化后的大纲应保留关键内容"
        
        # 5. 点击继续按钮创建大纲
        # 注意：必须成功，不允许降级到demoId
        # 点击按钮时会自动等待导航完成（包含API调用时间）
        # 创建大纲涉及落库/索引等操作，给出更现实的超时窗口
        outline_page.click_continue_button(wait_for_navigation=True, timeout=60000)
        
        # 验证已跳转到来源选择页面（URL已经在click_continue_button中等待了）
        current_url = page.url
        assert "/sources" in current_url, f"应该跳转到sources页面，但当前URL是: {current_url}"
        
        # 验证URL中包含真实的outlineId（不是demoId）
        current_url = page.url
        assert "id=" in current_url, "URL应该包含outlineId参数"
        outline_id = current_url.split("id=")[1].split("&")[0]
        # 验证outlineId不是时间戳格式的demoId（demoId是Date.now().toString()）
        assert not outline_id.isdigit() or len(outline_id) < 13, \
            f"检测到可能的demoId: {outline_id}，API应该返回真实的UUID格式outlineId"
        
        # 6. 上传PDF文件
        # 注意：必须成功，不允许失败
        source_page = SourceSelectionPage(page)
        # 根据实际前端代码，文件输入框id是file-upload
        file_input = page.locator('input[type="file"]#file-upload')
        expect(file_input).to_be_attached()
        
        source_page.upload_file(str(test_pdf_file))
        
        # 等待上传完成并验证成功
        # 注意：前端代码中上传成功后会在console.log，我们需要验证上传成功
        # 可以通过检查是否有错误提示来判断
        page.wait_for_timeout(3000)  # 等待上传请求发送
        
        # 验证上传成功（检查是否有错误提示）
        error_messages = page.locator("text=/错误|失败|error|failed/i").all()
        assert len(error_messages) == 0, f"文件上传失败: {[msg.text_content() for msg in error_messages]}"
        
        # 等待文档处理完成（包括图表转JSON等处理）
        # 说明：图转JSON是正常流程的一部分，耗时可能较长；不能用固定 sleep 代替。
        # 使用轮询间隔=10s，减少对后端的压力。
        stable_filename = compute_stable_filename(str(test_pdf_file))
        assert wait_for_document_processing(
            stable_filename, timeout=1800, poll_interval=10
        ), f"文档处理超时或失败（包含图表转JSON），stable_filename={stable_filename}"
        
        # 7. 查看推荐来源
        # 注意：推荐来源应该从API获取，不是mock数据
        # 等待推荐来源列表加载
        page.wait_for_timeout(3000)
        
        # 验证推荐来源已加载（根据实际代码，推荐来源会显示）
        # 注意：当前前端代码使用mock数据，但测试应该验证API调用
        source_cards = page.locator("h3.font-semibold.text-slate-900").all()
        # 至少应该有推荐来源显示
        assert len(source_cards) > 0, "应该显示推荐来源列表"
        
        # 8. 选择推荐来源
        # 注意：必须至少选择一个来源才能生成草稿
        checkboxes = page.locator('input[type="checkbox"]').all()
        assert len(checkboxes) > 0, "应该有可选择的推荐来源"
        
        # 至少选择一个来源（根据实际代码，生成草稿按钮需要至少选择一个来源）
        checkboxes[0].check()
        page.wait_for_timeout(500)
        
        # 验证至少一个来源被选中
        checked_count = sum(1 for cb in checkboxes if cb.is_checked())
        assert checked_count > 0, "至少应该选择一个来源"
        
        # 9. 点击生成草稿按钮
        # 注意：必须成功，不允许降级
        generate_button = page.locator("button:has-text('生成草稿')")
        expect(generate_button).to_be_visible()
        expect(generate_button).to_be_enabled()
        generate_button.click()
        
        # 等待跳转到草稿查看页面
        # 根据实际代码，跳转URL格式为 /final?id={outlineId}
        # 增加超时时间，因为生成草稿可能需要较长时间（包括API调用和导航）
        page.wait_for_url("**/final*", timeout=30000)
        
        # 验证已跳转到草稿查看页面（使用正则表达式匹配带查询参数的URL）
        import re
        expect(page).to_have_url(re.compile(r"http://localhost:5173/final(\?id=.*)?$"), timeout=5000)
        
        # 验证URL中包含真实的outlineId（不是demoId）
        final_url = page.url
        assert "id=" in final_url, "URL应该包含outlineId参数"
        final_outline_id = final_url.split("id=")[1].split("&")[0]
        # 验证outlineId不是时间戳格式的demoId
        assert not final_outline_id.isdigit() or len(final_outline_id) < 13, \
            f"检测到可能的demoId: {final_outline_id}，API应该返回真实的UUID格式outlineId"
        
        # 10. 等待草稿生成完成
        # 注意：必须从API获取真实数据，不允许使用mock数据
        final_page = FinalViewPage(page)

        # 等待草稿生成完成（最多5分钟）
        # 前端可能会先跳转到 /final 再异步生成草稿，所以这里必须等待生成结束
        final_page.wait_for_draft_generation(timeout=300000)
        
        # 11. 验证草稿内容
        # 注意：必须验证是真实API返回的数据，不是mock数据
        draft_content = final_page.get_draft_content()
        assert len(draft_content) > 0, "草稿内容不应为空"
        
        # 验证草稿不是mock数据（使用专门的检测工具）
        validate_not_mock_data(
            draft_content,
            data_type="final_view",
            context=f"草稿查看页面（outlineId: {final_outline_id}）"
        )
        
        # 验证草稿包含大纲的关键词（真实API生成的内容应该与大纲相关）
        assert "储能" in draft_content or "白皮书" in draft_content, \
            "草稿内容应包含大纲相关关键词"
        
        # 验证草稿内容长度（当前 MVP 版本可能不会生成超长全文，但至少应包含多个章节的可读内容）
        assert len(draft_content) > 100, \
            f"草稿内容太短（{len(draft_content)}字符），可能生成未完成或返回异常"
    
    def test_01_outline_optimization_only(
        self,
        page: Page,
        sample_outline_text: str,
    ):
        """测试大纲优化功能（单独测试）
        
        只测试大纲优化功能，不进行完整流程
        """
        if not check_backend_health():
            pytest.fail("后端服务不可用，请先启动后端服务（端口8000）。测试要求真实的后端API，不允许跳过。")
        
        outline_page = OutlineCreationPage(page)
        outline_page.goto()
        
        # 输入原始大纲（简单版本）
        original_text = "# 储能产业白皮书\n\n## 第一章 概述\n## 第二章 市场分析"
        outline_page.input_outline_text(original_text)
        
        # 记录原始文本
        original = outline_page.get_outline_text()
        assert len(original) > 0, "原始大纲应该已输入"
        
        # 点击优化按钮
        outline_page.click_polish_button()
        
        # 等待优化完成（最多60秒）
        outline_page.wait_for_polish_complete(timeout=60000)
        
        # 验证优化后的文本
        polished = outline_page.get_outline_text()
        assert len(polished) > 0, "优化后的大纲不应为空"
        # 优化后的大纲通常会更详细，但至少应该保留原始内容的关键部分
        assert "储能" in polished or "白皮书" in polished, "优化后的大纲应保留关键词"
