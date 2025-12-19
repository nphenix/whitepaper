# whitepaper 项目 speckit 规则

**版本**: 1.2.0 | **最后更新**: 2025-12-05 | **来源**: `.specify/memory/constitution.md`

本文档定义了在使用 CodeFlicker AI 进行 whitepaper 项目开发时，speckit 工具必须遵循的核心规则和约束。这些规则基于项目章程，确保 speckit 生成的规范、计划、任务等制品的质量和一致性。

## P1 代码质量守则

**模块化边界**
- speckit 生成的所有功能必须保持清晰的模块化边界，避免巨石式文件或隐式耦合
- 遵循分层架构：`src/domain/`（领域模型）、`src/application/`（应用服务）、`src/interfaces/`（接口层）、`src/infrastructure/`（基础设施）
- 模块之间通过明确的接口（Protocol/ABC）通信
- speckit 生成的架构设计必须体现模块化思想

**文件长度限制**
- ⚠️ **硬性限制**：speckit 生成的单个源文件不得超过 4000 行
- speckit 在生成代码时，如果预测文件超过限制，必须自动拆分为职责清晰的子模块
- speckit 生成的计划中必须包含文件长度守卫策略
- speckit 生成的 PR 检查清单必须包含文件长度验证

**测试要求**
- speckit 生成的所有新增功能必须同步交付自动化单元测试
- speckit 必须在任务清单中明确测试任务和验收标准
- speckit 生成的 PR 检查清单必须包含"单元测试已更新"检查项
- speckit 必须在计划中定义测试覆盖率目标和测试策略

**架构质量原则**
- **DRY 原则**：speckit 生成的代码禁止重复。发现重复代码模式时，必须提取为可复用的组件、基类或工具函数
- **SOLID 原则**：speckit 生成的设计必须遵循：
  - **单一职责**：每个类/模块只负责一个明确的功能领域
  - **开闭原则**：通过策略模式、适配器模式、工厂模式等实现扩展，而非修改现有代码
  - **依赖倒置**：客户端代码依赖抽象接口（ABC、Protocol），而非具体实现
- **设计模式优先**：speckit 在需要扩展性时，优先使用设计模式而非硬编码的条件分支
- **接口统一**：speckit 生成的同一功能的不同实现必须通过统一接口暴露，使用适配器模式整合

## P2 目录结构与工件定位

**目录规范**
- speckit 必须遵循 `specs/001-multi-agent-doc-system/plan.md` 中定义的项目结构
- speckit 不允许随意新增顶层目录或模糊命名
- speckit 生成的代码/文档必须写入预期路径（`specs/`、`docs/`、`src/` 下的既定子目录）
- speckit 生成的计划必须包含详细的目录结构定义

**文件定位规则**
- speckit 生成的领域模型必须放入 `src/domain/`
- speckit 生成的应用服务必须放入 `src/application/services/`
- speckit 生成的 Agent 实现必须放入 `src/application/agents/`
- speckit 生成的 API 路由必须放入 `src/interfaces/api/routes/`
- speckit 生成的 API Schema 必须放入 `src/interfaces/api/schemas/`
- speckit 生成的 CLI 命令必须放入 `src/interfaces/cli/`
- speckit 生成的基础设施适配器必须放入 `src/infrastructure/`
- speckit 生成的共享组件必须放入 `src/shared/`
- speckit 生成的测试文件必须放入 `tests/unit/`、`tests/integration/`、`tests/contract/`

**脚本验证**
- speckit 生成的脚本需在输出完成后验证文件是否落在正确位置
- speckit 生成的构建脚本必须包含文件位置验证逻辑
- 文件位置错误视为 speckit 生成失败

## P3 临时文件纪律

**临时文件管理**
- speckit 运行时生成的临时脚本、草稿或调试工件只能存在于隔离的工作区
- speckit 必须在使用完毕后立即删除临时文件，不得提交到仓库
- speckit 生成的处理流程必须包含临时文件自动清理机制
- speckit 生成的目录结构必须包含 `data/temp/` 临时文件目录

**缓存管理**
- speckit 在运行时若必须生成缓存，需在命令流程中显式清理
- speckit 生成的系统设计必须包含 LangGraph Checkpointer 缓存的可清理模式配置
- speckit 生成的构建流程必须保证仓库保持干净状态
- speckit 生成的 CI/CD 流程必须包含缓存管理策略

**CI/CD 检查**
- speckit 生成的 CI/CD 管道必须检查并阻止包含临时文件的提交
- speckit 必须在计划中定义禁止的文件模式：`.tmp`、`debug.log`、未命名文档等
- speckit 生成的 CI 流水线必须包含临时文件扫描步骤

## P4 文档与可维护性

**文档标注要求**
- speckit 生成的所有自动生成的代码/文档必须在文件头部标注生成命令与时间戳
- speckit 必须在生成的文件中包含以下格式的标注：
  ```python
  # 生成命令: /speckit.implement T023
  # 生成时间: 2025-12-05
  # 来源: specs/001-multi-agent-doc-system/tasks.md
  ```

**代码注释要求**
- speckit 生成的函数、组件、脚本若包含非显而易见的约束或副作用，必须通过行内注释或同目录 README 进行说明
- speckit 生成的复杂业务逻辑必须添加注释说明设计理由
- speckit 生成的文档必须包含使用说明和示例

**设计决策记录**
- speckit 生成的重大设计决策需在 `docs/` 或对应 `specs/` 下记录理由
- speckit 必须在计划中明确：
  - 架构变更 → `docs/architecture/`
  - API 变更 → `docs/api/`
  - 编码规范变更 → `docs/development/`
- speckit 生成的文档必须包含决策的背景、选项和最终选择的原因

**docs 目录文档管理规则**
- **文档更新时机**：
  - speckit 生成的架构变更必须在 PR 合并前更新 `docs/architecture/`
  - speckit 生成的 API 变更必须在 PR 合并前更新 `docs/api/`
  - speckit 生成的编码规范、开发流程变更必须同步更新 `docs/development/`
  - speckit 生成的部署配置、环境变更必须同步更新 `docs/deployment/`
- **文档更新责任**：
  - speckit 必须在任务清单中明确代码变更的发起者负责更新相关 `docs/` 文档
  - speckit 生成的 PR 描述模板必须明确列出受影响的文档并完成更新
  - speckit 生成的 Code Review 流程必须验证文档是否已同步更新
- **文档质量要求**：
  - speckit 生成的文档必须使用中文编写
  - speckit 生成的术语必须与代码保持一致
  - speckit 生成的架构文档必须包含组件图、数据流图
  - speckit 生成的 API 文档必须包含请求/响应示例、错误码说明
  - speckit 生成的文档中引用的代码路径、文件名必须与实际代码保持一致
  - speckit 生成的文档必须有明确的最后更新时间戳

## P5 Agent 设计原则

**单一职责**
- speckit 生成的每个 Agent 必须专注于单一功能领域（如文档预处理、信息检索、草稿生成）
- speckit 禁止生成混合多个不相关职责的 Agent
- speckit 生成的 Agent 必须有明确的功能边界定义

**可组合性**
- speckit 生成的 Agent 之间必须通过明确的接口（输入/输出契约）协作
- speckit 生成的系统必须支持 Agent 的独立开发、测试与替换
- speckit 必须使用 LangChain 统一编排接口设计 Agent

**可观测性**
- speckit 生成的所有 Agent 执行过程必须记录结构化日志
- speckit 生成的日志必须包含：输入参数、中间状态、输出结果、执行时间
- speckit 生成的系统必须使用 LangGraph Checkpointer 记录状态，便于调试与性能分析

**错误隔离**
- speckit 生成的 Agent 执行失败不得导致整个系统崩溃
- speckit 生成的系统必须实现优雅降级与错误恢复机制
- speckit 生成的系统必须使用统一的错误处理中间件

**知识库一致性**
- speckit 生成的信息检索 Agent 必须保证引用来源的真实性与可追溯性
- speckit 生成的系统必须确保所有检索结果附带来源文档与位置信息
- speckit 生成的系统必须支持段落级定位和页码定位

## 附加约束与结构约定

**分层架构**
- speckit 生成的业务与基础设施代码需要分层摆放：`src/domain/`、`src/application/`、`src/interfaces/`、`src/infrastructure/`
- speckit 生成的公共组件或工具库必须放入 `src/shared/`，并附带最小 README 说明复用方式
- speckit 生成的架构设计必须体现清晰的分层边界

**目录调整流程**
- speckit 生成的目录调整或新增子系统前，需更新相关文档（如 `plan.md` 的"项目结构"段落）并获得评审确认
- speckit 生成的文档变更流程必须包含评审机制

**开发环境**
- speckit 生成的开发与调试的基础环境为 Windows 11
- speckit 生成的默认字符集为 UTF-8
- speckit 生成的所有脚本与工具必须在该环境下通过验证

**依赖管理**
- speckit 生成的项目依赖通过名为 `whitepaper` 的 Conda 环境统一管理
- speckit 生成的文档中的命令示例应展示激活步骤：`conda activate whitepaper`

**团队沟通**
- speckit 生成的团队沟通（含规范、计划、任务、代码注释、PR 描述）一律使用中文
- speckit 生成的系统必须确保术语一致与可审阅性

## speckit 工作流程与质量门禁

**功能分支规范**
- speckit 生成的功能分支必须引用对应的 `specs/[feature]/` 文档
- speckit 生成的 PR 描述中必须说明受影响的章程原则

**speckit PR 检查清单**
- speckit 生成的 PR 检查清单必须包含：
  - [ ] 单元测试已更新
  - [ ] 目录规范已验证
  - [ ] 架构质量检查通过（DRY、SOLID、设计模式）
  - [ ] 文件长度 < 4000 行
  - [ ] 无临时文件
  - [ ] 相关文档已更新（如需要）

**speckit CI 流水线要求**
- speckit 生成的 CI 流水线需包含：
  - 静态代码检查（Ruff、Mypy）
  - 单元测试套件
  - 临时文件扫描
  - 文件长度守卫（检测 >4000 行）
  - 代码重复度检查（阈值 >5%）

**speckit CI 失败条件**
- speckit 生成的 CI 必须在以下情况下失败：
  - 文件长度超限（>4000 行）
  - 代码重复度 >5%
  - 生成目录异常
  - 违反 SOLID 原则
  - 文档未更新（如需要）

**文档同步要求**
- speckit 生成的任何代码或行为变更都必须同步更新相关文档
- speckit 必须在任务清单中明确受影响文档包括：`spec.md`、`plan.md`、`tasks.md`、`README`、架构图、`docs/` 目录中的相关文档
- speckit 生成的 PR 需明确列出受影响文档并完成更新或说明原因

**speckit 文档更新流程**
- speckit 生成的若更新影响 speckit 产物，必须按照顺序重新运行：
  1. `/speckit.specify` → 更新 `spec.md`
  2. `/speckit.plan` → 更新 `plan.md`
  3. `/speckit.tasks` → 更新 `tasks.md`
  4. `/speckit.analyze` → 复查一致性

## speckit 生成约束

**speckit 代码质量工具**
- speckit 生成的项目必须包含：
  - Ruff（代码格式化与 linting）
  - Mypy（类型检查）
  - pytest（测试框架）

**speckit CLI 工具**
- speckit 生成的项目必须包含：
  - Typer（CLI 框架）
  - Rich（输出格式化）

**speckit 禁止事项**
- speckit 严禁生成：
  - ❌ 超过 4000 行的源文件
  - ❌ 包含临时文件的提交（`.tmp`、`debug.log` 等）
  - ❌ 在代码中硬编码配置（必须使用环境变量或配置文件）
  - ❌ 违反 SOLID 原则的代码（特别是单一职责和依赖倒置）
  - ❌ 重复代码（必须先提取为可复用组件）
  - ❌ 绕过模块化边界的代码（直接访问内部实现）
  - ❌ 忽略错误处理的代码（必须实现优雅降级）
  - ❌ 缺少必要的测试的代码（新增功能必须包含测试）
  - ❌ 文档未更新的代码（架构/API 变更必须同步文档）

## speckit 生成提示

**speckit 代码生成时的要求**
- speckit 在编写新代码时必须：
  1. 检查文件是否接近 4000 行限制
  2. 确认代码遵循分层架构（domain/application/interfaces/infrastructure）
  3. 使用 Protocol/ABC 定义接口，而非具体实现
  4. 添加必要的类型注解（支持 Mypy 检查）
  5. 提取重复代码为可复用组件
  6. 添加单元测试
  7. 更新相关文档（如需要）
  8. 在文件头部添加生成命令和时间戳（如果是自动生成）

**speckit 重构代码时的要求**
- speckit 在重构现有代码时必须：
  1. 运行重构检查清单（见 P1 部分）
  2. 确保重构不破坏现有测试
  3. 更新相关文档和架构图

**speckit 实现 Agent 时的要求**
- speckit 在实现 Agent 时必须：
  1. 确认 Agent 遵循单一职责原则
  2. 定义明确的输入/输出接口
  3. 添加结构化日志记录
  4. 实现错误隔离机制
  5. 确保可追溯性（特别是信息检索 Agent）

## 章程版本

本章程基于 `.specify/memory/constitution.md` 版本 1.2.0（最后修正：2025-12-05）。

speckit 生成的任何原则的修改或新增需在提案中说明动机、影响与迁移计划，并由核心维护者批准后方可生效。