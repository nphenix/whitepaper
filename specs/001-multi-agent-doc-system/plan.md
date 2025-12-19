# 实施计划: 多 Agent 协作的文档处理与生成系统

**分支**: `001-multi-agent-doc-system` | **日期**: 2025-12-05 | **规范**: [spec.md](./spec.md)
**输入**: 来自 `/specs/001-multi-agent-doc-system/spec.md` 的功能规范

**注意**: 此模板由 `/speckit.plan` 命令填充. 执行工作流程请参见 `.specify/templates/commands/plan.md`.

## 摘要

构建一个基于多Agent协作的文档处理与生成系统，核心功能包括：本地知识库与数据抽取（支持PDF、HTML和DOCX文档解析、多模式索引）、结构优化Agent（大纲结构化增强）、信息检索Agent（向量/BM25/元数据/知识图谱混合检索）、草稿生成Agent（文稿生成与润色）、模板生成（基于固定模板的格式文档生成）和记忆系统（用户交互记录与Agent自我学习）。

技术方案采用LangChain 1.0统一编排Agent，LangMem + LangGraph Checkpointer实现记忆层，llamaIndex构建RAG管线，FastAPI + Arq提供Web服务，SQLite + Chroma + NetworkX维护多模式数据存储，PaddleOCR实现文档识别。

## 技术背景

**语言/版本**: Python 3.12
**主要依赖**: 
- LangChain 1.0 (Agent编排框架)
- LangMem + LangGraph Checkpointer (记忆层与状态管理)
- llamaIndex (RAG管线构建)
- FastAPI + Arq (Web服务与异步任务队列)
- FastMCP (MCP服务能力)
- Typer + Rich (CLI工具与输出)
- PaddleOCR (文档识别)
- Ruff + Mypy (Python静态检查)
- ESLint (前端代码检查，如需要)
**存储**: 
- SQLite (结构化数据：文档元数据、用户数据、记忆条目等)
- Chroma (向量数据：文档向量索引)
- NetworkX (图数据：知识图谱)
**测试**: pytest (单元测试、集成测试、合约测试)
**目标平台**: Windows 11 (开发环境), Linux服务器 (生产部署)
**项目类型**: Web应用 (后端API + CLI工具)
**性能目标**: 
- 文档解析: 单个文档(10MB以内)在5分钟内完成
- 检索响应: 混合检索响应时间<2秒
- 文稿生成: 2000-3000字文稿在2分钟内生成
- 并发处理: 支持至少10个用户并发请求
**约束条件**: 
- 文件大小限制: 单个文档不超过10MB
- 知识库规模: 支持至少1000个文档
- 内存使用: 单实例内存占用<4GB
- 响应时间: API响应p95<3秒
**规模/范围**: 
- 用户规模: 初期支持10-50个并发用户
- 文档规模: 支持1000+文档的知识库
- 代码规模: 预计5-10万行Python代码

## 章程检查

*门控: 必须在阶段 0 研究前通过. 阶段 1 设计后重新检查. *

### P1 代码质量守则检查
- ✅ **模块化边界**: Agent设计遵循单一职责原则，每个Agent独立模块
- ✅ **文件长度限制**: 所有源文件将控制在4000行以内，大型Agent拆分为多个子模块
- ✅ **测试要求**: 每个Agent和核心服务都将配备单元测试
- ✅ **架构质量**: 
  - DRY原则: 共享的文档解析、索引构建逻辑提取为可复用组件
  - SOLID原则: Agent通过Protocol定义接口，支持依赖倒置
  - 设计模式: 使用策略模式实现多模式检索，工厂模式创建Agent实例

### P2 目录结构与工件定位检查
- ✅ **目录规范**: 采用分层架构 `src/domain/`、`src/application/`、`src/interfaces/`
- ✅ **文件定位**: 所有生成的代码和文档将写入预期路径
- ✅ **脚本验证**: 构建脚本将验证输出文件位置

### P3 临时文件纪律检查
- ✅ **临时文件**: 文档解析、索引构建的临时文件将在处理完成后清理
- ✅ **缓存管理**: LangGraph Checkpointer的缓存将配置为可清理模式

### P4 文档与可维护性检查
- ✅ **文档标注**: 所有自动生成的代码将包含生成命令和时间戳
- ✅ **设计决策**: 技术选型理由将记录在research.md中

### P5 Agent设计原则检查
- ✅ **单一职责**: 文档预处理Agent、结构优化Agent、信息检索Agent、草稿生成Agent各司其职
- ✅ **可组合性**: Agent通过LangChain统一接口协作，文档预处理Agent的输出作为后续Agent的输入
- ✅ **可观测性**: 所有Agent执行过程通过LangGraph Checkpointer记录，包括预处理质量报告
- ✅ **错误隔离**: 每个Agent的错误处理独立，不影响其他Agent，预处理失败不影响已处理的文档
- ✅ **知识库一致性**: 信息检索Agent保证引用来源的真实性和可追溯性

**阶段0前检查结果**: ✅ 通过 - 所有章程原则均符合要求

**阶段1后检查**: ✅ 已完成 - 阶段1（设置）和阶段2（基础）已完成，所有基础设施组件已实现

## 项目结构

### 文档(此功能)

```
specs/[###-feature]/
├── plan.md              # 此文件 (/speckit.plan 命令输出)
├── research.md          # 阶段 0 输出 (/speckit.plan 命令)
├── data-model.md        # 阶段 1 输出 (/speckit.plan 命令)
├── quickstart.md        # 阶段 1 输出 (/speckit.plan 命令)
├── contracts/           # 阶段 1 输出 (/speckit.plan 命令)
└── tasks.md             # 阶段 2 输出 (/speckit.tasks 命令 - 非 /speckit.plan 创建)
```

### 源代码(仓库根目录)

```
src/
├── domain/                    # 领域模型层
│   ├── document/              # 文档领域模型 ✅
│   │   ├── document.py        # 文档领域模型
│   │   └── preprocessed_document.py  # 预处理文档模型
│   ├── knowledge_base/        # 知识库领域模型 ⏸️ 待实现
│   ├── agent/                 # Agent领域模型 ⏸️ 待实现
│   └── memory/                # 记忆系统领域模型 ⏸️ 待实现
├── application/               # 应用服务层
│   ├── agent_base.py          # Agent基类 ✅
│   ├── agents/                # Agent实现
│   │   ├── document_preprocessor.py  # 文档预处理Agent ✅
│   │   ├── structure_optimizer.py    # 结构优化Agent ⏸️ 待实现
│   │   ├── information_retriever.py  # 信息检索Agent ⏸️ 待实现
│   │   └── draft_generator.py        # 草稿生成Agent ⏸️ 待实现
│   ├── services/              # 业务服务
│   │   ├── document_service.py       # 文档服务 ✅
│   │   ├── knowledge_base_service.py # 知识库服务 ⏸️ 待实现
│   │   ├── memory_service.py         # 记忆服务 ⏸️ 待实现
│   │   └── prompt_engineering_service.py  # 提示词工程服务 ⏸️ 待实现
│   └── orchestrator.py        # LangChain Agent编排 ✅
├── interfaces/                # 接口层
│   ├── api/                   # FastAPI路由 ✅
│   │   ├── app.py             # FastAPI应用
│   │   ├── main.py            # API入口
│   │   ├── routes/            # API路由
│   │   │   └── documents.py   # 文档路由 ✅
│   │   └── schemas/           # API Schema
│   │       └── document_schemas.py  # 文档Schema ✅
│   ├── cli/                   # Typer CLI命令 ✅
│   │   ├── agents.py          # Agent相关命令
│   │   ├── documents.py       # 文档相关命令 ✅
│   │   ├── knowledge_base.py  # 知识库相关命令
│   │   ├── memory.py          # 记忆相关命令
│   │   ├── prompts.py         # 提示词相关命令
│   │   ├── templates.py       # 模板相关命令
│   │   ├── constraints.py     # 约束相关命令
│   │   ├── source_matching.py # 信息源匹配命令
│   │   └── homepage.py        # 首页命令
│   └── mcp/                   # FastMCP服务 ⏸️ 待实现
├── infrastructure/            # 基础设施层
│   ├── storage/               # 数据存储 ✅
│   │   ├── sqlite/            # SQLite适配器 ✅
│   │   │   ├── adapter.py     # SQLite适配器
│   │   │   └── connection.py  # SQLite连接管理
│   │   ├── chroma/            # Chroma向量存储适配器 ✅
│   │   │   ├── adapter.py     # Chroma适配器
│   │   │   └── connection.py  # Chroma连接管理
│   │   └── networkx/          # NetworkX图存储适配器 ✅
│   │       ├── adapter.py     # NetworkX适配器
│   │       └── graph_manager.py  # 图管理器
│   ├── indexing/              # 索引构建 ⏸️ 待实现
│   │   ├── vector_index.py
│   │   ├── bm25_index.py
│   │   └── knowledge_graph.py
│   ├── parsing/               # 文档解析 ⏸️ 待实现
│   │   ├── pdf_parser.py
│   │   ├── html_parser.py
│   │   └── docx_parser.py
│   │   └── ocr/               # PaddleOCR集成
│   ├── preprocessing/         # 文档预处理 ✅
│   │   ├── loaders/           # 文档加载器 ✅
│   │   │   ├── base_loader.py  # 基础加载器接口 ✅
│   │   │   ├── mineru_adapter.py  # MinerU适配器 ✅
│   │   │   ├── mineru_pdf_loader.py  # MinerU PDF加载器 ✅
│   │   │   └── mineru_docx_loader.py  # MinerU DOCX加载器 ✅
│   │   ├── cleaners/          # 文档清洗器 ✅
│   │   │   ├── llm_ad_remover.py  # LLM广告清洗器 ✅
│   │   │   ├── llm_chart_to_json_converter.py  # 图表转JSON转换器 ✅
│   │   │   └── summarization_middleware.py  # 总结中间件 ✅
│   │   ├── preprocessor.py    # 预处理协调器 ✅
│   │   ├── format_detector.py  # 格式检测器 ✅
│   │   ├── error_handler.py    # 错误处理器 ✅
│   │   ├── logging_config.py   # 日志配置 ✅
│   │   └── quality_report.py   # 质量报告生成器 ✅
│   ├── memory/                # 记忆层 ✅
│   │   ├── langmem_adapter.py  # LangMem适配器 ✅
│   │   └── checkpointer.py     # LangGraph Checkpointer ✅
│   └── tasks/                 # 异步任务队列 ✅
│       ├── tasks.py           # 任务定义
│       ├── worker.py          # Arq Worker
│       ├── client.py           # 任务客户端
│       ├── document_tasks.py   # 文档处理任务 ✅
│       ├── settings.py         # 任务配置
│       └── monitoring.py      # 任务监控
└── shared/                    # 共享组件
    ├── utils/                  # 通用工具函数 ✅
    │   ├── retry.py           # 通用重试工具 ✅ (新增)
    │   ├── logging.py         # 日志配置 ✅
    │   ├── error_handler.py   # 错误处理中间件 ✅
    │   ├── agent_logging_middleware.py  # Agent日志中间件 ✅
    │   ├── helpers.py         # 通用辅助函数 ✅
    │   └── validators.py      # 输入验证函数 ✅
    ├── config/                 # 配置管理 ✅
    │   ├── settings.py        # 系统配置 ✅
    │   ├── llm_service.py     # LLM服务 ✅
    │   └── config_validator.py  # 配置验证器 ✅
    ├── exceptions/             # 自定义异常类 ✅
    │   ├── base_exceptions.py  # 基础异常类 ✅
    │   ├── agent_exceptions.py  # Agent异常类 ✅
    │   └── storage_exceptions.py  # 存储异常类 ✅
    └── prompts/               # 提示词管理 ⏸️ 待实现
        ├── templates/         # 提示词模板
        ├── strategies/        # 提示词策略
        └── prompt_manager.py  # 提示词管理器

tests/                         # 测试目录 ✅
├── conftest.py               # 全局测试配置 ✅
├── integration/               # 集成测试 ✅
│   ├── test_checkpointer_integration.py  # Checkpointer集成测试 ✅
│   ├── test_llm_ad_remover_real_files.py  # LLM清洗器真实文件测试 ✅
│   ├── test_llm_chart_to_json_converter_integration.py  # 图表转换器集成测试 ✅
│   └── test_real_api_connectivity.py  # API连通性测试 ✅
├── unit/                      # 单元测试 ✅
│   ├── application/          # 应用层单元测试 ✅
│   ├── config/                # 配置单元测试 ✅
│   ├── domain/                # 领域模型单元测试 ✅
│   ├── exceptions/            # 异常类单元测试 ✅
│   ├── infrastructure/        # 基础设施单元测试 ✅
│   ├── migration/             # 迁移单元测试 ✅
│   └── utils/                 # 工具函数单元测试 ✅
├── infrastructure/            # 基础设施测试 ✅
│   └── memory/                # 记忆层测试 ✅
└── test_infrastructure/      # 基础设施测试 ✅
    └── test_tasks/            # 任务测试 ✅

cli/                           # CLI入口点 ✅
└── main.py                    # CLI主入口 ✅

scripts/                       # 工具脚本 ✅
├── migration/                 # 数据库迁移脚本 ✅
│   ├── init_db.py            # 数据库初始化 ✅
│   ├── migration_utils.py    # 迁移工具 ✅
│   └── migrations/           # 迁移SQL文件 ✅
└── validation/               # 验证脚本 ✅
    ├── check_directory_structure.py  # 目录结构检查 ✅
    ├── check_file_length.py  # 文件长度检查 ✅
    ├── check_temp_files.py   # 临时文件检查 ✅
    └── run_all_checks.py     # 运行所有检查 ✅

docs/                          # 开发文档（面向人类开发者）
├── architecture/              # 架构文档
│   ├── overview.md            # 系统概览
│   ├── high-level-design.md   # 概要设计
│   ├── detailed-design.md     # 详细设计
│   └── component-diagrams/    # 组件图
├── development/               # 开发文档
│   ├── coding-standards.md    # 编码规范
│   ├── git-workflow.md        # Git工作流
│   └── testing-guide.md       # 测试指南
├── api/                       # API文档
│   ├── api-overview.md        # API概览
│   └── endpoints/             # 各端点详细文档
├── deployment/                # 部署文档
│   ├── deployment-guide.md    # 部署指南
│   └── configuration.md       # 配置说明
└── troubleshooting/           # 故障排除文档
    └── common-issues.md       # 常见问题

data/                          # 数据目录（不提交到Git，通过.gitignore排除）✅
├── source/                    # 源数据：用户上传的原始文档 ✅
│   └── uploads/               # 上传临时目录 ✅
├── processed/                 # 处理后数据：外部工具处理结果 ✅
│   └── mineru/                # MinerU文档解析结果（临时存储，处理后归档）✅
├── archive/                   # 归档数据：已处理的原始数据备份 ⏸️ 待实现
│   └── mineru/                # MinerU处理结果归档（按时间戳组织）
├── cleaned/                   # 清洗后数据：文本清洗后的文档 ✅
│   └── documents/             # 清洗后的文档存储（按时间戳组织）✅
├── intermediate/              # 中间数据：处理过程中的数据 ✅
│   ├── preprocessed/          # 预处理后的文档 ⏸️ 待实现
│   ├── parsed/                # 解析后的文档块 ⏸️ 待实现
│   ├── indexed/               # 索引数据（向量、BM25、元数据）✅
│   │   ├── vectors/           # 向量索引文件 ✅
│   │   ├── bm25/              # BM25索引文件 ✅
│   │   └── metadata/          # 元数据索引文件 ✅
│   ├── knowledge_graph/       # 知识图谱数据 ⏸️ 待实现
│   └── checkpoints/           # LangGraph Checkpointer状态 ✅
├── templates/                 # 模板数据：可版本控制 ⏸️ 待实现
│   ├── document_templates/    # 文档模板（JSON/YAML）
│   ├── prompt_templates/      # 提示词模板
│   └── prompt_strategies/     # 提示词策略配置
├── output/                    # 结果数据：生成的文稿和导出文件 ✅
│   ├── drafts/                # 生成的文稿草稿 ✅
│   ├── final/                 # 最终文稿 ✅
│   ├── exports/               # 导出文件（PDF、Word等）✅
│   └── reports/               # 质量报告、分析报告 ✅
├── cache/                     # 缓存数据 ✅
│   ├── retrieval/             # 检索结果缓存 ✅
│   ├── embeddings/            # 向量嵌入缓存 ✅
│   ├── mineru/                # MinerU缓存 ✅
│   └── agent_states/          # Agent状态缓存 ✅
├── temp/                      # 临时数据（处理完成后自动清理）✅
│   ├── processing/            # 处理过程中的临时文件 ✅
│   ├── uploads/               # 上传过程中的临时文件 ✅
│   ├── output/                # 临时输出文件 ✅
│   └── test_outputs/          # 测试输出文件 ✅
└── logs/                      # 日志文件 ✅
    └── ...                    # 应用日志文件

storage/                       # 持久化存储（数据库文件）✅
├── sqlite/                    # SQLite数据库文件 ✅
│   └── whitepaper.db          # 主数据库文件 ✅
├── chroma/                    # Chroma向量数据库 ✅
│   └── chroma.sqlite3         # Chroma元数据数据库 ✅
└── networkx/                  # NetworkX图数据持久化 ✅
    └── ...                    # 图数据文件
```

**数据目录说明**:
- **data/source/**: 存储用户上传的原始文档，按用户ID和日期组织子目录，便于管理和清理
- **data/processed/**: 存储外部工具处理后的数据，如MinerU解析结果，作为文本清洗的输入源
- **data/archive/**: 存储已处理的原始数据备份，确保数据可追溯性和恢复能力
- **data/cleaned/**: 存储文本清洗后的高质量文档，作为后续Agent处理的输入
- **data/intermediate/**: 存储处理过程中的中间数据，包括预处理、解析、索引等结果，支持增量处理和恢复
- **data/templates/**: 存储模板数据，可以版本控制，便于模板的迭代和共享
- **data/output/**: 存储最终生成的结果数据，包括文稿、导出文件等，支持用户下载和归档
- **data/cache/**: 存储各种缓存数据，提高系统性能，支持缓存失效和清理策略
- **data/temp/**: 存储临时文件，处理完成后自动清理，符合章程P3要求
- **data/logs/**: 存储系统日志，支持日志轮转和归档
- **storage/**: 存储数据库文件，包括SQLite、Chroma、NetworkX的持久化数据

**数据管理策略**:
- 所有数据目录（除data/templates/）应在.gitignore中排除
- 临时文件（data/temp/）在处理完成后自动清理
- 缓存文件（data/cache/）实现TTL和LRU清理策略
- 中间数据（data/intermediate/）支持按时间清理旧数据
- 源数据和结果数据支持用户手动清理或自动归档
- 所有数据操作通过统一的数据访问层，确保数据一致性

**文档目录说明**:
- **docs/architecture/**: 存放架构设计文档，包括系统概览、概要设计、详细设计等，用于开发团队理解系统整体架构和设计思路
- **docs/development/**: 存放开发相关文档，包括编码规范、Git工作流、测试指南等，用于规范开发流程和代码质量
- **docs/api/**: 存放API文档，包括API概览和各个端点的详细文档，用于API使用和集成
- **docs/deployment/**: 存放部署相关文档，包括部署指南和配置说明，用于系统部署和运维
- **docs/troubleshooting/**: 存放故障排除文档，包括常见问题和解决方案，用于问题诊断和处理

**文档管理约束**（详见项目宪章 P4）:
- 代码变更时必须同步更新相关 `docs/` 文档，文档未更新视为 PR 不合格
- 文档必须有明确的最后更新时间戳，超过 6 个月未更新的文档必须进行审核和刷新
- 每季度进行一次文档审计，识别过期或与代码不一致的文档
- 文档必须使用中文编写，术语与代码保持一致，并包含完整的示例和说明

**结构决策**: 采用分层架构（domain/application/interfaces/infrastructure），符合章程P2要求。Agent实现位于application/agents，通过LangChain统一编排。数据存储适配器位于infrastructure/storage，支持SQLite、Chroma、NetworkX三种存储后端。数据目录明确区分源数据、中间数据、模板数据和结果数据，符合章程P2和P3的要求，确保数据组织清晰、临时文件及时清理。CLI和API作为不同的接口层，共享应用服务层。docs目录专门用于存放面向人类开发者的各类文档，支持团队协作和知识传承，这些文档与specs目录中的规范文档不同，主要用于开发过程中的交流和协作。

**实现状态说明**:
- ✅ 标记表示已实现并正在使用
- ⏸️ 标记表示计划中但尚未实现
- 未标记的目录/文件表示待实现或待完善

**架构重构更新** (2025-01-XX):
- 统一异常类定义：所有预处理相关异常类统一在`infrastructure/preprocessing/error_handler.py`中定义，遵循DRY原则 ✅
- 提取重试逻辑：创建`shared/utils/retry.py`模块，统一重试机制，支持指数退避和429错误特殊处理 ✅
- 文件长度控制：所有源文件均控制在4000行以内，符合项目规范 ✅

## 复杂度跟踪

*仅在章程检查有必须证明的违规时填写*

| 违规 | 为什么需要 | 拒绝更简单替代方案的原因 |
|-----------|------------|-------------------------------------|
| [例如: 第 4 个项目] | [当前需求] | [为什么 3 个项目不够] |
| [例如: 仓储模式] | [特定问题] | [为什么直接数据库访问不够] |
