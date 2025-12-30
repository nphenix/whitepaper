"""
请求限流中间件

提供API请求限流功能,防止滥用.
使用简单的内存存储实现,适合单实例部署.

生成命令: 优化任务
生成时间: 2025-01-XX
来源: docs/architecture/frontend-adapter-optimization-assessment.md
"""

import time
from collections import defaultdict
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.utils.logging import get_logger

# 获取日志器
logger = get_logger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """请求限流中间件

    基于IP地址和路径的简单限流实现.
    使用滑动窗口算法.
    """

    def __init__(
        self,
        app: Any,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
    ):
        """
        初始化限流中间件

        Args:
            app: FastAPI应用实例
            requests_per_minute: 每分钟允许的请求数
            requests_per_hour: 每小时允许的请求数
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # 存储请求记录:{ip: {path: [timestamp, ...]}}
        self._request_history: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        # 清理间隔(秒)
        self._cleanup_interval = 3600  # 1小时
        self._last_cleanup = time.time()

    async def dispatch(self, request: Request, call_next):
        """处理请求并应用限流

        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理函数

        Returns:
            响应对象
        """
        # 获取客户端IP
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # 跳过某些路径的限流(如健康检查,文档等)
        if self._should_skip_rate_limit(path):
            return await call_next(request)

        # 检查限流
        if not self._check_rate_limit(client_ip, path):
            logger.warning(
                "请求被限流: IP=%s, 路径=%s",
                client_ip,
                path,
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "success": False,
                    "error": "请求过于频繁,请稍后再试",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "details": f"每分钟最多 {self.requests_per_minute} 次请求,每小时最多 {self.requests_per_hour} 次请求",
                },
            )

        # 记录请求
        self._record_request(client_ip, path)

        # 定期清理过期记录
        self._cleanup_if_needed()

        # 继续处理请求
        return await call_next(request)

    def _should_skip_rate_limit(self, path: str) -> bool:
        """判断是否应该跳过限流

        Args:
            path: 请求路径

        Returns:
            是否跳过限流
        """
        # 跳过健康检查和API文档
        skip_paths = ["/health", "/docs", "/redoc", "/openapi.json"]
        return any(path.startswith(skip_path) for skip_path in skip_paths)

    def _check_rate_limit(self, client_ip: str, path: str) -> bool:
        """检查是否超过限流

        Args:
            client_ip: 客户端IP
            path: 请求路径

        Returns:
            是否允许请求
        """
        now = time.time()
        history = self._request_history[client_ip][path]

        # 清理过期记录(只保留最近1小时的记录)
        cutoff_time = now - 3600
        history[:] = [ts for ts in history if ts > cutoff_time]

        # 检查每分钟限制
        minute_cutoff = now - 60
        minute_requests = sum(1 for ts in history if ts > minute_cutoff)
        if minute_requests >= self.requests_per_minute:
            return False

        # 检查每小时限制
        hour_requests = len(history)
        return not hour_requests >= self.requests_per_hour

    def _record_request(self, client_ip: str, path: str) -> None:
        """记录请求

        Args:
            client_ip: 客户端IP
            path: 请求路径
        """
        now = time.time()
        self._request_history[client_ip][path].append(now)

    def _cleanup_if_needed(self) -> None:
        """如果需要,清理过期记录"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        # 清理超过1小时的记录
        cutoff_time = now - 3600
        for ip_history in self._request_history.values():
            for path_history in ip_history.values():
                path_history[:] = [ts for ts in path_history if ts > cutoff_time]

        # 清理空的IP记录
        empty_ips = [
            ip
            for ip, ip_history in self._request_history.items()
            if not any(ip_history.values())
        ]
        for ip in empty_ips:
            del self._request_history[ip]

        self._last_cleanup = now
        logger.debug("限流记录清理完成")

