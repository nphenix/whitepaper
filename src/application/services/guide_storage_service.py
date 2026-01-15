"""
指南内容存储服务

该模块提供指南内容的保存、读取、删除等管理功能。
指南内容以Markdown文件形式存储，用于后续生成HTML模板。

生成命令: /speckit.implement guide_storage
生成时间: 2026-01-08
来源: 用户需求
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from src.application.services.base_service import BaseService
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class GuideStorageService(BaseService):
    """
    指南内容存储服务

    提供指南内容的文件存储管理，包括：
    - 保存指南内容为Markdown文件
    - 读取指南内容
    - 删除指南内容
    - 管理指南历史版本
    """

    def get_service_name(self) -> str:
        """获取服务名称"""
        return "guide_storage"

    def __init__(self, template_dir: str | Path | None = None):
        """
        初始化指南存储服务

        Args:
            template_dir: 模板目录路径，如果为None则使用默认路径
        """
        super().__init__()
        # 默认模板目录
        if template_dir is None:
            self.template_dir = Path("./data/templates/guide")
        else:
            self.template_dir = Path(template_dir)

        # 确保目录存在
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """确保模板目录存在"""
        try:
            self.template_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("指南模板目录已创建/确认存在", path=str(self.template_dir))
        except Exception as e:
            logger.error("创建指南模板目录失败", error=str(e))
            raise ProcessingError(f"创建指南模板目录失败: {e}")

    def _get_guide_file_path(self, outline_id: str) -> Path:
        """
        获取指南文件的路径

        Args:
            outline_id: 大纲ID

        Returns:
            指南文件的完整路径
        """
        return self.template_dir / f"{outline_id}_guide.md"

    def _get_history_dir_path(self, outline_id: str) -> Path:
        """
        获取指南历史版本的目录路径

        Args:
            outline_id: 大纲ID

        Returns:
            历史版本目录的完整路径
        """
        return self.template_dir / f"{outline_id}_guide_history"

    def save_guide(
        self,
        outline_id: str,
        content: str,
        title: str | None = None,
        save_history: bool = True,
    ) -> dict[str, Any]:
        """
        保存指南内容

        Args:
            outline_id: 大纲ID
            content: 指南内容（Markdown格式）
            title: 指南标题（可选）
            save_history: 是否保存历史版本（默认True）

        Returns:
            保存结果信息
        """
        try:
            outline_uuid = uuid.UUID(outline_id)
        except ValueError:
            raise ProcessingError(f"无效的大纲ID格式: {outline_id}")

        # 检查内容是否为空
        if not content or not content.strip():
            raise ProcessingError("指南内容不能为空")

        file_path = self._get_guide_file_path(outline_id)
        now = datetime.now(UTC)

        # 如果需要保存历史版本
        if save_history and file_path.exists():
            self._save_history_version(outline_id, file_path, now)

        # 构建文件头部元数据（YAML Front Matter）
        metadata = {
            "outline_id": str(outline_uuid),
            "title": title or "白皮书指南",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # 组合元数据和内容
        file_content = self._format_guide_file(metadata, content)

        # 写入文件
        try:
            file_path.write_text(file_content, encoding="utf-8")
        except Exception as e:
            logger.error("写入指南文件失败", outline_id=outline_id, error=str(e))
            raise ProcessingError(f"写入指南文件失败: {e}")

        logger.info(
            "指南保存成功",
            outline_id=outline_id,
            file_path=str(file_path),
            content_length=len(content),
        )

        return {
            "success": True,
            "outline_id": str(outline_uuid),
            "file_path": str(file_path),
            "title": metadata["title"],
            "content_length": len(content),
            "saved_at": now.isoformat(),
        }

    def _save_history_version(
        self, outline_id: str, current_file_path: Path, current_time: datetime
    ) -> None:
        """
        保存当前版本到历史目录

        Args:
            outline_id: 大纲ID
            current_file_path: 当前文件路径
            current_time: 当前时间
        """
        history_dir = self._get_history_dir_path(outline_id)

        try:
            history_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("创建历史目录失败，跳过历史保存", outline_id=outline_id, error=str(e))
            return

        # 生成带时间戳的文件名
        timestamp = current_time.strftime("%Y%m%d_%H%M%S")
        history_file_path = history_dir / f"{timestamp}_guide.md"

        try:
            # 复制当前文件到历史目录
            if current_file_path.exists():
                history_file_path.write_text(
                    current_file_path.read_text(encoding="utf-8"), encoding="utf-8"
                )
                logger.debug("历史版本已保存", outline_id=outline_id, history_path=str(history_file_path))
        except Exception as e:
            logger.warning("保存历史版本失败", outline_id=outline_id, error=str(e))

    def _format_guide_file(self, metadata: dict[str, Any], content: str) -> str:
        """
        格式化指南文件内容（添加YAML Front Matter）

        Args:
            metadata: 元数据字典
            content: 指南内容

        Returns:
            格式化后的文件内容
        """
        # 将元数据转换为YAML格式
        yaml_content = yaml.dump(metadata, allow_unicode=True, sort_keys=False)

        # 组合文件内容
        return f"---\n{yaml_content}---\n\n{content.strip()}"

    def _parse_guide_file(self, file_path: Path) -> dict[str, Any]:
        """
        解析指南文件，提取元数据和内容

        Args:
            file_path: 文件路径

        Returns:
            包含元数据和内容的字典
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            raise ProcessingError(f"读取指南文件失败: {e}")

        # 检查是否有YAML Front Matter
        if content.startswith("---"):
            try:
                # 解析YAML Front Matter
                parts = content.split("---", 3)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                else:
                    metadata = {}
                    body = content
            except Exception as e:
                logger.warning("解析YAML Front Matter失败", error=str(e))
                metadata = {}
                body = content
        else:
            metadata = {}
            body = content

        return {
            "metadata": metadata,
            "content": body,
            "file_path": str(file_path),
        }

    def get_guide(self, outline_id: str) -> dict[str, Any] | None:
        """
        获取指南内容

        Args:
            outline_id: 大纲ID

        Returns:
            指南信息字典，如果不存在则返回None
        """
        file_path = self._get_guide_file_path(outline_id)

        if not file_path.exists():
            logger.debug("指南文件不存在", outline_id=outline_id)
            return None

        try:
            result = self._parse_guide_file(file_path)
            result["outline_id"] = outline_id
            result["exists"] = True

            logger.debug("指南获取成功", outline_id=outline_id)
            return result

        except StorageError:
            return None

    def get_guide_content(self, outline_id: str) -> str | None:
        """
        仅获取指南内容文本

        Args:
            outline_id: 大纲ID

        Returns:
            指南内容文本，如果不存在则返回None
        """
        guide = self.get_guide(outline_id)
        return guide["content"] if guide else None

    def delete_guide(self, outline_id: str, delete_history: bool = True) -> dict[str, Any]:
        """
        删除指南内容

        Args:
            outline_id: 大纲ID
            delete_history: 是否同时删除历史版本（默认True）

        Returns:
            删除结果信息
        """
        file_path = self._get_guide_file_path(outline_id)
        deleted_files: list[str] = []

        # 删除主文件
        if file_path.exists():
            try:
                file_path.unlink()
                deleted_files.append(str(file_path))
                logger.info("指南文件已删除", outline_id=outline_id, file_path=str(file_path))
            except Exception as e:
                raise ProcessingError(f"删除指南文件失败: {e}")

        # 删除历史版本
        if delete_history:
            history_dir = self._get_history_dir_path(outline_id)
            if history_dir.exists():
                try:
                    for hist_file in history_dir.glob("*.md"):
                        hist_file.unlink()
                        deleted_files.append(str(hist_file))
                    # 删除空目录
                    history_dir.rmdir()
                    logger.debug("历史版本已删除", outline_id=outline_id, count=len(deleted_files) - 1)
                except Exception as e:
                    logger.warning("删除历史版本失败", outline_id=outline_id, error=str(e))

        return {
            "success": True,
            "outline_id": outline_id,
            "deleted_files": deleted_files,
            "deleted_count": len(deleted_files),
        }

    def list_guides(self, include_content: bool = False) -> list[dict[str, Any]]:
        """
        列出所有指南文件

        Args:
            include_content: 是否包含内容（默认False，仅返回基本信息）

        Returns:
            指南文件列表
        """
        guides: list[dict[str, Any]] = []

        if not self.template_dir.exists():
            return guides

        # 查找所有指南文件（排除历史目录中的文件）
        for file_path in self.template_dir.glob("*_guide.md"):
            if "_guide_history" in file_path.name:
                continue

            # 提取outline_id
            file_name = file_path.stem  # 去掉 .md 后缀
            if file_name.endswith("_guide"):
                outline_id = file_name[:-6]  # 去掉 _guide 后缀
            else:
                continue

            guide_info = {
                "outline_id": outline_id,
                "file_path": str(file_path),
                "file_name": file_path.name,
                "file_size": file_path.stat().st_size,
                "modified_at": datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=UTC
                ).isoformat(),
            }

            if include_content:
                try:
                    result = self._parse_guide_file(file_path)
                    guide_info["metadata"] = result["metadata"]
                    guide_info["content"] = result["content"]
                except Exception as e:
                    logger.warning("读取指南内容失败", file_path=str(file_path), error=str(e))
                    guide_info["content"] = None

            guides.append(guide_info)

        return guides

    def guide_exists(self, outline_id: str) -> bool:
        """
        检查指南是否存在

        Args:
            outline_id: 大纲ID

        Returns:
            是否存在
        """
        file_path = self._get_guide_file_path(outline_id)
        return file_path.exists()

    def update_metadata(self, outline_id: str, **kwargs) -> dict[str, Any] | None:
        """
        更新指南元数据

        Args:
            outline_id: 大纲ID
            **kwargs: 要更新的元数据字段

        Returns:
            更新后的指南信息，如果不存在则返回None
        """
        file_path = self._get_guide_file_path(outline_id)

        if not file_path.exists():
            return None

        try:
            result = self._parse_guide_file(file_path)
            metadata = result["metadata"]
            content = result["content"]

            # 更新元数据
            metadata.update(kwargs)
            metadata["updated_at"] = datetime.now(UTC).isoformat()

            # 重新写入文件
            file_content = self._format_guide_file(metadata, content)
            file_path.write_text(file_content, encoding="utf-8")

            logger.info("指南元数据已更新", outline_id=outline_id, updated_fields=list(kwargs.keys()))

            return self.get_guide(outline_id)

        except Exception as e:
            logger.error("更新元数据失败", outline_id=outline_id, error=str(e))
            raise ProcessingError(f"更新元数据失败: {e}")

    def get_history_versions(self, outline_id: str) -> list[dict[str, Any]]:
        """
        获取指南的历史版本列表

        Args:
            outline_id: 大纲ID

        Returns:
            历史版本列表
        """
        history_dir = self._get_history_dir_path(outline_id)

        if not history_dir.exists():
            return []

        versions: list[dict[str, Any]] = []

        for file_path in sorted(history_dir.glob("*.md")):
            try:
                stat = file_path.stat()
                versions.append({
                    "file_path": str(file_path),
                    "file_name": file_path.name,
                    "file_size": stat.st_size,
                    "created_at": datetime.fromtimestamp(stat.st_ctime, tz=UTC).isoformat(),
                })
            except Exception as e:
                logger.warning("读取历史版本信息失败", file_path=str(file_path), error=str(e))

        return versions

    def restore_version(self, outline_id: str, version_file: str) -> dict[str, Any]:
        """
        恢复历史版本

        Args:
            outline_id: 大纲ID
            version_file: 历史版本文件名

        Returns:
            恢复结果信息
        """
        history_dir = self._get_history_dir_path(outline_id)
        source_path = history_dir / version_file

        if not source_path.exists():
            raise ProcessingError(f"历史版本不存在: {version_file}")

        current_path = self._get_guide_file_path(outline_id)

        # 保存当前版本到历史
        if current_path.exists():
            self._save_history_version(outline_id, current_path, datetime.now(UTC))

        # 恢复版本
        try:
            content = source_path.read_text(encoding="utf-8")
            return self.save_guide(outline_id, content, save_history=False)
        except Exception as e:
            raise ProcessingError(f"恢复历史版本失败: {e}")
