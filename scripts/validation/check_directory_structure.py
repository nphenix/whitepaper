#!/usr/bin/env python3
"""
目录结构检查脚本
验证项目目录结构是否符合plan.md中定义的规范(根据章程P2要求)

生成命令: 手动创建
生成时间: 2025-12-05
来源: .specify/memory/constitution.md P2原则
"""

import sys
from pathlib import Path

# 预期的顶层目录(根据plan.md)
EXPECTED_TOP_LEVEL_DIRS = {
    "src",
    "tests",
    "cli",
    "scripts",
    "docs",
    "specs",
    "data",
    "storage",
}

# src/ 下的预期目录
EXPECTED_SRC_DIRS = {
    "domain",
    "application",
    "interfaces",
    "infrastructure",
    "shared",
}

# application/ 下的预期目录
EXPECTED_APPLICATION_DIRS = {
    "agents",
    "services",
}

# interfaces/ 下的预期目录
EXPECTED_INTERFACES_DIRS = {
    "api",
    "cli",
    "mcp",
}

# 未定义的新目录需要警告
WARN_UNKNOWN_DIRS = True


def check_directory_structure(root_dir: Path) -> tuple[bool, list[str], list[str]]:
    """
    检查目录结构
    返回: (是否通过, 警告列表, 错误列表)
    """
    warnings = []
    errors = []

    # 检查顶层目录
    existing_dirs = {
        d.name for d in root_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    }

    # 检查预期的顶层目录是否存在(可选检查, 某些目录可能还未创建)
    for expected_dir in EXPECTED_TOP_LEVEL_DIRS:
        if expected_dir not in existing_dirs:
            warnings.append(f"预期目录不存在: {expected_dir}/ (可能尚未创建)")

    # 检查src/目录结构
    src_dir = root_dir / "src"
    if src_dir.exists():
        src_dirs = {d.name for d in src_dir.iterdir() if d.is_dir()}

        for expected_dir in EXPECTED_SRC_DIRS:
            if expected_dir not in src_dirs:
                warnings.append(f"预期目录不存在: src/{expected_dir}/ (可能尚未创建)")

        # 检查application/目录
        app_dir = src_dir / "application"
        if app_dir.exists():
            app_dirs = {d.name for d in app_dir.iterdir() if d.is_dir()}
            for expected_dir in EXPECTED_APPLICATION_DIRS:
                if expected_dir not in app_dirs:
                    warnings.append(
                        f"预期目录不存在: src/application/{expected_dir}/ (可能尚未创建)"
                    )

        # 检查interfaces/目录
        interfaces_dir = src_dir / "interfaces"
        if interfaces_dir.exists():
            interfaces_dirs = {d.name for d in interfaces_dir.iterdir() if d.is_dir()}
            for expected_dir in EXPECTED_INTERFACES_DIRS:
                if expected_dir not in interfaces_dirs:
                    warnings.append(
                        f"预期目录不存在: src/interfaces/{expected_dir}/ (可能尚未创建)"
                    )

    # 检查未知的顶层目录(警告)
    if WARN_UNKNOWN_DIRS:
        unknown_dirs = (
            existing_dirs - EXPECTED_TOP_LEVEL_DIRS - {".specify", ".cursor"}
        )  # 排除已知的特殊目录
        for unknown_dir in sorted(unknown_dirs):
            if not unknown_dir.startswith("."):
                warnings.append(
                    f"未知的顶层目录: {unknown_dir}/ (请确认是否符合计划规范)"
                )

    return len(errors) == 0, warnings, errors


def main():
    """主函数"""
    root_dir = Path(__file__).parent.parent.parent

    _passed, warnings, errors = check_directory_structure(root_dir)

    # 输出结果
    print("目录结构检查结果")
    print("=" * 60)

    if errors:
        print("❌ 发现目录结构错误:")
        for error in errors:
            print(f"  - {error}")
        print()

    if warnings:
        print("⚠️  目录结构警告:")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    if not errors and not warnings:
        print("✅ 目录结构符合规范")
        return 0
    elif not errors:
        print("i  目录结构基本符合规范, 但有警告信息")
        return 0
    else:
        print("❌ 目录结构不符合规范")
        print("   请参考 specs/001-multi-agent-doc-system/plan.md 中的项目结构定义")
        return 1


if __name__ == "__main__":
    sys.exit(main())
