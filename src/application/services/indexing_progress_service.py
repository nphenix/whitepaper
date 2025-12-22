# 生成命令: /speckit.implement T057
# 生成时间: 2025-12-21
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
索引构建进度跟踪和状态管理服务 (T057)

该模块实现索引构建进度跟踪和状态管理的服务层，提供进度跟踪、状态管理等功能。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from src.domain.indexing.indexing_progress import (
    IndexingProgress,
    IndexingStep,
    StepStatus,
    TaskStatus,
    TaskType,
)
from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class IndexingProgressService:
    """索引构建进度跟踪和状态管理服务"""
    
    def __init__(self, db_adapter: Optional[SQLiteAdapter] = None) -> None:
        """
        初始化索引构建进度跟踪服务
        
        Args:
            db_adapter: 数据库适配器，如果为None则使用默认配置
        """
        self.db_adapter = db_adapter or SQLiteAdapter(table_name="indexing_progress")
        self.steps_adapter = SQLiteAdapter(table_name="indexing_steps")
        
        logger.debug("索引构建进度跟踪服务初始化完成")
    
    def create_progress(
        self,
        task_id: str,
        knowledge_base_id: str,
        task_type: TaskType,
        steps: Optional[List[Dict[str, Any]]] = None,
    ) -> IndexingProgress:
        """
        创建进度跟踪记录
        
        Args:
            task_id: 任务ID
            knowledge_base_id: 知识库ID
            task_type: 任务类型
            steps: 步骤列表
            
        Returns:
            进度跟踪对象
        """
        try:
            # 创建进度记录
            progress = IndexingProgress(
                task_id=task_id,
                knowledge_base_id=knowledge_base_id,
                task_type=task_type,
            )
            
            # 添加步骤
            if steps:
                for step_data in steps:
                    step = IndexingStep(
                        progress_id=progress.id,
                        **step_data
                    )
                    progress.add_step(step)
            
            # 保存到数据库
            progress_dict = progress.to_dict()
            # 移除steps字段，因为步骤单独存储
            progress_dict_for_db = {k: v for k, v in progress_dict.items() if k != "steps"}
            
            # adapter 会自动处理字典和列表类型的序列化
            created_progress = self.db_adapter.create(progress_dict_for_db)
            
            # 保存步骤
            for step in progress.steps:
                step_dict = step.to_dict()
                # adapter 会自动处理字典和列表类型的序列化
                self.steps_adapter.create(step_dict)
            
            logger.info(f"创建进度跟踪记录: task_id={task_id}, progress_id={progress.id}")
            return progress
            
        except Exception as exc:
            error_msg = f"创建进度跟踪记录失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise
    
    def get_progress(self, task_id: str) -> Optional[IndexingProgress]:
        """
        获取进度跟踪记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            进度跟踪对象，如果不存在则返回None
        """
        try:
            # 获取进度记录
            progress_record = self.db_adapter.execute_custom_query(
                f"SELECT * FROM {self.db_adapter.table_name} WHERE task_id = ?",
                (task_id,),
                fetch_one=True
            )
            if not progress_record:
                return None
            
            # 获取步骤
            steps_records = self.steps_adapter.list(
                filters={"progress_id": progress_record["id"]},
                order_by="step_order ASC"
            )
            
            # 构建步骤对象
            steps = []
            for step_record in steps_records:
                # 确保状态字段是枚举类型
                if isinstance(step_record.get("status"), str):
                    step_record["status"] = StepStatus(step_record["status"])
                
                # 反序列化details字段
                if "details" in step_record and isinstance(step_record["details"], str):
                    try:
                        step_record["details"] = json.loads(step_record["details"])
                    except (json.JSONDecodeError, TypeError):
                        step_record["details"] = {}
                
                step = IndexingStep(**step_record)
                steps.append(step)
            
            # 构建进度对象
            progress_dict = dict(progress_record)
            progress_dict["steps"] = steps
            progress_dict["task_type"] = TaskType(progress_dict["task_type"])
            progress_dict["status"] = TaskStatus(progress_dict["status"])
            
            # 反序列化progress_details字段
            if "progress_details" in progress_dict and isinstance(progress_dict["progress_details"], str):
                try:
                    progress_dict["progress_details"] = json.loads(progress_dict["progress_details"])
                except (json.JSONDecodeError, TypeError):
                    progress_dict["progress_details"] = {}
            
            # 转换时间字段
            if progress_dict.get("start_time"):
                progress_dict["start_time"] = datetime.fromisoformat(progress_dict["start_time"])
            
            if progress_dict.get("end_time"):
                progress_dict["end_time"] = datetime.fromisoformat(progress_dict["end_time"])
            
            if progress_dict.get("created_at"):
                progress_dict["created_at"] = datetime.fromisoformat(progress_dict["created_at"])
            
            if progress_dict.get("updated_at"):
                progress_dict["updated_at"] = datetime.fromisoformat(progress_dict["updated_at"])
            
            # 转换步骤时间字段
            for step in steps:
                if isinstance(step.start_time, str):
                    step.start_time = datetime.fromisoformat(step.start_time)
                
                if isinstance(step.end_time, str):
                    step.end_time = datetime.fromisoformat(step.end_time)
                
                if isinstance(step.created_at, str):
                    step.created_at = datetime.fromisoformat(step.created_at)
                
                if isinstance(step.updated_at, str):
                    step.updated_at = datetime.fromisoformat(step.updated_at)
            
            progress = IndexingProgress(**progress_dict)
            return progress
            
        except Exception as exc:
            error_msg = f"获取进度跟踪记录失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise
    
    def update_progress(
        self,
        task_id: str,
        status: Optional[TaskStatus] = None,
        current_step: Optional[str] = None,
        completed_steps: Optional[int] = None,
        progress_details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
        documents_count: Optional[int] = None,
        nodes_count: Optional[int] = None,
        chunks_count: Optional[int] = None,
        vector_indexed_count: Optional[int] = None,
        bm25_indexed_count: Optional[int] = None,
        metadata_indexed_count: Optional[int] = None,
    ) -> Optional[IndexingProgress]:
        """
        更新进度跟踪记录
        
        Args:
            task_id: 任务ID
            status: 任务状态
            current_step: 当前步骤
            completed_steps: 已完成步骤数
            progress_details: 进度详情
            error_message: 错误消息
            error_traceback: 错误堆栈
            documents_count: 文档数量
            nodes_count: 节点数量
            chunks_count: 块数量
            vector_indexed_count: 向量索引数量
            bm25_indexed_count: BM25索引数量
            metadata_indexed_count: 元数据索引数量
            
        Returns:
            更新后的进度跟踪对象，如果不存在则返回None
        """
        try:
            # 获取现有进度记录
            progress = self.get_progress(task_id)
            if not progress:
                return None
            
            # 更新状态
            if status:
                progress.status = status
                
                # 根据状态更新时间
                if status == TaskStatus.RUNNING and not progress.start_time:
                    progress.start()
                elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    if status == TaskStatus.COMPLETED:
                        progress.complete()
                    elif status == TaskStatus.FAILED and error_message:
                        progress.fail(error_message, error_traceback)
                    elif status == TaskStatus.CANCELLED:
                        progress.cancel()
            
            # 更新进度
            progress.update_progress(
                current_step=current_step,
                completed_steps=completed_steps,
                progress_details=progress_details,
            )
            
            # 更新统计信息
            progress.update_statistics(
                documents_count=documents_count,
                nodes_count=nodes_count,
                chunks_count=chunks_count,
                vector_indexed_count=vector_indexed_count,
                bm25_indexed_count=bm25_indexed_count,
                metadata_indexed_count=metadata_indexed_count,
            )
            
            # 更新错误信息
            if error_message:
                progress.error_message = error_message
            
            if error_traceback:
                progress.error_traceback = error_traceback
            
            # 保存到数据库
            progress_dict = progress.to_dict()
            # 移除steps字段，因为步骤单独存储
            progress_dict_for_db = {k: v for k, v in progress_dict.items() if k != "steps"}
            
            # 将字典类型的字段序列化为JSON字符串
            if "progress_details" in progress_dict_for_db and isinstance(progress_dict_for_db["progress_details"], dict):
                progress_dict_for_db["progress_details"] = json.dumps(progress_dict_for_db["progress_details"])
            
            self.db_adapter.execute_custom_query(
                f"UPDATE {self.db_adapter.table_name} SET {', '.join(f'{k} = ?' for k in progress_dict_for_db.keys())} WHERE task_id = ?",
                tuple(list(progress_dict_for_db.values()) + [task_id])
            )
            
            logger.info(f"更新进度跟踪记录: task_id={task_id}, status={status.value if status else None}")
            return progress
            
        except Exception as exc:
            error_msg = f"更新进度跟踪记录失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise
    
    def update_step(
        self,
        task_id: str,
        step_name: str,
        status: StepStatus,
        description: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
    ) -> Optional[IndexingStep]:
        """
        更新步骤状态
        
        Args:
            task_id: 任务ID
            step_name: 步骤名称
            status: 步骤状态
            description: 步骤描述
            details: 步骤详情
            error_message: 错误消息
            
        Returns:
            更新后的步骤对象，如果不存在则返回None
        """
        try:
            # 获取进度记录
            progress = self.get_progress(task_id)
            if not progress:
                return None
            
            # 获取步骤
            step = progress.get_step_by_name(step_name)
            if not step:
                return None
            
            # 更新步骤状态
            if status == StepStatus.RUNNING and step.status != StepStatus.RUNNING:
                step.start()
            elif status == StepStatus.COMPLETED and step.status != StepStatus.COMPLETED:
                step.complete()
            elif status == StepStatus.FAILED and error_message:
                step.fail(error_message)
            elif status == StepStatus.SKIPPED and description:
                step.skip(description)
            
            # 更新描述和详情
            if description:
                step.description = description
            
            if details:
                step.details.update(details)
            
            # 保存到数据库
            step_dict = step.to_dict()
            self.steps_adapter.update(step.id, step_dict)
            
            # 更新进度记录的已完成步骤数
            completed_steps = sum(1 for s in progress.steps if s.status == StepStatus.COMPLETED)
            # 直接更新数据库，避免重复调用get_progress
            progress_dict = progress.to_dict()
            # 移除steps字段，因为步骤单独存储
            progress_dict_for_db = {k: v for k, v in progress_dict.items() if k != "steps"}
            progress_dict_for_db["completed_steps"] = completed_steps
            
            self.db_adapter.update(task_id, progress_dict_for_db, "task_id")
            
            logger.info(f"更新步骤状态: task_id={task_id}, step={step_name}, status={status.value}")
            return step
            
        except Exception as exc:
            error_msg = f"更新步骤状态失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise
    
    def list_progress(
        self,
        knowledge_base_id: Optional[str] = None,
        task_type: Optional[TaskType] = None,
        status: Optional[TaskStatus] = None,
        limit: Optional[int] = None,
    ) -> List[IndexingProgress]:
        """
        列出进度跟踪记录
        
        Args:
            knowledge_base_id: 知识库ID
            task_type: 任务类型
            status: 任务状态
            limit: 限制数量
            
        Returns:
            进度跟踪记录列表
        """
        try:
            # 构建过滤条件
            filters = {}
            if knowledge_base_id:
                filters["knowledge_base_id"] = knowledge_base_id
            
            if task_type:
                filters["task_type"] = task_type.value
            
            if status:
                filters["status"] = status.value
            
            # 查询记录
            progress_records = self.db_adapter.list(
                filters=filters,
                limit=limit,
                order_by="created_at DESC"
            )
            
            # 构建进度对象列表
            progress_list = []
            for record in progress_records:
                task_id = record["task_id"]
                progress = self.get_progress(task_id)
                if progress:
                    progress_list.append(progress)
            
            return progress_list
            
        except Exception as exc:
            error_msg = f"列出进度跟踪记录失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise
    
    def delete_progress(self, task_id: str) -> bool:
        """
        删除进度跟踪记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否删除成功
        """
        try:
            # 获取进度记录
            progress = self.get_progress(task_id)
            if not progress:
                return False
            
            # 删除步骤
            for step in progress.steps:
                self.steps_adapter.delete(step.id)
            
            # 删除进度记录
            success = self.db_adapter.execute_custom_query(
                f"DELETE FROM {self.db_adapter.table_name} WHERE task_id = ?",
                (task_id,)
            ) is not None
            
            if success:
                logger.info(f"删除进度跟踪记录: task_id={task_id}")
            
            return success
            
        except Exception as exc:
            error_msg = f"删除进度跟踪记录失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise
    
    def get_progress_summary(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取进度摘要
        
        Args:
            task_id: 任务ID
            
        Returns:
            进度摘要字典，如果不存在则返回None
        """
        try:
            progress = self.get_progress(task_id)
            if not progress:
                return None
            
            # 构建摘要
            summary = {
                "task_id": progress.task_id,
                "knowledge_base_id": progress.knowledge_base_id,
                "task_type": progress.task_type.value if hasattr(progress.task_type, 'value') else progress.task_type,
                "status": progress.status.value if hasattr(progress.status, 'value') else progress.status,
                "progress_percentage": progress.progress_percentage,
                "current_step": progress.current_step,
                "total_steps": progress.total_steps,
                "completed_steps": progress.completed_steps,
                "start_time": progress.start_time.isoformat() if progress.start_time else None,
                "end_time": progress.end_time.isoformat() if progress.end_time else None,
                "duration_seconds": progress.duration_seconds,
                "error_message": progress.error_message,
                "statistics": {
                    "documents_count": progress.documents_count,
                    "nodes_count": progress.nodes_count,
                    "chunks_count": progress.chunks_count,
                    "vector_indexed_count": progress.vector_indexed_count,
                    "bm25_indexed_count": progress.bm25_indexed_count,
                    "metadata_indexed_count": progress.metadata_indexed_count,
                },
                "steps": []
            }
            
            # 添加步骤摘要
            for step in progress.steps:
                step_summary = {
                    "name": step.step_name,
                    "order": step.step_order,
                    "status": step.status.value if hasattr(step.status, 'value') else step.status,
                    "description": step.description,
                    "duration_seconds": step.duration_seconds,
                    "error_message": step.error_message,
                }
                summary["steps"].append(step_summary)
            
            return summary
            
        except Exception as exc:
            error_msg = f"获取进度摘要失败: {exc}"
            logger.error(error_msg, exc_info=True)
            raise


# 全局服务实例
_progress_service: Optional[IndexingProgressService] = None


def get_progress_service() -> IndexingProgressService:
    """
    获取全局进度跟踪服务实例
    
    Returns:
        进度跟踪服务实例
    """
    global _progress_service
    if _progress_service is None:
        _progress_service = IndexingProgressService()
    return _progress_service