# 生成命令: T015 数据库迁移脚本框架
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
数据库迁移工具模块

提供数据库迁移的核心功能,包括迁移版本管理,SQL执行,回滚等.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from structlog import get_logger

from src.shared.exceptions.storage_exceptions import SQLiteError

logger = get_logger()


class Migration:
    """迁移类

    表示单个数据库迁移操作.
    """

    def __init__(
        self,
        version: str,
        description: str,
        up_sql: str,
        down_sql: str | None = None,
        dependencies: list[str] | None = None,
    ):
        """初始化迁移

        Args:
            version: 迁移版本号(如 '001', '002')
            description: 迁移描述
            up_sql: 升级SQL语句
            down_sql: 回滚SQL语句(可选)
            dependencies: 依赖的迁移版本列表(可选)
        """
        self.version = version
        self.description = description
        self.up_sql = up_sql
        self.down_sql = down_sql
        self.dependencies = dependencies or []

        # 验证版本格式
        if not self._is_valid_version(version):
            msg = f"无效的迁移版本格式: {version}"
            raise ValueError(msg)

    def _is_valid_version(self, version: str) -> bool:
        """验证版本格式是否有效

        Args:
            version: 版本号

        Returns:
            是否有效
        """
        # 版本号应该是数字字符串,如 '001', '002'
        return version.isdigit() and len(version) >= 3

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式

        Returns:
            迁移信息字典
        """
        return {
            "version": self.version,
            "description": self.description,
            "dependencies": self.dependencies,
            "created_at": datetime.utcnow().isoformat(),
        }

    def __repr__(self) -> str:
        return f"Migration(version={self.version}, description={self.description})"


class MigrationManager:
    """迁移管理器

    管理数据库迁移的执行,版本控制和回滚.
    """

    def __init__(self, db_path: str | Path):
        """初始化迁移管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.migrations: dict[str, Migration] = {}
        self._ensure_db_directory()

        logger.info("迁移管理器初始化完成", db_path=str(self.db_path))

    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        db_dir = self.db_path.parent
        if not db_dir.exists():
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.info("创建数据库目录", directory=str(db_dir))

    def add_migration(self, migration: Migration):
        """添加迁移

        Args:
            migration: 迁移对象
        """
        if migration.version in self.migrations:
            msg = f"迁移版本已存在: {migration.version}"
            raise ValueError(msg)

        # 检查依赖是否存在
        for dep_version in migration.dependencies:
            if dep_version not in self.migrations:
                msg = f"依赖的迁移版本不存在: {dep_version}"
                raise ValueError(msg)

        self.migrations[migration.version] = migration
        logger.info(
            "添加迁移", version=migration.version, description=migration.description
        )

    def load_migrations_from_directory(self, migrations_dir: str | Path):
        """从目录加载迁移文件

        Args:
            migrations_dir: 迁移文件目录
        """
        migrations_path = Path(migrations_dir)
        if not migrations_path.exists():
            logger.warning("迁移目录不存在", directory=str(migrations_path))
            return

        # 查找所有迁移文件(格式:XXX_description.sql)
        migration_files = sorted(
            [
                f
                for f in migrations_path.glob("*.sql")
                if f.stem.split("_")[0].isdigit()
            ],
            key=lambda f: f.stem.split("_")[0],
        )

        for migration_file in migration_files:
            try:
                migration = self._load_migration_from_file(migration_file)
                self.add_migration(migration)
            except Exception as e:
                logger.error("加载迁移文件失败", file=str(migration_file), error=str(e))
                raise

    def _load_migration_from_file(self, migration_file: Path) -> Migration:
        """从文件加载迁移

        Args:
            migration_file: 迁移文件路径

        Returns:
            迁移对象
        """
        # 从文件名中提取版本号:XXX_description.sql -> XXX
        stem = migration_file.stem
        if "_" in stem:
            version = stem.split("_", 1)[0]
            description = stem.split("_", 1)[1]
        else:
            version = stem
            description = stem

        # 读取SQL内容
        content = migration_file.read_text(encoding="utf-8")

        # 分离升级和回滚SQL
        up_sql, down_sql = self._parse_migration_sql(content)

        return Migration(
            version=version, description=description, up_sql=up_sql, down_sql=down_sql
        )

    def _parse_migration_sql(self, content: str) -> tuple[str, str | None]:
        """解析迁移SQL内容

        Args:
            content: SQL文件内容

        Returns:
            (升级SQL, 回滚SQL) 元组
        """
        # 查找回滚SQL分隔符
        down_marker = "-- @down"
        if down_marker in content:
            parts = content.split(down_marker, 1)
            up_sql = parts[0].strip()
            down_sql = parts[1].strip()
        else:
            up_sql = content.strip()
            down_sql = None

        return up_sql, down_sql

    def _ensure_migration_table(self):
        """确保迁移记录表存在"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    applied_at TEXT NOT NULL,
                    execution_time_ms INTEGER,
                    checksum TEXT
                )
            """
            )

            # 创建依赖关系表
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_dependencies (
                    version TEXT,
                    dependency_version TEXT,
                    PRIMARY KEY (version, dependency_version),
                    FOREIGN KEY (version) REFERENCES schema_migrations(version),
                    FOREIGN KEY (dependency_version) REFERENCES schema_migrations(version)
                )
            """
            )

            conn.commit()

    def get_applied_migrations(self) -> list[str]:
        """获取已应用的迁移列表

        Returns:
            已应用的迁移版本列表
        """
        self._ensure_migration_table()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
            return [row[0] for row in cursor.fetchall()]

    def get_pending_migrations(self) -> list[Migration]:
        """获取待应用的迁移列表

        Returns:
            待应用的迁移对象列表
        """
        applied_versions = set(self.get_applied_migrations())
        pending_migrations = []

        for version in sorted(self.migrations.keys()):
            if version not in applied_versions:
                migration = self.migrations[version]

                # 检查依赖是否已应用
                dependencies_applied = all(
                    dep in applied_versions for dep in migration.dependencies
                )

                if dependencies_applied:
                    pending_migrations.append(migration)
                else:
                    logger.warning(
                        "迁移依赖未满足,跳过",
                        version=version,
                        dependencies=migration.dependencies,
                    )

        return pending_migrations

    def apply_migration(self, migration: Migration) -> bool:
        """应用单个迁移

        Args:
            migration: 要应用的迁移

        Returns:
            是否应用成功
        """
        logger.info(
            "开始应用迁移", version=migration.version, description=migration.description
        )

        start_time = datetime.utcnow()

        try:
            with sqlite3.connect(self.db_path) as conn:
                # 确保迁移表存在
                self._ensure_migration_table()

                # 开始事务
                conn.execute("BEGIN IMMEDIATE")

                try:
                    # 执行升级SQL
                    statements = self._split_sql_statements(migration.up_sql)
                    for statement in statements:
                        if statement.strip():
                            conn.execute(statement)

                    # 记录迁移
                    end_time = datetime.utcnow()
                    execution_time = int((end_time - start_time).total_seconds() * 1000)

                    conn.execute(
                        """
                        INSERT INTO schema_migrations
                        (version, description, applied_at, execution_time_ms, checksum)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            migration.version,
                            migration.description,
                            end_time.isoformat(),
                            execution_time,
                            self._calculate_checksum(migration.up_sql),
                        ),
                    )

                    # 记录依赖关系
                    for dep_version in migration.dependencies:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO migration_dependencies
                            (version, dependency_version)
                            VALUES (?, ?)
                            """,
                            (migration.version, dep_version),
                        )

                    conn.commit()

                    logger.info(
                        "迁移应用成功",
                        version=migration.version,
                        execution_time_ms=execution_time,
                    )
                    return True

                except Exception as e:
                    conn.rollback()
                    error_msg = f"应用迁移失败: {e}"
                    logger.error(error_msg, version=migration.version)
                    raise SQLiteError(error_msg) from e

        except Exception as e:
            logger.error("迁移执行异常", version=migration.version, error=str(e))
            raise

    def rollback_migration(self, migration: Migration) -> bool:
        """回滚单个迁移

        Args:
            migration: 要回滚的迁移

        Returns:
            是否回滚成功
        """
        if not migration.down_sql:
            logger.error("迁移不支持回滚", version=migration.version)
            return False

        logger.info(
            "开始回滚迁移", version=migration.version, description=migration.description
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                # 开始事务
                conn.execute("BEGIN IMMEDIATE")

                try:
                    # 执行回滚SQL
                    statements = self._split_sql_statements(migration.down_sql)
                    for statement in statements:
                        if statement.strip():
                            conn.execute(statement)

                    # 删除迁移记录
                    conn.execute(
                        "DELETE FROM schema_migrations WHERE version = ?",
                        (migration.version,),
                    )

                    # 删除依赖关系
                    conn.execute(
                        "DELETE FROM migration_dependencies WHERE version = ?",
                        (migration.version,),
                    )

                    conn.commit()

                    logger.info("迁移回滚成功", version=migration.version)
                    return True

                except Exception as e:
                    conn.rollback()
                    error_msg = f"回滚迁移失败: {e}"
                    logger.error(error_msg, version=migration.version)
                    raise SQLiteError(error_msg) from e

        except Exception as e:
            logger.error("迁移回滚异常", version=migration.version, error=str(e))
            raise

    def apply_pending_migrations(self) -> list[str]:
        """应用所有待应用的迁移

        Returns:
            成功应用的迁移版本列表
        """
        pending_migrations = self.get_pending_migrations()

        if not pending_migrations:
            logger.info("没有待应用的迁移")
            return []

        logger.info("开始应用待应用的迁移", count=len(pending_migrations))

        applied_versions = []
        for migration in pending_migrations:
            try:
                if self.apply_migration(migration):
                    applied_versions.append(migration.version)
            except Exception as e:
                logger.error(
                    "应用迁移失败,停止后续迁移",
                    version=migration.version,
                    error=str(e),
                )
                break

        logger.info("迁移应用完成", applied_count=len(applied_versions))
        return applied_versions

    def get_migration_status(self) -> dict[str, Any]:
        """获取迁移状态

        Returns:
            迁移状态信息
        """
        applied_versions = self.get_applied_migrations()
        pending_migrations = self.get_pending_migrations()

        return {
            "total_migrations": len(self.migrations),
            "applied_count": len(applied_versions),
            "pending_count": len(pending_migrations),
            "applied_versions": applied_versions,
            "pending_versions": [m.version for m in pending_migrations],
            "database_path": str(self.db_path),
        }

    def _split_sql_statements(self, sql: str) -> list[str]:
        """分割SQL语句

        Args:
            sql: SQL内容

        Returns:
            SQL语句列表
        """
        # 简单的SQL语句分割,按分号分割
        # 注意:这是一个简化实现,实际项目中可能需要更复杂的解析
        statements = []
        current_statement = ""

        for line in sql.split("\n"):
            line = line.strip()

            # 跳过空行和注释
            if not line or line.startswith("--"):
                continue

            current_statement += line + "\n"

            # 如果行以分号结尾,表示语句结束
            if line.endswith(";"):
                statements.append(current_statement.strip())
                current_statement = ""

        # 添加最后一个语句(如果没有以分号结尾)
        if current_statement.strip():
            statements.append(current_statement.strip())

        return statements

    def _calculate_checksum(self, sql: str) -> str:
        """计算SQL内容的校验和

        Args:
            sql: SQL内容

        Returns:
            校验和字符串
        """
        import hashlib

        return hashlib.sha256(sql.encode("utf-8")).hexdigest()

    def export_migration_plan(self, output_path: str | Path):
        """导出迁移计划

        Args:
            output_path: 输出文件路径
        """
        applied_versions = set(self.get_applied_migrations())

        plan = {
            "database_path": str(self.db_path),
            "generated_at": datetime.utcnow().isoformat(),
            "migrations": [],
        }

        for version in sorted(self.migrations.keys()):
            migration = self.migrations[version]
            plan["migrations"].append(
                {
                    "version": migration.version,
                    "description": migration.description,
                    "dependencies": migration.dependencies,
                    "applied": version in applied_versions,
                }
            )

        output_file = Path(output_path)
        output_file.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        logger.info("迁移计划导出完成", output_path=str(output_file))


def create_migration_manager(db_path: str | Path) -> MigrationManager:
    """创建迁移管理器实例

    Args:
        db_path: 数据库文件路径

    Returns:
        迁移管理器实例
    """
    return MigrationManager(db_path)
