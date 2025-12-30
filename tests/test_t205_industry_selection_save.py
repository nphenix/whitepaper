"""
T205任务测试：行业和数据库选择保存功能

该测试文件验证行业和数据库选择保存功能的正确性，包括：
1. 保存行业和数据库选择
2. 获取已保存的选择
3. 更新选择记录
4. 删除选择记录
5. 根据会话ID获取选择列表
"""

# 生成命令: /speckit.implement T205
# 生成时间: 2025-12-23
# 来源: specs/001-multi-agent-doc-system/tasks.md

import json
import uuid
from datetime import UTC, datetime

import pytest

from src.application.services.industry_selection_service import IndustrySelectionService
from src.domain.agent.industry import Industry, IndustryCategory
from src.domain.knowledge_base.industry_database import (
    DatabaseType,
    DataSource,
    IndustryDatabase,
)
from src.infrastructure.storage.sqlite.connection import SQLiteConnectionManager
from src.shared.exceptions.base_exceptions import ResourceNotFoundError, ValidationError


@pytest.fixture
def temp_db():
    """创建临时数据库连接"""
    connection_manager = SQLiteConnectionManager(database_path=":memory:")
    
    # 创建表结构
    with connection_manager.get_connection() as conn:
        # 创建行业表
        conn.execute("""
            CREATE TABLE industries (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                category TEXT CHECK(category IN (
                    'ENERGY', 'TECHNOLOGY', 'MANUFACTURING', 'FINANCE',
                    'HEALTHCARE', 'EDUCATION', 'RETAIL', 'REAL_ESTATE',
                    'TRANSPORTATION', 'AGRICULTURE', 'OTHER'
                )),
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                sort_order INTEGER DEFAULT 0 CHECK(sort_order >= 0),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        
        # 创建行业数据库表
        conn.execute("""
            CREATE TABLE industry_databases (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT UNIQUE NOT NULL,
                industry_id TEXT NOT NULL,
                database_type TEXT CHECK(database_type IN (
                    'KNOWLEDGE_BASE', 'MARKET_DATA', 'POLICY_DATABASE',
                    'TECHNOLOGY_DATABASE', 'INDUSTRY_REPORTS', 'RESEARCH_PAPERS',
                    'NEWS_ARTICLES', 'PATENT_DATABASE', 'OTHER'
                )),
                data_source TEXT CHECK(data_source IN (
                    'PLATFORM_BUILTIN', 'USER_UPLOADED', 'WEB_CRAWLED',
                    'THIRD_PARTY', 'MIXED'
                )),
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                is_public BOOLEAN DEFAULT TRUE,
                sort_order INTEGER DEFAULT 0 CHECK(sort_order >= 0),
                documents_count INTEGER DEFAULT 0 CHECK(documents_count >= 0),
                size_mb REAL DEFAULT 0.0 CHECK(size_mb >= 0),
                last_updated TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE CASCADE
            )
        """)
        
        # 创建行业选择记录表
        conn.execute("""
            CREATE TABLE industry_selections (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                industry_id TEXT NOT NULL,
                database_ids TEXT NOT NULL,
                selection_name TEXT,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE CASCADE
            )
        """)
        
        # 插入测试数据
        now = datetime.now(UTC).isoformat()
        
        # 插入行业数据
        industry_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO industries (id, name, code, category, description, is_active, sort_order, created_at, updated_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            industry_id, "储能行业", "ENERGY_STORAGE", "ENERGY",
            "储能行业包括电池储能、抽水蓄能、压缩空气储能等各种储能技术及相关应用",
            True, 1, now, now, "{}"
        ))
        
        # 插入数据库数据
        db_id1 = str(uuid.uuid4())
        db_id2 = str(uuid.uuid4())
        db_id3 = str(uuid.uuid4())
        
        databases = [
            (db_id1, "储能行业知识库", "ENERGY_STORAGE_KB", industry_id, "KNOWLEDGE_BASE", "PLATFORM_BUILTIN",
             "储能行业知识库包含储能技术、市场、政策等相关文档和数据", True, True, 1, 0, 0.0, None, now, now, "{}"),
            (db_id2, "储能行业市场数据库", "ENERGY_STORAGE_MARKET", industry_id, "MARKET_DATA", "PLATFORM_BUILTIN",
             "储能行业市场数据库包含市场规模、价格趋势、竞争格局等市场数据", True, True, 2, 0, 0.0, None, now, now, "{}"),
            (db_id3, "储能行业政策数据库", "ENERGY_STORAGE_POLICY", industry_id, "POLICY_DATABASE", "PLATFORM_BUILTIN",
             "储能行业政策数据库包含国家政策、地方政策、行业标准等政策信息", True, True, 3, 0, 0.0, None, now, now, "{}"),
        ]
        
        conn.executemany("""
            INSERT INTO industry_databases (
                id, name, code, industry_id, database_type, data_source, description,
                is_active, is_public, sort_order, documents_count, size_mb, last_updated,
                created_at, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, databases)
        
        conn.commit()
    
    yield connection_manager
    
    # 清理
    connection_manager.close()


@pytest.fixture
def industry_service(temp_db):
    """创建行业选择服务实例"""
    return IndustrySelectionService(connection_manager=temp_db)


class TestIndustrySelectionSave:
    """行业选择保存功能测试"""
    
    def test_save_industry_selection_success(self, industry_service):
        """测试成功保存行业和数据库选择"""
        # 获取测试数据
        industries = industry_service.get_industries()
        assert len(industries) >= 1
        
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        assert len(databases) >= 2
        
        # 选择前两个数据库
        selected_db_ids = [databases[0]["id"], databases[1]["id"]]
        
        # 保存选择
        result = industry_service.save_industry_selection(
            session_id="test_session_001",
            industry_id=industry["id"],
            database_ids=selected_db_ids,
            selection_name="测试选择",
            description="这是一个测试选择记录"
        )
        
        # 验证结果
        assert "selection" in result
        assert "industry" in result
        assert "databases" in result
        
        selection = result["selection"]
        assert selection["session_id"] == "test_session_001"
        assert selection["industry_id"] == industry["id"]
        assert json.loads(selection["database_ids"]) == selected_db_ids
        assert selection["selection_name"] == "测试选择"
        assert selection["description"] == "这是一个测试选择记录"
        assert selection["is_active"] in (True, 1)
        
        # 验证返回的行业和数据库信息
        assert result["industry"]["id"] == industry["id"]
        assert len(result["databases"]) == 2
        assert [db["id"] for db in result["databases"]] == selected_db_ids
    
    def test_save_industry_selection_without_optional_fields(self, industry_service):
        """测试不提供可选字段时保存行业和数据库选择"""
        # 获取测试数据
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        
        # 保存选择（不提供可选字段）
        result = industry_service.save_industry_selection(
            session_id="test_session_002",
            industry_id=industry["id"],
            database_ids=[databases[0]["id"]]
        )
        
        # 验证结果
        selection = result["selection"]
        assert selection["session_id"] == "test_session_002"
        assert selection["selection_name"] is None
        assert selection["description"] is None
        assert selection["is_active"] in (True, 1)
    
    def test_save_industry_selection_invalid_industry(self, industry_service):
        """测试保存选择时提供无效行业ID"""
        with pytest.raises(ValidationError) as exc_info:
            industry_service.save_industry_selection(
                session_id="test_session_003",
                industry_id=str(uuid.uuid4()),  # 不存在的行业ID
                database_ids=[]
            )
        
        assert "行业不存在" in str(exc_info.value)
    
    def test_save_industry_selection_invalid_database(self, industry_service):
        """测试保存选择时提供无效数据库ID"""
        # 获取测试数据
        industries = industry_service.get_industries()
        industry = industries[0]
        
        with pytest.raises(ValidationError) as exc_info:
            industry_service.save_industry_selection(
                session_id="test_session_004",
                industry_id=industry["id"],
                database_ids=[str(uuid.uuid4())]  # 不存在的数据库ID
            )
        
        assert "数据库不存在" in str(exc_info.value)
    
    def test_save_industry_selection_database_not_belong_to_industry(self, industry_service):
        """测试保存选择时提供不属于指定行业的数据库"""
        # 获取测试数据
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        
        # 创建另一个行业和数据库
        other_industry_id = str(uuid.uuid4())
        with industry_service.industry_adapter.connection_manager.get_connection() as conn:
            now = datetime.now(UTC).isoformat()
            conn.execute("""
                INSERT INTO industries (id, name, code, category, description, is_active, sort_order, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                other_industry_id, "其他行业", "OTHER_INDUSTRY", "OTHER",
                "其他行业描述", True, 2, now, now, "{}"
            ))
            
            other_db_id = str(uuid.uuid4())
            conn.execute("""
                INSERT INTO industry_databases (
                    id, name, code, industry_id, database_type, data_source, description,
                    is_active, is_public, sort_order, documents_count, size_mb, last_updated,
                    created_at, updated_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                other_db_id, "其他行业数据库", "OTHER_DB", other_industry_id, "KNOWLEDGE_BASE", "PLATFORM_BUILTIN",
                "其他行业数据库描述", True, True, 1, 0, 0.0, None, now, now, "{}"
            ))
            conn.commit()
        
        # 尝试保存选择，包含不属于指定行业的数据库
        with pytest.raises(ValidationError) as exc_info:
            industry_service.save_industry_selection(
                session_id="test_session_005",
                industry_id=industry["id"],
                database_ids=[databases[0]["id"], other_db_id]
            )
        
        assert "不属于行业" in str(exc_info.value)


class TestGetIndustrySelection:
    """获取行业选择功能测试"""
    
    def test_get_industry_selection_success(self, industry_service):
        """测试成功获取行业选择记录"""
        # 先保存一个选择记录
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        selected_db_ids = [databases[0]["id"], databases[1]["id"]]
        
        save_result = industry_service.save_industry_selection(
            session_id="test_session_006",
            industry_id=industry["id"],
            database_ids=selected_db_ids,
            selection_name="测试获取"
        )
        
        selection_id = save_result["selection"]["id"]
        
        # 获取选择记录
        result = industry_service.get_industry_selection(selection_id)
        
        # 验证结果
        assert "selection" in result
        assert "industry" in result
        assert "databases" in result
        assert "database_ids" in result
        
        selection = result["selection"]
        assert selection["id"] == selection_id
        assert selection["session_id"] == "test_session_006"
        assert selection["selection_name"] == "测试获取"
        
        # 验证数据库ID列表
        assert result["database_ids"] == selected_db_ids
        assert len(result["databases"]) == 2
        assert [db["id"] for db in result["databases"]] == selected_db_ids
    
    def test_get_industry_selection_not_found(self, industry_service):
        """测试获取不存在的行业选择记录"""
        with pytest.raises(ResourceNotFoundError) as exc_info:
            industry_service.get_industry_selection(str(uuid.uuid4()))
        
        assert "行业选择记录不存在" in str(exc_info.value)
    
    def test_get_industry_selection_invalid_uuid(self, industry_service):
        """测试获取选择记录时提供无效UUID"""
        with pytest.raises(ValidationError) as exc_info:
            industry_service.get_industry_selection("invalid-uuid")
        
        assert "无效的UUID格式" in str(exc_info.value)


class TestGetSelectionsBySession:
    """根据会话ID获取选择列表功能测试"""
    
    def test_get_selections_by_session_success(self, industry_service):
        """测试成功根据会话ID获取选择列表"""
        # 获取测试数据
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        
        session_id = "test_session_007"
        
        # 保存多个选择记录
        selection1 = industry_service.save_industry_selection(
            session_id=session_id,
            industry_id=industry["id"],
            database_ids=[databases[0]["id"]],
            selection_name="选择1"
        )
        
        selection2 = industry_service.save_industry_selection(
            session_id=session_id,
            industry_id=industry["id"],
            database_ids=[databases[1]["id"], databases[2]["id"]],
            selection_name="选择2"
        )
        
        # 获取会话的选择列表
        selections = industry_service.get_selections_by_session(session_id)
        
        # 验证结果
        assert len(selections) == 2
        
        # 验证第一个选择
        sel1 = next(s for s in selections if s["selection"]["selection_name"] == "选择1")
        assert sel1["selection"]["session_id"] == session_id
        assert len(sel1["databases"]) == 1
        assert sel1["databases"][0]["id"] == databases[0]["id"]
        
        # 验证第二个选择
        sel2 = next(s for s in selections if s["selection"]["selection_name"] == "选择2")
        assert sel2["selection"]["session_id"] == session_id
        assert len(sel2["databases"]) == 2
        assert [db["id"] for db in sel2["databases"]] == [databases[1]["id"], databases[2]["id"]]
    
    def test_get_selections_by_session_with_filters(self, industry_service):
        """测试根据会话ID获取选择列表时使用过滤条件"""
        # 获取测试数据
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        
        session_id = "test_session_008"
        
        # 保存选择记录
        selection = industry_service.save_industry_selection(
            session_id=session_id,
            industry_id=industry["id"],
            database_ids=[databases[0]["id"]],
            selection_name="过滤测试"
        )
        
        # 获取活跃的选择
        active_selections = industry_service.get_selections_by_session(
            session_id, is_active=True
        )
        assert len(active_selections) == 1
        assert active_selections[0]["selection"]["is_active"] in (True, 1)
        
        # 获取非活跃的选择
        inactive_selections = industry_service.get_selections_by_session(
            session_id, is_active=False
        )
        assert len(inactive_selections) == 0
    
    def test_get_selections_by_session_empty(self, industry_service):
        """测试获取空会话的选择列表"""
        selections = industry_service.get_selections_by_session("empty_session")
        assert len(selections) == 0


class TestUpdateIndustrySelection:
    """更新行业选择功能测试"""
    
    def test_update_industry_selection_success(self, industry_service):
        """测试成功更新行业选择记录"""
        # 先保存一个选择记录
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        
        save_result = industry_service.save_industry_selection(
            session_id="test_session_009",
            industry_id=industry["id"],
            database_ids=[databases[0]["id"]],
            selection_name="原始选择"
        )
        
        selection_id = save_result["selection"]["id"]
        
        # 更新选择记录
        update_result = industry_service.update_industry_selection(
            selection_id=selection_id,
            database_ids=[databases[1]["id"], databases[2]["id"]],
            selection_name="更新后的选择",
            description="更新后的描述"
        )
        
        # 验证更新结果
        selection = update_result["selection"]
        assert selection["selection_name"] == "更新后的选择"
        assert selection["description"] == "更新后的描述"
        assert json.loads(selection["database_ids"]) == [databases[1]["id"], databases[2]["id"]]
        assert len(update_result["databases"]) == 2
        
        # 验证行业信息未变化
        assert update_result["industry"]["id"] == industry["id"]
    
    def test_update_industry_selection_partial(self, industry_service):
        """测试部分更新行业选择记录"""
        # 先保存一个选择记录
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        
        save_result = industry_service.save_industry_selection(
            session_id="test_session_010",
            industry_id=industry["id"],
            database_ids=[databases[0]["id"]],
            selection_name="原始选择"
        )
        
        selection_id = save_result["selection"]["id"]
        
        # 只更新选择名称
        update_result = industry_service.update_industry_selection(
            selection_id=selection_id,
            selection_name="仅更新名称"
        )
        
        # 验证更新结果
        selection = update_result["selection"]
        assert selection["selection_name"] == "仅更新名称"
        assert json.loads(selection["database_ids"]) == [databases[0]["id"]]  # 未变化
    
    def test_update_industry_selection_not_found(self, industry_service):
        """测试更新不存在的行业选择记录"""
        with pytest.raises(ResourceNotFoundError) as exc_info:
            industry_service.update_industry_selection(
                selection_id=str(uuid.uuid4()),
                selection_name="不存在的选择"
            )
        
        assert "行业选择记录不存在" in str(exc_info.value)
    
    def test_update_industry_selection_invalid_data(self, industry_service):
        """测试更新选择记录时提供无效数据"""
        # 先保存一个选择记录
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        
        save_result = industry_service.save_industry_selection(
            session_id="test_session_011",
            industry_id=industry["id"],
            database_ids=[databases[0]["id"]]
        )
        
        selection_id = save_result["selection"]["id"]
        
        # 尝试更新为无效的数据库ID
        with pytest.raises(ValidationError) as exc_info:
            industry_service.update_industry_selection(
                selection_id=selection_id,
                database_ids=[str(uuid.uuid4())]  # 不存在的数据库ID
            )
        
        assert "数据库不存在" in str(exc_info.value)


class TestDeleteIndustrySelection:
    """删除行业选择功能测试"""
    
    def test_delete_industry_selection_success(self, industry_service):
        """测试成功删除行业选择记录"""
        # 先保存一个选择记录
        industries = industry_service.get_industries()
        industry = industries[0]
        databases = industry_service.get_industry_databases(industry_id=industry["id"])
        
        save_result = industry_service.save_industry_selection(
            session_id="test_session_012",
            industry_id=industry["id"],
            database_ids=[databases[0]["id"]]
        )
        
        selection_id = save_result["selection"]["id"]
        
        # 删除选择记录
        success = industry_service.delete_industry_selection(selection_id)
        assert success is True
        
        # 验证记录已删除
        with pytest.raises(ResourceNotFoundError):
            industry_service.get_industry_selection(selection_id)
    
    def test_delete_industry_selection_not_found(self, industry_service):
        """测试删除不存在的行业选择记录"""
        with pytest.raises(ResourceNotFoundError) as exc_info:
            industry_service.delete_industry_selection(str(uuid.uuid4()))
        
        assert "行业选择记录不存在" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])