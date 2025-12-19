# whitepaper - AI驱动的智能文档生成平台

## 项目概述

whitepaper 是一个基于人工智能的深度文档生成系统，通过先进的AI技术实现专业文档的自动生成。

**项目状态**: 开发中 (Alpha 版本)
**版本**: 0.1.0
**许可证**: MIT

## 核心功能

### 🎯 MVP 核心流程
- **第一步**: 行业和数据库选择（储能行业分析与数据库）
- **第二步**: 大纲手写和AI优化
- **第三步**: 信息源爬取（储能行业网站）
- **第四步**: 草稿生成（带素材追溯链接）

### 📚 基础能力
- **文档预处理与清洗**: 支持PDF、HTML、DOCX格式的智能处理
  - **MinerU在线服务集成**: 支持批量文件上传和解析，自动处理PDF和DOCX文档
  - **智能路径管理**: 正式环境使用原始文件名作为目录名，便于查找和管理
- **知识库构建**: 基于RAG技术的多源数据统一索引
- **智能大纲优化**: 基于AI技术对文档框架进行结构化增强

## 技术栈

### 核心AI框架
- **Python 3.12**
- **LangChain 1.0** - AI Agent统一编排框架
- **llamaIndex** - RAG管线构建
- **FastAPI** - Web服务框架
- **Arq** - 异步任务队列

### 数据存储
- **SQLite** - 结构化数据存储
- **Chroma** - 向量数据存储
- **NetworkX** - 图数据存储

### 文档智能处理
- **MinerU在线服务** - 批量文档解析（PDF、DOCX），支持OCR和公式识别
- **PaddleOCR** - 文档识别
- **PyPDF2/pdfplumber** - PDF文档解析
- **python-docx** - Word文档处理
- **BeautifulSoup4** - HTML解析

### 代码质量工具
- **Ruff** - 代码格式化和linting
- **Mypy** - 类型检查
- **pytest** - 测试框架

### CLI工具
- **Typer** - CLI框架
- **Rich** - 输出格式化

## 项目结构

```
whitepaper/
├── src/                           # 源代码
│   ├── domain/                    # 领域模型层
│   │   ├── document/             # 文档领域模型
│   ├── knowledge_base/           # 知识库领域模型
│   ├── agent/                     # Agent领域模型
│   └── memory/                    # 记忆系统领域模型
├── application/                  # 应用服务层
│   ├── agents/                   # Agent实现
│   ├── services/                 # 业务服务
│   └── orchestrator.py          # AI Agent编排器
├── interfaces/                   # 接口层
│   ├── api/                      # FastAPI路由
│   ├── cli/                       # CLI命令
├── infrastructure/               # 基础设施层
│   ├── storage/                  # 数据存储适配器
│   ├── indexing/                 # 索引构建器
│   ├── parsing/                  # 文档解析器
│   ├── preprocessing/           # 文档预处理器
└── shared/                       # 共享组件
    ├── utils/                    # 通用工具函数
    │   ├── retry.py              # 通用重试工具（支持指数退避、429错误处理）✅
    │   ├── logging.py            # 日志配置
    │   └── ...                   # 其他工具函数
    ├── config/                   # 配置管理
    ├── exceptions/               # 自定义异常类
    └── prompts/                  # 提示词管理
```

### 快速开始

#### 环境设置
```bash
# 激活conda环境
conda activate whitepaper

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest
```

## AI智能特性

### 核心AI能力
- **语义理解**: 深度理解文档内容和用户意图
- **智能检索**: 基于多源数据的统一智能检索系统
- **专业文稿生成**: 基于AI技术的深度内容创作和结构化输出

### 开发规范

#### 代码质量守则
- **模块化边界**: 所有功能保持清晰的模块化边界
- **智能生成**: 基于知识库内容自动生成专业文稿
- **素材追溯**: 确保所有引用内容都可追溯至原始来源
- **错误隔离**: Agent执行失败不得导致整个系统崩溃

## 部署与运维

### 本地开发
```bash
# 启动FastAPI服务器
uvicorn src.interfaces.api.main:app --reload
```

## 贡献指南

### 开发流程
1. 创建功能分支，引用对应的 `specs/[feature]/` 文档
2. 遵循PR检查清单
3. 同步更新相关文档

---

## 文档

- [开发文档](docs/development/README.md) - 开发相关文档
- [MinerU使用指南](docs/development/mineru-usage-guide.md) - MinerU批量上传使用指南
- [MinerU路径配置](docs/development/mineru-path-configuration.md) - 路径配置说明

---

**最后更新**: 2025-12-12
**生成命令**: /speckit.implement T007
**来源**: `specs/001-multi-agent-doc-system/tasks.md`