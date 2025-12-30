# 生成命令: /speckit.implement T060
# 生成时间: 2025-12-19
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
预处理结果读取器

该模块实现预处理结果读取器,从阶段3预处理结果目录读取文档.
继承BaseLoader接口,支持读取clean.md,clean_content_list.json,images/和datajson/目录.

参考LangChain 1.0最佳实践:
- 继承BaseLoader接口,实现load()方法
- 返回langchain_core.documents.Document对象
- 元数据必须包含source和format字段
- 支持批量读取多个预处理结果目录
"""

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.infrastructure.preprocessing.loaders.base_loader import (
    BaseLoader,
    DocumentNotFoundError,
    DocumentParsingError,
    LoaderError,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class PreprocessedDocumentReader(BaseLoader):
    """
    预处理结果读取器

    从阶段3预处理结果目录读取文档,继承BaseLoader接口.
    支持读取以下内容:
    - clean.md: 清洗后的Markdown内容
    - clean_content_list.json: 内容列表和元数据
    - images/: 图片文件目录
    - datajson/: 图表JSON文件目录

    目录结构:
        data/cleaned/documents/{doc_name}/{extracted_dir}/
        ├── clean.md
        ├── clean_content_list.json
        ├── images/
        │   └── *.jpg, *.png, ...
        └── datajson/
            └── {图表名称}.json

    示例:
        >>> reader = PreprocessedDocumentReader(
        ...     source="data/cleaned/documents/doc1/extracted_dir"
        ... )
        >>> documents = reader.load()
        >>> for doc in documents:
        ...     print(doc.page_content)
        ...     print(doc.metadata)
    """

    def __init__(
        self,
        source: str,
        document_format: str | None = None,
        include_images: bool = True,
        include_charts: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        初始化预处理结果读取器

        Args:
            source: 预处理结果目录路径(data/cleaned/documents/{doc_name}/{extracted_dir}/)
            document_format: 文档格式,如果未提供则尝试从目录结构推断
            include_images: 是否在元数据中包含图片信息,默认为True
            include_charts: 是否在元数据中包含图表JSON信息,默认为True
            **kwargs: 额外的参数,包括metadata等
        """
        # 确保source是目录路径
        source_path = Path(source)
        if not source_path.exists():
            raise DocumentNotFoundError(source)
        if not source_path.is_dir():
            msg = f"Source must be a directory: {source}"
            raise LoaderError(msg)

        # 检测格式(从目录名或父目录名推断)
        if document_format is None:
            document_format = self._detect_format_from_path(source_path)

        super().__init__(source, document_format, **kwargs)

        self.source_path = source_path
        self.include_images = include_images
        self.include_charts = include_charts

        # 定义必需的文件路径
        self.clean_md_path = source_path / "clean.md"
        self.clean_content_list_path = source_path / "clean_content_list.json"
        self.images_dir = source_path / "images"
        self.datajson_dir = source_path / "datajson"

        logger.debug(
            f"初始化 {self.__class__.__name__}: "
            f"source={source}, format={self.format}, "
            f"include_images={include_images}, include_charts={include_charts}"
        )

    def load(self) -> list[Document]:
        """
        加载预处理结果并返回Document列表

        读取clean.md文件,提取元数据,关联图片和图表信息.

        Returns:
            List[Document]: Document对象列表

        Raises:
            DocumentNotFoundError: 如果clean.md文件不存在
            DocumentParsingError: 如果解析失败
        """
        # 检查必需文件
        if not self.clean_md_path.exists():
            msg = f"clean.md文件不存在: {self.clean_md_path}"
            raise DocumentNotFoundError(
                msg
            )

        try:
            # 读取clean.md内容
            with open(self.clean_md_path, encoding="utf-8") as f:
                page_content = f.read()

            if not page_content.strip():
                logger.warning(f"clean.md文件为空: {self.clean_md_path}")

            # 提取元数据
            metadata = self._extract_metadata()

            # 创建Document对象
            document = self._create_document(page_content, metadata)

            logger.info(
                f"成功加载预处理结果: source={self.source}, "
                f"content_length={len(page_content)}, "
                f"metadata_keys={list(metadata.keys())}"
            )

            return [document]

        except Exception as e:
            logger.error(f"加载预处理结果时出错: {e}", exc_info=True)
            msg = f"无法加载预处理结果: {e}"
            raise DocumentParsingError(
                msg,
                source=str(self.source_path),
                original_error=e,
            ) from e

    def lazy_load(self) -> Iterator[Document]:
        """
        懒加载预处理结果

        由于预处理结果通常是单个文件,此方法直接返回load()的结果.

        Yields:
            Document: 单个Document对象
        """
        yield from self.load()

    def _extract_metadata(self) -> dict[str, Any]:
        """
        提取元数据信息

        从clean_content_list.json,images/和datajson/目录提取元数据.

        Returns:
            Dict[str, Any]: 元数据字典
        """
        metadata: dict[str, Any] = {
            "source": str(self.source_path),
            "format": self.format,
            "loaded_at": datetime.now().isoformat(),
            "preprocessed": True,
        }

        # 读取clean_content_list.json
        if self.clean_content_list_path.exists():
            try:
                with open(self.clean_content_list_path, encoding="utf-8") as f:
                    content_list = json.load(f)

                # 提取关键元数据
                if isinstance(content_list, list) and len(content_list) > 0:
                    # 提取第一个元素的类型信息
                    first_item = content_list[0]
                    if isinstance(first_item, dict):
                        # 提取页面信息 - 转换为基本类型以符合LlamaIndex要求
                        # LlamaIndex要求metadata值必须是str, int, float, None
                        if "page_idx" in first_item:
                            # 将字典拆分为基本类型字段
                            metadata["page_first"] = int(first_item.get("page_idx", 0))
                            metadata["page_total_items"] = len(content_list)
                            # 如果需要保留完整信息,使用JSON字符串
                            metadata["page_info_json"] = json.dumps({
                                "first_page": first_item.get("page_idx", 0),
                                "total_items": len(content_list),
                            }, ensure_ascii=False)

                        # 提取格式信息 - 转换为字符串列表
                        if "type" in first_item:
                            content_types = list(
                                {item.get("type", "unknown") for item in content_list if isinstance(item, dict)}
                            )
                            # 将列表转换为逗号分隔的字符串(LlamaIndex要求)
                            metadata["content_types"] = ",".join(content_types) if content_types else "unknown"

                # content_list是复杂类型(列表),需要转换为JSON字符串以符合LlamaIndex要求
                # 但为了保持向后兼容,我们保留原始列表,在vector_index中会转换为JSON字符串
                metadata["content_list"] = content_list
                logger.debug(f"成功读取clean_content_list.json: {len(content_list)} 项")

            except Exception as e:
                logger.warning(f"读取clean_content_list.json时出错: {e}")

        # 关联图片信息
        if self.include_images and self.images_dir.exists():
            try:
                image_files = list(self.images_dir.glob("*.jpg")) + list(
                    self.images_dir.glob("*.png")
                )
                if image_files:
                    metadata["images"] = {
                        "count": len(image_files),
                        "files": [str(img.name) for img in image_files],
                        "directory": str(self.images_dir),
                    }
                    logger.debug(f"关联图片信息: {len(image_files)} 个文件")

            except Exception as e:
                logger.warning(f"读取images目录时出错: {e}")

        # 关联图表JSON信息
        if self.include_charts and self.datajson_dir.exists():
            try:
                json_files = list(self.datajson_dir.glob("*.json"))
                if json_files:
                    chart_info = []
                    for json_file in json_files:
                        try:
                            with open(json_file, encoding="utf-8") as f:
                                json.load(f)
                            chart_info.append({
                                "name": json_file.stem,
                                "file": json_file.name,
                                "path": str(json_file),
                            })
                        except Exception as e:
                            logger.warning(f"读取图表JSON文件 {json_file} 时出错: {e}")

                    if chart_info:
                        metadata["charts"] = {
                            "count": len(chart_info),
                            "charts": chart_info,
                            "directory": str(self.datajson_dir),
                        }
                        logger.debug(f"关联图表JSON信息: {len(chart_info)} 个文件")

            except Exception as e:
                logger.warning(f"读取datajson目录时出错: {e}")

        # 添加初始化时传入的元数据
        if self.metadata:
            metadata.update(self.metadata)

        return metadata

    def _detect_format_from_path(self, path: Path) -> str:
        """
        从路径推断文档格式

        Args:
            path: 预处理结果目录路径

        Returns:
            str: 检测到的格式,如果无法检测则返回'unknown'
        """
        # 尝试从父目录名推断格式
        parent_name = path.parent.name.lower()
        if "pdf" in parent_name or path.name.endswith("_pdf_extracted"):
            return "pdf"
        if "docx" in parent_name or path.name.endswith("_docx_extracted"):
            return "docx"
        if "html" in parent_name or path.name.endswith("_html_extracted"):
            return "html"

        # 尝试从extracted_dir名称推断
        dir_name = path.name.lower()
        if "pdf" in dir_name:
            return "pdf"
        if "docx" in dir_name:
            return "docx"
        if "html" in dir_name:
            return "html"

        # 默认返回markdown(因为预处理后统一为Markdown格式)
        return "markdown"

    def get_supported_formats(self) -> list[str]:
        """
        获取支持的文档格式列表

        Returns:
            List[str]: 支持的格式列表(预处理结果统一为Markdown)
        """
        return ["markdown", "pdf", "docx", "html"]

    def can_handle(self, source: str) -> bool:
        """
        检查是否能处理指定的预处理结果目录

        Args:
            source: 预处理结果目录路径

        Returns:
            bool: 是否能处理该目录
        """
        try:
            source_path = Path(source)
            if not source_path.exists() or not source_path.is_dir():
                return False

            # 检查是否存在clean.md文件
            clean_md_path = source_path / "clean.md"
            return clean_md_path.exists()

        except Exception:
            return False

    @classmethod
    def load_from_multiple_directories(
        cls,
        directories: list[str],
        include_images: bool = True,
        include_charts: bool = True,
    ) -> list[Document]:
        """
        从多个预处理结果目录批量加载文档

        Args:
            directories: 预处理结果目录路径列表
            include_images: 是否在元数据中包含图片信息
            include_charts: 是否在元数据中包含图表JSON信息

        Returns:
            List[Document]: 所有目录的Document对象列表
        """
        all_documents = []

        for directory in directories:
            try:
                reader = cls(
                    source=directory,
                    include_images=include_images,
                    include_charts=include_charts,
                )
                documents = reader.load()
                all_documents.extend(documents)
                logger.info(f"成功加载目录: {directory}, 文档数: {len(documents)}")

            except Exception as e:
                logger.error(f"加载目录 {directory} 时出错: {e}", exc_info=True)
                # 继续处理其他目录,不中断整个流程
                continue

        logger.info(f"批量加载完成: 总目录数={len(directories)}, 总文档数={len(all_documents)}")
        return all_documents

