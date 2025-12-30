#!/usr/bin/env python3
"""
运行行业选择API测试的脚本

这个脚本会：
1. 设置测试数据库（包含迁移）
2. 设置测试数据
3. 运行行业选择API测试
"""

import os
import sys
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    """主函数"""
    print("开始运行行业选择API测试...")
    
    # 1. 设置测试数据库（包含迁移）
    print("\n1. 设置测试数据库...")
    try:
        result = subprocess.run([
            sys.executable, "tests/setup_test_db_with_migration.py"
        ], cwd=project_root, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"设置测试数据库失败: {result.stderr}")
            return False
        print("✓ 测试数据库设置成功")
    except Exception as e:
        print(f"设置测试数据库异常: {e}")
        return False
    
    # 2. 设置测试数据
    print("\n2. 设置测试数据...")
    try:
        result = subprocess.run([
            sys.executable, "tests/setup_test_data.py"
        ], cwd=project_root, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"设置测试数据失败: {result.stderr}")
            return False
        print("✓ 测试数据设置成功")
    except Exception as e:
        print(f"设置测试数据异常: {e}")
        return False
    
    # 3. 运行测试
    print("\n3. 运行行业选择API测试...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/test_t206_industry_selection_api.py", 
            "-v", "--tb=short"
        ], cwd=project_root, capture_output=True, text=True)
        
        print("测试输出:")
        print(result.stdout)
        if result.stderr:
            print("错误输出:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✓ 所有测试通过！")
            return True
        else:
            print(f"✗ 测试失败，返回码: {result.returncode}")
            return False
            
    except Exception as e:
        print(f"运行测试异常: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)