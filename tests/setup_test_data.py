#!/usr/bin/env python3
"""
测试数据初始化脚本

用于为测试创建必要的行业和数据库数据
"""

import os
import sys
import uuid
from datetime import datetime, UTC
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.storage.sqlite.connection import get_connection_manager
from src.shared.config.settings import get_config
from src.domain.agent.industry import IndustryCategory
from src.domain.knowledge_base.industry_database import DatabaseType, DataSource

def setup_test_data():
    """设置测试数据"""
    try:
        # 获取配置
        config = get_config()
        # 确保数据库目录存在
        db_path = config.database.sqlite_db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 获取连接管理器
        connection_manager = get_connection_manager()
        
        # 创建测试数据
        now = datetime.now(UTC).isoformat()
        
        # 定义变量（在with语句外部）
        test_industry_id = None
        test_database_id = None
        test_selection = None
        
        # 插入数据（使用迁移中已存在的数据，或插入新的）
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 查询或获取测试行业数据（迁移003已经插入了ENERGY_STORAGE行业）
            cursor.execute("SELECT id FROM industries WHERE code = ?", ("ENERGY_STORAGE",))
            industry_row = cursor.fetchone()
            if industry_row:
                test_industry_id = industry_row[0]
                print(f"使用已存在的行业数据: {test_industry_id}")
            else:
                # 如果不存在，插入新的（这种情况不应该发生，因为迁移已经插入了）
                test_industry_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO industries (id, name, code, category, description, is_active, sort_order, created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    test_industry_id, "储能行业", "ENERGY_STORAGE",
                    IndustryCategory.ENERGY.value, "储能产业相关", True,
                    1, now, now, "{}"
                ))
                print(f"插入新的行业数据: {test_industry_id}")
            
            # 查询或获取测试数据库数据（迁移003已经插入了ENERGY_STORAGE_KB数据库）
            cursor.execute("SELECT id FROM industry_databases WHERE code = ?", ("ENERGY_STORAGE_KB",))
            database_row = cursor.fetchone()
            if database_row:
                test_database_id = database_row[0]
                print(f"使用已存在的数据库数据: {test_database_id}")
            else:
                # 如果不存在，插入新的
                test_database_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO industry_databases (id, name, code, industry_id, database_type, data_source, 
                    description, is_active, is_public, sort_order, documents_count, size_mb, last_updated, 
                    created_at, updated_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    test_database_id, "储能行业知识库", "ENERGY_STORAGE_KB",
                    test_industry_id, DatabaseType.KNOWLEDGE_BASE.value, DataSource.PLATFORM_BUILTIN.value,
                    "储能行业知识库", True, True,
                    1, 100, 50.5,
                    now, now, now, "{}"
                ))
                print(f"插入新的数据库数据: {test_database_id}")
            
            # 插入测试选择记录数据（每次测试都创建新的选择记录）
            test_selection = {
                "id": str(uuid.uuid4()),
                "session_id": str(uuid.uuid4()),
                "industry_id": test_industry_id,
                "database_ids": f'["{test_database_id}"]',
                "selection_name": "测试选择",
                "description": "测试描述",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
                "metadata": "{}",
            }
            
            cursor.execute("""
                INSERT INTO industry_selections (id, session_id, industry_id, database_ids, 
                selection_name, description, is_active, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                test_selection["id"], test_selection["session_id"], test_selection["industry_id"],
                test_selection["database_ids"], test_selection["selection_name"], test_selection["description"],
                test_selection["is_active"], test_selection["created_at"], test_selection["updated_at"],
                test_selection["metadata"]
            ))
            
            conn.commit()
            
        print("测试数据初始化成功")
        print(f"行业ID: {test_industry_id}")
        print(f"数据库ID: {test_database_id}")
        print(f"选择记录ID: {test_selection['id']}")
        
        return True
        
    except Exception as e:
        print(f"测试数据初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = setup_test_data()
    sys.exit(0 if success else 1)