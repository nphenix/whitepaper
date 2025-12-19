"""任务队列设置配置

提供任务队列相关的配置管理,包括:
- Redis 连接配置
- Worker 配置
- 任务执行配置
- 重试策略配置
"""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetrySettings(BaseModel):
    """重试配置"""

    max_retries: int = Field(default=3, ge=0, description="最大重试次数")
    retry_delay: int = Field(default=60, gt=0, description="重试延迟时间(秒)")
    retry_backoff: float = Field(default=2.0, ge=1.0, description="重试退避倍数")
    max_retry_delay: int = Field(default=3600, gt=0, description="最大重试延迟时间(秒)")
    jitter: bool = Field(default=True, description="是否添加随机抖动")

    model_config = ConfigDict(extra="ignore")


class QueueSettings(BaseModel):
    """队列配置"""

    name: str = Field(default="whitepaper_tasks", description="队列名称")
    max_jobs: int = Field(default=100, gt=0, description="最大任务数")
    job_timeout: int = Field(default=3600, gt=0, description="任务超时时间(秒)")
    keep_result: int = Field(default=3600, gt=0, description="结果保留时间(秒)")
    expires: int = Field(default=86400, gt=0, description="任务过期时间(秒)")

    # 并发配置
    max_concurrent_jobs: int = Field(default=10, gt=0, description="最大并发任务数")
    burst_timeout: int = Field(default=10, gt=0, description="突发任务超时时间(秒)")

    # 优先级配置
    enable_priorities: bool = Field(default=True, description="是否启用优先级")
    priority_levels: int = Field(default=5, ge=1, le=10, description="优先级级别数")

    model_config = ConfigDict(extra="ignore")


class HealthCheckSettings(BaseModel):
    """健康检查配置"""

    enabled: bool = Field(default=True, description="是否启用健康检查")
    interval: int = Field(default=30, gt=0, description="检查间隔(秒)")
    timeout: int = Field(default=5, gt=0, description="检查超时时间(秒)")
    failure_threshold: int = Field(default=3, gt=0, description="失败阈值")

    model_config = ConfigDict(extra="ignore")


class MonitoringSettings(BaseModel):
    """监控配置"""

    enabled: bool = Field(default=True, description="是否启用监控")
    metrics_interval: int = Field(default=60, gt=0, description="指标收集间隔(秒)")
    log_slow_jobs: bool = Field(default=True, description="是否记录慢任务")
    slow_job_threshold: int = Field(default=300, gt=0, description="慢任务阈值(秒)")

    # Prometheus 配置
    prometheus_enabled: bool = Field(default=False, description="是否启用 Prometheus")
    prometheus_port: int = Field(
        default=9090, ge=1, le=65535, description="Prometheus 端口"
    )

    model_config = ConfigDict(extra="ignore")


class LoggingSettings(BaseModel):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式",
    )
    file_path: Path | None = Field(default=None, description="日志文件路径")
    max_file_size: int = Field(
        default=10485760, gt=0, description="单个日志文件最大大小"
    )
    backup_count: int = Field(default=5, ge=0, description="保留的日志文件数量")
    rotation: str = Field(default="time", description="日志轮转策略")

    model_config = ConfigDict(extra="ignore")


class TaskSettings(BaseModel):
    """任务队列配置

    整合所有任务队列相关的配置项。
    """

    # Redis 配置
    redis_url: str | None = Field(default=None, description="Redis URL")
    redis_host: str = Field(default="localhost", description="Redis 主机")
    redis_port: int = Field(default=6379, gt=0, description="Redis 端口")
    redis_db: int = Field(default=1, ge=0, description="Redis 数据库")
    redis_password: str | None = Field(default=None, description="Redis 密码")
    redis_max_connections: int = Field(default=20, gt=0, description="最大连接数")
    redis_socket_timeout: int = Field(default=5, gt=0, description="Socket 超时时间")
    redis_socket_connect_timeout: int = Field(
        default=5, gt=0, description="连接超时时间"
    )
    redis_health_check_interval: int = Field(
        default=30, gt=0, description="健康检查间隔"
    )

    # 队列配置
    queue: QueueSettings = Field(default_factory=QueueSettings, description="队列配置")

    # 重试配置
    retry: RetrySettings = Field(default_factory=RetrySettings, description="重试配置")

    # 健康检查配置
    health_check: HealthCheckSettings = Field(
        default_factory=HealthCheckSettings, description="健康检查配置"
    )

    # 监控配置
    monitoring: MonitoringSettings = Field(
        default_factory=MonitoringSettings, description="监控配置"
    )

    # 日志配置
    logging: LoggingSettings = Field(
        default_factory=LoggingSettings, description="日志配置"
    )

    # Worker 配置
    worker_name: str = Field(default="whitepaper_worker", description="Worker 名称")
    worker_timeout: int = Field(default=300, gt=0, description="Worker 超时时间")
    worker_keepalive: int = Field(default=60, gt=0, description="Worker 保活时间")
    worker_graceful_shutdown_timeout: int = Field(
        default=30, gt=0, description="Worker 优雅关闭超时"
    )

    # 调试配置
    debug: bool = Field(default=False, description="是否启用调试模式")
    enable_profiling: bool = Field(default=False, description="是否启用性能分析")
    profile_output_dir: Path | None = Field(
        default=None, description="性能分析输出目录"
    )

    model_config = ConfigDict(extra="ignore")

    @field_validator("redis_url", mode="before")
    @classmethod
    def build_redis_url(cls, v: Any, info: Any) -> str:
        """构建 Redis URL"""
        if v:
            return v

        # 避免循环导入,直接从环境变量获取配置
        import os

        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = os.getenv("REDIS_PORT", "6379")
        redis_db = os.getenv("REDIS_DB", "1")
        redis_password = os.getenv("REDIS_PASSWORD")

        # 构建 Redis URL
        password_part = f":{redis_password}@" if redis_password else ""
        redis_url = f"redis://{password_part}{redis_host}:{redis_port}/{redis_db}"

        return redis_url  # type: ignore

    @field_validator("profile_output_dir", mode="before")
    @classmethod
    def set_default_profile_dir(cls, v: Any, info: Any) -> Path | None:
        """设置默认性能分析输出目录"""
        if v:
            return v

        # 避免循环导入,直接使用默认路径
        from pathlib import Path

        return Path("./data/profiles/tasks")  # type: ignore


def get_task_settings() -> TaskSettings:
    """获取任务队列配置实例

    Returns:
        TaskSettings 实例
    """
    # 避免循环导入,直接从环境变量获取配置
    import os

    # Redis 配置
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_db = int(os.getenv("REDIS_DB", "1")) + 1  # 使用不同的数据库
    redis_password = os.getenv("REDIS_PASSWORD")
    redis_max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
    redis_socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
    redis_socket_connect_timeout = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))

    # Arq 配置
    queue_name = os.getenv("ARQ_QUEUE_NAME", "whitepaper_tasks")
    max_jobs = int(os.getenv("ARQ_MAX_JOBS", "100"))
    job_timeout = int(os.getenv("ARQ_JOB_TIMEOUT", "3600"))

    # 调试配置
    debug = os.getenv("DEBUG", "false").lower() == "true"

    # 构建任务队列配置
    return TaskSettings(
        redis_host=redis_host,
        redis_port=redis_port,
        redis_db=redis_db,
        redis_password=redis_password,
        redis_max_connections=redis_max_connections,
        redis_socket_timeout=redis_socket_timeout,
        redis_socket_connect_timeout=redis_socket_connect_timeout,
        queue=QueueSettings(
            name=queue_name,
            max_jobs=max_jobs,
            job_timeout=job_timeout,
        ),
        debug=debug,
    )
