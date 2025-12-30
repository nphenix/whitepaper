# 生成命令: /speckit.implement T021
# 生成时间: 2025-12-09
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
WhitePaper CLI 基础类

提供CLI应用的通用功能和工具方法,包括:
- 系统状态检查
- 配置管理
- 数据库初始化
- 存储管理
- 通用工具函数
"""

import asyncio
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from src.infrastructure.storage.chroma.connection import ChromaConnectionManager
from src.infrastructure.storage.networkx.graph_manager import NetworkXGraphManager
from src.infrastructure.storage.sqlite.connection import SQLiteConnectionManager
from src.shared.config.settings import AppConfig, get_config
from src.shared.utils.logging import get_logger

console = Console()
logger = get_logger(__name__)


class BaseCLI:
    """CLI基础类,提供通用功能和方法"""

    def __init__(self) -> None:
        """初始化基础CLI"""
        self.settings: AppConfig | None = None
        self._load_settings()

    def _load_settings(self) -> None:
        """加载配置设置"""
        try:
            self.settings = get_config()
        except Exception as e:
            console.print(f"[bold red]配置加载失败: {e!s}[/bold red]")
            logger.error("配置加载失败: %s", e)

    def check_config_status(self) -> str:
        """检查配置状态"""
        if not self.settings:
            return "未加载"

        try:
            # 检查必要的配置项
            if not self.settings.llm_provider:
                return "缺少llm_provider"
            if not self.settings.embedding.provider:
                return "缺少embedding_provider"
            if not self.settings.database.sqlite_db_path:
                return "缺少database配置"

            return "正常"
        except Exception:
            return "异常"

    def check_database_status(self) -> str:
        """检查数据库状态"""
        try:
            if not self.settings:
                return "配置未加载"

            connection_manager = SQLiteConnectionManager(
                database_path=self.settings.database.sqlite_db_path
            )

            # 尝试连接数据库
            with connection_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return "正常"
        except Exception as e:
            logger.error("数据库状态检查失败: %s", e)
            return f"异常: {str(e)[:50]}"

    def check_vector_store_status(self) -> str:
        """检查向量存储状态"""
        try:
            if not self.settings:
                return "配置未加载"

            connection_manager = ChromaConnectionManager(
                db_path=self.settings.database.chroma_db_path,
                persist_directory=self.settings.database.chroma_db_path,
            )

            # 尝试连接Chroma
            connection_manager._get_sync_client()
            return "正常"
        except Exception as e:
            logger.error("向量存储状态检查失败: %s", e)
            return f"异常: {str(e)[:50]}"

    def check_graph_store_status(self) -> str:
        """检查图存储状态"""
        try:
            if not self.settings:
                return "配置未加载"

            graph_manager = NetworkXGraphManager(
                data_directory=self.settings.database.networkx_data_directory
            )

            # 尝试加载图
            with graph_manager.get_graph() as graph:
                if graph is not None:
                    return "正常"
                else:
                    return "无数据"
        except Exception as e:
            logger.error("图存储状态检查失败: %s", e)
            return f"异常: {str(e)[:50]}"

    def check_task_queue_status(self) -> str:
        """检查任务队列状态"""
        try:
            if not self.settings:
                return "配置未加载"

            # 检查Redis连接
            import redis

            r = redis.Redis(
                host=self.settings.redis.redis_host,
                port=self.settings.redis.redis_port,
                db=self.settings.redis.redis_db,
                password=self.settings.redis.redis_password,
                decode_responses=True,
            )

            if r.ping():
                return "正常"
            else:
                return "连接失败"
        except Exception as e:
            logger.error("任务队列状态检查失败: %s", e)
            return f"异常: {str(e)[:50]}"

    def init_config(self, *, force: bool = False) -> bool:
        """初始化配置"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("初始化配置...", total=None)

                # 检查配置文件是否存在
                config_file = Path(".env")
                if config_file.exists() and not force:
                    progress.update(task, description="配置文件已存在")
                    console.print(
                        "[bold yellow]配置文件已存在,使用 --force 强制重新初始化[/bold yellow]"
                    )
                    return True

                # 创建默认配置文件
                if not config_file.exists() or force:
                    progress.update(task, description="创建默认配置文件...")

                    default_config = """# WhitePaper 系统配置
# 生成命令: /speckit.implement T021
# 生成时间: 2025-12-09

# LLM配置
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# Embedding配置
EMBEDDING_PROVIDER=dashscope
DASHSCOPE_API_KEY=your_dashscope_api_key_here
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4

# Rerank配置
RERANK_PROVIDER=dashscope
DASHSCOPE_RERANK_MODEL=qwen3-rerank

# 数据库配置
DATABASE_URL=sqlite:///./storage/sqlite/whitepaper.db

# Chroma向量数据库配置
CHROMA_PERSIST_DIRECTORY=./storage/chroma/chroma_db
CHROMA_HOST=localhost
CHROMA_PORT=8000

# NetworkX图数据库配置
NETWORKX_PERSIST_DIRECTORY=./storage/networkx

# Redis配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=./data/logs/app.log

# 文件存储配置
UPLOAD_DIR=./data/source/uploads
TEMP_DIR=./data/temp
OUTPUT_DIR=./data/output
"""

                    with config_file.open("w", encoding="utf-8") as f:
                        f.write(default_config)

                    progress.update(task, description="配置文件创建完成")

                # 重新加载配置
                self._load_settings()

                if self.settings:
                    progress.update(task, description="配置验证通过")
                    return True
                else:
                    progress.update(task, description="配置验证失败")
                    return False

        except Exception as e:
            console.print(f"[bold red]配置初始化失败: {e!s}[/bold red]")
            logger.error("配置初始化失败: %s", e)
            return False

    def init_database(self, *, force: bool = False) -> bool:
        """初始化数据库"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("初始化数据库...", total=None)

                if not self.settings:
                    progress.update(task, description="配置未加载")
                    return False

                # 创建数据库目录
                db_dir = Path("./storage/sqlite")
                db_dir.mkdir(parents=True, exist_ok=True)

                progress.update(task, description="运行数据库迁移...")

                # 运行数据库迁移
                import sys

                from scripts.migration.init_db import main as migrate_main

                # 保存原始sys.argv
                original_argv = sys.argv.copy()
                try:
                    # 设置迁移命令参数
                    sys.argv = ["migrate", "init"]
                    if force:
                        sys.argv.append("--force")

                    # 运行迁移
                    migrate_main()

                finally:
                    # 恢复原始sys.argv
                    sys.argv = original_argv

                progress.update(task, description="数据库初始化完成")
                return True

        except Exception as e:
            console.print(f"[bold red]数据库初始化失败: {e!s}[/bold red]")
            logger.error("数据库初始化失败: %s", e)
            return False

    def init_storage(self, *, force: bool = False) -> bool:
        """初始化存储"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("初始化存储...", total=None)

                if not self.settings:
                    progress.update(task, description="配置未加载")
                    return False

                # 创建必要的目录
                directories = [
                    "./storage/sqlite",
                    "./storage/chroma",
                    "./storage/networkx",
                    "./data/source/documents",
                    "./data/source/uploads",
                    "./data/intermediate/preprocessed",
                    "./data/intermediate/parsed",
                    "./data/intermediate/indexed/vectors",
                    "./data/intermediate/indexed/bm25",
                    "./data/intermediate/indexed/metadata",
                    "./data/intermediate/knowledge_graph",
                    "./data/intermediate/checkpoints",
                    "./data/templates/document_templates",
                    "./data/templates/prompt_templates",
                    "./data/templates/prompt_strategies",
                    "./data/output/drafts",
                    "./data/output/final",
                    "./data/output/exports",
                    "./data/output/reports",
                    "./data/cache/retrieval",
                    "./data/cache/embeddings",
                    "./data/cache/agent_states",
                    "./data/temp/processing",
                    "./data/temp/uploads",
                    "./data/logs",
                ]

                for directory in directories:
                    progress.update(task, description=f"创建目录: {directory}")
                    Path(directory).mkdir(parents=True, exist_ok=True)

                progress.update(task, description="存储初始化完成")
                return True

        except Exception as e:
            console.print(f"[bold red]存储初始化失败: {e!s}[/bold red]")
            logger.error("存储初始化失败: %s", e)
            return False

    def init_sample_data(self) -> bool:
        """初始化示例数据"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("初始化示例数据...", total=None)

                # 这里可以添加示例数据的初始化逻辑
                # 例如:创建示例文档,知识库条目等

                progress.update(task, description="示例数据初始化完成")
                return True

        except Exception as e:
            console.print(f"[bold red]示例数据初始化失败: {e!s}[/bold red]")
            logger.error("示例数据初始化失败: %s", e)
            return False

    def print_success(self, message: str) -> None:
        """打印成功消息"""
        console.print(
            Panel(Text(message, style="bold green"), title="成功", border_style="green")
        )

    def print_error(self, message: str) -> None:
        """打印错误消息"""
        console.print(
            Panel(Text(message, style="bold red"), title="错误", border_style="red")
        )

    def print_warning(self, message: str) -> None:
        """打印警告消息"""
        console.print(
            Panel(
                Text(message, style="bold yellow"), title="警告", border_style="yellow"
            )
        )

    def print_info(self, message: str) -> None:
        """打印信息消息"""
        console.print(
            Panel(Text(message, style="bold blue"), title="信息", border_style="blue")
        )

    def confirm_action(self, message: str, *, default: bool = False) -> bool:
        """确认操作"""
        from rich.prompt import Confirm

        return Confirm.ask(message, default=default)

    def prompt_input(self, message: str, default: str | None = None) -> str:
        """获取用户输入"""
        from rich.prompt import Prompt

        return Prompt.ask(message, default=default)

    def prompt_choice(
        self, message: str, choices: list[str], default: str | None = None
    ) -> str:
        """获取用户选择"""
        from rich.prompt import Prompt

        return Prompt.ask(message, choices=choices, default=default)

    def run_async(self, coro):
        """运行异步函数"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)
