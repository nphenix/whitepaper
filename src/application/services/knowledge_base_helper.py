"""
知识库创建辅助函数

提供文档上传后自动创建知识库的功能。
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

# 类型检查导入
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.application.services.knowledge_base_service import KnowledgeBaseService

from src.application.services.indexing_progress_service import get_progress_service
from src.application.services.knowledge_base_service import KnowledgeBaseService
from src.domain.document.document import Document, DocumentFormat
from src.shared.utils.logging import get_logger

# 索引构建器导入（可选依赖）
try:
    from src.infrastructure.indexing.bm25_index import BM25IndexBuilder
    from src.infrastructure.indexing.metadata_index import MetadataIndexBuilder
    from src.infrastructure.indexing.vector_index import VectorIndexBuilder
    from src.infrastructure.storage.chroma.connection import get_connection_manager as get_chroma_connection_manager
    from src.infrastructure.storage.sqlite.connection import get_connection_manager as get_sqlite_connection_manager
    INDEX_BUILDERS_AVAILABLE = True
except ImportError:
    INDEX_BUILDERS_AVAILABLE = False
    BM25IndexBuilder = None  # type: ignore[assignment, misc]
    MetadataIndexBuilder = None  # type: ignore[assignment, misc]
    VectorIndexBuilder = None  # type: ignore[assignment, misc]
    get_chroma_connection_manager = None  # type: ignore[assignment, misc]
    get_sqlite_connection_manager = None  # type: ignore[assignment, misc]

logger = get_logger(__name__)


def create_knowledge_base_from_documents(
    documents: list[Document],
    document_id: str | uuid.UUID | None = None,
    knowledge_base_id: str | None = None,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    enable_vector: bool = True,
    enable_bm25: bool = True,
    enable_metadata: bool = True,
    return_service: bool = False,
) -> str | None | tuple["KnowledgeBaseService", dict[str, Any]]:
    """
    从预处理后的文档自动创建知识库并构建向量索引

    此函数用于文档上传后自动创建知识库，确保文档可以立即用于检索。
    如果创建失败，不会抛出异常，而是记录错误并返回 None。

    Args:
        documents: 预处理后的 LangChain Document 对象列表
        document_id: 文档ID，用于生成知识库ID（可选，如果提供了knowledge_base_id则忽略）
        knowledge_base_id: 知识库ID（可选，如果提供则直接使用，否则根据document_id生成）
        chunk_size: 文档分块大小，默认 1000
        chunk_overlap: 文档分块重叠大小，默认 200
        enable_vector: 是否启用向量索引，默认 True
        enable_bm25: 是否启用BM25索引，默认 True
        enable_metadata: 是否启用元数据索引，默认 True
        return_service: 是否返回服务实例，默认 False。如果为 True，返回 (kb_service, result) 元组

    Returns:
        如果 return_service=False: 知识库ID（字符串），如果创建失败则返回 None
        如果 return_service=True: (kb_service, result) 元组，如果创建失败则抛出异常（与测试脚本行为一致）
    """
    if not documents:
        logger.warning("文档列表为空，跳过知识库创建")
        if return_service:
            raise ValueError("文档列表为空，无法创建知识库")
        return None

    try:
        # 生成知识库ID
        if not knowledge_base_id:
            if document_id:
                knowledge_base_id = f"kb_doc_{uuid.UUID(str(document_id)).hex[:16]}"
            else:
                knowledge_base_id = f"kb_{uuid.uuid4().hex[:16]}"

        logger.info(
            "开始自动创建知识库: kb_id=%s, document_count=%d, enable_vector=%s",
            knowledge_base_id,
            len(documents),
            enable_vector,
        )

        # 创建索引构建器
        vector_index_builder = None
        bm25_index_builder = None
        metadata_index_builder = None

        if INDEX_BUILDERS_AVAILABLE:
            # 创建向量索引构建器
            if enable_vector:
                try:
                    vector_collection = f"kb_{knowledge_base_id}_vector"
                    if get_chroma_connection_manager:
                        vector_index_builder = VectorIndexBuilder(
                            collection_name=vector_collection,
                            connection_manager=get_chroma_connection_manager(),
                        )
                        logger.info("创建向量索引构建器: collection_name=%s", vector_collection)
                    else:
                        logger.warning("ChromaDB连接管理器不可用，跳过向量索引构建器创建")
                except Exception as e:
                    logger.warning("创建向量索引构建器失败: %s", e, exc_info=True)

            # 创建BM25索引构建器
            if enable_bm25:
                try:
                    bm25_path = f"./data/bm25_index/kb_{knowledge_base_id}.pkl"
                    Path(bm25_path).parent.mkdir(parents=True, exist_ok=True)
                    if BM25IndexBuilder:
                        bm25_index_builder = BM25IndexBuilder(index_path=bm25_path)
                        logger.info("创建BM25索引构建器: index_path=%s", bm25_path)
                    else:
                        logger.warning("BM25IndexBuilder不可用，跳过BM25索引构建器创建")
                except Exception as e:
                    logger.warning("创建BM25索引构建器失败: %s", e, exc_info=True)

            # 创建元数据索引构建器
            if enable_metadata:
                try:
                    metadata_table_name = f"kb_{knowledge_base_id}_metadata"
                    if get_sqlite_connection_manager and MetadataIndexBuilder:
                        metadata_index_builder = MetadataIndexBuilder(
                            table_name=metadata_table_name,
                            connection_manager=get_sqlite_connection_manager(),
                        )
                        logger.info("创建元数据索引构建器: table_name=%s", metadata_table_name)
                    else:
                        logger.warning("SQLite连接管理器或MetadataIndexBuilder不可用，跳过元数据索引构建器创建")
                except Exception as e:
                    logger.warning("创建元数据索引构建器失败: %s", e, exc_info=True)
        else:
            logger.warning("索引构建器不可用（INDEX_BUILDERS_AVAILABLE=False），将跳过索引构建")

        # 创建知识库服务
        progress_service = get_progress_service()
        kb_service = KnowledgeBaseService(
            progress_service=progress_service,
            vector_index_builder=vector_index_builder,
            bm25_index_builder=bm25_index_builder,
            metadata_index_builder=metadata_index_builder,
            enable_vector=enable_vector,
            enable_bm25=enable_bm25,
            enable_metadata=enable_metadata,
        )

        # 将 LangChain Document 转换为领域模型 Document
        from langchain_core.documents import Document as LangChainDocument
        domain_documents: list[Document] = []

        def _looks_like_uuid(s: str) -> bool:
            try:
                uuid.UUID(str(s))
                return True
            except Exception:
                return False

        def _clean_doc_dir_name(name: str) -> str:
            """清理 cleaned/documents 下目录名噪音：去掉末尾 _86/_e6 等。"""
            import re

            s = (name or "").strip()
            if not s:
                return ""
            s = re.sub(r"_[0-9]{1,3}$", "", s)
            s = re.sub(r"_[0-9a-fA-F]{2}$", "", s)
            return s.strip(" _-")

        for i, lc_doc in enumerate(documents):
            try:
                # 从 LangChain Document 创建领域模型 Document
                lc_meta = dict(getattr(lc_doc, "metadata", {}) or {})
                source_path = str(lc_meta.get("source") or "")

                # 1) filename：优先用上游传入；否则从 source 推断
                filename = str(lc_meta.get("filename") or "").strip()
                if not filename:
                    filename = Path(source_path).name if source_path else f"document_{i}.md"

                # 2) 如果 source 指向 cleaned 的 clean.md，推断出 pdf_extracted / doc_dir / 原始 pdf 文件名
                try:
                    p = Path(source_path) if source_path else None
                    if p and p.name.lower() == "clean.md" and p.parent.name.endswith(".pdf_extracted"):
                        extracted_dir = p.parent
                        doc_dir = extracted_dir.parent
                        extracted_name = extracted_dir.name  # e.g. "<uuid>_<pdf>.pdf_extracted"
                        base = extracted_name[: -len(".pdf_extracted")]  # e.g. "<uuid>_<pdf>.pdf"

                        # 去掉前缀 UUID_
                        pdf_filename = ""
                        parts = base.split("_", 1)
                        if len(parts) == 2 and _looks_like_uuid(parts[0]):
                            pdf_filename = parts[1]
                        else:
                            pdf_filename = base

                        if pdf_filename:
                            lc_meta.setdefault("original_pdf_filename", pdf_filename)
                            # 展示/引用优先用 pdf 文件名（比 clean.md 更友好）
                            lc_meta.setdefault("filename", pdf_filename)
                            filename = pdf_filename

                        lc_meta.setdefault("cleaned_extracted_dir", str(extracted_dir))
                        lc_meta.setdefault("cleaned_doc_dir", str(doc_dir))
                        source_title = _clean_doc_dir_name(doc_dir.name)
                        lc_meta.setdefault("source_title", source_title)
                        # 统一补齐 document_name，供下游向量库/元数据表/引用展示使用
                        lc_meta.setdefault("document_name", source_title or Path(filename).stem)
                except Exception:
                    pass

                # 3) 确保 file_path/source 至少有一个可用于定位
                if source_path:
                    lc_meta.setdefault("file_path", source_path)
                    lc_meta.setdefault("source", source_path)
                
                # 获取 uploaded_by：
                # - 优先使用 LangChain metadata（如果上游显式传入）
                # - 否则回退到真实 document 记录（create_knowledge_base_from_documents 传入的 document_id）
                # - 若仍不可得，使用 None（而不是硬编码UUID）
                uploaded_by: uuid.UUID | None = None
                uploaded_by_str = lc_doc.metadata.get("uploaded_by")
                if uploaded_by_str:
                    try:
                        uploaded_by = uuid.UUID(str(uploaded_by_str))
                    except Exception:
                        uploaded_by = None
                if uploaded_by is None and document_id is not None:
                    try:
                        from src.application.services.document_service import DocumentService

                        doc = DocumentService().get_document(document_id)
                        uploaded_by = doc.uploaded_by if doc else None
                    except Exception:
                        uploaded_by = None

                # 确定文档格式与 MIME（必须保持一致，否则会触发 Document 的跨字段校验）
                #
                # 说明：预处理产物通常是 markdown/纯文本，但当前 DocumentFormat 不包含 MARKDOWN。
                # 为避免校验失败并确保索引可用，这里统一将“可索引的文本产物”视作 HTML 近似格式，
                # 并将 mime_type 设为与 HTML 匹配的 text/html。
                #
                # 如果未来引入 DocumentFormat.MARKDOWN，再按真实格式回填。
                doc_format = DocumentFormat.HTML
                mime_type = "text/html"

                # 4) 复用真实 document_id（如果传入），避免后续通过 documents 表补元数据时匹配不到
                domain_doc_id = uuid.uuid4()
                if document_id is not None:
                    try:
                        domain_doc_id = uuid.UUID(str(document_id))
                    except Exception:
                        domain_doc_id = uuid.uuid4()
                
                domain_doc = Document(
                    id=domain_doc_id,
                    filename=filename,
                    file_path=source_path,
                    file_size=len(lc_doc.page_content.encode('utf-8')),
                    format=doc_format,
                    content=lc_doc.page_content,
                    mime_type=mime_type,
                    parsed_at=datetime.now(),
                    uploaded_by=uploaded_by,
                    error_message=None,
                    metadata=lc_meta,
                )
                domain_documents.append(domain_doc)
            except Exception as e:
                logger.warning("转换文档失败 [%d/%d]: %s", i + 1, len(documents), e, exc_info=True)
                continue

        if not domain_documents:
            logger.error("没有可用的文档用于创建知识库")
            if return_service:
                raise ValueError("没有可用的文档用于创建知识库")
            return None

        # 创建知识库
        result = kb_service.create_knowledge_base(
            knowledge_base_id=knowledge_base_id,
            documents=domain_documents,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        kb_id = result.get("id") or result.get("knowledge_base_id") or knowledge_base_id
        logger.info(
            "知识库创建成功: kb_id=%s, document_count=%d, chunk_count=%d, index_count=%d",
            kb_id,
            result.get("document_count", 0),
            result.get("chunk_count", 0),
            result.get("index_count", 0),
        )

        if return_service:
            return (kb_service, result)  # type: ignore[return-value]
        return kb_id

    except Exception as e:
        # 知识库创建失败不应该影响文档上传的成功
        logger.error(
            "自动创建知识库失败（不影响文档上传）: document_id=%s, 错误=%s",
            document_id,
            e,
            exc_info=True,
        )
        if return_service:
            # 如果 return_service=True，测试场景通常需要抛出异常以便调试
            raise
        return None

