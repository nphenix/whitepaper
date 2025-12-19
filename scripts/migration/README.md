# 数据库迁移框架

这是 whitepaper 项目的数据库迁移框架，用于管理数据库结构的版本控制和迁移。

## 目录结构

```
scripts/migration/
├── README.md                    # 本文档
├── migration_utils.py           # 迁移工具模块
├── init_db.py                  # 迁移命令行工具
└── migrations/                 # 迁移文件目录
    └── 001_create_initial_tables.sql  # 初始表结构迁移
```

## 功能特性

- **版本控制**: 支持数据库结构的版本化管理
- **依赖关系**: 支持迁移之间的依赖关系定义
- **回滚支持**: 支持迁移的回滚操作
- **状态跟踪**: 跟踪迁移的执行状态和历史
- **命令行工具**: 提供完整的CLI界面
- **Rich输出**: 使用Rich库提供美观的命令行输出

## 使用方法

### 1. 初始化数据库

```bash
# 使用默认配置初始化数据库
python scripts/migration/init_db.py init

# 指定数据库路径
python scripts/migration/init_db.py init --db-path ./data/my.db

# 强制重新初始化（即使数据库已存在）
python scripts/migration/init_db.py init --force
```

### 2. 应用迁移

```bash
# 应用所有待应用的迁移
python scripts/migration/init_db.py migrate

# 指定数据库路径和迁移目录
python scripts/migration/init_db.py migrate \
    --db-path ./data/my.db \
    --migrations-dir ./custom_migrations
```

### 3. 查看迁移状态

```bash
# 显示当前迁移状态
python scripts/migration/init_db.py status
```

### 4. 创建新迁移

```bash
# 创建新的迁移文件
python scripts/migration/init_db.py create_migration "add_user_profile_table"
```

这将在 `migrations/` 目录下创建一个新的迁移文件模板。

### 5. 回滚迁移

```bash
# 回滚到指定版本
python scripts/migration/init_db.py rollback 001
```

### 6. 导出迁移计划

```bash
# 导出当前迁移状态为JSON文件
python scripts/migration/init_db.py export_plan migration_plan.json
```

## 迁移文件格式

迁移文件使用SQL格式，支持升级和回滚脚本：

```sql
-- Migration: Add User Profile Table
-- Version: 002
-- Created: 2025-12-08

-- @up
-- 在此处添加升级SQL语句
CREATE TABLE user_profiles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    bio TEXT,
    avatar_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- @down
-- 在此处添加回滚SQL语句（可选）
DROP TABLE IF EXISTS user_profiles;
```

### 迁移文件命名规则

迁移文件使用以下命名格式：
- 文件名：`{version}_{description}.sql`
- 版本号：3位数字，如 `001`, `002`, `003`
- 描述：使用下划线分隔的小写字母，如 `create_initial_tables`

## 编程接口

### MigrationManager 类

```python
from migration_utils import create_migration_manager

# 创建迁移管理器
manager = create_migration_manager("./data/whitepaper.db")

# 加载迁移文件
manager.load_migrations_from_directory("./scripts/migration/migrations")

# 应用待应用的迁移
applied_versions = manager.apply_pending_migrations()

# 获取迁移状态
status = manager.get_migration_status()
```

### Migration 类

```python
from migration_utils import Migration

# 创建迁移对象
migration = Migration(
    version="002",
    description="Add user profile table",
    up_sql="CREATE TABLE user_profiles (...)",
    down_sql="DROP TABLE IF EXISTS user_profiles",
    dependencies=["001"]  # 依赖版本001
)

# 添加到管理器
manager.add_migration(migration)
```

## 数据库表结构

初始迁移文件 (`001_create_initial_tables.sql`) 创建了以下表：

- `users` - 用户表
- `documents` - 文档表
- `document_chunks` - 文档块表
- `knowledge_entries` - 知识库条目表
- `graph_entities` - 图谱实体表
- `graph_relations` - 图谱关系表
- `global_constraints` - 全局约束条件表
- `outlines` - 大纲表
- `optimized_outlines` - 优化后大纲表
- `source_matches` - 信息源匹配结果表
- `source_feedback` - 信息源反馈表
- `custom_data_sources` - 自定义数据源表
- `web_data_sources` - 网络数据源表
- `retrieval_queries` - 检索查询表
- `retrieval_results` - 检索结果表
- `drafts` - 文稿草稿表
- `chart_configs` - 图表配置表
- `draft_edit_states` - 草稿编辑界面状态表
- `document_templates` - 文档模板表
- `memory_entries` - 记忆条目表
- `learning_patterns` - 学习模式表

## 最佳实践

1. **迁移文件**: 每个迁移文件应该是一个独立的逻辑单元
2. **回滚脚本**: 始终提供回滚脚本，除非是数据迁移
3. **依赖关系**: 明确声明迁移之间的依赖关系
4. **测试**: 在开发环境中测试迁移和回滚
5. **备份**: 在生产环境应用迁移前备份数据库
6. **版本控制**: 将迁移文件纳入版本控制系统

## 错误处理

迁移框架提供了完善的错误处理：

- **SQL错误**: 详细的SQL执行错误信息
- **依赖检查**: 自动检查迁移依赖关系
- **事务支持**: 每个迁移在事务中执行，失败时自动回滚
- **状态跟踪**: 记录迁移的执行时间和状态

## 日志记录

迁移框架使用 structlog 进行结构化日志记录：

- 迁移开始和完成
- SQL执行状态
- 错误和警告信息
- 性能指标（执行时间）

## 配置

迁移框架使用项目的配置系统：

```python
from src.shared.config.settings import get_config

config = get_config()
db_path = config.database.sqlite_db_path
```

## 测试

运行迁移框架的测试：

```bash
# 运行所有测试
pytest tests/unit/migration/

# 运行特定测试
pytest tests/unit/migration/test_migration_utils.py
```

## 故障排除

### 常见问题

1. **数据库锁定**: 确保没有其他进程正在使用数据库
2. **权限问题**: 确保对数据库目录有写权限
3. **迁移失败**: 检查SQL语法和依赖关系
4. **版本冲突**: 确保迁移版本号唯一

### 调试模式

启用详细日志输出：

```bash
python scripts/migration/init_db.py --log-level DEBUG migrate
```

## 贡献

在添加新的迁移时，请遵循：

1. 使用描述性的迁移名称
2. 提供完整的回滚脚本
3. 添加必要的索引
4. 更新相关文档
5. 测试迁移和回滚流程