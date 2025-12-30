#!/usr/bin/env python3
"""
行业选择服务测试脚本

用于测试 IndustrySelectionService 的基本功能。
"""

import sys
import os
import uuid
from datetime import UTC, datetime

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.application.services.industry_selection_service import IndustrySelectionService
from src.infrastructure.storage.sqlite.connection import get_connection_manager
from src.domain.agent.industry import Industry, IndustryCategory
from src.domain.knowledge_base.industry_database import (
    IndustryDatabase,
    DatabaseType,
    DataSource,
)


def test_industry_selection_service():
    """测试行业选择服务"""
    print("开始测试行业选择服务...")
    
    # 初始化服务
    connection_manager = get_connection_manager()
    service = IndustrySelectionService(connection_manager)
    
    try:
        # 1. 测试获取行业列表
        print("\n1. 测试获取行业列表...")
        industries = service.get_industries()
        print(f"   获取到 {len(industries)} 个行业")
        for industry in industries:
            print(f"   - {industry['name']} ({industry['code']}) - {industry['category']}")
        
        # 2. 测试根据ID获取行业
        print("\n2. 测试根据ID获取行业...")
        if industries:
            industry_id = industries[0]['id']
            industry = service.get_industry_by_id(industry_id)
            print(f"   获取到行业: {industry['name']} ({industry['code']})")
        
        # 3. 测试根据代码获取行业
        print("\n3. 测试根据代码获取行业...")
        industry_by_code = service.get_industry_by_code("ENERGY")
        print(f"   获取到行业: {industry_by_code['name']} ({industry_by_code['code']})")
        
        # 4. 测试获取储能相关行业
        print("\n4. 测试获取储能相关行业...")
        storage_industries = service.get_storage_industries()
        print(f"   获取到 {len(storage_industries)} 个储能相关行业")
        for industry in storage_industries:
            print(f"   - {industry['name']} ({industry['code']})")
        
        # 5. 测试获取能源相关行业
        print("\n5. 测试获取能源相关行业...")
        energy_industries = service.get_energy_industries()
        print(f"   获取到 {len(energy_industries)} 个能源相关行业")
        for industry in energy_industries:
            print(f"   - {industry['name']} ({industry['code']})")
        
        # 6. 测试获取行业数据库列表
        print("\n6. 测试获取行业数据库列表...")
        if industries:
            industry_id = industries[0]['id']
            databases = service.get_industry_databases(industry_id=industry_id)
            print(f"   获取到 {len(databases)} 个数据库")
            for db in databases:
                print(f"   - {db['name']} ({db['code']}) - {db['database_type']}")
        
        # 7. 测试获取知识库类型数据库
        print("\n7. 测试获取知识库类型数据库...")
        if industries:
            industry_id = industries[0]['id']
            kb_databases = service.get_knowledge_base_databases(industry_id)
            print(f"   获取到 {len(kb_databases)} 个知识库类型数据库")
            for db in kb_databases:
                print(f"   - {db['name']} ({db['code']})")
        
        # 8. 测试获取平台内置数据库
        print("\n8. 测试获取平台内置数据库...")
        if industries:
            industry_id = industries[0]['id']
            builtin_databases = service.get_platform_builtin_databases(industry_id)
            print(f"   获取到 {len(builtin_databases)} 个平台内置数据库")
            for db in builtin_databases:
                print(f"   - {db['name']} ({db['code']})")
        
        # 9. 测试行业统计信息
        print("\n9. 测试获取行业统计信息...")
        if industries:
            industry_id = industries[0]['id']
            stats = service.get_industry_statistics(industry_id)
            print(f"   行业: {stats['industry']['name']}")
            print(f"   总数据库数: {stats['total_databases']}")
            print(f"   活跃数据库数: {stats['active_databases']}")
            print(f"   公开数据库数: {stats['public_databases']}")
        
        # 10. 测试验证行业选择
        print("\n10. 测试验证行业选择...")
        if industries and len(industries) > 0:
            industry_id = industries[0]['id']
            databases = service.get_industry_databases(industry_id=industry_id)
            if databases:
                database_ids = [d['id'] for d in databases[:2]]  # 取前2个数据库
                validation = service.validate_industry_selection(industry_id, database_ids)
                print(f"   验证结果: {'有效' if validation['is_valid'] else '无效'}")
                if validation['errors']:
                    print(f"   错误: {validation['errors']}")
                if validation['warnings']:
                    print(f"   警告: {validation['warnings']}")
        
        print("\n✅ 所有测试通过!")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = test_industry_selection_service()
    sys.exit(0 if success else 1)