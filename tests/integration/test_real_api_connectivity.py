# 生成命令: 测试 T009 任务的实际API连通性
# 生成时间: 2025-12-07
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
实际API连通性测试
测试 katpro1(OpenAI兼容)和阿里百炼(DashScope)模型的实际连接和功能
"""

import time

import pytest

from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.config.settings import load_config


class TestKATPro1Connectivity:
    """测试 katpro1(OpenAI兼容)模型的连通性"""

    def setup_method(self):
        """测试前设置"""
        # 清理单例状态
        LLMService._instance = None
        self.llm_service = get_llm_service()

        # 加载配置
        self.config = load_config()
        self.llm_service.set_config(self.config)

    @pytest.mark.integration
    @pytest.mark.slow
    def test_katpro1_chat_model_connectivity(self):
        """测试 katpro1 聊天模型的实际连通性"""
        try:
            # 获取 katpro1 聊天模型
            model = self.llm_service.get_chat_model("openai_compatible")

            # 测试简单对话
            from langchain_core.messages import HumanMessage

            messages = [HumanMessage(content="你好,请回复'连接成功'")]

            start_time = time.time()
            response = model.invoke(messages)
            end_time = time.time()

            # 验证响应
            assert response is not None
            assert hasattr(response, "content")
            assert len(response.content) > 0
            assert "连接成功" in response.content or "成功" in response.content

            # 记录响应时间
            response_time = end_time - start_time
            print(f"katpro1 响应时间: {response_time:.2f}秒")
            print(f"katpro1 响应内容: {response.content}")

            assert response_time < 30.0  # 响应时间应少于30秒

        except Exception as e:
            pytest.fail(f"katpro1 连接失败: {e!s}")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_katpro1_chat_model_with_different_temperatures(self):
        """测试 katpro1 不同温度参数的影响"""
        try:
            # 获取模型
            model = self.llm_service.get_chat_model("openai_compatible")

            # 测试不同温度
            temperatures = [0.0, 0.7, 1.0]
            responses = []

            for temp in temperatures:
                # 创建带温度的模型
                temp_model = model.with_config(temperature=temp)

                from langchain_core.messages import HumanMessage

                messages = [HumanMessage(content="请用一句话描述人工智能")]

                response = temp_model.invoke(messages)
                responses.append(response.content)

                assert response is not None
                assert len(response.content) > 0

            # 验证不同温度产生不同响应(至少有一些差异)
            assert len(set(responses)) >= 1  # 至少有一个响应

            print("不同温度的响应:")
            for i, temp in enumerate(temperatures):
                print(f"温度 {temp}: {responses[i]}")

        except Exception as e:
            pytest.fail(f"katpro1 温度参数测试失败: {e!s}")


class TestDashScopeConnectivity:
    """测试阿里百炼(DashScope)模型的连通性"""

    def setup_method(self):
        """测试前设置"""
        # 清理单例状态
        LLMService._instance = None
        self.llm_service = get_llm_service()

        # 加载配置
        self.config = load_config()
        self.llm_service.set_config(self.config)

    @pytest.mark.integration
    @pytest.mark.slow
    def test_dashscope_embedding_model_connectivity(self):
        """测试阿里百炼嵌入模型的实际连通性"""
        try:
            # 获取嵌入模型
            model = self.llm_service.get_embedding_model("dashscope")

            # 测试单个文本嵌入
            test_text = "这是一个测试文本,用于验证嵌入模型的功能。"
            start_time = time.time()
            embedding = model.embed_query(test_text)
            end_time = time.time()

            # 验证嵌入结果
            assert embedding is not None
            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, (float, int)) for x in embedding)

            # 验证维度(根据配置应该是1536)
            expected_dimension = self.config.embedding.dimension
            assert len(embedding) == expected_dimension

            # 记录响应时间
            response_time = end_time - start_time
            print(f"DashScope 嵌入响应时间: {response_time:.2f}秒")
            print(f"嵌入向量维度: {len(embedding)}")
            print(f"嵌入向量前5个值: {embedding[:5]}")

            assert response_time < 30.0  # 响应时间应少于30秒

        except Exception as e:
            pytest.fail(f"DashScope 嵌入模型连接失败: {e!s}")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_dashscope_embedding_batch_processing(self):
        """测试阿里百炼嵌入模型的批量处理"""
        try:
            # 获取嵌入模型
            model = self.llm_service.get_embedding_model("dashscope")

            # 测试批量嵌入
            test_texts = [
                "这是第一个测试文本",
                "这是第二个测试文本",
                "这是第三个测试文本",
            ]

            start_time = time.time()
            embeddings = model.embed_documents(test_texts)
            end_time = time.time()

            # 验证批量嵌入结果
            assert embeddings is not None
            assert isinstance(embeddings, list)
            assert len(embeddings) == len(test_texts)

            # 验证每个嵌入向量
            for _i, embedding in enumerate(embeddings):
                assert embedding is not None
                assert isinstance(embedding, list)
                assert len(embedding) == self.config.embedding.dimension
                assert all(isinstance(x, (float, int)) for x in embedding)

            # 记录响应时间
            response_time = end_time - start_time
            print(f"DashScope 批量嵌入响应时间: {response_time:.2f}秒")
            print(f"处理文本数量: {len(test_texts)}")
            print(f"平均每个文本响应时间: {response_time / len(test_texts):.2f}秒")

            assert response_time < 60.0  # 批量处理响应时间应少于60秒

        except Exception as e:
            pytest.fail(f"DashScope 批量嵌入测试失败: {e!s}")

    @pytest.mark.integration
    @pytest.mark.slow
    def test_dashscope_rerank_model_connectivity(self):
        """测试阿里百炼重排序模型的实际连通性"""
        try:
            # 获取重排序模型
            model = self.llm_service.get_rerank_model("dashscope")

            # 测试重排序功能
            query = "人工智能的发展趋势"
            documents = [
                "人工智能正在快速发展,改变着各行各业。",
                "机器学习是人工智能的一个重要分支。",
                "深度学习技术在近年来取得了突破性进展。",
                "自然语言处理是人工智能应用的重要领域。",
                "计算机视觉让机器能够理解和分析图像。",
            ]

            start_time = time.time()
            results = model.rerank(query, documents)
            end_time = time.time()

            # 验证重排序结果
            assert results is not None
            assert isinstance(results, list)
            assert len(results) <= len(documents)  # 结果数量应不超过输入文档数量

            # 验证每个结果的结构
            for result in results:
                assert isinstance(result, dict)
                assert "document" in result
                assert "index" in result
                assert "relevance_score" in result

                # 验证相关性分数
                score = result["relevance_score"]
                assert isinstance(score, (float, int))
                assert 0.0 <= score <= 1.0  # 相关性分数应在0-1范围内

                # 验证文档索引
                index = result["index"]
                assert isinstance(index, int)
                assert 0 <= index < len(documents)

                # 验证文档内容
                doc = result["document"]
                assert doc in documents

            # 记录响应时间
            response_time = end_time - start_time
            print(f"DashScope 重排序响应时间: {response_time:.2f}秒")
            print(f"输入文档数量: {len(documents)}")
            print(f"返回结果数量: {len(results)}")

            # 打印重排序结果
            print("重排序结果:")
            for i, result in enumerate(results):
                print(
                    f"{i + 1}. [分数: {result['relevance_score']:.3f}] {result['document']}"
                )

            assert response_time < 30.0  # 响应时间应少于30秒

        except Exception as e:
            pytest.fail(f"DashScope 重排序模型连接失败: {e!s}")


class TestIntegratedWorkflow:
    """测试集成工作流程"""

    def setup_method(self):
        """测试前设置"""
        # 清理单例状态
        LLMService._instance = None
        self.llm_service = get_llm_service()

        # 加载配置
        self.config = load_config()
        self.llm_service.set_config(self.config)

    @pytest.mark.integration
    @pytest.mark.slow
    def test_complete_workflow(self):
        """测试完整的工作流程:嵌入 + 重排序 + LLM生成"""
        try:
            # 1. 获取模型
            chat_model = self.llm_service.get_chat_model("openai_compatible")
            embedding_model = self.llm_service.get_embedding_model("dashscope")
            rerank_model = self.llm_service.get_rerank_model("dashscope")

            # 2. 准备测试数据
            query = "什么是人工智能?"
            documents = [
                "人工智能(AI)是计算机科学的一个分支,致力于创建能够执行通常需要人类智能的任务的系统。",
                "机器学习是人工智能的一个子集,使计算机能够在没有明确编程的情况下学习和改进。",
                "深度学习是机器学习的一个子集,使用人工神经网络来模拟人脑的工作方式。",
                "自然语言处理(NLP)是人工智能的一个领域,专注于计算机与人类语言之间的交互。",
                "计算机视觉是人工智能的一个领域,使计算机能够从数字图像或视频中获取有意义的信息。",
            ]

            # 3. 嵌入查询
            print("步骤1: 嵌入查询")
            query_embedding = embedding_model.embed_query(query)
            assert query_embedding is not None
            assert len(query_embedding) == self.config.embedding.dimension

            # 4. 嵌入文档
            print("步骤2: 批量嵌入文档")
            doc_embeddings = embedding_model.embed_documents(documents)
            assert doc_embeddings is not None
            assert len(doc_embeddings) == len(documents)

            # 5. 重排序文档
            print("步骤3: 重排序文档")
            rerank_results = rerank_model.rerank(query, documents)
            assert rerank_results is not None
            assert len(rerank_results) > 0

            # 6. 使用最相关的文档生成回答
            print("步骤4: 生成回答")
            most_relevant_doc = rerank_results[0]["document"]

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="你是一个知识助手,请根据提供的上下文回答问题。"),
                HumanMessage(
                    content=f"问题: {query}\n\n上下文: {most_relevant_doc}\n\n请基于上下文回答问题。"
                ),
            ]

            response = chat_model.invoke(messages)

            # 7. 验证最终结果
            assert response is not None
            assert hasattr(response, "content")
            assert len(response.content) > 0

            print(f"最终回答: {response.content}")

            # 验证回答包含相关信息
            assert any(
                keyword in response.content.lower()
                for keyword in ["人工智能", "ai", "计算机", "智能"]
            )

        except Exception as e:
            pytest.fail(f"集成工作流程测试失败: {e!s}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
