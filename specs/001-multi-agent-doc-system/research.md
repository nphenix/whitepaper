# 技术研究: 多 Agent 协作的文档处理与生成系统

**创建时间**: 2025-12-05
**状态**: 完成

## 研究目标

基于功能规范和技术栈要求，研究关键技术选型的实现方案、最佳实践和集成模式。

## 技术决策与研究结果

### 1. LangChain 1.0 Agent编排架构

**Decision**: 使用LangChain 1.0作为统一的Agent编排框架，通过LangGraph实现多Agent协作流程。

**Rationale**: 
- LangChain 1.0提供了成熟的Agent框架，支持工具调用、记忆管理和状态流转
- LangGraph提供了有向图结构，适合实现多Agent协作的复杂工作流
- 统一的接口设计符合章程P5的Agent可组合性原则
- 生态成熟，文档完善，社区支持良好

**Alternatives considered**:
- 自研Agent框架：开发成本高，不符合YAGNI原则
- 其他Agent框架（如AutoGPT）：生态不成熟，集成复杂度高

**Implementation Notes**:
- 使用`langchain.agents`模块创建Agent实例
- 使用`langgraph.graph`构建Agent协作图
- 每个Agent实现单一职责（结构优化、信息检索、草稿生成）
- Agent之间通过明确的输入/输出契约协作

**References**:
- LangChain 1.0 Documentation: https://python.langchain.com/
- LangGraph Documentation: https://langchain-ai.github.io/langgraph/

---

### 2. LangMem + LangGraph Checkpointer 记忆层

**Decision**: 使用LangMem作为长期记忆存储，LangGraph Checkpointer作为工作记忆（Submission记忆层），实现持久化工作/长期记忆。

**Rationale**:
- LangMem提供结构化的长期记忆管理，适合存储用户交互历史
- LangGraph Checkpointer提供Agent执行状态持久化，支持工作流恢复
- 两者结合可以满足记忆系统的完整需求（FR-024到FR-027）
- 与LangChain 1.0无缝集成，生态成熟

**Alternatives considered**:
- 仅使用LangGraph Checkpointer：缺少长期记忆管理能力
- 仅使用LangMem：缺少工作流状态管理能力
- 自研记忆系统：开发成本高，重复造轮子

**Implementation Notes**:
- LangMem用于存储用户交互历史、操作习惯、优化策略等长期记忆
- LangGraph Checkpointer用于持久化Agent执行状态，支持工作流中断恢复
- 记忆条目支持版本管理，记录知识的演进历史
- 从交互记忆中提取模式，用于优化文档识别、提示词、意图识别

**References**:
- LangMem: https://github.com/langchain-ai/langmem
- LangGraph Checkpointer: https://langchain-ai.github.io/langgraph/how-tos/persistence/

---

### 3. llamaIndex RAG管线构建

**Decision**: 使用llamaIndex构建RAG（检索增强生成）管线，支持文档加载、分块、向量化和检索。

**Rationale**:
- llamaIndex提供了完整的RAG工具链，从文档加载到检索生成
- 支持多种文档格式和向量存储后端
- 可以与LangChain集成，作为Agent的工具使用

**Alternatives considered**:
- 自研RAG管线：开发成本高，需要处理大量细节
- 仅使用LangChain的RAG功能：功能相对简单，不如llamaIndex完整

**Implementation Notes**:
- 使用`llama_index.core`作为RAG管线基础
- 文档加载器支持PDF、HTML和DOCX格式（MVP要求）
- 文档分块策略：按章节和段落分块，保留结构信息
- 向量化使用与Chroma兼容的嵌入模型
- RAG检索结果作为信息检索Agent的输入

**References**:
- llamaIndex Documentation: https://docs.llamaindex.ai/

---

### 4. FastAPI + Arq 异步服务架构

**Decision**: 使用FastAPI提供同步API服务，Arq提供异步任务队列，处理文档解析、索引构建等耗时操作。

**Rationale**:
- FastAPI提供高性能的Web框架，支持异步请求处理
- Arq基于asyncio和Redis，适合处理后台任务
- 两者结合可以满足同步API和异步任务的需求

**Alternatives considered**:
- 仅使用FastAPI：无法处理长时间运行的后台任务
- Celery：配置复杂，对Redis依赖重
- 自研任务队列：开发成本高

**Implementation Notes**:
- FastAPI路由处理用户请求（文档上传、检索、生成等）
- Arq任务处理文档解析、索引构建、文稿生成等耗时操作
- 使用WebSocket或轮询提供任务进度反馈
- 错误处理和重试机制确保任务可靠性

**References**:
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Arq Documentation: https://arq-docs.helpmanual.io/

---

### 5. FastMCP MCP服务能力

**Decision**: 使用FastMCP提供MCP（Model Context Protocol）服务能力，支持与外部AI模型的集成。

**Rationale**:
- MCP是标准化的模型上下文协议，支持与多种AI模型集成
- FastMCP提供了Python实现，易于集成到现有系统
- 支持Agent调用外部AI模型进行内容生成

**Alternatives considered**:
- 直接调用AI模型API：缺少标准化接口
- 自研MCP实现：开发成本高

**Implementation Notes**:
- FastMCP作为MCP服务器，提供文档处理、内容生成等服务
- Agent通过MCP协议调用外部AI模型
- 支持多种AI模型后端（OpenAI、Anthropic等）

**References**:
- FastMCP: https://github.com/jlowin/fastmcp
- MCP Specification: https://modelcontextprotocol.io/

---

### 6. SQLite + Chroma + NetworkX 多模式数据存储

**Decision**: 使用SQLite存储结构化数据，Chroma存储向量数据，NetworkX存储图数据，实现多模式数据管理。

**Rationale**:
- SQLite适合存储文档元数据、用户数据、记忆条目等结构化数据
- Chroma是专门的向量数据库，适合存储文档向量索引
- NetworkX是成熟的图计算库，适合构建和查询知识图谱
- 三者结合可以满足多模式索引的需求（FR-003）

**Alternatives considered**:
- 单一数据库方案（如PostgreSQL + pgvector）：功能完整但配置复杂
- 仅使用向量数据库：缺少结构化数据和图数据支持
- 自研存储方案：开发成本高

**Implementation Notes**:
- SQLite存储：文档表、用户表、记忆条目表、大纲表、文稿表等
- Chroma存储：文档向量索引，支持语义检索
- NetworkX存储：知识图谱（实体节点、关系边），支持关系查询
- 数据一致性：通过事务和同步机制确保多存储的一致性
- 数据迁移：提供脚本支持数据迁移和备份

**References**:
- SQLite: https://www.sqlite.org/
- Chroma: https://www.trychroma.com/
- NetworkX: https://networkx.org/

---

### 7. PaddleOCR 文档识别

**Decision**: 使用PaddleOCR实现文档识别，支持PDF和HTML中的图像文字识别。DOCX格式使用python-docx库直接解析，无需OCR。

**Rationale**:
- PaddleOCR是开源的OCR工具，支持中英文识别
- 可以处理PDF中的扫描图像和HTML中的图片
- 识别准确率高，适合文档处理场景

**Alternatives considered**:
- Tesseract OCR：识别准确率相对较低
- 商业OCR服务（如百度OCR）：成本高，依赖外部服务
- 自研OCR：开发成本极高

**Implementation Notes**:
- PaddleOCR用于识别PDF中的扫描页面和HTML中的图片
- DOCX格式使用python-docx库解析，支持提取文本、表格、图片等结构化内容
- 识别结果与文本提取结果合并，形成完整的文档内容
- 支持批量识别和异步处理
- 识别结果存储到知识库，支持后续检索

**References**:
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR

---

### 8. 多模式检索实现策略

**Decision**: 实现向量语义检索、BM25关键词检索、元数据检索和知识图谱检索的混合检索策略。

**Rationale**:
- 不同检索模式适用于不同场景：向量检索适合语义匹配，BM25适合精确匹配，元数据检索适合筛选，知识图谱检索适合关系查询
- 混合检索可以综合各模式优势，提高检索准确率（SC-005要求70%以上）

**Alternatives considered**:
- 仅使用向量检索：无法处理精确匹配和章节定位需求
- 仅使用BM25检索：无法处理语义相似度匹配
- 自研检索算法：开发成本高，不如成熟方案可靠

**Implementation Notes**:
- 向量检索：使用Chroma进行语义相似度检索
- BM25检索：使用rank-bm25库实现关键词检索，支持章节定位
- 元数据检索：使用SQLite查询文档属性、章节标签等
- 知识图谱检索：使用NetworkX查询实体关系
- 混合检索：根据查询类型自动选择检索模式，或融合多个模式的结果
- 结果排序：使用相关性评分、时间、来源等维度进行融合排序

**References**:
- rank-bm25: https://github.com/dorianbrown/rank_bm25
- Chroma Retrieval: https://docs.trychroma.com/guides/querying

---

### 9. 静态检查工具配置

**Decision**: 使用Ruff进行Python代码格式化和linting，Mypy进行类型检查，ESLint进行前端代码检查（如需要）。

**Rationale**:
- Ruff是快速的Python linter和formatter，替代flake8、black等工具
- Mypy提供静态类型检查，提高代码质量
- ESLint是前端代码检查的标准工具

**Alternatives considered**:
- 使用flake8 + black + isort：工具链复杂，速度慢
- 不使用类型检查：代码质量难以保证

**Implementation Notes**:
- Ruff配置：启用所有推荐的规则，集成到CI/CD流程
- Mypy配置：严格模式，检查所有类型注解
- ESLint配置：如需要前端代码，配置标准规则集
- 预提交钩子：在提交前自动运行静态检查

**References**:
- Ruff: https://docs.astral.sh/ruff/
- Mypy: https://mypy.readthedocs.io/
- ESLint: https://eslint.org/

---

### 10. Typer + Rich CLI工具

**Decision**: 使用Typer构建CLI命令，Rich提供美观的输出格式。

**Rationale**:
- Typer基于Python类型提示，API简洁易用
- Rich提供丰富的终端输出格式（表格、进度条、语法高亮等）
- 两者结合可以构建用户友好的CLI工具

**Alternatives considered**:
- argparse：API复杂，输出格式单一
- click：功能完整但配置复杂

**Implementation Notes**:
- Typer命令：文档上传、知识库管理、Agent执行、系统配置等
- Rich输出：表格展示检索结果、进度条显示处理进度、语法高亮显示文稿内容
- 错误处理：友好的错误消息和帮助信息

**References**:
- Typer: https://typer.tiangolo.com/
- Rich: https://rich.readthedocs.io/

---

## 技术风险与缓解措施

### 风险1: 多存储后端的数据一致性
**风险**: SQLite、Chroma、NetworkX三个存储后端，数据同步可能不一致
**缓解**: 
- 实现统一的数据访问层，封装多存储操作
- 使用事务机制确保关键操作的一致性
- 定期数据一致性检查

### 风险2: LangChain 1.0 API变更
**风险**: LangChain版本更新可能导致API变更
**缓解**:
- 锁定LangChain版本到1.0.x
- 使用依赖注入，隔离LangChain依赖
- 编写适配器层，降低API变更影响

### 风险3: 大文件处理性能
**风险**: 10MB以上的文档处理可能影响系统性能
**缓解**:
- 使用异步任务队列处理大文件
- 实现文档分块处理，避免内存溢出
- 提供进度反馈，改善用户体验

### 风险4: 多模式检索的性能
**风险**: 混合检索可能影响响应时间
**缓解**:
- 实现检索结果缓存
- 并行执行多个检索模式
- 优化索引结构，提高检索速度

---

## 待解决的技术问题

所有技术选型已确定，无待解决的NEEDS CLARIFICATION项。

---

---

### 11. 文档预处理Agent实现策略

**Decision**: 实现独立的文档预处理Agent，负责文档格式识别、内容加载和清洗处理。

**Rationale**:
- 文档预处理是文档处理流程的第一步，需要处理不同格式的文档
- 清洗处理能够提高文档质量，确保后续解析和索引的准确性
- 独立的Agent设计符合单一职责原则（章程P5）

**Alternatives considered**:
- 在解析阶段处理清洗：职责不清，违反单一职责原则
- 使用外部工具：缺少灵活性，难以定制清洗规则

**Implementation Notes**:
- 使用策略模式实现不同格式的文档加载器（PDF、HTML、DOCX等）
- 实现文档清洗器：去除页眉页脚、水印、广告等无关内容
- 文本格式化：统一编码、标准化换行、去除多余空白
- 质量报告：记录清洗前后的对比、处理统计信息
- 与llamaIndex文档加载器集成，支持扩展

**References**:
- llamaIndex Document Loaders: https://docs.llamaindex.ai/en/stable/module_guides/loading/

---

### 12. 提示词工程能力实现

**Decision**: 实现提示词工程服务，支持提示词模板的创建、编辑、测试、版本管理和策略配置。

**Rationale**:
- 提示词质量直接影响Agent执行效果
- 需要支持变量替换、条件逻辑等高级功能
- 版本管理和效果分析能够持续优化提示词

**Alternatives considered**:
- 硬编码提示词：缺少灵活性，难以优化
- 简单文本模板：功能有限，无法支持复杂场景

**Implementation Notes**:
- 提示词模板格式：支持变量（{{variable}}）、条件逻辑（{% if condition %}）、循环等
- 模板编辑器：提供Web界面和CLI工具
- 测试功能：使用测试数据执行提示词，展示Agent响应
- 版本管理：记录提示词演进历史，支持回退和对比
- 效果分析：基于Agent响应质量、用户满意度等指标推荐优化建议
- 策略配置：根据文档类型、用户偏好等条件自动选择提示词模板
- 与LangChain PromptTemplate集成

**References**:
- LangChain Prompt Templates: https://python.langchain.com/docs/modules/model_io/prompts/prompt_templates/

---

## 总结

技术栈选型已完成，所有关键技术都有明确的实现方案和最佳实践。系统架构采用分层设计，符合章程要求。多Agent协作通过LangChain统一编排，多模式数据存储通过适配器层统一管理，确保系统的可维护性和可扩展性。新增的文档预处理Agent和提示词工程能力进一步增强了系统的灵活性和适应性。
