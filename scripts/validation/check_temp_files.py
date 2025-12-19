#!/usr/bin/env python3
"""
临时文件检查脚本
检查仓库中是否存在不应提交的临时文件(根据章程P3要求)

生成命令: 手动创建
生成时间: 2025-12-05
来源: .specify/memory/constitution.md P3原则
"""

import os
import sys
from pathlib import Path

# 临时文件模式(根据章程P3定义)
TEMP_FILE_PATTERNS = {
    "*.tmp",
    "*.temp",
    "debug.log",
    "*.log",  # 但排除 data/logs/ 中的正常日志
    ".DS_Store",
    "Thumbs.db",
    "*.swp",
    "*.swo",
    "*~",
    ".vscode/settings.json",  # IDE配置不应提交
}

# 允许的目录(这些目录中的某些文件类型是正常的)
ALLOWED_DIRS = {
    "data/logs",  # 日志目录中的.log文件是正常的
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
}


def is_temp_file(file_path: Path, root_dir: Path) -> bool:
    """
    判断文件是否为临时文件
    """
    # 检查是否在允许的目录中
    rel_path = file_path.relative_to(root_dir)
    for allowed_dir in ALLOWED_DIRS:
        if str(rel_path).startswith(allowed_dir.replace("\\", "/")):
            return False

    # 检查文件名模式
    file_name = file_path.name

    # 精确匹配
    if file_name in {"debug.log", ".DS_Store", "Thumbs.db"}:
        return True

    # 扩展名匹配
    if file_name.endswith((".tmp", ".temp", ".swp", ".swo")):
        return True

    # 以~结尾的文件
    return bool(file_name.endswith("~"))


def find_temp_files(root_dir: Path) -> list[Path]:
    """查找所有临时文件"""
    temp_files = []

    # 排除的目录(不遍历)
    exclude_dirs = {
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
    }

    for root, dirs, files in os.walk(root_dir):
        # 排除指定目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        for file in files:
            file_path = Path(root) / file
            if is_temp_file(file_path, root_dir):
                temp_files.append(file_path)

    return temp_files


def main():
    """主函数"""
    root_dir = Path(__file__).parent.parent.parent

    # 查找临时文件
    temp_files = find_temp_files(root_dir)

    # 输出结果
    print("临时文件检查结果")
    print("=" * 60)
    print(f"发现的临时文件数: {len(temp_files)}")
    print()

    if temp_files:
        print("❌ 发现不应提交的临时文件:")
        print()
        for file_path in sorted(temp_files):
            rel_path = file_path.relative_to(root_dir)
            print(f"  {rel_path}")
        print()
        print("⚠️  根据章程P3原则,临时文件不得提交到仓库")
        print("   请删除这些文件或将其添加到 .gitignore")
        return 1
    else:
        print("✅ 未发现临时文件")
        return 0


if __name__ == "__main__":
    sys.exit(main())
