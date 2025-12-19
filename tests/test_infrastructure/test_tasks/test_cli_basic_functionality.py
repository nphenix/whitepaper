"""
T021任务基本功能测试

测试Typer CLI基础结构的基本功能。

生成命令: /speckit.implement T021
生成时间: 2025-12-10
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from cli.base import BaseCLI
from cli.main import app


class TestCLIBasicFunctionality:
    """CLI基本功能测试"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    def test_cli_version_callback(self, runner):
        """测试版本信息显示"""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "WhitePaper version: 0.1.0" in result.stdout

    def test_cli_help(self, runner):
        """测试帮助信息显示"""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "多Agent协作的文档处理与生成系统" in result.stdout

    def test_cli_info_command(self, runner):
        """测试info命令"""
        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        assert "系统信息" in result.stdout
        assert "版本" in result.stdout
        assert "LangChain 1.0" in result.stdout

    @patch("cli.base.BaseCLI.check_config_status")
    @patch("cli.base.BaseCLI.check_database_status")
    @patch("cli.base.BaseCLI.check_vector_store_status")
    @patch("cli.base.BaseCLI.check_graph_store_status")
    @patch("cli.base.BaseCLI.check_task_queue_status")
    def test_cli_status_command(
        self, mock_queue, mock_graph, mock_vector, mock_db, mock_config, runner
    ):
        """测试status命令"""
        # 模拟所有组件状态正常
        mock_config.return_value = "正常"
        mock_db.return_value = "正常"
        mock_vector.return_value = "正常"
        mock_graph.return_value = "正常"
        mock_queue.return_value = "正常"

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "WhitePaper 系统状态" in result.stdout
        assert "✅" in result.stdout

    @patch("cli.base.BaseCLI.init_config")
    @patch("cli.base.BaseCLI.init_database")
    @patch("cli.base.BaseCLI.init_storage")
    @patch("cli.base.BaseCLI.init_sample_data")
    def test_cli_init_command(
        self, mock_sample, mock_storage, mock_db, mock_config, runner
    ):
        """测试init命令"""
        # 模拟所有初始化成功
        mock_config.return_value = True
        mock_db.return_value = True
        mock_storage.return_value = True
        mock_sample.return_value = True

        result = runner.invoke(app, ["init", "--sample-data"])
        assert result.exit_code == 0
        assert "WhitePaper系统初始化完成" in result.stdout

    def test_cli_documents_subcommand(self, runner):
        """测试documents子命令"""
        result = runner.invoke(app, ["documents", "--help"])
        assert result.exit_code == 0
        assert "文档管理和预处理" in result.stdout
        assert "upload" in result.stdout
        assert "list" in result.stdout
        assert "preprocess" in result.stdout
        assert "clean" in result.stdout

    def test_cli_knowledge_base_subcommand(self, runner):
        """测试knowledge-base子命令"""
        result = runner.invoke(app, ["knowledge-base", "--help"])
        assert result.exit_code == 0
        assert "知识库管理和检索" in result.stdout
        assert "status" in result.stdout
        assert "build" in result.stdout
        assert "search" in result.stdout

    def test_cli_agents_subcommand(self, runner):
        """测试agents子命令"""
        result = runner.invoke(app, ["agents", "--help"])
        assert result.exit_code == 0
        assert "Agent管理和编排" in result.stdout

    def test_cli_homepage_subcommand(self, runner):
        """测试homepage子命令"""
        result = runner.invoke(app, ["homepage", "--help"])
        assert result.exit_code == 0
        assert "首页和智能检索" in result.stdout

    def test_cli_memory_subcommand(self, runner):
        """测试memory子命令"""
        result = runner.invoke(app, ["memory", "--help"])
        assert result.exit_code == 0
        assert "记忆系统管理" in result.stdout

    def test_cli_prompts_subcommand(self, runner):
        """测试prompts子命令"""
        result = runner.invoke(app, ["prompts", "--help"])
        assert result.exit_code == 0
        assert "提示词工程" in result.stdout

    def test_cli_templates_subcommand(self, runner):
        """测试templates子命令"""
        result = runner.invoke(app, ["templates", "--help"])
        assert result.exit_code == 0
        assert "文档模板管理" in result.stdout

    def test_cli_constraints_subcommand(self, runner):
        """测试constraints子命令"""
        result = runner.invoke(app, ["constraints", "--help"])
        assert result.exit_code == 0
        assert "规范条件设置" in result.stdout

    def test_cli_source_matching_subcommand(self, runner):
        """测试source-matching子命令"""
        result = runner.invoke(app, ["source-matching", "--help"])
        assert result.exit_code == 0
        assert "信息源排名与匹配" in result.stdout


class TestBaseCLI:
    """BaseCLI类测试"""

    def test_base_cli_initialization(self):
        """测试BaseCLI初始化"""
        with patch("cli.base.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.llm_provider = "openai"
            mock_config.embedding.provider = "dashscope"
            mock_config.database.sqlite_db_path = "./test.db"
            mock_get_config.return_value = mock_config

            base_cli = BaseCLI()
            assert base_cli.settings is not None
            assert base_cli.settings == mock_config

    def test_base_cli_config_status_check(self):
        """测试配置状态检查"""
        with patch("cli.base.get_config") as mock_get_config:
            # 测试正常配置
            mock_config = MagicMock()
            mock_config.llm_provider = "openai"
            mock_config.embedding.provider = "dashscope"
            mock_config.database.sqlite_db_path = "./test.db"
            mock_get_config.return_value = mock_config

            base_cli = BaseCLI()
            status = base_cli.check_config_status()
            assert status == "正常"

            # 测试缺少配置
            mock_config.llm_provider = None
            status = base_cli.check_config_status()
            assert status == "缺少llm_provider"

    @patch("cli.base.SQLiteConnectionManager")
    def test_base_cli_database_status_check(self, mock_connection_manager):
        """测试数据库状态检查"""
        with patch("cli.base.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.database.sqlite_db_path = "./test.db"
            mock_get_config.return_value = mock_config

            # 模拟数据库连接成功
            mock_conn = MagicMock()
            mock_connection_manager.return_value.get_connection.return_value.__enter__.return_value = mock_conn

            base_cli = BaseCLI()
            status = base_cli.check_database_status()
            assert status == "正常"

    @patch("cli.base.ChromaConnectionManager")
    def test_base_cli_vector_store_status_check(self, mock_connection_manager):
        """测试向量存储状态检查"""
        with patch("cli.base.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.database.chroma_db_path = "./test_chroma"
            mock_get_config.return_value = mock_config

            # 模拟Chroma连接成功
            mock_client = MagicMock()
            mock_connection_manager.return_value._get_sync_client.return_value = (
                mock_client
            )

            base_cli = BaseCLI()
            status = base_cli.check_vector_store_status()
            assert status == "正常"

    @patch("cli.base.NetworkXGraphManager")
    def test_base_cli_graph_store_status_check(self, mock_graph_manager):
        """测试图存储状态检查"""
        with patch("cli.base.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.database.networkx_data_directory = "./test_graph"
            mock_get_config.return_value = mock_config

            # 模拟图存储有数据
            mock_graph = MagicMock()
            mock_graph_manager.return_value.get_graph.return_value.__enter__.return_value = mock_graph

            base_cli = BaseCLI()
            status = base_cli.check_graph_store_status()
            assert status == "正常"

    @patch("redis.Redis")
    def test_base_cli_task_queue_status_check(self, mock_redis):
        """测试任务队列状态检查"""
        with patch("cli.base.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_config.redis.redis_host = "localhost"
            mock_config.redis.redis_port = 6379
            mock_config.redis.redis_db = 0
            mock_config.redis.redis_password = None
            mock_get_config.return_value = mock_config

            # 模拟Redis连接成功
            mock_redis.return_value.ping.return_value = True

            base_cli = BaseCLI()
            status = base_cli.check_task_queue_status()
            assert status == "正常"

    def test_base_cli_init_config(self):
        """测试配置初始化"""
        with patch("cli.base.get_config") as mock_get_config:
            with patch("builtins.open", create=True) as mock_open:
                with patch("pathlib.Path.exists", return_value=False):
                    with patch("pathlib.Path.mkdir"):
                        mock_config = MagicMock()
                        mock_get_config.return_value = mock_config

                        base_cli = BaseCLI()
                        result = base_cli.init_config()

                        assert result is True
                        mock_open.assert_called_once()

    def test_base_cli_utility_methods(self):
        """测试工具方法"""
        with patch("cli.base.get_config") as mock_get_config:
            mock_config = MagicMock()
            mock_get_config.return_value = mock_config

            base_cli = BaseCLI()

            # 测试run_async方法
            async def test_async():
                return "test_result"

            result = base_cli.run_async(test_async())
            assert result == "test_result"


class TestDocumentsCLI:
    """文档管理CLI测试"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    def test_documents_upload_command(self, runner):
        """测试文档上传命令"""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            # 直接运行命令,不进行复杂的模拟
            result = runner.invoke(app, ["documents", "upload", temp_path])
            assert result.exit_code == 0
            assert "文档上传成功" in result.stdout
        finally:
            os.unlink(temp_path)

    def test_documents_upload_nonexistent_file(self, runner):
        """测试上传不存在的文件"""
        result = runner.invoke(app, ["documents", "upload", "nonexistent.pdf"])
        assert result.exit_code == 1
        assert "文件不存在" in result.stdout

    def test_documents_upload_unsupported_file(self, runner):
        """测试上传不支持的文件类型"""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_file:
            temp_path = temp_file.name

        try:
            with patch("pathlib.Path.exists", return_value=True):
                result = runner.invoke(app, ["documents", "upload", temp_path])
                assert result.exit_code == 1
                assert "不支持的文件类型" in result.stdout
        finally:
            os.unlink(temp_path)

    def test_documents_status_command(self, runner):
        """测试文档状态命令"""
        result = runner.invoke(app, ["documents", "status"])
        assert result.exit_code == 0
        assert "文档处理状态" in result.stdout


class TestKnowledgeBaseCLI:
    """知识库管理CLI测试"""

    @pytest.fixture
    def runner(self):
        """创建CLI测试运行器"""
        return CliRunner()

    def test_knowledge_base_status_command(self, runner):
        """测试知识库状态命令"""
        result = runner.invoke(app, ["knowledge-base", "status"])
        assert result.exit_code == 0
        assert "知识库状态" in result.stdout

    def test_knowledge_base_build_command(self, runner):
        """测试知识库构建命令"""
        with patch("pathlib.Path.exists", return_value=True):
            result = runner.invoke(app, ["knowledge-base", "build", "./test_dir"])
            assert result.exit_code == 0
            assert "知识库索引构建完成" in result.stdout

    def test_knowledge_base_search_command(self, runner):
        """测试知识库搜索命令"""
        result = runner.invoke(app, ["knowledge-base", "search", "test query"])
        assert result.exit_code == 0
        assert "搜索结果" in result.stdout


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
