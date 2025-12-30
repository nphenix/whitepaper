"""
流式聊天响应实现

符合LangChain 1.0最佳实践的流式响应实现.
使用llm.astream()方法实现流式响应,支持Server-Sent Events (SSE)格式.

生成时间: 2025-01-XX
来源: T253.4任务
"""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi.responses import StreamingResponse
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.interfaces.api.schemas.frontend_adapter_schemas import ChatRequest
from src.shared.config.llm_service import LLMService
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


async def _chat_stream(
    request: ChatRequest,
    llm_service: LLMService,
    hybrid_retriever: Any | None,
) -> StreamingResponse:
    """流式聊天响应(符合LangChain 1.0最佳实践)

    使用LangChain的astream方法实现流式响应,支持Server-Sent Events (SSE)格式.

    Args:
        request: 聊天请求
        llm_service: LLM服务
        hybrid_retriever: 混合检索引擎(可能为None)

    Returns:
        StreamingResponse: 流式响应
    """

    async def generate_stream():
        """生成流式响应"""
        try:
            # 获取LLM模型
            try:
                llm = llm_service.get_chat_model()
            except Exception as e:
                logger.error("获取LLM模型失败: %s", e, exc_info=True)
                error_data = json.dumps({
                    "type": "error",
                    "error": "LLM服务不可用",
                    "message": "无法获取语言模型,请检查配置"
                })
                yield f"data: {error_data}\n\n"
                return

            # 使用ChatPromptTemplate管理提示词
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", """你是一个专业的文档分析助手,擅长回答关于文档内容的问题.

请根据提供的上下文信息回答问题.如果上下文中没有相关信息,请诚实地说不知道,不要编造答案.

回答要求:
1. 基于提供的上下文信息回答
2. 回答要准确,专业,简洁
3. 如果上下文不足,明确说明
4. 使用中文回答"""),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", """上下文信息:
{context}

问题:{input}

请基于上述上下文信息回答问题."""),
            ])

            # 加载对话历史(如果启用)
            chat_history = []
            if request.enableContext and request.outlineId:
                try:
                    from src.infrastructure.storage.chat_history import (
                        get_chat_history_manager,
                    )
                    history_manager = get_chat_history_manager()
                    chat_history = history_manager.load_history(
                        outline_id=request.outlineId,
                        max_messages=6,
                    )
                    logger.info(
                        "加载对话历史: outline_id=%s, messages_count=%d",
                        request.outlineId,
                        len(chat_history)
                    )
                except Exception as e:
                    logger.warning("加载对话历史失败: %s,将使用无上下文模式", e)
                    chat_history = []

            # 构建上下文和来源信息
            context = ""
            sources_list = []

            # 如果有HybridRetriever,使用RAG模式
            if hybrid_retriever:
                try:
                    top_k = request.topK or 5
                    logger.info("执行RAG检索: query=%s, top_k=%d", request.message[:50], top_k)

                    # 检索相关文档
                    retrieved_nodes = hybrid_retriever.retrieve(
                        query_str=request.message,
                        top_k=top_k,
                    )

                    # 构建上下文
                    context_parts = []
                    for i, node_with_score in enumerate(retrieved_nodes):
                        node = node_with_score.node
                        score = node_with_score.score
                        content = node.get_content() if hasattr(node, "get_content") else str(node.text)
                        metadata = node.metadata if hasattr(node, "metadata") else {}

                        context_parts.append(f"[文档{i+1}] {content}")

                        # 构建来源信息
                        source_info = {
                            "index": i + 1,
                            "score": float(score) if score else 0.0,
                            "content": content[:200] + "..." if len(content) > 200 else content,
                        }

                        if metadata:
                            if "filename" in metadata:
                                source_info["filename"] = metadata["filename"]
                            if "document_id" in metadata:
                                source_info["documentId"] = str(metadata["document_id"])
                            if "page" in metadata:
                                source_info["page"] = metadata["page"]

                        sources_list.append(source_info)

                    context = "\n\n".join(context_parts)

                    # 发送来源信息
                    if sources_list:
                        sources_data = json.dumps({
                            "type": "sources",
                            "sources": sources_list
                        })
                        yield f"data: {sources_data}\n\n"

                except Exception as e:
                    logger.error("RAG检索失败: %s", e, exc_info=True)
                    # 降级到无RAG模式
                    context = ""
                    warning_data = json.dumps({
                        "type": "warning",
                        "message": "RAG检索失败,使用无RAG模式"
                    })
                    yield f"data: {warning_data}\n\n"
            else:
                # 无RAG模式
                logger.warning("HybridRetriever不可用,使用无RAG模式")
                warning_data = json.dumps({
                    "type": "warning",
                    "message": "知识库不可用,当前使用无RAG模式"
                })
                yield f"data: {warning_data}\n\n"

            # 使用提示词模板格式化消息
            messages = prompt_template.format_messages(
                context=context,
                input=request.message,
                chat_history=chat_history,
            )

            # 流式调用LLM(符合LangChain 1.0最佳实践)
            logger.info("开始流式调用LLM")
            full_response = ""

            async for chunk in llm.astream(messages):
                # 提取chunk内容
                if hasattr(chunk, "content"):
                    content = chunk.content
                elif hasattr(chunk, "text"):
                    content = chunk.text
                else:
                    content = str(chunk)

                if content:
                    full_response += content
                    # 发送数据块(SSE格式)
                    chunk_data = json.dumps({
                        "type": "chunk",
                        "content": content
                    })
                    yield f"data: {chunk_data}\n\n"

            # 发送完成信号
            done_data = json.dumps({
                "type": "done",
                "timestamp": datetime.now(UTC).isoformat(),
            })
            yield f"data: {done_data}\n\n"

            # 保存对话历史(如果启用)
            if request.enableContext and request.outlineId:
                try:
                    from src.infrastructure.storage.chat_history import (
                        get_chat_history_manager,
                    )
                    history_manager = get_chat_history_manager()
                    # 保存用户消息
                    history_manager.save_message(
                        outline_id=request.outlineId,
                        role="user",
                        content=request.message,
                    )
                    # 保存助手回复
                    history_manager.save_message(
                        outline_id=request.outlineId,
                        role="assistant",
                        content=full_response,
                        metadata={"sources_count": len(sources_list), "stream": True},
                    )
                    logger.debug("保存对话历史: outline_id=%s", request.outlineId)
                except Exception as e:
                    logger.warning("保存对话历史失败: %s", e)

            logger.info("流式响应完成: response_length=%d", len(full_response))

        except Exception as e:
            logger.exception("流式响应异常: %s", e)
            error_data = json.dumps({
                "type": "error",
                "error": "流式响应失败",
                "message": str(e)
            })
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
        }
    )

