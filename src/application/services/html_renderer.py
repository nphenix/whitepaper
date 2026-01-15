"""
HTML渲染器服务

该模块实现草稿到HTML的转换功能,支持图表渲染和附录数据展示.
用于T174任务:图表集成到HTML交付物.

生成命令: /speckit.implement T174
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
import re
import uuid
from pathlib import Path
from typing import Any

import markdown
from markdown.extensions import codehilite, fenced_code, tables

from src.domain.agent.chart_config import ChartConfig, ChartType
from src.domain.agent.draft import Draft, DraftSection
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)

# 延迟导入,避免循环依赖
_table_renderer: Any = None


def _get_table_renderer() -> Any:
    """获取表格渲染器实例(延迟导入)"""
    global _table_renderer
    if _table_renderer is None:
        from src.application.services.table_renderer import TableRenderer

        _table_renderer = TableRenderer()
    return _table_renderer


def _extract_subsections_from_md_template(draft: Draft) -> list[dict[str, str]]:
    """
    从md模板中提取子章节（带缩进的标题行）
    
    支持多种md大纲格式：
    - 标准markdown: "    1.1 xxx" (4空格缩进)
    - 制表符缩进: "\t1.1 xxx"
    - 纯文本编号: "1.1 xxx" (无缩进但有编号)
    
    Args:
        draft: 草稿对象
        
    Returns:
        子章节列表，每个元素包含 {number, title, level, indent}
    """
    import re
    from pathlib import Path
    
    subsections: list[dict[str, str]] = []
    
    # 1. 尝试从metadata获取md模板路径
    md_template_path = None
    if isinstance(draft.metadata, dict):
        md_template_path = draft.metadata.get("outline_template_path") or draft.metadata.get("md_template_path")
    
    # 2. 如果metadata中没有，尝试从description提取
    if not md_template_path and draft.description:
        # description中可能包含 "file: xxx.md" 格式
        match = re.search(r'file[:：]\s*(.+\.md)', draft.description)
        if match:
            md_template_path = match.group(1).strip()
    
    # 3. 尝试在常见位置查找md模板
    candidate_paths = []
    if md_template_path:
        candidate_paths.append(Path(md_template_path))
    
    # 添加常见路径
    if isinstance(draft.metadata, dict):
        outline_id = draft.metadata.get("outline_id")
        if outline_id:
            candidate_paths.append(Path(__file__).parent.parent.parent.parent / "data" / "output" / "drafts" / f"outline_template_{outline_id}.md")
    
    # 从draft.description提取outline_id
    if not candidate_paths and draft.description:
        outline_match = re.search(r'([0-9a-fA-F-]{36})', draft.description) or re.search(r'outline_template_([0-9a-fA-F-]{8}-[0-9a-fA-F-]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F-]{4}-[0-9a-fA-F]{12})', draft.description)
        if outline_match:
            candidate_paths.append(Path(__file__).parent.parent.parent.parent / "data" / "output" / "drafts" / f"outline_template_{outline_match.group(1)}.md")
    
    # 4. 读取并解析md内容
    md_content = None
    for md_path in candidate_paths:
        try:
            if md_path.exists():
                with open(md_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                logger.debug("找到md模板: %s", md_path)
                break
        except Exception as e:
            logger.warning("读取md模板失败: %s, error=%s", md_path, e)
    
    if not md_content:
        # 容错：从data/output/drafts目录查找最新的md文件
        drafts_dir = Path(__file__).parent.parent.parent.parent / "data" / "output" / "drafts"
        if drafts_dir.exists():
            md_files = list(drafts_dir.glob("outline_template_*.md"))
            if md_files:
                try:
                    md_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                    with open(md_files[0], 'r', encoding='utf-8') as f:
                        md_content = f.read()
                    logger.debug("使用最新的md模板: %s", md_files[0])
                except Exception as e:
                    logger.warning("读取最新md模板失败: %s, error=%s", md_files[0], e)
    
    if not md_content:
        logger.debug("未找到md模板，跳过子章节补充")
        return []
    
    # 5. 解析md内容，提取子章节
    subsections = _parse_subsections_from_content(md_content)
    logger.info("从md模板提取子章节: %d个", len(subsections))
    
    return subsections


def _parse_subsections_from_content(md_content: str) -> list[dict[str, str]]:
    """
    从md内容中解析子章节
    
    支持格式：
    - 缩进子章节: "    1.1 xxx" 或 "\t1.1 xxx"
    - 无缩进但有编号: "1.1 xxx" (视为子章节)
    
    Args:
        md_content: md文件内容
        
    Returns:
        子章节列表
    """
    import re
    subsections: list[dict[str, str]] = []
    
    # 提取所有行
    lines = md_content.split('\n')
    
    for line in lines:
        stripped = line.strip()
        
        # 跳过空行和已经是markdown标题的行（以#开头）
        if not stripped or stripped.startswith('#'):
            continue
        
        # 计算缩进（空格数）
        leading_spaces = len(line) - len(line.lstrip())
        has_tab = '\t' in line and line.find('\t') < leading_spaces
        
        # 判断是否为子章节行
        # 条件1: 4空格以上缩进
        # 条件2: 缩进+制表符
        # 条件3: 无缩进但匹配编号格式（如 "1.1 xxx"）
        is_subsection = False
        
        if leading_spaces >= 4 or has_tab:
            is_subsection = True
        else:
            # 无缩进但有编号（如 "1.1 xxx"）也视为子章节
            # 匹配 "数字.数字 xxx" 格式
            subsection_pattern = r'^(\d+\.\d+[\.\d]*)\s+(.+)$'
            if re.match(subsection_pattern, stripped):
                is_subsection = True
                leading_spaces = 0  # 无缩进
        
        if is_subsection:
            # 提取编号和标题
            # 优先匹配 "1.1.1 xxx" 格式（多级编号）
            multi_level_pattern = r'^(\d+\.\d+\.\d+[\.\d]*)\s+(.+)$'
            match = re.match(multi_level_pattern, stripped)
            
            if not match:
                # 降级匹配 "1.1 xxx" 格式
                subsection_pattern = r'^(\d+\.\d+[\.\d]*)\s+(.+)$'
                match = re.match(subsection_pattern, stripped)
            
            if match:
                number = match.group(1)
                title = match.group(2).strip()
                
                # 清理标题（去除markdown格式符号）
                title = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', title)  # 清理链接
                title = re.sub(r'\*\*([^*]+)\*\*', r'\1', title)  # 清理粗体
                title = re.sub(r'\*([^*]+)\*', r'\1', title)  # 清理斜体
                
                # 根据缩进计算层级（2空格=1级）
                level = max(3, 3 + (leading_spaces // 4))
                
                subsections.append({
                    'number': number,
                    'title': title,
                    'level': level,
                    'indent': leading_spaces
                })
    
    # 统计层级分布
    level_counts: dict[int, int] = {}
    for sub in subsections:
        level = sub['level']
        level_counts[level] = level_counts.get(level, 0) + 1
    
    if subsections:
        logger.debug("子章节层级分布: %s", level_counts)
    
    return subsections


class HTMLRenderer:
    """
    HTML渲染器

    将草稿转换为HTML格式,支持:
    - Markdown内容转换为HTML
    - 图表占位符替换为ECharts图表
    - 附录数据表格展示
    - 离线可用的单文件HTML(内嵌ECharts脚本)
    """

    def __init__(self, datajson_base_dir: str | Path | None = None):
        """
        初始化HTML渲染器

        Args:
            datajson_base_dir: datajson目录的基础路径,用于查找图表JSON文件
        """
        self.datajson_base_dir = (
            Path(datajson_base_dir) if datajson_base_dir else None
        )

        # 配置Markdown解析器
        self.md = markdown.Markdown(
            extensions=[
                "tables",  # 表格支持
                "codehilite",  # 代码高亮
                "fenced_code",  # 代码块
                # 注意：不要启用 nl2br
                # - nl2br 会把“普通换行”转换为 <br/>，导致同一段落内出现硬换行
                # - 由于我们的正文使用 text-indent 做首行缩进，<br/> 后的行不会缩进，
                #   视觉上就会出现你反馈的“段落缩进不统一/排版混乱”
                # 正确做法：依赖 Markdown 默认规则（单换行视为“空格”，空行才分段）。
            ],
        )

        logger.debug(f"初始化 {self.__class__.__name__}")

    def render_draft_to_html(
        self,
        draft: Draft,
        chart_configs: list[ChartConfig] | None = None,
        include_appendix: bool = True,
    ) -> str:
        """
        将草稿渲染为HTML格式

        Args:
            draft: 草稿领域模型对象
            chart_configs: 图表配置列表,如果为None则尝试从草稿内容中提取占位符
            include_appendix: 是否包含附录数据表格

        Returns:
            完整的HTML字符串

        Raises:
            Exception: 如果渲染失败
        """
        try:
            logger.info(
                "开始渲染草稿为HTML: draft_id=%s, title='%s', 章节数=%d",
                draft.id,
                draft.title,
                len(draft.sections),
            )

            # 0. 预处理：按交付物要求过滤不需要的章节
            # - “图转Json呈现”类附录：避免直接贴 raw JSON（交付物将用 datajson 附录表格展示）
            #
            # 注意：不要过滤“摘要”章节。
            # 用户提供的 MD 结构通常是：
            #   ## 摘要
            #   ### 核心观点与关键发现
            #   ### 主要政策建议概览
            #   ### 未来五年发展前景研判
            # 之前过滤掉“摘要”会导致这三个子章节 parent_id 指向被过滤节点，最终被当作“孤儿章节”
            # 追加到文末（看起来像跑到附录里），造成结构混乱。
            # - “图转Json呈现”类附录：避免直接贴 raw JSON（交付物将用 datajson 附录表格展示）
            abstract_html = ""
            main_content_html = ""

            def _should_skip_section(section: DraftSection) -> bool:
                if not section.title:
                    return False
                t = section.title.strip()
                # raw JSON 附录类
                # 兼容大小写/全角
                if "图转json" in t.lower() or "图转Json" in t or "图转JSON" in t or "图转Json呈现" in t:
                    return True
                return False

            def _is_abstract_title(title: str | None) -> bool:
                """判断是否属于“摘要”树（用于仅保留结构/标题但隐藏正文内容）。"""
                if not title:
                    return False
                t = title.strip()
                return (
                    "执行摘要" in t
                    or "内容摘要" in t
                    or t == "摘要"
                    or t.endswith("摘要")
                )

            # 获取所有section，按层级排序（先 level 再 order，后续会在树渲染里修正 root 顺序）
            sorted_sections = sorted(draft.sections, key=lambda s: (s.level, s.order))
            filtered_sections = [s for s in sorted_sections if not _should_skip_section(s)]

            # 旧逻辑：把摘要章节单独样式化展示（当前交付物不需要摘要，因此禁用）
            abstract_section = None
            non_abstract_sections = filtered_sections

            # 摘要内容展示策略（默认：仅保留“摘要”结构与标题，不展示其正文内容）
            # 原因：摘要往往在正文尚未完全生成前就被生成，容易与最终正文不一致。
            # 但用户仍希望“核心观点与关键发现/主要政策建议概览/未来五年发展前景研判”等结构出现在文首。
            section_by_id: dict[uuid.UUID, DraftSection] = {s.id: s for s in non_abstract_sections if getattr(s, "id", None)}
            abstract_root_ids: set[uuid.UUID] = {s.id for s in non_abstract_sections if _is_abstract_title(s.title)}

            def _is_in_abstract_tree(section: DraftSection) -> bool:
                """section 是否位于任一摘要根节点之下（含自身）。"""
                sid = getattr(section, "id", None)
                if not isinstance(sid, uuid.UUID):
                    return False
                cur: uuid.UUID | None = sid
                # 避免异常循环
                guard = 0
                while cur and guard < 50:
                    if cur in abstract_root_ids:
                        return True
                    parent_id = section_by_id.get(cur).parent_id if cur in section_by_id else None
                    cur = parent_id if isinstance(parent_id, uuid.UUID) else None
                    guard += 1
                return False
            
            # 1. 将草稿内容转换为Markdown
            logger.debug("步骤1: 提取草稿内容为Markdown")
            
            # 不再输出摘要（abstract_html 保持为空）
            
            # 构建非摘要部分的markdown（保持章节的层级关系和父子结构）
            # 先构建章节树，然后递归渲染，确保子章节在父章节之后
            root_sections = [s for s in non_abstract_sections if s.parent_id is None]
            # root 内部顺序：优先 order，其次 level（避免“先按 level 排序”导致章节顺序错乱）
            root_sections = sorted(root_sections, key=lambda s: (s.order, s.level))
            
            # 用于跟踪已渲染的章节，避免重复
            rendered_section_ids: set[str] = set()
            
            def render_section_recursive(section: DraftSection, computed_level: int) -> list[str]:
                """递归渲染章节（层级由父子关系计算，避免 section.level 数据不可靠导致子标题大于父标题）"""
                # 检查是否已渲染（避免重复）
                section_id_str = str(section.id)
                if section_id_str in rendered_section_ids:
                    return []
                rendered_section_ids.add(section_id_str)
                
                parts = []
                if section.title:
                    # +1 确保正文至少是 ##（因为文档标题是 #）
                    prefix = "#" * min(max(int(computed_level) + 1, 2), 6)
                    parts.append(f"{prefix} {section.title}\n")
                # 摘要树下默认不展示正文内容（只展示标题/结构）
                if section.content and (not _is_in_abstract_tree(section)):
                    # 修正模型可能生成的“素材N”引用：若章节 metadata 中携带了 material_source_map，则替换为真实文件名
                    content = section.content
                    try:
                        if isinstance(section.metadata, dict):
                            msm = section.metadata.get("material_source_map")
                            if isinstance(msm, dict) and msm:
                                def _repl(m: re.Match) -> str:
                                    n = m.group(1)
                                    src = msm.get(f"素材{n}") or msm.get(n) or f"素材{n}"
                                    return f"[来源:{src}]"

                                content = re.sub(r"\[来源[:：]\s*素材(\d+)\s*\]", _repl, content)
                    except Exception:
                        pass
                    parts.append(f"{content}\n")
                
                # 渲染子章节
                children = [s for s in non_abstract_sections if s.parent_id == section.id]
                children = sorted(children, key=lambda s: (s.order, s.level))
                for child in children:
                    parts.extend(render_section_recursive(child, computed_level + 1))
                
                return parts
            
            main_markdown_parts = []
            for root_section in root_sections:
                main_markdown_parts.extend(render_section_recursive(root_section, 1))

            # 容错：如果存在“孤儿章节”（parent_id 指向不存在/被过滤章节），也要保证不丢失
            orphan_sections = [
                s for s in non_abstract_sections if str(s.id) not in rendered_section_ids
            ]
            if orphan_sections:
                orphan_sections = sorted(orphan_sections, key=lambda s: (s.order, s.level))
                logger.warning(
                    "检测到未被渲染的章节(可能为孤儿节点)，将追加渲染以避免子章节丢失: count=%d",
                    len(orphan_sections),
                )
                for s in orphan_sections:
                    # 对孤儿节点：尽量尊重其自带 level，但仍做合理下限
                    try:
                        base_level = max(1, int(getattr(s, "level", 1) or 1))
                    except Exception:
                        base_level = 1
                    main_markdown_parts.extend(render_section_recursive(s, base_level))
            
            markdown_content = "\n\n".join(main_markdown_parts)
            logger.debug("Markdown内容长度: %d字符", len(markdown_content))

            # 1.15 统一图片引用格式：把 Markdown 图片语法 ![](images/xxx) 转为 [[IMAGE:xxx]]
            # 目的：
            # - 走同一套“manifest 映射/离线 images 目录”逻辑，避免图片链接断裂
            # - referenced_figures/附录依赖 [[IMAGE:...]] 才能识别“正文引用过的图”
            try:
                md_img_pattern = re.compile(r"!\[[^\]]*\]\((?:images/)?([^)]+)\)")
                markdown_content = md_img_pattern.sub(r"[[IMAGE:\1]]", markdown_content)
            except Exception:
                pass

            # 1.2 轻量规范化 Markdown：确保“列表/表格”能被 Markdown 正确识别为块级结构
            # 常见问题：
            # - 章节内容里直接写了 `- item` 或 `| a | b |`，但前一行不是空行，python-markdown 会把它当成普通段落文本
            #   → 结果就是你截图里的“列表/表格像纯文本一样堆在一起”
            # 这里做一个非常保守的修复：在需要的地方自动补空行，不改变正文语义。
            def _normalize_block_markdown(md: str) -> str:
                import re

                lines = md.splitlines()
                out: list[str] = []

                in_fence = False
                fence_pat = re.compile(r"^\s*(```|~~~)")

                def _is_blank(s: str) -> bool:
                    return not s.strip()

                def _is_heading(s: str) -> bool:
                    return bool(re.match(r"^\s*#{1,6}\s+", s))

                def _is_list_item(s: str) -> bool:
                    # unordered: -, *, +
                    # ordered: 1. 2)
                    return bool(re.match(r"^\s*(?:[-*+]|(\d+[\.\)]))\s+\S+", s))

                def _is_table_line(s: str) -> bool:
                    ss = s.lstrip()
                    # markdown table row typically starts with | and contains another |
                    return ss.startswith("|") and ss.count("|") >= 2

                def _prev_line() -> str:
                    return out[-1] if out else ""

                for line in lines:
                    if fence_pat.match(line):
                        in_fence = not in_fence
                        out.append(line)
                        continue
                    if in_fence:
                        out.append(line)
                        continue

                    # 在 list/table 之前补空行（如果上一行不是空行且也不是同类块）
                    prev = _prev_line()
                    if (not _is_blank(prev)) and (not _is_heading(prev)):
                        if _is_table_line(line) and (not _is_table_line(prev)):
                            out.append("")
                        elif _is_list_item(line) and (not _is_list_item(prev)):
                            out.append("")

                    out.append(line)

                return "\n".join(out)

            markdown_content = _normalize_block_markdown(markdown_content)

            # 1.4.5 清理“伪表格行”（标题/章节被写成只有第一列有内容的表格行）
            # 典型坏例子（会撑爆“序号”列宽度，并把后续章节也吞进表格里）：
            # | **表C.1-2 ...** |  |  |
            # | #### C.2 ...    |  |  |
            try:
                markdown_content = self._sanitize_markdown_table_pseudo_rows(markdown_content)
            except Exception as e:
                logger.warning("表格伪行清洗失败（容错处理）: %s", e, exc_info=True)

            # 1.5 不再“从 md 模板补齐子章节”
            # 说明：
            # - 该补齐逻辑历史上会误判父章节（如把 "1" 误匹配到 "2.1"），并将子标题直接追加到文末，
            #   导致交付物末尾出现一串孤儿小标题（你反馈的问题1）。
            # - 正确的做法应在生成阶段把小节内容写出来；交付物渲染阶段不再做猜测性补齐。

            # 1.6 补充图片占位符（如果正文中没有图片引用）
            # 当draft中没有[[IMAGE:xxx]]占位符时，从rag_media_manifest中获取图片并智能插入
            try:
                image_placeholder_pattern = r'\[\[IMAGE:[^\]]+\]\]'
                has_image_placeholders = bool(re.search(image_placeholder_pattern, markdown_content))
                
                if not has_image_placeholders:
                    # 尝试补充图片占位符
                    markdown_content = self._supplement_image_placeholders(markdown_content, draft)
            except Exception as e:
                logger.warning("补充图片占位符失败（容错处理）: %s", e, exc_info=True)

            # 1.7 参考文献“清洗”：仅保留标题，移除 (未知位置) 与本地路径等噪声
            # 说明：
            # - 旧草稿可能在正文末尾直接写入了 "1. 标题 (未知位置) - data/cleaned/.../clean.md"
            # - 导出阶段不应暴露本地路径/中间产物；交付物只需展示文献标题即可
            try:
                markdown_content = self._sanitize_reference_section(markdown_content)
            except Exception as e:
                logger.warning("参考文献清洗失败（容错处理）: %s", e, exc_info=True)

            # 2. 将Markdown转换为HTML
            logger.debug("步骤2: 将Markdown转换为HTML")
            main_html_body = self._markdown_to_html(markdown_content)
            logger.debug("HTML正文长度: %d字符", len(main_html_body))

            # 3. 替换图表占位符
            logger.debug("步骤3: 提取和替换图表与图片占位符")
            if chart_configs is None:
                chart_configs = self._extract_chart_configs_from_draft(draft)
                logger.info("从草稿中提取图表配置: 图表数=%d", len(chart_configs))
            else:
                logger.info("使用提供的图表配置: 图表数=%d", len(chart_configs))

            main_html_body = self._replace_chart_placeholders(main_html_body, chart_configs)
            
            # 3.5 替换图片占位符（传入draft以获取manifest映射）
            main_html_body = self._replace_image_placeholders(main_html_body, draft=draft)
            logger.debug("图表与图片占位符替换完成")

            # 4. 组合HTML：摘要在前，正文在后
            html_body = f"{abstract_html}\n{main_html_body}" if abstract_html else main_html_body

            # 5. 生成完整的HTML文档
            logger.debug("步骤5: 生成完整HTML文档")
            
            # 提取“正文中引用的图表/图片”，用于附录显示
            # 注意：正文图片占位符可能是在本次渲染过程中动态补齐的（不一定写回 draft.sections），
            # 因此这里以 markdown_content 为准进行提取，保证“插图/附录”一致。
            referenced_figures: set[str] = set()
            referenced_figures_order: list[str] = []
            try:
                pattern = r"\[\[IMAGE:(?:images/)?([^\]]+)\]\]"
                seen_order: set[str] = set()
                for match in re.finditer(pattern, markdown_content or ""):
                    m = match.group(1)
                    if not m:
                        continue
                    name = m.strip()
                    if not name:
                        continue
                    referenced_figures.add(name)
                    if name not in seen_order:
                        referenced_figures_order.append(name)
                        seen_order.add(name)
            except Exception:
                referenced_figures = self._extract_referenced_figures_from_draft(draft)
                referenced_figures_order = list(referenced_figures)
            
            # 生成“附录：图表数据”
            # 说明：draft 里可能本身就含有“附录/图转Json”等章节，但这些不一定符合交付要求，
            # 且我们在前面会过滤掉 raw JSON 附录章节。因此这里不再用“是否存在附录章节”来阻止生成。
            appendix_html = (
                self._generate_appendix_html(draft, referenced_figures, referenced_figures_order)
                if include_appendix
                else ""
            )
            
            html_doc = self._generate_html_document(
                title=draft.title,
                description=draft.description,
                body=html_body,
                chart_configs=[],
            )
            if appendix_html:
                html_doc = html_doc.replace("</main>", f"</main>{appendix_html}", 1)

            logger.info(
                "草稿渲染为HTML完成: draft_id=%s, HTML长度=%d字符, 图表数=%d",
                draft.id,
                len(html_doc),
                len(chart_configs) if chart_configs else 0,
            )

            # 6. 重新编号图表（确保正文和附录使用一致的编号）
            logger.debug("步骤6: 重新编号图表")
            html_doc = self._renumber_figures_in_html(html_doc)

            return html_doc

        except Exception as e:
            logger.error(
                "渲染草稿为HTML失败: draft_id=%s, title='%s', 错误=%s",
                draft.id,
                draft.title,
                e,
                exc_info=True,
            )
            raise

    def _sanitize_reference_section(self, markdown_content: str) -> str:
        """
        清洗“参考文献”段落的每条引用项，确保交付物仅展示标题，
        不展示(未知位置)/本地路径(clean.md/pdf等)。

        仅在检测到参考文献段落后对后续行做处理，避免误伤正文。
        """
        if not markdown_content:
            return markdown_content

        lines = markdown_content.splitlines()
        in_refs = False

        # 参考文献段落起始标识（markdown粗体/标题/纯文本）
        refs_start_pat = re.compile(
            r"^\s*(\*\*参考文献[:：]\*\*|#+\s*参考文献\s*[:：]?\s*$|参考文献\s*[:：]\s*$)"
        )

        # 用于识别“本地路径”尾巴（命中才会裁掉）
        path_tail_markers = (
            " - data/cleaned/",
            " - data\\cleaned\\",
            " - storage/",
            " - storage\\",
            " - f:\\",
            " - f:/",
        )

        # 尾部 location 括号（在裁掉路径后再尝试移除）
        location_tail_pat = re.compile(
            r"\s*\((?:未知位置|第?\s*\d+\s*页|页码\s*\d+|段落\s*\d+|行\s*\d+|p\.?\s*\d+)[^)]*\)\s*$"
        )

        def _strip_local_path_tail(s: str) -> str:
            lower = s.lower()
            for marker in path_tail_markers:
                idx = lower.find(marker)
                if idx >= 0:
                    return s[:idx].rstrip()
            return s

        def _sanitize_one_line(raw: str) -> str:
            stripped = raw.strip()
            if not stripped:
                return raw

            # 只处理“看起来像引用条目”的行（编号/列表项）
            if not re.match(r"^\s*(?:[-*+]\s+)?\d+[\.\)]\s+\S+", raw):
                return raw

            # 保留行首缩进与列表前缀（例如 "1. " / "- 1. "）
            m = re.match(r"^(\s*(?:[-*+]\s+)?(?:\d+[\.\)]\s+))", raw)
            prefix = m.group(1) if m else ""
            rest = raw[len(prefix) :] if prefix else raw

            # 1) 先裁掉本地路径尾巴（只有命中 marker 才裁）
            rest2 = _strip_local_path_tail(rest)

            # 2) 再移除尾部 location 括号（仅限典型 location 格式）
            rest2 = location_tail_pat.sub("", rest2).rstrip()

            # 3) 再兜底：若仍存在 " (未知位置)" 且在末尾，移除
            rest2 = re.sub(r"\s*\(未知位置\)\s*$", "", rest2).rstrip()

            if not rest2.strip():
                return raw
            return f"{prefix}{rest2}".rstrip()

        for i, line in enumerate(lines):
            if (not in_refs) and refs_start_pat.match(line.strip()):
                in_refs = True
                continue

            if in_refs:
                # 参考文献一般在文末；遇到新大标题可以退出（保守）
                if re.match(r"^\s*#\s+\S+", line) and not refs_start_pat.match(
                    line.strip()
                ):
                    in_refs = False
                    continue
                lines[i] = _sanitize_one_line(line)

        return "\n".join(lines)

    def _sanitize_markdown_table_pseudo_rows(self, markdown_content: str) -> str:
        """
        将“只有第一列有内容，其余列为空”的表格行，从表格中剥离出来，恢复为普通段落/标题行。

        目的：
        - 避免长标题行被当作表格第一列内容，导致“序号列”被撑得很宽
        - 避免后续章节标题（#### / ###）被吞进表格，破坏排版
        """
        if not markdown_content:
            return markdown_content

        out: list[str] = []
        for raw in markdown_content.splitlines():
            line = raw.rstrip("\n")
            s = line.strip()

            # 只处理“像表格行”的行
            if not (s.startswith("|") and s.count("|") >= 2):
                out.append(line)
                continue

            # 分割单元格（去掉首尾空单元）
            parts = [p.strip() for p in s.strip("|").split("|")]
            if len(parts) < 2:
                out.append(line)
                continue

            first = parts[0]
            rest = parts[1:]
            if not first:
                out.append(line)
                continue

            # 仅当“后续列全部为空”时，判为伪行
            if any(cell for cell in rest):
                out.append(line)
                continue

            # 识别伪行内容：表标题/章节标题/markdown标题
            # - **表C.1-2 ...**
            # - #### C.2 ...
            # - ### D. ...
            is_caption = bool(re.match(r"^\*{0,2}表[\w\.\-]*", first))
            is_heading = bool(re.match(r"^#{2,6}\s+\S+", first))
            if not (is_caption or is_heading):
                out.append(line)
                continue

            # 输出为普通行，并在前后补空行，确保表格正确闭合/段落分隔
            if out and out[-1].strip():
                out.append("")
            out.append(first)
            out.append("")

        return "\n".join(out)

    def _supplement_image_placeholders(self, markdown_content: str, draft: Draft) -> str:
        """
        补充图片占位符（当正文中没有图片引用时）

        从draft.metadata.rag_media_manifest获取图片列表，智能插入到markdown中：
        1. 检查是否已有图片占位符
        2. 从rag_media_manifest获取图片
        3. 将图片按章节关键词匹配，插入到相关章节末尾
        4. 如果无法匹配关键词，均匀分布到各章节

        Args:
            markdown_content: Markdown内容
            draft: 草稿对象

        Returns:
            补充后的Markdown内容
        """
        import re
        from pathlib import Path
        
        # 1. 获取图片列表（严格模式）
        # 只允许使用 draft.metadata.rag_media_manifest（=生成阶段确实召回/注入了图片）。
        # 不再做“目录扫描/按顺序硬配对”的兜底，避免出现“正文没召回但被强行插入图片”的不一致。
        manifest = (
            draft.metadata.get("rag_media_manifest")
            if isinstance(draft.metadata, dict)
            else None
        )
        if not manifest or not isinstance(manifest, list):
            logger.debug("无rag_media_manifest，跳过图片补充（严格模式）")
            return markdown_content
        
        images: list[dict[str, str]] = []
        for item in manifest:
            if isinstance(item, dict):
                figure_name = item.get("figure_name") or item.get("image_file")
                json_file = item.get("json_file")
                if figure_name:
                    images.append({
                        'figure_name': figure_name,
                        'json_file': json_file or figure_name.replace('.jpg', '.json')
                    })
        
        if not images:
            logger.debug("manifest中无图片，跳过图片补充")
            return markdown_content
        
        logger.info("开始补充图片占位符: 找到%d张图片", len(images))
        
        # 2. 将图片文件名转换为占位符
        # 同时构建 figure_name -> placeholder，避免后续误用最后一次循环的变量
        image_placeholders: list[str] = []
        figure_to_placeholder: dict[str, str] = {}
        for img in images:
            ph = f"[[IMAGE:{img['figure_name']}]]"
            image_placeholders.append(ph)
            figure_to_placeholder[img["figure_name"]] = ph
        
        # 3. 按章节关键词匹配插入
        # 定义常见关键词到图片的映射规则
        keyword_to_images: dict[str, list[str]] = {}
        
        for img in images:
            figure_name = (img.get("figure_name") or "").lower()
            # 从图片文件名提取关键词
            keywords = re.findall(r'[\d\w]+', figure_name)
            
            for keyword in keywords:
                if len(keyword) >= 2:  # 忽略过短的关键词
                    if keyword not in keyword_to_images:
                        keyword_to_images[keyword] = []
                    # 该 keyword 对应当前图片占位符
                    ph = figure_to_placeholder.get(img.get("figure_name") or "", "")
                    if ph:
                        keyword_to_images[keyword].append(ph)
        
        # 4. 在markdown中查找章节并插入图片
        # 章节标题模式：## xxx 或 ### xxx
        section_pattern = r'^(#{2,4})\s+(.+)$'
        
        lines = markdown_content.split('\n')
        result_lines: list[str] = []
        images_to_insert: dict[int, list[str]] = {}  # 行号 -> 要插入的图片占位符
        
        for i, line in enumerate(lines):
            result_lines.append(line)
            
            # 检查是否是章节标题
            match = re.match(section_pattern, line.strip())
            if match:
                section_title = match.group(2).lower()
                section_level = len(match.group(1))
                
                # 查找匹配的关键词
                matched_images: list[str] = []
                for keyword, img_list in keyword_to_images.items():
                    if keyword in section_title:
                        matched_images.extend(img_list)
                
                # 去重并限制数量
                matched_images = list(dict.fromkeys(matched_images))[:2]  # 每章节最多2张图
                
                if matched_images:
                    # 在章节标题后的第一个非空行插入图片
                    images_to_insert[i + 1] = matched_images
                    logger.debug("章节 '%s' 匹配到 %d 张图片", section_title, len(matched_images))
        
        # 5. 重建markdown，插入图片
        if images_to_insert:
            final_lines: list[str] = []
            for i, line in enumerate(lines):
                final_lines.append(line)
                if i in images_to_insert:
                    for img_placeholder in images_to_insert[i]:
                        final_lines.append(f"\n{img_placeholder}\n")
            
            markdown_content = '\n'.join(final_lines)
            logger.info("补充图片占位符完成: 插入%d张图片", sum(len(imgs) for imgs in images_to_insert.values()))
        else:
            # 6. 无法匹配关键词，均匀分布到各章节
            if len(lines) > 10 and len(image_placeholders) > 0:
                # 计算插入间隔
                insert_interval = max(1, len(lines) // (len(image_placeholders) + 1))
                
                final_lines = []
                img_index = 0
                for i, line in enumerate(lines):
                    final_lines.append(line)
                    # 在每个章节后的适当位置插入图片
                    if (i > 0 and i < len(lines) - 1 and 
                        re.match(section_pattern, line.strip()) and 
                        img_index < len(image_placeholders)):
                        # 插入1-2张图片
                        count = min(2, len(image_placeholders) - img_index)
                        for _ in range(count):
                            final_lines.append(f"\n{image_placeholders[img_index]}\n")
                            img_index += 1
                            if img_index >= len(image_placeholders):
                                break
                
                if img_index > 0:
                    markdown_content = '\n'.join(final_lines)
                    logger.info("均匀分布图片占位符: 插入%d张图片", img_index)
        
        return markdown_content

    def _markdown_to_html(self, markdown_content: str) -> str:
        """
        将Markdown内容转换为HTML

        注意：会移除所有 [CONTENT_PLACEHOLDER:...] 占位符，
        这些占位符是用于标识章节位置的元数据，不应出现在最终HTML中。

        Args:
            markdown_content: Markdown格式的内容

        Returns:
            HTML格式的内容
        """
        # 移除所有 [CONTENT_PLACEHOLDER:...] 占位符（这些是元数据，不应出现在最终HTML中）
        import re
        content_placeholder_pattern = re.compile(
            r'\[CONTENT_PLACEHOLDER:[^\]]+\]'
        )
        markdown_content = content_placeholder_pattern.sub('', markdown_content)
        
        # 清理多余的空行（占位符移除后可能留下的空行）
        markdown_content = re.sub(r'\n{3,}', '\n\n', markdown_content)
        
        # 重置Markdown解析器状态
        self.md.reset()

        # 转换为HTML
        html = self.md.convert(markdown_content)

        # 增强表格渲染(确保表格可读)
        html = self._enhance_tables_in_html(html)

        return html

    def _enhance_tables_in_html(self, html: str) -> str:
        """
        增强HTML中的表格渲染

        Args:
            html: HTML内容

        Returns:
            增强后的HTML内容
        """
        try:
            table_renderer = _get_table_renderer()

            # 查找所有表格
            table_pattern = r"<table[^>]*>.*?</table>"
            tables = re.findall(table_pattern, html, re.DOTALL | re.IGNORECASE)

            for table in tables:
                # 增强表格
                enhanced_table = table_renderer._enhance_html_table(table, add_styles=True)
                html = html.replace(table, enhanced_table, 1)

        except Exception as e:
            logger.warning(f"增强表格渲染失败: {e}, 使用原始HTML")

        # 二次清洗：修复“章节标题/表标题被塞进表格”的问题
        # 典型坏例子：
        #   <tr><td><strong>表C.1-2 ...</strong></td><td></td><td></td></tr>
        #   <tr><td>#### C.2 ...</td><td></td><td></td></tr>
        # 这种行会把后续章节内容吞进表格，导致列宽异常/内容错位。
        try:
            html = self._sanitize_rendered_tables_in_html(html)
        except Exception as e:
            logger.warning("表格HTML二次清洗失败（容错处理）: %s", e, exc_info=True)

        return html

    def _sanitize_rendered_tables_in_html(self, html: str) -> str:
        """
        修复 rendered-table 中混入的“伪行”（只有第一列有内容，其余列为空）。

        策略：
        - 对每个 rendered-table：
          - 保留伪行之前的正常数据行
          - 从第一个伪行开始，截断表格，并把伪行/后续同类行以段落/标题形式移到表格外
        """
        if not html:
            return html

        table_pat = re.compile(
            r"(<table[^>]*class=[\"'][^\"']*rendered-table[^\"']*[\"'][^>]*>)(.*?)(</table>)",
            re.IGNORECASE | re.DOTALL,
        )

        def _strip_tags(s: str) -> str:
            if not s:
                return ""
            t = re.sub(r"<[^>]+>", "", s)
            t = t.replace("&nbsp;", " ").replace("\u00a0", " ")
            return re.sub(r"\s+", " ", t).strip()

        def _is_pseudo_row(cells: list[str]) -> bool:
            if len(cells) < 2:
                return False
            first = _strip_tags(cells[0])
            if not first:
                return False
            rest = [_strip_tags(c) for c in cells[1:]]
            return all(not r for r in rest)

        def _render_extracted_block(cell_html: str) -> str:
            txt = _strip_tags(cell_html)
            if not txt:
                return ""

            # Markdown风格标题（以 #### / ### 等开头）——转换为对应的 h 标签
            m = re.match(r"^(#{2,6})\s*(.+)$", txt)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                # 将 markdown 标题转成 HTML 标题
                return f"<h{level}>{title}</h{level}>"

            # 表标题/图标题：保持强调样式
            if txt.startswith("表") or txt.startswith("图"):
                return f'<p class="table-caption">{cell_html}</p>'

            # 普通段落
            return f"<p>{cell_html}</p>"

        def _process_one_table(full_table: str) -> str:
            # 提取 thead 与 tbody（若不存在tbody，直接返回）
            m_body = re.search(r"(<tbody[^>]*>)(.*?)(</tbody>)", full_table, re.IGNORECASE | re.DOTALL)
            if not m_body:
                return full_table

            tbody_open, tbody_inner, tbody_close = m_body.group(1), m_body.group(2), m_body.group(3)
            row_pat = re.compile(r"<tr[^>]*>.*?</tr>", re.IGNORECASE | re.DOTALL)
            rows = row_pat.findall(tbody_inner)
            if not rows:
                return full_table

            kept: list[str] = []
            extracted_blocks: list[str] = []
            cut = False

            cell_pat = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)

            for row in rows:
                cells = cell_pat.findall(row) or []
                if (not cut) and _is_pseudo_row(cells):
                    cut = True

                if cut:
                    # 把“伪行”及其后续同类行搬出表格
                    if _is_pseudo_row(cells):
                        block = _render_extracted_block(cells[0])
                        if block:
                            extracted_blocks.append(block)
                    else:
                        # 已进入 cut 状态后，遇到非伪行也不再放回表格，避免吞回去（保守）
                        # 将整行第一列作为段落输出（尽量不丢信息）
                        first_html = cells[0] if cells else _strip_tags(row)
                        block = _render_extracted_block(first_html)
                        if block:
                            extracted_blocks.append(block)
                else:
                    kept.append(row)

            if not cut:
                return full_table

            new_tbody_inner = "\n".join(kept).strip()
            new_full = full_table[: m_body.start(2)] + new_tbody_inner + full_table[m_body.end(2) :]

            # 在表格后追加提取出的块
            extra = "\n".join(b for b in extracted_blocks if b).strip()
            if extra:
                new_full = new_full + "\n" + extra + "\n"
            return new_full

        # 逐个表格替换（避免全局替换引发错位）
        out = html
        for m in list(table_pat.finditer(html)):
            full = m.group(0)
            processed = _process_one_table(full)
            if processed != full:
                out = out.replace(full, processed, 1)

        return out

    def _extract_chart_configs_from_draft(
        self, draft: Draft
    ) -> list[ChartConfig]:
        """
        从草稿内容中提取图表配置

        优先从datajson目录加载,如果没有则尝试从结构化数据生成.

        Args:
            draft: 草稿领域模型对象

        Returns:
            图表配置列表
        """
        chart_configs: list[ChartConfig] = []

        try:
            logger.debug("开始从草稿中提取图表配置: draft_id=%s", draft.id)

            # 获取草稿内容
            content = draft.get_content()

            # 查找所有图表占位符: [[CHART:<id>]] 或 [[CHART:<index>]] 或 [[IMAGE:<filename>.json]]
            placeholder_pattern = r"\[\[(?:CHART|IMAGE):([^\]]+)\]\]"
            matches = list(re.finditer(placeholder_pattern, content))
            logger.debug("找到图表/图片占位符: 数量=%d", len(matches))

            chart_index = 0
            for match_idx, match in enumerate(matches, 1):
                chart_id_or_index = match.group(1)
                
                # 如果是图片且不是 .json 结尾，跳过（不作为图表处理，由 _replace_image_placeholders 处理）
                if match.group(0).startswith("[[IMAGE:") and not chart_id_or_index.lower().endswith(".json"):
                    continue

                try:
                    logger.debug(
                        "处理图表占位符 [%d/%d]: id_or_index='%s'",
                        match_idx,
                        len(matches),
                        chart_id_or_index,
                    )

                    # 允许三种形式：
                    # 1) UUID
                    # 2) 数字索引
                    # 3) 直接写 datajson 文件名（如: 图1xxx.json / 8474....json）
                    parsed_chart_index: int | None = None
                    try:
                        uuid.UUID(chart_id_or_index)
                        logger.debug("解析为UUID: %s", chart_id_or_index)
                    except ValueError:
                        try:
                            parsed_chart_index = int(chart_id_or_index)
                            logger.debug("解析为索引: %d", parsed_chart_index)
                        except ValueError:
                            if not chart_id_or_index.lower().endswith(".json"):
                                logger.warning(
                                    "无法解析图表占位符ID: '%s', 跳过",
                                    chart_id_or_index,
                                )
                                continue
                            chart_id_or_index = Path(str(chart_id_or_index)).name
                            logger.debug("解析为JSON文件名: %s", chart_id_or_index)

                    # 优先尝试从datajson目录加载图表数据
                    chart_config = self._load_chart_config_from_datajson(
                        draft_id=draft.id,
                        chart_id_or_index=chart_id_or_index,
                        chart_index=parsed_chart_index if parsed_chart_index is not None else chart_index,
                    )

                    # 如果datajson加载失败,尝试从结构化数据生成
                    if not chart_config:
                        logger.debug(
                            "datajson加载失败，尝试从结构化数据生成: chart_index=%d",
                            chart_index,
                        )
                        chart_config = (
                            self._generate_chart_config_from_structured_data(
                                draft_id=draft.id,
                                content=content,
                                chart_index=chart_index,
                            )
                        )

                    if chart_config:
                        chart_configs.append(chart_config)
                        logger.debug(
                            "成功提取图表配置 [%d]: type=%s, title='%s'",
                            match_idx,
                            getattr(chart_config.chart_type, "value", chart_config.chart_type),
                            chart_config.title or "无标题",
                        )
                        chart_index += 1
                    else:
                        logger.warning(
                            "未能提取图表配置: chart_id_or_index='%s', chart_index=%d",
                            chart_id_or_index,
                            chart_index,
                        )

                except Exception as e:
                    logger.error(
                        "提取图表配置失败: chart_id_or_index='%s', 错误=%s",
                        chart_id_or_index,
                        e,
                        exc_info=True,
                    )
                    # 继续处理其他图表，不中断流程

            logger.info(
                "从草稿中提取图表配置完成: draft_id=%s, 占位符数=%d, 成功提取数=%d",
                draft.id,
                len(matches),
                len(chart_configs),
            )

        except Exception as e:
            logger.error(
                "从草稿中提取图表配置失败: draft_id=%s, 错误=%s",
                draft.id,
                e,
                exc_info=True,
            )
            # 返回已提取的配置，不抛出异常

        return chart_configs

    def _generate_chart_config_from_structured_data(
        self,
        draft_id: uuid.UUID,
        content: str,
        chart_index: int,
    ) -> ChartConfig | None:
        """
        从结构化数据生成图表配置(作为datajson的补充方案)

        Args:
            draft_id: 草稿ID
            content: 草稿内容
            chart_index: 图表索引

        Returns:
            图表配置对象,如果生成失败则返回None
        """
        try:
            from src.application.services.structured_data_chart_generator import (
                StructuredDataChartGenerator,
            )

            generator = StructuredDataChartGenerator()

            # 提取结构化数据
            structured_data_list = generator.extract_structured_data(content)

            if not structured_data_list:
                logger.debug("未找到结构化数据,无法生成图表配置")
                return None

            # 使用第一个找到的结构化数据(或根据索引选择)
            if chart_index < len(structured_data_list):
                structured_data = structured_data_list[chart_index]
            else:
                structured_data = structured_data_list[0]

            # 生成图表配置
            chart_config = generator.generate_chart_config_from_data(
                draft_id=draft_id,
                structured_data=structured_data,
                chart_type_hint=None,
            )

            if chart_config:
                logger.info(
                    f"从结构化数据生成图表配置成功: 类型={chart_config.chart_type.value}"
                )

            return chart_config

        except Exception as e:
            logger.warning(f"从结构化数据生成图表配置失败: {e}")
            return None

    def _load_chart_config_from_datajson(
        self,
        draft_id: uuid.UUID,
        chart_id_or_index: str,
        chart_index: int,
    ) -> ChartConfig | None:
        """
        从datajson目录加载图表配置

        Args:
            draft_id: 草稿ID
            chart_id_or_index: 图表ID或索引
            chart_index: 图表索引(用于按顺序加载)

        Returns:
            图表配置对象,如果加载失败则返回None
        """
        try:
            if not self.datajson_base_dir or not self.datajson_base_dir.exists():
                logger.debug(
                    "datajson目录不存在: %s, 无法加载图表数据",
                    self.datajson_base_dir,
                )
                return None

            logger.debug(
                "从datajson目录加载图表配置: draft_id=%s, chart_index=%d, dir=%s",
                draft_id,
                chart_index,
                self.datajson_base_dir,
            )

            # 查找所有JSON文件
            json_files = sorted(list(self.datajson_base_dir.glob("*.json")))

            if not json_files:
                logger.debug(
                    "datajson目录中没有JSON文件: %s",
                    self.datajson_base_dir,
                )
                return None

            logger.debug(
                "找到JSON文件: 数量=%d, 文件列表=%s",
                len(json_files),
                [f.name for f in json_files[:5]],  # 只显示前5个
            )

            # 根据索引选择JSON文件
            if chart_index < len(json_files):
                json_file = json_files[chart_index]
            else:
                logger.warning(
                    "图表索引 %d 超出范围(共 %d 个文件), 使用最后一个文件",
                    chart_index,
                    len(json_files),
                )
                json_file = json_files[-1]

            logger.debug("选择JSON文件: %s", json_file.name)

            # 加载JSON数据
            with open(json_file, encoding="utf-8") as f:
                chart_data = json.load(f)

            logger.debug(
                "JSON文件加载成功: file=%s, 数据键=%s",
                json_file.name,
                list(chart_data.keys()),
            )

            # 解析图表类型
            chart_type_str = chart_data.get("chart_type", "OTHER")
            chart_type = self._parse_chart_type(chart_type_str)

            # 创建图表配置
            chart_config = ChartConfig.create_from_data_source(
                draft_id=draft_id,
                chart_type=chart_type,
                data_source=chart_data,
                title=chart_data.get("title"),
                description=chart_data.get("description"),
                source_file=str(json_file),
            )

            # 生成ECharts配置
            echarts_config = self._generate_echarts_config(chart_data, chart_type)
            chart_config.update_dsl_config({"option": echarts_config})

            logger.info(
                "成功加载图表配置: file=%s, type=%s, title='%s'",
                json_file.name,
                chart_type.value,
                chart_config.title or "无标题",
            )

            return chart_config

        except json.JSONDecodeError as e:
            logger.error(
                "JSON解析失败: file=%s, 错误=%s",
                json_file if "json_file" in locals() else "unknown",
                e,
                exc_info=True,
            )
            return None
        except FileNotFoundError as e:
            logger.error(
                "文件不存在: file=%s, 错误=%s",
                json_file if "json_file" in locals() else "unknown",
                e,
            )
            return None
        except Exception as e:
            logger.error(
                "加载图表JSON文件失败: file=%s, 错误=%s",
                json_file if "json_file" in locals() else "unknown",
                e,
                exc_info=True,
            )
            return None

    def _load_all_charts_from_datajson(
        self, draft_id: uuid.UUID
    ) -> list[ChartConfig]:
        """
        从datajson目录加载所有图表配置（用于附录显示）

        当草稿中没有图表占位符时，仍然可以从datajson目录加载所有图表数据
        并在附录中显示，以体现项目的图表处理能力。

        Args:
            draft_id: 草稿ID

        Returns:
            图表配置列表
        """
        chart_configs: list[ChartConfig] = []

        try:
            if not self.datajson_base_dir or not self.datajson_base_dir.exists():
                logger.debug("datajson目录不存在，无法加载图表")
                return chart_configs

            # 查找所有JSON文件
            json_files = sorted(list(self.datajson_base_dir.glob("*.json")))

            if not json_files:
                logger.debug("datajson目录中没有JSON文件")
                return chart_configs

            logger.debug(
                "从datajson目录加载所有图表: 目录=%s, JSON文件数=%d",
                self.datajson_base_dir,
                len(json_files),
            )

            # 加载每个JSON文件
            for idx, json_file in enumerate(json_files):
                try:
                    chart_config = self._load_chart_config_from_datajson(
                        draft_id=draft_id,
                        chart_id_or_index=str(idx),
                        chart_index=idx,
                    )
                    if chart_config:
                        chart_configs.append(chart_config)
                        logger.debug(
                            "成功加载图表配置 [%d/%d]: %s",
                            idx + 1,
                            len(json_files),
                            json_file.name,
                        )
                except Exception as e:
                    logger.warning(
                        "加载图表配置失败 [%d/%d]: file=%s, 错误=%s",
                        idx + 1,
                        len(json_files),
                        json_file.name,
                        e,
                    )
                    # 继续处理其他文件，不中断流程

            logger.info(
                "从datajson目录加载图表配置完成: draft_id=%s, 成功加载数=%d/%d",
                draft_id,
                len(chart_configs),
                len(json_files),
            )

        except Exception as e:
            logger.error(
                "从datajson目录加载所有图表配置失败: draft_id=%s, 错误=%s",
                draft_id,
                e,
                exc_info=True,
            )
            # 返回已加载的配置，不抛出异常

        return chart_configs

    def _parse_chart_type(self, chart_type_str: str) -> ChartType:
        """
        解析图表类型字符串为ChartType枚举

        Args:
            chart_type_str: 图表类型字符串

        Returns:
            ChartType枚举值
        """
        chart_type_str_lower = chart_type_str.lower()

        if "bar" in chart_type_str_lower:
            return ChartType.BAR
        elif "line" in chart_type_str_lower:
            return ChartType.LINE
        elif "pie" in chart_type_str_lower:
            return ChartType.PIE
        elif "scatter" in chart_type_str_lower:
            return ChartType.SCATTER
        elif "table" in chart_type_str_lower:
            return ChartType.TABLE
        else:
            return ChartType.OTHER

    def _generate_echarts_config(
        self, chart_data: dict[str, Any], chart_type: ChartType
    ) -> dict[str, Any]:
        """
        根据图表数据生成ECharts配置

        Args:
            chart_data: 图表数据字典
            chart_type: 图表类型

        Returns:
            ECharts配置字典
        """
        base_config: dict[str, Any] = {
            "title": {
                "text": chart_data.get("title", "图表"),
                "left": "center",
                "textStyle": {"fontSize": 18},
            },
            "tooltip": {
                "trigger": "axis"
                if chart_type in [ChartType.BAR, ChartType.LINE]
                else "item",
            },
            "legend": {"show": True, "left": "center"},
        }

        # 根据图表类型生成特定配置
        if chart_type == ChartType.BAR:
            base_config.update(self._generate_bar_chart_config(chart_data))
        elif chart_type == ChartType.LINE:
            base_config.update(self._generate_line_chart_config(chart_data))
        elif chart_type == ChartType.PIE:
            base_config.update(self._generate_pie_chart_config(chart_data))
        elif chart_type == ChartType.SCATTER:
            base_config.update(self._generate_scatter_chart_config(chart_data))
        else:
            # 其他类型,使用通用配置
            base_config["series"] = []

        return base_config

    def _generate_bar_chart_config(
        self, chart_data: dict[str, Any]
    ) -> dict[str, Any]:
        """生成柱状图ECharts配置"""
        chart_data_list = chart_data.get("chart_data", [])
        categories: list[str] = []
        values: list[float] = []

        for item in chart_data_list:
            if isinstance(item, dict):
                category = item.get("category") or item.get("label", "")
                value = item.get("value", 0)
                if isinstance(value, str):
                    # 尝试从字符串中提取数字
                    value = float(re.sub(r"[^\d.]", "", value) or "0")
                categories.append(str(category))
                values.append(float(value))

        return {
            "xAxis": {"type": "category", "data": categories},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": values, "name": "数值"}],
        }

    def _generate_line_chart_config(
        self, chart_data: dict[str, Any]
    ) -> dict[str, Any]:
        """生成折线图ECharts配置"""
        chart_data_list = chart_data.get("chart_data", [])
        categories: list[str] = []
        values: list[float] = []

        for item in chart_data_list:
            if isinstance(item, dict):
                category = item.get("category") or item.get("label", "")
                value = item.get("value", 0)
                if isinstance(value, str):
                    value = float(re.sub(r"[^\d.]", "", value) or "0")
                categories.append(str(category))
                values.append(float(value))

        return {
            "xAxis": {"type": "category", "data": categories},
            "yAxis": {"type": "value"},
            "series": [{"type": "line", "data": values, "name": "数值"}],
        }

    def _generate_pie_chart_config(
        self, chart_data: dict[str, Any]
    ) -> dict[str, Any]:
        """生成饼图ECharts配置"""
        chart_data_list = chart_data.get("chart_data", [])
        pie_data: list[dict[str, Any]] = []

        for item in chart_data_list:
            if isinstance(item, dict) and "_chart_separator" not in item:
                label = item.get("label", "")
                value = item.get("value", 0)
                if isinstance(value, str):
                    value = float(re.sub(r"[^\d.]", "", value) or "0")
                pie_data.append({"name": str(label), "value": float(value)})

        return {
            "series": [
                {
                    "type": "pie",
                    "data": pie_data,
                    "radius": "60%",
                    "center": ["50%", "60%"],
                    "emphasis": {
                        "itemStyle": {
                            "shadowBlur": 10,
                            "shadowOffsetX": 0,
                            "shadowColor": "rgba(0, 0, 0, 0.5)",
                        }
                    },
                }
            ],
        }

    def _generate_scatter_chart_config(
        self, chart_data: dict[str, Any]
    ) -> dict[str, Any]:
        """生成散点图ECharts配置"""
        chart_data_list = chart_data.get("chart_data", [])
        scatter_data: list[list[float]] = []

        for item in chart_data_list:
            if isinstance(item, dict):
                x = item.get("x", 0)
                y = item.get("y", 0)
                if isinstance(x, str):
                    x = float(re.sub(r"[^\d.]", "", x) or "0")
                if isinstance(y, str):
                    y = float(re.sub(r"[^\d.]", "", y) or "0")
                scatter_data.append([float(x), float(y)])

        return {
            "xAxis": {"type": "value"},
            "yAxis": {"type": "value"},
            "series": [{"type": "scatter", "data": scatter_data, "name": "数据点"}],
        }

    def _replace_image_placeholders(self, html_content: str, draft: Draft | None = None) -> str:
        """
        替换HTML内容中的图片占位符为 <img> 标签

        支持两种文件名格式：
        1. figure_name格式：如 "图1_xxx.jpg"（从manifest的figure_name获取）
        2. UUID格式：如 "84744014a2a5ef64b05634adc6e8e7f7e3b148e8cf99b7fdfe40635389724dc7.jpg"

        Args:
            html_content: HTML内容
            draft: 草稿对象（可选，用于获取manifest映射）

        Returns:
            替换后的HTML内容
        """
        try:
            # 构建figure_name到UUID文件名的映射
            figure_to_uuid_map: dict[str, str] = {}
            images_dir = None
            if self.datajson_base_dir:
                # 查找images目录
                images_dir = self.datajson_base_dir / "images"
                if not images_dir.exists():
                    images_dir = self.datajson_base_dir.parent / "images"
                
                if images_dir.exists():
                    for img_file in images_dir.glob("*.jpg"):
                        # 如果文件名是UUID格式，建立映射
                        try:
                            uuid.UUID(img_file.stem)
                            # UUID格式文件，尝试从manifest获取figure_name
                            # 暂时跳过，将在下面的逻辑中处理
                        except ValueError:
                            # 非UUID格式，直接使用文件名
                            figure_to_uuid_map[img_file.name] = img_file.name
                    
                    logger.debug(
                        "图片占位符替换：扫描images目录找到%d个非UUID格式图片",
                        len(figure_to_uuid_map)
                    )
            
            # 从draft.metadata获取manifest，建立figure_name到original_uuid的映射
            manifest_figure_to_uuid: dict[str, str] = {}
            if draft and isinstance(draft.metadata, dict):
                manifest = draft.metadata.get("rag_media_manifest")
                if isinstance(manifest, list):
                    for item in manifest:
                        if isinstance(item, dict):
                            figure_name = item.get("figure_name") or item.get("image_file")
                            original_uuid = item.get("original_uuid")
                            if figure_name and original_uuid:
                                manifest_figure_to_uuid[figure_name] = original_uuid
                    logger.debug(
                        "图片占位符替换：从manifest加载%d条figure_name->UUID映射",
                        len(manifest_figure_to_uuid)
                    )
                    # 调试：打印manifest内容
                    logger.info("图片占位符替换：manifest_figure_to_uuid=%s", manifest_figure_to_uuid)

            # 从clean_content_list.json加载图片名称映射
            image_caption_map: dict[str, str] = {}
            if self.datajson_base_dir:
                # 查找clean_content_list.json（可能在当前目录或父目录中）
                possible_paths = [
                    self.datajson_base_dir / "clean_content_list.json",
                    self.datajson_base_dir.parent / "clean_content_list.json",
                ]
                clean_content_list_path = None
                for path in possible_paths:
                    if path.exists():
                        clean_content_list_path = path
                        break

                if clean_content_list_path:
                    import json
                    with open(clean_content_list_path, encoding="utf-8") as f:
                        content_list = json.load(f)
                    # 构建图片文件名到image_caption的映射
                    for item in content_list:
                        if isinstance(item, dict) and item.get("type") == "image":
                            img_path = item.get("img_path", "")
                            img_filename = Path(img_path).name if img_path else ""
                            captions = item.get("image_caption", [])
                            if isinstance(captions, list) and len(captions) > 0:
                                image_caption_map[img_filename] = captions[0]
                            elif isinstance(captions, str) and captions:
                                image_caption_map[img_filename] = captions
                    logger.debug("从clean_content_list.json加载图片映射: %d 条", len(image_caption_map))

            # 查找 [[IMAGE:filename.jpg]] 或 [[IMAGE:filename.json]]
            pattern = r"\[\[IMAGE:([^\]]+)\]\]"
            
            # 跟踪图片出现顺序，用于编号
            image_counter: dict[str, int] = {}  # filename -> count
            # 从 1 开始，避免出现 __FIGURE_0__ 导致正文/附录编号错位
            figure_number = 1

            def replace_image(match: re.Match[str]) -> str:
                nonlocal figure_number
                filename = match.group(1).strip()
                # 注意：不要在这里“默认归一化 *_1.jpg -> *.jpg”，否则会把多张不同图片错误映射成同一张。
                # 只有在 manifest 中完全找不到该 filename 时，才允许做降级处理（见下方 key_for_manifest）。
                normalized_filename = filename
                try:
                    m2 = re.match(r"^(.*)_(\d+)(\.[A-Za-z0-9]+)$", filename)
                    if m2:
                        base, _n, ext = m2.group(1), m2.group(2), m2.group(3)
                        # 只对“非uuid”的人类文件名做归一化候选
                        try:
                            uuid.UUID(Path(base).stem)
                        except Exception:
                            normalized_filename = f"{base}{ext}"
                except Exception:
                    normalized_filename = filename
                
                # 调试：打印每个占位符的解析结果
                logger.info("图片占位符替换：开始处理 filename='%s'", filename)
                logger.info("图片占位符替换：manifest_figure_to_uuid=%s", manifest_figure_to_uuid)
                logger.info("图片占位符替换：filename in manifest=%s", filename in manifest_figure_to_uuid)

                # 如果是 .json 结尾，尝试将其作为图表处理（如果之前没处理过）
                if filename.lower().endswith(".json"):
                    # 交付要求：json 图表数据不在正文中分散展示，统一放到文末附录表格。
                    # 这里直接移除正文占位符，附录仍会基于 referenced_figures + manifest/datajson 生成表格。
                    return ""

                # 为图片分配临时占位符ID（用于后续重新编号）
                figure_placeholder_id = f"__FIGURE_{figure_number}__"
                figure_number += 1

                # 否则作为图片处理
                # 确定实际的图片文件名
                actual_filename = filename
                image_found = False
                image_search_info = []  # 用于调试信息

                # 1. 首先检查filename是否已经是UUID格式（不含.jpg后缀）
                try:
                    uuid.UUID(filename)
                    # 是UUID格式（不含后缀），直接使用
                    actual_filename = f"{filename}.jpg"
                    image_found = True
                    image_search_info.append(f"filename是UUID格式: {actual_filename}")
                    logger.info("图片占位符替换：filename是UUID格式 actual_filename='%s'", actual_filename)
                except ValueError:
                    logger.info("图片占位符替换：filename不是UUID格式，继续查找manifest映射")
                    # 2. 尝试从manifest映射获取UUID（必须使用UUID文件名，因为文件是UUID格式存储的）
                    key_for_manifest = filename
                    # 只有在“精确匹配失败”时，才尝试降级到 normalized（避免错误引用）
                    if key_for_manifest not in manifest_figure_to_uuid and normalized_filename != filename:
                        key_for_manifest = normalized_filename

                    if key_for_manifest in manifest_figure_to_uuid:
                        uuid_from_manifest = manifest_figure_to_uuid[key_for_manifest]
                        logger.info("图片占位符替换：从manifest找到映射 uuid_from_manifest='%s'", uuid_from_manifest)
                        # 检查uuid_from_manifest是否已经包含.jpg后缀
                        if uuid_from_manifest.endswith('.jpg'):
                            actual_filename = uuid_from_manifest
                        else:
                            actual_filename = f"{uuid_from_manifest}.jpg"
                        image_found = True
                        image_search_info.append(f"从manifest映射获取UUID: {uuid_from_manifest} -> {actual_filename}")
                        logger.info("图片占位符替换：manifest映射成功 actual_filename='%s' image_found=%s", actual_filename, image_found)
                    # 3. 如果manifest映射失败，尝试反向查找（通过文件名stem匹配）
                    elif manifest_figure_to_uuid:
                        # 尝试通过文件名匹配（去除扩展名后匹配）
                        filename_stem = Path(filename).stem
                        normalized_stem = Path(normalized_filename).stem
                        for fig_name, uuid_name in manifest_figure_to_uuid.items():
                            if fig_name and (Path(fig_name).stem == filename_stem or Path(fig_name).stem == normalized_stem):
                                uuid_from_manifest = uuid_name
                                if uuid_from_manifest.endswith('.jpg'):
                                    actual_filename = uuid_from_manifest
                                else:
                                    actual_filename = f"{uuid_from_manifest}.jpg"
                                image_found = True
                                image_search_info.append(f"通过反向匹配找到UUID: {fig_name} -> {actual_filename}")
                                logger.info("图片占位符替换：反向匹配成功 actual_filename='%s'", actual_filename)
                                break
                    
                    # 4. 如果仍未找到，检查filename是否已经有图片扩展名
                    if not image_found:
                        # 检查是否已经有常见的图片扩展名
                        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.bmp']
                        has_image_extension = any(filename.lower().endswith(ext) for ext in image_extensions)
                        
                        if has_image_extension:
                            # 已经有图片扩展名，直接使用
                            actual_filename = filename
                            image_found = True
                            image_search_info.append(f"filename已有图片扩展名: {actual_filename}")
                            logger.info("图片占位符替换：filename已有图片扩展名，直接使用 actual_filename='%s'", actual_filename)
                        else:
                            # 没有图片扩展名，尝试添加.jpg后缀
                            fig_jpg = f"{filename}.jpg"
                            image_search_info.append(f"尝试添加.jpg后缀: {fig_jpg}")
                            actual_filename = fig_jpg
                            image_found = True  # 标记为找到，尝试使用添加了.jpg后缀的文件名
                            logger.info("图片占位符替换：不在manifest中，添加.jpg后缀 actual_filename='%s'", actual_filename)

                # 图片通常放在 images/ 目录下
                # 避免重复添加 images/ 前缀
                if actual_filename.startswith("images/"):
                    image_src = actual_filename
                else:
                    image_src = f"images/{actual_filename}"
                
                # 使用临时占位符（后续会重新编号）
                # 优先从 clean_content_list.json 获取说明；若缺失则从 filename 推断，避免“只显示 图1/图2 …”
                original_caption = image_caption_map.get(filename, "") or image_caption_map.get(normalized_filename, "")
                if not original_caption:
                    try:
                        stem = Path(normalized_filename).stem
                        # 去掉生成阶段为避免重名追加的 _1/_2/... 后缀
                        stem = re.sub(r"_(\d+)$", "", stem)
                        # 去掉可能存在的 “图X_” 前缀
                        stem = re.sub(r"^图\d+[_\s：:]*", "", stem).strip()
                        if stem:
                            original_caption = stem
                    except Exception:
                        original_caption = ""
                # 如果原始说明包含"图X"格式的编号，去除它，只保留纯描述
                if "图" in original_caption:
                    # 去除编号部分，保留描述
                    import re
                    clean_caption = re.sub(r'^图\d+[\s：:]*', '', original_caption).strip()
                    if clean_caption:
                        image_caption = f"{figure_placeholder_id}: {clean_caption}"
                    else:
                        image_caption = figure_placeholder_id
                else:
                    image_caption = f"{figure_placeholder_id}: {original_caption}" if original_caption else figure_placeholder_id
                
                logger.debug(
                    "图片占位符替换: filename='%s' -> actual='%s', found=%s, search=%s, caption='%s'",
                    filename, actual_filename, image_found, image_search_info, image_caption
                )
                
                return f"""
                <div class="image-container">
                    <img src="{image_src}" alt="{filename}" class="report-image" onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                    <div class="image-error-placeholder" style="display:none; padding: 20px; background: #f8f9fa; border: 1px dashed #dee2e6; text-align: center; color: #6c757d;">
                        图片未找到: {filename}<br>
                        <small>实际尝试加载: {actual_filename}</small>
                    </div>
                    <div class="image-caption">{image_caption}</div>
                </div>
                """

            return re.sub(pattern, replace_image, html_content)
        except Exception as e:
            logger.error(f"替换图片占位符失败: {e}", exc_info=True)
            return html_content

    def _replace_chart_placeholders(
        self, html_content: str, chart_configs: list[ChartConfig]
    ) -> str:
        """
        替换HTML内容中的图表占位符为ECharts图表容器

        Args:
            html_content: HTML内容
            chart_configs: 图表配置列表

        Returns:
            替换后的HTML内容
        """
        try:
            logger.debug(
                "开始替换图表占位符: HTML长度=%d字符, 图表配置数=%d",
                len(html_content),
                len(chart_configs),
            )

            # 创建占位符到图表配置的映射
            placeholder_map: dict[str, tuple[ChartConfig, int]] = {}

            for i, chart_config in enumerate(chart_configs):
                try:
                    # 支持两种占位符格式
                    placeholder_by_id = chart_config.get_placeholder_string()
                    placeholder_by_index = chart_config.get_placeholder_string_by_index(
                        i
                    )
                    placeholder_map[placeholder_by_id] = (chart_config, i)
                    placeholder_map[placeholder_by_index] = (chart_config, i)
                    logger.debug(
                        "注册图表占位符 [%d]: id='%s', index='%s'",
                        i,
                        placeholder_by_id,
                        placeholder_by_index,
                    )
                except Exception as e:
                    logger.warning(
                        "注册图表占位符失败: chart_index=%d, 错误=%s",
                        i,
                        e,
                    )

            # 查找所有占位符
            pattern = r"\[\[CHART:[^\]]+\]\]"
            matches = list(re.finditer(pattern, html_content))
            logger.debug("找到图表占位符: 数量=%d", len(matches))

            # 替换占位符
            def replace_placeholder(match: re.Match[str]) -> str:
                placeholder = match.group(0)
                result = placeholder_map.get(placeholder)

                if result:
                    chart_config, chart_index = result
                    try:
                        chart_html = self._generate_chart_html(
                            chart_config, chart_index
                        )
                        logger.debug(
                            "成功替换图表占位符: placeholder='%s', chart_index=%d",
                            placeholder,
                            chart_index,
                        )
                        return chart_html
                    except Exception as e:
                        logger.error(
                            "生成图表HTML失败: placeholder='%s', 错误=%s",
                            placeholder,
                            e,
                            exc_info=True,
                        )
                        return f'<div class="chart-placeholder">图表生成失败: {placeholder}</div>'
                else:
                    logger.warning("未找到图表配置: placeholder='%s'", placeholder)
                    return f'<div class="chart-placeholder">图表占位符: {placeholder}</div>'

            # 执行替换
            html_content = re.sub(pattern, replace_placeholder, html_content)

            logger.info(
                "图表占位符替换完成: 占位符数=%d, 成功替换数=%d",
                len(matches),
                len([m for m in matches if placeholder_map.get(m.group(0))]),
            )

        except Exception as e:
            logger.error(
                "替换图表占位符失败: 错误=%s",
                e,
                exc_info=True,
            )
            # 返回原始内容，不抛出异常

        return html_content

    def _generate_chart_html(
        self, chart_config: ChartConfig, chart_index: int
    ) -> str:
        """
        生成图表的HTML代码

        Args:
            chart_config: 图表配置对象
            chart_index: 图表索引(用于生成唯一ID)

        Returns:
            图表的HTML代码
        """
        chart_id = f"chart_{chart_config.id.hex[:8]}_{chart_index}"
        echarts_config = chart_config.get_echarts_config()

        # 生成图表容器
        chart_html = f"""
        <div class="chart-container" id="{chart_id}_container">
            <div class="chart-title">{chart_config.title or '图表'}</div>
            <div id="{chart_id}" style="width: 100%; height: 400px;"></div>
            {f'<div class="chart-description">{chart_config.description}</div>' if chart_config.description else ''}
        </div>
        <script>
        (function() {{
            var chartDom = document.getElementById('{chart_id}');
            if (chartDom && typeof echarts !== 'undefined') {{
                var myChart = echarts.init(chartDom);
                var option = {json.dumps(echarts_config, ensure_ascii=False, indent=2)};
                myChart.setOption(option);
            }}
        }})();
        </script>
        """

        return chart_html

    def _json_to_table(self, data: dict, table_index: int = 0) -> str:
        """
        将JSON数据的chart_data转化为表格形式展示

        Args:
            data: JSON数据字典
            table_index: 表格序号（用于生成"图X"标题）

        Returns:
            HTML表格字符串
        """
        if not isinstance(data, dict):
            return f"<pre>{self._escape_html(str(data))}</pre>"

        # 获取chart_data
        chart_data = data.get("chart_data", [])
        if not chart_data or not isinstance(chart_data, list):
            return "<p>无数据</p>"

        # 使用顺序编号作为标题（"图1"、"图2"）
        table_title = f"图{table_index + 1}"

        # 获取数据项的字段
        keys = set()
        for item in chart_data:
            if isinstance(item, dict):
                keys.update(item.keys())

        if not keys:
            return "<p>无有效数据</p>"

        # 生成表格（只展示数据）
        html = f'<table class="json-data-table-inner"><thead><tr>'
        for key in sorted(keys):
            html += f'<th>{self._escape_html(str(key))}</th>'
        html += '</tr></thead><tbody>'

        for item in chart_data:
            if isinstance(item, dict):
                html += "<tr>"
                for key in sorted(keys):
                    value = item.get(key, "")
                    html += f"<td>{self._escape_html(str(value))}</td>"
                html += "</tr>"

        html += '</tbody></table>'
        return html

    def _extract_referenced_figures_from_draft(self, draft: Draft) -> set[str]:
        """
        从草稿内容中提取被引用的图表/图片文件名

        通过正则表达式匹配 [[IMAGE:xxx]] 占位符，提取所有被引用的图片文件名

        Args:
            draft: 草稿对象

        Returns:
            被引用的图表名称集合
        """
        referenced_figures: set[str] = set()
        
        try:
            # 从所有章节内容中提取引用
            for section in draft.sections:
                content = section.content if section.content else ""
                if not content:
                    continue
                
                # 匹配 [[IMAGE:xxx]] 或 [[IMAGE:images/xxx]] 格式
                pattern = r'\[\[IMAGE:(?:images/)?([^]]+)\]\]'
                matches = re.findall(pattern, content)
                
                for match in matches:
                    # 清理文件名（去掉 .jpg 扩展名用于匹配）
                    figure_name = match.strip()
                    referenced_figures.add(figure_name)
                    # 也添加不带路径的版本
                    if '/' in figure_name:
                        referenced_figures.add(Path(figure_name).name)
            
            # 从 draft.description 中也提取
            if draft.description:
                pattern = r'\[\[IMAGE:(?:images/)?([^]]+)\]\]'
                matches = re.findall(pattern, draft.description)
                for match in matches:
                    referenced_figures.add(match.strip())
                    if '/' in match:
                        referenced_figures.add(Path(match).name)
            
            logger.debug("从草稿内容提取引用图表: draft_id=%s, 引用数=%d, figures=%s",
                        draft.id, len(referenced_figures), referenced_figures)
                        
        except Exception as e:
            logger.warning("提取引用图表失败: %s", e, exc_info=True)
        
        return referenced_figures

    def _generate_appendix_html(
        self,
        draft: Draft,
        referenced_figures: set[str] | None = None,
        referenced_figures_order: list[str] | None = None,
    ) -> str:
        """
        生成附录HTML：
        - 只显示正文中引用的图表
        - 为每个被引用的图表生成：图片 + 独立表格
        - 图片显示在上面，表格显示在下面
        - 每个图片-表格组合独立展示

        Args:
            draft: 草稿对象
            referenced_figures: 正文中引用的图表名称集合（可选，如果不提供则从draft内容提取）

        Returns:
            附录HTML字符串，如果没有可显示的内容则返回空字符串
        """
        import json
        from pathlib import Path

        manifest = draft.metadata.get("rag_media_manifest") if isinstance(draft.metadata, dict) else None
        
        # 如果没有提供引用集合，尝试从 draft 内容中提取
        # 使用 None 作为哨兵值来区分"未提供"和"空集合"
        if referenced_figures is None:
            referenced_figures = self._extract_referenced_figures_from_draft(draft)
        if referenced_figures_order is None:
            referenced_figures_order = list(referenced_figures or [])
        
        logger.debug("附录生成：引用图表数=%d, referenced_figures=%s", 
                    len(referenced_figures), referenced_figures)

        # 核心逻辑：只显示正文中引用的图表，不使用兜底加载所有图表
        if not referenced_figures:
            # 如果正文中没有引用任何图表，附录为空
            # 不使用兜底策略加载所有图表
            logger.debug("附录生成：正文中无引用图表，跳过生成（不使用兜底）")
            return ""
        
        # 如果有引用的图表，继续生成附录
        #
        # 1) 优先使用 rag_media_manifest（最可靠：能把 figure_name / json_file / uuid 对齐）
        # 2) 若没有 manifest，则在 datajson 目录中扫描 *.json 作为兜底，并按“文件名主干”与引用集合匹配
        manifest_items: list[dict[str, Any]] = []
        if isinstance(manifest, list):
            manifest_items = [x for x in manifest if isinstance(x, dict)]

        if not manifest_items:
            # datajson 兜底：只展示被引用的图表 JSON（按文件名主干匹配）
            try:
                if not self.datajson_base_dir or not self.datajson_base_dir.exists():
                    logger.debug(
                        "附录生成：无rag_media_manifest且未找到datajson目录，跳过生成"
                    )
                    return ""

                chart_configs = self._load_all_charts_from_datajson(draft.id)
                ref_stems = {Path(ref).stem for ref in referenced_figures if ref}

                filtered: list[ChartConfig] = []
                for cfg in chart_configs:
                    fig_stem = Path(cfg.source_file).stem if cfg.source_file else ""
                    if fig_stem and fig_stem in ref_stems:
                        filtered.append(cfg)

                if not filtered:
                    logger.debug("附录生成：无manifest且无被引用的图表JSON")
                    return ""

                appendix_items = [
                    self._generate_chart_appendix_item(cfg, i + 1, referenced_figures)
                    for i, cfg in enumerate(filtered)
                ]
                return (
                    '<div class="appendix">'
                    "<h2>附录：图表数据</h2>"
                    + "\n".join(appendix_items)
                    + "</div>"
                )
            except Exception as e:
                logger.warning("附录生成（datajson兜底）失败: %s", e, exc_info=True)
                return ""

        # 获取当前工作目录（仅作为回退；优先使用项目根目录，避免 cwd 指向 Temp）
        cwd = Path.cwd()
        try:
            from src.shared.config.settings import _find_project_root

            project_root = _find_project_root()
        except Exception:
            project_root = cwd

        # 确定datajson目录 - 优先使用self.datajson_base_dir
        datajson_dir = self.datajson_base_dir
        if not datajson_dir or not datajson_dir.exists():
            # 尝试在项目根目录（优先）及 cwd（回退）中查找
            for search_dir in [
                project_root,
                project_root / "data" / "output" / "final",
                cwd,
                cwd / "data" / "output" / "final",
            ]:
                if search_dir.exists():
                    # 查找datajson子目录
                    datajson_candidates = list(search_dir.rglob("datajson"))
                    if datajson_candidates:
                        datajson_dir = datajson_candidates[0]
                        logger.debug(f"附录生成：找到datajson目录: {datajson_dir}")
                        break

        if not datajson_dir or not datajson_dir.exists():
            logger.warning("附录生成：未找到datajson目录")
            return ""

        logger.debug(f"附录生成：datajson_dir={datajson_dir}")

        # 确定images目录
        images_dir = None
        # 首先检查datajson目录同级或父级是否有images目录
        for search_dir in [
            datajson_dir,
            datajson_dir.parent,
            project_root / "data" / "output" / "final",
            cwd / "data" / "output" / "final",
        ]:
            if search_dir:
                test_images = search_dir / "images"
                if test_images.exists():
                    images_dir = test_images
                    logger.debug(f"附录生成：找到images目录: {images_dir}")
                    break

        if not images_dir:
            logger.warning("附录生成：未找到images目录")
            # 即使没有图片目录，也继续生成表格（只显示表格，不显示图片）
            logger.info("附录生成：将只生成表格，不显示图片")

        logger.debug(f"附录生成：images_dir={images_dir}")

        # 预扫描images目录，建立figure_name到UUID文件名的映射
        figure_to_uuid_map: dict[str, str] = {}
        if images_dir and images_dir.exists():
            for img_file in images_dir.glob("*.jpg"):
                # 跳过已经是UUID格式的文件
                try:
                    uuid.UUID(img_file.stem)
                    continue
                except ValueError:
                    # 非UUID格式，直接使用文件名
                    figure_to_uuid_map[img_file.name] = img_file.name
            logger.debug(f"附录生成：找到{len(figure_to_uuid_map)}个非UUID格式图片文件")

        # 为每个manifest项生成图片+表格组合
        appendix_items: list[str] = []
        skipped_items: list[str] = []  # 记录跳过的项，用于调试
        referenced_count = 0  # 引用计数

        table_index = 1
        for idx, item in enumerate(manifest_items):
            if not isinstance(item, dict):
                continue

            # 获取字段（支持新旧字段名）
            figure_name = item.get("figure_name") or item.get("image_file")
            json_file = item.get("json_file")
            original_uuid = item.get("original_uuid")

            logger.debug(f"附录处理 [{idx}]: figure_name={figure_name}, original_uuid={original_uuid}")

            # json_file 是生成表格的最小条件；figure_name 可能为空（例如“仅有 JSON 数据”的图表）
            if not json_file:
                logger.debug(f"附录跳过 [{idx}]: 缺少json_file")
                continue

            # 检查图表是否被引用（如果提供了引用集合）
            if referenced_figures:
                is_referenced = False
                # 用 figure_name（如果有）或 json_file 作为匹配键
                key_name = str(figure_name) if figure_name else str(json_file)
                fig_stem = Path(key_name).stem if key_name else ""
                # 使用精确匹配（文件名主干）
                for ref in referenced_figures:
                    ref_stem = Path(ref).stem if ref else ""
                    if fig_stem and ref_stem and fig_stem == ref_stem:
                        is_referenced = True
                        break
                    # 也检查完整文件名匹配
                    if figure_name == ref or str(json_file) == ref:
                        is_referenced = True
                        break
                    # 兼容UUID格式的图片引用（如 8b026cf6c23cd462e8d100e9838843ebb60dcb23d73fad4d4d89df9b91007062）
                    # 检查 figure_name 是否是UUID格式，以及 referenced_figures 中是否有对应的引用
                    if fig_stem:
                        try:
                            uuid.UUID(fig_stem)
                            # 如果是UUID格式，检查 referenced_figures 中是否有以此UUID开头的引用
                            # referenced_figures 可能是 "uuid.jpg" 或 "images/uuid.jpg" 格式
                            for ref_item in referenced_figures:
                                if fig_stem in ref_item or ref_item.startswith(fig_stem):
                                    is_referenced = True
                                    break
                        except ValueError:
                            pass
                
                if not is_referenced:
                    logger.debug(f"附录跳过 [{idx}] ({key_name}): 未在正文中引用")
                    continue
                else:
                    referenced_count += 1
                    logger.debug(f"附录处理 [{idx}] ({key_name}): 已在正文中引用")

            # 查找JSON文件
            json_path = None
            json_from_figure = f"{Path(str(figure_name)).stem}.json" if figure_name else None
            if json_from_figure:
                json_path = datajson_dir / json_from_figure
            if not json_path or not json_path.exists():
                json_path = datajson_dir / Path(str(json_file)).name

            if not json_path or not json_path.exists():
                logger.warning(f"附录跳过 [{idx}] ({figure_name}): JSON文件不存在: {json_path or 'unknown'}")
                skipped_items.append(f"{figure_name}: JSON文件不存在")
                continue

            # 加载JSON数据
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                logger.warning(f"附录跳过 [{idx}] ({figure_name}): JSON加载失败: {e}")
                skipped_items.append(f"{figure_name}: JSON加载失败")
                continue

            # 生成图片HTML - 支持UUID格式的图片文件名
            image_html = ""
            image_found = False
            image_src = ""

            if images_dir:
                # 预扫描images目录，建立UUID到文件的映射
                uuid_to_file: dict[str, str] = {}
                for img_file in images_dir.glob("*.jpg"):
                    uuid_to_file[img_file.stem] = img_file.name
                
                logger.debug(f"附录 [{idx}]: 扫描images目录找到{len(uuid_to_file)}个图片文件")
                
                # 查找策略：
                # 1. 如果有original_uuid，直接使用
                # 2. 如果没有original_uuid，但有json_file，尝试从json文件名提取UUID
                # 3. 如果figure_name是UUID格式，直接使用
                
                # 1. 首先尝试使用original_uuid
                if original_uuid:
                    # 提取UUID（去除.jpg后缀）
                    uuid_stem = Path(original_uuid).stem if original_uuid.endswith('.jpg') else original_uuid
                    if uuid_stem in uuid_to_file:
                        image_src = f"images/{uuid_to_file[uuid_stem]}"
                        image_found = True
                        logger.debug(f"附录 [{idx}]: 通过original_uuid找到图片: {uuid_to_file[uuid_stem]}")
                
                # 2. 尝试从json_file提取UUID
                if not image_found and json_file:
                    json_uuid = Path(str(json_file)).stem
                    if json_uuid in uuid_to_file:
                        image_src = f"images/{uuid_to_file[json_uuid]}"
                        image_found = True
                        logger.debug(f"附录 [{idx}]: 通过json文件stem找到图片: {uuid_to_file[json_uuid]}")
                
                # 3. 尝试figure_name是UUID格式
                if not image_found and figure_name:
                    try:
                        uuid.UUID(figure_name)
                        # figure_name是UUID格式（不含后缀），直接查找
                        if figure_name in uuid_to_file:
                            image_src = f"images/{uuid_to_file[figure_name]}"
                            image_found = True
                            logger.debug(f"附录 [{idx}]: figure_name是UUID格式，找到图片: {uuid_to_file[figure_name]}")
                        else:
                            # 尝试添加.jpg后缀
                            figure_name_jpg = f"{figure_name}.jpg"
                            for img_filename in uuid_to_file.values():
                                if img_filename == figure_name_jpg:
                                    image_src = f"images/{img_filename}"
                                    image_found = True
                                    logger.debug(f"附录 [{idx}]: figure_name是UUID格式，找到图片: {img_filename}")
                                    break
                    except ValueError:
                        pass
                
                # 4. 如果仍然找不到，记录警告（附录只显示数据表格，不显示图片）
                if not image_found:
                    logger.warning(f"附录 [{idx}] ({figure_name or json_file}): 未找到对应的UUID图片文件")
                    # 附录只显示数据表格，不显示图片
                    image_html = ""
            
            # 表格序号必须按“实际输出的表”连续编号（不能用 manifest 的 idx，否则会出现 表9/表12 这种跳号）
            # 表名：按你的要求，直接使用 json 文件名（去掉扩展名）
            display_title = Path(str(json_file)).stem

            table_html = self._generate_single_table_from_json(
                data,
                table_index,
                display_title,
                figure_placeholder_id=None,
            )

            # 组合图片+表格
            if table_html.strip():
                appendix_items.append(f"{image_html}{table_html}")
                table_index += 1

        # 记录跳过的项用于调试
        if skipped_items:
            logger.info(f"附录生成：跳过{len(skipped_items)}项，跳过原因: {skipped_items[:5]}...")

        # 记录引用统计
        if referenced_figures:
            logger.info(f"附录生成：正文中引用图表数={len(referenced_figures)}, 实际生成={len(appendix_items)}")

        if not appendix_items:
            logger.debug("附录生成：无有效内容可展示")
            return ""

        logger.info(f"附录生成完成：共{len(appendix_items)}项")

        # 组装完整的附录HTML
        return (
            '<div class="appendix">'
            '<h2>附录：图表数据</h2>'
            + "\n".join(appendix_items)
            + '</div>'
        )

    def _generate_single_table_from_json(
        self, data: dict, table_index: int, figure_name: str | None = None,
        figure_placeholder_id: str | None = None
    ) -> str:
        """
        从单个JSON数据生成一个独立的表格

        Args:
            data: JSON数据字典
            table_index: 表格序号（用于生成"表1"标题）
            figure_name: 图名（用于表格标题）
            figure_placeholder_id: 图片占位符ID（如 __FIGURE_1__），用于后续重新编号

        Returns:
            表格HTML字符串
        """
        chart_data = data.get("chart_data", [])
        if not chart_data or not isinstance(chart_data, list):
            return ""

        # 表格标题：统一用“表X”，满足“json 图表数据放到文末以表格形式呈现”的交付要求
        if figure_name:
            import re
            clean_title = re.sub(r'^图\d+[\s：:]*', '', str(figure_name)).strip()
            clean_title = clean_title.replace("_", " ").replace(".jpg", "").replace(".json", "").strip()
            if clean_title:
                title_html = f'<div class="chart-title">表{table_index}: {clean_title}</div>'
            else:
                title_html = f'<div class="chart-title">表{table_index}</div>'
        else:
            title_html = f'<div class="chart-title">表{table_index}</div>'

        # 收集所有字段名
        all_keys = set()
        for item in chart_data:
            if isinstance(item, dict):
                all_keys.update(item.keys())

        # 移除内部字段
        all_keys = {k for k in all_keys if not k.startswith("_")}

        if not all_keys:
            return ""

        # 字段名中英文映射
        key_mapping = {
            "label": "类别",
            "value": "数值",
            "unit": "单位",
            "category": "类别",
            "category_name": "类别",
            "name": "名称",
            "amount": "金额",
            "percentage": "占比",
            "percent": "占比",
            "count": "数量",
            "year": "年份",
            "month": "月份",
            "province": "省份",
            "region": "地区",
            "type": "类型",
            "technology": "技术",
            "capacity": "容量",
            "power": "功率",
            "ratio": "比率",
        }

        # 生成表格头部
        keys_list = sorted(all_keys)
        thead_html = "<thead><tr>"
        for key in keys_list:
            # 转换为中文显示名称
            display_key = key_mapping.get(key, key.replace("_", " ").replace("-", " ").title())
            thead_html += f"<th>{display_key}</th>"
        thead_html += "</tr></thead>"

        # 生成表格内容
        tbody_html = "<tbody>"
        for item in chart_data:
            if not isinstance(item, dict):
                continue
            tbody_html += "<tr>"
            for key in keys_list:
                value = item.get(key, "")
                # 格式化数值
                if isinstance(value, (int, float)):
                    if isinstance(value, float):
                        value = f"{value:.2f}"
                    else:
                        value = str(value)
                tbody_html += f"<td>{self._escape_html(str(value))}</td>"
            tbody_html += "</tr>"
        tbody_html += "</tbody>"

        # 完整的表格HTML
        return f"""
        <div class="data-table-container">
            {title_html}
            <table class="data-table">
                {thead_html}
                {tbody_html}
            </table>
        </div>
        """

    def _generate_chart_appendix_item(
        self, chart_config: ChartConfig, index: int, referenced_figures: set[str] | None = None
    ) -> str:
        """
        生成单个图表的附录项

        Args:
            chart_config: 图表配置对象
            index: 图表索引
            referenced_figures: 正文中引用的图表名称集合（用于判断是否显示序号）

        Returns:
            图表附录HTML字符串
        """
        # 图表标题和来源
        title = chart_config.title or ""
        
        # 清理标题：如果 title 已经是 "图表 X" 格式，则提取纯标题
        if title:
            # 移除已有的 "图表 X:" 或 "图表 X" 前缀
            clean_title = re.sub(r'^图表\s*\d+[:：]?\s*', '', title).strip()
            if clean_title:
                title = clean_title
            # 如果清理后为空，使用默认格式
            if not title:
                title = f"图表 {index}"
        else:
            title = f"图表 {index}"
        
        # 判断是否是被引用的图表
        # 从source_file提取文件名（去掉路径和扩展名）作为figure_name
        figure_name = ""
        if chart_config.source_file:
            # 提取文件名（不含路径）
            source_filename = Path(chart_config.source_file).name
            # 去掉.json扩展名，得到figure_name
            figure_name = Path(source_filename).stem
        elif chart_config.title:
            # 如果没有source_file，尝试使用title
            figure_name = chart_config.title
        
        is_referenced = figure_name in (referenced_figures or set()) if figure_name else False
        
        # 如果没有被引用且有引用集合，则跳过（只在明确需要时显示）
        # 这里我们仍然显示，但标记为未引用
        
        # 交付物要求：附录只展示“数据表格名称 + 数据表格”，不输出多余描述（如数据来源、JSON路径等）
        display_name = title or (figure_name.strip() if figure_name else "") or f"表 {index}"
        html = f"""
        <div class="appendix-item">
            <h3>{self._escape_html(display_name)}</h3>
        """

        # 数据表格
        if chart_config.data_source:
            html += self._generate_data_table(chart_config)
        # 交付物中不直接暴露原始 JSON（用户需要的是“表格化”的附录）

        html += "</div>\n"

        return html

    def _generate_data_table(self, chart_config: ChartConfig) -> str:
        """
        生成数据表格HTML

        Args:
            chart_config: 图表配置对象

        Returns:
            数据表格HTML字符串
        """
        chart_data = chart_config.data_source.get("chart_data", [])

        if not chart_data:
            return "<p>无数据</p>"

        # 确定表格列
        if chart_config.chart_type == ChartType.PIE:
            # 饼图: label, value, unit
            html = '<table class="data-table">\n<thead><tr><th>标签</th><th>数值</th><th>单位</th></tr></thead>\n<tbody>\n'
            for item in chart_data:
                if isinstance(item, dict) and "_chart_separator" not in item:
                    label = item.get("label", "")
                    value = item.get("value", "")
                    unit = item.get("unit", "")
                    html += f"<tr><td>{self._escape_html(str(label))}</td><td>{self._escape_html(str(value))}</td><td>{self._escape_html(str(unit))}</td></tr>\n"
        elif chart_config.chart_type in [ChartType.BAR, ChartType.LINE]:
            # 柱状图/折线图: category, value, unit
            html = '<table class="data-table">\n<thead><tr><th>类别</th><th>数值</th><th>单位</th></tr></thead>\n<tbody>\n'
            for item in chart_data:
                if isinstance(item, dict) and "_chart_separator" not in item:
                    category = item.get("category", "")
                    value = item.get("value", "")
                    unit = item.get("unit", "")
                    html += f"<tr><td>{self._escape_html(str(category))}</td><td>{self._escape_html(str(value))}</td><td>{self._escape_html(str(unit))}</td></tr>\n"
        else:
            # 其他类型: 显示所有字段
            html = '<table class="data-table">\n<thead><tr>'
            if chart_data and isinstance(chart_data[0], dict):
                keys = [
                    k
                    for k in chart_data[0].keys()
                    if k != "_chart_separator"
                ]
                for key in keys:
                    html += f"<th>{self._escape_html(str(key))}</th>"
            html += "</tr></thead>\n<tbody>\n"
            for item in chart_data:
                if isinstance(item, dict) and "_chart_separator" not in item:
                    html += "<tr>"
                    for key in keys:
                        value = item.get(key, "")
                        html += f"<td>{self._escape_html(str(value))}</td>"
                    html += "</tr>\n"

        html += "</tbody>\n</table>\n"

        return html

    def _escape_html(self, text: str) -> str:
        """转义HTML特殊字符"""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

    def _renumber_figures_in_html(self, html_content: str) -> str:
        """
        重新编号HTML中的图表（两阶段编号策略）

        第一阶段生成的HTML使用临时占位符（如 __FIGURE_1__），此方法扫描整个HTML，
        按占位符出现的顺序重新编号，确保正文和附录的图表编号一致。

        Args:
            html_content: HTML内容

        Returns:
            重新编号后的HTML内容
        """
        import re

        try:
            # 1. 提取所有占位符ID及其位置
            placeholder_positions: list[tuple[str, int]] = []
            pattern = r"__FIGURE_(\d+)__"
            
            for match in re.finditer(pattern, html_content):
                placeholder_id = match.group(0)
                placeholder_positions.append((placeholder_id, match.start()))
            
            if not placeholder_positions:
                logger.debug("未找到图表占位符，无需重新编号")
                return html_content
            
            logger.debug(f"找到 {len(placeholder_positions)} 个图表占位符")
            
            # 2. 按出现顺序提取唯一的占位符
            unique_placeholders: list[str] = []
            seen = set()
            for placeholder_id, _ in placeholder_positions:
                if placeholder_id not in seen:
                    seen.add(placeholder_id)
                    unique_placeholders.append(placeholder_id)
            
            logger.debug(f"唯一占位符数量: {len(unique_placeholders)}")
            
            # 3. 创建占位符到新编号的映射
            placeholder_to_new_number: dict[str, str] = {}
            for i, placeholder_id in enumerate(unique_placeholders, 1):
                new_label = f"图{i}"
                placeholder_to_new_number[placeholder_id] = new_label
                logger.debug(f"映射: {placeholder_id} -> {new_label}")
            
            # 4. 替换所有占位符为新编号
            # 注意：需要使用字符串替换，因为占位符可能在多个地方出现（正文和附录）
            result_html = html_content
            for placeholder_id, new_label in placeholder_to_new_number.items():
                # 替换所有 occurrences
                count = result_html.count(placeholder_id)
                if count > 0:
                    result_html = result_html.replace(placeholder_id, new_label)
                    logger.debug(f"已替换 {count} 个 {placeholder_id} 为 {new_label}")
            
            logger.info(
                f"图表重新编号完成: 占位符数={len(unique_placeholders)}, 替换后HTML长度={len(result_html)}字符"
            )
            
            return result_html
            
        except Exception as e:
            logger.error(f"重新编号图表失败: {e}, 返回原始HTML", exc_info=True)
            return html_content

    def _generate_html_document(
        self,
        title: str,
        description: str | None,
        body: str,
        chart_configs: list[ChartConfig],
    ) -> str:
        """
        生成完整的HTML文档
        """
        # 生成附录（由 render_draft_to_html 负责传入合适的内容；此处保持空串）
        appendix_html = ""

        # ECharts脚本(内嵌,离线可用)
        echarts_script = self._get_echarts_script()

        # 使用用户输入的标题（如果为空则使用默认标题"白皮书"）
        page_title = title or "白皮书"
        description_html = (
            f'<div class="description">{self._escape_html(description)}</div>'
            if description
            else ""
        )
        header_html = (
            "<header>"
            f"<h1>{self._escape_html(page_title)}</h1>"
            f"{description_html}"
            "</header>"
        )

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self._escape_html(page_title)}</title>
    <style>
        {self._get_css_styles()}
    </style>
</head>
<body>
    <div class="container">
        {header_html}
        <main>
            {body}
        </main>
        {appendix_html}
    </div>
    {echarts_script}
</body>
</html>
"""
        return html

    def _get_echarts_script(self) -> str:
        """
        获取ECharts脚本

        注意: 当前使用CDN链接,需要网络连接才能加载图表.
        如需完全离线可用,可以:
        1. 下载ECharts脚本: https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js
        2. 将脚本内容内嵌到HTML中(替换下面的CDN链接)
        3. 或者将脚本保存为本地文件,使用相对路径引用

        Returns:
            ECharts脚本标签
        """
        # 使用CDN(需要网络连接)
        # 如需完全离线,请下载ECharts脚本并内嵌,或使用本地文件
        return """
    <!-- ECharts图表库 (CDN版本,需要网络连接) -->
    <!-- 如需完全离线使用,请下载 https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js 并内嵌 -->
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <script>
        // 确保所有图表在页面加载后初始化
        document.addEventListener('DOMContentLoaded', function() {
            // 图表初始化脚本已经在占位符替换时生成
            // 如果ECharts加载失败,显示错误提示
            if (typeof echarts === 'undefined') {
                console.error('ECharts库加载失败,请检查网络连接或使用离线版本');
                document.querySelectorAll('.chart-container').forEach(function(container) {
                    var errorDiv = document.createElement('div');
                    errorDiv.className = 'chart-error';
                    errorDiv.style.cssText = 'padding: 20px; background-color: #fee; border: 1px solid #fcc; color: #c33;';
                    errorDiv.textContent = '图表加载失败: ECharts库未加载. 请检查网络连接或使用离线版本.';
                    container.appendChild(errorDiv);
                });
            }
        });
    </script>
"""

    def _get_css_styles(self) -> str:
        """获取CSS样式"""
        return """
        :root {
            --primary-color: #1e40af;
            --primary-light: #3b82f6;
            --primary-dark: #1e3a8a;
            --secondary-color: #0891b2;
            --accent-color: #f59e0b;
            --text-color: #1f2937;
            --text-light: #6b7280;
            --bg-color: #ffffff;
            --section-bg: #f8fafc;
            --border-color: #e5e7eb;
            --card-bg: #ffffff;
            --success-color: #10b981;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: "PingFang SC", "Microsoft YaHei", "Inter", -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 2;
            color: var(--text-color);
            background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 100%);
            min-height: 100vh;
            padding: 60px 20px;
        }
        .container {
            max-width: 960px;
            margin: 0 auto;
            background-color: var(--bg-color);
            padding: 0;
            box-shadow: var(--shadow-lg);
            border-radius: 16px;
            overflow: hidden;
        }
        header {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
            margin-bottom: 0;
            padding: 60px 80px;
            text-align: center;
            color: #ffffff;
            position: relative;
        }
        header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.05'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            opacity: 0.5;
        }
        header h1 {
            font-size: 2.5em;
            font-weight: 700;
            margin-bottom: 20px;
            color: #ffffff;
            line-height: 1.3;
            position: relative;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        header .description {
            font-size: 1.15em;
            color: rgba(255,255,255,0.9);
            font-style: normal;
            position: relative;
        }
        .header-badge {
            display: inline-block;
            background: var(--accent-color);
            color: #ffffff;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.85em;
            margin-top: 20px;
            font-weight: 500;
        }
        main {
            margin-bottom: 0;
            padding: 50px 70px;
        }
        /* 正文段落缩进：更符合中文报告排版习惯 */
        main p {
            text-indent: 2em;
            margin: 0 0 18px 0;
        }
        /* 列表/表格/代码等场景不缩进 */
        main li p,
        main table p,
        main pre p,
        main blockquote p {
            text-indent: 0;
            margin: 0;
        }
        /* 摘要不缩进（摘要区单独样式，这里做兜底） */
        main .abstract p {
            text-indent: 0;
        }
        /* 摘要样式 */
        .abstract {
            background: linear-gradient(135deg, #fef9c3 0%, #fef3c7 100%);
            border: 1px solid #f59e0b;
            border-radius: 12px;
            padding: 30px 40px;
            margin: 40px 0 50px 0;
            position: relative;
        }
        .abstract::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #f59e0b 0%, #d97706 100%);
            border-radius: 12px 12px 0 0;
        }
        .abstract h2 {
            color: #92400e;
            font-size: 1.5em;
            margin-bottom: 20px;
            border-left: none;
            padding-left: 0;
            background: none;
            margin-top: 0;
        }
        .abstract h2::after {
            display: none;
        }
        .abstract p {
            color: #78350f;
            font-size: 1.05em;
            line-height: 1.8;
            margin-bottom: 15px;
        }
        .abstract ul {
            color: #78350f;
            margin-left: 20px;
        }
        .abstract li {
            margin-bottom: 10px;
            line-height: 1.7;
        }
        .abstract hr {
            border: none;
            border-top: 1px solid rgba(245, 158, 11, 0.3);
            margin: 25px 0;
        }
        .abstract .reference-note {
            font-size: 0.9em;
            color: #92400e;
            font-style: italic;
        }
        /* 长文档排版：使用响应式字号比例，确保层级稳定（h2 > h3 > h4） */
        h2, h3, h4 {
            scroll-margin-top: 90px;
        }
        h2 {
            font-size: clamp(1.35rem, 1.1rem + 1vw, 1.75rem);
            margin-top: 50px;
            margin-bottom: 25px;
            color: var(--primary-color);
            border-left: 5px solid var(--primary-color);
            padding-left: 20px;
            padding-top: 10px;
            padding-bottom: 10px;
            position: relative;
            background: linear-gradient(90deg, var(--section-bg) 0%, transparent 100%);
        }
        h2::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 1px;
            background: linear-gradient(90deg, var(--primary-color) 0%, transparent 100%);
        }
        h3 {
            font-size: clamp(1.15rem, 1.0rem + 0.6vw, 1.35rem);
            margin-top: 35px;
            margin-bottom: 18px;
            color: var(--secondary-color);
            font-weight: 600;
            position: relative;
            padding-left: 15px;
        }
        h3::before {
            content: '';
            position: absolute;
            left: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 4px;
            height: 1.2em;
            background: var(--secondary-color);
            border-radius: 2px;
        }
        h4 {
            font-size: clamp(1.05rem, 0.98rem + 0.4vw, 1.1rem);
            margin-top: 25px;
            margin-bottom: 12px;
            color: var(--text-color);
            font-weight: 600;
        }
        p {
            margin-bottom: 22px;
            text-align: justify;
            text-justify: inter-word;
            color: var(--text-color);
            line-height: 2;
        }
        .image-container, .chart-container {
            margin: 45px 0;
            padding: 30px;
            background: linear-gradient(145deg, #ffffff 0%, var(--section-bg) 100%);
            border-radius: 16px;
            border: 1px solid var(--border-color);
            text-align: center;
            transition: all 0.3s ease;
            box-shadow: var(--shadow-md);
        }
        .image-container:hover, .chart-container:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }
        .report-image {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: var(--shadow-md);
        }
        .image-caption, .chart-title {
            margin-top: 20px;
            font-size: 1em;
            font-weight: 600;
            color: var(--primary-color);
            padding: 12px 20px;
            background: var(--section-bg);
            border-radius: 8px;
            display: inline-block;
        }
        .chart-description {
            margin-top: 12px;
            font-size: 0.9em;
            color: var(--text-light);
        }
        .appendix {
            margin-top: 80px;
            padding-top: 50px;
            border-top: 3px solid var(--border-color);
            position: relative;
        }
        .appendix::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--primary-color) 0%, var(--secondary-color) 50%, var(--accent-color) 100%);
        }
        .appendix h2 {
            color: var(--text-light);
            border-left-color: var(--text-light);
        }
        .appendix-item {
            margin-bottom: 40px;
            padding: 30px;
            background: var(--section-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }
        .data-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin: 25px 0;
            background-color: #fff;
            font-size: 0.9em;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
        }
        .data-table th, .data-table td {
            padding: 14px 18px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        .data-table th {
            background: linear-gradient(135deg, var(--primary-color) 0%, var(--primary-dark) 100%);
            color: #fff;
            font-weight: 600;
            text-transform: none;
            letter-spacing: 0;
            font-size: 0.9em;
        }
        .data-table tr:first-child td {
            border-top: none;
        }
        .data-table tr td:first-child {
            border-left: none;
        }
        .data-table tr td:last-child {
            border-right: none;
        }
        .data-table tr:last-child td {
            border-bottom: none;
        }
        .data-table tr:nth-child(even) {
            background-color: #f9fafb;
        }
        .data-table tr:hover {
            background-color: #f0f7ff;
        }
        details {
            margin-top: 25px;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            overflow: hidden;
            background: #fff;
        }
        summary {
            cursor: pointer;
            font-weight: 600;
            padding: 16px 24px;
            background: var(--section-bg);
            outline: none;
            position: relative;
            padding-right: 50px;
        }
        summary::after {
            content: '▼';
            position: absolute;
            right: 20px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.8em;
            transition: transform 0.3s;
        }
        details[open] summary::after {
            transform: translateY(-50%) rotate(180deg);
        }
        summary:hover {
            background: #e5e7eb;
        }
        pre {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: #e2e8f0;
            padding: 24px;
            border-radius: 0 0 10px 10px;
            overflow-x: auto;
            font-size: 0.85em;
            line-height: 1.7;
        }
        code {
            font-family: "Fira Code", "Consolas", "Monaco", monospace;
        }
        table:not(.data-table) {
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
        }
        table:not(.data-table) th {
            background: var(--section-bg);
            color: var(--primary-color);
            font-weight: 600;
            padding: 14px 18px;
            text-align: left;
            border-bottom: 2px solid var(--primary-color);
        }
        table:not(.data-table) td {
            padding: 12px 18px;
            border-bottom: 1px solid var(--border-color);
        }
        table:not(.data-table) tr:hover {
            background: var(--section-bg);
        }

        /* Markdown表格（TableRenderer 输出的 rendered-table）：让“序号列最窄，地区列不挤成竖排” */
        table.rendered-table {
            width: 100%;
            border-collapse: collapse;
            table-layout: auto;
        }
        table.rendered-table th,
        table.rendered-table td {
            padding: 12px 18px;
            text-align: left;
            vertical-align: top;
            border-bottom: 1px solid var(--border-color);
        }
        table.rendered-table thead th {
            background: var(--section-bg);
            color: var(--primary-color);
            font-weight: 600;
            border-bottom: 2px solid var(--primary-color);
        }
        /* 序号列：固定窄宽度 + 不换行 */
        table.rendered-table th:first-child,
        table.rendered-table td:first-child {
            width: 4.5rem;
            white-space: nowrap;
        }
        /* 地区列：避免被挤到逐字换行（CJK 允许任意断行） */
        table.rendered-table th:nth-child(2),
        table.rendered-table td:nth-child(2) {
            min-width: 8rem;
            white-space: nowrap;
        }
        /* 百分比列：适度收紧 */
        table.rendered-table th:last-child,
        table.rendered-table td:last-child {
            width: 8.5rem;
            white-space: nowrap;
        }
        blockquote {
            border-left: 4px solid var(--primary-light);
            padding: 20px 30px;
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
            margin: 25px 0;
            color: var(--primary-dark);
            border-radius: 0 8px 8px 0;
        }
        blockquote p:last-child {
            margin-bottom: 0;
        }
        ul, ol {
            margin: 20px 0;
            padding-left: 30px;
        }
        li {
            margin-bottom: 10px;
            line-height: 1.8;
        }
        strong {
            color: var(--primary-color);
            font-weight: 600;
        }
        /* 参考文献样式 */
        .references {
            margin-top: 40px;
            padding: 30px;
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border-radius: 12px;
            border: 1px solid #f59e0b;
        }
        .references h3 {
            color: #92400e;
            margin-top: 0;
        }
        .references ol {
            color: #78350f;
            font-size: 0.95em;
        }
        .references li {
            margin-bottom: 12px;
            padding-left: 10px;
        }
        /* 附录独立表格样式 */
        .data-table-container {
            margin: 30px 0;
            padding: 25px;
            background: #fff;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow-md);
        }
        .data-table-container .chart-title {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--primary-color);
            color: var(--primary-color);
            font-size: 1.1em;
            font-weight: 600;
        }
        /* 附录图片样式 */
        .appendix-image-container {
            margin-bottom: 25px;
            text-align: center;
        }
        .appendix-image {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: var(--shadow-md);
        }
        /* 响应式设计 */
        @media (max-width: 768px) {
            body {
                padding: 20px 10px;
            }
            .container {
                border-radius: 12px;
            }
            header {
                padding: 40px 30px;
            }
            header h1 {
                font-size: 1.8em;
            }
            main {
                padding: 30px 25px;
            }
            h2 {
                font-size: 1.4em;
                padding-left: 15px;
            }
            h3 {
                font-size: 1.15em;
            }
            .image-container, .chart-container {
                padding: 20px;
                margin: 30px 0;
            }
        }
        """

