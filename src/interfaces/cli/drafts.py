# 生成命令: /speckit.implement MVP-DRAFT-EXPORT
# 生成时间: 2025-12-30
"""
草稿管理 CLI 命令

提供草稿查询与导出能力，面向 MVP 演示/交付使用。
"""

from __future__ import annotations

import re
import sqlite3
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


