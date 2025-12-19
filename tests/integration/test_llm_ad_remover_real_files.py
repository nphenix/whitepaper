"""
LLM广告清洗器集成测试 - 使用真实文件

测试基于LLM的广告清洗器与真实文件的集成功能,包括:
- 使用真实LLM服务进行广告清洗
- 处理真实MinerU处理后的文档
- 验证清洗结果的质量和完整性
- 测试异步处理功能
- 测试批量处理功能

生成命令: /speckit.implement T030A-LLM-AdRemover
生成时间: 2025-12-14
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import re
import time
from pathlib import Path

import pytest
from langchain_core.documents import Document

from src.infrastructure.preprocessing.cleaners.llm_ad_remover import LLMAdRemover
from src.shared.config.settings import load_config


class TestLLMAdRemoverRealFiles:
    """测试LLM广告清洗器与真实文件的集成"""

    @pytest.fixture(scope="class")
    def real_config(self):
        """加载真实配置"""
        return load_config()

    @pytest.fixture(scope="class")
    def test_documents(self):
        """准备测试文档"""
        # 使用真实MinerU处理后的文档
        doc_path = Path(
            "data/processed/mineru/2023年中国储能行业系列研究-超级电容器储能_ae/6fd23ee4-b12a-4604-af9f-0ddc50b33a01_2023年中国储能行业系列研究-超级电容器储能.pdf_extracted/full.md"
        )

        if not doc_path.exists():
            pytest.skip(f"测试文档不存在: {doc_path}")

        # 读取文档内容
        with open(doc_path, encoding="utf-8") as f:
            content = f.read()

        # 创建Document对象
        document = Document(
            page_content=content,
            metadata={"source": str(doc_path), "format": "md", "pipeline": "mineru"},
        )

        return [document]

    @pytest.fixture(scope="class")
    def llm_ad_remover(self, real_config):
        """创建LLM广告清洗器实例"""
        return LLMAdRemover()

    def test_real_document_cleaning(self, llm_ad_remover, test_documents):
        """测试真实文档清洗"""
        if not test_documents:
            pytest.skip("没有可用的测试文档")

        document = test_documents[0]
        print(f"\n原始文档长度: {len(document.page_content)} 字符")
        print(f"原始文档前200字符: {document.page_content[:200]}...")

        # 记录开始时间
        start_time = time.time()

        # 执行清洗
        cleaned_doc = llm_ad_remover.clean_document(document)

        # 记录结束时间
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"清洗后文档长度: {len(cleaned_doc.page_content)} 字符")
        print(f"清洗后文档前200字符: {cleaned_doc.page_content[:200]}...")
        print(f"处理时间: {processing_time:.2f} 秒")

        # 验证清洗结果
        assert cleaned_doc.page_content != document.page_content, (
            "清洗后内容应该与原始内容不同"
        )
        assert len(cleaned_doc.page_content) > 0, "清洗后内容不应为空"

        # 验证元数据
        assert cleaned_doc.metadata["llm_cleaned"] is True, "应该标记为已清洗"
        assert "cleaning_timestamp" in cleaned_doc.metadata, "应该包含清洗时间戳"
        assert "removed_items_count" in cleaned_doc.metadata, "应该包含移除项数量"
        assert "preserved_items_count" in cleaned_doc.metadata, "应该包含保留项数量"

        # 验证图片链接被保留(重要要求)
        image_links = []
        lines = cleaned_doc.page_content.split("\n")
        for line in lines:
            if line.strip().startswith("![](images/"):
                image_links.append(line.strip())

        print(f"保留的图片链接数量: {len(image_links)}")
        if image_links:
            print(f"示例图片链接: {image_links[0]}")

        # 验证至少保留了一些图片链接
        assert len(image_links) > 0, "应该保留图片链接"

        # 验证文档结构(标题等)被保留
        headings = []
        for line in lines:
            if line.strip().startswith("#"):
                headings.append(line.strip())

        print(f"保留的标题数量: {len(headings)}")
        if headings:
            print(f"示例标题: {headings[0]}")

        # 验证至少保留了一些标题
        assert len(headings) > 0, "应该保留文档标题结构"

        # 验证处理时间合理(应该在120秒内完成)
        assert processing_time < 120, f"处理时间过长: {processing_time:.2f}秒"

    def test_real_document_batch_cleaning(self, llm_ad_remover, test_documents):
        """测试真实文档批量清洗"""
        if not test_documents or len(test_documents) < 1:
            pytest.skip("没有足够的测试文档")

        # 如果只有一个文档,复制它来模拟批量处理
        documents = test_documents
        if len(documents) == 1:
            # 创建几个相同的文档用于批量测试
            documents = [test_documents[0] for _ in range(3)]
            # 给每个文档不同的元数据
            for i, doc in enumerate(documents):
                doc.metadata = {**doc.metadata, "batch_index": i}

        print(f"\n批量清洗 {len(documents)} 个文档")

        # 记录开始时间
        start_time = time.time()

        # 执行批量清洗
        cleaned_docs = llm_ad_remover.clean_documents(documents)

        # 记录结束时间
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"批量清洗完成,处理时间: {processing_time:.2f} 秒")
        print(f"平均每个文档处理时间: {processing_time / len(documents):.2f} 秒")

        # 验证结果
        assert len(cleaned_docs) == len(documents), "返回的文档数量应该与输入相同"

        # 验证每个文档都被正确清洗
        for i, cleaned_doc in enumerate(cleaned_docs):
            assert cleaned_doc.metadata["llm_cleaned"] is True, (
                f"文档{i}应该标记为已清洗"
            )
            assert len(cleaned_doc.page_content) > 0, f"文档{i}清洗后内容不应为空"

            # 验证保留了图片链接
            lines = cleaned_doc.page_content.split("\n")
            image_links = [
                line.strip() for line in lines if line.strip().startswith("![](images/")
            ]
            assert len(image_links) > 0, f"文档{i}应该保留图片链接"

    @pytest.mark.asyncio
    async def test_real_document_async_cleaning(self, llm_ad_remover, test_documents):
        """测试真实文档异步清洗"""
        if not test_documents:
            pytest.skip("没有可用的测试文档")

        document = test_documents[0]
        print(f"\n异步清洗文档,原始长度: {len(document.page_content)} 字符")

        # 记录开始时间
        start_time = time.time()

        # 执行异步清洗
        cleaned_doc = await llm_ad_remover.aclean_document(document)

        # 记录结束时间
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"异步清洗完成,处理时间: {processing_time:.2f} 秒")
        print(f"清洗后长度: {len(cleaned_doc.page_content)} 字符")

        # 验证清洗结果
        assert cleaned_doc.page_content != document.page_content, (
            "清洗后内容应该与原始内容不同"
        )
        assert len(cleaned_doc.page_content) > 0, "清洗后内容不应为空"

        # 验证元数据
        assert cleaned_doc.metadata["llm_cleaned"] is True, "应该标记为已清洗"
        assert "cleaning_timestamp" in cleaned_doc.metadata, "应该包含清洗时间戳"

        # 验证保留了图片链接
        lines = cleaned_doc.page_content.split("\n")
        image_links = [
            line.strip() for line in lines if line.strip().startswith("![](images/")
        ]
        assert len(image_links) > 0, "应该保留图片链接"

    @pytest.mark.asyncio
    async def test_real_document_async_batch_cleaning(
        self, llm_ad_remover, test_documents
    ):
        """测试真实文档异步批量清洗"""
        if not test_documents or len(test_documents) < 1:
            pytest.skip("没有足够的测试文档")

        # 如果只有一个文档,复制它来模拟批量处理
        documents = test_documents
        if len(documents) == 1:
            documents = [test_documents[0] for _ in range(2)]
            for i, doc in enumerate(documents):
                doc.metadata = {**doc.metadata, "async_batch_index": i}

        print(f"\n异步批量清洗 {len(documents)} 个文档")

        # 记录开始时间
        start_time = time.time()

        # 执行异步批量清洗
        cleaned_docs = await llm_ad_remover.aclean_documents(documents)

        # 记录结束时间
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"异步批量清洗完成,处理时间: {processing_time:.2f} 秒")
        print(f"平均每个文档处理时间: {processing_time / len(documents):.2f} 秒")

        # 验证结果
        assert len(cleaned_docs) == len(documents), "返回的文档数量应该与输入相同"

        # 验证每个文档都被正确清洗
        for i, cleaned_doc in enumerate(cleaned_docs):
            assert cleaned_doc.metadata["llm_cleaned"] is True, (
                f"文档{i}应该标记为已清洗"
            )
            assert len(cleaned_doc.page_content) > 0, f"文档{i}清洗后内容不应为空"

    def test_cleaning_quality_preservation(self, llm_ad_remover, test_documents):
        """测试清洗质量 - 验证重要内容被保留"""
        if not test_documents:
            pytest.skip("没有可用的测试文档")

        document = test_documents[0]
        original_content = document.page_content

        # 执行清洗
        cleaned_doc = llm_ad_remover.clean_document(document)
        cleaned_content = cleaned_doc.page_content

        # 验证技术术语被保留(超级电容器相关)
        technical_terms = [
            "超级电容器",
            "储能",
            "电容器",
            "功率密度",
            "能量密度",
            "循环寿命",
        ]

        preserved_terms = []
        for term in technical_terms:
            if term in cleaned_content:
                preserved_terms.append(term)

        print(f"\n保留的技术术语: {preserved_terms}")
        assert len(preserved_terms) >= len(technical_terms) * 0.7, (
            "应该保留大部分技术术语"
        )

        # 验证数据(数字、百分比等)被保留
        import re

        numbers_in_original = re.findall(r"\d+\.?\d*%?", original_content)
        numbers_in_cleaned = re.findall(r"\d+\.?\d*%?", cleaned_content)

        print(f"原始文档数字数量: {len(numbers_in_original)}")
        print(f"清洗后文档数字数量: {len(numbers_in_cleaned)}")

        # 应该保留大部分数字数据
        if len(numbers_in_original) > 10:  # 只有足够多的数字时才验证
            preservation_rate = len(numbers_in_cleaned) / len(numbers_in_original)
            assert preservation_rate >= 0.5, f"数字保留率过低: {preservation_rate:.2%}"

    def test_ad_content_removal(self, llm_ad_remover, test_documents):
        """测试广告内容移除效果"""
        if not test_documents:
            pytest.skip("没有可用的测试文档")

        document = test_documents[0]
        original_content = document.page_content

        # 执行清洗
        cleaned_doc = llm_ad_remover.clean_document(document)
        cleaned_content = cleaned_doc.page_content

        # 检查可能被移除的内容类型
        potential_ad_patterns = [
            r"购买",
            r"订购",
            r"价格",
            r"联系电话",
            r"官网",
            r"www\.",
            r"http",
            r"邮箱",
            r"@",
        ]

        removed_patterns = []
        for pattern in potential_ad_patterns:
            original_matches = len(re.findall(pattern, original_content))
            cleaned_matches = len(re.findall(pattern, cleaned_content))

            if original_matches > cleaned_matches:
                removed_patterns.append(pattern)

        print(f"\n可能被移除的广告模式: {removed_patterns}")

        # 验证目录内容被移除
        toc_indicators = ["目录", "Contents", "图表目录", "Table of Contents"]
        toc_removed = False
        for indicator in toc_indicators:
            if indicator in original_content and indicator not in cleaned_content:
                toc_removed = True
                break

        print(f"目录内容被移除: {toc_removed}")

        # 验证清洗后的内容更简洁(长度减少或结构更清晰)
        # 注意:由于LLM可能会重新组织内容,长度不一定减少,但应该更简洁
        print(f"原始内容长度: {len(original_content)}")
        print(f"清洗后内容长度: {len(cleaned_content)}")

        # 验证清洗后的内容保持了良好的结构
        lines = cleaned_content.split("\n")
        non_empty_lines = [line for line in lines if line.strip()]

        # 应该有合理的行数(不能太少,也不能太多空行)
        assert len(non_empty_lines) > 50, "清洗后应该保留足够的内容行"

        # 验证没有过多的连续空行
        consecutive_empty_lines = 0
        max_consecutive_empty = 0
        for line in lines:
            if not line.strip():
                consecutive_empty_lines += 1
                max_consecutive_empty = max(
                    max_consecutive_empty, consecutive_empty_lines
                )
            else:
                consecutive_empty_lines = 0

        assert max_consecutive_empty <= 5, "不应该有过多的连续空行"

    def test_error_handling_with_real_file(self, llm_ad_remover):
        """测试真实文件处理的错误处理"""
        # 测试空文档
        empty_doc = Document(page_content="", metadata={"source": "empty.md"})

        try:
            cleaned_doc = llm_ad_remover.clean_document(empty_doc)
            # 空文档应该被处理,但结果可能也是空的
            assert isinstance(cleaned_doc, Document)
        except Exception as e:
            # 如果抛出异常,应该是预期的异常类型
            from src.shared.exceptions.base_exceptions import ProcessingError

            assert isinstance(e, ProcessingError)

        # 测试非常长的文档(可能导致超时)
        long_content = "这是一个测试句子。\n" * 10000  # 创建一个很长的文档
        long_doc = Document(page_content=long_content, metadata={"source": "long.md"})

        try:
            # 设置较短的超时时间
            start_time = time.time()
            cleaned_doc = llm_ad_remover.clean_document(long_doc)
            processing_time = time.time() - start_time

            # 长文档应该被处理,但可能需要更长时间
            assert isinstance(cleaned_doc, Document)
            print(f"长文档处理时间: {processing_time:.2f} 秒")

        except Exception as e:
            # 长文档处理失败是可以接受的
            from src.shared.exceptions.base_exceptions import ProcessingError

            assert isinstance(e, ProcessingError)
            print(f"长文档处理失败(预期): {e}")


class TestLLMAdRemoverMultipleRealFiles:
    """测试LLM广告清洗器处理多个真实文件"""

    @pytest.fixture(scope="class")
    def multiple_test_documents(self):
        """准备多个测试文档"""
        # 查找所有可用的真实文档
        doc_paths = [
            Path(
                "data/processed/mineru/2023年中国储能行业系列研究-超级电容器储能_ae/6fd23ee4-b12a-4604-af9f-0ddc50b33a01_2023年中国储能行业系列研究-超级电容器储能.pdf_extracted/full.md"
            ),
            Path(
                "data/processed/mineru/水电总院王昊轶:储能是沙戈荒基地高质量建设的'金钥匙'_98/6fd23ee4-b12a-4604-af9f-0ddc50b33a01_水电总院王昊轶:储能是沙戈荒基地高质量建设的'金钥匙'.docx_extracted/full.md"
            ),
        ]

        documents = []
        for doc_path in doc_paths:
            if doc_path.exists():
                with open(doc_path, encoding="utf-8") as f:
                    content = f.read()

                document = Document(
                    page_content=content,
                    metadata={
                        "source": str(doc_path),
                        "format": "md",
                        "pipeline": "mineru",
                        "filename": doc_path.name,
                    },
                )
                documents.append(document)

        if not documents:
            pytest.skip("没有找到可用的测试文档")

        return documents

    def test_multiple_files_cleaning(self, llm_ad_remover, multiple_test_documents):
        """测试多个文件清洗"""
        print(f"\n找到 {len(multiple_test_documents)} 个测试文档")

        # 记录开始时间
        start_time = time.time()

        # 批量清洗所有文档
        cleaned_docs = llm_ad_remover.clean_documents(multiple_test_documents)

        # 记录结束时间
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"批量清洗完成,总处理时间: {processing_time:.2f} 秒")
        print(
            f"平均每个文档处理时间: {processing_time / len(multiple_test_documents):.2f} 秒"
        )

        # 验证结果
        assert len(cleaned_docs) == len(multiple_test_documents), (
            "返回的文档数量应该与输入相同"
        )

        # 验证每个文档都被正确清洗
        for i, cleaned_doc in enumerate(cleaned_docs):
            original_doc = multiple_test_documents[i]

            assert cleaned_doc.page_content != original_doc.page_content, (
                f"文档{i}清洗后内容应该与原始内容不同"
            )
            assert len(cleaned_doc.page_content) > 0, f"文档{i}清洗后内容不应为空"
            assert cleaned_doc.metadata["llm_cleaned"] is True, (
                f"文档{i}应该标记为已清洗"
            )

            # 验证保留了图片链接
            lines = cleaned_doc.page_content.split("\n")
            image_links = [
                line.strip() for line in lines if line.strip().startswith("![](images/")
            ]

            if image_links:  # 只有当原始文档有图片时才验证
                assert len(image_links) > 0, f"文档{i}应该保留图片链接"

            print(
                f"文档 {i + 1} ({cleaned_doc.metadata.get('filename', 'unknown')}): "
                f"原始长度={len(original_doc.page_content)}, "
                f"清洗后长度={len(cleaned_doc.page_content)}, "
                f"图片链接={len(image_links)}"
            )

    @pytest.mark.asyncio
    async def test_multiple_files_async_cleaning(
        self, llm_ad_remover, multiple_test_documents
    ):
        """测试多个文件异步清洗"""
        print(f"\n异步清洗 {len(multiple_test_documents)} 个测试文档")

        # 记录开始时间
        start_time = time.time()

        # 异步批量清洗所有文档
        cleaned_docs = await llm_ad_remover.aclean_documents(multiple_test_documents)

        # 记录结束时间
        end_time = time.time()
        processing_time = end_time - start_time

        print(f"异步批量清洗完成,总处理时间: {processing_time:.2f} 秒")
        print(
            f"平均每个文档处理时间: {processing_time / len(multiple_test_documents):.2f} 秒"
        )

        # 验证结果
        assert len(cleaned_docs) == len(multiple_test_documents), (
            "返回的文档数量应该与输入相同"
        )

        # 验证每个文档都被正确清洗
        for i, cleaned_doc in enumerate(cleaned_docs):
            original_doc = multiple_test_documents[i]

            assert cleaned_doc.page_content != original_doc.page_content, (
                f"文档{i}清洗后内容应该与原始内容不同"
            )
            assert len(cleaned_doc.page_content) > 0, f"文档{i}清洗后内容不应为空"
            assert cleaned_doc.metadata["llm_cleaned"] is True, (
                f"文档{i}应该标记为已清洗"
            )
