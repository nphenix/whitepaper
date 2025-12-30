"""
前端 API 响应格式统一中间件

自动将适配层接口(/api/*)的响应转换为统一格式:{ success: bool, data?: any, error?: string }
同时处理异常并转换为标准错误格式.

注意:
- 只处理 /api/* 路径(不包括 /api/v1/*)
- 如果响应已经是统一格式(已有 success 字段),则不再转换
- 保持现有 /api/v1/* 接口格式不变

生成命令: /speckit.implement T250
生成时间: 2025-01-XX
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.interfaces.api.schemas.frontend_adapter_schemas import (
    create_error_response,
    create_success_response,
)
from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)


class ResponseFormatterMiddleware(BaseHTTPMiddleware):
    """响应格式转换中间件

    自动将适配层接口的响应转换为统一格式.
    """

    async def dispatch(self, request: Request, call_next):
        """处理请求并转换响应格式

        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            转换后的响应
        """
        # 检查路径是否需要格式化
        path = request.url.path

        # 只处理 /api/* 路径,但不包括 /api/v1/* 和 /api/docs 等
        if not self._should_format_response(path):
            return await call_next(request)

        try:
            # 调用下一个中间件或路由处理函数
            response = await call_next(request)

            # 如果响应是 JSONResponse,尝试转换格式
            if isinstance(response, JSONResponse):
                # 检查响应大小,避免处理大文件
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
                    logger.warning("响应体过大,跳过格式化: %s bytes, 路径: %s", content_length, path)
                    return response

                # 获取响应内容(JSONResponse 的 body 属性包含序列化后的 JSON 字节)
                try:
                    # 读取响应体(限制大小,避免内存溢出)
                    response_body = b""
                    max_size = 10 * 1024 * 1024  # 10MB限制
                    async for chunk in response.body_iterator:
                        response_body += chunk
                        if len(response_body) > max_size:
                            logger.warning("响应体超过限制,跳过格式化: 路径: %s", path)
                            return response

                    # 解析 JSON 内容
                    try:
                        content = json.loads(response_body.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError) as e:
                        logger.warning("无法解析响应 JSON: %s, 路径: %s", e, path)
                        # 如果无法解析,返回原始响应
                        return Response(
                            content=response_body,
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            media_type=response.media_type,
                        )

                    # 检查是否已经是统一格式
                    if self._is_unified_format(content):
                        # 已经是统一格式,直接返回(需要重新创建响应,因为 body_iterator 已被消费)
                        return JSONResponse(
                            content=content,
                            status_code=response.status_code,
                            headers=dict(response.headers),
                        )

                    # 转换为统一格式
                    formatted_content = self._format_response(
                        content, response.status_code, path
                    )

                    return JSONResponse(
                        content=formatted_content,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                    )
                except Exception as e:
                    # 如果读取响应体失败,记录错误但返回原始响应
                    logger.warning("读取响应体失败: %s, 路径: %s", e, path)
                    # 由于 body_iterator 已被消费,无法返回原始响应
                    # 返回错误响应
                    error_response = create_error_response(
                        "响应处理失败",
                        "无法读取响应内容",
                    )
                    return JSONResponse(
                        content=error_response,
                        status_code=response.status_code,
                    )
            else:
                # 非 JSON 响应,直接返回
                return response

        except Exception as e:
            # 捕获异常并转换为统一错误格式
            logger.exception("中间件处理异常: %s, 路径: %s", e, path)
            # 根据日志级别决定是否显示详细错误信息
            import logging
            show_details = logger.isEnabledFor(logging.DEBUG)
            error_response = create_error_response(
                "服务器内部错误",
                str(e) if show_details else "请稍后重试或联系管理员",
            )
            return JSONResponse(
                content=error_response,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _should_format_response(self, path: str) -> bool:
        """判断路径是否需要格式化响应

        Args:
            path: 请求路径

        Returns:
            是否需要格式化
        """
        # 只处理 /api/* 路径
        if not path.startswith("/api/"):
            return False

        # 排除 /api/v1/* 路径(保持原有格式)
        if path.startswith("/api/v1/"):
            return False

        # 排除 API 文档路径
        if path.startswith(("/api/docs", "/api/openapi")):
            return False

        # 排除静态文件路径
        return not (path.startswith(("/api/static", "/api/uploads")))

    def _is_unified_format(self, content: dict[str, Any]) -> bool:
        """检查响应是否已经是统一格式

        Args:
            content: 响应内容

        Returns:
            是否已经是统一格式
        """
        if not isinstance(content, dict):
            return False

        # 检查是否有 success 字段(统一格式的标志)
        return "success" in content

    def _format_response(
        self, content: Any, status_code: int, path: str
    ) -> dict[str, Any]:
        """将响应转换为统一格式

        Args:
            content: 原始响应内容
            status_code: HTTP 状态码
            path: 请求路径

        Returns:
            统一格式的响应内容
        """
        # 如果是成功状态码(2xx),转换为成功响应
        if 200 <= status_code < 300:
            # 如果 content 是字典且包含 data 字段,直接使用
            if isinstance(content, dict) and "data" in content:
                return create_success_response(data=content["data"])
            # 否则将整个 content 作为 data
            return create_success_response(data=content)

        # 如果是错误状态码,转换为错误响应
        error_message = "请求失败"
        error_details = None

        if isinstance(content, dict):
            # 尝试从常见错误字段中提取错误信息
            error_message = (
                content.get("detail")
                or content.get("message")
                or content.get("error")
                or error_message
            )
            error_details = content.get("details") or content.get("description")
        elif isinstance(content, str):
            error_message = content

        return create_error_response(error_message, error_details)

