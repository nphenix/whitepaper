#!/usr/bin/env python3
"""
测试数据库初始化脚本（包含迁移）

用于创建测试所需的数据库表，包括行业选择相关的表
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.storage.sqlite.connection import get_connection_manager
from src.shared.config.settings import get_config
from scripts.migration.migration_utils import MigrationManager

def setup_test_database_with_migration():
    """设置测试数据库（包含迁移）"""
    try:
        # 获取配置
        config = get_config()
        # 确保数据库目录存在
        db_path = config.database.sqlite_db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 获取连接管理器
        connection_manager = get_connection_manager()
        
        # 使用迁移管理器运行所有迁移
        migration_manager = MigrationManager(connection_manager.database_path)
        
        # 加载迁移文件
        migrations_dir = project_root / "scripts" / "migration" / "migrations"
        migration_manager.load_migrations_from_directory(migrations_dir)
        
        # 应用所有待应用的迁移
        applied_versions = migration_manager.apply_pending_migrations()
        
        # 检查迁移状态，确认是否所有迁移都已成功应用
        status = migration_manager.get_migration_status()
        
        # 如果有待应用的迁移，说明迁移可能失败了
        if status['pending_count'] > 0:
            print(f"警告: 仍有 {status['pending_count']} 个迁移待应用")
            print(f"已应用的迁移: {status['applied_versions']}")
            print(f"待应用的迁移: {status['pending_versions']}")
            
            # 检查是否有迁移失败（应用列表为空但有待应用的迁移）
            if not applied_versions and status['pending_count'] > 0:
                print("错误: 迁移应用失败，没有成功应用任何迁移")
                return False
        
        print(f"测试数据库初始化成功（包含迁移）")
        print(f"总迁移数: {status['total_migrations']}, 已应用: {status['applied_count']}, 待应用: {status['pending_count']}")
        return True
        
    except Exception as e:
        print(f"测试数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = setup_test_database_with_migration()
    sys.exit(0 if success else 1)