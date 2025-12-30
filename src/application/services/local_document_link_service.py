"""
本地文章链接服务

该模块实现本地文章链接功能,支持文件路径,段落定位,页码定位等.
用于MVP 3步流程中的第四步: 草稿生成(带素材追溯链接).

提供本地文章链接的生成,解析,验证和格式化功能.
"""

# 生成命令: /speckit.implement T236
# 生成时间: 2025-12-25
# 来源: specs/001-multi-agent-doc-system/tasks.md

import urllib.parse
from pathlib import Path
from typing import Any

from src.domain.agent.source_reference import (
    LocalDocumentReference,
    SourceReference,
)
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class LocalDocumentLinkService:
    """
    本地文章链接服务

    提供本地文章链接的生成,解析,验证和格式化功能.
    支持文件路径,段落定位,页码定位等本地文档引用信息.
    """

    def __init__(self, base_path: str | Path | None = None) -> None:
        """
        初始化本地文章链接服务

        Args:
            base_path: 基础路径,用于解析相对路径(可选)
        """
        self.base_path = Path(base_path) if base_path else None

    def generate_link(
        self,
        file_path: str,
        paragraph_index: int | None = None,
        page_number: int | None = None,
        line_number: int | None = None,
        scheme: str = "file",
    ) -> str:
        """
        生成本地文章链接

        Args:
            file_path: 文件路径(相对路径或绝对路径)
            paragraph_index: 段落索引(从0开始)
            page_number: 页码(从1开始)
            line_number: 行号(从1开始)
            scheme: 链接方案(file:// 或 http://localhost等)

        Returns:
            生成的链接URL字符串
        """
        try:
            # 解析文件路径
            path = Path(file_path)
            if self.base_path and not path.is_absolute():
                # 如果是相对路径且有base_path,转换为绝对路径
                path = self.base_path / path
            absolute_path = path.resolve()

            # 构建查询参数
            params: dict[str, Any] = {}
            if paragraph_index is not None:
                params["paragraph"] = paragraph_index
            if page_number is not None:
                params["page"] = page_number
            if line_number is not None:
                params["line"] = line_number

            # 根据scheme生成不同的链接格式
            if scheme == "file":
                # file:// 协议
                file_url = absolute_path.as_uri()
                if params:
                    query_string = urllib.parse.urlencode(params)
                    return f"{file_url}?{query_string}"
                return file_url
            elif scheme == "http" or scheme == "https":
                # HTTP协议(用于前端通过HTTP服务访问)
                # 将文件路径编码为URL参数
                urllib.parse.quote(str(absolute_path), safe="/")
                base_url = f"{scheme}://localhost/document"
                params["path"] = str(absolute_path)
                query_string = urllib.parse.urlencode(params)
                return f"{base_url}?{query_string}"
            else:
                # 自定义scheme
                file_url = f"{scheme}://{absolute_path.as_posix()}"
                if params:
                    query_string = urllib.parse.urlencode(params)
                    return f"{file_url}?{query_string}"
                return file_url

        except Exception as e:
            logger.error(f"生成本地文章链接失败: {e}", exc_info=True)
            # 返回基本的文件路径
            return file_path

    def parse_link(self, link: str) -> dict[str, Any]:
        """
        解析本地文章链接

        Args:
            link: 链接URL字符串

        Returns:
            包含文件路径和定位信息的字典
        """
        try:
            # 解析URL
            parsed = urllib.parse.urlparse(link)

            # 提取文件路径
            if parsed.scheme == "file":
                # file:// 协议
                file_path = urllib.parse.unquote(parsed.path)
                # Windows路径处理
                if file_path.startswith("/") and len(file_path) > 1:
                    # 去掉开头的斜杠(Windows路径)
                    if file_path[1] == ":":
                        file_path = file_path[1:]
            else:
                # 其他协议,从path或query参数中提取
                file_path = parsed.path
                if not file_path:
                    # 从query参数中提取path
                    query_params = urllib.parse.parse_qs(parsed.query)
                    path_list = query_params.get("path", [])
                    if path_list:
                        file_path = path_list[0]

            # 解析查询参数
            query_params = urllib.parse.parse_qs(parsed.query)
            paragraph_index = None
            page_number = None
            line_number = None

            if "paragraph" in query_params:
                paragraph_index = int(query_params["paragraph"][0])
            if "page" in query_params:
                page_number = int(query_params["page"][0])
            if "line" in query_params:
                line_number = int(query_params["line"][0])

            return {
                "file_path": file_path,
                "paragraph_index": paragraph_index,
                "page_number": page_number,
                "line_number": line_number,
            }

        except Exception as e:
            logger.error(f"解析本地文章链接失败: {e}", exc_info=True)
            return {
                "file_path": link,
                "paragraph_index": None,
                "page_number": None,
                "line_number": None,
            }

    def validate_file_path(self, file_path: str) -> bool:
        """
        验证文件路径是否存在

        Args:
            file_path: 文件路径

        Returns:
            文件是否存在
        """
        try:
            path = Path(file_path)
            if self.base_path and not path.is_absolute():
                # 如果是相对路径且有base_path,转换为绝对路径
                path = self.base_path / path
            return path.exists() and path.is_file()
        except Exception as e:
            logger.error(f"验证文件路径失败: {e}", exc_info=True)
            return False

    def format_display_link(
        self,
        file_path: str,
        paragraph_index: int | None = None,
        page_number: int | None = None,
        line_number: int | None = None,
        max_path_length: int = 50,
    ) -> str:
        """
        格式化显示链接

        Args:
            file_path: 文件路径
            paragraph_index: 段落索引
            page_number: 页码
            line_number: 行号
            max_path_length: 最大路径长度(超过则截断)

        Returns:
            格式化的显示链接字符串
        """
        # 格式化文件路径
        path = Path(file_path)
        display_path = path.name  # 只显示文件名
        display_path = path.name if len(str(path)) > max_path_length else str(path)

        # 构建定位信息
        location_parts = []
        if page_number is not None:
            location_parts.append(f"第{page_number}页")
        if paragraph_index is not None:
            location_parts.append(f"第{paragraph_index + 1}段")
        if line_number is not None:
            location_parts.append(f"第{line_number}行")

        if location_parts:
            location_str = ", ".join(location_parts)
            return f"{display_path} ({location_str})"
        return display_path

    def create_link_from_reference(
        self, source_reference: SourceReference, scheme: str = "file"
    ) -> str | None:
        """
        从SourceReference创建链接

        Args:
            source_reference: 信息源引用对象
            scheme: 链接方案

        Returns:
            生成的链接URL,如果引用类型不是本地文档则返回None
        """
        if not source_reference.is_local_document():
            return None

        local_ref = source_reference.local_reference
        if not local_ref:
            return None

        return self.generate_link(
            file_path=local_ref.file_path,
            paragraph_index=local_ref.paragraph_index,
            page_number=local_ref.page_number,
            line_number=local_ref.line_number,
            scheme=scheme,
        )

    def create_link_from_local_reference(
        self, local_ref: LocalDocumentReference, scheme: str = "file"
    ) -> str:
        """
        从LocalDocumentReference创建链接

        Args:
            local_ref: 本地文档引用对象
            scheme: 链接方案

        Returns:
            生成的链接URL
        """
        return self.generate_link(
            file_path=local_ref.file_path,
            paragraph_index=local_ref.paragraph_index,
            page_number=local_ref.page_number,
            line_number=local_ref.line_number,
            scheme=scheme,
        )

    def get_jump_url(
        self,
        file_path: str,
        paragraph_index: int | None = None,
        page_number: int | None = None,
        line_number: int | None = None,
        use_http: bool = False,
    ) -> str:
        """
        获取跳转URL(用于前端跳转)

        Args:
            file_path: 文件路径
            paragraph_index: 段落索引
            page_number: 页码
            line_number: 行号
            use_http: 是否使用HTTP协议(用于前端通过HTTP服务访问)

        Returns:
            跳转URL
        """
        if use_http:
            return self.generate_link(
                file_path=file_path,
                paragraph_index=paragraph_index,
                page_number=page_number,
                line_number=line_number,
                scheme="http",
            )
        else:
            return self.generate_link(
                file_path=file_path,
                paragraph_index=paragraph_index,
                page_number=page_number,
                line_number=line_number,
                scheme="file",
            )

    def format_location_string(
        self,
        paragraph_index: int | None = None,
        page_number: int | None = None,
        line_number: int | None = None,
    ) -> str:
        """
        格式化定位字符串

        Args:
            paragraph_index: 段落索引
            page_number: 页码
            line_number: 行号

        Returns:
            格式化的定位信息字符串
        """
        parts = []
        if page_number is not None:
            parts.append(f"第{page_number}页")
        if paragraph_index is not None:
            parts.append(f"第{paragraph_index + 1}段")
        if line_number is not None:
            parts.append(f"第{line_number}行")

        if parts:
            return ", ".join(parts)
        return "未知位置"


# 便利函数

def create_local_document_link_service(
    base_path: str | Path | None = None,
) -> LocalDocumentLinkService:
    """
    创建本地文章链接服务的便捷函数

    Args:
        base_path: 基础路径

    Returns:
        LocalDocumentLinkService实例
    """
    return LocalDocumentLinkService(base_path=base_path)


def generate_local_document_link(
    file_path: str,
    paragraph_index: int | None = None,
    page_number: int | None = None,
    line_number: int | None = None,
    scheme: str = "file",
    base_path: str | Path | None = None,
) -> str:
    """
    生成本地文章链接的便捷函数

    Args:
        file_path: 文件路径
        paragraph_index: 段落索引
        page_number: 页码
        line_number: 行号
        scheme: 链接方案
        base_path: 基础路径

    Returns:
        生成的链接URL
    """
    service = LocalDocumentLinkService(base_path=base_path)
    return service.generate_link(
        file_path=file_path,
        paragraph_index=paragraph_index,
        page_number=page_number,
        line_number=line_number,
        scheme=scheme,
    )

