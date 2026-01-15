"""
OpenAI SDK 到 LangChain 的适配器

将 OpenAI SDK 包装为 LangChain 兼容的 BaseLanguageModel,
解决 LangChain ChatOpenAI 在某些 API 端点（如火山引擎）上的 URL 构建问题.

使用场景:
- 当 LangChain ChatOpenAI 的 URL 构建逻辑与 API 提供商不兼容时
- 需要更精确控制 API 调用时
- OpenAI SDK 已验证可以正常工作，但 LangChain 失败时
"""

import time
from typing import Any, Iterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class OpenAISDKAdapter(BaseChatModel):
    """OpenAI SDK 的 LangChain 适配器

    将 OpenAI SDK 包装为 LangChain 兼容的 BaseLanguageModel,
    解决 LangChain ChatOpenAI 在某些 API 端点上的 URL 构建问题.

    优势:
    - 使用 OpenAI SDK，已验证可以正常工作
    - 精确控制 API 调用和 URL 构建
    - 完全兼容 LangChain BaseLanguageModel 接口
    """

    def __init__(
        self,
        model_name: str,
        temperature: float,
        api_key: str,
        base_url: str,
        max_tokens: int | None = None,
        timeout: float = 60.0,
        **kwargs,
    ):
        """初始化 OpenAI SDK 适配器

        Args:
            model_name: 模型名称
            temperature: 温度参数
            api_key: API 密钥
            base_url: API 基础 URL（完整路径，包括 /endpoints 等）
            max_tokens: 最大 token 数，如果为 None 则不设置，让模型自动决定
            timeout: 超时时间（秒）
            **kwargs: 其他参数
        """
        super().__init__()
        
        from openai import OpenAI
        
        # 使用 object.__setattr__ 绕过 Pydantic 的字段验证
        # 这些属性不应该是 Pydantic 字段，而是内部状态
        object.__setattr__(self, "_model_name", model_name)
        object.__setattr__(self, "_temperature", temperature)
        object.__setattr__(self, "_max_tokens", max_tokens)
        object.__setattr__(self, "_api_key", api_key)
        object.__setattr__(self, "_base_url", base_url)
        object.__setattr__(self, "_timeout", timeout)
        # 连接类异常的额外重试次数（OpenAI SDK 自带 retry 之外，再加一层客户端重建重试）
        object.__setattr__(self, "_connection_retries", int(kwargs.get("connection_retries", 2)))
        
        # 创建 OpenAI 客户端（已验证可以正常工作）
        object.__setattr__(
            self,
            "_client",
            OpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            ),
        )
        
        logger.info(
            "创建OpenAI SDK适配器: model=%s, base_url=%s, timeout=%.1f秒",
            model_name,
            base_url,
            timeout,
        )

    def _recreate_client(self) -> None:
        """在连接异常后重建 OpenAI 客户端，避免 httpx 连接池处于坏状态。"""
        from openai import OpenAI

        object.__setattr__(
            self,
            "_client",
            OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            ),
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """生成响应（同步）

        Args:
            messages: LangChain 消息列表
            stop: 停止词列表
            run_manager: 运行管理器
            **kwargs: 其他参数

        Returns:
            LangChain LLMResult
        """
        openai_messages: list[dict[str, Any]] = []
        try:
            # 转换 LangChain 消息格式为 OpenAI SDK 格式
            openai_messages = self._convert_messages(messages)
            
            # 验证转换后的消息不为空
            if not openai_messages:
                error_msg = f"消息转换后为空，原始消息数量: {len(messages)}"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.debug(
                "消息转换完成: 原始消息数=%d, 转换后消息数=%d",
                len(messages),
                len(openai_messages),
            )
            
            # 构建请求参数
            request_params = {
                "model": self._model_name,
                "messages": openai_messages,
                "temperature": self._temperature,
            }
            
            # 只有当 max_tokens 不为 None 时才添加到请求参数中
            # 如果不设置 max_tokens，模型会根据内容自动决定输出长度（最佳实践）
            if self._max_tokens is not None:
                request_params["max_tokens"] = self._max_tokens
            
            # 添加停止词（如果提供）
            if stop:
                request_params["stop"] = stop
            
            # GLM-4.6V 特殊处理：检查是否需要添加 thinking 参数
            # 如果模型名称包含 "glm-4" 或 "glm_4"，且 kwargs 中包含 enable_thinking
            if ("glm-4" in self._model_name.lower() or "glm_4" in self._model_name.lower()):
                # 如果 kwargs 中明确指定了 thinking 参数，使用它
                if "thinking" in kwargs:
                    request_params["thinking"] = kwargs["thinking"]
                # 否则，如果 enable_thinking 为 True，添加默认的 thinking 参数
                elif kwargs.get("enable_thinking", False):
                    request_params["thinking"] = {"type": "enabled"}
            
            # 合并其他参数（但排除已处理的 thinking 相关参数和 LangChain 内部参数）
            # LangChain 可能会传递一些内部参数，这些参数不应该传递给 API
            excluded_params = {
                "thinking", "enable_thinking",
                "run_name", "run_id", "tags", "metadata",  # LangChain 内部参数
                "callbacks", "callback_manager",  # LangChain 回调参数
            }
            other_kwargs = {k: v for k, v in kwargs.items() 
                           if k not in excluded_params}
            
            # 特殊处理：如果 max_tokens 为 None，从 request_params 中移除（让模型自动决定）
            # 这样可以覆盖模型创建时的 max_tokens 设置
            if "max_tokens" in other_kwargs and other_kwargs["max_tokens"] is None:
                # 移除 request_params 中的 max_tokens（如果之前设置了）
                request_params.pop("max_tokens", None)
                # 从 other_kwargs 中移除，不传递给 API
                other_kwargs.pop("max_tokens")
                logger.debug("max_tokens=None，已移除，让模型自动决定输出长度")
            elif "max_tokens" in other_kwargs:
                # 如果 other_kwargs 中有 max_tokens 且不为 None，覆盖默认值
                request_params["max_tokens"] = other_kwargs.pop("max_tokens")
                logger.debug("使用运行时指定的 max_tokens: %d", request_params["max_tokens"])
            
            # 记录被排除的参数（用于调试）
            excluded = {k: v for k, v in kwargs.items() if k in excluded_params}
            if excluded:
                logger.debug("排除的参数（不会传递给API）: %s", list(excluded.keys()))
            
            # 记录将要传递的其他参数（用于调试）
            if other_kwargs:
                logger.debug("额外的请求参数: %s", list(other_kwargs.keys()))
            
            request_params.update(other_kwargs)
            
            # 调用 OpenAI SDK
            logger.debug(
                "调用OpenAI SDK: model=%s, base_url=%s, messages=%d, params=%s",
                self._model_name,
                self._base_url,
                len(openai_messages),
                list(request_params.keys()),
            )
            
            # 记录多模态消息的详细信息（用于调试）
            for i, msg in enumerate(openai_messages):
                if isinstance(msg.get("content"), list):
                    logger.debug(
                        "多模态消息[%d]: role=%s, content_items=%d",
                        i,
                        msg.get("role"),
                        len(msg.get("content", [])),
                    )
                    for j, item in enumerate(msg.get("content", [])):
                        if isinstance(item, dict):
                            item_type = item.get("type", "unknown")
                            if item_type == "image_url":
                                image_url = item.get("image_url", {}).get("url", "")
                                # 只记录URL的前100个字符，避免日志过长
                                url_preview = image_url[:100] + "..." if len(image_url) > 100 else image_url
                                logger.debug(
                                    "  内容项[%d]: type=%s, url_length=%d, url_preview=%s",
                                    j,
                                    item_type,
                                    len(image_url),
                                    url_preview,
                                )
                            else:
                                text_preview = str(item.get("text", ""))[:100]
                                logger.debug(
                                    "  内容项[%d]: type=%s, text_preview=%s",
                                    j,
                                    item_type,
                                    text_preview,
                                )
            
            # 记录完整的请求参数结构（不记录敏感内容）
            logger.debug(
                "请求参数: model=%s, temperature=%s, max_tokens=%s, messages_count=%d",
                request_params.get("model"),
                request_params.get("temperature"),
                request_params.get("max_tokens"),
                len(request_params.get("messages", [])),
            )
            
            # 记录完整的请求参数（用于调试，但不记录敏感信息）
            logger.debug(
                "准备调用 OpenAI SDK: model=%s, base_url=%s, request_params_keys=%s",
                self._model_name,
                self._base_url,
                list(request_params.keys()),
            )
            
            # 记录消息的完整结构（用于调试）
            for i, msg in enumerate(openai_messages):
                logger.debug(
                    "消息[%d]: role=%s, content_type=%s",
                    i,
                    msg.get("role"),
                    type(msg.get("content")).__name__,
                )
                if isinstance(msg.get("content"), list):
                    for j, item in enumerate(msg.get("content", [])):
                        logger.debug(
                            "  内容项[%d]: %s",
                            j,
                            {k: (v[:50] + "..." if isinstance(v, str) and len(v) > 50 else v) 
                             for k, v in item.items() if k != "image_url" or not isinstance(v, dict) or "url" not in v or len(v.get("url", "")) < 100}
                        )
            
            import random
            import time
            import httpx
            import httpcore
            from openai import APIConnectionError

            last_error: Exception | None = None
            max_attempts = max(1, int(self._connection_retries) + 1)

            for attempt in range(1, max_attempts + 1):
                try:
                    response = self._client.chat.completions.create(**request_params)
                    last_error = None
                    break
                except Exception as api_error:
                    last_error = api_error

                    # 仅对连接类异常做“重建客户端+重试”
                    is_conn = isinstance(api_error, (APIConnectionError, httpx.RemoteProtocolError, httpcore.RemoteProtocolError))
                    if not is_conn or attempt >= max_attempts:
                        break

                    # 指数退避 + 抖动，避免雪崩
                    sleep_s = min(2.0, 0.25 * (2 ** (attempt - 1))) + random.random() * 0.25
                    logger.warning(
                        "OpenAI SDK 连接异常，重建客户端并重试: attempt=%d/%d, sleep=%.2fs, err=%s",
                        attempt,
                        max_attempts,
                        sleep_s,
                        api_error,
                    )
                    try:
                        self._recreate_client()
                    except Exception as recreate_err:
                        logger.warning("重建 OpenAI client 失败(继续重试原client): %s", recreate_err)
                    time.sleep(sleep_s)

            if last_error is not None:
                # 走下面的统一错误日志逻辑
                raise last_error

            try:
                # 这里 response 已经拿到
                pass
            except Exception as api_error:
                # 记录请求参数的详细信息（用于调试API错误）
                import json
                request_debug = {
                    "model": request_params.get("model"),
                    "temperature": request_params.get("temperature"),
                    "max_tokens": request_params.get("max_tokens"),
                    "messages_count": len(request_params.get("messages", [])),
                    "has_stop": "stop" in request_params,
                }
                # 记录消息结构（不记录实际内容，但记录前100个字符用于调试）
                messages_debug = []
                for msg in request_params.get("messages", []):
                    msg_debug = {"role": msg.get("role")}
                    content = msg.get("content")
                    if isinstance(content, str):
                        msg_debug["content_type"] = "string"
                        msg_debug["content_length"] = len(content)
                        msg_debug["content_preview"] = content[:100]  # 记录前100个字符用于调试
                    elif isinstance(content, list):
                        msg_debug["content_type"] = "list"
                        msg_debug["items"] = []
                        for item in content:
                            if isinstance(item, dict):
                                item_type = item.get("type", "unknown")
                                item_info = {"type": item_type}
                                if item_type == "image_url":
                                    url = item.get("image_url", {}).get("url", "")
                                    item_info["url_length"] = len(url)
                                    item_info["url_starts_with"] = url[:50] if url else ""
                                elif item_type == "text":
                                    text = item.get("text", "")
                                    item_info["text_length"] = len(text)
                                    item_info["text_preview"] = text[:100]  # 记录前100个字符用于调试
                                msg_debug["items"].append(item_info)
                        messages_debug.append(msg_debug)
                request_debug["messages"] = messages_debug
                
                logger.error(
                    "API调用失败，请求详情: %s",
                    json.dumps(request_debug, indent=2, ensure_ascii=False),
                )
                raise api_error  # 重新抛出原始异常
            
            # 转换响应为 LangChain 格式
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content or ""
                message = AIMessage(content=content)
                generation = ChatGeneration(message=message)
                return ChatResult(generations=[generation])
            else:
                error_msg = "OpenAI API 返回空响应"
                logger.error(error_msg)
                raise Exception(error_msg)
                
        except Exception as e:
            # 记录详细的错误信息，包括请求参数（但不记录敏感信息）
            error_details = {
                "model": self._model_name,
                "base_url": self._base_url,
                "messages_count": len(openai_messages),
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
            
            # 记录消息结构（不记录实际内容）
            message_structure = []
            for msg in openai_messages:
                msg_info = {"role": msg.get("role")}
                content = msg.get("content")
                if isinstance(content, str):
                    msg_info["content_type"] = "string"
                    msg_info["content_length"] = len(content)
                elif isinstance(content, list):
                    msg_info["content_type"] = "multimodal_list"
                    msg_info["content_items"] = []
                    for item in content:
                        if isinstance(item, dict):
                            item_type = item.get("type", "unknown")
                            item_info = {"type": item_type}
                            if item_type == "image_url":
                                url = item.get("image_url", {}).get("url", "")
                                item_info["url_length"] = len(url)
                                item_info["url_prefix"] = url[:30] if url else ""
                            elif item_type == "text":
                                text = item.get("text", "")
                                item_info["text_length"] = len(text)
                            msg_info["content_items"].append(item_info)
                message_structure.append(msg_info)
            
            error_details["message_structure"] = message_structure
            logger.error(
                "OpenAI SDK 调用失败: %s\n请求详情: %s",
                e,
                error_details,
                exc_info=True,
            )
            raise

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """流式生成响应

        Args:
            messages: LangChain 消息列表
            stop: 停止词列表
            run_manager: 运行管理器
            **kwargs: 其他参数

        Yields:
            LangChain GenerationChunk
        """
        try:
            # 转换 LangChain 消息格式为 OpenAI SDK 格式
            openai_messages = self._convert_messages(messages)
            
            # 构建请求参数
            request_params = {
                "model": self._model_name,
                "messages": openai_messages,
                "temperature": self._temperature,
                "stream": True,  # 启用流式输出
            }
            
            # 添加停止词（如果提供）
            if stop:
                request_params["stop"] = stop
            
            # 合并其他参数（但排除 LangChain 内部参数）
            excluded_params = {
                "run_name", "run_id", "tags", "metadata",  # LangChain 内部参数
                "callbacks", "callback_manager",  # LangChain 回调参数
            }
            other_kwargs = {k: v for k, v in kwargs.items() 
                           if k not in excluded_params}

            # max_tokens 覆盖逻辑：与 _generate 保持一致
            # - 默认使用构造时的 max_tokens（如果设置）
            # - 如果运行时传 max_tokens=None，则显式移除，让模型自动决定输出长度
            # - 如果运行时传 max_tokens=具体值，则覆盖默认值
            if self._max_tokens is not None:
                request_params["max_tokens"] = self._max_tokens

            if "max_tokens" in other_kwargs and other_kwargs["max_tokens"] is None:
                request_params.pop("max_tokens", None)
                other_kwargs.pop("max_tokens")
                logger.debug("stream: max_tokens=None，已移除，让模型自动决定输出长度")
            elif "max_tokens" in other_kwargs:
                request_params["max_tokens"] = other_kwargs.pop("max_tokens")
                logger.debug("stream: 使用运行时指定的 max_tokens: %d", request_params["max_tokens"])

            request_params.update(other_kwargs)

            final_max_tokens = request_params.get("max_tokens")
            if final_max_tokens is not None and final_max_tokens > 16384:
                logger.warning(
                    "流式调用使用 max_tokens=%d（>16384）。若遇到 400/慢响应，请考虑降低到 16384 以内",
                    final_max_tokens,
                )
            
            # 调用 OpenAI SDK 流式 API
            logger.debug(
                "调用OpenAI SDK流式API: model=%s, base_url=%s, messages=%d, max_tokens=%s",
                self._model_name,
                self._base_url,
                len(openai_messages),
                final_max_tokens,
            )
            
            t0 = time.monotonic()
            stream = self._client.chat.completions.create(**request_params)
            
            # 转换流式响应为 LangChain 格式
            # 重要：ChatGenerationChunk.message 必须是 BaseMessageChunk（例如 AIMessageChunk），
            # 不能是 AIMessage，否则会触发 Pydantic 校验错误。
            first_token_s: float | None = None
            chunks = 0
            chars = 0
            stream_id: str | None = None
            for chunk in stream:
                if stream_id is None and getattr(chunk, "id", None):
                    stream_id = str(getattr(chunk, "id"))

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        content = delta.content
                        if first_token_s is None:
                            first_token_s = time.monotonic() - t0
                            # 只有在首 token 很慢时才打到 warning，避免噪音
                            if first_token_s >= 10:
                                logger.warning(
                                    "LLM 首 token 慢: model=%s, stream_id=%s, ttfb=%.2fs, max_tokens=%s",
                                    self._model_name,
                                    stream_id,
                                    first_token_s,
                                    final_max_tokens,
                                )
                            else:
                                logger.debug(
                                    "LLM 首 token: model=%s, stream_id=%s, ttfb=%.2fs",
                                    self._model_name,
                                    stream_id,
                                    first_token_s,
                                )

                        message_chunk = AIMessageChunk(content=content)
                        generation_chunk = ChatGenerationChunk(message=message_chunk)
                        chunks += 1
                        chars += len(content)

                        # 通知运行管理器
                        if run_manager:
                            run_manager.on_llm_new_token(content)

                        yield generation_chunk

            total_s = time.monotonic() - t0
            # 仅对“显著慢”的流式调用输出高优先级日志，便于定位抖动
            if total_s >= 60:
                logger.warning(
                    "LLM 流式调用耗时过长: model=%s, stream_id=%s, total=%.2fs, ttfb=%s, chunks=%d, chars=%d, max_tokens=%s",
                    self._model_name,
                    stream_id,
                    total_s,
                    f"{first_token_s:.2f}s" if first_token_s is not None else "N/A",
                    chunks,
                    chars,
                    final_max_tokens,
                )
            else:
                logger.debug(
                    "LLM 流式调用完成: model=%s, stream_id=%s, total=%.2fs, ttfb=%s, chunks=%d, chars=%d",
                    self._model_name,
                    stream_id,
                    total_s,
                    f"{first_token_s:.2f}s" if first_token_s is not None else "N/A",
                    chunks,
                    chars,
                )

        except Exception as e:
            logger.error("OpenAI SDK 流式调用失败: %s", e, exc_info=True)
            raise

    def _convert_messages(self, messages: list[BaseMessage]) -> list[dict[str, str]]:
        """转换 LangChain 消息格式为 OpenAI SDK 格式

        Args:
            messages: LangChain 消息列表

        Returns:
            OpenAI SDK 消息列表
        """
        openai_messages = []
        
        for msg in messages:
            if not isinstance(msg, BaseMessage):
                continue
                
            # 转换消息类型
            role_map = {
                "system": "system",
                "human": "user",
                "ai": "assistant",
                "assistant": "assistant",
            }
            
            msg_type = msg.type
            role = role_map.get(msg_type)
            
            if not role:
                logger.warning("跳过不支持的消息类型: %s", msg_type)
                continue
            
            # 获取消息内容
            content = msg.content
            if isinstance(content, str):
                # 纯文本消息
                message_content = content
                openai_messages.append({
                    "role": role,
                    "content": message_content,
                })
            elif isinstance(content, list):
                # 多模态消息（包含文本和图像）
                # 需要转换为OpenAI SDK的多模态格式
                multimodal_content = []
                for item in content:
                    if isinstance(item, str):
                        # 文本内容
                        multimodal_content.append({
                            "type": "text",
                            "text": item,
                        })
                    elif isinstance(item, dict):
                        # 可能是图像URL或文本对象
                        if "type" in item:
                            # 已经是OpenAI格式（type: "text" 或 "image_url"）
                            # 对于 GLM-4.6V，确保 image_url 格式正确
                            if item.get("type") == "image_url":
                                image_url_obj = item.get("image_url", {})
                                # 如果 image_url 是字符串，需要转换为对象格式
                                if isinstance(image_url_obj, str):
                                    multimodal_content.append({
                                        "type": "image_url",
                                        "image_url": {"url": image_url_obj},
                                    })
                                else:
                                    # 已经是对象格式，直接使用
                                    multimodal_content.append(item)
                            else:
                                multimodal_content.append(item)
                        elif "image_url" in item or "url" in item:
                            # 图像URL格式
                            if "image_url" in item:
                                image_url_obj = item["image_url"]
                                # 如果 image_url 是字符串，需要转换为对象格式
                                if isinstance(image_url_obj, str):
                                    multimodal_content.append({
                                        "type": "image_url",
                                        "image_url": {"url": image_url_obj},
                                    })
                                else:
                                    multimodal_content.append({
                                        "type": "image_url",
                                        "image_url": image_url_obj,
                                    })
                            else:
                                multimodal_content.append({
                                    "type": "image_url",
                                    "image_url": {"url": item["url"]},
                                })
                        elif "text" in item:
                            # 文本对象
                            multimodal_content.append({
                                "type": "text",
                                "text": item["text"],
                            })
                        else:
                            # 未知格式，尝试转换为文本
                            logger.warning("未知的多模态内容格式: %s", item)
                            multimodal_content.append({
                                "type": "text",
                                "text": str(item),
                            })
                    else:
                        # 其他类型，转换为文本
                        multimodal_content.append({
                            "type": "text",
                            "text": str(item),
                        })
                
                # 如果只有一个文本项，可以简化为字符串
                if len(multimodal_content) == 1 and multimodal_content[0].get("type") == "text":
                    openai_messages.append({
                        "role": role,
                        "content": multimodal_content[0]["text"],
                    })
                else:
                    # 多模态内容
                    openai_messages.append({
                        "role": role,
                        "content": multimodal_content,
                    })
            else:
                # 其他类型，转换为文本
                message_content = str(content)
                openai_messages.append({
                    "role": role,
                    "content": message_content,
                })
        
        return openai_messages

    @property
    def _llm_type(self) -> str:
        """返回 LLM 类型标识"""
        return "openai_sdk_adapter"

