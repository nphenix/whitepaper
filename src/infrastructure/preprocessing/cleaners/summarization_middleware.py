"""
总结中间件

用于处理超长文档,防止token溢出.当文档超过阈值时,自动触发总结流程.

本模块所有文本处理均使用UTF-8编码,确保正确处理中文和其他Unicode字符.

生成命令: /speckit.implement T040B
生成时间: 2025-12-18
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import asyncio
from collections.abc import Callable
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import HumanMessage, SystemMessage

from src.infrastructure.preprocessing.error_handler import (
    preprocessing_error_handler,
)
from src.infrastructure.preprocessing.logging_config import (
    PreprocessingAction,
    PreprocessingStep,
    create_llm_remover_logger,
)
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class SummarizationMiddleware(AgentMiddleware):
    """
    总结中间件

    用于处理超长文档,防止token溢出.当文档超过max_tokens阈值时,
    自动触发总结流程,将超长文档分段总结后传递给下游处理.

    使用示例:
        ```python
        from src.infrastructure.preprocessing.cleaners.summarization_middleware import SummarizationMiddleware

        middleware = SummarizationMiddleware(
            max_tokens=100000,
            chunk_size=50000,
            overlap_size=5000,
            llm_service=llm_service,
        )

        agent = create_agent(
            model='gpt-4o',
            tools=[...],
            middleware=[middleware],
        )
        ```
    """

    def __init__(
        self,
        max_tokens: int = 100000,
        chunk_size: int = 50000,
        overlap_size: int = 5000,
        summary_model: BaseLanguageModel | None = None,
        llm_service: LLMService | None = None,
        enabled: bool = True,
    ):
        """初始化总结中间件

        Args:
            max_tokens: 文档长度阈值(字符数),超过此值将触发总结
            chunk_size: 分段大小(字符数),用于分段总结
            overlap_size: 分段重叠大小(字符数),确保上下文连贯
            summary_model: 用于总结的专用模型(如果与主模型不同)
            llm_service: LLM服务实例(从T009获取),如果为None则使用全局实例
            enabled: 是否启用中间件,默认True
        """
        self.max_tokens = max_tokens
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.enabled = enabled

        # 获取LLM服务
        self.llm_service = llm_service or get_llm_service()

        # 获取总结模型(如果未提供,使用广告清洗模型作为默认)
        if summary_model:
            self.summary_model = summary_model
        else:
            try:
                self.summary_model = self.llm_service.get_ad_cleaning_chat_model()
                logger.info("使用广告清洗模型作为总结模型")
            except Exception as e:
                logger.warning(f"无法获取总结模型: {e},将在运行时获取")
                self.summary_model = None

        # 创建专用的日志记录器
        self.preprocessing_logger = create_llm_remover_logger()

        logger.info(
            "总结中间件初始化完成: max_tokens=%d, "
            "chunk_size=%d, overlap_size=%d, enabled=%s",
            max_tokens,
            chunk_size,
            overlap_size,
            enabled,
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """包装模型调用,实现超长文档总结

        Args:
            request: 模型请求
            handler: 模型调用处理器

        Returns:
            模型响应

        Raises:
            ProcessingError: 如果总结过程失败
        """
        if not self.enabled:
            return handler(request)

        # 检测文档长度
        content_length = self._calculate_content_length(request)

        # 如果文档长度 <= max_tokens,直接传递给下游处理
        if content_length <= self.max_tokens:
            logger.debug(
                "文档长度 %d <= %d,无需总结,直接传递",
                content_length,
                self.max_tokens,
            )
            return handler(request)

        # 文档长度 > max_tokens,执行总结流程
        logger.info(
            "文档长度 %d > %d,触发总结流程",
            content_length,
            self.max_tokens,
        )

        try:
            # 提取文档内容
            content = self._extract_content(request)

            # 分段总结
            summarized_content = self._summarize_content(content)

            # 更新请求中的内容
            updated_request = self._update_request_content(request, summarized_content)

            # 记录总结信息(并将信息存储到state中)
            self._log_summarization(
                content_length, len(summarized_content), updated_request
            )

            # 将总结后的内容传递给下游处理
            return handler(updated_request)

        except Exception as e:
            error_msg = f"总结过程失败: {e}"
            logger.error(error_msg, exc_info=True)

            # 记录错误
            preprocessing_error_handler.log_llm_cleaning_error(
                ProcessingError(error_msg, original_error=e),
                "summarization",
            )

            # 如果总结失败,尝试直接传递原始请求(降级策略)
            logger.warning("总结失败,尝试直接传递原始请求")
            return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        """异步包装模型调用,实现超长文档总结

        Args:
            request: 模型请求
            handler: 模型调用处理器

        Returns:
            模型响应

        Raises:
            ProcessingError: 如果总结过程失败
        """
        if not self.enabled:
            return handler(request)

        # 检测文档长度
        content_length = self._calculate_content_length(request)

        # 如果文档长度 <= max_tokens,直接传递给下游处理
        if content_length <= self.max_tokens:
            logger.debug(
                "文档长度 %d <= %d,无需总结,直接传递",
                content_length,
                self.max_tokens,
            )
            return handler(request)

        # 文档长度 > max_tokens,执行总结流程
        logger.info(
            "文档长度 %d > %d,触发总结流程",
            content_length,
            self.max_tokens,
        )

        try:
            # 提取文档内容
            content = self._extract_content(request)

            # 异步分段总结
            summarized_content = await self._asummarize_content(content)

            # 更新请求中的内容
            updated_request = self._update_request_content(request, summarized_content)

            # 记录总结信息(并将信息存储到state中)
            self._log_summarization(
                content_length, len(summarized_content), updated_request
            )

            # 将总结后的内容传递给下游处理
            return handler(updated_request)

        except Exception as e:
            error_msg = f"总结过程失败: {e}"
            logger.error(error_msg, exc_info=True)

            # 记录错误
            preprocessing_error_handler.log_llm_cleaning_error(
                ProcessingError(error_msg, original_error=e),
                "summarization",
            )

            # 如果总结失败,尝试直接传递原始请求(降级策略)
            logger.warning("总结失败,尝试直接传递原始请求")
            return handler(request)

    def _calculate_content_length(self, request: ModelRequest) -> int:
        """计算请求中的内容长度(字符数)

        Args:
            request: 模型请求

        Returns:
            内容长度(字符数)
        """
        try:
            # 从request中提取messages
            messages = request.messages if hasattr(request, "messages") else []

            # 计算所有消息的总字符数
            total_length = 0
            for message in messages:
                if hasattr(message, "content"):
                    content = message.content
                    if isinstance(content, str):
                        total_length += len(content)
                    elif isinstance(content, list):
                        # 处理多模态内容(文本+图片)
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                total_length += len(item["text"])
                            elif isinstance(item, str):
                                total_length += len(item)

            return total_length

        except Exception as e:
            logger.warning(f"计算内容长度失败: {e},使用默认值0")
            return 0

    def _extract_content(self, request: ModelRequest) -> str:
        """从请求中提取文档内容

        Args:
            request: 模型请求

        Returns:
            文档内容字符串
        """
        try:
            # 从request中提取messages
            messages = request.messages if hasattr(request, "messages") else []

            # 提取最后一个HumanMessage的内容
            content_parts = []
            for message in reversed(messages):
                if hasattr(message, "type") and message.type == "human":
                    if hasattr(message, "content"):
                        content = message.content
                        if isinstance(content, str):
                            content_parts.append(content)
                        elif isinstance(content, list):
                            # 处理多模态内容
                            for item in content:
                                if isinstance(item, dict) and "text" in item:
                                    content_parts.append(item["text"])
                                elif isinstance(item, str):
                                    content_parts.append(item)
                    break

            # 如果没有找到HumanMessage,尝试提取所有消息的内容
            if not content_parts:
                for message in messages:
                    if hasattr(message, "content"):
                        content = message.content
                        if isinstance(content, str):
                            content_parts.append(content)
                        elif isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and "text" in item:
                                    content_parts.append(item["text"])
                                elif isinstance(item, str):
                                    content_parts.append(item)

            return "\n".join(content_parts)

        except Exception as e:
            logger.error(f"提取文档内容失败: {e}", exc_info=True)
            msg = f"提取文档内容失败: {e}"
            raise ProcessingError(msg, original_error=e)

    def _update_request_content(
        self, request: ModelRequest, new_content: str
    ) -> ModelRequest:
        """更新请求中的内容

        Args:
            request: 原始请求
            new_content: 新的内容(总结后的内容)

        Returns:
            更新后的请求
        """
        try:
            # 创建新的请求对象(浅拷贝)
            # 注意:ModelRequest可能是不可变的,需要根据实际实现调整
            if hasattr(request, "messages"):
                # 更新最后一个HumanMessage的内容
                messages = list(request.messages)
                for i in range(len(messages) - 1, -1, -1):
                    if hasattr(messages[i], "type") and messages[i].type == "human":
                        # 创建新的消息对象
                        messages[i] = HumanMessage(content=new_content)
                        break

                # 创建新的请求对象
                # 注意:这里假设ModelRequest有messages属性且可以更新
                # 如果ModelRequest是不可变的,可能需要使用其他方式
                updated_request = ModelRequest(
                    messages=messages,
                    state=request.state if hasattr(request, "state") else {},
                )
                return updated_request
            else:
                # 如果无法更新,返回原始请求
                logger.warning("无法更新请求内容,返回原始请求")
                return request

        except Exception as e:
            logger.error(f"更新请求内容失败: {e}", exc_info=True)
            # 如果更新失败,返回原始请求
            return request

    def _summarize_content(self, content: str) -> str:
        """同步总结文档内容

        Args:
            content: 原始文档内容

        Returns:
            总结后的内容
        """
        # 分段
        chunks = self._split_content(content)

        # 对每个分段进行总结
        summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(
                "总结分段 %d/%d (长度: %d 字符)",
                i + 1,
                len(chunks),
                len(chunk),
            )
            summary = self._summarize_chunk(chunk, i + 1, len(chunks))
            summaries.append(summary)

        # 合并所有分段的总结结果
        summarized_content = "\n\n".join(summaries)

        logger.info(
            "总结完成: 原始长度=%d 字符, 总结后长度=%d 字符, 压缩比=%.1f%%",
            len(content),
            len(summarized_content),
            len(summarized_content) / len(content) * 100,
        )

        return summarized_content

    async def _asummarize_content(self, content: str) -> str:
        """异步总结文档内容

        Args:
            content: 原始文档内容

        Returns:
            总结后的内容
        """
        # 分段
        chunks = self._split_content(content)

        # 并发总结所有分段(限制并发数)
        semaphore = asyncio.Semaphore(3)  # 最多3个并发

        async def summarize_with_semaphore(chunk: str, index: int, total: int) -> str:
            async with semaphore:
                logger.info(
                    "总结分段 %d/%d (长度: %d 字符)",
                    index + 1,
                    total,
                    len(chunk),
                )
                return await self._asummarize_chunk(chunk, index + 1, total)

        # 创建所有任务
        tasks = [
            summarize_with_semaphore(chunk, i, len(chunks))
            for i, chunk in enumerate(chunks)
        ]

        # 等待所有任务完成
        summaries = await asyncio.gather(*tasks)

        # 合并所有分段的总结结果
        summarized_content = "\n\n".join(summaries)

        logger.info(
            "总结完成: 原始长度=%d 字符, 总结后长度=%d 字符, 压缩比=%.1f%%",
            len(content),
            len(summarized_content),
            len(summarized_content) / len(content) * 100,
        )

        return summarized_content

    def _split_content(self, content: str) -> list[str]:
        """将内容分段

        Args:
            content: 原始内容

        Returns:
            分段后的内容列表
        """
        chunks = []
        start = 0
        content_length = len(content)

        while start < content_length:
            # 计算当前段的结束位置
            end = min(start + self.chunk_size, content_length)

            # 如果不是最后一段,尝试在段落边界处分割
            if end < content_length:
                # 向后查找最近的段落边界(空行或换行符)
                # 优先查找空行(双换行符)
                paragraph_boundary = content.rfind("\n\n", start, end)
                if paragraph_boundary == -1:
                    # 如果没有找到空行,查找单换行符
                    paragraph_boundary = content.rfind("\n", start, end)

                if paragraph_boundary > start:
                    end = paragraph_boundary + 1

            # 提取当前段
            chunk = content[start:end]
            chunks.append(chunk)

            # 计算下一段的开始位置(考虑重叠)
            start = max(start + 1, end - self.overlap_size)

        logger.info(
            "内容分段完成: 总长度=%d 字符, 分段数=%d, 平均段长=%.0f 字符",
            content_length,
            len(chunks),
            content_length / len(chunks),
        )

        return chunks

    def _summarize_chunk(self, chunk: str, chunk_index: int, total_chunks: int) -> str:
        """同步总结单个分段

        Args:
            chunk: 分段内容
            chunk_index: 分段索引(从1开始)
            total_chunks: 总分段数

        Returns:
            总结后的内容
        """
        # 获取总结模型
        model = self._get_summary_model()

        # 构建提示词
        system_prompt = self._get_summarization_prompt()
        user_prompt = f"""请总结以下文档内容,保留关键信息,章节结构和图片链接.

**重要要求**:
1. 保留所有图片链接信息(`![](images/xxx.jpg)`格式)
2. 保留章节结构和标题层次
3. 保留关键数据和重要观点
4. 删除冗余描述和重复内容
5. 保持文档逻辑连贯性

**文档内容**(分段 {chunk_index}/{total_chunks}):
{chunk}"""

        try:
            # 调用模型进行总结
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = model.invoke(messages)

            # 提取响应内容
            if hasattr(response, "content"):
                summary = response.content
            elif isinstance(response, str):
                summary = response
            else:
                summary = str(response)

            return summary

        except Exception as e:
            error_msg = f"总结分段 {chunk_index}/{total_chunks} 失败: {e}"
            logger.error(error_msg, exc_info=True)
            # 如果总结失败,返回原始内容(降级策略)
            logger.warning("总结失败,返回原始分段内容")
            return chunk

    async def _asummarize_chunk(
        self, chunk: str, chunk_index: int, total_chunks: int
    ) -> str:
        """异步总结单个分段

        Args:
            chunk: 分段内容
            chunk_index: 分段索引(从1开始)
            total_chunks: 总分段数

        Returns:
            总结后的内容
        """
        # 获取总结模型
        model = self._get_summary_model()

        # 构建提示词
        system_prompt = self._get_summarization_prompt()
        user_prompt = f"""请总结以下文档内容,保留关键信息,章节结构和图片链接.

**重要要求**:
1. 保留所有图片链接信息(`![](images/xxx.jpg)`格式)
2. 保留章节结构和标题层次
3. 保留关键数据和重要观点
4. 删除冗余描述和重复内容
5. 保持文档逻辑连贯性

**文档内容**(分段 {chunk_index}/{total_chunks}):
{chunk}"""

        try:
            # 调用模型进行总结
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            response = await model.ainvoke(messages)

            # 提取响应内容
            if hasattr(response, "content"):
                summary = response.content
            elif isinstance(response, str):
                summary = response
            else:
                summary = str(response)

            return summary

        except Exception as e:
            error_msg = f"总结分段 {chunk_index}/{total_chunks} 失败: {e}"
            logger.error(error_msg, exc_info=True)
            # 如果总结失败,返回原始内容(降级策略)
            logger.warning("总结失败,返回原始分段内容")
            return chunk

    def _get_summary_model(self) -> BaseLanguageModel:
        """获取总结模型

        Returns:
            总结模型实例

        Raises:
            ProcessingError: 如果无法获取模型
        """
        if self.summary_model:
            return self.summary_model

        # 如果模型未初始化,尝试获取
        try:
            self.summary_model = self.llm_service.get_ad_cleaning_chat_model()
            logger.info("成功获取总结模型")
            return self.summary_model
        except Exception as e:
            error_msg = f"无法获取总结模型: {e}"
            logger.error(error_msg, exc_info=True)
            raise ProcessingError(error_msg, original_error=e)

    def _get_summarization_prompt(self) -> str:
        """获取总结提示词

        Returns:
            总结提示词字符串
        """
        return """你是一个专业的文档总结助手,专门负责总结超长文档,保留关键信息.

**总结要求**:
1. **保留所有图片链接**:必须保留所有图片链接信息(`![](images/xxx.jpg)`格式),即使图片本身被删除,链接信息也要保留
2. **保留章节结构**:保留文档的章节标题和层次结构
3. **保留关键信息**:保留重要的数据,观点,结论等关键信息
4. **删除冗余内容**:删除重复描述,冗余说明等不必要的内容
5. **保持逻辑连贯**:确保总结后的内容逻辑连贯,易于理解

**输出要求**:
- 直接输出总结后的Markdown文档
- 不要添加任何说明,注释或解释
- 保持文档格式完整,逻辑连贯
- 确保所有图片链接信息都被保留"""

    def _log_summarization(
        self,
        original_length: int,
        summarized_length: int,
        request: ModelRequest | None = None,
    ) -> dict[str, Any]:
        """记录总结信息并返回摘要元数据

        Args:
            original_length: 原始文档长度
            summarized_length: 总结后文档长度
            request: 模型请求(可选,用于将信息存储到state中)

        Returns:
            摘要元数据字典,包含是否摘要,摘要前后长度,触发原因等信息
        """
        compression_ratio = (
            (1 - summarized_length / original_length) * 100
            if original_length > 0
            else 0
        )

        # 构建摘要元数据
        summarization_metadata = {
            "summarization_applied": True,
            "original_length": original_length,
            "summarized_length": summarized_length,
            "compression_ratio": compression_ratio,
            "trigger_reason": f"文档长度 {original_length} 超过阈值 {self.max_tokens}",
            "max_tokens_threshold": self.max_tokens,
        }

        # 如果有request且request有state,将摘要信息存储到state中
        if request and hasattr(request, "state") and isinstance(request.state, dict):
            if "summarization_metadata" not in request.state:
                request.state["summarization_metadata"] = []
            request.state["summarization_metadata"].append(summarization_metadata)

        # 记录到预处理日志
        self.preprocessing_logger.info(
            f"文档总结完成: 原始长度={original_length} 字符, "
            f"总结后长度={summarized_length} 字符, "
            f"压缩比={compression_ratio:.1f}%",
            extra={
                "step": PreprocessingStep.SUMMARIZATION,
                "action": PreprocessingAction.SUMMARIZE,
                "original_length": original_length,
                "summarized_length": summarized_length,
                "compression_ratio": compression_ratio,
                "summarization_metadata": summarization_metadata,
            },
        )

        logger.info(
            "文档总结完成: 原始长度=%d 字符, 总结后长度=%d 字符, 压缩比=%.1f%%",
            original_length,
            summarized_length,
            compression_ratio,
        )

        return summarization_metadata


def create_summarization_middleware(
    max_tokens: int = 100000,
    chunk_size: int = 50000,
    overlap_size: int = 5000,
    summary_model: BaseLanguageModel | None = None,
    llm_service: LLMService | None = None,
    enabled: bool = True,
) -> SummarizationMiddleware:
    """创建总结中间件的便捷函数

    Args:
        max_tokens: 文档长度阈值(字符数)
        chunk_size: 分段大小(字符数)
        overlap_size: 分段重叠大小(字符数)
        summary_model: 用于总结的专用模型
        llm_service: LLM服务实例
        enabled: 是否启用中间件

    Returns:
        总结中间件实例
    """
    return SummarizationMiddleware(
        max_tokens=max_tokens,
        chunk_size=chunk_size,
        overlap_size=overlap_size,
        summary_model=summary_model,
        llm_service=llm_service,
        enabled=enabled,
    )


class SummarizationHelper:
    """
    总结辅助类

    用于在直接模型调用场景下(非Agent框架)使用总结功能.
    可以在LLMAdRemover等直接调用模型的组件中使用.
    """

    def __init__(
        self,
        max_tokens: int = 100000,
        chunk_size: int = 50000,
        overlap_size: int = 5000,
        summary_model: BaseLanguageModel | None = None,
        llm_service: LLMService | None = None,
        enabled: bool = True,
    ):
        """初始化总结辅助类

        Args:
            max_tokens: 文档长度阈值(字符数)
            chunk_size: 分段大小(字符数)
            overlap_size: 分段重叠大小(字符数)
            summary_model: 用于总结的专用模型
            llm_service: LLM服务实例
            enabled: 是否启用总结功能
        """
        self.max_tokens = max_tokens
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.enabled = enabled

        # 获取LLM服务
        self.llm_service = llm_service or get_llm_service()

        # 获取总结模型
        if summary_model:
            self.summary_model = summary_model
        else:
            try:
                self.summary_model = self.llm_service.get_ad_cleaning_chat_model()
                logger.info("使用广告清洗模型作为总结模型")
            except Exception as e:
                logger.warning(f"无法获取总结模型: {e},将在运行时获取")
                self.summary_model = None

        # 创建专用的日志记录器
        self.preprocessing_logger = create_llm_remover_logger()

        logger.info(
            "总结辅助类初始化完成: max_tokens=%d, "
            "chunk_size=%d, overlap_size=%d, enabled=%s",
            max_tokens,
            chunk_size,
            overlap_size,
            enabled,
        )

    def summarize_if_needed(self, content: str) -> str:
        """如果需要,对内容进行总结

        Args:
            content: 原始内容

        Returns:
            总结后的内容(如果需要)或原始内容(如果不需要)
        """
        if not self.enabled:
            return content

        content_length = len(content)

        # 如果文档长度 <= max_tokens,直接返回
        if content_length <= self.max_tokens:
            logger.debug(
                "文档长度 %d <= %d,无需总结",
                content_length,
                self.max_tokens,
            )
            return content

        # 文档长度 > max_tokens,执行总结流程
        logger.info(
            "文档长度 %d > %d,触发总结流程",
            content_length,
            self.max_tokens,
        )

        try:
            # 分段总结
            summarized_content = self._summarize_content(content)

            # 记录总结信息
            self._log_summarization(content_length, len(summarized_content))

            return summarized_content

        except Exception as e:
            error_msg = f"总结过程失败: {e}"
            logger.error(error_msg, exc_info=True)

            # 记录错误
            preprocessing_error_handler.log_llm_cleaning_error(
                ProcessingError(error_msg, original_error=e),
                "summarization",
            )

            # 如果总结失败,返回原始内容(降级策略)
            logger.warning("总结失败,返回原始内容")
            return content

    async def asummarize_if_needed(self, content: str) -> str:
        """异步总结内容(如果需要)

        Args:
            content: 原始内容

        Returns:
            总结后的内容(如果需要)或原始内容(如果不需要)
        """
        if not self.enabled:
            return content

        content_length = len(content)

        # 如果文档长度 <= max_tokens,直接返回
        if content_length <= self.max_tokens:
            logger.debug(
                "文档长度 %d <= %d,无需总结",
                content_length,
                self.max_tokens,
            )
            return content

        # 文档长度 > max_tokens,执行总结流程
        logger.info(
            "文档长度 %d > %d,触发总结流程",
            content_length,
            self.max_tokens,
        )

        try:
            # 异步分段总结
            summarized_content = await self._asummarize_content(content)

            # 记录总结信息
            self._log_summarization(content_length, len(summarized_content))

            return summarized_content

        except Exception as e:
            error_msg = f"总结过程失败: {e}"
            logger.error(error_msg, exc_info=True)

            # 记录错误
            preprocessing_error_handler.log_llm_cleaning_error(
                ProcessingError(error_msg, original_error=e),
                "summarization",
            )

            # 如果总结失败,返回原始内容(降级策略)
            logger.warning("总结失败,返回原始内容")
            return content

    def _summarize_content(self, content: str) -> str:
        """同步总结文档内容(复用SummarizationMiddleware的逻辑)"""
        # 创建临时中间件实例以复用逻辑
        middleware = SummarizationMiddleware(
            max_tokens=self.max_tokens,
            chunk_size=self.chunk_size,
            overlap_size=self.overlap_size,
            summary_model=self.summary_model,
            llm_service=self.llm_service,
            enabled=True,
        )
        return middleware._summarize_content(content)

    async def _asummarize_content(self, content: str) -> str:
        """异步总结文档内容(复用SummarizationMiddleware的逻辑)"""
        # 创建临时中间件实例以复用逻辑
        middleware = SummarizationMiddleware(
            max_tokens=self.max_tokens,
            chunk_size=self.chunk_size,
            overlap_size=self.overlap_size,
            summary_model=self.summary_model,
            llm_service=self.llm_service,
            enabled=True,
        )
        return await middleware._asummarize_content(content)

    def _log_summarization(self, original_length: int, summarized_length: int) -> None:
        """记录总结信息(复用SummarizationMiddleware的逻辑)"""
        middleware = SummarizationMiddleware(
            max_tokens=self.max_tokens,
            chunk_size=self.chunk_size,
            overlap_size=self.overlap_size,
            summary_model=self.summary_model,
            llm_service=self.llm_service,
            enabled=True,
        )
        middleware._log_summarization(original_length, summarized_length)
