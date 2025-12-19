"""FastAPI 应用主入口

提供启动 FastAPI 应用的主函数和命令行接口。
"""

import sys
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from src.shared.config.settings import get_config
from src.shared.utils.logging import get_logger

# 生成命令: /speckit.implement T019
# 生成时间: 2025-12-09
# 来源: specs/001-multi-agent-doc-system/tasks.md

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入应用

# 获取配置和日志器
config = get_config()
logger = get_logger(__name__)
console = Console()

# 创建 CLI 应用
cli = typer.Typer(
    name="whitepaper-api",
    help="WhitePaper API 服务器",
    no_args_is_help=True,
)


@cli.command()
def run(
    host: str = typer.Option(config.api.host, "--host", "-h", help="绑定的主机地址"),
    port: int = typer.Option(config.api.port, "--port", "-p", help="绑定的端口"),
    reload: bool = typer.Option(
        config.api.reload,
        "--reload",
        "-r",
        help="是否启用自动重载(开发模式)",
    ),
    workers: int = typer.Option(
        config.api.workers, "--workers", "-w", help="工作进程数"
    ),
    log_level: str = typer.Option(
        config.api.log_level, "--log-level", "-l", help="日志级别"
    ),
    access_log: bool = typer.Option(
        config.api.access_log,
        "--access-log/--no-access-log",
        help="是否启用访问日志",
    ),
):
    """启动 API 服务器"""

    # 显示启动信息
    _display_startup_info(host, port, reload, workers, log_level)

    # 配置 uvicorn
    use_reload = reload
    use_workers = workers if not reload else 1
    use_access_log = access_log
    use_colors = True

    if config.environment == "production":
        use_reload = False
        use_workers = max(workers, 2)
        use_access_log = True
        use_colors = False

    try:
        # 启动服务器
        logger.info("启动 WhitePaper API 服务器: http://%s:%s", host, port)
        uvicorn.run(
            app="src.interfaces.api.app:app",
            host=host,
            port=port,
            reload=use_reload,
            workers=use_workers,
            log_level=log_level.lower(),
            access_log=use_access_log,
            use_colors=use_colors,
            log_config=None,
        )
    except KeyboardInterrupt:
        logger.info("服务器已停止")
    except Exception as e:
        logger.error("服务器启动失败: %s", e)
        raise typer.Exit(1) from e


@cli.command()
def info():
    """显示应用信息"""

    table = Table(title="WhitePaper API 信息")
    table.add_column("配置项", style="cyan", no_wrap=True)
    table.add_column("值", style="green")

    table.add_row("版本", "0.1.0")
    table.add_row("环境", config.environment)
    table.add_row("调试模式", str(config.debug))
    table.add_row("主机", config.api.host)
    table.add_row("端口", str(config.api.port))
    table.add_row("工作进程数", str(config.api.workers))
    table.add_row("日志级别", config.api.log_level)
    table.add_row("数据目录", str(config.data_dir))
    table.add_row("存储目录", str(config.storage_dir))

    console.print(table)


def _display_startup_info(
    host: str,
    port: int,
    reload: bool,
    workers: int,
    log_level: str,
) -> None:
    """显示启动信息

    Args:
        host: 主机地址
        port: 端口
        reload: 是否启用重载
        workers: 工作进程数
        log_level: 日志级别
    """
    console.print("\n[bold blue]🚀 WhitePaper API 服务器[/bold blue]\n")

    table = Table(show_header=False, box=None)
    table.add_column("配置项", style="cyan")
    table.add_column("值", style="green")

    table.add_row("环境", config.environment)
    table.add_row("地址", f"http://{host}:{port}")
    table.add_row("重载", "启用" if reload else "禁用")
    table.add_row("工作进程", str(workers))
    table.add_row("日志级别", log_level)

    console.print(table)

    if config.environment == "development":
        console.print("\n[yellow]📚 API 文档:[/yellow]")
        console.print(f"   • Swagger UI: http://{host}:{port}/docs")
        console.print(f"   • ReDoc: http://{host}:{port}/redoc")
        console.print(f"   • OpenAPI: http://{host}:{port}/openapi.json")

    console.print("\n[green]✅ 服务器配置完成,正在启动...[/green]\n")


def main() -> None:
    """主入口函数"""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 再见![/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ 错误: {e}[/red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    main()
