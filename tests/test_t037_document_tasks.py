"""
T037 文档预处理异步任务测试

测试文档预处理异步任务的功能,包括:
- 单个文档处理
- 批量文档处理
- 图表转换功能
- 错误处理和重试机制
"""

import asyncio
import tempfile
from pathlib import Path

from src.infrastructure.tasks.document_tasks import (
    create_batch_document_processing_task,
    create_document_processing_task,
)
from src.infrastructure.tasks.tasks import TaskContext, TaskStatus
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


async def test_document_processing_task():
    """测试文档预处理任务"""
    logger.info("开始测试文档预处理任务")

    # 创建临时测试文件
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # 创建测试文档路径
        test_file = temp_path / "test_document.txt"
        test_file.write_text("# 测试文档\n\n这是一个测试文档内容。")

        # 创建任务实例
        task = create_document_processing_task(
            use_agent=True,
            enable_chart_conversion=False,  # 测试时不启用图表转换
        )

        # 创建任务上下文
        ctx = TaskContext(
            task_id="test_doc_processing",
            retry_count=0,
            max_retries=3,
            timeout=3600,
            metadata={"test_mode": True},
        )

        try:
            # 执行任务
            result = await task.execute(ctx, str(test_file))

            # 验证结果
            assert result["status"] == TaskStatus.COMPLETED, (
                f"任务状态应为COMPLETED,实际为: {result['status']}"
            )
            assert result["file_count"] == 1, (
                f"文件数量应为1,实际为: {result['file_count']}"
            )
            assert "error" not in result, f"结果不应包含错误,实际: {result}"

            logger.info("文档预处理任务测试通过")
            return True

        except Exception as e:
            logger.error(f"文档预处理任务测试失败: {e}")
            return False


async def test_batch_document_processing_task():
    """测试批量文档预处理任务"""
    logger.info("开始测试批量文档预处理任务")

    # 创建临时测试文件
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # 创建多个测试文档
        test_files = []
        for i in range(3):
            test_file = temp_path / f"test_document_{i}.txt"
            test_file.write_text(f"# 测试文档 {i}\n\n这是第{i}个测试文档内容。")
            test_files.append(str(test_file))

        # 创建批量任务实例
        task = create_batch_document_processing_task(
            batch_size=2,
            enable_chart_conversion=False,  # 测试时不启用图表转换
        )

        # 创建任务上下文
        ctx = TaskContext(
            task_id="test_batch_doc_processing",
            retry_count=0,
            max_retries=2,
            timeout=7200,
            metadata={"test_mode": True},
        )

        try:
            # 执行批量任务
            result = await task.execute(ctx, test_files)

            # 验证结果
            assert result["status"] == TaskStatus.COMPLETED, (
                f"批量任务状态应为COMPLETED,实际为: {result['status']}"
            )
            assert result["total_files"] == 3, (
                f"总文件数应为3,实际为: {result['total_files']}"
            )
            assert result["batch_count"] == 2, (
                f"批次数应为2,实际为: {result['batch_count']}"
            )
            assert len(result["processed_files"]) >= 2, (
                f"成功处理文件数应>=2,实际为: {len(result['processed_files'])}"
            )
            assert "error" not in result, f"结果不应包含错误,实际: {result}"

            logger.info("批量文档预处理任务测试通过")
            return True

        except Exception as e:
            logger.error(f"批量文档预处理任务测试失败: {e}")
            return False


async def test_chart_conversion_feature():
    """测试图表转换功能"""
    logger.info("开始测试图表转换功能")

    # 注意:这个测试需要真实的文档目录结构,可能会失败
    # 主要测试任务是否能正确处理图表转换相关的参数

    # 创建任务实例(启用图表转换)
    task = create_document_processing_task(
        use_agent=True,
        enable_chart_conversion=True,
    )

    # 创建任务上下文
    ctx = TaskContext(
        task_id="test_chart_conversion",
        retry_count=0,
        max_retries=3,
        timeout=3600,
        metadata={"test_mode": True},
    )

    try:
        # 使用一个不存在的文件路径(避免实际处理)
        result = await task.execute(ctx, "/nonexistent/file.pdf")

        # 验证任务能处理图表转换相关配置
        assert result["enable_chart_conversion"], (
            f"图表转换应启用,实际为: {result['enable_chart_conversion']}"
        )

        logger.info("图表转换功能测试通过")
        return True

    except Exception as e:
        logger.error(f"图表转换功能测试失败: {e}")
        return False


async def test_error_handling():
    """测试错误处理机制"""
    logger.info("开始测试错误处理机制")

    # 创建任务实例
    task = create_document_processing_task(
        use_agent=True,
        enable_chart_conversion=False,
    )

    # 创建任务上下文
    ctx = TaskContext(
        task_id="test_error_handling",
        retry_count=0,
        max_retries=1,  # 减少重试次数以快速测试
        timeout=60,  # 减少超时时间
        metadata={"test_mode": True},
    )

    try:
        # 使用无效的文件路径
        result = await task.execute(ctx, "/invalid/file/path.txt")

        # 验证错误处理
        assert result["status"] == TaskStatus.FAILED, (
            f"任务状态应为FAILED,实际为: {result['status']}"
        )
        assert "error" in result, f"结果应包含错误信息,实际: {result}"

        logger.info("错误处理机制测试通过")
        return True

    except Exception as e:
        logger.error(f"错误处理机制测试失败: {e}")
        return False


async def main():
    """主测试函数"""
    logger.info("开始T037文档预处理异步任务测试")

    tests = [
        ("文档预处理任务", test_document_processing_task),
        ("批量文档预处理任务", test_batch_document_processing_task),
        ("图表转换功能", test_chart_conversion_feature),
        ("错误处理机制", test_error_handling),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"执行测试: {test_name}")
        try:
            if await test_func():
                passed += 1
                logger.info(f"✅ {test_name} - 通过")
            else:
                logger.error(f"❌ {test_name} - 失败")
        except Exception as e:
            logger.error(f"❌ {test_name} - 异常: {e}")

    logger.info(f"测试完成: {passed}/{total} 通过")

    if passed == total:
        logger.info("🎉 所有测试通过!T037任务实现正确")
        return True
    else:
        logger.error(f"💥 部分测试失败: {passed}/{total}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
