"""
行业选择服务

该模块提供行业和行业数据库的管理服务, 支持行业列表获取,数据库列表获取,
行业和数据库选择保存等功能.用于MVP 4步流程中的第一步: 行业和数据库选择.
"""

# 生成命令: /speckit.implement T202
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import uuid
from datetime import UTC, datetime
from typing import Any

from structlog import get_logger

from src.application.services.base_service import BaseService
from src.domain.agent.industry import IndustryCategory
from src.domain.knowledge_base.industry_database import (
    DatabaseType,
    DataSource,
)
from src.shared.exceptions.base_exceptions import (
    ResourceNotFoundError,
    ValidationError,
)
from src.shared.utils.validators import validate_uuid

logger = get_logger()


class IndustrySelectionService(BaseService):
    """
    行业选择服务

    提供行业和行业数据库的管理功能, 包括列表获取,选择保存,数据验证等.
    """

    def get_service_name(self) -> str:
        """
        获取服务名称

        Returns:
            服务名称字符串
        """
        return "industry_selection_service"

    def __init__(self, connection_manager=None):
        """
        初始化行业选择服务

        Args:
            connection_manager: SQLite连接管理器, 如果为None则使用默认连接
        """
        super().__init__(connection_manager)
        self.industry_adapter = self._get_or_create_adapter("industries")
        self.database_adapter = self._get_or_create_adapter("industry_databases")
        self.selection_adapter = self._get_or_create_adapter("industry_selections")

    def get_industries(
        self,
        category: IndustryCategory | None = None,
        is_active: bool | None = None,
        sort_by: str = "sort_order",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        """
        获取行业列表

        Args:
            category: 行业分类过滤条件
            is_active: 激活状态过滤条件
            sort_by: 排序字段
            sort_order: 排序方向(asc/desc)

        Returns:
            行业列表
        """
        try:
            filters = {}
            if category is not None:
                filters["category"] = category.value
            if is_active is not None:
                filters["is_active"] = is_active

            order_clause = f"{sort_by} {sort_order.upper()}"
            industries = self.industry_adapter.list(
                filters=filters, order_by=order_clause
            )

            logger.debug(
                "获取行业列表成功",
                count=len(industries),
                category=category.value if category else None,
                is_active=is_active,
            )
            return industries

        except Exception as e:
            error_msg = f"获取行业列表失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_industry_by_id(self, industry_id: str) -> dict[str, Any]:
        """
        根据ID获取行业

        Args:
            industry_id: 行业ID

        Returns:
            行业信息

        Raises:
            ResourceNotFoundError: 行业不存在时抛出
        """
        def _operation():
            validate_uuid(industry_id)
            return self._get_resource_or_raise(
                self.industry_adapter, industry_id, "Industry"
            )

        return self._execute_with_error_handling(
            _operation,
            "获取行业信息",
            re_raise=(ResourceNotFoundError,),
        )

    def get_industry_by_code(self, code: str) -> dict[str, Any]:
        """
        根据代码获取行业

        Args:
            code: 行业代码

        Returns:
            行业信息

        Raises:
            ResourceNotFoundError: 行业不存在时抛出
        """
        try:
            # 验证代码格式
            if not code or not code.strip():
                error_msg = "行业代码不能为空"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            code = code.strip().upper()
            industry = self.industry_adapter.execute_custom_query(
                "SELECT * FROM industries WHERE code = ? AND is_active = 1",
                (code,),
                fetch_one=True,
            )

            if not industry:
                error_msg = f"行业不存在: {code}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(error_msg, resource_type="Industry", resource_id=code)

            logger.debug("根据代码获取行业信息成功", code=code)
            return industry

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"根据代码获取行业信息失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_industry_databases(
        self,
        industry_id: str | None = None,
        database_type: DatabaseType | None = None,
        data_source: DataSource | None = None,
        is_active: bool | None = None,
        is_public: bool | None = None,
        sort_by: str = "sort_order",
        sort_order: str = "asc",
    ) -> list[dict[str, Any]]:
        """
        获取行业数据库列表

        Args:
            industry_id: 所属行业ID过滤条件
            database_type: 数据库类型过滤条件
            data_source: 数据来源过滤条件
            is_active: 激活状态过滤条件
            is_public: 公开状态过滤条件
            sort_by: 排序字段
            sort_order: 排序方向(asc/desc)

        Returns:
            行业数据库列表
        """
        try:
            filters = {}
            if industry_id:
                validate_uuid(industry_id)
                filters["industry_id"] = industry_id
            if database_type is not None:
                filters["database_type"] = database_type.value
            if data_source is not None:
                filters["data_source"] = data_source.value
            if is_active is not None:
                filters["is_active"] = is_active
            if is_public is not None:
                filters["is_public"] = is_public

            order_clause = f"{sort_by} {sort_order.upper()}"
            databases = self.database_adapter.list(
                filters=filters, order_by=order_clause
            )

            logger.debug(
                "获取行业数据库列表成功",
                count=len(databases),
                industry_id=industry_id,
                database_type=database_type.value if database_type else None,
                data_source=data_source.value if data_source else None,
            )
            return databases

        except Exception as e:
            error_msg = f"获取行业数据库列表失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_database_by_id(self, database_id: str) -> dict[str, Any]:
        """
        根据ID获取行业数据库

        Args:
            database_id: 数据库ID

        Returns:
            数据库信息

        Raises:
            ResourceNotFoundError: 数据库不存在时抛出
        """
        def _operation():
            validate_uuid(database_id)
            return self._get_resource_or_raise(
                self.database_adapter, database_id, "IndustryDatabase"
            )

        return self._execute_with_error_handling(
            _operation,
            "获取行业数据库信息",
            re_raise=(ResourceNotFoundError,),
        )

    def get_database_by_code(self, code: str) -> dict[str, Any]:
        """
        根据代码获取行业数据库

        Args:
            code: 数据库代码

        Returns:
            数据库信息

        Raises:
            ResourceNotFoundError: 数据库不存在时抛出
        """
        try:
            # 验证代码格式
            if not code or not code.strip():
                error_msg = "数据库代码不能为空"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            code = code.strip().upper()
            database = self.database_adapter.execute_custom_query(
                "SELECT * FROM industry_databases WHERE code = ? AND is_active = 1",
                (code,),
                fetch_one=True,
            )

            if not database:
                error_msg = f"行业数据库不存在: {code}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="IndustryDatabase", resource_id=code
                )

            logger.debug("根据代码获取行业数据库信息成功", code=code)
            return database

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"根据代码获取行业数据库信息失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def select_industry_and_databases(
        self,
        industry_id: str,
        database_ids: list[str],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        保存行业和数据库选择

        Args:
            industry_id: 选择的行业ID
            database_ids: 选择的数据库ID列表
            session_id: 会话ID(可选)

        Returns:
            选择结果信息

        Raises:
            ResourceNotFoundError: 行业或数据库不存在时抛出
        """
        try:
            # 验证行业ID
            industry = self.get_industry_by_id(industry_id)

            # 验证数据库ID列表
            selected_databases = []
            for db_id in database_ids:
                database = self.get_database_by_id(db_id)
                # 验证数据库是否属于该行业
                if str(database["industry_id"]) != industry_id:
                    error_msg = f"数据库 {db_id} 不属于行业 {industry_id}"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)
                selected_databases.append(database)

            # 创建选择记录(这里简化处理,实际可能需要保存到专门的选择记录表)
            selection_result = {
                "industry": industry,
                "databases": selected_databases,
                "selection_time": datetime.now(UTC).isoformat(),
                "session_id": session_id,
                "total_databases": len(selected_databases),
            }

            logger.info(
                "行业和数据库选择保存成功",
                industry_id=industry_id,
                database_count=len(selected_databases),
                session_id=session_id,
            )
            return selection_result

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"保存行业和数据库选择失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_storage_industries(self) -> list[dict[str, Any]]:
        """
        获取储能相关行业列表

        Returns:
            储能相关行业列表
        """
        try:
            # 查询包含储能关键词的行业
            storage_keywords = ["储能", "电池", "蓄能", "energy storage", "battery"]
            # 构建安全的参数化查询
            query = """
                SELECT * FROM industries
                WHERE (name LIKE ? OR name LIKE ? OR name LIKE ? OR name LIKE ? OR name LIKE ?)
                AND is_active = 1
                ORDER BY sort_order, name
            """
            params = [f"%{keyword}%" for keyword in storage_keywords]

            industries = self.industry_adapter.execute_custom_query(
                query, params, fetch_all=True
            )

            logger.debug("获取储能相关行业列表成功", count=len(industries))
            return industries

        except Exception as e:
            error_msg = f"获取储能相关行业列表失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_energy_industries(self) -> list[dict[str, Any]]:
        """
        获取能源相关行业列表

        Returns:
            能源相关行业列表
        """
        try:
            # 查询能源分类的行业
            industries = self.industry_adapter.execute_custom_query(
                "SELECT * FROM industries WHERE category = ? AND is_active = 1 ORDER BY sort_order, name",
                (IndustryCategory.ENERGY.value,),
                fetch_all=True,
            )

            logger.debug("获取能源相关行业列表成功", count=len(industries))
            return industries

        except Exception as e:
            error_msg = f"获取能源相关行业列表失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_knowledge_base_databases(self, industry_id: str) -> list[dict[str, Any]]:
        """
        获取知识库类型数据库列表

        Args:
            industry_id: 行业ID

        Returns:
            知识库类型数据库列表
        """
        try:
            validate_uuid(industry_id)

            databases = self.industry_adapter.execute_custom_query(
                "SELECT * FROM industry_databases WHERE industry_id = ? AND database_type = ? AND is_active = 1 ORDER BY sort_order, name",
                (industry_id, DatabaseType.KNOWLEDGE_BASE.value),
                fetch_all=True,
            )

            logger.debug(
                "获取知识库类型数据库列表成功", industry_id=industry_id, count=len(databases)
            )
            return databases

        except Exception as e:
            error_msg = f"获取知识库类型数据库列表失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_platform_builtin_databases(self, industry_id: str) -> list[dict[str, Any]]:
        """
        获取平台内置数据库列表

        Args:
            industry_id: 行业ID

        Returns:
            平台内置数据库列表
        """
        try:
            validate_uuid(industry_id)

            databases = self.industry_adapter.execute_custom_query(
                "SELECT * FROM industry_databases WHERE industry_id = ? AND data_source = ? AND is_active = 1 ORDER BY sort_order, name",
                (industry_id, DataSource.PLATFORM_BUILTIN.value),
                fetch_all=True,
            )

            logger.debug(
                "获取平台内置数据库列表成功",
                industry_id=industry_id,
                count=len(databases),
            )
            return databases

        except Exception as e:
            error_msg = f"获取平台内置数据库列表失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_industry_statistics(self, industry_id: str) -> dict[str, Any]:
        """
        获取行业统计信息

        Args:
            industry_id: 行业ID

        Returns:
            行业统计信息
        """
        try:
            validate_uuid(industry_id)

            # 获取行业基本信息
            industry = self.get_industry_by_id(industry_id)

            # 获取数据库统计
            total_databases = self.database_adapter.count({"industry_id": industry_id})
            active_databases = self.database_adapter.count(
                {"industry_id": industry_id, "is_active": True}
            )
            public_databases = self.database_adapter.count(
                {"industry_id": industry_id, "is_public": True}
            )

            # 按类型统计
            type_stats = {}
            for db_type in DatabaseType:
                count = self.database_adapter.count(
                    {"industry_id": industry_id, "database_type": db_type.value}
                )
                type_stats[db_type.value] = count

            # 按来源统计
            source_stats = {}
            for source in DataSource:
                count = self.database_adapter.count(
                    {"industry_id": industry_id, "data_source": source.value}
                )
                source_stats[source.value] = count

            statistics = {
                "industry": industry,
                "total_databases": total_databases,
                "active_databases": active_databases,
                "public_databases": public_databases,
                "database_type_stats": type_stats,
                "data_source_stats": source_stats,
                "last_updated": datetime.now(UTC).isoformat(),
            }

            logger.debug("获取行业统计信息成功", industry_id=industry_id)
            return statistics

        except Exception as e:
            error_msg = f"获取行业统计信息失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def validate_industry_selection(
        self, industry_id: str, database_ids: list[str]
    ) -> dict[str, Any]:
        """
        验证行业和数据库选择的有效性

        Args:
            industry_id: 行业ID
            database_ids: 数据库ID列表

        Returns:
            验证结果
        """
        try:
            validation_result = {
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "industry": None,
                "databases": [],
            }

            # 验证行业
            try:
                industry = self.get_industry_by_id(industry_id)
                validation_result["industry"] = industry
                if not industry.get("is_active", False):
                    validation_result["warnings"].append("行业已停用")
            except ResourceNotFoundError:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"行业不存在: {industry_id}")
                return validation_result

            # 验证数据库
            for db_id in database_ids:
                try:
                    database = self.get_database_by_id(db_id)
                    if database["industry_id"] != industry_id:
                        validation_result["is_valid"] = False
                        validation_result["errors"].append(
                            f"数据库 {db_id} 不属于行业 {industry_id}"
                        )
                    elif not database.get("is_active", False):
                        validation_result["warnings"].append(f"数据库 {db_id} 已停用")
                    else:
                        validation_result["databases"].append(database)
                except ResourceNotFoundError:
                    validation_result["is_valid"] = False
                    validation_result["errors"].append(f"数据库不存在: {db_id}")

            logger.debug(
                "行业和数据库选择验证完成",
                industry_id=industry_id,
                database_count=len(database_ids),
                is_valid=validation_result["is_valid"],
            )
            return validation_result

        except Exception as e:
            error_msg = f"验证行业和数据库选择失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def save_industry_selection(
        self,
        session_id: str,
        industry_id: str,
        database_ids: list[str],
        selection_name: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        保存行业和数据库选择到数据库

        Args:
            session_id: 会话ID
            industry_id: 选择的行业ID
            database_ids: 选择的数据库ID列表
            selection_name: 选择名称(可选)
            description: 选择描述(可选)

        Returns:
            保存的选择记录信息

        Raises:
            ResourceNotFoundError: 行业或数据库不存在时抛出
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证行业和数据库选择
            validation_result = self.validate_industry_selection(industry_id, database_ids)
            if not validation_result["is_valid"]:
                error_msg = f"行业和数据库选择验证失败: {validation_result['errors']}"
                logger.error(error_msg)
                raise ValidationError(error_msg)

            # 创建选择记录
            import json
            selection_id = str(uuid.uuid4())
            now = datetime.now(UTC).isoformat()

            selection_data = {
                "id": selection_id,
                "session_id": session_id,
                "industry_id": industry_id,
                "database_ids": json.dumps(database_ids),
                "selection_name": selection_name,
                "description": description,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
                "metadata": "{}",
            }

            # 保存到数据库
            self.selection_adapter.create(selection_data)

            # 获取完整的保存记录
            saved_selection = self.selection_adapter.get_by_id(selection_id)

            logger.info(
                "行业和数据库选择保存成功",
                selection_id=selection_id,
                session_id=session_id,
                industry_id=industry_id,
                database_count=len(database_ids),
            )

            return {
                "selection": saved_selection,
                "industry": validation_result["industry"],
                "databases": validation_result["databases"],
            }

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"保存行业和数据库选择失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_industry_selection(self, selection_id: str) -> dict[str, Any]:
        """
        根据ID获取行业选择记录

        Args:
            selection_id: 选择记录ID

        Returns:
            选择记录信息

        Raises:
            ResourceNotFoundError: 选择记录不存在时抛出
        """
        try:
            # 验证UUID格式
            validate_uuid(selection_id)

            selection = self.selection_adapter.get_by_id(selection_id)
            if not selection:
                error_msg = f"行业选择记录不存在: {selection_id}"
                logger.warning(error_msg)
                raise ResourceNotFoundError(
                    error_msg, resource_type="IndustrySelection", resource_id=selection_id
                )

            # 解析数据库ID列表
            import json
            database_ids = json.loads(selection["database_ids"])

            # 获取行业和数据库详细信息
            industry = self.get_industry_by_id(selection["industry_id"])
            databases = []
            for db_id in database_ids:
                try:
                    database = self.get_database_by_id(db_id)
                    databases.append(database)
                except ResourceNotFoundError:
                    logger.warning(f"数据库 {db_id} 不存在,跳过")

            logger.debug("获取行业选择记录成功", selection_id=selection_id)
            return {
                "selection": selection,
                "industry": industry,
                "databases": databases,
                "database_ids": database_ids,
            }

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"获取行业选择记录失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def get_selections_by_session(
        self,
        session_id: str,
        is_active: bool | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[dict[str, Any]]:
        """
        根据会话ID获取行业选择记录列表

        Args:
            session_id: 会话ID
            is_active: 激活状态过滤条件
            sort_by: 排序字段
            sort_order: 排序方向(asc/desc)

        Returns:
            选择记录列表
        """
        try:
            filters = {"session_id": session_id}
            if is_active is not None:
                filters["is_active"] = is_active

            order_clause = f"{sort_by} {sort_order.upper()}"
            selections = self.selection_adapter.list(
                filters=filters, order_by=order_clause
            )

            # 为每个选择记录获取详细信息
            result = []
            import json
            for selection in selections:
                try:
                    database_ids = json.loads(selection["database_ids"])
                    industry = self.get_industry_by_id(selection["industry_id"])

                    databases = []
                    for db_id in database_ids:
                        try:
                            database = self.get_database_by_id(db_id)
                            databases.append(database)
                        except ResourceNotFoundError:
                            logger.warning(f"数据库 {db_id} 不存在,跳过")

                    result.append({
                        "selection": selection,
                        "industry": industry,
                        "databases": databases,
                        "database_ids": database_ids,
                    })
                except Exception as e:
                    logger.warning(f"处理选择记录 {selection['id']} 时出错: {e}")
                    continue

            logger.debug(
                "获取会话行业选择记录列表成功",
                session_id=session_id,
                count=len(result),
            )
            return result

        except Exception as e:
            error_msg = f"获取会话行业选择记录列表失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def update_industry_selection(
        self,
        selection_id: str,
        industry_id: str | None = None,
        database_ids: list[str] | None = None,
        selection_name: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> dict[str, Any]:
        """
        更新行业选择记录

        Args:
            selection_id: 选择记录ID
            industry_id: 新的行业ID(可选)
            database_ids: 新的数据库ID列表(可选)
            selection_name: 新的选择名称(可选)
            description: 新的选择描述(可选)
            is_active: 新的激活状态(可选)

        Returns:
            更新后的选择记录信息

        Raises:
            ResourceNotFoundError: 选择记录不存在时抛出
            ValidationError: 验证失败时抛出
        """
        try:
            # 验证选择记录存在
            existing_selection = self.get_industry_selection(selection_id)

            # 准备更新数据
            update_data = {"updated_at": datetime.now(UTC).isoformat()}

            # 如果提供了新的行业ID或数据库ID,需要验证
            new_industry_id = industry_id if industry_id is not None else existing_selection["industry"]["id"]
            new_database_ids = database_ids if database_ids is not None else existing_selection["database_ids"]

            if industry_id is not None or database_ids is not None:
                validation_result = self.validate_industry_selection(new_industry_id, new_database_ids)
                if not validation_result["is_valid"]:
                    error_msg = f"行业和数据库选择验证失败: {validation_result['errors']}"
                    logger.error(error_msg)
                    raise ValidationError(error_msg)

            # 更新字段
            if industry_id is not None:
                update_data["industry_id"] = industry_id
            if database_ids is not None:
                import json
                update_data["database_ids"] = json.dumps(database_ids)
            if selection_name is not None:
                update_data["selection_name"] = selection_name
            if description is not None:
                update_data["description"] = description
            if is_active is not None:
                update_data["is_active"] = is_active

            # 执行更新
            self.selection_adapter.update(selection_id, update_data)

            # 获取更新后的记录
            updated_selection = self.get_industry_selection(selection_id)

            logger.info(
                "行业选择记录更新成功",
                selection_id=selection_id,
                updated_fields=list(update_data.keys()),
            )

            return updated_selection

        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_msg = f"更新行业选择记录失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e

    def delete_industry_selection(self, selection_id: str) -> bool:
        """
        删除行业选择记录

        Args:
            selection_id: 选择记录ID

        Returns:
            是否成功删除

        Raises:
            ResourceNotFoundError: 选择记录不存在时抛出
        """
        try:
            # 验证选择记录存在
            self.get_industry_selection(selection_id)

            # 删除记录
            success = self.selection_adapter.delete(selection_id)

            if success:
                logger.info("行业选择记录删除成功", selection_id=selection_id)
            else:
                logger.warning("行业选择记录删除失败", selection_id=selection_id)

            return success

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_msg = f"删除行业选择记录失败: {e}"
            logger.error(error_msg)
            raise ValidationError(error_msg) from e
