"""
LLM 广告清洗器单文件调试脚本

用途:
- 不通过完整产线, 直接对一个 MinerU 生成的 full.md 运行一次 LLMAdRemover
- 打印出失败时的原始 LLM 错误信息 (original_error), 方便定位清洗失败原因

运行方式:
    pytest tests/debug_llm_ad_remover_single_full_md.py -v -s

前置条件:
- .env 中已正确配置 AD_CLEANING_LLM_* 相关配置
- data/processed/mineru 下存在至少一个 full.md
"""

from pathlib import Path

import pytest
from langchain_core.documents import Document

from src.infrastructure.preprocessing.cleaners.llm_ad_remover import LLMAdRemover
from src.infrastructure.preprocessing.error_handler import LLMAdRemoverError
from src.shared.config.llm_service import get_llm_service


def _find_first_full_md() -> Path | None:
    base_dir = Path("data/processed/mineru")
    if not base_dir.exists():
        return None
    for path in base_dir.rglob("full.md"):
        if path.is_file():
            return path
    return None


@pytest.mark.slow
def test_debug_single_full_md_cleaning() -> None:
    """对单个 MinerU full.md 运行一次 LLM 广告清洗, 打印底层错误原因."""

    full_md_path = _find_first_full_md()
    if not full_md_path:
        pytest.skip("未在 data/processed/mineru 下找到 full.md, 无法调试 LLM 清洗")

    print(f"[DEBUG] 使用 full.md 文件: {full_md_path}")

    # 读取内容,为了避免超长,可以只取前 N 字符做一次试跑
    content = full_md_path.read_text(encoding="utf-8", errors="ignore")
    if len(content) > 20000:
        print(f"[DEBUG] 原文长度 {len(content)} 字符, 仅取前 20000 字符做调试")
        content = content[:20000]

    doc = Document(
        page_content=content,
        metadata={
            "source": str(full_md_path),
            "format": "markdown",
        },
    )

    llm_service = get_llm_service()
    remover = LLMAdRemover(llm_service=llm_service)

    try:
        cleaned = remover.clean_document(doc)
        print(
            "[DEBUG] 清洗成功, 原始长度=%d, 清洗后长度=%d"
            % (len(doc.page_content), len(cleaned.page_content))
        )
    except LLMAdRemoverError as e:
        print("[DEBUG] LLMAdRemoverError 捕获:")
        print(f"  error_code: {e.error_code}")
        print(f"  message   : {e}")
        details = getattr(e, "details", {}) or {}
        original = details.get("original_error")
        if original:
            print("  original_error:")
            print(original)
        else:
            print("  details 中未包含 original_error, details =", details)
        pytest.fail("LLM 广告清洗失败, 详情见上方 DEBUG 输出")
    except Exception as e:  # pragma: no cover - 调试专用
        print("[DEBUG] 未知异常捕获:", repr(e))
        pytest.fail(f"LLM 广告清洗未知异常: {e!r}")


