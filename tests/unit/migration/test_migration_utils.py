# 生成命令: T015 数据库迁移脚本框架
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
迁移工具模块测试

测试 Migration 和 MigrationManager 类的功能。
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.migration.migration_utils import (
    Migration,
    MigrationManager,
    create_migration_manager,
)
from src.shared.exceptions.storage_exceptions import SQLiteError


class TestMigration:
    """Migration 类测试"""

    def test_migration_creation_valid(self):
        """测试创建有效的迁移"""
        migration = Migration(
            version="001",
            description="Create users table",
            up_sql="CREATE TABLE users (id INTEGER PRIMARY KEY);",
            down_sql="DROP TABLE users;",
        )

        assert migration.version == "001"
        assert migration.description == "Create users table"
        assert migration.up_sql == "CREATE TABLE users (id INTEGER PRIMARY KEY);"
        assert migration.down_sql == "DROP TABLE users;"
        assert migration.dependencies == []

    def test_migration_creation_with_dependencies(self):
        """测试创建带依赖的迁移"""
        migration = Migration(
            version="002",
            description="Add user profiles",
            up_sql="CREATE TABLE user_profiles (...);",
            down_sql="DROP TABLE user_profiles;",
            dependencies=["001"],
        )

        assert migration.dependencies == ["001"]

    def test_migration_invalid_version_format(self):
        """测试无效版本格式"""
        with pytest.raises(ValueError, match="无效的迁移版本格式"):
            Migration(version="invalid", description="Test", up_sql="SELECT 1;")

        with pytest.raises(ValueError, match="无效的迁移版本格式"):
            Migration(version="1", description="Test", up_sql="SELECT 1;")

    def test_migration_to_dict(self):
        """测试转换为字典"""
        migration = Migration(
            version="001",
            description="Test migration",
            up_sql="CREATE TABLE test (id INTEGER);",
        )

        result = migration.to_dict()

        assert result["version"] == "001"
        assert result["description"] == "Test migration"
        assert result["dependencies"] == []
        assert "created_at" in result

    def test_migration_repr(self):
        """测试字符串表示"""
        migration = Migration(
            version="001",
            description="Test migration",
            up_sql="CREATE TABLE test (id INTEGER);",
        )

        repr_str = repr(migration)
        assert "Migration(version=001" in repr_str
        assert "description=Test migration" in repr_str


class TestMigrationManager:
    """MigrationManager 类测试"""

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            yield tmp.name
        # 清理临时文件
        Path(tmp.name).unlink(missing_ok=True)

    @pytest.fixture
    def migration_manager(self, temp_db_path):
        """创建迁移管理器实例"""
        return MigrationManager(temp_db_path)

    @pytest.fixture
    def sample_migrations(self):
        """创建示例迁移"""
        return [
            Migration(
                version="001",
                description="Create users table",
                up_sql="CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);",
                down_sql="DROP TABLE users;",
            ),
            Migration(
                version="002",
                description="Add user profiles",
                up_sql="CREATE TABLE profiles (id INTEGER PRIMARY KEY, user_id INTEGER, bio TEXT);",
                down_sql="DROP TABLE profiles;",
                dependencies=["001"],
            ),
            Migration(
                version="003",
                description="Add posts table",
                up_sql="CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT);",
                down_sql="DROP TABLE posts;",
                dependencies=["001"],
            ),
        ]

    def test_migration_manager_init(self, temp_db_path):
        """测试迁移管理器初始化"""
        manager = MigrationManager(temp_db_path)

        assert manager.db_path == Path(temp_db_path)
        assert manager.migrations == {}
        assert temp_db_path.exists()  # 数据库目录应该被创建

    def test_add_migration(self, migration_manager, sample_migrations):
        """测试添加迁移"""
        migration = sample_migrations[0]
        migration_manager.add_migration(migration)

        assert "001" in migration_manager.migrations
        assert migration_manager.migrations["001"] == migration

    def test_add_duplicate_migration(self, migration_manager, sample_migrations):
        """测试添加重复迁移"""
        migration = sample_migrations[0]
        migration_manager.add_migration(migration)

        with pytest.raises(ValueError, match="迁移版本已存在"):
            migration_manager.add_migration(migration)

    def test_add_migration_with_missing_dependency(
        self, migration_manager, sample_migrations
    ):
        """测试添加依赖缺失的迁移"""
        migration_with_invalid_dep = Migration(
            version="999",
            description="Invalid migration",
            up_sql="SELECT 1;",
            dependencies=["888"],  # 不存在的依赖
        )

        with pytest.raises(ValueError, match="依赖的迁移版本不存在"):
            migration_manager.add_migration(migration_with_invalid_dep)

    def test_get_applied_migrations_empty(self, migration_manager):
        """测试获取已应用的迁移(空数据库)"""
        applied = migration_manager.get_applied_migrations()
        assert applied == []

    def test_apply_migration(self, migration_manager, sample_migrations):
        """测试应用迁移"""
        migration = sample_migrations[0]
        migration_manager.add_migration(migration)

        result = migration_manager.apply_migration(migration)

        assert result is True

        # 检查迁移记录
        applied = migration_manager.get_applied_migrations()
        assert "001" in applied

        # 检查表是否创建
        with sqlite3.connect(migration_manager.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            tables = cursor.fetchall()
            assert len(tables) == 1

    def test_apply_migration_with_dependencies(
        self, migration_manager, sample_migrations
    ):
        """测试应用带依赖的迁移"""
        # 添加所有迁移
        for migration in sample_migrations:
            migration_manager.add_migration(migration)

        # 应用迁移002(依赖001)
        migration_002 = migration_manager.migrations["002"]
        result = migration_manager.apply_migration(migration_002)

        assert result is True

        # 检查迁移记录
        applied = migration_manager.get_applied_migrations()
        assert "002" in applied

        # 检查表是否存在
        with sqlite3.connect(migration_manager.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='profiles'"
            )
            tables = cursor.fetchall()
            assert len(tables) == 1

    def test_rollback_migration(self, migration_manager, sample_migrations):
        """测试回滚迁移"""
        migration = sample_migrations[0]
        migration_manager.add_migration(migration)

        # 先应用迁移
        migration_manager.apply_migration(migration)

        # 然后回滚
        result = migration_manager.rollback_migration(migration)

        assert result is True

        # 检查迁移记录
        applied = migration_manager.get_applied_migrations()
        assert "001" not in applied

        # 检查表是否被删除
        with sqlite3.connect(migration_manager.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            tables = cursor.fetchall()
            assert len(tables) == 0

    def test_rollback_migration_without_down_sql(self, migration_manager):
        """测试回滚没有回滚SQL的迁移"""
        migration = Migration(
            version="001",
            description="Test migration",
            up_sql="CREATE TABLE test (id INTEGER);",
            # 没有 down_sql
        )
        migration_manager.add_migration(migration)

        result = migration_manager.rollback_migration(migration)
        assert result is False

    def test_get_pending_migrations(self, migration_manager, sample_migrations):
        """测试获取待应用的迁移"""
        # 添加所有迁移
        for migration in sample_migrations:
            migration_manager.add_migration(migration)

        # 应用第一个迁移
        migration_manager.apply_migration(sample_migrations[0])

        pending = migration_manager.get_pending_migrations()

        # 应该有两个待应用的迁移
        assert len(pending) == 2
        pending_versions = [m.version for m in pending]
        assert "002" in pending_versions
        assert "003" in pending_versions
        assert "001" not in pending_versions

    def test_get_pending_migrations_with_unmet_dependencies(
        self, migration_manager, sample_migrations
    ):
        """测试获取依赖未满足的待应用迁移"""
        # 只添加迁移002和003(依赖001)
        migration_manager.add_migration(sample_migrations[1])  # 002
        migration_manager.add_migration(sample_migrations[2])  # 003

        pending = migration_manager.get_pending_migrations()

        # 依赖001未满足,所以没有待应用的迁移
        assert len(pending) == 0

    def test_apply_pending_migrations(self, migration_manager, sample_migrations):
        """测试应用所有待应用的迁移"""
        # 添加所有迁移
        for migration in sample_migrations:
            migration_manager.add_migration(migration)

        # 应用所有待应用的迁移
        applied_versions = migration_manager.apply_pending_migrations()

        assert len(applied_versions) == 3
        assert "001" in applied_versions
        assert "002" in applied_versions
        assert "003" in applied_versions

        # 检查最终状态
        applied = migration_manager.get_applied_migrations()
        assert len(applied) == 3

    def test_get_migration_status(self, migration_manager, sample_migrations):
        """测试获取迁移状态"""
        # 添加所有迁移
        for migration in sample_migrations:
            migration_manager.add_migration(migration)

        # 应用第一个迁移
        migration_manager.apply_migration(sample_migrations[0])

        status = migration_manager.get_migration_status()

        assert status["total_migrations"] == 3
        assert status["applied_count"] == 1
        assert status["pending_count"] == 2
        assert "001" in status["applied_versions"]
        assert "002" in status["pending_versions"]
        assert "003" in status["pending_versions"]

    def test_load_migrations_from_directory(self, migration_manager):
        """测试从目录加载迁移"""
        # 创建临时迁移目录
        with tempfile.TemporaryDirectory() as temp_dir:
            migrations_dir = Path(temp_dir)

            # 创建测试迁移文件
            migration_file = migrations_dir / "001_test_migration.sql"
            migration_file.write_text("""
-- Migration: Test Migration
-- Version: 001

-- @up
CREATE TABLE test_table (id INTEGER PRIMARY KEY);

-- @down
DROP TABLE test_table;
            """)

            # 加载迁移
            migration_manager.load_migrations_from_directory(migrations_dir)

            assert "001" in migration_manager.migrations
            migration = migration_manager.migrations["001"]
            assert migration.description == "test_migration"
            assert "CREATE TABLE test_table" in migration.up_sql
            assert "DROP TABLE test_table" in migration.down_sql

    def test_parse_migration_sql(self, migration_manager):
        """测试解析迁移SQL"""
        # 测试带回滚SQL的内容
        content_with_down = """
CREATE TABLE users (id INTEGER PRIMARY KEY);
-- @down
DROP TABLE users;
        """

        up_sql, down_sql = migration_manager._parse_migration_sql(content_with_down)
        assert "CREATE TABLE users" in up_sql
        assert "DROP TABLE users" in down_sql

        # 测试不带回滚SQL的内容
        content_without_down = """
CREATE TABLE users (id INTEGER PRIMARY KEY);
        """

        up_sql, down_sql = migration_manager._parse_migration_sql(content_without_down)
        assert "CREATE TABLE users" in up_sql
        assert down_sql is None

    def test_split_sql_statements(self, migration_manager):
        """测试分割SQL语句"""
        sql = """
-- 创建用户表
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

-- 创建索引
CREATE INDEX idx_users_name ON users(name);
        """

        statements = migration_manager._split_sql_statements(sql)

        assert len(statements) == 2
        assert "CREATE TABLE users" in statements[0]
        assert "CREATE INDEX idx_users_name" in statements[1]

    def test_calculate_checksum(self, migration_manager):
        """测试计算校验和"""
        sql = "CREATE TABLE users (id INTEGER PRIMARY KEY);"
        checksum1 = migration_manager._calculate_checksum(sql)
        checksum2 = migration_manager._calculate_checksum(sql)

        assert checksum1 == checksum2
        assert len(checksum1) == 32  # MD5 hash length

    def test_export_migration_plan(self, migration_manager, sample_migrations):
        """测试导出迁移计划"""
        # 添加所有迁移
        for migration in sample_migrations:
            migration_manager.add_migration(migration)

        # 应用第一个迁移
        migration_manager.apply_migration(sample_migrations[0])

        # 导出计划
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            migration_manager.export_migration_plan(tmp.name)

            # 读取并验证导出的计划
            with open(tmp.name) as f:
                plan = json.load(f)

            assert plan["total_migrations"] == 3
            assert len(plan["migrations"]) == 3

            # 检查迁移状态
            migrations = {m["version"]: m for m in plan["migrations"]}
            assert migrations["001"]["applied"] is True
            assert migrations["002"]["applied"] is False
            assert migrations["003"]["applied"] is False

            # 清理临时文件
            Path(tmp.name).unlink(missing_ok=True)

    def test_migration_failure_rollback(self, migration_manager):
        """测试迁移失败时的回滚"""
        # 创建一个会失败的迁移
        invalid_migration = Migration(
            version="001",
            description="Invalid migration",
            up_sql="INVALID SQL STATEMENT;",
            down_sql="SELECT 1;",
        )
        migration_manager.add_migration(invalid_migration)

        # 应用迁移应该失败
        with pytest.raises(SQLiteError):
            migration_manager.apply_migration(invalid_migration)

        # 检查没有迁移记录
        applied = migration_manager.get_applied_migrations()
        assert len(applied) == 0


class TestCreateMigrationManager:
    """测试 create_migration_manager 函数"""

    def test_create_migration_manager(self):
        """测试创建迁移管理器"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            manager = create_migration_manager(tmp.name)
            assert isinstance(manager, MigrationManager)
            assert manager.db_path == Path(tmp.name)
            Path(tmp.name).unlink(missing_ok=True)
