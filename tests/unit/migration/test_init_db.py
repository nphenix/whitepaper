# 生成命令: T015 数据库迁移脚本框架
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
初始化脚本测试

测试 init_db.py 命令行工具的功能。
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scripts.migration.init_db import app, get_default_db_path


class TestGetDefaultDbPath:
    """测试获取默认数据库路径"""

    @patch("scripts.migration.init_db.get_config")
    def test_get_default_db_path(self, mock_get_config):
        """测试获取默认数据库路径"""
        mock_config = MagicMock()
        mock_config.database.sqlite_db_path = Path("./test.db")
        mock_get_config.return_value = mock_config

        result = get_default_db_path()

        assert result == Path("./test.db")
        mock_get_config.assert_called_once()


class TestInitCommand:
    """测试 init 命令"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            yield tmp.name
        # 清理临时文件
        Path(tmp.name).unlink(missing_ok=True)

    @pytest.fixture
    def temp_migrations_dir(self):
        """创建临时迁移目录"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 创建一个测试迁移文件
            migration_file = Path(tmp_dir) / "001_test.sql"
            migration_file.write_text("""
-- Migration: Test Migration
-- Version: 001

-- @up
CREATE TABLE test_table (id INTEGER PRIMARY KEY);

-- @down
DROP TABLE test_table;
            """)
            yield tmp_dir

    def test_init_success(self, runner, temp_db_path, temp_migrations_dir):
        """测试成功的初始化"""
        result = runner.invoke(
            app,
            [
                "init",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 0
        assert "数据库初始化成功完成" in result.stdout
        assert Path(temp_db_path).exists()

    def test_init_with_existing_db(self, runner, temp_db_path, temp_migrations_dir):
        """测试数据库已存在的情况"""
        # 先创建数据库文件
        Path(temp_db_path).touch()

        result = runner.invoke(
            app,
            [
                "init",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 1
        assert "数据库文件已存在" in result.stdout

    def test_init_force(self, runner, temp_db_path, temp_migrations_dir):
        """测试强制初始化"""
        # 先创建数据库文件
        Path(temp_db_path).touch()

        result = runner.invoke(
            app,
            [
                "init",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
                "--force",
            ],
        )

        assert result.exit_code == 0
        assert "数据库初始化成功完成" in result.stdout

    def test_init_no_migrations_dir(self, runner, temp_db_path):
        """测试迁移目录不存在的情况"""
        non_existent_dir = "/tmp/non_existent_migrations"

        result = runner.invoke(
            app,
            ["init", "--db-path", temp_db_path, "--migrations-dir", non_existent_dir],
        )

        assert result.exit_code == 0
        assert "迁移目录不存在" in result.stdout
        assert "将创建空的数据库" in result.stdout

    @patch("scripts.migration.init_db.get_config")
    def test_init_with_defaults(self, mock_get_config, runner, temp_migrations_dir):
        """测试使用默认参数的初始化"""
        mock_config = MagicMock()
        mock_config.database.sqlite_db_path = Path("./default_test.db")
        mock_get_config.return_value = mock_config

        result = runner.invoke(app, ["init", "--migrations-dir", temp_migrations_dir])

        assert result.exit_code == 0
        assert "数据库初始化成功完成" in result.stdout
        assert Path("./default_test.db").exists()

        # 清理
        Path("./default_test.db").unlink(missing_ok=True)


class TestMigrateCommand:
    """测试 migrate 命令"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    @pytest.fixture
    def setup_database(self, runner, temp_db_path, temp_migrations_dir):
        """设置初始数据库"""
        # 先初始化数据库
        runner.invoke(
            app,
            [
                "init",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        # 创建一个新的迁移文件
        new_migration = Path(temp_migrations_dir) / "002_new_table.sql"
        new_migration.write_text("""
-- Migration: Add New Table
-- Version: 002

-- @up
CREATE TABLE new_table (id INTEGER PRIMARY KEY, name TEXT);

-- @down
DROP TABLE new_table;
        """)

        return temp_db_path, temp_migrations_dir

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            yield tmp.name
        # 清理临时文件
        Path(tmp.name).unlink(missing_ok=True)

    @pytest.fixture
    def temp_migrations_dir(self):
        """创建临时迁移目录"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 创建一个测试迁移文件
            migration_file = Path(tmp_dir) / "001_test.sql"
            migration_file.write_text("""
-- Migration: Test Migration
-- Version: 001

-- @up
CREATE TABLE test_table (id INTEGER PRIMARY KEY);

-- @down
DROP TABLE test_table;
            """)
            yield tmp_dir

    def test_migrate_success(self, runner, setup_database):
        """测试成功的迁移"""
        temp_db_path, temp_migrations_dir = setup_database

        result = runner.invoke(
            app,
            [
                "migrate",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 0
        assert "数据库迁移成功完成" in result.stdout
        assert "成功应用 1 个迁移" in result.stdout

    def test_migrate_no_pending(self, runner, setup_database):
        """测试没有待应用迁移的情况"""
        temp_db_path, temp_migrations_dir = setup_database

        # 先应用一次迁移
        runner.invoke(
            app,
            [
                "migrate",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        # 再次迁移应该没有待应用的迁移
        result = runner.invoke(
            app,
            [
                "migrate",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 0
        assert "数据库已是最新状态" in result.stdout

    def test_migrate_no_database(self, runner, temp_migrations_dir):
        """测试数据库不存在的情况"""
        non_existent_db = "/tmp/non_existent.db"

        result = runner.invoke(
            app,
            [
                "migrate",
                "--db-path",
                non_existent_db,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 1
        assert "数据库文件不存在" in result.stdout


class TestRollbackCommand:
    """测试 rollback 命令"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            yield tmp.name
        # 清理临时文件
        Path(tmp.name).unlink(missing_ok=True)

    @pytest.fixture
    def temp_migrations_dir(self):
        """创建临时迁移目录"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 创建测试迁移文件
            migration_file = Path(tmp_dir) / "001_test.sql"
            migration_file.write_text("""
-- Migration: Test Migration
-- Version: 001

-- @up
CREATE TABLE test_table (id INTEGER PRIMARY KEY);

-- @down
DROP TABLE test_table;
            """)
            yield tmp_dir

    def test_rollback_success(self, runner, temp_db_path, temp_migrations_dir):
        """测试成功的回滚"""
        # 先初始化数据库
        runner.invoke(
            app,
            [
                "init",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        # 模拟用户确认
        with patch("typer.confirm", return_value=True):
            result = runner.invoke(
                app,
                [
                    "rollback",
                    "000",  # 回滚到不存在的版本
                    "--db-path",
                    temp_db_path,
                    "--migrations-dir",
                    temp_migrations_dir,
                ],
            )

        # 应该失败,因为目标版本不存在
        assert result.exit_code == 1

    def test_rollback_target_version_not_applied(
        self, runner, temp_db_path, temp_migrations_dir
    ):
        """测试回滚到未应用的版本"""
        # 先初始化数据库
        runner.invoke(
            app,
            [
                "init",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        result = runner.invoke(
            app,
            [
                "rollback",
                "002",  # 不存在的版本
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 1
        assert "目标版本 002 未在数据库中应用" in result.stdout


class TestStatusCommand:
    """测试 status 命令"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            yield tmp.name
        # 清理临时文件
        Path(tmp.name).unlink(missing_ok=True)

    @pytest.fixture
    def temp_migrations_dir(self):
        """创建临时迁移目录"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 创建测试迁移文件
            migration_file = Path(tmp_dir) / "001_test.sql"
            migration_file.write_text("""
-- Migration: Test Migration
-- Version: 001

-- @up
CREATE TABLE test_table (id INTEGER PRIMARY KEY);

-- @down
DROP TABLE test_table;
            """)
            yield tmp_dir

    def test_status_with_database(self, runner, temp_db_path, temp_migrations_dir):
        """测试显示数据库状态"""
        # 先初始化数据库
        runner.invoke(
            app,
            [
                "init",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        result = runner.invoke(
            app,
            [
                "status",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 0
        assert "数据库迁移状态" in result.stdout
        assert "迁移状态" in result.stdout

    def test_status_no_database(self, runner, temp_migrations_dir):
        """测试数据库不存在时的状态"""
        non_existent_db = "/tmp/non_existent.db"

        result = runner.invoke(
            app,
            [
                "status",
                "--db-path",
                non_existent_db,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 0
        assert "数据库文件不存在" in result.stdout


class TestCreateMigrationCommand:
    """测试 create-migration 命令"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    @pytest.fixture
    def temp_migrations_dir(self):
        """创建临时迁移目录"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield tmp_dir

    def test_create_migration_success(self, runner, temp_migrations_dir):
        """测试成功创建迁移文件"""
        result = runner.invoke(
            app,
            [
                "create-migration",
                "Add User Profile Table",
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 0
        assert "迁移文件已创建" in result.stdout
        assert "版本号: 001" in result.stdout

        # 检查文件是否创建
        migration_file = Path(temp_migrations_dir) / "001_add_user_profile_table.sql"
        assert migration_file.exists()

        # 检查文件内容
        content = migration_file.read_text()
        assert "Add User Profile Table" in content
        assert "-- @up" in content
        assert "-- @down" in content

    def test_create_migration_with_existing_files(self, runner, temp_migrations_dir):
        """测试在已有迁移文件的情况下创建新迁移"""
        # 先创建一个迁移文件
        existing_file = Path(temp_migrations_dir) / "001_existing.sql"
        existing_file.write_text("-- Existing migration")

        result = runner.invoke(
            app,
            [
                "create-migration",
                "New Migration",
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 0
        assert "版本号: 002" in result.stdout

        # 检查新文件是否创建
        new_file = Path(temp_migrations_dir) / "002_new_migration.sql"
        assert new_file.exists()


class TestExportPlanCommand:
    """测试 export-plan 命令"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    @pytest.fixture
    def temp_db_path(self):
        """创建临时数据库路径"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            yield tmp.name
        # 清理临时文件
        Path(tmp.name).unlink(missing_ok=True)

    @pytest.fixture
    def temp_migrations_dir(self):
        """创建临时迁移目录"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 创建测试迁移文件
            migration_file = Path(tmp_dir) / "001_test.sql"
            migration_file.write_text("""
-- Migration: Test Migration
-- Version: 001

-- @up
CREATE TABLE test_table (id INTEGER PRIMARY KEY);

-- @down
DROP TABLE test_table;
            """)
            yield tmp_dir

    @pytest.fixture
    def temp_output_file(self):
        """创建临时输出文件"""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            yield tmp.name
        # 清理临时文件
        Path(tmp.name).unlink(missing_ok=True)

    def test_export_plan_success(
        self, runner, temp_db_path, temp_migrations_dir, temp_output_file
    ):
        """测试成功导出迁移计划"""
        # 先初始化数据库
        runner.invoke(
            app,
            [
                "init",
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        result = runner.invoke(
            app,
            [
                "export-plan",
                temp_output_file,
                "--db-path",
                temp_db_path,
                "--migrations-dir",
                temp_migrations_dir,
            ],
        )

        assert result.exit_code == 0
        assert "迁移计划已导出" in result.stdout

        # 检查输出文件
        output_path = Path(temp_output_file)
        assert output_path.exists()

        # 检查JSON内容
        with open(output_path) as f:
            plan = json.load(f)

        assert "migrations" in plan
        assert "database_path" in plan
        assert "generated_at" in plan
