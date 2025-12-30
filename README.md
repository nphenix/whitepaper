# whitepaper - AI驱动的智能文档生成平台

## 项目概述

whitepaper 是一个基于人工智能的深度文档生成系统，通过先进的AI技术实现专业文档的自动生成。

**项目状态**: 开发中 (Alpha 版本)
**版本**: 0.1.0
**许可证**: MIT

## 核心功能

### ✅ 已完成功能

#### 📄 用户故事1 - 文档预处理与清洗（已完成）
- **MinerU产线集成**: 
  - PDF和DOCX文档加载器，支持批量处理
  - 自动去除非主体内容（页眉、页脚、脚注、页码）
  - 多模态内容处理（文本、公式、表格、图表）
  - 智能路径管理，使用原始文件名作为目录名
- **LLM智能清洗**:
  - 基于LangChain 1.0的智能广告清洗
  - 自动识别并删除广告、目录、图表目录等无意义信息
  - 保留有价值内容（图片链接、文档主体、章节结构）
  - 支持长文摘要中间件，防止token溢出
- **图表转JSON转换器**:
  - 自动识别文档中的图表（柱状图、折线图、饼图等）
  - 将图表转换为结构化JSON格式
  - 支持从图表JSON中提取数据用于后续生成
- **文档预处理协调器**:
  - 统一协调文档加载和清洗流程
  - 支持同步和异步处理
  - 完善的错误处理和进度跟踪
- **API和CLI接口**:
  - 文档上传、预处理、查询等完整API
  - 丰富的CLI命令，支持批量处理

#### 📚 用户故事2 - 建立本地知识库（已完成）
- **文档解析**:
  - Markdown解析器，支持从预处理结果读取
  - 提取结构化信息（章节、段落、标题层次、列表、表格等）
  - 自动生成章节路径（如"1.2.3"）
- **多模式索引构建**:
  - **向量索引**: 基于Chroma的语义检索
  - **BM25索引**: 关键词匹配检索
  - **元数据索引**: 结构化查询（章节路径、文档层级等）
  - **知识图谱**: 实体关系提取和图存储
- **混合检索引擎**:
  - 融合向量检索、BM25检索、元数据检索、知识图谱检索
  - 支持Reciprocal Rank Fusion (RRF)等多种融合算法
  - 动态检索策略，根据查询类型自动调整
  - Rerank重排序支持
- **检索块与合成块分离**:
  - 检索块（较小）优化检索精度
  - 合成块（较大）提供生成上下文
  - 建立映射关系，优化RAG性能
- **知识库服务**:
  - 知识库创建、更新、删除、查询等完整功能
  - 支持批量文档处理和索引更新
  - 索引进度跟踪和状态管理
- **API和CLI接口**:
  - 知识库管理完整API
  - 支持混合查询和结构化查询
  - 丰富的CLI命令

### 🎯 MVP 核心流程（规划中）
- **第一步**: 行业和数据库选择（储能行业分析与数据库）
- **第二步**: 大纲手写和AI优化
- **第三步**: 信息源爬取（储能行业网站）
- **第四步**: 草稿生成（带素材追溯链接）

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
- **MinerU在线服务** - 批量文档解析（PDF、DOCX），支持OCR和公式识别 ✅
- **LLM智能清洗** - 基于LangChain 1.0的智能广告和噪声去除 ✅
- **图表转JSON** - 自动识别和转换文档中的图表为结构化数据 ✅
- **Markdown解析** - 结构化解析预处理后的Markdown文档 ✅
- **BeautifulSoup4** - HTML解析（用于网页爬取内容）✅

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

### 核心AI能力（已实现）
- **语义理解**: 深度理解文档内容和用户意图 ✅
- **智能检索**: 基于多源数据的统一智能检索系统 ✅
  - 混合检索（向量+BM25+元数据+知识图谱）
  - 动态检索策略
  - Rerank重排序
- **智能清洗**: 基于LLM的文档智能清洗 ✅
  - 自动识别和删除广告、目录等无意义内容
  - 保留有价值内容（图片、主体、章节结构）
  - 长文摘要支持，防止token溢出
- **知识图谱**: 实体关系提取和图存储 ✅
  - LLM驱动的实体和关系提取
  - 实体消歧和合并
  - 支持储能产业特定实体类型

### 规划中的AI能力
- **专业文稿生成**: 基于AI技术的深度内容创作和结构化输出
- **大纲优化**: 基于AI技术对文档框架进行结构化增强

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

### 开发文档
- [开发文档](docs/development/README.md) - 开发相关文档索引
- [MinerU使用指南](docs/development/mineru-usage-guide.md) - MinerU批量上传使用指南
- [MinerU路径配置](docs/development/mineru-path-configuration.md) - 路径配置说明

### API文档
- [知识库API文档](docs/api/T055_knowledge_base_api.md) - 知识库管理API完整文档

### 架构文档
- [高层设计](docs/architecture/high-level-design.md) - 系统架构设计
- [LangChain 1.0评估](docs/architecture/langchain-1.0-evaluation.md) - LangChain 1.0最佳实践
- [重构总结](docs/architecture/refactoring-summary.md) - 架构重构记录

### 实现报告
- [阶段3任务评估](docs/development/phase3-task-evaluation.md) - 文档预处理任务评估
- [阶段4任务评估](docs/development/phase4-task-evaluation.md) - 知识库构建任务评估
- [T050完成报告](docs/development/t050-completion-report.md) - 知识库服务实现报告
- [T051实现总结](docs/development/T051_implementation_summary.md) - 索引任务实现总结

---

**项目状态**: 开发中 (Alpha 版本)  
**当前版本**: 0.1.0  
**最后更新**: 2025-01-27  
**完成阶段**: 阶段1-2（基础）✅ | 阶段3（文档预处理）✅ | 阶段4（知识库构建）✅