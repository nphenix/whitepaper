# 生成命令: /speckit.implement T026A-MinerU
# 生成时间: 2025-12-10
# 来源: specs/001-multi-agent-doc-system/tasks.md

"""
MinerU在线服务适配器

该模块实现了MinerU在线API的适配器,用于封装MinerU API调用,
支持PDF和DOCX格式的文档解析,并将响应转换为LangChain Document格式.

功能特性:
- 封装MinerU在线服务API调用
- 支持PDF和DOCX格式解析
- 统一的响应格式转换(转换为LangChain Document格式)
- 完善的错误处理和日志记录
- 服务配置管理(从settings.py读取配置)
- 服务健康检查和错误重试机制(使用tenacity库)
- 支持异步处理,避免阻塞主流程

参考文档: https://mineru.net/apiManage/docs
"""

import asyncio
import hashlib
import json
import os
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
import requests
from langchain_core.documents import Document

from src.infrastructure.preprocessing.error_handler import (
    MinerUAdapterError,
    MinerUAPIError,
    MinerUConfigError,
    MinerUFileError,
    preprocessing_error_handler,
)
from src.infrastructure.preprocessing.logging_config import (
    create_mineru_logger,
)
from src.shared.config.settings import AppConfig, get_config
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class MinerUAdapter:
    """
    MinerU在线服务适配器

    封装MinerU在线API调用,提供统一的接口用于文档解析.
    统一使用批量上传API,即使是单个文件也通过批量API处理.
    支持同步和异步调用,自动重试机制,完善的错误处理.
    """

    def __init__(self, config: AppConfig | None = None):
        """
        初始化MinerU适配器

        Args:
            config: 应用配置对象,如果为None则使用默认配置

        Raises:
            MinerUConfigError: 配置错误时抛出
        """
        self.config = config or get_config()
        self.mineru_config = self.config.mineru

        # 创建专用的日志记录器
        self.preprocessing_logger = create_mineru_logger()

        # 验证配置
        if not self.mineru_config.api_key:
            error = MinerUConfigError(
                "MinerU API Key未配置,请在.env文件中设置MINERU_API_KEY",
                error_code="MINERU_CONFIG_ERROR",
            )
            preprocessing_error_handler.log_mineru_error(error, "config_validation")
            raise error

        if not self.mineru_config.api_url:
            error = MinerUConfigError(
                "MinerU API URL未配置,请在.env文件中设置MINERU_API_URL",
                error_code="MINERU_CONFIG_ERROR",
            )
            preprocessing_error_handler.log_mineru_error(error, "config_validation")
            raise error

        # 构建API端点
        # 规范化base_url,移除尾部斜杠
        self.base_url = self.mineru_config.api_url.rstrip("/")

        # 构建API端点 - 使用文件上传方式(推荐)
        # 根据官方文档,应该使用 /api/v4/file-urls/batch 申请上传链接
        if self.base_url.endswith("/api") or "/api/" in self.base_url:
            # base_url是 https://mineru.net/api 或包含 /api/,端点应该是 /v4/file-urls/batch
            self.batch_urls_endpoint = f"{self.base_url}/v4/file-urls/batch"
        else:
            # base_url是 https://mineru.net,端点应该是 /api/v4/file-urls/batch
            self.batch_urls_endpoint = f"{self.base_url}/api/v4/file-urls/batch"

        # 同时保留批量任务端点(用于URL方式,如果需要的话)
        if self.base_url.endswith("/api") or "/api/" in self.base_url:
            self.batch_task_endpoint = f"{self.base_url}/v4/extract/task/batch"
        else:
            self.batch_task_endpoint = f"{self.base_url}/api/v4/extract/task/batch"

        # 批量获取任务结果端点
        if self.base_url.endswith("/api") or "/api/" in self.base_url:
            self.batch_results_endpoint_template = (
                f"{self.base_url}/v4/extract-results/batch"
            )
        else:
            self.batch_results_endpoint_template = (
                f"{self.base_url}/api/v4/extract-results/batch"
            )

        # 健康检查端点
        self.health_endpoint = f"{self.base_url}/health"

        # 缓存目录(用于临时存储下载的ZIP文件,可以定期清理)
        cache_dir = Path(self.config.data_dir) / "cache" / "mineru"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir

        # 已处理文件目录(正式环境:存储处理后的文件结果,需要长期保存)
        # 注意:下载的ZIP文件和解压结果应该保存到这里,而不是cache_dir
        processed_dir = Path(self.config.data_dir) / "processed" / "mineru"
        processed_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir = processed_dir

        # 源文件上传目录(正式环境:用户上传的文件应该放在这里)
        # 注意:测试环境可能使用 data/temp/uploads,但正式环境应该使用 data/source/uploads
        source_uploads_dir = Path(self.config.data_dir) / "source" / "uploads"
        source_uploads_dir.mkdir(parents=True, exist_ok=True)
        self.source_uploads_dir = source_uploads_dir

        # 失败记录文件(记录处理失败的文件,避免短时间内重复提交)
        self.failed_records_file = cache_dir / "failed_records.json"

        # 锁目录(用于文件处理锁,防止并发重复提交)
        lock_dir = cache_dir / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        self.lock_dir = lock_dir

        # 设置请求头
        # 注意:确保API Key不为空且格式正确
        api_key = self.mineru_config.api_key.strip()
        if not api_key:
            msg = "MinerU API Key为空,请在.env文件中设置MINERU_API_KEY"
            raise MinerUConfigError(
                msg,
                error_code="MINERU_CONFIG_ERROR",
            )

        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        # SSL验证配置(从环境变量读取,默认启用)
        self.verify_ssl = os.getenv("MINERU_VERIFY_SSL", "true").lower() == "true"

        # 记录初始化信息(不记录完整的API Key,只记录长度和前缀)
        api_key_display = (
            f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        )
        logger.info(
            "MinerU适配器初始化完成: api_url=%s, "
            "batch_urls_endpoint=%s, "
            "timeout=%ss, "
            "max_retries=%s, "
            "api_key=%s (length=%s)",
            self.base_url,
            self.batch_urls_endpoint,
            self.mineru_config.timeout,
            self.mineru_config.max_retries,
            api_key_display,
            len(api_key),
        )

    def _validate_file(self, file_path: str) -> None:
        """
        验证文件是否符合要求

        Args:
            file_path: 文件路径

        Raises:
            MinerUFileError: 文件验证失败时抛出
        """
        path = Path(file_path)
        if not path.exists():
            error = MinerUFileError(
                f"文件不存在: {file_path}",
                error_code="FILE_NOT_FOUND",
                details={"file_path": file_path},
            )
            preprocessing_error_handler.log_mineru_error(error, file_path)
            raise error

        if not path.is_file():
            error = MinerUFileError(
                f"路径不是文件: {file_path}",
                error_code="NOT_A_FILE",
                details={"file_path": file_path},
            )
            preprocessing_error_handler.log_mineru_error(error, file_path)
            raise error

        # 检查文件大小
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.mineru_config.max_file_size_mb:
            error = MinerUFileError(
                f"文件大小超过限制: {file_size_mb:.2f}MB > {self.mineru_config.max_file_size_mb}MB",
                error_code="FILE_TOO_LARGE",
                details={
                    "file_path": file_path,
                    "file_size_mb": file_size_mb,
                    "max_size_mb": self.mineru_config.max_file_size_mb,
                },
            )
            preprocessing_error_handler.log_mineru_error(error, file_path)
            raise error

        # 检查文件格式
        suffix = path.suffix.lower()
        if suffix not in [".pdf", ".docx"]:
            error = MinerUFileError(
                f"不支持的文件格式: {suffix},仅支持PDF和DOCX",
                error_code="UNSUPPORTED_FORMAT",
                details={"file_path": file_path, "format": suffix},
            )
            preprocessing_error_handler.log_mineru_error(error, file_path)
            raise error

    def _get_file_hash(self, file_path: str) -> str:
        """
        计算文件的hash值(基于文件路径,修改时间和大小)

        Args:
            file_path: 文件路径

        Returns:
            文件的hash值
        """
        # 标准化为绝对路径,确保不同调用路径下的文件hash一致
        path = Path(file_path).absolute().resolve()
        stat = path.stat()
        # 使用文件路径(小写,避免Windows路径大小写问题),修改时间和大小计算hash
        hash_input = (
            f"{str(path).lower().replace('\\', '/')}_{stat.st_mtime}_{stat.st_size}"
        )
        return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

    def _get_friendly_dir_name(self, file_path: str) -> str:
        """
        生成用户友好的目录名(基于原始文件名)

        Args:
            file_path: 文件路径

        Returns:
            友好的目录名(原始文件名去除扩展名,加上hash前2位避免冲突)
        """
        file_name = Path(file_path).stem  # 获取文件名(不含扩展名)
        file_hash = self._get_file_hash(file_path)

        # 清理文件名中的特殊字符,避免路径问题
        # 替换Windows不允许的字符:< > : ' / \ | ? *
        import re

        safe_name = re.sub(r'[<>:"/\\|?*]', "_", file_name)

        # 如果文件名过长,截断(保留前100个字符)
        if len(safe_name) > 100:
            safe_name = safe_name[:100]

        # 添加hash前2位,避免同名文件冲突
        friendly_name = f"{safe_name}_{file_hash[:2]}"

        return friendly_name

    def _load_failed_records(self) -> dict[str, dict[str, Any]]:
        """
        加载失败记录

        Returns:
            失败记录字典,key为文件hash,value为失败信息
        """
        try:
            if self.failed_records_file.exists():
                with open(self.failed_records_file, encoding="utf-8") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.warning("加载失败记录失败: %s", e)
            return {}

    def _save_failed_record(self, file_path: str, error_msg: str) -> None:
        """
        保存失败记录

        Args:
            file_path: 文件路径
            error_msg: 错误信息
        """
        try:
            file_hash = self._get_file_hash(file_path)
            failed_records = self._load_failed_records()

            failed_records[file_hash] = {
                "file_path": file_path,
                "error_msg": error_msg,
                "failed_at": time.time(),
            }

            with open(self.failed_records_file, "w", encoding="utf-8") as f:
                json.dump(failed_records, f, ensure_ascii=False, indent=2)

            logger.info("保存失败记录: %s, 错误: %s", file_path, error_msg)
        except Exception as e:
            logger.warning("保存失败记录失败: %s", e)

    def clear_failed_record(self, file_path: str | None = None) -> None:
        """
        清除失败记录

        Args:
            file_path: 要清除的文件路径,如果为None则清除所有失败记录
        """
        try:
            if file_path is None:
                # 清除所有失败记录
                if self.failed_records_file.exists():
                    self.failed_records_file.unlink()
                    logger.info("已清除所有失败记录")
                else:
                    logger.info("没有失败记录需要清除")
            else:
                # 清除特定文件的失败记录
                file_hash = self._get_file_hash(file_path)
                failed_records = self._load_failed_records()
                if file_hash in failed_records:
                    del failed_records[file_hash]
                    with open(self.failed_records_file, "w", encoding="utf-8") as f:
                        json.dump(failed_records, f, ensure_ascii=False, indent=2)
                    logger.info("已清除文件失败记录: %s", file_path)
                else:
                    logger.info("文件没有失败记录: %s", file_path)
        except Exception as e:
            logger.warning("清除失败记录失败: %s", e)

    def _check_cached_result(self, file_path: str) -> dict[str, Any] | None:
        """
        检查文件是否有缓存结果

        Args:
            file_path: 文件路径

        Returns:
            缓存的结果数据,如果没有缓存则返回None
        """
        try:
            file_hash = self._get_file_hash(file_path)

            # 检查是否有处理记录
            record_file = self.cache_dir / f"{file_hash}_record.json"
            if record_file.exists():
                with open(record_file, encoding="utf-8") as f:
                    record = json.load(f)

                # 检查是否有解压文件夹
                batch_id = record.get("batch_id")
                file_name = record.get("file_name")
                record_file_path = record.get(
                    "file_path", file_path
                )  # 优先使用记录中的路径
                if batch_id and file_name:
                    cache_key = f"{batch_id}_{file_name}"
                    # 尝试从processed_dir查找(正式环境)
                    if record_file_path:
                        # 使用友好的目录名(原始文件名)
                        friendly_dir_name = self._get_friendly_dir_name(
                            record_file_path
                        )
                        processed_subdir = self.processed_dir / friendly_dir_name
                        extracted_dir = processed_subdir / f"{cache_key}_extracted"
                        # 如果processed_dir中不存在,尝试使用hash方式查找(向后兼容)
                        if not extracted_dir.exists():
                            file_hash = self._get_file_hash(record_file_path)
                            processed_subdir_old = self.processed_dir / file_hash[:2]
                            extracted_dir_old = (
                                processed_subdir_old / f"{cache_key}_extracted"
                            )
                            if extracted_dir_old.exists():
                                extracted_dir = extracted_dir_old
                            else:
                                # 最后回退到cache_dir(向后兼容)
                                extracted_dir = (
                                    self.cache_dir / f"{cache_key}_extracted"
                                )
                    else:
                        # 向后兼容:如果没有file_path,使用cache_dir
                        extracted_dir = self.cache_dir / f"{cache_key}_extracted"

                    if extracted_dir.exists() and extracted_dir.is_dir():
                        logger.info("找到缓存结果: %s", extracted_dir)
                        # 从解压文件夹中读取内容
                        markdown_content, json_content = (
                            self._read_content_from_extracted_dir(extracted_dir)
                        )

                        return {
                            "code": 0,
                            "msg": "使用缓存结果",
                            "markdown": markdown_content,
                            "json": json_content,
                            "extracted_dir": str(extracted_dir),
                            "data": {
                                "batch_id": batch_id,
                                "file_name": file_name,
                                "extracted_dir": str(extracted_dir),
                            },
                        }

            return None
        except Exception as e:
            logger.warning("检查缓存结果失败: %s", e)
            return None

    def _save_file_record(
        self, file_hash: str, file_path: str, batch_id: str, file_name: str
    ) -> None:
        """
        保存文件处理记录

        Args:
            file_hash: 文件hash
            file_path: 文件路径
            batch_id: 批量任务ID
            file_name: 文件名
        """
        try:
            record = {
                "file_hash": file_hash,
                "file_path": file_path,
                "batch_id": batch_id,
                "file_name": file_name,
                "processed_at": time.time(),
            }

            record_file = self.cache_dir / f"{file_hash}_record.json"
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)

            logger.debug("保存文件处理记录: %s", file_hash)
        except Exception as e:
            logger.warning("保存文件处理记录失败: %s", e)

    def _acquire_file_lock(
        self, file_hash: str, timeout: int = 30, max_retries: int = 5
    ) -> Any | None:
        """
        获取文件处理锁,防止并发重复提交

        Args:
            file_hash: 文件hash值
            timeout: 超时时间(秒)
            max_retries: 最大重试次数

        Returns:
            锁对象(用于释放锁),如果获取失败返回None
        """
        lock_file = self.lock_dir / f"{file_hash}.lock"

        for attempt in range(max_retries):
            try:
                # 尝试创建锁文件(原子操作)
                try:
                    # 如果文件不存在,会创建;如果存在,会抛出FileExistsError
                    lock_file.touch(exist_ok=False)
                    logger.info(
                        f"🔒 成功获取文件锁 (尝试 {attempt + 1}/{max_retries}): file_hash={file_hash}"
                    )
                    return lock_file
                except FileExistsError:
                    # 文件已存在,检查是否过期
                    if lock_file.exists():
                        lock_age = time.time() - lock_file.stat().st_mtime
                        if lock_age > timeout:
                            logger.warning(
                                f"发现过期锁文件,删除: {lock_file}, age={lock_age:.1f}s"
                            )
                            try:
                                lock_file.unlink()
                                # 删除后重试创建
                                continue
                            except Exception:
                                pass
                        else:
                            logger.debug(
                                f"文件正在处理中(已有锁文件): file_hash={file_hash}, lock_age={lock_age:.1f}s"
                            )
                            if attempt < max_retries - 1:
                                # 等待一小段时间后重试
                                time.sleep(0.5)
                                continue
                            return None
                    else:
                        # 文件在检查时被删除,重试
                        continue
            except Exception as e:
                logger.warning(
                    f"获取文件锁失败 (尝试 {attempt + 1}/{max_retries}): {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(0.5)
                    continue
                return None

        logger.warning(
            f"无法获取文件锁(已重试 {max_retries} 次): file_hash={file_hash}"
        )
        return None

    def _release_file_lock(self, lock_file: Any | None):
        """
        释放文件处理锁

        Args:
            lock_file: 锁文件路径
        """
        if lock_file and isinstance(lock_file, Path) and lock_file.exists():
            try:
                lock_file.unlink()
                logger.debug("释放文件锁: %s", lock_file)
            except Exception as e:
                logger.warning("释放文件锁失败: %s", e)

    # 旧的 _call_api 方法已删除,现在统一使用批量API (extract_batch)

    def _query_batch_results(self, batch_id: str) -> dict[str, Any]:
        """
        查询批量任务结果

        按照官方API文档:https://mineru.net/apiManage/docs
        请求头需要包含 Content-Type: application/json

        Args:
            batch_id: 批量任务ID

        Returns:
            任务结果数据

        Raises:
            MinerUAPIError: 查询失败时抛出
        """
        try:
            url = f"{self.batch_results_endpoint_template}/{batch_id}"

            # 按照官方示例,请求头需要包含 Content-Type
            query_headers = {
                **self.headers,
                "Content-Type": "application/json",
            }

            logger.info("🔍 查询批量任务结果: %s, batch_id=%s", url, batch_id)
            response = requests.get(
                url,
                headers=query_headers,
                timeout=30,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            result = response.json()

            # 详细记录响应内容,便于调试
            logger.info(
                "📋 批量任务结果响应: code=%s, msg=%s",
                result.get("code"),
                result.get("msg"),
            )
            logger.debug("完整响应数据: %s", result)

            if result.get("code") != 0:
                error_msg = result.get("msg", "查询任务结果失败")
                error_code = result.get("code")
                logger.error(
                    "❌ 查询任务结果失败: %s (code: %s)", error_msg, error_code
                )
                msg = f"查询任务结果失败: {error_msg} (code: {error_code})"
                raise MinerUAPIError(
                    msg,
                    error_code="QUERY_RESULT_ERROR",
                    details={"batch_id": batch_id, "response": result},
                )

            # 检查响应数据结构
            data = result.get("data", {})
            if not data:
                logger.warning("⚠️ 响应中缺少data字段")
                return result

            # 记录提取结果信息
            extract_results = data.get("extract_result", [])
            if extract_results:
                logger.info("📊 找到 %s 个文件的处理结果", len(extract_results))
                for i, item in enumerate(extract_results):
                    file_name = item.get("file_name", f"file_{i}")
                    state = item.get("state", "unknown")
                    logger.info("  文件 %s: %s -> 状态: %s", i + 1, file_name, state)

                    # 如果状态为done,记录下载链接
                    if state == "done":
                        zip_url = item.get("full_zip_url", "")
                        if zip_url:
                            logger.info("    ✅ 下载链接: %s...", zip_url[:80])
                        else:
                            logger.warning("    ⚠️ 状态为done但缺少下载链接")
                    elif state == "failed":
                        err_msg = item.get("err_msg", "未知错误")
                        logger.error("    ❌ 处理失败: %s", err_msg)
            else:
                logger.warning("⚠️ 未找到extract_result数据")

            return result

        except requests.exceptions.RequestException as e:
            error_msg = f"查询任务结果请求失败: batch_id={batch_id}"
            logger.exception(error_msg)
            raise MinerUAPIError(
                error_msg,
                error_code="QUERY_RESULT_REQUEST_ERROR",
                details={"batch_id": batch_id},
                original_error=e,
            )

    def _wait_for_result(
        self,
        batch_id: str,
        file_name: str,
        file_path: str,
        max_wait_time: int = 300,
        poll_interval: int = 5,
    ) -> dict[str, Any]:
        """
        等待任务完成并获取解析结果

        Args:
            batch_id: 批量任务ID
            file_name: 文件名
            file_path: 文件路径
            max_wait_time: 最大等待时间(秒)
            poll_interval: 轮询间隔(秒)

        Returns:
            解析结果数据

        Raises:
            MinerUAPIError: 等待超时或任务失败时抛出
        """
        start_time = time.time()
        last_state = None

        while time.time() - start_time < max_wait_time:
            try:
                result = self._query_batch_results(batch_id)
                data = result.get("data", {})
                extract_results = data.get("extract_result", [])

                # 添加详细日志
                logger.debug(
                    f"查询结果: batch_id={data.get('batch_id')}, extract_result数量={len(extract_results)}"
                )

                if not extract_results:
                    logger.warning(
                        f"未找到任务结果: batch_id={batch_id}, 响应数据: {data}"
                    )
                    time.sleep(poll_interval)
                    continue

                # 查找匹配的文件结果
                file_result = None
                for item in extract_results:
                    item_file_name = item.get("file_name", "")
                    logger.debug("检查文件: %s vs %s", item_file_name, file_name)
                    if item_file_name == file_name:
                        file_result = item
                        logger.info("找到匹配的文件结果: %s", file_name)
                        break

                if not file_result:
                    available_files = [
                        item.get("file_name", "unknown") for item in extract_results
                    ]
                    logger.warning(
                        f"未找到文件 {file_name} 的结果: batch_id={batch_id}, "
                        f"可用文件: {available_files}"
                    )
                    time.sleep(poll_interval)
                    continue

                state = file_result.get("state", "")

                # 如果状态改变,记录日志
                if state != last_state:
                    logger.info("任务状态更新: %s -> %s", file_name, state)
                    last_state = state

                # 检查任务状态
                if state == "done":
                    # 任务完成,下载并提取结果
                    full_zip_url = file_result.get("full_zip_url")
                    if not full_zip_url:
                        msg = f"任务完成但未找到结果下载链接: {file_name}"
                        raise MinerUAPIError(
                            msg,
                            error_code="NO_RESULT_URL",
                            details={"batch_id": batch_id, "file_name": file_name},
                        )

                    logger.info("任务完成,开始下载结果: %s", file_name)
                    return self._download_and_extract_result(
                        full_zip_url, batch_id, file_name, file_path
                    )

                elif state == "failed":
                    err_msg = file_result.get("err_msg", "解析失败")
                    msg = f"任务解析失败: {file_name}, 错误: {err_msg}"
                    raise MinerUAPIError(
                        msg,
                        error_code="TASK_FAILED",
                        details={
                            "batch_id": batch_id,
                            "file_name": file_name,
                            "err_msg": err_msg,
                        },
                    )

                elif state in ["waiting-file", "pending", "running", "converting"]:
                    # 任务进行中,显示进度
                    if "extract_progress" in file_result:
                        progress = file_result["extract_progress"]
                        extracted = progress.get("extracted_pages", 0)
                        total = progress.get("total_pages", 0)
                        logger.info(
                            "任务进行中: %s, 进度: %s/%s 页",
                            file_name,
                            extracted,
                            total,
                        )

                    time.sleep(poll_interval)
                    continue
                else:
                    logger.warning("未知任务状态: %s, 继续等待...", state)
                    time.sleep(poll_interval)
                    continue

            except MinerUAPIError:
                # 重新抛出MinerUAPIError
                raise
            except Exception as e:
                logger.warning("查询任务结果时出错: %s, 继续重试...", e)
                time.sleep(poll_interval)
                continue

        # 超时
        msg = f"等待任务完成超时: {file_name}, batch_id={batch_id}"
        raise MinerUAPIError(
            msg,
            error_code="TASK_TIMEOUT",
            details={
                "batch_id": batch_id,
                "file_name": file_name,
                "max_wait_time": max_wait_time,
            },
        )

    def _download_and_extract_result(
        self, zip_url: str, batch_id: str, file_name: str, file_path: str
    ) -> dict[str, Any]:
        """
        下载并提取解析结果(解压到完整文件夹)

        Args:
            zip_url: ZIP文件下载URL
            batch_id: 批量任务ID
            file_name: 文件名
            file_path: 原始文件路径

        Returns:
            解析结果数据,包含解压后的文件夹路径
        """
        try:
            # 正式环境:将处理结果保存到 processed_dir,而不是 cache_dir
            # cache_dir 仅用于临时缓存ZIP文件,processed_dir 用于长期保存解压结果
            cache_key = f"{batch_id}_{file_name}"

            # ZIP文件:先保存到cache_dir(临时缓存,可以定期清理)
            cache_file = self.cache_dir / f"{cache_key}.zip"

            # 解压目录:保存到processed_dir(正式环境长期保存)
            # 使用原始文件名作为目录名,对用户更友好
            friendly_dir_name = self._get_friendly_dir_name(file_path)
            processed_subdir = self.processed_dir / friendly_dir_name
            processed_subdir.mkdir(parents=True, exist_ok=True)
            extracted_dir = processed_subdir / f"{cache_key}_extracted"

            # 处理zip_url:如果是相对URL,需要拼接base_url
            if zip_url.startswith("/"):
                # 相对URL,拼接base_url
                zip_url = f"{self.base_url}{zip_url}"
                logger.info("📝 ZIP URL是相对路径,已拼接为完整URL: %s", zip_url)
            elif not zip_url.startswith(("http://", "https://")):
                # 既不是绝对URL也不是相对URL,尝试拼接base_url
                zip_url = f"{self.base_url}/{zip_url.lstrip('/')}"
                logger.info("📝 ZIP URL格式异常,已拼接为完整URL: %s", zip_url)

            logger.info("📥 开始下载ZIP文件: %s", file_name)
            logger.info("   下载链接: %s", zip_url)
            logger.info("   缓存文件: %s", cache_file)
            logger.info("   解压目录: %s", extracted_dir)

            # 如果解压文件夹已存在,直接使用
            if extracted_dir.exists() and extracted_dir.is_dir():
                logger.info("✅ 使用缓存的解压文件夹: %s", extracted_dir)
                # 从解压文件夹中读取 markdown 和 json(用于向后兼容)
                markdown_content, json_content = self._read_content_from_extracted_dir(
                    extracted_dir
                )
            else:
                # 下载ZIP文件
                if not cache_file.exists():
                    logger.info("🌐 从URL下载ZIP文件: %s", zip_url)

                    # 使用更详细的请求头,确保下载成功
                    # 注意:下载zip文件时也需要包含API认证头
                    download_headers = {
                        **self.headers,  # 包含Authorization头(Bearer token)
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/octet-stream, application/zip, application/x-zip-compressed, */*",
                        "Accept-Encoding": "gzip, deflate",
                        "Connection": "keep-alive",
                    }

                    response = requests.get(
                        zip_url,
                        headers=download_headers,
                        timeout=300,
                        verify=self.verify_ssl,
                        stream=True,  # 使用流式下载,处理大文件
                    )
                    response.raise_for_status()

                    # 检查内容类型
                    content_type = response.headers.get("content-type", "")
                    content_length = response.headers.get("content-length", "unknown")
                    logger.info(
                        "📋 文件信息: 类型=%s, 大小=%s bytes",
                        content_type,
                        content_length,
                    )

                    # 保存到缓存
                    with open(cache_file, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:  # 过滤掉保持连接的新块
                                f.write(chunk)

                    file_size = cache_file.stat().st_size
                    logger.info(
                        "💾 ZIP文件下载完成: %s, 大小: %s bytes", cache_file, file_size
                    )
                else:
                    logger.info("✅ 使用缓存的ZIP文件: %s", cache_file)
                    file_size = cache_file.stat().st_size
                    logger.info("📁 缓存文件大小: %s bytes", file_size)

                # 验证ZIP文件完整性
                if not zipfile.is_zipfile(cache_file):
                    msg = f"下载的文件不是有效的ZIP文件: {cache_file}"
                    raise MinerUAPIError(
                        msg,
                        error_code="INVALID_ZIP_FILE",
                        details={"cache_file": str(cache_file), "zip_url": zip_url},
                    )

                # 解压ZIP文件到完整文件夹
                logger.info("📂 解压ZIP文件到: %s", extracted_dir)
                extracted_dir.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(cache_file, "r") as zip_ref:
                    file_list = zip_ref.namelist()
                    logger.info("📋 ZIP文件包含 %s 个文件/目录", len(file_list))

                    # 记录文件列表(前10个文件)
                    for i, file in enumerate(file_list[:10]):
                        logger.info("  %s: %s", i + 1, file)
                    if len(file_list) > 10:
                        logger.info("  ... 还有 %s 个文件", len(file_list) - 10)

                    # 解压文件
                    zip_ref.extractall(extracted_dir)

                    # 验证解压结果
                    extracted_files = list(extracted_dir.rglob("*"))
                    logger.info(
                        "✅ ZIP文件解压完成,实际解压了 %s 个文件/目录",
                        len(extracted_files),
                    )

                # 从解压文件夹中读取 markdown 和 json(用于向后兼容)
                markdown_content, json_content = self._read_content_from_extracted_dir(
                    extracted_dir
                )

            # 返回解析结果
            result = {
                "code": 0,
                "msg": "解析成功",
                "markdown": markdown_content,  # 保留用于向后兼容
                "json": json_content,  # 保留用于向后兼容
                "extracted_dir": str(extracted_dir),  # 新增:解压后的文件夹路径
                "data": {
                    "batch_id": batch_id,
                    "file_name": file_name,
                    "zip_url": zip_url,
                    "extracted_dir": str(extracted_dir),
                },
            }

            logger.info("🎉 文件处理完成: %s", file_name)
            logger.info("   Markdown长度: %s 字符", len(markdown_content))
            logger.info("   JSON长度: %s 字符", len(json_content))
            logger.info("   解压目录: %s", extracted_dir)

            # 保存文件处理记录(在下载和解压成功后保存,确保缓存可用)
            file_hash = self._get_file_hash(file_path)
            logger.info(
                "💾 保存文件处理记录: file_hash=%s, batch_id=%s, file_name=%s",
                file_hash,
                batch_id,
                file_name,
            )
            self._save_file_record(file_hash, file_path, batch_id, file_name)
            logger.info("✅ 文件处理记录已保存,后续调用将使用缓存")

            return result

        except Exception as e:
            error_msg = f"下载或提取解析结果失败: {file_name}"
            logger.exception(error_msg)
            raise MinerUAPIError(
                error_msg,
                error_code="EXTRACT_RESULT_ERROR",
                details={
                    "batch_id": batch_id,
                    "file_name": file_name,
                    "zip_url": zip_url,
                },
                original_error=e,
            )

    def _read_content_from_extracted_dir(self, extracted_dir: Path) -> tuple[str, str]:
        """
        从解压后的文件夹中读取 markdown 和 json 内容

        Args:
            extracted_dir: 解压后的文件夹路径

        Returns:
            (markdown_content, json_content) 元组
        """
        markdown_content = ""
        json_content = ""

        # 查找 markdown 文件
        md_files = list(extracted_dir.rglob("*.md"))
        if not md_files:
            # 如果没有找到.md文件,尝试查找其他文本文件
            md_files = list(extracted_dir.rglob("*.txt")) + list(
                extracted_dir.rglob("*.markdown")
            )

        if md_files:
            try:
                with open(md_files[0], encoding="utf-8") as f:
                    markdown_content = f.read()
                logger.debug(
                    f"从解压文件夹读取 markdown: {md_files[0]}, 长度: {len(markdown_content)}"
                )
            except Exception as e:
                logger.warning("读取 markdown 文件失败: %s", e)

        # 查找 json 文件
        json_files = list(extracted_dir.rglob("*.json"))
        if json_files:
            try:
                with open(json_files[0], encoding="utf-8") as f:
                    json_content = f.read()
                logger.debug(
                    f"从解压文件夹读取 json: {json_files[0]}, 长度: {len(json_content)}"
                )
            except Exception as e:
                logger.warning("读取 json 文件失败: %s", e)

        return markdown_content, json_content

    def _extract_all_formats_from_zip(
        self, zip_path: Path, file_name: str
    ) -> dict[str, str]:
        """
        从ZIP文件中提取所有格式的内容

        Args:
            zip_path: ZIP文件路径
            file_name: 原始文件名

        Returns:
            包含各种格式内容的字典
        """
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                file_list = zip_ref.namelist()
                logger.info("ZIP文件内容: %s", file_list)

                result = {}

                # 提取Markdown内容
                md_files = [f for f in file_list if f.endswith(".md")]
                if not md_files:
                    # 如果没有找到.md文件,尝试查找其他文本文件
                    text_files = [
                        f for f in file_list if f.endswith((".txt", ".markdown"))
                    ]
                    if text_files:
                        md_files = text_files

                if md_files:
                    md_file = md_files[0]
                    content = zip_ref.read(md_file).decode("utf-8")
                    result["markdown"] = content
                    logger.info(
                        "从ZIP中提取markdown: %s, 长度: %s", md_file, len(content)
                    )

                # 提取JSON内容
                json_files = [f for f in file_list if f.endswith(".json")]
                if json_files:
                    json_file = json_files[0]
                    content = zip_ref.read(json_file).decode("utf-8")
                    result["json"] = content
                    logger.info(
                        "从ZIP中提取JSON: %s, 长度: %s", json_file, len(content)
                    )

                # 提取HTML内容
                html_files = [f for f in file_list if f.endswith(".html")]
                if html_files:
                    html_file = html_files[0]
                    content = zip_ref.read(html_file).decode("utf-8")
                    result["html"] = content
                    logger.info(
                        "从ZIP中提取HTML: %s, 长度: %s", html_file, len(content)
                    )

                # 检查图表数据(可能在images目录或单独的图表文件中)
                image_files = [
                    f
                    for f in file_list
                    if f.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".gif"))
                ]
                if image_files:
                    result["images"] = image_files
                    logger.info("发现图片文件: %s 个", len(image_files))

                # 检查图表数据文件(可能是专门的图表数据格式)
                chart_files = [
                    f for f in file_list if "chart" in f.lower() or "graph" in f.lower()
                ]
                if chart_files:
                    result["chart_files"] = chart_files
                    logger.info("发现图表文件: %s", chart_files)

                return result

        except zipfile.BadZipFile as e:
            msg = f"ZIP文件损坏: {zip_path}"
            raise MinerUAPIError(
                msg,
                error_code="BAD_ZIP_FILE",
                details={"zip_path": str(zip_path)},
                original_error=e,
            )
        except Exception as e:
            msg = f"提取文件内容失败: {zip_path}"
            raise MinerUAPIError(
                msg,
                error_code="EXTRACT_CONTENT_ERROR",
                details={"zip_path": str(zip_path)},
                original_error=e,
            )

    def _extract_markdown_from_zip(self, zip_path: Path, file_name: str) -> str:
        """
        从ZIP文件中提取markdown内容(保持向后兼容)

        Args:
            zip_path: ZIP文件路径
            file_name: 原始文件名

        Returns:
            Markdown内容
        """
        extracted_data = self._extract_all_formats_from_zip(zip_path, file_name)
        return extracted_data.get("markdown", "")

    async def _acall_api(self, file_path: str, file_format: str) -> dict[str, Any]:
        """
        调用MinerU API进行文档解析(异步)

        使用官方推荐的批量文件上传链接方式:
        1. 先调用 /api/v4/file-urls/batch 获取文件上传链接
        2. 使用PUT方法上传文件到获取的链接
        3. 系统会自动提交解析任务

        Args:
            file_path: 文件路径
            file_format: 文件格式(pdf或docx)

        Returns:
            API响应数据

        Raises:
            MinerUAPIError: API调用失败时抛出
        """
        self._validate_file(file_path)

        # 标准化文件路径
        file_path = str(Path(file_path).absolute().resolve())

        # 检查是否有缓存结果,避免重复提交
        logger.info("🔍 检查文件缓存(异步): %s", file_path)
        cached_result = self._check_cached_result(file_path)
        if cached_result:
            logger.info("✅ 使用缓存结果,跳过API调用(异步): %s", file_path)
            return cached_result

        # 获取文件锁,防止并发重复提交
        file_hash = self._get_file_hash(file_path)
        lock_file = self._acquire_file_lock(file_hash)
        if lock_file is None:
            # 如果无法获取锁,说明文件正在处理中,等待一段时间后再次检查缓存
            logger.warning("⚠️ 文件正在处理中,等待后重试(异步): %s", file_path)
            await asyncio.sleep(2)  # 等待2秒
            cached_result = self._check_cached_result(file_path)
            if cached_result:
                logger.info("✅ 等待后找到缓存结果(异步): %s", file_path)
                return cached_result
            # 如果还是没有,抛出错误
            msg = f"文件正在被其他进程处理: {file_path}"
            raise MinerUAPIError(
                msg,
                error_code="FILE_LOCKED",
                details={"file_path": file_path},
            )

        try:
            # 双重检查锁定:获取锁后再次检查缓存,避免竞态条件
            logger.info("🔒 已获取文件锁,再次检查缓存(异步): %s", file_path)
            cached_result = self._check_cached_result(file_path)
            if cached_result:
                logger.info("✅ 获取锁后发现缓存结果,使用缓存(异步): %s", file_path)
                self._release_file_lock(lock_file)
                return cached_result

            logger.info("🚀 开始异步调用MinerU API解析文档(新提交): %s", file_path)

            # 创建SSL上下文(如果需要禁用SSL验证)
            ssl_context = None
            if not self.verify_ssl:
                import ssl

                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(
                ssl=ssl_context if not self.verify_ssl else True
            )

            # 步骤1: 申请文件上传链接
            file_name = Path(file_path).name
            batch_data = {
                "files": [{"name": file_name, "data_id": file_name}],
                "model_version": "vlm",  # 使用vlm模型版本
                "extra_formats": [
                    "html"
                ],  # 请求额外格式输出(json和markdown是默认格式,无需指定)
            }

            # 设置Content-Type为application/json
            json_headers = {**self.headers, "Content-Type": "application/json"}

            logger.info("申请文件上传链接: %s", self.batch_urls_endpoint)
            # 创建session并在整个上传过程中保持打开
            async with aiohttp.ClientSession(connector=connector) as session:
                # 步骤1: 申请文件上传链接
                async with session.post(
                    self.batch_urls_endpoint,
                    headers=json_headers,
                    json=batch_data,
                    timeout=aiohttp.ClientTimeout(total=self.mineru_config.timeout),
                    ssl=ssl_context if not self.verify_ssl else True,
                ) as batch_response:
                    batch_response.raise_for_status()
                    batch_result = await batch_response.json()

                # 检查响应码
                if batch_result.get("code") != 0:
                    error_msg = batch_result.get("msg", "申请文件上传链接失败")
                    msg = f"申请文件上传链接失败: {error_msg}"
                    raise MinerUAPIError(
                        msg,
                        error_code="BATCH_URL_ERROR",
                        details={"file_path": file_path, "response": batch_result},
                    )

                batch_id = batch_result["data"]["batch_id"]
                logger.info("获取到任务ID: batch_id=%s", batch_id)

                # 步骤2: 上传文件到获取的链接
                # 注意:上传文件时不需要设置Content-Type请求头
                # 在同一个session中完成上传,保持连接
                logger.info("开始上传文件: %s", file_path)

                # 从batch_result中获取上传链接
                file_urls = batch_result["data"]["file_urls"]
                if not file_urls:
                    msg = "未获取到文件上传链接"
                    raise MinerUAPIError(
                        msg,
                        error_code="NO_UPLOAD_URL",
                        details={"file_path": file_path, "batch_result": batch_result},
                    )

                upload_url = file_urls[0]  # 第一个文件的上传链接
                logger.info("获取到上传链接: %s...", upload_url[:80])

                # 读取文件内容到内存(因为需要在async上下文中使用)
                with open(file_path, "rb") as f:
                    file_data = f.read()

                # 在同一个session中上传文件,避免会话关闭问题
                async with session.put(
                    upload_url,
                    data=file_data,
                    timeout=aiohttp.ClientTimeout(total=self.mineru_config.timeout),
                    ssl=ssl_context if not self.verify_ssl else True,
                ) as upload_response:
                    upload_response.raise_for_status()

                    if upload_response.status == 200:
                        logger.info(
                            "✅ 文件上传成功(异步): %s, batch_id=%s",
                            file_path,
                            batch_id,
                        )
                        # 保存文件处理记录(在文件上传成功后立即保存,避免并发重复提交)
                        file_hash = self._get_file_hash(file_path)
                        logger.info(
                            "💾 保存文件处理记录(异步): file_hash=%s, batch_id=%s, file_name=%s",
                            file_hash,
                            batch_id,
                            file_name,
                        )
                        self._save_file_record(
                            file_hash, file_path, batch_id, file_name
                        )
                        logger.info("✅ 文件处理记录已保存,后续调用将使用缓存(异步)")
                        # 系统会自动提交解析任务,现在需要等待并获取解析结果
                        logger.info(
                            "⏳ 等待解析任务完成(异步): batch_id=%s, file_name=%s",
                            batch_id,
                            file_name,
                        )
                        result = await self._await_result(
                            batch_id, file_name, file_path
                        )
                        # 释放文件锁
                        self._release_file_lock(lock_file)
                        return result
                    else:
                        msg = f"文件上传失败: 状态码 {upload_response.status}"
                        raise MinerUAPIError(
                            msg,
                            error_code="FILE_UPLOAD_ERROR",
                            details={
                                "file_path": file_path,
                                "status_code": upload_response.status,
                            },
                        )

        except TimeoutError as e:
            error_msg = f"MinerU API异步请求超时: {file_path}"
            logger.exception(error_msg)
            raise MinerUAPIError(
                error_msg,
                error_code="API_TIMEOUT",
                details={"file_path": file_path, "timeout": self.mineru_config.timeout},
                original_error=e,
            )

        except aiohttp.ClientSSLError as e:
            error_msg = f"MinerU API异步SSL连接错误: {file_path}"
            logger.exception(error_msg)
            raise MinerUAPIError(
                error_msg,
                error_code="API_SSL_ERROR",
                details={
                    "file_path": file_path,
                    "endpoint": self.batch_urls_endpoint,
                    "verify_ssl": self.verify_ssl,
                },
                original_error=e,
            )
        except aiohttp.ClientResponseError as e:
            # 处理HTTP错误(如401, 403, 404等)
            status_code = e.status
            response_text = ""
            try:
                if hasattr(e, "message"):
                    response_text = str(e.message)[:500]
            except Exception:
                pass

            error_msg = f"MinerU API异步HTTP错误: {file_path} (状态码: {status_code})"
            if status_code == 401:
                error_msg += " - 认证失败,请检查MINERU_API_KEY是否正确配置"
            elif status_code == 403:
                error_msg += " - 权限不足,请检查API Key是否有访问权限"
            elif status_code == 404:
                error_msg += " - 端点不存在,请检查API URL配置"

            logger.error(
                f"{error_msg}, endpoint={self.batch_urls_endpoint}, "
                f"response={response_text}"
            )
            raise MinerUAPIError(
                error_msg,
                error_code=(
                    f"API_HTTP_ERROR_{status_code}" if status_code else "API_HTTP_ERROR"
                ),
                details={
                    "file_path": file_path,
                    "status_code": status_code,
                    "endpoint": self.batch_urls_endpoint,
                    "response_text": response_text,
                },
                original_error=e,
            )
        except aiohttp.ClientError as e:
            error_msg = f"MinerU API异步请求失败: {file_path}"
            logger.exception(error_msg)
            raise MinerUAPIError(
                error_msg,
                error_code="API_REQUEST_ERROR",
                details={"file_path": file_path, "endpoint": self.batch_urls_endpoint},
                original_error=e,
            )

        except ValueError as e:
            error_msg = f"MinerU API响应解析失败: {file_path}"
            logger.exception(error_msg)
            raise MinerUAPIError(
                error_msg,
                error_code="API_RESPONSE_PARSE_ERROR",
                details={"file_path": file_path},
                original_error=e,
            )
        finally:
            # 确保在异常情况下也释放锁
            if "lock_file" in locals():
                self._release_file_lock(lock_file)

    async def _aquery_batch_results(self, batch_id: str) -> dict[str, Any]:
        """
        异步查询批量任务结果

        Args:
            batch_id: 批量任务ID

        Returns:
            任务结果数据

        Raises:
            MinerUAPIError: 查询失败时抛出
        """
        try:
            # 创建SSL上下文(如果需要禁用SSL验证)
            ssl_context = None
            if not self.verify_ssl:
                import ssl

                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(
                ssl=ssl_context if not self.verify_ssl else True
            )
            url = f"{self.batch_results_endpoint_template}/{batch_id}"

            # 按照官方示例,请求头需要包含 Content-Type
            query_headers = {
                **self.headers,
                "Content-Type": "application/json",
            }

            logger.info("🔍 异步查询批量任务结果: %s, batch_id=%s", url, batch_id)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    url,
                    headers=query_headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=ssl_context if not self.verify_ssl else True,
                ) as response:
                    response.raise_for_status()
                    result = await response.json()

            # 详细记录响应内容,便于调试
            logger.info(
                "📋 异步批量任务结果响应: code=%s, msg=%s",
                result.get("code"),
                result.get("msg"),
            )
            logger.debug("完整响应数据: %s", result)

            if result.get("code") != 0:
                error_msg = result.get("msg", "查询任务结果失败")
                error_code = result.get("code")
                logger.error(
                    f"❌ 异步查询任务结果失败: {error_msg} (code: {error_code})"
                )
                msg = f"查询任务结果失败: {error_msg} (code: {error_code})"
                raise MinerUAPIError(
                    msg,
                    error_code="QUERY_RESULT_ERROR",
                    details={"batch_id": batch_id, "response": result},
                )

            # 检查响应数据结构
            data = result.get("data", {})
            if not data:
                logger.warning("⚠️ 异步响应中缺少data字段")
                return result

            # 记录提取结果信息
            extract_results = data.get("extract_result", [])
            if extract_results:
                logger.info("📊 异步找到 %s 个文件的处理结果", len(extract_results))
                for i, item in enumerate(extract_results):
                    file_name = item.get("file_name", f"file_{i}")
                    state = item.get("state", "unknown")
                    logger.info(
                        "  异步文件 %s: %s -> 状态: %s", i + 1, file_name, state
                    )

                    # 如果状态为done,记录下载链接
                    if state == "done":
                        zip_url = item.get("full_zip_url", "")
                        if zip_url:
                            logger.info("    ✅ 异步下载链接: %s...", zip_url[:80])
                        else:
                            logger.warning("    ⚠️ 异步状态为done但缺少下载链接")
                    elif state == "failed":
                        err_msg = item.get("err_msg", "未知错误")
                        logger.error("    ❌ 异步处理失败: %s", err_msg)
            else:
                logger.warning("⚠️ 异步未找到extract_result数据")

            return result

        except aiohttp.ClientError as e:
            error_msg = f"异步查询任务结果请求失败: batch_id={batch_id}"
            logger.exception(error_msg)
            raise MinerUAPIError(
                error_msg,
                error_code="QUERY_RESULT_REQUEST_ERROR",
                details={"batch_id": batch_id},
                original_error=e,
            )

    async def _await_result(
        self,
        batch_id: str,
        file_name: str,
        file_path: str,
        max_wait_time: int = 300,
        poll_interval: int = 5,
    ) -> dict[str, Any]:
        """
        异步等待任务完成并获取解析结果

        Args:
            batch_id: 批量任务ID
            file_name: 文件名
            file_path: 文件路径
            max_wait_time: 最大等待时间(秒)
            poll_interval: 轮询间隔(秒)

        Returns:
            解析结果数据

        Raises:
            MinerUAPIError: 等待超时或任务失败时抛出
        """
        start_time = time.time()
        last_state = None

        while time.time() - start_time < max_wait_time:
            try:
                result = await self._aquery_batch_results(batch_id)
                data = result.get("data", {})
                extract_results = data.get("extract_result", [])

                # 添加详细日志
                logger.debug(
                    f"异步查询结果: batch_id={data.get('batch_id')}, extract_result数量={len(extract_results)}"
                )

                if not extract_results:
                    logger.warning(
                        f"未找到任务结果: batch_id={batch_id}, 响应数据: {data}"
                    )
                    await asyncio.sleep(poll_interval)
                    continue

                # 查找匹配的文件结果
                file_result = None
                for item in extract_results:
                    item_file_name = item.get("file_name", "")
                    logger.debug("检查文件: %s vs %s", item_file_name, file_name)
                    if item_file_name == file_name:
                        file_result = item
                        logger.info("找到匹配的文件结果: %s", file_name)
                        break

                if not file_result:
                    available_files = [
                        item.get("file_name", "unknown") for item in extract_results
                    ]
                    logger.warning(
                        f"未找到文件 {file_name} 的结果: batch_id={batch_id}, "
                        f"可用文件: {available_files}"
                    )
                    await asyncio.sleep(poll_interval)
                    continue

                state = file_result.get("state", "")

                # 如果状态改变,记录日志
                if state != last_state:
                    logger.info("任务状态更新: %s -> %s", file_name, state)
                    last_state = state

                # 检查任务状态
                if state == "done":
                    # 任务完成,下载并提取结果
                    full_zip_url = file_result.get("full_zip_url")
                    if not full_zip_url:
                        msg = f"任务完成但未找到结果下载链接: {file_name}"
                        raise MinerUAPIError(
                            msg,
                            error_code="NO_RESULT_URL",
                            details={"batch_id": batch_id, "file_name": file_name},
                        )

                    logger.info("任务完成,开始下载结果: %s", file_name)
                    return await self._adownload_and_extract_result(
                        full_zip_url, batch_id, file_name, file_path
                    )

                elif state == "failed":
                    err_msg = file_result.get("err_msg", "解析失败")
                    msg = f"任务解析失败: {file_name}, 错误: {err_msg}"
                    raise MinerUAPIError(
                        msg,
                        error_code="TASK_FAILED",
                        details={
                            "batch_id": batch_id,
                            "file_name": file_name,
                            "err_msg": err_msg,
                        },
                    )

                elif state in ["waiting-file", "pending", "running", "converting"]:
                    # 任务进行中,显示进度
                    if "extract_progress" in file_result:
                        progress = file_result["extract_progress"]
                        extracted = progress.get("extracted_pages", 0)
                        total = progress.get("total_pages", 0)
                        logger.info(
                            "任务进行中: %s, 进度: %s/%s 页",
                            file_name,
                            extracted,
                            total,
                        )

                    await asyncio.sleep(poll_interval)
                    continue
                else:
                    logger.warning("未知任务状态: %s, 继续等待...", state)
                    await asyncio.sleep(poll_interval)
                    continue

            except MinerUAPIError:
                # 重新抛出MinerUAPIError
                raise
            except Exception as e:
                logger.warning("异步查询任务结果时出错: %s, 继续重试...", e)
                await asyncio.sleep(poll_interval)
                continue

        # 超时
        msg = f"异步等待任务完成超时: {file_name}, batch_id={batch_id}"
        raise MinerUAPIError(
            msg,
            error_code="TASK_TIMEOUT",
            details={
                "batch_id": batch_id,
                "file_name": file_name,
                "max_wait_time": max_wait_time,
            },
        )

    async def _adownload_and_extract_result(
        self, zip_url: str, batch_id: str, file_name: str, file_path: str
    ) -> dict[str, Any]:
        """
        异步下载并提取解析结果(解压到完整文件夹)

        Args:
            zip_url: ZIP文件下载URL
            batch_id: 批量任务ID
            file_name: 文件名
            file_path: 原始文件路径

        Returns:
            解析结果数据,包含解压后的文件夹路径
        """
        try:
            # 正式环境:将处理结果保存到 processed_dir,而不是 cache_dir
            # cache_dir 仅用于临时缓存ZIP文件,processed_dir 用于长期保存解压结果
            cache_key = f"{batch_id}_{file_name}"

            # ZIP文件:先保存到cache_dir(临时缓存,可以定期清理)
            cache_file = self.cache_dir / f"{cache_key}.zip"

            # 解压目录:保存到processed_dir(正式环境长期保存)
            # 使用原始文件名作为目录名,对用户更友好
            friendly_dir_name = self._get_friendly_dir_name(file_path)
            processed_subdir = self.processed_dir / friendly_dir_name
            processed_subdir.mkdir(parents=True, exist_ok=True)
            extracted_dir = processed_subdir / f"{cache_key}_extracted"

            # 处理zip_url:如果是相对URL,需要拼接base_url
            if zip_url.startswith("/"):
                # 相对URL,拼接base_url
                zip_url = f"{self.base_url}{zip_url}"
                logger.info("📝 ZIP URL是相对路径(异步),已拼接为完整URL: %s", zip_url)
            elif not zip_url.startswith(("http://", "https://")):
                # 既不是绝对URL也不是相对URL,尝试拼接base_url
                zip_url = f"{self.base_url}/{zip_url.lstrip('/')}"
                logger.info("📝 ZIP URL格式异常(异步),已拼接为完整URL: %s", zip_url)

            logger.info("📥 异步开始下载ZIP文件: %s", file_name)
            logger.info("   下载链接: %s", zip_url)
            logger.info("   缓存文件: %s", cache_file)
            logger.info("   解压目录: %s", extracted_dir)

            # 如果解压文件夹已存在,直接使用
            if extracted_dir.exists() and extracted_dir.is_dir():
                logger.info("✅ 异步使用缓存的解压文件夹: %s", extracted_dir)
                # 从解压文件夹中读取 markdown 和 json(用于向后兼容)
                markdown_content, json_content = self._read_content_from_extracted_dir(
                    extracted_dir
                )
            else:
                # 下载ZIP文件
                if not cache_file.exists():
                    logger.info("🌐 异步从URL下载ZIP文件: %s", zip_url)

                    # 创建SSL上下文(如果需要禁用SSL验证)
                    ssl_context = None
                    if not self.verify_ssl:
                        import ssl

                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE

                    connector = aiohttp.TCPConnector(
                        ssl=ssl_context if not self.verify_ssl else True
                    )

                    # 使用更详细的请求头
                    # 注意:下载zip文件时也需要包含API认证头
                    download_headers = {
                        **self.headers,  # 包含Authorization头(Bearer token)
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/octet-stream, application/zip, application/x-zip-compressed, */*",
                        "Accept-Encoding": "gzip, deflate",
                        "Connection": "keep-alive",
                    }

                    async with aiohttp.ClientSession(connector=connector) as session:
                        async with session.get(
                            zip_url,
                            headers=download_headers,
                            timeout=aiohttp.ClientTimeout(total=300),
                            ssl=ssl_context if not self.verify_ssl else True,
                        ) as response:
                            response.raise_for_status()

                            # 检查内容类型
                            content_type = response.headers.get("content-type", "")
                            content_length = response.headers.get(
                                "content-length", "unknown"
                            )
                            logger.info(
                                "📋 异步文件信息: 类型=%s, 大小=%s bytes",
                                content_type,
                                content_length,
                            )

                            # 流式下载
                            with open(cache_file, "wb") as f:
                                async for chunk in response.content.iter_chunked(8192):
                                    if chunk:
                                        f.write(chunk)

                    file_size = cache_file.stat().st_size
                    logger.info(
                        "💾 异步ZIP文件下载完成: %s, 大小: %s bytes",
                        cache_file,
                        file_size,
                    )
                else:
                    logger.info("✅ 异步使用缓存的ZIP文件: %s", cache_file)
                    file_size = cache_file.stat().st_size
                    logger.info("📁 异步缓存文件大小: %s bytes", file_size)

                # 验证ZIP文件完整性
                if not zipfile.is_zipfile(cache_file):
                    msg = f"异步下载的文件不是有效的ZIP文件: {cache_file}"
                    raise MinerUAPIError(
                        msg,
                        error_code="INVALID_ZIP_FILE",
                        details={"cache_file": str(cache_file), "zip_url": zip_url},
                    )

                # 解压ZIP文件到完整文件夹
                logger.info("📂 异步解压ZIP文件到: %s", extracted_dir)
                extracted_dir.mkdir(parents=True, exist_ok=True)

                with zipfile.ZipFile(cache_file, "r") as zip_ref:
                    file_list = zip_ref.namelist()
                    logger.info("📋 异步ZIP文件包含 %s 个文件/目录", len(file_list))

                    # 记录文件列表(前10个文件)
                    for i, file in enumerate(file_list[:10]):
                        logger.info("  %s: %s", i + 1, file)
                    if len(file_list) > 10:
                        logger.info("  ... 还有 %s 个文件", len(file_list) - 10)

                    # 解压文件
                    zip_ref.extractall(extracted_dir)

                    # 验证解压结果
                    extracted_files = list(extracted_dir.rglob("*"))
                    logger.info(
                        "✅ 异步ZIP文件解压完成,实际解压了 %s 个文件/目录",
                        len(extracted_files),
                    )

                # 从解压文件夹中读取 markdown 和 json(用于向后兼容)
                markdown_content, json_content = self._read_content_from_extracted_dir(
                    extracted_dir
                )

            # 返回解析结果
            result = {
                "code": 0,
                "msg": "解析成功",
                "markdown": markdown_content,  # 保留用于向后兼容
                "json": json_content,  # 保留用于向后兼容
                "extracted_dir": str(extracted_dir),  # 新增:解压后的文件夹路径
                "data": {
                    "batch_id": batch_id,
                    "file_name": file_name,
                    "zip_url": zip_url,
                    "extracted_dir": str(extracted_dir),
                },
            }

            logger.info("🎉 异步文件处理完成: %s", file_name)
            logger.info("   Markdown长度: %s 字符", len(markdown_content))
            logger.info("   JSON长度: %s 字符", len(json_content))
            logger.info("   解压目录: %s", extracted_dir)

            # 保存文件处理记录(在下载和解压成功后保存,确保缓存可用)
            file_hash = self._get_file_hash(file_path)
            logger.info(
                "💾 保存文件处理记录(异步): file_hash=%s, batch_id=%s, file_name=%s",
                file_hash,
                batch_id,
                file_name,
            )
            self._save_file_record(file_hash, file_path, batch_id, file_name)
            logger.info("✅ 文件处理记录已保存,后续调用将使用缓存(异步)")

            return result

        except Exception as e:
            error_msg = f"异步下载或提取解析结果失败: {file_name}"
            logger.exception(error_msg)
            raise MinerUAPIError(
                error_msg,
                error_code="EXTRACT_RESULT_ERROR",
                details={
                    "batch_id": batch_id,
                    "file_name": file_name,
                    "zip_url": zip_url,
                },
                original_error=e,
            )

    def _convert_to_documents(
        self, api_response: dict[str, Any], file_path: str, file_format: str
    ) -> list[Document]:
        """
        将MinerU API响应转换为LangChain Document格式

        Args:
            api_response: MinerU API响应数据
            file_path: 原始文件路径
            file_format: 文件格式

        Returns:
            Document对象列表

        Raises:
            MinerUAdapterError: 转换失败时抛出
        """
        try:
            documents = []

            # MinerU API返回的数据结构可能包含:
            # - markdown: Markdown格式的文本内容
            # - json: JSON格式的结构化数据
            # - pages: 页面列表
            # - metadata: 元数据信息

            # 提取主要文本内容
            page_content = ""
            structured_data = None

            # 优先使用JSON格式的结构化数据
            if api_response.get("json"):
                try:
                    import json

                    structured_data = json.loads(api_response["json"])
                    logger.info("成功解析JSON结构化数据: %s", file_path)
                except json.JSONDecodeError as e:
                    logger.warning("JSON数据解析失败: %s", e)

            # 提取文本内容
            if "markdown" in api_response:
                page_content = api_response["markdown"]
            elif "text" in api_response:
                page_content = api_response["text"]
            elif "content" in api_response:
                page_content = api_response["content"]
            else:
                # 如果没有找到文本内容,尝试从pages中提取
                if "pages" in api_response and isinstance(api_response["pages"], list):
                    page_contents = []
                    for page in api_response["pages"]:
                        if isinstance(page, dict):
                            if "content" in page:
                                page_contents.append(str(page["content"]))
                            elif "text" in page:
                                page_contents.append(str(page["text"]))
                        elif isinstance(page, str):
                            page_contents.append(page)
                    page_content = "\n\n".join(page_contents)

            # 如果有结构化数据,尝试从中提取图表信息并增强文本内容
            if structured_data:
                enhanced_content = self._enhance_content_with_structured_data(
                    page_content, structured_data
                )
                if enhanced_content != page_content:
                    page_content = enhanced_content
                    logger.info("使用结构化数据增强了内容: %s", file_path)

            if not page_content:
                logger.warning("MinerU API响应中未找到文本内容: %s", file_path)
                page_content = ""

            # 构建元数据
            metadata: dict[str, Any] = {
                "source": file_path,
                "format": file_format,
                "pipeline": "mineru",
                "processed_at": datetime.now().isoformat(),
                "has_json": bool(structured_data),
                "has_structured_data": structured_data is not None,
            }

            # 添加解压文件夹路径(如果存在)
            if "extracted_dir" in api_response:
                metadata["extracted_dir"] = api_response["extracted_dir"]
            elif "data" in api_response and isinstance(api_response["data"], dict):
                if "extracted_dir" in api_response["data"]:
                    metadata["extracted_dir"] = api_response["data"]["extracted_dir"]

            # 如果有结构化数据,提取更详细的元数据
            if structured_data:
                # 提取文档信息
                if "document_info" in structured_data:
                    doc_info = structured_data["document_info"]
                    for key in ["title", "pages", "language"]:
                        if key in doc_info:
                            metadata[f"document_{key}"] = doc_info[key]

                # 统计各种元素数量
                if "pages" in structured_data and isinstance(
                    structured_data["pages"], list
                ):
                    metadata["total_pages"] = len(structured_data["pages"])

                    # 统计各种块类型
                    table_count = 0
                    formula_count = 0
                    image_count = 0
                    chart_count = 0

                    for page in structured_data["pages"]:
                        if "blocks" in page and isinstance(page["blocks"], list):
                            for block in page["blocks"]:
                                block_type = block.get("type", "").lower()
                                if block_type == "table":
                                    table_count += 1
                                elif block_type == "formula":
                                    formula_count += 1
                                elif block_type == "image":
                                    image_count += 1
                                    # 检查是否是图表
                                    if "chart" in block.get("content", "").lower():
                                        chart_count += 1

                    if table_count > 0:
                        metadata["table_count"] = table_count
                    if formula_count > 0:
                        metadata["formula_count"] = formula_count
                    if image_count > 0:
                        metadata["image_count"] = image_count
                    if chart_count > 0:
                        metadata["chart_count"] = chart_count

            # 提取API响应中的元数据
            if "metadata" in api_response:
                api_metadata = api_response["metadata"]
                if isinstance(api_metadata, dict):
                    # 提取总页数
                    if "total_pages" in api_metadata:
                        metadata["total_pages"] = api_metadata["total_pages"]
                    elif "pages" in api_metadata:
                        metadata["total_pages"] = api_metadata["pages"]

                    # 提取其他元数据
                    for key in ["title", "author", "created_at", "modified_at"]:
                        if key in api_metadata:
                            metadata[key] = api_metadata[key]

            # 如果响应中有pages信息(非结构化),提取页面相关元数据
            if "pages" in api_response and isinstance(api_response["pages"], list):
                metadata["total_pages"] = len(api_response["pages"])

                # 统计表格和公式数量
                table_count = 0
                formula_count = 0
                for page in api_response["pages"]:
                    if isinstance(page, dict):
                        if "tables" in page:
                            table_count += len(page.get("tables", []))
                        if "formulas" in page:
                            formula_count += len(page.get("formulas", []))

                if table_count > 0:
                    metadata["table_count"] = table_count
                if formula_count > 0:
                    metadata["formula_count"] = formula_count

            # 创建Document对象
            document = Document(page_content=page_content, metadata=metadata)
            documents.append(document)

            logger.info(
                "成功转换MinerU响应为Document: %s, "
                "pages=%s, "
                "charts=%s, "
                "tables=%s, "
                "formulas=%s, "
                "has_json=%s",
                file_path,
                metadata.get("total_pages", "unknown"),
                metadata.get("chart_count", 0),
                metadata.get("table_count", 0),
                metadata.get("formula_count", 0),
                metadata.get("has_json", False),
            )

            return documents

        except Exception as e:
            error_msg = f"转换MinerU响应为Document失败: {file_path}"
            logger.exception(error_msg)
            raise MinerUAdapterError(
                error_msg,
                error_code="RESPONSE_CONVERSION_ERROR",
                details={"file_path": file_path},
                original_error=e,
            ) from e

    def _enhance_content_with_structured_data(
        self, original_content: str, structured_data: dict[str, Any]
    ) -> str:
        """
        使用结构化数据增强原始内容,特别是图表数据

        Args:
            original_content: 原始文本内容
            structured_data: JSON格式的结构化数据

        Returns:
            增强后的内容
        """
        try:
            enhanced_content = original_content
            chart_data_sections = []

            # 从结构化数据中提取图表信息
            if "pages" in structured_data and isinstance(
                structured_data["pages"], list
            ):
                for page in structured_data["pages"]:
                    if "blocks" in page and isinstance(page["blocks"], list):
                        for block in page["blocks"]:
                            block_type = block.get("type", "").lower()

                            # 处理图表块
                            if (
                                block_type == "image"
                                and "chart" in block.get("content", "").lower()
                            ):
                                chart_info = {
                                    "page": page.get("page_number", "unknown"),
                                    "content": block.get("content", ""),
                                    "caption": block.get("caption", ""),
                                    "bbox": block.get("bbox", []),
                                }
                                chart_data_sections.append(
                                    f"\n\n## 图表数据 (页面 {chart_info['page']})\n"
                                )
                                chart_data_sections.append(
                                    f"**图片路径**: {chart_info['content']}\n"
                                )
                                if chart_info["caption"]:
                                    chart_data_sections.append(
                                        f"**标题**: {chart_info['caption']}\n"
                                    )
                                if chart_info["bbox"]:
                                    chart_data_sections.append(
                                        f"**位置**: {chart_info['bbox']}\n"
                                    )

                            # 处理表格块
                            elif block_type == "table":
                                table_data = block.get("content", [])
                                if isinstance(table_data, list) and table_data:
                                    chart_data_sections.append(
                                        f"\n\n## 表格数据 (页面 {page.get('page_number', 'unknown')})\n"
                                    )
                                    # 将表格数据转换为Markdown格式
                                    for i, row in enumerate(table_data):
                                        if isinstance(row, list):
                                            row_str = " | ".join(
                                                str(cell) for cell in row
                                            )
                                            chart_data_sections.append(f"{row_str} |")
                                            if i == 0:
                                                chart_data_sections.append(
                                                    "|" + "---|" * len(row)
                                                )

            # 如果找到图表数据,将其添加到内容末尾
            if chart_data_sections:
                enhanced_content += "\n\n" + "=" * 50 + "\n"
                enhanced_content += "## 结构化数据补充\n"
                enhanced_content += "=" * 50 + "\n"
                enhanced_content += "".join(chart_data_sections)
                logger.info(
                    "使用结构化数据补充了 %s 个数据段", len(chart_data_sections)
                )

            return enhanced_content

        except Exception as e:
            logger.warning("使用结构化数据增强内容失败: %s", e)
            return original_content

    def _move_to_processed(self, file_path: str) -> str:
        """
        将文件移动到已处理目录

        注意:测试文件通常在 data/temp/uploads 目录下,处理完成后会移动到
        data/processed/mineru/ 目录,避免重复提交.

        Args:
            file_path: 源文件路径

        Returns:
            移动后的文件路径
        """
        source_path = Path(file_path).resolve()
        if not source_path.exists():
            logger.warning("文件不存在,无法移动: %s", file_path)
            return file_path

        # 如果文件已经在已处理目录中,不需要移动
        try:
            if str(source_path).startswith(str(self.processed_dir.resolve())):
                logger.debug("文件已在已处理目录中,无需移动: %s", file_path)
                return str(source_path)
        except Exception:
            pass

        # 使用原始文件名作为目录名,对用户更友好
        friendly_dir_name = self._get_friendly_dir_name(str(source_path))
        file_name = source_path.name
        target_dir = self.processed_dir / friendly_dir_name
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / file_name

        # 如果目标文件已存在,添加时间戳
        if target_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            stem = source_path.stem
            suffix = source_path.suffix
            target_path = target_dir / f"{stem}_{timestamp}{suffix}"

        try:
            # 移动文件
            shutil.move(str(source_path), str(target_path))
            logger.info("✅ 文件已移动到已处理目录: %s -> %s", source_path, target_path)
            logger.info("   源目录: %s", source_path.parent)
            logger.info("   目标目录: %s", target_path.parent)
            return str(target_path)
        except Exception as e:
            logger.error("移动文件失败: %s -> %s, 错误: %s", file_path, target_path, e)
            msg = f"移动文件到已处理目录失败: {file_path}"
            raise MinerUFileError(
                msg,
                error_code="FILE_MOVE_ERROR",
                details={"file_path": file_path, "target_path": str(target_path)},
                original_error=e,
            ) from e

    def _is_processed(self, file_path: str) -> bool:
        """
        检查文件是否已在已处理目录

        Args:
            file_path: 文件路径

        Returns:
            是否已处理
        """
        source_path = Path(file_path)

        # 如果文件不存在,检查是否在已处理目录中
        if not source_path.exists():
            # 文件不存在,检查已处理目录
            try:
                # 使用友好的目录名查找
                friendly_dir_name = self._get_friendly_dir_name(file_path)
                file_name = source_path.name
                target_dir = self.processed_dir / friendly_dir_name
                if target_dir.exists():
                    # 检查是否有匹配的文件
                    for _processed_file in target_dir.glob(f"{file_name}*"):
                        # 如果文件名匹配,认为已处理
                        return True

                # 向后兼容:尝试使用hash方式查找(旧数据)
                file_hash = self._get_file_hash(file_path)
                target_dir_old = self.processed_dir / file_hash[:2]
                if target_dir_old.exists():
                    for _processed_file in target_dir_old.glob(f"{file_name}*"):
                        return True
            except Exception as e:
                logger.debug("检查已处理文件时出错: %s", e)
            return False

        # 如果文件在已处理目录中,说明已经处理过
        try:
            if str(source_path.resolve()).startswith(str(self.processed_dir.resolve())):
                return True
        except Exception:
            pass

        # 检查已处理目录中是否有相同文件名的文件
        try:
            # 使用友好的目录名查找
            friendly_dir_name = self._get_friendly_dir_name(file_path)
            file_name = source_path.name
            target_dir = self.processed_dir / friendly_dir_name
            if target_dir.exists():
                # 检查是否有匹配的文件
                for _processed_file in target_dir.glob(f"{file_name}*"):
                    # 文件名匹配即可
                    return True

            # 向后兼容:尝试使用hash方式查找(旧数据)
            file_hash = self._get_file_hash(file_path)
            target_dir_old = self.processed_dir / file_hash[:2]
            if target_dir_old.exists():
                for _processed_file in target_dir_old.glob(f"{file_name}*"):
                    return True
        except Exception as e:
            logger.debug("检查文件是否已处理时出错: %s", e)

        return False

    def extract_batch(
        self, file_paths_or_dir: str | list[str], file_formats: list[str] | None = None
    ) -> dict[str, list[Document]]:
        """
        批量提取文档内容(一次性提交所有文件)

        Args:
            file_paths_or_dir: 文件路径列表,或目录路径(会自动收集目录下的所有PDF和DOCX文件)
            file_formats: 文件格式列表(pdf或docx),如果为None则自动检测

        Returns:
            字典,key为文件路径,value为Document对象列表

        Raises:
            MinerUAdapterError: 提取失败时抛出
        """
        # 如果是目录路径,自动收集所有PDF和DOCX文件
        if isinstance(file_paths_or_dir, str):
            dir_path = Path(file_paths_or_dir)
            if dir_path.is_dir():
                logger.info("📁 检测到目录路径,收集目录下的所有文件: %s", dir_path)
                file_paths = []
                for ext in [".pdf", ".docx"]:
                    # 收集所有匹配的文件
                    found_files = list(dir_path.glob(f"*{ext}"))
                    # 过滤:只保留常规文件,排除隐藏文件,临时文件等
                    for fp in found_files:
                        if fp.is_file():  # 确保是文件而不是目录
                            file_name = fp.name
                            # 排除隐藏文件(以.开头)和临时文件(以~结尾)
                            if not file_name.startswith(".") and not file_name.endswith(
                                "~"
                            ):
                                file_paths.append(fp)
                file_paths = [str(fp) for fp in file_paths]
                logger.info(
                    f"📋 找到 {len(file_paths)} 个文件: {[Path(fp).name for fp in file_paths]}"
                )
            else:
                file_paths = [file_paths_or_dir]
        else:
            file_paths = file_paths_or_dir

        if not file_paths:
            logger.warning("未找到需要处理的文件")
            return {}

        # 标准化文件路径
        file_paths = [str(Path(fp).absolute().resolve()) for fp in file_paths]

        # 自动检测文件格式
        if file_formats is None:
            file_formats = []
            for file_path in file_paths:
                suffix = Path(file_path).suffix.lower()
                if suffix == ".pdf":
                    file_formats.append("pdf")
                elif suffix == ".docx":
                    file_formats.append("docx")
                else:
                    msg = f"不支持的文件格式: {file_path}"
                    raise MinerUFileError(
                        msg,
                        error_code="UNSUPPORTED_FORMAT",
                        details={"file_path": file_path},
                    )

        # 先检查缓存,分离需要处理和已缓存的文件
        files_to_process = []
        formats_to_process = []
        cached_results = {}

        for file_path, file_format in zip(file_paths, file_formats, strict=False):
            cached_result = self._check_cached_result(file_path)
            if cached_result:
                logger.info("✅ 使用缓存结果,跳过上传: %s", file_path)
                cached_results[file_path] = cached_result
            else:
                files_to_process.append(file_path)
                formats_to_process.append(file_format)

        # 批量提交需要处理的文件(如果有)
        batch_results = {}
        if files_to_process:
            logger.info(
                "📦 需要处理 %s 个文件(%s 个使用缓存)",
                len(files_to_process),
                len(cached_results),
            )
            batch_results = self._call_batch_api(files_to_process, formats_to_process)
        else:
            logger.info("✅ 所有文件都使用缓存,无需上传")

        # 合并缓存结果和批量处理结果
        all_results = {**cached_results, **batch_results}

        # 转换为Document格式
        results = {}
        for file_path, api_response in all_results.items():
            file_format = file_formats[file_paths.index(file_path)]
            results[file_path] = self._convert_to_documents(
                api_response, file_path, file_format
            )

        return results

    def _call_batch_api(
        self, file_paths: list[str], file_formats: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        批量调用MinerU API(一次性提交所有文件)

        Args:
            file_paths: 文件路径列表
            file_formats: 文件格式列表

        Returns:
            字典,key为文件路径,value为API响应数据
        """
        # 验证所有文件
        for file_path in file_paths:
            self._validate_file(file_path)

        logger.info("📦 批量提交 %s 个文件到MinerU", len(file_paths))

        # 步骤1: 申请批量文件上传链接
        files_data = []
        for file_path in file_paths:
            file_name = Path(file_path).name
            Path(file_path).suffix.lower()
            # 使用文件路径的hash作为data_id,确保唯一性
            file_hash = self._get_file_hash(file_path)

            # 构建文件信息
            file_info = {"name": file_name, "data_id": file_hash}

            # 注意:is_ocr 参数仅对 pipeline 模型有效,我们使用的是 vlm 模型
            # vlm 模型会自动处理OCR,无需手动设置 is_ocr

            files_data.append(file_info)

        batch_data = {
            "files": files_data,
            "model_version": "vlm",
            # extra_formats 是可选参数,暂时不设置,使用默认格式(markdown和json)
        }

        json_headers = {**self.headers, "Content-Type": "application/json"}

        logger.info("申请批量文件上传链接: %s", self.batch_urls_endpoint)
        logger.debug("请求体: %s", batch_data)
        logger.debug("请求头: %s", json_headers)

        batch_response = requests.post(
            self.batch_urls_endpoint,
            headers=json_headers,
            json=batch_data,
            timeout=self.mineru_config.timeout,
            verify=self.verify_ssl,
        )

        logger.debug("响应状态码: %s", batch_response.status_code)
        batch_response.raise_for_status()
        batch_result = batch_response.json()
        logger.debug("响应内容: %s", batch_result)

        if batch_result.get("code") != 0:
            error_msg = batch_result.get("msg", "申请文件上传链接失败")
            error_code = batch_result.get("code")
            logger.error("API返回错误: code=%s, msg=%s", error_code, error_msg)
            logger.error("完整响应: %s", batch_result)
            msg = f"申请批量文件上传链接失败: {error_msg} (code: {error_code})"
            raise MinerUAPIError(
                msg,
                error_code="BATCH_URL_ERROR",
                details={"response": batch_result},
            )

        batch_id = batch_result["data"]["batch_id"]
        file_urls = batch_result["data"]["file_urls"]

        if len(file_urls) != len(file_paths):
            msg = f"获取的上传链接数量不匹配: 期望 {len(file_paths)}, 实际 {len(file_urls)}"
            raise MinerUAPIError(
                msg,
                error_code="NO_UPLOAD_URL",
                details={"batch_result": batch_result},
            )

        logger.info(
            "✅ 获取到批量上传链接: batch_id=%s, 文件数=%s", batch_id, len(file_paths)
        )

        # 建立 data_id 到 file_path 的映射,用于后续匹配结果
        data_id_to_path = {}
        for file_path in file_paths:
            file_hash = self._get_file_hash(file_path)
            data_id_to_path[file_hash] = file_path

        # 步骤2: 上传所有文件
        for i, (file_path, upload_url) in enumerate(
            zip(file_paths, file_urls, strict=False)
        ):
            file_name = Path(file_path).name
            logger.info("上传文件 %s/%s: %s", i + 1, len(file_paths), file_name)
            logger.debug("上传URL: %s", upload_url)

            # 检查文件是否存在和可读
            if not Path(file_path).exists():
                msg = f"文件不存在: {file_path}"
                raise MinerUAPIError(
                    msg,
                    error_code="FILE_NOT_FOUND",
                )

            file_size = Path(file_path).stat().st_size
            logger.debug(
                "文件大小: %s bytes (%.2f MB)", file_size, file_size / 1024 / 1024
            )

            with open(file_path, "rb") as f:
                # 根据API文档,上传文件时无须设置 Content-Type 请求头
                upload_response = requests.put(
                    upload_url,
                    data=f,
                    timeout=self.mineru_config.timeout,
                    verify=self.verify_ssl,
                )
                logger.debug("上传响应状态码: %s", upload_response.status_code)
                upload_response.raise_for_status()

                # 记录上传成功的详细信息
                if upload_response.status_code == 200:
                    logger.info("✅ 文件上传成功: %s", file_name)
                else:
                    logger.warning(
                        "⚠️ 文件上传响应状态码: %s", upload_response.status_code
                    )

        logger.info("✅ 所有文件上传成功,等待处理完成: batch_id=%s", batch_id)
        logger.info("⏳ 等待服务端自动提交解析任务(通常需要几秒钟)...")

        # 文件上传后,等待一段时间让服务端自动扫描并提交解析任务
        # 根据API文档:文件上传完成后,系统会自动扫描已上传完成文件自动提交解析任务
        import time

        wait_after_upload = 3  # 等待3秒,让服务端有时间处理
        logger.info("等待 %s 秒,让服务端自动提交解析任务...", wait_after_upload)
        time.sleep(wait_after_upload)

        # 步骤3: 等待所有文件处理完成并获取结果
        return self._wait_for_batch_results(batch_id, file_paths, data_id_to_path)

    async def _acall_batch_api(
        self, file_paths: list[str], file_formats: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        异步批量调用MinerU API(一次性提交所有文件)

        Args:
            file_paths: 文件路径列表
            file_formats: 文件格式列表

        Returns:
            字典,key为文件路径,value为API响应数据
        """
        # 验证所有文件
        for file_path in file_paths:
            self._validate_file(file_path)

        logger.info("📦 批量提交 %s 个文件到MinerU(异步)", len(file_paths))

        # 创建SSL上下文(如果需要禁用SSL验证)
        ssl_context = None
        if not self.verify_ssl:
            import ssl

            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(
            ssl=ssl_context if not self.verify_ssl else True
        )

        # 步骤1: 申请批量文件上传链接
        files_data = []
        for file_path in file_paths:
            file_name = Path(file_path).name
            # 使用文件路径的hash作为data_id,确保唯一性
            file_hash = self._get_file_hash(file_path)
            files_data.append({"name": file_name, "data_id": file_hash})

        batch_data = {
            "files": files_data,
            "model_version": "vlm",
            "extra_formats": ["html"],  # json和markdown是默认格式,无需指定
        }

        json_headers = {**self.headers, "Content-Type": "application/json"}

        logger.info("申请批量文件上传链接(异步): %s", self.batch_urls_endpoint)
        # 使用同一个session完成所有操作
        async with aiohttp.ClientSession(connector=connector) as session:
            # 步骤1: 申请批量文件上传链接
            async with session.post(
                self.batch_urls_endpoint,
                headers=json_headers,
                json=batch_data,
                timeout=aiohttp.ClientTimeout(total=self.mineru_config.timeout),
                ssl=ssl_context if not self.verify_ssl else True,
            ) as batch_response:
                batch_response.raise_for_status()
                batch_result = await batch_response.json()

            if batch_result.get("code") != 0:
                error_msg = batch_result.get("msg", "申请文件上传链接失败")
                msg = f"申请批量文件上传链接失败: {error_msg}"
                raise MinerUAPIError(
                    msg,
                    error_code="BATCH_URL_ERROR",
                    details={"response": batch_result},
                )

            batch_id = batch_result["data"]["batch_id"]
            file_urls = batch_result["data"]["file_urls"]

            if len(file_urls) != len(file_paths):
                msg = f"获取的上传链接数量不匹配: 期望 {len(file_paths)}, 实际 {len(file_urls)}"
                raise MinerUAPIError(
                    msg,
                    error_code="NO_UPLOAD_URL",
                    details={"batch_result": batch_result},
                )

            logger.info(
                f"✅ 获取到批量上传链接(异步): batch_id={batch_id}, 文件数={len(file_paths)}"
            )

            # 步骤2: 上传所有文件(在同一个session中)
            for i, (file_path, upload_url) in enumerate(
                zip(file_paths, file_urls, strict=False)
            ):
                file_name = Path(file_path).name
                logger.info(
                    "上传文件 %s/%s(异步): %s", i + 1, len(file_paths), file_name
                )
                logger.debug("上传URL: %s", upload_url)

                # 检查文件是否存在和可读
                if not Path(file_path).exists():
                    msg = f"文件不存在: {file_path}"
                    raise MinerUAPIError(
                        msg,
                        error_code="FILE_NOT_FOUND",
                    )

                file_size = Path(file_path).stat().st_size
                logger.debug(
                    f"文件大小: {file_size} bytes ({file_size / 1024 / 1024:.2f} MB)"
                )

                # aiohttp不支持直接传递文件对象,需要读取文件内容到内存
                # 对于大文件,可以考虑使用aiofiles,但这里先使用同步读取
                with open(file_path, "rb") as f:
                    file_data = f.read()

                # 根据API文档,上传文件时无须设置 Content-Type 请求头
                # aiohttp会自动处理二进制数据,不需要额外设置
                try:
                    async with session.put(
                        upload_url,
                        data=file_data,
                        timeout=aiohttp.ClientTimeout(total=self.mineru_config.timeout),
                        ssl=ssl_context if not self.verify_ssl else True,
                    ) as upload_response:
                        logger.debug(f"上传响应状态码(异步): {upload_response.status}")
                        upload_response.raise_for_status()

                        # 记录上传成功的详细信息
                        if upload_response.status == 200:
                            logger.info("✅ 文件上传成功(异步): %s", file_name)
                        else:
                            logger.warning(
                                "⚠️ 文件上传响应状态码(异步): %s", upload_response.status
                            )
                except aiohttp.ClientResponseError as e:
                    # 如果是403错误,提供更详细的错误信息
                    if e.status == 403:
                        error_msg = (
                            f"文件上传被拒绝(403 Forbidden): {file_name}\n"
                            f"URL: {upload_url}\n"
                            f"这可能是因为OSS签名验证失败或URL已过期"
                        )
                        logger.error(error_msg)
                        raise MinerUAPIError(
                            error_msg,
                            error_code="UPLOAD_FORBIDDEN",
                            details={
                                "file_path": file_path,
                                "upload_url": upload_url,
                                "status": e.status,
                            },
                        ) from e
                    else:
                        raise

            logger.info("✅ 所有文件上传成功,等待处理完成(异步): batch_id=%s", batch_id)

        # 步骤3: 等待所有文件处理完成并获取结果
        return await self._await_batch_results(batch_id, file_paths)

    async def _await_batch_results(
        self,
        batch_id: str,
        file_paths: list[str],
        max_wait_time: int = 300,
        poll_interval: int = 5,
    ) -> dict[str, dict[str, Any]]:
        """
        异步等待批量任务完成并获取所有文件的解析结果

        Args:
            batch_id: 批量任务ID
            file_paths: 文件路径列表
            max_wait_time: 最大等待时间(秒)
            poll_interval: 轮询间隔(秒)

        Returns:
            字典,key为文件路径,value为解析结果数据
        """
        start_time = time.time()
        file_names = [Path(fp).name for fp in file_paths]
        results = {}

        logger.info(
            "⏳ 等待批量任务完成(异步): batch_id=%s, 文件数=%s",
            batch_id,
            len(file_paths),
        )

        while time.time() - start_time < max_wait_time:
            try:
                result = await self._aquery_batch_results(batch_id)
                data = result.get("data", {})
                extract_results = data.get("extract_result", [])

                if not extract_results:
                    logger.debug("未找到任务结果(异步): batch_id=%s", batch_id)
                    await asyncio.sleep(poll_interval)
                    continue

                # 检查所有文件的状态
                all_done = True
                for file_path, file_name in zip(file_paths, file_names, strict=False):
                    if file_path in results:
                        continue  # 已经完成

                    # 查找匹配的文件结果
                    file_result = None
                    for item in extract_results:
                        if item.get("file_name", "") == file_name:
                            file_result = item
                            break

                    if not file_result:
                        all_done = False
                        continue

                    state = file_result.get("state", "")

                    if state == "done":
                        # 文件处理完成,下载结果
                        full_zip_url = file_result.get("full_zip_url")
                        if full_zip_url:
                            logger.info("✅ 文件处理完成(异步): %s", file_name)
                            results[file_path] = (
                                await self._adownload_and_extract_result(
                                    full_zip_url, batch_id, file_name, file_path
                                )
                            )
                        else:
                            logger.warning("文件完成但无下载链接(异步): %s", file_name)
                            all_done = False
                    elif state == "failed":
                        err_msg = file_result.get("err_msg", "解析失败")
                        logger.error(
                            "❌ 文件处理失败(异步): %s, 错误: %s", file_name, err_msg
                        )
                        msg = f"任务解析失败: {file_name}, 错误: {err_msg}"
                        raise MinerUAPIError(
                            msg,
                            error_code="TASK_FAILED",
                            details={
                                "batch_id": batch_id,
                                "file_name": file_name,
                                "err_msg": err_msg,
                            },
                        )
                    else:
                        # 还在处理中
                        all_done = False
                        if "extract_progress" in file_result:
                            progress = file_result["extract_progress"]
                            extracted = progress.get("extracted_pages", 0)
                            total = progress.get("total_pages", 0)
                            logger.debug(
                                "文件处理中(异步): %s, 进度: %s/%s 页",
                                file_name,
                                extracted,
                                total,
                            )

                if all_done:
                    logger.info("✅ 所有文件处理完成(异步): batch_id=%s", batch_id)
                    return results

                await asyncio.sleep(poll_interval)

            except MinerUAPIError:
                raise
            except Exception as e:
                logger.warning("查询任务结果时出错(异步): %s, 继续重试...", e)
                await asyncio.sleep(poll_interval)
                continue

        # 超时
        incomplete_files = [fp for fp in file_paths if fp not in results]
        msg = f"等待批量任务完成超时(异步): batch_id={batch_id}, 未完成文件: {incomplete_files}"
        raise MinerUAPIError(
            msg,
            error_code="TASK_TIMEOUT",
            details={
                "batch_id": batch_id,
                "incomplete_files": incomplete_files,
                "max_wait_time": max_wait_time,
            },
        )

    def _wait_for_batch_results(
        self,
        batch_id: str,
        file_paths: list[str],
        data_id_to_path: dict[str, str] | None = None,
        max_wait_time: int = 300,
        poll_interval: int = 5,
    ) -> dict[str, dict[str, Any]]:
        """
        等待批量任务完成并获取所有文件的解析结果

        Args:
            batch_id: 批量任务ID
            file_paths: 文件路径列表
            data_id_to_path: data_id到文件路径的映射(可选)
            max_wait_time: 最大等待时间(秒)
            poll_interval: 轮询间隔(秒)

        Returns:
            字典,key为文件路径,value为解析结果数据
        """
        start_time = time.time()
        file_names = [Path(fp).name for fp in file_paths]
        results = {}

        logger.info(
            "⏳ 等待批量任务完成: batch_id=%s, 文件数=%s", batch_id, len(file_paths)
        )

        while time.time() - start_time < max_wait_time:
            try:
                result = self._query_batch_results(batch_id)
                data = result.get("data", {})
                extract_results = data.get("extract_result", [])

                if not extract_results:
                    logger.debug("未找到任务结果: batch_id=%s", batch_id)
                    time.sleep(poll_interval)
                    continue

                # 检查所有文件的状态
                all_done = True

                # 记录所有可用的结果,便于调试
                logger.debug(
                    "📋 当前查询结果中的文件: %s",
                    [item.get("file_name", "unknown") for item in extract_results],
                )
                logger.debug("📋 期望匹配的文件: %s", file_names)

                for file_path, file_name in zip(file_paths, file_names, strict=False):
                    if file_path in results:
                        continue  # 已经完成

                    # 查找匹配的文件结果
                    # 优先使用 data_id 匹配(更可靠),如果失败则尝试使用 file_name 匹配
                    file_result = None
                    file_hash = self._get_file_hash(file_path)

                    for item in extract_results:
                        item_file_name = item.get("file_name", "")
                        item_data_id = item.get("data_id", "")

                        # 优先使用 data_id 匹配(更可靠)
                        if data_id_to_path and item_data_id:
                            if (
                                item_data_id == file_hash
                                and data_id_to_path.get(item_data_id) == file_path
                            ):
                                file_result = item
                                logger.info(
                                    "✅ 通过data_id匹配: %s (data_id: %s...)",
                                    file_name,
                                    item_data_id[:8],
                                )
                                break

                        # 如果data_id匹配失败,尝试文件名匹配
                        if not file_result and item_file_name == file_name:
                            file_result = item
                            logger.info("✅ 通过文件名匹配: %s", file_name)
                            # 如果通过文件名匹配,记录data_id以便后续验证
                            if item_data_id:
                                logger.debug(
                                    "   匹配到的data_id: %s, 期望的data_id: %s",
                                    item_data_id,
                                    file_hash,
                                )
                            break

                    if not file_result:
                        all_done = False
                        # 记录详细信息,便于调试
                        available_files = [
                            (
                                item.get("file_name", "unknown"),
                                item.get("data_id", "no_id")[:8],
                            )
                            for item in extract_results
                        ]
                        logger.warning("⚠️ 未找到文件 %s 的结果", file_name)
                        logger.warning("   期望的data_id: %s", file_hash)
                        logger.warning("   可用文件: %s", available_files)
                        continue

                    state = file_result.get("state", "")

                    if state == "done":
                        # 文件处理完成,下载结果
                        full_zip_url = file_result.get("full_zip_url")
                        if full_zip_url:
                            logger.info("✅ 文件处理完成: %s", file_name)
                            results[file_path] = self._download_and_extract_result(
                                full_zip_url, batch_id, file_name, file_path
                            )
                        else:
                            logger.warning("文件完成但无下载链接: %s", file_name)
                            all_done = False
                    elif state == "failed":
                        err_msg = file_result.get("err_msg", "解析失败")
                        data_id = file_result.get("data_id", "unknown")
                        logger.error("❌ 文件处理失败: %s", file_name)
                        logger.error("   错误信息: %s", err_msg)
                        logger.error("   data_id: %s", data_id)
                        logger.error("   batch_id: %s", batch_id)
                        logger.error("   文件路径: %s", file_path)

                        # 记录完整的文件结果信息,便于调试
                        logger.debug("   完整结果: %s", file_result)

                        # 根据错误信息判断是否是文件本身的问题
                        if (
                            "retry limit reached" in err_msg.lower()
                            or "replace the file" in err_msg.lower()
                        ):
                            logger.error(
                                "   可能的原因: 文件格式不支持、文件损坏或服务端处理失败"
                            )
                            logger.error(
                                "   建议: 检查文件格式是否正确,文件是否损坏,或稍后重试"
                            )

                        msg = f"任务解析失败: {file_name}, 错误: {err_msg}"
                        raise MinerUAPIError(
                            msg,
                            error_code="TASK_FAILED",
                            details={
                                "batch_id": batch_id,
                                "file_name": file_name,
                                "file_path": file_path,
                                "data_id": data_id,
                                "err_msg": err_msg,
                                "file_result": file_result,
                            },
                        )
                    else:
                        # 还在处理中
                        all_done = False
                        if "extract_progress" in file_result:
                            progress = file_result["extract_progress"]
                            extracted = progress.get("extracted_pages", 0)
                            total = progress.get("total_pages", 0)
                            logger.debug(
                                f"文件处理中: {file_name}, 进度: {extracted}/{total} 页"
                            )

                if all_done:
                    logger.info("✅ 所有文件处理完成: batch_id=%s", batch_id)
                    return results

                time.sleep(poll_interval)

            except MinerUAPIError:
                raise
            except Exception as e:
                logger.warning("查询任务结果时出错: %s, 继续重试...", e)
                time.sleep(poll_interval)
                continue

        # 超时
        incomplete_files = [fp for fp in file_paths if fp not in results]
        msg = (
            f"等待批量任务完成超时: batch_id={batch_id}, 未完成文件: {incomplete_files}"
        )
        raise MinerUAPIError(
            msg,
            error_code="TASK_TIMEOUT",
            details={
                "batch_id": batch_id,
                "incomplete_files": incomplete_files,
                "max_wait_time": max_wait_time,
            },
        )

    def extract(self, file_path: str, file_format: str | None = None) -> list[Document]:
        """
        同步提取文档内容(单个文件,内部使用批量API)

        注意:即使是单个文件,也统一使用批量上传API处理,确保接口一致性.

        Args:
            file_path: 文件路径
            file_format: 文件格式(pdf或docx),如果为None则自动检测

        Returns:
            Document对象列表

        Raises:
            MinerUAdapterError: 提取失败时抛出
        """
        start_time = time.time()

        try:
            # 自动检测文件格式
            if file_format is None:
                suffix = Path(file_path).suffix.lower()
                if suffix == ".pdf":
                    file_format = "pdf"
                elif suffix == ".docx":
                    file_format = "docx"
                else:
                    error = MinerUFileError(
                        f"无法自动检测文件格式: {file_path}",
                        error_code="FORMAT_DETECTION_ERROR",
                        details={"file_path": file_path},
                    )
                    preprocessing_error_handler.log_mineru_error(error, file_path)
                    raise error

            # 获取文件信息
            file_path_obj = Path(file_path)
            file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)

            # 记录开始日志
            self.preprocessing_logger.log_mineru_start(
                file_path=file_path, file_format=file_format, file_size_mb=file_size_mb
            )

            # 标准化文件路径(与extract_batch保持一致,确保路径匹配)
            normalized_path = str(Path(file_path).absolute().resolve())

            # 使用批量API处理单个文件(将单个文件作为批量处理)
            batch_results = self.extract_batch([file_path], [file_format])

            # 使用标准化路径从结果中获取文档(因为extract_batch会标准化路径)
            documents = batch_results.get(normalized_path, [])

            # 如果使用标准化路径找不到,尝试使用原始路径(向后兼容)
            if not documents:
                documents = batch_results.get(file_path, [])

            if not documents:
                # 提供更详细的错误信息,包括可用的keys
                available_keys = list(batch_results.keys())
                error = MinerUAdapterError(
                    f"文件处理失败: {file_path}",
                    error_code="NO_RESULT_AVAILABLE",
                    details={
                        "file_path": file_path,
                        "normalized_path": normalized_path,
                        "available_keys": available_keys,
                        "batch_results_count": len(batch_results),
                    },
                )
                preprocessing_error_handler.log_mineru_error(error, file_path)
                raise error

            # 计算处理时间
            processing_time = time.time() - start_time

            # 提取文档信息用于日志记录
            pages_extracted = 0
            images_extracted = 0
            tables_extracted = 0
            output_path = ""

            if documents:
                metadata = documents[0].metadata
                pages_extracted = metadata.get("total_pages", 0)
                images_extracted = metadata.get("image_count", 0)
                tables_extracted = metadata.get("table_count", 0)
                output_path = metadata.get("extracted_dir", "")

            # 记录成功日志
            self.preprocessing_logger.log_mineru_success(
                file_path=file_path,
                batch_id="",  # 单个文件处理可能没有batch_id
                processing_time_seconds=processing_time,
                pages_extracted=pages_extracted,
                images_extracted=images_extracted,
                tables_extracted=tables_extracted,
                output_path=output_path,
            )

            return documents

        except Exception as e:
            # 映射错误并记录日志
            mapped_error = preprocessing_error_handler.map_mineru_error(
                e, file_path, api_endpoint=self.batch_urls_endpoint
            )
            preprocessing_error_handler.log_mineru_error(mapped_error, file_path)
            raise mapped_error from e

    async def aextract_batch(
        self, file_paths_or_dir: str | list[str], file_formats: list[str] | None = None
    ) -> dict[str, list[Document]]:
        """
        异步批量提取文档内容(一次性提交所有文件)

        Args:
            file_paths_or_dir: 文件路径列表,或目录路径(会自动收集目录下的所有PDF和DOCX文件)
            file_formats: 文件格式列表(pdf或docx),如果为None则自动检测

        Returns:
            字典,key为文件路径,value为Document对象列表

        Raises:
            MinerUAdapterError: 提取失败时抛出
        """
        # 如果是目录路径,自动收集所有PDF和DOCX文件
        if isinstance(file_paths_or_dir, str):
            dir_path = Path(file_paths_or_dir)
            if dir_path.is_dir():
                logger.info(f"📁 检测到目录路径,收集目录下的所有文件(异步): {dir_path}")
                file_paths = []
                for ext in [".pdf", ".docx"]:
                    # 收集所有匹配的文件
                    found_files = list(dir_path.glob(f"*{ext}"))
                    # 过滤:只保留常规文件,排除隐藏文件,临时文件等
                    for fp in found_files:
                        if fp.is_file():  # 确保是文件而不是目录
                            file_name = fp.name
                            # 排除隐藏文件(以.开头)和临时文件(以~结尾)
                            if not file_name.startswith(".") and not file_name.endswith(
                                "~"
                            ):
                                file_paths.append(fp)
                file_paths = [str(fp) for fp in file_paths]
                logger.info(
                    f"📋 找到 {len(file_paths)} 个文件: {[Path(fp).name for fp in file_paths]}"
                )
            else:
                file_paths = [file_paths_or_dir]
        else:
            file_paths = file_paths_or_dir

        if not file_paths:
            logger.warning("未找到需要处理的文件(异步)")
            return {}

        # 标准化文件路径
        file_paths = [str(Path(fp).absolute().resolve()) for fp in file_paths]

        # 自动检测文件格式
        if file_formats is None:
            file_formats = []
            for file_path in file_paths:
                suffix = Path(file_path).suffix.lower()
                if suffix == ".pdf":
                    file_formats.append("pdf")
                elif suffix == ".docx":
                    file_formats.append("docx")
                else:
                    msg = f"不支持的文件格式: {file_path}"
                    raise MinerUFileError(
                        msg,
                        error_code="UNSUPPORTED_FORMAT",
                        details={"file_path": file_path},
                    )

        # 先检查缓存,分离需要处理和已缓存的文件
        files_to_process = []
        formats_to_process = []
        cached_results = {}

        for file_path, file_format in zip(file_paths, file_formats, strict=False):
            cached_result = self._check_cached_result(file_path)
            if cached_result:
                logger.info("✅ 使用缓存结果,跳过上传(异步): %s", file_path)
                cached_results[file_path] = cached_result
            else:
                files_to_process.append(file_path)
                formats_to_process.append(file_format)

        # 批量提交需要处理的文件(如果有)
        batch_results = {}
        if files_to_process:
            logger.info(
                f"📦 需要处理 {len(files_to_process)} 个文件(异步)({len(cached_results)} 个使用缓存)"
            )
            batch_results = await self._acall_batch_api(
                files_to_process, formats_to_process
            )
        else:
            logger.info("✅ 所有文件都使用缓存,无需上传(异步)")

        # 合并缓存结果和批量处理结果
        all_results = {**cached_results, **batch_results}

        # 转换为Document格式
        results = {}
        for file_path, api_response in all_results.items():
            file_format = file_formats[file_paths.index(file_path)]
            results[file_path] = self._convert_to_documents(
                api_response, file_path, file_format
            )

        return results

    async def aextract(
        self, file_path: str, file_format: str | None = None
    ) -> list[Document]:
        """
        异步提取文档内容(单个文件,内部使用批量API)

        注意:即使是单个文件,也统一使用批量上传API处理,确保接口一致性.

        Args:
            file_path: 文件路径
            file_format: 文件格式(pdf或docx),如果为None则自动检测

        Returns:
            Document对象列表

        Raises:
            MinerUAdapterError: 提取失败时抛出
        """
        # 自动检测文件格式
        if file_format is None:
            suffix = Path(file_path).suffix.lower()
            if suffix == ".pdf":
                file_format = "pdf"
            elif suffix == ".docx":
                file_format = "docx"
            else:
                msg = f"无法自动检测文件格式: {file_path}"
                raise MinerUFileError(
                    msg,
                    error_code="FORMAT_DETECTION_ERROR",
                    details={"file_path": file_path},
                )

        # 标准化文件路径(与aextract_batch保持一致,确保路径匹配)
        normalized_path = str(Path(file_path).absolute().resolve())

        # 使用批量API处理单个文件(统一使用批量上传,即使是单个文件)
        batch_results = await self.aextract_batch([file_path], [file_format])

        # 使用标准化路径从结果中获取文档(因为aextract_batch会标准化路径)
        documents = batch_results.get(normalized_path, [])

        # 如果使用标准化路径找不到,尝试使用原始路径(向后兼容)
        if not documents:
            documents = batch_results.get(file_path, [])

        if not documents:
            # 提供更详细的错误信息,包括可用的keys
            available_keys = list(batch_results.keys())
            msg = f"文件处理失败(异步): {file_path}"
            raise MinerUAdapterError(
                msg,
                error_code="NO_RESULT_AVAILABLE",
                details={
                    "file_path": file_path,
                    "normalized_path": normalized_path,
                    "available_keys": available_keys,
                    "batch_results_count": len(batch_results),
                },
            )

        return documents

    def health_check(self) -> bool:
        """
        检查MinerU服务健康状态(同步)

        Returns:
            服务是否健康

        Raises:
            MinerUAPIError: 健康检查失败时抛出
        """
        try:
            response = requests.get(
                self.health_endpoint,
                headers=self.headers,
                timeout=10,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            logger.info("MinerU服务健康检查通过")
            return True
        except requests.exceptions.RequestException as e:
            logger.warning("MinerU服务健康检查失败: %s", e)
            return False

    async def ahealth_check(self) -> bool:
        """
        检查MinerU服务健康状态(异步)

        Returns:
            服务是否健康

        Raises:
            MinerUAPIError: 健康检查失败时抛出
        """
        try:
            # 创建SSL上下文(如果需要禁用SSL验证)
            ssl_context = None
            if not self.verify_ssl:
                import ssl

                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(
                ssl=ssl_context if not self.verify_ssl else True
            )
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    self.health_endpoint,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=ssl_context if not self.verify_ssl else True,
                ) as response:
                    response.raise_for_status()
                    logger.info("MinerU服务健康检查通过")
                    return True
        except (TimeoutError, aiohttp.ClientError) as e:
            logger.warning("MinerU服务健康检查失败: %s", e)
            return False
