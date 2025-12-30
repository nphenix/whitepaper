"""
大纲服务

该模块提供大纲的管理服务, 支持手写大纲输入(文本输入,结构化输入),
大纲查询,大纲更新等功能.用于MVP 4步流程中的第二步: 大纲手写和AI优化.
"""

# 生成命令: /speckit.implement T212
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from typing import Any

from structlog import get_logger

from src.application.services.base_service import BaseService
from src.domain.agent.outline import (
    Outline,
    OutlineItem,
    OutlineItemType,
    OutlineStatus,
    create_outline_from_structure,
    create_outline_from_text,
)
from src.shared.exceptions.base_exceptions import (
    ResourceNotFoundError,
    ValidationError,
)
from src.shared.utils.validators import validate_uuid

logger = get_logger()


class OutlineService(BaseService):
    """
    大纲服务

    提供大纲的管理功能, 包括文本输入,结构化输入,大纲查询,大纲更新等.
    """

    def get_service_name(self) -> str:
        """
        获取服务名称

        Returns:
            服务名称字符串
        """
        return "outline_service"

    def __init__(self, connection_manager=None):
        """
        初始化大纲服务

        Args:
            connection_manager: SQLite连接管理器, 如果为None则使用默认连接
        """
        super().__init__(connection_manager)
        # TODO: 添加大纲持久化适配器(当需要数据库存储时)
        self._outlines: dict[str, Outline] = {}  # 临时内存存储

    def create_outline_from_text(
        self,
        title: str,
        text: str,
        industry_id: str,
        database_ids: list[str] | None = None,
        description: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        从文本创建大纲

        Args:
            title: 大纲标题
            text: 大纲文本(支持Markdown格式)
            industry_id: 所属行业ID
            database_ids: 数据库ID列表
            description: 大纲描述
            session_id: 会话ID(可选)

        Returns:
            创建的大纲信息

        Raises:
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证输入
            if not title or not title.strip():
                error_msg = "大纲标题不能为空"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            if not text or not text.strip():
                error_msg = "大纲文本不能为空"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            # 验证UUID格式
            validate_uuid(industry_id)

            if database_ids:
                for db_id in database_ids:
                    validate_uuid(db_id)

            # 创建大纲
            outline = create_outline_from_text(
                title=title.strip(),
                text=text.strip(),
                industry_id=uuid.UUID(industry_id),
                database_ids=[uuid.UUID(db_id) for db_id in (database_ids or [])],
                description=description.strip() if description else None,
            )

            # 保存到内存(TODO: 后续改为数据库存储)
            outline_id = str(outline.id)
            self._outlines[outline_id] = outline

            # 创建初始版本
            outline.create_version(OutlineStatus.DRAFT, "从文本创建大纲")

            result = {
                "outline": outline.to_dict(),
                "outline_id": outline_id,
                "title": outline.title,
                "status": outline.status.value
                if hasattr(outline.status, "value")
                else str(outline.status),
                "total_items": len(outline.items),
                "created_at": outline.created_at.isoformat(),
                "session_id": session_id,
            }

            logger.info(
                "从文本创建大纲成功",
                outline_id=outline_id,
                title=title,
                industry_id=industry_id,
                total_items=len(outline.items),
            )

            return result

        except ValidationError:
            raise
        except Exception as e:
            error_msg = f"从文本创建大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def create_outline_from_structure(
        self,
        title: str,
        structure: list[dict[str, Any]],
        industry_id: str,
        database_ids: list[str] | None = None,
        description: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        从结构化数据创建大纲

        Args:
            title: 大纲标题
            structure: 结构化大纲数据(嵌套的children)
            industry_id: 所属行业ID
            database_ids: 数据库ID列表
            description: 大纲描述
            session_id: 会话ID(可选)

        Returns:
            创建的大纲信息

        Raises:
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证输入
            if not title or not title.strip():
                error_msg = "大纲标题不能为空"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            if not structure:
                error_msg = "大纲结构不能为空"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            # 验证UUID格式
            validate_uuid(industry_id)

            if database_ids:
                for db_id in database_ids:
                    validate_uuid(db_id)

            # 创建大纲
            outline = create_outline_from_structure(
                title=title.strip(),
                structure=structure,
                industry_id=uuid.UUID(industry_id),
                database_ids=[uuid.UUID(db_id) for db_id in (database_ids or [])],
                description=description.strip() if description else None,
            )

            # 保存到内存(TODO: 后续改为数据库存储)
            outline_id = str(outline.id)
            self._outlines[outline_id] = outline

            # 创建初始版本
            outline.create_version(OutlineStatus.DRAFT, "从结构化数据创建大纲")

            result = {
                "outline": outline.to_dict(),
                "outline_id": outline_id,
                "title": outline.title,
                "status": outline.status.value
                if hasattr(outline.status, "value")
                else str(outline.status),
                "total_items": len(outline.items),
                "created_at": outline.created_at.isoformat(),
                "session_id": session_id,
            }

            logger.info(
                "从结构化数据创建大纲成功",
                outline_id=outline_id,
                title=title,
                industry_id=industry_id,
                total_items=len(outline.items),
            )

            return result

        except ValidationError:
            raise
        except Exception as e:
            error_msg = f"从结构化数据创建大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_outline(self, outline_id: str) -> dict[str, Any]:
        """
        获取大纲

        Args:
            outline_id: 大纲ID

        Returns:
            大纲信息

        Raises:
            ResourceNotFoundError: 大纲不存在时抛出
        """
        try:
            # 验证UUID格式
            validate_uuid(outline_id)

            outline = self._outlines.get(outline_id)
            if not outline:
                error_msg = f"大纲不存在: {outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="Outline", resource_id=outline_id
                )

            logger.debug("获取大纲信息成功", outline_id=outline_id)

            return {
                "outline": outline.to_dict(),
                "outline_id": outline_id,
                "title": outline.title,
                "description": outline.description,
                "status": outline.status.value
                if hasattr(outline.status, "value")
                else str(outline.status),
                "total_items": len(outline.items),
                "current_version": outline.current_version,
                "created_at": outline.created_at.isoformat(),
                "updated_at": outline.updated_at.isoformat(),
            }

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"获取大纲信息失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_outline_tree(self, outline_id: str) -> dict[str, Any]:
        """
        获取大纲树结构

        Args:
            outline_id: 大纲ID

        Returns:
            大纲树结构信息

        Raises:
            ResourceNotFoundError: 大纲不存在时抛出
        """
        try:
            # 验证UUID格式
            validate_uuid(outline_id)

            outline = self._outlines.get(outline_id)
            if not outline:
                error_msg = f"大纲不存在: {outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="Outline", resource_id=outline_id
                )

            tree = outline.build_tree()

            logger.debug("获取大纲树结构成功", outline_id=outline_id)

            return {
                "outline_id": outline_id,
                "title": outline.title,
                "description": outline.description,
                "status": outline.status.value
                if hasattr(outline.status, "value")
                else str(outline.status),
                "tree": tree,
                "total_items": len(outline.items),
            }

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"获取大纲树结构失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def update_outline(
        self,
        outline_id: str,
        title: str | None = None,
        description: str | None = None,
        items: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        更新大纲

        Args:
            outline_id: 大纲ID
            title: 新标题(可选)
            description: 新描述(可选)
            items: 新大纲项列表(可选)

        Returns:
            更新后的大纲信息

        Raises:
            ResourceNotFoundError: 大纲不存在时抛出
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证UUID格式
            validate_uuid(outline_id)

            outline = self._outlines.get(outline_id)
            if not outline:
                error_msg = f"大纲不存在: {outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="Outline", resource_id=outline_id
                )

            # 更新标题
            if title is not None:
                if not title or not title.strip():
                    error_msg = "大纲标题不能为空"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)
                outline.title = title.strip()

            # 更新描述
            if description is not None:
                outline.description = description.strip() if description else None

            # 更新大纲项
            if items is not None:
                # 清空现有大纲项
                outline.items = []

                # 添加新大纲项
                for item_data in items:
                    item = OutlineItem(**item_data)
                    outline.add_item(item)

            logger.info(
                "更新大纲成功",
                outline_id=outline_id,
                updated_fields=[
                    field
                    for field in ["title", "description", "items"]
                    if locals()[field] is not None
                ],
            )

            return self.get_outline(outline_id)

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"更新大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def add_outline_item(
        self,
        outline_id: str,
        parent_id: str | None,
        item_type: str,
        title: str,
        level: int,
        description: str | None = None,
        order: int = 0,
    ) -> dict[str, Any]:
        """
        添加大纲项

        Args:
            outline_id: 大纲ID
            parent_id: 父级大纲项ID(可选)
            item_type: 大纲项类型
            title: 大纲项标题
            level: 大纲项层级
            description: 大纲项描述(可选)
            order: 排序顺序

        Returns:
            添加的大纲项信息

        Raises:
            ResourceNotFoundError: 大纲不存在时抛出
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证UUID格式
            validate_uuid(outline_id)

            outline = self._outlines.get(outline_id)
            if not outline:
                error_msg = f"大纲不存在: {outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="Outline", resource_id=outline_id
                )

            # 验证父级ID
            parent_uuid = None
            if parent_id:
                validate_uuid(parent_id)
                parent_uuid = uuid.UUID(parent_id)
                # 检查父级是否存在
                parent_exists = any(item.id == parent_uuid for item in outline.items)
                if not parent_exists:
                    error_msg = f"父级大纲项不存在: {parent_id}"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)

            # 验证大纲项类型
            try:
                item_type_enum = OutlineItemType(item_type)
            except ValueError:
                error_msg = f"无效的大纲项类型: {item_type}"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            # 创建大纲项
            item = OutlineItem(
                parent_id=parent_uuid,
                item_type=item_type_enum,
                level=level,
                title=title.strip(),
                description=description.strip() if description else None,
                order=order,
            )

            # 添加到大纲
            outline.add_item(item)

            logger.info(
                "添加大纲项成功",
                outline_id=outline_id,
                item_id=str(item.id),
                title=title,
                level=level,
            )

            return {
                "item": item.to_dict(),
                "item_id": str(item.id),
                "outline_id": outline_id,
            }

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"添加大纲项失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def update_outline_item(
        self,
        outline_id: str,
        item_id: str,
        title: str | None = None,
        description: str | None = None,
        order: int | None = None,
    ) -> dict[str, Any]:
        """
        更新大纲项

        Args:
            outline_id: 大纲ID
            item_id: 大纲项ID
            title: 新标题(可选)
            description: 新描述(可选)
            order: 新排序顺序(可选)

        Returns:
            更新后的大纲项信息

        Raises:
            ResourceNotFoundError: 大纲或大纲项不存在时抛出
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证UUID格式
            validate_uuid(outline_id)
            validate_uuid(item_id)

            outline = self._outlines.get(outline_id)
            if not outline:
                error_msg = f"大纲不存在: {outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="Outline", resource_id=outline_id
                )

            # 获取大纲项
            item = outline.get_item(uuid.UUID(item_id))
            if not item:
                error_msg = f"大纲项不存在: {item_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="OutlineItem", resource_id=item_id
                )

            # 更新字段
            if title is not None:
                if not title or not title.strip():
                    error_msg = "大纲项标题不能为空"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)
                item.title = title.strip()

            if description is not None:
                item.description = description.strip() if description else None

            if order is not None:
                item.set_order(order)

            logger.info(
                "更新大纲项成功",
                outline_id=outline_id,
                item_id=item_id,
                updated_fields=[
                    field
                    for field in ["title", "description", "order"]
                    if locals()[field] is not None
                ],
            )

            return {
                "item": item.to_dict(),
                "item_id": item_id,
                "outline_id": outline_id,
            }

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"更新大纲项失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def delete_outline_item(self, outline_id: str, item_id: str) -> bool:
        """
        删除大纲项

        Args:
            outline_id: 大纲ID
            item_id: 大纲项ID

        Returns:
            是否成功删除

        Raises:
            ResourceNotFoundError: 大纲或大纲项不存在时抛出
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证UUID格式
            validate_uuid(outline_id)
            validate_uuid(item_id)

            outline = self._outlines.get(outline_id)
            if not outline:
                error_msg = f"大纲不存在: {outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="Outline", resource_id=outline_id
                )

            # 删除大纲项
            success = outline.remove_item(uuid.UUID(item_id))

            if success:
                logger.info(
                    "删除大纲项成功",
                    outline_id=outline_id,
                    item_id=item_id,
                )
            else:
                logger.warning(
                    "删除大纲项失败",
                    outline_id=outline_id,
                    item_id=item_id,
                )

            return success

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"删除大纲项失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def list_outlines(
        self,
        industry_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        列出大纲

        Args:
            industry_id: 所属行业ID过滤条件(可选)
            status: 状态过滤条件(可选)
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            大纲列表信息
        """
        try:
            # 验证过滤条件
            if industry_id:
                validate_uuid(industry_id)

            if status:
                try:
                    OutlineStatus(status)
                except ValueError:
                    error_msg = f"无效的大纲状态: {status}"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)

            # 过滤大纲
            filtered_outlines = []
            for outline_id, outline in self._outlines.items():
                # 行业过滤
                if industry_id and str(outline.industry_id) != industry_id:
                    continue

                # 状态过滤
                if status and outline.status.value != status:
                    continue

                filtered_outlines.append(
                    {
                        "outline_id": outline_id,
                        "title": outline.title,
                        "description": outline.description,
                        "status": outline.status.value
                        if hasattr(outline.status, "value")
                        else str(outline.status),
                        "total_items": len(outline.items),
                        "current_version": outline.current_version,
                        "created_at": outline.created_at.isoformat(),
                        "updated_at": outline.updated_at.isoformat(),
                    }
                )

            # 分页
            total = len(filtered_outlines)
            outlines = filtered_outlines[offset : offset + limit]

            logger.debug(
                "列出大纲成功",
                total=total,
                returned=len(outlines),
                industry_id=industry_id,
                status=status,
            )

            return {
                "outlines": outlines,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

        except ValidationError:
            raise
        except Exception as e:
            error_msg = f"列出大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def delete_outline(self, outline_id: str) -> bool:
        """
        删除大纲

        Args:
            outline_id: 大纲ID

        Returns:
            是否成功删除

        Raises:
            ResourceNotFoundError: 大纲不存在时抛出
        """
        try:
            # 验证UUID格式
            validate_uuid(outline_id)

            if outline_id not in self._outlines:
                error_msg = f"大纲不存在: {outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="Outline", resource_id=outline_id
                )

            # 删除大纲
            del self._outlines[outline_id]

            logger.info("删除大纲成功", outline_id=outline_id)

            return True

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"删除大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e
