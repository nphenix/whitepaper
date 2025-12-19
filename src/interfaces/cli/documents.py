# 生成命令: /speckit.implement T036
# 生成时间: 2025-12-17
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
文档管理CLI命令

提供文档上传、预处理、清洗等功能的命令行接口。
集成T033文档服务,支持同步和异步处理。
"""

import asyncio
import json
import uuid
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

from cli.base import BaseCLI
from src.application.services.document_service import DocumentService
from src.domain.document.document import DocumentStatus
from src.shared.config.llm_service import get_llm_service

# 创建Typer应用实例
documents_app = typer.Typer(
    name="documents",
    help="文档管理和预处理",
    no_args_is_help=True,
)

console = Console()


def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _format_processing_time(seconds: float) -> str:
    """格式化处理时间"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.1f}m"
    else:
        return f"{seconds / 3600:.1f}h"


@documents_app.command()
def upload(
    file_path: str = typer.Argument(..., help="要上传的文档文件路径"),
    uploaded_by: str | None = typer.Option(
        None, "--uploaded-by", "-u", help="上传用户ID"
    ),
    format: str | None = typer.Option(
        None, "--format", "-f", help="文档格式(可选,自动检测)"
    ),
    enable_chart_conversion: bool = typer.Option(
        True,
        "--enable-chart-conversion/--disable-chart-conversion",
        help="是否启用图表转换",
    ),
    use_agent: bool = typer.Option(
        True, "--use-agent/--use-preprocessor", help="使用Agent还是Preprocessor"
    ),
    output_dir: str | None = typer.Option(
        None, "--output-dir", "-o", help="输出目录(可选)"
    ),
) -> None:
    """上传并处理文档(同步)"""
    BaseCLI()

    # 检查文件是否存在
    file = Path(file_path)
    if not file.exists():
        console.print(f"[bold red]文件不存在: {file_path}[/bold red]")
        raise typer.Exit(1)

    # 检查文件类型
    supported_extensions = [".pdf", ".docx"]
    if file.suffix.lower() not in supported_extensions:
        console.print(f"[bold red]不支持的文件类型: {file.suffix}[/bold red]")
        console.print(f"支持的文件类型: {', '.join(supported_extensions)}")
        raise typer.Exit(1)

    # 解析用户ID
    if uploaded_by:
        try:
            user_id = uuid.UUID(uploaded_by)
        except ValueError:
            console.print(f"[bold red]无效的用户ID格式: {uploaded_by}[/bold red]")
            raise typer.Exit(1)
    else:
        # 使用默认测试用户
        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    console.print(f"[bold blue]正在上传并处理文档: {file.name}[/bold blue]")
    console.print(f"[bold cyan]用户: {user_id}[/bold cyan]")
    console.print(
        f"[bold cyan]使用: {'Agent' if use_agent else 'Preprocessor'}[/bold cyan]"
    )
    console.print(
        f"[bold cyan]图表转换: {'启用' if enable_chart_conversion else '禁用'}[/bold cyan]"
    )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("处理文档...", total=None)

            # 初始化文档服务
            service = DocumentService(
                llm_service=get_llm_service(),
                enable_chart_conversion=enable_chart_conversion,
                use_agent=use_agent,
            )

            # 上传并处理文档
            documents = service.upload_and_process(
                file_path=file_path,
                uploaded_by=user_id,
                format=format,
            )

            progress.update(task, description="文档处理完成")

        console.print(f"[bold green]✅ 文档处理成功: {file.name}[/bold green]")
        console.print(f"[bold green]生成 {len(documents)} 个文档片段[/bold green]")

        # 显示文档信息
        if documents:
            doc = documents[0]
            metadata = doc.metadata
            console.print(
                Panel(
                    f"文件名: {metadata.get('source', file.name)}\n"
                    f"格式: {metadata.get('format', 'unknown')}\n"
                    f"管线: {metadata.get('pipeline', 'unknown')}\n"
                    f"大小: {_format_file_size(file.stat().st_size)}",
                    title="文档信息",
                    border_style="green",
                )
            )

    except Exception as e:
        console.print(f"[bold red]文档处理失败: {e!s}[/bold red]")
        raise typer.Exit(1)


@documents_app.command()
def upload_async(
    file_path: str = typer.Argument(..., help="要上传的文档文件路径"),
    uploaded_by: str | None = typer.Option(
        None, "--uploaded-by", "-u", help="上传用户ID"
    ),
    format: str | None = typer.Option(
        None, "--format", "-f", help="文档格式(可选,自动检测)"
    ),
    enable_chart_conversion: bool = typer.Option(
        True,
        "--enable-chart-conversion/--disable-chart-conversion",
        help="是否启用图表转换",
    ),
    use_agent: bool = typer.Option(
        True, "--use-agent/--use-preprocessor", help="使用Agent还是Preprocessor"
    ),
) -> None:
    """上传并处理文档(异步)"""

    # 检查文件是否存在
    file = Path(file_path)
    if not file.exists():
        console.print(f"[bold red]文件不存在: {file_path}[/bold red]")
        raise typer.Exit(1)

    # 检查文件类型
    supported_extensions = [".pdf", ".docx"]
    if file.suffix.lower() not in supported_extensions:
        console.print(f"[bold red]不支持的文件类型: {file.suffix}[/bold red]")
        console.print(f"支持的文件类型: {', '.join(supported_extensions)}")
        raise typer.Exit(1)

    # 解析用户ID
    if uploaded_by:
        try:
            user_id = uuid.UUID(uploaded_by)
        except ValueError:
            console.print(f"[bold red]无效的用户ID格式: {uploaded_by}[/bold red]")
            raise typer.Exit(1)
    else:
        # 使用默认测试用户
        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    console.print(f"[bold blue]开始异步上传并处理文档: {file.name}[/bold blue]")
    console.print(f"[bold cyan]用户: {user_id}[/bold cyan]")
    console.print(
        f"[bold cyan]使用: {'Agent' if use_agent else 'Preprocessor'}[/bold cyan]"
    )
    console.print(
        f"[bold cyan]图表转换: {'启用' if enable_chart_conversion else '禁用'}[/bold cyan]"
    )

    try:
        # 初始化文档服务
        service = DocumentService(
            llm_service=get_llm_service(),
            enable_chart_conversion=enable_chart_conversion,
            use_agent=use_agent,
        )

        # 异步处理文档
        result = asyncio.run(
            service.upload_and_process_async(
                file_path=file_path,
                uploaded_by=user_id,
                format=format,
                enable_chart_conversion=enable_chart_conversion,
            )
        )

        console.print(f"[bold green]✅ 异步文档处理完成: {file.name}[/bold green]")

        # 显示结果
        if result.get("status") == "completed":
            console.print(
                f"[bold green]成功处理 {result.get('file_count', 0)} 个文件[/bold green]"
            )
            console.print(
                f"[bold green]生成 {result.get('documents_count', 0)} 个文档片段[/bold green]"
            )
            console.print(
                f"[bold green]处理时间: {_format_processing_time(result.get('processing_time', 0))}[/bold green]"
            )
        else:
            console.print(
                f"[bold red]处理失败: {result.get('error', 'Unknown error')}[/bold red]"
            )

    except Exception as e:
        console.print(f"[bold red]异步文档处理失败: {e!s}[/bold red]")
        raise typer.Exit(1)


@documents_app.command()
def upload_batch_async(
    file_paths: list[str] = typer.Argument(..., help="要上传的文档文件路径列表"),
    uploaded_by: str | None = typer.Option(
        None, "--uploaded-by", "-u", help="上传用户ID"
    ),
    batch_size: int = typer.Option(10, "--batch-size", "-b", help="批量处理大小"),
    enable_chart_conversion: bool = typer.Option(
        True,
        "--enable-chart-conversion/--disable-chart-conversion",
        help="是否启用图表转换",
    ),
    use_agent: bool = typer.Option(
        True, "--use-agent/--use-preprocessor", help="使用Agent还是Preprocessor"
    ),
) -> None:
    """批量上传并处理文档(异步)"""

    # 检查文件是否存在
    valid_files = []
    for file_path in file_paths:
        file = Path(file_path)
        if not file.exists():
            console.print(f"[bold red]文件不存在: {file_path}[/bold red]")
            continue

        # 检查文件类型
        supported_extensions = [".pdf", ".docx"]
        if file.suffix.lower() not in supported_extensions:
            console.print(
                f"[bold red]不支持的文件类型: {file.suffix} (文件: {file_path})[/bold red]"
            )
            continue

        valid_files.append(file_path)

    if not valid_files:
        console.print("[bold red]没有有效的文件需要处理[/bold red]")
        raise typer.Exit(1)

    # 解析用户ID
    if uploaded_by:
        try:
            user_id = uuid.UUID(uploaded_by)
        except ValueError:
            console.print(f"[bold red]无效的用户ID格式: {uploaded_by}[/bold red]")
            raise typer.Exit(1)
    else:
        # 使用默认测试用户
        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    console.print(
        f"[bold blue]开始批量异步上传并处理文档: {len(valid_files)} 个文件[/bold blue]"
    )
    console.print(f"[bold cyan]用户: {user_id}[/bold cyan]")
    console.print(f"[bold cyan]批量大小: {batch_size}[/bold cyan]")
    console.print(
        f"[bold cyan]使用: {'Agent' if use_agent else 'Preprocessor'}[/bold cyan]"
    )
    console.print(
        f"[bold cyan]图表转换: {'启用' if enable_chart_conversion else '禁用'}[/bold cyan]"
    )

    try:
        # 初始化文档服务
        service = DocumentService(
            llm_service=get_llm_service(),
            enable_chart_conversion=enable_chart_conversion,
            use_agent=use_agent,
        )

        # 异步批量处理文档
        result = asyncio.run(
            service.upload_and_process_batch_async(
                file_paths=valid_files,
                uploaded_by=user_id,
                batch_size=batch_size,
                enable_chart_conversion=enable_chart_conversion,
            )
        )

        console.print("[bold green]✅ 批量异步文档处理完成[/bold green]")

        # 显示结果
        if result.get("status") == "completed":
            console.print(
                f"[bold green]成功处理 {result.get('processed_files', [])} 个文件[/bold green]"
            )
            console.print(
                f"[bold green]失败文件: {result.get('failed_files', [])}[/bold green]"
            )
            console.print(
                f"[bold green]成功率: {result.get('success_rate', 0):.1f}%[/bold green]"
            )
            console.print(
                f"[bold green]处理时间: {_format_processing_time(result.get('processing_time', 0))}[/bold green]"
            )
        else:
            console.print(
                f"[bold red]批量处理失败: {result.get('error', 'Unknown error')}[/bold red]"
            )

    except Exception as e:
        console.print(f"[bold red]批量异步文档处理失败: {e!s}[/bold red]")
        raise typer.Exit(1)


@documents_app.command()
def list(
    uploaded_by: str | None = typer.Option(
        None, "--uploaded-by", "-u", help="上传用户ID"
    ),
    status: str | None = typer.Option(None, "--status", "-s", help="文档状态过滤"),
    limit: int | None = typer.Option(None, "--limit", "-l", help="限制返回数量"),
) -> None:
    """列出系统中的文档"""
    BaseCLI()

    try:
        # 初始化文档服务
        service = DocumentService()

        # 解析用户ID
        user_id = None
        if uploaded_by:
            try:
                user_id = uuid.UUID(uploaded_by)
            except ValueError:
                console.print(f"[bold red]无效的用户ID格式: {uploaded_by}[/bold red]")
                raise typer.Exit(1)

        # 解析状态
        status_enum = None
        if status:
            try:
                status_enum = DocumentStatus(status.lower())
            except ValueError:
                console.print(f"[bold red]无效的状态: {status}[/bold red]")
                console.print(f"支持的状态: {[s.value for s in DocumentStatus]}")
                raise typer.Exit(1)

        # 查询文档
        documents = service.list_documents(
            uploaded_by=user_id,
            status=status_enum,
            limit=limit,
        )

        if not documents:
            console.print("[bold yellow]没有找到文档[/bold yellow]")
            return

        # 创建文档列表表格
        table = Table(title=f"文档列表 (共 {len(documents)} 个)")
        table.add_column("ID", style="cyan", no_wrap=True, width=36)
        table.add_column("文件名", style="magenta", no_wrap=True)
        table.add_column("类型", style="green")
        table.add_column("大小", style="blue")
        table.add_column("状态", style="yellow")
        table.add_column("上传时间", style="cyan")
        table.add_column("处理时间", style="blue")

        for doc in documents:
            table.add_row(
                str(doc.id),
                doc.filename,
                doc.format if isinstance(doc.format, str) else doc.format.value,
                _format_file_size(doc.file_size),
                doc.status if isinstance(doc.status, str) else doc.status.value,
                doc.uploaded_at.strftime("%Y-%m-%d %H:%M:%S"),
                (
                    doc.parsed_at.strftime("%Y-%m-%d %H:%M:%S")
                    if doc.parsed_at
                    else "未处理"
                ),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[bold red]查询文档失败: {e!s}[/bold red]")
        raise typer.Exit(1)


@documents_app.command()
def get(
    document_id: str = typer.Argument(..., help="文档ID"),
) -> None:
    """获取文档详细信息"""
    BaseCLI()

    try:
        # 解析文档ID
        try:
            doc_id = uuid.UUID(document_id)
        except ValueError:
            console.print(f"[bold red]无效的文档ID格式: {document_id}[/bold red]")
            raise typer.Exit(1)

        # 初始化文档服务
        service = DocumentService()

        # 查询文档
        document = service.get_document(doc_id)

        if not document:
            console.print(f"[bold red]未找到文档: {document_id}[/bold red]")
            raise typer.Exit(1)

        # 显示文档信息
        console.print(
            Panel(
                f"ID: {document.id}\n"
                f"文件名: {document.filename}\n"
                f"文件路径: {document.file_path}\n"
                f"类型: {document.format if isinstance(document.format, str) else document.format.value}\n"
                f"大小: {_format_file_size(document.file_size)}\n"
                f"MIME类型: {document.mime_type}\n"
                f"状态: {document.status if isinstance(document.status, str) else document.status.value}\n"
                f"上传时间: {document.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"处理时间: {document.parsed_at.strftime('%Y-%m-%d %H:%M:%S') if document.parsed_at else '未处理'}\n"
                f"上传用户: {document.uploaded_by}\n"
                f"错误信息: {document.error_message or '无'}",
                title="文档详细信息",
                border_style="green",
            )
        )

        # 显示元数据(JSON格式)
        if document.metadata:
            metadata_json = json.dumps(document.metadata, ensure_ascii=False, indent=2)
            syntax = Syntax(metadata_json, "json", theme="monokai", line_numbers=True)
            console.print(Panel(syntax, title="元数据", border_style="blue"))

    except Exception as e:
        console.print(f"[bold red]获取文档信息失败: {e!s}[/bold red]")
        raise typer.Exit(1)


@documents_app.command()
def status() -> None:
    """显示文档处理状态统计"""
    BaseCLI()

    try:
        # 初始化文档服务
        service = DocumentService()

        # 查询所有文档
        documents = service.list_documents()

        if not documents:
            console.print("[bold yellow]没有找到文档[/bold yellow]")
            return

        # 统计信息
        total = len(documents)
        status_counts = {}
        format_counts = {}

        for doc in documents:
            # 统计状态
            status = doc.status if isinstance(doc.status, str) else doc.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

            # 统计格式
            format_type = (
                doc.format if isinstance(doc.format, str) else doc.format.value
            )
            format_counts[format_type] = format_counts.get(format_type, 0) + 1

        # 创建状态统计表格
        status_table = Table(title="文档状态统计")
        status_table.add_column("状态", style="cyan", no_wrap=True)
        status_table.add_column("数量", style="magenta")
        status_table.add_column("占比", style="green")

        for status, count in status_counts.items():
            percentage = count / total * 100
            status_table.add_row(status, str(count), f"{percentage:.1f}%")

        # 创建格式统计表格
        format_table = Table(title="文档格式统计")
        format_table.add_column("格式", style="cyan", no_wrap=True)
        format_table.add_column("数量", style="magenta")
        format_table.add_column("占比", style="green")

        for format_type, count in format_counts.items():
            percentage = count / total * 100
            format_table.add_row(format_type, str(count), f"{percentage:.1f}%")

        # 显示总览
        console.print(
            Panel(
                f"总文档数: {total}\n"
                f"已处理: {status_counts.get('indexed', 0)}\n"
                f"处理中: {status_counts.get('parsing', 0)}\n"
                f"失败: {status_counts.get('failed', 0)}",
                title="文档处理总览",
                border_style="green",
            )
        )

        console.print(status_table)
        console.print(format_table)

    except Exception as e:
        console.print(f"[bold red]获取状态统计失败: {e!s}[/bold red]")
        raise typer.Exit(1)


@documents_app.command()
def process(
    document_id: str = typer.Argument(..., help="文档ID"),
    enable_chart_conversion: bool = typer.Option(
        True,
        "--enable-chart-conversion/--disable-chart-conversion",
        help="是否启用图表转换",
    ),
    use_agent: bool = typer.Option(
        True, "--use-agent/--use-preprocessor", help="使用Agent还是Preprocessor"
    ),
) -> None:
    """处理指定文档"""
    BaseCLI()

    try:
        # 解析文档ID
        try:
            doc_id = uuid.UUID(document_id)
        except ValueError:
            console.print(f"[bold red]无效的文档ID格式: {document_id}[/bold red]")
            raise typer.Exit(1)

        # 初始化文档服务
        service = DocumentService(
            llm_service=get_llm_service(),
            enable_chart_conversion=enable_chart_conversion,
            use_agent=use_agent,
        )

        # 查询文档
        document = service.get_document(doc_id)

        if not document:
            console.print(f"[bold red]未找到文档: {document_id}[/bold red]")
            raise typer.Exit(1)

        # 检查文档状态
        current_status = (
            document.status
            if isinstance(document.status, str)
            else document.status.value
        )
        if current_status != DocumentStatus.PENDING.value:
            console.print(
                f"[bold yellow]文档状态不是PENDING,当前状态: {current_status}[/bold yellow]"
            )
            if not Confirm.ask("是否继续处理?"):
                raise typer.Exit(1)

        console.print(f"[bold blue]开始处理文档: {document.filename}[/bold blue]")
        console.print(
            f"[bold cyan]使用: {'Agent' if use_agent else 'Preprocessor'}[/bold cyan]"
        )
        console.print(
            f"[bold cyan]图表转换: {'启用' if enable_chart_conversion else '禁用'}[/bold cyan]"
        )

        # 重新处理文档
        file_path = document.file_path
        user_id = document.uploaded_by

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("处理文档...", total=None)

            # 上传并处理文档
            documents = service.upload_and_process(
                file_path=file_path,
                uploaded_by=user_id,
            )

            progress.update(task, description="文档处理完成")

        console.print(f"[bold green]✅ 文档处理成功: {document.filename}[/bold green]")
        console.print(f"[bold green]生成 {len(documents)} 个文档片段[/bold green]")

    except Exception as e:
        console.print(f"[bold red]处理文档失败: {e!s}[/bold red]")
        raise typer.Exit(1)


@documents_app.command()
def process_batch(
    batch_size: int = typer.Option(10, "--batch-size", "-b", help="批量处理大小"),
    enable_chart_conversion: bool = typer.Option(
        True,
        "--enable-chart-conversion/--disable-chart-conversion",
        help="是否启用图表转换",
    ),
    use_agent: bool = typer.Option(
        True, "--use-agent/--use-preprocessor", help="使用Agent还是Preprocessor"
    ),
    limit: int | None = typer.Option(None, "--limit", "-l", help="限制处理数量"),
) -> None:
    """批量处理待处理的文档"""
    BaseCLI()

    try:
        # 初始化文档服务
        service = DocumentService(
            llm_service=get_llm_service(),
            enable_chart_conversion=enable_chart_conversion,
            use_agent=use_agent,
        )

        # 查询待处理的文档
        pending_documents = service.list_documents(status=DocumentStatus.PENDING)

        if not pending_documents:
            console.print("[bold yellow]没有待处理的文档[/bold yellow]")
            return

        # 限制处理数量
        if limit:
            pending_documents = pending_documents[:limit]

        console.print(
            f"[bold blue]开始批量处理 {len(pending_documents)} 个文档[/bold blue]"
        )
        console.print(f"[bold cyan]批量大小: {batch_size}[/bold cyan]")
        console.print(
            f"[bold cyan]使用: {'Agent' if use_agent else 'Preprocessor'}[/bold cyan]"
        )
        console.print(
            f"[bold cyan]图表转换: {'启用' if enable_chart_conversion else '禁用'}[/bold cyan]"
        )

        # 分批处理
        processed_count = 0
        failed_count = 0

        for i in range(0, len(pending_documents), batch_size):
            batch = pending_documents[i : i + batch_size]

            console.print(
                f"\n[bold blue]处理批次 {i // batch_size + 1}/{(len(pending_documents) - 1) // batch_size + 1}[/bold blue]"
            )

            file_paths = [doc.file_path for doc in batch]
            user_ids = [doc.uploaded_by for doc in batch]

            try:
                # 异步批量处理
                result = asyncio.run(
                    service.upload_and_process_batch_async(
                        file_paths=file_paths,
                        uploaded_by=user_ids[0],  # 使用第一个用户的ID
                        batch_size=batch_size,
                        enable_chart_conversion=enable_chart_conversion,
                    )
                )

                if result.get("status") == "completed":
                    processed_count += len(file_paths)
                    console.print(
                        f"[bold green]批次处理成功: {len(result.get('processed_files', []))} 个文件[/bold green]"
                    )
                else:
                    failed_count += len(file_paths)
                    console.print(
                        f"[bold red]批次处理失败: {result.get('error', 'Unknown error')}[/bold red]"
                    )

            except Exception as e:
                failed_count += len(file_paths)
                console.print(f"[bold red]批次处理异常: {e!s}[/bold red]")

        console.print("\n[bold green]批量处理完成[/bold green]")
        console.print(f"[bold green]成功处理: {processed_count} 个文件[/bold green]")
        console.print(f"[bold red]处理失败: {failed_count} 个文件[/bold red]")

    except Exception as e:
        console.print(f"[bold red]批量处理失败: {e!s}[/bold red]")
        raise typer.Exit(1)
