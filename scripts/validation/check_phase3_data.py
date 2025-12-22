#!/usr/bin/env python3
"""
阶段3数据产物完整性检查脚本

检查阶段3预处理结果是否满足阶段4知识库构建的需求。
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.parsing.loaders.preprocessed_document_reader import (
    PreprocessedDocumentReader,
)


def check_directory_structure(cleaned_dir: Path) -> Tuple[bool, List[str]]:
    """
    检查目录结构是否符合要求
    
    Args:
        cleaned_dir: 清洗后文档目录路径
        
    Returns:
        (是否通过, 问题列表)
    """
    issues = []
    
    if not cleaned_dir.exists():
        return False, [f"目录不存在: {cleaned_dir}"]
    
    # 查找所有extracted目录
    extracted_dirs = []
    for doc_dir in cleaned_dir.rglob("*_extracted"):
        if doc_dir.is_dir():
            extracted_dirs.append(doc_dir)
    
    if not extracted_dirs:
        return False, [f"未找到任何extracted目录: {cleaned_dir}"]
    
    print(f"✅ 找到 {len(extracted_dirs)} 个extracted目录")
    
    # 检查每个extracted目录
    all_valid = True
    for extracted_dir in extracted_dirs:
        print(f"\n📁 检查目录: {extracted_dir.relative_to(cleaned_dir)}")
        
        # 检查必需文件
        clean_md = extracted_dir / "clean.md"
        if not clean_md.exists():
            issues.append(f"❌ 缺少clean.md: {extracted_dir}")
            all_valid = False
        else:
            size = clean_md.stat().st_size
            if size == 0:
                issues.append(f"⚠️  clean.md为空: {extracted_dir}")
            else:
                print(f"  ✅ clean.md ({size:,} 字节)")
        
        # 检查可选文件
        clean_content_list = extracted_dir / "clean_content_list.json"
        if clean_content_list.exists():
            try:
                with open(clean_content_list, "r", encoding="utf-8") as f:
                    content_list = json.load(f)
                print(f"  ✅ clean_content_list.json ({len(content_list)} 项)")
            except Exception as e:
                issues.append(f"⚠️  clean_content_list.json解析失败: {extracted_dir} - {e}")
        else:
            print(f"  ⚠️  缺少clean_content_list.json (可选)")
        
        # 检查images目录
        images_dir = extracted_dir / "images"
        if images_dir.exists():
            image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
            if image_files:
                print(f"  ✅ images/ ({len(image_files)} 个图片)")
            else:
                print(f"  ⚠️  images/目录为空")
        else:
            print(f"  ⚠️  缺少images/目录 (可选)")
        
        # 检查datajson目录
        datajson_dir = extracted_dir / "datajson"
        if datajson_dir.exists():
            json_files = list(datajson_dir.glob("*.json"))
            if json_files:
                print(f"  ✅ datajson/ ({len(json_files)} 个图表JSON)")
            else:
                print(f"  ⚠️  datajson/目录为空")
        else:
            print(f"  ⚠️  缺少datajson/目录 (可选)")
    
    return all_valid, issues


def check_document_readability(cleaned_dir: Path) -> Tuple[bool, List[str]]:
    """
    检查文档是否可以被PreprocessedDocumentReader读取
    
    Args:
        cleaned_dir: 清洗后文档目录路径
        
    Returns:
        (是否通过, 问题列表)
    """
    issues = []
    
    # 查找所有extracted目录
    extracted_dirs = []
    for doc_dir in cleaned_dir.rglob("*_extracted"):
        if doc_dir.is_dir():
            extracted_dirs.append(doc_dir)
    
    all_valid = True
    for extracted_dir in extracted_dirs:
        try:
            reader = PreprocessedDocumentReader(source=str(extracted_dir))
            documents = reader.load()
            
            if not documents:
                issues.append(f"❌ 无法加载文档: {extracted_dir}")
                all_valid = False
            else:
                doc = documents[0]
                content_length = len(doc.page_content)
                metadata_keys = list(doc.metadata.keys())
                
                print(f"\n✅ 成功读取: {extracted_dir.name}")
                print(f"   - 内容长度: {content_length:,} 字符")
                print(f"   - 元数据字段: {len(metadata_keys)} 个")
                print(f"   - 格式: {doc.metadata.get('format', 'unknown')}")
                
                # 检查关键元数据
                if "source" not in doc.metadata:
                    issues.append(f"⚠️  缺少source元数据: {extracted_dir}")
                if "format" not in doc.metadata:
                    issues.append(f"⚠️  缺少format元数据: {extracted_dir}")
                
        except Exception as e:
            issues.append(f"❌ 读取失败: {extracted_dir} - {e}")
            all_valid = False
    
    return all_valid, issues


def check_data_statistics(cleaned_dir: Path) -> Dict:
    """
    统计数据信息
    
    Args:
        cleaned_dir: 清洗后文档目录路径
        
    Returns:
        统计数据字典
    """
    stats = {
        "total_documents": 0,
        "total_size": 0,
        "total_images": 0,
        "total_charts": 0,
        "formats": {},
    }
    
    # 查找所有extracted目录
    extracted_dirs = []
    for doc_dir in cleaned_dir.rglob("*_extracted"):
        if doc_dir.is_dir():
            extracted_dirs.append(doc_dir)
    
    for extracted_dir in extracted_dirs:
        stats["total_documents"] += 1
        
        # 统计文件大小
        clean_md = extracted_dir / "clean.md"
        if clean_md.exists():
            stats["total_size"] += clean_md.stat().st_size
        
        # 统计图片
        images_dir = extracted_dir / "images"
        if images_dir.exists():
            image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
            stats["total_images"] += len(image_files)
        
        # 统计图表
        datajson_dir = extracted_dir / "datajson"
        if datajson_dir.exists():
            json_files = list(datajson_dir.glob("*.json"))
            stats["total_charts"] += len(json_files)
        
        # 统计格式
        try:
            reader = PreprocessedDocumentReader(source=str(extracted_dir))
            documents = reader.load()
            if documents:
                doc_format = documents[0].metadata.get("format", "unknown")
                stats["formats"][doc_format] = stats["formats"].get(doc_format, 0) + 1
        except:
            pass
    
    return stats


def main():
    """主函数"""
    print("=" * 70)
    print("阶段3数据产物完整性检查")
    print("=" * 70)
    print()
    
    # 获取配置
    from src.shared.config.settings import get_config
    config = get_config()
    # 使用 data_dir 构建 cleaned_dir 路径
    # cleaned_dir 应该在 data_dir/cleaned/documents 下
    data_dir = Path(config.data_dir) if hasattr(config, 'data_dir') else Path("./data")
    cleaned_dir = data_dir / "cleaned" / "documents"
    
    print(f"📁 检查目录: {cleaned_dir}")
    print()
    
    # 1. 检查目录结构
    print("1️⃣  检查目录结构...")
    print("-" * 70)
    structure_valid, structure_issues = check_directory_structure(cleaned_dir)
    
    if structure_issues:
        print("\n⚠️  发现以下问题:")
        for issue in structure_issues:
            print(f"  {issue}")
    
    print()
    
    # 2. 检查文档可读性
    print("2️⃣  检查文档可读性...")
    print("-" * 70)
    readability_valid, readability_issues = check_document_readability(cleaned_dir)
    
    if readability_issues:
        print("\n⚠️  发现以下问题:")
        for issue in readability_issues:
            print(f"  {issue}")
    
    print()
    
    # 3. 统计数据
    print("3️⃣  数据统计...")
    print("-" * 70)
    stats = check_data_statistics(cleaned_dir)
    
    print(f"📊 总文档数: {stats['total_documents']}")
    print(f"📊 总大小: {stats['total_size']:,} 字节 ({stats['total_size'] / 1024 / 1024:.2f} MB)")
    print(f"📊 总图片数: {stats['total_images']}")
    print(f"📊 总图表数: {stats['total_charts']}")
    print(f"📊 格式分布: {stats['formats']}")
    
    print()
    
    # 4. 总结
    print("=" * 70)
    print("📋 检查总结")
    print("=" * 70)
    
    all_valid = structure_valid and readability_valid
    
    if all_valid:
        print("✅ 所有检查通过！阶段3数据产物满足阶段4知识库构建需求。")
        print()
        print("✅ 可以开始阶段4的端到端验证：")
        print("   1. 使用PreprocessedDocumentReader读取文档")
        print("   2. 使用MarkdownParser解析文档")
        print("   3. 使用DocumentChunkingStrategy分块")
        print("   4. 使用EmbeddingGenerator生成向量")
        print("   5. 使用HybridRetriever构建混合检索")
        print("   6. 使用KnowledgeBaseService创建知识库")
        return 0
    else:
        print("❌ 检查未完全通过，请修复以下问题：")
        all_issues = structure_issues + readability_issues
        for i, issue in enumerate(all_issues, 1):
            print(f"   {i}. {issue}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

