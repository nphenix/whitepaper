"""
工作流API路由模块

提供工作流状态管理相关接口:
- GET /api/workflow/{workflow_id}/status: 获取工作流状态
- POST /api/workflow/{workflow_id}/step/{step_number}: 更新工作流步骤状态

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter

from src.interfaces.api.error_handlers import (
    create_error_response_from_exception,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    UpdateWorkflowStepRequest,
    create_error_response,
    create_success_response,
)
from src.shared.utils.logging import get_logger

from .core import get_workflow_adapter

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(tags=["工作流管理"])


@router.get(
    "/workflow/{workflow_id}/status",
    response_model=dict[str, Any],
    summary="获取工作流状态",
    description="获取指定工作流的当前状态和步骤进度(前端适配接口)",
)
async def get_workflow_status(
    workflow_id: str,
) -> dict[str, Any]:
    """
    获取工作流状态接口(前端适配)

    从数据库获取工作流的状态信息,包括:
    - 当前状态(current_status)
    - 各步骤的完成状态(step1_status, step2_status, step3_status, step4_status)
    - 步骤数据(step_data,用于数据传递)

    Args:
        workflow_id: 工作流ID(通常是outline_id或draft_id)

    Returns:
        统一响应格式:{ success: bool, data: { workflowId, currentStatus, step1Status, ... } }
    """
    try:
        # 获取工作流状态适配器
        workflow_adapter = get_workflow_adapter()

        # 从数据库获取工作流状态
        try:
            workflow_statuses = workflow_adapter.list(
                filters={"workflow_id": workflow_id},
                limit=1
            )
        except Exception as e:
            logger.error("从数据库获取工作流状态失败: %s", e, exc_info=True)
            return create_error_response(
                "获取工作流状态失败",
                str(e)
            )

        # 如果不存在,返回默认状态
        if not workflow_statuses:
            default_status = {
                "workflowId": workflow_id,
                "currentStatus": "step1_selected",  # 默认从第一步开始
                "step1Status": "pending",
                "step2Status": "pending",
                "step3Status": "pending",
                "step4Status": "pending",
                "stepData": {},
                "createdAt": datetime.now(UTC).isoformat(),
                "updatedAt": datetime.now(UTC).isoformat(),
            }
            return create_success_response(data=default_status)

        # 获取第一个(应该只有一个)
        status_data = workflow_statuses[0]

        # 解析step_data(JSON字符串)
        step_data = {}
        step_data_str = status_data.get("step_data", "{}")
        if step_data_str:
            try:
                step_data = json.loads(step_data_str) if isinstance(step_data_str, str) else step_data_str
            except (json.JSONDecodeError, TypeError):
                step_data = {}

        # 转换为前端期望的格式
        response_data = {
            "workflowId": status_data.get("workflow_id", workflow_id),
            "currentStatus": status_data.get("current_status", "step1_selected"),
            "step1Status": status_data.get("step1_status", "pending"),
            "step2Status": status_data.get("step2_status", "pending"),
            "step3Status": status_data.get("step3_status", "pending"),
            "step4Status": status_data.get("step4_status", "pending"),
            "stepData": step_data,
            "createdAt": status_data.get("created_at", ""),
            "updatedAt": status_data.get("updated_at", ""),
        }

        logger.info("获取工作流状态成功: workflow_id=%s, current_status=%s", workflow_id, response_data["currentStatus"])

        return create_success_response(data=response_data)

    except Exception as e:
        logger.exception("获取工作流状态异常: %s", e)
        return create_error_response_from_exception(e)


@router.post(
    "/workflow/{workflow_id}/step/{step_number}",
    response_model=dict[str, Any],
    summary="更新工作流步骤状态",
    description="更新指定工作流的指定步骤状态(前端适配接口)",
)
async def update_workflow_step(
    workflow_id: str,
    step_number: int,
    request: UpdateWorkflowStepRequest,
) -> dict[str, Any]:
    """
    更新工作流步骤状态接口(前端适配)

    支持更新4个步骤的状态:
    - step_number=1: 步骤1(行业和数据库选择)
    - step_number=2: 步骤2(大纲优化)
    - step_number=3: 步骤3(来源选择)
    - step_number=4: 步骤4(草稿生成)

    步骤状态:pending(待处理)或 completed(已完成)

    当步骤状态更新为completed时,会自动更新current_status为对应的状态值:
    - step1 completed -> current_status = "step1_selected"
    - step2 completed -> current_status = "step2_optimized"
    - step3 completed -> current_status = "step3_sources_selected"
    - step4 completed -> current_status = "step4_generated"

    Args:
        workflow_id: 工作流ID(通常是outline_id或draft_id)
        step_number: 步骤编号(1-4)
        request: 更新请求,包含status和可选的stepData

    Returns:
        统一响应格式:{ success: bool, message?: str }
    """
    try:
        # 验证步骤编号
        if step_number < 1 or step_number > 4:
            return create_error_response(
                "无效的步骤编号",
                f"步骤编号必须在1-4之间,当前值: {step_number}"
            )

        # 验证状态值
        if request.status not in ["pending", "completed"]:
            return create_error_response(
                "无效的状态值",
                f"状态值必须是 'pending' 或 'completed',当前值: {request.status}"
            )

        # 获取工作流状态适配器
        workflow_adapter = get_workflow_adapter()

        # 从数据库获取现有状态(如果存在)
        try:
            existing_statuses = workflow_adapter.list(
                filters={"workflow_id": workflow_id},
                limit=1
            )
        except Exception as e:
            logger.error("从数据库获取工作流状态失败: %s", e, exc_info=True)
            return create_error_response(
                "获取工作流状态失败",
                str(e)
            )

        now = datetime.now(UTC).isoformat()

        if existing_statuses:
            # 更新现有记录
            status_data = existing_statuses[0]
            status_id = status_data["id"]

            # 更新对应步骤的状态
            step_field = f"step{step_number}_status"
            status_data[step_field] = request.status

            # 如果步骤完成,更新current_status
            if request.status == "completed":
                if step_number == 1:
                    status_data["current_status"] = "step1_selected"
                elif step_number == 2:
                    status_data["current_status"] = "step2_optimized"
                elif step_number == 3:
                    status_data["current_status"] = "step3_sources_selected"
                elif step_number == 4:
                    status_data["current_status"] = "step4_generated"

            # 更新step_data(合并现有数据)
            step_data = {}
            step_data_str = status_data.get("step_data", "{}")
            if step_data_str:
                try:
                    step_data = json.loads(step_data_str) if isinstance(step_data_str, str) else step_data_str
                except (json.JSONDecodeError, TypeError):
                    step_data = {}

            # 合并新的step_data
            if request.stepData:
                step_data.update(request.stepData)

            status_data["step_data"] = json.dumps(step_data, ensure_ascii=False)
            status_data["updated_at"] = now

            # 更新数据库
            try:
                workflow_adapter.update(status_id, status_data)
                logger.info("更新工作流步骤状态成功: workflow_id=%s, step=%d, status=%s",
                           workflow_id, step_number, request.status)
            except Exception as e:
                logger.error("更新工作流状态到数据库失败: %s", e, exc_info=True)
                return create_error_response(
                    "更新工作流状态失败",
                    str(e)
                )
        else:
            # 创建新记录
            # 初始化所有步骤状态为pending
            initial_statuses = {
                "step1_status": "pending",
                "step2_status": "pending",
                "step3_status": "pending",
                "step4_status": "pending",
            }

            # 设置当前步骤的状态
            step_field = f"step{step_number}_status"
            initial_statuses[step_field] = request.status

            # 确定current_status
            if request.status == "completed":
                if step_number == 1:
                    current_status = "step1_selected"
                elif step_number == 2:
                    current_status = "step2_optimized"
                elif step_number == 3:
                    current_status = "step3_sources_selected"
                elif step_number == 4:
                    current_status = "step4_generated"
                else:
                    current_status = "step1_selected"
            else:
                current_status = "step1_selected"

            # 准备step_data
            step_data = request.stepData or {}

            new_status = {
                "id": str(uuid.uuid4()),
                "workflow_id": workflow_id,
                "current_status": current_status,
                "step1_status": initial_statuses["step1_status"],
                "step2_status": initial_statuses["step2_status"],
                "step3_status": initial_statuses["step3_status"],
                "step4_status": initial_statuses["step4_status"],
                "step_data": json.dumps(step_data, ensure_ascii=False),
                "created_at": now,
                "updated_at": now,
            }

            # 创建新记录
            try:
                workflow_adapter.create(new_status)
                logger.info("创建工作流状态成功: workflow_id=%s, step=%d, status=%s",
                           workflow_id, step_number, request.status)
            except Exception as e:
                logger.error("创建工作流状态到数据库失败: %s", e, exc_info=True)
                return create_error_response(
                    "创建工作流状态失败",
                    str(e)
                )

        return create_success_response(
            message=f"步骤{step_number}状态已更新为: {request.status}"
        )

    except Exception as e:
        logger.exception("更新工作流步骤状态异常: %s", e)
        return create_error_response_from_exception(e)


__all__ = ["router"]
