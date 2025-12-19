# 生成命令: /speckit.implement T005
# 生成时间: 2025-12-07
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
pytest配置文件
定义测试夹具和全局测试配置
"""

import os
import shutil
import sys
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "cli"))


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """返回测试数据目录路径"""
    return project_root / "tests" / "test_data"


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """创建临时目录夹具"""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def sample_text_file(temp_dir: Path) -> Path:
    """创建示例文本文件夹具"""
    file_path = temp_dir / "sample.txt"
    content = "这是一个测试文本文件。\n包含多行内容。\n用于测试文档处理功能。"
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def sample_markdown_file(temp_dir: Path) -> Path:
    """创建示例Markdown文件夹具"""
    file_path = temp_dir / "sample.md"
    content = """# 测试文档

这是一个测试Markdown文档。

## 章节一

内容一

## 章节二

内容二

- 列表项1
- 列表项2
"""
    file_path.write_text(content, encoding="utf-8")
    return file_path


@pytest.fixture
def mock_redis():
    """模拟Redis连接"""
    redis_mock = MagicMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    return redis_mock


@pytest.fixture
def mock_chroma_client():
    """模拟ChromaDB客户端"""
    client_mock = MagicMock()
    collection_mock = MagicMock()
    client_mock.get_or_create_collection.return_value = collection_mock
    collection_mock.add.return_value = None
    collection_mock.query.return_value = {"ids": [], "documents": [], "metadatas": []}
    return client_mock


@pytest.fixture
def mock_llm():
    """模拟LLM客户端"""
    llm_mock = AsyncMock()
    llm_mock.ainvoke.return_value = "这是一个模拟的LLM响应"
    llm_mock.apredict.return_value = "这是一个模拟的LLM预测"
    return llm_mock


@pytest.fixture
def mock_embedding_model():
    """模拟嵌入模型"""
    embedding_mock = MagicMock()
    embedding_mock.embed_query.return_value = [0.1] * 384  # 模拟384维向量
    embedding_mock.embed_documents.return_value = [[0.1] * 384, [0.2] * 384]
    return embedding_mock


@pytest.fixture
def sqlite_test_db(temp_dir: Path):
    """创建SQLite测试数据库夹具"""
    db_path = temp_dir / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    # 创建会话工厂
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # 创建表结构(这里需要导入实际的模型,暂时跳过)
    # Base.metadata.create_all(bind=engine)

    yield SessionLocal

    # 清理
    engine.dispose()


@pytest.fixture
def sample_document_data():
    """示例文档数据夹具"""
    return {
        "title": "测试文档",
        "content": "这是测试文档的内容",
        "metadata": {
            "source": "test",
            "type": "text",
            "created_at": "2025-12-07T00:00:00Z",
        },
    }


@pytest.fixture
def sample_knowledge_entry():
    """示例知识库条目夹具"""
    return {
        "id": "test-entry-1",
        "content": "这是知识库条目的内容",
        "source": "test_source",
        "metadata": {
            "type": "knowledge",
            "created_at": "2025-12-07T00:00:00Z",
            "tags": ["test", "sample"],
        },
    }


@pytest.fixture
def sample_outline():
    """示例大纲夹具"""
    return {
        "title": "测试大纲",
        "sections": [
            {
                "id": "section-1",
                "title": "第一章",
                "content": "第一章的内容",
                "subsections": [
                    {
                        "id": "subsection-1-1",
                        "title": "第一节",
                        "content": "第一节的内容",
                    }
                ],
            }
        ],
    }


@pytest.fixture
def mock_agent_state():
    """模拟Agent状态夹具"""
    return {
        "agent_id": "test-agent-1",
        "status": "idle",
        "current_task": None,
        "history": [],
        "metadata": {
            "created_at": "2025-12-07T00:00:00Z",
            "updated_at": "2025-12-07T00:00:00Z",
        },
    }


@pytest.fixture
def mock_file_upload():
    """模拟文件上传夹具"""
    return {
        "filename": "test_document.pdf",
        "content_type": "application/pdf",
        "size": 1024,
        "path": "/tmp/test_document.pdf",
    }


# 异步夹具
@pytest_asyncio.fixture
async def async_temp_dir() -> AsyncGenerator[Path, None]:
    """创建异步临时目录夹具"""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest_asyncio.fixture
async def mock_async_llm():
    """模拟异步LLM客户端"""
    llm_mock = AsyncMock()
    llm_mock.ainvoke.return_value = "这是一个模拟的异步LLM响应"
    llm_mock.apredict.return_value = "这是一个模拟的异步LLM预测"
    llm_mock.agenerate.return_value = {
        "generations": [["这是一个模拟的异步LLM生成内容"]],
        "llm_output": {"token_usage": {"total_tokens": 10}},
    }
    return llm_mock


@pytest_asyncio.fixture
async def mock_async_redis():
    """模拟异步Redis连接"""
    redis_mock = AsyncMock()
    redis_mock.ping.return_value = True
    redis_mock.get.return_value = None
    redis_mock.set.return_value = True
    redis_mock.delete.return_value = 1
    redis_mock.exists.return_value = False
    return redis_mock


# 标记定义
def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line("markers", "slow: 标记为慢速测试")
    config.addinivalue_line("markers", "integration: 标记为集成测试")
    config.addinivalue_line("markers", "unit: 标记为单元测试")
    config.addinivalue_line("markers", "contract: 标记为契约测试")
    config.addinivalue_line("markers", "api: 标记为API测试")
    config.addinivalue_line("markers", "cli: 标记为CLI测试")
    config.addinivalue_line("markers", "agent: 标记为Agent测试")
    config.addinivalue_line("markers", "infrastructure: 标记为基础设施测试")
    config.addinivalue_line("markers", "requires_redis: 需要Redis服务的测试")
    config.addinivalue_line("markers", "requires_chroma: 需要ChromaDB的测试")


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试收集,自动添加标记"""
    for item in items:
        # 根据文件路径自动添加标记
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "contract" in str(item.fspath):
            item.add_marker(pytest.mark.contract)

        # 根据测试名称自动添加标记
        if "test_api" in item.name:
            item.add_marker(pytest.mark.api)
        elif "test_cli" in item.name:
            item.add_marker(pytest.mark.cli)
        elif "test_agent" in item.name:
            item.add_marker(pytest.mark.agent)
        elif "test_infrastructure" in item.name:
            item.add_marker(pytest.mark.infrastructure)


# 环境变量设置
@pytest.fixture(autouse=True, scope="session")
def setup_test_environment():
    """设置测试环境变量"""
    # 设置pytest运行标志,用于日志配置
    import sys

    sys._pytest_running = True

    # 设置测试环境变量
    os.environ["TESTING"] = "true"
    os.environ["LOG_LEVEL"] = "DEBUG"

    # 设置测试数据库路径
    os.environ["DATABASE_URL"] = "sqlite:///test.db"

    # 设置测试Redis配置
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"

    # 设置测试ChromaDB配置
    os.environ["CHROMA_PERSIST_DIRECTORY"] = "./test_chroma"

    yield

    # 清理环境变量
    test_vars = [
        "TESTING",
        "LOG_LEVEL",
        "DATABASE_URL",
        "REDIS_URL",
        "CHROMA_PERSIST_DIRECTORY",
    ]
    for var in test_vars:
        if var in os.environ:
            del os.environ[var]

    # 清理pytest标志
    if hasattr(sys, "_pytest_running"):
        delattr(sys, "_pytest_running")
