"""FastAPI 应用主入口

提供启动 FastAPI 应用的主函数和命令行接口.
"""

import sys
import logging
from pathlib import Path
from typing import Optional

# 必须在任何其他模块导入之前配置日志
# 这样所有模块的日志都会写入文件
def _setup_early_logging():
    """早期日志配置 - 检查命令行参数并配置日志"""
    # 检查是否提供了 --log-file 参数
    log_file = None
    log_level = "INFO"

    for i, arg in enumerate(sys.argv):
        if arg in ["--log-file", "-f"] and i + 1 < len(sys.argv):
            log_file = sys.argv[i + 1]
        elif arg.startswith("--log-file="):
            log_file = arg.split("=")[1]
        if arg in ["--log-level", "-l"] and i + 1 < len(sys.argv):
            log_level = sys.argv[i + 1]

    if not log_file:
        return

    # 清除所有现有的日志处理器
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # 配置根日志器
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 抑制第三方库的DEBUG日志，避免显示敏感数据（如base64）
    # 但保留INFO级别的重要信息（如HTTP请求结果）
    for logger_name in [
        "openai",
        "httpx",
        "httpcore",
        "urllib3",
    ]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)  # 只显示INFO及以上，不显示DEBUG

    # 创建文件处理器
    from logging.handlers import RotatingFileHandler
    log_path = Path(log_file).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )

    # 设置详细格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 禁用 uvicorn 的默认日志配置
    import uvicorn.config
    uvicorn.config.LOGGING_CONFIG = {}

    # 禁用 LoggerManager 的自动配置
    try:
        from src.shared.utils.logging import LoggerManager
        LoggerManager._configured = True
    except ImportError:
        pass

    print(f"[INFO] 已启用文件日志: {log_path}")


# 在任何导入之前配置日志
_setup_early_logging()

# 清除 _setup_early_logging 以避免污染命名空间
del _setup_early_logging

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

config = get_config()
logger = get_logger(__name__)
console = Console()

# 创建 CLI 应用
cli = typer.Typer(
    name="whitepaper-api",
    help="WhitePaper API 服务器",
    no_args_is_help=True,
)


def _display_startup_info(
    host: str,
    port: int,
    reload: bool,
    workers: int,
    log_level: str,
    env: str = "development",
):
    """显示启动信息"""
    table = Table(title="🚀 WhitePaper API 服务器", expand=True)

    table.add_row("环境", f"[bold]{env}[/bold]")
    table.add_row("地址", f"[bold]http://{host}:{port}[/bold]")
    table.add_row("重载", "启用" if reload else "禁用")
    table.add_row("工作进程", str(workers))
    table.add_row("日志级别", log_level)

    console.print(table)

    console.rule("📚 API 文档")
    console.print("   • Swagger UI: [link]http://localhost:8000/docs[/link]")
    console.print("   • ReDoc: [link]http://localhost:8000/redoc[/link]")
    console.print("   • OpenAPI: [link]http://localhost:8000/openapi.json[/link]")


@cli.command()
def stop(
    host: str = typer.Option(config.api.host, "--host", "-h", help="后端主机地址"),
    port: int = typer.Option(config.api.port, "--port", "-p", help="后端端口"),
    token: Optional[str] = typer.Option(
        None,
        "--token",
        help="关闭令牌(可选，对应环境变量 WHITEPAPER_SHUTDOWN_TOKEN)",
    ),
):
    """请求停止 API 服务器（开发/测试用）"""
    import requests

    url = f"http://{host}:{port}/__shutdown__"
    headers = {}
    if token:
        headers["x-shutdown-token"] = token

    try:
        resp = requests.post(url, headers=headers, timeout=5)
        if resp.status_code >= 400:
            console.print(f"[bold red]关闭失败: HTTP {resp.status_code}[/bold red]")
            console.print(resp.text)
            raise typer.Exit(1)
        console.print("[bold green]已发送关闭请求[/bold green]")
    except Exception as e:
        console.print(f"[bold red]发送关闭请求失败: {e!s}[/bold red]")
        raise typer.Exit(1) from e


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
        True,
        "--access-log/--no-access-log",
        help="是否启用访问日志",
    ),
    log_file: str = typer.Option(
        None,
        "--log-file", "-f",
        help="日志文件路径 (可选，启用后将同时输出到控制台和文件)",
    ),
):
    """启动 API 服务器"""

    # 显示启动信息
    _display_startup_info(host, port, reload, workers, log_level)

    # 环境检查
    if sys.platform == "win32" and workers > 1:
        import ctypes
        from ctypes import wintypes

        logger.warning(
            "Windows 环境下多进程 workers=%d 会触发 WinError 10022，已自动降级为单进程 (workers=1)",
            workers,
        )
        console.print(
            f"[bold yellow]Windows 环境下多进程模式可能不稳定,已降级为单进程[/bold yellow]"
        )
        workers = 1

    console.print("[bold green]✅ 服务器配置完成,正在启动...[/bold green]")

    # 导入 FastAPI 应用
    from src.interfaces.api.app import create_app

    app = create_app()

    # 启动服务器
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_level.lower(),
        access_log=access_log,
        log_config=None,  # 使用我们自己的日志配置
    )


if __name__ == "__main__":
    cli()
