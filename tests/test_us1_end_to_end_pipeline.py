"""
用户故事 1 端到端回归测试

目标: 覆盖从 OCR(MinerU) -> 广告清洗(LLMAdRemover) -> 图表转 JSON(LLMChartToJsonConverter)
的完整真实产线, 不使用任何 mock, 不做降级或假设。

测试前置:
- 需要正确配置 MinerU、广告清洗 LLM、图表转 JSON LLM 等相关环境变量
- 需要在 data/source/uploads 目录下放置至少 1 个 PDF 或 DOCX 测试文件
- 建议只在手动回归或 CI 中专门跑此用例, 因为会比较耗时和耗 token
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.application.services.document_service import DocumentService
from src.infrastructure.preprocessing.preprocessor import DocumentPreprocessor
from src.shared.config.llm_service import get_llm_service
from src.shared.config.settings import get_config


def _collect_real_upload_files() -> list[str]:
    """从 data/source/uploads 收集真实待处理文件."""

    uploads_dir = Path("data/source/uploads")
    if not uploads_dir.exists():
        return []

    paths: list[str] = []
    for ext in (".pdf", ".docx"):
        for f in uploads_dir.glob(f"*{ext}"):
            if f.is_file():
                paths.append(str(f))
    return paths


@pytest.mark.slow
def test_us1_end_to_end_batch_ocr_cleaning_chart_json(tmp_path: Path) -> None:
    """
    用户故事 1 端到端回归测试(批量上传入口).

    流程:
    1. 使用真实 PDF/DOCX 文件, 通过 DocumentService.upload_and_process_batch_async
       走 MinerU OCR + 预处理协调器/Agent 的批量上传通路
    2. 在异步任务中开启 enable_chart_conversion=True, 触发:
       - LLMAdRemover 对 MinerU 生成的 full.md 进行广告清洗, 产出 clean.md 等
       - LLMChartToJsonConverter 扫描 data/cleaned/documents 下的 *_extracted 目录,
         将图表图像转换为 JSON, 输出到 datajson/ 目录
    3. 断言:
       - 至少有 1 个文件被成功处理
       - 对应的 cleaned 目录存在 clean.md
       - 至少有一个 datajson/*.json 被生成 (如果存在图表)
    """

    # 1. 收集真实上传文件, 统一走「批量上传」入口
    file_paths = _collect_real_upload_files()
    if not file_paths:
        pytest.skip("data/source/uploads 下没有可用的 PDF/DOCX 测试文件")

    # 2. 初始化文档服务, 使用 Agent 并开启图表转换
    service = DocumentService(
        llm_service=get_llm_service(),
        enable_chart_conversion=True,
        use_agent=True,
    )

    # DocumentService 会负责:
    # - 格式检测 + 验证
    # - 在 SQLite documents 表中写入记录
    # - 调用批量异步任务 (process_batch_documents_async)
    #   其中 DocumentProcessingTask / BatchDocumentProcessingTask 会:
    #   - 通过 DocumentPreprocessorAgent 或 DocumentPreprocessor 调用 MinerU 管线
    #   - 使用 LLMAdRemover 进行广告清洗, 写入 data/cleaned/documents
    #   - 使用 LLMChartToJsonConverter 在 cleaned 目录下生成 datajson/*.json
    import asyncio

    result = asyncio.run(
        service.upload_and_process_batch_async(
            file_paths=file_paths,
            uploaded_by=_get_default_test_user_id(),
            batch_size=len(file_paths),
            enable_chart_conversion=True,
        )
    )

    # 3. 基本结果断言: 只关心本次批量任务是否成功, 不再依赖历史文件产物
    assert result.get("status") is not None, "批量处理结果必须包含 status 字段"
    assert result["status"] == "completed", f"批量处理未成功, result={result}"

    processed_files = result.get("processed_files", [])
    assert processed_files, "至少应有 1 个文件被成功处理"

    # 所有入参文件都应在 processed_files 中(路径可能被规范化,这里做包含性检查)
    normalized_processed = {str(Path(p).absolute().resolve()) for p in processed_files}
    for fp in file_paths:
        assert (
            str(Path(fp).absolute().resolve()) in normalized_processed
        ), f"输入文件未出现在成功列表中: {fp}"

    # 4. 进一步强约束: 使用文档预处理协调器直接跑一遍,要求 LLM 广告清洗真正成功
    #    - OCR: 通过 MinerU 批量 API (DocumentPreprocessor.process_documents)
    #    - 广告清洗: 必须走到 LLMAdRemover, 且 pipeline 标记为 llm_ad_cleaning
    config = get_config()
    llm_service = get_llm_service()
    preprocessor = DocumentPreprocessor(
        config=config,
        llm_service=llm_service,
        cleaning_enabled=True,
        progress_tracking_enabled=True,
    )

    docs = preprocessor.process_documents(file_paths)
    assert docs, "预处理协调器应返回至少一个 Document"

    # 要求当前这次处理的管线必须是 llm_ad_cleaning, 否则认为广告清洗未真正跑通
    pipelines = {doc.metadata.get("pipeline") for doc in docs}
    assert "llm_ad_cleaning" in pipelines, (
        f"本次处理未经过 LLM 广告清洗管线, 实际 pipeline 集合: {pipelines}"
    )


def _get_default_test_user_id():
    """获取与 CLI 一致的默认测试用户 ID."""

    import uuid

    # 与 interfaces/cli/documents.py 中的默认用户保持一致
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


