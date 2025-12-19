# 测试框架说明

## 目录结构

```
tests/
├── conftest.py              # 全局测试夹具
├── unit/                    # 单元测试
│   └── config/              # 配置模块单元测试
├── integration/             # 集成测试
└── contract/               # 契约测试
```

## 运行测试

### 运行所有测试
```bash
pytest
```

### 运行特定类型
```bash
# 单元测试
pytest -m unit

# 集成测试
pytest -m integration

# 跳过慢速测试
pytest -m "not slow"
```

### 运行特定目录
```bash
pytest tests/unit/
pytest tests/integration/
```

### 生成覆盖率报告
```bash
pytest --cov=src --cov-report=html
```

## 测试标记

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.slow` - 慢速测试

## 常用夹具

- `temp_dir` - 临时目录
- `sample_text_file` - 示例文本文件
- `mock_llm` - 模拟LLM客户端
- `mock_embedding_model` - 模拟嵌入模型

## 最佳实践

1. 测试文件名应为 `test_*.py`
2. 测试函数名应以 `test_` 开头
3. 使用标记分类测试
4. 确保测试之间相互独立
