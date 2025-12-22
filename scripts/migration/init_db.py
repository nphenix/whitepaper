# 生成命令: T015 数据库迁移脚本框架
# 生成时间: 2025-12-08
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
数据库初始化脚本

用于初始化数据库结构和管理数据库迁移。
"""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from migration_utils import create_migration_manager

# 初始化 Rich Console
console = Console()

# 创建 Typer 应用
app = typer.Typer(
    name="init_db",
    help="数据库初始化和迁移管理工具",
    no_args_is_help=True,
)


def get_default_db_path() -> Path:
    """获取默认数据库路径

    Returns:
        默认数据库文件路径
    """
    from src.shared.config.settings import get_config

    config = get_config()
    return config.database.sqlite_db_path


@app.command()
def init(
    db_path: str | None = typer.Option(
        None, "--db-path", "-d", help="数据库文件路径(默认使用配置文件中的路径)"
    ),
    migrations_dir: str | None = typer.Option(
        None,
        "--migrations-dir",
        "-m",
        help="迁移文件目录(默认为 scripts/migration/migrations)",
    ),
    force: bool = typer.Option(
        "--force",
        "-f",
        help="强制初始化,即使数据库已存在",
        flag_value=True,
    ),
):
    """初始化数据库

    创建数据库结构并应用所有迁移。
    """
    # 设置默认路径
    if db_path is None:
        db_path = str(get_default_db_path())

    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"

    db_file = Path(db_path)
    migrations_path = Path(migrations_dir)

    console.print("[bold blue]初始化数据库[/bold blue]")
    console.print(f"数据库路径: {db_file}")
    console.print(f"迁移目录: {migrations_path}")

    # 检查数据库是否已存在
    if db_file.exists() and not force:
        console.print(f"[yellow]数据库文件已存在: {db_file}[/yellow]")
        console.print("使用 --force 选项强制重新初始化")
        raise typer.Exit(1)

    try:
        # 创建迁移管理器
        manager = create_migration_manager(db_file)

        # 加载迁移文件
        if migrations_path.exists():
            manager.load_migrations_from_directory(migrations_path)
            console.print(f"[green]已加载 {len(manager.migrations)} 个迁移文件[/green]")
        else:
            console.print(f"[yellow]迁移目录不存在: {migrations_path}[/yellow]")
            console.print("将创建空的数据库")

        # 应用迁移
        applied_versions = manager.apply_pending_migrations()

        if applied_versions:
            console.print(f"[green]成功应用 {len(applied_versions)} 个迁移:[/green]")
            for version in applied_versions:
                migration = manager.migrations[version]
                console.print(f"  - {version}: {migration.description}")
        else:
            console.print("[green]数据库初始化完成(无迁移需要应用)[/green]")

        # 显示状态
        status = manager.get_migration_status()
        console.print("\n[bold]数据库状态:[/bold]")
        console.print(f"总迁移数: {status['total_migrations']}")
        console.print(f"已应用: {status['applied_count']}")
        console.print(f"待应用: {status['pending_count']}")

        console.print("\n[green]✓ 数据库初始化成功完成[/green]")

    except Exception as e:
        console.print(f"[red]✗ 数据库初始化失败: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def migrate(
    db_path: str | None = typer.Option(
        None, "--db-path", "-d", help="数据库文件路径(默认使用配置文件中的路径)"
    ),
    migrations_dir: str | None = typer.Option(
        None,
        "--migrations-dir",
        "-m",
        help="迁移文件目录(默认为 scripts/migration/migrations)",
    ),
    target_version: str | None = typer.Option(
        None, "--target", "-t", help="目标迁移版本(默认应用所有待应用迁移)"
    ),
):
    """应用数据库迁移

    将数据库升级到最新版本或指定版本。
    """
    # 设置默认路径
    if db_path is None:
        db_path = str(get_default_db_path())

    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"

    db_file = Path(db_path)
    migrations_path = Path(migrations_dir)

    console.print("[bold blue]应用数据库迁移[/bold blue]")
    console.print(f"数据库路径: {db_file}")
    console.print(f"迁移目录: {migrations_path}")

    # 检查数据库是否存在
    if not db_file.exists():
        console.print(f"[red]数据库文件不存在: {db_file}[/red]")
        console.print('请先运行 "init" 命令初始化数据库')
        raise typer.Exit(1)

    try:
        # 创建迁移管理器
        manager = create_migration_manager(db_file)

        # 加载迁移文件
        if migrations_path.exists():
            manager.load_migrations_from_directory(migrations_path)
            console.print(f"[green]已加载 {len(manager.migrations)} 个迁移文件[/green]")
        else:
            console.print(f"[yellow]迁移目录不存在: {migrations_path}[/yellow]")
            console.print("没有可应用的迁移")
            return

        # 获取当前状态
        status_before = manager.get_migration_status()
        console.print("\n[bold]迁移前状态:[/bold]")
        console.print(f"总迁移数: {status_before['total_migrations']}")
        console.print(f"已应用: {status_before['applied_count']}")
        console.print(f"待应用: {status_before['pending_count']}")

        if status_before["pending_count"] == 0:
            console.print("[green]数据库已是最新状态,无需迁移[/green]")
            return

        # 应用迁移
        applied_versions = manager.apply_pending_migrations()

        if applied_versions:
            console.print(f"\n[green]成功应用 {len(applied_versions)} 个迁移:[/green]")
            for version in applied_versions:
                migration = manager.migrations[version]
                console.print(f"  - {version}: {migration.description}")

        # 显示迁移后状态
        status_after = manager.get_migration_status()
        console.print("\n[bold]迁移后状态:[/bold]")
        console.print(f"总迁移数: {status_after['total_migrations']}")
        console.print(f"已应用: {status_after['applied_count']}")
        console.print(f"待应用: {status_after['pending_count']}")

        console.print("\n[green]✓ 数据库迁移成功完成[/green]")

    except Exception as e:
        console.print(f"[red]✗ 数据库迁移失败: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def rollback(
    version: str = typer.Argument(..., help="要回滚到的迁移版本"),
    db_path: str | None = typer.Option(
        None, "--db-path", "-d", help="数据库文件路径(默认使用配置文件中的路径)"
    ),
    migrations_dir: str | None = typer.Option(
        None,
        "--migrations-dir",
        "-m",
        help="迁移文件目录(默认为 scripts/migration/migrations)",
    ),
):
    """回滚数据库迁移

    将数据库回滚到指定版本。
    """
    # 设置默认路径
    if db_path is None:
        db_path = str(get_default_db_path())

    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"

    db_file = Path(db_path)
    migrations_path = Path(migrations_dir)

    console.print("[bold blue]回滚数据库迁移[/bold blue]")
    console.print(f"数据库路径: {db_file}")
    console.print(f"目标版本: {version}")
    console.print(f"迁移目录: {migrations_path}")

    # 检查数据库是否存在
    if not db_file.exists():
        console.print(f"[red]数据库文件不存在: {db_file}[/red]")
        raise typer.Exit(1)

    try:
        # 创建迁移管理器
        manager = create_migration_manager(db_file)

        # 加载迁移文件
        if migrations_path.exists():
            manager.load_migrations_from_directory(migrations_path)
            console.print(f"[green]已加载 {len(manager.migrations)} 个迁移文件[/green]")
        else:
            console.print(f"[red]迁移目录不存在: {migrations_path}[/red]")
            raise typer.Exit(1)

        # 获取已应用的迁移
        applied_versions = manager.get_applied_migrations()

        if version not in applied_versions:
            console.print(f"[red]目标版本 {version} 未在数据库中应用[/red]")
            raise typer.Exit(1)

        # 找到需要回滚的迁移(倒序)
        to_rollback = []
        for v in reversed(applied_versions):
            if v == version:
                break
            to_rollback.append(v)

        if not to_rollback:
            console.print(f"[green]数据库已在版本 {version},无需回滚[/green]")
            return

        console.print(f"[yellow]将要回滚 {len(to_rollback)} 个迁移:[/yellow]")
        for v in to_rollback:
            migration = manager.migrations.get(v)
            if migration:
                console.print(f"  - {v}: {migration.description}")
            else:
                console.print(f"  - {v}: (迁移文件未找到)")

        # 执行回滚
        console.print("\n[yellow]警告: 回滚将导致数据丢失,请确认操作[/yellow]")
        confirm = typer.confirm("确认要继续回滚吗?", default=False)

        if not confirm:
            console.print("[yellow]回滚操作已取消[/yellow]")
            raise typer.Exit(0)

        # 按顺序回滚
        rolled_back = []
        for v in to_rollback:
            migration = manager.migrations.get(v)
            if migration and manager.rollback_migration(migration):
                rolled_back.append(v)
                console.print(f"[green]✓ 已回滚 {v}: {migration.description}[/green]")
            else:
                console.print(f"[red]✗ 回滚失败 {v}[/red]")
                break

        if rolled_back:
            console.print(f"\n[green]✓ 成功回滚 {len(rolled_back)} 个迁移[/green]")
        else:
            console.print("\n[red]✗ 没有迁移被回滚[/red]")
            raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]✗ 数据库回滚失败: {e}[/red]")
        raise typer.Exit(1) from e


@app.command()
def status(
    db_path: str | None = typer.Option(
        None, "--db-path", "-d", help="数据库文件路径(默认使用配置文件中的路径)"
    ),
    migrations_dir: str | None = typer.Option(
        None,
        "--migrations-dir",
        "-m",
        help="迁移文件目录(默认为 scripts/migration/migrations)",
    ),
):
    """显示数据库迁移状态

    查看当前数据库的迁移状态和待应用的迁移。
    """
    # 设置默认路径
    if db_path is None:
        db_path = str(get_default_db_path())

    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"

    db_file = Path(db_path)
    migrations_path = Path(migrations_dir)

    console.print("[bold blue]数据库迁移状态[/bold blue]")
    console.print(f"数据库路径: {db_file}")
    console.print(f"迁移目录: {migrations_path}")

    # 检查数据库是否存在
    if not db_file.exists():
        console.print(f"[red]数据库文件不存在: {db_file}[/red]")
        console.print('请先运行 "init" 命令初始化数据库')
        return

    try:
        # 创建迁移管理器
        manager = create_migration_manager(db_file)

        # 加载迁移文件
        if migrations_path.exists():
            manager.load_migrations_from_directory(migrations_path)
            console.print(f"[green]已加载 {len(manager.migrations)} 个迁移文件[/green]")
        else:
            console.print(f"[yellow]迁移目录不存在: {migrations_path}[/yellow]")
            return

        # 获取状态
        status = manager.get_migration_status()
        applied_versions = set(status["applied_versions"])

        # 创建状态表格
        table = Table(title="迁移状态")
        table.add_column("版本", style="cyan", no_wrap=True)
        table.add_column("描述", style="magenta")
        table.add_column("状态", style="green")
        table.add_column("依赖", style="yellow")

        for version in sorted(manager.migrations.keys()):
            migration = manager.migrations[version]
            status_text = "✓ 已应用" if version in applied_versions else "○ 待应用"
            status_style = "green" if version in applied_versions else "yellow"
            dependencies = (
                ", ".join(migration.dependencies) if migration.dependencies else "-"
            )

            table.add_row(
                version,
                migration.description,
                f"[{status_style}]{status_text}[/{status_style}]",
                dependencies,
            )

        console.print(table)

        # 显示统计信息
        console.print("\n[bold]统计信息:[/bold]")
        console.print(f"总迁移数: {status['total_migrations']}")
        console.print(f"已应用: {status['applied_count']}")
        console.print(f"待应用: {status['pending_count']}")

    except Exception as e:
        console.print(f"[red]✗ 获取状态失败: {e}[/red]")


@app.command()
def create_migration(
    name: str = typer.Argument(..., help="迁移名称(描述性)"),
    migrations_dir: str | None = typer.Option(
        None,
        "--migrations-dir",
        "-m",
        help="迁移文件目录(默认为 scripts/migration/migrations)",
    ),
):
    """创建新的迁移文件

    生成一个新的迁移文件模板。
    """
    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"

    migrations_path = Path(migrations_dir)

    console.print("[bold blue]创建迁移文件[/bold blue]")
    console.print(f"迁移名称: {name}")
    console.print(f"迁移目录: {migrations_path}")

    # 确保迁移目录存在
    migrations_path.mkdir(parents=True, exist_ok=True)

    # 获取下一个版本号
    existing_files = list(migrations_path.glob("*.sql"))
    version_numbers = []
    for f in existing_files:
        stem = f.stem
        version_part = stem.split("_", 1)[0] if "_" in stem else stem

        if version_part.isdigit():
            version_numbers.append(int(version_part))

    next_version = max(version_numbers) + 1 if version_numbers else 1

    version_str = f"{next_version:03d}"
    filename = f"{version_str}_{name.replace(' ', '_').lower()}.sql"
    filepath = migrations_path / filename

    # 生成迁移文件模板
    template = f"""-- Migration: {name}
-- Version: {version_str}
-- Created: N/A

-- @up
-- 在此处添加升级SQL语句
-- 例如:
-- CREATE TABLE example_table (
--     id INTEGER PRIMARY KEY AUTOINCREMENT,
--     name TEXT NOT NULL,
--     created_at TEXT DEFAULT CURRENT_TIMESTAMP
-- );

-- @down
-- 在此处添加回滚SQL语句(可选)
-- 例如:
-- DROP TABLE IF EXISTS example_table;
"""

    filepath.write_text(template, encoding="utf-8")

    console.print(f"[green]✓ 迁移文件已创建: {filepath}[/green]")
    console.print(f"版本号: {version_str}")
    console.print("请编辑文件添加具体的SQL语句")


@app.command()
def export_plan(
    output_file: str = typer.Argument(..., help="输出文件路径"),
    db_path: str | None = typer.Option(
        None, "--db-path", "-d", help="数据库文件路径(默认使用配置文件中的路径)"
    ),
    migrations_dir: str | None = typer.Option(
        None,
        "--migrations-dir",
        "-m",
        help="迁移文件目录(默认为 scripts/migration/migrations)",
    ),
):
    """导出迁移计划

    将当前迁移状态导出为JSON文件。
    """
    # 设置默认路径
    if db_path is None:
        db_path = str(get_default_db_path())

    if migrations_dir is None:
        migrations_dir = Path(__file__).parent / "migrations"

    db_file = Path(db_path)
    migrations_path = Path(migrations_dir)
    output_path = Path(output_file)

    console.print("[bold blue]导出迁移计划[/bold blue]")
    console.print(f"数据库路径: {db_file}")
    console.print(f"迁移目录: {migrations_path}")
    console.print(f"输出文件: {output_path}")

    try:
        # 创建迁移管理器
        manager = create_migration_manager(db_file)

        # 加载迁移文件
        if migrations_path.exists():
            manager.load_migrations_from_directory(migrations_path)

        # 导出计划
        manager.export_migration_plan(output_path)

        console.print(f"[green]✓ 迁移计划已导出: {output_path}[/green]")

    except Exception as e:
        console.print(f"[red]✗ 导出失败: {e}[/red]")
        raise typer.Exit(1) from e


def main():
    """主函数"""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]操作已取消[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]发生未预期的错误: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
