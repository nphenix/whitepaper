"""
大纲服务

该模块提供大纲的管理服务, 支持手写大纲输入(文本输入,结构化输入),
大纲查询,大纲更新等功能.用于MVP 4步流程中的第二步: 大纲手写和AI优化.
"""

# 生成命令: /speckit.implement T212
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import json
import uuid
from datetime import UTC, datetime
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
from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
from src.infrastructure.storage.sqlite.connection import get_connection_manager
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
        
        # 初始化数据库适配器
        self._cm = connection_manager or get_connection_manager()
        self.outline_adapter = SQLiteAdapter(
            table_name="outlines",
            connection_manager=self._cm,
            id_field="id",
        )
        
        # 尝试初始化大纲项表（如果不存在则创建）
        self._init_outline_items_table()
        
        self.outline_item_adapter = SQLiteAdapter(
            table_name="outline_items",
            connection_manager=self._cm,
            id_field="id",
        )

    def _init_outline_items_table(self) -> None:
        """初始化大纲项表"""
        try:
            with self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS outline_items (
                        id TEXT PRIMARY KEY,
                        outline_id TEXT NOT NULL,
                        parent_id TEXT,
                        item_type TEXT NOT NULL,
                        level INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        order_index INTEGER DEFAULT 0,
                        is_optimized INTEGER DEFAULT 0,
                        original_title TEXT,
                        original_description TEXT,
                        optimization_suggestions TEXT DEFAULT '[]',
                        metadata TEXT DEFAULT '{}',
                        created_at TEXT,
                        updated_at TEXT,
                        FOREIGN KEY (outline_id) REFERENCES outlines(id),
                        FOREIGN KEY (parent_id) REFERENCES outline_items(id)
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_outline_items_outline_id ON outline_items (outline_id)")
                conn.commit()
                logger.debug("大纲项表初始化成功")
        except Exception as e:
            logger.warning("初始化大纲项表失败: %s, 将使用兼容模式", e)

    def _ensure_outlines_table(self) -> None:
        """确保outlines表存在"""
        try:
            with self._cm.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS outlines (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        description TEXT,
                        industry_id TEXT,
                        database_ids TEXT DEFAULT '[]',
                        status TEXT DEFAULT 'DRAFT',
                        current_version INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        metadata TEXT DEFAULT '{}',
                        items_json TEXT DEFAULT '[]'
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.warning("确保outlines表存在失败: %s", e)

    def _save_outline_to_db(self, outline: Outline) -> None:
        """
        保存大纲到数据库

        Args:
            outline: 大纲对象
        """
        self._ensure_outlines_table()
        
        now = datetime.now(UTC).isoformat()
        outline_data = {
            "id": str(outline.id),
            "title": outline.title,
            "description": outline.description or "",
            "industry_id": str(outline.industry_id),
            "database_ids": json.dumps([str(db_id) for db_id in outline.database_ids]),
            "status": outline.status.value if hasattr(outline.status, "value") else str(outline.status),
            "current_version": outline.current_version,
            "created_at": outline.created_at.isoformat() if outline.created_at else now,
            "updated_at": now,
            "metadata": json.dumps(outline.metadata),
            "items_json": json.dumps([item.model_dump() for item in outline.items]),
        }
        
        # 检查是否已存在
        existing = self.outline_adapter.get_by_id(str(outline.id))
        if existing:
            self.outline_adapter.update(str(outline.id), outline_data)
        else:
            self.outline_adapter.create(outline_data)
        
        logger.debug("保存大纲到数据库成功", outline_id=str(outline.id))

    def _load_outline_from_db(self, outline_id: str) -> Outline | None:
        """
        从数据库加载大纲

        Args:
            outline_id: 大纲ID

        Returns:
            大纲对象，如果不存在则返回None
        """
        self._ensure_outlines_table()
        
        try:
            outline_data = self.outline_adapter.get_by_id(outline_id)
            if not outline_data:
                return None
            
            # 解析items_json
            items_json = outline_data.get("items_json", "[]")
            if isinstance(items_str := items_json, str):
                try:
                    items_data = json.loads(items_str)
                except json.JSONDecodeError:
                    items_data = []
            else:
                items_data = items_json
            
            # 解析database_ids
            database_ids_json = outline_data.get("database_ids", "[]")
            if isinstance(db_ids_str := database_ids_json, str):
                try:
                    database_ids = [uuid.UUID(db_id) for db_id in json.loads(db_ids_str)]
                except json.JSONDecodeError:
                    database_ids = []
            else:
                database_ids = [uuid.UUID(db_id) for db_id in database_ids_json]
            
            # 解析metadata
            metadata_json = outline_data.get("metadata", "{}")
            if isinstance(metadata_str := metadata_json, str):
                try:
                    metadata = json.loads(metadata_str)
                except json.JSONDecodeError:
                    metadata = {}
            else:
                metadata = metadata_json
            
            # 解析status
            status_value = outline_data.get("status", "DRAFT")
            try:
                status = OutlineStatus(status_value)
            except ValueError:
                status = OutlineStatus.DRAFT
            
            # 创建Outline对象
            outline = Outline(
                id=uuid.UUID(outline_data["id"]),
                title=outline_data["title"],
                description=outline_data.get("description"),
                industry_id=uuid.UUID(outline_data["industry_id"]),
                database_ids=database_ids,
                status=status,
                current_version=outline_data.get("current_version", 1),
                metadata=metadata,
            )
            
            # 还原items
            if items_data:
                outline.items = [OutlineItem(**item) for item in items_data]
            
            logger.debug("从数据库加载大纲成功", outline_id=outline_id)
            return outline
            
        except Exception as e:
            logger.error("从数据库加载大纲失败: %s", e, exc_info=True)
            return None

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

            # 保存到数据库
            self._save_outline_to_db(outline)

            # 创建初始版本
            outline.create_version(OutlineStatus.DRAFT, "从文本创建大纲")

            # 获取outline_id用于返回结果
            outline_id = str(outline.id)

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

            # 保存到数据库
            self._save_outline_to_db(outline)

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

            outline = self._load_outline_from_db(outline_id)
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

            outline = self._load_outline_from_db(outline_id)
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

            outline = self._load_outline_from_db(outline_id)
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

            # 保存到数据库
            self._save_outline_to_db(outline)

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

            outline = self._load_outline_from_db(outline_id)
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

            # 保存到数据库
            self._save_outline_to_db(outline)

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

    def list_outlines(
        self,
        industry_id: str | None = None,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        列出大纲

        Args:
            industry_id: 行业ID过滤(可选)
            status: 状态过滤(可选)
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            大纲列表和分页信息

        Raises:
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证行业ID格式
            if industry_id:
                validate_uuid(industry_id)

            # 从数据库获取所有大纲
            self._ensure_outlines_table()
            
            try:
                all_outlines = self.outline_adapter.list()
            except Exception:
                all_outlines = []
            
            # 过滤大纲
            filtered_outlines = []
            for outline_data in all_outlines:
                outline_id = outline_data.get("id")
                
                # 行业过滤
                if industry_id and outline_data.get("industry_id") != industry_id:
                    continue

                # 状态过滤
                if status and outline_data.get("status") != status:
                    continue

                filtered_outlines.append(
                    {
                        "outline_id": outline_id,
                        "title": outline_data.get("title"),
                        "description": outline_data.get("description"),
                        "status": outline_data.get("status"),
                        "total_items": len(json.loads(outline_data.get("items_json", "[]"))),
                        "current_version": outline_data.get("current_version", 1),
                        "created_at": outline_data.get("created_at"),
                        "updated_at": outline_data.get("updated_at"),
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

            # 从数据库加载大纲
            outline = self._load_outline_from_db(outline_id)
            if not outline:
                error_msg = f"大纲不存在: {outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="Outline", resource_id=outline_id
                )

            # 从数据库删除
            self.outline_adapter.delete(outline_id)

            logger.info("删除大纲成功", outline_id=outline_id)

            return True

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"删除大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e
