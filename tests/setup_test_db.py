#!/usr/bin/env python3
"""
测试数据库初始化脚本

用于创建测试所需的数据库表
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.storage.sqlite.connection import get_connection_manager
from src.shared.config.settings import get_config

def setup_test_database():
    """设置测试数据库"""
    try:
        # 获取配置
        config = get_config()
        # 确保数据库目录存在
        db_path = config.database.sqlite_db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 获取连接管理器
        connection_manager = get_connection_manager()
        
        # 创建索引进度表
        create_progress_table = """
        CREATE TABLE IF NOT EXISTS indexing_progress (
            id TEXT PRIMARY KEY,
            task_id TEXT UNIQUE NOT NULL,
            knowledge_base_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            current_step TEXT,
            total_steps INTEGER DEFAULT 0,
            completed_steps INTEGER DEFAULT 0,
            progress_percentage REAL DEFAULT 0.0,
            start_time TEXT,
            end_time TEXT,
            duration_seconds REAL,
            error_message TEXT,
            error_traceback TEXT,
            documents_count INTEGER DEFAULT 0,
            nodes_count INTEGER DEFAULT 0,
            chunks_count INTEGER DEFAULT 0,
            vector_indexed_count INTEGER DEFAULT 0,
            bm25_indexed_count INTEGER DEFAULT 0,
            metadata_indexed_count INTEGER DEFAULT 0,
            progress_details TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
        
        # 创建索引步骤表
        create_steps_table = """
        CREATE TABLE IF NOT EXISTS indexing_steps (
            id TEXT PRIMARY KEY,
            progress_id TEXT NOT NULL,
            step_name TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            start_time TEXT,
            end_time TEXT,
            duration_seconds REAL,
            description TEXT,
            details TEXT,
            error_message TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (progress_id) REFERENCES indexing_progress (id) ON DELETE CASCADE
        )
        """
        
        # 创建索引
        create_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_indexing_progress_task_id ON indexing_progress(task_id)",
            "CREATE INDEX IF NOT EXISTS idx_indexing_progress_knowledge_base_id ON indexing_progress(knowledge_base_id)",
            "CREATE INDEX IF NOT EXISTS idx_indexing_progress_status ON indexing_progress(status)",
            "CREATE INDEX IF NOT EXISTS idx_indexing_progress_created_at ON indexing_progress(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_indexing_steps_progress_id ON indexing_steps(progress_id)",
            "CREATE INDEX IF NOT EXISTS idx_indexing_steps_step_name ON indexing_steps(step_name)",
            "CREATE INDEX IF NOT EXISTS idx_indexing_steps_step_order ON indexing_steps(step_order)"
        ]
        
        # 执行创建表的SQL
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 创建表
            cursor.execute(create_progress_table)
            cursor.execute(create_steps_table)
            
            # 创建索引
            for index_sql in create_indexes:
                cursor.execute(index_sql)
            
            conn.commit()
            
        print("测试数据库初始化成功")
        return True
        
    except Exception as e:
        print(f"测试数据库初始化失败: {e}")
        return False

if __name__ == "__main__":
    success = setup_test_database()
    sys.exit(0 if success else 1)