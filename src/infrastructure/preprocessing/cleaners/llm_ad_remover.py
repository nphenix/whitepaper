"""
基于LLM的广告清洗器

使用LangChain 1.0的Agent框架和中间件机制实现智能广告清洗。
支持动态模型调用、结构化输出、错误处理和重试机制。

本模块所有文本处理均使用UTF-8编码,确保正确处理中文和其他Unicode字符。

生成命令: /speckit.implement T030A-LLM-AdRemover
生成时间: 2025-12-14
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import time

from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from src.infrastructure.preprocessing.cleaners.summarization_middleware import (
    SummarizationHelper,
)
from src.infrastructure.preprocessing.error_handler import (
    LLMAdRemoverError,
    preprocessing_error_handler,
)
from src.infrastructure.preprocessing.logging_config import (
    create_llm_remover_logger,
)
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger
from src.shared.utils.retry import RetryConfig, RetryHandler

# 注意:UTF-8编码处理由日志系统统一管理,不需要在这里修改sys.stdout/stderr
# 直接修改sys.stdout/stderr会导致文件对象关闭问题

logger = get_logger(__name__)


class AdCleaningResult(BaseModel):
    """广告清洗结果结构化输出模型(仅用于文档说明,不再强制使用)"""

    cleaned_content: str = Field(description="清洗后的Markdown文档内容")
    removed_items: list[str] = Field(
        default_factory=list, description="被移除的内容摘要列表"
    )
    preserved_items: list[str] = Field(
        default_factory=list, description="保留的内容摘要列表"
    )
    cleaning_summary: str = Field(default="", description="清洗过程摘要说明")


class LLMAdRemover:
    """
    基于LLM的广告清洗器

    直接调用LLM模型进行广告清洗,支持:
    1. 分段处理大文档
    2. 重试机制
    3. 批量处理

    必须从T009创建的llm_service获取模型实例。

    注意:不使用LangChain的Agent框架,直接调用模型以提高兼容性。
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        max_retries: int = 3,
        retry_delay: float = 3.0,  # 默认3秒,使用指数退避策略
        summarization_max_tokens: int = 100000,
        summarization_chunk_size: int = 50000,
        summarization_overlap_size: int = 5000,
        summarization_enabled: bool = False,
    ):
        """初始化LLM广告清洗器

        Args:
            llm_service: LLM服务实例(从T009获取),如果为None则使用全局实例
            max_retries: 最大重试次数
            retry_delay: 重试延迟(秒)
            enable_summarization: 是否启用总结功能(默认False)
            summarization_max_tokens: 总结阈值(字符数),超过此值将触发总结
            summarization_chunk_size: 总结分段大小(字符数)
            summarization_overlap_size: 总结分段重叠大小(字符数)
        """
        self.llm_service = llm_service or get_llm_service()

        # 初始化重试处理器
        retry_config = RetryConfig(
            max_retries=max_retries,
            retry_delay=retry_delay,
        )
        self.retry_handler = RetryHandler(retry_config)

        # 初始化总结辅助类(如果启用)
        self.summarization_helper: SummarizationHelper | None = None
        if summarization_enabled:
            self.summarization_helper = SummarizationHelper(
                max_tokens=summarization_max_tokens,
                chunk_size=summarization_chunk_size,
                overlap_size=summarization_overlap_size,
                llm_service=self.llm_service,
                enabled=True,
            )
            logger.info("总结功能已启用")

        # 创建专用的日志记录器
        self.preprocessing_logger = create_llm_remover_logger()

        # 获取广告清洗模型(必须从llm_service获取)
        try:
            self.model = self.llm_service.get_ad_cleaning_chat_model()
            logger.info("成功获取广告清洗模型")
        except Exception as e:
            error = LLMAdRemoverError(
                f"无法获取广告清洗模型: {e}",
                error_code="MODEL_INIT_ERROR",
                original_error=e,
                model_name="ad_cleaning_chat_model",
            )
            preprocessing_error_handler.log_llm_cleaning_error(error, "initialization")
            raise error from e

        # 获取配置
        try:
            config = self.llm_service._config
            if config and hasattr(config, "ad_cleaning_llm"):
                self.config_max_tokens = config.ad_cleaning_llm.max_tokens
                # 从配置读取上下文窗口,如果没有设置则使用 max_tokens 的值
                # 因为对于大多数模型,max_tokens 通常接近上下文窗口大小
                context_window = getattr(config.ad_cleaning_llm, "context_window", None)
                self.model_context_window = (
                    context_window if context_window else self.config_max_tokens
                )
                logger.info(
                    "从配置获取: max_tokens=%d, context_window=%d",
                    self.config_max_tokens,
                    self.model_context_window,
                )
            else:
                self.config_max_tokens = 128000
                self.model_context_window = 128000
                logger.warning(
                    "无法获取配置,使用默认值: max_tokens=%d, context_window=%d",
                    self.config_max_tokens,
                    self.model_context_window,
                )
        except Exception as e:
            self.config_max_tokens = 128000
            self.model_context_window = 128000
            logger.warning(
                "获取配置失败: %s,使用默认值: max_tokens=%d, context_window=%d",
                e,
                self.config_max_tokens,
                self.model_context_window,
            )

        # 使用配置的max_tokens作为输出限制
        self.output_max_tokens = self.config_max_tokens

        logger.info(
            "Token限制配置: max_tokens=%d, context_window=%d tokens",
            self.config_max_tokens,
            self.model_context_window,
        )

        logger.info("LLM广告清洗器初始化完成")

    def _get_model(self, max_tokens_override: int | None = None) -> BaseLanguageModel:
        """获取模型实例

        Args:
            max_tokens_override: 可选的max_tokens覆盖值

        Returns:
            模型实例
        """
        if max_tokens_override is not None:
            logger.debug("使用动态max_tokens: %s", max_tokens_override)
            return self.llm_service.get_ad_cleaning_chat_model(
                max_tokens_override=max_tokens_override
            )
        return self.model

    def _invoke_model_with_retry(
        self, messages: list, max_tokens: int | None = None
    ) -> str:
        """使用流式响应调用模型,带重试机制

        使用 stream() 方法代替 invoke(),避免长时间等待导致的超时问题。
        流式响应会持续接收数据块,只要服务器在发送数据就不会超时。

        Args:
            messages: 消息列表
            max_tokens: 可选的max_tokens覆盖值

        Returns:
            模型返回的完整文本内容(由流式数据块拼接而成)
        """
        model = self._get_model(max_tokens)

        def _stream_model_call() -> str:
            """执行流式模型调用"""
            full_response = ""
            chunk_count = 0

            logger.debug("开始流式调用模型...")

            for chunk in model.stream(messages):
                # AIMessageChunk 对象有 content 属性
                if hasattr(chunk, "content") and chunk.content:
                    full_response += chunk.content
                    chunk_count += 1

                    # 每100个chunk记录一次进度
                    if chunk_count % 100 == 0:
                        logger.debug(
                            "已接收 %s 个数据块,当前响应长度: %s 字符",
                            chunk_count,
                            len(full_response),
                        )

            logger.debug(
                "流式响应完成,共接收 %s 个数据块,响应长度: %s 字符",
                chunk_count,
                len(full_response),
            )
            return full_response

        return self.retry_handler.execute_with_retry(
            _stream_model_call,
            operation_name="流式模型调用",
        )

    def _get_system_message(self) -> str:
        """获取系统提示词

        Returns:
            系统提示词字符串
        """
        return """你是一个专业的文档清洗助手,专门负责清理Markdown文档中的非正文内容。

**请删除以下内容**:
1. 广告内容(推广、营销、购买链接等)
2. 目录页和章节索引页(Table of Contents、图表目录、章节目录等)
   - **特别注意**:只有章节标题、没有正文内容的章节(如目录页、章节索引页)应该被删除
   - 保留正文中的章节标题和结构,但删除纯目录页
   - 如果某个章节只包含章节标题列表,没有正文内容,应该被识别为目录页并删除
3. 封面图片(通常位于文档开头、标题前的装饰性图片)
4. 文档结尾的装饰性图片(如作者照片、版权页图片、封底图片等)
   - **特别注意**:文档开头和结尾的装饰性图片都应该被删除
   - 包括但不限于:封面图、作者照片、版权页图片、封底图片等
5. 版权声明、页眉页脚信息
6. 出版信息(doi、中图分类号、文献标志码、文章编号等期刊元数据)
7. 作者简介、通讯作者信息
8. 收稿日期、修回日期等日期信息
9. 基金项目、资助信息
10. 无实质内容的装饰性图片(包括文档开头和结尾的装饰性图片)
11. 中英双语重复内容中的英文部分(如:中英文标题重复只保留中文标题,中英文摘要重复只保留中文摘要,图表标题的中英双语只保留中文标题)。注意:参考文献中的英文、正文引用的英文术语或文献应保留

**必须保留的内容**:
- 正文内容(包括摘要、关键词、正文章节、结论、参考文献)
- 正文中的图片(图表、数据图、示意图等有实际内容的图片)
- 公式和表格
- 章节标题和结构(但删除纯目录页)

**图片判断规则**:
- **删除**:文档开头和结尾的装饰性图片(封面、作者照片、版权页等)
- **删除**:无实质内容的装饰性图片
- **保留**:正文中的图表、数据图、示意图等有实际内容的图片
- **保留**:所有图片链接信息(`![](images/xxx.jpg)`格式),即使图片本身被删除,链接信息也要保留

**输出要求**:
- 直接输出清洗后的Markdown文档
- 不要添加任何说明、注释或解释
- 保持文档格式完整、逻辑连贯"""

    def _split_by_paragraphs(self, content: str, max_size_kb: int = 96) -> list[str]:
        """按段落将文档内容分段

        将Markdown文档按段落(空行分隔)分成多个段,每段不超过指定大小(KB)。
        尽量保持段落的完整性,不会在段落中间切断。

        Args:
            content: 待分段的Markdown文档内容
            max_size_kb: 每段最大大小(KB),默认96KB

        Returns:
            List[str]: 分段后的内容列表
        """
        max_size_bytes = max_size_kb * 1024

        # 如果内容小于限制,直接返回
        content_bytes = len(content.encode("utf-8"))
        if content_bytes <= max_size_bytes:
            logger.info(
                "文档大小 %s 字节,小于限制 %s 字节,无需分段",
                content_bytes,
                max_size_bytes,
            )
            return [content]

        # 按空行分割段落(保留空行)
        paragraphs = []
        current_paragraph = []

        lines = content.split("\n")
        for line in lines:
            # 如果当前行是空行,结束当前段落
            if line.strip() == "":
                if current_paragraph:
                    paragraphs.append("\n".join(current_paragraph))
                    current_paragraph = []
                paragraphs.append("")  # 保留空行
            else:
                current_paragraph.append(line)

        # 添加最后一个段落
        if current_paragraph:
            paragraphs.append("\n".join(current_paragraph))

        # 将段落组合成不超过限制的段
        segments = []
        current_segment = []
        current_size = 0

        for paragraph in paragraphs:
            paragraph_bytes = len(paragraph.encode("utf-8"))

            # 如果单个段落就超过限制,需要强制分割(这种情况很少见)
            if paragraph_bytes > max_size_bytes:
                # 如果当前段不为空,先保存当前段
                if current_segment:
                    segments.append("\n".join(current_segment))
                    current_segment = []
                    current_size = 0

                # 强制按行分割超大段落
                lines_in_paragraph = paragraph.split("\n")
                for line in lines_in_paragraph:
                    line_bytes = len(line.encode("utf-8"))
                    if current_size + line_bytes > max_size_bytes and current_segment:
                        segments.append("\n".join(current_segment))
                        current_segment = []
                        current_size = 0
                    current_segment.append(line)
                    current_size += line_bytes
                    if line != lines_in_paragraph[-1]:  # 不是最后一行,添加换行符
                        current_size += 1
            else:
                # 检查添加这个段落后是否超过限制
                if current_size + paragraph_bytes > max_size_bytes and current_segment:
                    # 保存当前段,开始新段
                    segments.append("\n".join(current_segment))
                    current_segment = [paragraph]
                    current_size = paragraph_bytes
                else:
                    # 添加到当前段
                    if current_segment:
                        current_segment.append(paragraph)
                        current_size += paragraph_bytes + 1  # +1 for newline
                    else:
                        current_segment = [paragraph]
                        current_size = paragraph_bytes

        # 添加最后一段
        if current_segment:
            segments.append("\n".join(current_segment))

        logger.info(
            "文档分段完成:原始大小 %s 字节,分成 %s 段,平均每段 %s 字节",
            content_bytes,
            len(segments),
            content_bytes // len(segments),
        )

        return segments

    def _clean_single_segment(
        self,
        segment: str,
        segment_index: int,
        total_segments: int,
        max_tokens: int | None = None,
    ) -> str:
        """清洗单个文档段

        直接调用模型进行清洗,不使用Agent框架,提高兼容性。

        Args:
            segment: 待清洗的文档段
            segment_index: 当前段的索引(从0开始)
            total_segments: 总段数
            max_tokens: 可选的max_tokens覆盖值

        Returns:
            清洗后的文档段
        """
        logger.info(
            "开始清洗第 %s/%s 段,大小: %s 字节",
            segment_index + 1,
            total_segments,
            len(segment.encode("utf-8")),
        )

        # 构建消息
        system_message = SystemMessage(content=self._get_system_message())

        if total_segments == 1:
            user_content = f"请清洗以下Markdown文档中的广告内容,直接返回清洗后的完整Markdown文档:\n\n{segment}"
        else:
            user_content = f"请清洗以下Markdown文档片段中的广告内容(这是文档的第 {segment_index + 1}/{total_segments} 段),直接返回清洗后的内容:\n\n{segment}"

        user_message = HumanMessage(content=user_content)
        messages = [system_message, user_message]

        # 直接调用模型(带重试机制)
        cleaned_segment = self._invoke_model_with_retry(messages, max_tokens)

        # 确保清洗后的内容是UTF-8字符串
        if isinstance(cleaned_segment, bytes):
            cleaned_segment = cleaned_segment.decode("utf-8", errors="replace")

        logger.info(
            "第 %s/%s 段清洗完成,原始大小: %s 字节,清洗后大小: %s 字节",
            segment_index + 1,
            total_segments,
            len(segment.encode("utf-8")),
            len(cleaned_segment.encode("utf-8")),
        )

        return cleaned_segment

    def _estimate_tokens(self, text: str) -> int:
        """改进的token估算方法

        基于字符类型进行更精确的估算:
        - 中文字符:每个约等于1.5个token
        - 英文单词:每个约等于1.2个token
        - 数字和符号:每个约等于0.8个token

        Args:
            text: 待估算的文本

        Returns:
            估算的token数量
        """
        import re

        if not text:
            return 0

        # 中文字符匹配(包括中文标点)
        chinese_chars = re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", text)
        chinese_tokens = len(chinese_chars) * 1.5

        # 英文单词匹配
        english_words = re.findall(r"[a-zA-Z]+", text)
        english_tokens = len(english_words) * 1.2

        # 数字匹配
        numbers = re.findall(r"\d+", text)
        number_tokens = len(numbers) * 0.8

        # 其他字符(空格、标点等)
        other_chars = (
            len(text)
            - len(chinese_chars)
            - sum(len(word) for word in english_words)
            - sum(len(num) for num in numbers)
        )
        other_tokens = other_chars * 0.5

        # 总估算token数
        estimated_tokens = (
            chinese_tokens + english_tokens + number_tokens + other_tokens
        )

        # 添加安全系数(增加20%余量)
        safe_tokens = int(estimated_tokens * 1.2)

        return safe_tokens

    def _split_paragraph_by_sentences(self, paragraph: str) -> list[str]:
        """将段落按句子分割

        使用中文和英文的句子结束符来分割句子,保持语义完整性。

        Args:
            paragraph: 待分割的段落

        Returns:
            List[str]: 句子列表
        """
        import re

        # 中文和英文的句子结束符
        # 包括:。!?;\n(用于Markdown中的换行)
        # 注意:保留结束符在句子中
        sentence_endings = r"([。!?;\n]+)"

        # 分割句子,但保留分隔符
        parts = re.split(sentence_endings, paragraph)

        sentences = []
        current_sentence = ""

        for part in parts:
            if re.match(sentence_endings, part):
                # 这是句子结束符
                if current_sentence:
                    current_sentence += part
                    sentences.append(current_sentence)
                    current_sentence = ""
                elif part.strip():
                    # 如果只有结束符(比如连续的空行),也保留
                    sentences.append(part)
            else:
                # 这是句子内容
                current_sentence += part

        # 添加最后一个句子(如果有)
        if current_sentence:
            sentences.append(current_sentence)

        return sentences if sentences else [paragraph]

    def _split_by_tokens(self, content: str, max_input_tokens: int) -> list[str]:
        """优化的分段策略

        使用改进的token计算,添加安全边界,优先保持段落和句子完整性

        将Markdown文档分成多个段,每段内容不超过指定的token数量。
        分段策略(按优先级):
        1. 优先按段落分段(保持段落完整性)
        2. 如果单个段落超过限制,按句子分割(保持句子完整性)
        3. 如果单个句子超过限制,才按行分割(最后手段)

        Args:
            content: 待分段的Markdown文档内容
            max_input_tokens: 每段最大输入token数量(不包括提示词开销)

        Returns:
            List[str]: 分段后的内容列表
        """
        # 估算整个文档的token数量
        total_tokens = self._estimate_tokens(content)
        logger.info("文档总token估算: %s tokens", total_tokens)

        # 添加非常保守的安全边界(预留50%空间),确保分段逻辑被触发
        safe_max_tokens = int(max_input_tokens * 0.5)

        # 如果文档token数小于限制,直接返回
        if total_tokens <= safe_max_tokens:
            logger.info("文档token数 %s <= %s,无需分段", total_tokens, safe_max_tokens)
            return [content]

        logger.info(
            "文档需要分段:总token %s,"
            "每段最大 %s tokens(含15%安全边界)",
            total_tokens,
            safe_max_tokens,
        )

        # 第一步:按空行分割段落(保持段落完整性)
        paragraphs = []
        current_paragraph = []

        lines = content.split("\n")
        for line in lines:
            if line.strip() == "":
                if current_paragraph:
                    paragraphs.append("\n".join(current_paragraph))
                    current_paragraph = []
                paragraphs.append("")  # 保留空行
            else:
                current_paragraph.append(line)

        if current_paragraph:
            paragraphs.append("\n".join(current_paragraph))

        logger.info("识别出 %s 个段落", len(paragraphs))

        # 第二步:将段落组合成不超过token限制的段
        segments = []
        current_segment = []
        current_tokens = 0

        for paragraph in paragraphs:
            paragraph_tokens = self._estimate_tokens(paragraph)

            # 如果单个段落就超过限制,需要进一步分割
            if paragraph_tokens > safe_max_tokens:
                # 如果当前段不为空,先保存当前段
                if current_segment:
                    segments.append("\n".join(current_segment))
                    current_segment = []
                    current_tokens = 0

                logger.warning(
                    "发现超大段落(%s tokens),"
                    "将按句子分割以保持语义完整性",
                    paragraph_tokens,
                )

                # 按句子分割超大段落
                sentences = self._split_paragraph_by_sentences(paragraph)
                logger.debug("段落分割为 %s 个句子", len(sentences))

                for sentence in sentences:
                    sentence_tokens = self._estimate_tokens(sentence)

                    # 如果单个句子也超过限制(很少见),按行分割
                    if sentence_tokens > safe_max_tokens:
                        logger.warning(
                            "发现超大句子(%s tokens),"
                            "将按行分割(最后手段)",
                            sentence_tokens,
                        )

                        # 如果当前段不为空,先保存
                        if current_segment:
                            segments.append("\n".join(current_segment))
                            current_segment = []
                            current_tokens = 0

                        # 按行分割超大句子
                        lines_in_sentence = sentence.split("\n")
                        for line in lines_in_sentence:
                            line_tokens = self._estimate_tokens(line)
                            if (
                                current_tokens + line_tokens > safe_max_tokens
                                and current_segment
                            ):
                                segments.append("\n".join(current_segment))
                                current_segment = []
                                current_tokens = 0
                            current_segment.append(line)
                            current_tokens += line_tokens
                            if line != lines_in_sentence[-1]:
                                current_tokens += 1  # 换行符
                    else:
                        # 检查添加这个句子后是否超过限制
                        if (
                            current_tokens + sentence_tokens > safe_max_tokens
                            and current_segment
                        ):
                            segments.append("\n".join(current_segment))
                            current_segment = [sentence]
                            current_tokens = sentence_tokens
                        else:
                            if current_segment:
                                current_segment.append(sentence)
                                current_tokens += sentence_tokens
                            else:
                                current_segment = [sentence]
                                current_tokens = sentence_tokens
            else:
                # 段落大小正常,检查添加这个段落后是否超过限制
                if (
                    current_tokens + paragraph_tokens > safe_max_tokens
                    and current_segment
                ):
                    segments.append("\n".join(current_segment))
                    current_segment = [paragraph]
                    current_tokens = paragraph_tokens
                else:
                    if current_segment:
                        current_segment.append(paragraph)
                        current_tokens += paragraph_tokens + 1  # +1 for newline
                    else:
                        current_segment = [paragraph]
                        current_tokens = paragraph_tokens

        # 添加最后一段
        if current_segment:
            segments.append("\n".join(current_segment))

        logger.info(
            "文档分段完成:原始 %s tokens,分成 %s 段,平均每段 %s tokens",
            total_tokens,
            len(segments),
            total_tokens // len(segments) if segments else 0,
        )

        return segments

    def _calculate_dynamic_max_tokens(self, estimated_input_tokens: int) -> int:
        """动态计算max_tokens

        根据估算的输入token数,动态计算可用的输出token数。
        确保 input_tokens + max_tokens <= context_window。

        Args:
            estimated_input_tokens: 估算的输入token数

        Returns:
            可用的max_tokens值
        """
        # 上下文窗口限制
        context_window = self.model_context_window  # 256000

        # 预留安全边界(防止估算误差)
        safety_margin = 20000  # 增加到20000,因为token估算可能不准确

        # 可用的输出token数
        available_output = context_window - estimated_input_tokens - safety_margin

        # 限制在合理范围内
        # 最小值:确保有足够空间输出
        min_output = 8000
        # 最大值:使用配置的输出限制(不同模型限制不同)
        max_output = self.output_max_tokens

        dynamic_max_tokens = max(min_output, min(available_output, max_output))

        logger.debug(
            "动态max_tokens计算:上下文=%s, "
            "估算输入=%s, 安全边界=%s, "
            "可用输出=%s, 配置限制=%s, "
            "最终max_tokens=%s",
            context_window,
            estimated_input_tokens,
            safety_margin,
            available_output,
            max_output,
            dynamic_max_tokens,
        )

        return dynamic_max_tokens

    def _split_by_sections(
        self, content: str, max_tokens_per_segment: int = 64000
    ) -> list[str]:
        """按章节和段落智能分段

        简单粗暴的分段策略:
        1. 优先按Markdown章节标题分段(#, ##, ###等)
        2. 如果单个章节太大,按段落分段
        3. 每段最大64k tokens

        Args:
            content: 待分段的Markdown文档内容
            max_tokens_per_segment: 每段最大token数,默认64000

        Returns:
            List[str]: 分段后的内容列表
        """
        import re

        # 按章节标题分割(匹配 # 开头的行)
        # 保留标题在分段中
        section_pattern = r"^(#{1,6}\s+.+)$"

        lines = content.split("\n")
        sections = []
        current_section = []

        for line in lines:
            # 如果是标题行,开始新的章节
            if re.match(section_pattern, line.strip()):
                # 保存之前的章节
                if current_section:
                    sections.append("\n".join(current_section))
                current_section = [line]
            else:
                current_section.append(line)

        # 添加最后一个章节
        if current_section:
            sections.append("\n".join(current_section))

        logger.info("文档按章节分割为 %s 个部分", len(sections))

        # 将章节组合成不超过token限制的段
        segments = []
        current_segment = []
        current_tokens = 0

        for section in sections:
            section_tokens = self._estimate_tokens(section)

            # 如果单个章节就超过限制,需要进一步分割
            if section_tokens > max_tokens_per_segment:
                # 先保存当前段
                if current_segment:
                    segments.append("\n\n".join(current_segment))
                    current_segment = []
                    current_tokens = 0

                logger.info("发现超大章节(%s tokens),按段落分割", section_tokens)

                # 按段落分割超大章节
                paragraphs = section.split("\n\n")
                sub_segment = []
                sub_tokens = 0

                for para in paragraphs:
                    para_tokens = self._estimate_tokens(para)

                    # 如果单个段落也超过限制,强制按行分割
                    if para_tokens > max_tokens_per_segment:
                        if sub_segment:
                            segments.append("\n\n".join(sub_segment))
                            sub_segment = []
                            sub_tokens = 0

                        # 按行分割
                        para_lines = para.split("\n")
                        line_segment = []
                        line_tokens = 0
                        for para_line in para_lines:
                            line_token = self._estimate_tokens(para_line)
                            if (
                                line_tokens + line_token > max_tokens_per_segment
                                and line_segment
                            ):
                                segments.append("\n".join(line_segment))
                                line_segment = []
                                line_tokens = 0
                            line_segment.append(para_line)
                            line_tokens += line_token
                        if line_segment:
                            segments.append("\n".join(line_segment))
                    elif (
                        sub_tokens + para_tokens > max_tokens_per_segment
                        and sub_segment
                    ):
                        # 当前子段落已满,保存并开始新的
                        segments.append("\n\n".join(sub_segment))
                        sub_segment = [para]
                        sub_tokens = para_tokens
                    else:
                        sub_segment.append(para)
                        sub_tokens += para_tokens

                if sub_segment:
                    segments.append("\n\n".join(sub_segment))

            elif (
                current_tokens + section_tokens > max_tokens_per_segment
                and current_segment
            ):
                # 当前段已满,保存并开始新的
                segments.append("\n\n".join(current_segment))
                current_segment = [section]
                current_tokens = section_tokens
            else:
                current_segment.append(section)
                current_tokens += section_tokens

        # 添加最后一段
        if current_segment:
            segments.append("\n\n".join(current_segment))

        logger.info(
            "分段完成:共 %s 段,平均每段 %s tokens",
            len(segments),
            (
                sum(self._estimate_tokens(s) for s in segments) // len(segments)
                if segments
                else 0
            ),
        )

        return segments

    def clean_document(self, document: Document) -> Document:
        """
        清洗单个LangChain Document对象

        如果文档token数量超过限制,会自动按段落分段处理,然后合并结果。
        KAT-Coder-Pro V1的最大上下文长度是256000 tokens,需要留出空间给输出。

        Args:
            document: 待清洗的Document对象

        Returns:
            清洗后的Document对象

        Raises:
            ProcessingError: 当清洗过程中出现错误时
        """
        start_time = time.time()

        try:
            source = document.metadata.get("source", "unknown")

            # 构建用户消息(确保使用UTF-8编码)
            # 确保文档内容是UTF-8字符串
            doc_content = document.page_content
            if isinstance(doc_content, bytes):
                doc_content = doc_content.decode("utf-8", errors="replace")

            # 如果启用了总结功能,先检查文档长度并总结(如果需要)
            if self.summarization_helper:
                doc_content = self.summarization_helper.summarize_if_needed(doc_content)
                logger.info("文档总结完成(如果需要)")

            # 验证:确保传递的是Markdown文本内容,而不是文件路径
            # 注意:这里抛出的已经是领域自定义异常,后续不应再次通过map_llm_error二次包装
            if (
                doc_content.startswith(("F:", "C:", "/", "\\"))
                and len(doc_content) < 500
            ):
                # 可能是误传了文件路径
                msg = "传递给LLM的内容格式错误,应该是Markdown文本而不是文件路径"
                raise LLMAdRemoverError(
                    msg,
                    error_code="INVALID_CONTENT_FORMAT",
                    file_path=source,
                    model_name=getattr(self.model, "model_name", "unknown"),
                )

            # 记录传递给LLM的内容类型和大小
            len(doc_content.encode("utf-8"))
            content_tokens = self._estimate_tokens(doc_content)

            # 记录开始日志
            self.preprocessing_logger.log_llm_cleaning_start(
                file_path=source,
                document_length=len(doc_content),
                estimated_tokens=content_tokens,
                segments_count=0,  # 将在分段后更新
                model_name=getattr(self.model, "model_name", "unknown"),
            )

            # ============================================================
            # 简单粗暴的分段策略:强制按64k tokens分段
            # ============================================================
            # 核心原则:宁可多分段,也不要因为token超限导致请求失败
            # 每段最大64k tokens(预留足够的输出和安全边界)
            MAX_TOKENS_PER_SEGMENT = 64000

            # 估算文档token数
            doc_tokens = self._estimate_tokens(doc_content)

            logger.info(
                "分段策略:强制按 %s tokens 分段,"
                "文档估算 %s tokens",
                MAX_TOKENS_PER_SEGMENT,
                doc_tokens,
            )

            # 使用按章节分段的方法(优先按章节、段落分段,避免语义截断)
            segments = self._split_by_sections(doc_content, MAX_TOKENS_PER_SEGMENT)

            logger.info("文档分成 %s 段进行处理", len(segments))

            # 更新分段数量到日志
            self.preprocessing_logger.log_llm_cleaning_start(
                file_path=source,
                document_length=len(doc_content),
                estimated_tokens=content_tokens,
                segments_count=len(segments),
                model_name=getattr(self.model, "model_name", "unknown"),
            )

            # 逐段处理并合并结果
            cleaned_segments = []
            prompt_overhead = 3000  # 提示词开销
            user_message_overhead = 50  # 用户消息开销

            for i, segment in enumerate(segments):
                segment_start_time = time.time()
                try:
                    # 估算当前段的输入token数
                    segment_tokens = self._estimate_tokens(segment)
                    segment_input_tokens = (
                        segment_tokens + prompt_overhead + user_message_overhead
                    )

                    # 动态计算max_tokens
                    dynamic_max_tokens = self._calculate_dynamic_max_tokens(
                        segment_input_tokens
                    )

                    # 记录段落开始日志
                    self.preprocessing_logger.log_llm_segment_start(
                        file_path=source,
                        segment_index=i,
                        total_segments=len(segments),
                        segment_length=len(segment),
                        estimated_tokens=segment_tokens,
                    )

                    # 直接调用模型清洗(不使用Agent)
                    cleaned_segment = self._clean_single_segment(
                        segment, i, len(segments), dynamic_max_tokens
                    )

                    # 计算处理时间和缩减比例
                    segment_processing_time = time.time() - segment_start_time
                    original_length = len(segment)
                    cleaned_length = len(cleaned_segment)
                    reduction_ratio = (
                        (original_length - cleaned_length) / original_length
                        if original_length > 0
                        else 0
                    )

                    # 记录段落成功日志
                    self.preprocessing_logger.log_llm_segment_success(
                        file_path=source,
                        segment_index=i,
                        total_segments=len(segments),
                        processing_time_seconds=segment_processing_time,
                        original_length=original_length,
                        cleaned_length=cleaned_length,
                        reduction_ratio=reduction_ratio,
                    )

                    cleaned_segments.append(cleaned_segment)

                except Exception as e:
                    # 映射错误并记录日志
                    mapped_error = preprocessing_error_handler.map_llm_error(
                        e,
                        source,
                        i,
                        len(segments),
                        getattr(self.model, "model_name", "unknown"),
                    )

                    error_str = str(e).lower()
                    if (
                        "token count exceeds" in error_str
                        or "maximum context length" in error_str
                    ):
                        # Token超限,尝试进一步分段(减半到32k)
                        logger.warning(
                            "段落 %s/%s 仍超限,进一步分段(32k)",
                            i + 1,
                            len(segments),
                        )
                        further_segments = self._split_by_sections(segment, 32000)
                        logger.info(
                            "段落 %s 进一步分成 %s 个子段落",
                            i + 1,
                            len(further_segments),
                        )

                        for j, sub_segment in enumerate(further_segments):
                            try:
                                sub_tokens = self._estimate_tokens(sub_segment)
                                sub_input_tokens = (
                                    sub_tokens + prompt_overhead + user_message_overhead
                                )
                                dynamic_max_tokens = self._calculate_dynamic_max_tokens(
                                    sub_input_tokens
                                )
                                cleaned_sub_segment = self._clean_single_segment(
                                    sub_segment,
                                    j,
                                    len(further_segments),
                                    dynamic_max_tokens,
                                )
                                cleaned_segments.append(cleaned_sub_segment)
                            except Exception as sub_e:
                                # 如果子段落也失败,记录错误但继续处理
                                sub_mapped_error = (
                                    preprocessing_error_handler.map_llm_error(
                                        sub_e,
                                        source,
                                        j,
                                        len(further_segments),
                                        getattr(self.model, "model_name", "unknown"),
                                    )
                                )
                                preprocessing_error_handler.log_llm_cleaning_error(
                                    sub_mapped_error, source, j, len(further_segments)
                                )
                                # 保留原始内容
                                cleaned_segments.append(sub_segment)
                    else:
                        # 其他错误,记录但继续处理
                        preprocessing_error_handler.log_llm_cleaning_error(
                            mapped_error, source, i, len(segments)
                        )
                        # 保留原始内容
                        cleaned_segments.append(segment)

            # 合并所有清洗后的段落
            cleaned_content = "\n\n".join(cleaned_segments)
            logger.info("分段处理完成,共处理 %s 个段落", len(segments))

            # 计算总体处理时间和缩减比例
            total_processing_time = time.time() - start_time
            original_length = len(doc_content)
            cleaned_length = len(cleaned_content)
            overall_reduction_ratio = (
                (original_length - cleaned_length) / original_length
                if original_length > 0
                else 0
            )

            # 记录完成日志
            self.preprocessing_logger.log_llm_cleaning_success(
                file_path=source,
                total_processing_time_seconds=total_processing_time,
                total_segments=len(segments),
                original_length=original_length,
                cleaned_length=cleaned_length,
                overall_reduction_ratio=overall_reduction_ratio,
                model_name=getattr(self.model, "model_name", "unknown"),
            )

            # 提取统计信息(仅在非分段情况下可用)
            total_removed_count = 0
            total_preserved_count = 0

            # 创建新的Document对象
            cleaned_document = Document(
                page_content=cleaned_content,
                metadata={
                    **document.metadata,
                    "llm_cleaned": True,
                    "cleaning_timestamp": time.time(),
                    "removed_items_count": total_removed_count,
                    "preserved_items_count": total_preserved_count,
                },
            )

            logger.info(
                "Document清洗完成,移除了 %s 项内容,保留了 %s 项内容",
                total_removed_count,
                total_preserved_count,
            )

            return cleaned_document

        except LLMAdRemoverError as e:
            # 已经是领域自定义异常:只记录一次结构化日志后直接抛出,避免二次包装
            source = document.metadata.get("source", "unknown")
            preprocessing_error_handler.log_llm_cleaning_error(e, source)
            raise
        except Exception as e:
            # 其他底层异常统一映射为领域异常并记录日志
            source = document.metadata.get("source", "unknown")
            mapped_error = preprocessing_error_handler.map_llm_error(
                e,
                source,
                model_name=getattr(self.model, "model_name", "unknown"),
            )
            preprocessing_error_handler.log_llm_cleaning_error(mapped_error, source)
            raise mapped_error from e

    def clean_documents(self, documents: list[Document]) -> list[Document]:
        """
        批量清洗LangChain Document对象

        Args:
            documents: 待清洗的Document对象列表

        Returns:
            清洗后的Document对象列表
        """
        logger.info("开始批量清洗 %s 个Document对象", len(documents))

        cleaned_documents = []
        for i, document in enumerate(documents):
            try:
                cleaned_doc = self.clean_document(document)
                cleaned_documents.append(cleaned_doc)
                logger.info("成功清洗第 %s/%s 个Document", i + 1, len(documents))
            except Exception as e:
                logger.error("第 %s 个Document清洗失败: %s", i + 1, e)
                # 根据配置决定是否跳过失败的文档
                # 这里选择保留原始文档,避免数据丢失
                cleaned_documents.append(document)

        logger.info("批量清洗完成,成功处理 %s 个Document对象", len(cleaned_documents))
        return cleaned_documents

    async def aclean_document(self, document: Document) -> Document:
        """
        异步清洗单个LangChain Document对象

        支持异步总结功能(如果启用)。

        Args:
            document: 待清洗的Document对象

        Returns:
            清洗后的Document对象

        Raises:
            ProcessingError: 当清洗过程中出现错误时
        """
        start_time = time.time()

        try:
            source = document.metadata.get("source", "unknown")

            # 构建用户消息(确保使用UTF-8编码)
            # 确保文档内容是UTF-8字符串
            doc_content = document.page_content
            if isinstance(doc_content, bytes):
                doc_content = doc_content.decode("utf-8", errors="replace")

            # 如果启用了总结功能,先异步检查文档长度并总结(如果需要)
            if self.summarization_helper:
                doc_content = await self.summarization_helper.asummarize_if_needed(
                    doc_content
                )
                logger.info("文档总结完成(如果需要)")

            # 验证:确保传递的是Markdown文本内容,而不是文件路径
            if (
                doc_content.startswith(("F:", "C:", "/", "\\"))
                and len(doc_content) < 500
            ):
                # 可能是误传了文件路径
                error_msg = (
                    f"检测到可能的文件路径而非文档内容: {doc_content[:100]}。"
                    "请确保传入的是Document对象的page_content,而不是文件路径。"
                )
                raise ProcessingError(error_msg)

            # 使用同步方法实现清洗,因为底层模型调用是同步的
            # 如果需要真正的异步,可以使用asyncio.to_thread
            import asyncio

            # 创建临时Document对象用于清洗
            temp_doc = Document(page_content=doc_content, metadata=document.metadata)
            cleaned_doc = await asyncio.to_thread(
                self._clean_document_content, temp_doc
            )

            # 更新元数据
            cleaned_doc.metadata.update(document.metadata)
            cleaned_doc.metadata["cleaned"] = True
            cleaned_doc.metadata["processed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # 记录处理时间
            duration = time.time() - start_time
            logger.info("异步清洗完成: %s, 耗时 %.2f 秒", source, duration)

            return cleaned_doc

        except ProcessingError:
            # 重新抛出ProcessingError,不进行二次包装
            raise
        except Exception as e:
            error = LLMAdRemoverError(
                f"异步清洗文档失败: {e}",
                error_code="CLEANING_ERROR",
                original_error=e,
                source=document.metadata.get("source", "unknown"),
            )
            preprocessing_error_handler.log_llm_cleaning_error(error, "async_cleaning")
            raise error from e

    def _clean_document_content(self, document: Document) -> Document:
        """清洗文档内容的内部方法(用于异步包装)

        注意:此方法假设文档内容已经过总结处理(如果需要),
        直接进行清洗,不再进行总结。

        Args:
            document: 待清洗的Document对象(内容应已总结)

        Returns:
            清洗后的Document对象
        """
        start_time = time.time()

        try:
            source = document.metadata.get("source", "unknown")
            doc_content = document.page_content

            # 直接进行清洗,不再进行总结(已在aclean_document中处理)
            # 使用分段清洗策略
            segments = self._split_by_paragraphs(doc_content)

            cleaned_segments = []
            for i, segment in enumerate(segments):
                cleaned_segment = self._clean_single_segment(segment, i, len(segments))
                cleaned_segments.append(cleaned_segment)

            # 合并清洗后的内容
            cleaned_content = "\n".join(cleaned_segments)

            # 创建清洗后的Document对象
            cleaned_doc = Document(
                page_content=cleaned_content, metadata=document.metadata.copy()
            )

            # 更新元数据
            cleaned_doc.metadata["cleaned"] = True
            cleaned_doc.metadata["processed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # 记录处理时间
            duration = time.time() - start_time
            logger.info("清洗完成: %s, 耗时 %.2f 秒", source, duration)

            return cleaned_doc

        except ProcessingError:
            # 重新抛出ProcessingError,不进行二次包装
            raise
        except Exception as e:
            error = LLMAdRemoverError(
                f"清洗文档失败: {e}",
                error_code="CLEANING_ERROR",
                original_error=e,
                source=document.metadata.get("source", "unknown"),
            )
            preprocessing_error_handler.log_llm_cleaning_error(error, "cleaning")
            raise error from e

    async def aclean_documents(self, documents: list[Document]) -> list[Document]:
        """
        异步批量清洗LangChain Document对象

        Args:
            documents: 待清洗的Document对象列表

        Returns:
            清洗后的Document对象列表
        """
        logger.info("开始异步批量清洗 %s 个Document对象", len(documents))

        cleaned_documents = []
        for i, document in enumerate(documents):
            try:
                cleaned_doc = await self.aclean_document(document)
                cleaned_documents.append(cleaned_doc)
                logger.info("成功异步清洗第 %s/%s 个Document", i + 1, len(documents))
            except Exception as e:
                logger.error("第 %s 个Document异步清洗失败: %s", i + 1, e)
                # 保留原始文档
                cleaned_documents.append(document)

        logger.info(
            "异步批量清洗完成,成功处理 %s 个Document对象", len(cleaned_documents)
        )
        return cleaned_documents


class LLMAdRemovalError(ProcessingError):
    """LLM广告清洗专用异常"""
