#!/usr/bin/env python
"""
Embedding 配置一致性检查脚本

用途:验证项目中所有 embedding 配置的一致性
确保以 .env 实际配置为准

生成命令: T016 任务配置验证脚本
生成时间: 2025-12-08
"""

import sys
from pathlib import Path

from src.shared.config.settings import get_config

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_embedding_config():
    """检查 embedding 配置一致性"""

    print("=" * 70)
    print("Embedding 配置一致性检查")
    print("=" * 70)
    print()

    # 1. 加载配置
    print("📋 1. 加载项目配置 (.env)")
    print("-" * 70)

    try:
        config = get_config()
        embedding_config = config.embedding

        provider = embedding_config.provider
        model_name = embedding_config.model_name
        dimension = embedding_config.dimension
        batch_size = embedding_config.batch_size
        api_key = embedding_config.api_key

        print(f"✅ Provider:     {provider}")
        print(f"✅ Model:        {model_name}")
        print(f"✅ Dimension:    {dimension}")
        print(f"✅ Batch Size:   {batch_size}")
        print(f"✅ API Key:      {api_key[:10] if api_key else 'NOT_SET'}...")
        print()

    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
        return False

    # 2. 验证阿里百炼 text-embedding-v4 规格
    print("🔍 2. 验证阿里百炼 text-embedding-v4 规格")
    print("-" * 70)

    expected_specs = {
        "provider": "dashscope",
        "model": "text-embedding-v4",
        "dimension": 1024,  # 官方规格
    }

    issues = []

    if provider != expected_specs["provider"]:
        issues.append(
            f"❌ Provider 不匹配: 期望 {expected_specs['provider']}, 实际 {provider}"
        )
    else:
        print(f"✅ Provider: {provider}")

    if model_name != expected_specs["model"]:
        issues.append(
            f"❌ Model 不匹配: 期望 {expected_specs['model']}, 实际 {model_name}"
        )
    else:
        print(f"✅ Model: {model_name}")

    if dimension != expected_specs["dimension"]:
        issues.append(
            f"❌ Dimension 不匹配: 期望 {expected_specs['dimension']}, 实际 {dimension}"
        )
    else:
        print(f"✅ Dimension: {dimension}")

    print()

    # 3. 检查 API Key
    print("🔑 3. 检查 API Key 配置")
    print("-" * 70)

    if not api_key or api_key.startswith("your_"):
        issues.append("❌ API Key 未正确配置(仍为占位符或为空)")
        print("❌ API Key: 未配置或为占位符")
    else:
        print(f"✅ API Key: {api_key[:10]}... (已配置)")

    print()

    # 4. 检查 LangMem 适配器配置
    print("🔧 4. 检查 LangMem 适配器集成")
    print("-" * 70)

    try:
        from src.infrastructure.memory.langmem_adapter import LangMemAdapter

        adapter = LangMemAdapter()

        if adapter.embedding_provider != provider:
            issues.append(
                f"❌ LangMem 适配器 Provider 不一致: "
                f"{adapter.embedding_provider} vs {provider}"
            )
        else:
            print(f"✅ LangMem Provider: {adapter.embedding_provider}")

        if adapter.embedding_model != model_name:
            issues.append(
                f"❌ LangMem 适配器 Model 不一致: "
                f"{adapter.embedding_model} vs {model_name}"
            )
        else:
            print(f"✅ LangMem Model: {adapter.embedding_model}")

        if adapter.embedding_dimension != dimension:
            issues.append(
                f"❌ LangMem 适配器 Dimension 不一致: "
                f"{adapter.embedding_dimension} vs {dimension}"
            )
        else:
            print(f"✅ LangMem Dimension: {adapter.embedding_dimension}")

    except Exception as e:
        issues.append(f"❌ LangMem 适配器检查失败: {e}")
        print(f"❌ 无法创建 LangMem 适配器: {e}")
        raise

    print()

    # 5. 检查 .env.example 同步状态
    print("📝 5. 检查 .env.example 同步状态")
    print("-" * 70)

    env_example_path = project_root / ".env.example"
    if env_example_path.exists():
        with env_example_path.open(encoding="utf-8") as f:
            env_example_content = f.read()

        # 检查维度配置
        if "EMBEDDING_DIMENSION=1024" in env_example_content:
            print("✅ .env.example 维度配置正确: 1024")
        elif "EMBEDDING_DIMENSION=1536" in env_example_content:
            issues.append("⚠️  .env.example 维度配置滞后: 1536 (应为 1024)")
            print("⚠️  .env.example 维度配置滞后: 1536 → 应修正为 1024")
        else:
            print("⚠️  .env.example 未找到 EMBEDDING_DIMENSION 配置")
    else:
        print("⚠️  .env.example 文件不存在")

    print()

    # 6. 最终结果
    print("=" * 70)
    print("📊 检查结果")
    print("=" * 70)

    if issues:
        print(f"❌ 发现 {len(issues)} 个问题:")
        print()
        for issue in issues:
            print(f"  {issue}")
        print()
        print("💡 建议:")
        print("  1. 检查 .env 文件配置是否正确")
        print("  2. 确保 EMBEDDING_DIMENSION=1024")
        print("  3. 同步更新 .env.example")
        print("  4. 重启服务使配置生效")
        return False
    else:
        print("✅ 所有检查通过!配置完全一致。")
        print()
        print("📋 配置总结:")
        print(f"  - Provider:  {provider}")
        print(f"  - Model:     {model_name}")
        print(f"  - Dimension: {dimension} ✅")
        print("  - API Key:   已配置 ✅")
        return True


if __name__ == "__main__":
    success = check_embedding_config()
    sys.exit(0 if success else 1)
