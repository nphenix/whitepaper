"""
端到端测试配置和fixtures

使用Playwright进行浏览器自动化测试。
注意：使用pytest-playwright插件，需要先安装：
  pip install pytest-playwright
  playwright install chromium
"""

import pytest
from datetime import datetime
from pathlib import Path
from playwright.sync_api import Page, expect

# 前端和后端URL配置
FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://localhost:8000"


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """让 fixture 能在 teardown 阶段感知用例是否失败"""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture
def page(page: Page, request: pytest.FixtureRequest) -> Page:
    """创建页面并访问前端首页
    
    注意：这个fixture依赖于pytest-playwright提供的page fixture
    """
    artifacts_dir = Path("test-results") / "e2e"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # 启用 tracing（失败时导出，便于定位卡在哪一步/哪个请求）
    try:
        page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
    except Exception:
        # tracing 不应影响测试
        pass

    # 自动关闭浏览器弹窗（alert/confirm/prompt）。
    # 端到端用例中出现 alert 往往意味着错误分支；不处理会导致 Playwright 等待卡死。
    try:
        page.on("dialog", lambda dialog: dialog.dismiss())
    except Exception:
        pass

    # 访问前端首页
    try:
        # 对 SPA（Vite/React）不建议使用 networkidle：常驻连接/轮询会导致永远不“空闲”
        page.goto(FRONTEND_URL, wait_until="domcontentloaded", timeout=10000)
    except Exception as e:
        pytest.skip(f"无法连接到前端服务 {FRONTEND_URL}: {e}")
    
    yield page

    # --- teardown: 失败时保存诊断信息 ---
    failed = bool(getattr(request.node, "rep_call", None) and request.node.rep_call.failed)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_name = request.node.name.replace("/", "_").replace("\\", "_").replace(":", "_")

    if failed:
        try:
            # URL
            (artifacts_dir / f"{test_name}_{ts}.url.txt").write_text(page.url, encoding="utf-8")
        except Exception:
            pass
        try:
            # Screenshot
            page.screenshot(path=str(artifacts_dir / f"{test_name}_{ts}.png"), full_page=True)
        except Exception:
            pass
        try:
            # Trace
            page.context.tracing.stop(path=str(artifacts_dir / f"{test_name}_{ts}.trace.zip"))
        except Exception:
            pass
    else:
        try:
            page.context.tracing.stop()
        except Exception:
            pass


@pytest.fixture(scope="session")
def test_pdf_file() -> Path:
    """获取测试PDF文件"""
    uploads_dir = Path("data/source/uploads")
    if not uploads_dir.exists():
        pytest.skip(f"测试文件目录不存在: {uploads_dir}")
    
    pdf_files = list(uploads_dir.glob("*.pdf"))
    if not pdf_files:
        pytest.skip(f"在 {uploads_dir} 目录下没有找到PDF测试文件")
    
    return pdf_files[0]


@pytest.fixture
def sample_outline_text() -> str:
    """示例大纲文本"""
    return """# 储能产业白皮书

## 第一章 储能行业发展概况
- 储能技术分类
- 市场发展现状
- 政策环境分析

## 第二章 储能技术发展趋势
- 锂离子电池技术
- 钠离子电池技术
- 新型储能技术

## 第三章 储能市场前景
- 市场规模预测
- 投资机会分析
- 风险与挑战
"""


@pytest.fixture
def test_industry_id() -> str:
    """测试行业ID（储能）"""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def test_database_id() -> str:
    """测试数据库ID"""
    return "550e8400-e29b-41d4-a716-446655440001"
