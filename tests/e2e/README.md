# 端到端测试代码说明

> **📌 重要**：如果你是第一次运行测试，请先阅读 [测试执行指南](../../docs/testing/e2e-testing-execution-guide.md)
>
> **📚 文档导航**：查看 [测试文档导航](../../docs/testing/README.md) 了解所有文档的阅读顺序

## 安装依赖

### 1. 安装Playwright和pytest插件

```bash
pip install playwright pytest-playwright
```

### 2. 安装浏览器

```bash
playwright install chromium
```

## 运行测试

### 前置条件

**重要**：运行测试前必须确保以下服务已启动：

1. **后端API服务**（端口8000）：
```bash
python -m cli.main api run --host localhost --port 8000
```

2. **前端开发服务器**（端口5173）：
```bash
cd TTsending
npm run dev
```

### 运行所有测试

#### 可视化模式（推荐 - 可以观察测试过程）

```bash
# 运行所有端到端测试（显示浏览器窗口）
pytest tests/e2e/ -v --headed

# 运行完整流程测试（显示浏览器窗口）
pytest tests/e2e/test_complete_workflow.py -v --headed

# 跳过慢速测试（显示浏览器窗口）
pytest tests/e2e/ -m "not slow" -v --headed
```

**说明**：
- `--headed` 参数会让浏览器以可见模式运行，你可以实时观察测试过程
- 浏览器会自动打开并执行所有操作，便于调试和验证
- **推荐使用此方式**，可以确认测试是否正确执行

#### 无头模式（后台运行，速度更快）

```bash
# 运行所有端到端测试（无头模式，不显示浏览器）
pytest tests/e2e/ -v

# 运行完整流程测试（无头模式）
pytest tests/e2e/test_complete_workflow.py -v

# 跳过慢速测试（无头模式）
pytest tests/e2e/ -m "not slow" -v
```

**说明**：
- 默认是headless模式（无头模式），浏览器在后台运行
- 速度更快，适合CI/CD环境
- 测试失败时会自动截图保存到 `test-results/e2e/` 目录

### 调试模式

如果测试失败，可以：

1. **查看浏览器操作**：
   - 使用 `--headed` 参数运行测试，可以看到浏览器操作过程
   - 示例：`pytest tests/e2e/ -v --headed`
2. **暂停测试**：在测试代码中添加 `page.pause()` 可以暂停测试进行调试
3. **截图和Trace**：测试失败时自动截图和trace保存到 `test-results/e2e/` 目录
   - 截图：`test-results/e2e/{test_name}_{timestamp}.png`
   - Trace：`test-results/e2e/{test_name}_{timestamp}.trace.zip`
   - 可以使用 `playwright show-trace` 命令查看trace文件

## 测试文件说明

- `conftest.py`: 测试配置和fixtures
- `test_complete_workflow.py`: 完整流程测试（从大纲创建到草稿生成）
- `test_document_processing.py`: 文档上传和处理测试
- `utils/page_objects.py`: 页面对象模型，封装页面操作
- `utils/api_helper.py`: API辅助函数，用于验证后端数据

## 注意事项

1. 测试使用真实的前端页面，需要前端服务运行
2. 测试会调用真实的API，需要后端服务运行
3. 测试使用真实的PDF文件（从 `data/source/uploads/` 目录）
4. 草稿生成测试可能需要较长时间（标记为 `@pytest.mark.slow`）

## 重要原则

### 不允许使用模拟数据

- ✅ **所有测试必须使用真实API数据**
- ✅ **不允许前端降级到mock数据**
- ✅ **如果检测到mock数据，测试必须失败**

### 不允许降级或跳过

- ✅ **测试遇到错误必须失败，不允许使用try-except捕获后继续**
- ✅ **如果后端服务不可用，测试必须失败（使用pytest.fail而不是pytest.skip）**
- ✅ **如果API调用失败，测试必须失败，不允许降级到mock数据**

### Mock数据检测

测试使用 `mock_detector.py` 工具自动检测mock数据：
- 检测草稿内容是否是mock数据
- 检测推荐来源是否是mock数据
- 如果检测到mock数据，会抛出详细的错误信息

## 在Cursor中运行

如果Cursor已配置Playwright MCP，可以直接在Cursor中运行测试。否则，使用命令行运行。
