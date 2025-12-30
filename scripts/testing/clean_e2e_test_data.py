#!/usr/bin/env python3
"""
清理端到端测试数据脚本

用于在运行端到端测试前清理可能影响测试的旧数据。
清理范围：
- 数据库中的测试数据（大纲、草稿、文档记录等）
- 处理后的文件（但保留源文件）
- 输出文件（草稿、报告等）
- 缓存文件
- ChromaDB向量数据（所有集合，确保测试环境干净）

保留：
- 基础配置数据（行业、数据库配置等）
- 源文件（data/source/uploads/）
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
import argparse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.storage.sqlite.connection import get_connection_manager
from src.shared.config.settings import get_config


def clean_database():
    """清理数据库中的测试数据"""
    print("=" * 60)
    print("清理数据库测试数据...")
    print("=" * 60)
    
    try:
        config = get_config()
        connection_manager = get_connection_manager()
        
        with connection_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # 统计清理前的数据量
            # 注意：检查表是否存在，如果不存在则跳过
            tables_to_clean = [
                ("drafts", "草稿"),
                ("outlines", "大纲"),
                ("documents", "文档"),
                ("outline_sources", "大纲来源"),  # 正确的表名
                ("source_selections", "来源选择"),  # 备用表名（如果存在）
            ]
            
            for table_name, display_name in tables_to_clean:
                try:
                    # 检查表是否存在
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,)
                    )
                    if not cursor.fetchone():
                        # 表不存在，跳过
                        continue
                    
                    # 表存在，统计数据量
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count_before = cursor.fetchone()[0]
                    
                    if count_before > 0:
                        cursor.execute(f"DELETE FROM {table_name}")
                        conn.commit()
                        print(f"  ✓ 清理 {display_name} 表: 删除了 {count_before} 条记录")
                    else:
                        print(f"  - {display_name} 表: 无数据需要清理")
                except Exception as e:
                    # 如果查询失败，可能是表不存在或其他错误
                    print(f"  ⚠ {display_name} 表 ({table_name}): 跳过（表可能不存在或查询失败: {e}）")
                    continue
            
            # 清理文档处理任务记录（如果存在）
            try:
                cursor.execute("SELECT COUNT(*) FROM document_processing_tasks")
                count = cursor.fetchone()[0]
                if count > 0:
                    cursor.execute("DELETE FROM document_processing_tasks")
                    conn.commit()
                    print(f"  ✓ 清理文档处理任务: 删除了 {count} 条记录")
            except Exception:
                # 表可能不存在，忽略
                pass
            
            print("  ✓ 数据库清理完成")
            
    except Exception as e:
        print(f"  ✗ 数据库清理失败: {e}")
        return False
    
    return True


def clean_processed_files():
    """清理处理后的文件"""
    print("\n" + "=" * 60)
    print("清理处理后的文件...")
    print("=" * 60)
    
    data_dir = project_root / "data"
    
    # 要清理的目录
    dirs_to_clean = [
        "processed/mineru",  # MinerU处理结果
        "cleaned/documents",  # 清洗后的文档
        "intermediate/checkpoints",  # 检查点
        "intermediate/indexed",  # 索引文件
        "intermediate/parsed",  # 解析文件
        "intermediate/preprocessed",  # 预处理文件
        "output/drafts",  # 草稿输出
        "output/exports",  # 导出文件
        "output/final",  # 最终文件
        "output/reports",  # 报告文件
        "cache/agent_states",  # Agent状态缓存
        "cache/embeddings",  # 嵌入缓存
        "cache/mineru",  # MinerU缓存
        "cache/retrieval",  # 检索缓存
        "temp",  # 临时文件
    ]
    
    for dir_path in dirs_to_clean:
        full_path = data_dir / dir_path
        if full_path.exists():
            try:
                # 删除目录中的所有文件，但保留目录结构
                for item in full_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                print(f"  ✓ 清理 {dir_path}")
            except Exception as e:
                print(f"  ✗ 清理 {dir_path} 失败: {e}")
        else:
            print(f"  - {dir_path}: 目录不存在，跳过")
    
    print("  ✓ 处理后文件清理完成")


def clean_chromadb_test_data():
    """清理ChromaDB中的向量数据
    
    清理所有集合，确保端到端测试从干净状态开始。
    前期的测试数据会导致向量数据不正确，影响测试结果。
    """
    print("\n" + "=" * 60)
    print("清理ChromaDB向量数据...")
    print("=" * 60)
    
    chroma_dir = project_root / "data" / "chroma"
    
    if not chroma_dir.exists():
        print("  - ChromaDB目录不存在，跳过")
        return True
    
    # 统计清理前的集合数量
    collection_dirs = [d for d in chroma_dir.iterdir() if d.is_dir() and d.name != "chroma.sqlite3"]
    collections_before = len(collection_dirs)
    
    if collections_before == 0:
        print("  - ChromaDB中无集合数据，跳过")
        return True
    
    print(f"  - 发现 {collections_before} 个集合需要清理")
    
    # 方式1：通过ChromaDB API删除集合（推荐）
    try:
        from src.infrastructure.storage.chroma.connection import ChromaConnectionManager
        
        connection_manager = ChromaConnectionManager()
        
        # 列出所有集合
        collections = connection_manager.list_collections()
        
        deleted_count = 0
        for collection_name in collections:
            try:
                if connection_manager.delete_collection(collection_name):
                    deleted_count += 1
                    print(f"    ✓ 删除集合: {collection_name}")
                else:
                    print(f"    ✗ 删除集合失败: {collection_name}")
            except Exception as e:
                print(f"    ✗ 删除集合 {collection_name} 时出错: {e}")
        
        if deleted_count > 0:
            print(f"  ✓ 通过API删除了 {deleted_count} 个集合")
        
        # 如果API删除不完整，使用方式2补充清理
        remaining_dirs = [d for d in chroma_dir.iterdir() if d.is_dir() and d.name != "chroma.sqlite3"]
        if remaining_dirs:
            print(f"  - 检测到 {len(remaining_dirs)} 个残留集合目录，使用文件系统清理...")
            for dir_path in remaining_dirs:
                try:
                    shutil.rmtree(dir_path)
                    print(f"    ✓ 删除集合目录: {dir_path.name}")
                except Exception as e:
                    print(f"    ✗ 删除集合目录 {dir_path.name} 失败: {e}")
        
    except Exception as e:
        print(f"  ⚠ 通过API清理失败: {e}")
        print("  - 尝试使用文件系统方式清理...")
        
        # 方式2：直接删除集合目录（备用方案）
        deleted_count = 0
        for dir_path in collection_dirs:
            try:
                shutil.rmtree(dir_path)
                deleted_count += 1
                print(f"    ✓ 删除集合目录: {dir_path.name}")
            except Exception as e:
                print(f"    ✗ 删除集合目录 {dir_path.name} 失败: {e}")
        
        if deleted_count > 0:
            print(f"  ✓ 通过文件系统删除了 {deleted_count} 个集合目录")
    
    # 清理ChromaDB的SQLite数据库（可选，但建议清理以保持一致性）
    chroma_db_file = chroma_dir / "chroma.sqlite3"
    if chroma_db_file.exists():
        try:
            # 注意：删除chroma.sqlite3会清除所有元数据
            # 对于端到端测试，这是可接受的，因为我们需要干净的环境
            chroma_db_file.unlink()
            print("  ✓ 清理ChromaDB元数据文件 (chroma.sqlite3)")
        except Exception as e:
            print(f"  ⚠ 清理ChromaDB元数据文件失败: {e}")
    
    print("  ✓ ChromaDB清理完成")
    return True


def clean_logs():
    """清理日志文件"""
    print("\n" + "=" * 60)
    print("清理日志文件...")
    print("=" * 60)
    
    logs_dir = project_root / "data" / "logs"
    
    if logs_dir.exists():
        try:
            for log_file in logs_dir.glob("*.log"):
                log_file.unlink()
                print(f"  ✓ 删除日志文件: {log_file.name}")
            
            # 清理旧的日志文件（保留最近7天的）
            # 这里简化处理，只清理.log文件
            print("  ✓ 日志文件清理完成")
        except Exception as e:
            print(f"  ✗ 日志文件清理失败: {e}")
    else:
        print("  - 日志目录不存在，跳过")


def preserve_source_files():
    """确保源文件目录存在且包含测试文件"""
    print("\n" + "=" * 60)
    print("检查源文件...")
    print("=" * 60)
    
    uploads_dir = project_root / "data" / "source" / "uploads"
    
    if not uploads_dir.exists():
        uploads_dir.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ 创建源文件目录: {uploads_dir}")
    
    # 检查是否有PDF文件
    pdf_files = list(uploads_dir.glob("*.pdf"))
    if pdf_files:
        print(f"  ✓ 找到 {len(pdf_files)} 个PDF测试文件:")
        for pdf_file in pdf_files:
            print(f"    - {pdf_file.name}")
    else:
        print("  ⚠ 警告: 未找到PDF测试文件")
        print(f"    请将测试PDF文件放入: {uploads_dir}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="端到端测试数据清理脚本")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="不进行交互式确认，直接执行清理（用于 CI/自动化）",
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("端到端测试数据清理脚本")
    print("=" * 60)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"项目根目录: {project_root}")
    print()
    
    # 确认操作
    if not args.yes:
        response = input("是否继续清理测试数据？(y/N): ").strip().lower()
        if response != "y":
            print("操作已取消")
            return
    
    print()
    
    # 执行清理
    success = True
    
    # 1. 清理数据库
    if not clean_database():
        success = False
    
    # 2. 清理处理后的文件
    clean_processed_files()
    
    # 3. 清理ChromaDB向量数据（重要：确保测试环境干净）
    if not clean_chromadb_test_data():
        success = False
    
    # 4. 清理日志
    clean_logs()
    
    # 5. 检查源文件
    preserve_source_files()
    
    # 总结
    print("\n" + "=" * 60)
    if success:
        print("✓ 数据清理完成！")
        print("\n现在可以运行端到端测试了：")
        print("  pytest tests/e2e/test_complete_workflow.py -v")
    else:
        print("⚠ 数据清理完成，但部分操作失败")
        print("请检查错误信息并手动处理")
    print("=" * 60)


if __name__ == "__main__":
    main()
