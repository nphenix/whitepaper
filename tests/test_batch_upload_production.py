#!/usr/bin/env python3
"""
MinerU 批量上传测试脚本(正式环境)

使用正式环境的路径配置进行测试:
- 上传文件路径: data/source/uploads/
- 处理结果路径: data/processed/mineru/{hash前2位}/
- 缓存路径: data/cache/mineru/
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.preprocessing.loaders.mineru_adapter import MinerUAdapter
from src.shared.config.settings import get_config
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


def test_batch_upload_production():
    """测试批量文件上传(正式环境)"""
    logger.info("=" * 60)
    logger.info("开始批量上传测试(正式环境)")
    logger.info("=" * 60)

    # 获取配置
    config = get_config()
    data_dir = Path(config.data_dir)

    # 正式环境:使用 data/source/uploads/
    source_uploads_dir = data_dir / "source" / "uploads"

    # 如果正式环境目录不存在,检查是否有测试文件可以复制
    if not source_uploads_dir.exists():
        logger.warning(f"⚠️ 正式环境上传目录不存在: {source_uploads_dir}")

        # 检查测试目录是否有文件
        test_dir = data_dir / "temp" / "uploads"
        if test_dir.exists():
            test_files = list(test_dir.glob("*.pdf")) + list(test_dir.glob("*.docx"))
            test_files = [f for f in test_files if f.is_file()]

            if test_files:
                logger.info(f"📋 在测试目录找到 {len(test_files)} 个文件")
                logger.info("   是否要复制到正式环境目录?")
                logger.info(f"   测试目录: {test_dir}")
                logger.info(f"   正式目录: {source_uploads_dir}")

                # 创建正式环境目录
                source_uploads_dir.mkdir(parents=True, exist_ok=True)

                # 复制文件(可选,这里自动复制)
                import shutil

                for test_file in test_files:
                    dest_file = source_uploads_dir / test_file.name
                    if not dest_file.exists():
                        logger.info(f"   复制文件: {test_file.name}")
                        shutil.copy2(test_file, dest_file)
                    else:
                        logger.info(f"   文件已存在,跳过: {test_file.name}")
            else:
                logger.error(f"❌ 测试目录中没有文件: {test_dir}")
                return False
        else:
            logger.error(f"❌ 测试目录也不存在: {test_dir}")
            logger.error("   请先准备测试文件")
            return False

    # 使用正式环境目录
    test_dir = source_uploads_dir

    if not test_dir.exists():
        logger.error(f"❌ 测试目录不存在: {test_dir}")
        return False

    # 列出目录中的文件
    files = list(test_dir.glob("*.pdf")) + list(test_dir.glob("*.docx"))
    files = [f for f in files if f.is_file() and not f.name.startswith(".")]

    logger.info(f"📁 正式环境上传目录: {test_dir}")
    logger.info(f"📋 找到 {len(files)} 个文件:")
    for f in files:
        logger.info(f"   - {f.name} ({f.stat().st_size / 1024 / 1024:.2f} MB)")

    if len(files) == 0:
        logger.warning("⚠️ 正式环境目录中没有文件")
        return False

    try:
        # 初始化适配器
        logger.info("\n🔧 初始化 MinerU 适配器...")
        adapter = MinerUAdapter()
        logger.info(f"   API URL: {adapter.base_url}")
        logger.info(f"   批量上传端点: {adapter.batch_urls_endpoint}")
        logger.info(f"   缓存目录: {adapter.cache_dir}")
        logger.info(f"   处理结果目录: {adapter.processed_dir}")
        logger.info(f"   源文件上传目录: {adapter.source_uploads_dir}")

        # 健康检查
        logger.info("\n🏥 执行健康检查...")
        is_healthy = adapter.health_check()
        if not is_healthy:
            logger.error("❌ API健康检查失败")
            return False
        logger.info("✅ API健康检查通过")

        # 执行批量上传
        logger.info(f"\n🚀 开始批量处理目录(正式环境): {test_dir}")
        logger.info("-" * 60)

        batch_results = adapter.extract_batch(str(test_dir))

        if batch_results:
            logger.info("\n" + "=" * 60)
            logger.info("✅ 批量处理成功!")
            logger.info("=" * 60)
            logger.info(f"处理了 {len(batch_results)} 个文件:")

            total_docs = 0
            for file_path, documents in batch_results.items():
                file_name = Path(file_path).name
                doc_count = len(documents)
                total_docs += doc_count
                logger.info(f"   📄 {file_name}: {doc_count} 个文档块")

                # 显示处理结果路径
                if documents:
                    first_doc = documents[0]
                    if (
                        hasattr(first_doc, "metadata")
                        and "extracted_dir" in first_doc.metadata
                    ):
                        extracted_dir = first_doc.metadata["extracted_dir"]
                        logger.info(f"      📂 处理结果: {extracted_dir}")

            logger.info(
                f"\n📊 总计: {len(batch_results)} 个文件, {total_docs} 个文档块"
            )

            # 显示存储路径信息
            logger.info("\n📁 存储路径信息:")
            logger.info(f"   缓存目录(临时): {adapter.cache_dir}")
            logger.info(f"   处理结果目录(正式): {adapter.processed_dir}")
            logger.info(f"   源文件目录: {adapter.source_uploads_dir}")

            return True
        else:
            logger.warning("⚠️ 批量处理返回空结果")
            return False

    except Exception as e:
        logger.error(f"\n❌ 批量处理失败: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = test_batch_upload_production()

    if success:
        logger.info("\n" + "=" * 60)
        logger.info("✅ 正式环境测试通过")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("\n" + "=" * 60)
        logger.error("❌ 正式环境测试失败")
        logger.error("=" * 60)
        sys.exit(1)
