#!/usr/bin/env python3
"""
运行所有验证检查
整合所有章程验证脚本,用于CI/CD和本地开发

生成命令: 手动创建
生成时间: 2025-12-05
来源: .specify/memory/constitution.md
"""

import subprocess
import sys
from pathlib import Path


def run_script(script_name: str) -> int:
    """运行验证脚本"""
    script_path = Path(__file__).parent / script_name
    if not script_path.exists():
        print(f"❌ 脚本不存在: {script_path}")
        return 1

    print(f"\n{'=' * 60}")
    print(f"运行: {script_name}")
    print("=" * 60)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=Path(__file__).parent.parent.parent,
            check=False,
            shell=False,
        )
        return result.returncode
    except Exception as e:
        print(f"❌ 运行脚本失败: {e}")
        return 1


def main():
    """主函数"""
    print("whitepaper 项目章程验证检查")
    print("=" * 60)
    print("根据 .specify/memory/constitution.md 进行验证")
    print()

    # 定义所有检查脚本
    checks = [
        ("check_file_length.py", "P1: 文件长度检查"),
        ("check_temp_files.py", "P3: 临时文件检查"),
        ("check_directory_structure.py", "P2: 目录结构检查"),
    ]

    results = []
    for script_name, description in checks:
        print(f"\n检查项: {description}")
        exit_code = run_script(script_name)
        results.append((description, exit_code))

    # 汇总结果
    print("\n" + "=" * 60)
    print("检查结果汇总")
    print("=" * 60)

    all_passed = True
    for description, exit_code in results:
        status = "✅ 通过" if exit_code == 0 else "❌ 失败"
        print(f"{status}: {description}")
        if exit_code != 0:
            all_passed = False

    print()
    if all_passed:
        print("✅ 所有检查通过")
        return 0
    else:
        print("❌ 部分检查失败,请修复后重新运行")
        return 1


if __name__ == "__main__":
    sys.exit(main())
