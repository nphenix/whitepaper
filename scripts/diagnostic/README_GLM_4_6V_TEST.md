# GLM-4.6V API 调用验证脚本

## 概述

这个脚本用于验证 GLM-4.6V API 的不同调用方式，帮助诊断 API 调用问题。

## 功能

脚本会测试以下4种调用方式：

1. **直接使用 OpenAI SDK**：最原始的方式，直接调用 OpenAI SDK
2. **使用 OpenAI SDK + thinking 参数**：添加 GLM-4.6V 特有的 thinking 参数
3. **使用 OpenAISDKAdapter**：当前实现，通过适配器调用
4. **使用 LLMService**：完整流程，通过 LLMService 获取模型并调用

## 使用方法

### 1. 设置环境变量

```bash
# Windows PowerShell
$env:CHART_TO_JSON_LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4/"
$env:CHART_TO_JSON_LLM_API_KEY="your-api-key-here"
$env:CHART_TO_JSON_LLM_MODEL_NAME="glm-4.6v"

# Linux/Mac
export CHART_TO_JSON_LLM_BASE_URL="https://open.bigmodel.cn/api/paas/v4/"
export CHART_TO_JSON_LLM_API_KEY="your-api-key-here"
export CHART_TO_JSON_LLM_MODEL_NAME="glm-4.6v"
```

### 2. 运行脚本

```bash
# 激活 conda 环境
conda activate lumoscribe2025

# 切换到项目根目录
cd F:\WhitePaper

# 运行脚本（脚本会自动查找项目中的图片文件）
python scripts/diagnostic/test_glm_4_6v_api.py

# 或者指定图片路径
python scripts/diagnostic/test_glm_4_6v_api.py path/to/your/image.jpg
```

## 输出说明

脚本会输出每个测试方法的详细结果：

- ✅ **成功**：调用成功，显示响应内容的前200个字符
- ❌ **失败**：调用失败，显示错误信息

最后会显示测试总结，列出所有成功和失败的方法。

## 诊断建议

1. **如果方法1（直接使用 OpenAI SDK）成功**：
   - 说明 API 配置和网络连接正常
   - 问题可能在于适配器或消息格式转换

2. **如果方法1失败，但方法2（+ thinking）成功**：
   - 说明需要添加 thinking 参数
   - 需要修改 OpenAISDKAdapter 以支持 thinking 参数

3. **如果方法3（OpenAISDKAdapter）失败**：
   - 检查消息格式转换逻辑
   - 检查 base_url 格式
   - 检查参数传递

4. **如果方法4（LLMService）失败**：
   - 检查配置加载
   - 检查模型创建过程
   - 检查完整调用链

## 注意事项

- 确保 API 密钥有效且有足够的配额
- 确保网络连接正常
- 图片文件大小不要太大（建议 < 5MB）
- 脚本会自动查找项目中的图片文件，如果没有找到，需要手动指定路径

