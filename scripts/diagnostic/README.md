# LLM API SSL连接诊断工具

## 概述

`test_llm_ssl_connection.py` 是一个用于诊断和定位LLM API调用时SSL连接错误的工具。

## 功能

- ✅ 测试SSL握手
- ✅ 测试HTTP连接
- ✅ 测试OpenAI客户端连接
- ✅ 测试LangChain模型连接（实际使用的）
- ✅ 捕获详细的SSL错误信息
- ✅ 提供诊断建议

## 使用方法

### 1. 测试当前配置的LLM API

```bash
# 从环境变量或配置文件读取配置
python scripts/diagnostic/test_llm_ssl_connection.py
```

### 2. 测试指定的API URL

```bash
# 测试智谱AI
python scripts/diagnostic/test_llm_ssl_connection.py \
    --api-url https://open.bigmodel.cn/api/paas/v4 \
    --api-key your_api_key \
    --model-name glm-4

# 测试火山引擎
python scripts/diagnostic/test_llm_ssl_connection.py \
    --api-url https://wanqing.streamlakeapi.com/api/gateway/v1/endpoints \
    --api-key your_api_key \
    --model-name doubao-pro-4k
```

### 3. 测试所有配置的提供商

```bash
python scripts/diagnostic/test_llm_ssl_connection.py --all-providers
```

### 4. 跳过SSL握手测试（仅测试API调用）

```bash
python scripts/diagnostic/test_llm_ssl_connection.py --skip-ssl-handshake
```

## 输出示例

```
✅ 配置加载成功

============================================================
测试: SSL握手 - open.bigmodel.cn
============================================================
✅ 测试成功
SSL版本: TLSv1.3
证书主题: *.bigmodel.cn
证书颁发者: DigiCert Global Root CA

============================================================
测试: HTTP连接 - https://open.bigmodel.cn/api/paas/v4
============================================================
✅ 测试成功
响应时间: 0.45秒

============================================================
测试: LangChain模型 - https://open.bigmodel.cn/api/paas/v4
============================================================
✅ 测试成功
响应时间: 1.23秒

============================================================
测试总结
============================================================
总测试数: 4
成功: 4 ✅
失败: 0 ❌
```

## 错误诊断

如果检测到SSL错误，脚本会显示：

```
❌ 测试失败
错误类型: APIConnectionError
错误信息: Connection error.

🔍 SSL错误详情:
   [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1010)

SSL错误代码: 1
SSL错误库: 20
SSL错误原因: UNEXPECTED_EOF_WHILE_READING
```

## 环境变量

脚本会从以下环境变量读取配置：

- `LLM_BASE_URL`: API基础URL
- `LLM_API_KEY`: API密钥
- `LLM_MODEL_NAME`: 模型名称（可选，默认: gpt-4）

或者从项目的配置文件（`.env`）读取。

## 常见问题

### Q: 如何知道是哪个API端点出问题？

A: 脚本会测试所有配置的端点，并显示每个端点的测试结果。查看"LangChain模型"测试的结果，这是实际使用的连接方式。

### Q: SSL错误可能的原因是什么？

A: 
1. 网络不稳定导致SSL握手中断
2. 防火墙/代理干扰SSL连接
3. API服务器端SSL配置问题
4. 证书验证失败

### Q: 如何修复SSL错误？

A: 
1. 检查网络连接
2. 检查防火墙/代理设置
3. 联系API服务提供商
4. 考虑添加重试机制
5. 检查系统时间是否正确（影响证书验证）

## 注意事项

- 脚本会进行实际的API调用，可能会消耗API配额
- 测试使用最小的请求（max_tokens=5）以节省成本
- 某些API可能需要特定的模型名称，请根据实际情况调整

