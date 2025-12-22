"""FastAPI 应用配置

创建和配置 FastAPI 应用实例,包括中间件、CORS、异常处理等。
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.shared.config.settings import get_config
from src.shared.utils.logging import get_logger

# 生成命令: /speckit.implement T019
# 生成时间: 2025-12-09
# 来源: specs/001-multi-agent-doc-system/tasks.md

# 获取配置和日志器
config = get_config()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理

    处理应用启动和关闭时的初始化和清理工作。
    """
    # 启动时执行
    logger.info("FastAPI 应用启动中...")

    # 确保必要的目录存在
    _ensure_directories()

    # 初始化数据库连接
    # TODO: 添加数据库初始化逻辑

    logger.info("FastAPI 应用启动完成")

    yield

    # 关闭时执行
    logger.info("FastAPI 应用关闭中...")

    # 清理资源
    # TODO: 添加资源清理逻辑

    logger.info("FastAPI 应用关闭完成")


def _ensure_directories() -> None:
    """确保必要的目录存在"""
    current_config = get_config()
    directories = [
        current_config.data_dir,
        current_config.storage_dir,
        current_config.log_dir,
        current_config.database.sqlite_db_path.parent,
        current_config.database.chroma_db_path,
        current_config.database.networkx_data_directory,
        current_config.document.upload_temp_dir,
    ]

    for directory in directories:
        if not isinstance(directory, Path):
            directory = Path(directory)

        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            logger.info("创建目录: %s", directory)


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例

    Returns:
        配置好的 FastAPI 应用实例
    """
    current_config = get_config()
    # 创建 FastAPI 应用
    app = FastAPI(
        title="WhitePaper API",
        description="多 Agent 协作的文档处理与生成系统 API",
        version="0.1.0",
        docs_url="/docs" if current_config.environment != "production" else None,
        redoc_url="/redoc" if current_config.environment != "production" else None,
        openapi_url=(
            "/openapi.json" if current_config.environment != "production" else None
        ),
        lifespan=lifespan,
    )

    # 添加中间件
    _add_middleware(app)

    # 添加异常处理器
    _add_exception_handlers(app)

    # 添加路由
    _add_routes(app)

    # 添加静态文件服务
    _add_static_files(app)

    return app


def _add_middleware(app: FastAPI) -> None:
    """添加中间件

    Args:
        app: FastAPI 应用实例
    """
    current_config = get_config()
    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=current_config.api.cors_origins,
        allow_credentials=current_config.api.cors_credentials,
        allow_methods=current_config.api.cors_methods,
        allow_headers=current_config.api.cors_headers,
    )

    # 受信任主机中间件
    if current_config.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"],  # 生产环境中应该配置具体的主机名
        )

    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录请求日志"""
        import time

        start_time = time.time()

        # 记录请求
        logger.info(
            "请求开始",
            extra={
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )

        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = time.time() - start_time

        # 记录响应
        logger.info(
            "请求完成",
            extra={
                "method": request.method,
                "url": str(request.url),
                "status_code": response.status_code,
                "process_time": process_time,
            },
        )

        # 添加处理时间到响应头
        response.headers["X-Process-Time"] = str(process_time)

        return response


def _add_exception_handlers(app: FastAPI) -> None:
    """添加异常处理器

    Args:
        app: FastAPI 应用实例
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """HTTP 异常处理"""
        logger.warning(
            "HTTP 异常",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "url": str(request.url),
            },
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """通用异常处理"""
        logger.error(
            "未处理的异常",
            extra={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "url": str(request.url),
            },
        )

        current_config = get_config()
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": (
                    "内部服务器错误"
                    if current_config.environment == "production"
                    else str(exc)
                ),
                "status_code": 500,
                "path": str(request.url.path),
            },
        )


def _add_routes(app: FastAPI) -> None:
    """添加路由

    Args:
        app: FastAPI 应用实例
    """

    current_config = get_config()

    # 根路径
    @app.get("/", tags=["根路径"])
    async def root():
        """根路径"""
        return {
            "message": "WhitePaper API",
            "version": "0.1.0",
            "environment": current_config.environment,
        }

    # 健康检查
    @app.get("/health", tags=["健康检查"])
    async def health_check():
        """健康检查"""
        return {
            "status": "healthy",
            "environment": current_config.environment,
            "version": "0.1.0",
        }

    # 添加其他路由
    from .routes import documents, knowledge_base

    app.include_router(documents.router)
    # 添加知识库路由
    app.include_router(knowledge_base.router)
    # TODO: 添加其他路由
    # from .routes import agents
    # app.include_router(agents.router, prefix='/api/v1/agents', tags=['Agent'])


def _add_static_files(app: FastAPI) -> None:
    """添加静态文件服务

    Args:
        app: FastAPI 应用实例
    """
    # 静态文件目录
    static_dir = Path("./static")
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    current_config = get_config()
    # 上传文件目录
    upload_dir = current_config.document.upload_temp_dir
    if upload_dir.exists():
        app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")


# 创建应用实例
app = create_app()
