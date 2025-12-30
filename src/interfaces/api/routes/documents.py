"""
文档上传和预处理API路由

实现文档上传,预处理,查询等API接口.
使用T035定义的Schema,调用T033文档服务.

生成命令: /speckit.implement T034
生成时间: 2025-12-17
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import contextlib
import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from src.application.services.document_service import DocumentService
from src.domain.document.document import DocumentFormat, DocumentStatus
from src.interfaces.api.schemas.document_schemas import (
    BatchDocumentProcessRequest,
    BatchDocumentProcessResponse,
    DocumentDeleteResponse,
    DocumentListResponse,
    DocumentProcessRequest,
    DocumentProcessResponse,
    DocumentQueryRequestValidator,
    DocumentResponse,
    DocumentUploadRequestValidator,
    DocumentUploadResponse,
    DocumentValidationResponse,
    ErrorResponse,
    ProcessingProgressResponse,
    ProcessingStatistics,
    ProcessingStatus,
)
from src.shared.config.settings import get_config
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger

# 获取配置和日志器
config = get_config()
logger = get_logger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/documents", tags=["文档"])


# 依赖注入:获取文档服务实例
def get_document_service() -> DocumentService:
    """获取文档服务实例"""
    return DocumentService()


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        413: {"model": ErrorResponse, "description": "文件过大"},
        422: {"model": ErrorResponse, "description": "文档格式不支持"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="上传文档",
    description="上传文档文件并创建文档记录,支持PDF,DOCX等格式",
)
async def upload_document(
    file: UploadFile = File(..., description="要上传的文档文件"),
    file_format: str | None = Form(
        None, description="文档格式(可选, 如果不指定则自动识别)"
    ),
    enable_chart_conversion: bool = Form(
        default=True, description="是否启用图表转换功能"
    ),
    cleaning_level: str = Form("standard", description="清洗级别"),
    use_async: bool = Form(default=False, description="是否使用异步处理"),
    metadata: str | None = Form(None, description="附加元数据(JSON格式)"),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentUploadResponse:
    """
    上传文档接口

    Args:
        file: 上传的文件
        file_format: 文档格式(可选)
        enable_chart_conversion: 是否启用图表转换
        cleaning_level: 清洗级别
        use_async: 是否使用异步处理
        metadata: 附加元数据
        document_service: 文档服务实例

    Returns:
        DocumentUploadResponse: 上传结果

    Raises:
        HTTPException: 上传失败时抛出
    """
    try:
        # 验证文件大小
        max_file_size = config.document.max_upload_size
        file.file.seek(0, 2)  # 移动到文件末尾
        file_size = file.file.tell()
        file.file.seek(0)  # 重置文件指针

        if file_size > max_file_size:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件过大,最大允许 {max_file_size} 字节",
            )

        # 解析元数据
        custom_metadata = {}
        if metadata:
            import json

            try:
                custom_metadata = json.loads(metadata)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="元数据格式错误,应为有效的JSON字符串",
                ) from e

        # 验证请求参数
        upload_request = DocumentUploadRequestValidator(
            format=file_format,
            enable_chart_conversion=enable_chart_conversion,
            cleaning_level=cleaning_level,
            use_async=use_async,
            metadata=custom_metadata,
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
                # 复用已存在文件，避免改变mtime导致MinerU缓存失效
                logger.info("检测到相同内容文件已存在，复用: %s", file_path)
            else:
                with file_path.open("wb") as f:
                    f.write(content)
        except Exception as e:
            logger.error("保存上传文件失败: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存文件失败",
            ) from e

        logger.info("文件上传成功: %s -> %s (sha256=%s)", file.filename, file_path, file_hash[:12])

        # 处理文档
        try:
            # 使用固定的测试用户ID,避免FOREIGN KEY约束失败
            # 在实际应用中,这里应该从认证信息获取真实的用户ID
            test_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

            if use_async:
                # 异步处理
                result = await document_service.upload_and_process_async(
                    file_path=str(file_path),
                    uploaded_by=test_user_id,
                    format=upload_request.format,
                    enable_chart_conversion=upload_request.enable_chart_conversion,
                )

                # 从数据库查询最新的文档记录(按上传时间倒序取一条)
                documents = document_service.list_documents(
                    uploaded_by=test_user_id,
                    limit=1,
                )
                if not documents:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="文档上传成功但未找到文档记录",
                    )

                domain_doc = documents[-1]
                document_response = DocumentResponse(
                    id=domain_doc.id,
                    filename=domain_doc.filename,
                    file_path=domain_doc.file_path,
                    # 兼容领域层枚举大小写差异：交给 Schema validator 统一归一化
                    status=domain_doc.status,
                    format=domain_doc.format,
                    uploaded_by=domain_doc.uploaded_by,
                    metadata={
                        "file_size": domain_doc.file_size,
                        "mime_type": domain_doc.mime_type or "",
                        "format_info": domain_doc.metadata.get("format_info"),
                        "uploaded_at": domain_doc.uploaded_at,
                        "parsed_at": domain_doc.parsed_at,
                        "processing_duration": None,
                        "error_message": domain_doc.error_message,
                        "quality_score": None,
                        "custom_metadata": domain_doc.metadata,
                    },
                )

                # 返回上传响应(异步处理)
                return DocumentUploadResponse(
                    document=document_response,
                    processing_task_id=result.get("task_id"),
                    message="文档上传成功,正在异步处理中",
                )

            # 同步处理
            documents = document_service.upload_and_process(
                file_path=str(file_path),
                uploaded_by=test_user_id,
                format=upload_request.format,
            )

            # 同步处理完成后从数据库获取最新文档记录
            db_documents = document_service.list_documents(
                uploaded_by=test_user_id,
                limit=1,
            )
            if not db_documents:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="文档上传并处理完成但未找到文档记录",
                )

            domain_doc = db_documents[-1]
            document_response = DocumentResponse(
                id=domain_doc.id,
                filename=domain_doc.filename,
                file_path=domain_doc.file_path,
                status=domain_doc.status,
                format=domain_doc.format,
                uploaded_by=domain_doc.uploaded_by,
                metadata={
                    "file_size": domain_doc.file_size,
                    "mime_type": domain_doc.mime_type or "",
                    "format_info": domain_doc.metadata.get("format_info"),
                    "uploaded_at": domain_doc.uploaded_at,
                    "parsed_at": domain_doc.parsed_at,
                    "processing_duration": None,
                    "error_message": domain_doc.error_message,
                    "quality_score": None,
                    "custom_metadata": domain_doc.metadata,
                },
            )

            return DocumentUploadResponse(
                document=document_response,
                processing_task_id=None,
                message="文档上传并处理完成",
            )

        except ProcessingError as e:
            logger.error("文档处理失败: %s", e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("上传文档异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="上传文档失败",
        ) from e


@router.post(
    "/process",
    response_model=DocumentProcessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        404: {"model": ErrorResponse, "description": "文档不存在"},
        422: {"model": ErrorResponse, "description": "文档处理失败"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="处理文档",
    description="对已上传的文档进行预处理,包括格式识别,内容清洗等",
)
async def process_document(
    request: DocumentProcessRequest,
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentProcessResponse:
    """
    处理文档接口

    Args:
        request: 文档处理请求
        document_service: 文档服务实例

    Returns:
        DocumentProcessResponse: 处理结果

    Raises:
        HTTPException: 处理失败时抛出
    """
    try:
        # 获取文档
        document = document_service.get_document(request.document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在",
            )

        def _to_format_str(v: object) -> str:
            """兼容 Enum/字符串，统一返回小写格式字符串（供服务层使用）"""
            try:
                from enum import Enum

                if isinstance(v, Enum):
                    return str(v.value).lower()
            except Exception:
                pass
            return str(v).lower()

        # 处理文档
        try:
            if request.use_async:
                # 异步处理
                result = await document_service.upload_and_process_async(
                    file_path=document.file_path,
                    uploaded_by=document.uploaded_by,
                    format=_to_format_str(document.format),
                    enable_chart_conversion=request.enable_chart_conversion,
                )

                return DocumentProcessResponse(
                    document=document,
                    processing_result=result,
                    processing_task_id=result.get("task_id"),
                    message="文档处理已开始",
                )
            else:
                # 同步处理
                documents = document_service.upload_and_process(
                    file_path=document.file_path,
                    uploaded_by=document.uploaded_by,
                    format=_to_format_str(document.format),
                )

                return DocumentProcessResponse(
                    document=document,
                    processing_result={"processed_documents": len(documents)},
                    processing_task_id=None,
                    message="文档处理完成",
                )

        except ProcessingError as e:
            logger.error("文档处理失败: %s", e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("处理文档异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理文档失败",
        ) from e


@router.post(
    "/process/batch",
    response_model=BatchDocumentProcessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="批量处理文档",
    description="批量处理多个文档,支持异步处理",
)
async def process_documents_batch(
    request: BatchDocumentProcessRequest,
    document_service: DocumentService = Depends(get_document_service),
) -> BatchDocumentProcessResponse:
    """
    批量处理文档接口

    Args:
        request: 批量处理请求
        document_service: 文档服务实例

    Returns:
        BatchDocumentProcessResponse: 批量处理结果

    Raises:
        HTTPException: 处理失败时抛出
    """
    try:
        # 获取文档列表
        documents = []
        for doc_id in request.document_ids:
            doc = document_service.get_document(doc_id)
            if doc:
                documents.append(doc)

        if not documents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有找到有效的文档",
            )

        # 批量处理文档
        try:
            file_paths = [doc.file_path for doc in documents]
            result = await document_service.upload_and_process_batch_async(
                file_paths=file_paths,
                uploaded_by=documents[0].uploaded_by,  # 使用第一个文档的上传者
                batch_size=request.batch_size,
                enable_chart_conversion=request.enable_chart_conversion,
            )

            processed_files = set(result.get("processed_files", []))
            failed_files = set(result.get("failed_files", []))

            # 构建每个文档的处理结果
            process_results: list[DocumentProcessResponse] = []
            for doc in documents:
                if doc.file_path in processed_files:
                    status_label = "success"
                elif doc.file_path in failed_files:
                    status_label = "failed"
                else:
                    status_label = "unknown"

                process_results.append(
                    DocumentProcessResponse(
                        document=doc,
                        processing_result={"status": status_label},
                        processing_task_id=None,
                        message=(
                            "文档处理完成"
                            if status_label == "success"
                            else "文档处理失败"
                        ),
                    )
                )

            total_docs = len(documents)
            successful = len(processed_files)
            failed = len(failed_files)

            statistics = ProcessingStatistics(
                total_documents=total_docs,
                successful_documents=successful,
                failed_documents=failed,
                total_processing_time=float(result.get("processing_time", 0.0)),
                average_processing_time=(
                    float(result.get("processing_time", 0.0)) / total_docs
                    if total_docs > 0
                    else 0.0
                ),
                charts_converted=None,
            )

            # 构建响应
            return BatchDocumentProcessResponse(
                task_id=result.get("task_id", str(uuid.uuid4())),
                statistics=statistics,
                results=process_results,
                message="批量文档处理完成",
            )

        except ProcessingError as e:
            logger.error("批量处理文档失败: %s", e)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from e

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("批量处理文档异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="批量处理文档失败",
        ) from e


@router.get(
    "",
    response_model=DocumentListResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="查询文档列表",
    description="根据条件查询文档列表,支持分页和筛选",
)
async def list_documents(
    status: DocumentStatus | None = Query(None, description="文档状态过滤"),
    file_format: DocumentFormat | None = Query(
        None, description="文档格式过滤"
    ),
    uploaded_by: uuid.UUID | None = Query(None, description="上传用户ID过滤"),
    start_date: datetime | None = Query(None, description="开始日期过滤"),
    end_date: datetime | None = Query(None, description="结束日期过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    search: str | None = Query(
        None, min_length=1, max_length=100, description="搜索关键词"
    ),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentListResponse:
    """
    查询文档列表接口

    Args:
        status: 文档状态过滤
        file_format: 文档格式过滤
        uploaded_by: 上传用户ID过滤
        start_date: 开始日期过滤
        end_date: 结束日期过滤
        limit: 返回数量限制
        offset: 偏移量
        search: 搜索关键词
        document_service: 文档服务实例

    Returns:
        DocumentListResponse: 文档列表响应

    Raises:
        HTTPException: 查询失败时抛出
    """
    try:
        # 验证请求参数
        query_request = DocumentQueryRequestValidator(
            status=status,
            format=file_format,
            uploaded_by=uploaded_by,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
            search=search,
        )

        # 查询文档列表
        documents = document_service.list_documents(
            uploaded_by=query_request.uploaded_by,
            status=query_request.status,
            limit=query_request.limit,
        )

        # 转换为响应格式
        document_responses: list[DocumentResponse] = []
        for doc in documents:
            metadata = {
                "file_size": doc.file_size,
                "mime_type": doc.mime_type or "",
                "format_info": doc.metadata.get("format_info"),
                "uploaded_at": doc.uploaded_at,
                "parsed_at": doc.parsed_at,
                "processing_duration": None,
                "error_message": doc.error_message,
                "quality_score": None,
                "custom_metadata": doc.metadata,
            }
            document_responses.append(
                DocumentResponse(
                    id=doc.id,
                    filename=doc.filename,
                    file_path=doc.file_path,
                    status=doc.status,
                    format=doc.format,
                    uploaded_by=doc.uploaded_by,
                    metadata=metadata,
                )
            )

        # 返回响应
        return DocumentListResponse(
            documents=document_responses,
            total=len(documents),
            limit=query_request.limit,
            offset=query_request.offset,
            has_more=len(documents) >= query_request.limit,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("查询文档列表异常: %s", e)
        raise HTTPException(
            status_code=500,
            detail="查询文档列表失败",
        ) from e


@router.get(
    "/{document_id}",
    response_model=dict,
    responses={
        404: {"model": ErrorResponse, "description": "文档不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="获取文档详情",
    description="根据文档ID获取文档详细信息",
)
async def get_document(
    document_id: uuid.UUID,
    document_service: DocumentService = Depends(get_document_service),
) -> dict:
    """
    获取文档详情接口

    Args:
        document_id: 文档ID
        document_service: 文档服务实例

    Returns:
        dict: 文档详情

    Raises:
        HTTPException: 获取失败时抛出
    """
    try:
        # 获取文档
        document = document_service.get_document(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在",
            )

        # 返回文档详情
        def _to_lower_str(v: object) -> str:
            """兼容 Enum/字符串，统一返回小写字符串。"""
            try:
                # Enum
                from enum import Enum

                if isinstance(v, Enum):
                    return str(v.value).lower()
            except Exception:
                pass
            return str(v).lower()

        return {
            "id": str(document.id),
            "filename": document.filename,
            "file_path": document.file_path,
            "file_size": document.file_size,
            "mime_type": document.mime_type,
            # 领域层可能因为 use_enum_values=True 返回字符串（如 'PDF'/'PARSING'）
            "format": _to_lower_str(document.format),
            "status": _to_lower_str(document.status),
            "uploaded_by": str(document.uploaded_by),
            "uploaded_at": document.uploaded_at.isoformat(),
            "metadata": document.metadata,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取文档详情异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取文档详情失败",
        ) from e


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    responses={
        404: {"model": ErrorResponse, "description": "文档不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="删除文档",
    description="根据文档ID删除文档及其相关数据",
)
async def delete_document(
    document_id: uuid.UUID,
    force: bool = Query(default=False, description="是否强制删除(包括处理结果)"),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentDeleteResponse:
    """
    删除文档接口

    Args:
        document_id: 文档ID
        force: 是否强制删除
        document_service: 文档服务实例

    Returns:
        DocumentDeleteResponse: 删除结果

    Raises:
        HTTPException: 删除失败时抛出
    """
    try:
        # 获取文档
        document = document_service.get_document(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在",
            )

        # 删除文档
        try:
            # 删除数据库记录
            deleted = document_service.document_repository.delete(str(document_id))

            # 删除文件系统中的文件(忽略失败)
            try:
                Path(document.file_path).unlink(missing_ok=True)
            except Exception:
                logger.warning("删除文档文件失败,但不影响接口返回", exc_info=True)

            success = bool(deleted)
            message = "文档删除成功" if success else "文档记录不存在或已删除"

            return DocumentDeleteResponse(
                document_id=document_id,
                success=success,
                message=message,
            )

        except Exception as e:
            logger.exception("删除文档失败: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="删除文档失败",
            ) from e

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除文档异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="删除文档失败",
        ) from e


@router.get(
    "/{document_id}/progress",
    response_model=ProcessingProgressResponse,
    responses={
        404: {"model": ErrorResponse, "description": "文档或任务不存在"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="查询处理进度",
    description="查询文档处理任务的进度信息",
)
async def get_processing_progress(
    document_id: uuid.UUID,
    task_id: str | None = Query(None, description="任务ID"),
    document_service: DocumentService = Depends(get_document_service),
) -> ProcessingProgressResponse:
    """
    查询处理进度接口

    Args:
        document_id: 文档ID
        task_id: 任务ID
        document_service: 文档服务实例

    Returns:
        ProcessingProgressResponse: 处理进度

    Raises:
        HTTPException: 查询失败时抛出
    """
    try:
        # 获取文档
        document = document_service.get_document(document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文档不存在",
            )

        # 根据文档状态返回粗略进度信息
        if document.status == DocumentStatus.INDEXED:
            progress = 1.0
            status_value = ProcessingStatus.COMPLETED
            current_step = "处理完成"
        elif document.status == DocumentStatus.PARSING:
            progress = 0.5
            status_value = ProcessingStatus.PROCESSING
            current_step = "处理中"
        elif document.status == DocumentStatus.FAILED:
            progress = 1.0
            status_value = ProcessingStatus.FAILED
            current_step = "处理失败"
        else:
            progress = 0.0
            status_value = ProcessingStatus.PENDING
            current_step = "待处理"

        return ProcessingProgressResponse(
            task_id=task_id or str(uuid.uuid4()),
            status=status_value,
            progress=progress,
            current_step=current_step,
            estimated_remaining_time=None,
            error_message=document.error_message,
            result={"status": document.status},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("查询处理进度异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="查询处理进度失败",
        ) from e


@router.post(
    "/validate",
    response_model=DocumentValidationResponse,
    responses={
        400: {"model": ErrorResponse, "description": "请求参数错误"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"},
    },
    summary="验证文档",
    description="验证文档格式和完整性",
)
async def validate_document(
    file: UploadFile = File(..., description="要验证的文档文件"),
    document_service: DocumentService = Depends(get_document_service),
) -> DocumentValidationResponse:
    """
    验证文档接口

    Args:
        file: 上传的文件
        document_service: 文档服务实例

    Returns:
        DocumentValidationResponse: 验证结果

    Raises:
        HTTPException: 验证失败时抛出
    """
    try:
        # 保存上传的文件到临时目录
        upload_dir = config.document.upload_temp_dir
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        file_extension = Path(file.filename).suffix if file.filename else ""
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = upload_dir / unique_filename

        # 保存文件
        try:
            with file_path.open("wb") as f:
                content = await file.read()
                f.write(content)
        except Exception as e:
            logger.error("保存验证文件失败: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="保存文件失败",
            ) from e

        # 验证文档
        try:
            # 检测格式
            format_info = document_service.detect_format(str(file_path))

            # 验证文档
            try:
                is_valid = document_service.validate_document(str(file_path))
            except Exception:
                # 如果验证失败,仍然返回格式信息,但标记为无效
                is_valid = False

            return DocumentValidationResponse(
                is_valid=is_valid,
                errors=[] if is_valid else ["文档格式验证失败"],
                warnings=[],
                format_info={
                    "format": format_info.format,
                    "mime_type": format_info.mime_type or "",
                    "extension": format_info.extension,
                    "confidence": format_info.confidence,
                },
            )

        except ProcessingError as e:
            logger.error("文档验证失败: %s", e)
            return DocumentValidationResponse(
                is_valid=False,
                errors=[str(e)],
                warnings=[],
                format_info=None,
            )
        finally:
            # 清理临时文件
            with contextlib.suppress(Exception):
                file_path.unlink()

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("验证文档异常: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="验证文档失败",
        ) from e
