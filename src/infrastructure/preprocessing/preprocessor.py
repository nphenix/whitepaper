# 生成命令: /speckit.implement T031
# 生成时间: 2025-12-14
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
文档预处理协调器

该模块统一协调文档加载和清洗流程,仅支持MinerU产线.
根据文档格式自动选择对应的加载器,直接使用LLMAdRemover进行清洗处理.
基于LangChain 1.0最佳实践实现,提供统一的文档预处理接口.

功能特性:
- 统一协调文档加载和清洗流程(仅支持MinerU产线)
- 根据文档格式自动选择对应的加载器
  - PDF格式: MinerU PDF加载器(T026-MinerU)
  - DOCX格式: MinerU DOCX加载器(T027)
- 直接使用LLMAdRemover(T030A)进行清洗处理
- 处理流程:格式识别(T038) → 加载器加载(MinerU) → LLM清洗(T030A) → 返回处理后的Document列表
- 所有输入输出使用LangChain Document对象格式
- 完善的错误处理和日志记录
- 支持同步和异步处理
- 支持批量处理和进度跟踪
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.infrastructure.preprocessing.cleaners.llm_ad_remover import LLMAdRemover
from src.infrastructure.preprocessing.error_handler import (
    preprocessing_error_handler,
)
from src.infrastructure.preprocessing.format_detector import (
    FormatDetector,
    FormatInfo,
)
from src.infrastructure.preprocessing.loaders.base_loader import BaseLoader
from src.infrastructure.preprocessing.loaders.mineru_docx_loader import (
    MinerUDOCXLoader,
)
from src.infrastructure.preprocessing.loaders.mineru_pdf_loader import (
    MinerUPDFLoader,
)
from src.infrastructure.preprocessing.logging_config import (
    create_coordinator_logger,
)
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.config.settings import AppConfig, get_config
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentPreprocessor:
    """
    文档预处理协调器

    统一协调文档加载和清洗流程,仅支持MinerU产线.
    根据文档格式自动选择对应的加载器,直接使用LLMAdRemover进行清洗处理.

    处理流程:
    1. 格式识别(T038)→ 检测文档格式和验证
    2. 加载器加载(MinerU)→ 根据格式选择对应的加载器
    3. LLM清洗(T030A)→ 直接使用LLMAdRemover进行清洗
    4. 返回处理后的Document列表

    最佳实践:
    - 使用LangChain 1.0 Document对象作为统一数据格式
    - 支持同步和异步处理
    - 完善的错误处理和日志记录
    - 支持批量处理和进度跟踪
    - 遵循SOLID原则,保持模块化设计

    示例:
        >>> preprocessor = DocumentPreprocessor()
        >>> documents = preprocessor.process_document('document.pdf')
        >>> for doc in documents:
        ...     print(doc.page_content)
        ...     print(doc.metadata)
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        llm_service: LLMService | None = None,
        format_detector: FormatDetector | None = None,
        cleaning_enabled: bool = True,
        progress_tracking_enabled: bool = True,
        output_dir: str | None = None,
        chart_conversion_enabled: bool = True,
    ):
        """初始化文档预处理协调器

        Args:
            config: 应用配置对象,如果为None则使用默认配置
            llm_service: LLM服务实例,如果为None则使用全局实例
            format_detector: 格式检测器实例,如果为None则创建新实例
            enable_cleaning: 是否启用LLM清洗,默认为True
            enable_progress_tracking: 是否启用进度跟踪,默认为True
            output_dir: 输出目录,如果指定则将清洗后的Markdown文件保存到此目录
                       如果为None且启用了清洗,则使用默认目录 'data/cleaned/documents'
            enable_chart_conversion: 是否启用图表转JSON功能,默认为True
        """
        self.config = config or get_config()
        self.llm_service = llm_service or get_llm_service()
        self.format_detector = format_detector or FormatDetector()
        self.enable_cleaning = cleaning_enabled
        self.enable_progress_tracking = progress_tracking_enabled
        self.enable_chart_conversion = chart_conversion_enabled

        # 创建专用的日志记录器
        self.preprocessing_logger = create_coordinator_logger()

        # 设置输出目录:如果指定了则使用指定的,否则如果启用了清洗则使用默认目录
        if output_dir:
            self.output_dir = Path(output_dir)
        elif cleaning_enabled:
            # 默认输出目录: <project_root>/data/cleaned/documents
            # 注意：不要依赖 cwd（worker/api 运行目录可能不在项目根）
            self.output_dir = self.config.data_dir / "cleaned" / "documents"
        else:
            self.output_dir = None

        # 延迟初始化加载器
        self._loaders: dict[str, BaseLoader] = {}

        # 共享的MinerU适配器实例,避免重复创建
        self._shared_adapter: Any | None = None

        # 处理统计信息
        self.stats = {
            "total_documents": 0,
            "processed_documents": 0,
            "failed_documents": 0,
            "skipped_documents": 0,
            "start_time": None,
            "end_time": None,
            "processing_time": 0,
            "format_distribution": {},
            "pipeline_distribution": {},
        }

        logger.info("文档预处理协调器初始化完成")
        logger.info(f"支持格式: {self.format_detector.get_supported_formats()}")
        logger.info(f"启用清洗: {self.enable_cleaning}")
        logger.info(f"启用进度跟踪: {self.enable_progress_tracking}")
        logger.info(f"启用图表转JSON: {self.enable_chart_conversion}")
        if self.output_dir:
            logger.info("输出目录: %s", self.output_dir.absolute())

    def _get_loader(self, file_path: str, format_info: FormatInfo) -> BaseLoader:
        """获取对应格式的文档加载器

        Args:
            file_path: 文件路径
            format_info: 格式信息

        Returns:
            BaseLoader: 对应格式的加载器实例

        Raises:
            ProcessingError: 如果格式不支持或加载器创建失败
        """
        format_name = format_info.format

        # 检查是否已有缓存的加载器
        if format_name in self._loaders:
            loader = self._loaders[format_name]
            # 检查加载器是否能处理该文件
            if loader.can_handle(file_path):
                return loader
            else:
                # 如果不能处理,移除缓存
                del self._loaders[format_name]

        # 创建新的加载器
        try:
            # 使用共享的adapter实例,避免重复创建
            if self._shared_adapter is None:
                from src.infrastructure.preprocessing.loaders.mineru_adapter import (
                    MinerUAdapter,
                )

                self._shared_adapter = MinerUAdapter(config=self.config)

            if format_name == "pdf":
                loader = MinerUPDFLoader(
                    source=file_path,
                    adapter=self._shared_adapter,  # 使用共享的adapter
                    config=self.config,
                )
            elif format_name == "docx":
                loader = MinerUDOCXLoader(
                    source=file_path,
                    adapter=self._shared_adapter,  # 使用共享的adapter
                    config=self.config,
                )
            else:
                msg = f"不支持的文档格式: {format_name}"
                raise ProcessingError(msg)

            # 缓存加载器
            self._loaders[format_name] = loader

            logger.debug("创建%s加载器成功: %s", format_name, file_path)
            return loader

        except Exception as e:
            error_msg = f"创建{format_name}加载器失败: {file_path}"
            logger.error(error_msg, exc_info=True)

            # 映射错误并记录日志
            mapped_error = preprocessing_error_handler.map_coordinator_error(
                e, file_path, "loader_creation"
            )
            self.preprocessing_logger.log_coordinator_error(
                mapped_error, file_path, "loader_creation"
            )
            raise mapped_error

    def _save_cleaned_documents(
        self, file_path: str, documents: list[Document], format_name: str
    ) -> None:
        """保存清洗后的Markdown文件到输出目录,并复制相关资源文件

        按照 T031A 要求的目录结构保存:
        - 输出:data/cleaned/documents/{doc_name}/{extracted_dir}/clean.md
        - 同时复制:images/ 目录,layout.json 等元数据文件

        Args:
            file_path: 原始文件路径
            documents: 清洗后的Document列表
            format_name: 文档格式名称
        """
        import shutil

        if not self.output_dir:
            return

        try:
            # 为每个Document保存文件
            for i, doc in enumerate(documents):
                if not doc.page_content:
                    logger.warning(f"Document {i + 1} 内容为空,跳过保存")
                    continue

                # 尝试从 metadata 获取源目录信息
                extracted_dir = doc.metadata.get("extracted_dir")

                if extracted_dir:
                    # 有 extracted_dir,按照 T031A 要求的目录结构保存
                    extracted_path = Path(extracted_dir)

                    # 获取文档名(从源目录结构中提取)
                    # 结构:data/processed/mineru/{doc_name}_xx/{cache_key}_extracted/
                    # 我们需要保持相同的目录结构
                    try:
                        # 获取相对路径(相对于 processed/mineru)
                        mineru_base = Path("data/processed/mineru")
                        if extracted_path.is_absolute():
                            # 尝试找到 mineru 目录的位置
                            parts = extracted_path.parts
                            for j, part in enumerate(parts):
                                if part == "mineru" and j + 2 < len(parts):
                                    # 获取 {doc_name}_xx/{cache_key}_extracted 部分
                                    relative_parts = parts[j + 1 :]
                                    relative_path = Path(*relative_parts)
                                    break
                            else:
                                # 如果找不到 mineru 目录,使用最后两级目录
                                relative_path = (
                                    Path(extracted_path.parent.name)
                                    / extracted_path.name
                                )
                        else:
                            relative_path = extracted_path.relative_to(mineru_base)
                    except ValueError:
                        # 如果无法获取相对路径,使用最后两级目录
                        relative_path = (
                            Path(extracted_path.parent.name) / extracted_path.name
                        )

                    # 创建输出目录
                    output_dir = self.output_dir / relative_path
                    output_dir.mkdir(parents=True, exist_ok=True)

                    # 保存清洗后的 Markdown 文件
                    output_md_path = output_dir / "clean.md"
                    with open(output_md_path, "w", encoding="utf-8") as f:
                        f.write(doc.page_content)
                    logger.info(f"已保存清洗后的Markdown文件: {output_md_path}")

                    # 复制 images 目录
                    source_images_dir = extracted_path / "images"
                    if source_images_dir.exists() and source_images_dir.is_dir():
                        dest_images_dir = output_dir / "images"
                        if dest_images_dir.exists():
                            shutil.rmtree(dest_images_dir)
                        shutil.copytree(source_images_dir, dest_images_dir)
                        logger.info(f"已复制 images 目录: {dest_images_dir}")

                    # 复制 layout.json
                    source_layout = extracted_path / "layout.json"
                    if source_layout.exists():
                        dest_layout = output_dir / "layout.json"
                        shutil.copy2(source_layout, dest_layout)
                        logger.info(f"已复制 layout.json: {dest_layout}")

                    # 复制其他 JSON 文件(如 content_list.json, model.json 等)
                    # 注意:跳过 *content_list.json 和 *model.json,因为它们会在 _rebuild_metadata_files 中重构
                    for json_file in extracted_path.glob("*.json"):
                        if json_file.name != "layout.json":  # layout.json 已经复制过
                            # 跳过会被重构的文件(带 UUID 前缀的 content_list.json 和 model.json)
                            if json_file.name.endswith(
                                "_content_list.json"
                            ) or json_file.name.endswith("_model.json"):
                                logger.debug(
                                    f"跳过元数据文件(将在重构时处理): {json_file.name}"
                                )
                                continue
                            dest_json = output_dir / json_file.name
                            shutil.copy2(json_file, dest_json)
                            logger.debug(f"已复制元数据文件: {dest_json}")

                    # 提取清洗后文档中被引用的图片,用于重构元数据文件
                    retained_images = self._extract_image_references(doc.page_content)
                    logger.info(
                        "从清洗后文档中提取到 %d 个图片引用", len(retained_images)
                    )

                    # 重构元数据文件(content_list.json, model.json, layout.json)
                    # 根据清洗后的内容过滤,只保留文档中仍存在的内容块
                    self._rebuild_metadata_files(
                        extracted_path=extracted_path,
                        output_dir=output_dir,
                        doc=doc,
                        retained_images=retained_images,
                    )

                    # 图表转JSON(如果启用)
                    if self.enable_chart_conversion:
                        try:
                            from src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter import (
                                LLMChartToJsonConverter,
                            )

                            # 如果已经生成过 datajson/*.json，则跳过重复的LLM图表解析
                            datajson_dir = output_dir / "datajson"
                            existing_json = (
                                datajson_dir.exists()
                                and any(datajson_dir.rglob("*.json"))
                            )
                            if existing_json:
                                logger.info(
                                    "检测到图表JSON已存在，跳过图表转JSON: %s",
                                    datajson_dir,
                                )
                            else:
                                logger.info(f"开始图表转JSON转换: {output_dir}")
                                chart_converter = LLMChartToJsonConverter(
                                    llm_service=self.llm_service
                                )
                                chart_result = chart_converter.process_mineru_directory(
                                    str(output_dir), create_datajson_dir=True
                                )
                                stats = chart_result.get("overall_statistics", {})
                                logger.info(
                                    f"图表转JSON完成: 处理 {stats.get('total_images_processed', 0)} 个图像, "
                                    f"发现 {stats.get('total_charts_found', 0)} 个图表, "
                                    f"生成 {stats.get('total_json_files_generated', 0)} 个JSON文件"
                                )
                        except Exception as e:
                            logger.warning(f"图表转JSON失败,不影响主流程: {e}")

                    # ---- 统一补齐媒体元数据与 rag_media_manifest（无论图转JSON是否跳过） ----
                    try:
                        import json

                        images_dir = output_dir / "images"
                        datajson_dir = output_dir / "datajson"

                        # 如果正文里没有保留任何图片引用，但目录中确实有图片，则兜底为“保留全部图片”
                        # 目的：避免 LLM 清洗/格式差异导致 retained_images 为空，从而无法生成 manifest / 注入插图。
                        if (not retained_images) and images_dir.exists():
                            retained_images = {
                                p.name
                                for p in list(images_dir.glob("*.jpg"))
                                + list(images_dir.glob("*.png"))
                                + list(images_dir.glob("*.jpeg"))
                                + list(images_dir.glob("*.webp"))
                            }

                        # 1) 写入 images / charts 元数据（供后续索引/检索节点 metadata 使用）
                        try:
                            if images_dir.exists():
                                img_files = sorted(
                                    [p.name for p in images_dir.glob("*") if p.is_file()],
                                    key=lambda x: x,
                                )
                                if img_files:
                                    doc.metadata["images"] = {
                                        "count": len(img_files),
                                        "files": img_files,
                                        "directory": str(images_dir),
                                    }
                        except Exception:
                            pass

                        try:
                            if datajson_dir.exists():
                                json_files = sorted(
                                    [p.name for p in datajson_dir.glob("*.json") if p.is_file()],
                                    key=lambda x: x,
                                )
                                if json_files:
                                    doc.metadata["charts"] = {
                                        "count": len(json_files),
                                        "charts": [{"name": Path(f).stem, "file": f} for f in json_files],
                                        "directory": str(datajson_dir),
                                    }
                        except Exception:
                            pass

                        # 2) 始终生成 rag_media_manifest（只要 clean_content_list.json 存在）
                        rag_media_manifest = self._generate_rag_media_manifest(output_dir, retained_images)

                        # 3) 保存 rag_media_manifest 到 JSON 文件（幂等：覆盖写）
                        if rag_media_manifest:
                            manifest_file = output_dir / "rag_media_manifest.json"
                            with open(manifest_file, "w", encoding="utf-8") as f:
                                json.dump(rag_media_manifest, f, ensure_ascii=False, indent=2)
                            logger.info("已保存 rag_media_manifest 到: %s", manifest_file)
                            doc.metadata["rag_media_manifest"] = rag_media_manifest
                    except Exception as e:
                        logger.warning("生成/补齐 rag_media_manifest 失败（不影响主流程）: %s", e)

                else:
                    # 没有 extracted_dir,使用简单的文件名保存(向后兼容)
                    self.output_dir.mkdir(parents=True, exist_ok=True)
                    source_path = Path(file_path)
                    source_name = source_path.stem

                    if len(documents) == 1:
                        output_filename = f"{source_name}_cleaned.md"
                    else:
                        output_filename = f"{source_name}_cleaned_{i + 1}.md"

                    output_path = self.output_dir / output_filename

                    try:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, "w", encoding="utf-8") as f:
                            f.write(doc.page_content)
                        logger.info(f"已保存清洗后的Markdown文件: {output_path}")
                    except Exception as e:
                        logger.error(f"保存Markdown文件失败: {output_path}, 错误: {e}")

        except Exception as e:
            logger.warning(f"保存清洗后的文件失败: {e}")

    def _update_stats(self, format_name: str, pipeline_name: str, success: bool = True):
        """更新处理统计信息

        Args:
            format_name: 文档格式名称
            pipeline_name: 处理管线名称
            success: 是否处理成功
        """
        # 更新格式分布
        if format_name not in self.stats["format_distribution"]:
            self.stats["format_distribution"][format_name] = 0
        self.stats["format_distribution"][format_name] += 1

        # 更新管线分布
        if pipeline_name not in self.stats["pipeline_distribution"]:
            self.stats["pipeline_distribution"][pipeline_name] = 0
        self.stats["pipeline_distribution"][pipeline_name] += 1

        # 更新处理计数
        if success:
            self.stats["processed_documents"] += 1
        else:
            self.stats["failed_documents"] += 1

    def process_document(self, file_path: str) -> list[Document]:
        """处理单个文档

        Args:
            file_path: 文档路径

        Returns:
            List[Document]: 处理后的Document列表

        Raises:
            ProcessingError: 处理过程中出现错误
        """
        try:
            logger.info("开始处理文档: %s", file_path)

            # 1. 格式识别和验证
            format_info = self.format_detector.detect_format(file_path)
            validation_result = self.format_detector.validate_document(
                file_path, format_info
            )

            if not validation_result.is_valid:
                error_msg = (
                    f"文档验证失败: {file_path}, 错误: {validation_result.errors}"
                )
                logger.error(error_msg)
                raise ProcessingError(error_msg)

            if validation_result.warnings:
                logger.warning(
                    f"文档验证警告: {file_path}, 警告: {validation_result.warnings}"
                )

            logger.debug(
                "文档格式检测结果: %s, 置信度: %s",
                format_info.format,
                format_info.confidence,
            )

            # 2. 加载文档
            stage_start_time = time.time()
            self.preprocessing_logger.log_coordinator_stage_start(
                file_path=file_path, stage="document_loading"
            )

            loader = self._get_loader(file_path, format_info)
            documents = loader.load()

            if not documents:
                logger.warning(f"加载器返回空文档列表: {file_path}")
                documents = [
                    Document(
                        page_content="",
                        metadata={
                            "source": file_path,
                            "format": format_info.format,
                            "pipeline": "unknown",
                            "warning": "加载器返回空内容",
                        },
                    )
                ]

            # 记录文档加载阶段成功
            stage_processing_time = time.time() - stage_start_time
            self.preprocessing_logger.log_coordinator_stage_success(
                file_path=file_path,
                stage="document_loading",
                processing_time_seconds=stage_processing_time,
                output_documents_count=len(documents),
            )

            # 验证:确保加载器返回的是Markdown文本内容,而不是文件路径
            for i, doc in enumerate(documents):
                page_content = doc.page_content
                if isinstance(page_content, bytes):
                    page_content = page_content.decode("utf-8", errors="replace")

                # 检查是否是文件路径(误传)
                if page_content and (
                    page_content.startswith(("F:", "C:", "/", "\\"))
                    and len(page_content) < 500
                ):
                    logger.error(
                        "错误:Document %d 的page_content看起来像是文件路径而不是Markdown文本: "
                        "%s...",
                        i + 1,
                        page_content[:200],
                    )
                    msg = "加载器返回的Document内容格式错误,应该是Markdown文本而不是文件路径"
                    raise ProcessingError(msg)

                # 记录Document内容信息
                logger.debug(
                    "Document %d 内容类型: Markdown文本, "
                    "大小: %d 字符, "
                    "前100字符: %s...",
                    i + 1,
                    len(page_content),
                    (
                        page_content[:100].replace(chr(10), "\n").replace(chr(13), "\r")
                        if page_content
                        else ""
                    ),
                )

            # 3. LLM清洗(如果启用)
            # 重要:逐个处理每个Document,避免一次性提交多个文档导致上下文过长
            if self.enable_cleaning:
                try:
                    stage_start_time = time.time()
                    self.preprocessing_logger.log_coordinator_stage_start(
                        file_path=file_path, stage="content_cleaning"
                    )

                    # 复用已存在的清洗产物：若 clean.md 已存在，则跳过LLM清洗
                    used_cache = False
                    if self.output_dir:
                        for doc in documents:
                            extracted_dir = doc.metadata.get("extracted_dir")
                            if not extracted_dir:
                                continue
                            extracted_path = Path(extracted_dir)
                            try:
                                mineru_base = Path("data/processed/mineru")
                                if extracted_path.is_absolute():
                                    parts = extracted_path.parts
                                    for j, part in enumerate(parts):
                                        if part == "mineru" and j + 2 < len(parts):
                                            relative_path = Path(*parts[j + 1 :])
                                            break
                                    else:
                                        relative_path = (
                                            Path(extracted_path.parent.name)
                                            / extracted_path.name
                                        )
                                else:
                                    relative_path = extracted_path.relative_to(mineru_base)
                            except ValueError:
                                relative_path = (
                                    Path(extracted_path.parent.name) / extracted_path.name
                                )

                            cached_clean_md = self.output_dir / relative_path / "clean.md"
                            if cached_clean_md.exists() and cached_clean_md.stat().st_size > 0:
                                try:
                                    cached_content = cached_clean_md.read_text(
                                        encoding="utf-8"
                                    )
                                    doc.page_content = cached_content
                                    doc.metadata.update(
                                        {
                                            "cleaned": True,
                                            "cache_hit": True,
                                            "cached_clean_md": str(cached_clean_md),
                                        }
                                    )
                                    used_cache = True
                                except Exception as e:
                                    logger.warning(
                                        "读取缓存clean.md失败，将回退LLM清洗: %s (error=%s)",
                                        cached_clean_md,
                                        e,
                                    )

                    if used_cache:
                        logger.info("检测到clean.md缓存命中，跳过LLM广告清洗: %s", file_path)
                        pipeline_name = "cached_clean_md"
                    else:
                        # 直接使用LLMAdRemover清洗Document对象
                        # 注意:cleaning_pipeline.process_single_document是用于处理文件系统的,
                        # 这里我们处理的是已经加载的Document对象,所以直接使用LLMAdRemover
                        ad_remover = LLMAdRemover(llm_service=self.llm_service)

                        # 逐个清洗文档,避免上下文过长
                        cleaned_documents = []
                        for i, doc in enumerate(documents):
                            try:
                                logger.info(
                                    "开始清洗文档 %d/%d: %s",
                                    i + 1,
                                    len(documents),
                                    doc.metadata.get("source", "unknown"),
                                )
                                # 逐个提交每个Document,避免上下文过长
                                cleaned_doc = ad_remover.clean_document(doc)
                                cleaned_documents.append(cleaned_doc)
                                logger.info(
                                    "完成清洗文档 %d/%d: %s",
                                    i + 1,
                                    len(documents),
                                    doc.metadata.get("source", "unknown"),
                                )
                            except Exception as e:
                                logger.warning(
                                    f"清洗文档 {i + 1}/{len(documents)} 失败,保留原始文档: {e}"
                                )
                                cleaned_documents.append(doc)

                        documents = cleaned_documents
                        pipeline_name = "llm_ad_cleaning"

                    # 记录内容清洗阶段成功
                    stage_processing_time = time.time() - stage_start_time
                    self.preprocessing_logger.log_coordinator_stage_success(
                        file_path=file_path,
                        stage="content_cleaning",
                        processing_time_seconds=stage_processing_time,
                        output_documents_count=len(documents),
                    )

                except Exception as e:
                    # 映射错误并记录日志,并将错误向上抛出(严格模式:清洗失败视为整个预处理失败)
                    mapped_error = preprocessing_error_handler.map_coordinator_error(
                        e, file_path, "content_cleaning"
                    )
                    self.preprocessing_logger.log_coordinator_error(
                        mapped_error, file_path, "content_cleaning"
                    )
                    logger.error("LLM 清洗失败,终止预处理: %s", mapped_error)
                    raise mapped_error
            else:
                pipeline_name = "loader_only"

            # 4. 更新元数据
            for doc in documents:
                doc.metadata.update(
                    {
                        "preprocessed_at": datetime.now().isoformat(),
                        "preprocessor_version": "1.0.0",
                        "format_confidence": format_info.confidence,
                        "validation_warnings": validation_result.warnings,
                        "pipeline": pipeline_name,
                    }
                )

            # 5. 保存清洗后的Markdown文件(如果指定了输出目录且启用了清洗)
            if (
                self.output_dir
                and self.enable_cleaning
                and pipeline_name == "llm_ad_cleaning"
            ):
                self._save_cleaned_documents(file_path, documents, format_info.format)

            # 6. 更新统计信息
            self._update_stats(format_info.format, pipeline_name, success=True)

            # 计算总处理时间
            # 确保start_time不为None，如果为None或不存在，使用当前时间
            start_time = self.stats.get("start_time") or time.time()
            total_processing_time = time.time() - start_time

            # 记录完成日志
            completed_stages = ["format_detection", "document_loading"]
            if self.enable_cleaning:
                completed_stages.append("content_cleaning")

            self.preprocessing_logger.log_coordinator_success(
                file_path=file_path,
                total_processing_time_seconds=total_processing_time,
                pipeline_stages_completed=completed_stages,
                final_documents_count=len(documents),
            )

            logger.info(
                "文档处理完成: %s, 格式=%s, 管线=%s, 文档数=%d",
                file_path,
                format_info.format,
                pipeline_name,
                len(documents),
            )

            return documents

        except Exception as e:
            # 映射错误并记录日志
            mapped_error = preprocessing_error_handler.map_coordinator_error(
                e, file_path
            )
            self.preprocessing_logger.log_coordinator_error(mapped_error, file_path)

            logger.error(f"处理文档失败: {file_path}, 错误: {e}")
            # 尝试获取格式信息,如果失败则使用默认值
            try:
                format_info = self.format_detector.detect_format(file_path)
                # 检查format_info是否是Mock对象或有效对象
                if hasattr(format_info, "format") and not str(
                    format_info.format
                ).startswith("<Mock"):
                    format_name = format_info.format
                else:
                    format_name = "unknown"
            except Exception:
                format_name = "unknown"
            self._update_stats(
                format_name,
                "failed",
                success=False,
            )
            raise mapped_error

    def process_documents(self, file_paths: list[str]) -> list[Document]:
        """批量处理文档

        使用MinerU批量API一次性处理所有文件,避免重复上传.

        Args:
            file_paths: 文档路径列表

        Returns:
            List[Document]: 所有处理后的Document列表
        """
        logger.info("开始批量处理 %d 个文档", len(file_paths))

        # 重置统计信息
        self.stats.update(
            {
                "total_documents": len(file_paths),
                "processed_documents": 0,
                "failed_documents": 0,
                "skipped_documents": 0,
                "start_time": datetime.now().timestamp(),
                "end_time": None,
                "processing_time": 0,
                "format_distribution": {},
                "pipeline_distribution": {},
            }
        )

        if not file_paths:
            return []

        # 1. 格式识别和验证所有文件
        file_format_map = {}  # file_path -> format_info
        file_validation_map = {}  # file_path -> validation_result
        valid_files = []

        for file_path in file_paths:
            try:
                format_info = self.format_detector.detect_format(file_path)
                validation_result = self.format_detector.validate_document(
                    file_path, format_info
                )

                if not validation_result.is_valid:
                    logger.error(
                        "文档验证失败,跳过: %s, 错误: %s",
                        file_path,
                        validation_result.errors,
                    )
                    self.stats["failed_documents"] += 1
                    continue

                if validation_result.warnings:
                    logger.warning(
                        "文档验证警告: %s, 警告: %s",
                        file_path,
                        validation_result.warnings,
                    )

                # 只处理PDF和DOCX格式(MinerU支持)
                if format_info.format in ["pdf", "docx"]:
                    file_format_map[file_path] = format_info
                    file_validation_map[file_path] = validation_result
                    valid_files.append(file_path)
                else:
                    logger.warning(
                        "不支持的格式,跳过: %s, 格式: %s",
                        file_path,
                        format_info.format,
                    )
                    self.stats["skipped_documents"] += 1

            except Exception as e:
                logger.error("格式识别失败,跳过: %s, 错误: %s", file_path, e)
                self.stats["failed_documents"] += 1

        if not valid_files:
            logger.warning("没有有效的文件需要处理")
            return []

        # 2. 使用MinerU批量API一次性处理所有文件
        all_documents = []

        # 获取共享的adapter实例
        if self._shared_adapter is None:
            from src.infrastructure.preprocessing.loaders.mineru_adapter import (
                MinerUAdapter,
            )

            self._shared_adapter = MinerUAdapter(config=self.config)

        # 准备批量处理的文件路径和格式
        file_formats = [file_format_map[fp].format for fp in valid_files]

        try:
            # 一次性批量处理所有文件
            logger.info("使用MinerU批量API一次性处理 %d 个文件", len(valid_files))
            batch_results = self._shared_adapter.extract_batch(
                valid_files, file_formats
            )

            # 3. 处理每个文件的结果
            for file_path in valid_files:
                try:
                    format_info = file_format_map[file_path]
                    validation_result = file_validation_map.get(file_path)

                    # 从批量结果中获取该文件的文档
                    # extract_batch返回的key是标准化后的路径
                    normalized_path = str(Path(file_path).absolute().resolve())
                    documents = batch_results.get(
                        normalized_path, batch_results.get(file_path, [])
                    )

                    if not documents:
                        logger.warning("批量处理未返回文档: %s", file_path)
                        self.stats["failed_documents"] += 1
                        continue

                    # 4. LLM清洗(如果启用)
                    # 重要:逐个处理每个Document,避免一次性提交多个文档导致上下文过长
                    if self.enable_cleaning:
                        try:
                            # 复用已存在的清洗产物：若 clean.md 已存在，则跳过LLM清洗
                            used_cache = False
                            if self.output_dir:
                                for doc in documents:
                                    extracted_dir = doc.metadata.get("extracted_dir")
                                    if not extracted_dir:
                                        continue
                                    extracted_path = Path(extracted_dir)
                                    try:
                                        mineru_base = Path("data/processed/mineru")
                                        if extracted_path.is_absolute():
                                            parts = extracted_path.parts
                                            for j, part in enumerate(parts):
                                                if part == "mineru" and j + 2 < len(parts):
                                                    relative_path = Path(*parts[j + 1 :])
                                                    break
                                            else:
                                                relative_path = (
                                                    Path(extracted_path.parent.name)
                                                    / extracted_path.name
                                                )
                                        else:
                                            relative_path = extracted_path.relative_to(mineru_base)
                                    except ValueError:
                                        relative_path = (
                                            Path(extracted_path.parent.name)
                                            / extracted_path.name
                                        )

                                    cached_clean_md = self.output_dir / relative_path / "clean.md"
                                    if cached_clean_md.exists() and cached_clean_md.stat().st_size > 0:
                                        try:
                                            cached_content = cached_clean_md.read_text(
                                                encoding="utf-8"
                                            )
                                            doc.page_content = cached_content
                                            doc.metadata.update(
                                                {
                                                    "cleaned": True,
                                                    "cache_hit": True,
                                                    "cached_clean_md": str(cached_clean_md),
                                                }
                                            )
                                            used_cache = True
                                        except Exception as e:
                                            logger.warning(
                                                "读取缓存clean.md失败，将回退LLM清洗: %s (error=%s)",
                                                cached_clean_md,
                                                e,
                                            )

                            if used_cache:
                                logger.info(
                                    "检测到clean.md缓存命中，跳过LLM广告清洗: %s",
                                    file_path,
                                )
                                pipeline_name = "cached_clean_md"
                            else:
                                ad_remover = LLMAdRemover(llm_service=self.llm_service)
                                cleaned_documents = []
                                for i, doc in enumerate(documents):
                                    try:
                                        logger.info(
                                            "开始清洗文档 %d/%d (文件: %s): %s",
                                            i + 1,
                                            len(documents),
                                            file_path,
                                            doc.metadata.get("source", "unknown"),
                                        )
                                        # 逐个提交每个Document,避免上下文过长
                                        cleaned_doc = ad_remover.clean_document(doc)
                                        cleaned_documents.append(cleaned_doc)
                                        logger.info(
                                            "完成清洗文档 %d/%d (文件: %s): %s",
                                            i + 1,
                                            len(documents),
                                            file_path,
                                            doc.metadata.get("source", "unknown"),
                                        )
                                    except Exception as e:
                                        logger.warning(
                                            f"清洗文档 {i + 1}/{len(documents)} (文件: {file_path}) 失败,保留原始文档: {e}"
                                        )
                                        cleaned_documents.append(doc)
                                documents = cleaned_documents
                                pipeline_name = "llm_ad_cleaning"
                        except Exception as e:
                            logger.warning(f"LLM清洗失败,跳过清洗步骤: {e}")
                            pipeline_name = "loader_only"
                    else:
                        pipeline_name = "loader_only"

                    # 5. 更新元数据
                    for doc in documents:
                        doc.metadata.update(
                            {
                                "preprocessed_at": datetime.now().isoformat(),
                                "preprocessor_version": "1.0.0",
                                "format_confidence": format_info.confidence,
                                "validation_warnings": (
                                    validation_result.warnings
                                    if validation_result
                                    else []
                                ),
                                "pipeline": pipeline_name,
                            }
                        )

                    # 6. 保存清洗后的Markdown文件(如果指定了输出目录且启用了清洗)
                    if (
                        self.output_dir
                        and self.enable_cleaning
                        and pipeline_name == "llm_ad_cleaning"
                    ):
                        self._save_cleaned_documents(
                            file_path, documents, format_info.format
                        )

                    # 7. 更新统计信息
                    self._update_stats(format_info.format, pipeline_name, success=True)
                    all_documents.extend(documents)

                    if self.enable_progress_tracking:
                        processed = len(
                            [
                                f
                                for f in valid_files
                                if f
                                in [d.metadata.get("source") for d in all_documents]
                            ]
                        )
                        progress = processed / len(valid_files) * 100
                        logger.info(
                            "处理进度: %.1f%% (%d/%d)",
                            progress,
                            processed,
                            len(valid_files),
                        )

                except Exception as e:
                    logger.error("处理文件结果失败: %s, 错误: %s", file_path, e)
                    self.stats["failed_documents"] += 1

        except Exception as e:
            logger.error("批量处理失败: %s", e, exc_info=True)
            # 如果批量处理失败,记录所有文件为失败
            self.stats["failed_documents"] += len(valid_files)

        # 更新最终统计信息
        self.stats["end_time"] = datetime.now().timestamp()
        self.stats["processing_time"] = (
            self.stats["end_time"] - self.stats["start_time"]
        )

        logger.info("批量处理完成")
        logger.info("总文档数: %d", self.stats["total_documents"])
        logger.info("成功处理: %d", self.stats["processed_documents"])
        logger.info("处理失败: %d", self.stats["failed_documents"])
        logger.info("处理时间: %.2f秒", self.stats["processing_time"])
        logger.info("格式分布: %s", self.stats["format_distribution"])
        logger.info("管线分布: %s", self.stats["pipeline_distribution"])

        return all_documents

    async def aprocess_document(self, file_path: str) -> list[Document]:
        """异步处理单个文档(内部使用批量API)

        注意:即使是单个文件,也统一使用批量上传API处理,确保接口一致性.

        Args:
            file_path: 文档路径

        Returns:
            List[Document]: 处理后的Document列表

        Raises:
            ProcessingError: 处理过程中出现错误
        """
        # 直接使用批量处理接口,避免重复上传
        return await self.aprocess_documents([file_path])

    async def aprocess_documents(self, file_paths: list[str]) -> list[Document]:
        """异步批量处理文档(使用批量API一次性处理所有文件)

        使用MinerU批量API一次性处理所有文件,避免重复上传.

        Args:
            file_paths: 文档路径列表

        Returns:
            List[Document]: 所有处理后的Document列表
        """
        logger.info("开始异步批量处理 %d 个文档", len(file_paths))

        # 重置统计信息
        self.stats.update(
            {
                "total_documents": len(file_paths),
                "processed_documents": 0,
                "failed_documents": 0,
                "skipped_documents": 0,
                "start_time": datetime.now().timestamp(),
                "end_time": None,
                "processing_time": 0,
                "format_distribution": {},
                "pipeline_distribution": {},
            }
        )

        if not file_paths:
            return []

        # 1. 格式识别和验证所有文件
        file_format_map = {}  # file_path -> format_info
        file_validation_map = {}  # file_path -> validation_result
        valid_files = []

        for file_path in file_paths:
            try:
                format_info = self.format_detector.detect_format(file_path)
                validation_result = self.format_detector.validate_document(
                    file_path, format_info
                )

                if not validation_result.is_valid:
                    logger.error(
                        "文档验证失败,跳过: %s, 错误: %s",
                        file_path,
                        validation_result.errors,
                    )
                    self.stats["failed_documents"] += 1
                    continue

                if validation_result.warnings:
                    logger.warning(
                        "文档验证警告: %s, 警告: %s",
                        file_path,
                        validation_result.warnings,
                    )

                # 只处理PDF和DOCX格式(MinerU支持)
                if format_info.format in ["pdf", "docx"]:
                    file_format_map[file_path] = format_info
                    file_validation_map[file_path] = validation_result
                    valid_files.append(file_path)
                else:
                    logger.warning(
                        "不支持的格式,跳过: %s, 格式: %s",
                        file_path,
                        format_info.format,
                    )
                    self.stats["skipped_documents"] += 1

            except Exception as e:
                logger.error("格式识别失败,跳过: %s, 错误: %s", file_path, e)
                self.stats["failed_documents"] += 1

        if not valid_files:
            logger.warning("没有有效的文件需要处理")
            return []

        # 2. 使用MinerU批量API一次性处理所有文件(异步)
        all_documents = []

        # 获取共享的adapter实例
        if self._shared_adapter is None:
            from src.infrastructure.preprocessing.loaders.mineru_adapter import (
                MinerUAdapter,
            )

            self._shared_adapter = MinerUAdapter(config=self.config)

        # 准备批量处理的文件路径和格式
        file_formats = [file_format_map[fp].format for fp in valid_files]

        try:
            # 一次性批量处理所有文件(异步)
            logger.info(
                "使用MinerU批量API一次性处理 %d 个文件(异步)",
                len(valid_files),
            )
            batch_results = await self._shared_adapter.aextract_batch(
                valid_files, file_formats
            )

            # 3. 处理每个文件的结果
            for file_path in valid_files:
                try:
                    format_info = file_format_map[file_path]
                    validation_result = file_validation_map.get(file_path)

                    # 从批量结果中获取该文件的文档
                    # aextract_batch返回的key是标准化后的路径
                    normalized_path = str(Path(file_path).absolute().resolve())
                    documents = batch_results.get(
                        normalized_path, batch_results.get(file_path, [])
                    )

                    if not documents:
                        logger.warning("批量处理未返回文档: %s", file_path)
                        self.stats["failed_documents"] += 1
                        continue

                    # 4. LLM清洗(如果启用)
                    # 重要:逐个处理每个Document,避免一次性提交多个文档导致上下文过长
                    if self.enable_cleaning:
                        try:
                            ad_remover = LLMAdRemover(llm_service=self.llm_service)
                            cleaned_documents = []
                            for i, doc in enumerate(documents):
                                try:
                                    logger.info(
                                        "开始异步清洗文档 %d/%d (文件: %s): %s",
                                        i + 1,
                                        len(documents),
                                        file_path,
                                        doc.metadata.get("source", "unknown"),
                                    )
                                    # 逐个提交每个Document,避免上下文过长
                                    cleaned_doc = await ad_remover.aclean_document(doc)
                                    cleaned_documents.append(cleaned_doc)
                                    logger.info(
                                        "完成异步清洗文档 %d/%d (文件: %s): %s",
                                        i + 1,
                                        len(documents),
                                        file_path,
                                        doc.metadata.get("source", "unknown"),
                                    )
                                except Exception as e:
                                    logger.warning(
                                        f"异步清洗文档 {i + 1}/{len(documents)} (文件: {file_path}) 失败,保留原始文档: {e}"
                                    )
                                    cleaned_documents.append(doc)
                            documents = cleaned_documents
                            pipeline_name = "llm_ad_cleaning"
                        except Exception as e:
                            logger.warning(f"LLM清洗失败,跳过清洗步骤: {e}")
                            pipeline_name = "loader_only"
                    else:
                        pipeline_name = "loader_only"

                    # 5. 更新元数据
                    for doc in documents:
                        doc.metadata.update(
                            {
                                "preprocessed_at": datetime.now().isoformat(),
                                "preprocessor_version": "1.0.0",
                                "format_confidence": format_info.confidence,
                                "validation_warnings": (
                                    validation_result.warnings
                                    if validation_result
                                    else []
                                ),
                                "pipeline": pipeline_name,
                            }
                        )

                    # 6. 保存清洗后的Markdown文件(如果指定了输出目录且启用了清洗)
                    if (
                        self.output_dir
                        and self.enable_cleaning
                        and pipeline_name == "llm_ad_cleaning"
                    ):
                        self._save_cleaned_documents(
                            file_path, documents, format_info.format
                        )

                    # 7. 更新统计信息
                    self._update_stats(format_info.format, pipeline_name, success=True)
                    all_documents.extend(documents)

                    if self.enable_progress_tracking:
                        processed = len(
                            [
                                f
                                for f in valid_files
                                if f
                                in [d.metadata.get("source") for d in all_documents]
                            ]
                        )
                        progress = processed / len(valid_files) * 100
                        logger.info(
                            "异步处理进度: %.1f%% (%d/%d)",
                            progress,
                            processed,
                            len(valid_files),
                        )

                except Exception as e:
                    logger.error("处理文件结果失败: %s, 错误: %s", file_path, e)
                    self.stats["failed_documents"] += 1

        except Exception as e:
            logger.error("批量处理失败(异步): %s", e, exc_info=True)
            # 如果批量处理失败,记录所有文件为失败
            self.stats["failed_documents"] += len(valid_files)

        # 更新最终统计信息
        self.stats["end_time"] = datetime.now().timestamp()
        self.stats["processing_time"] = (
            self.stats["end_time"] - self.stats["start_time"]
        )

        logger.info("异步批量处理完成")
        logger.info("总文档数: %d", self.stats["total_documents"])
        logger.info("成功处理: %d", self.stats["processed_documents"])
        logger.info("处理失败: %d", self.stats["failed_documents"])
        logger.info("处理时间: %.2f秒", self.stats["processing_time"])
        logger.info("格式分布: %s", self.stats["format_distribution"])
        logger.info("管线分布: %s", self.stats["pipeline_distribution"])

        return all_documents

    def get_processing_stats(self) -> dict[str, Any]:
        """获取处理统计信息

        Returns:
            Dict[str, Any]: 统计信息字典
        """
        return {
            "total_documents": self.stats["total_documents"],
            "processed_documents": self.stats["processed_documents"],
            "failed_documents": self.stats["failed_documents"],
            "skipped_documents": self.stats["skipped_documents"],
            "success_rate": (
                self.stats["processed_documents"] / self.stats["total_documents"] * 100
                if self.stats["total_documents"] > 0
                else 0
            ),
            "format_distribution": self.stats["format_distribution"],
            "pipeline_distribution": self.stats["pipeline_distribution"],
            "start_time": self.stats["start_time"],
            "end_time": self.stats["end_time"],
            "processing_time": self.stats["processing_time"],
            "supported_formats": self.format_detector.get_supported_formats(),
            "cleaning_enabled": self.enable_cleaning,
        }

    def get_supported_formats(self) -> list[str]:
        """获取支持的文档格式列表

        Returns:
            List[str]: 支持的格式列表
        """
        return self.format_detector.get_supported_formats()

    def is_format_supported(self, file_path: str) -> bool:
        """检查文档格式是否支持

        Args:
            file_path: 文档路径

        Returns:
            bool: 是否支持该格式
        """
        try:
            format_info = self.format_detector.detect_format(file_path)
            return format_info.is_valid
        except Exception:
            return False

    def process_mineru_directory(
        self,
        mineru_dir: str | None = None,
    ) -> list[Document]:
        """处理 MinerU 已提取的目录中的所有文档

        遍历 data/processed/mineru 目录下的所有子目录,
        找到每个文档的 full.md 文件,清洗后保存为 clean.md,
        并复制 images 目录和元数据文件.

        目录结构:
        - 输入:data/processed/mineru/{doc_name}/{extracted_dir}/full.md
        - 输出:data/cleaned/documents/{doc_name}/{extracted_dir}/clean.md
        - 同时复制:images/ 目录,layout.json 等元数据文件

        Args:
            mineru_dir: MinerU 处理结果目录,默认为 'data/processed/mineru'

        Returns:
            List[Document]: 所有清洗后的 Document 列表

        Raises:
            ProcessingError: 如果启用清洗但清洗失败,会抛出异常终止任务
        """

        # 设置默认目录
        if mineru_dir is None:
            mineru_dir = "data/processed/mineru"

        mineru_path = Path(mineru_dir)

        if not mineru_path.exists():
            logger.warning(f"MinerU 目录不存在: {mineru_path}")
            return []

        logger.info("开始处理 MinerU 目录: %s", mineru_path)

        # 查找所有 full.md 文件
        full_md_files = list(mineru_path.rglob("full.md"))

        if not full_md_files:
            logger.warning(f"MinerU 目录中没有找到 full.md 文件: {mineru_path}")
            return []

        logger.info("找到 %d 个待处理的 Markdown 文件", len(full_md_files))

        # 初始化统计
        self.stats["total_documents"] = len(full_md_files)
        self.stats["start_time"] = datetime.now()

        # 获取或初始化清洗器
        if self.enable_cleaning and not hasattr(self, "_llm_ad_remover"):
            try:
                self._llm_ad_remover = LLMAdRemover(llm_service=self.llm_service)
            except Exception as e:
                logger.error(f"初始化 LLM 广告清洗器失败: {e}")
                msg = f"无法初始化清洗器: {e}"
                raise ProcessingError(msg) from e

        all_documents = []

        for i, full_md_path in enumerate(full_md_files):
            try:
                logger.info(
                    "处理文件 %d/%d: %s",
                    i + 1,
                    len(full_md_files),
                    full_md_path,
                )

                # 读取 full.md 内容
                with open(full_md_path, encoding="utf-8") as f:
                    markdown_content = f.read()

                if not markdown_content.strip():
                    logger.warning("文件内容为空,跳过: %s", full_md_path)
                    self.stats["skipped_documents"] += 1
                    continue

                # 获取 extracted_dir(full.md 所在的目录)
                extracted_dir = full_md_path.parent

                # 创建 Document 对象
                doc = Document(
                    page_content=markdown_content,
                    metadata={
                        "source": str(full_md_path),
                        "extracted_dir": str(extracted_dir),
                        "format": "markdown",
                        "preprocessed_at": datetime.now().isoformat(),
                        "preprocessor_version": "1.0.0",
                    },
                )

                # 清洗文档
                if self.enable_cleaning:
                    logger.info("开始清洗文档: %s", full_md_path)
                    # 清洗失败时抛出异常，终止任务
                    cleaned_doc = self._llm_ad_remover.clean_document(doc)
                    cleaned_doc.metadata["pipeline"] = "llm_ad_cleaning"
                    doc = cleaned_doc
                    
                    # 只有在启用清洗且清洗成功时才保存clean.md文件
                    if self.output_dir:
                        self._save_mineru_cleaned_document(extracted_dir, doc)
                else:
                    doc.metadata["pipeline"] = "loader_only"
                    # 如果未启用清洗，不保存clean.md文件

                all_documents.append(doc)
                self.stats["processed_documents"] += 1

                # 更新管线分布
                pipeline = doc.metadata.get("pipeline", "unknown")
                if pipeline not in self.stats["pipeline_distribution"]:
                    self.stats["pipeline_distribution"][pipeline] = 0
                self.stats["pipeline_distribution"][pipeline] += 1

                logger.info(
                    "完成处理文件 %d/%d: %s",
                    i + 1,
                    len(full_md_files),
                    full_md_path,
                )

            except Exception as e:
                # 如果是清洗失败，抛出明确的异常给用户
                error_msg = f"文档清洗失败: {full_md_path}, 错误: {e}"
                logger.error(error_msg)
                self.stats["failed_documents"] += 1
                # 将异常重新抛出，终止任务
                raise ProcessingError(error_msg) from e

        # 更新统计
        self.stats["end_time"] = datetime.now()
        if self.stats["start_time"]:
            self.stats["processing_time"] = (
                self.stats["end_time"] - self.stats["start_time"]
            ).total_seconds()

        logger.info("MinerU 目录处理完成")
        logger.info("总文档数: %d", self.stats["total_documents"])
        logger.info("成功处理: %d", self.stats["processed_documents"])
        logger.info("处理失败: %d", self.stats["failed_documents"])
        logger.info("跳过: %d", self.stats["skipped_documents"])
        logger.info("处理时间: %.2f秒", self.stats["processing_time"])

        return all_documents

    def _extract_image_references(self, markdown_content: str) -> set:
        """从 Markdown 内容中提取所有图片引用

        匹配格式:![](images/xxx.jpg) 或 ![alt](images/xxx.png) 等

        Args:
            markdown_content: Markdown 文档内容

        Returns:
            set: 被引用的图片文件名集合
        """
        import re

        # 匹配 Markdown 图片语法:![alt](path)
        # 提取 images/ 目录下的图片文件名
        pattern = r"!\[.*?\]\(images/([^)]+)\)"
        matches = re.findall(pattern, markdown_content)

        return set(matches)

    def _extract_text_content(self, markdown_content: str) -> set:
        """从清洗后的 Markdown 中提取所有文本内容片段

        提取所有非空行作为文本片段,用于与 JSON 元数据匹配.
        会去除 Markdown 语法标记,提取纯文本内容.

        Args:
            markdown_content: Markdown 文档内容

        Returns:
            set: 文本片段集合
        """
        import re

        text_fragments = set()

        for line in markdown_content.split("\n"):
            line = line.strip()
            if not line:
                continue

            # 跳过纯图片行
            if re.match(r"^!\[.*?\]\(.*?\)$", line):
                continue

            # 去除 Markdown 标题标记
            line = re.sub(r"^#+\s*", "", line)

            # 去除加粗,斜体标记
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            line = re.sub(r"\*(.+?)\*", r"\1", line)

            # 去除行内代码标记
            line = re.sub(r"`(.+?)`", r"\1", line)

            # 去除链接标记,保留文本
            line = re.sub(r"\[(.+?)\]\(.*?\)", r"\1", line)

            # 去除图片标记
            line = re.sub(r"!\[.*?\]\(.*?\)", "", line)

            line = line.strip()
            if line and len(line) > 2:  # 忽略太短的片段
                text_fragments.add(line)

        return text_fragments

    def _text_matches_fragment(self, json_text: str, text_fragments: set) -> bool:
        """检查 JSON 中的文本是否在清洗后的文档中存在

        使用子串匹配,因为 LLM 清洗可能会对文本进行微调.

        Args:
            json_text: JSON 元数据中的文本
            text_fragments: 清洗后文档的文本片段集合

        Returns:
            bool: 是否匹配
        """
        import re

        if not json_text:
            return False

        # 清理 HTML 标签(如 <sup>1</sup>)
        clean_text = re.sub(r"<[^>]+>", "", json_text)
        clean_text = clean_text.strip()

        if not clean_text or len(clean_text) < 3:
            return False

        # 精确匹配
        if clean_text in text_fragments:
            return True

        # 子串匹配(JSON 文本是否包含在任一片段中)
        for fragment in text_fragments:
            if clean_text in fragment or fragment in clean_text:
                return True
            # 前20个字符匹配(处理截断情况)
            if len(clean_text) > 20 and len(fragment) > 20:
                if clean_text[:20] in fragment or fragment[:20] in clean_text:
                    return True

        return False

    def _filter_content_list(
        self,
        content_list: list,
        text_fragments: set,
        retained_images: set,
    ) -> list:
        """过滤 content_list.json,只保留清洗后文档中存在的内容

        Args:
            content_list: 原始 content_list.json 数据
            text_fragments: 清洗后文档的文本片段集合
            retained_images: 保留的图片文件名集合

        Returns:
            list: 过滤后的 content_list
        """
        filtered = []

        for item in content_list:
            item_type = item.get("type", "")

            if item_type == "image":
                # 检查图片是否被保留
                img_path = item.get("img_path", "")
                if img_path:
                    # img_path 格式:images/xxx.jpg,提取文件名
                    img_name = img_path.split("/")[-1] if "/" in img_path else img_path
                    if img_name in retained_images:
                        filtered.append(item)

            elif item_type == "text":
                # 检查文本是否在清洗后的文档中
                text = item.get("text", "")
                if self._text_matches_fragment(text, text_fragments):
                    filtered.append(item)

            elif item_type == "table":
                # 表格通常保留
                filtered.append(item)

            else:
                # 其他类型(如公式),检查是否有文本内容
                text = item.get("text", "")
                if text and self._text_matches_fragment(text, text_fragments):
                    filtered.append(item)

        return filtered

    def _filter_model_json(
        self,
        model_data: list,
        text_fragments: set,
        retained_images: set,
    ) -> list:
        """过滤 model.json,只保留清洗后文档中存在的内容

        model.json 是二维数组,每页一个数组.

        Args:
            model_data: 原始 model.json 数据(二维数组)
            text_fragments: 清洗后文档的文本片段集合
            retained_images: 保留的图片文件名集合

        Returns:
            list: 过滤后的 model.json(保持二维结构)
        """
        filtered_pages = []

        for page_items in model_data:
            filtered_page = []

            for item in page_items:
                item_type = item.get("type", "")
                content = item.get("content")

                if item_type == "image":
                    # model.json 中的图片没有路径,无法直接匹配
                    # 保守策略:如果有任何图片被保留,则保留所有图片元素
                    if retained_images:
                        filtered_page.append(item)

                elif item_type in ["header", "footer"]:
                    # 页眉页脚通常被清洗删除,跳过
                    continue

                elif content:
                    # 有内容的元素,检查是否匹配
                    if self._text_matches_fragment(content, text_fragments):
                        filtered_page.append(item)

                elif item_type == "table":
                    # 表格通常保留
                    filtered_page.append(item)

            filtered_pages.append(filtered_page)

        return filtered_pages

    def _filter_layout_json(
        self,
        layout_data: dict,
        text_fragments: set,
        retained_images: set,
    ) -> dict:
        """过滤 layout.json,只保留清洗后文档中存在的内容

        layout.json 结构复杂:pdf_info -> 每页 -> para_blocks -> lines -> spans

        Args:
            layout_data: 原始 layout.json 数据
            text_fragments: 清洗后文档的文本片段集合
            retained_images: 保留的图片文件名集合(不带 images/ 前缀)

        Returns:
            dict: 过滤后的 layout.json
        """
        if "pdf_info" not in layout_data:
            return layout_data

        filtered_pdf_info = []

        for page_info in layout_data["pdf_info"]:
            filtered_page = {}

            # 复制页面级元数据
            for key, value in page_info.items():
                if key != "para_blocks":
                    filtered_page[key] = value

            # 过滤 para_blocks
            if "para_blocks" in page_info:
                filtered_para_blocks = []

                for para_block in page_info["para_blocks"]:
                    block_type = para_block.get("type", "")

                    if block_type == "image":
                        # 检查图片是否被保留
                        # 图片路径在 blocks -> lines -> spans -> image_path
                        image_retained = False
                        blocks = para_block.get("blocks", [])
                        for block in blocks:
                            for line in block.get("lines", []):
                                for span in line.get("spans", []):
                                    img_path = span.get("image_path", "")
                                    if img_path and img_path in retained_images:
                                        image_retained = True
                                        break

                        if image_retained:
                            filtered_para_blocks.append(para_block)

                    else:
                        # 文本或其他类型,检查 lines -> spans -> content
                        content_retained = False

                        for line in para_block.get("lines", []):
                            for span in line.get("spans", []):
                                content = span.get("content", "")
                                if content and self._text_matches_fragment(
                                    content, text_fragments
                                ):
                                    content_retained = True
                                    break
                            if content_retained:
                                break

                        if content_retained:
                            filtered_para_blocks.append(para_block)

                filtered_page["para_blocks"] = filtered_para_blocks

            filtered_pdf_info.append(filtered_page)

        result = dict(layout_data)
        result["pdf_info"] = filtered_pdf_info
        return result

    def _rebuild_metadata_files(
        self,
        extracted_path: Path,
        output_dir: Path,
        doc: Document,
        retained_images: set,
    ) -> None:
        """重构所有元数据 JSON 文件

        根据清洗后的 Markdown 内容过滤 content_list.json,model.json,layout.json,
        只保留文档中仍存在的内容块.

        Args:
            extracted_path: 源文件目录路径
            output_dir: 输出目录路径
            doc: 清洗后的 Document 对象
            retained_images: 保留的图片文件名集合
        """
        import json

        # 提取清洗后文档的文本片段
        text_fragments = self._extract_text_content(doc.page_content)

        logger.info(
            "开始重构元数据文件,文本片段数: %d, 保留图片数: %d",
            len(text_fragments),
            len(retained_images),
        )
        logger.info("源目录 (extracted_path): %s", extracted_path)
        logger.info("输出目录 (output_dir): %s", output_dir)

        # 查找并处理 content_list.json(可能有 UUID 前缀)
        content_list_files = list(extracted_path.glob("*content_list.json"))
        logger.info(
            "找到 %d 个 content_list.json 文件: %s",
            len(content_list_files),
            [f.name for f in content_list_files],
        )
        for content_list_file in content_list_files:
            try:
                with open(content_list_file, encoding="utf-8") as f:
                    content_list = json.load(f)

                original_count = len(content_list)
                filtered_content_list = self._filter_content_list(
                    content_list, text_fragments, retained_images
                )

                # 保存为 clean_content_list.json
                output_file = output_dir / "clean_content_list.json"
                logger.info("准备保存 clean_content_list.json 到: %s", output_file)
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(filtered_content_list, f, ensure_ascii=False, indent=2)

                logger.info(
                    "已重构 content_list.json: %d -> %d 个元素",
                    original_count,
                    len(filtered_content_list),
                )
                logger.info("✅ clean_content_list.json 已保存到: %s", output_file)

                # 删除输出目录中可能存在的带 UUID 前缀的 content_list.json 文件
                for old_file in output_dir.glob("*_content_list.json"):
                    if old_file.name != "clean_content_list.json":
                        try:
                            old_file.unlink()
                            logger.debug(
                                f"已删除旧的 content_list.json 文件: {old_file.name}"
                            )
                        except Exception as e:
                            logger.warning(
                                f"删除旧文件失败: {old_file.name}, 错误: {e}"
                            )

            except Exception as e:
                # 回退策略: 如果过滤失败,至少复制原始 content_list.json 为 clean_content_list.json
                logger.error(f"处理 content_list.json 失败,使用原始文件回退: {e}")
                try:
                    fallback_output = output_dir / "clean_content_list.json"
                    with open(content_list_file, encoding="utf-8") as f_src, open(
                        fallback_output, "w", encoding="utf-8"
                    ) as f_dst:
                        json.dump(json.load(f_src), f_dst, ensure_ascii=False, indent=2)
                    logger.warning(
                        "已使用原始 content_list.json 生成回退文件: %s", fallback_output
                    )
                except Exception as fallback_e:
                    logger.error(f"回退复制 content_list.json 失败: {fallback_e}")

        # 查找并处理 model.json(可能有 UUID 前缀)
        model_json_files = list(extracted_path.glob("*model.json"))
        for model_json_file in model_json_files:
            try:
                with open(model_json_file, encoding="utf-8") as f:
                    model_data = json.load(f)

                original_count = sum(len(page) for page in model_data)
                filtered_model = self._filter_model_json(
                    model_data, text_fragments, retained_images
                )
                filtered_count = sum(len(page) for page in filtered_model)

                # 保存为 clean_model.json
                output_file = output_dir / "clean_model.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(filtered_model, f, ensure_ascii=False, indent=2)

                logger.info(
                    "已重构 model.json: %d -> %d 个元素",
                    original_count,
                    filtered_count,
                )

                # 删除输出目录中可能存在的带 UUID 前缀的 model.json 文件
                for old_file in output_dir.glob("*_model.json"):
                    if old_file.name != "clean_model.json":
                        try:
                            old_file.unlink()
                            logger.debug(f"已删除旧的 model.json 文件: {old_file.name}")
                        except Exception as e:
                            logger.warning(
                                f"删除旧文件失败: {old_file.name}, 错误: {e}"
                            )

            except Exception as e:
                # 回退策略: 如果过滤失败,至少复制原始 model.json 为 clean_model.json
                logger.error(f"处理 model.json 失败,使用原始文件回退: {e}")
                try:
                    fallback_output = output_dir / "clean_model.json"
                    with open(model_json_file, encoding="utf-8") as f_src, open(
                        fallback_output, "w", encoding="utf-8"
                    ) as f_dst:
                        json.dump(json.load(f_src), f_dst, ensure_ascii=False, indent=2)
                    logger.warning(
                        "已使用原始 model.json 生成回退文件: %s", fallback_output
                    )
                except Exception as fallback_e:
                    logger.error(f"回退复制 model.json 失败: {fallback_e}")

        # 处理 layout.json(没有 UUID 前缀)
        layout_file = extracted_path / "layout.json"
        if layout_file.exists():
            try:
                with open(layout_file, encoding="utf-8") as f:
                    layout_data = json.load(f)

                # 统计原始 para_blocks 数量
                original_count = sum(
                    len(page.get("para_blocks", []))
                    for page in layout_data.get("pdf_info", [])
                )

                filtered_layout = self._filter_layout_json(
                    layout_data, text_fragments, retained_images
                )

                filtered_count = sum(
                    len(page.get("para_blocks", []))
                    for page in filtered_layout.get("pdf_info", [])
                )

                # 保存为 clean_layout.json
                output_file = output_dir / "clean_layout.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(filtered_layout, f, ensure_ascii=False, indent=2)

                logger.info(
                    "已重构 layout.json: %d -> %d 个段落块",
                    original_count,
                    filtered_count,
                )

            except Exception as e:
                logger.error(f"处理 layout.json 失败: {e}")

    def _generate_rag_media_manifest(
        self,
        output_dir: Path,
        retained_images: set,
    ) -> list[dict]:
        """生成 rag_media_manifest 用于 RAG 流程的图片映射

        从 clean_content_list.json 中提取图片信息,建立 figure_name 到 original_uuid 的映射.

        Args:
            output_dir: 输出目录路径 (包含 images/ 目录和 clean_content_list.json)
            retained_images: 保留的图片文件名集合 (UUID 格式)

        Returns:
            list[dict]: rag_media_manifest 列表,每个元素包含 figure_name, original_uuid, json_file
        """
        import json
        import uuid as uuid_module

        manifest = []
        
        # 查找 clean_content_list.json
        content_list_file = output_dir / "clean_content_list.json"
        if not content_list_file.exists():
            logger.warning("clean_content_list.json 不存在,无法生成 rag_media_manifest")
            return manifest
        
        try:
            with open(content_list_file, encoding="utf-8") as f:
                content_list = json.load(f)
        except Exception as e:
            logger.error(f"读取 clean_content_list.json 失败: {e}")
            return manifest
        
        # 查找 images 目录,建立 UUID 到文件名的映射
        images_dir = output_dir / "images"
        uuid_to_filename = {}
        if images_dir.exists():
            for img_file in images_dir.glob("*.jpg"):
                try:
                    # 验证是否为 UUID 格式
                    uuid_module.UUID(img_file.stem)
                    uuid_to_filename[img_file.stem] = img_file.name
                except ValueError:
                    # 非 UUID 格式,跳过
                    continue
        
        # 处理每个图片条目
        for item in content_list:
            if not isinstance(item, dict):
                continue
            
            if item.get("type") != "image":
                continue
            
            img_path = item.get("img_path", "")
            if not img_path:
                continue
            
            # 提取图片文件名
            img_filename = Path(img_path).name if "/" in img_path else img_path
            
            # 检查图片是否被保留
            if img_filename not in retained_images:
                continue
            
            # 提取 figure_name (从 image_caption 中找以'图'开头的标题)
            figure_name = None
            image_captions = item.get("image_caption", [])
            if isinstance(image_captions, list):
                for caption in image_captions:
                    if caption and isinstance(caption, str) and caption.strip():
                        if caption.startswith("图"):
                            figure_name = caption.strip()
                            break
                # 如果没找到以'图'开头的标题,使用第一个标题
                if not figure_name and image_captions:
                    caption = image_captions[0]
                    if caption and isinstance(caption, str):
                        figure_name = caption.strip()
            elif isinstance(image_captions, str) and image_captions:
                figure_name = image_captions.strip()
            
            # 如果没有标题,使用 img_path 中的文件名
            if not figure_name:
                figure_name = img_filename
            
            # 确保 figure_name 以 .jpg 结尾
            if not figure_name.endswith(".jpg"):
                figure_name = f"{figure_name}.jpg"
            
            # 查找对应的 UUID 文件名
            original_uuid = None
            for uuid_stem, filename in uuid_to_filename.items():
                if filename == img_filename:
                    original_uuid = filename  # 已经是完整文件名
                    break
            
            # 如果找不到 UUID 格式的文件,使用原始文件名
            if not original_uuid:
                original_uuid = img_filename
            
            # 查找对应的 JSON 文件
            json_file = None
            datajson_dir = output_dir / "datajson"
            if datajson_dir.exists():
                # 优先使用 figure_name 查找
                json_candidate = f"{Path(figure_name).stem}.json"
                json_path = datajson_dir / json_candidate
                if json_path.exists():
                    json_file = json_candidate
                else:
                    # 如果找不到,尝试使用 UUID 查找
                    for json_file_path in datajson_dir.glob("*.json"):
                        if Path(json_file_path).stem == Path(original_uuid).stem:
                            json_file = json_file_path.name
                            break
            
            manifest_entry = {
                "figure_name": figure_name,
                "original_uuid": original_uuid,
                "json_file": json_file,
            }
            manifest.append(manifest_entry)
            logger.debug(
                "生成 rag_media_manifest 条目: figure_name=%s, original_uuid=%s, json_file=%s",
                figure_name, original_uuid, json_file
            )
        
        logger.info("生成 rag_media_manifest 完成: 共 %d 条目", len(manifest))
        return manifest

    def _save_mineru_cleaned_document(
        self,
        extracted_dir: Path,
        doc: Document,
    ) -> None:
        """保存 MinerU 清洗后的文档,只复制被引用的图片

        按照 T031A 要求的目录结构保存:
        - 输出:data/cleaned/documents/{doc_name}/{extracted_dir}/clean.md
        - 只复制清洗后文档中仍被引用的图片
        - 更新元数据记录保留和删除的图片信息

        Args:
            extracted_dir: 源文件的 extracted_dir 路径
            doc: 清洗后的 Document 对象
        """
        import shutil

        if not self.output_dir:
            return

        try:
            extracted_path = Path(extracted_dir)

            # 获取相对路径(相对于 processed/mineru)
            # 结构:data/processed/mineru/{doc_name}_xx/{cache_key}_extracted/
            try:
                # 尝试找到 mineru 目录的位置
                parts = extracted_path.parts
                for j, part in enumerate(parts):
                    if part == "mineru" and j + 2 < len(parts):
                        # 获取 {doc_name}_xx/{cache_key}_extracted 部分
                        relative_parts = parts[j + 1 :]
                        relative_path = Path(*relative_parts)
                        break
                else:
                    # 如果找不到 mineru 目录,使用最后两级目录
                    relative_path = (
                        Path(extracted_path.parent.name) / extracted_path.name
                    )
            except Exception:
                # 如果无法获取相对路径,使用最后两级目录
                relative_path = Path(extracted_path.parent.name) / extracted_path.name

            # 创建输出目录
            output_dir = self.output_dir / relative_path
            output_dir.mkdir(parents=True, exist_ok=True)

            # 保存清洗后的 Markdown 文件
            output_md_path = output_dir / "clean.md"
            with open(output_md_path, "w", encoding="utf-8") as f:
                f.write(doc.page_content)
            logger.info("已保存清洗后的Markdown文件: %s", output_md_path)

            # 提取清洗后文档中仍被引用的图片
            referenced_images = self._extract_image_references(doc.page_content)

            # 初始化 retained_images(确保在所有情况下都有定义)
            retained_images = set()

            # 只复制被引用的图片(而不是整个 images 目录)
            source_images_dir = extracted_path / "images"
            if source_images_dir.exists() and source_images_dir.is_dir():
                # 获取源目录中的所有图片
                all_source_images = {
                    f.name for f in source_images_dir.iterdir() if f.is_file()
                }

                # 计算被保留和被删除的图片
                retained_images = referenced_images & all_source_images
                removed_images = all_source_images - referenced_images

                # 创建目标 images 目录
                dest_images_dir = output_dir / "images"
                if dest_images_dir.exists():
                    shutil.rmtree(dest_images_dir)
                dest_images_dir.mkdir(parents=True, exist_ok=True)

                # 只复制被引用的图片
                copied_count = 0
                for image_name in retained_images:
                    source_image = source_images_dir / image_name
                    if source_image.exists():
                        dest_image = dest_images_dir / image_name
                        shutil.copy2(source_image, dest_image)
                        copied_count += 1

                # 更新 Document 的 metadata
                doc.metadata["images_stats"] = {
                    "total_source_images": len(all_source_images),
                    "retained_images_count": len(retained_images),
                    "removed_images_count": len(removed_images),
                }
                doc.metadata["retained_images"] = list(retained_images)
                doc.metadata["removed_images"] = list(removed_images)

                logger.info(
                    "图片处理完成: 源目录 %d 张, 保留 %d 张, 删除 %d 张",
                    len(all_source_images),
                    len(retained_images),
                    len(removed_images),
                )

                if removed_images:
                    logger.debug("被删除的图片: %s", removed_images)
            else:
                logger.warning("源 images 目录不存在: %s", source_images_dir)

            # 重构元数据文件(content_list.json, model.json, layout.json)
            # 根据清洗后的内容过滤,只保留文档中仍存在的内容块
            self._rebuild_metadata_files(
                extracted_path=extracted_path,
                output_dir=output_dir,
                doc=doc,
                retained_images=retained_images,
            )

            # 图表转JSON(如果启用)
            if self.enable_chart_conversion:
                try:
                    from src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter import (
                        LLMChartToJsonConverter,
                    )

                    logger.info("开始图表转JSON转换: %s", output_dir)
                    chart_converter = LLMChartToJsonConverter(
                        llm_service=self.llm_service
                    )
                    chart_result = chart_converter.process_mineru_directory(
                        str(output_dir), create_datajson_dir=True
                    )
                    stats = chart_result.get("overall_statistics", {})
                    logger.info(
                        "图表转JSON完成: 处理 %d 个图像, "
                        "发现 %d 个图表, "
                        "生成 %d 个JSON文件",
                        stats.get("total_images_processed", 0),
                        stats.get("total_charts_found", 0),
                        stats.get("total_json_files_generated", 0),
                    )
                    
                    # 生成 rag_media_manifest
                    rag_media_manifest = self._generate_rag_media_manifest(
                        output_dir, retained_images
                    )
                    
                    # 保存 rag_media_manifest 到 JSON 文件
                    if rag_media_manifest:
                        manifest_file = output_dir / "rag_media_manifest.json"
                        import json
                        with open(manifest_file, "w", encoding="utf-8") as f:
                            json.dump(rag_media_manifest, f, ensure_ascii=False, indent=2)
                        logger.info("已保存 rag_media_manifest 到: %s", manifest_file)
                        
                        # 更新 Document 的 metadata
                        doc.metadata["rag_media_manifest"] = rag_media_manifest
                        
                except Exception as e:
                    logger.warning("图表转JSON失败,不影响主流程: {}", e)

        except Exception as e:
            logger.error("保存清洗后的文件失败: %s", e)


class DocumentPreprocessorError(ProcessingError):
    """文档预处理协调器专用异常"""
