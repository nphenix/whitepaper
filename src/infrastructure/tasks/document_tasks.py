"""
文档预处理异步任务

基于Arq任务队列的文档预处理异步任务,支持大文件处理和批量处理。
调用T031预处理协调器或T032文档预处理Agent执行实际处理。
支持T031B图表转JSON功能(可选)。

生成命令: /speckit.implement T037
生成时间: 2025-12-17
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.application.agents.document_preprocessor import DocumentPreprocessorAgent
from src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter import (
    LLMChartToJsonConverter,
)
from src.infrastructure.preprocessing.preprocessor import DocumentPreprocessor
from src.infrastructure.tasks.settings import TaskSettings, get_task_settings
from src.infrastructure.tasks.tasks import BaseTask, TaskContext, TaskStatus
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.config.settings import get_config
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentProcessingTask(BaseTask):
    """文档预处理异步任务

    封装文档预处理流程为异步任务,支持大文件处理和批量处理。
    使用Arq任务队列,支持任务状态跟踪和错误重试。
    调用T031预处理协调器或T032文档预处理Agent执行实际处理。
    支持T031B图表转JSON功能(可选)。

    功能特性:
    - 支持单个文档和批量文档处理
    - 可选启用图表转JSON功能
    - 任务进度报告和状态跟踪
    - 错误重试机制
    - 完善的日志记录
    - 集成任务监控
    """

    name = "document_processing"
    description = "文档预处理异步任务,支持大文件处理和批量处理"
    timeout = 3600  # 1小时超时
    max_retries = 3

    def __init__(
        self,
        config: TaskSettings | None = None,
        llm_service: LLMService | None = None,
        use_agent: bool = True,
        enable_chart_conversion: bool = True,
        **kwargs,
    ):
        """初始化文档预处理任务

        Args:
            config: 任务队列配置,如果为None则使用默认配置
            llm_service: LLM服务实例,如果为None则使用全局实例
            use_agent: 是否使用T032 Agent(True)或T031协调器(False)
            enable_chart_conversion: 是否启用图表转JSON功能,默认为True
            **kwargs: 其他参数
        """
        super().__init__(**kwargs)
        self.config = config or get_task_settings()
        self.llm_service = llm_service or get_llm_service()
        self.use_agent = use_agent
        self.enable_chart_conversion = enable_chart_conversion

        # 初始化处理器
        if self.use_agent:
            # 使用T032文档预处理Agent
            from src.application.agent_base import AgentConfig

            # 从全局配置获取LLM参数
            global_config = get_config()
            llm_config = global_config.llm_config or {}

            agent_config = AgentConfig(
                agent_id="document_preprocessor_task",
                agent_name="Document Preprocessor Task",
                description="文档预处理异步任务",
                model=llm_config.get("model_name", "gpt-4"),
                temperature=llm_config.get("temperature", 0.7),
                max_tokens=llm_config.get("max_tokens", 4096),
                timeout=self.config.worker_timeout,
                max_retries=self.config.retry.max_retries,
            )

            self.processor = DocumentPreprocessorAgent(
                config=agent_config,
                llm_service=self.llm_service,
                enable_chart_conversion=self.enable_chart_conversion,
            )
            logger.info("使用DocumentPreprocessorAgent进行文档处理")
        else:
            # 使用T031预处理协调器
            self.processor = DocumentPreprocessor(llm_service=self.llm_service)
            logger.info("使用DocumentPreprocessor进行文档处理")

        # 初始化图表转换器(如果启用)
        self.chart_converter = None
        if self.enable_chart_conversion:
            try:
                self.chart_converter = LLMChartToJsonConverter(
                    llm_service=self.llm_service
                )
                logger.info("图表转JSON转换器已启用")
            except Exception as e:
                logger.error(f"初始化图表转JSON转换器失败: {e}")
                # 图表转换器初始化失败不影响主要功能
                self.chart_converter = None

    async def execute(
        self, ctx: TaskContext, file_paths: str | list[str], **kwargs
    ) -> dict[str, Any]:
        """执行文档预处理任务

        Args:
            ctx: 任务上下文
            file_paths: 文档路径(单个路径或路径列表)
            **kwargs: 其他参数

        Returns:
            任务执行结果字典
        """
        start_time = time.time()

        # 标准化输入为列表
        if isinstance(file_paths, str):
            file_paths = [file_paths]

        logger.info(f"开始文档预处理任务: {len(file_paths)} 个文件")
        logger.info(
            f"使用Agent: {self.use_agent}, 图表转换: {self.enable_chart_conversion}"
        )

        try:
            # 验证输入文件
            valid_files = await self._validate_files(file_paths)
            if not valid_files:
                msg = "没有有效的文件需要处理"
                raise ProcessingError(msg)

            # 执行文档预处理
            if self.use_agent:
                # 使用T032 Agent处理
                documents = await self._process_with_agent(valid_files)
            else:
                # 使用T031协调器处理
                documents = await self._process_with_preprocessor(valid_files)

            # 执行图表转换(如果启用)
            chart_conversion_result = None
            if self.enable_chart_conversion and self.chart_converter:
                chart_conversion_result = await self._execute_chart_conversion(
                    valid_files
                )

            # 构建结果
            processing_time = time.time() - start_time

            result = {
                "status": TaskStatus.COMPLETED,
                "task_id": ctx.task_id,
                "file_count": len(valid_files),
                "processed_files": list(valid_files),
                "documents_count": len(documents),
                "processing_time": processing_time,
                "use_agent": self.use_agent,
                "enable_chart_conversion": self.enable_chart_conversion,
                "chart_conversion": chart_conversion_result,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"文档预处理任务完成: {len(valid_files)} 个文件, "
                f"生成 {len(documents)} 个文档, "
                f"耗时 {processing_time:.2f} 秒"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"文档预处理任务失败: {e!s}"
            logger.error(error_msg, exc_info=True)

            result = {
                "status": TaskStatus.FAILED,
                "task_id": ctx.task_id,
                "error": str(e),
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat(),
            }

            return result

    async def _validate_files(self, file_paths: list[str]) -> list[str]:
        """验证输入文件

        Args:
            file_paths: 文件路径列表

        Returns:
            有效的文件路径列表
        """
        valid_files = []

        for file_path in file_paths:
            path = Path(file_path)

            # 检查文件是否存在
            if not path.exists():
                logger.warning(f"文件不存在,跳过: {file_path}")
                continue

            # 检查是否为文件(不是目录)
            if not path.is_file():
                logger.warning(f"路径不是文件,跳过: {file_path}")
                continue

            # 检查文件大小(避免处理过大的文件)
            file_size = path.stat().st_size
            if file_size > 100 * 1024 * 1024:  # 100MB
                logger.warning(
                    f"文件过大,跳过: {file_path} ({file_size / 1024 / 1024:.1f} MB)"
                )
                continue

            valid_files.append(file_path)

        logger.info(f"文件验证完成: {len(valid_files)}/{len(file_paths)} 个有效文件")
        return valid_files

    async def _process_with_agent(self, file_paths: list[str]) -> list[Document]:
        """使用T032 Agent处理文档

        Args:
            file_paths: 文件路径列表

        Returns:
            处理后的Document列表
        """
        logger.info("使用DocumentPreprocessorAgent处理文档")
        documents = []

        for file_path in file_paths:
            try:
                # 使用Agent的load_and_process方法
                processed_docs = self.processor.load_and_process(file_path)
                documents.extend(processed_docs)

            except Exception as e:
                logger.error(f"Agent处理文档失败: {file_path}, 错误: {e}")
                # 继续处理其他文件,不中断整个任务
                continue

        return documents

    async def _process_with_preprocessor(self, file_paths: list[str]) -> list[Document]:
        """使用T031预处理协调器处理文档

        Args:
            file_paths: 文件路径列表

        Returns:
            处理后的Document列表
        """
        logger.info("使用DocumentPreprocessor处理文档")

        try:
            # 使用预处理协调器的异步批量处理方法
            documents = await self.processor.aprocess_documents(file_paths)
            return documents

        except Exception as e:
            logger.error(f"预处理协调器处理文档失败: {e}")
            # 降级到同步处理
            logger.info("降级到同步处理模式")
            return self.processor.process_documents(file_paths)

    async def _execute_chart_conversion(self, file_paths: list[str]) -> dict[str, Any]:
        """执行图表转换任务

        Args:
            file_paths: 文档路径列表

        Returns:
            图表转换结果统计
        """
        if not self.chart_converter:
            return {"enabled": False, "reason": "图表转换器未初始化"}

        logger.info("开始执行图表转换任务")
        start_time = time.time()

        try:
            # 查找所有已处理的文档目录
            processed_dirs = []

            # 查找data/cleaned/documents目录下的所有子目录
            cleaned_base_dir = Path("data/cleaned/documents")
            if cleaned_base_dir.exists():
                for doc_dir in cleaned_base_dir.iterdir():
                    if doc_dir.is_dir():
                        # 查找extracted目录
                        extracted_dirs = [
                            d
                            for d in doc_dir.iterdir()
                            if d.is_dir() and d.name.endswith("_extracted")
                        ]
                        processed_dirs.extend(extracted_dirs)

            if not processed_dirs:
                logger.warning("未找到已处理的文档目录,跳过图表转换")
                return {
                    "enabled": True,
                    "processed_directories": 0,
                    "total_images": 0,
                    "charts_found": 0,
                    "json_generated": 0,
                    "errors": 0,
                    "processing_time": time.time() - start_time,
                }

            # 处理每个目录
            total_images = 0
            total_charts_found = 0
            total_json_generated = 0
            total_errors = 0
            processed_directories = 0

            for extracted_dir in processed_dirs:
                try:
                    logger.info(f"处理图表转换目录: {extracted_dir}")

                    # 使用图表转换器处理目录
                    result = self.chart_converter.process_mineru_directory(
                        str(extracted_dir), create_datajson_dir=True
                    )

                    # 更新统计信息
                    stats = result.get("overall_statistics", {})
                    total_images += stats.get("total_images_processed", 0)
                    total_charts_found += stats.get("total_charts_found", 0)
                    total_json_generated += stats.get("total_json_files_generated", 0)
                    total_errors += stats.get("total_errors", 0)
                    processed_directories += 1

                except Exception as e:
                    logger.error(f"处理图表转换目录失败: {extracted_dir}, 错误: {e}")
                    total_errors += 1

            processing_time = time.time() - start_time

            result = {
                "enabled": True,
                "processed_directories": processed_directories,
                "total_images": total_images,
                "charts_found": total_charts_found,
                "json_generated": total_json_generated,
                "errors": total_errors,
                "processing_time": processing_time,
            }

            logger.info(
                f"图表转换完成: 处理 {processed_directories} 个目录, "
                f"总图像 {total_images} 个, "
                f"发现图表 {total_charts_found} 个, "
                f"生成JSON {total_json_generated} 个, "
                f"错误 {total_errors} 个, "
                f"耗时 {processing_time:.2f} 秒"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"图表转换任务失败: {e!s}"
            logger.error(error_msg, exc_info=True)

            return {
                "enabled": True,
                "error": str(e),
                "processing_time": processing_time,
            }


class BatchDocumentProcessingTask(BaseTask):
    """批量文档预处理异步任务

    专门用于批量处理大量文档的优化任务。
    支持分批处理和进度报告。
    """

    name = "batch_document_processing"
    description = "批量文档预处理异步任务,支持大量文档的分批处理"
    timeout = 7200  # 2小时超时
    max_retries = 2  # 批量任务重试次数较少

    def __init__(
        self,
        config: TaskSettings | None = None,
        llm_service: LLMService | None = None,
        batch_size: int = 10,
        enable_chart_conversion: bool = True,
        **kwargs,
    ):
        """初始化批量文档预处理任务

        Args:
            config: 任务队列配置,如果为None则使用默认配置
            llm_service: LLM服务实例,如果为None则使用全局实例
            batch_size: 批量处理大小,默认为10
            enable_chart_conversion: 是否启用图表转JSON功能,默认为True
            **kwargs: 其他参数
        """
        super().__init__(**kwargs)
        self.config = config or get_task_settings()
        self.llm_service = llm_service or get_llm_service()
        self.batch_size = batch_size
        self.enable_chart_conversion = enable_chart_conversion

        # 创建基础文档处理任务
        self.base_task = DocumentProcessingTask(
            config=self.config,
            llm_service=self.llm_service,
            use_agent=True,  # 批量处理使用Agent
            enable_chart_conversion=self.enable_chart_conversion,
        )

    async def execute(
        self, ctx: TaskContext, file_paths: list[str], **kwargs
    ) -> dict[str, Any]:
        """执行批量文档预处理任务

        Args:
            ctx: 任务上下文
            file_paths: 文档路径列表
            **kwargs: 其他参数

        Returns:
            任务执行结果字典
        """
        start_time = time.time()

        logger.info(f"开始批量文档预处理任务: {len(file_paths)} 个文件")
        logger.info(
            f"批量大小: {self.batch_size}, 图表转换: {self.enable_chart_conversion}"
        )

        try:
            # 分批处理
            processed_files = []
            failed_files = []
            batch_count = 0

            for i in range(0, len(file_paths), self.batch_size):
                batch_files = file_paths[i : i + self.batch_size]
                batch_count += 1

                logger.info(f"处理批次 {batch_count}: {len(batch_files)} 个文件")

                # 创建批次任务上下文
                batch_ctx = TaskContext(
                    task_id=f"{ctx.task_id}_batch_{batch_count}",
                    retry_count=0,
                    max_retries=self.max_retries,
                    timeout=self.timeout,
                    metadata=ctx.metadata,
                )

                # 执行批次处理
                batch_result = await self.base_task.execute(batch_ctx, batch_files)

                if batch_result["status"] == TaskStatus.COMPLETED:
                    # 注意:这里无法直接获取Document对象,因为结果被序列化了
                    # 在实际实现中,可能需要重新处理或从文件系统读取
                    processed_files.extend(batch_result["processed_files"])
                else:
                    failed_files.extend(batch_result.get("processed_files", []))
                    logger.error(
                        f"批次 {batch_count} 处理失败: {batch_result.get('error', 'Unknown error')}"
                    )

            # 执行图表转换(如果启用且所有批次都成功)
            chart_conversion_result = None
            if (
                self.enable_chart_conversion
                and len(failed_files) == 0
                and self.base_task.chart_converter
            ):
                logger.info("开始执行批量图表转换")
                chart_conversion_result = (
                    await self.base_task._execute_chart_conversion(processed_files)
                )

            processing_time = time.time() - start_time

            result = {
                "status": (
                    TaskStatus.COMPLETED
                    if len(failed_files) == 0
                    else TaskStatus.FAILED
                ),
                "task_id": ctx.task_id,
                "total_files": len(file_paths),
                "batch_count": batch_count,
                "batch_size": self.batch_size,
                "processed_files": processed_files,
                "failed_files": failed_files,
                "success_rate": (
                    len(processed_files) / len(file_paths) * 100 if file_paths else 0
                ),
                "processing_time": processing_time,
                "enable_chart_conversion": self.enable_chart_conversion,
                "chart_conversion": chart_conversion_result,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(
                f"批量文档预处理任务完成: 成功 {len(processed_files)}/{len(file_paths)} 个文件, "
                f"失败 {len(failed_files)} 个, "
                f"成功率 {result['success_rate']:.1f}%, "
                f"耗时 {processing_time:.2f} 秒"
            )

            return result

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"批量文档预处理任务失败: {e!s}"
            logger.error(error_msg, exc_info=True)

            result = {
                "status": TaskStatus.FAILED,
                "task_id": ctx.task_id,
                "error": str(e),
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat(),
            }

            return result


# 任务工厂函数
def create_document_processing_task(
    use_agent: bool = True, enable_chart_conversion: bool = True, **kwargs
) -> DocumentProcessingTask:
    """创建文档预处理任务实例

    Args:
        use_agent: 是否使用T032 Agent(True)或T031协调器(False)
        enable_chart_conversion: 是否启用图表转JSON功能,默认为True
        **kwargs: 其他参数

    Returns:
        文档预处理任务实例
    """
    return DocumentProcessingTask(
        use_agent=use_agent, enable_chart_conversion=enable_chart_conversion, **kwargs
    )


def create_batch_document_processing_task(
    batch_size: int = 10, enable_chart_conversion: bool = True, **kwargs
) -> BatchDocumentProcessingTask:
    """创建批量文档预处理任务实例

    Args:
        batch_size: 批量处理大小,默认为10
        enable_chart_conversion: 是否启用图表转JSON功能,默认为True
        **kwargs: 其他参数

    Returns:
        批量文档预处理任务实例
    """
    return BatchDocumentProcessingTask(
        batch_size=batch_size, enable_chart_conversion=enable_chart_conversion, **kwargs
    )


# 便捷函数
async def process_document_async(
    file_path: str,
    use_agent: bool = True,
    enable_chart_conversion: bool = True,
    **kwargs,
) -> dict[str, Any]:
    """异步处理单个文档

    便捷函数,用于快速处理单个文档。

    Args:
        file_path: 文档路径
        use_agent: 是否使用T032 Agent
        enable_chart_conversion: 是否启用图表转JSON功能
        **kwargs: 其他参数

    Returns:
        处理结果字典
    """
    task = create_document_processing_task(
        use_agent=use_agent, enable_chart_conversion=enable_chart_conversion, **kwargs
    )

    ctx = TaskContext(
        task_id="single_doc_processing",
        retry_count=0,
        max_retries=task.max_retries,
        timeout=task.timeout,
        metadata={},
    )

    return await task.execute(ctx, file_path)


async def process_documents_async(
    file_paths: list[str],
    use_agent: bool = True,
    enable_chart_conversion: bool = True,
    **kwargs,
) -> dict[str, Any]:
    """异步处理多个文档

    便捷函数,用于快速处理多个文档。

    Args:
        file_paths: 文档路径列表
        use_agent: 是否使用T032 Agent
        enable_chart_conversion: 是否启用图表转JSON功能
        **kwargs: 其他参数

    Returns:
        处理结果字典
    """
    task = create_document_processing_task(
        use_agent=use_agent, enable_chart_conversion=enable_chart_conversion, **kwargs
    )

    ctx = TaskContext(
        task_id="multi_doc_processing",
        retry_count=0,
        max_retries=task.max_retries,
        timeout=task.timeout,
        metadata={},
    )

    return await task.execute(ctx, file_paths)


async def process_batch_documents_async(
    file_paths: list[str],
    batch_size: int = 10,
    enable_chart_conversion: bool = True,
    **kwargs,
) -> dict[str, Any]:
    """异步批量处理大量文档

    便捷函数,用于处理大量文档。

    Args:
        file_paths: 文档路径列表
        batch_size: 批量处理大小
        enable_chart_conversion: 是否启用图表转JSON功能
        **kwargs: 其他参数

    Returns:
        处理结果字典
    """
    task = create_batch_document_processing_task(
        batch_size=batch_size, enable_chart_conversion=enable_chart_conversion, **kwargs
    )

    ctx = TaskContext(
        task_id="batch_doc_processing",
        retry_count=0,
        max_retries=task.max_retries,
        timeout=task.timeout,
        metadata={},
    )

    return await task.execute(ctx, file_paths)
