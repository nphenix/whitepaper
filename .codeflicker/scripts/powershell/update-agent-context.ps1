# update-agent-context.ps1
# 为 codeflicker 更新 AI 代理上下文文件
# 支持的代理: claude, gemini, copilot, cursor-agent, qwen, opencode, codex, windsurf, kilocode, auggie, roo, codebuddy, amp, shai, q

param(
    [Parameter(Position=0)]
    [ValidateSet('claude','gemini','copilot','cursor-agent','qwen','opencode','codex','windsurf','kilocode','auggie','roo','codebuddy','amp','shai','q')]
    [string]$AgentType
)

# 函数: 输出带时间戳的错误消息
function Write-Err {
    param([string]$Message)
    Write-Host -ForegroundColor Red "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] ERROR: $Message"
}

# 函数: 输出带时间戳的警告消息
function Write-Warn {
    param([string]$Message)
    Write-Host -ForegroundColor Yellow "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] WARNING: $Message"
}

# 函数: 输出带时间戳的信息消息
function Write-Info {
    param([string]$Message)
    Write-Host -ForegroundColor Cyan "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] INFO: $Message"
}

# 设置默认值
if ([string]::IsNullOrEmpty($AgentType)) {
    Write-Err "Agent type is required."
    Write-Info 'Usage: ./update-agent-context.ps1 [-AgentType claude|gemini|copilot|cursor-agent|qwen|opencode|codex|windsurf|kilocode|auggie|roo|codebuddy|amp|shai|q]'
    exit 1
}

# 路径和文件名
$REPO_ROOT = Resolve-Path -Path "$PSScriptRoot/../../.."
$SPECIFY_DIR = Join-Path $REPO_ROOT '.specify'
$RULES_DIR = Join-Path $REPO_ROOT '.codeflicker/rules'
$COMMANDS_DIR = Join-Path $REPO_ROOT '.codeflicker/commands'
$COPILOT_FILE  = Join-Path $REPO_ROOT '.github/agents/copilot-instructions.md'
$CURSOR_FILE   = Join-Path $REPO_ROOT '.cursor/rules/specify-rules.mdc'
$QWEN_FILE     = Join-Path $REPO_ROOT 'QWEN.md'
$OPENCODE_FILE = Join-Path $REPO_ROOT '.opencode/rules/specify-rules.md'
$CODEX_FILE    = Join-Path $REPO_ROOT '.codex/rules/specify-rules.md'
$WINDSURF_FILE = Join-Path $REPO_ROOT '.windsurf/rules/specify-rules.md'
$KILOCODE_FILE = Join-Path $REPO_ROOT '.kilocode/rules/specify-rules.md'
$AUGGIE_FILE   = Join-Path $REPO_ROOT '.auggie/rules/specify-rules.md'
$ROO_FILE      = Join-Path $REPO_ROOT '.roo/rules/specify-rules.md'
$CODEBUDDY_FILE= Join-Path $REPO_ROOT '.codebuddy/rules/specify-rules.md'
$AMP_FILE      = Join-Path $REPO_ROOT '.amp/rules/specify-rules.md'
$SHAI_FILE     = Join-Path $REPO_ROOT '.shai/rules/specify-rules.md'
$Q_FILE        = Join-Path $REPO_ROOT '.q/rules/specify-rules.md'

# 函数: 读取规则模板
function Get-RulesTemplate {
    $RULES_TEMPLATE = @"
# whitepaper 项目开发代理规则

**版本**: 1.2.0 | **最后更新**: 2025-12-05 | **来源**: `.specify/memory/constitution.md`

本文档定义了在使用 $AgentName 进行 whitepaper 项目开发时必须遵循的核心规则和约束。这些规则基于项目章程，确保代码质量、架构一致性和可维护性。

## 核心原则

### P1 代码质量守则

**模块化边界**
- 所有功能必须保持清晰的模块化边界，避免巨石式文件或隐式耦合
- 遵循分层架构：`src/domain/`（领域模型）、`src/application/`（应用服务）、`src/interfaces/`（接口层）、`src/infrastructure/`（基础设施）
- 模块之间通过明确的接口（Protocol/ABC）通信

**文件长度限制**
- ⚠️ **硬性限制**：单个源文件不得超过 4000 行
- 如果文件超过限制，必须拆分为职责清晰的子模块
- 拆分时保持单一职责原则（Single Responsibility Principle）

**测试要求**
- 所有新增功能必须同步交付自动化单元测试
- 测试文件位置：`tests/unit/`、`tests/integration/`、`tests/contract/`
- 通过正式代码评审后方可合入主干

**架构质量原则**
- **DRY 原则**：禁止重复代码。发现重复代码模式时，必须提取为可复用的组件、基类或工具函数
- **SOLID 原则**：
  - **单一职责**：每个类/模块只负责一个明确的功能领域
  - **开闭原则**：通过策略模式、适配器模式、工厂模式等实现扩展，而非修改现有代码
  - **依赖倒置**：客户端代码依赖抽象接口（ABC、Protocol），而非具体实现
- **设计模式优先**：在需要扩展性时，优先使用设计模式而非硬编码的条件分支
- **接口统一**：同一功能的不同实现必须通过统一接口暴露，使用适配器模式整合

**重构检查清单**（每次修改代码时必须自检）
- [ ] 是否存在重复代码？如有，是否已提取为可复用组件？
- [ ] 类/模块是否违反单一职责原则？如有，是否已拆分？
- [ ] 是否需要扩展性？如有，是否使用了设计模式而非硬编码？
- [ ] 接口是否统一？不同实现是否通过适配器模式整合？
- [ ] 错误处理是否使用了统一的上下文管理器或装饰器？

### P2 目录结构与工件定位

**目录规范**
- 必须遵循 `specs/001-multi-agent-doc-system/plan.md` 中定义的项目结构
- 不允许随意新增顶层目录或模糊命名
- 自动生成的代码/文档必须写入预期路径（`specs/`、`docs/`、`src/` 下的既定子目录）
- 生成脚本需在输出完成后验证文件是否落在正确位置，文件位置错误视为构建失败

**文件定位规则**
- 领域模型 → `src/domain/`
- 应用服务 → `src/application/services/`
- Agent 实现 → `src/application/agents/`
- API 路由 → `src/interfaces/api/routes/`
- API Schema → `src/interfaces/api/schemas/`
- CLI 命令 → `src/interfaces/cli/`
- 基础设施适配器 → `src/infrastructure/`
- 共享组件 → `src/shared/`
- 测试文件 → `tests/unit/`、`tests/integration/`、`tests/contract/`

**脚本验证**
- 生成脚本需在输出完成后验证文件是否落在正确位置，文件位置错误视为构建失败

### P3 临时文件纪律

**临时文件管理**
- 临时脚本、草稿或调试工件只能存在于隔离的工作区，使用完毕立即删除，不得提交到仓库
- 临时文件目录：`data/temp/`（处理完成后自动清理）

**缓存管理**
- 运行 speckit 或其他脚本时若必须生成缓存，需在命令流程中显式清理
- LangGraph Checkpointer 缓存配置为可清理模式
- 保证仓库保持干净状态

**CI/CD 检查**
- CI/CD 管道需检查并阻止包含临时文件的提交
- 禁止的文件模式：`.tmp`、`debug.log`、未命名文档等

### P4 文档与可维护性

**文档标注要求**
- 所有自动生成的代码/文档必须在文件头部标注生成命令与时间戳
- 格式示例：
  ```python
  # 生成命令: /speckit.implement T023
  # 生成时间: 2025-12-05
  # 来源: specs/001-multi-agent-doc-system/tasks.md
  ```

**代码注释要求**
- 函数、组件、脚本若包含非显而易见的约束或副作用，必须通过行内注释或同目录 README 进行说明
- 复杂业务逻辑必须添加注释说明设计理由

**设计决策记录**
- 重大设计决策需在 `docs/` 或对应 `specs/` 下记录理由
- 架构变更 → `docs/architecture/`
- API 变更 → `docs/api/`
- 编码规范变更 → `docs/development/`

**docs 目录文档管理规则**
- **文档更新时机**：
  - 架构变更必须在 PR 合并前更新 `docs/architecture/`
  - API 变更必须在 PR 合并前更新 `docs/api/`
  - 编码规范、开发流程变更必须同步更新 `docs/development/`
  - 部署配置、环境变更必须同步更新 `docs/deployment/`
- **文档更新责任**：
  - 代码变更的发起者负责更新相关 `docs/` 文档
  - PR 描述中必须明确列出受影响的文档并完成更新
  - Code Review 时必须验证文档是否已同步更新
- **文档质量要求**：
  - 文档必须使用中文编写
  - 术语与代码保持一致
  - 架构文档必须包含组件图、数据流图
  - API 文档必须包含请求/响应示例、错误码说明
  - 文档中引用的代码路径、文件名必须与实际代码保持一致
  - 文档必须有明确的最后更新时间戳

### P5 Agent 设计原则

**单一职责**
- 每个 Agent 必须专注于单一功能领域（如文档预处理、信息检索、草稿生成）
- 禁止混合多个不相关职责

**可组合性**
- Agent 之间通过明确的接口（输入/输出契约）协作
- 支持独立开发、测试与替换
- 使用 LangChain 统一编排接口

**可观测性**
- 所有 Agent 执行过程必须记录结构化日志
- 日志包含：输入参数、中间状态、输出结果、执行时间
- 使用 LangGraph Checkpointer 记录状态，便于调试与性能分析

**错误隔离**
- Agent 执行失败不得导致整个系统崩溃
- 必须实现优雅降级与错误恢复机制
- 使用统一的错误处理中间件

**知识库一致性**
- 信息检索 Agent 必须保证引用来源的真实性与可追溯性
- 所有检索结果需附带来源文档与位置信息
- 支持段落级定位和页码定位

**Agent 设计检查清单**
- [ ] Agent 是否遵循单一职责原则？
- [ ] Agent 协作接口是否明确？
- [ ] Agent 执行过程是否具备可观测性（日志、追踪）？
- [ ] Agent 错误处理是否独立且优雅？

## 附加约束与结构约定

**分层架构**
- 业务与基础设施代码需要分层摆放：`src/domain/`、`src/application/`、`src/interfaces/`、`src/infrastructure/`
- 公共组件或工具库必须放入 `src/shared/`，并附带最小 README 说明复用方式

**目录调整流程**
- 目录调整或新增子系统前，需更新相关文档（如 `plan.md` 的"项目结构"段落）并获得评审确认

**开发环境**
- 开发与调试的基础环境为 Windows 11
- 默认字符集 UTF-8
- 所有脚本与工具必须在该环境下通过验证

**依赖管理**
- 项目依赖通过名为 `whitepaper` 的 Conda 环境统一管理
- 文档中的命令示例应展示激活步骤：`conda activate whitepaper`

**团队沟通**
- 团队沟通（含规范、计划、任务、代码注释、PR 描述）一律使用中文
- 确保术语一致与可审阅性

## 开发工作流程与质量门禁

**功能分支规范**
- 每个功能分支必须引用对应的 `specs/[feature]/` 文档
- PR 描述中说明受影响的章程原则

**PR 检查清单**
- [ ] 单元测试已更新
- [ ] 目录规范已验证
- [ ] 架构质量检查通过（DRY、SOLID、设计模式）
- [ ] 文件长度 < 4000 行
- [ ] 无临时文件
- [ ] 相关文档已更新（如需要）

**CI 流水线要求**
- 静态代码检查（Ruff、Mypy）
- 单元测试套件
- 临时文件扫描
- 文件长度守卫（检测 >4000 行）
- 代码重复度检查（阈值 >5%）

**CI 失败条件**
- 文件长度超限（>4000 行）
- 代码重复度 >5%
- 生成目录异常
- 违反 SOLID 原则
- 文档未更新（如需要）

**文档同步要求**
- 任何代码或行为变更都必须同步更新相关文档
- 受影响文档包括：`spec.md`、`plan.md`、`tasks.md`、`README`、架构图、`docs/` 目录中的相关文档
- PR 需明确列出受影响文档并完成更新或说明原因

**speckit 文档更新流程**
- 若更新影响 speckit 产物，必须按照顺序重新运行：
  1. `/speckit.specify` → 更新 `spec.md`
  2. `/speckit.plan` → 更新 `plan.md`
  3. `/speckit.tasks` → 更新 `tasks.md`
  4. `/speckit.analyze` → 复查一致性

## 技术栈约束

**核心框架**
- Python 3.12
- LangChain 1.0（Agent 编排）
- LangGraph（状态管理）
- LangMem（记忆系统）
- llamaIndex（RAG 管线）
- FastAPI（Web 服务）
- Arq（异步任务队列）
- SQLite（结构化数据）
- Chroma（向量数据）
- NetworkX（图数据）

**代码质量工具**
- Ruff（代码格式化与 linting）
- Mypy（类型检查）
- pytest（测试框架）

**CLI 工具**
- Typer（CLI 框架）
- Rich（输出格式化）

## 禁止事项

**严格禁止**
- ❌ 创建超过 4000 行的源文件
- ❌ 提交临时文件（`.tmp`、`debug.log` 等）
- ❌ 在代码中硬编码配置（使用环境变量或配置文件）
- ❌ 违反 SOLID 原则（特别是单一职责和依赖倒置）
- ❌ 重复代码（必须先提取为可复用组件）
- ❌ 绕过模块化边界（直接访问内部实现）
- ❌ 忽略错误处理（必须实现优雅降级）
- ❌ 缺少必要的测试（新增功能必须包含测试）
- ❌ 文档未更新（架构/API 变更必须同步文档）

## 代码生成提示

**当编写新代码时，请：**
1. 检查文件是否接近 4000 行限制
2. 确认代码遵循分层架构（domain/application/interfaces/infrastructure）
3. 使用 Protocol/ABC 定义接口，而非具体实现
4. 添加必要的类型注解（支持 Mypy 检查）
5. 提取重复代码为可复用组件
6. 添加单元测试
7. 更新相关文档（如需要）
8. 在文件头部添加生成命令和时间戳（如果是自动生成）

**当重构现有代码时，请：**
1. 运行重构检查清单（见 P1 部分）
2. 确保重构不破坏现有测试
3. 更新相关文档和架构图

**当实现 Agent 时，请：**
1. 确认 Agent 遵循单一职责原则
2. 定义明确的输入/输出接口
3. 添加结构化日志记录
4. 实现错误隔离机制
5. 确保可追溯性（特别是信息检索 Agent）

## 章程版本

本章程基于 `.specify/memory/constitution.md` 版本 1.2.0（最后修正：2025-12-05）。

任何原则的修改或新增需在提案中说明动机、影响与迁移计划，并由核心维护者批准后方可生效。

## 快速参考

**常用路径**
- 章程文件：`.specify/memory/constitution.md`
- 规范文档：`specs/001-multi-agent-doc-system/spec.md`
- 计划文档：`specs/001-multi-agent-doc-system/plan.md`
- 任务文档：`specs/001-multi-agent-doc-system/tasks.md`
- 数据模型：`specs/001-multi-agent-doc-system/data-model.md`
- 架构文档：`docs/architecture/`
- API 文档：`docs/api/`

**常用命令**
- 激活环境：`conda activate whitepaper`
- 运行测试：`pytest`
- 代码检查：`ruff check .`、`mypy .`
- 代码格式化：`ruff format .`

"@
    return $RULES_TEMPLATE
}

# 函数: 更新 Agent 文件
function Update-AgentFile {
    param(
        [string]$TargetFile,
        [string]$AgentName
    )

    Write-Info "Updating $TargetFile for $AgentName..."

    # 读取模板
    $content = Get-RulesTemplate -AgentName $AgentName

    # 写入文件
    try {
        $content | Out-File -FilePath $TargetFile -Encoding utf8 -Force
        Write-Info "Successfully updated $TargetFile"
    } catch {
        Write-Err "Failed to write $TargetFile : $_"
        return $false
    }
    return $true
}

# 主逻辑
$AgentName = $AgentType

# 创建目录（如果不存在）
if (!(Test-Path $RULES_DIR)) {
    New-Item -ItemType Directory -Path $RULES_DIR -Force | Out-Null
}
if (!(Test-Path $COMMANDS_DIR)) {
    New-Item -ItemType Directory -Path $COMMANDS_DIR -Force | Out-Null
}

# 选择并更新对应的文件
switch ($AgentType) {
    'copilot' {
        Update-AgentFile -TargetFile $COPILOT_FILE  -AgentName 'GitHub Copilot'
    }
    'cursor-agent' {
        Update-AgentFile -TargetFile $CURSOR_FILE   -AgentName 'Cursor IDE'
    }
    'qwen' {
        Update-AgentFile -TargetFile $QWEN_FILE     -AgentName 'Qwen Code'
    }
    'opencode' {
        Update-AgentFile -TargetFile $OPENCODE_FILE -AgentName 'OpenCode'
    }
    'codex' {
        Update-AgentFile -TargetFile $CODEX_FILE    -AgentName 'OpenAI Codex'
    }
    'windsurf' {
        Update-AgentFile -TargetFile $WINDSURF_FILE -AgentName 'Windsurf'
    }
    'kilocode' {
        Update-AgentFile -TargetFile $KILOCODE_FILE -AgentName 'KiloCode'
    }
    'auggie' {
        Update-AgentFile -TargetFile $AUGGIE_FILE   -AgentName 'Auggie'
    }
    'roo' {
        Update-AgentFile -TargetFile $ROO_FILE      -AgentName 'Roo'
    }
    'codebuddy' {
        Update-AgentFile -TargetFile $CODEBUDDY_FILE- AgentName 'CodeBuddy'
    }
    'amp' {
        Update-AgentFile -TargetFile $AMP_FILE      -AgentName 'Amazon CodeWhisperer'
    }
    'shai' {
        Update-AgentFile -TargetFile $SHAI_FILE     -AgentName 'Shai'
    }
    'q' {
        Update-AgentFile -TargetFile $Q_FILE        -AgentName 'Amazon Q Developer CLI'
    }
    default {
        Write-Err "Unknown agent type '$Type'"
        Write-Err 'Expected: claude|gemini|copilot|cursor-agent|qwen|opencode|codex|windsurf|kilocode|auggie|roo|codebuddy|amp|shai|q'
        return $false
    }
}

# 如果是 roo，额外创建 commands 目录
if ($AgentType -eq 'roo') {
    # 检查 commands 目录是否存在
    if (!(Test-Path $COMMANDS_DIR)) {
        Write-Info "Creating commands directory for roo..."
        New-Item -ItemType Directory -Path $COMMANDS_DIR -Force | Out-Null
    }
}

Write-Info "Agent context update completed for $AgentName."