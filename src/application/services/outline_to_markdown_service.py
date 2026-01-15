"""
大纲转MD模板服务

该模块提供将优化后的大纲转换为Markdown模板的功能。
生成的MD模板可以作为草稿生成的单一数据源，确保结构准确性。

功能特性：
- 按层级生成标准的Markdown标题结构
- 在每个章节后插入内容占位符
- 支持字数要求和素材类型标注
- 自动推断父子关系和排序

使用示例：
    from src.application.services.outline_to_markdown_service import (
        OutlineToMarkdownService,
        SectionBlueprint,
    )
    
    service = OutlineToMarkdownService()
    template_path = service.save_optimized_outline_to_markdown(
        optimized_outline=outline,
        output_dir=Path("data/output/drafts"),
    )
"""

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.domain.agent.optimized_outline import (
    OptimizedOutline,
    OptimizedOutlineItem,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SectionBlueprint:
    """
    章节蓝图 - 描述MD模板中一个章节的结构信息
    
    Attributes:
        section_id: 章节唯一标识（从占位符提取）
        title: 章节标题（不含层级符号）
        level: 标题层级（1=#, 2=##, 3=###, 4=####）
        min_words: 最小字数要求
        max_words: 最大字数要求
        parent_section_id: 父章节ID（用于构建层级关系）
        order: 同级章节中的排序顺序
        description: 章节描述（从大纲项提取）
        prompt: 提示词（用于LLM生成，会传递给LLm但不会出现在最终HTML中）
    """
    section_id: str
    title: str
    level: int
    min_words: int = 500
    max_words: int = 800
    parent_section_id: str | None = None
    order: int = 0
    description: str | None = None
    prompt: str | None = None


@dataclass
class MarkdownTemplateResult:
    """MD模板生成结果"""
    template_path: Path
    template_content: str
    section_blueprints: list[SectionBlueprint]
    outline_id: str


class OutlineToMarkdownService:
    """
    大纲转MD模板服务
    
    提供将 OptimizedOutline 转换为标准 Markdown 模板的功能。
    生成的模板可以作为草稿生成的单一数据源，确保结构准确性。
    
    核心方法：
        save_optimized_outline_to_markdown(): 将大纲保存为MD模板
        parse_markdown_to_blueprints(): 从MD模板解析章节蓝图
    """
    
    # 占位符格式模板
    PLACEHOLDER_TEMPLATE = (
        "[CONTENT_PLACEHOLDER:"
        "section_id={section_id},"
        "min_words={min_words},"
        "max_words={max_words}]"
    )
    
    # 标题层级符号映射
    HEADING_SYMBOLS = {
        1: "#",
        2: "##",
        3: "###",
        4: "####",
        5: "#####",
        6: "######",
    }
    
    # 章节类型对应的字数要求（默认）
    DEFAULT_WORD_COUNTS = {
        "SECTION": (800, 1200),      # 一级章节：800-1200字
        "SUBSECTION": (500, 800),    # 二级章节：500-800字
        "PARAGRAPH": (300, 500),     # 三级章节：300-500字
        "CONTENT": (200, 400),       # 内容段落：200-400字
    }
    
    def __init__(self, base_output_dir: Path | None = None):
        """
        初始化服务
        
        Args:
            base_output_dir: 基础输出目录，默认为 data/output/drafts
        """
        # 重要：不要用 cwd 解析相对路径（API/worker/pytest 的工作目录可能不在项目根）
        # 统一以项目根目录为基准，确保模板读写稳定落在 <repo>/data/output/drafts
        from src.shared.config.settings import _find_project_root

        project_root = _find_project_root()
        base_output_dir = base_output_dir or Path("data/output/drafts")
        self.base_output_dir = (
            base_output_dir
            if base_output_dir.is_absolute()
            else (project_root / base_output_dir).resolve()
        )
        logger.info(
            "OutlineToMarkdownService 初始化完成: 输出目录=%s",
            self.base_output_dir
        )
    
    def save_optimized_outline_to_markdown(
        self,
        optimized_outline: OptimizedOutline,
        output_dir: Path | None = None,
        filename: str | None = None,
    ) -> MarkdownTemplateResult:
        """
        将优化后的大纲保存为Markdown模板
        
        该方法执行以下操作：
        1. 按层级结构生成Markdown标题
        2. 为每个章节插入内容占位符
        3. 生成唯一的文件路径并保存
        4. 返回模板路径和章节蓝图列表
        
        Args:
            optimized_outline: 优化后的大纲对象
            output_dir: 输出目录（覆盖基础目录）
            filename: 文件名（默认使用 outline_id）
            
        Returns:
            MarkdownTemplateResult: 包含模板路径、内容和章节蓝图的 Result 对象
            
        Example:
            >>> service = OutlineToMarkdownService()
            >>> result = service.save_optimized_outline_to_markdown(outline)
            >>> print(f"模板已保存: {result.template_path}")
            >>> print(f"章节数量: {len(result.section_blueprints)}")
        """
        # 确定输出目录和文件名
        output_dir = output_dir or self.base_output_dir
        outline_id = str(optimized_outline.id)
        
        if filename is None:
            filename = f"outline_template_{outline_id}.md"
        
        template_path = output_dir / filename
        # 确保输出目录存在
        template_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 1. 转换为章节蓝图
        blueprints = self._convert_to_blueprints(optimized_outline)
        
        # 2. 生成Markdown内容
        markdown_content = self._generate_markdown_content(
            optimized_outline=optimized_outline,
            blueprints=blueprints,
        )
        
        # 3. 保存到文件
        try:
            template_path.write_text(markdown_content, encoding="utf-8")
            logger.info(
                "MD模板已保存: 路径=%s, 章节数=%d",
                template_path,
                len(blueprints)
            )
        except Exception as e:
            logger.error("保存MD模板失败: 路径=%s, 错误=%s", template_path, e)
            raise
        
        return MarkdownTemplateResult(
            template_path=template_path,
            template_content=markdown_content,
            section_blueprints=blueprints,
            outline_id=outline_id,
        )
    
    def _has_sequence_number(self, title: str) -> bool:
        """
        检测标题是否包含序号（必须出现在标题开头）
        
        支持的序号格式：
        - 阿拉伯数字：1. 2) 3） (1) （2）
        - 中文数字：一、二、三、 （一）（二）
        - 字母序号：A. B) (A) （B）
        - 罗马数字：I. II) (I) （II）
        
        Args:
            title: 标题文本
            
        Returns:
            如果标题开头包含序号则返回True，否则返回False
        """
        if not title or not title.strip():
            return False
        
        title = title.strip()
        
        # 匹配开头的序号模式
        patterns = [
            r'^[\d]+(\.[\d]+)*[\.\)）]\s*',  # 数字序号：1. 2) 3） 1.1. 7.2.1. 1.1.1.
            r'^[（(][\d]+[）)]\s*',  # 括号数字：(1) （2）
            r'^[一二三四五六七八九十百千万]+[、，.．]\s*',  # 中文数字：一、二、
            r'^[（(][一二三四五六七八九十百千万]+[）)]\s*',  # 括号中文：（一）（二）
            r'^[A-Za-z][\.\)）]\s*',  # 字母序号：A. B) c)
            r'^[（(][A-Za-z][）)]\s*',  # 括号字母：(A) （B）
            r'^[IVX]+[\.\)）]\s*',  # 罗马数字：I. II) IV)
            r'^[（(][IVX]+[）)]\s*',  # 括号罗马：(I) （II）
            r'^[①②③④⑤⑥⑦⑧⑨⑩]',  # 圆圈数字：①②③
            r'^[㈠㈡¶æ',  # 括号中文数字：¶æ
        ]
        
        for pattern in patterns:
            if re.match(pattern, title):
                return True
        
        return False
    
    def _get_heading_level(self, title: str) -> int | None:
        """
        根据标题格式判断层级
        
        Args:
            title: 标题文本
            
        Returns:
            层级（2=一级章节，3=二级章节，4=三级章节），无法识别返回None
        """
        # 一级章节：第x章、第x篇
        if re.match(r'^第[一二三四五六七八九十百千]+[章篇]', title):
            return 2
        
        # 附录、摘要、结论等特殊章节
        if re.match(r'^(附录|摘要|结论|前言|引言)', title):
            return 2
        
        # 二级章节：x.x. 或 x) 格式（1.1.、2.3.）
        if re.match(r'^[\d]+\.[\d]+[\.）)]', title):
            return 3
        
        # 三级章节：x.x.x. 格式（1.1.1.）
        if re.match(r'^[\d]+\.[\d]+\.[\d]+', title):
            return 4
        
        # 中文数字序号：x、y、z（作为二级章节）
        if re.match(r'^[一二三四五六七八九十]+[、]', title):
            return 3
        
        return None
    
    def _extract_title_from_numbered_line(self, line: str) -> str:
        """
        从带序号的行中提取标题（去除序号部分）
        
        Args:
            line: 带序号的行
            
        Returns:
            纯标题文本
        """
        # 去除各种序号格式
        patterns = [
            r'^[\d]+\.[\d]+[\.）)]?\s*',  # 1.1. 1)
            r'^[\d]+\.[\d]+\.[\d]+[\.）)]?\s*',  # 1.1.1.
            r'^[\d]+[\.）)]\s*',  # 1. 2)
            r'^[\d]+[\.）)]?\s*',  # 1 2
            r'^[一二三四五六七八九十]+[、]',  # 一、二、
        ]
        
        for pattern in patterns:
            line = re.sub(pattern, '', line)
        
        return line.strip()
    
    def _convert_to_blueprints(
        self,
        optimized_outline: OptimizedOutline,
    ) -> list[SectionBlueprint]:
        """
        将优化大纲转换为章节蓝图列表
        
        Args:
            optimized_outline: 优化后的大纲
            
        Returns:
            按层级排序的章节蓝图列表
        """
        blueprints: list[SectionBlueprint] = []
        
        # 构建ID映射：optimized_item.id -> blueprint.section_id
        id_mapping: dict[uuid.UUID, str] = {}
        
        # 第一遍：创建所有蓝图，建立ID映射
        for idx, item in enumerate(optimized_outline.optimized_items):
            optimized_item = item.optimized_item
            
            # 获取章节类型对应的默认字数
            item_type = str(optimized_item.item_type)
            min_words, max_words = self.DEFAULT_WORD_COUNTS.get(
                item_type,
                (500, 800)
            )
            
            # 创建蓝图
            blueprint = SectionBlueprint(
                section_id=str(optimized_item.id),
                title=optimized_item.title or "未命名章节",
                level=int(optimized_item.level or 1),
                min_words=min_words,
                max_words=max_words,
                order=int(optimized_item.order or idx),
                description=optimized_item.description,
            )
            
            blueprints.append(blueprint)
            id_mapping[optimized_item.id] = blueprint.section_id
        
        # 第二遍：推断父子关系
        for item in optimized_outline.optimized_items:
            optimized_item = item.optimized_item
            
            if optimized_item.parent_id:
                # 从ID映射中获取父章节的blueprint ID
                parent_blueprint_id = id_mapping.get(optimized_item.parent_id)
                
                # 找到当前章节的blueprint并设置parent_id
                current_blueprint_id = id_mapping.get(optimized_item.id)
                for bp in blueprints:
                    if bp.section_id == current_blueprint_id:
                        bp.parent_section_id = parent_blueprint_id
                        break
        
        # 按层级和order排序
        sorted_blueprints = sorted(
            blueprints,
            key=lambda bp: (bp.level, bp.order)
        )
        
        logger.debug(
            "转换为章节蓝图: 总数=%d",
            len(sorted_blueprints)
        )
        
        return sorted_blueprints
    
    def _generate_markdown_content(
        self,
        optimized_outline: OptimizedOutline,
        blueprints: list[SectionBlueprint],
    ) -> str:
        """
        生成Markdown模板内容（简洁版，不生成占位符）
        
        规则说明：
        - 一级章节（level=1）使用 ## 标题
        - 子章节（level>1）作为提示词合并到父章节，不输出为独立标题
        - 章节描述直接作为提示词，在模板中清晰可见
        
        Args:
            optimized_outline: 优化后的大纲
            blueprints: 章节蓝图列表
            
        Returns:
            Markdown格式的模板内容（简洁的大纲格式）
        """
        lines: list[str] = []

        # 1. 添加文档标题（使用大纲标题或默认标题）
        doc_title = optimized_outline.metadata.get(
            "title",
            "白皮书草稿"
        )
        lines.append(f"# {doc_title}\n")

        # 2. 构建章节树：按parent_section_id组织
        # 所有章节索引：section_id -> blueprint（用于查找父章节）
        all_blueprints_by_id: dict[str, SectionBlueprint] = {
            bp.section_id: bp for bp in blueprints
        }
        
        # 一级章节索引：section_id -> blueprint（没有parent_section_id的章节为一级章节）
        section_by_id: dict[str, SectionBlueprint] = {}
        # 子章节索引：parent_section_id -> list[blueprint]
        children_by_parent: dict[str, list[SectionBlueprint]] = {}
        
        # 第一遍：找出所有一级章节（没有parent_section_id的章节）
        for blueprint in blueprints:
            if blueprint.parent_section_id is None:
                # 没有父章节的为一级章节（根章节）
                section_by_id[blueprint.section_id] = blueprint
                children_by_parent[blueprint.section_id] = []
        
        # 第二遍：将所有子章节归类到父章节下，同时检查父章节是否存在
        for blueprint in blueprints:
            parent_id = blueprint.parent_section_id
            if parent_id and parent_id in all_blueprints_by_id:
                # 父章节存在，将当前章节归类到父章节下
                if parent_id not in children_by_parent:
                    children_by_parent[parent_id] = []
                children_by_parent[parent_id].append(blueprint)
            elif parent_id:
                # 父章节ID存在但父章节不存在于蓝图中，记录警告并将当前章节作为一级章节
                logger.warning(
                    "章节 '%s' 的父章节 '%s' 不存在，将作为一级章节处理",
                    blueprint.title,
                    parent_id
                )
                if blueprint.section_id not in section_by_id:
                    section_by_id[blueprint.section_id] = blueprint
                    children_by_parent[blueprint.section_id] = []
        
        # 如果没有找到一级章节（所有章节都有parent_section_id），说明可能是数据问题
        # 兜底处理1：将所有没有有效父章节的章节作为一级章节
        if not section_by_id:
            logger.warning(
                "未找到一级章节（所有章节都有parent_section_id），将使用兜底逻辑1"
            )
            for blueprint in blueprints:
                parent_id = blueprint.parent_section_id
                # 检查父章节是否存在
                if not parent_id or parent_id not in all_blueprints_by_id:
                    # 父章节不存在，将当前章节作为一级章节
                    section_by_id[blueprint.section_id] = blueprint
                    children_by_parent[blueprint.section_id] = []
        
        # 兜底处理2：如果仍然没有找到一级章节，说明所有章节都有有效的parent_id
        # 这种情况下，找出所有没有被其他章节指向的章节作为一级章节（根章节）
        if not section_by_id:
            logger.warning(
                "所有章节都有有效的parent_section_id，将找出所有根章节作为一级章节"
            )
            # 找出所有被其他章节指向的章节ID
            referenced_ids = {
                bp.parent_section_id
                for bp in blueprints
                if bp.parent_section_id and bp.parent_section_id in all_blueprints_by_id
            }
            # 找出所有没有被指向的章节作为一级章节
            for blueprint in blueprints:
                if blueprint.section_id not in referenced_ids:
                    section_by_id[blueprint.section_id] = blueprint
                    children_by_parent[blueprint.section_id] = []
        
        # 最终兜底：如果仍然没有找到一级章节（可能所有章节形成循环引用），
        # 将第一个章节作为一级章节
        if not section_by_id:
            logger.error(
                "无法找到一级章节，所有章节可能形成循环引用。将第一个章节作为一级章节（兜底）"
            )
            if blueprints:
                first_blueprint = blueprints[0]
                section_by_id[first_blueprint.section_id] = first_blueprint
                children_by_parent[first_blueprint.section_id] = []
        
        # 4. 为每个一级章节生成内容
        # 按order排序一级章节
        sorted_sections = sorted(
            section_by_id.values(),
            key=lambda bp: bp.order
        )
        
        for section_blueprint in sorted_sections:
            # 添加空行分隔
            if lines and lines[-1].strip():
                lines.append("")
            
            # 添加一级标题
            lines.append(f"## {section_blueprint.title}\n")
            
            # 收集提示词：章节自身描述 + 无序号的子章节
            prompt_parts = []
            
            # 章节自身的描述（作为主要提示词）
            if section_blueprint.description:
                prompt_parts.append(section_blueprint.description)
            
            # 获取所有子章节
            child_blueprints = children_by_parent.get(section_blueprint.section_id, [])
            # 按order排序子章节
            child_blueprints = sorted(child_blueprints, key=lambda bp: bp.order)
            
            # 区分子章节和提示词
            real_subsections: list[SectionBlueprint] = []  # 有序号的真正子章节
            prompt_subsections: list[SectionBlueprint] = []  # 无序号作为提示词的子章节
            
            for child_bp in child_blueprints:
                if self._has_sequence_number(child_bp.title):
                    # 有序号：真正的子章节
                    real_subsections.append(child_bp)
                else:
                    # 无序号：作为提示词
                    prompt_subsections.append(child_bp)
            
            # 合并无序号子章节到提示词
            for prompt_bp in prompt_subsections:
                prompt_text = prompt_bp.title
                if prompt_bp.description:
                    prompt_text += "：" + prompt_bp.description
                prompt_parts.append(prompt_text)
            
            # 保存提示词到blueprint.prompt（用于后续传递给LLM）
            if prompt_parts:
                section_blueprint.prompt = "。".join(prompt_parts)
            
            # 直接在模板中显示提示词（使用注释格式，不会出现在最终HTML中）
            if section_blueprint.prompt:
                lines.append(f"**提示词**：{section_blueprint.prompt}\n")
            
            # 添加有序号的真正子章节（作为章节结构的一部分）
            for subsection_bp in real_subsections:
                lines.append(f"    {subsection_bp.title}\n")
                
                # 子章节的描述作为提示词（如果有）
                if subsection_bp.description:
                    subsection_bp.prompt = subsection_bp.description
                    lines.append(f"    **提示词**：{subsection_bp.prompt}\n")
        
        return "\n".join(lines)
    
    def parse_markdown_to_blueprints(
        self,
        template_path: Path,
    ) -> list[SectionBlueprint]:
        """
        从MD模板解析章节蓝图
        
        用于草稿生成时读取MD模板的结构信息。
        支持多种格式的模板：
        1. 粗体格式：**标题**、**第一章：xxx**
        2. 标准格式：# 标题、## 标题
        3. 列表格式：1.1. xxx、2.3. xxx
        
        所有标题都会被解析，包括一级章节和子章节，
        并根据层级和位置自动构建父子关系。
        
        Args:
            template_path: MD模板文件路径
            
        Returns:
            章节蓝图列表
            
        Raises:
            FileNotFoundError: 如果模板文件不存在
            ValueError: 如果模板格式不正确
        """
        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")
        
        content = template_path.read_text(encoding="utf-8")
        
        # 查找所有标题
        # 支持多种格式：
        # 1. 粗体格式：**标题**
        # 2. 标准格式：# 标题
        # 3. 列表/编号行：1.1 xxx、2.3 xxx、1.1.1 xxx（带序号的行；常见于 outline_template）
        
        # 匹配 **xxx** 格式
        bold_heading_pattern = re.compile(
            r"^\s*\*\*(.+?)\*\*\s*$",
            re.MULTILINE
        )
        bold_matches = list(bold_heading_pattern.finditer(content))
        
        # 匹配 # 标题 格式
        hash_heading_pattern = re.compile(
            r"^\s*(#{1,6})\s+(.+?)$",
            re.MULTILINE
        )
        hash_matches = list(hash_heading_pattern.finditer(content))

        # 匹配“编号行标题”格式：
        # - 1.1 xxx
        # - 1.1.1 xxx
        # 注意：不要求末尾有 '.'，因为模板里常见写法是 "1.1 标题"
        list_heading_pattern = re.compile(
            r"^\s*(\d+(?:\.\d+)+)\s+(.+?)\s*$",
            re.MULTILINE,
        )
        list_matches = list(list_heading_pattern.finditer(content))
        
        # 合并所有匹配结果
        all_headings: list[dict] = []
        
        for m in bold_matches:
            title = m.group(1).strip()
            level = self._get_heading_level(title)
            if level:
                all_headings.append({
                    'type': 'bold',
                    'start': m.start(),
                    'end': m.end(),
                    'title': title,
                    'level': level,
                    'line_number': content[:m.start()].count('\n'),
                })
        
        for m in hash_matches:
            hash_count = len(m.group(1))
            title = m.group(2).strip()
            # # 标题对应 level+1（因为文档标题用 #）
            level = hash_count + 1 if hash_count < 6 else 6
            all_headings.append({
                'type': 'hash',
                'start': m.start(),
                'end': m.end(),
                'title': title,
                'level': level,
                'line_number': content[:m.start()].count('\n'),
            })

        for m in list_matches:
            number = m.group(1).strip()
            text = m.group(2).strip()
            if not number or not text:
                continue
            # level 规则：
            # - 1.1 -> level 3（章节下的小节）
            # - 1.1.1 -> level 4（小节下的子小节）
            dot_count = number.count(".")
            level = min(3 + max(dot_count - 1, 0), 6)
            title = f"{number} {text}"
            all_headings.append(
                {
                    "type": "list",
                    "start": m.start(),
                    "end": m.end(),
                    "title": title,
                    "level": level,
                    "line_number": content[: m.start()].count("\n"),
                }
            )
        
        # 合并所有标题后按位置排序
        all_headings.sort(key=lambda x: x['start'])
        
        # 去重（同位置的保留一个）
        unique_headings: list[dict] = []
        seen_positions: set[int] = set()
        for h in all_headings:
            pos = h['line_number']
            if pos not in seen_positions:
                unique_headings.append(h)
                seen_positions.add(pos)
        
        if not unique_headings:
            logger.warning("MD模板中未找到任何标题: %s", template_path)
            return []

        logger.debug(
            "MD模板标题匹配结果: 路径=%s, 总标题数=%d",
            template_path,
            len(unique_headings)
        )

        # 跳过文档标题（通常是第一个，带书名号）
        if len(unique_headings) > 1:
            first_title = unique_headings[0]['title']
            if len(first_title) > 10 and ('《' in first_title or '白皮书' in first_title or '报告' in first_title):
                logger.debug("跳过文档标题: %s", first_title)
                unique_headings = unique_headings[1:]
        
        # 构建章节蓝图列表
        blueprints: list[SectionBlueprint] = []
        
        # 跟踪同级别的最后一个章节ID，用于推断父章节
        last_of_level: dict[int, str] = {}
        
        for idx, h in enumerate(unique_headings):
            title = h['title']
            level = h['level']
            
            # 生成 section_id（基于标题的稳定UUID）
            section_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{title}_{idx}"))
            
            # 推断父章节：找最近的前一个较低层级的章节
            parent_id = None
            for check_level in range(level - 1, 0, -1):
                if check_level in last_of_level:
                    parent_id = last_of_level[check_level]
                    break
            
            # 更新同级别的最后一个章节ID
            last_of_level[level] = section_id
            
            # 提取章节描述：从标题后到下一个标题之间的内容
            section_start = h['end']
            
            # 找到下一个标题的开始位置
            next_heading_start = len(content)
            if idx + 1 < len(unique_headings):
                next_heading_start = unique_headings[idx + 1]['start']
            
            # 提取章节内容
            section_content = content[section_start:next_heading_start]
            
            # 移除占位符行，提取描述文本
            description_lines = []
            for line in section_content.split('\n'):
                line = line.strip()
                # 跳过空行和占位符
                if not line or line.startswith('[') or line.startswith('**提示词**'):
                    continue
                # 跳过列表项（其他子章节）
                if re.match(r'^[\d\.]+[\.\)）\s]', line):
                    continue
                # 跳过中文序号行
                if re.match(r'^[一二三四五六七八九十]+[、.．]', line):
                    continue
                # 跳过缩进的列表项
                if re.match(r'^\s{2,8}[\d\w]', line):
                    continue
                if line:
                    description_lines.append(line)
            
            description = ' '.join(description_lines) if description_lines else None
            
            # 根据层级设置默认字数
            if level == 2:
                min_words, max_words = 800, 1200
            elif level == 3:
                min_words, max_words = 500, 800
            else:
                min_words, max_words = 300, 500
            
            blueprint = SectionBlueprint(
                section_id=section_id,
                title=title,
                level=level,
                min_words=min_words,
                max_words=max_words,
                parent_section_id=parent_id,
                order=idx,
                description=description,
                prompt=description,
            )
            blueprints.append(blueprint)
        
        # 按order排序
        blueprints = sorted(blueprints, key=lambda bp: bp.order)
        
        logger.debug(
            "从MD模板解析章节蓝图: 路径=%s, 章节数=%d",
            template_path,
            len(blueprints)
        )
        
        return blueprints
    
    def _parse_placeholder_params(self, params_str: str) -> dict[str, Any]:
        """
        解析占位符参数字符串
        
        Args:
            params_str: 参数字符串，如 "section_id=xxx,min_words=500"
            
        Returns:
            参数字典
        """
        params = {}
        for part in params_str.split(","):
            if "=" in part:
                key, value = part.split("=", 1)
                key = key.strip()
                value = value.strip()
                
                # 类型转换
                if key in ("min_words", "max_words"):
                    value = int(value)
                
                params[key] = value
        
        return params
    
    def get_template_path(
        self,
        outline_id: str | uuid.UUID,
        output_dir: Path | None = None,
    ) -> Path | None:
        """
        获取指定大纲的MD模板路径
        
        Args:
            outline_id: 大纲ID
            output_dir: 输出目录
            
        Returns:
            模板路径，如果不存在则返回None
        """
        output_dir = output_dir or self.base_output_dir
        # 同样确保 output_dir 以项目根目录为基准
        if not output_dir.is_absolute():
            from src.shared.config.settings import _find_project_root

            project_root = _find_project_root()
            output_dir = (project_root / output_dir).resolve()
        outline_id_str = str(outline_id)
        
        # 尝试多种可能的文件名
        possible_names = [
            f"outline_template_{outline_id_str}.md",
            f"{outline_id_str}.md",
        ]
        
        for name in possible_names:
            path = output_dir / name
            if path.exists():
                return path
        
        return None
    
    def template_exists(
        self,
        outline_id: str | uuid.UUID,
        output_dir: Path | None = None,
    ) -> bool:
        """
        检查指定大纲的MD模板是否存在
        
        Args:
            outline_id: 大纲ID
            output_dir: 输出目录
            
        Returns:
            是否存在
        """
        return self.get_template_path(outline_id, output_dir) is not None


# 便利函数


def create_outline_to_markdown_service(
    base_output_dir: str | Path | None = None,
) -> OutlineToMarkdownService:
    """
    创建大纲转MD模板服务的便捷函数
    
    Args:
        base_output_dir: 基础输出目录
        
    Returns:
        OutlineToMarkdownService 实例
    """
    if base_output_dir:
        base_output_dir = Path(base_output_dir)
    
    return OutlineToMarkdownService(base_output_dir=base_output_dir)
