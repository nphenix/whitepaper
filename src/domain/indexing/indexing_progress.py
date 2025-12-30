# 生成命令: /speckit.implement T057
# 生成时间: 2025-12-21
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
索引构建进度跟踪和状态管理领域模型 (T057)

该模块实现索引构建进度跟踪和状态管理的领域模型,用于跟踪知识库索引构建过程中的进度和状态.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, validator


class TaskType(str, Enum):
    """任务类型枚举"""

    CREATE_KNOWLEDGE_BASE = "create_knowledge_base"  # 创建知识库
    UPDATE_KNOWLEDGE_BASE = "update_knowledge_base"  # 更新知识库
    DELETE_KNOWLEDGE_BASE = "delete_knowledge_base"  # 删除知识库
    QUERY_KNOWLEDGE_BASE = "query_knowledge_base"  # 查询知识库


class TaskStatus(str, Enum):
    """任务状态枚举"""

    PENDING = "pending"  # 待处理
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


class StepStatus(str, Enum):
    """步骤状态枚举"""

    PENDING = "pending"  # 待处理
    RUNNING = "running"  # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 已跳过


class IndexingStep(BaseModel):
    """索引构建步骤模型"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    progress_id: str
    step_name: str
    step_order: int
    status: StepStatus = StepStatus.PENDING
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float | None = None
    description: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        """Pydantic配置"""
        use_enum_values = True
        validate_assignment = True
        arbitrary_types_allowed = True

    @validator("duration_seconds", pre=True, always=True)
    def calculate_duration(cls, v: float | None, values: dict[str, Any]) -> float | None:
        """计算持续时间"""
        if v is not None:
            return v

        start_time = values.get("start_time")
        end_time = values.get("end_time")

        if start_time and end_time:
            return float((end_time - start_time).total_seconds())

        return None

    def start(self) -> None:
        """开始步骤"""
        self.status = StepStatus.RUNNING
        self.start_time = datetime.now()
        self.updated_at = datetime.now()

    def complete(self) -> None:
        """完成步骤"""
        self.status = StepStatus.COMPLETED
        self.end_time = datetime.now()
        self.updated_at = datetime.now()

        # 重新计算持续时间
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def fail(self, error_message: str) -> None:
        """步骤失败"""
        self.status = StepStatus.FAILED
        self.error_message = error_message
        self.end_time = datetime.now()
        self.updated_at = datetime.now()

        # 重新计算持续时间
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def skip(self, reason: str) -> None:
        """跳过步骤"""
        self.status = StepStatus.SKIPPED
        self.description = reason
        self.end_time = datetime.now()
        self.updated_at = datetime.now()

        # 重新计算持续时间
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "progress_id": self.progress_id,
            "step_name": self.step_name,
            "step_order": self.step_order,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "description": self.description,
            "details": self.details,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class IndexingProgress(BaseModel):
    """索引构建进度跟踪模型"""

    id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    knowledge_base_id: str
    task_type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float | None = None

    # 进度信息
    current_step: str | None = None
    total_steps: int = 0
    completed_steps: int = 0
    progress_percentage: float = 0.0

    # 详细进度信息
    progress_details: dict[str, Any] = Field(default_factory=dict)

    # 错误信息
    error_message: str | None = None
    error_traceback: str | None = None

    # 结果统计
    documents_count: int = 0
    nodes_count: int = 0
    chunks_count: int = 0

    # 索引统计
    vector_indexed_count: int = 0
    bm25_indexed_count: int = 0
    metadata_indexed_count: int = 0

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # 关联的步骤
    steps: list[IndexingStep] = Field(default_factory=list)

    class Config:
        """Pydantic配置"""
        use_enum_values = True
        validate_assignment = True
        arbitrary_types_allowed = True

    @validator("duration_seconds", pre=True, always=True)
    def calculate_duration(cls, v: float | None, values: dict[str, Any]) -> float | None:
        """计算持续时间"""
        if v is not None:
            return v

        start_time = values.get("start_time")
        end_time = values.get("end_time")

        if start_time and end_time:
            return float((end_time - start_time).total_seconds())

        return None

    @validator("progress_percentage", pre=True, always=True)
    def calculate_progress_percentage(cls, v: float | None, values: dict[str, Any]) -> float:
        """计算进度百分比"""
        if v is not None:
            return v

        total_steps = values.get("total_steps", 0)
        completed_steps = values.get("completed_steps", 0)

        if total_steps > 0:
            return float(round((completed_steps / total_steps) * 100, 2))

        return 0.0

    def start(self) -> None:
        """开始任务"""
        self.status = TaskStatus.RUNNING
        self.start_time = datetime.now()
        self.updated_at = datetime.now()

    def complete(self) -> None:
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.end_time = datetime.now()
        self.updated_at = datetime.now()
        self.progress_percentage = 100.0
        self.completed_steps = self.total_steps

        # 重新计算持续时间
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def fail(self, error_message: str, error_traceback: str | None = None) -> None:
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.error_message = error_message
        self.error_traceback = error_traceback
        self.end_time = datetime.now()
        self.updated_at = datetime.now()

        # 重新计算持续时间
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def cancel(self) -> None:
        """取消任务"""
        self.status = TaskStatus.CANCELLED
        self.end_time = datetime.now()
        self.updated_at = datetime.now()

        # 重新计算持续时间
        if self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()

    def update_progress(
        self,
        current_step: str | None = None,
        completed_steps: int | None = None,
        progress_details: dict[str, Any] | None = None,
    ) -> None:
        """更新进度"""
        if current_step is not None:
            self.current_step = current_step

        if completed_steps is not None:
            self.completed_steps = completed_steps

        if progress_details is not None:
            self.progress_details.update(progress_details)

        # 重新计算进度百分比
        if self.total_steps > 0:
            self.progress_percentage = round((self.completed_steps / self.total_steps) * 100, 2)

        self.updated_at = datetime.now()

    def update_statistics(
        self,
        documents_count: int | None = None,
        nodes_count: int | None = None,
        chunks_count: int | None = None,
        vector_indexed_count: int | None = None,
        bm25_indexed_count: int | None = None,
        metadata_indexed_count: int | None = None,
    ) -> None:
        """更新统计信息"""
        if documents_count is not None:
            self.documents_count = documents_count

        if nodes_count is not None:
            self.nodes_count = nodes_count

        if chunks_count is not None:
            self.chunks_count = chunks_count

        if vector_indexed_count is not None:
            self.vector_indexed_count = vector_indexed_count

        if bm25_indexed_count is not None:
            self.bm25_indexed_count = bm25_indexed_count

        if metadata_indexed_count is not None:
            self.metadata_indexed_count = metadata_indexed_count

        self.updated_at = datetime.now()

    def add_step(self, step: IndexingStep) -> None:
        """添加步骤"""
        self.steps.append(step)
        self.total_steps = len(self.steps)
        self.updated_at = datetime.now()

    def get_step_by_name(self, step_name: str) -> IndexingStep | None:
        """根据名称获取步骤"""
        for step in self.steps:
            if step.step_name == step_name:
                return step
        return None

    def get_current_step_obj(self) -> IndexingStep | None:
        """获取当前步骤对象"""
        if not self.current_step:
            return None

        return self.get_step_by_name(self.current_step)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "knowledge_base_id": self.knowledge_base_id,
            "task_type": self.task_type.value if hasattr(self.task_type, "value") else self.task_type,
            "status": self.status.value if hasattr(self.status, "value") else self.status,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "progress_percentage": self.progress_percentage,
            "progress_details": self.progress_details,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
            "documents_count": self.documents_count,
            "nodes_count": self.nodes_count,
            "chunks_count": self.chunks_count,
            "vector_indexed_count": self.vector_indexed_count,
            "bm25_indexed_count": self.bm25_indexed_count,
            "metadata_indexed_count": self.metadata_indexed_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "steps": [step.to_dict() for step in self.steps],
        }
