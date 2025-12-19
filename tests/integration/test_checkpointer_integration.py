"""T017 Checkpointer 集成测试

验证checkpointer与项目配置的集成
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from src.infrastructure.memory import create_checkpointer, get_checkpointer_manager
from src.shared.config.settings import AppConfig, get_config


class TestCheckpointerIntegration:
    """Checkpointer集成测试"""

    def test_config_integration(self):
        """测试与项目配置的集成"""
        config = get_config()

        # 验证Agent配置存在
        assert hasattr(config, "agent")
        assert hasattr(config.agent, "checkpoint_type")
        assert hasattr(config.agent, "checkpoint_db_path")
        assert hasattr(config.agent, "checkpoint_ttl")

        # 验证配置值
        assert config.agent.checkpoint_type in ["memory", "sqlite"]
        assert isinstance(config.agent.checkpoint_db_path, Path)
        assert config.agent.checkpoint_ttl > 0

    def test_manager_with_default_config(self):
        """测试使用默认配置的管理器"""
        manager = get_checkpointer_manager()

        # 验证管理器使用默认配置
        assert manager.config is not None
        assert manager.config.checkpoint_type == get_config().agent.checkpoint_type

        manager.cleanup()

    def test_create_checkpointer_function(self):
        """测试便捷函数"""
        # 测试内存存储
        memory_saver = create_checkpointer("memory")
        assert memory_saver is not None

        # 测试SQLite存储
        sqlite_saver = create_checkpointer("sqlite")
        assert sqlite_saver is not None

        # 测试默认存储
        default_saver = create_checkpointer("default")
        assert default_saver is not None

    def test_config_validation(self):
        """测试配置验证"""
        # 创建临时配置
        temp_dir = tempfile.mkdtemp()
        temp_db_path = Path(temp_dir) / "test_checkpoints.db"

        try:
            # 测试有效配置
            config = AppConfig()
            config.agent.checkpoint_type = "sqlite"
            config.agent.checkpoint_db_path = temp_db_path
            config.agent.checkpoint_ttl = 3600

            assert config.agent.checkpoint_type == "sqlite"
            assert config.agent.checkpoint_db_path == temp_db_path
            assert config.agent.checkpoint_ttl == 3600

        finally:
            # 清理
            if temp_dir and Path(temp_dir).exists():
                shutil.rmtree(temp_dir)

    def test_directory_creation(self):
        """测试数据库目录自动创建"""
        temp_dir = tempfile.mkdtemp()
        temp_db_path = Path(temp_dir) / "subdir" / "test_checkpoints.db"

        try:
            config = AppConfig()
            config.agent.checkpoint_type = "sqlite"
            config.agent.checkpoint_db_path = temp_db_path

            # 确保父目录不存在
            assert not temp_db_path.parent.exists()

            # 创建管理器应该自动创建目录
            from src.infrastructure.memory.checkpointer import CheckpointerManager

            manager = CheckpointerManager(config=config)

            # 验证目录已创建
            assert temp_db_path.parent.exists()

            manager.cleanup()

        finally:
            # 清理
            if temp_dir and Path(temp_dir).exists():
                shutil.rmtree(temp_dir)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
