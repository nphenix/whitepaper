"""测试任务队列配置"""

from unittest.mock import MagicMock, patch

from src.infrastructure.tasks.settings import TaskSettings, get_task_settings


class TestTaskSettings:
    """测试任务队列设置"""

    def test_task_settings_creation(self):
        """测试任务设置创建"""
        settings = TaskSettings(
            redis_url="redis://localhost:6379/1",
            redis_host="localhost",
            redis_port=6379,
            redis_db=1,
        )

        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.redis_db == 1
        assert settings.queue.name == "whitepaper_tasks"
        assert settings.queue.max_jobs == 100
        assert settings.retry.max_retries == 3

    @patch("src.infrastructure.tasks.settings.get_config")
    def test_get_task_settings(self, mock_get_config):
        """测试获取任务设置"""
        # 模拟主配置
        mock_config = MagicMock()
        mock_config.redis.redis_host = "localhost"
        mock_config.redis.redis_port = 6379
        mock_config.redis.redis_db = 0
        mock_config.redis.redis_password = None
        mock_config.redis.redis_max_connections = 20
        mock_config.redis.redis_socket_timeout = 5
        mock_config.redis.redis_socket_connect_timeout = 5
        mock_config.arq.queue_name = "test_queue"
        mock_config.arq.max_jobs = 50
        mock_config.arq.job_timeout = 1800
        mock_config.debug = False

        mock_get_config.return_value = mock_config

        # 获取任务设置
        settings = get_task_settings()

        assert settings.redis_host == "localhost"
        assert settings.redis_port == 6379
        assert settings.redis_db == 1  # +1 from main config
        assert settings.queue.name == "test_queue"
        assert settings.queue.max_jobs == 50
        assert settings.queue.job_timeout == 1800
        assert settings.debug is False

    def test_redis_url_building(self):
        """测试 Redis URL 构建"""
        # 测试无密码的 URL
        settings = TaskSettings(
            redis_url="redis://localhost:6379/1",
            redis_host="localhost",
            redis_port=6379,
            redis_db=1,
        )

        assert settings.redis_url == "redis://localhost:6379/1"

        # 测试有密码的 URL
        settings_with_password = TaskSettings(
            redis_url="redis://:secret123@localhost:6379/1",
            redis_host="localhost",
            redis_port=6379,
            redis_db=1,
            redis_password="secret123",
        )

        assert settings_with_password.redis_url == "redis://:secret123@localhost:6379/1"

    def test_queue_settings(self):
        """测试队列设置"""
        queue_settings = TaskSettings().queue

        assert queue_settings.name == "whitepaper_tasks"
        assert queue_settings.max_jobs == 100
        assert queue_settings.job_timeout == 3600
        assert queue_settings.keep_result == 3600
        assert queue_settings.expires == 86400
        assert queue_settings.max_concurrent_jobs == 10
        assert queue_settings.enable_priorities is True
        assert queue_settings.priority_levels == 5

    def test_retry_settings(self):
        """测试重试设置"""
        retry_settings = TaskSettings().retry

        assert retry_settings.max_retries == 3
        assert retry_settings.retry_delay == 60
        assert retry_settings.retry_backoff == 2.0
        assert retry_settings.max_retry_delay == 3600
        assert retry_settings.jitter is True

    def test_health_check_settings(self):
        """测试健康检查设置"""
        health_settings = TaskSettings().health_check

        assert health_settings.enabled is True
        assert health_settings.interval == 30
        assert health_settings.timeout == 5
        assert health_settings.failure_threshold == 3

    def test_monitoring_settings(self):
        """测试监控设置"""
        monitoring_settings = TaskSettings().monitoring

        assert monitoring_settings.enabled is True
        assert monitoring_settings.metrics_interval == 60
        assert monitoring_settings.log_slow_jobs is True
        assert monitoring_settings.slow_job_threshold == 300
        assert monitoring_settings.prometheus_enabled is False
        assert monitoring_settings.prometheus_port == 9090
