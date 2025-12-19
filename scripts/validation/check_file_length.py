#!/usr/bin/env python3
"""
文件长度检查脚本
检查项目中所有Python源文件是否超过4000行限制(根据章程P1要求)

生成命令: 手动创建
生成时间: 2025-12-05
来源: .specify/memory/constitution.md P1原则
"""

import os
import sys
from pathlib import Path

# 章程要求的文件长度限制
MAX_FILE_LENGTH = 4000

# 排除的目录和文件
EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
    "data",
    "storage",
}

EXCLUDE_FILES = {
    "__init__.py",  # __init__.py 通常很短, 但如果有需要也可以检查
}


def count_lines(file_path: Path) -> int:
    """计算文件行数"""
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except Exception as e:
        print(f"警告: 无法读取文件 {file_path}: {e}", file=sys.stderr)
        return 0


def check_file(file_path: Path) -> tuple[bool, int]:
    """
    检查单个文件
    返回: (是否通过, 行数)
    """
    if file_path.name in EXCLUDE_FILES:
        return True, 0

    lines = count_lines(file_path)
    return lines <= MAX_FILE_LENGTH, lines


def find_python_files(root_dir: Path) -> list[Path]:
    """查找所有Python源文件"""
    python_files = []
    for root, dirs, files in os.walk(root_dir):
        # 排除指定目录
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

        for file in files:
            if file.endswith(".py"):
                file_path = Path(root) / file
                python_files.append(file_path)

    return python_files


def main():
    """主函数"""
    # 从项目根目录开始
    root_dir = Path(__file__).parent.parent.parent

    # 查找所有Python文件
    python_files = find_python_files(root_dir)

    # 检查每个文件
    violations = []
    total_files = 0

    for file_path in python_files:
        total_files += 1
        passed, lines = check_file(file_path)

        if not passed:
            # 计算相对路径以便显示
            rel_path = file_path.relative_to(root_dir)
            violations.append((rel_path, lines))

    # 输出结果
    print("文件长度检查结果")
    print("=" * 60)
    print(f"检查的文件总数: {total_files}")
    print(f"违反限制的文件数: {len(violations)}")
    print()

    if violations:
        print("❌ 发现违反文件长度限制的文件:")
        print()
        for rel_path, lines in sorted(violations, key=lambda x: x[1], reverse=True):
            print(f"  {rel_path}")
            print(f"    行数: {lines} (限制: {MAX_FILE_LENGTH})")
            print(f"    超出: {lines - MAX_FILE_LENGTH} 行")
            print()

        print("⚠️  根据章程P1原则, 单个源文件不得超过 {MAX_FILE_LENGTH} 行")
        print("   请将违规文件拆分为职责清晰的子模块")
        return 1
    else:
        print("✅ 所有文件都符合长度限制")
        return 0


if __name__ == "__main__":
    sys.exit(main())
