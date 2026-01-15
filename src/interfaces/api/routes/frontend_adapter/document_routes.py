"""
文档处理API路由模块

提供文件上传和向量数据状态/生成相关接口:
- POST /api/upload: 上传文件
- POST /api/vector-data-generation: 触发向量数据生成
- GET /api/vector-data-generation/status: 获取向量数据生成状态

生成命令: speckit.refactor frontend_adapter
生成时间: 2026-01-10
来源: constitution.md P1,P2 规则拆分
"""

import glob
import hashlib
import json
import os
import time
import uuid
from datetime import UTC
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Depends, Query, UploadFile, status
from fastapi.responses import JSONResponse

from src.application.services.document_service import DocumentService
from src.interfaces.api.error_handlers import (
    create_error_response_from_exception,
    handle_errors,
)
from src.interfaces.api.schemas.frontend_adapter_schemas import (
    create_error_response,
    create_success_response,
)
from src.shared.config.settings import get_config
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger

from .core import get_document_service, get_source_adapter

# 获取日志器
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(tags=["文档处理"])


@router.post(
    "/upload",
    response_model=dict[str, Any],
    summary="上传文件",
    description="上传文档文件(前端适配接口)",
)
async def upload_file(
    file: UploadFile = File(..., description="要上传的文件"),
    document_service: DocumentService = Depends(get_document_service),
    outline_id: str | None = Query(None, description="关联的大纲ID(可选)，用于写入 outline_sources"),
) -> dict[str, Any]:
    """
    上传文件接口(前端适配)

    映射到:POST /api/v1/documents/upload

    完整流程:
    1. 保存文件到临时目录
    2. 调用文档服务进行格式识别和预处理
    3. 从数据库获取处理后的文档记录
    4. 转换为前端期望的响应格式

    Args:
        file: 上传的文件
        document_service: 文档服务
        outline_id: 关联的大纲ID(可选)

    Returns:
        统一响应格式:{ success: bool, data: { file: { filename, path, size } } }
    """
    file_path: Path | None = None
    lock_path: Path | None = None
    try:
        def _ensure_outline_uploaded_source(outline_id_val: str, document_id_val: str) -> None:
            """确保 outline_sources 中存在 uploaded_file 记录（用于 E2E 以及 RAG 关联）。"""
            from datetime import datetime

            try:
                source_adapter = get_source_adapter()
                existing = source_adapter.list(
                    filters={
                        "outline_id": outline_id_val,
                        "source_type": "uploaded_file",
                        "source_id": document_id_val,
                    },
                    limit=1,
                )
                if existing:
                    return
                now = datetime.now(UTC).isoformat()
                source_adapter.create(
                    {
                        "id": str(uuid.uuid4()),
                        "outline_id": outline_id_val,
                        "source_type": "uploaded_file",
                        "source_id": document_id_val,
                        "source_data": json.dumps(
                            {"document_id": document_id_val, "filename": stable_filename},
                            ensure_ascii=False,
                        ),
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                logger.info(
                    "已关联上传文件来源: outline_id=%s, document_id=%s",
                    outline_id_val,
                    document_id_val,
                )
            except Exception as e:
                logger.warning(
                    "关联上传文件来源失败(不影响上传): outline_id=%s, document_id=%s, err=%s",
                    outline_id_val,
                    document_id_val,
                    e,
                )

        config = get_config()

        # 验证文件大小
        max_file_size = config.document.max_upload_size
        file.file.seek(0, 2)  # 移动到文件末尾
        file_size = file.file.tell()
        file.file.seek(0)  # 重置文件指针

        if file_size > max_file_size:
            logger.warning("文件过大: %s (大小: %d, 限制: %d)", file.filename, file_size, max_file_size)
            return create_error_response(
                f"文件过大,最大允许 {max_file_size} 字节",
                f"文件大小: {file_size} 字节"
            )

        # 保存上传的文件到临时目录
        upload_dir = config.document.upload_temp_dir
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成稳定文件名(基于内容hash)，避免同一文件在 e2e/pytest 重跑时重复触发预处理和LLM调用
        file_extension = Path(file.filename).suffix if file.filename else ""
        content = await file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        stable_filename = f"{file_hash[:32]}{file_extension}"
        file_path = upload_dir / stable_filename

        # 保存文件
        try:
            if file_path.exists() and file_path.is_file() and file_path.stat().st_size == len(content):
                logger.info("检测到相同内容文件已存在，复用: %s", file_path)
            else:
                with file_path.open("wb") as f:
                    f.write(content)
                logger.info("文件保存成功: %s -> %s", file.filename, file_path)
        except Exception as e:
            logger.error("保存上传文件失败: %s", e, exc_info=True)
            return create_error_response("保存文件失败", str(e))

        # 使用固定的测试用户ID
        test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

        # 处理锁：同一内容文件在处理期间禁止重复触发预处理（解决连接中断/重复点击/pytest 重试导致的重复跑）
        lock_path = upload_dir / f"{stable_filename}.processing.lock"
        # 如果锁存在且很久没更新，认为是 stale（例如上次进程异常退出）
        if lock_path.exists():
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > 6 * 3600:  # 6h
                    logger.warning("检测到 stale processing lock，移除: %s (age=%.0fs)", lock_path, age)
                    lock_path.unlink(missing_ok=True)
            except Exception:
                # ignore
                pass

        lock_acquired = False
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(f"pid={os.getpid()}\nfilename={stable_filename}\n")
            lock_acquired = True
            logger.info("获取 processing lock: %s", lock_path)
        except FileExistsError:
            logger.info("processing lock 已存在，跳过重复处理: %s", lock_path)

        # 如果同一份内容已经有文档记录（处理中或已完成），直接复用记录，避免重复触发预处理/LLM调用
        try:
            existing_rows = document_service.document_repository.list(
                filters={"uploaded_by": str(test_user_id), "filename": stable_filename},
                limit=5,
                order_by="uploaded_at DESC",
            )
            if existing_rows:
                latest = existing_rows[0]
                existing_status = str(latest.get("status", "")).lower()
                # 如果已经在处理/已完成，直接返回；如果 lock 未获取到，也必须返回（避免并发重复处理）
                if (existing_status and existing_status != "failed") or (not lock_acquired):
                    logger.info(
                        "检测到文档记录已存在，跳过重复处理: filename=%s, status=%s, id=%s",
                        stable_filename,
                        existing_status,
                        latest.get("id"),
                    )
                    if outline_id and latest.get("id"):
                        _ensure_outline_uploaded_source(outline_id, str(latest.get("id")))
                    return create_success_response(
                        data={
                            "file": {
                                "id": str(latest.get("id")) if latest.get("id") else None,
                                "filename": latest.get("filename") or stable_filename,
                                "path": latest.get("file_path") or str(file_path),
                                "size": latest.get("file_size") or file_size,
                            }
                        }
                    )
        except Exception as e:
            # 防御性：复用查询失败不应阻断正常处理流程
            logger.warning("检查重复文档记录失败，将继续处理: %s", e)

        # 如果没有获取到 lock，说明其他请求正在处理；这里直接返回"已接收/处理中"，避免重复跑
        if not lock_acquired:
            # 关键兼容：并发场景下（已有其他请求在处理同一份内容），此分支会导致前端拿不到 document_id，
            # 从而无法写入 outline_sources，E2E 会在 verify_hybrid_retriever_available 处失败。
            # 这里尝试快速从数据库"捞"出刚刚创建/正在处理的文档记录并建立 outline->document 关联。
            doc_id: str | None = None
            try:
                rows = document_service.document_repository.list(
                    filters={"uploaded_by": str(test_user_id), "filename": stable_filename},
                    limit=1,
                    order_by="uploaded_at DESC",
                )
                if rows and rows[0].get("id"):
                    doc_id = str(rows[0].get("id"))
                    if outline_id:
                        _ensure_outline_uploaded_source(outline_id, doc_id)
            except Exception:
                # 不阻断返回
                doc_id = None
            return create_success_response(
                data={
                    "file": {
                        "id": doc_id,
                        "filename": stable_filename,
                        "path": str(file_path),
                        "size": file_size,
                    }
                }
            )

        # 调用文档服务进行完整的文档处理(同步处理)
        try:
            logger.info("开始处理文档: %s", file_path)
            documents = document_service.upload_and_process(
                file_path=str(file_path),
                uploaded_by=test_user_id,
                doc_format=None,  # 自动识别格式
            )
            logger.info("文档处理完成,生成 %d 个文档片段", len(documents))

            # 从数据库获取最新文档记录
            db_documents = document_service.list_documents(
                uploaded_by=test_user_id,
                limit=1,
            )
            if not db_documents:
                logger.error("文档处理完成但未找到文档记录")
                return create_error_response(
                    "文档处理完成但未找到文档记录",
                    "请检查数据库连接或文档服务配置"
                )

            # 获取最新的文档记录
            domain_doc = db_documents[-1]
            logger.info("获取文档记录: ID=%s, filename=%s, status=%s",
                       domain_doc.id, domain_doc.filename, domain_doc.status)
            if outline_id:
                _ensure_outline_uploaded_source(outline_id, str(domain_doc.id))

            # 自动创建知识库并构建索引（知识库创建是RAG功能的核心，必须成功）
            try:
                from src.application.services.knowledge_base_helper import (
                    create_knowledge_base_from_documents,
                )

                kb_id = create_knowledge_base_from_documents(
                    documents=documents,
                    document_id=domain_doc.id,
                    enable_vector=True,  # 启用向量索引，确保embedding被调用
                    enable_bm25=True,
                    enable_metadata=True,
                )

                if kb_id:
                    logger.info("知识库自动创建成功: kb_id=%s, document_id=%s", kb_id, domain_doc.id)
                else:
                    error_msg = f"知识库自动创建失败: document_id={domain_doc.id}。知识库创建返回None。"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            except Exception as kb_error:
                # 知识库创建失败是严重错误，需要向上抛出
                error_msg = f"知识库创建失败（影响RAG功能）: document_id={domain_doc.id}, 错误={kb_error}"
                logger.error(error_msg, exc_info=True)
                raise ValueError(error_msg) from kb_error

            # 转换为前端期望的响应格式
            return create_success_response(
                data={
                    "file": {
                        "id": str(domain_doc.id),
                        "filename": domain_doc.filename,
                        "path": domain_doc.file_path,
                        "size": domain_doc.file_size,
                    }
                }
            )

        except ProcessingError as e:
            # 预期错误：例如用户上传了不支持的文件格式。
            # 不需要打印完整 traceback；同时应返回 4xx，避免前端/调用方误判为成功(HTTP 200)。
            logger.warning("文档处理失败: %s", e)
            return JSONResponse(
                content=create_error_response("文档处理失败", str(e)),
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            )
        except Exception as e:
            logger.exception("调用文档服务异常: %s", e)
            return create_error_response(
                "文档处理异常",
                str(e)
            )

    except Exception as e:
        logger.exception("上传文件异常: %s", e)
        return create_error_response_from_exception(e)
    finally:
        # 释放 processing lock
        try:
            if lock_path and lock_path.exists():
                lock_path.unlink(missing_ok=True)
        except Exception:
            pass


@router.post(
    "/data-preprocessing",
    response_model=dict[str, Any],
    summary="数据预处理",
    description="执行完整的数据预处理流程：MinerU转换 → LLM广告清洗 → 图表转JSON，从data/source/uploads目录读取文件",
)
@handle_errors(operation_name="数据预处理", log_level="info")
async def trigger_data_preprocessing() -> dict[str, Any]:
    """
    数据预处理接口（前端适配）

    执行完整的数据预处理流程：
    1. 从 data/source/uploads 目录读取 PDF/DOCX 文件
    2. 调用 MinerU 进行 PDF 解析和 OCR
    3. 调用 LLM 广告清洗器去除广告、目录等非正文内容
    4. 调用图表转 JSON 识别并转换图表数据
    5. 生成 rag_media_manifest.json 媒体清单

    读取目录：data/source/uploads
    输出目录：data/cleaned/documents

    Returns:
        统一响应格式:
        {
            "success": bool,
            "data": {
                "source_files": int,        # 源文件数量
                "processed_count": int,     # 成功处理的文档数量
                "cleaned_count": int,       # 清洗成功的文档数量
                "chart_json_count": int,    # 生成的图表JSON数量
                "errors": list[str]         # 错误列表
            }
        }
    """
    import asyncio
    from src.infrastructure.preprocessing.preprocessor import DocumentPreprocessor
    from src.shared.config.llm_service import get_llm_service
    from src.shared.config.settings import get_config

    config = get_config()
    llm_service = get_llm_service()

    # 查找源文件
    source_dir = Path("data/source/uploads")
    if not source_dir.exists():
        return create_success_response(
            data={
                "source_files": 0,
                "processed_count": 0,
                "cleaned_count": 0,
                "chart_json_count": 0,
                "errors": ["源文件目录不存在: data/source/uploads"]
            }
        )

    # 查找所有 PDF 和 DOCX 文件
    source_files = []
    for ext in [".pdf", ".docx"]:
        source_files.extend(source_dir.glob(f"*{ext}"))
        source_files.extend(source_dir.glob(f"*{ext.upper()}"))

    # 去重
    source_files = list(set(source_files))

    if not source_files:
        return create_success_response(
            data={
                "source_files": 0,
                "processed_count": 0,
                "cleaned_count": 0,
                "chart_json_count": 0,
                "errors": ["未找到任何 PDF/DOCX 文件"]
            }
        )

    logger.info("找到 %d 个源文件待处理", len(source_files))

    # 初始化预处理器（启用清洗和图表转换）
    preprocessor = DocumentPreprocessor(
        config=config,
        llm_service=llm_service,
        cleaning_enabled=True,
        progress_tracking_enabled=True,
        output_dir="data/cleaned/documents",
        chart_conversion_enabled=True,
    )

    # 执行批量处理
    file_paths = [str(f) for f in source_files]
    documents = preprocessor.process_documents(file_paths)

    # 统计结果
    cleaned_count = sum(1 for doc in documents if doc.metadata.get("pipeline") == "llm_ad_cleaning")

    # 统计图表JSON文件数量
    chart_json_count = 0
    cleaned_dir = Path("data/cleaned/documents")
    if cleaned_dir.exists():
        chart_json_count = len(list(cleaned_dir.rglob("datajson/*.json")))

    return create_success_response(
        data={
            "source_files": len(source_files),
            "processed_count": len(documents),
            "cleaned_count": cleaned_count,
            "chart_json_count": chart_json_count,
            "errors": []
        }
    )
    """
    触发向量数据生成接口（前端适配）

    遍历 data/cleaned/documents 下所有 clean.md 文件，
    为每个文档创建知识库并构建向量索引。

    Returns:
        统一响应格式:
        {
            "success": bool,
            "data": {
                "processed_count": int,  # 处理的文档数量
                "indexed_count": int,    # 成功构建索引的数量
                "errors": list[str]      # 错误列表
            }
        }
    """
    from src.application.services.knowledge_base_helper import (
        create_knowledge_base_from_documents,
    )
    from src.interfaces.api.routes.frontend_adapter.core import get_document_service
    from src.infrastructure.parsing.loaders.preprocessed_document_reader import (
        PreprocessedDocumentReader,
    )

    processed_count = 0
    indexed_count = 0
    errors: list[str] = []

    # 查找所有清洗后的文档
    cleaned_dir = Path("data/cleaned/documents")
    if not cleaned_dir.exists():
        return create_success_response(
            data={
                "processed_count": 0,
                "indexed_count": 0,
                "errors": ["清洗后的文档目录不存在"]
            }
        )

    # 查找所有 clean.md 文件
    clean_md_files = list(cleaned_dir.rglob("clean.md"))
    logger.info("找到 %d 个清洗后的文档", len(clean_md_files))

    if not clean_md_files:
        return create_success_response(
            data={
                "processed_count": 0,
                "indexed_count": 0,
                "errors": ["未找到任何清洗后的文档"]
            }
        )

    document_service = get_document_service()

    def _normalize_name(s: str) -> str:
        import re

        t = (s or "").strip().lower()
        t = re.sub(r"\.(pdf|docx)$", "", t)
        # 去掉常见符号/空白，提升命中率
        t = re.sub(r"[\s·：:（）()【】\\[\\]，,。\\.\\-_]+", "", t)
        return t

    def _find_document_id(doc_filename: str, doc_dir_name: str) -> str | None:
        """从 documents 表里尽可能找到对应 document_id，用于生成稳定 kb_doc_xxx。

        说明：前端“向量数据库生成”批处理如果找不到 document_id，会生成随机 kb_xxx，
        后续 RAG 侧按 outline 反查 kb_doc_xxx 时会失配（表现为只用到某一个索引/来源异常）。
        """
        try:
            from src.infrastructure.storage.sqlite.connection import get_connection_manager

            cm = get_connection_manager()
            with cm.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, filename, file_path FROM documents")
                rows = cur.fetchall() or []
        except Exception:
            rows = []

        # 优先精确匹配
        for rid, fn, _fp in rows:
            if str(fn or "").strip() == str(doc_filename or "").strip():
                return str(rid)

        # 次优：stem 匹配（忽略扩展名）
        target = _normalize_name(doc_filename) or _normalize_name(doc_dir_name)
        if not target:
            return None

        best_id: str | None = None
        best_score = -1
        for rid, fn, fp in rows:
            cand = _normalize_name(str(fn or "")) or _normalize_name(str(fp or ""))
            if not cand:
                continue
            score = 0
            if cand == target:
                score = 100
            elif cand in target or target in cand:
                score = 60
            # doc_dir_name 兜底
            dd = _normalize_name(doc_dir_name)
            if dd and (dd in cand or cand in dd):
                score = max(score, 50)
            if score > best_score:
                best_score = score
                best_id = str(rid)

        return best_id

    def _looks_like_uuid(s: str) -> bool:
        import uuid as _uuid

        try:
            _uuid.UUID(str(s))
            return True
        except Exception:
            return False

    def _clean_doc_dir_name(name: str) -> str:
        import re

        s = (name or "").strip()
        if not s:
            return ""
        s = re.sub(r"_[0-9]{1,3}$", "", s)
        s = re.sub(r"_[0-9a-fA-F]{2}$", "", s)
        return s.strip(" _-")

    def _infer_pdf_filename_from_extracted_dir(extracted_dir_name: str) -> str:
        """
        从 '<uuid>_<pdf>.pdf_extracted' 推断 '<pdf>.pdf'。
        若不符合该结构，则回退为去掉 '.pdf_extracted' 后的字符串。
        """
        name = (extracted_dir_name or "").strip()
        if not name.endswith(".pdf_extracted"):
            return name
        base = name[: -len(".pdf_extracted")]  # e.g. "<uuid>_<pdf>.pdf"
        parts = base.split("_", 1)
        if len(parts) == 2 and _looks_like_uuid(parts[0]):
            return parts[1]
        return base

    for clean_md_path in clean_md_files:
        try:
            processed_count += 1
            logger.info("处理文档: %s", clean_md_path)

            # 尝试推断“原始 PDF 文件名”，用于：
            # 1) 匹配 documents 表（如果存在）
            # 2) 作为 RAG 引用展示用 filename（避免显示 clean.md）
            extracted_dir = clean_md_path.parent  # .../<pdf>_extracted
            doc_dir = extracted_dir.parent  # .../<文档目录>
            inferred_pdf_filename = _infer_pdf_filename_from_extracted_dir(extracted_dir.name)
            doc_filename = inferred_pdf_filename or (doc_dir.name + ".pdf")

            # 更稳健地找到 document_id（避免生成随机 kb_xxx 导致后续失配）
            document_id = _find_document_id(doc_filename, doc_dir.name)

            # 用预处理目录读取器加载（包含 images/ + datajson/ 元数据）
            reader = PreprocessedDocumentReader(
                source=str(extracted_dir),
                include_images=True,
                include_charts=True,
            )
            loaded_docs = reader.load()
            if not loaded_docs:
                raise ValueError(f"预处理目录读取失败: {extracted_dir}")

            # 兜底补齐展示字段（不覆盖 reader 已有信息）
            for d in loaded_docs:
                try:
                    d.metadata = dict(d.metadata or {})
                    d.metadata.setdefault("filename", doc_filename)
                    d.metadata.setdefault("source_title", _clean_doc_dir_name(doc_dir.name))
                    d.metadata.setdefault("file_path", str(clean_md_path))
                    d.metadata.setdefault("cleaned_doc_dir", str(doc_dir))
                    d.metadata.setdefault("cleaned_extracted_dir", str(extracted_dir))
                except Exception:
                    pass

            # 创建知识库并构建索引
            kb_id = None
            try:
                import uuid as _uuid

                kb_uuid = _uuid.UUID(str(document_id)) if document_id else None
                if kb_uuid:
                    kb_id = f"kb_doc_{kb_uuid.hex[:16]}"
            except Exception:
                kb_id = None

            kb_id = create_knowledge_base_from_documents(
                documents=loaded_docs,
                document_id=document_id,
                knowledge_base_id=kb_id,
                enable_vector=True,
                enable_bm25=True,
                enable_metadata=True,
            )

            if kb_id:
                indexed_count += 1
                logger.info("知识库创建成功: kb_id=%s", kb_id)
            else:
                errors.append(f"文档 {clean_md_path} 知识库创建返回None")

        except Exception as e:
            error_msg = f"处理文档 {clean_md_path} 失败: {e}"
            logger.error(error_msg)
            errors.append(str(e))

    result_data = {
        "processed_count": processed_count,
        "indexed_count": indexed_count,
        "errors": errors
    }

    logger.info("向量数据生成完成: processed=%d, indexed=%d, errors=%d",
                processed_count, indexed_count, len(errors))

    return create_success_response(data=result_data)


@router.get(
    "/data-preprocessing/status",
    response_model=dict[str, Any],
    summary="获取数据预处理状态",
    description="检查当前数据预处理的状态，包括文档清洗、索引和图表JSON状态",
)
@handle_errors(operation_name="获取数据预处理状态", log_level="info")
async def get_preprocessing_status() -> dict[str, Any]:
    """
    获取数据预处理状态接口（前端适配）

    检查当前数据预处理的状态，包括：
    - 清洗后文档数量
    - 向量索引状态
    - BM25索引状态
    - 图表JSON文件数量

    Returns:
        统一响应格式:
        {
            "success": bool,
            "data": {
                "cleaned_documents": int,
                "vector_index_available": bool,
                "bm25_index_available": bool,
                "chart_json_files": int,
                "status": str  # ready, partial, empty
            }
        }
    """
    status_data = {
        "cleaned_documents": 0,
        "vector_index_available": False,
        "bm25_index_available": False,
        "chart_json_files": 0,
        "status": "empty"
    }

    # 检查清洗后文档
    cleaned_dir = Path("data/cleaned/documents")
    if cleaned_dir.exists():
        clean_md_files = list(cleaned_dir.rglob("clean.md"))
        status_data["cleaned_documents"] = len(clean_md_files)

        # 检查图表JSON文件
        datajson_files = list(cleaned_dir.rglob("datajson/*.json"))
        status_data["chart_json_files"] = len(datajson_files)

    # 检查向量索引
    try:
        from src.infrastructure.storage.chroma.connection import get_chroma_connection_manager
        conn_manager = get_chroma_connection_manager()
        # 正确使用 list_collections 方法
        collections = conn_manager.list_collections()
        status_data["vector_index_available"] = len(collections) > 0
    except Exception as e:
        logger.warning(f"检查向量索引失败: {e}")

    # 检查BM25索引（检查任意 kb_*.json 文件）
    import glob
    bm25_json_files = glob.glob("./data/bm25_index/kb_*.json")
    status_data["bm25_index_available"] = len(bm25_json_files) > 0
    if bm25_json_files:
        logger.info("找到 %d 个BM25索引文件", len(bm25_json_files))

    # 判断整体状态
    if status_data["cleaned_documents"] > 0 and status_data["vector_index_available"]:
        status_data["status"] = "ready"
    elif status_data["cleaned_documents"] > 0 or status_data["vector_index_available"]:
        status_data["status"] = "partial"
    else:
        status_data["status"] = "empty"

    return create_success_response(data=status_data)


# 保留原有的向量数据生成接口（向后兼容）
@router.get(
    "/vector-data-generation/status",
    response_model=dict[str, Any],
    summary="获取向量数据生成状态（向后兼容）",
    deprecated=True,
)
async def get_vector_data_status_compat() -> dict[str, Any]:
    """向后兼容接口，调用 get_preprocessing_status"""
    return await get_preprocessing_status()


@router.post(
    "/data-preprocessing",
    response_model=dict[str, Any],
    summary="数据预处理",
    description="扫描 data/source/uploads 目录，对所有文件执行 MinerU OCR → LLM清洗 → 图转JSON",
)
@handle_errors(operation_name="数据预处理", log_level="info")
async def trigger_data_preprocessing() -> dict[str, Any]:
    """
    数据预处理接口

    完整流程：
    1. 扫描 data/source/uploads 目录下的所有文件
    2. 对每个文件调用 MinerU 进行 OCR 识别
    3. 对 data/processed/mineru 下的结果进行 LLM 清洗
    4. 执行图表转 JSON

    Returns:
        统一响应格式:
        {
            "success": bool,
            "data": {
                "source_files_count": int,     # 源文件数量
                "processed_count": int,        # 成功处理数量
                "failed_count": int,           # 失败数量
                "cleaned_count": int,          # 清洗后文档数量
                "chart_json_count": int,       # 图表JSON数量
                "steps": [
                    {"step_name": "pdf_parsing", "status": "completed", "progress": 100, "message": "..."},
                    {"step_name": "data_cleaning", "status": "completed", "progress": 100, "message": "..."},
                    {"step_name": "chart_conversion", "status": "completed", "progress": 100, "message": "..."},
                ],
                "errors": list[str]
            }
        }
    """
    from src.infrastructure.preprocessing.preprocessor import DocumentPreprocessor

    source_dir = Path("data/source/uploads")
    mineru_dir = Path("data/processed/mineru")
    cleaned_dir = Path("data/cleaned/documents")

    steps = []
    errors = []
    source_files_count = 0
    processed_count = 0
    failed_count = 0
    cleaned_count = 0
    chart_json_count = 0

    # 步骤1: 扫描源文件并调用 MinerU
    step1_progress = 0
    if source_dir.exists():
        source_files = list(source_dir.glob("*.pdf")) + list(source_dir.glob("*.docx"))
        source_files_count = len(source_files)
        logger.info(f"找到 {source_files_count} 个源文件")

        if source_files_count > 0:
            try:
                preprocessor = DocumentPreprocessor(
                    cleaning_enabled=True,
                    chart_conversion_enabled=True,
                )

                # 对每个源文件调用 MinerU
                for i, file_path in enumerate(source_files):
                    try:
                        logger.info(f"MinerU 处理 {i+1}/{source_files_count}: {file_path}")
                        docs = preprocessor.process_document(str(file_path))
                        if docs:
                            processed_count += 1
                            logger.info(f"MinerU 处理成功: {file_path}")
                        else:
                            failed_count += 1
                            errors.append(f"MinerU 返回空结果: {file_path}")
                    except Exception as e:
                        failed_count += 1
                        error_msg = f"MinerU 处理失败: {file_path}, 错误: {e}"
                        logger.error(error_msg)
                        errors.append(str(e))

                step1_progress = 100 if source_files_count > 0 else 0
                steps.append({
                    "step_name": "pdf_parsing",
                    "status": "completed" if failed_count == 0 else "partial",
                    "progress": step1_progress,
                    "message": f"MinerU 处理完成: 成功 {processed_count}, 失败 {failed_count}"
                })
            except Exception as e:
                error_msg = f"初始化预处理失败: {e}"
                logger.error(error_msg)
                errors.append(str(e))
                steps.append({
                    "step_name": "pdf_parsing",
                    "status": "failed",
                    "progress": step1_progress,
                    "message": error_msg
                })
        else:
            steps.append({
                "step_name": "pdf_parsing",
                "status": "completed",
                "progress": 100,
                "message": "源目录为空，无需处理"
            })
    else:
        steps.append({
            "step_name": "pdf_parsing",
            "status": "failed",
            "progress": 0,
            "message": f"源目录不存在: {source_dir}"
        })
        errors.append(f"源目录不存在: {source_dir}")

    # 步骤2: LLM 清洗
    step2_progress = 0
    try:
        if mineru_dir.exists():
            preprocessor = DocumentPreprocessor(
                cleaning_enabled=True,
                chart_conversion_enabled=False,  # 步骤3单独处理图转JSON
            )
            cleaned_docs = preprocessor.process_mineru_directory(str(mineru_dir))
            cleaned_count = len(cleaned_docs)
            step2_progress = 100
            logger.info(f"LLM 清洗完成: {cleaned_count} 个文档")
            steps.append({
                "step_name": "data_cleaning",
                "status": "completed",
                "progress": step2_progress,
                "message": f"LLM 清洗完成: {cleaned_count} 个文档"
            })
        else:
            steps.append({
                "step_name": "data_cleaning",
                "status": "completed",
                "progress": 100,
                "message": f"MinerU 目录不存在: {mineru_dir}"
            })
    except Exception as e:
        error_msg = f"LLM 清洗失败: {e}"
        logger.error(error_msg)
        errors.append(str(e))
        steps.append({
            "step_name": "data_cleaning",
            "status": "failed",
            "progress": step2_progress,
            "message": error_msg
        })

    # 步骤3: 图表转 JSON
    step3_progress = 0
    try:
        if cleaned_dir.exists():
            # 查找所有包含 images 目录的清洗后文档
            chart_json_dirs = []
            for cleaned_doc_dir in cleaned_dir.iterdir():
                if cleaned_doc_dir.is_dir():
                    for extracted_dir in cleaned_doc_dir.iterdir():
                        if extracted_dir.is_dir() and (extracted_dir / "images").exists():
                            chart_json_dirs.append(extracted_dir)

            if chart_json_dirs:
                from src.infrastructure.preprocessing.cleaners.llm_chart_to_json_converter import (
                    LLMChartToJsonConverter,
                )

                chart_converter = LLMChartToJsonConverter()

                for chart_dir in chart_json_dirs:
                    try:
                        result = chart_converter.process_mineru_directory(
                            str(chart_dir), create_datajson_dir=True
                        )
                        stats = result.get("overall_statistics", {})
                        chart_json_count += stats.get("total_json_files_generated", 0)
                    except Exception as e:
                        logger.warning(f"图表转JSON失败: {chart_dir}, 错误: {e}")

            step3_progress = 100
            steps.append({
                "step_name": "chart_conversion",
                "status": "completed",
                "progress": step3_progress,
                "message": f"图表转JSON完成: {chart_json_count} 个JSON文件"
            })
        else:
            steps.append({
                "step_name": "chart_conversion",
                "status": "completed",
                "progress": 100,
                "message": "清洗目录不存在，跳过图表转换"
            })
    except Exception as e:
        error_msg = f"图表转JSON失败: {e}"
        logger.error(error_msg)
        errors.append(str(e))
        steps.append({
            "step_name": "chart_conversion",
            "status": "failed",
            "progress": step3_progress,
            "message": error_msg
        })

    result_data = {
        "source_files_count": source_files_count,
        "processed_count": processed_count,
        "failed_count": failed_count,
        "cleaned_count": cleaned_count,
        "chart_json_count": chart_json_count,
        "steps": steps,
        "errors": errors
    }

    success = failed_count == 0 and len(errors) == 0
    logger.info(f"数据预处理完成: success={success}, {result_data}")

    if success:
        return create_success_response(data=result_data)
    else:
        return create_success_response(data=result_data)


__all__ = ["router"]
