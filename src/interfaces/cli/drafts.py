# 生成命令: /speckit.implement MVP-DRAFT-EXPORT
# 生成时间: 2025-12-30
"""
草稿管理 CLI 命令

提供草稿查询与导出能力，面向 MVP 演示/交付使用。
"""

from __future__ import annotations

import re
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from src.shared.config.settings import get_config


drafts_app = typer.Typer(
    name="drafts",
    help="草稿管理（导出/查看）",
    no_args_is_help=True,
)

console = Console()


def _slugify(value: str, max_len: int = 60) -> str:
    v = value.strip()
    # Windows 文件名安全化
    v = re.sub(r'[<>:"/\\\\|?*]+', "-", v)
    v = re.sub(r"\s+", " ", v).strip()
    v = v.replace(" ", "_")
    if len(v) > max_len:
        v = v[:max_len].rstrip("_-")
    return v or "draft"


def _get_db_path() -> Path:
    cfg = get_config()
    return Path(cfg.database.sqlite_db_path).resolve()


def _query_one(sql: str, params: tuple) -> Optional[sqlite3.Row]:
    db_path = _get_db_path()
    if not db_path.exists():
        raise typer.BadParameter(f"SQLite 数据库文件不存在: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        conn.close()


@drafts_app.command("export-latest")
def export_latest(
    out_dir: str = typer.Option(
        "data/output/drafts",
        "--out-dir",
        help="导出目录（相对项目根目录或绝对路径）",
    ),
    draft_id: Optional[str] = typer.Option(
        None, "--draft-id", help="指定草稿ID（优先级高于 outline-id / latest）"
    ),
    outline_id: Optional[str] = typer.Option(
        None, "--outline-id", help="指定大纲ID，导出该大纲下最新草稿"
    ),
    filename: Optional[str] = typer.Option(
        None,
        "--filename",
        help="指定导出的文件名（例如 demo.md）。不传则使用 <draft_id>_<title>.md",
    ),
):
    """导出草稿为 Markdown 文件（默认导出最新一版）"""

    if draft_id:
        row = _query_one(
            """
            SELECT id, outline_id, title, content, updated_at, created_at
            FROM drafts
            WHERE id = ?
            """,
            (draft_id,),
        )
        if not row:
            raise typer.Exit(f"未找到草稿: {draft_id}")
    elif outline_id:
        row = _query_one(
            """
            SELECT id, outline_id, title, content, updated_at, created_at
            FROM drafts
            WHERE outline_id = ?
            ORDER BY COALESCE(updated_at, created_at) DESC
            LIMIT 1
            """,
            (outline_id,),
        )
        if not row:
            raise typer.Exit(f"未找到草稿(按outline_id): {outline_id}")
    else:
        row = _query_one(
            """
            SELECT id, outline_id, title, content, updated_at, created_at
            FROM drafts
            ORDER BY COALESCE(updated_at, created_at) DESC
            LIMIT 1
            """,
            (),
        )
        if not row:
            raise typer.Exit("当前数据库中没有任何草稿记录(drafts 表为空)")

    content = (row["content"] or "").strip()
    if not content:
        raise typer.Exit("草稿内容为空，无法导出（drafts.content 为空）")

    out_path = Path(out_dir)
    if not out_path.is_absolute():
        out_path = (Path.cwd() / out_path).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    if filename:
        file_path = out_path / filename
    else:
        safe_title = _slugify(str(row["title"] or "draft"))
        file_path = out_path / f"{row['id']}_{safe_title}.md"

    file_path.write_text(content, encoding="utf-8")
    console.print("[bold green]导出成功[/bold green]")
    console.print(f"- draft_id: {row['id']}")
    console.print(f"- outline_id: {row['outline_id']}")
    console.print(f"- file: {file_path}")


@drafts_app.command("export-html")
def export_html(
    out_dir: str = typer.Option(
        "data/output/final",
        "--out-dir",
        help="导出目录（相对项目根目录或绝对路径）",
    ),
    md_path: Optional[str] = typer.Option(
        None,
        "--md-path",
        help="从Markdown文件直接导出HTML（不依赖数据库）。例如 data/output/drafts/outline_template_<id>.md",
    ),
    draft_id: Optional[str] = typer.Option(
        None, "--draft-id", help="指定草稿ID（优先级高于 outline-id / latest）"
    ),
    outline_id: Optional[str] = typer.Option(
        None, "--outline-id", help="指定大纲ID，导出该大纲下最新草稿"
    ),
    filename: Optional[str] = typer.Option(
        None,
        "--filename",
        help="指定导出的文件名（例如 demo.html）。不传则使用 <timestamp>_<draft_id>_<title>.html",
    ),
    datajson_dir: Optional[str] = typer.Option(
        None,
        "--datajson-dir",
        help="datajson目录路径（用于加载图表数据），如果不指定则尝试自动查找",
    ),
    retrieve: Optional[bool] = typer.Option(
        None,
        "--retrieve/--no-retrieve",
        help=(
            "md-path 模式下是否按章节触发 RAG/BM25 召回并填充正文。"
            "默认自动判断：像“只有标题的模板md”就开启；否则关闭。"
        ),
    ),
    top_k: int = typer.Option(
        5,
        "--top-k",
        min=1,
        max=20,
        help="每章召回的 TopK（仅 --md-path 生效）",
    ),
    max_sections: Optional[int] = typer.Option(
        None,
        "--max-sections",
        min=1,
        help="最多处理的章节数（调试用，仅 --md-path 生效；不传表示全部）",
    ),
    bm25_index_json: Optional[str] = typer.Option(
        None,
        "--bm25-index-json",
        help="指定 BM25 索引 JSON 文件路径（例如 data/bm25_index/kb_kb_xxx.json；仅 --md-path 生效）",
    ),
    vector_collection: Optional[str] = typer.Option(
        None,
        "--vector-collection",
        help="指定 Chroma collection 名称（默认 whitepaper_documents；仅 --md-path 生效）",
    ),
):
    """导出草稿为 HTML 文件（包含图表渲染和附录数据）"""
    from src.application.services.html_export_service import HTMLExportService
    from src.shared.exceptions.base_exceptions import ResourceNotFoundError, ValidationError

    try:
        # 使用服务层函数
        export_service = HTMLExportService()
        if md_path:
            file_path = export_service.export_markdown_file_to_html(
                md_path=md_path,
                output_dir=out_dir,
                filename=filename,
                datajson_dir=datajson_dir,
                include_appendix=True,
                outline_id=outline_id,
                retrieve=retrieve,
                retrieval_top_k=top_k,
                max_sections=max_sections,
                bm25_index_json=bm25_index_json,
                vector_collection_name=vector_collection,
            )
        else:
            file_path = export_service.export_draft_to_html(
                draft_id=draft_id,
                outline_id=outline_id,
                output_dir=out_dir,
                filename=filename,
                datajson_dir=datajson_dir,
                include_appendix=True,
            )

        # 获取草稿信息用于显示（md_path 模式不依赖数据库）
        draft = None
        if not md_path:
            draft_service = export_service.draft_service
            if draft_id:
                draft = draft_service.get_draft(uuid.UUID(draft_id))
            elif outline_id:
                drafts = draft_service.list_drafts(outline_id=uuid.UUID(outline_id))
                draft = drafts[0] if drafts else None
            else:
                drafts = draft_service.list_drafts()
                draft = drafts[0] if drafts else None

        console.print("[bold green]HTML导出成功[/bold green]")
        if draft:
            console.print(f"- draft_id: {draft.id}")
            console.print(f"- outline_id: {draft.outline_id}")
        if md_path:
            console.print(f"- md: {md_path}")
        console.print(f"- file: {file_path}")
        if datajson_dir:
            console.print(f"- datajson目录: {datajson_dir}")

    except ResourceNotFoundError as e:
        raise typer.Exit(str(e))
    except ValidationError as e:
        raise typer.Exit(str(e))
    except Exception as e:
        console.print(f"[bold red]导出失败: {e}[/bold red]")
        raise typer.Exit(1)


