"""FastAPI 应用配置

创建和配置 FastAPI 应用实例,包括中间件,CORS,异常处理等.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.interfaces.api.middleware.response_formatter import (
    ResponseFormatterMiddleware,
)
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

    处理应用启动和关闭时的初始化和清理工作.
    """
    # 启动时执行
    logger.info("FastAPI 应用启动中...")

    # 确保必要的目录存在
    _ensure_directories()

    # 初始化数据库连接
    from src.infrastructure.storage.sqlite.connection import get_connection_manager
    connection_manager = get_connection_manager()  # 初始化连接管理器
    logger.info("数据库连接管理器已初始化")

    # 自动执行数据库迁移（检查并应用待应用的迁移）
    # 最佳实践：应用启动时自动检查并应用待应用的迁移，确保数据库结构是最新的
    try:
        from pathlib import Path
        from scripts.migration.migration_utils import MigrationManager
        
        # 获取数据库路径和迁移目录
        db_path = connection_manager.database_path
        # app.py 位于 src/interfaces/api/app.py，需要向上4级到达项目根目录
        project_root = Path(__file__).parent.parent.parent.parent
        migrations_dir = project_root / "scripts" / "migration" / "migrations"
        
        # 检查数据库文件是否存在（如果不存在，迁移管理器会处理）
        db_file = Path(db_path)
        if not db_file.exists():
            logger.info(f"数据库文件不存在: {db_path}，将在首次迁移时创建")
        
        # 检查迁移目录是否存在
        if not migrations_dir.exists():
            logger.warning(f"迁移目录不存在: {migrations_dir}，跳过自动迁移")
            logger.warning("建议检查项目结构或手动运行迁移命令: python scripts/migration/init_db.py migrate")
        else:
            # 创建迁移管理器
            migration_manager = MigrationManager(db_path)
            
            # 加载迁移文件
            migration_manager.load_migrations_from_directory(migrations_dir)
            logger.info(f"已加载 {len(migration_manager.migrations)} 个迁移文件")
            
            # 检查迁移状态
            status = migration_manager.get_migration_status()
            pending_count = status.get("pending_count", 0)
            
            if pending_count > 0:
                logger.info(f"发现 {pending_count} 个待应用的迁移，开始自动应用...")
                
                # 应用待应用的迁移
                applied_versions = migration_manager.apply_pending_migrations()
                
                if applied_versions:
                    logger.info(f"✅ 成功应用 {len(applied_versions)} 个迁移:")
                    for version in applied_versions:
                        migration = migration_manager.migrations[version]
                        logger.info(f"  - {version}: {migration.description}")
                else:
                    logger.warning("没有迁移被应用，可能是迁移过程中出现了错误")
            else:
                logger.info("数据库已是最新状态，无需迁移")
            
    except Exception as e:
        # 迁移失败不应该阻止应用启动，但应该记录错误
        # 这样即使迁移失败，应用仍然可以启动（可能在某些情况下仍然可用）
        logger.error(f"自动执行数据库迁移失败: {e}", exc_info=True)
        logger.warning("应用将继续启动，但建议手动运行迁移命令检查问题:")
        logger.warning("  python scripts/migration/init_db.py status  # 查看迁移状态")
        logger.warning("  python scripts/migration/init_db.py migrate  # 应用迁移")

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

    # 请求限流中间件(应该在CORS之后,其他中间件之前)
    from src.interfaces.api.middleware.rate_limiter import RateLimiterMiddleware

    app.add_middleware(
        RateLimiterMiddleware,
        requests_per_minute=60,  # 每分钟60次请求
        requests_per_hour=1000,  # 每小时1000次请求
    )

    # 响应格式转换中间件(前端适配层)
    # 注意:此中间件应该在 CORS 之后,日志中间件之前
    app.add_middleware(ResponseFormatterMiddleware)

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

    # 开发/测试环境的快速关闭入口（用于 Windows 下 Ctrl+C 不可靠时的兜底）
    # - 仅在非 production 环境启用
    # - 可选用环境变量 WHITEPAPER_SHUTDOWN_TOKEN 做简单保护
    @app.post("/__shutdown__", include_in_schema=False)
    async def shutdown(request: Request):
        """请求关闭服务器（开发/测试用）"""
        import os
        import signal
        import threading
        import time

        if current_config.environment == "production":
            raise HTTPException(status_code=404, detail="Not Found")

        expected = os.getenv("WHITEPAPER_SHUTDOWN_TOKEN")
        if expected:
            token = request.headers.get("x-shutdown-token") or request.query_params.get(
                "token"
            )
            if token != expected:
                raise HTTPException(status_code=403, detail="Forbidden")

        def _trigger_shutdown() -> None:
            # 给响应一点时间发回给客户端
            time.sleep(0.2)
            try:
                # 优先走 SIGINT，尽量触发 uvicorn 优雅退出
                os.kill(os.getpid(), signal.SIGINT)
            except Exception:
                # 兜底：强制退出
                os._exit(0)  # noqa: S404

        threading.Thread(target=_trigger_shutdown, daemon=True).start()
        return {"success": True, "message": "shutdown requested"}

    # 添加其他路由
    from .routes import (
        documents,
        draft_frontend,
        draft_mvp,
        frontend_adapter,
        frontend_integration,
        industry_selection,
        knowledge_base,
        outline_frontend,
        outline_mvp,
    )

    app.include_router(documents.router)
    # 添加知识库路由
    app.include_router(knowledge_base.router)
    # 添加行业选择路由
    app.include_router(industry_selection.router)
    # 添加前端集成路由
    app.include_router(frontend_integration.router)
    # 添加大纲管理路由
    app.include_router(outline_mvp.router)
    # 添加大纲前端集成路由
    app.include_router(outline_frontend.router)
    # 添加草稿管理路由
    app.include_router(draft_mvp.router)
    # 添加草稿前端集成路由
    app.include_router(draft_frontend.router)
    # 添加前端适配层路由(必须在最后注册,避免路由冲突)
    app.include_router(frontend_adapter.router)
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
