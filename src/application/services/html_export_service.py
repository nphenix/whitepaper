"""
HTML导出服务

提供草稿到HTML的导出功能，可被CLI、API和pytest直接调用。
用于T089任务：创建"生成最终HTML文稿"API或CLI入口。

生成命令: /speckit.implement T089
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
import shutil
from typing import Optional

from src.application.services.draft_service import DraftService
from src.application.services.html_renderer import HTMLRenderer
from src.domain.agent.draft import Draft
from src.shared.config.settings import get_config
from src.shared.exceptions.base_exceptions import ResourceNotFoundError, ValidationError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class HTMLExportService:
    """
    HTML导出服务

    提供草稿到HTML的导出功能，支持：
    - 根据草稿ID、大纲ID或最新草稿导出
    - 自动查找datajson目录
    - 生成带时间戳的文件名
    - 可被CLI、API和pytest直接调用
    """

    def __init__(
        self,
        draft_service: DraftService | None = None,
        html_renderer: HTMLRenderer | None = None,
    ):
        """
        初始化HTML导出服务

        Args:
            draft_service: 草稿服务实例，如果为None则创建新实例
            html_renderer: HTML渲染器实例，如果为None则创建新实例
        """
        self.draft_service = draft_service or DraftService()
        self.html_renderer = html_renderer

    def export_draft_to_html(
        self,
        draft_id: str | uuid.UUID | None = None,
        outline_id: str | uuid.UUID | None = None,
        draft: Draft | None = None,
        output_dir: str | Path = "data/output/final",
        filename: str | None = None,
        datajson_dir: str | Path | None = None,
        include_appendix: bool = True,
        overwrite_latest: bool = False,
    ) -> Path:
        """
        导出草稿为HTML文件

        优先级：draft > draft_id > outline_id > 最新草稿

        Args:
            draft_id: 草稿ID（可选）
            outline_id: 大纲ID（可选，导出该大纲下最新草稿）
            draft: 草稿对象（可选，如果提供则直接使用）
            output_dir: 输出目录（默认：data/output/final）
            filename: 输出文件名（可选，如果不提供则自动生成）
            datajson_dir: datajson目录路径（可选，如果不提供则尝试自动查找）
            include_appendix: 是否包含附录数据表格（默认：True）
            overwrite_latest: 是否以“固定文件名”覆盖导出（用于正式流程交付，避免生成多个HTML）

        Returns:
            生成的HTML文件路径

        Raises:
            ResourceNotFoundError: 如果草稿不存在
            ValidationError: 如果参数验证失败
        """
        try:
            logger.info(
                "开始导出草稿为HTML: draft_id=%s, outline_id=%s, output_dir=%s, include_appendix=%s",
                draft_id,
                outline_id,
                output_dir,
                include_appendix,
            )

            # 1. 获取草稿
            logger.debug("步骤1: 获取草稿对象")
            if draft:
                target_draft = draft
                logger.debug("使用提供的草稿对象: draft_id=%s", draft.id)
            elif draft_id:
                logger.debug("根据draft_id获取草稿: draft_id=%s", draft_id)
                target_draft = self.draft_service.get_draft(draft_id)
                if not target_draft:
                    raise ResourceNotFoundError(f"草稿不存在: {draft_id}")
            elif outline_id:
                logger.debug("根据outline_id获取最新草稿: outline_id=%s", outline_id)
                # 使用 get_latest_draft_for_outline 确保获取最新草稿
                # 注意：不能使用 list_drafts + drafts[0]，因为 list_drafts 没有显式排序
                target_draft = self.draft_service.get_latest_draft_for_outline(outline_id)
                logger.debug(
                    "找到最新草稿: draft_id=%s, title='%s'",
                    target_draft.id,
                    target_draft.title,
                )
            else:
                logger.debug("获取最新草稿")
                # 获取最新草稿
                drafts = self.draft_service.list_drafts()
                if not drafts:
                    raise ResourceNotFoundError(
                        "当前数据库中没有任何草稿记录(drafts 表为空)"
                    )
                target_draft = drafts[0]
                logger.debug(
                    "找到最新草稿: draft_id=%s, title='%s'",
                    target_draft.id,
                    target_draft.title,
                )

            logger.info(
                "草稿获取成功: draft_id=%s, title='%s', 章节数=%d",
                target_draft.id,
                target_draft.title,
                len(target_draft.sections),
            )

            # 1.5 导出前确保 rag_media_manifest 已加载：
            # - 如果草稿本身已有 rag_media_manifest（通常包含 *_1.jpg 等“去重后缀”映射），不要覆盖！
            # - 只有在缺失/为空时，才从预处理产物加载兜底。
            try:
                has_manifest = (
                    isinstance(getattr(target_draft, "metadata", None), dict)
                    and isinstance(target_draft.metadata.get("rag_media_manifest"), list)
                    and len(target_draft.metadata.get("rag_media_manifest") or []) > 0
                )
                if not has_manifest:
                    self.draft_service._load_rag_media_manifest(target_draft)  # type: ignore[attr-defined]
            except Exception:
                # 容错：不影响导出主流程
                pass

            # 2. 确定datajson目录
            logger.debug("步骤2: 确定datajson目录")
            datajson_path = self._resolve_datajson_dir(datajson_dir, draft=target_draft)
            if datajson_path:
                logger.info("使用datajson目录: %s", datajson_path)
            else:
                logger.warning("未找到datajson目录，图表可能无法正常渲染")

            # 2.2 为“md驱动/离线产物”场景补一个默认来源标题（避免 documents 表为空时来源退化为内部标识）
            # - 优先从 cleaned/documents/<dir> 目录名推断（并去噪）
            # - 仅作为展示用 fallback，不影响检索/索引
            try:
                if isinstance(target_draft.metadata, dict) and not target_draft.metadata.get("default_source_title"):
                    default_source_title = self._infer_default_source_title_from_datajson(datajson_path)
                    if default_source_title:
                        target_draft.metadata["default_source_title"] = default_source_title
                        logger.info("设置 default_source_title: %s", default_source_title)
            except Exception:
                pass

            # 2.5 尝试定位图片目录（兼容 datajson 同级 images 目录）
            images_source_dir: Path | None = None
            if datajson_path:
                candidate_1 = datajson_path / "images"
                candidate_2 = datajson_path.parent / "images"
                if candidate_1.exists() and candidate_1.is_dir():
                    images_source_dir = candidate_1
                elif candidate_2.exists() and candidate_2.is_dir():
                    images_source_dir = candidate_2

            # 3. 创建HTML渲染器（如果未提供）
            logger.debug("步骤3: 创建HTML渲染器")
            if self.html_renderer is None:
                html_renderer = HTMLRenderer(datajson_base_dir=datajson_path)
                logger.debug("创建新的HTML渲染器实例")
            else:
                html_renderer = self.html_renderer
                logger.debug("使用提供的HTML渲染器实例")

            # 4. 渲染HTML（HTML中应使用UUID文件名引用图片）
            logger.debug("步骤4: 渲染HTML内容")
            html_content = html_renderer.render_draft_to_html(
                draft=target_draft,
                chart_configs=None,
                include_appendix=include_appendix,
            )
            logger.debug("HTML渲染完成: 内容长度=%d字符", len(html_content))

            # 5. 确定输出路径
            logger.debug("步骤5: 确定输出路径")
            output_path = Path(output_dir)
            if not output_path.is_absolute():
                # 重要：不要用 cwd 解析相对路径（API/worker/pytest 的工作目录可能不在项目根）
                # 统一以项目根目录为基准，确保默认输出落在 <repo>/data/output/final
                from src.shared.config.settings import _find_project_root

                project_root = _find_project_root()
                output_path = (project_root / output_path).resolve()
            logger.debug("输出目录: %s", output_path)
            output_path.mkdir(parents=True, exist_ok=True)
            logger.debug("输出目录创建/确认完成")

            # 5.5 拷贝 datajson 与 images 到输出目录，保证 HTML 离线可打开
            # - datajson: 输出目录/datajson
            # - images: 输出目录/images
            # 注意：不重命名文件，保持UUID格式，HTML中直接使用UUID文件名引用
            try:
                if datajson_path and datajson_path.exists() and datajson_path.is_dir():
                    dst_datajson = output_path / "datajson"
                    if not dst_datajson.exists():
                        shutil.copytree(datajson_path, dst_datajson, dirs_exist_ok=True)
                    else:
                        # 目录已存在时,只拷贝不存在的文件
                        for src_file in datajson_path.iterdir():
                            if src_file.is_file():
                                dst_file = dst_datajson / src_file.name
                                if not dst_file.exists():
                                    shutil.copy2(src_file, dst_file)

                    logger.info("已处理datajson目录: %s", dst_datajson)

                if images_source_dir and images_source_dir.exists() and images_source_dir.is_dir():
                    dst_images = output_path / "images"
                    if not dst_images.exists():
                        shutil.copytree(images_source_dir, dst_images, dirs_exist_ok=True)
                    else:
                        for src_file in images_source_dir.iterdir():
                            if src_file.is_file():
                                dst_file = dst_images / src_file.name
                                if not dst_file.exists():
                                    shutil.copy2(src_file, dst_file)

                    logger.info("已处理images目录: %s (保持UUID文件名格式)", dst_images)
                elif datajson_path:
                    # 保持旧日志行为（但不再误判 datajson/images 必须存在）
                    logger.warning("未找到可用图片目录: datajson=%s", datajson_path)
            except Exception as copy_err:
                logger.warning("拷贝datajson/images到输出目录失败(不影响HTML导出): %s", copy_err, exc_info=True)

            # 5.6 根据 HTML 实际引用的图片，补拷贝缺失文件（避免 datajson_dir 选到 output/final 导致 images 不完整）
            try:
                dst_images_dir = output_path / "images"
                dst_images_dir.mkdir(parents=True, exist_ok=True)

                # 提取 <img src="images/..."> 引用的文件名
                needed: set[str] = set()
                for m in re.finditer(r"""<img[^>]+src=['"]images/([^'"]+)['"]""", html_content or ""):
                    fn = (m.group(1) or "").strip()
                    if fn:
                        needed.add(fn)

                if needed:
                    missing = [fn for fn in sorted(needed) if not (dst_images_dir / fn).exists()]
                    if missing:
                        logger.info("检测到HTML引用图片缺失: count=%d", len(missing))

                        # 构建若干可能的源 images 目录（优先：本次解析到的 images_source_dir / datajson 同级 images）
                        candidates: list[Path] = []
                        if images_source_dir and images_source_dir.exists():
                            candidates.append(images_source_dir)
                        if datajson_path:
                            for p in [datajson_path / "images", datajson_path.parent / "images"]:
                                if p.exists() and p.is_dir():
                                    candidates.append(p)

                        # 再补一个“全局搜索根”（按需单文件搜索，避免全量拷贝）
                        from src.shared.config.settings import _find_project_root

                        project_root = _find_project_root()
                        search_roots = [
                            project_root / "data" / "cleaned" / "documents",
                            project_root / "data" / "processed" / "mineru",
                        ]

                        def _copy_one(found: Path, dst: Path) -> bool:
                            try:
                                dst.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(found, dst)
                                return True
                            except Exception:
                                return False

                        copied = 0
                        for fn in missing:
                            dst = dst_images_dir / fn
                            if dst.exists():
                                continue

                            found_path: Path | None = None
                            # 1) 先在候选 images 目录内直接找
                            for c in candidates:
                                p = c / fn
                                if p.exists() and p.is_file():
                                    found_path = p
                                    break

                            # 2) 再在全局 root 下按 “**/images/<fn>” 精确查找
                            if found_path is None:
                                for root in search_roots:
                                    if not root.exists():
                                        continue
                                    try:
                                        hits = list(root.rglob(f"images/{fn}"))
                                    except Exception:
                                        hits = []
                                    if hits:
                                        found_path = hits[0]
                                        break

                            if found_path and _copy_one(found_path, dst):
                                copied += 1
                            else:
                                logger.warning("仍未找到HTML引用图片: %s", fn)

                        if copied:
                            logger.info("已补拷贝缺失图片: copied=%d", copied)
            except Exception as e:
                logger.warning("补拷贝缺失图片失败(不影响HTML导出): %s", e, exc_info=True)

            # 6. 生成文件名
            logger.debug("步骤6: 生成文件名")
            if filename:
                file_path = output_path / filename
                logger.debug("使用指定文件名: %s", filename)
            else:
                # 使用用户输入的标题（如果为空则使用默认标题）
                fixed_title = target_draft.title or "白皮书"
                safe_title = self._slugify(fixed_title)
                if overwrite_latest:
                    # 正式流程推荐：每个 outline 固定输出一个 latest 文件，避免同一轮流程产生多份 HTML
                    # 注意：outline_id 可能为空（历史/测试数据），此时回退到 draft_id。
                    stable_id = getattr(target_draft, "outline_id", None) or target_draft.id
                    # 清理同 outline 的旧 latest 文件（例如标题变化导致的多个 latest_*）
                    try:
                        for old in output_path.glob(f"latest_{stable_id}_*.html"):
                            # 不要误删当前将要写入的文件
                            if old.name != f"latest_{stable_id}_{safe_title}.html":
                                old.unlink(missing_ok=True)
                    except Exception:
                        pass

                    file_path = output_path / f"latest_{stable_id}_{safe_title}.html"
                    logger.debug("使用latest覆盖文件名: %s", file_path.name)
                else:
                    # 保留历史：增加微秒，避免同一秒多次导出发生覆盖导致“文件内容变化”
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    file_path = output_path / f"{timestamp}_{target_draft.id}_{safe_title}.html"
                    logger.debug("自动生成文件名: %s", file_path.name)

            # 7. 写入文件
            logger.debug("步骤7: 写入HTML文件")
            file_path.write_text(html_content, encoding="utf-8")

            file_size = file_path.stat().st_size
            logger.info(
                "HTML导出成功: file_path=%s, file_size=%d字节",
                file_path,
                file_size,
            )

            return file_path

        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "导出草稿为HTML失败: draft_id=%s, outline_id=%s, 错误=%s",
                draft_id,
                outline_id,
                e,
                exc_info=True,
            )
            msg = f"导出草稿为HTML失败: {e!s}"
            raise ValidationError(msg) from e

    def export_markdown_file_to_html(
        self,
        md_path: str | Path,
        output_dir: str | Path = "data/output/final",
        filename: str | None = None,
        datajson_dir: str | Path | None = None,
        include_appendix: bool = True,
        title: str | None = None,
        outline_id: str | uuid.UUID | None = None,
        retrieve: bool | None = None,
        retrieval_top_k: int = 5,
        max_sections: int | None = None,
        bm25_index_json: str | Path | None = None,
        vector_collection_name: str | None = None,
    ) -> Path:
        """
        从 Markdown 文件直接导出 HTML（不依赖数据库 drafts 记录）

        说明：
        - 适用于“md 驱动”的导出流程（数据库仅作辅助）
        - 内部会构造一个最小 Draft 对象交给 HTMLRenderer 渲染

        Args:
            md_path: Markdown 文件路径
            output_dir: 输出目录（默认：data/output/final）
            filename: 输出文件名（可选）
            datajson_dir: datajson目录路径（可选）
            include_appendix: 是否包含附录数据表格（默认：True）
            title: 文档标题（可选；不传则从 md 的首个 '# ' 标题或文件名推断）
            outline_id: 大纲ID（可选；用于在 HTMLRenderer 中定位对应 outline_template）
            retrieve: 是否在“md 模板导出”场景下按章节触发召回并填充正文
                      - None: 自动判断（像模板就开启，否则关闭）
                      - True/False: 强制开关
            retrieval_top_k: 每章召回 top_k（HybridRetriever）
            max_sections: 最多处理的章节数（调试用，None 表示全部）
            bm25_index_json: 指定 BM25 索引 JSON 文件路径（例如 data/bm25_index/kb_kb_xxx.json）
            vector_collection_name: 指定 Chroma collection（不传则使用默认 whitepaper_documents）

        Returns:
            生成的HTML文件路径
        """
        md_file = Path(md_path)
        if not md_file.exists() or not md_file.is_file():
            raise ValidationError(f"Markdown 文件不存在: {md_file}")

        md_content = md_file.read_text(encoding="utf-8").lstrip("\ufeff").strip()
        if not md_content:
            raise ValidationError(f"Markdown 文件内容为空: {md_file}")

        # 解析标题：优先取第一个 "# xxx"；否则用文件名
        inferred_title: str | None = None
        for line in md_content.splitlines():
            s = line.strip()
            if s.startswith("# "):
                inferred_title = s[2:].strip()
                break
        final_title = title or inferred_title or md_file.stem

        # outline_id 解析（仅用于 metadata，避免 Draft model 因必填字段失败）
        outline_uuid: uuid.UUID = uuid.uuid4()
        if outline_id:
            outline_uuid = uuid.UUID(str(outline_id))

        from src.domain.agent.draft import Draft, DraftSection, DraftSectionType, DraftStatus

        # -------- md 模板识别与“逐章召回填充” --------
        # md 导出：记录本次实际使用的 BM25 索引路径（由 _build_hybrid_retriever_for_md_export 填充，供后续注入 manifest 使用）
        bm25_pkl_used_for_md_export: str | None = None

        def _looks_like_outline_template(text: str) -> bool:
            """非常保守的启发式：模板通常只有标题/分隔线，几乎没有正文段落。"""
            meaningful_non_heading = 0
            for raw in text.splitlines():
                line = raw.strip()
                if not line:
                    continue
                if line == "---":
                    continue
                if line.startswith("#"):
                    continue
                # 子项目符号行也算“结构”而非正文
                if line.startswith(("-", "*")):
                    continue
                meaningful_non_heading += 1
                if meaningful_non_heading >= 5:
                    return False
            return True

        def _parse_md_headings(text: str) -> list[dict[str, object]]:
            """解析 Markdown 标题为线性结构（含层级），并保留标题之间的正文。"""
            items: list[dict[str, object]] = []
            lines = text.splitlines()
            cur: dict[str, object] | None = None

            def _flush() -> None:
                nonlocal cur
                if not cur:
                    return
                # 清理正文
                content_lines = cur.get("content_lines") or []
                if isinstance(content_lines, list):
                    content = "\n".join([str(x) for x in content_lines]).strip()
                else:
                    content = ""
                cur["content"] = content
                cur.pop("content_lines", None)
                items.append(cur)
                cur = None

            for raw in lines:
                s = raw.rstrip("\n")
                stripped = s.strip()
                if stripped.startswith("#"):
                    # 仅识别形如 "### title" 的标准标题行
                    m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
                    if m:
                        _flush()
                        level = len(m.group(1))
                        title_txt = m.group(2).strip()
                        cur = {
                            "heading_level": level,
                            "title": title_txt,
                            "content_lines": [],
                        }
                        continue
                if cur is not None:
                    content_lines = cur.get("content_lines")
                    if isinstance(content_lines, list):
                        content_lines.append(s)
            _flush()
            return items

        def _build_hybrid_retriever_for_md_export():
            """为 md 导出构建 HybridRetriever（向量+BM25+metadata），不依赖 DB 的 KB 映射。"""
            try:
                from src.infrastructure.indexing.bm25_index import BM25IndexBuilder
                from src.infrastructure.indexing.hybrid_retriever import HybridRetriever
                from src.infrastructure.indexing.metadata_index import MetadataIndexBuilder
                from src.infrastructure.indexing.multi_kb_retriever import MultiKBHybridRetriever
                from src.infrastructure.indexing.vector_index import VectorIndexBuilder
                from src.infrastructure.storage.chroma.connection import get_chroma_connection_manager
                from src.infrastructure.storage.sqlite.connection import get_sqlite_connection_manager
                from src.shared.config.llm_service import get_llm_service
            except Exception as e:  # pragma: no cover
                logger.warning("无法导入检索依赖，跳过召回填充: %s", e, exc_info=True)
                return None

            # 0) 默认兜底：自动发现当前 Chroma 中所有 kb_*_vector 集合并 MultiKB 检索
            # 背景：离线/批处理流程常会生成多个 kb_kb_xxx（每个 KB 对应一份 PDF）。
            # md 导出若只用单库（或 whitepaper_documents）会导致“来源永远只有一个文件”。
            if not vector_collection_name and not bm25_index_json:
                try:
                    cm = get_chroma_connection_manager()
                    collections = cm.list_collections()
                    names: list[str] = []
                    for c in collections:
                        n = getattr(c, "name", None)
                        if isinstance(n, str) and n:
                            names.append(n)
                        else:
                            s = str(c)
                            if s:
                                names.append(s)

                    kb_ids: list[str] = []
                    for name in names:
                        if name == "whitepaper_documents":
                            continue
                        if isinstance(name, str) and name.startswith("kb_") and name.endswith("_vector"):
                            kb_id = name[len("kb_") : -len("_vector")]
                            if kb_id:
                                kb_ids.append(kb_id)

                    seen: set[str] = set()
                    kb_ids = [x for x in kb_ids if not (x in seen or seen.add(x))]
                    if kb_ids:
                        logger.info("md导出召回：自动发现可用知识库: kb_count=%d", len(kb_ids))

                        def _build_one(kb_id: str) -> HybridRetriever:
                            vector_collection = f"kb_{kb_id}_vector"
                            bm25_path = f"./data/bm25_index/kb_{kb_id}.pkl"
                            metadata_table = f"kb_{kb_id}_metadata"
                            return HybridRetriever(
                                vector_index_builder=VectorIndexBuilder(
                                    collection_name=vector_collection,
                                    connection_manager=get_chroma_connection_manager(),
                                ),
                                bm25_index_builder=BM25IndexBuilder(index_path=bm25_path),
                                metadata_index_builder=MetadataIndexBuilder(
                                    table_name=metadata_table,
                                    connection_manager=get_sqlite_connection_manager(),
                                ),
                                llm_service=get_llm_service(),
                            )

                        if len(kb_ids) == 1:
                            return _build_one(kb_ids[0])
                        return MultiKBHybridRetriever(retrievers=[_build_one(x) for x in kb_ids])
                except Exception:
                    # 自动发现失败则回退到历史单库逻辑
                    pass

            # 1) BM25：
            # - 优先使用用户指定 bm25_index_json
            # - 否则在 data/bm25_index 下选择“documents 数最多”的 kb_kb_*.json（更可能覆盖多文档），再用 mtime 破同
            bm25_pkl_path: str | None = None
            try:
                if bm25_index_json:
                    p = Path(bm25_index_json)
                    if p.exists() and p.is_file():
                        bm25_pkl_path = str(p).replace(".json", ".pkl")
                if not bm25_pkl_path:
                    from src.shared.config.settings import _find_project_root

                    project_root = _find_project_root()
                    bm25_dir = project_root / "data" / "bm25_index"
                    if bm25_dir.exists():
                        candidates = list(bm25_dir.glob("kb_kb_*.json"))
                        if candidates:
                            import json as _json

                            scored: list[tuple[int, float, Path]] = []
                            for jf in candidates:
                                doc_count = 0
                                try:
                                    data = _json.loads(jf.read_text(encoding="utf-8"))
                                    docs = data.get("documents") or []
                                    if isinstance(docs, list):
                                        doc_count = len(docs)
                                except Exception:
                                    doc_count = 0
                                try:
                                    mtime = float(jf.stat().st_mtime)
                                except Exception:
                                    mtime = 0.0
                                scored.append((doc_count, mtime, jf))

                            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
                            best = scored[0][2]
                            bm25_pkl_path = str(best).replace(".json", ".pkl")
                            logger.info(
                                "md导出召回：使用BM25索引(按documents数优先): %s (documents=%d)",
                                best.name,
                                scored[0][0],
                            )
            except Exception as e:
                logger.warning("选择BM25索引失败，将继续尝试默认路径: %s", e, exc_info=True)

            if not bm25_pkl_path:
                # 兜底（可能不存在，但 BM25IndexBuilder 会自己检查 json 同名文件）
                bm25_pkl_path = "data/bm25_index/default.pkl"

            # 记录本次 md 导出实际使用的 BM25 路径，供后续 manifest 注入使用（闭包变量）
            nonlocal bm25_pkl_used_for_md_export
            bm25_pkl_used_for_md_export = bm25_pkl_path

            vector_builder = VectorIndexBuilder(
                collection_name=vector_collection_name,
                connection_manager=get_chroma_connection_manager(),
            )
            bm25_builder = BM25IndexBuilder(index_path=bm25_pkl_path)
            # metadata 表命名需与 collection 命名保持一致：
            # - 若 collection 为 kb_<id>_vector，则 metadata 表为 kb_<id>_metadata
            # - 否则回退到默认 document_chunks_metadata
            metadata_table_name = "document_chunks_metadata"
            if vector_collection_name and vector_collection_name.endswith("_vector"):
                metadata_table_name = vector_collection_name.replace("_vector", "_metadata")
            metadata_builder = MetadataIndexBuilder(
                table_name=metadata_table_name,
                connection_manager=get_sqlite_connection_manager(),
            )

            try:
                return HybridRetriever(
                    vector_index_builder=vector_builder,
                    bm25_index_builder=bm25_builder,
                    metadata_index_builder=metadata_builder,
                    llm_service=get_llm_service(),
                )
            except Exception as e:
                logger.warning("HybridRetriever 初始化失败，跳过召回填充: %s", e, exc_info=True)
                return None

        def _node_text(node) -> str:
            txt = getattr(node, "text", None)
            if isinstance(txt, str) and txt.strip():
                return txt.strip()
            get_content = getattr(node, "get_content", None)
            if callable(get_content):
                try:
                    c = get_content()
                    if isinstance(c, str) and c.strip():
                        return c.strip()
                except Exception:
                    pass
            return str(txt or "").strip()

        # 自动决定是否开启召回填充
        if retrieve is None:
            retrieve = _looks_like_outline_template(md_content)

        if retrieve:
            heading_items = _parse_md_headings(md_content)
            # 去掉文档标题（#）本身作为 section 的情况，只保留 ## 及以下作为章节
            chapter_items = [it for it in heading_items if int(it.get("heading_level") or 0) >= 2]
            if max_sections is not None:
                chapter_items = chapter_items[: max(0, int(max_sections))]

            retriever = _build_hybrid_retriever_for_md_export()
            if not retriever:
                logger.warning("md导出召回：检索器不可用，将直接按原 md 渲染")
                retrieve = False

        if not retrieve:
            # 纯 md → HTML：兼容已有行为
            draft = Draft(
                title=final_title,
                description=f"file: {md_file}",
                outline_id=outline_uuid,
                industry_id=outline_uuid,  # md 驱动导出场景下不需要真实 industry_id
                database_ids=[],
                status=DraftStatus.GENERATED,
                sections=[
                    DraftSection(
                        section_type=DraftSectionType.PARAGRAPH,
                        level=1,
                        title=None,
                        content=md_content,
                        order=0,
                    )
                ],
                metadata={
                    "outline_template_path": str(md_file),
                    "md_template_path": str(md_file),
                    "outline_id": str(outline_uuid),
                },
            )
        else:
            # md 模板 → 逐章召回填充 → Draft(section tree)
            # 说明：这里仅做“召回与摘录拼装”，不调用 LLM 润色/扩写（避免导出阶段引入不确定性）。
            draft = Draft(
                title=final_title,
                description=f"file: {md_file}",
                outline_id=outline_uuid,
                industry_id=outline_uuid,
                database_ids=[],
                status=DraftStatus.GENERATED,
                sections=[],
                metadata={
                    "outline_template_path": str(md_file),
                    "md_template_path": str(md_file),
                    "outline_id": str(outline_uuid),
                    "md_export_retrieve": True,
                    "md_export_retrieval_top_k": int(retrieval_top_k),
                },
            )

            # 用栈构建父子关系
            section_stack: list[tuple[int, uuid.UUID]] = []  # (heading_level, section_id)
            order = 0

            def _looks_like_structural_only(text: str) -> bool:
                """章节内容如果只有分隔线/标题/项目符号/空行，视作模板结构，允许触发召回覆盖。"""
                meaningful = 0
                for raw in (text or "").splitlines():
                    line = raw.strip()
                    if not line:
                        continue
                    if line == "---":
                        continue
                    if line.startswith("#"):
                        continue
                    if line.startswith(("-", "*")):
                        continue
                    meaningful += 1
                    if meaningful >= 2:
                        return False
                return True

            # doc_id -> filename/file_path cache（用于把 [来源:knowledge_base_service] 解析为真实文件名）
            doc_info_cache: dict[str, dict[str, str]] = {}

            def _lookup_document_info(document_id: str) -> dict[str, str]:
                if not document_id:
                    return {}
                if document_id in doc_info_cache:
                    return doc_info_cache[document_id]
                info: dict[str, str] = {}
                try:
                    from src.infrastructure.storage.sqlite.connection import get_connection_manager

                    cm = get_connection_manager()
                    with cm.get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT filename, file_path FROM documents WHERE id = ?",
                            (str(document_id),),
                        )
                        row = cur.fetchone()
                        if row:
                            filename = row[0] or ""
                            file_path = row[1] or ""
                            if filename:
                                info["filename"] = str(filename)
                            if file_path:
                                info["file_path"] = str(file_path)
                except Exception:
                    info = {}
                doc_info_cache[document_id] = info
                return info

            def _resolve_source_display(meta: dict, default_source_title: str | None) -> str:
                """尽量返回“原始文件名”，避免显示 knowledge_base_service 等内部标识。"""
                if not isinstance(meta, dict):
                    return default_source_title or "unknown"

                # 1) 明确字段优先
                for k in ("filename", "document_title_from_content", "document_title", "title"):
                    v = meta.get(k)
                    if isinstance(v, str) and v.strip():
                        return v.strip()

                # 2) file_path
                fp = meta.get("file_path")
                if isinstance(fp, str) and fp.strip():
                    try:
                        return Path(fp).name
                    except Exception:
                        return fp.strip()

                # 3) 用 document_id 查 documents 表（兜底）
                doc_id = meta.get("document_id")
                if isinstance(doc_id, str) and doc_id.strip():
                    info = _lookup_document_info(doc_id.strip())
                    if info.get("filename"):
                        return info["filename"]
                    if info.get("file_path"):
                        try:
                            return Path(info["file_path"]).name
                        except Exception:
                            return info["file_path"]

                # 4) 最后才用 source（很多情况下是内部标识）
                src = meta.get("source")
                if isinstance(src, str) and src.strip() and src.strip() != "knowledge_base_service":
                    try:
                        return Path(src.strip()).name
                    except Exception:
                        return src.strip()

                return "unknown"

            for it in chapter_items:
                order += 1
                heading_level = int(it.get("heading_level") or 2)
                sec_title = str(it.get("title") or "").strip()
                existing_content = str(it.get("content") or "").strip()

                # 父级：找到最近一个更高层级的标题作为 parent
                parent_id = None
                while section_stack and section_stack[-1][0] >= heading_level:
                    section_stack.pop()
                if section_stack:
                    parent_id = section_stack[-1][1]

                # 构建查询：尽量带上父标题，提升检索精度
                query = " ".join([p for p in [final_title, sec_title] if p])

                # 关键：模板 md 往往在标题下只有“项目符号/占位说明”，这种应视为“无正文”以触发召回填充
                content = existing_content
                if content and _looks_like_structural_only(content):
                    content = ""

                if not content:
                    try:
                        nodes = retriever.retrieve(query_str=query, top_k=int(retrieval_top_k))  # type: ignore[union-attr]
                    except Exception as e:
                        logger.warning("md导出召回失败: title=%s err=%s", sec_title, e, exc_info=True)
                        nodes = []

                    paras: list[str] = []
                    if nodes:
                        paras.append(f"（RAG/BM25 召回 Top{min(int(retrieval_top_k), len(nodes))} 片段摘录）")
                        for r in nodes[: int(retrieval_top_k)]:
                            node = getattr(r, "node", None)
                            meta = getattr(node, "metadata", {}) if node else {}
                            default_source_title = None
                            if isinstance(draft.metadata, dict):
                                default_source_title = cast("str | None", draft.metadata.get("default_source_title"))
                            src_name = _resolve_source_display(meta if isinstance(meta, dict) else {}, default_source_title)
                            snippet = _node_text(node)
                            if not snippet:
                                continue
                            snippet = snippet[:900].rstrip()
                            paras.append(f"{snippet}\n[来源:{src_name}]")
                    else:
                        paras.append("（未召回到相关内容片段）")
                    content = "\n\n".join([p for p in paras if p.strip()])

                section_id = uuid.uuid4()
                draft.add_section(
                    DraftSection(
                        id=section_id,
                        parent_id=parent_id,
                        section_type=DraftSectionType.SECTION,
                        # HTMLRenderer 会 +1，因此这里用 (heading_level - 1) 来对齐 md 的 ##/###
                        level=max(1, heading_level - 1),
                        title=sec_title,
                        content=content,
                        order=order,
                    )
                )
                section_stack.append((heading_level, section_id))

            # ---- 为 HTMLRenderer 的“严格补图”准备 rag_media_manifest（md 导出场景）----
            # 说明：
            # - md 导出检索模式下，我们当前不在正文里强行插入图片占位符（避免污染 md 模板本身）。
            # - 但 HTMLRenderer 在正文没有 [[IMAGE:...]] 时，会根据 draft.metadata.rag_media_manifest 自动补图。
            # - 因此这里根据召回节点的 metadata(images/charts) 汇总一个 manifest，保证离线 HTML 能嵌图。
            try:
                import json as _json

                seen_fig: set[str] = set()
                manifest: list[dict[str, Any]] = []

                # 复用“chapter_items 循环中最后一次 nodes”的变量不可靠，这里重新按章节遍历一次 section_materials 不存在，
                # 所以采用：直接从 draft.sections 内容里无法提取媒体；我们只能从 BM25 索引 JSON / Chroma metadata 中拿。
                # 这里退一步：从 bm25_index_json（或选中的 bm25_pkl_path 对应 json）读取 documents[*].metadata.images/charts。
                # 这在“md 导出 + 旧BM25索引”场景下最稳定。

                # 尝试定位 BM25 json
                bm25_json: Path | None = None
                if bm25_index_json:
                    p = Path(bm25_index_json)
                    if p.exists() and p.is_file():
                        bm25_json = p
                if bm25_json is None and bm25_pkl_used_for_md_export:
                    p = Path(str(bm25_pkl_used_for_md_export).replace(".pkl", ".json"))
                    if p.exists() and p.is_file():
                        bm25_json = p

                if bm25_json and bm25_json.exists():
                    data = _json.loads(bm25_json.read_text(encoding="utf-8"))
                    docs = data.get("documents") or []
                    if isinstance(docs, list):
                        for d in docs:
                            if not isinstance(d, dict):
                                continue
                            meta = d.get("metadata") or {}
                            if not isinstance(meta, dict):
                                continue
                            raw_images = meta.get("images")
                            images_meta: dict[str, Any] | None = None
                            if isinstance(raw_images, dict):
                                images_meta = raw_images
                            elif isinstance(raw_images, str) and raw_images.strip().startswith("{"):
                                try:
                                    parsed = _json.loads(raw_images)
                                    if isinstance(parsed, dict):
                                        images_meta = parsed
                                except Exception:
                                    images_meta = None
                            if images_meta:
                                files = images_meta.get("files") or []
                                if isinstance(files, list):
                                    for f in files:
                                        fn = Path(str(f)).name
                                        if not fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg")):
                                            continue
                                        if fn in seen_fig:
                                            continue
                                        seen_fig.add(fn)
                                        manifest.append(
                                            {
                                                "figure_name": fn,
                                                "original_uuid": fn,
                                                "json_file": f"{Path(fn).stem}.json",
                                                "source_file": Path(str(meta.get("file_path") or meta.get("source") or "")).name,
                                            }
                                        )
                if manifest and isinstance(draft.metadata, dict):
                    draft.metadata["rag_media_manifest"] = manifest
                    logger.info("md导出召回：已注入 rag_media_manifest: items=%d", len(manifest))
            except Exception as e:
                logger.warning("md导出召回：注入 rag_media_manifest 失败（容错，不影响导出）: %s", e, exc_info=True)

        return self.export_draft_to_html(
            draft=draft,
            output_dir=output_dir,
            filename=filename,
            datajson_dir=datajson_dir,
            include_appendix=include_appendix,
        )

    def _infer_default_source_title_from_datajson(self, datajson_path: Path | None) -> str | None:
        """从 datajson 目录推断“默认来源标题”（用于引用展示兜底）。

        典型路径：
        - data/cleaned/documents/<doc_dir>/<something>_extracted/datajson
        """
        if not datajson_path:
            return None
        try:
            p = Path(datajson_path).resolve()
        except Exception:
            p = Path(datajson_path)

        # 向上寻找 cleaned/documents/<doc_dir>
        parts = [x for x in p.parts]
        try:
            idx = parts.index("cleaned")
            # .../cleaned/documents/<doc_dir>/...
            if idx + 2 < len(parts) and parts[idx + 1] == "documents":
                doc_dir = parts[idx + 2]
                return self._clean_doc_dir_name(doc_dir)
        except ValueError:
            pass

        # 回退：如果在路径中看到类似 "<title>_86" 的目录名，也做一次去噪
        for seg in reversed(parts):
            cleaned = self._clean_doc_dir_name(seg)
            if cleaned and cleaned != seg:
                return cleaned
        return None

    def _clean_doc_dir_name(self, name: str) -> str:
        """清理 cleaned/documents 下的目录名噪音：去掉末尾计数/hash 等。"""
        import re

        s = (name or "").strip()
        if not s:
            return ""
        # 常见噪音：末尾 _86 / _77 / _e0 / _1b 等
        s = re.sub(r"_[0-9]{1,3}$", "", s)
        s = re.sub(r"_[0-9a-fA-F]{2}$", "", s)
        # 有时带“目录”字样
        s = re.sub(r"目录$", "", s)
        s = s.strip(" _-")
        return s

    def generate_html_content(
        self,
        draft_id: str | uuid.UUID | None = None,
        outline_id: str | uuid.UUID | None = None,
        draft: Draft | None = None,
        datajson_dir: str | Path | None = None,
        include_appendix: bool = True,
    ) -> str:
        """
        生成HTML内容（不写入文件）

        用于API返回或pytest测试，只返回HTML字符串，不写入文件。

        Args:
            draft_id: 草稿ID（可选）
            outline_id: 大纲ID（可选）
            draft: 草稿对象（可选）
            datajson_dir: datajson目录路径（可选）
            include_appendix: 是否包含附录数据表格（默认：True）

        Returns:
            HTML内容字符串

        Raises:
            ResourceNotFoundError: 如果草稿不存在
            ValidationError: 如果参数验证失败
        """
        try:
            logger.info(
                "开始生成HTML内容: draft_id=%s, outline_id=%s, include_appendix=%s",
                draft_id,
                outline_id,
                include_appendix,
            )

            # 1. 获取草稿
            logger.debug("步骤1: 获取草稿对象")
            if draft:
                target_draft = draft
                logger.debug("使用提供的草稿对象: draft_id=%s", draft.id)
            elif draft_id:
                logger.debug("根据draft_id获取草稿: draft_id=%s", draft_id)
                target_draft = self.draft_service.get_draft(draft_id)
                if not target_draft:
                    raise ResourceNotFoundError(f"草稿不存在: {draft_id}")
            elif outline_id:
                logger.debug("根据outline_id获取最新草稿: outline_id=%s", outline_id)
                # 使用 get_latest_draft_for_outline 确保获取最新草稿
                target_draft = self.draft_service.get_latest_draft_for_outline(outline_id)
                logger.debug(
                    "找到最新草稿: draft_id=%s, title='%s'",
                    target_draft.id,
                    target_draft.title,
                )
            else:
                logger.debug("获取最新草稿")
                drafts = self.draft_service.list_drafts()
                if not drafts:
                    raise ResourceNotFoundError(
                        "当前数据库中没有任何草稿记录(drafts 表为空)"
                    )
                target_draft = drafts[0]
                logger.debug(
                    "找到最新草稿: draft_id=%s, title='%s'",
                    target_draft.id,
                    target_draft.title,
                )

            logger.debug(
                "草稿获取成功: draft_id=%s, 章节数=%d",
                target_draft.id,
                len(target_draft.sections),
            )

            # 2. 确定datajson目录
            logger.debug("步骤2: 确定datajson目录")
            datajson_path = self._resolve_datajson_dir(datajson_dir)
            if datajson_path:
                logger.debug("使用datajson目录: %s", datajson_path)
            else:
                logger.debug("未找到datajson目录")

            # 3. 创建HTML渲染器
            logger.debug("步骤3: 创建HTML渲染器")
            if self.html_renderer is None:
                html_renderer = HTMLRenderer(datajson_base_dir=datajson_path)
            else:
                html_renderer = self.html_renderer

            # 4. 渲染HTML
            logger.debug("步骤4: 渲染HTML内容")
            html_content = html_renderer.render_draft_to_html(
                draft=target_draft,
                chart_configs=None,
                include_appendix=include_appendix,
            )

            logger.info(
                "HTML内容生成成功: draft_id=%s, 内容长度=%d字符",
                target_draft.id,
                len(html_content),
            )

            return html_content

        except ResourceNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "生成HTML内容失败: draft_id=%s, outline_id=%s, 错误=%s",
                draft_id,
                outline_id,
                e,
                exc_info=True,
            )
            msg = f"生成HTML内容失败: {e!s}"
            raise ValidationError(msg) from e

    def _resolve_datajson_dir(
        self, datajson_dir: str | Path | None, draft: Draft | None = None
    ) -> Path | None:
        """
        解析datajson目录路径

        Args:
            datajson_dir: 指定的datajson目录路径
            draft: 草稿对象（可选；用于根据 rag_media_manifest 选择最匹配的 datajson 目录）

        Returns:
            datajson目录路径，如果找不到则返回None
        """
        try:
            # 0) 若 draft.metadata 显式提供 datajson_dir，则优先使用（比“全盘扫描”更稳定）
            try:
                if (
                    draft
                    and isinstance(getattr(draft, "metadata", None), dict)
                    and isinstance(draft.metadata.get("datajson_dir"), str)
                ):
                    p = Path(str(draft.metadata.get("datajson_dir")))
                    if p.exists() and p.is_dir():
                        logger.info("使用 draft.metadata 指定的datajson目录: %s", p)
                        return p
            except Exception:
                pass

            if datajson_dir:
                datajson_path = Path(datajson_dir)
                if datajson_path.exists() and datajson_path.is_dir():
                    logger.debug("使用指定的datajson目录: %s", datajson_path)
                    return datajson_path
                else:
                    logger.warning(
                        "指定的datajson目录不存在或不是目录: %s", datajson_path
                    )

            # 0) 优先在“项目根目录”下查找（避免因 cwd 变化导致误用 Temp 目录）
            # - <repo>/datajson
            # - <repo>/data/output/final/datajson
            # - <repo>/data/output/final/**/datajson（兼容更深层结构）
            from src.shared.config.settings import _find_project_root

            project_root = _find_project_root()

            def _is_good_datajson_dir(p: Path) -> bool:
                if not (p.exists() and p.is_dir()):
                    return False
                # 尽量选择包含 JSON 的目录；若为空目录则继续回退
                try:
                    return any(p.glob("*.json"))
                except Exception:
                    return True

            def _extract_manifest_json_names() -> set[str]:
                names: set[str] = set()
                try:
                    if not draft or not isinstance(getattr(draft, "metadata", None), dict):
                        return names
                    manifest = draft.metadata.get("rag_media_manifest")
                    if not isinstance(manifest, list):
                        return names
                    for item in manifest:
                        if not isinstance(item, dict):
                            continue
                        jf = item.get("json_file")
                        if isinstance(jf, str) and jf.strip().lower().endswith(".json"):
                            names.add(Path(jf.strip()).name)
                except Exception:
                    return names
                return names

            def _extract_manifest_image_names() -> set[str]:
                names: set[str] = set()
                try:
                    if not draft or not isinstance(getattr(draft, "metadata", None), dict):
                        return names
                    manifest = draft.metadata.get("rag_media_manifest")
                    if not isinstance(manifest, list):
                        return names
                    for item in manifest:
                        if not isinstance(item, dict):
                            continue
                        ou = item.get("original_uuid")
                        if not isinstance(ou, str):
                            continue
                        ou_name = Path(ou.strip()).name
                        if ou_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")):
                            names.add(ou_name)
                except Exception:
                    return names
                return names

            manifest_json_names = _extract_manifest_json_names()
            manifest_image_names = _extract_manifest_image_names()

            def _score_candidate(p: Path) -> tuple[int, int, int]:
                """
                返回 (match_json_count, match_image_count, total_json_count)
                match_count: 该 datajson 目录中包含多少 manifest 指定的 json_file
                """
                try:
                    json_files = {x.name for x in p.glob("*.json")}
                    match = len(manifest_json_names.intersection(json_files)) if manifest_json_names else 0
                    # image 匹配度：datajson 同级 images/ 或 datajson/images/
                    img_match = 0
                    if manifest_image_names:
                        img_dir = None
                        for cand in [p / "images", p.parent / "images"]:
                            if cand.exists() and cand.is_dir():
                                img_dir = cand
                                break
                        if img_dir:
                            present = {x.name for x in img_dir.iterdir() if x.is_file()}
                            img_match = len(manifest_image_names.intersection(present))
                    return match, img_match, len(json_files)
                except Exception:
                    return 0, 0, 0

            # 注意：output/final 是导出目标目录，不应作为“源 datajson”的优先候选，否则会把不完整的 images 带进来。
            # 若用户确实想用 output/final/datajson，请显式传入 --datajson-dir。
            project_candidates: list[Path] = [project_root / "datajson"]
            for candidate in project_candidates:
                if _is_good_datajson_dir(candidate):
                    # 若 manifest 已知，优先选择与其更匹配的目录；否则沿用旧逻辑（第一个可用）
                    if manifest_json_names:
                        match, img_match, total = _score_candidate(candidate)
                        if match > 0:
                            logger.info(
                                "自动找到datajson目录(项目根优先+manifest匹配): %s (json_match=%d, img_match=%d, total_json=%d)",
                                candidate,
                                match,
                                img_match,
                                total,
                            )
                            return candidate
                    logger.info("自动找到datajson目录(项目根优先): %s", candidate)
                    return candidate

            # 尝试自动查找datajson目录
            # 查找 data/cleaned/documents/*/datajson/ 目录
            logger.debug("尝试自动查找datajson目录")
            try:
                config = get_config()
                cleaned_docs_dir = config.data_dir / "cleaned" / "documents"
                if cleaned_docs_dir.exists():
                    # 查找所有datajson目录
                    datajson_dirs = list(cleaned_docs_dir.rglob("datajson"))
                    if datajson_dirs:
                        if manifest_json_names:
                            # 按匹配度选择最优 datajson 目录
                            best_dir: Path | None = None
                            best_score: tuple[int, int, int] | None = None
                            for d in datajson_dirs:
                                if not _is_good_datajson_dir(d):
                                    continue
                                score = _score_candidate(d)
                                if best_score is None or score > best_score:
                                    best_score = score
                                    best_dir = d
                            if best_dir is not None:
                                logger.info(
                                    "自动找到datajson目录(清洗目录扫描+manifest匹配): %s (json_match=%d, img_match=%d, total_json=%d, candidates=%d)",
                                    best_dir,
                                    best_score[0] if best_score else 0,  # json_match
                                    best_score[1] if best_score else 0,  # img_match
                                    best_score[2] if best_score else 0,  # total_json
                                    len(datajson_dirs),
                                )
                                return best_dir
                        # 兜底：使用第一个找到的datajson目录
                        logger.info(
                            "自动找到datajson目录: %s (共找到%d个)",
                            datajson_dirs[0],
                            len(datajson_dirs),
                        )
                        return datajson_dirs[0]
                    else:
                        logger.debug(
                            "在 %s 下未找到datajson目录", cleaned_docs_dir
                        )
                else:
                    logger.debug("cleaned文档目录不存在: %s", cleaned_docs_dir)
            except Exception as e:
                logger.warning("自动查找datajson目录失败: %s", e, exc_info=True)

            # 最末兜底：输出目录扫描（用于“只剩导出产物”的场景）
            deep_candidate_root = project_root / "data" / "output" / "final"
            if deep_candidate_root.exists():
                best: tuple[int, int, int] | None = None
                best_path: Path | None = None
                for candidate in deep_candidate_root.rglob("datajson"):
                    if not _is_good_datajson_dir(candidate):
                        continue
                    if not manifest_json_names:
                        logger.info("自动找到datajson目录(输出目录兜底扫描): %s", candidate)
                        return candidate
                    score = _score_candidate(candidate)
                    if best is None or score > best:
                        best = score
                        best_path = candidate
                if best_path is not None:
                    logger.info(
                        "自动找到datajson目录(输出目录兜底扫描+manifest匹配): %s (json_match=%d, img_match=%d, total_json=%d)",
                        best_path,
                        best[0] if best else 0,
                        best[1] if best else 0,
                        best[2] if best else 0,
                    )
                    return best_path

            logger.debug("未找到datajson目录")
            return None

        except Exception as e:
            logger.error(
                "解析datajson目录路径失败: datajson_dir=%s, 错误=%s",
                datajson_dir,
                e,
                exc_info=True,
            )
            return None

    def _slugify(self, value: str, max_len: int = 60) -> str:
        """
        将字符串转换为文件名安全的格式

        Args:
            value: 原始字符串
            max_len: 最大长度

        Returns:
            文件名安全的字符串
        """
        v = (value or "").strip()
        # Windows 文件名安全化（先处理系统禁止字符）
        v = re.sub(r'[<>:"/\\|?*]+', "-", v)
        # 进一步清理：避免把 dict/JSON 字符串直接带进文件名（例如 "{'id':...,'name':...}"）
        # 允许：中文、英文、数字、下划线、连字符、点号
        v = re.sub(r"[^\w\u4e00-\u9fff\.\-]+", "_", v, flags=re.UNICODE)
        v = re.sub(r"_+", "_", v).strip("_")
        if len(v) > max_len:
            v = v[:max_len].rstrip("_-")
        return v or "draft"


def get_html_export_service() -> HTMLExportService:
    """
    获取HTML导出服务实例（用于依赖注入）

    Returns:
        HTMLExportService: HTML导出服务实例
    """
    return HTMLExportService()

