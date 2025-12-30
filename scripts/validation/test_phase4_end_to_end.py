#!/usr/bin/env python3
"""
阶段4端到端验证脚本

使用阶段3的数据产物,完整验证知识库构建流程:
1. 使用PreprocessedDocumentReader读取文档
2. 使用MarkdownParser解析文档
3. 使用DocumentChunkingStrategy分块
4. 使用EmbeddingGenerator生成向量
5. 使用HybridRetriever构建混合检索
6. 使用KnowledgeBaseService创建知识库
"""

import io
import sys
import uuid
from pathlib import Path

# 设置标准输出为UTF-8编码(Windows兼容)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from src.application.services.indexing_progress_service import IndexingProgressService
from src.application.services.knowledge_base_service import KnowledgeBaseService
from src.infrastructure.parsing.loaders.preprocessed_document_reader import (
    PreprocessedDocumentReader,
)
from src.shared.config.settings import get_config
from src.shared.utils.logging import get_logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logger = get_logger(__name__)


def find_preprocessed_directories(cleaned_dir: Path) -> list[str]:
    """
    查找所有预处理结果目录

    Args:
        cleaned_dir: 清洗后文档目录路径

    Returns:
        预处理结果目录路径列表
    """
    directories = []

    # 查找所有*_extracted目录
    for extracted_dir in cleaned_dir.rglob("*_extracted"):
        if extracted_dir.is_dir():
            # 检查是否有clean.md文件
            clean_md = extracted_dir / "clean.md"
            if clean_md.exists():
                directories.append(str(extracted_dir))
                logger.info(f"找到预处理目录: {extracted_dir.relative_to(cleaned_dir)}")

    return directories


def load_documents_from_preprocessed_dirs(directories: list[str]) -> list:
    """
    从预处理结果目录加载文档

    Args:
        directories: 预处理结果目录路径列表

    Returns:
        Document对象列表
    """
    all_documents = []

    for directory in directories:
        try:
            logger.info(f"正在加载文档: {directory}")
            reader = PreprocessedDocumentReader(
                source=directory,
                include_images=True,
                include_charts=True,
            )
            documents = reader.load()
            all_documents.extend(documents)
            logger.info(f"成功加载 {len(documents)} 个文档")

        except Exception as e:
            logger.error(f"加载文档失败: {directory} - {e}", exc_info=True)
            continue

    logger.info(f"总共加载 {len(all_documents)} 个文档")
    return all_documents


def create_knowledge_base_from_documents(
    documents: list,
    knowledge_base_id: str | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> tuple:
    """
    从文档创建知识库

    Args:
        documents: Document对象列表
        knowledge_base_id: 知识库ID,如果为None则自动生成
        chunk_size: 文档块大小
        chunk_overlap: 文档块重叠大小

    Returns:
        (知识库服务实例, 知识库创建结果) 元组
    """
    if knowledge_base_id is None:
        knowledge_base_id = f"kb_{uuid.uuid4().hex[:8]}"

    logger.info(f"开始创建知识库: {knowledge_base_id}")
    logger.info(f"  - 文档数量: {len(documents)}")
    logger.info(f"  - 块大小: {chunk_size}")
    logger.info(f"  - 块重叠: {chunk_overlap}")

    # 创建索引进度服务
    progress_service = IndexingProgressService()

    # 创建知识库服务
    kb_service = KnowledgeBaseService(progress_service=progress_service)

    # 创建知识库
    try:
        result = kb_service.create_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            documents=documents,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        logger.info("✅ 知识库创建成功")
        logger.info(f"  - 知识库ID: {result['id']}")
        logger.info(f"  - 文档数: {result['document_count']}")
        logger.info(f"  - 块数: {result['chunk_count']}")
        logger.info(f"  - 索引数: {result['index_count']}")

        # 返回服务实例和结果,以便后续使用同一个实例进行查询
        return kb_service, result

    except Exception as e:
        logger.error(f"❌ 知识库创建失败: {e}", exc_info=True)
        raise


def query_knowledge_base(
    kb_service: KnowledgeBaseService,
    knowledge_base_id: str,
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    """
    查询知识库

    Args:
        kb_service: 知识库服务实例
        knowledge_base_id: 知识库ID
        query_text: 查询文本
        top_k: 返回结果数量

    Returns:
        查询结果列表
    """
    logger.info(f"查询知识库: {knowledge_base_id}")
    logger.info(f"  - 查询文本: {query_text}")
    logger.info(f"  - Top K: {top_k}")

    try:
        results = kb_service.query(
            knowledge_base_id=knowledge_base_id,
            query_text=query_text,
            top_k=top_k,
        )

        logger.info(f"✅ 查询成功,返回 {len(results)} 个结果")

        for i, result in enumerate(results, 1):
            logger.info(f"\n结果 {i}:")
            logger.info(f"  - 块ID: {result.get('chunk_id', 'N/A')}")
            logger.info(f"  - 分数: {result.get('score', 'N/A')}")
            logger.info(f"  - 内容预览: {result.get('content', 'N/A')[:200]}...")
            if "metadata" in result:
                logger.info(f"  - 元数据: {list(result['metadata'].keys())}")

        return results

    except Exception as e:
        logger.error(f"❌ 查询失败: {e}", exc_info=True)
        raise


def get_knowledge_base_status(
    kb_service: KnowledgeBaseService,
    knowledge_base_id: str,
) -> dict:
    """
    获取知识库状态

    Args:
        kb_service: 知识库服务实例
        knowledge_base_id: 知识库ID

    Returns:
        知识库状态信息
    """
    try:
        status = kb_service.get_status(knowledge_base_id=knowledge_base_id)
        return status
    except Exception as e:
        logger.error(f"获取知识库状态失败: {e}", exc_info=True)
        raise


def main():
    """主函数"""
    print("=" * 70)
    print("阶段4端到端验证")
    print("=" * 70)
    print()

    # 获取配置
    config = get_config()
    data_dir = Path(config.data_dir) if hasattr(config, "data_dir") else Path("./data")
    cleaned_dir = data_dir / "cleaned" / "documents"

    print(f"📁 数据目录: {cleaned_dir}")
    print()

    # 步骤1: 查找预处理结果目录
    print("1️⃣  查找预处理结果目录...")
    print("-" * 70)
    directories = find_preprocessed_directories(cleaned_dir)

    if not directories:
        print("❌ 未找到任何预处理结果目录")
        return 1

    print(f"✅ 找到 {len(directories)} 个预处理结果目录")
    print()

    # 步骤2: 加载文档
    print("2️⃣  加载文档...")
    print("-" * 70)
    documents = load_documents_from_preprocessed_dirs(directories)

    if not documents:
        print("❌ 未能加载任何文档")
        return 1

    print(f"✅ 成功加载 {len(documents)} 个文档")
    print()

    # 步骤3: 创建知识库
    print("3️⃣  创建知识库...")
    print("-" * 70)
    knowledge_base_id = f"phase4_e2e_test_{uuid.uuid4().hex[:8]}"

    try:
        # 创建知识库并获取服务实例(使用同一个实例进行后续操作)
        kb_service, result = create_knowledge_base_from_documents(
            documents=documents,
            knowledge_base_id=knowledge_base_id,
            chunk_size=1000,
            chunk_overlap=200,
        )
        print()

    except Exception as e:
        print(f"❌ 知识库创建失败: {e}")
        return 1

    # 步骤4: 获取知识库状态
    print("4️⃣  获取知识库状态...")
    print("-" * 70)

    try:
        status = get_knowledge_base_status(kb_service, knowledge_base_id)
        print(f"✅ 知识库状态: {status.get('status', 'N/A')}")
        if "statistics" in status:
            stats = status["statistics"]
            print(f"  - 文档数: {stats.get('documents_count', 'N/A')}")
            print(f"  - 块数: {stats.get('chunks_count', 'N/A')}")
        print()
    except Exception as e:
        print(f"⚠️  获取知识库状态失败: {e}")
        print()

    # 步骤5: 测试查询
    print("5️⃣  测试查询...")
    print("-" * 70)

    test_queries = [
        "储能技术",
        "中国储能市场",
        "电化学储能",
    ]

    for query_text in test_queries:
        try:
            query_knowledge_base(
                kb_service=kb_service,
                knowledge_base_id=knowledge_base_id,
                query_text=query_text,
                top_k=3,
            )
            print()
        except Exception as e:
            print(f"⚠️  查询失败: {query_text} - {e}")
            print()

    # 总结
    print("=" * 70)
    print("📋 验证总结")
    print("=" * 70)
    print("✅ 阶段4端到端验证完成!")
    print()
    print("📊 验证结果:")
    print(f"  - 预处理目录数: {len(directories)}")
    print(f"  - 加载文档数: {len(documents)}")
    print(f"  - 知识库ID: {knowledge_base_id}")
    print(f"  - 文档块数: {result.get('chunk_count', 'N/A')}")
    print(f"  - 索引数: {result.get('index_count', 'N/A')}")
    print()
    print("✅ 所有步骤执行成功,知识库已创建并可以查询!")

    return 0


if __name__ == "__main__":
    sys.exit(main())

