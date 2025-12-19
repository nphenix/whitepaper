"""
T032文档预处理Agent测试

测试DocumentPreprocessorAgent的基本功能。
"""

from pathlib import Path

import pytest
from langchain_core.documents import Document

from src.application.agent_base import AgentConfig
from src.application.agents.document_preprocessor import DocumentPreprocessorAgent
from src.shared.config.llm_service import get_llm_service


@pytest.fixture
def agent_config() -> AgentConfig:
    """创建Agent配置"""
    return {
        "agent_id": "test-doc-preprocessor",
        "agent_name": "TestDocumentPreprocessor",
        "agent_type": "document_preprocessor",
        "description": "测试文档预处理Agent",
        "enable_error_handling": True,
        "enable_logging": True,
    }


@pytest.fixture
def agent(agent_config: AgentConfig) -> DocumentPreprocessorAgent:
    """创建Agent实例"""
    return DocumentPreprocessorAgent(
        config=agent_config,
        llm_service=get_llm_service(),
        enable_chart_conversion=False,  # 测试时禁用图表转换以加快速度
    )


def test_agent_initialization(agent: DocumentPreprocessorAgent):
    """测试Agent初始化"""
    assert agent is not None
    assert agent.agent_name == "TestDocumentPreprocessor"
    assert agent.agent_id == "test-doc-preprocessor"
    assert agent.preprocessor is not None
    assert agent.ad_remover is not None
    assert agent.enable_chart_conversion is False


def test_get_tools(agent: DocumentPreprocessorAgent):
    """测试工具获取"""
    tools = agent.get_tools()
    assert len(tools) > 0

    # 检查是否有clean_document工具
    tool_names = [tool.name for tool in tools]
    assert "clean_document" in tool_names


def test_get_tools_with_chart_conversion():
    """测试启用图表转换时的工具获取"""
    config: AgentConfig = {
        "agent_id": "test-doc-preprocessor-chart",
        "agent_name": "TestDocumentPreprocessorChart",
        "agent_type": "document_preprocessor",
        "description": "测试文档预处理Agent(启用图表转换)",
        "enable_error_handling": True,
        "enable_logging": True,
    }

    agent = DocumentPreprocessorAgent(
        config=config,
        llm_service=get_llm_service(),
        enable_chart_conversion=True,
    )

    tools = agent.get_tools()
    tool_names = [tool.name for tool in tools]

    # 应该包含clean_document和convert_charts_to_json工具
    assert "clean_document" in tool_names
    assert "convert_charts_to_json" in tool_names


def test_process_document(agent: DocumentPreprocessorAgent):
    """测试处理单个Document对象"""
    # 创建测试Document
    test_doc = Document(
        page_content="# 测试文档\n\n这是测试内容。",
        metadata={"source": "test.md", "format": "markdown"},
    )

    # 处理Document
    processed_doc = agent.process_document(test_doc)

    assert processed_doc is not None
    assert processed_doc.page_content is not None
    assert processed_doc.metadata.get("cleaned") is True


def test_process_documents(agent: DocumentPreprocessorAgent):
    """测试批量处理Document列表"""
    # 创建测试Document列表
    test_docs = [
        Document(
            page_content=f"# 测试文档 {i}\n\n这是测试内容 {i}。",
            metadata={"source": f"test_{i}.md", "format": "markdown"},
        )
        for i in range(3)
    ]

    # 批量处理
    processed_docs = agent.process_documents(test_docs)

    assert len(processed_docs) == len(test_docs)
    for doc in processed_docs:
        assert doc.metadata.get("cleaned") is True


@pytest.mark.skip(reason="需要真实的文档文件,仅在有测试文件时运行")
def test_load_and_process_real_file(agent: DocumentPreprocessorAgent):
    """测试加载并处理真实文档文件"""
    # 使用测试文件(如果存在)
    test_file = Path("data/temp/uploads/test.pdf")
    if not test_file.exists():
        pytest.skip("测试文件不存在")

    # 加载并处理
    documents = agent.load_and_process(str(test_file))

    assert len(documents) > 0
    for doc in documents:
        assert doc.page_content is not None
        assert doc.metadata is not None


def test_system_message(agent: DocumentPreprocessorAgent):
    """测试系统消息"""
    system_msg = agent._get_system_message()
    assert system_msg is not None
    assert "文档预处理" in system_msg or "DocumentPreprocessor" in system_msg
    assert "clean_document" in system_msg or "清洗" in system_msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
