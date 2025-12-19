# 生成命令: /speckit.implement T021
# 生成时间: 2025-12-09
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
WhitePaper CLI 主入口点

这是WhitePaper系统的命令行界面入口,提供对文档处理、知识库管理、
Agent编排等功能的命令行访问。
"""

import typer
from rich.console import Console
from rich.table import Table

from cli.base import BaseCLI
from src.interfaces.cli.agents import agents_app
from src.interfaces.cli.constraints import constraints_app
from src.interfaces.cli.documents import documents_app
from src.interfaces.cli.homepage import homepage_app
from src.interfaces.cli.knowledge_base import knowledge_base_app
from src.interfaces.cli.memory import memory_app
from src.interfaces.cli.prompts import prompts_app
from src.interfaces.cli.source_matching import source_matching_app
from src.interfaces.cli.templates import templates_app

# 创建Typer应用实例
app = typer.Typer(
    name="whitepaper",
    help="多Agent协作的文档处理与生成系统",
    rich_markup_mode="rich",
)

# 创建控制台实例
console = Console()

# 添加子应用
app.add_typer(documents_app, name="documents", help="文档管理和预处理")
app.add_typer(knowledge_base_app, name="knowledge-base", help="知识库管理和检索")
app.add_typer(agents_app, name="agents", help="Agent管理和编排")
app.add_typer(homepage_app, name="homepage", help="首页和智能检索")
app.add_typer(memory_app, name="memory", help="记忆系统管理")
app.add_typer(prompts_app, name="prompts", help="提示词工程")
app.add_typer(templates_app, name="templates", help="文档模板管理")
app.add_typer(constraints_app, name="constraints", help="规范条件设置")
app.add_typer(source_matching_app, name="source-matching", help="信息源排名与匹配")


def version_callback(*, value: bool) -> None:
    """显示版本信息的回调函数"""
    if value:
        console.print("WhitePaper version: 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        False,
        "--version",
        "-v",
        help="显示版本信息",
        callback=version_callback,
        is_eager=True,
        flag_value=True,
    ),
    verbose: bool | None = typer.Option(
        False,
        "--verbose",
        help="启用详细输出",
        flag_value=True,
    ),
    config: str | None = typer.Option(None, "--config", "-c", help="指定配置文件路径"),
) -> None:
    """
    WhitePaper - 多Agent协作的文档处理与生成系统

    这是一个基于LangChain 1.0的智能文档处理系统,支持:
    • 文档预处理与清洗
    • 多模式索引构建(向量、BM25、元数据、知识图谱)
    • 结构优化Agent
    • 信息源排名与匹配
    • 草稿生成与润色
    • 基于模板的格式文档生成
    • 记忆系统与自我学习
    """
    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)
        console.print("[bold green]详细模式已启用[/bold green]")

    if config:
        import os

        os.environ["WHITEPAPER_CONFIG"] = config
        console.print(f"[bold blue]使用配置文件: {config}[/bold blue]")


@app.command()
def status() -> None:
    """显示系统状态概览"""
    base_cli = BaseCLI()

    # 创建状态表格
    table = Table(title="WhitePaper 系统状态")
    table.add_column("组件", style="cyan", no_wrap=True)
    table.add_column("状态", style="magenta")
    table.add_column("描述", style="green")

    # 检查各组件状态
    components = [
        ("配置管理", base_cli.check_config_status(), "系统配置和LLM服务"),
        ("数据库", base_cli.check_database_status(), "SQLite数据库连接"),
        ("向量存储", base_cli.check_vector_store_status(), "Chroma向量数据库"),
        ("图存储", base_cli.check_graph_store_status(), "NetworkX图数据库"),
        ("任务队列", base_cli.check_task_queue_status(), "Arq异步任务队列"),
    ]

    for component, status, description in components:
        status_icon = "✅" if status == "正常" else "❌"
        table.add_row(component, f"{status_icon} {status}", description)

    console.print(table)


@app.command()
def info() -> None:
    """显示系统信息"""
    info_table = Table(title="系统信息")
    info_table.add_column("属性", style="cyan")
    info_table.add_column("值", style="green")

    info_table.add_row("版本", "0.1.0")
    info_table.add_row("描述", "多Agent协作的文档处理与生成系统")
    info_table.add_row("Python版本", "3.12+")
    info_table.add_row("核心框架", "LangChain 1.0")
    info_table.add_row("存储后端", "SQLite + Chroma + NetworkX")
    info_table.add_row("任务队列", "Arq")

    console.print(info_table)


@app.command()
def init(
    force: bool = typer.Option(
        "--force",
        "-f",
        help="强制重新初始化",
        flag_value=True,
    ),
    sample_data: bool = typer.Option(
        "--sample-data",
        help="初始化示例数据",
        flag_value=True,
    ),
) -> None:
    """初始化系统环境"""
    base_cli = BaseCLI()

    console.print("[bold blue]正在初始化WhitePaper系统...[/bold blue]")

    try:
        # 初始化配置
        if not base_cli.init_config(force=force):
            console.print("[bold red]配置初始化失败[/bold red]")
            raise typer.Exit(1)

        # 初始化数据库
        if not base_cli.init_database(force=force):
            console.print("[bold red]数据库初始化失败[/bold red]")
            raise typer.Exit(1)

        # 初始化存储
        if not base_cli.init_storage(force=force):
            console.print("[bold red]存储初始化失败[/bold red]")
            raise typer.Exit(1)

        # 初始化示例数据
        if sample_data and not base_cli.init_sample_data():
            console.print(
                "[bold yellow]示例数据初始化失败,但系统仍可使用[/bold yellow]"
            )

        console.print("[bold green]✅ WhitePaper系统初始化完成![/bold green]")
        console.print("\n[bold cyan]下一步操作:[/bold cyan]")
        console.print('1. 运行 "whitepaper status" 检查系统状态')
        console.print('2. 运行 "whitepaper documents --help" 查看文档管理命令')
        console.print('3. 运行 "whitepaper knowledge-base --help" 查看知识库管理命令')

    except Exception as e:
        console.print(f"[bold red]初始化失败: {e!s}[/bold red]")
        raise typer.Exit(1) from e


if __name__ == "__main__":
    app()
