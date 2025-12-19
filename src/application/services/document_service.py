"""
文档服务

封装文档预处理Agent和异步任务,提供业务层接口。
处理文档上传、格式识别、预处理等业务流程。
输入输出使用LangChain Document对象格式。

基于LangChain 1.0最佳实践实现:
- 封装Agent为服务层接口
- 统一使用LangChain Document对象格式
- 支持异步处理和批量处理
- 集成文档存储和元数据管理

生成命令: /speckit.implement T033
生成时间: 2025-12-17
来源: specs/001-multi-agent-doc-system/tasks.md
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from src.application.agent_base import AgentConfig
from src.application.agents.document_preprocessor import DocumentPreprocessorAgent
from src.domain.document.document import (
    Document as DomainDocument,
    DocumentFormat,
    DocumentStatus,
)
from src.infrastructure.preprocessing.format_detector import FormatDetector, FormatInfo
from src.infrastructure.storage.sqlite.adapter import SQLiteAdapter
from src.infrastructure.tasks.document_tasks import (
    process_batch_documents_async,
    process_document_async,
)
from src.shared.config.llm_service import LLMService, get_llm_service
from src.shared.config.settings import get_config
from src.shared.exceptions.agent_exceptions import AgentExecutionError
from src.shared.exceptions.base_exceptions import ProcessingError
from src.shared.utils.logging import get_logger

logger = get_logger(__name__)


class DocumentService:
    """
    文档服务

    封装文档预处理Agent(T032)和异步任务(T037),提供业务层接口。
    处理文档上传、格式识别、预处理等业务流程。
    输入输出使用LangChain Document对象格式。

    功能特性:
    - 文档上传和元数据管理
    - 格式识别和验证
    - 文档预处理(同步和异步)
    - 批量文档处理
    - 文档查询和状态管理
    - 集成SQLite存储

    使用示例:
        ```python
        service = DocumentService()

        # 上传并处理文档
        documents = service.upload_and_process(
            file_path='path/to/document.pdf',
            uploaded_by=user_id
        )

        # 异步处理文档
        result = await service.upload_and_process_async(
            file_path='path/to/document.pdf',
            uploaded_by=user_id
        )
        ```
    """

    def __init__(
        self,
        llm_service: LLMService | None = None,
        document_repository: SQLiteAdapter | None = None,
        *,
        enable_chart_conversion: bool = True,
        use_agent: bool = True,
    ):
        """
        初始化文档服务

        Args:
            llm_service: LLM服务实例,如果为None则使用全局实例
            document_repository: 文档存储适配器,如果为None则创建新实例
            enable_chart_conversion: 是否启用图表转换功能,默认为True
            use_agent: 是否使用T032 Agent(True)或T031协调器(False),默认为True
        """
        self.llm_service = llm_service or get_llm_service()
        self.enable_chart_conversion = enable_chart_conversion
        self.use_agent = use_agent

        # 初始化格式检测器
        self.format_detector = FormatDetector(enable_deep_detection=True)

        # 初始化文档存储适配器
        if document_repository is None:
            # 使用SQLiteAdapter存储文档元数据
            # 注意:这里假设documents表已经存在(通过数据库迁移创建)
            self.document_repository = SQLiteAdapter(
                table_name="documents",
                id_field="id",
                created_at_field="uploaded_at",
                updated_at_field="parsed_at",
            )
        else:
            self.document_repository = document_repository

        # 初始化用户存储适配器(用于确保用户存在)
        from src.infrastructure.storage.sqlite.connection import get_connection_manager

        get_connection_manager()
        self.user_repository = SQLiteAdapter(
            table_name="users",
            id_field="id",
            created_at_field="created_at",
            updated_at_field="updated_at",
        )

        # 初始化文档预处理Agent(仅在需要同步处理时使用)
        self._agent: DocumentPreprocessorAgent | None = None

        logger.info(
            "DocumentService初始化完成: use_agent=%s, chart_conversion=%s",
            use_agent,
            "enabled" if enable_chart_conversion else "disabled",
        )

    def _get_agent(self) -> DocumentPreprocessorAgent:
        """获取文档预处理Agent实例(懒加载)

        Returns:
            DocumentPreprocessorAgent实例
        """
        if self._agent is None:
            global_config = get_config()
            llm_config = global_config.llm_config or {}

            agent_config = AgentConfig(
                agent_id="document_service_agent",
                agent_name="Document Service Agent",
                description="文档服务使用的文档预处理Agent",
                model_name=llm_config.get("model_name", "gpt-4"),
                temperature=llm_config.get("temperature", 0.7),
                max_tokens=llm_config.get("max_tokens", 4096),
                enable_error_handling=True,
                enable_logging=True,
            )

            self._agent = DocumentPreprocessorAgent(
                config=agent_config,
                llm_service=self.llm_service,
                enable_chart_conversion=self.enable_chart_conversion,
            )

        return self._agent

    def _ensure_user_exists(self, user_id: uuid.UUID) -> None:
        """
        确保用户存在(如果不存在则创建测试用户)

        这是一个辅助方法,用于处理外键约束。
        在测试环境中,如果用户不存在,会创建一个默认的测试用户。

        Args:
            user_id: 用户ID
        """
        try:
            # 检查用户是否存在
            user_data = self.user_repository.get_by_id(str(user_id))
            if user_data is None:
                # 用户不存在,创建测试用户
                # 注意:由于users表的id是TEXT类型(UUID字符串),不是自增ID,
                # 我们需要直接使用INSERT语句,而不是依赖SQLiteAdapter的create方法
                # (因为create方法对于TEXT类型的ID可能会出错)
                import json
                from datetime import datetime

                from src.infrastructure.storage.sqlite.connection import (
                    get_connection_manager,
                )

                connection_manager = get_connection_manager()
                user_id_str = str(user_id)
                test_user_data = {
                    "id": user_id_str,
                    "username": f"test_user_{user_id_str[:8]}",  # 使用前8位避免用户名过长
                    "email": None,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                    "preferences": json.dumps({}),
                }

                try:
                    # 直接使用SQL执行插入,因为ID是TEXT类型
                    # 使用INSERT OR IGNORE避免并发创建时的唯一约束冲突
                    with connection_manager.transaction() as cursor:
                        # 先检查是否已经存在(避免不必要的插入尝试)
                        cursor.execute(
                            "SELECT id FROM users WHERE id = ?", (user_id_str,)
                        )
                        if cursor.fetchone() is None:
                            # 执行插入,使用INSERT OR IGNORE避免唯一约束冲突
                            try:
                                cursor.execute(
                                    """INSERT OR IGNORE INTO users (id, username, email, created_at, updated_at, preferences)
                                       VALUES (?, ?, ?, ?, ?, ?)""",
                                    (
                                        test_user_data["id"],
                                        test_user_data["username"],
                                        test_user_data["email"],
                                        test_user_data["created_at"],
                                        test_user_data["updated_at"],
                                        test_user_data["preferences"],
                                    ),
                                )
                                if cursor.rowcount > 0:
                                    logger.info("创建测试用户: %s", user_id)
                                else:
                                    logger.debug(
                                        "测试用户已存在(并发创建): %s", user_id
                                    )
                            except Exception as insert_error:
                                # 如果插入失败(如唯一约束冲突),这是正常的(并发情况)
                                logger.debug(
                                    "创建测试用户失败(可能已存在): %s, 错误: %s",
                                    user_id,
                                    insert_error,
                                )
                except Exception as e:
                    # 如果创建失败(可能因为并发创建),忽略错误
                    # 因为用户可能已经被其他请求创建了
                    logger.debug(
                        "创建测试用户失败(可能已存在): %s, 错误: %s", user_id, e
                    )
        except Exception as e:
            # 如果检查用户失败,记录警告但继续执行
            # 这允许在用户表不存在或有问题的情况下继续运行
            logger.warning("检查用户存在性失败: %s, 错误: %s", user_id, e)

    def detect_format(self, file_path: str) -> FormatInfo:
        """
        检测文档格式

        Args:
            file_path: 文件路径

        Returns:
            FormatInfo: 格式信息

        Raises:
            FileNotFoundError: 文件不存在时抛出
            ProcessingError: 格式检测失败时抛出
        """
        try:
            format_info = self.format_detector.detect_format(file_path)
            logger.debug("格式检测完成: %s, format=%s", file_path, format_info.format)

            # 检查格式是否支持
            supported_formats = {"pdf", "docx", "html"}
            if format_info.format.lower() not in supported_formats:
                msg = (
                    f"不支持的文档格式: {format_info.format}。"
                    f"支持的格式: {', '.join(supported_formats)}"
                )
                raise ProcessingError(msg)

            return format_info
        except FileNotFoundError:
            raise
        except ProcessingError:
            raise
        except Exception as e:
            error_msg = f"格式检测失败: {file_path}, 错误: {e}"
            logger.error(error_msg)
            raise ProcessingError(error_msg) from e

    def validate_document(self, file_path: str) -> bool:
        """
        验证文档

        Args:
            file_path: 文件路径

        Returns:
            bool: 是否通过验证

        Raises:
            ProcessingError: 验证失败时抛出
        """
        try:
            validation_result = self.format_detector.validate_document(file_path)
            if not validation_result.is_valid:
                errors = ", ".join(validation_result.errors)
                msg = f"文档验证失败: {errors}"
                raise ProcessingError(msg)

            return True
        except Exception as e:
            if isinstance(e, ProcessingError):
                raise
            error_msg = f"文档验证异常: {file_path}, 错误: {e}"
            logger.error(error_msg)
            raise ProcessingError(error_msg) from e

    def _langchain_to_domain_document(
        self,
        langchain_doc: Document,
        domain_doc: DomainDocument,
    ) -> dict[str, Any]:
        """
        将LangChain Document对象转换为领域模型Document的更新数据

        Args:
            langchain_doc: LangChain Document对象
            domain_doc: 领域模型Document对象

        Returns:
            更新数据字典
        """
        # 从LangChain Document的元数据中提取信息
        metadata = langchain_doc.metadata.copy()

        # 更新领域模型的元数据
        domain_metadata = domain_doc.metadata.copy()
        domain_metadata.update(
            {
                "langchain_metadata": metadata,
                "page_content_length": len(langchain_doc.page_content),
                "processed_at": datetime.utcnow().isoformat(),
            }
        )

        # 返回更新数据
        return {
            "metadata": domain_metadata,
        }

    def _domain_to_langchain_document(self, domain_doc: DomainDocument) -> Document:
        """
        将领域模型Document转换为LangChain Document对象

        Args:
            domain_doc: 领域模型Document对象

        Returns:
            LangChain Document对象

        Note:
            由于领域模型Document只存储元数据,不存储内容,
            这个方法主要用于文档查询时构建LangChain Document对象。
            实际的内容需要从文件系统或其他存储中读取。
        """
        # 从领域模型的元数据中提取LangChain元数据
        langchain_metadata = domain_doc.metadata.get("langchain_metadata", {})
        langchain_metadata.update(
            {
                "source": domain_doc.file_path,
                "format": domain_doc.format,  # 由于use_enum_values=True,已经是字符串
                "id": str(domain_doc.id),
                "filename": domain_doc.filename,
                "uploaded_at": domain_doc.uploaded_at.isoformat(),
                "status": domain_doc.status,  # 由于use_enum_values=True,已经是字符串
            }
        )

        # 创建LangChain Document对象
        # 注意:page_content为空,因为领域模型不存储内容
        return Document(
            page_content="",
            metadata=langchain_metadata,
        )

    def create_document_record(
        self,
        file_path: str,
        uploaded_by: uuid.UUID,
        format_info: FormatInfo | None = None,
    ) -> DomainDocument:
        """
        创建文档记录(保存到数据库)

        Args:
            file_path: 文件路径
            uploaded_by: 上传用户ID
            format_info: 格式信息,如果为None则自动检测

        Returns:
            DomainDocument: 创建的文档领域模型对象

        Raises:
            ProcessingError: 创建失败时抛出
        """
        try:
            # 检测格式(如果未提供)
            if format_info is None:
                format_info = self.detect_format(file_path)

            # 验证文件
            path = Path(file_path)
            if not path.exists():
                msg = f"文件不存在: {file_path}"
                raise FileNotFoundError(msg)

            file_size = path.stat().st_size

            # 映射格式字符串到DocumentFormat枚举
            format_mapping = {
                "pdf": DocumentFormat.PDF,
                "docx": DocumentFormat.DOCX,
                "html": DocumentFormat.HTML,
            }
            doc_format = format_mapping.get(format_info.format.lower())
            if doc_format is None:
                msg = (
                    f"不支持的文档格式: {format_info.format}。"
                    f"支持的格式: {', '.join(format_mapping.keys())}"
                )
                raise ProcessingError(msg)

            # 确保用户存在(避免外键约束失败)
            self._ensure_user_exists(uploaded_by)

            # 创建领域模型对象
            domain_doc = DomainDocument(
                id=uuid.uuid4(),
                filename=path.name,
                file_path=str(path.absolute()),
                file_size=file_size,
                mime_type=format_info.mime_type,
                format=doc_format,
                uploaded_by=uploaded_by,
                status=DocumentStatus.PENDING,
                metadata={
                    "format_info": {
                        "format": format_info.format,
                        "mime_type": format_info.mime_type,
                        "extension": format_info.extension,
                        "confidence": format_info.confidence,
                    }
                },
            )

            # 保存到数据库
            # 注意:由于documents表的id是TEXT类型(UUID字符串),不是自增ID,
            # 我们需要直接使用SQL执行插入,而不是依赖SQLiteAdapter的create方法
            # (因为create方法对于TEXT类型的ID可能会出错)
            import json

            from src.infrastructure.storage.sqlite.connection import (
                get_connection_manager,
            )

            # 准备数据
            doc_id_str = str(domain_doc.id)
            uploaded_by_str = str(domain_doc.uploaded_by)
            metadata_json = json.dumps(domain_doc.metadata, ensure_ascii=False)

            connection_manager = get_connection_manager()
            try:
                # 直接使用SQL执行插入和查询(在同一事务中)
                with connection_manager.transaction() as cursor:
                    # 执行插入
                    cursor.execute(
                        """INSERT INTO documents
                           (id, filename, file_path, file_size, mime_type, format,
                            uploaded_at, uploaded_by, status, parsed_at, error_message, metadata)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            doc_id_str,
                            domain_doc.filename,
                            domain_doc.file_path,
                            domain_doc.file_size,
                            domain_doc.mime_type,
                            domain_doc.format,  # 由于use_enum_values=True,已经是字符串
                            domain_doc.uploaded_at.isoformat(),
                            uploaded_by_str,
                            domain_doc.status,  # 由于use_enum_values=True,已经是字符串
                            (
                                domain_doc.parsed_at.isoformat()
                                if domain_doc.parsed_at
                                else None
                            ),
                            domain_doc.error_message,
                            metadata_json,
                        ),
                    )

                    # 查询刚创建的记录
                    cursor.execute(
                        "SELECT * FROM documents WHERE id = ?",
                        (doc_id_str,),
                    )
                    row = cursor.fetchone()

                    if row is None:
                        msg = f"创建文档记录后无法找到记录: {doc_id_str}"
                        raise ProcessingError(msg)

                    # 转换为字典
                    saved_data = dict(row)

                    # 反序列化metadata
                    if "metadata" in saved_data and isinstance(
                        saved_data["metadata"], str
                    ):
                        saved_data["metadata"] = json.loads(saved_data["metadata"])

                    # 转换数据类型
                    saved_data["id"] = uuid.UUID(saved_data["id"])
                    saved_data["uploaded_by"] = uuid.UUID(saved_data["uploaded_by"])
                    saved_data["format"] = DocumentFormat(saved_data["format"])
                    saved_data["status"] = DocumentStatus(saved_data["status"])

                    logger.info(
                        "文档记录创建成功: %s, file=%s", domain_doc.id, file_path
                    )
                    return DomainDocument(**saved_data)

            except Exception as e:
                if isinstance(e, ProcessingError):
                    raise
                error_msg = f"保存文档记录失败: {e}"
                logger.exception(error_msg)
                raise ProcessingError(error_msg) from e

        except Exception as e:
            if isinstance(e, (ProcessingError, FileNotFoundError)):
                raise
            error_msg = f"创建文档记录失败: {file_path}, 错误: {e}"
            logger.exception(error_msg)
            raise ProcessingError(error_msg) from e

    def upload_and_process(
        self,
        file_path: str,
        uploaded_by: uuid.UUID,
        doc_format: str | None = None,
    ) -> list[Document]:
        """
        上传并处理文档(同步)

        完整流程:
        1. 格式识别和验证
        2. 创建文档记录
        3. 使用Agent预处理文档
        4. 更新文档状态

        Args:
            file_path: 文件路径
            uploaded_by: 上传用户ID
            format: 文档格式(可选,如果不指定则自动识别)

        Returns:
            List[Document]: 处理后的LangChain Document列表

        Raises:
            ProcessingError: 处理失败时抛出
        """
        try:
            logger.info("开始上传并处理文档: %s", file_path)

            # 1. 格式识别和验证
            format_info = self.detect_format(file_path)
            if doc_format:
                # 检查指定格式是否支持
                supported_formats = {"pdf", "docx", "html"}
                if doc_format.lower() not in supported_formats:
                    msg = (
                        f"不支持的指定格式: {doc_format}。"
                        f"支持的格式: {', '.join(supported_formats)}"
                    )
                    raise ProcessingError(msg)

                # 验证指定格式与检测格式是否匹配
                if doc_format.lower() != format_info.format.lower():
                    msg = (
                        f"指定格式 '{doc_format}' 与检测格式 '{format_info.format}' 不匹配。"
                        f"请确认文件格式或移除doc_format参数以使用自动检测。"
                    )
                    raise ProcessingError(msg)

            # 验证文档
            self.validate_document(file_path)

            # 2. 创建文档记录
            domain_doc = self.create_document_record(
                file_path=file_path,
                uploaded_by=uploaded_by,
                format_info=format_info,
            )

            # 3. 更新状态为处理中
            try:
                self.document_repository.update(
                    str(domain_doc.id), {"status": DocumentStatus.PARSING.value}
                )
            except Exception as e:
                logger.warning("更新文档状态失败: %s", e)

            # 4. 使用Agent预处理文档
            try:
                agent = self._get_agent()
                langchain_docs = agent.load_and_process(
                    file_path=file_path,
                    doc_format=format_info.format,
                )

                # 5. 更新文档记录(保存处理结果元数据)
                if langchain_docs:
                    update_data = self._langchain_to_domain_document(
                        langchain_docs[0],
                        domain_doc,
                    )
                    update_data["status"] = DocumentStatus.INDEXED.value
                    update_data["parsed_at"] = datetime.utcnow().isoformat()

                    # 将metadata字典转换为JSON字符串以避免SQLite绑定错误
                    import json

                    if "metadata" in update_data and isinstance(
                        update_data["metadata"], dict
                    ):
                        update_data["metadata"] = json.dumps(
                            update_data["metadata"], ensure_ascii=False
                        )

                    self.document_repository.update(
                        str(domain_doc.id),
                        update_data,
                    )

                logger.info(
                    "文档处理完成: %s, 文档数=%d", file_path, len(langchain_docs)
                )
                return langchain_docs

            except AgentExecutionError as e:
                # Agent执行失败,更新状态为失败
                error_msg = str(e)
                try:
                    self.document_repository.update(
                        str(domain_doc.id),
                        {
                            "status": DocumentStatus.FAILED.value,
                            "error_message": error_msg,
                        },
                    )
                except Exception as update_error:
                    logger.error("更新文档失败状态失败: %s", update_error)

                msg = f"文档预处理失败: {error_msg}"
                raise ProcessingError(msg) from e

        except Exception as e:
            if isinstance(e, ProcessingError):
                raise
            error_msg = f"上传并处理文档失败: {file_path}, 错误: {e}"
            logger.exception(error_msg)
            raise ProcessingError(error_msg) from e

    async def upload_and_process_async(
        self,
        file_path: str,
        uploaded_by: uuid.UUID,
        doc_format: str | None = None,
        *,
        enable_chart_conversion: bool | None = None,
    ) -> dict[str, Any]:
        """
        上传并处理文档(异步)

        使用T037异步任务处理文档,适用于大文件或需要异步处理的场景。

        Args:
            file_path: 文件路径
            uploaded_by: 上传用户ID
            format: 文档格式(可选,如果不指定则自动识别)
            enable_chart_conversion: 是否启用图表转换,如果为None则使用服务默认值

        Returns:
            Dict[str, Any]: 任务执行结果字典

        Raises:
            ProcessingError: 处理失败时抛出
        """
        try:
            logger.info("开始异步上传并处理文档: %s", file_path)

            # 1. 格式识别和验证
            format_info = self.detect_format(file_path)
            if doc_format:
                # 检查指定格式是否支持
                supported_formats = {"pdf", "docx", "html"}
                if doc_format.lower() not in supported_formats:
                    msg = (
                        f"不支持的指定格式: {doc_format}。"
                        f"支持的格式: {', '.join(supported_formats)}"
                    )
                    raise ProcessingError(msg)

                # 验证指定格式与检测格式是否匹配
                if doc_format.lower() != format_info.format.lower():
                    msg = (
                        f"指定格式 '{doc_format}' 与检测格式 '{format_info.format}' 不匹配。"
                        f"请确认文件格式或移除doc_format参数以使用自动检测。"
                    )
                    raise ProcessingError(msg)

            # 验证文档
            self.validate_document(file_path)

            # 2. 创建文档记录
            domain_doc = self.create_document_record(
                file_path=file_path,
                uploaded_by=uploaded_by,
                format_info=format_info,
            )

            # 3. 更新状态为处理中
            try:
                self.document_repository.update(
                    str(domain_doc.id), {"status": DocumentStatus.PARSING.value}
                )
            except Exception as e:
                logger.warning("更新文档状态失败: %s", e)

            # 4. 调用异步任务处理文档
            chart_conversion = (
                enable_chart_conversion
                if enable_chart_conversion is not None
                else self.enable_chart_conversion
            )

            result = await process_document_async(
                file_path=file_path,
                use_agent=self.use_agent,
                enable_chart_conversion=chart_conversion,
            )

            # 5. 更新文档状态
            if result.get("status") == "completed":
                try:
                    # 将metadata字典转换为JSON字符串以避免SQLite绑定错误
                    import json

                    metadata_dict = {
                        "task_result": result,
                    }

                    self.document_repository.update(
                        str(domain_doc.id),
                        {
                            "status": DocumentStatus.INDEXED.value,
                            "parsed_at": datetime.utcnow().isoformat(),
                            "metadata": json.dumps(metadata_dict, ensure_ascii=False),
                        },
                    )
                except Exception as e:
                    logger.warning("更新文档状态失败: %s", e)
            else:
                # 处理失败
                error_msg = result.get("error", "Unknown error")
                try:
                    self.document_repository.update(
                        str(domain_doc.id),
                        {
                            "status": DocumentStatus.FAILED.value,
                            "error_message": error_msg,
                        },
                    )
                except Exception as e:
                    logger.warning("更新文档失败状态失败: %s", e)

                msg = f"文档异步处理失败: {error_msg}"
                raise ProcessingError(msg)

            logger.info("文档异步处理完成: %s", file_path)
            return result

        except Exception as e:
            if isinstance(e, ProcessingError):
                raise
            error_msg = f"异步上传并处理文档失败: {file_path}, 错误: {e}"
            logger.exception(error_msg)
            raise ProcessingError(error_msg) from e

    async def upload_and_process_batch_async(
        self,
        file_paths: list[str],
        uploaded_by: uuid.UUID,
        batch_size: int = 10,
        *,
        enable_chart_conversion: bool | None = None,
    ) -> dict[str, Any]:
        """
        批量上传并处理文档(异步)

        使用T037批量异步任务处理多个文档。

        Args:
            file_paths: 文件路径列表
            uploaded_by: 上传用户ID
            batch_size: 批量处理大小,默认为10
            enable_chart_conversion: 是否启用图表转换,如果为None则使用服务默认值

        Returns:
            Dict[str, Any]: 批量处理结果字典

        Raises:
            ProcessingError: 处理失败时抛出
        """
        try:
            logger.info("开始批量异步上传并处理文档: %d 个文件", len(file_paths))

            # 1. 创建所有文档记录
            domain_docs = []
            for file_path in file_paths:
                try:
                    format_info = self.detect_format(file_path)
                    self.validate_document(file_path)
                    domain_doc = self.create_document_record(
                        file_path=file_path,
                        uploaded_by=uploaded_by,
                        format_info=format_info,
                    )
                    domain_docs.append(domain_doc)

                    # 更新状态为处理中
                    try:
                        self.document_repository.update(
                            str(domain_doc.id), {"status": DocumentStatus.PARSING.value}
                        )
                    except Exception as e:
                        logger.warning("更新文档状态失败: %s", e)

                except Exception as e:
                    logger.error("创建文档记录失败: %s, 错误: %s", file_path, e)
                    continue

            if not domain_docs:
                msg = "没有有效的文档需要处理"
                raise ProcessingError(msg)

            # 2. 调用批量异步任务处理文档
            chart_conversion = (
                enable_chart_conversion
                if enable_chart_conversion is not None
                else self.enable_chart_conversion
            )

            result = await process_batch_documents_async(
                file_paths=file_paths,
                batch_size=batch_size,
                enable_chart_conversion=chart_conversion,
            )

            # 3. 更新所有文档状态
            processed_files = result.get("processed_files", [])
            failed_files = result.get("failed_files", [])

            for domain_doc in domain_docs:
                if domain_doc.file_path in processed_files:
                    try:
                        self.document_repository.update(
                            str(domain_doc.id),
                            {
                                "status": DocumentStatus.INDEXED.value,
                                "parsed_at": datetime.utcnow().isoformat(),
                            },
                        )
                    except Exception as e:
                        logger.warning("更新文档状态失败: %s", e)
                elif domain_doc.file_path in failed_files:
                    try:
                        self.document_repository.update(
                            str(domain_doc.id),
                            {
                                "status": DocumentStatus.FAILED.value,
                                "error_message": "批量处理失败",
                            },
                        )
                    except Exception as e:
                        logger.warning("更新文档失败状态失败: %s", e)

            logger.info(
                "批量文档异步处理完成: 成功 %d/%d 个文件",
                len(processed_files),
                len(file_paths),
            )
            return result

        except Exception as e:
            if isinstance(e, ProcessingError):
                raise
            error_msg = f"批量异步上传并处理文档失败: 错误: {e}"
            logger.exception(error_msg)
            raise ProcessingError(error_msg) from e

    def get_document(self, document_id: uuid.UUID) -> DomainDocument | None:
        """
        根据ID获取文档

        Args:
            document_id: 文档ID

        Returns:
            DomainDocument: 文档领域模型对象,如果不存在则返回None

        Raises:
            ProcessingError: 查询失败时抛出
        """
        try:
            doc_data = self.document_repository.get_by_id(str(document_id))
            if doc_data is None:
                return None

            # 转换数据格式
            doc_data["id"] = uuid.UUID(doc_data["id"])
            doc_data["uploaded_by"] = uuid.UUID(doc_data["uploaded_by"])
            doc_data["format"] = DocumentFormat(doc_data["format"])
            doc_data["status"] = DocumentStatus(doc_data["status"])

            # 反序列化metadata字段(如果是JSON字符串)
            if "metadata" in doc_data and isinstance(doc_data["metadata"], str):
                try:
                    import json

                    doc_data["metadata"] = json.loads(doc_data["metadata"])
                except (json.JSONDecodeError, TypeError):
                    # 如果反序列化失败,设置为空字典
                    doc_data["metadata"] = {}

            return DomainDocument(**doc_data)

        except Exception as e:
            error_msg = f"查询文档失败: {document_id}, 错误: {e}"
            logger.error(error_msg)
            raise ProcessingError(error_msg) from e

    def list_documents(
        self,
        uploaded_by: uuid.UUID | None = None,
        status: DocumentStatus | None = None,
        limit: int | None = None,
    ) -> list[DomainDocument]:
        """
        列出文档

        Args:
            uploaded_by: 上传用户ID(可选,用于筛选)
            status: 文档状态(可选,用于筛选)
            limit: 限制数量(可选)

        Returns:
            List[DomainDocument]: 文档列表

        Raises:
            ProcessingError: 查询失败时抛出
        """
        try:
            filters = {}
            if uploaded_by:
                filters["uploaded_by"] = str(uploaded_by)
            if status:
                filters["status"] = status.value

            doc_data_list = self.document_repository.list(
                filters=filters if filters else None,
                limit=limit,
            )

            domain_docs = []
            for doc_data in doc_data_list:
                try:
                    # 转换数据格式
                    doc_data["id"] = uuid.UUID(doc_data["id"])
                    doc_data["uploaded_by"] = uuid.UUID(doc_data["uploaded_by"])
                    doc_data["format"] = DocumentFormat(doc_data["format"])
                    doc_data["status"] = DocumentStatus(doc_data["status"])

                    # 反序列化metadata字段(如果是JSON字符串)
                    if "metadata" in doc_data and isinstance(doc_data["metadata"], str):
                        try:
                            import json

                            doc_data["metadata"] = json.loads(doc_data["metadata"])
                        except (json.JSONDecodeError, TypeError):
                            # 如果反序列化失败,设置为空字典
                            doc_data["metadata"] = {}

                    domain_docs.append(DomainDocument(**doc_data))
                except Exception as e:
                    logger.warning(
                        "转换文档数据失败: %s, 错误: %s", doc_data.get("id"), e
                    )
                    continue

            return domain_docs

        except Exception as e:
            error_msg = f"列出文档失败: 错误: {e}"
            logger.error(error_msg)
            raise ProcessingError(error_msg) from e

    def process_document(
        self,
        document: Document,
    ) -> Document:
        """
        处理单个LangChain Document对象

        Args:
            document: LangChain Document对象

        Returns:
            Document: 处理后的LangChain Document对象

        Raises:
            ProcessingError: 处理失败时抛出
        """
        try:
            agent = self._get_agent()
            processed_doc = agent.process_document(document)
            logger.info(
                "Document处理完成: %s", document.metadata.get("source", "unknown")
            )
            return processed_doc
        except AgentExecutionError as e:
            error_msg = f"处理Document失败: {e}"
            logger.error(error_msg)
            raise ProcessingError(error_msg) from e

    def process_documents(
        self,
        documents: list[Document],
    ) -> list[Document]:
        """
        批量处理LangChain Document对象列表

        Args:
            documents: LangChain Document对象列表

        Returns:
            List[Document]: 处理后的LangChain Document对象列表

        Raises:
            ProcessingError: 处理失败时抛出
        """
        try:
            agent = self._get_agent()
            processed_docs = agent.process_documents(documents)
            logger.info("批量Document处理完成: %d 个文档", len(processed_docs))
            return processed_docs
        except AgentExecutionError as e:
            error_msg = f"批量处理Document失败: {e}"
            logger.error(error_msg)
            raise ProcessingError(error_msg) from e
