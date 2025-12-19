"""
LLM广告清洗器单元测试

测试基于LLM的广告清洗器的各种功能,包括:
- 结构化输出模型
- 动态模型调用中间件
- 重试中间件
- LLM广告清洗器核心功能
- 异步处理功能
- 错误处理和重试机制

生成命令: /speckit.implement T030A-LLM-AdRemover
生成时间: 2025-12-14
来源: specs/001-multi-agent-doc-system/tasks.md
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.documents import Document
from langchain_core.language_models import BaseLanguageModel

from src.infrastructure.preprocessing.cleaners.llm_ad_remover import (
    AdCleaningResult,
    DynamicModelMiddleware,
    LLMAdRemovalError,
    LLMAdRemover,
    RetryMiddleware,
)
from src.shared.exceptions.base_exceptions import ProcessingError


class TestAdCleaningResult:
    """测试广告清洗结果结构化输出模型"""

    def test_default_values(self):
        """测试默认值"""
        result = AdCleaningResult(
            cleaned_content="清洗后的内容", cleaning_summary="清洗摘要"
        )

        assert result.cleaned_content == "清洗后的内容"
        assert result.removed_items == []
        assert result.preserved_items == []
        assert result.cleaning_summary == "清洗摘要"

    def test_with_values(self):
        """测试带值的初始化"""
        result = AdCleaningResult(
            cleaned_content="清洗后的内容",
            removed_items=["广告1", "广告2"],
            preserved_items=["图片1", "章节1"],
            cleaning_summary="清洗摘要",
        )

        assert result.cleaned_content == "清洗后的内容"
        assert result.removed_items == ["广告1", "广告2"]
        assert result.preserved_items == ["图片1", "章节1"]
        assert result.cleaning_summary == "清洗摘要"

    def test_model_validation(self):
        """测试模型验证"""
        # 正常情况应该不抛出异常
        result = AdCleaningResult(cleaned_content="测试内容")
        assert result.cleaned_content == "测试内容"


class TestDynamicModelMiddleware:
    """测试动态模型调用中间件"""

    def setup_method(self):
        """设置测试环境"""
        self.primary_model = Mock(spec=BaseLanguageModel)
        self.fallback_model = Mock(spec=BaseLanguageModel)
        self.middleware = DynamicModelMiddleware(
            primary_model=self.primary_model,
            fallback_model=self.fallback_model,
            switch_threshold=100,
        )

    def test_initialization(self):
        """测试初始化"""
        middleware = DynamicModelMiddleware(
            primary_model=self.primary_model,
            fallback_model=self.fallback_model,
            switch_threshold=200,
        )

        assert middleware.primary_model == self.primary_model
        assert middleware.fallback_model == self.fallback_model
        assert middleware.switch_threshold == 200

    def test_initialization_without_fallback(self):
        """测试无备用模型的初始化"""
        middleware = DynamicModelMiddleware(
            primary_model=self.primary_model, fallback_model=None, switch_threshold=200
        )

        assert middleware.primary_model == self.primary_model
        assert middleware.fallback_model is None

    def test_wrap_model_call_short_content(self):
        """测试短内容使用主模型"""
        # 创建模拟请求
        request = Mock(spec=ModelRequest)
        request.messages = [Mock(content="短内容"), Mock(content="更多内容")]

        # 创建模拟处理器
        handler = Mock(return_value=Mock(spec=ModelResponse))

        # 调用中间件
        self.middleware.wrap_model_call(request, handler)

        # 验证使用了主模型
        assert request.model == self.primary_model
        handler.assert_called_once_with(request)

    def test_wrap_model_call_long_content(self):
        """测试长内容使用备用模型"""
        # 创建长内容请求
        long_content = "内容" * 1000  # 超过阈值
        request = Mock(spec=ModelRequest)
        request.messages = [Mock(content=long_content), Mock(content="更多内容")]

        # 创建模拟处理器
        handler = Mock(return_value=Mock(spec=ModelResponse))

        # 调用中间件
        self.middleware.wrap_model_call(request, handler)

        # 验证使用了备用模型
        assert request.model == self.fallback_model
        handler.assert_called_once_with(request)

    def test_wrap_model_call_no_fallback(self):
        """测试无备用模型时始终使用主模型"""
        middleware = DynamicModelMiddleware(
            primary_model=self.primary_model, fallback_model=None, switch_threshold=100
        )

        # 创建长内容请求
        long_content = "内容" * 1000  # 超过阈值
        request = Mock(spec=ModelRequest)
        request.messages = [Mock(content=long_content)]

        # 创建模拟处理器
        handler = Mock(return_value=Mock(spec=ModelResponse))

        # 调用中间件
        middleware.wrap_model_call(request, handler)

        # 验证使用了主模型(因为没有备用模型)
        assert request.model == self.primary_model
        handler.assert_called_once_with(request)

    def test_wrap_model_call_content_without_content_attribute(self):
        """测试消息没有content属性的情况"""
        request = Mock(spec=ModelRequest)
        request.messages = [
            Mock(),  # 没有content属性
            Mock(content="有内容的消息"),
        ]

        # 创建模拟处理器
        handler = Mock(return_value=Mock(spec=ModelResponse))

        # 调用中间件
        self.middleware.wrap_model_call(request, handler)

        # 验证使用了主模型(因为总长度为0)
        assert request.model == self.primary_model
        handler.assert_called_once_with(request)


class TestRetryMiddleware:
    """测试重试中间件"""

    def setup_method(self):
        """设置测试环境"""
        self.middleware = RetryMiddleware(
            max_retries=3,
            retry_delay=0.1,  # 减少测试时间
        )

    def test_initialization(self):
        """测试初始化"""
        middleware = RetryMiddleware(max_retries=5, retry_delay=2.0)

        assert middleware.max_retries == 5
        assert middleware.retry_delay == 2.0

    def test_wrap_model_call_success_first_try(self):
        """测试第一次调用成功"""
        request = Mock(spec=ModelRequest)
        handler = Mock(return_value=Mock(spec=ModelResponse))

        # 调用中间件
        result = self.middleware.wrap_model_call(request, handler)

        # 验证只调用了一次
        handler.assert_called_once_with(request)
        assert result is not None

    def test_wrap_model_call_success_after_retry(self):
        """测试重试后成功"""
        request = Mock(spec=ModelRequest)
        response = Mock(spec=ModelResponse)

        # 前两次失败,第三次成功
        handler = Mock(side_effect=[Exception("错误1"), Exception("错误2"), response])

        # 调用中间件
        result = self.middleware.wrap_model_call(request, handler)

        # 验证调用了三次
        assert handler.call_count == 3
        assert result is response

    def test_wrap_model_call_all_retries_failed(self):
        """测试所有重试都失败"""
        request = Mock(spec=ModelRequest)
        error = Exception("最终错误")

        # 所有调用都失败
        handler = Mock(side_effect=[Exception("错误1"), Exception("错误2"), error])

        # 调用中间件,应该抛出异常
        with pytest.raises(Exception) as exc_info:
            self.middleware.wrap_model_call(request, handler)

        # 验证调用了三次,且抛出了最后一个错误
        assert handler.call_count == 3
        assert str(exc_info.value) == "最终错误"

    @patch("time.sleep")
    def test_wrap_model_call_retry_delay(self, mock_sleep):
        """测试重试延迟"""
        request = Mock(spec=ModelRequest)
        response = Mock(spec=ModelResponse)

        # 第一次失败,第二次成功
        handler = Mock(side_effect=[Exception("错误1"), response])

        # 调用中间件
        self.middleware.wrap_model_call(request, handler)

        # 验证调用了两次,且有一次延迟
        assert handler.call_count == 2
        mock_sleep.assert_called_once_with(0.1)


class TestLLMAdRemover:
    """测试LLM广告清洗器"""

    def setup_method(self):
        """设置测试环境"""
        # 模拟LLM服务
        self.mock_llm_service = Mock()
        self.mock_model = Mock(spec=BaseLanguageModel)
        self.mock_llm_service.get_ad_cleaning_chat_model.return_value = self.mock_model

        # 模拟Agent
        self.mock_agent = Mock()
        self.mock_agent.invoke.return_value = {
            "structured_response": AdCleaningResult(
                cleaned_content="清洗后的内容",
                removed_items=["广告1"],
                preserved_items=["图片1"],
                cleaning_summary="清洗完成",
            )
        }

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_initialization(self, mock_get_llm_service):
        """测试初始化"""
        mock_get_llm_service.return_value = self.mock_llm_service

        remover = LLMAdRemover()

        # 验证LLM服务被调用
        mock_get_llm_service.assert_called_once()
        self.mock_llm_service.get_ad_cleaning_chat_model.assert_called_once()

        # 验证属性
        assert remover.llm_service == self.mock_llm_service
        assert remover.model == self.mock_model
        assert remover.enable_dynamic_model is False
        assert remover.enable_retry is True

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_initialization_with_custom_params(self, mock_get_llm_service):
        """测试自定义参数初始化"""
        mock_get_llm_service.return_value = self.mock_llm_service

        remover = LLMAdRemover(
            enable_dynamic_model=True,
            enable_retry=False,
            max_retries=5,
            retry_delay=2.0,
        )

        # 验证属性
        assert remover.enable_dynamic_model is True
        assert remover.enable_retry is False
        assert remover.max_retries == 5
        assert remover.retry_delay == 2.0

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_initialization_llm_service_error(self, mock_get_llm_service):
        """测试LLM服务初始化错误"""
        mock_get_llm_service.return_value = self.mock_llm_service
        self.mock_llm_service.get_ad_cleaning_chat_model.side_effect = Exception(
            "模型获取失败"
        )

        # 应该抛出ProcessingError
        with pytest.raises(ProcessingError) as exc_info:
            LLMAdRemover()

        assert "无法获取广告清洗模型" in str(exc_info.value)

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_build_agent(self, mock_get_llm_service, mock_create_agent):
        """测试构建Agent"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        remover = LLMAdRemover(enable_retry=False)
        agent = remover._build_agent()

        # 验证create_agent被调用
        mock_create_agent.assert_called_once()

        # 验证返回的Agent
        assert agent == self.mock_agent
        assert remover._agent == self.mock_agent

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_build_agent_with_retry(self, mock_get_llm_service, mock_create_agent):
        """测试构建带重试的Agent"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        remover = LLMAdRemover(enable_retry=True, max_retries=5, retry_delay=2.0)
        remover._build_agent()

        # 验证create_agent被调用
        mock_create_agent.assert_called_once()

        # 验证中间件配置
        call_args = mock_create_agent.call_args
        middleware = call_args[1]["middleware"]
        assert len(middleware) == 1
        assert isinstance(middleware[0], RetryMiddleware)
        assert middleware[0].max_retries == 5
        assert middleware[0].retry_delay == 2.0

    def test_get_system_message(self):
        """测试获取系统消息"""
        remover = LLMAdRemover.__new__(LLMAdRemover)  # 不调用__init__
        system_message = remover._get_system_message()

        # 验证系统消息包含关键内容
        assert "广告内容" in system_message
        assert "目录" in system_message
        assert "图片链接" in system_message
        assert "Markdown格式" in system_message

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_clean_document(self, mock_get_llm_service, mock_create_agent):
        """测试清洗单个文档"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        remover = LLMAdRemover()
        document = Document(
            page_content="这是包含广告的文档内容", metadata={"source": "test.md"}
        )

        cleaned_doc = remover.clean_document(document)

        # 验证Agent被调用
        self.mock_agent.invoke.assert_called_once()

        # 验证返回的文档
        assert cleaned_doc.page_content == "清洗后的内容"
        assert cleaned_doc.metadata["llm_cleaned"] is True
        assert "cleaning_timestamp" in cleaned_doc.metadata
        assert cleaned_doc.metadata["removed_items_count"] == 1
        assert cleaned_doc.metadata["preserved_items_count"] == 1

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_clean_document_bytes_content(
        self, mock_get_llm_service, mock_create_agent
    ):
        """测试处理字节内容的文档"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        # 修改Agent返回值为字节内容
        self.mock_agent.invoke.return_value = {
            "structured_response": AdCleaningResult(
                cleaned_content="清洗后的内容".encode(),
                removed_items=["广告1"],
                preserved_items=["图片1"],
                cleaning_summary="清洗完成",
            )
        }

        remover = LLMAdRemover()
        document = Document(
            page_content="这是包含广告的文档内容".encode(),
            metadata={"source": "test.md"},
        )

        cleaned_doc = remover.clean_document(document)

        # 验证字节内容被正确处理
        assert cleaned_doc.page_content == "清洗后的内容"
        assert isinstance(cleaned_doc.page_content, str)

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_clean_document_no_structured_response(
        self, mock_get_llm_service, mock_create_agent
    ):
        """测试没有结构化响应的情况"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        # 修改Agent返回值,没有结构化响应
        mock_message = Mock()
        mock_message.content = "清洗后的内容"
        self.mock_agent.invoke.return_value = {"messages": [mock_message]}

        remover = LLMAdRemover()
        document = Document(
            page_content="这是包含广告的文档内容", metadata={"source": "test.md"}
        )

        cleaned_doc = remover.clean_document(document)

        # 验证从messages中提取内容
        assert cleaned_doc.page_content == "清洗后的内容"

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_clean_document_error(self, mock_get_llm_service, mock_create_agent):
        """测试清洗文档错误"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        # Agent调用失败
        self.mock_agent.invoke.side_effect = Exception("模型调用失败")

        remover = LLMAdRemover()
        document = Document(
            page_content="这是包含广告的文档内容", metadata={"source": "test.md"}
        )

        # 应该抛出ProcessingError
        with pytest.raises(ProcessingError) as exc_info:
            remover.clean_document(document)

        assert "LLM广告清洗失败" in str(exc_info.value)

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_clean_documents_batch(self, mock_get_llm_service, mock_create_agent):
        """测试批量清洗文档"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        remover = LLMAdRemover()
        documents = [
            Document(page_content="文档1内容", metadata={"source": "test1.md"}),
            Document(page_content="文档2内容", metadata={"source": "test2.md"}),
            Document(page_content="文档3内容", metadata={"source": "test3.md"}),
        ]

        cleaned_docs = remover.clean_documents(documents)

        # 验证返回的文档数量
        assert len(cleaned_docs) == 3

        # 验证每个文档都被清洗
        for doc in cleaned_docs:
            assert doc.page_content == "清洗后的内容"
            assert doc.metadata["llm_cleaned"] is True

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    def test_clean_documents_batch_with_error(
        self, mock_get_llm_service, mock_create_agent
    ):
        """测试批量清洗文档时有错误"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        # 第二个文档清洗失败
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                msg = "清洗失败"
                raise Exception(msg)
            return {
                "structured_response": AdCleaningResult(
                    cleaned_content=f"清洗后的内容{call_count}",
                    removed_items=[],
                    preserved_items=[],
                    cleaning_summary="",
                )
            }

        self.mock_agent.invoke.side_effect = side_effect

        remover = LLMAdRemover()
        documents = [
            Document(page_content="文档1内容", metadata={"source": "test1.md"}),
            Document(page_content="文档2内容", metadata={"source": "test2.md"}),
            Document(page_content="文档3内容", metadata={"source": "test3.md"}),
        ]

        cleaned_docs = remover.clean_documents(documents)

        # 验证返回的文档数量
        assert len(cleaned_docs) == 3

        # 验证第一个和第三个文档被清洗,第二个保持原样
        assert cleaned_docs[0].page_content == "清洗后的内容1"
        assert cleaned_docs[1].page_content == "文档2内容"  # 保持原样
        assert cleaned_docs[2].page_content == "清洗后的内容3"


class TestLLMAdRemoverAsync:
    """测试LLM广告清洗器异步功能"""

    def setup_method(self):
        """设置测试环境"""
        # 模拟LLM服务
        self.mock_llm_service = Mock()
        self.mock_model = Mock(spec=BaseLanguageModel)
        self.mock_llm_service.get_ad_cleaning_chat_model.return_value = self.mock_model

        # 模拟异步Agent
        self.mock_agent = AsyncMock()
        self.mock_agent.ainvoke.return_value = {
            "structured_response": AdCleaningResult(
                cleaned_content="清洗后的内容",
                removed_items=["广告1"],
                preserved_items=["图片1"],
                cleaning_summary="清洗完成",
            )
        }

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    @pytest.mark.asyncio
    async def test_aclean_document(self, mock_get_llm_service, mock_create_agent):
        """测试异步清洗单个文档"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        remover = LLMAdRemover()
        document = Document(
            page_content="这是包含广告的文档内容", metadata={"source": "test.md"}
        )

        cleaned_doc = await remover.aclean_document(document)

        # 验证异步Agent被调用
        self.mock_agent.ainvoke.assert_called_once()

        # 验证返回的文档
        assert cleaned_doc.page_content == "清洗后的内容"
        assert cleaned_doc.metadata["llm_cleaned"] is True
        assert "cleaning_timestamp" in cleaned_doc.metadata

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    @pytest.mark.asyncio
    async def test_aclean_document_bytes_content(
        self, mock_get_llm_service, mock_create_agent
    ):
        """测试异步处理字节内容的文档"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        # 修改Agent返回值为字节内容
        self.mock_agent.ainvoke.return_value = {
            "structured_response": AdCleaningResult(
                cleaned_content="清洗后的内容".encode(),
                removed_items=["广告1"],
                preserved_items=["图片1"],
                cleaning_summary="清洗完成",
            )
        }

        remover = LLMAdRemover()
        document = Document(
            page_content="这是包含广告的文档内容".encode(),
            metadata={"source": "test.md"},
        )

        cleaned_doc = await remover.aclean_document(document)

        # 验证字节内容被正确处理
        assert cleaned_doc.page_content == "清洗后的内容"
        assert isinstance(cleaned_doc.page_content, str)

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    @pytest.mark.asyncio
    async def test_aclean_document_error(self, mock_get_llm_service, mock_create_agent):
        """测试异步清洗文档错误"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        # 异步Agent调用失败
        self.mock_agent.ainvoke.side_effect = Exception("模型调用失败")

        remover = LLMAdRemover()
        document = Document(
            page_content="这是包含广告的文档内容", metadata={"source": "test.md"}
        )

        # 应该抛出ProcessingError
        with pytest.raises(ProcessingError) as exc_info:
            await remover.aclean_document(document)

        assert "LLM广告清洗失败" in str(exc_info.value)

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    @pytest.mark.asyncio
    async def test_aclean_documents_batch(
        self, mock_get_llm_service, mock_create_agent
    ):
        """测试异步批量清洗文档"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        remover = LLMAdRemover()
        documents = [
            Document(page_content="文档1内容", metadata={"source": "test1.md"}),
            Document(page_content="文档2内容", metadata={"source": "test2.md"}),
            Document(page_content="文档3内容", metadata={"source": "test3.md"}),
        ]

        cleaned_docs = await remover.aclean_documents(documents)

        # 验证返回的文档数量
        assert len(cleaned_docs) == 3

        # 验证每个文档都被清洗
        for doc in cleaned_docs:
            assert doc.page_content == "清洗后的内容"
            assert doc.metadata["llm_cleaned"] is True

    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.create_agent")
    @patch("src.infrastructure.preprocessing.cleaners.llm_ad_remover.get_llm_service")
    @pytest.mark.asyncio
    async def test_aclean_documents_batch_with_error(
        self, mock_get_llm_service, mock_create_agent
    ):
        """测试异步批量清洗文档时有错误"""
        mock_get_llm_service.return_value = self.mock_llm_service
        mock_create_agent.return_value = self.mock_agent

        # 第二个文档清洗失败
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                msg = "清洗失败"
                raise Exception(msg)
            return {
                "structured_response": AdCleaningResult(
                    cleaned_content=f"清洗后的内容{call_count}",
                    removed_items=[],
                    preserved_items=[],
                    cleaning_summary="",
                )
            }

        self.mock_agent.ainvoke.side_effect = side_effect

        remover = LLMAdRemover()
        documents = [
            Document(page_content="文档1内容", metadata={"source": "test1.md"}),
            Document(page_content="文档2内容", metadata={"source": "test2.md"}),
            Document(page_content="文档3内容", metadata={"source": "test3.md"}),
        ]

        cleaned_docs = await remover.aclean_documents(documents)

        # 验证返回的文档数量
        assert len(cleaned_docs) == 3

        # 验证第一个和第三个文档被清洗,第二个保持原样
        assert cleaned_docs[0].page_content == "清洗后的内容1"
        assert cleaned_docs[1].page_content == "文档2内容"  # 保持原样
        assert cleaned_docs[2].page_content == "清洗后的内容3"


class TestLLMAdRemovalError:
    """测试LLM广告清洗异常类"""

    def test_exception_inheritance(self):
        """测试异常继承关系"""
        error = LLMAdRemovalError("测试错误")

        # 验证异常继承关系
        assert isinstance(error, ProcessingError)

    def test_exception_message(self):
        """测试异常消息"""
        message = "测试错误消息"
        error = LLMAdRemovalError(message)

        assert str(error) == message
