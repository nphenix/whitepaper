"""
大纲优化服务

该模块提供大纲优化和用户反馈的管理服务, 支持保存大纲,保存优化后的大纲,
接受/拒绝优化建议等功能.用于MVP 4步流程中的第二步: 大纲手写和AI优化.

新增功能：
- 自动将优化后的大纲保存为MD模板文件
- MD模板作为草稿生成的单一数据源
- 确保生成内容的结构准确性
"""

# 生成命令: /speckit.implement T215
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from structlog import get_logger

from src.application.services.base_service import BaseService
from src.application.services.outline_to_markdown_service import (
    OutlineToMarkdownService,
)
from src.domain.agent.optimized_outline import (
    OptimizedOutline,
)
from src.domain.agent.outline import (
    Outline,
    OutlineItem,
    OutlineItemType,
    OutlineStatus,
)
from src.shared.exceptions.base_exceptions import (
    ResourceNotFoundError,
    ValidationError,
)
from src.shared.utils.validators import validate_uuid

logger = get_logger()


class OutlineOptimizationService(BaseService):
    """
    大纲优化服务

    提供大纲优化和用户反馈的管理功能, 包括大纲保存,优化建议接受/拒绝等.
    """

    def get_service_name(self) -> str:
        """
        获取服务名称

        Returns:
            服务名称字符串
        """
        return "outline_optimization_service"

    def __init__(self, connection_manager=None):
        """
        初始化大纲优化服务

        Args:
            connection_manager: SQLite连接管理器, 如果为None则使用默认连接
        """
        super().__init__(connection_manager)
        # 运行时补齐缺失表（历史数据库可能只初始化了 outlines/optimized_outlines，但缺 outline_items/outline_versions）。
        # 这样即使未执行迁移脚本，也不会在读取/保存大纲时出现 "no such table" 警告。
        self._ensure_outline_item_version_tables_exist()
        self.outline_adapter = self._get_or_create_adapter("outlines")
        # 兼容外键校验:为缺失的行业/数据库提前插入占位数据
        self.industry_adapter = self._get_or_create_adapter("industries")
        self.industry_db_adapter = self._get_or_create_adapter("industry_databases")
        self.outline_item_adapter = self._get_or_create_adapter(
            "outline_items", created_at_field=None, updated_at_field=None
        )
        self.outline_version_adapter = self._get_or_create_adapter(
            "outline_versions", updated_at_field=None
        )
        # 确保 optimized_outlines 表包含 metadata 列（兼容旧表结构）
        self._ensure_optimized_outlines_table_columns()
        self.optimized_outline_adapter = self._get_or_create_adapter("optimized_outlines")
        self.optimized_item_adapter = self._get_or_create_adapter(
            "optimized_outline_items", created_at_field=None, updated_at_field=None
        )
        self.optimization_summary_adapter = self._get_or_create_adapter(
            "optimization_summaries", updated_at_field=None
        )
        # MD模板生成服务
        self.outline_to_markdown_service = OutlineToMarkdownService()

    def _ensure_outline_item_version_tables_exist(self) -> None:
        """
        确保 outline_items / outline_versions 表存在（兼容旧表结构）。

        说明：历史上存在多套 outlines 表结构迁移，且迁移未必被正确执行。
        因此这里采用 CREATE TABLE IF NOT EXISTS 作为自愈兜底。
        """
        from src.infrastructure.storage.sqlite.connection import get_connection_manager

        cm = self._connection_manager or get_connection_manager()
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS outline_items (
                id TEXT PRIMARY KEY,
                outline_id TEXT NOT NULL,
                parent_id TEXT,
                item_type TEXT NOT NULL,
                level INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                order_index INTEGER NOT NULL DEFAULT 0,
                is_optimized BOOLEAN DEFAULT FALSE,
                original_title TEXT,
                original_description TEXT,
                optimization_suggestions TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (outline_id) REFERENCES outlines(id) ON DELETE CASCADE,
                FOREIGN KEY (parent_id) REFERENCES outline_items(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS outline_versions (
                id TEXT PRIMARY KEY,
                outline_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                change_reason TEXT,
                items_snapshot TEXT NOT NULL,
                created_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (outline_id) REFERENCES outlines(id) ON DELETE CASCADE
            );
            """,
            "CREATE INDEX IF NOT EXISTS idx_outline_items_outline_id ON outline_items(outline_id);",
            "CREATE INDEX IF NOT EXISTS idx_outline_items_parent_id ON outline_items(parent_id);",
            "CREATE INDEX IF NOT EXISTS idx_outline_items_level ON outline_items(level);",
            "CREATE INDEX IF NOT EXISTS idx_outline_items_order ON outline_items(order_index);",
            "CREATE INDEX IF NOT EXISTS idx_outline_versions_outline_id ON outline_versions(outline_id);",
            "CREATE INDEX IF NOT EXISTS idx_outline_versions_version_number ON outline_versions(version_number);",
            "CREATE INDEX IF NOT EXISTS idx_outline_versions_created_at ON outline_versions(created_at);",
        ]

        try:
            with cm.get_connection() as conn:
                for stmt in ddl_statements:
                    conn.execute(stmt)
                conn.commit()
        except Exception as e:
            # 不阻断服务初始化；保持旧行为（后续读写时会继续走“缺表兼容”分支）
            logger.warning("运行时补齐 outline_items/outline_versions 表失败: %s", e)

    def _ensure_optimized_outlines_table_columns(self) -> None:
        """
        确保 optimized_outlines 表包含必要的列（兼容旧表结构）
        
        说明：某些列（如 metadata）可能在表创建时不存在，需要运行时添加。
        SQLite 支持 ADD COLUMN，因此可以在运行时做一次轻量级迁移。
        """
        from src.infrastructure.storage.sqlite.connection import get_connection_manager
        
        cm = self._connection_manager or get_connection_manager()
        
        try:
            with cm.get_connection() as conn:
                cursor = conn.cursor()
                # 检查现有列
                cursor.execute("PRAGMA table_info(optimized_outlines)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                
                # 添加缺失的列
                ddl_statements: list[str] = []
                
                if "metadata" not in existing_cols:
                    ddl_statements.append("ALTER TABLE optimized_outlines ADD COLUMN metadata TEXT DEFAULT '{}'")
                
                if "original_outline_id" not in existing_cols:
                    ddl_statements.append("ALTER TABLE optimized_outlines ADD COLUMN original_outline_id TEXT")
                
                if "optimization_status" not in existing_cols:
                    ddl_statements.append("ALTER TABLE optimized_outlines ADD COLUMN optimization_status TEXT DEFAULT 'PENDING'")
                
                if "is_accepted" not in existing_cols:
                    ddl_statements.append("ALTER TABLE optimized_outlines ADD COLUMN is_accepted BOOLEAN DEFAULT FALSE")
                
                if "user_feedback" not in existing_cols:
                    ddl_statements.append("ALTER TABLE optimized_outlines ADD COLUMN user_feedback TEXT")
                
                if "updated_at" not in existing_cols:
                    ddl_statements.append("ALTER TABLE optimized_outlines ADD COLUMN updated_at TEXT")
                
                # 执行 DDL 语句
                for ddl in ddl_statements:
                    cursor.execute(ddl)
                
                if ddl_statements:
                    conn.commit()
                    logger.info(
                        "为 optimized_outlines 表添加了 %d 个缺失的列: %s",
                        len(ddl_statements),
                        [stmt.split("ADD COLUMN")[1].split()[0] for stmt in ddl_statements]
                    )
        except Exception as e:
            # 不阻断服务初始化；保持旧行为
            logger.warning("运行时补齐 optimized_outlines 表列失败: %s", e)

    def save_outline(self, outline: Outline) -> dict[str, Any]:
        """
        保存大纲到数据库

        Args:
            outline: 大纲对象

        Returns:
            保存的大纲信息
        """
        try:
            # 确保关联的行业与数据库存在,避免外键约束失败(测试环境未预置数据)
            self._ensure_industry_exists(str(outline.industry_id))
            self._ensure_databases_exist(
                [str(db_id) for db_id in outline.database_ids],
                str(outline.industry_id),
            )

            # 保存大纲基本信息
            outline_data = {
                "id": str(outline.id),
                "title": outline.title,
                "description": outline.description,
                "industry_id": str(outline.industry_id),
                "database_ids": json.dumps([str(db_id) for db_id in outline.database_ids]),
                "status": outline.status.value if hasattr(outline.status, "value") else outline.status,
                "current_version": outline.current_version,
                "created_at": outline.created_at.isoformat(),
                "updated_at": outline.updated_at.isoformat(),
                "metadata": json.dumps(outline.metadata),
                # SQLite outlines 表存在 NOT NULL 的 structure 字段,存储树形结构 JSON
                # 使用 Outline.build_tree() 生成层级结构并序列化,确保插入/更新时满足约束
                "structure": json.dumps(outline.build_tree()),
            }

            # 兼容旧表结构:如果表有user_id和constraints_id列,提供默认值
            # 使用一个虚拟的UUID作为默认值,因为旧表结构要求这些字段NOT NULL
            # 确保这些默认值引用的记录存在(避免外键约束失败)
            default_user_id = "00000000-0000-0000-0000-000000000001"
            default_constraints_id = "00000000-0000-0000-0000-000000000001"
            
            # 确保默认用户存在
            from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
            from src.infrastructure.storage.sqlite.connection import get_connection_manager
            user_adapter = SQLiteAdapter(
                table_name="users",
                connection_manager=get_connection_manager(),
                id_field="id",
            )
            try:
                existing_user = user_adapter.get_by_id(default_user_id)
                if not existing_user:
                    # 创建默认用户
                    now = datetime.now(UTC).isoformat()
                    user_adapter.create({
                        "id": default_user_id,
                        "username": "default_user",
                        "email": "default@example.com",
                        "created_at": now,
                        "updated_at": now,
                    })
            except Exception as e:
                logger.warning("创建默认用户失败(可能表不存在或已有记录): %s", e)
            
            # 确保默认约束存在
            constraints_adapter = SQLiteAdapter(
                table_name="global_constraints",
                connection_manager=get_connection_manager(),
                id_field="id",
            )
            try:
                existing_constraints = constraints_adapter.get_by_id(default_constraints_id)
                if not existing_constraints:
                    # 创建默认约束
                    now = datetime.now(UTC).isoformat()
                    constraints_adapter.create({
                        "id": default_constraints_id,
                        "user_id": default_user_id,
                        "report_type": "MARKET_RESEARCH",
                        "language": "CHINESE",
                        "target_length": 10000,
                        "created_at": now,
                        "updated_at": now,
                    })
            except Exception as e:
                logger.warning("创建默认约束失败(可能表不存在或已有记录): %s", e)

            # 为了兼容旧表结构,添加默认值
            # 注意:这些值只在表有这些列时才会被使用
            outline_data.setdefault("user_id", default_user_id)
            outline_data.setdefault("constraints_id", default_constraints_id)

            # 检查是否已存在
            existing = self.outline_adapter.get_by_id(str(outline.id))
            if existing:
                # 更新现有记录
                self.outline_adapter.update(str(outline.id), outline_data)
                logger.debug("更新大纲成功", outline_id=str(outline.id))
            else:
                # 创建新记录
                self.outline_adapter.create(outline_data)
                logger.debug("创建大纲成功", outline_id=str(outline.id))

            # 保存大纲项
            # 如果outline_items表不存在，则跳过保存items（可能使用的是旧表结构）
            try:
                for item in outline.items:
                    item_data = {
                        "id": str(item.id),
                        "outline_id": str(outline.id),
                        "parent_id": str(item.parent_id) if item.parent_id else None,
                        "item_type": item.item_type.value if hasattr(item.item_type, "value") else item.item_type,
                        "level": item.level,
                        "title": item.title,
                        "description": item.description,
                        "order_index": item.order,
                        "is_optimized": item.is_optimized,
                        "original_title": item.original_title,
                        "original_description": item.original_description,
                        "optimization_suggestions": json.dumps(item.optimization_suggestions),
                        "metadata": json.dumps(item.metadata),
                    }

                    existing_item = self.outline_item_adapter.get_by_id(str(item.id))
                    if existing_item:
                        self.outline_item_adapter.update(str(item.id), item_data)
                    else:
                        self.outline_item_adapter.create(item_data)
            except Exception as items_error:
                # 如果outline_items表不存在，记录警告但继续执行（至少保证outline主记录被保存）
                error_str = str(items_error)
                # 检查异常链中的所有异常消息
                error_messages = [error_str]
                current_exception = items_error
                while current_exception.__cause__:
                    error_messages.append(str(current_exception.__cause__))
                    current_exception = current_exception.__cause__
                # 合并所有异常消息进行检查
                all_error_text = " ".join(error_messages).lower()
                
                if "no such table" in all_error_text or "outline_items" in all_error_text:
                    logger.warning(
                        "outline_items表不存在，跳过保存大纲项。这可能是正常的（使用旧表结构）。错误: %s",
                        error_str
                    )
                else:
                    # 如果是其他错误，重新抛出
                    raise

            # 保存版本
            # 如果outline_versions表不存在，则跳过保存版本（可能使用的是旧表结构）
            if outline.versions:
                try:
                    for version in outline.versions:
                        version_data = {
                            "id": str(version.id),
                            "outline_id": str(outline.id),
                            "version_number": version.version_number,
                            "status": version.status.value if hasattr(version.status, "value") else version.status,
                            "change_reason": version.change_reason,
                            "items_snapshot": json.dumps(version.items_snapshot),
                            "created_at": version.created_at.isoformat(),
                            "metadata": json.dumps(version.metadata),
                        }

                        existing_version = self.outline_version_adapter.get_by_id(str(version.id))
                        if existing_version:
                            self.outline_version_adapter.update(str(version.id), version_data)
                        else:
                            self.outline_version_adapter.create(version_data)
                except Exception as versions_error:
                    # 如果outline_versions表不存在，记录警告但继续执行
                    error_str = str(versions_error)
                    if "no such table" in error_str.lower() or "outline_versions" in error_str.lower():
                        logger.warning(
                            "outline_versions表不存在，跳过保存版本。这可能是正常的（使用旧表结构）。错误: %s",
                            error_str
                        )
                    else:
                        # 如果是其他错误，重新抛出
                        raise

            logger.info("大纲保存成功", outline_id=str(outline.id), item_count=len(outline.items))
            return outline.to_dict()

        except Exception as e:
            error_msg = f"保存大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def _ensure_industry_exists(self, industry_id: str) -> None:
        """
        确保行业记录存在, 如不存在则插入占位数据以通过外键校验
        """
        existing = self.industry_adapter.get_by_id(industry_id)
        if existing:
            return

        now = datetime.now(UTC).isoformat()
        placeholder = {
            "id": industry_id,
            "name": "默认行业",
            "code": f"IND_{industry_id[:8]}",
            "category": "OTHER",
            "description": None,
            "is_active": True,
            "sort_order": 0,
            "created_at": now,
            "updated_at": now,
            "metadata": {},
        }
        try:
            self.industry_adapter.create(placeholder)
            logger.debug("插入占位行业记录以满足外键", industry_id=industry_id)
        except Exception as e:
            logger.warning("插入占位行业记录失败,可能已被并发写入", error=str(e))

    def _ensure_databases_exist(self, database_ids: list[str], industry_id: str) -> None:
        """
        确保数据库记录存在, 如不存在则插入占位数据以通过外键校验
        """
        now = datetime.now(UTC).isoformat()
        for db_id in database_ids:
            if not db_id:
                continue

            existing = self.industry_db_adapter.get_by_id(db_id)
            if existing:
                continue

            placeholder = {
                "id": db_id,
                "name": "默认数据库",
                "code": f"DB_{db_id[:8]}",
                "industry_id": industry_id,
                "database_type": "KNOWLEDGE_BASE",
                "data_source": "PLATFORM_BUILTIN",
                "description": None,
                "is_active": True,
                "is_public": True,
                "sort_order": 0,
                "documents_count": 0,
                "size_mb": 0.0,
                "last_updated": None,
                "created_at": now,
                "updated_at": now,
                "metadata": {},
            }
            try:
                self.industry_db_adapter.create(placeholder)
                logger.debug(
                    "插入占位数据库记录以满足外键", database_id=db_id, industry_id=industry_id
                )
            except Exception as e:
                logger.warning("插入占位数据库记录失败,可能已被并发写入", error=str(e))

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
        def _operation():
            validate_uuid(outline_id)
            
            # 1. 先尝试从数据库获取
            try:
                outline = self._get_resource_or_raise(
                    self.outline_adapter, outline_id, "Outline"
                )
                # 文件驱动原则：
                # - 若存在对应的模板文件，且数据库记录是“模板影子记录”，则仍以文件内容为准返回。
                template_path = Path(f"data/output/drafts/outline_template_{outline_id}.md")
                if template_path.exists():
                    try:
                        raw_meta = outline.get("metadata", {}) if isinstance(outline, dict) else {}
                        meta = raw_meta
                        if isinstance(raw_meta, str):
                            try:
                                meta = json.loads(raw_meta)
                            except Exception:
                                meta = {}
                        if isinstance(meta, dict) and meta.get("source") in {"template_file", "template_shadow"}:
                            logger.info(
                                "检测到模板影子大纲记录，按文件驱动返回模板内容: outline_id=%s, template=%s",
                                outline_id,
                                template_path,
                            )
                            return self._load_outline_from_template(template_path, outline_id)
                    except Exception:
                        # 元数据解析失败不影响数据库路径
                        pass
            except ResourceNotFoundError:
                # 2. 数据库没有，尝试从文件系统读取大纲模板
                template_path = Path(f"data/output/drafts/outline_template_{outline_id}.md")
                if template_path.exists():
                    logger.info("大纲模板文件存在，从文件系统加载: %s", template_path)
                    payload = self._load_outline_from_template(template_path, outline_id)
                    # 方案B：文件为真，DB放“影子 outline”仅用于外键/关联
                    self._ensure_outline_shadow_record_from_template(payload, template_path)
                    return payload
                else:
                    raise

            # 获取大纲项（如果表不存在，返回空列表）
            items = []
            try:
                items = self.outline_item_adapter.list(filters={"outline_id": outline_id})
            except Exception as items_error:
                # 如果outline_items表不存在，返回空列表（可能使用的是旧表结构）
                error_str = str(items_error)
                error_messages = [error_str]
                current_exception = items_error
                while current_exception.__cause__:
                    error_messages.append(str(current_exception.__cause__))
                    current_exception = current_exception.__cause__
                all_error_text = " ".join(error_messages).lower()
                
                if "no such table" in all_error_text or "outline_items" in all_error_text:
                    logger.warning(
                        "outline_items表不存在，返回空列表。这可能是正常的（使用旧表结构）。错误: %s",
                        error_str
                    )
                    items = []
                else:
                    # 如果是其他错误，重新抛出
                    raise

            # 获取版本（如果表不存在，返回空列表）
            versions = []
            try:
                versions = self.outline_version_adapter.list(filters={"outline_id": outline_id})
            except Exception as versions_error:
                # 如果outline_versions表不存在，返回空列表（可能使用的是旧表结构）
                error_str = str(versions_error)
                error_messages = [error_str]
                current_exception = versions_error
                while current_exception.__cause__:
                    error_messages.append(str(current_exception.__cause__))
                    current_exception = current_exception.__cause__
                all_error_text = " ".join(error_messages).lower()
                
                if "no such table" in all_error_text or "outline_versions" in all_error_text:
                    logger.warning(
                        "outline_versions表不存在，返回空列表。这可能是正常的（使用旧表结构）。错误: %s",
                        error_str
                    )
                    versions = []
                else:
                    # 如果是其他错误，重新抛出
                    raise

            return {
                "outline": outline,
                "items": items,
                "versions": versions,
            }

        return self._execute_with_error_handling(
            _operation,
            "获取大纲",
            re_raise=(ResourceNotFoundError,),
        )

    def _ensure_outline_shadow_record_from_template(
        self, payload: dict[str, Any], template_path: Path
    ) -> None:
        """确保 outlines 表存在“影子 outline”记录（不作为内容来源）

        背景：
        - outlines 可能由文件系统模板驱动（data/output/drafts/outline_template_{id}.md）
        - 但 drafts.outline_id 通常有外键约束 -> outlines(id)
        - 如果 outline 仅存在于文件而未落库，保存草稿会失败（你提供的日志即为此）

        该方法只做最小落库：
        - 仅在 outlines 中缺失该 id 时插入一条记录
        - 使用 SQLiteAdapter 的“按实际列过滤写入”能力，兼容 outlines 表的多版本结构
        - metadata 标记 source=template_shadow，明确 DB 非内容来源
        """
        outline_data = payload.get("outline") or {}
        if not isinstance(outline_data, dict):
            return

        outline_id = str(outline_data.get("id") or "").strip()
        if not outline_id:
            return

        # 已存在则不覆盖（避免覆盖真实 outline）
        existing = self.outline_adapter.get_by_id(outline_id)
        if existing:
            return

        # 解析 industry_id / database_ids（用于可能存在的外键约束）
        industry_id = str(outline_data.get("industry_id") or "00000000-0000-0000-0000-000000000001")
        database_ids_raw = outline_data.get("database_ids") or "[]"
        database_ids: list[str] = []
        if isinstance(database_ids_raw, str):
            try:
                parsed = json.loads(database_ids_raw)
                if isinstance(parsed, list):
                    database_ids = [str(x) for x in parsed if x]
            except Exception:
                database_ids = []
        elif isinstance(database_ids_raw, list):
            database_ids = [str(x) for x in database_ids_raw if x]

        try:
            self._ensure_industry_exists(industry_id)
            self._ensure_databases_exist(database_ids, industry_id)
        except Exception as e:
            # 外键占位创建失败不应静默：否则影子记录落库会失败且更难定位
            logger.warning("创建影子 outline 的外键占位数据失败(将继续尝试落库): %s", e)

        # 兼容旧表结构中可能存在的 user_id/constraints_id NOT NULL 约束
        default_user_id = "00000000-0000-0000-0000-000000000001"
        default_constraints_id = "00000000-0000-0000-0000-000000000001"
        try:
            from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
            from src.infrastructure.storage.sqlite.connection import get_connection_manager

            cm = get_connection_manager()
            user_adapter = SQLiteAdapter(table_name="users", connection_manager=cm, id_field="id", created_at_field="created_at", updated_at_field="updated_at")
            if not user_adapter.get_by_id(default_user_id):
                now = datetime.now(UTC).isoformat()
                try:
                    user_adapter.create(
                        {
                            "id": default_user_id,
                            "username": "default_user",
                            "email": "default@example.com",
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
                except Exception:
                    pass

            constraints_adapter = SQLiteAdapter(table_name="global_constraints", connection_manager=cm, id_field="id", created_at_field="created_at", updated_at_field="updated_at")
            if not constraints_adapter.get_by_id(default_constraints_id):
                now = datetime.now(UTC).isoformat()
                try:
                    constraints_adapter.create(
                        {
                            "id": default_constraints_id,
                            "user_id": default_user_id,
                            "report_type": "MARKET_RESEARCH",
                            "language": "CHINESE",
                            "target_length": 10000,
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
                except Exception:
                    pass
        except Exception:
            # 可能无 users/global_constraints 表；不阻断影子记录写入
            pass

        now = datetime.now(UTC).isoformat()
        raw_structure = outline_data.get("structure")
        if isinstance(raw_structure, str):
            structure_value = raw_structure
        else:
            try:
                structure_value = json.dumps(raw_structure or [])
            except Exception:
                structure_value = "[]"

        # metadata：明确 DB 为影子记录，文件为真
        shadow_meta = {
            "source": "template_shadow",
            "template_path": str(template_path),
        }
        record: dict[str, Any] = {
            "id": outline_id,
            "title": str(outline_data.get("title") or "白皮书草稿"),
            "description": str(outline_data.get("description") or ""),
            "industry_id": industry_id,
            "database_ids": json.dumps(database_ids),
            "status": str(outline_data.get("status") or "DRAFT"),
            "current_version": int(outline_data.get("current_version") or 1),
            "created_at": str(outline_data.get("created_at") or now),
            "updated_at": str(outline_data.get("updated_at") or now),
            "metadata": json.dumps(shadow_meta, ensure_ascii=False),
            # 兼容不同 outlines 表结构
            "items_json": json.dumps(payload.get("items") or [], ensure_ascii=False),
            "structure": structure_value,
            "original_outline_id": outline_id,
            "user_id": default_user_id,
            "constraints_id": default_constraints_id,
        }

        self.outline_adapter.create(record)
        logger.info("已创建 outline 影子记录(用于外键/关联): outline_id=%s", outline_id)

    def _load_outline_from_template(self, template_path: Path, outline_id: str) -> dict[str, Any]:
        """
        从大纲模板文件加载大纲数据
        
        Args:
            template_path: 大纲模板文件路径
            outline_id: 大纲ID
            
        Returns:
            大纲信息字典
        """
        import re
        
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 解析标题（第一行的 ### 和第二行的 ###）
        title = "白皮书草稿"
        subtitle = ""
        
        lines = content.strip().split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith("### "):
                title = line.replace("### ", "").strip()
            elif line.startswith("#### "):
                subtitle = line.replace("#### ", "").strip()
        
        # 解析章节结构（兼容真实模板格式）
        # 你当前模板的典型格式是：
        # - 顶层标题行：### **第一章：xxx**
        # - 列表项：- 1.1 xxx
        # - 递进列表：    - 1.1.1 xxx
        items: list[dict[str, Any]] = []
        order = 0
        current_root_id: str | None = None
        # 记录编号层级的最近节点：depth(点号数) -> item_id
        # depth=1 对应 1.1，depth=2 对应 1.1.1
        last_numbered_id_by_depth: dict[int, str] = {}

        def _cleanup_line(raw: str) -> str:
            """去掉 markdown 标题/粗体/列表前缀，得到可匹配文本。"""
            s = raw.strip()
            # 去掉 markdown 标题前缀
            s = re.sub(r"^#{1,6}\s*", "", s)
            # 先去掉粗体标记（避免把 **xxx** 的首个 * 误删成“列表前缀”）
            s = s.replace("**", "").replace("__", "").strip()
            # 再去掉列表前缀（- / *），要求后面跟空格，避免误伤正文中的 *
            s = re.sub(r"^[-*]\s+", "", s).strip()
            return s

        # 顶层“章/摘要/附录”标题（允许中文/英文冒号）
        root_heading_re = re.compile(
            r"^(第[一二三四五六七八九十]+章[^：:]*(?:综述|概述|分析|展望|建议)?|执行摘要|摘要|附录[^：:]*)[:：](.+)$"
        )
        # 编号项：1.1 / 1.1.1 / 1.1.1.1 ...
        numbered_re = re.compile(r"^(\d+(?:\.\d+){1,5})\s+(.+)$")

        for raw_line in lines:
            if not raw_line or not raw_line.strip():
                continue

            line = _cleanup_line(raw_line)
            if not line:
                continue

            # 1) 顶层标题（章/摘要/附录）
            m_root = root_heading_re.match(line)
            if m_root:
                root_title = f"{m_root.group(1)}：{m_root.group(2).strip()}"
                root_id = str(uuid.uuid4())
                items.append(
                    {
                        "id": root_id,
                        "outline_id": outline_id,
                        "parent_id": None,
                        "item_type": "SECTION",
                        "level": 1,
                        "title": root_title,
                        "description": None,
                        "order_index": order,
                        "is_optimized": False,
                        "original_title": None,
                        "original_description": None,
                        "optimization_suggestions": "[]",
                        "metadata": "{}",
                    }
                )
                order += 1
                current_root_id = root_id
                last_numbered_id_by_depth = {}
                continue

            # 2) 编号项（必须挂在某个 root 下，否则跳过）
            m_num = numbered_re.match(line)
            if m_num and current_root_id:
                num_str = m_num.group(1)
                title_text = m_num.group(2).strip()
                depth = num_str.count(".")  # 1 => 1.1, 2 => 1.1.1 ...
                # 层级：root 是 level=1；1.1 作为 level=2；1.1.1 作为 level=3 ...
                level = min(1 + depth + 0, 6)  # depth=1 -> level=2
                item_type = "SUBSECTION" if level <= 2 else "PARAGRAPH"

                # 父级：depth=1 直接挂 root；depth>1 挂 depth-1 的最近节点
                if depth <= 1:
                    parent_id = current_root_id
                else:
                    parent_id = last_numbered_id_by_depth.get(depth - 1) or current_root_id

                item_id = str(uuid.uuid4())
                items.append(
                    {
                        "id": item_id,
                        "outline_id": outline_id,
                        "parent_id": parent_id,
                        "item_type": item_type,
                        "level": level,
                        "title": f"{num_str} {title_text}",
                        "description": None,
                        "order_index": order,
                        "is_optimized": False,
                        "original_title": None,
                        "original_description": None,
                        "optimization_suggestions": "[]",
                        "metadata": "{}",
                    }
                )
                order += 1
                last_numbered_id_by_depth[depth] = item_id
                # 清理更深层的缓存，避免跨分支错误挂载
                for k in list(last_numbered_id_by_depth.keys()):
                    if k > depth:
                        del last_numbered_id_by_depth[k]
                continue
        
        # 构建结构数据
        structure = []
        for item in items:
            structure.append({
                "id": item["id"],
                "parent_id": item["parent_id"],
                "item_type": item["item_type"],
                "level": item["level"],
                "title": item["title"],
                "order": item["order_index"],
            })
        
        # 返回模拟的大纲数据
        now = datetime.now(UTC).isoformat()
        outline_data = {
            "id": outline_id,
            "title": title,
            "description": subtitle,
            "industry_id": "00000000-0000-0000-0000-000000000001",
            "database_ids": "[]",
            "status": "DRAFT",
            "current_version": 1,
            "created_at": now,
            "updated_at": now,
            "structure": json.dumps(structure),
            "metadata": json.dumps({"source": "template_file", "template_path": str(template_path)}),
        }
        
        logger.info(
            "从模板文件加载大纲成功: outline_id=%s, item_count=%d",
            outline_id,
            len(items)
        )
        
        return {
            "outline": outline_data,
            "items": items,
            "versions": [],
        }

    def save_optimized_outline(self, optimized_outline: OptimizedOutline) -> dict[str, Any]:
        """
        保存优化后的大纲到数据库

        Args:
            optimized_outline: 优化后的大纲对象

        Returns:
            保存的优化后大纲信息
        """
        try:
            # 保存优化后的大纲基本信息
            # 注意：为了兼容旧表结构（使用outline_id）和新表结构（使用original_outline_id），
            # 同时设置两个字段
            original_outline_id_str = str(optimized_outline.original_outline_id)
            optimized_outline_data = {
                "id": str(optimized_outline.id),
                "original_outline_id": original_outline_id_str,
                "outline_id": original_outline_id_str,  # 兼容旧表结构
                # 兼容 001 初始表结构：optimized_outlines.optimized_structure 为 NOT NULL
                # 新表结构(005)没有该列，SQLiteAdapter 会自动过滤不存在的列。
                "optimized_structure": optimized_outline.build_tree(),
                # 兼容旧表结构字段（如存在则写入，不存在则自动过滤）
                "optimization_suggestions": [],
                "applied_suggestions": [],
                "summary_id": str(optimized_outline.summary.id) if optimized_outline.summary else None,
                "is_accepted": optimized_outline.is_accepted,
                "user_feedback": optimized_outline.user_feedback,
                "optimization_status": optimized_outline.optimization_status,
                "created_at": optimized_outline.created_at.isoformat(),
                "updated_at": optimized_outline.updated_at.isoformat(),
                "metadata": json.dumps(optimized_outline.metadata),
            }

            existing = self.optimized_outline_adapter.get_by_id(str(optimized_outline.id))
            if existing:
                self.optimized_outline_adapter.update(str(optimized_outline.id), optimized_outline_data)
                logger.debug("更新优化后大纲成功", optimized_outline_id=str(optimized_outline.id))
            else:
                self.optimized_outline_adapter.create(optimized_outline_data)
                logger.debug("创建优化后大纲成功", optimized_outline_id=str(optimized_outline.id))

            # 保存优化后的大纲项
            try:
                for item in optimized_outline.optimized_items:
                    # 先将优化后的具体大纲项写入 outline_items,方便后续生成最终大纲时查询
                    optimized_outline_item = item.optimized_item
                    outline_item_data = {
                        "id": str(optimized_outline_item.id),
                        "outline_id": str(optimized_outline.original_outline_id),
                        "parent_id": str(optimized_outline_item.parent_id)
                        if optimized_outline_item.parent_id
                        else None,
                        "item_type": optimized_outline_item.item_type.value
                        if hasattr(optimized_outline_item.item_type, "value")
                        else optimized_outline_item.item_type,
                        "level": optimized_outline_item.level,
                        "title": optimized_outline_item.title,
                        "description": optimized_outline_item.description,
                        "order_index": optimized_outline_item.order,
                        "is_optimized": True,
                        "original_title": item.original_item.title if item.original_item else None,
                        "original_description": item.original_item.description if item.original_item else None,
                        "optimization_suggestions": json.dumps(item.optimization_suggestions),
                        "metadata": json.dumps(
                            getattr(optimized_outline_item, "metadata", {}) or {}
                        ),
                    }

                    existing_outline_item = self.outline_item_adapter.get_by_id(
                        str(optimized_outline_item.id)
                    )
                    if existing_outline_item:
                        self.outline_item_adapter.update(
                            str(optimized_outline_item.id), outline_item_data
                        )
                    else:
                        self.outline_item_adapter.create(outline_item_data)

                    item_data = {
                        "id": str(item.id),
                        "optimized_outline_id": str(optimized_outline.id),
                        "original_item_id": str(item.original_item_id) if item.original_item_id else None,
                        "optimized_item_id": str(item.optimized_item.id),
                        "change_type": item.change_type.value if hasattr(item.change_type, "value") else item.change_type,
                        "change_description": item.change_description,
                        "optimization_reason": item.optimization_reason,
                        "optimization_suggestions": json.dumps(item.optimization_suggestions),
                        "is_accepted": item.is_accepted,
                        "user_feedback": item.user_feedback,
                        "metadata": json.dumps(item.metadata),
                    }

                    existing_item = self.optimized_item_adapter.get_by_id(str(item.id))
                    if existing_item:
                        self.optimized_item_adapter.update(str(item.id), item_data)
                    else:
                        self.optimized_item_adapter.create(item_data)
            except Exception as items_error:
                # 兼容旧表结构：如果 outline_items / optimized_outline_items 表不存在，则跳过保存明细
                error_str = str(items_error)
                error_messages = [error_str]
                current_exception = items_error
                while current_exception.__cause__:
                    error_messages.append(str(current_exception.__cause__))
                    current_exception = current_exception.__cause__
                all_error_text = " ".join(error_messages).lower()

                if (
                    "no such table" in all_error_text
                    and ("outline_items" in all_error_text or "optimized_outline_items" in all_error_text)
                ):
                    logger.warning(
                        "优化明细表不存在，已仅保存 optimized_outlines 主记录(兼容旧表结构)。错误: %s",
                        error_str,
                    )
                else:
                    raise

            # 保存优化摘要
            if optimized_outline.summary:
                try:
                    summary_data = {
                        "id": str(optimized_outline.summary.id),
                        "optimized_outline_id": str(optimized_outline.id),
                        "total_changes": optimized_outline.summary.total_changes,
                        "added_items": optimized_outline.summary.added_items,
                        "modified_items": optimized_outline.summary.modified_items,
                        "deleted_items": optimized_outline.summary.deleted_items,
                        "moved_items": optimized_outline.summary.moved_items,
                        "reordered_items": optimized_outline.summary.reordered_items,
                        "merged_items": optimized_outline.summary.merged_items,
                        "split_items": optimized_outline.summary.split_items,
                        "quality_score": optimized_outline.summary.quality_score,
                        "completeness_score": optimized_outline.summary.completeness_score,
                        "coherence_score": optimized_outline.summary.coherence_score,
                        "relevance_score": optimized_outline.summary.relevance_score,
                        "optimization_summary": optimized_outline.summary.optimization_summary,
                        "key_improvements": json.dumps(optimized_outline.summary.key_improvements),
                        "potential_issues": json.dumps(optimized_outline.summary.potential_issues),
                        "created_at": optimized_outline.summary.created_at.isoformat(),
                        "metadata": json.dumps(optimized_outline.summary.metadata),
                    }

                    existing_summary = self.optimization_summary_adapter.get_by_id(str(optimized_outline.summary.id))
                    if existing_summary:
                        self.optimization_summary_adapter.update(str(optimized_outline.summary.id), summary_data)
                    else:
                        self.optimization_summary_adapter.create(summary_data)
                except Exception as summary_error:
                    # 兼容旧表结构：optimization_summaries 表不存在时忽略
                    error_str = str(summary_error)
                    if "no such table" in error_str.lower() and "optimization_summaries" in error_str.lower():
                        logger.warning(
                            "optimization_summaries表不存在，跳过保存优化摘要(兼容旧表结构)。错误: %s",
                            error_str,
                        )
                    else:
                        raise

            logger.info("优化后大纲保存成功", optimized_outline_id=str(optimized_outline.id))
            
            # 生成MD模板文件（新增功能）
            try:
                result = self.outline_to_markdown_service.save_optimized_outline_to_markdown(
                    optimized_outline=optimized_outline,
                )
                
                # 将MD模板路径保存到 metadata 中
                template_path = str(result.template_path)
                metadata = json.loads(optimized_outline.metadata or "{}")
                metadata["markdown_template_path"] = template_path
                metadata["markdown_template_content"] = result.template_content
                metadata["section_blueprints_count"] = len(result.section_blueprints)
                
                # 更新 metadata 到数据库
                self.optimized_outline_adapter.update(
                    str(optimized_outline.id),
                    {"metadata": json.dumps(metadata)}
                )
                
                logger.info(
                    "MD模板生成成功: 路径=%s, 章节数=%d",
                    template_path,
                    len(result.section_blueprints)
                )
            except Exception as md_error:
                # MD模板生成失败不影响主流程，仅记录警告
                logger.warning(
                    "MD模板生成失败（不影响大纲保存）: 错误=%s",
                    md_error
                )
            
            return optimized_outline.to_dict()

        except Exception as e:
            error_msg = f"保存优化后大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_optimized_outline(self, optimized_outline_id: str) -> dict[str, Any]:
        """
        获取优化后的大纲

        Args:
            optimized_outline_id: 优化后大纲ID

        Returns:
            优化后大纲信息

        Raises:
            ResourceNotFoundError: 优化后大纲不存在时抛出
        """
        try:
            validate_uuid(optimized_outline_id)

            optimized_outline = self.optimized_outline_adapter.get_by_id(optimized_outline_id)
            if not optimized_outline:
                error_msg = f"优化后大纲不存在: {optimized_outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="OptimizedOutline", resource_id=optimized_outline_id
                )

            # 获取优化后的大纲项
            try:
                items = self.optimized_item_adapter.list(filters={"optimized_outline_id": optimized_outline_id})
            except Exception as items_error:
                # 兼容旧表结构：optimized_outline_items 表不存在
                error_str = str(items_error)
                if "no such table" in error_str.lower() and "optimized_outline_items" in error_str.lower():
                    logger.warning(
                        "optimized_outline_items表不存在，返回空 items(兼容旧表结构)。错误: %s",
                        error_str,
                    )
                    items = []
                else:
                    raise

            # 获取优化摘要
            summary = None
            if optimized_outline.get("summary_id"):
                try:
                    summary = self.optimization_summary_adapter.get_by_id(optimized_outline["summary_id"])
                except Exception as summary_error:
                    error_str = str(summary_error)
                    if "no such table" in error_str.lower() and "optimization_summaries" in error_str.lower():
                        summary = None
                    else:
                        raise

            # 兼容旧表结构：optimized_outlines 可能只有 outline_id
            if not optimized_outline.get("original_outline_id") and optimized_outline.get("outline_id"):
                optimized_outline["original_outline_id"] = optimized_outline.get("outline_id")

            logger.debug("获取优化后大纲成功", optimized_outline_id=optimized_outline_id)
            return {
                "optimized_outline": optimized_outline,
                "items": items,
                "summary": summary,
            }

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"获取优化后大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def accept_optimization_item(
        self, optimized_outline_id: str, item_id: str, feedback: str | None = None
    ) -> dict[str, Any]:
        """
        接受单个优化项

        Args:
            optimized_outline_id: 优化后大纲ID
            item_id: 优化项ID
            feedback: 用户反馈

        Returns:
            更新后的优化项信息
        """
        try:
            validate_uuid(optimized_outline_id)
            validate_uuid(item_id)

            # 获取优化项
            item = self.optimized_item_adapter.get_by_id(item_id)
            if not item:
                error_msg = f"优化项不存在: {item_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(error_msg, resource_type="OptimizedOutlineItem", resource_id=item_id)

            # 验证优化项属于该优化后大纲
            if item.get("optimized_outline_id") != optimized_outline_id:
                error_msg = f"优化项 {item_id} 不属于优化后大纲 {optimized_outline_id}"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            # 更新优化项
            update_data = {
                "is_accepted": True,
                "user_feedback": feedback.strip() if feedback else "",
            }
            self.optimized_item_adapter.update(item_id, update_data)

            logger.info("接受优化项成功", item_id=item_id, feedback=feedback)
            result = self.optimized_item_adapter.get_by_id(item_id)
            # 确保 is_accepted 是布尔值(SQLite 可能返回整数)
            if result and "is_accepted" in result:
                result["is_accepted"] = bool(result["is_accepted"])
            return result

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"接受优化项失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def reject_optimization_item(
        self, optimized_outline_id: str, item_id: str, feedback: str | None = None
    ) -> dict[str, Any]:
        """
        拒绝单个优化项

        Args:
            optimized_outline_id: 优化后大纲ID
            item_id: 优化项ID
            feedback: 用户反馈

        Returns:
            更新后的优化项信息
        """
        try:
            validate_uuid(optimized_outline_id)
            validate_uuid(item_id)

            # 获取优化项
            item = self.optimized_item_adapter.get_by_id(item_id)
            if not item:
                error_msg = f"优化项不存在: {item_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(error_msg, resource_type="OptimizedOutlineItem", resource_id=item_id)

            # 验证优化项属于该优化后大纲
            if item.get("optimized_outline_id") != optimized_outline_id:
                error_msg = f"优化项 {item_id} 不属于优化后大纲 {optimized_outline_id}"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            # 更新优化项
            update_data = {
                "is_accepted": False,
                "user_feedback": feedback.strip() if feedback else "",
            }
            self.optimized_item_adapter.update(item_id, update_data)

            logger.info("拒绝优化项成功", item_id=item_id, feedback=feedback)
            result = self.optimized_item_adapter.get_by_id(item_id)
            # 确保 is_accepted 是布尔值(SQLite 可能返回整数)
            if result and "is_accepted" in result:
                result["is_accepted"] = bool(result["is_accepted"])
            return result

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"拒绝优化项失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def accept_all_optimizations(
        self, optimized_outline_id: str, feedback: str | None = None
    ) -> dict[str, Any]:
        """
        接受所有优化建议

        Args:
            optimized_outline_id: 优化后大纲ID
            feedback: 用户整体反馈

        Returns:
            更新后的优化后大纲信息
        """
        try:
            validate_uuid(optimized_outline_id)

            # 获取所有优化项
            items = self.optimized_item_adapter.list(filters={"optimized_outline_id": optimized_outline_id})

            # 更新所有优化项
            for item in items:
                self.optimized_item_adapter.update(
                    item["id"], {"is_accepted": True, "user_feedback": None}
                )

            # 更新优化后大纲状态
            update_data = {
                "is_accepted": True,
                "user_feedback": feedback.strip() if feedback else "",
                "optimization_status": "ACCEPTED",
                "updated_at": datetime.now(UTC).isoformat(),
            }
            self.optimized_outline_adapter.update(optimized_outline_id, update_data)

            logger.info("接受所有优化建议成功", optimized_outline_id=optimized_outline_id)
            result = self.optimized_outline_adapter.get_by_id(optimized_outline_id)
            # 确保 is_accepted 是布尔值(SQLite 可能返回整数)
            if result and "is_accepted" in result:
                result["is_accepted"] = bool(result["is_accepted"])
            return result

        except Exception as e:
            error_msg = f"接受所有优化建议失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def reject_all_optimizations(
        self, optimized_outline_id: str, feedback: str | None = None
    ) -> dict[str, Any]:
        """
        拒绝所有优化建议

        Args:
            optimized_outline_id: 优化后大纲ID
            feedback: 用户整体反馈

        Returns:
            更新后的优化后大纲信息
        """
        try:
            validate_uuid(optimized_outline_id)

            # 获取所有优化项
            items = self.optimized_item_adapter.list(filters={"optimized_outline_id": optimized_outline_id})

            # 更新所有优化项
            for item in items:
                self.optimized_item_adapter.update(
                    item["id"], {"is_accepted": False, "user_feedback": None}
                )

            # 更新优化后大纲状态
            update_data = {
                "is_accepted": False,
                "user_feedback": feedback.strip() if feedback else "",
                "optimization_status": "REJECTED",
                "updated_at": datetime.now(UTC).isoformat(),
            }
            self.optimized_outline_adapter.update(optimized_outline_id, update_data)

            logger.info("拒绝所有优化建议成功", optimized_outline_id=optimized_outline_id)
            result = self.optimized_outline_adapter.get_by_id(optimized_outline_id)
            # 确保 is_accepted 是布尔值(SQLite 可能返回整数)
            if result and "is_accepted" in result:
                result["is_accepted"] = bool(result["is_accepted"])
            return result

        except Exception as e:
            error_msg = f"拒绝所有优化建议失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def generate_final_outline(
        self, optimized_outline_id: str, outline_id: str
    ) -> dict[str, Any]:
        """
        根据用户接受/拒绝的优化生成最终大纲

        Args:
            optimized_outline_id: 优化后大纲ID
            outline_id: 原始大纲ID

        Returns:
            最终大纲信息
        """
        try:
            validate_uuid(optimized_outline_id)
            validate_uuid(outline_id)

            # 获取原始大纲
            original_outline_data = self.get_outline(outline_id)
            original_outline_dict = original_outline_data["outline"]
            # 只保留原始大纲项,过滤掉在 outline_items 中标记为 is_optimized 的记录
            original_items = [
                item for item in original_outline_data["items"] if not bool(item.get("is_optimized", False))
            ]

            # 获取优化后的大纲
            optimized_outline_data = self.get_optimized_outline(optimized_outline_id)
            optimized_items = optimized_outline_data["items"]
            is_all_accepted = optimized_outline_data["optimized_outline"].get("optimization_status") == "ACCEPTED"

            # 创建新的大纲对象
            final_outline = Outline(
                title=original_outline_dict["title"],
                description=original_outline_dict.get("description"),
                industry_id=uuid.UUID(original_outline_dict["industry_id"]),
                database_ids=json.loads(original_outline_dict["database_ids"]),
                status=OutlineStatus.ACCEPTED,
            )

            # 构建原始大纲项字典
            original_items_dict = {item["id"]: item for item in original_items}

            # 获取所有优化项的详细信息(从 outline_items 表)
            optimized_item_ids = [item["optimized_item_id"] for item in optimized_items if item.get("optimized_item_id")]
            optimized_items_dict = {}
            if optimized_item_ids:
                for item_id in optimized_item_ids:
                    item_data = self.outline_item_adapter.get_by_id(item_id)
                    if item_data:
                        optimized_items_dict[item_id] = item_data

            # 处理优化项
            processed_item_ids = set()
            added_item_ids = set()
            reparent_map = {}
            removed_item_ids = set()

            for optimized_item in optimized_items:
                optimized_item["id"]
                # 处理 is_accepted 可能是布尔值或整数(0/1)的情况
                is_accepted = bool(optimized_item.get("is_accepted", False))
                change_type = optimized_item.get("change_type", "NONE")
                original_item_id = optimized_item.get("original_item_id")
                optimized_item_db_id = optimized_item.get("optimized_item_id")

                # 从 outline_items 表获取优化项的详细信息
                if not optimized_item_db_id or optimized_item_db_id not in optimized_items_dict:
                    logger.warning(f"优化项 {optimized_item_db_id} 不存在于 outline_items 表中,跳过")
                    continue

                optimized_item_data = optimized_items_dict[optimized_item_db_id]

                # 获取优化后项的OutlineItem
                parent_id_value = None
                if original_item_id and original_item_id in original_items_dict:
                    parent_id_str = original_items_dict[original_item_id].get("parent_id")
                    if parent_id_str:
                        parent_id_value = uuid.UUID(parent_id_str)
                elif optimized_item_data.get("parent_id"):
                    # 如果没有原始项,使用优化项本身的 parent_id
                    parent_id_value = uuid.UUID(optimized_item_data["parent_id"])

                optimized_item_obj = OutlineItem(
                    id=uuid.UUID(optimized_item_data["id"]),
                    parent_id=parent_id_value,
                    item_type=OutlineItemType(optimized_item_data["item_type"]) if isinstance(optimized_item_data.get("item_type"), str) else optimized_item_data.get("item_type"),
                    level=optimized_item_data.get("level", 1),
                    title=optimized_item_data.get("title", ""),
                    description=optimized_item_data.get("description"),
                    order=optimized_item_data.get("order_index", 0),
                )

                if is_accepted:
                    # 接受优化
                    if change_type == "ADD":
                        # 新增项
                        if str(optimized_item_obj.id) not in added_item_ids:
                            final_outline.add_item(optimized_item_obj)
                            added_item_ids.add(str(optimized_item_obj.id))
                    elif change_type in ["MODIFY", "MOVE", "REORDER"]:
                        # 修改/移动/重排项
                        if original_item_id:
                            if str(optimized_item_obj.id) not in added_item_ids:
                                final_outline.add_item(optimized_item_obj)
                                added_item_ids.add(str(optimized_item_obj.id))
                            processed_item_ids.add(original_item_id)
                            # 记录重定向关系, 便于子节点重新挂载到新的父节点
                            reparent_map[original_item_id] = str(optimized_item_obj.id)
                    elif change_type == "DELETE":
                        # 删除项 - 不添加到最终大纲
                        if original_item_id:
                            processed_item_ids.add(original_item_id)
                            removed_item_ids.add(original_item_id)
                else:
                    # 拒绝优化 - 保留原始项
                    if original_item_id and original_item_id in original_items_dict:
                        original_item = original_items_dict[original_item_id]
                        original_outline_item = OutlineItem(
                            id=uuid.UUID(original_item["id"]),
                            parent_id=uuid.UUID(original_item["parent_id"])
                            if original_item["parent_id"]
                            else None,
                            item_type=OutlineItemType(original_item["item_type"]),
                            level=original_item["level"],
                            title=original_item["title"],
                            description=original_item.get("description"),
                            order=original_item["order_index"],
                        )
                        if str(original_outline_item.id) not in added_item_ids:
                            final_outline.add_item(original_outline_item)
                            added_item_ids.add(str(original_outline_item.id))

            # 添加未被优化的原始项
            for item in original_items:
                # 如果父级被删除, 跳过该子项
                if item.get("parent_id") and item["parent_id"] in removed_item_ids:
                    continue

                # 如果整体已接受所有优化,则被替换的父级的子项不再保留
                if (
                    is_all_accepted
                    and item.get("parent_id")
                    and item["parent_id"] in processed_item_ids
                ):
                    continue

                # 已被处理(替换)的节点跳过
                if item["id"] in processed_item_ids:
                    continue

                parent_id_value = None
                if item.get("parent_id"):
                    if item["parent_id"] in reparent_map:
                        parent_id_value = uuid.UUID(reparent_map[item["parent_id"]])
                    else:
                        parent_id_value = uuid.UUID(item["parent_id"])

                original_outline_item = OutlineItem(
                    id=uuid.UUID(item["id"]),
                    parent_id=parent_id_value,
                    item_type=OutlineItemType(item["item_type"]),
                    level=item["level"],
                    title=item["title"],
                    description=item.get("description"),
                    order=item["order_index"],
                )
                if str(original_outline_item.id) not in added_item_ids:
                    final_outline.add_item(original_outline_item)
                    added_item_ids.add(str(original_outline_item.id))

            # 保存最终大纲
            result = self.save_outline(final_outline)

            logger.info("生成最终大纲成功", optimized_outline_id=optimized_outline_id, outline_id=outline_id)
            return result

        except Exception as e:
            error_msg = f"生成最终大纲失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_optimization_history(self, outline_id: str) -> list[dict[str, Any]]:
        """
        获取大纲的优化历史

        Args:
            outline_id: 大纲ID

        Returns:
            优化历史列表
        """
        try:
            validate_uuid(outline_id)

            # 获取所有优化后的大纲
            # 兼容两种表结构：
            # - 新表(005): original_outline_id
            # - 旧表(001): outline_id
            try:
                optimized_outlines = self.optimized_outline_adapter.list(
                    filters={"original_outline_id": outline_id}
                )
            except Exception as e:
                # 检查是否是列不存在的错误
                error_str = str(e)
                error_messages = [error_str]
                current_exception = e
                while current_exception.__cause__:
                    error_messages.append(str(current_exception.__cause__))
                    current_exception = current_exception.__cause__
                all_error_text = " ".join(error_messages).lower()

                # 检查是否是列不存在的错误（兼容多种错误信息格式）
                if ("no such column" in all_error_text and "original_outline_id" in all_error_text) or \
                   ("original_outline_id" in all_error_text and ("列" in all_error_text or "column" in all_error_text.lower())):
                    logger.warning(
                        "optimized_outlines表缺少original_outline_id列，尝试使用 outline_id 查询(兼容旧表结构)。错误: %s",
                        error_str,
                    )
                    try:
                        optimized_outlines = self.optimized_outline_adapter.list(
                            filters={"outline_id": outline_id}
                        )
                    except Exception as fallback_error:
                        logger.error(
                            "使用outline_id查询也失败: %s",
                            fallback_error,
                            exc_info=True,
                        )
                        # 如果使用outline_id也失败，返回空列表（兼容旧表结构）
                        logger.warning("返回空的优化历史列表（兼容旧表结构）")
                        optimized_outlines = []
                else:
                    raise

            # 如果数据库中没有优化历史，检查是否存在大纲模板文件
            if not optimized_outlines:
                template_path = Path(f"data/output/drafts/outline_template_{outline_id}.md")
                if template_path.exists():
                    logger.info("数据库中没有优化历史，从模板文件创建优化历史: %s", template_path)

                    # 从MD模板文件解析实际的大纲结构
                    try:
                        from src.application.services.outline_to_markdown_service import (
                            OutlineToMarkdownService,
                        )
                        md_service = OutlineToMarkdownService()
                        blueprints = md_service.parse_markdown_to_blueprints(template_path)

                        # 将蓝本转换为 optimized_structure 格式
                        optimized_structure = []
                        for bp in blueprints:
                            # 构建节点结构
                            node = {
                                "id": str(uuid.uuid4()),
                                "optimized_item_id": bp.section_id,
                                "item_type": "SECTION",
                                "level": bp.level,
                                "title": bp.title,
                                "description": bp.description or "",
                                "order": bp.order,
                                "change_type": "NONE",
                                "optimization_suggestions": bp.prompt or "",
                                "is_accepted": True,
                                "metadata": {
                                    "min_words": bp.min_words,
                                    "max_words": bp.max_words,
                                    "source": "template_file",
                                },
                            }
                            optimized_structure.append(node)

                        logger.info(
                            "从MD模板解析出大纲结构: 蓝本数=%d, 章节数=%d",
                            len(blueprints),
                            len(optimized_structure)
                        )
                    except Exception as parse_err:
                        logger.warning(
                            "从MD模板解析大纲结构失败，将使用空结构: %s",
                            parse_err
                        )
                        optimized_structure = []

                    # 创建模拟的优化历史（已接受的优化）
                    now = datetime.now(UTC).isoformat()
                    # 使用 outline_id 作为优化后大纲ID的一部分，便于追溯
                    mock_optimized_id = str(uuid.uuid4())
                    optimized_outlines = [{
                        "id": mock_optimized_id,
                        "original_outline_id": outline_id,
                        "outline_id": outline_id,
                        "optimized_structure": optimized_structure,  # 使用解析出的实际结构
                        "optimization_suggestions": [],
                        "applied_suggestions": [],
                        "summary_id": None,
                        "is_accepted": True,
                        "user_feedback": None,
                        "optimization_status": "ACCEPTED",
                        "created_at": now,
                        "updated_at": now,
                        "metadata": json.dumps({
                            "source": "template_file",
                            "from_template": True,
                            "template_path": str(template_path),
                        }),
                    }]

            # 为每个优化后大纲获取详细信息
            history = []
            for optimized_outline in optimized_outlines:
                optimized_outline_id = optimized_outline["id"]
                try:
                    items = self.optimized_item_adapter.list(
                        filters={"optimized_outline_id": optimized_outline_id}
                    )
                except Exception as items_error:
                    error_str = str(items_error)
                    if "no such table" in error_str.lower() and "optimized_outline_items" in error_str.lower():
                        items = []
                    else:
                        raise
                summary = None
                if optimized_outline.get("summary_id"):
                    try:
                        summary = self.optimization_summary_adapter.get_by_id(optimized_outline["summary_id"])
                    except Exception as summary_error:
                        error_str = str(summary_error)
                        if "no such table" in error_str.lower() and "optimization_summaries" in error_str.lower():
                            summary = None
                        else:
                            raise

                # 兼容旧表结构：optimized_outlines 可能只有 outline_id
                if not optimized_outline.get("original_outline_id") and optimized_outline.get("outline_id"):
                    optimized_outline["original_outline_id"] = optimized_outline.get("outline_id")

                # 计算接受统计
                # 处理 is_accepted 可能是布尔值或整数(0/1)的情况
                accepted_count = sum(1 for item in items if bool(item.get("is_accepted", False)))
                rejected_count = len(items) - accepted_count

                history.append({
                    "optimized_outline": optimized_outline,
                    "items": items,
                    "summary": summary,
                    "statistics": {
                        "total_items": len(items),
                        "accepted_count": accepted_count,
                        "rejected_count": rejected_count,
                    },
                })

            logger.debug("获取优化历史成功", outline_id=outline_id, count=len(history))
            return history

        except Exception as e:
            error_msg = f"获取优化历史失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_optimization_status(self, optimized_outline_id: str) -> dict[str, Any]:
        """
        获取优化状态

        Args:
            optimized_outline_id: 优化后大纲ID

        Returns:
            优化状态信息
        """
        try:
            validate_uuid(optimized_outline_id)

            # 获取优化后大纲
            optimized_outline = self.optimized_outline_adapter.get_by_id(optimized_outline_id)
            if not optimized_outline:
                error_msg = f"优化后大纲不存在: {optimized_outline_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="OptimizedOutline", resource_id=optimized_outline_id
                )

            # 获取优化项
            items = self.optimized_item_adapter.list(filters={"optimized_outline_id": optimized_outline_id})

            # 计算统计信息
            total_items = len(items)
            # 处理 is_accepted 可能是布尔值或整数(0/1)的情况
            accepted_items = sum(1 for item in items if bool(item.get("is_accepted", False)))

            # 判断是否整体拒绝(通过 optimized_outline 的 optimization_status)
            is_overall_rejected = optimized_outline.get("optimization_status") == "REJECTED"

            # rejected_items 的计算:
            # 1. 如果整体拒绝,所有未接受的项都算作拒绝
            # 2. 否则,只有明确拒绝的项(is_accepted == False 且 user_feedback 不为空)才算作拒绝
            if is_overall_rejected:
                rejected_items = sum(1 for item in items if not bool(item.get("is_accepted", False)))
            else:
                rejected_items = sum(1 for item in items if not bool(item.get("is_accepted", False)) and item.get("user_feedback"))

            # 待处理项:未接受且未拒绝(is_accepted 为 False 且没有 user_feedback,且 change_type 不为 NONE,且不是整体拒绝状态)
            if is_overall_rejected:
                pending_items = 0
            else:
                pending_items = sum(1 for item in items if not bool(item.get("is_accepted", False)) and not item.get("user_feedback") and item.get("change_type") != "NONE")

            # 按变更类型统计
            change_type_stats = {}
            for item in items:
                change_type = item.get("change_type", "NONE")
                if change_type not in change_type_stats:
                    change_type_stats[change_type] = {"total": 0, "accepted": 0, "rejected": 0}
                change_type_stats[change_type]["total"] += 1
                # 处理 is_accepted 可能是布尔值或整数(0/1)的情况
                if bool(item.get("is_accepted", False)):
                    change_type_stats[change_type]["accepted"] += 1
                else:
                    change_type_stats[change_type]["rejected"] += 1

            status_info = {
                "optimized_outline": optimized_outline,
                "total_items": total_items,
                "accepted_items": accepted_items,
                "rejected_items": rejected_items,
                "pending_items": pending_items,
                "completion_rate": round(accepted_items / total_items * 100, 2) if total_items > 0 else 0,
                "change_type_stats": change_type_stats,
            }

            logger.debug("获取优化状态成功", optimized_outline_id=optimized_outline_id)
            return status_info

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"获取优化状态失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e
