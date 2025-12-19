"""
任务模块初始化

自动注册所有文档预处理任务到任务注册表中。
"""

# 导入所有任务类,确保它们被注册
from .document_tasks import (
    BatchDocumentProcessingTask,
    DocumentProcessingTask,
    create_batch_document_processing_task,
    create_document_processing_task,
    process_batch_documents_async,
    process_document_async,
    process_documents_async,
)


# 确保任务被注册
def register_document_tasks() -> None:
    """注册所有文档预处理任务"""
    from .worker import get_task_registry

    registry = get_task_registry()

    # 注册基础任务类
    registry.register_task(DocumentProcessingTask, name="document_processing")
    registry.register_task(
        BatchDocumentProcessingTask, name="batch_document_processing"
    )

    # 注册便捷函数
    registry.register_task(
        create_document_processing_task, name="create_document_processing_task"
    )
    registry.register_task(
        create_batch_document_processing_task,
        name="create_batch_document_processing_task",
    )
    registry.register_task(process_document_async, name="process_document_async")
    registry.register_task(process_documents_async, name="process_documents_async")
    registry.register_task(
        process_batch_documents_async, name="process_batch_documents_async"
    )

    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"已注册 {len(registry.list_tasks())} 个文档预处理任务")


# 自动注册任务
register_document_tasks()

__all__ = [
    "BatchDocumentProcessingTask",
    "DocumentProcessingTask",
    "create_batch_document_processing_task",
    "create_document_processing_task",
    "process_batch_documents_async",
    "process_document_async",
    "process_documents_async",
    "register_document_tasks",
]
