"""
预处理质量报告生成器

基于文档预处理任务的执行结果,生成结构化的质量报告。
聚合来自T031预处理协调器、T030A LLM清洗器、T031B图表转换器等组件的统计信息。

生成命令: /speckit.implement T039
生成时间: 2025-12-17
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.shared.config.settings import get_config
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentQualityMetrics(BaseModel):
    """单个文档的质量指标"""

    document_id: str = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    file_format: str = Field(..., description="文档格式")
    file_size: int = Field(..., description="文件大小(字节)")

    # 处理状态
    processing_status: str = Field(..., description="处理状态")
    processing_time: float | None = Field(None, description="处理时间(秒)")
    error_message: str | None = Field(None, description="错误信息")

    # 预处理统计
    original_length: int | None = Field(None, description="原始内容长度")
    cleaned_length: int | None = Field(None, description="清洗后内容长度")
    content_reduction_rate: float | None = Field(None, description="内容减少率(%)")

    # 图表处理统计
    total_images: int | None = Field(0, description="总图片数")
    charts_found: int | None = Field(0, description="发现的图表数")
    charts_converted: int | None = Field(0, description="成功转换的图表数")

    # 元数据
    pipeline_used: str | None = Field(None, description="使用的处理管线")
    confidence_score: float | None = Field(None, description="格式识别置信度")
    validation_warnings: list[str] | None = Field(None, description="验证警告")


class ReportStatistics(BaseModel):
    """报告统计信息"""

    # 总体统计
    total_documents: int = Field(..., description="总文档数")
    processed_documents: int = Field(..., description="成功处理的文档数")
    failed_documents: int = Field(..., description="处理失败的文档数")
    skipped_documents: int = Field(0, description="跳过的文档数")

    # 成功率和性能
    success_rate: float = Field(..., description="成功率(%)")
    average_processing_time: float | None = Field(None, description="平均处理时间(秒)")
    total_processing_time: float | None = Field(None, description="总处理时间(秒)")

    # 格式分布
    format_distribution: dict[str, int] = Field(
        default_factory=dict, description="格式分布统计"
    )

    # 管线分布
    pipeline_distribution: dict[str, int] = Field(
        default_factory=dict, description="处理管线分布"
    )

    # 内容质量统计
    total_original_length: int | None = Field(None, description="原始内容总长度")
    total_cleaned_length: int | None = Field(None, description="清洗后内容总长度")
    average_content_reduction: float | None = Field(
        None, description="平均内容减少率(%)"
    )

    # 图表处理统计
    total_images: int | None = Field(0, description="总图片数")
    total_charts_found: int | None = Field(0, description="发现的图表总数")
    total_charts_converted: int | None = Field(0, description="成功转换的图表总数")
    chart_conversion_rate: float | None = Field(None, description="图表转换成功率(%)")

    # 错误统计
    error_categories: dict[str, int] = Field(
        default_factory=dict, description="错误分类统计"
    )

    # 时间戳
    report_generated_at: datetime = Field(
        default_factory=datetime.now, description="报告生成时间"
    )


class QualityReport(BaseModel):
    """质量报告模型"""

    job_id: str = Field(..., description="任务ID")
    job_type: str = Field(..., description="任务类型")

    # 时间信息
    started_at: datetime | None = Field(None, description="任务开始时间")
    completed_at: datetime | None = Field(None, description="任务完成时间")
    duration: float | None = Field(None, description="任务持续时间(秒)")

    # 统计信息
    statistics: ReportStatistics = Field(..., description="统计信息")

    # 文档质量指标列表
    document_metrics: list[DocumentQualityMetrics] = Field(
        default_factory=list, description="文档质量指标列表"
    )

    # 配置信息
    configuration: dict[str, Any] = Field(
        default_factory=dict, description="任务配置信息"
    )

    # 附加信息
    notes: str | None = Field(None, description="附加说明")
    recommendations: list[str] | None = Field(None, description="改进建议")


class QualityReportGenerator:
    """
    预处理质量报告生成器

    基于任务ID从数据库中聚合处理结果,生成结构化的质量报告。
    支持JSON和Markdown格式的输出。
    """

    def __init__(self, db_path: str | None = None):
        """初始化质量报告生成器

        Args:
            db_path: 数据库路径,如果为None则使用默认配置
        """
        self.config = get_config()
        self.db_path = db_path or str(Path(self.config.data_dir) / "whitepaper.db")

        logger.info(f"质量报告生成器初始化完成,数据库路径: {self.db_path}")

    def _get_db_connection(self) -> sqlite3.Connection:
        """获取数据库连接

        Returns:
            sqlite3.Connection: 数据库连接对象
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 启用字典式访问
            return conn
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            msg = f"无法连接到数据库: {e}"
            raise ProcessingError(msg) from e

    def _get_job_info(self, job_id: str) -> dict[str, Any]:
        """获取任务基本信息

        Args:
            job_id: 任务ID

        Returns:
            任务信息字典
        """
        conn = self._get_db_connection()
        try:
            # 查询任务表
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, status, created_at, updated_at, metadata, result
                FROM tasks
                WHERE id = ? OR name = ?
            """,
                (job_id, job_id),
            )

            task_row = cursor.fetchone()
            if not task_row:
                # 尝试查询文档表
                cursor.execute(
                    """
                    SELECT id, filename, status, uploaded_at, parsed_at, metadata
                    FROM documents
                    WHERE id = ? OR filename LIKE ?
                """,
                    (job_id, f"%{job_id}%"),
                )

                doc_rows = cursor.fetchall()
                if doc_rows:
                    # 基于文档构造虚拟任务信息
                    return self._construct_job_from_documents(doc_rows, job_id)

                msg = f"未找到任务: {job_id}"
                raise ProcessingError(msg)

            # 解析任务信息
            task_info = {
                "job_id": task_row["id"],
                "job_name": task_row["name"],
                "status": task_row["status"],
                "started_at": task_row["created_at"],
                "completed_at": task_row["updated_at"],
                "metadata": (
                    json.loads(task_row["metadata"]) if task_row["metadata"] else {}
                ),
                "result": json.loads(task_row["result"]) if task_row["result"] else {},
            }

            return task_info

        except Exception as e:
            logger.error(f"获取任务信息失败: {e}")
            msg = f"获取任务信息失败: {e}"
            raise ProcessingError(msg) from e
        finally:
            conn.close()

    def _construct_job_from_documents(
        self, doc_rows: list[sqlite3.Row], job_id: str
    ) -> dict[str, Any]:
        """基于文档信息构造虚拟任务信息

        Args:
            doc_rows: 文档行数据列表
            job_id: 任务ID

        Returns:
            虚拟任务信息字典
        """
        if not doc_rows:
            msg = f"未找到相关文档: {job_id}"
            raise ProcessingError(msg)

        # 计算时间范围
        start_time = min(row["uploaded_at"] for row in doc_rows)
        parsed_times = [row["parsed_at"] for row in doc_rows if row["parsed_at"]]
        end_time = max(parsed_times) if parsed_times else None

        # 统计状态
        status_counts: dict[str, int] = {}
        for row in doc_rows:
            status = row["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

        # 确定总体状态
        if status_counts.get("FAILED", 0) > 0:
            overall_status = "FAILED"
        elif status_counts.get("PARSING", 0) > 0:
            overall_status = "PARSING"
        elif status_counts.get("INDEXED", 0) == len(doc_rows):
            overall_status = "COMPLETED"
        else:
            overall_status = "PENDING"

        return {
            "job_id": f"doc_batch_{job_id}",
            "job_name": f"文档批次处理_{job_id}",
            "status": overall_status,
            "started_at": start_time,
            "completed_at": end_time,
            "metadata": {
                "document_count": len(doc_rows),
                "constructed_from_documents": True,
            },
            "result": {
                "file_count": len(doc_rows),
                "processed_files": [row["filename"] for row in doc_rows],
                "status_distribution": status_counts,
            },
        }

    def _get_document_metrics(
        self,
        job_id: str,
        job_info: dict[str, Any] | None = None,
    ) -> list[DocumentQualityMetrics]:
        """获取文档质量指标

        Args:
            job_id: 任务ID

        Returns:
            文档质量指标列表
        """
        conn = self._get_db_connection()
        try:
            cursor = conn.cursor()

            doc_rows: list[sqlite3.Row] = []

            # 优先使用任务结果中的关联文件信息进行精确过滤
            if job_info and isinstance(job_info.get("result"), dict):
                result_data = job_info["result"]
                filenames: list[str] = []

                for key in ("processed_files", "failed_files", "skipped_files"):
                    value = result_data.get(key)
                    if isinstance(value, list):
                        filenames.extend(str(v) for v in value)

                # 去重
                filenames = list(dict.fromkeys(filenames))

                if filenames:
                    placeholders = ",".join("?" for _ in filenames)
                    cursor.execute(
                        f"""
                        SELECT id, filename, file_path, file_size, mime_type,
                               status, uploaded_at, parsed_at, error_message, metadata
                        FROM documents
                        WHERE filename IN ({placeholders})
                        ORDER BY uploaded_at
                        """,  # noqa: S608 placeholders are parameterized
                        filenames,
                    )
                    doc_rows = cursor.fetchall()

            # 如果任务结果中没有显式的文件列表, 回退到基于 job_id 的模糊匹配
            if not doc_rows:
                cursor.execute(
                    """
                    SELECT id, filename, file_path, file_size, mime_type,
                           status, uploaded_at, parsed_at, error_message, metadata
                    FROM documents
                    WHERE id = ? OR filename LIKE ? OR metadata LIKE ?
                    ORDER BY uploaded_at
                    """,
                    (job_id, f"%{job_id}%", f"%{job_id}%"),
                )
                doc_rows = cursor.fetchall()

            # 如果仍然没有找到, 作为最后兜底: 查询所有文档
            if not doc_rows:
                cursor.execute(
                    """
                    SELECT id, filename, file_path, file_size, mime_type,
                           status, uploaded_at, parsed_at, error_message, metadata
                    FROM documents
                    ORDER BY uploaded_at
                    """
                )
                doc_rows = cursor.fetchall()
            metrics = []

            for row in doc_rows:
                try:
                    # 解析元数据
                    metadata = json.loads(row["metadata"]) if row["metadata"] else {}

                    # 计算处理时间
                    processing_time = None
                    if row["uploaded_at"] and row["parsed_at"]:
                        start = datetime.fromisoformat(row["uploaded_at"])
                        end = datetime.fromisoformat(row["parsed_at"])
                        processing_time = (end - start).total_seconds()

                    # 提取统计信息
                    images_stats = metadata.get("images_stats", {})
                    cleaning_stats = metadata.get("processing_stats", {})
                    chart_stats = metadata.get("chart_conversion_stats", {})

                    # 计算内容减少率
                    content_reduction_rate = None
                    original_length = cleaning_stats.get("original_length")
                    cleaned_length = cleaning_stats.get("cleaned_length")
                    if original_length and cleaned_length and original_length > 0:
                        content_reduction_rate = round(
                            (1 - cleaned_length / original_length) * 100, 1
                        )

                    # 创建文档质量指标
                    metric = DocumentQualityMetrics(
                        document_id=row["id"],
                        filename=row["filename"],
                        file_format=metadata.get("format", "unknown"),
                        file_size=row["file_size"],
                        processing_status=row["status"],
                        processing_time=processing_time,
                        error_message=row["error_message"],
                        # 预处理统计
                        original_length=original_length,
                        cleaned_length=cleaned_length,
                        content_reduction_rate=content_reduction_rate,
                        # 图表处理统计
                        total_images=images_stats.get("total_source_images", 0),
                        charts_found=chart_stats.get("charts_found", 0),
                        charts_converted=chart_stats.get("charts_converted", 0),
                        # 元数据
                        pipeline_used=metadata.get("pipeline"),
                        confidence_score=metadata.get("format_confidence"),
                        validation_warnings=metadata.get("validation_warnings", []),
                    )

                    metrics.append(metric)

                except Exception as e:
                    logger.warning(f"处理文档指标失败: {row['filename']}, 错误: {e}")
                    continue

            return metrics

        except Exception as e:
            logger.error(f"获取文档质量指标失败: {e}")
            msg = f"获取文档质量指标失败: {e}"
            raise ProcessingError(msg) from e
        finally:
            conn.close()

    def _calculate_statistics(
        self, document_metrics: list[DocumentQualityMetrics]
    ) -> ReportStatistics:
        """计算统计信息

        Args:
            document_metrics: 文档质量指标列表

        Returns:
            统计信息对象
        """
        if not document_metrics:
            return ReportStatistics(
                total_documents=0,
                processed_documents=0,
                failed_documents=0,
                success_rate=0.0,
                skipped_documents=0,
                average_processing_time=None,
                total_processing_time=None,
                total_original_length=None,
                total_cleaned_length=None,
                average_content_reduction=None,
                total_images=0,
                total_charts_found=0,
                total_charts_converted=0,
                chart_conversion_rate=None,
                format_distribution={},
                pipeline_distribution={},
                error_categories={},
            )

        total_docs = len(document_metrics)
        processed_docs = len(
            [m for m in document_metrics if m.processing_status == "INDEXED"]
        )
        failed_docs = len(
            [m for m in document_metrics if m.processing_status == "FAILED"]
        )
        skipped_docs = len(
            [m for m in document_metrics if m.processing_status == "PENDING"]
        )

        # 计算成功率
        success_rate = (processed_docs / total_docs * 100) if total_docs > 0 else 0.0

        # 计算平均处理时间
        processing_times = [
            m.processing_time for m in document_metrics if m.processing_time is not None
        ]
        avg_processing_time = (
            sum(processing_times) / len(processing_times) if processing_times else None
        )
        total_processing_time = sum(processing_times) if processing_times else None

        # 格式分布
        format_dist: dict[str, int] = {}
        for metric in document_metrics:
            fmt = metric.file_format
            format_dist[fmt] = format_dist.get(fmt, 0) + 1

        # 管线分布
        pipeline_dist: dict[str, int] = {}
        for metric in document_metrics:
            pipeline = metric.pipeline_used or "unknown"
            pipeline_dist[pipeline] = pipeline_dist.get(pipeline, 0) + 1

        # 内容质量统计
        total_original_length = sum(m.original_length or 0 for m in document_metrics)
        total_cleaned_length = sum(m.cleaned_length or 0 for m in document_metrics)

        avg_content_reduction = None
        if total_original_length > 0:
            avg_content_reduction = round(
                (1 - total_cleaned_length / total_original_length) * 100, 1
            )

        # 图表处理统计
        total_images = sum(m.total_images or 0 for m in document_metrics)
        total_charts_found = sum(m.charts_found or 0 for m in document_metrics)
        total_charts_converted = sum(m.charts_converted or 0 for m in document_metrics)

        chart_conversion_rate = None
        if total_charts_found > 0:
            chart_conversion_rate = (total_charts_converted / total_charts_found) * 100

        # 错误分类统计
        error_categories: dict[str, int] = {}
        for metric in document_metrics:
            if metric.processing_status == "FAILED" and metric.error_message:
                # 简单的错误分类
                error_msg = metric.error_message.lower()
                if "format" in error_msg or "格式" in error_msg:
                    category = "格式错误"
                elif "size" in error_msg or "大小" in error_msg:
                    category = "文件大小错误"
                elif "network" in error_msg or "网络" in error_msg:
                    category = "网络错误"
                elif "llm" in error_msg or "模型" in error_msg:
                    category = "LLM处理错误"
                else:
                    category = "其他错误"

                error_categories[category] = error_categories.get(category, 0) + 1

        return ReportStatistics(
            total_documents=total_docs,
            processed_documents=processed_docs,
            failed_documents=failed_docs,
            skipped_documents=skipped_docs,
            success_rate=success_rate,
            average_processing_time=avg_processing_time,
            total_processing_time=total_processing_time,
            format_distribution=format_dist,
            pipeline_distribution=pipeline_dist,
            total_original_length=total_original_length,
            total_cleaned_length=total_cleaned_length,
            average_content_reduction=avg_content_reduction,
            total_images=total_images,
            total_charts_found=total_charts_found,
            total_charts_converted=total_charts_converted,
            chart_conversion_rate=chart_conversion_rate,
            error_categories=error_categories,
        )

    def _generate_recommendations(self, statistics: ReportStatistics) -> list[str]:
        """生成改进建议

        Args:
            statistics: 统计信息

        Returns:
            改进建议列表
        """
        recommendations = []

        # 成功率建议
        if statistics.success_rate < 90:
            recommendations.append(
                f"成功率较低({statistics.success_rate:.1f}%),建议检查失败原因并优化处理流程"
            )

        # 处理时间建议
        if (
            statistics.average_processing_time
            and statistics.average_processing_time > 300
        ):  # 5分钟
            recommendations.append(
                f"平均处理时间较长({statistics.average_processing_time:.1f}秒),建议优化处理算法或增加并行处理"
            )

        # 内容减少率建议
        if (
            statistics.average_content_reduction
            and statistics.average_content_reduction > 50
        ):
            recommendations.append(
                f"内容减少率较高({statistics.average_content_reduction:.1f}%),建议检查清洗规则是否过于严格"
            )

        # 图表转换建议
        if statistics.chart_conversion_rate and statistics.chart_conversion_rate < 80:
            recommendations.append(
                f"图表转换成功率较低({statistics.chart_conversion_rate:.1f}%),建议优化图表识别算法或调整阈值"
            )

        # 错误分类建议
        if statistics.error_categories:
            top_error = max(statistics.error_categories.items(), key=lambda x: x[1])
            recommendations.append(
                f"主要错误类型为'{top_error[0]}'({top_error[1]}次),建议针对性优化"
            )

        if not recommendations:
            recommendations.append("处理质量良好,无特殊建议")

        return recommendations

    def generate_report(self, job_id: str) -> QualityReport:
        """生成质量报告

        Args:
            job_id: 任务ID

        Returns:
            质量报告对象
        """
        logger.info(f"开始生成质量报告: {job_id}")

        try:
            # 获取任务信息
            job_info = self._get_job_info(job_id)

            # 获取文档质量指标(基于任务关联的文档)
            document_metrics = self._get_document_metrics(job_id, job_info=job_info)

            # 计算统计信息
            statistics = self._calculate_statistics(document_metrics)

            # 生成改进建议
            recommendations = self._generate_recommendations(statistics)

            # 计算任务持续时间
            duration = None
            if job_info["started_at"] and job_info["completed_at"]:
                start = datetime.fromisoformat(job_info["started_at"])
                end = datetime.fromisoformat(job_info["completed_at"])
                duration = (end - start).total_seconds()

            # 创建质量报告
            report = QualityReport(
                job_id=job_info["job_id"],
                job_type=job_info["job_name"],
                started_at=(
                    datetime.fromisoformat(job_info["started_at"])
                    if job_info["started_at"]
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(job_info["completed_at"])
                    if job_info["completed_at"]
                    else None
                ),
                duration=duration,
                statistics=statistics,
                document_metrics=document_metrics,
                configuration=job_info["metadata"],
                recommendations=recommendations,
                notes=None,
            )

            logger.info(f"质量报告生成完成: {job_id}")
            return report

        except Exception as e:
            error_msg = f"生成质量报告失败: {e}"
            logger.error(error_msg)
            raise ProcessingError(error_msg) from e

    def generate_json_report(self, job_id: str) -> str:
        """生成JSON格式报告

        Args:
            job_id: 任务ID

        Returns:
            JSON格式的报告字符串
        """
        report = self.generate_report(job_id)
        return report.model_dump_json(indent=2, ensure_ascii=False)

    def generate_markdown_report(self, job_id: str) -> str:
        """生成Markdown格式报告

        Args:
            job_id: 任务ID

        Returns:
            Markdown格式的报告字符串
        """
        report = self.generate_report(job_id)

        # 构建Markdown报告
        md_lines = [
            "# 预处理质量报告",
            "",
            "## 任务信息",
            f"- **任务ID**: {report.job_id}",
            f"- **任务类型**: {report.job_type}",
            f"- **开始时间**: {report.started_at or '未知'}",
            f"- **完成时间**: {report.completed_at or '未知'}",
            (
                f"- **持续时间**: {report.duration:.2f}秒"
                if report.duration
                else "- **持续时间**: 未知"
            ),
            "",
        ]

        # 总体统计
        stats = report.statistics
        md_lines.extend(
            [
                "## 总体统计",
                "",
                "| 指标 | 数值 |",
                "|------|------|",
                f"| 总文档数 | {stats.total_documents} |",
                f"| 成功处理 | {stats.processed_documents} |",
                f"| 处理失败 | {stats.failed_documents} |",
                f"| 跳过文档 | {stats.skipped_documents} |",
                f"| 成功率 | {stats.success_rate:.1f}% |",
                (
                    f"| 平均处理时间 | {stats.average_processing_time:.2f}秒"
                    if stats.average_processing_time
                    else "| 平均处理时间 | 未知 |"
                ),
                (
                    f"| 总处理时间 | {stats.total_processing_time:.2f}秒"
                    if stats.total_processing_time
                    else "| 总处理时间 | 未知 |"
                ),
                "",
            ]
        )

        # 格式分布
        if stats.format_distribution:
            md_lines.extend(
                [
                    "### 格式分布",
                    "",
                    "| 格式 | 数量 |",
                    "|------|------|",
                ]
            )
            for fmt, count in stats.format_distribution.items():
                md_lines.append(f"| {fmt} | {count} |")
            md_lines.append("")

        # 管线分布
        if stats.pipeline_distribution:
            md_lines.extend(
                [
                    "### 处理管线分布",
                    "",
                    "| 管线 | 数量 |",
                    "|------|------|",
                ]
            )
            for pipeline, count in stats.pipeline_distribution.items():
                md_lines.append(f"| {pipeline} | {count} |")
            md_lines.append("")

        # 内容质量统计
        if stats.total_original_length is not None:
            md_lines.extend(
                [
                    "### 内容质量统计",
                    "",
                    f"- 原始内容总长度: {stats.total_original_length:,} 字符",
                    f"- 清洗后内容总长度: {stats.total_cleaned_length:,} 字符",
                    (
                        f"- 平均内容减少率: {stats.average_content_reduction:.1f}%"
                        if stats.average_content_reduction
                        else "- 平均内容减少率: 未知"
                    ),
                    "",
                ]
            )

        # 图表处理统计
        if stats.total_images is not None and stats.total_images > 0:
            md_lines.extend(
                [
                    "### 图表处理统计",
                    "",
                    f"- 总图片数: {stats.total_images}",
                    f"- 发现图表数: {stats.total_charts_found}",
                    f"- 成功转换图表数: {stats.total_charts_converted}",
                    (
                        f"- 图表转换成功率: {stats.chart_conversion_rate:.1f}%"
                        if stats.chart_conversion_rate
                        else "- 图表转换成功率: 未知"
                    ),
                    "",
                ]
            )

        # 错误分析
        if stats.error_categories:
            md_lines.extend(
                [
                    "### 错误分析",
                    "",
                    "| 错误类型 | 数量 |",
                    "|----------|------|",
                ]
            )
            for error_type, count in stats.error_categories.items():
                md_lines.append(f"| {error_type} | {count} |")
            md_lines.append("")

        # 改进建议
        if report.recommendations:
            md_lines.extend(
                [
                    "## 改进建议",
                    "",
                ]
            )
            for i, rec in enumerate(report.recommendations, 1):
                md_lines.append(f"{i}. {rec}")
            md_lines.append("")

        # 文档详情
        if report.document_metrics:
            md_lines.extend(
                [
                    "## 文档详情",
                    "",
                    "| 文件名 | 格式 | 状态 | 处理时间(秒) | 内容减少率(%) | 图表转换 |",
                    "|--------|------|------|-------------|---------------|----------|",
                ]
            )

            for metric in report.document_metrics:
                status_emoji = (
                    "✅"
                    if metric.processing_status == "INDEXED"
                    else "❌" if metric.processing_status == "FAILED" else "⏳"
                )
                processing_time = (
                    f"{metric.processing_time:.1f}"
                    if metric.processing_time
                    else "未知"
                )
                content_reduction = (
                    f"{metric.content_reduction_rate:.1f}"
                    if metric.content_reduction_rate
                    else "未知"
                )
                chart_info = (
                    f"{metric.charts_converted}/{metric.charts_found}"
                    if metric.charts_found and metric.charts_found > 0
                    else "无"
                )

                md_lines.append(
                    f"| {metric.filename} | {metric.file_format} | {status_emoji} {metric.processing_status} "
                    f"| {processing_time} | {content_reduction} | {chart_info} |"
                )

            md_lines.append("")

        # 报告生成信息
        md_lines.extend(
            [
                "---",
                "",
                f"*报告生成时间: {report.statistics.report_generated_at}*",
                "*生成工具: whitepaper 预处理质量报告生成器*",
            ]
        )

        return "\n".join(md_lines)

    def save_report(
        self, job_id: str, output_dir: str, output_format: str = "json"
    ) -> str:
        """保存报告到文件

        Args:
            job_id: 任务ID
            output_dir: 输出目录
            output_format: 输出格式 (json 或 markdown)

        Returns:
            保存的文件路径
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if output_format.lower() == "json":
            filename = f"quality_report_{job_id}_{timestamp}.json"
            content = self.generate_json_report(job_id)
        elif output_format.lower() in ["markdown", "md"]:
            filename = f"quality_report_{job_id}_{timestamp}.md"
            content = self.generate_markdown_report(job_id)
        else:
            error_msg = f"不支持的格式: {output_format}"
            raise ValueError(error_msg)

        file_path = output_path / filename

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"质量报告已保存: {file_path}")
            return str(file_path)

        except Exception as e:
            error_msg = f"保存报告失败: {e}"
            logger.error(error_msg)
            raise ProcessingError(error_msg) from e


class QualityReportError(ProcessingError):
    """质量报告生成专用异常"""
