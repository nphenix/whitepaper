"""
大纲规范化服务

该服务负责将用户输入的各种格式的大纲文本转换为标准的Markdown格式，
去除噪音，生成结构清晰的大纲。
"""

# 生成命令: /speckit.implement T250
# 生成时间: 2026-01-08
# 来源: 用户反馈

import uuid
from typing import Any

from src.application.services.base_service import BaseService
from src.shared.config.llm_service import LLMService
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class OutlineNormalizerService(BaseService):
    """
    大纲规范化服务

    将用户输入的文本转换为标准的Markdown大纲格式，
    去除噪音，生成层级清晰的结构。
    """

    def get_service_name(self) -> str:
        """
        获取服务名称

        Returns:
            服务名称字符串
        """
        return "outline_normalizer_service"

    def __init__(self, llm_service: LLMService | None = None):
        """
        初始化大纲规范化服务

        Args:
            llm_service: LLM服务实例，如果为None则创建新实例
        """
        super().__init__()
        self.llm_service = llm_service or LLMService()

    def normalize_outline_text(
        self,
        raw_text: str,
        title: str = "白皮书大纲",
        report_type: str = "市场研究报告",
    ) -> str:
        """
        将用户输入的大纲文本转换为标准Markdown格式

        Args:
            raw_text: 用户原始输入的文本
            title: 大纲标题
            report_type: 报告类型

        Returns:
            标准Markdown格式的大纲文本
        """
        try:
            # 构建提示词
            system_prompt = """你是一位专业的文档结构化专家。你的任务是将用户提供的任意格式的大纲输入转换为标准的Markdown格式。

转换要求：
1. 【重要】每个章节标题必须独立成行，不能与其他内容混在同一行
2. 一级章节使用 ## 开头，二级章节使用 ### 开头，三级章节使用 #### 开头
3. 章节标题后面必须直接换行，不能在同一行添加任何描述、冒号、提示词等内容
4. 不同章节之间必须用空行分隔，确保每个章节标题都是独立的一行
5. 不要包含"提示词"、"摘要"、"执行摘要"、"---"等标记
6. 不要在章节标题后面添加冒号或描述内容

正确示例：
## 第一章 引言

### 1.1. 双碳目标下的储能战略定位

### 1.2. 新型电力系统中的储能功能

## 第二章 全球储能发展

### 2.1. 主要经济体储能政策比较

错误示例（禁止）：
## 第一章 引言：储能的时代使命（禁止在同一行添加冒号和描述）
## 第一章 引言 ### 1.1. 双碳目标（禁止把多个标题放在同一行）
## 第一章 引言
**提示词**：摘要。第一章：...（禁止在章节后添加提示词标记）

请直接输出转换后的Markdown大纲，每个标题独立一行，标题后直接换行。"""

            user_prompt = f"""请将以下用户输入的大纲文本转换为标准Markdown格式：

【报告类型】
{report_type}

【大纲标题】
{title}

【用户原始输入】
{raw_text}

请转换为标准的Markdown格式。"""

            # 调用LLM进行转换
            model = self.llm_service.get_chat_model()
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = model.invoke(messages)
            result = response.content if hasattr(response, "content") else str(response)

            # 清理结果，确保是有效的Markdown格式
            result = self._cleanup_markdown(result)

            logger.info("大纲文本规范化完成，输入长度=%d，输出长度=%d", len(raw_text), len(result))
            return result

        except Exception as e:
            logger.error("大纲文本规范化失败: %s", e, exc_info=True)
            # 如果规范化失败，尝试简单的清理后返回
            return self._fallback_normalize(raw_text, title)

    def _cleanup_markdown(self, text: str) -> str:
        """
        清理Markdown文本，移除可能的解释性文字

        Args:
            text: 原始Markdown文本

        Returns:
            清理后的Markdown文本
        """
        if not text:
            return text

        # 移除可能的代码块标记（如果LLM错误地添加了）
        text = text.strip()

        # 如果文本被包裹在 ```markdown 和 ``` 中，提取内容
        if text.startswith("```markdown"):
            text = text[len("```markdown"):].strip()
        elif text.startswith("```"):
            # 尝试找到真正的markdown内容
            lines = text.split("\n")
            if len(lines) >= 2:
                # 找到第一个非```行作为开始
                start_idx = 0
                for i, line in enumerate(lines):
                    if not line.strip().startswith("```"):
                        start_idx = i
                        break
                # 从内容开始的地方取到最后
                text = "\n".join(lines[start_idx:]).strip()
                # 移除结尾的 ```
                if text.endswith("```"):
                    text = text[:-3].strip()

        return text

    def _fallback_normalize(self, raw_text: str, title: str) -> str:
        """
        简单的规范化备用方案

        Args:
            raw_text: 原始文本
            title: 标题

        Returns:
            简单的Markdown格式
        """
        lines = raw_text.strip().split("\n")
        markdown_lines = [f"# {title}\n"]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 简单的模式匹配
            import re

            # 检测数字序号开头的行
            num_match = re.match(r"^(\d+)\.\s*(.+)", line)
            if num_match:
                markdown_lines.append(f"## {line}")
                continue

            # 检测中文序号开头的行
            cn_match = re.match(r"^([一二三四五六七八九十]+)[、.](.+)", line)
            if cn_match:
                markdown_lines.append(f"## {line}")
                continue

            # 检测短横线开头的行
            if line.startswith("-"):
                markdown_lines.append(f"- {line[1:].strip()}")
                continue

            # 其他行作为普通段落
            markdown_lines.append(line)

        return "\n".join(markdown_lines)
