"""
素材来源跳转服务

该模块实现素材来源点击跳转功能,支持跳转到原文位置.
用于MVP 3步流程中的第四步: 草稿生成(带素材追溯链接).

当前版本仅支持本地文章跳转,网络文章跳转功能待第三步完成后启用.
"""

# 生成命令: /speckit.implement T238
# 生成时间: 2025-12-25
# 来源: specs/001-multi-agent-doc-system/tasks.md

import platform
import subprocess
import webbrowser
from pathlib import Path
from typing import Any

from src.application.services.local_document_link_service import (
    LocalDocumentLinkService,
)
from src.domain.agent.source_reference import SourceReference
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class JumpScheme(str):
    """跳转方案枚举"""

    FILE = "file"  # file:// 协议(系统默认打开)
    HTTP = "http"  # HTTP协议(通过HTTP服务访问)
    HTTPS = "https"  # HTTPS协议(通过HTTPS服务访问)
    CUSTOM = "custom"  # 自定义方案


class SourceJumpService:
    """
    素材来源跳转服务

    提供素材来源点击跳转功能,支持跳转到原文位置.
    当前版本仅支持本地文章跳转,网络文章跳转功能待第三步完成后启用.
    """

    def __init__(
        self,
        link_service: LocalDocumentLinkService | None = None,
        default_scheme: str = "file",
    ) -> None:
        """
        初始化素材来源跳转服务

        Args:
            link_service: 本地文章链接服务(可选)
            default_scheme: 默认跳转方案(file,http,https等)
        """
        self.link_service = link_service or LocalDocumentLinkService()
        self.default_scheme = default_scheme

    def get_jump_url(
        self,
        source_reference: SourceReference,
        scheme: str | None = None,
        use_http: bool = False,
    ) -> str | None:
        """
        获取跳转URL

        Args:
            source_reference: 信息源引用对象
            scheme: 跳转方案(可选,默认使用default_scheme)
            use_http: 是否使用HTTP协议(用于前端通过HTTP服务访问)

        Returns:
            跳转URL,如果不可跳转则返回None
        """
        if not source_reference.can_jump_to_source():
            return None

        if source_reference.is_local_document():
            return self._get_local_document_jump_url(
                source_reference, scheme=scheme, use_http=use_http
            )
        elif source_reference.is_web_article():
            # 网络文章跳转功能待第三步完成后启用
            logger.warning("网络文章跳转功能待第三步完成后启用")
            return None
        else:
            return None

    def _get_local_document_jump_url(
        self,
        source_reference: SourceReference,
        scheme: str | None = None,
        use_http: bool = False,
    ) -> str | None:
        """
        获取本地文档跳转URL

        Args:
            source_reference: 信息源引用对象
            scheme: 跳转方案
            use_http: 是否使用HTTP协议

        Returns:
            跳转URL
        """
        if not source_reference.local_reference:
            return None

        local_ref = source_reference.local_reference

        # 确定使用的scheme
        if use_http:
            pass

        return self.link_service.get_jump_url(
            file_path=local_ref.file_path,
            paragraph_index=local_ref.paragraph_index,
            page_number=local_ref.page_number,
            line_number=local_ref.line_number,
            use_http=use_http,
        )

    def can_jump(self, source_reference: SourceReference) -> bool:
        """
        检查是否可以跳转

        Args:
            source_reference: 信息源引用对象

        Returns:
            是否可以跳转
        """
        if not source_reference.can_jump_to_source():
            return False

        if source_reference.is_local_document():
            # 检查文件是否存在
            if source_reference.local_reference:
                return self.link_service.validate_file_path(
                    source_reference.local_reference.file_path
                )
        elif source_reference.is_web_article():
            # 网络文章跳转功能待第三步完成后启用
            return False

        return False

    def jump_to_source(
        self,
        source_reference: SourceReference,
        scheme: str | None = None,
        use_http: bool = False,
        open_in_browser: bool = False,
    ) -> bool:
        """
        跳转到来源(实际执行跳转操作)

        Args:
            source_reference: 信息源引用对象
            scheme: 跳转方案
            use_http: 是否使用HTTP协议
            open_in_browser: 是否在浏览器中打开(仅对HTTP/HTTPS有效)

        Returns:
            是否成功跳转
        """
        jump_url = self.get_jump_url(
            source_reference, scheme=scheme, use_http=use_http
        )
        if not jump_url:
            logger.warning(f"无法获取跳转URL: {source_reference.id}")
            return False

        try:
            if open_in_browser or use_http or scheme in ["http", "https"]:
                # 在浏览器中打开
                webbrowser.open(jump_url)
                logger.info(f"在浏览器中打开: {jump_url}")
                return True
            elif scheme == "file" or jump_url.startswith("file://"):
                # 使用系统默认程序打开文件
                return self._open_file(jump_url, source_reference)
            else:
                # 其他方案,尝试在浏览器中打开
                webbrowser.open(jump_url)
                logger.info(f"在浏览器中打开: {jump_url}")
                return True
        except Exception as e:
            logger.error(f"跳转失败: {e}", exc_info=True)
            return False

    def _open_file(
        self, file_url: str, source_reference: SourceReference
    ) -> bool:
        """
        打开文件(使用系统默认程序)

        Args:
            file_url: 文件URL
            source_reference: 信息源引用对象

        Returns:
            是否成功打开
        """
        try:
            # 从file:// URL中提取文件路径
            if file_url.startswith("file://"):
                # 移除file://前缀
                file_path = file_url[7:]
                # Windows路径处理
                if platform.system() == "Windows":
                    # Windows下file://路径可能是/file/path格式,需要处理
                    if file_path.startswith("/") and len(file_path) > 1:
                        if file_path[1] == ":":
                            file_path = file_path[1:]
                        else:
                            # 去掉开头的斜杠
                            file_path = file_path[1:]
            else:
                file_path = file_url

            # 解析查询参数(如果有)
            if "?" in file_path:
                file_path = file_path.split("?")[0]

            # 验证文件是否存在
            path = Path(file_path)
            if not path.exists():
                logger.warning(f"文件不存在: {file_path}")
                return False

            # 根据操作系统使用不同的打开方式
            system = platform.system()
            if system == "Windows":
                # Windows: 使用start命令
                subprocess.run([r"C:\Windows\System32\cmd.exe", "/c", "start", "", str(path)], check=True)
            elif system == "Darwin":
                # macOS: 使用open命令
                subprocess.run(["/usr/bin/open", str(path)], check=True)
            else:
                # Linux: 使用xdg-open命令
                subprocess.run(["/usr/bin/xdg-open", str(path)], check=True)

            logger.info(f"成功打开文件: {file_path}")
            return True

        except Exception as e:
            logger.error(f"打开文件失败: {e}", exc_info=True)
            return False

    def get_jump_info(
        self, source_reference: SourceReference
    ) -> dict[str, Any]:
        """
        获取跳转信息(用于前端显示)

        Args:
            source_reference: 信息源引用对象

        Returns:
            包含跳转信息的字典
        """
        can_jump = self.can_jump(source_reference)
        jump_url = self.get_jump_url(source_reference) if can_jump else None

        info = {
            "can_jump": can_jump,
            "jump_url": jump_url,
            "reference_type": source_reference.reference_type.value
            if hasattr(source_reference.reference_type, "value")
            else str(source_reference.reference_type),
            "title": source_reference.title,
            "location": source_reference.get_location_info(),
        }

        if source_reference.is_local_document() and source_reference.local_reference:
            local_ref = source_reference.local_reference
            info["file_path"] = local_ref.file_path
            info["display_path"] = local_ref.get_display_path()
            info["paragraph_index"] = local_ref.paragraph_index
            info["page_number"] = local_ref.page_number
            info["line_number"] = local_ref.line_number
            info["file_exists"] = self.link_service.validate_file_path(
                local_ref.file_path
            )
        elif source_reference.is_web_article():
            info["web_article_supported"] = False
            info["message"] = "网络文章跳转功能待第三步完成后启用"

        return info

    def format_jump_link(
        self,
        source_reference: SourceReference,
        link_text: str | None = None,
        scheme: str | None = None,
        use_http: bool = False,
    ) -> str:
        """
        格式化跳转链接(用于Markdown/HTML渲染)

        Args:
            source_reference: 信息源引用对象
            link_text: 链接文本(可选,默认使用标题)
            scheme: 跳转方案
            use_http: 是否使用HTTP协议

        Returns:
            格式化的链接字符串(Markdown或HTML格式)
        """
        jump_url = self.get_jump_url(
            source_reference, scheme=scheme, use_http=use_http
        )
        if not jump_url:
            # 如果无法跳转,返回纯文本
            return link_text or source_reference.title

        text = link_text or source_reference.title

        # 根据URL格式判断返回Markdown还是HTML
        if use_http or scheme in ["http", "https"]:
            # HTML格式
            return f'<a href="{jump_url}" target="_blank">{text}</a>'
        else:
            # Markdown格式
            return f"[{text}]({jump_url})"

    def set_default_scheme(self, scheme: str) -> None:
        """
        设置默认跳转方案

        Args:
            scheme: 跳转方案
        """
        self.default_scheme = scheme


# 便利函数

def create_source_jump_service(
    link_service: LocalDocumentLinkService | None = None,
    default_scheme: str = "file",
) -> SourceJumpService:
    """
    创建素材来源跳转服务的便捷函数

    Args:
        link_service: 本地文章链接服务(可选)
        default_scheme: 默认跳转方案

    Returns:
        SourceJumpService实例
    """
    return SourceJumpService(
        link_service=link_service, default_scheme=default_scheme
    )


def jump_to_source_reference(
    source_reference: SourceReference,
    scheme: str | None = None,
    use_http: bool = False,
    open_in_browser: bool = False,
) -> bool:
    """
    跳转到来源引用的便捷函数

    Args:
        source_reference: 信息源引用对象
        scheme: 跳转方案
        use_http: 是否使用HTTP协议
        open_in_browser: 是否在浏览器中打开

    Returns:
        是否成功跳转
    """
    service = SourceJumpService()
    return service.jump_to_source(
        source_reference,
        scheme=scheme,
        use_http=use_http,
        open_in_browser=open_in_browser,
    )

