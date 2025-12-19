# CodeFlicker AI 代理配置

本目录包含了为 CodeFlicker AI 代理配置的完整 speckit 规则和命令。

## 配置概述

### 1. 规则文件
- **`rules/agents.md`**: CodeFlicker 代理的核心开发规则，包含 P1-P5 所有原则
- **`rules/specify-rules.md`**: speckit 工具的专用规则，确保生成内容符合项目章程

### 2. 命令文件
- **`commands/speckit.specify.md`**: 功能规范创建命令
- **`commands/speckit.plan.md`**: 实施计划创建命令
- **`commands/speckit.tasks.md`**: 任务分解命令
- **`commands/speckit.checklist.md`**: 质量检查清单创建命令
- **`commands/speckit.clarify.md`**: 规范澄清命令
- **`commands/speckit.analyze.md`**: 一致性分析命令
- **`commands/speckit.constitution.md`**: 章程更新命令
- **`commands/speckit.implement.md`**: 项目实施命令
- **`commands/speckit.taskstoissues.md`**: 任务转 GitHub Issues 命令

### 3. 脚本文件
- **`scripts/powershell/update-agent-context.ps1`**: 自动更新代理上下文的 PowerShell 脚本

## 快速开始

### 使用 update-agent-context.ps1 脚本

1. 打开 PowerShell
2. 导航到项目根目录
3. 运行脚本更新 CodeFlicker 上下文：

```powershell
# 更新 codeflicker 的规则文件
./.codeflicker/scripts/powershell/update-agent-context.ps1 -AgentType codeflicker

# 或者使用简写形式（如果脚本支持）
./.codeflicker/scripts/powershell/update-agent-context.ps1 codeflicker
```

## 配置说明

### 与 roocode 和 cursor 的区别

1. **目录结构**：
   - roocode: `.roo/rules/` 和 `.roo/commands/`
   - cursor: `.cursor/rules/` 和 `.cursor/commands/`
   - codeflicker: `.codeflicker/rules/` 和 `.codeflicker/commands/`

2. **规则内容**：
   - 所有三个代理都遵循相同的项目章程（`.specify/memory/constitution.md`）
   - 规则内容完全一致，确保跨代理的一致性
   - 每个代理都有针对其特定环境的微调

3. **命令文件**：
   - 所有命令文件结构相同
   - 确保在不同 AI 代理间无缝切换

### 支持的 speckit 命令

- **`/speckit.specify`**: 从自然语言描述创建功能规范
- **`/speckit.plan`**: 为功能规范创建实施计划
- **`/speckit.tasks`**: 将计划分解为具体任务
- **`/speckit.checklist`**: 创建质量检查清单
- **`/speckit.clarify`**: 澄清和细化规范
- **`/speckit.analyze`**: 分析规范、计划、任务的一致性
- **`/speckit.constitution`**: 更新项目章程
- **`/speckit.implement`**: 实施项目
- **`/speckit.taskstoissues`**: 将任务转换为 GitHub Issues

## 项目章程原则

所有配置都基于 `.specify/memory/constitution.md` 中定义的 P1-P5 原则：

### P1 代码质量守则
- 模块化边界
- 文件长度限制（≤4000行）
- 测试要求
- 架构质量原则（DRY、SOLID、设计模式）

### P2 目录结构与工件定位
- 目录规范
- 文件定位规则
- 脚本验证

### P3 临时文件纪律
- 临时文件管理
- 缓存管理
- CI/CD 检查

### P4 文档与可维护性
- 文档标注要求
- 代码注释要求
- 设计决策记录
- docs 目录文档管理规则

### P5 Agent 设计原则
- 单一职责
- 可组合性
- 可观测性
- 错误隔离
- 知识库一致性

## 使用示例

### 创建新功能规范

1. 在 CodeFlicker 中输入：
```
/speckit.specify 实现用户认证功能，支持邮箱注册、登录和密码重置
```

2. CodeFlicker 将：
   - 创建功能分支
   - 生成 `specs/[feature]/spec.md`
   - 创建质量检查清单
   - 提示继续下一步

### 创建实施计划

1. 在 CodeFlicker 中输入：
```
/speckit.plan 为用户认证功能创建实施计划
```

2. CodeFlicker 将：
   - 分析技术背景
   - 定义项目结构
   - 创建实施阶段
   - 生成数据模型
   - 创建快速开始指南

### 分解任务

1. 在 CodeFlicker 中输入：
```
/speckit.tasks 将用户认证计划分解为任务
```

2. CodeFlicker 将：
   - 分析功能需求
   - 分解为具体任务
   - 分配优先级
   - 生成 `tasks.md`

## 维护

### 更新规则

如果项目章程更新，需要同步更新所有代理的规则文件：

1. 更新 `.specify/memory/constitution.md`
2. 运行 update-agent-context.ps1 更新所有代理
3. 验证配置是否正确

### 添加新命令

如需添加新的 speckit 命令：

1. 在 `.codeflicker/commands/` 目录下创建新文件
2. 使用标准的 YAML frontmatter 格式
3. 确保命令遵循项目章程原则
4. 更新此 README 文档

## 故障排除

### 常见问题

1. **脚本无法运行**：
   - 确保 PowerShell 执行策略允许脚本运行
   - 使用 `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`

2. **规则文件未更新**：
   - 检查脚本路径是否正确
   - 确保有写入权限

3. **speckit 命令不工作**：
   - 确保 CodeFlicker 已正确加载规则文件
   - 重启 CodeFlicker 以重新加载配置

### 获取帮助

如有问题，请：
1. 检查 `.specify/memory/constitution.md` 了解项目章程
2. 查看其他代理的配置作为参考
3. 联系项目维护者

## 版本信息

- **配置版本**: 1.2.0
- **最后更新**: 2025-12-05
- **基于章程**: `.specify/memory/constitution.md` v1.2.0