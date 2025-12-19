# 任务: 多 Agent 协作的文档处理与生成系统

**输入**: 来自 `/specs/001-multi-agent-doc-system/` 的设计文档
**前置条件**: plan.md(必需)、spec.md(用户故事必需)、research.md、data-model.md、contracts/

**测试**: 以下任务不包含测试任务。测试是可选的 - 仅在功能规范中明确要求时才包含。

**组织结构**: 任务按用户故事分组, 以便每个故事能够独立实施和测试。

## 格式: `[ID] [P?] [Story] 描述`
- **[P]**: 可以并行运行(不同文件, 无依赖关系)
- **[Story]**: 此任务属于哪个用户故事(例如: US1、US2、US3)
- 在描述中包含确切的文件路径

## 路径约定
- **项目结构**: 仓库根目录下的 `src/`、`tests/`、`cli/`
- 根据 plan.md 中的分层架构组织

---

## 阶段 1: 设置(共享基础设施)

**目的**: 项目初始化和基本结构

- [x] T001 根据 plan.md 创建项目目录结构 (src/domain/, src/application/, src/interfaces/, src/infrastructure/, src/shared/, tests/, cli/，...) [技术栈: 无特定要求]
- [x] T002 初始化 Python 3.12 项目，创建 requirements.txt 和 pyproject.toml [技术栈: Python 3.12]
- [x] T003 [P] 配置 Ruff 代码格式化和 linting 工具 (ruff.toml) [技术栈: Ruff]
- [x] T004 [P] 配置 Mypy 类型检查工具 (mypy.ini) [技术栈: Mypy]
- [x] T005 [P] 配置 pytest 测试框架 (pytest.ini, conftest.py) [技术栈: pytest]
- [x] T006 创建 .env.example 环境变量模板文件 [技术栈: 无特定要求]
- [x] T007 创建 README.md 项目说明文档 [技术栈: Markdown]
- [x] T008 创建 .gitignore 文件，排除临时文件和缓存 [技术栈: Git]

---

## 阶段 2: 基础(阻塞前置条件)

**目的**: 在任何用户故事可以实施之前必须完成的核心基础设施

**⚠️ 关键**: 在此阶段完成之前, 无法开始任何用户故事工作

- [x] T009 在 src/shared/config/ 中创建配置管理模块和LangChain 1.0动态模型统一集中配置服务 (settings.py, llm_service.py) [技术栈: Python标准库, pydantic, pydantic-settings, LangChain 1.0, langchain-openai, langchain-google-genai] 
  - 实现配置管理 (settings.py)，使用 Pydantic Settings 自动加载环境变量和 .env 文件 ✅
  - 实现LangChain 1.0动态模型统一集中配置服务 (llm_service.py) ✅
  - 支持多种LLM提供商动态加载：OpenAI Compatible (默认KATpro1)、Gemini、Anthropic Claude ✅
  - 支持Embedding模型配置：阿里百炼text-embedding-v4 ✅
  - 支持Rerank模型配置：阿里百炼qwen3-rerank ✅
  - 提供统一的模型获取接口，后续所有需要使用大模型服务的地方都从此服务获取 ✅
  - 使用工厂模式或单例模式管理模型实例，支持按需创建和缓存 ✅
  - 支持通过环境变量动态切换模型提供商和配置 ✅
  - 所有配置项必须通过 .env 文件配置，无硬编码默认值 ✅
  - **完成日期**: 2025-12-07
  - **静态检查**: 已完成，修复5个问题（详见 docs/static-check-report-t009.md）
  - **连通性测试**: 已完成（katpro1、embedding和rerank模型）
- [x] T010 在 src/shared/exceptions/ 中创建自定义异常类 (base_exceptions.py, agent_exceptions.py, storage_exceptions.py) [技术栈: Python标准库]
  - 实现基础异常类 (base_exceptions.py) ✅
  - 实现Agent相关异常类 (agent_exceptions.py) ✅
  - 实现存储相关异常类 (storage_exceptions.py) ✅
  - 提供统一的异常处理接口，支持异常链和序列化 ✅
  - 完整的测试覆盖（4个测试文件） ✅
  - **完成日期**: 2025-12-08
  - **静态检查**: 已完成，所有mypy类型检查通过
  - **详细报告**: 详见 docs/development/t010-t011-completion-report.md
- [x] T011 在 src/shared/utils/ 中创建通用工具函数 (logging.py, validators.py, helpers.py) [技术栈: Python标准库]
  - 实现日志配置和格式化工具 (logging.py) ✅
  - 实现输入验证函数 (validators.py) ✅
  - 实现通用辅助函数 (helpers.py) ✅
  - 支持多种日志格式（简单、详细、结构化、JSON） ✅
  - 提供丰富的验证函数和预设规则 ✅
  - 提供24个通用辅助函数 ✅
  - 完整的测试覆盖（3个测试文件） ✅
  - **完成日期**: 2025-12-08
  - **静态检查**: 已完成，修复5个mypy unreachable错误，所有类型检查通过
  - **详细报告**: 详见 docs/development/t010-t011-completion-report.md
- [x] T012 在 src/infrastructure/storage/sqlite/ 中创建 SQLite 数据库适配器和连接管理 (adapter.py, connection.py) [技术栈: SQLite, aiosqlite/sqlite3]
  - 实现 SQLite 连接管理器 (connection.py)，支持同步和异步连接、连接池、事务管理 ✅
  - 实现 SQLite 适配器 (adapter.py)，提供完整的 CRUD 操作、批量操作、自定义查询 ✅
  - 支持 WAL 模式、外键约束、连接生命周期管理 ✅
  - 完整的异常处理和日志记录 ✅
  - **完成日期**: 2025-12-08
  - **详细报告**: 详见 docs/development/t012-t013-t014-evaluation-report.md
- [x] T013 在 src/infrastructure/storage/chroma/ 中创建 Chroma 向量存储适配器 (adapter.py, connection.py) [技术栈: Chroma]
  - 实现 Chroma 连接管理器 (connection.py)，支持集合管理、本地和远程连接 ✅
  - 实现 Chroma 适配器 (adapter.py)，提供向量增删改查、相似性搜索、批量操作 ✅
  - 支持多种嵌入函数配置、元数据管理、集合信息获取 ✅
  - 完整的异常处理和日志记录 ✅
  - **完成日期**: 2025-12-08
  - **详细报告**: 详见 docs/development/t012-t013-t014-evaluation-report.md
- [x] T014 在 src/infrastructure/storage/networkx/ 中创建 NetworkX 图存储适配器 (adapter.py, graph_manager.py) [技术栈: NetworkX]
  - 实现 NetworkX 图管理器 (graph_manager.py)，支持多种图类型、图持久化、自动保存 ✅
  - 实现 NetworkX 适配器 (adapter.py)，提供节点和边的增删改查、图遍历、路径查找 ✅
  - 支持多种文件格式（GML、GraphML、JSON、Pickle）、图信息获取 ✅
  - 完整的异常处理和日志记录 ✅
  - **完成日期**: 2025-12-08
  - **详细报告**: 详见 docs/development/t012-t013-t014-evaluation-report.md
- [x] T015 创建数据库迁移脚本框架 (scripts/migration/init_db.py, migration_utils.py) [技术栈: SQLite, Python标准库]
  - 实现数据库初始化脚本 (init_db.py)，提供完整的CLI工具，支持init、migrate、rollback、status等命令 ✅
  - 实现迁移工具模块 (migration_utils.py)，提供Migration和MigrationManager类 ✅
  - 支持版本控制、依赖关系管理、回滚操作、状态跟踪 ✅
  - 支持SQL文件解析（@up和@down标记）、事务支持、校验和计算 ✅
  - 提供初始数据库表结构迁移文件 (001_create_initial_tables.sql) ✅
  - 完整的测试覆盖（2个测试文件，975+行测试代码） ✅
  - 提供完整的使用文档 (README.md) ✅
  - **完成日期**: 2025-12-08
  - **详细报告**: 详见 docs/development/t015-completion-report.md
- [x] T016 在 src/infrastructure/memory/ 中创建 LangMem 适配器 (langmem_adapter.py) [技术栈: LangMem, LangGraph Store]
  - 实现长期记忆管理适配器, 基于LangGraph Store和LangMem ✅
  - 使用namespace实现多用户/多场景记忆隔离 ✅
  - 配置向量索引支持语义检索 ✅
  - 集成项目统一的embedding配置(阿里百炼text-embedding-v4) ✅
  - 提供完整的增删改查接口 ✅
  - 支持记忆版本管理和演进跟踪 ✅
  - 创建记忆管理工具(manage_memory_tool, search_memory_tool) ✅
  - **注意**: 必须从T009创建的llm_service获取embedding模型实例 ✅
  - **完成日期**: 2025-12-09
  - **优化**: 修复namespace使用问题, 正确配置向量索引, 工具与store绑定 ✅
  - **重构优化** (2025-12-09): 
    - 添加`get_memory_tools()`方法，支持为指定namespace创建记忆工具 ✅
    - 添加`create_memory_tools_for_namespace()`便捷方法 ✅
    - 完善Tool模式集成，支持在BaseAgent中自动注册记忆工具 ✅
    - 符合LangChain 1.0和LangMem官方最佳实践 ✅
- [x] T017 在 src/infrastructure/memory/ 中创建 LangGraph Checkpointer 配置 (checkpointer.py) [技术栈: LangGraph Checkpointer]
  - 实现工作记忆管理能力, 支持Agent执行状态的持久化与恢复 ✅
  - 支持多种存储后端(内存、SQLite) ✅
  - 支持工作流恢复和断点续传 ✅
  - 线程安全的检查点管理 ✅
  - 检查点历史追踪和版本管理 ✅
  - 自动清理过期检查点 ✅
  - 上下文管理器模式确保资源正确释放 ✅
  - **注意**: 此模块为可选组件, 主要用于需要工作流状态持久化的场景 ✅
  - **完成日期**: 2025-12-09
  - **优化**: 修复资源管理问题, 实现异步清理功能, 添加健康检查 ✅
- [x] T018 在 src/application/ 中创建 LangChain Agent 编排器基础框架 (orchestrator.py, agent_base.py) [技术栈: LangChain 1.0, create_agent]
  - 实现Agent基础类(BaseAgent), 基于LangChain 1.0的create_agent API ✅
  - 实现Agent编排器(AgentOrchestrator), 支持多Agent协作编排 ✅
  - 统一的Agent生命周期管理 ✅
  - 集成LLM服务(T009), 必须从llm_service获取模型实例 ✅
  - 中间件支持, 基于LangChain 1.0的Middleware模式 ✅
  - 状态管理和错误处理 ✅
  - 支持工具调用, 自动集成Agent工具和记忆工具 ✅
  - 依赖管理和并行执行支持 ✅
  - **注意**: 必须从T009创建的llm_service获取LLM模型实例, 不得直接创建模型实例 ✅
  - **完成日期**: 2025-12-09
  - **重大重构** (2025-12-09): 
    - **使用create_agent替代手搓LCEL链** ✅
      - 移除`_build_lcel_chain()`方法，使用`_create_agent()`方法 ✅
      - 完全基于LangChain 1.0官方推荐的`create_agent` API ✅
      - 符合LangChain 1.0最佳实践，降低技术负债 ✅
    - **新增功能**:
      - 支持结构化输出（response_format）✅
      - 集成Checkpointer状态持久化（利用T017）✅
      - 自动注册LangMem Tools（利用T016）✅
      - 支持官方内置中间件（HumanInTheLoopMiddleware等）✅
      - 支持运行时上下文（context_schema）✅
    - **API变更**:
      - `invoke()`返回标准dict格式（包含messages和structured_response）✅
      - 移除自定义`AgentState` TypedDict，使用标准状态格式 ✅
    - **代码质量**:
      - 代码行数: ~409行（功能更强大但代码更简洁）✅
      - 无linter错误 ✅
  - **详细文档**: 参见 docs/development/t018-refactoring-summary.md ✅
- [x] T019 配置 FastAPI 应用基础结构 (src/interfaces/api/main.py, app.py) [技术栈: FastAPI]
  - 实现FastAPI应用实例创建和配置 (app.py) ✅
  - 实现应用生命周期管理（启动/关闭） ✅
  - 实现中间件配置（CORS、受信任主机、请求日志） ✅
  - 实现异常处理器（HTTP异常、通用异常） ✅
  - 实现基础路由（根路径、健康检查） ✅
  - 实现静态文件服务 ✅
  - 实现CLI启动命令（main.py，使用Typer） ✅
  - 支持环境配置（开发/生产模式） ✅
  - 集成API文档（Swagger/ReDoc） ✅
  - **完成日期**: 2025-12-09
  - **代码质量**: 无linter错误，已修复uvicorn配置路径问题 ✅
- [x] T020 配置 Arq 异步任务队列 (src/infrastructure/tasks/worker.py, settings.py) [技术栈: Arq, Redis]
  - 实现Worker配置和管理 (worker.py) ✅
  - 实现任务注册表（支持任务类、函数、装饰器） ✅
  - 实现Redis连接管理 ✅
  - 实现健康检查机制 ✅
  - 实现优雅启动和关闭 ✅
  - 实现信号处理（SIGTERM/SIGINT） ✅
  - 实现重试机制和退避策略 ✅
  - 实现任务上下文管理 ✅
  - 实现监控和日志记录 ✅
  - 实现任务队列配置管理 (settings.py) ✅
  - 支持CLI启动Worker ✅
  - **完成日期**: 2025-12-09
  - **代码质量**: 无linter错误，类型注解完整，异常处理完善 ✅
- [x] T021 配置 Typer CLI 基础结构 (cli/main.py, cli/base.py) [技术栈: Typer, Rich]
  - 实现CLI主入口 (main.py)，基于Typer ✅
  - 实现系统状态检查（配置、数据库、向量存储、图存储、任务队列） ✅
  - 实现系统初始化功能（配置、数据库、存储、示例数据） ✅
  - 集成所有子命令（documents、knowledge-base、agents、homepage、memory、prompts、templates、constraints、source-matching） ✅
  - 实现基础CLI类 (base.py)，提供通用功能 ✅
  - 实现Rich格式化输出（表格、面板、进度条） ✅
  - 实现用户交互工具（确认、输入、选择） ✅
  - 集成配置管理和存储管理 ✅
  - 支持异步函数执行 ✅
  - **完成日期**: 2025-12-09
  - **代码质量**: 无linter错误，代码结构清晰，错误处理完善 ✅
- [x] T022 创建错误处理和日志记录中间件 (src/shared/utils/error_handler.py, src/shared/utils/agent_logging_middleware.py) [技术栈: Python标准库logging, LangChain 1.0中间件]
  - 实现错误处理中间件(ErrorHandlingMiddleware)，基于LangChain 1.0的AgentMiddleware ✅
  - 实现Agent日志记录中间件(AgentLoggingMiddleware)，记录Agent执行生命周期 ✅
  - 支持模型调用错误处理和重试机制 ✅
  - 支持工具调用错误处理和自定义错误消息 ✅
  - 支持结构化日志记录（输入、输出、性能指标、工具调用） ✅
  - 自动集成到BaseAgent，所有Agent默认启用 ✅
  - 符合项目规范中的可观测性和错误隔离要求 ✅
  - **完成日期**: 2025-12-09
  - **详细报告**: 详见 docs/development/t022-completion-report.md

**检查点**: 基础就绪 - 现在可以开始并行实施用户故事

---

## 阶段 3: 用户故事 1 - 文档预处理与清洗 (优先级: P1)🎯 MVP

**目标**: 实现文档预处理Agent，能够识别文档格式、加载文档内容，并进行清洗处理

**独立测试**: 可以上传不同格式的文档（PDF、DOCX），验证系统能够正确识别格式、加载内容并进行清洗。即使没有后续的解析和索引功能，用户也能看到文档预处理的结果。

**框架引入策略**: 采用最小化策略引入LangChain 1.0框架
- ✅ 引入LangChain 1.0 Document对象格式（所有加载器统一返回`langchain_core.documents.Document`）
- ✅ 引入LangChain 1.0 Agent框架（T032要求）
- ❌ 不引入HTML加载器（目前无实际需求）
- ❌ 不引入LangChain的PDF/DOCX加载器（使用项目确定的在线服务方案）
- 自定义PDF/DOCX加载器需遵循LangChain 1.0集成最佳实践（详见`docs/development/phase3-framework-evaluation.md`）

**测试文件**: 已在 `F:\WhitePaper\data\temp\uploads` 目录下放置测试文件：
- `2022储能产业研究白皮书.pdf` - PDF测试文件
- `新型储能发展现状及长时储能在电力系统的应用前景展望.docx` - DOCX测试文件

**文档处理产线规划**:
- **产线1: MinerU产线** (优先实现)
  - 支持格式：PDF、DOCX
  - MinerU自动去除非主体内容（页眉、页脚、脚注、页码），多模态内容处理，结构化输出
  - API文档: https://mineru.net/apiManage/docs
  - 需要配置API Token（Bearer Token格式）
- **产线2: PaddleOCR产线** ⏸️ **已暂停**
  - 当前聚焦MinerU产线和LLM智能清洗
  - 待MinerU产线稳定后，根据实际需求评估是否需要实现
  - 需要配置API Key和Secret Key

### 用户故事 1 的实施

- [x] T023 [P] [US1] 在 src/domain/document/ 中创建 Document 领域模型 (document.py) [技术栈: Python标准库, pydantic]
  - 实现完整的Document领域模型，包含所有必需字段和验证逻辑 ✅
  - 提供业务方法（状态管理、元数据操作等） ✅
  - 完整的测试覆盖（18个测试用例） ✅
  - **完成日期**: 2025-12-10
  - **详细报告**: 详见 docs/development/t023-t024-t025-evaluation-report.md
- [x] T024 [P] [US1] 在 src/domain/document/ 中创建 PreprocessedDocument 领域模型 (preprocessed_document.py) [技术栈: Python标准库, pydantic]
  - 实现完整的PreprocessedDocument领域模型，包含所有必需字段和验证逻辑 ✅
  - 提供业务方法（处理流程管理、元数据操作等） ✅
  - 完整的测试覆盖（15个测试用例） ✅
  - **完成日期**: 2025-12-10
  - **详细报告**: 详见 docs/development/t023-t024-t025-evaluation-report.md
- [x] T025 [P] [US1] 在 src/infrastructure/preprocessing/loaders/ 中创建基础文档加载器接口 (base_loader.py) [技术栈: Python标准库, abc模块, LangChain 1.0]
  - **实现要求**:
    - 定义基础文档加载器接口，兼容LangChain 1.0的BaseLoader接口 ✅
    - 所有加载器必须实现`load()`方法，返回`List[langchain_core.documents.Document]` ✅
    - 可选实现`lazy_load()`方法，支持流式加载（处理大文件） ✅
    - Document对象必须包含：
      - `page_content`: 文档文本内容 ✅
      - `metadata`: 文档元数据（至少包含`source`和`format`字段） ✅
    - 参考LangChain 1.0最佳实践（详见`docs/development/phase3-framework-evaluation.md`） ✅
  - **LangChain 1.0兼容性**: 完全符合LangChain 1.0规范，使用标准`langchain_core.documents.Document`对象 ✅
  - 提供异步加载支持（`aload()`、`alazy_load()`） ✅
  - 提供文档验证机制和格式检测功能 ✅
  - 完整的测试覆盖（20+个测试用例） ✅
  - **完成日期**: 2025-12-10
  - **详细报告**: 详见 docs/development/t023-t024-t025-evaluation-report.md
  - **后续工作建议**: 按照依赖关系顺序实现后续任务



#### 第1组: 基础组件（所有产线共享）

- [x] T038 [P] [US1] 在 src/infrastructure/preprocessing/ 中实现文档格式识别和验证逻辑 (format_detector.py) [技术栈: Python标准库, python-magic/filetype]
  - **实现要求**:
    - 支持识别PDF、DOCX格式（HTML已暂停） ✅
    - 验证文件格式与扩展名是否匹配 ✅
    - 验证文件大小和基本完整性 ✅
    - 返回格式信息供加载器选择使用 ✅
    - 提供统一的格式检测接口，供预处理协调器调用 ✅
  - **注意**: 此任务应在所有加载器之前完成，因为格式识别是加载器选择的基础 ✅
  - **完成日期**: 2025-12-10
  - **代码质量**: 无linter错误，支持深度检测（python-magic/filetype），完善的验证逻辑 ✅

#### 第2组: MinerU产线加载器（优先实现）


- [x] T026A-MinerU [P] [US1] 在 src/infrastructure/preprocessing/loaders/ 中创建MinerU服务适配器 (mineru_adapter.py) [技术栈: Python标准库, requests/aiohttp]
  - **实现要求**:
    - 实现MinerU在线服务适配器接口 ✅
    - 封装MinerU API调用（PDF、DOCX格式解析） ✅
    - 实现统一的响应格式转换（转换为LangChain Document格式） ✅
    - 实现错误处理和日志记录 ✅
    - 支持服务配置管理（从settings.py读取配置，API Token等） ✅
    - 实现服务健康检查和错误重试机制（使用tenacity库） ✅
    - 支持异步处理，避免阻塞主流程 ✅
    - 参考文档: https://mineru.net/apiManage/docs ✅
  - **注意**: 此任务应在T026-MinerU之前完成 ✅
  - **完成日期**: 2025-12-10
  - **代码质量**: 无linter错误，完善的错误处理、重试机制、健康检查 ✅
- [x] T026-MinerU [P] [US1] 在 src/infrastructure/preprocessing/loaders/ 中实现 MinerU PDF 文档加载器 (mineru_pdf_loader.py) [技术栈: MinerU在线服务, requests/aiohttp, LangChain 1.0]
  - **实现要求**:
    - **继承BaseLoader接口**，实现`load()`方法返回`List[langchain_core.documents.Document]` ✅
    - **使用T026A-MinerU实现的服务适配器**，通过适配器调用MinerU服务 ✅
    - MinerU自动去除非主体内容（页眉、页脚、脚注、页码），输出结构化内容 ✅
    - 支持服务配置（API Token等）通过环境变量配置 ✅
    - 支持异步处理，避免阻塞主流程 ✅
    - **Document对象元数据规范**:
      - `source`: 文件路径 ✅
      - `format`: "pdf" ✅
      - `pipeline`: "mineru" ✅
      - `processed_at`: 处理时间（ISO格式） ✅
      - `total_pages`: 总页数 ✅
      - 其他扩展元数据（页面结构、表格数量、公式数量等） ✅
    - 可选实现`lazy_load()`方法，支持按页流式加载（处理大文件） ✅
    - 参考LangChain 1.0集成最佳实践（详见`docs/development/phase3-framework-evaluation.md`） ✅
  - **注意**: 此任务依赖T026A-MinerU完成 ✅
  - **完成日期**: 2025-12-10
  - **代码质量**: 无linter错误，类型注解完整，异常处理完善，支持同步/异步/懒加载 ✅
- [x] T027 [P] [US1] 在 src/infrastructure/preprocessing/loaders/ 中实现 MinerU DOCX 文档加载器 (mineru_docx_loader.py) [技术栈: MinerU在线服务, python-docx(降级), LangChain 1.0]
  - **实现要求**:
    - **继承BaseLoader接口**，实现`load()`方法返回`List[langchain_core.documents.Document]` ✅
    - **使用T026A-MinerU实现的服务适配器**，通过适配器调用MinerU服务处理DOCX文档 ✅
    - **降级方案**: python-docx库（当MinerU服务不可用时自动降级） ✅
    - MinerU自动去除非主体内容，支持多模态内容提取（文本、公式、表格、图表等） ✅
    - 实现完善的错误处理和日志记录 ✅
    - **Document对象元数据规范**:
      - `source`: 文件路径 ✅
      - `format`: "docx" ✅
      - `pipeline`: "mineru" 或 "python-docx" ✅
      - `paragraphs`: 段落数量（如果适用） ✅F:\WhitePaper\data\processed\mineru
      - `processed_at`: 处理时间（ISO格式） ✅
      - 其他扩展元数据（章节结构、表格数量、公式数量等） ✅
    - 参考LangChain 1.0集成最佳实践（详见`docs/development/phase3-framework-evaluation.md`） ✅
  - **注意**: 此任务依赖T026A-MinerU完成 ✅
  - **完成日期**: 2025-12-10
  - **代码质量**: 无linter错误，类型注解完整，异常处理完善 ✅

#### 第3组: 共享清洗组件（两条产线共享，可在加载器之后实现）

- [x] ~~T028 [P] [US1] 在 src/infrastructure/preprocessing/cleaners/ 中创建文本清洗器 (text_cleaner.py) [技术栈: Python标准库, 正则表达式]~~ **已废弃**
  - **废弃原因**: 已被T030A-LLM-AdRemover替代。大模型清洗后的MD文件不存在格式问题，不再需要传统的文本清洗步骤。
  - **废弃日期**: 2025-12-14
  - **替代方案**: 使用T030A-LLM-AdRemover进行智能清洗
- [x] ~~T029 [P] [US1] 在 src/infrastructure/preprocessing/cleaners/ 中创建格式标准化器 (format_normalizer.py) [技术栈: Python标准库, unicodedata]~~ **已废弃**
  - **废弃原因**: 已被T030A-LLM-AdRemover替代。大模型清洗后的MD文件不存在格式问题，不再需要格式标准化步骤。
  - **废弃日期**: 2025-12-14
  - **替代方案**: 使用T030A-LLM-AdRemover进行智能清洗

#### 第4组: MinerU产线清洗组件

- [x] ~~T030-MinerU [P] [US1] 在 src/infrastructure/preprocessing/cleaners/ 中创建MinerU产线噪声去除器 (mineru_noise_remover.py) [技术栈: Python标准库, 正则表达式]~~ **已废弃**
  - **废弃原因**: 已被T030A-LLM-AdRemover替代。基于正则表达式的噪声去除效果不如大模型智能清洗，且大模型清洗后的MD文件不存在格式问题。
  - **废弃日期**: 2025-12-14
  - **替代方案**: 使用T030A-LLM-AdRemover进行智能清洗
- [x] T030A-LLM-AdRemover [P] [US1] 在 src/infrastructure/preprocessing/cleaners/ 中创建基于LLM的广告清洗器 (llm_ad_remover.py) [技术栈: LangChain 1.0, LLM, Agent Middleware]
  - **实现要求**:
    - 使用LangChain 1.0的Agent框架和中间件机制实现智能广告清洗 ✅
    - **必须从T009创建的llm_service获取模型实例**，使用专门的广告清洗模型配置（`ad_cleaning_llm`） ✅
    - 广告清洗模型配置采用OpenAI兼容接口配置方案，在settings.py中单独配置 ✅
    - 支持多模型动态调用，可通过中间件机制动态切换模型（基于LangChain 1.0的AgentMiddleware） ✅
    - 读取Markdown文档内容，使用大模型智能识别并删除：
      - 广告内容 ✅
      - 目录 ✅
      - 图表目录 ✅
      - 其他无意义信息 ✅
    - **保留有价值内容**：
      - 保留所有图片链接信息（`![](images/xxx.jpg)` 格式） ✅
      - 保留文档主体内容 ✅
      - 保留章节结构 ✅
    - 输入输出使用LangChain Document对象格式 ✅
    - 支持配置清洗规则和提示词模板 ✅
    - 实现错误处理和重试机制 ✅
    - 支持批量处理 ✅
  - **技术实现**:
    - 使用LangChain 1.0的`create_agent`创建Agent ✅
    - 使用`AgentMiddleware`实现模型动态调用和中间件机制 ✅
    - 使用结构化输出（Pydantic模型）确保清洗结果格式一致 ✅
    - 参考LangChain 1.0最佳实践（详见`docs/development/phase3-framework-evaluation.md`） ✅
  - **注意**: 此任务依赖T009（llm_service）完成，必须从llm_service获取模型实例 ✅
  - **注意**: 此任务替代了已废弃的T030-MinerU，作为新的默认广告清洗管线 ✅
  - **完成日期**: 2025-12-14
  - **代码质量**: 
    - 文件长度: 603行（< 4000行限制） ✅
    - 无linter错误 ✅
    - UTF-8编码支持完整 ✅
  - **测试覆盖**:
    - 单元测试: `tests/unit/infrastructure/preprocessing/test_llm_ad_remover.py` (738行，51个测试方法) ✅
    - 集成测试: `tests/integration/test_llm_ad_remover_real_files.py` (499行) ✅
    - ~~简单测试脚本: `tests/test_t030_llm_ad_remover_simple.py` (已删除，功能已由集成测试覆盖)~~
  - **实现文件**: `src/infrastructure/preprocessing/cleaners/llm_ad_remover.py`
  - **核心功能**:
    - `LLMAdRemover`: 主清洗器类，支持同步和异步处理 ✅
    - `AdCleaningResult`: 结构化输出Pydantic模型 ✅
    - `DynamicModelMiddleware`: 动态模型调用中间件 ✅
    - `RetryMiddleware`: 重试机制中间件（支持同步和异步） ✅
    - `clean_document()` / `aclean_document()`: 单文档清洗 ✅
    - `clean_documents()` / `aclean_documents()`: 批量清洗 ✅
#### 第5组: 协调器和Agent（需要所有加载器和清洗器）

- [x] T031 [US1] 在 src/infrastructure/preprocessing/ 中创建文档预处理协调器 (preprocessor.py) [技术栈: Python标准库, LangChain 1.0]
  - **实现要求**:
    - 统一协调文档加载和清洗流程（**仅支持MinerU产线**） ✅
    - 根据文档格式自动选择对应的加载器 ✅
      - PDF格式: MinerU PDF加载器（T026-MinerU） ✅
      - DOCX格式: MinerU DOCX加载器（T027） ✅
    - 清洗处理：直接使用T030A-LLM-AdRemover进行清洗，`process_mineru_directory`方法自行实现图片和元数据文件重构 ✅
    - 加载器返回的Document对象传递给清洗器处理 ✅
    - 支持批量处理 ✅
    - 处理流程：格式识别（T038） → 加载器加载（MinerU） → LLM清洗（T030A） → 返回处理后的Document列表 ✅
    - 所有输入输出使用LangChain Document对象格式 ✅
    - 实现完善的错误处理和日志记录 ✅
  - **注意**: 此任务依赖T038、T026-MinerU、T027、T030A-LLM-AdRemover完成 ✅
  - **注意**: 仅支持MinerU产线，PaddleOCR产线已暂停 ✅
  - **完成日期**: 2025-12-15
  - **代码质量**: 
    - 文件长度: 1572行（< 4000行限制） ✅
    - 无linter错误 ✅
    - UTF-8编码支持完整 ✅
    - 完善的类型注解和文档字符串 ✅
  - **测试覆盖**:
    - 真实数据测试: `tests/test_t031_real_document_processing.py` ✅
    - 测试通过: 成功处理2个真实文档（PDF和DOCX），清洗功能正常 ✅
    - 处理时间: 1114.67秒（约18分钟），包含LLM清洗流程 ✅
  - **核心功能**:
    - `process_document()`: 处理单个文档 ✅
    - `process_documents()`: 批量处理文档 ✅
    - `process_mineru_directory()`: 处理MinerU目录中的所有文档 ✅
    - `aprocess_document()` / `aprocess_documents()`: 异步处理支持 ✅
    - 格式自动识别和加载器选择 ✅
    - LLM智能清洗集成 ✅
    - 完善的统计信息和进度跟踪 ✅
  - **详细评估**: 详见 `docs/development/t031-evaluation-report.md` ✅
- [x] T031B [P] [US1] 在 src/infrastructure/preprocessing/cleaners/ 中创建基于LLM的图表转JSON转换器 (llm_chart_to_json_converter.py) [技术栈: LangChain 1.0, LLM]
  - **实现要求**:
    - **创建新的LLM配置**: 在settings.py中创建`ChartToJsonLLMConfig`配置类，用于图表转JSON的专用LLM配置
      - 配置类结构参考`AdCleaningLLMConfig`，采用OpenAI兼容接口配置方案
      - 在`.env`文件中通过环境变量单独配置，使用openai兼容模式（如`CHART_TO_JSON_LLM_BASE_URL`、`CHART_TO_JSON_LLM_API_KEY`等）
      - 在`llm_service.py`中添加`get_chart_to_json_chat_model()`方法，从配置中获取专用模型实例
    - **图表识别能力**:
      - 扫描T031处理后的目录中的`images/`文件夹，识别所有图片文件
      - 使用LLM对每个图片进行分析，判断是否为图表（而非普通图片、照片等）
      - 对于识别为图表的图片，进一步判断是否具有准确的坐标数据（如柱状图、折线图、饼图等结构化图表）
      - 对于不具备准确坐标数据的图表（如概念图、流程图等），可以标记但不需要转换
    - **图表转JSON功能**:
      - 对于识别为具有准确坐标数据的图表，调用LLM将图表转换为JSON格式
      - JSON格式应包含图表的结构化数据（如数据系列、坐标轴、图例等）
      - 使用结构化输出（Pydantic模型）确保JSON格式的一致性
    - **JSON文件命名**:
      - 从对应的json文件（`clean_content_list.json`）中提取对应图表的中文名称/标题
      - JSON文件名使用图表的中文名称（进行文件系统安全的字符处理，如去除特殊字符、限制长度等）
    - **目录结构**:
      - 在T031处理后的输出目录（`data/cleaned/documents/{doc_name}/{extracted_dir}/`）下创建名为`datajson`的新目录
      - 将转换后的JSON文件保存到`datajson/`目录中
      - JSON文件命名格式：`{图表中文名称}.json`（如`储能市场规模增长趋势.json`）
    - **集成到预处理流程**:
      - 可以作为T031预处理协调器的可选功能，在清洗完成后自动执行图表转换
      - 也可以在T032文档预处理Agent中作为工具调用
      - 支持独立调用，处理已清洗的文档目录
    - **错误处理**:
      - 对于无法识别的图片或转换失败的图表，记录错误日志但不中断流程
      - 支持批量处理，处理多个图片时即使部分失败也继续处理其他图片
      - 提供详细的处理统计信息（成功/失败数量、处理时间等）
  - **技术实现**:
    - 使用LangChain 1.0的`create_agent`创建Agent，或直接使用LLM进行图表识别和转换
    - 使用多模态LLM能力（如果支持）进行图片分析，或使用图片描述+文本分析的方式
    - 使用结构化输出（Pydantic模型）定义JSON格式规范
    - 参考LangChain 1.0最佳实践（详见`docs/development/phase3-framework-evaluation.md`）
  - **LangChain 1.0适用能力**:
    - **结构化输出（Structured Output）**: 使用Pydantic定义图表JSON数据模型，结合`response_format`参数（如`ToolStrategy`）实现结构化输出，确保生成符合预期结构的JSON数据
    - **create_agent API**: 使用`create_agent`创建Agent处理图表识别和转换的复杂流程，支持工具调用和错误处理
    - **多模态处理**: 支持调用支持vision的LLM模型（如GPT-4V、Claude 3等）进行图像分析和图表识别
    - **JsonOutputParser**: 使用`JsonOutputParser`将模型输出解析为JSON格式，或直接使用结构化输出获得Pydantic对象
    - **标准化内容块**: 利用LangChain 1.0的标准化内容块统一不同vision模型的输入输出格式
  - **注意**: 此任务依赖T009（llm_service）和T031完成
  - **注意**: 必须从T009创建的llm_service获取模型实例，使用新的`get_chart_to_json_chat_model()`方法
  - **注意**: 仅处理T031中已处理的文档目录（`data/cleaned/documents/`下的目录）
  - **完成日期**: 2025-12-16
  - **测试覆盖**:
    - 单元测试: `tests/test_t031b_chart_to_json_converter.py` (8个测试用例，100%通过)
    - 集成测试: 真实文档处理测试，处理15个图像文件
    - ~~演示脚本: `tests/simple_chart_to_json.py`、`tests/temp_single_image_to_json.py` (已删除，功能已由正式测试覆盖)~~
  - **功能验证**:
    - GLM-4.6V多模态图表识别 ✅
    - 饼图和柱状图数据提取 ✅
    - 智能文件命名（从clean_content_list.json提取标题）✅
    - 批量处理和错误恢复 ✅
    - 中文路径和文件名处理 ✅
  - **性能指标**:
    - 平均处理时间: 11秒/图像
    - API成功率: 93.3%
    - 总执行时间: 2分45秒（15个图像）
  - **安全性验证**:
    - 无无限循环风险 ✅
    - 无重复上传问题 ✅
    - 无内存泄漏 ✅
  - **代码质量**:
    - 文件长度: 1288行（< 4000行限制）✅
    - 无linter错误 ✅
    - UTF-8编码支持完整 ✅
  - **详细报告**: 详见 `tests/LLM图表转JSON转换器测试报告.md`
- [x] T032 [US1] 在 src/application/agents/ 中实现文档预处理Agent (document_preprocessor.py) [技术栈: LangChain 1.0]
  - **实现要求**:
    - **基于BaseAgent实现**（T018已完成），继承`src.application.agents.agent_base.BaseAgent`
    - 使用LangChain 1.0的Agent框架和工具系统
    - **核心功能**:
      - `load_and_process(file_path: str, format: str) -> List[Document]`: 加载并处理文档（完整流程）
      - `process_document(document: Document) -> Document`: 处理单个Document对象
      - `process_documents(documents: List[Document]) -> List[Document]`: 批量处理Document列表
    - **集成T031预处理协调器**:
      - 调用T031预处理协调器执行文档加载和清洗
      - 根据文档格式自动选择对应的加载器（MinerU PDF/DOCX加载器）
      - 支持将加载器封装为LangChain工具（可选）
    - **清洗流程**（使用LLM智能清洗）:
      - 直接使用T030A-LLM-AdRemover进行清洗
      - 清洗器: T030A-LLM-AdRemover（LLM智能广告清洗）
    - **Document对象处理**:
      - 输入：LangChain Document对象（来自加载器）
      - 输出：处理后的LangChain Document对象（保留原始元数据，添加处理信息）
      - 元数据更新：添加`cleaned=True`、`processed_at`等处理信息
    - **错误处理**:
      - 完善的异常处理和日志记录
      - 支持处理失败时的降级策略
    - **BaseAgent框架集成**（优化项）:
      - **将LLMAdRemover封装为LangChain工具**:
        - 创建`clean_document_tool`工具，封装`LLMAdRemover.clean_document()`方法
        - 工具应接受Document对象作为输入，返回清洗后的Document对象
        - 工具描述应清晰说明清洗功能和保留内容规则
        - 使用`@tool`装饰器或`StructuredTool.from_function()`创建工具
      - **创建DocumentPreprocessorAgent类**:
        - 继承`BaseAgent`，实现`get_tools()`方法返回清洗工具
        - 在`get_tools()`中返回封装好的`clean_document_tool`
        - 利用BaseAgent的中间件系统（自动集成ErrorHandlingMiddleware、AgentLoggingMiddleware）
        - 支持状态持久化（通过BaseAgent的Checkpointer配置）
        - 支持记忆管理（通过BaseAgent的LangMem集成）
      - **Agent工具调用流程**:
        - Agent接收预处理请求后，可以调用`clean_document_tool`进行清洗
        - 工具调用结果自动记录到Agent执行历史中
        - 支持工具调用的错误处理和重试（通过BaseAgent中间件）
      - **架构优势**:
        - 保持`LLMAdRemover`的独立性（可作为独立组件使用）
        - 统一使用BaseAgent的生命周期管理
        - 自动获得错误处理、日志记录、状态持久化等能力
        - 符合LangChain 1.0最佳实践（工具化设计模式）
    - **集成T031B图表转JSON功能**（推荐）:
      - 在预处理流程中集成T031B的图表转JSON功能（推荐，可通过配置控制）
      - 将图表转换作为预处理流程的可选步骤，在清洗完成后执行
      - 将`LLMChartToJsonConverter`封装为LangChain工具（`chart_to_json_tool`）
      - 工具应接受文档目录路径作为输入，返回转换统计信息
      - 支持通过配置参数控制是否启用图表转换功能（`enable_chart_conversion: bool = True`）
      - 支持异步处理，避免阻塞主流程
      - 提供详细的处理统计信息（成功/失败数量、处理时间等）
    - **注意**: 如需使用LLM，必须从T009创建的llm_service获取模型实例
    - **注意**: 此任务依赖T031完成，推荐依赖T031B（如果启用图表转换，可通过配置控制）
    - **注意**: 仅支持MinerU产线，PaddleOCR产线已暂停
    - 参考LangChain 1.0集成最佳实践（详见`docs/development/phase3-framework-evaluation.md`）
    - 参考优化评估报告（详见`docs/development/phase3-optimization-evaluation.md`）
  - **完成日期**: 2025-12-17
  - **代码质量**: 
    - 文件长度: 404行（< 4000行限制）✅
    - 无linter错误 ✅
    - UTF-8编码支持完整 ✅
    - 完善的类型注解和文档字符串 ✅
  - **测试覆盖**: 
    - 单元测试: `tests/test_t032_document_preprocessor_agent.py` (7个测试用例，6个通过，1个跳过) ✅
    - 代码覆盖率: 56% ✅
    - 测试通过: Agent初始化、工具获取、文档处理、批量处理等功能正常 ✅
  - **核心功能**: 
    - `DocumentPreprocessorAgent`: 文档预处理Agent类，继承BaseAgent ✅
    - `get_tools()`: 返回清洗工具和图表转换工具 ✅
    - `load_and_process()`: 加载并处理文档（完整流程）✅
    - `process_document()`: 处理单个Document对象 ✅
    - `process_documents()`: 批量处理Document列表 ✅
    - `create_clean_document_tool()`: 创建文档清洗工具 ✅
    - `create_chart_to_json_tool()`: 创建图表转JSON工具 ✅
    - 集成T031预处理协调器 ✅
    - 集成T030A-LLM-AdRemover ✅
    - 集成T031B图表转JSON转换器（可选）✅

#### 第6组: 异步任务（需要协调器或Agent）

- [x] T037 [US1] 在 src/infrastructure/tasks/ 中创建文档预处理异步任务 (document_tasks.py) [技术栈: Arq]
  - **实现要求**:
    - 封装文档预处理流程为异步任务，支持大文件处理和批量处理 ✅
    - 使用Arq任务队列，支持任务状态跟踪和错误重试 ✅
    - 调用T031预处理协调器或T032文档预处理Agent执行实际处理 ✅
    - **支持T031B图表转JSON功能**（推荐）: 在预处理完成后可选执行图表转换任务 ✅
      - 添加`enable_chart_conversion`参数，默认值为`True` ✅
      - 在任务状态中添加图表转换进度信息 ✅
      - 记录图表转换的成功/失败数量 ✅
      - 图表转换失败不应导致整个预处理任务失败 ✅
    - 支持任务进度报告和结果回调 ✅
    - 集成任务监控和日志记录 ✅
  - **注意**: 此任务依赖T031或T032完成，推荐依赖T031B（如果启用图表转换，可通过参数控制），应在T033之前完成 ✅
  - **完成日期**: 2025-12-17
  - **代码质量**: 
    - 文件长度: 699行（< 4000行限制）✅
    - 无linter错误 ✅
    - UTF-8编码支持完整 ✅
    - 完善的类型注解和文档字符串 ✅
  - **测试覆盖**: 
    - 单元测试: `tests/test_t037_document_tasks.py` (4个测试用例) ✅
    - 测试通过: 文档预处理、批量处理、图表转换、错误处理等功能正常 ✅
  - **核心功能**: 
    - `DocumentProcessingTask`: 文档预处理异步任务类 ✅
    - `BatchDocumentProcessingTask`: 批量文档预处理任务类 ✅
    - `create_document_processing_task()`: 任务工厂函数 ✅
    - `create_batch_document_processing_task()`: 批量任务工厂函数 ✅
    - `process_document_async()`: 便捷函数（单个文档）✅
    - `process_documents_async()`: 便捷函数（多个文档）✅
    - `process_batch_documents_async()`: 便捷函数（批量文档）✅
    - 支持T031协调器和T032 Agent两种处理方式 ✅
    - 支持T031B图表转JSON功能（可选，默认启用）✅
    - 任务状态跟踪和错误重试 ✅
    - 完善的日志记录和监控 ✅
  - **详细报告**: 详见 `docs/development/t037-completion-evaluation.md` ✅

#### 第7组: 服务层（需要Agent和异步任务）

- [x] T033 [US1] 在 src/application/services/ 中创建文档服务 (document_service.py) [技术栈: Python标准库, LangChain 1.0]
  - **实现要求**:
    - 封装文档预处理Agent（T032），提供业务层接口 ✅
    - 处理文档上传、格式识别、预处理等业务流程 ✅
    - 输入输出使用LangChain Document对象格式 ✅
    - 支持异步处理和批量处理（调用T037异步任务） ✅
    - 集成文档存储（SQLite）和元数据管理 ✅
  - **注意**: 此任务依赖T032和T037完成 ✅
  - **完成日期**: 2025-12-17
  - **代码质量**: 
    - 文件长度: 829行（< 4000行限制） ✅
    - 无linter错误 ✅
    - UTF-8编码支持完整 ✅
    - 完善的类型注解和文档字符串 ✅
  - **核心功能**: 
    - `DocumentService`: 文档服务类，封装文档预处理Agent和异步任务 ✅
    - `detect_format()`: 文档格式检测 ✅
    - `validate_document()`: 文档验证 ✅
    - `create_document_record()`: 创建文档记录（保存到SQLite） ✅
    - `upload_and_process()`: 上传并处理文档（同步） ✅
    - `upload_and_process_async()`: 上传并处理文档（异步） ✅
    - `upload_and_process_batch_async()`: 批量上传并处理文档（异步） ✅
    - `get_document()` / `list_documents()`: 文档查询 ✅
    - `process_document()` / `process_documents()`: 处理LangChain Document对象 ✅
    - 集成SQLite存储和元数据管理 ✅
    - LangChain Document对象与领域模型Document的转换 ✅
    - 完整的错误处理和日志记录 ✅
  - **技术实现**: 
    - 遵循LangChain 1.0最佳实践（不使用LangSmith） ✅
    - 统一使用LangChain Document对象格式 ✅
    - 支持同步和异步处理 ✅
    - 完整的文档状态管理（PENDING → PARSING → INDEXED/FAILED） ✅

#### 第8组: 接口层（需要服务层）

- [x] T035 [US1] 在 src/interfaces/api/schemas/ 中创建文档相关Schema (document_schemas.py) [技术栈: FastAPI, pydantic]
  - **实现要求**:
    - 定义文档上传、预处理、查询等API的请求和响应Schema
    - 使用Pydantic进行数据验证
  - **注意**: 此任务应在T034之前完成，因为API路由需要Schema
- [x] T034 [US1] 在 src/interfaces/api/routes/ 中创建文档上传和预处理API路由 (documents.py) [技术栈: FastAPI, python-multipart]
  - **实现要求**:
    - 实现文档上传接口
    - 实现文档预处理接口（调用T033文档服务）
    - 实现文档查询接口
    - 使用T035定义的Schema
  - **注意**: 此任务依赖T033和T035完成
- [x] T036 [US1] 在 src/interfaces/cli/ 中创建文档上传CLI命令 (documents.py) [技术栈: Typer, Rich]
  - **实现要求**:
    - 实现文档上传CLI命令（调用T033文档服务）
    - 实现文档预处理CLI命令
    - 实现文档查询CLI命令
    - 使用Rich进行输出美化
  - **注意**: 此任务依赖T033完成

#### 第9组: 增强功能（可选，可在最后实现）

- [x] T039 [US1] 在 src/infrastructure/preprocessing/ 中实现预处理质量报告生成功能 (quality_report.py) [技术栈: Python标准库]
  - **实现要求**:
  - **输入**: 一次预处理批处理任务的 Job ID（例如异步任务ID或批处理任务ID），而不是单个文件路径
  - 从 `documents` 表和相关任务状态表中读取该 Job 关联的所有文档的 `metadata` 与统计信息
  - 聚合已有流水线元数据（格式识别结果、LLMAdRemover 清洗统计、图表转换统计、错误信息等），生成**结构化质量报告**（JSON/Pydantic模型）
  - 支持生成面向用户/运维的可读化报告（如 Markdown 文本），便于 CLI / API / 前端展示
  - 复用现有日志和中间件输出，不在 T039 内重复实现日志采集逻辑
 - [x] T040 [US1] 在 src/infrastructure/preprocessing/ 中完善错误处理和日志记录 (error_handler.py, logging_config.py) [技术栈: Python标准库logging]
  - **实现要求**:
  - 为 MinerU 适配器、预处理协调器、LLMAdRemover 等预处理关键步骤补充**领域特定**的结构化日志字段（例如清洗前后长度、广告删除比例、图表转换成功率等）
  - 所有错误与日志输出统一接入项目已有的异常体系（`src/shared/exceptions`）和日志体系（`src/shared/utils/logging.py`、T022 中间件），不再单独创建一套全局 logging 配置
  - 将底层服务/LLM/MinerU 的错误统一映射为项目自定义异常，便于 T022/T137/T138 进行统一处理和重试
  - **完成日期**: 2025-12-17
  - **测试文件**: `tests/test_t040_preprocessing_error_handling.py`（15 个用例全部通过）
- [x] T040B [US1] 在 src/infrastructure/preprocessing/cleaners/ 中实现总结中间件 (summarization_middleware.py) [技术栈: LangChain 1.0, Agent Middleware]
  - **实现要求**:
    - **实现SummarizationMiddleware中间件**，用于处理超长文档，防止token溢出 ✅
    - 继承`AgentMiddleware`，实现`wrap_model_call()`和`awrap_model_call()`方法 ✅
    - **核心功能**:
      - 检测文档长度（通过计算messages中的总token数或字符数） ✅
      - 当文档超过`max_tokens`阈值时，自动触发总结流程 ✅
      - 使用LLM对超长文档进行分段总结，保留关键信息 ✅
      - 将总结后的内容传递给下游处理流程 ✅
    - **配置参数**:
      - `max_tokens: int = 100000`: 文档长度阈值（字符数或token数） ✅
      - `chunk_size: int = 50000`: 分段大小，用于分段总结 ✅
      - `overlap_size: int = 5000`: 分段重叠大小，确保上下文连贯 ✅
      - `summary_model`: 可选，用于总结的专用模型（如果与主模型不同） ✅
    - **实现策略**:
      - 如果文档长度 <= `max_tokens`，直接传递给下游处理 ✅
      - 如果文档长度 > `max_tokens`，执行以下步骤：
        1. 将文档分段（使用`chunk_size`和`overlap_size`） ✅
        2. 对每个分段使用LLM进行总结（保留关键信息、章节结构、图片链接等） ✅
        3. 合并所有分段的总结结果 ✅
        4. 将合并后的总结内容传递给下游处理 ✅
    - **集成位置**:
      - 在`LLMAdRemover`中集成，支持通过初始化参数控制是否启用 ✅
      - 应在清洗之前执行（先总结，再清洗） ✅
      - 可通过`LLMAdRemover`的初始化参数控制是否启用 ✅
    - **使用场景**:
      - 处理超长PDF文档（数百页） ✅
      - 处理包含大量内容的DOCX文档 ✅
      - 防止模型token限制导致的处理失败 ✅
    - **注意事项**:
      - 总结过程可能会丢失部分细节信息，需要权衡 ✅
      - 总结本身也会消耗token，需要合理设置阈值 ✅
      - 应保留文档的章节结构和关键元数据 ✅
      - 必须保留所有图片链接信息（`![](images/xxx.jpg)`格式） ✅
    - **技术实现**:
      - 使用LangChain 1.0的`AgentMiddleware`接口 ✅
      - 从T009创建的llm_service获取总结模型（如果配置了专用模型） ✅
      - 支持同步和异步处理 ✅
      - 实现完善的错误处理和日志记录 ✅
    - **注意**: 此任务依赖T009（llm_service）和T030A-LLM-AdRemover完成 ✅
    - **注意**: 这是优化项，可根据实际需求决定是否实现 ✅
    - 参考LangChain 1.0最佳实践（详见`docs/development/phase3-framework-evaluation.md`） ✅
    - 参考优化评估报告（详见`docs/development/phase3-optimization-evaluation.md`） ✅
  - **完成日期**: 2025-12-18
  - **代码质量**: 
    - 文件长度: 892行（< 4000行限制） ✅
    - 无linter错误 ✅
    - UTF-8编码支持完整 ✅
    - 完善的类型注解和文档字符串 ✅
  - **核心功能**: 
    - `SummarizationMiddleware`: Agent中间件类，继承AgentMiddleware ✅
    - `SummarizationHelper`: 辅助类，用于直接模型调用场景 ✅
    - `wrap_model_call()` / `awrap_model_call()`: 同步/异步模型调用包装 ✅
    - `summarize_if_needed()` / `asummarize_if_needed()`: 同步/异步总结方法 ✅
    - 文档长度检测、分段总结、错误处理和降级策略 ✅
  - **集成情况**: 
    - 已集成到`LLMAdRemover`中，支持通过`enable_summarization`参数控制 ✅
    - 在`clean_document()`和`aclean_document()`方法中自动应用 ✅
    - 总结在清洗之前执行，防止token溢出 ✅
 - [x] T040C [US1] 在 src/application/agents/ 与 src/application/services/ 中集成长文摘要中间件控制逻辑（document_preprocessor.py, document_service.py, document_tasks.py）[技术栈: LangChain 1.0, Agent Middleware]
  - **实现要求**:
  - 将 T040B 的 SummarizationMiddleware 作为 BaseAgent/DocumentPreprocessorAgent 的可配置中间件进行统一注册 ✅
  - 在文档预处理 Agent（T032）、文档服务（T033）和异步任务（T037）中**默认启用**长文摘要中间件 ✅
  - 自动判断是否触发摘要：基于模型 token 计数或内容长度，当预计上下文超出模型安全阈值时才执行分段总结，否则直接透传原文 ✅
  - 支持通过配置（settings.py / llm_service）覆盖阈值和是否启用，但默认开启以保护长文场景 ✅
  - 将"是否摘要、摘要前后长度、触发原因"等信息写入文档或任务的 metadata，以便 T039 质量报告使用 ✅
  - 保证与 T022 的错误处理/日志中间件兼容，中间件执行顺序为：SummarizationMiddleware 在 RetryMiddleware 之前 ✅
  - **完成日期**: 2025-12-18
  - **核心实现**:
    - 在 `settings.py` 中添加了 `SummarizationMiddlewareConfig` 配置类，支持通过环境变量配置 ✅
    - 在 `BaseAgent._build_middleware()` 中集成 SummarizationMiddleware，确保在错误处理中间件之前执行 ✅
    - 默认启用 SummarizationMiddleware（通过全局配置控制），所有基于 BaseAgent 的 Agent 自动继承 ✅
    - `SummarizationMiddleware._log_summarization()` 方法记录摘要信息到 ModelRequest.state 和日志中 ✅
    - 摘要信息包含：是否摘要、摘要前后长度、压缩比、触发原因、阈值等 ✅
  - **技术实现**:
    - 中间件执行顺序：日志记录 → SummarizationMiddleware → 错误处理 → HITL（符合 LangChain 1.0 最佳实践）✅
    - 支持通过 AgentConfig.summarization_config 覆盖全局配置 ✅
    - 摘要信息通过 ModelRequest.state 传递，便于后续提取并写入文档 metadata ✅

#### 第10组: PaddleOCR产线（已暂停，待MinerU产线稳定后考虑实现）

**状态**: ⏸️ **已暂停** - 当前聚焦MinerU产线和LLM智能清洗，PaddleOCR产线暂不实现

### 产线2: PaddleOCR产线 (已暂停)

- [ ] ~~T026A-PaddleOCR [P] [US1] 在 src/infrastructure/preprocessing/loaders/ 中创建PaddleOCR服务适配器 (paddleocr_adapter.py)~~ **⏸️ 已暂停**
  - **暂停原因**: 当前聚焦MinerU产线和LLM智能清洗，PaddleOCR产线暂不实现
  - **后续计划**: 待MinerU产线稳定后，根据实际需求评估是否需要实现
- [ ] ~~T026-PaddleOCR [P] [US1] 在 src/infrastructure/preprocessing/loaders/ 中实现 PaddleOCR PDF 文档加载器 (paddleocr_pdf_loader.py)~~ **⏸️ 已暂停**
  - **暂停原因**: 当前聚焦MinerU产线和LLM智能清洗，PaddleOCR产线暂不实现
- [ ] ~~T030-PaddleOCR [P] [US1] 在 src/infrastructure/preprocessing/cleaners/ 中创建PaddleOCR产线噪声去除器 (paddleocr_noise_remover.py)~~ **⏸️ 已暂停**
  - **暂停原因**: 当前聚焦MinerU产线和LLM智能清洗，PaddleOCR产线暂不实现
  - **注意**: 如果未来实现PaddleOCR产线，将直接使用T030A-LLM-AdRemover进行清洗，不再需要专门的PaddleOCR噪声去除器
- [ ] ~~T040A [US1] 完成PaddleOCR产线后更新相关任务以支持两条产线~~ **⏸️ 已暂停**
  - **暂停原因**: PaddleOCR产线已暂停，此任务不再需要

**检查点**: 此时, 用户故事 1 应该完全功能化且可独立测试

**阶段3当前状态总结**:
- ✅ **已完成**: MinerU产线（PDF/DOCX加载器）、LLM智能广告清洗（T030A）、格式识别（T038）、文档预处理协调器（T031）
- 📋 **新增任务**: 图表转JSON转换器（T031B）- 在T031基础上新增的图表识别和转换功能
- 🔄 **进行中**: 文档预处理Agent（T032）
- ⏸️ **已暂停**: PaddleOCR产线相关任务（T026A-PaddleOCR、T026-PaddleOCR、T030-PaddleOCR、T040A）
- 📋 **后续任务**: 异步任务（T037）、服务层（T033）、接口层（T034/T035/T036）、增强功能（T039/T040）
- 🔗 **关联任务**: T174（阶段9的图表生成能力）可以利用T031B生成的图表JSON数据

---

## 阶段 4: 用户故事 2 - 建立本地知识库 (优先级: P1)🎯 MVP

**目标**: 实现文档解析和多模式索引构建，建立结构化的知识库。知识库支持多种数据源：用户上传的文档（通过文档预处理流程）和网络检索数据（通过信息源爬取任务获取的网站内容，建立索引后进入知识库）

**独立测试**: 可以通过上传一个或多个预处理后的文档，验证系统能够成功解析文档内容、建立索引，并通过简单的检索查询验证知识库是否正常工作。即使只实现这个功能，用户也能获得一个可用的文档管理系统。

### 用户故事 2 的实施

- [ ] T041 [P] [US2] 在 src/domain/knowledge_base/ 中创建 KnowledgeEntry 领域模型 (knowledge_entry.py) [技术栈: Python标准库, pydantic]
- [ ] T042 [P] [US2] 在 src/domain/knowledge_base/ 中创建 DocumentChunk 领域模型 (document_chunk.py) [技术栈: Python标准库, pydantic]
- [ ] T043 [P] [US2] 在 src/infrastructure/parsing/ 中实现 PDF 解析器 (pdf_parser.py) [技术栈: PaddleOCR在线服务(默认), MinerU在线服务(备选), 复用T026的PDF处理服务适配器]
  - **实现要求**:
    - 复用阶段3中T026实现的PDF处理服务适配器
    - 在预处理结果基础上进行深度解析，提取结构化信息（章节、段落、标题层次）
    - 提取元数据（文档标题、作者、创建时间等）
    - 支持表格、图片等非文本内容的识别和提取
- [ ] T044 [P] [US2] 在 src/infrastructure/parsing/ 中实现 HTML 解析器 (html_parser.py) [技术栈: llamaIndex BeautifulSoupWebReader, BeautifulSoup4]
- [ ] T044A [P] [US2] 在 src/infrastructure/parsing/ 中实现 DOCX 解析器 (docx_parser.py) [技术栈: 待阶段3评估确定]
  - **实现要求**:
    - 基于阶段3中T027确定的DOCX处理方案实现解析器
    - 在预处理结果基础上进行深度解析，提取结构化信息（章节、段落、标题层次）
    - 提取元数据（文档标题、作者、创建时间等）
    - 支持表格、图片等非文本内容的识别和提取
- [ ] T045 [P] [US2] 在 src/infrastructure/parsing/ocr/ 中集成 OCR 处理服务 (ocr_processor.py) [技术栈: PaddleOCR在线服务, MinerU在线服务]
  - **实现要求**:
    - 主要用于处理PDF中的扫描页面和HTML中的图片
    - 复用阶段3中T026实现的PDF处理服务适配器
    - 支持图片OCR识别，提取图片中的文字内容
    - 识别结果与文本提取结果合并，形成完整的文档内容
- [ ] T046 [P] [US2] 在 src/infrastructure/indexing/ 中实现向量索引构建器 (vector_index.py) [技术栈: llamaIndex, Chroma, 向量嵌入模型]
  - **注意**: 必须从T009创建的llm_service获取Embedding模型实例
- [ ] T047 [P] [US2] 在 src/infrastructure/indexing/ 中实现 BM25 索引构建器 (bm25_index.py) [技术栈: rank-bm25]
- [ ] T048 [P] [US2] 在 src/infrastructure/indexing/ 中实现元数据索引构建器 (metadata_index.py) [技术栈: SQLite]
- [ ] T049 [P] [US2] 在 src/infrastructure/indexing/ 中实现知识图谱构建器 (knowledge_graph.py) [技术栈: NetworkX, 实体关系提取(可使用LLM或spaCy)]
  - **注意**: 如需使用LLM进行实体关系提取，必须从T009创建的llm_service获取模型实例
- [ ] T050 [US2] 在 src/application/services/ 中创建知识库服务 (knowledge_base_service.py) [技术栈: Python标准库]
- [ ] T051 [US2] 在 src/infrastructure/tasks/ 中创建文档解析和索引构建异步任务 (indexing_tasks.py) [技术栈: Arq]
- [ ] T052 [US2] 实现文档分块策略（按章节和段落） [技术栈: llamaIndex NodeParser, SentenceSplitter]
- [ ] T053 [US2] 实现向量嵌入生成（使用llamaIndex） [技术栈: llamaIndex Embedding]
  - **注意**: 必须从T009创建的llm_service获取Embedding模型实例
- [ ] T054 [US2] 实现知识图谱实体和关系提取 [技术栈: LLM(通过LangChain调用), NetworkX, 或spaCy NER]
  - **注意**: 如需使用LLM，必须从T009创建的llm_service获取模型实例
- [ ] T055 [US2] 在 src/interfaces/api/routes/ 中创建知识库管理API路由 (knowledge_base.py) [技术栈: FastAPI]
- [ ] T056 [US2] 在 src/interfaces/cli/ 中创建知识库管理CLI命令 (knowledge_base.py) [技术栈: Typer, Rich]
- [ ] T057 [US2] 添加索引构建进度跟踪和状态管理 [技术栈: SQLite, Python标准库]
- [ ] T058 [US2] 添加错误处理和日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 用户故事 1 和 2 都应该独立运行

---

## 阶段 5: MVP 4步流程 - 储能行业文档生成 (优先级: P0)🚀 核心流程

**目的**: 实现从行业选择到草稿生成的完整4步流程，专注于储能行业用例，并与前端集成

**目标**: 构建最基础的文档生成流程：第一步选择储能行业分析和储能行业数据库，第二步手写大纲并AI优化大纲，第三步信息源爬取（储能相关网站），第四步根据前3步生成草稿大纲，草稿大纲中的素材需能链接到具体的网络文章和本地文章，方便追溯。

**前置条件**: 完成阶段1（设置）、阶段2（基础）、阶段3（用户故事1 - 文档预处理与清洗）和阶段4（用户故事2 - 建立本地知识库）后，优先完成此阶段。RAG数据库和文档清洗是基础，必须在4步流程之前完成。

### 第一步：行业和数据库选择

- [ ] T200 [MVP] 在 src/domain/agent/ 中创建 Industry 领域模型 (industry.py)，包含储能行业等预定义行业 [技术栈: Python标准库, pydantic]
- [ ] T201 [MVP] 在 src/domain/knowledge_base/ 中创建 IndustryDatabase 领域模型 (industry_database.py)，支持储能行业数据库 [技术栈: Python标准库, pydantic]
- [ ] T202 [MVP] 在 src/application/services/ 中创建行业选择服务 (industry_selection_service.py) [技术栈: Python标准库]
- [ ] T203 [MVP] 实现行业列表获取功能（储能行业、能源行业等预定义行业） [技术栈: SQLite]
- [ ] T204 [MVP] 实现行业数据库列表获取功能（储能行业数据库、储能行业分析数据库等） [技术栈: SQLite]
- [ ] T205 [MVP] 实现行业和数据库选择保存功能 [技术栈: SQLite]
- [ ] T206 [MVP] 在 src/interfaces/api/routes/ 中创建行业选择API路由 (industry_selection.py) [技术栈: FastAPI]
- [ ] T207 [MVP] 在 src/interfaces/api/schemas/ 中创建行业选择相关Schema (industry_selection_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T208 [MVP] 创建前端集成接口（行业选择组件、数据库选择组件） [技术栈: FastAPI RESTful API]

### 第二步：大纲手写和AI优化

- [ ] T209 [MVP] 在 src/domain/agent/ 中创建 Outline 领域模型 (outline.py)，支持手写大纲输入 [技术栈: Python标准库, pydantic]
- [ ] T210 [MVP] 在 src/domain/agent/ 中创建 OptimizedOutline 领域模型 (optimized_outline.py) [技术栈: Python标准库, pydantic]
- [ ] T211 [MVP] 在 src/application/agents/ 中实现大纲优化Agent (outline_optimizer_mvp.py) [技术栈: LangChain 1.0, LangGraph, LLM]
  - **注意**: 必须从T009创建的llm_service获取LLM模型实例
- [ ] T212 [MVP] 实现手写大纲输入功能（支持文本输入、结构化输入） [技术栈: Python标准库]
- [ ] T213 [MVP] 实现AI优化大纲功能（基于选择的行业和数据库上下文进行优化） [技术栈: LangChain 1.0, LLM, PromptTemplate]
  - **注意**: 必须从T009创建的llm_service获取LLM模型实例
- [ ] T214 [MVP] 实现大纲优化建议展示（新增章节、调整顺序、完善描述） [技术栈: Python标准库]
- [ ] T215 [MVP] 实现大纲接受/拒绝优化建议功能 [技术栈: SQLite]
- [ ] T216 [MVP] 在 src/interfaces/api/routes/ 中创建大纲管理API路由 (outline_mvp.py) [技术栈: FastAPI]
- [ ] T217 [MVP] 在 src/interfaces/api/schemas/ 中创建大纲相关Schema (outline_mvp_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T218 [MVP] 创建前端集成接口（大纲编辑器、优化建议展示组件） [技术栈: FastAPI RESTful API]

### 第三步：信息源爬取（储能行业网站）

- [ ] T219 [MVP] 在 src/domain/knowledge_base/ 中创建 WebDataSource 领域模型 (web_data_source.py) [技术栈: Python标准库, pydantic]
- [ ] T220 [MVP] 在 src/infrastructure/crawling/ 中创建网页爬取器 (web_crawler.py) [技术栈: Scrapy, BeautifulSoup4, requests, aiohttp]
- [ ] T221 [MVP] 在 src/infrastructure/crawling/ 中创建内容提取器 (content_extractor.py) [技术栈: BeautifulSoup4, readability-lxml, trafilatura]
- [ ] T222 [MVP] 实现储能行业网站列表管理（预定义5-8个储能相关网站） [技术栈: SQLite]
- [ ] T223 [MVP] 实现网站爬取功能（支持指定深度爬取、正文提取、去噪处理） [技术栈: Scrapy/自定义爬虫, BeautifulSoup4]
- [ ] T224 [MVP] 实现爬取内容索引功能（建立页面级和段落级索引，利用已有的RAG数据库索引能力，索引后的内容进入知识库，与本地知识库统一检索） [技术栈: llamaIndex, Chroma(向量索引), rank-bm25(BM25索引), SQLite(元数据索引)]
- [ ] T225 [MVP] 实现爬取进度跟踪和状态管理 [技术栈: SQLite, Python标准库]
- [ ] T226 [MVP] 在 src/infrastructure/tasks/ 中创建网站爬取异步任务 (crawling_tasks.py) [技术栈: Arq]
- [ ] T227 [MVP] 在 src/interfaces/api/routes/ 中创建信息源爬取API路由 (web_crawling.py) [技术栈: FastAPI]
- [ ] T228 [MVP] 在 src/interfaces/api/schemas/ 中创建爬取相关Schema (crawling_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T229 [MVP] 创建前端集成接口（爬取管理界面、进度展示组件） [技术栈: FastAPI RESTful API, WebSocket(可选)]

### 第四步：草稿生成（带素材追溯链接）

- [ ] T230 [MVP] 在 src/domain/agent/ 中创建 Draft 领域模型 (draft.py) [技术栈: Python标准库, pydantic]
- [ ] T231 [MVP] 在 src/domain/agent/ 中创建 SourceReference 领域模型 (source_reference.py)，支持链接到网络文章和本地文章 [技术栈: Python标准库, pydantic]
- [ ] T232 [MVP] 在 src/application/agents/ 中实现草稿生成Agent (draft_generator_mvp.py) [技术栈: LangChain 1.0, LangGraph, LLM]
  - **注意**: 必须从T009创建的llm_service获取LLM模型实例
- [ ] T233 [MVP] 实现基于优化大纲和信息源的草稿生成功能（利用已有知识库进行RAG检索，统一检索本地知识库和网络检索数据） [技术栈: LangChain 1.0, llamaIndex QueryEngine, Chroma检索, rank-bm25检索]
- [ ] T234 [MVP] 实现素材引用嵌入功能（每个段落/章节关联具体的信息源） [技术栈: Python标准库]
- [ ] T235 [MVP] 实现网络文章链接功能（URL链接、段落定位、关键词高亮） [技术栈: Python标准库]
- [ ] T236 [MVP] 实现本地文章链接功能（文件路径、段落定位、页码定位） [技术栈: Python标准库]
- [ ] T237 [MVP] 实现草稿中素材追溯显示功能（在草稿中标记引用的素材来源） [技术栈: Python标准库, Markdown/HTML渲染]
- [ ] T238 [MVP] 实现素材来源点击跳转功能（支持跳转到原文位置） [技术栈: Python标准库]
- [ ] T239 [MVP] 在 src/interfaces/api/routes/ 中创建草稿生成API路由 (draft_mvp.py) [技术栈: FastAPI]
- [ ] T240 [MVP] 在 src/interfaces/api/schemas/ 中创建草稿相关Schema (draft_mvp_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T241 [MVP] 在 src/infrastructure/tasks/ 中创建草稿生成异步任务 (draft_tasks_mvp.py) [技术栈: Arq]
- [ ] T242 [MVP] 创建前端集成接口（草稿编辑器、素材追溯展示组件、跳转链接组件） [技术栈: FastAPI RESTful API]

### 前端集成和完整流程

- [ ] T243 [MVP] 创建4步流程的前端页面组件（步骤导航、步骤内容区） [技术栈: 前端框架(React/Vue等)]
- [ ] T244 [MVP] 实现前端流程状态管理（步骤进度、数据传递） [技术栈: 前端状态管理(Redux/Pinia等)]
- [ ] T245 [MVP] 实现前端与后端API的完整集成 [技术栈: Axios/Fetch API]
- [ ] T246 [MVP] 实现前端错误处理和用户反馈 [技术栈: 前端框架]
- [ ] T247 [MVP] 添加前端数据验证和用户提示 [技术栈: 前端验证库(如Yup/Zod)]
- [ ] T248 [MVP] 创建MVP流程的端到端测试 [技术栈: pytest, pytest-asyncio, FastAPI TestClient]

**检查点**: MVP 4步流程应该完全功能化，用户可以从第一步走到第四步完成整个文档生成流程，所有素材都有可追溯的链接。流程依赖的RAG数据库和文档清洗能力已经在阶段3和阶段4完成。

---

## 阶段 6: 用户故事 3 - 设置硬性规范条件 (优先级: P1)🎯 MVP

**目标**: 实现硬性规范条件设置功能，设置整份白皮书的硬性规则和约束条件

**独立测试**: 用户可以设置报告类型、语言、风格、知识库范围等硬性条件，验证系统能够保存这些设置并在后续流程中作为约束条件使用。

### 用户故事 3 的实施

- [ ] T145 [P] [US3] 在 src/domain/agent/ 中创建 GlobalConstraints 领域模型 (global_constraints.py) [技术栈: Python标准库, pydantic]
- [ ] T146 [P] [US3] 在 src/domain/agent/ 中创建 ReportType 枚举 (report_type.py) [技术栈: Python标准库, enum]
- [ ] T147 [US3] 在 src/application/services/ 中创建规范条件服务 (constraints_service.py) [技术栈: Python标准库]
- [ ] T148 [US3] 实现报告类型选择功能（市场研究、政策比对、技术评估等） [技术栈: SQLite]
- [ ] T149 [US3] 实现平台内置用户知识库选择功能 [技术栈: SQLite]
- [ ] T150 [US3] 实现生成过程硬性要求设置（报告语言、报告长度目标、是否必须包含图表等） [技术栈: SQLite]
- [ ] T151 [US3] 实现硬性约束条件在后续Agent中的传递和强制执行机制 [技术栈: LangChain 1.0, LangGraph状态管理]
- [ ] T152 [US3] 在 src/interfaces/api/routes/ 中创建规范条件设置API路由 (constraints.py) [技术栈: FastAPI]
- [ ] T153 [US3] 在 src/interfaces/api/schemas/ 中创建规范条件相关Schema (constraints_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T154 [US3] 在 src/interfaces/cli/ 中创建规范条件设置CLI命令 (constraints.py) [技术栈: Typer, Rich]
- [ ] T155 [US3] 添加约束条件验证和错误处理 [技术栈: Python标准库, pydantic验证]
- [ ] T156 [US3] 添加日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 用户故事 1、2 和 3 都应该独立运行

---

## 阶段 7: 用户故事 4 - 优化文档大纲结构 (优先级: P2)

**目标**: 实现结构优化Agent，能够分析大纲结构并提供优化建议

**独立测试**: 可以通过输入一个简单的大纲，验证系统能够识别结构问题并提供增强建议。即使没有知识库和生成功能，用户也能获得有价值的大纲优化服务。

### 用户故事 4 的实施

- [ ] T059 [P] [US4] 在 src/domain/agent/ 中创建 Outline 领域模型 (outline.py) [技术栈: Python标准库, pydantic]
- [ ] T060 [P] [US4] 在 src/domain/agent/ 中创建 OptimizedOutline 领域模型 (optimized_outline.py) [技术栈: Python标准库, pydantic]
- [ ] T061 [US4] 在 src/application/agents/ 中实现结构优化Agent (structure_optimizer.py) [技术栈: LangChain 1.0, LangGraph, LLM]
- [ ] T062 [US4] 实现大纲结构分析逻辑（识别缺失章节、逻辑顺序、层次结构），考虑硬性规范条件中的报告类型要求 [技术栈: LangChain 1.0, LLM, PromptTemplate]
- [ ] T063 [US4] 实现结构优化建议生成（新增章节、调整顺序、完善描述），建议必须符合报告类型的技术模板和写作风格 [技术栈: LangChain 1.0, LLM]
- [ ] T064 [US4] 在 src/interfaces/api/routes/ 中创建结构优化API路由 (agents.py) [技术栈: FastAPI]
- [ ] T065 [US4] 在 src/interfaces/api/schemas/ 中创建大纲相关Schema (outline_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T066 [US4] 在 src/interfaces/cli/ 中创建结构优化CLI命令 (agents.py) [技术栈: Typer, Rich]
- [ ] T067 [US4] 添加大纲验证和错误处理 [技术栈: Python标准库, pydantic验证]
- [ ] T068 [US4] 添加日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 用户故事 1、2、3 和 4 都应该独立运行

---

## 阶段 8: 用户故事 5 - 准确可追溯的信息源排名与匹配 (优先级: P2)🎯 MVP

**目标**: 实现信息源排名Agent，能够从多类信息源中检索、排序和匹配信息源，提供可验证、可追溯、可引用的信息源，并支持用户自定义增加素材。信息源包括：平台内置库、本地知识库（用户上传的文档）、网络检索数据（通过信息源爬取任务获取的网站内容，已建立索引并进入知识库）

**独立测试**: 可以在已有知识库的基础上，针对特定大纲节点进行检索，验证系统能够返回按相关度排序的信息源，并提供可追溯的引用信息。用户可以勾选期望的信息源，系统能够记录反馈。

### 用户故事 5 的实施

- [ ] T157 [P] [US5] 在 src/domain/knowledge_base/ 中创建 SourceMatch 领域模型 (source_match.py) [技术栈: Python标准库, pydantic]
- [ ] T158 [P] [US5] 在 src/domain/knowledge_base/ 中创建 SourceFeedback 领域模型 (source_feedback.py) [技术栈: Python标准库, pydantic]
- [ ] T159 [P] [US5] 在 src/domain/knowledge_base/ 中创建 CustomDataSource 领域模型 (custom_data_source.py) [技术栈: Python标准库, pydantic]
- [ ] T160 [US5] 在 src/application/agents/ 中实现信息源排名Agent (source_matcher.py) [技术栈: LangChain 1.0, LangGraph]
- [ ] T161 [US5] 实现多类信息源检索功能（平台内置库、本地知识库、用户上传文档、网络检索数据）。网络检索数据通过信息源爬取任务获取，已建立索引并进入知识库，与本地知识库统一检索 [技术栈: llamaIndex QueryEngine, Chroma检索, rank-bm25检索, SQLite元数据检索]
- [ ] T162 [US5] 实现信息源相关度排序算法（语义相似度+关键词匹配度+来源可信度） [技术栈: Python标准库, 融合排序算法]
- [ ] T163 [US5] 实现可追溯原文功能（URL和文件路径可点击跳转、可定位关键段落和页码、提供snippet预览和关键词高亮） [技术栈: Python标准库]
- [ ] T164 [US5] 实现用户勾选期望信息源功能，记录勾选与拒绝作为feedback [技术栈: SQLite, LangMem]
- [ ] T165 [US5] 实现手动导入本地知识库功能（PDF/Docs/Markdown等），上传后自动进入私有知识库 [技术栈: llamaIndex文档加载器, 复用阶段4的索引构建流程]
- [ ] T166 [US5] 实现添加自定义网站作为可检索数据源功能（自动爬取、提取正文、去噪、建立索引，索引后的内容进入知识库，与本地知识库统一检索） [技术栈: Scrapy/自定义爬虫, BeautifulSoup4, llamaIndex索引构建]
- [ ] T167 [US5] 实现用户反馈数据收集和排名模型优化机制（trust score提升、反馈数据用于优化） [技术栈: SQLite, LangMem, 机器学习模型(可选)]
- [ ] T168 [US5] 在 src/interfaces/api/routes/ 中创建信息源排名API路由 (source_matching.py) [技术栈: FastAPI]
- [ ] T169 [US5] 在 src/interfaces/api/schemas/ 中创建信息源相关Schema (source_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T170 [US5] 在 src/interfaces/cli/ 中创建信息源排名CLI命令 (source_matching.py) [技术栈: Typer, Rich]
- [ ] T171 [US5] 添加错误处理和日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 用户故事 1、2、3、4 和 5 都应该独立运行

---

## 阶段 9: 用户故事 6 - 生成完整文稿与图表 (优先级: P3)🎯 MVP

**目标**: 实现草稿生成Agent，能够综合大纲和信息源（包括本地知识库和网络检索数据）生成文稿，支持图表自动生成，并提供草稿编辑界面的辅助AI工具。信息源包括：1) 本地知识库（用户上传的文档）；2) 网络检索数据（通过信息源爬取任务获取的网站内容，已建立索引并进入知识库）

**独立测试**: 可以在完成前面所有步骤的基础上，验证系统能够基于大纲和信息源生成一篇完整的文稿，并自动识别和生成图表。这是整个系统的完整流程验证。

### 用户故事 6 的实施

- [ ] T084 [P] [US6] 在 src/domain/agent/ 中创建 Draft 领域模型 (draft.py) [技术栈: Python标准库, pydantic]
- [ ] T172 [P] [US6] 在 src/domain/agent/ 中创建 ChartConfig 领域模型 (chart_config.py) [技术栈: Python标准库, pydantic]
- [ ] T173 [P] [US6] 在 src/domain/agent/ 中创建 DraftEditState 领域模型 (draft_edit_state.py) [技术栈: Python标准库, pydantic]
- [ ] T085 [US6] 在 src/application/agents/ 中实现草稿生成Agent (draft_generator.py) [技术栈: LangChain 1.0, LangGraph]
- [ ] T086 [US6] 实现文稿内容生成逻辑（综合大纲和信息源，整合规范约束→大纲优化→信息源匹配）。信息源包括本地知识库和网络检索数据，系统统一从知识库中检索 [技术栈: LangChain 1.0, LLM, llamaIndex RAG]
- [ ] T087 [US6] 实现引用信息嵌入功能，确保内容专业、可信、可审计 [技术栈: Python标准库]
- [ ] T088 [US6] 实现基础润色功能（语言流畅性、逻辑连贯性、格式规范性） [技术栈: LangChain 1.0, LLM]
- [ ] T174 [US6] 实现图表生成能力（图表理解Chart Reasoning、图表生成Chart Synthesis） [技术栈: LLM(通过LangChain), 图表生成库(如matplotlib/plotly/ECharts), JSON解析]
  - **实现要求**:
    - **图表理解（Chart Reasoning）**: 基于T031B生成的图表JSON数据进行理解，提取关键信息、趋势和模式
      - 优先使用T031B生成的JSON文件（`datajson/`目录）
      - 如果JSON文件不存在，则使用OCR和Layout Parsing作为降级方案
      - 使用LLM分析图表数据，提取关键洞察
    - **图表生成（Chart Synthesis）**: 根据理解结果生成新的图表
      - 支持多种图表类型（柱状图、折线图、饼图、散点图等）
      - 支持多种图表库（matplotlib、plotly、ECharts等）
      - 生成图表DSL（如ECharts JSON）用于前端渲染
    - **输入数据优先级**:
      1. T031B生成的JSON文件（`datajson/`目录）- **优先使用**
      2. OCR和Layout Parsing - **降级方案**
    - **技术栈简化**:
      - ❌ **移除**: 图表识别（Chart OCR）- 已由T031B完成
      - ⚠️ **简化**: Layout Parsing - 仅作为降级方案
      - ✅ **保留**: LLM（用于图表理解和生成）
      - ✅ **保留**: 图表生成库（matplotlib/plotly/ECharts）
  - **注意**: 此任务**优先使用**T031B生成的图表JSON数据作为输入，T031B已经在预处理阶段将文档中的图表转换为结构化JSON格式，存储在`datajson/`目录中。这样可以大幅提高处理效率和准确性，避免重复识别图表。
- [ ] T175 [US6] 实现行业特定图表的专项训练（储能/能源/政策类图表） [技术栈: 机器学习框架(可选), 训练数据]
- [ ] T176 [US6] 实现表格→Markdown/HTML渲染功能 [技术栈: Python标准库, markdown库, html库]
- [ ] T177 [US6] 实现自动识别可结构化内容（数值、趋势、对比数据），生成图表DSL（如ECharts JSON） [技术栈: LLM(通过LangChain), Python标准库, JSON]
- [ ] T178 [US6] 实现草稿编辑界面左侧多源信息源管理区（展示匹配到的所有信息源，高亮显示当前段落使用的来源，支持跳转和段落级定位） [技术栈: FastAPI RESTful API, 前端框架]
- [ ] T179 [US6] 实现草稿编辑界面右侧AI智能检索模块（可将检索结果"一键加入草稿"并自动生成引用链路） [技术栈: LangChain 1.0, llamaIndex QueryEngine, FastAPI]
- [ ] T180 [US6] 实现草稿编辑界面中间AI智能分析工具（段落级修改建议，支持"一键优化"，按照结构完整度、数据引用完整性、逻辑一致性、专业性指标、可读性评估打分） [技术栈: LangChain 1.0, LLM, FastAPI]
- [ ] T089 [US6] 在 src/interfaces/api/routes/ 中创建文稿生成API路由 (drafts.py) [技术栈: FastAPI]
- [ ] T090 [US6] 在 src/interfaces/api/schemas/ 中创建文稿相关Schema (draft_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T091 [US6] 在 src/interfaces/cli/ 中创建文稿生成CLI命令 (drafts.py) [技术栈: Typer, Rich]
- [ ] T092 [US6] 在 src/infrastructure/tasks/ 中创建文稿生成异步任务 (draft_tasks.py) [技术栈: Arq]
- [ ] T093 [US6] 实现文稿编辑和版本管理 [技术栈: SQLite, Git或自定义版本管理]
- [ ] T094 [US6] 添加错误处理和日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 用户故事 1-6 都应该独立运行

---

## 阶段 10: 用户故事 7 - 基于固定模板生成格式文档 (优先级: P3)

**目标**: 实现基于固定模板的格式文档生成功能

**独立测试**: 可以选择一个预定义模板，输入基本内容，验证系统能够生成完全符合模板格式要求的文档。即使没有知识库检索，用户也能获得格式规范的文档生成服务。

### 用户故事 6 的实施

- [ ] T095 [P] [US7] 在 src/domain/agent/ 中创建 DocumentTemplate 领域模型 (document_template.py) [技术栈: Python标准库, pydantic]
- [ ] T096 [US7] 在 src/application/services/ 中创建模板服务 (template_service.py) [技术栈: Python标准库, Jinja2或自定义模板引擎]
- [ ] T097 [US7] 实现模板定义和存储（JSON/YAML格式） [技术栈: Python标准库json/yaml库, SQLite]
- [ ] T098 [US7] 实现模板验证逻辑（检查格式规范） [技术栈: Python标准库, pydantic验证]
- [ ] T099 [US7] 实现基于模板的文稿生成（严格遵循模板格式） [技术栈: Jinja2, LangChain 1.0(可选), LLM(可选)]
- [ ] T100 [US7] 在 src/interfaces/api/routes/ 中创建模板管理API路由 (templates.py) [技术栈: FastAPI]
- [ ] T101 [US7] 在 src/interfaces/api/schemas/ 中创建模板相关Schema (template_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T102 [US7] 在 src/interfaces/cli/ 中创建模板管理CLI命令 (templates.py) [技术栈: Typer, Rich]
- [ ] T103 [US7] 创建预定义模板库（技术报告、学术论文、商业计划书等） [技术栈: JSON/YAML文件存储]
- [ ] T104 [US7] 添加模板匹配度验证 [技术栈: Python标准库, 模板解析器]
- [ ] T105 [US7] 添加错误处理和日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 用户故事 1-7 都应该独立运行

---

## 阶段 11: 用户故事 8 - Homepage与AI智能检索 (优先级: P2)

**目标**: 实现Homepage作为系统入口，提供AI智能检索、知识库管理、白皮书历史记录等功能

**独立测试**: 用户可以通过Homepage访问所有功能模块，使用AI智能检索进行问题查询，验证系统能够返回基于证据的专业分析。用户可以查看历史白皮书记录并继续编辑。

### 用户故事 8 的实施

- [ ] T181 [P] [US8] 在 src/domain/homepage/ 中创建 HomepageState 领域模型 (homepage_state.py) [技术栈: Python标准库, pydantic]
- [ ] T182 [P] [US8] 在 src/domain/homepage/ 中创建 AISearchQuery 领域模型 (ai_search_query.py) [技术栈: Python标准库, pydantic]
- [ ] T183 [US8] 在 src/application/services/ 中创建Homepage服务 (homepage_service.py) [技术栈: Python标准库]
- [ ] T184 [US8] 实现AI智能检索模块（通过对多源数据的统一索引与行业语境特征建模） [技术栈: llamaIndex QueryEngine, LangChain 1.0, LLM, Chroma检索, rank-bm25检索]
- [ ] T185 [US8] 实现检索结果自动过滤噪声内容、抽取关键要点、结构化重排功能 [技术栈: LangChain 1.0, LLM, Python标准库]
- [ ] T186 [US8] 实现用户反馈评价功能，后台保存用户数据作为记忆和学习训练 [技术栈: SQLite, LangMem]
- [ ] T187 [US8] 实现知识库管理与数据抽取能力（专业级垂直领域数据处理Pipeline） [技术栈: llamaIndex, 复用阶段4的数据处理流程]
- [ ] T188 [US8] 实现白皮书历史记录入口，支持一键继续编辑 [技术栈: SQLite, FastAPI]
- [ ] T189 [US8] 在 src/interfaces/api/routes/ 中创建Homepage API路由 (homepage.py) [技术栈: FastAPI]
- [ ] T190 [US8] 在 src/interfaces/api/schemas/ 中创建Homepage相关Schema (homepage_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T191 [US8] 在 src/interfaces/cli/ 中创建Homepage CLI命令 (homepage.py) [技术栈: Typer, Rich]
- [ ] T192 [US8] 添加错误处理和日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 用户故事 1-8 都应该独立运行

---

## 阶段 12: 用户故事 9 - 记忆系统支持人机协作与Agent自我学习 (优先级: P4)

**目标**: 实现记忆系统，记录用户交互历史并支持Agent自我学习

**独立测试**: 可以记录用户与系统的交互历史，验证系统能够从交互记录中提取模式，优化文档识别准确率或调整提示词。即使没有其他功能，用户也能看到系统基于交互历史的持续改进。

### 用户故事 7 的实施

- [ ] T106 [P] [US9] 在 src/domain/memory/ 中创建 MemoryEntry 领域模型 (memory_entry.py) [技术栈: Python标准库, pydantic]
- [ ] T107 [P] [US9] 在 src/domain/memory/ 中创建 InteractionHistory 领域模型 (interaction_history.py) [技术栈: Python标准库, pydantic]
- [ ] T108 [US9] 在 src/application/services/ 中创建记忆服务 (memory_service.py) [技术栈: LangMem, LangGraph Checkpointer]
- [ ] T109 [US9] 实现交互历史记录功能（用户查询、系统响应、用户反馈、操作习惯） [技术栈: LangMem, SQLite]
- [ ] T110 [US9] 实现交互模式提取和分析 [技术栈: Python标准库, 数据分析库(如pandas), 机器学习(可选)]
- [ ] T111 [US9] 实现基于交互记忆的优化建议生成（文档识别、提示词、意图识别） [技术栈: LangChain 1.0, LLM, LangMem]
- [ ] T112 [US9] 实现Agent自我学习机制（从交互记忆中学习执行策略） [技术栈: LangChain 1.0, LangMem, LangGraph Checkpointer]
- [ ] T113 [US9] 实现记忆版本管理 [技术栈: LangMem, SQLite, 版本控制逻辑]
- [ ] T114 [US9] 在 src/interfaces/api/routes/ 中创建记忆系统API路由 (memory.py) [技术栈: FastAPI]
- [ ] T115 [US9] 在 src/interfaces/api/schemas/ 中创建记忆相关Schema (memory_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T116 [US9] 在 src/interfaces/cli/ 中创建记忆系统CLI命令 (memory.py) [技术栈: Typer, Rich]
- [ ] T117 [US9] 添加错误处理和日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 用户故事 1-9 都应该独立运行

---

## 阶段 13: 用户故事 10 - 提示词工程能力 (优先级: P4)

**目标**: 实现提示词工程服务，支持提示词模板的创建、编辑、测试和优化

**独立测试**: 可以创建和编辑提示词模板，验证系统能够正确应用提示词、支持变量替换和条件逻辑，并能够测试提示词效果。即使没有其他功能，用户也能获得提示词管理服务。

### 用户故事 8 的实施

- [ ] T118 [P] [US10] 在 src/domain/agent/ 中创建 PromptTemplate 领域模型 (prompt_template.py) [技术栈: Python标准库, pydantic]
- [ ] T119 [P] [US10] 在 src/domain/agent/ 中创建 PromptStrategy 领域模型 (prompt_strategy.py) [技术栈: Python标准库, pydantic]
- [ ] T120 [US10] 在 src/application/services/ 中创建提示词工程服务 (prompt_engineering_service.py) [技术栈: Python标准库]
- [ ] T121 [US10] 在 src/shared/prompts/ 中创建提示词管理器 (prompt_manager.py) [技术栈: LangChain PromptTemplate, Jinja2]
- [ ] T122 [US10] 实现提示词模板解析器（支持变量、条件逻辑、多轮对话） [技术栈: Jinja2, Python标准库]
- [ ] T123 [US10] 实现提示词模板渲染功能 [技术栈: Jinja2, LangChain PromptTemplate]
- [ ] T124 [US10] 实现提示词测试功能（使用测试数据执行提示词） [技术栈: LangChain 1.0, LLM, pytest]
- [ ] T125 [US10] 实现提示词版本管理 [技术栈: SQLite, Git或自定义版本管理]
- [ ] T126 [US10] 实现提示词效果分析（基于Agent响应质量、用户满意度） [技术栈: Python标准库, 数据分析库(如pandas)]
- [ ] T127 [US10] 实现提示词优化建议生成 [技术栈: LangChain 1.0, LLM]
- [ ] T128 [US10] 实现提示词策略配置（根据场景条件自动选择模板） [技术栈: SQLite, Python标准库, 规则引擎(可选)]
- [ ] T129 [US10] 在 src/interfaces/api/routes/ 中创建提示词工程API路由 (prompts.py) [技术栈: FastAPI]
- [ ] T130 [US10] 在 src/interfaces/api/schemas/ 中创建提示词相关Schema (prompt_schemas.py) [技术栈: FastAPI, pydantic]
- [ ] T131 [US10] 在 src/interfaces/cli/ 中创建提示词工程CLI命令 (prompts.py) [技术栈: Typer, Rich]
- [ ] T132 [US10] 创建提示词模板编辑器（Web界面或CLI） [技术栈: 前端框架(Web界面), Typer/Rich(CLI)]
- [ ] T133 [US10] 添加错误处理和日志记录 [技术栈: Python标准库logging]

**检查点**: 此时, 所有用户故事都应该独立运行

---

## 阶段 14: 完善与横切关注点

**目的**: 影响多个用户故事的改进

- [ ] T134 [P] 在 docs/ 中更新项目文档（API文档、架构图、用户指南） [技术栈: Markdown, Sphinx或MkDocs, OpenAPI/Swagger]
- [ ] T135 代码清理和重构（遵循DRY、SOLID原则） [技术栈: Python标准库, 代码质量工具]
- [ ] T136 跨所有Agent的性能优化 [技术栈: Python标准库, 性能分析工具(如cProfile), asyncio优化]
- [ ] T137 实现统一的错误处理和重试机制 [技术栈: Python标准库, tenacity(retry库), 自定义异常处理]
- [ ] T138 实现统一的日志记录和可观测性 [技术栈: Python标准库logging, structlog, 或opentelemetry]
- [ ] T139 实现API限流和并发控制 [技术栈: slowapi(限流), FastAPI中间件, Redis(可选)]
- [ ] T140 实现数据备份和恢复机制 [技术栈: SQLite备份工具, 文件系统备份, 自定义备份脚本]
- [ ] T141 安全加固（输入验证、SQL注入防护、XSS防护） [技术栈: pydantic验证, SQLite参数化查询, FastAPI安全中间件]
- [ ] T142 运行 quickstart.md 验证完整流程 [技术栈: pytest, pytest-asyncio, 集成测试]
- [ ] T143 实现CI/CD流水线（代码检查、测试、部署） [技术栈: GitHub Actions/GitLab CI, Ruff, Mypy, pytest, Docker]
- [ ] T144 添加监控和告警机制 [技术栈: Prometheus/Grafana, 或Sentry, 日志聚合系统]

---

## 依赖关系与执行顺序

### 阶段依赖关系

- **设置(阶段 1)**: 无依赖关系 - 可立即开始
- **基础(阶段 2)**: 依赖于设置完成 - 阻塞所有用户故事
- **用户故事 1(阶段 3)**: 依赖于基础阶段完成 - 文档预处理与清洗
- **用户故事 2(阶段 4)**: 依赖于阶段3完成 - 建立本地知识库（RAG数据库）
- **MVP 4步流程(阶段 5)**: 依赖于阶段1、2、3、4完成 - 优先级P0，应在其他用户故事之前完成
  - 这是核心MVP流程，专注于储能行业用例
  - RAG数据库和文档清洗是基础，必须在阶段5之前完成
  - 包含4个步骤：行业选择、大纲优化、信息源爬取、草稿生成
  - 需要前端集成支持
- **用户故事(阶段 6-13)**: 都依赖于基础阶段完成
  - US3 (P1): 可在基础完成后开始，独立于US1/US2
  - US4 (P2): 依赖于US2完成（需要知识库）
  - US5 (P2): 依赖于US3和US4完成（需要大纲和检索结果）
  - US6 (P3): 可在基础完成后开始，独立于其他故事
  - US7 (P3): 可在基础完成后开始，独立可测试
  - US8 (P2): 可在基础完成后开始，独立可测试，但最好在US1-US2完成后
  - US9 (P4): 依赖于US1-US8完成（需要完整的交互历史）
  - US10 (P4): 可在基础完成后开始，但最好在US1-US4完成后
  - 然后用户故事可以并行进行(如果有人员)
  - 或按优先级顺序进行(P1 → P2 → P3 → P4)
- **完善(阶段 14)**: 依赖于所有期望的用户故事完成

### 用户故事依赖关系

- **用户故事 1 (P1)**: 可在基础(阶段 2)后开始 - 无其他故事依赖
- **用户故事 2 (P1)**: 依赖于US1完成 - 需要预处理后的文档
- **用户故事 3 (P1)**: 可在基础(阶段 2)后开始 - 独立可测试，但应在US4之前完成（US4需要硬性规范条件）
- **用户故事 4 (P2)**: 依赖于US3完成 - 需要硬性规范条件作为约束
- **用户故事 5 (P2)**: 依赖于US2和US4完成 - 需要知识库和优化后的大纲
- **用户故事 6 (P3)**: 依赖于US4和US5完成 - 需要大纲和信息源匹配结果
- **用户故事 7 (P3)**: 可在基础(阶段 2)后开始 - 独立可测试
- **用户故事 8 (P2)**: 可在基础(阶段 2)后开始 - 独立可测试，但最好在US1-US2完成后
- **用户故事 9 (P4)**: 依赖于US1-US8完成 - 需要完整的交互历史
- **用户故事 10 (P4)**: 可在基础(阶段 2)后开始，但最好在US1-US4完成后

### 每个用户故事内部

- 领域模型在服务之前
- 基础设施组件在Agent之前
- Agent在API/CLI之前
- 核心实施在集成之前
- 故事完成后才移至下一个优先级

### 并行机会

- 所有标记为 [P] 的设置任务可以并行运行
- 所有标记为 [P] 的基础任务可以并行运行(在阶段 2 内)
- 基础阶段完成后, US3和US6可以并行开始（独立故事）
- 用户故事中所有标记为 [P] 的领域模型可以并行运行
- 用户故事中所有标记为 [P] 的基础设施组件可以并行运行
- 不同用户故事可以由不同团队成员并行处理（在满足依赖关系的前提下）

---

## 并行示例: 用户故事 1

```bash
# 一起启动用户故事 1 的所有领域模型: 
任务: "在 src/domain/document/ 中创建 Document 领域模型"
任务: "在 src/domain/document/ 中创建 PreprocessedDocument 领域模型"

# 一起启动用户故事 1 的所有加载器: 
任务: "实现 PDF 文档加载器"
任务: "实现 HTML 文档加载器"

# 一起启动用户故事 1 的所有清洗器: 
任务: "创建文本清洗器"
任务: "创建格式标准化器"
任务: "创建噪声去除器"
```

---

## 实施策略

### 核心 MVP(阶段 5 - 4步流程)

1. 完成阶段 1: 设置
2. 完成阶段 2: 基础(关键 - 阻塞所有故事)
3. 完成阶段 3: 用户故事 1 (文档预处理与清洗)
4. 完成阶段 4: 用户故事 2 (建立本地知识库 - RAG数据库)
5. 完成阶段 5: MVP 4步流程 (储能行业文档生成)
   - 第一步：行业和数据库选择
   - 第二步：大纲手写和AI优化
   - 第三步：信息源爬取（储能行业网站）
   - 第四步：草稿生成（带素材追溯链接）
   - 前端集成和完整流程
6. **停止并验证**: 端到端测试完整的4步流程
7. 如准备好则部署/演示

### 扩展 MVP(用户故事 1 和 2)

1. 完成阶段 1: 设置
2. 完成阶段 2: 基础(关键 - 阻塞所有故事)
3. 完成阶段 3: 用户故事 1 (文档预处理)
4. 完成阶段 4: 用户故事 2 (知识库建立)
5. **停止并验证**: 独立测试用户故事 1 和 2
6. 如准备好则部署/演示

### 增量交付

1. 完成设置 + 基础 → 基础就绪
2. 添加用户故事 1 → 独立测试 → 部署/演示
3. 添加用户故事 2 → 独立测试 → 部署/演示 (MVP!)
4. 添加用户故事 3 → 独立测试 → 部署/演示
5. 添加用户故事 4 → 独立测试 → 部署/演示
6. 添加用户故事 5 → 独立测试 → 部署/演示
7. 添加用户故事 6 → 独立测试 → 部署/演示
8. 添加用户故事 7 → 独立测试 → 部署/演示
9. 添加用户故事 8 → 独立测试 → 部署/演示
10. 每个故事在不破坏先前故事的情况下增加价值

### 并行团队策略

有多个开发人员时: 

1. 团队一起完成设置 + 基础
2. 基础完成后: 
   - 开发人员 A: 用户故事 1 (文档预处理)
   - 开发人员 B: 用户故事 3 (结构优化) - 独立故事
3. 用户故事 1 完成后:
   - 开发人员 A: 用户故事 2 (知识库建立)
   - 开发人员 B: 继续用户故事 3
   - 开发人员 C: 用户故事 6 (模板生成) - 独立故事
4. 用户故事 2 完成后:
   - 开发人员 A: 用户故事 4 (信息检索)
   - 开发人员 B: 继续用户故事 3
   - 开发人员 C: 继续用户故事 6
5. 用户故事 3 和 4 完成后:
   - 开发人员 A: 用户故事 5 (文稿生成)
   - 开发人员 B: 用户故事 7 (记忆系统)
   - 开发人员 C: 用户故事 8 (提示词工程)
6. 故事独立完成和集成

---

## 注意事项

- [P] 任务 = 不同文件, 无依赖关系
- [Story] 标签将任务映射到特定用户故事以实现可追溯性
- 每个用户故事应该独立可完成和可测试
- 在每个任务或逻辑组后提交
- 在任何检查点停止以独立验证故事
- 避免: 模糊任务、相同文件冲突、破坏独立性的跨故事依赖
- 遵循章程要求: 文件长度<4000行, 模块化边界, DRY/SOLID原则

---

## 任务统计

- **总任务数**: 243
- **阶段 1 (设置)**: 8 个任务
- **阶段 2 (基础)**: 14 个任务
- **阶段 3 (US1 - 文档预处理与清洗)**: 20 个任务（新增DOCX加载器、图表转JSON转换器T031B）
- **阶段 4 (US2 - 建立本地知识库)**: 19 个任务（新增DOCX解析器，RAG数据库）
- **阶段 5 (MVP 4步流程)**: 49 个任务（优先级P0，在阶段3和4完成后优先完成）
  - 第一步（行业和数据库选择）: 9 个任务
  - 第二步（大纲手写和AI优化）: 10 个任务
  - 第三步（信息源爬取）: 11 个任务
  - 第四步（草稿生成）: 13 个任务
  - 前端集成和完整流程: 6 个任务
- **阶段 6 (US3)**: 12 个任务
- **阶段 7 (US4)**: 10 个任务
- **阶段 8 (US5)**: 15 个任务
- **阶段 9 (US6)**: 24 个任务
- **阶段 10 (US7)**: 11 个任务
- **阶段 11 (US8)**: 12 个任务
- **阶段 12 (US9)**: 12 个任务
- **阶段 13 (US10)**: 16 个任务
- **阶段 14 (完善)**: 11 个任务

**并行任务数**: 约 80+ 个任务可以并行执行

**建议的核心MVP范围**: 阶段 1 + 阶段 2 + 阶段 3 + 阶段 4 + 阶段 5 (MVP 4步流程 - 储能行业文档生成)
  - 阶段3和4提供RAG数据库和文档清洗基础能力
  - 阶段5实现完整的4步流程

**建议的完整MVP范围**: 阶段 1 + 阶段 2 + 阶段 3 + 阶段 4 + 阶段 5 + 阶段 6 + 阶段 8 + 阶段 9 (用户故事 1、2、3、5、6)

