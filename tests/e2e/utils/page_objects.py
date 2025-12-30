"""
页面对象模型（Page Object Model）

封装页面操作，提高测试代码的可维护性。
"""

import re

from playwright.sync_api import Page, Locator, expect
from typing import Optional


class BasePage:
    """基础页面类"""
    
    def __init__(self, page: Page, base_url: str = "http://localhost:5173"):
        self.page = page
        self.base_url = base_url
    
    def goto(self, path: str = ""):
        """导航到页面"""
        url = f"{self.base_url}/{path}" if path else self.base_url
        # 对 SPA（Vite/React）不建议使用 networkidle：常驻连接/轮询会导致永远不“空闲”
        self.page.goto(url, wait_until="domcontentloaded")
    
    def wait_for_load(self, timeout: int = 10000):
        """等待页面加载完成"""
        self.page.wait_for_load_state("domcontentloaded", timeout=timeout)


class HomePage(BasePage):
    """首页"""
    
    def click_new_whitepaper(self):
        """点击"新建白皮书"按钮"""
        self.page.click("text=新建白皮书", timeout=5000)
    
    def navigate_to_outline(self):
        """导航到大纲创建页面"""
        self.goto("outline")


class OutlineCreationPage(BasePage):
    """大纲创建页面"""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = f"{self.base_url}/outline"
    
    def goto(self):
        """导航到大纲创建页面"""
        super().goto("outline")
        self.wait_for_load()
    
    def input_outline_text(self, text: str):
        """输入大纲文本
        
        根据实际前端代码，大纲输入框是一个textarea元素
        """
        textarea = self.page.locator("textarea").first
        textarea.fill(text)
        # 等待输入完成
        self.page.wait_for_timeout(500)
    
    def get_outline_text(self) -> str:
        """获取当前大纲文本"""
        textarea = self.page.locator("textarea").first
        return textarea.input_value()
    
    def click_polish_button(self):
        """点击"AI润色优化"按钮
        
        根据实际前端代码，按钮文本是"AI润色优化"
        """
        # 等待按钮可点击
        polish_button = self.page.locator("button:has-text('AI润色优化')")
        polish_button.wait_for(state="visible", timeout=5000)
        polish_button.click()
    
    def wait_for_polish_complete(self, timeout: int = 60000):
        """等待AI优化完成
        
        通过检查按钮文本变化来判断优化是否完成
        优化中按钮显示"AI优化中..."，完成后恢复为"AI润色优化"
        
        注意：如果超时或失败，会抛出异常，不允许降级
        """
        # 点击后按钮文本会从“AI润色优化”切换到“AI优化中...”，
        # 完成后恢复为“AI润色优化”并重新启用。
        polish_button = self.page.locator("button").filter(
            has_text=re.compile(r"AI润色优化|AI优化中")
        )
        expect(polish_button).to_be_visible(timeout=5000)

        # 等待期间如果前端已展示错误提示，立即失败（不要傻等到超时）
        polish_error = self.page.locator("[data-testid='polish-error']")
        import time

        start = time.time()
        poll_ms = 250
        while (time.time() - start) * 1000 < timeout:
            if polish_error.count() > 0 and polish_error.is_visible():
                raise Exception(f"AI优化失败: {polish_error.text_content() or ''}")

            try:
                # 期望按钮恢复可用
                expect(polish_button).to_be_enabled(timeout=poll_ms)
                return
            except Exception:
                # 继续轮询
                self.page.wait_for_timeout(poll_ms)

        # 超时后再给出更明确的信息（优先报 UI 错误）
        if polish_error.count() > 0 and polish_error.is_visible():
            raise Exception(f"AI优化失败: {polish_error.text_content() or ''}")
        raise TimeoutError("等待AI优化完成超时：按钮未恢复可点击状态")
    
    def click_continue_button(self, wait_for_navigation: bool = True, timeout: int = 30000):
        """点击"继续"按钮创建大纲
        
        根据实际前端代码，按钮文本是"继续"
        
        Args:
            wait_for_navigation: 是否等待导航完成
            timeout: 超时时间（毫秒）
        """
        continue_button = self.page.locator("button:has-text('继续')")
        continue_button.wait_for(state="visible", timeout=5000)
        
        # 记录当前 URL
        current_url = self.page.url
        
        # 点击按钮（React Router 使用客户端导航，不会触发完整的页面导航事件）
        continue_button.click()
        
        if wait_for_navigation:
            # 等待按钮状态变化（处理中...），表示 API 调用已开始
            try:
                # 等待按钮文本变为"处理中..."
                self.page.wait_for_selector("button:has-text('处理中...')", timeout=2000, state="visible")
            except Exception:
                # 如果没有"处理中..."状态，继续等待
                pass
            
            # 使用轮询方式等待 URL 变化（更可靠，适合 React Router）
            # 因为 React Router 使用客户端路由，wait_for_url 可能不够可靠
            import time
            start_time = time.time()
            check_interval = 300  # 每300ms检查一次
            
            while time.time() - start_time < timeout / 1000:
                new_url = self.page.url
                if "/sources" in new_url and new_url != current_url:
                    return  # 成功导航到 sources 页面
                
                # 检查是否有错误提示（如果 API 调用失败，可能会显示错误）
                error_elements = self.page.locator("text=/错误|失败|error|failed/i").all()
                if len(error_elements) > 0:
                    error_texts = [elem.text_content() for elem in error_elements if elem.text_content()]
                    raise Exception(f"检测到错误提示: {error_texts}")
                
                self.page.wait_for_timeout(check_interval)
            
            # 如果超时，检查当前状态
            final_url = self.page.url
            if "/sources" not in final_url:
                # 检查按钮是否还在"处理中..."状态（说明 API 调用可能卡住了）
                is_processing = self.page.locator("button:has-text('处理中...')").count() > 0
                if is_processing:
                    raise TimeoutError(
                        f"API调用超时（按钮仍在'处理中...'状态）。当前URL: {final_url}, 原始URL: {current_url}"
                    )
                else:
                    raise TimeoutError(
                        f"等待导航到 sources 页面超时。当前URL: {final_url}, 原始URL: {current_url}"
                    )
    
    def wait_for_navigation_to_sources(self, timeout: int = 10000):
        """等待跳转到来源选择页面"""
        self.page.wait_for_url("**/sources*", timeout=timeout)


class SourceSelectionPage(BasePage):
    """来源选择页面"""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = f"{self.base_url}/sources"
    
    def goto(self, outline_id: Optional[str] = None):
        """导航到来源选择页面"""
        if outline_id:
            super().goto(f"sources?id={outline_id}")
        else:
            super().goto("sources")
        self.wait_for_load()
    
    def upload_file(self, file_path: str, timeout: int = 1800000):
        """上传文件
        
        根据实际前端代码，文件输入框的id是"file-upload"，隐藏在label后面
        
        注意：如果上传失败，会抛出异常，不允许降级
        """
        # 查找文件输入框（根据实际代码，id是file-upload）
        file_input = self.page.locator('input[type="file"]#file-upload')
        file_input.wait_for(state="attached", timeout=5000)
        file_input.set_input_files(file_path)

        # 前端会在上传/处理期间展示 uploading indicator；必须等待其结束，否则可能在处理中就进入下一步，导致请求被导航取消
        uploading = self.page.locator("[data-testid='uploading-indicator']")
        uploading.wait_for(state="visible", timeout=5000)
        uploading.wait_for(state="hidden", timeout=timeout)

        # 如果有明确的错误提示，立刻失败（不允许兜底）
        upload_error = self.page.locator("[data-testid='upload-error']")
        if upload_error.count() > 0 and upload_error.is_visible():
            raise Exception(f"文件上传失败: {upload_error.text_content() or ''}")
    
    def get_recommended_sources(self) -> list:
        """获取推荐来源列表
        
        根据实际前端代码，推荐来源显示在卡片中，每个卡片包含标题、作者等信息
        """
        sources = []
        # 根据实际代码，来源卡片包含标题（h3元素）
        source_cards = self.page.locator("h3.font-semibold.text-slate-900").all()
        
        for card in source_cards:
            title = card.text_content() or ""
            sources.append({"title": title})
        
        return sources
    
    def select_source(self, index: int = 0):
        """选择推荐来源（通过索引）
        
        根据实际前端代码，每个来源卡片内有一个checkbox
        """
        # 获取所有checkbox（在来源卡片内的）
        checkboxes = self.page.locator('input[type="checkbox"]').all()
        if index < len(checkboxes):
            checkboxes[index].check()
            # 等待选择状态更新
            self.page.wait_for_timeout(500)
    
    def add_custom_url(self, url: str):
        """添加自定义URL
        
        根据实际前端代码，URL输入框是type="url"，placeholder包含"例如:"
        """
        url_input = self.page.locator('input[type="url"]').first
        url_input.wait_for(state="visible", timeout=5000)
        url_input.fill(url)
        # 点击"添加"按钮
        add_button = self.page.locator("button:has-text('添加')")
        add_button.click()
        self.page.wait_for_timeout(500)
    
    def click_generate_draft_button(self):
        """点击"生成草稿"按钮
        
        根据实际前端代码，按钮文本是"生成草稿"
        """
        generate_button = self.page.locator("button:has-text('生成草稿')")
        generate_button.wait_for(state="visible", timeout=5000)
        generate_button.click()
    
    def wait_for_navigation_to_final(self, timeout: int = 10000):
        """等待跳转到草稿查看页面"""
        self.page.wait_for_url("**/final*", timeout=timeout)


class FinalViewPage(BasePage):
    """草稿查看页面"""
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.url = f"{self.base_url}/final"
    
    def goto(self, outline_id: Optional[str] = None):
        """导航到草稿查看页面"""
        if outline_id:
            super().goto(f"final?id={outline_id}")
        else:
            super().goto("final")
        self.wait_for_load()
    
    def wait_for_draft_generation(self, timeout: int = 300000):
        """等待草稿生成完成（最多5分钟）"""
        # FinalView 在 isLoading=true 时会只显示“生成中...”
        loading = self.page.locator("text=生成中...")
        editor = self.page.locator("[data-testid='rich-text-editor']")
        draft_error = self.page.locator("[data-testid='draft-error']")

        import time

        start = time.time()
        poll_ms = 500
        while (time.time() - start) * 1000 < timeout:
            # 如果出现明确错误提示，立即失败（避免等待到超时）
            try:
                if draft_error.count() > 0 and draft_error.first.is_visible():
                    raise Exception(f"草稿生成失败: {draft_error.text_content() or ''}")
            except Exception:
                raise

            # editor 出现即可认为页面已进入“可编辑”状态（内容可能仍在填充）
            try:
                if editor.count() > 0 and editor.first.is_visible():
                    return
            except Exception:
                pass

            # 仍在 loading：继续等
            try:
                if loading.count() > 0 and loading.first.is_visible():
                    self.page.wait_for_timeout(poll_ms)
                    continue
            except Exception:
                pass

            # 既不是 loading 也没 editor：给 UI 一点时间渲染
            self.page.wait_for_timeout(poll_ms)

        # 超时后提供更可读的错误
        if loading.count() > 0 and loading.first.is_visible():
            raise TimeoutError("等待草稿生成超时：页面仍停留在“生成中...”")
        raise TimeoutError("等待草稿生成超时：未检测到草稿编辑器渲染完成")
    
    def get_draft_content(self) -> str:
        """获取草稿内容
        
        根据实际前端代码，草稿使用RichTextEditor组件，内容是HTML格式
        编辑器应该是contenteditable元素
        """
        # 尝试查找RichTextEditor的内容区域
        # 根据实际代码，可能是contenteditable的div
        editor_locator = self.page.locator("[contenteditable='true']")
        if editor_locator.count() > 0:
            editor = editor_locator.first
            return editor.text_content() or editor.inner_html() or ""
        
        # 如果找不到，尝试查找包含草稿内容的区域
        draft_locator = self.page.locator(".bg-white.rounded-xl")
        if draft_locator.count() > 0:
            draft_area = draft_locator.first
            return draft_area.text_content() or ""
        
        return ""
    
    def verify_draft_contains(self, text: str) -> bool:
        """验证草稿内容包含指定文本"""
        content = self.get_draft_content()
        return text.lower() in content.lower()
