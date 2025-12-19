# 配置管理模块

## 概述

配置管理模块提供了统一的环境变量加载、配置管理和 LLM 服务，支持多种 LLM 提供商的动态加载。

## 特性

- ✅ **统一配置管理**: 使用 Pydantic 定义所有配置项，支持环境变量注入和验证
- ✅ **多提供商支持**: 支持 OpenAI Compatible、Gemini、Anthropic Claude、DashScope
- ✅ **动态模型加载**: 根据环境变量动态选择和加载 LLM 模型
- ✅ **工厂模式 + 单例模式**: 使用工厂模式创建模型，单例模式管理服务
- ✅ **LangChain 1.0 支持**: 支持运行时参数调整

## 快速开始

### 基础使用

```python
from src.shared.config import load_config, get_llm_service

# 加载配置
config = load_config()

# 获取 LLM 服务
llm_service = get_llm_service()
llm_service.set_config(config)

# 获取模型
chat_model = llm_service.get_chat_model()
embedding_model = llm_service.get_embedding_model()
rerank_model = llm_service.get_rerank_model()
```

### 切换提供商

```python
# 切换到不同的提供商
gemini_model = llm_service.get_chat_model("gemini")
anthropic_model = llm_service.get_chat_model("anthropic")
```

## 环境变量配置

所有配置通过环境变量或 `.env` 文件设置：

```bash
# LLM 配置
LLM_PROVIDER=openai_compatible
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL_NAME=your_model_name
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
LLM_TIMEOUT=60

# Embedding 配置
EMBEDDING_PROVIDER=dashscope
EMBEDDING_API_KEY=your_api_key
EMBEDDING_MODEL_NAME=text-embedding-v4

# Rerank 配置
RERANK_PROVIDER=dashscope
RERANK_API_KEY=your_api_key
RERANK_MODEL_NAME=qwen3-rerank
```

## 在代码中使用

**✅ 正确做法**：从 LLM 服务获取模型

```python
from src.shared.config import get_llm_service

class MyAgent:
    def __init__(self):
        self.llm_service = get_llm_service()
        self.llm = self.llm_service.get_chat_model()
```

**❌ 错误做法**：直接创建模型实例（禁止）

```python
# 不要这样做
from langchain_openai import ChatOpenAI
self.llm = ChatOpenAI(...)  # 硬编码，不灵活
```

## 测试

```bash
# 运行单元测试
pytest tests/unit/config/ -v

# 运行集成测试
pytest tests/integration/test_real_api_connectivity.py -v
```

## 注意事项

1. **禁止直接创建模型实例**: 所有 Agent 必须通过 `LLMService` 获取模型
2. **配置优先级**: 环境变量 > 配置文件 > 默认值
3. **缓存机制**: 模型实例会被缓存，配置变更后需要调用 `clear_cache()`
