# 贡献指南

感谢您对 whitepaper 项目的关注！我们欢迎各种形式的贡献。

## 项目概述

whitepaper 是一个基于人工智能的深度文档生成系统，通过先进的AI技术实现专业文档的自动生成。

## 如何开始

### 1. 环境设置

```bash
# 克隆仓库
git clone https://github.com/nphenix/whitepaper.git
cd whitepaper

# 激活conda环境
conda activate whitepaper

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest
```

### 2. 开发流程

1. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **编写代码**
   - 遵循项目代码规范
   - 添加必要的测试
   - 更新相关文档

3. **提交更改**
   ```bash
   git add .
   git commit -m "feat: 添加新功能描述"
   ```

4. **推送分支**
   ```bash
   git push origin feature/your-feature-name
   ```

5. **创建 Pull Request**
   - 描述更改内容
   - 说明影响范围
   - 标记相关 Issue

## 代码规范

### Python 代码规范
- 使用 Ruff 进行代码格式化和 linting
- 遵循 PEP 8 规范
- 添加必要的类型注解

### 提交信息规范
- 使用 [Conventional Commits](https://www.conventionalcommits.org/) 规范
- 示例：
  - `feat: 添加新功能`
  - `fix: 修复某个 bug`
  - `docs: 更新文档`
  - `refactor: 重构代码`
  - `test: 添加测试`
  - `chore: 构建过程或辅助工具的变动`

## 测试

### 运行测试
```bash
# 运行所有测试
pytest

# 运行特定测试
pytest tests/test_specific_module.py

# 运行带覆盖率的测试
pytest --cov=src
```

### 编写测试
- 为新功能编写单元测试
- 测试文件放在 `tests/` 目录
- 遵循 AAA 模式（Arrange, Act, Assert）

## 文档

### 更新文档
- 修改 `README.md` 以反映新功能
- 更新 `docs/` 目录中的相关文档
- 确保文档与代码保持同步

### 文档格式
- 使用 Markdown 格式
- 保持文档简洁明了
- 添加必要的示例和截图

## 提交 Pull Request

### PR 要求
- [ ] 代码通过所有测试
- [ ] 代码符合规范要求
- [ ] 添加了必要的测试
- [ ] 更新了相关文档
- [ ] PR 描述清晰明确

### PR 描述模板
```markdown
## 概述
简要描述本次更改

## 更改内容
- [ ] 新增功能
- [ ] 修复 Bug
- [ ] 文档更新
- [ ] 其他

## 测试
- [ ] 本地测试通过
- [ ] 新增测试用例
- [ ] 文档已更新

## 相关 Issue
Fixes #XXX
```

## 问题反馈

如果您遇到问题或有改进建议，请：

1. 检查是否已有相关 Issue
2. [创建新 Issue](https://github.com/nphenix/whitepaper/issues/new)
3. 提供详细的问题描述和复现步骤

## 联系我们

- 项目地址：https://github.com/nphenix/whitepaper
- 问题反馈：https://github.com/nphenix/whitepaper/issues

## 许可证

本项目采用 MIT 许可证。参与贡献即表示您同意遵循此许可证。

---

**感谢您的贡献！** 🎉