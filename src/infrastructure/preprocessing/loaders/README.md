# 文档加载器模块

该模块包含文档加载器的基础接口和实现，用于加载不同格式的文档到LangChain Document对象。

## 基础接口

### BaseLoader

所有文档加载器都必须继承自`BaseLoader`抽象基类，该类提供了以下功能：

- 标准化的文档加载接口，兼容LangChain 1.0规范
- 同步和异步加载支持
- 流式加载支持（处理大文件）
- 文档格式自动检测
- 标准元数据管理（source、format、loaded_at等）

### 核心方法

- `load()`: 加载文档并返回`List[Document]`（必须实现）
- `lazy_load()`: 懒加载文档，支持流式处理（可选实现）
- `aload()`: 异步加载文档
- `alazy_load()`: 异步懒加载文档
- `can_handle(source)`: 检查是否能处理指定的文档
- `get_supported_formats()`: 获取支持的文档格式列表

### 使用示例

```python
from src.infrastructure.preprocessing.loaders import BaseLoader

class MyLoader(BaseLoader):
    def load(self) -> List[Document]:
        # 实现加载逻辑
        documents = []
        # ... 加载文档内容
        return documents
    
    def get_supported_formats(self) -> List[str]:
        return ["txt", "md"]

# 使用加载器
loader = MyLoader("example.txt")
documents = loader.load()
```

## 异常类

模块提供了以下异常类：

- `LoaderError`: 文档加载器异常基类
- `UnsupportedFormatError`: 不支持的文档格式异常
- `DocumentNotFoundError`: 文档未找到异常
- `DocumentParsingError`: 文档解析异常

## MinerU适配器

### MinerUAdapter

MinerU在线服务适配器，用于封装MinerU API调用，支持PDF和DOCX格式的文档解析。

**功能特性：**
- 封装MinerU在线服务API调用
- 支持PDF和DOCX格式解析
- 统一的响应格式转换（转换为LangChain Document格式）
- 完善的错误处理和日志记录
- 服务配置管理（从settings.py读取配置）
- 服务健康检查和错误重试机制（使用tenacity库）
- 支持异步处理，避免阻塞主流程

**配置要求：**

在`.env`文件中配置以下环境变量：

```env
MINERU_API_KEY=your_api_key_here
MINERU_API_URL=https://mineru.net/api
MINERU_TIMEOUT=300
MINERU_MAX_RETRIES=3
MINERU_MAX_FILE_SIZE_MB=200
MINERU_MAX_PAGES=600
```

**使用示例：**

```python
from src.infrastructure.preprocessing.loaders import MinerUAdapter

# 创建适配器实例（自动从settings.py读取配置）
adapter = MinerUAdapter()

# 同步提取文档
documents = adapter.extract("document.pdf")
for doc in documents:
    print(doc.page_content)
    print(doc.metadata)

# 异步提取文档
import asyncio
async def main():
    documents = await adapter.aextract("document.docx")
    for doc in documents:
        print(doc.page_content)

asyncio.run(main())

# 健康检查
is_healthy = adapter.health_check()
print(f"MinerU服务状态: {'健康' if is_healthy else '异常'}")
```

**异常处理：**

适配器提供了以下异常类（统一在`error_handler.py`中定义）：

- `MinerUAdapterError`: MinerU适配器异常基类（继承自`PreprocessingError`）
- `MinerUAPIError`: MinerU API调用异常
- `MinerUConfigError`: MinerU配置错误
- `MinerUFileError`: MinerU文件处理错误

**注意**: 所有异常类现在统一在`src/infrastructure/preprocessing/error_handler.py`中定义，遵循DRY原则，避免重复定义。

**参考文档：**
- MinerU API文档: https://mineru.net/apiManage/docs

## LangChain 1.0兼容性

该模块完全兼容LangChain 1.0规范：

- 使用`langchain_core.documents.Document`作为标准文档格式
- 实现标准的`load()`方法返回`List[Document]`
- 支持元数据标准（source、format等）
- 提供异步加载支持