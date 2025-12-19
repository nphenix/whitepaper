# 快速开始指南: 多 Agent 协作的文档处理与生成系统

**创建时间**: 2025-12-05  
**最后更新**: 2025-12-10  
**当前状态**: 阶段1（设置）和阶段2（基础）已完成 ✅

## 概述

本指南帮助开发者快速搭建和运行系统，包括环境配置、依赖安装、数据库初始化、服务启动等步骤。

## 前置要求

- Python 3.12
- Conda环境管理器
- Git
- Windows 11 (开发环境)

## 环境设置

### 1. 创建Conda环境

```bash
conda create -n whitepaper python=3.12
conda activate whitepaper
```

### 2. 安装依赖

```bash
# 克隆仓库
git clone <repository-url>
cd whitepaper

# 安装Python依赖
pip install -r requirements.txt
```

**主要依赖包**:
- langchain>=1.0.0
- langgraph>=0.1.0
- langmem>=0.1.0
- llama-index>=0.10.0
- python-docx>=1.1.0  # DOCX文档处理
- fastapi>=0.104.0
- arq>=0.25.0
- fastmcp>=0.1.0
- typer>=0.9.0
- rich>=13.7.0
- paddleocr>=2.7.0
- chromadb>=0.4.0
- networkx>=3.2.0
- ruff>=0.1.0
- mypy>=1.7.0

### 3. 配置环境变量

创建 `.env` 文件（参考 `.env.example`）：

```bash
# 复制环境变量模板
# Windows:
copy .env.example .env

# Linux/Mac:
cp .env.example .env
```

然后编辑 `.env` 文件，配置以下**必需的**环境变量：

```env
# LLM 模型配置（必需）
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=your_api_base_url
LLM_API_KEY=your_api_key
LLM_MODEL_NAME=your_model_name
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
LLM_TIMEOUT=60

# Embedding 模型配置（必需）
EMBEDDING_PROVIDER=dashscope
EMBEDDING_API_KEY=your_dashscope_api_key
EMBEDDING_MODEL_NAME=text-embedding-v4
EMBEDDING_DIMENSION=1536
EMBEDDING_BATCH_SIZE=32

# Rerank 模型配置（必需）
RERANK_PROVIDER=dashscope
RERANK_API_KEY=your_dashscope_api_key
RERANK_MODEL_NAME=qwen3-rerank
RERANK_TOP_K=10

# 数据库配置
DATABASE__SQLITE_DB_PATH=./storage/sqlite/whitepaper.db
DATABASE__CHROMA_DB_PATH=./storage/chroma
DATABASE__NETWORKX_GRAPH_PATH=./storage/networkx/knowledge_graph.pkl

# Redis 配置（Arq任务队列需要）
REDIS__REDIS_URL=redis://localhost:6379/0

# API 配置
API__HOST=0.0.0.0
API__PORT=8000

# 日志配置
LOG__LEVEL=INFO
LOG__FILE=./data/logs/app.log
```

**状态**: ✅ 已完成 - 配置管理模块已实现（T009），支持Pydantic Settings自动加载环境变量。所有配置项必须通过.env文件配置，无硬编码默认值。LangChain 1.0动态模型统一集中配置服务已实现，支持多种LLM提供商动态加载。

**注意**: `.env.example` 文件已更新（2025-12-10），包含所有必需的配置项和阶段标记。请参考该文件了解完整的配置选项。配置项使用嵌套格式（如 `DATABASE__SQLITE_DB_PATH`），这是 Pydantic Settings 的标准格式。

## 数据库初始化

### 1. 初始化SQLite数据库

```bash
# 运行数据库迁移脚本
python scripts/migration/init_db.py init
```

这将创建以下表：
- documents (文档表)
- users (用户表)
- knowledge_entries (知识库条目表)
- outlines (大纲表)
- drafts (文稿表)
- memory_entries (记忆条目表)
- templates (模板表)

**状态**: ✅ 已完成 - 数据库迁移框架已实现（T015），支持init、migrate、rollback、status等命令

### 2. 初始化Chroma向量数据库

```bash
# Chroma会在首次使用时自动创建
# 确保CHROMA_DB_PATH目录存在
mkdir -p data/chroma
```

**状态**: ✅ 已完成 - Chroma适配器和连接管理器已实现（T013），支持本地和远程连接

### 3. 初始化NetworkX知识图谱

```bash
# 知识图谱会在首次使用时自动创建
# 确保数据目录存在
mkdir -p data
```

**状态**: ✅ 已完成 - NetworkX适配器和图管理器已实现（T014），支持多种图类型和持久化

### 4. 创建文档处理目录

```bash
# 创建MinerU处理结果目录
mkdir -p data/processed/mineru

# 创建归档目录（存放原始MinerU处理结果）
mkdir -p data/archive/mineru

# 创建清洗后文档目录（存放清洗后的文档）
mkdir -p data/cleaned/documents
```

**状态**: ✅ 已完成 - 文档处理目录结构已建立（T028），支持MinerU解析结果归档和文本清洗后的文档存储

## 启动服务

### 1. 启动Redis (Arq任务队列需要)

```bash
# Windows (使用WSL或Docker)
redis-server

# 或使用Docker
docker run -d -p 6379:6379 redis:latest
```

**状态**: ✅ 已完成 - Arq任务队列已配置（T020），支持任务注册、重试机制、健康检查

### 2. 启动FastAPI服务

```bash
# 开发模式
uvicorn src.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000

# 或使用CLI
python -m src.interfaces.api.main
```

**状态**: ✅ 已完成 - FastAPI应用基础结构已配置（T019），包含中间件、异常处理、路由、API文档

### 3. 启动Arq工作进程

```bash
# 在另一个终端
arq src.infrastructure.tasks.worker.WorkerSettings
```

**状态**: ✅ 已完成 - Arq Worker已实现（T020），支持优雅启动/关闭、信号处理、任务上下文管理

### 4. 验证服务

访问API文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 使用CLI工具

### 基本命令

```bash
# 查看帮助
python cli/main.py --help

# 系统状态检查
python cli/main.py check

# 系统初始化
python cli/main.py init

# 上传文档（功能待实现）
# python cli/main.py documents upload path/to/document.pdf

# 查看文档列表（功能待实现）
# python cli/main.py documents list

# 检索知识库（功能待实现）
# python cli/main.py knowledge-base search "查询内容"

# 执行结构优化Agent（功能待实现）
# python cli/main.py agents structure-optimize --outline-file outline.json

# 执行信息检索Agent（功能待实现）
# python cli/main.py agents information-retrieve --query "查询内容"

# 生成文稿（功能待实现）
# python cli/main.py agents draft-generate --outline-file outline.json --sources-file sources.json
```

**状态**: ✅ 已完成 - CLI基础结构已实现（T021），包含系统状态检查、初始化功能、Rich格式化输出。文档、知识库、Agent等子命令框架已就绪，等待后续阶段实现具体功能。

## 开发工作流

### 1. 代码格式化

```bash
# 使用Ruff格式化代码
ruff format src/

# 使用Ruff检查代码
ruff check src/
```

**状态**: ✅ 已完成 - Ruff配置已完成（T003）

### 2. 类型检查

```bash
# 使用Mypy检查类型
mypy src/
```

**状态**: ✅ 已完成 - Mypy配置已完成（T004）

### 3. 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 运行合约测试
pytest tests/contract/
```

**状态**: ✅ 已完成 - pytest配置已完成（T005），包含conftest.py全局测试夹具

### 4. 代码质量检查

```bash
# 检查代码重复度
ruff check --select RUF src/

# 检查文件长度（应<4000行）
find src/ -name "*.py" -exec wc -l {} \; | sort -rn
```

**状态**: ✅ 已完成 - 所有代码质量工具已配置

## 常见问题

### Q: 文档解析失败怎么办？

A: 检查以下几点：
1. 文档格式是否为PDF、HTML或DOCX（MVP版本）
2. 文档大小是否超过10MB
3. PaddleOCR是否正确安装（PDF需要）
4. python-docx库是否正确安装（DOCX需要）
5. 查看日志文件获取详细错误信息

### Q: 向量检索结果为空？

A: 检查以下几点：
1. 文档是否已成功解析和索引
2. Chroma数据库是否正常
3. 向量索引是否已构建
4. 查询内容是否与文档内容相关

### Q: Agent执行失败？

A: 检查以下几点：
1. LangChain配置是否正确
2. AI模型API密钥是否有效
3. 查看Agent执行日志
4. 检查LangGraph Checkpointer状态

### Q: 如何查看系统日志？

A: 日志文件位置：
- 应用日志: `./logs/app.log`
- Agent执行日志: `./logs/agents.log`
- 错误日志: `./logs/error.log`

## 下一步

- 阅读 [data-model.md](./data-model.md) 了解数据模型
- 阅读 [plan.md](./plan.md) 了解系统架构
- 阅读 [research.md](./research.md) 了解技术选型
- 查看 [contracts/openapi.yaml](./contracts/openapi.yaml) 了解API规范

## 获取帮助

- 查看项目文档: `docs/`
- 提交Issue: GitHub Issues
- 联系开发团队: [联系方式]
