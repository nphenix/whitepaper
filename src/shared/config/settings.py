"""配置管理模型

使用 Pydantic 定义所有配置项的模型,支持环境变量注入和验证。
"""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderConfig(BaseModel):
    """LLM 提供商配置"""

    # 通用配置
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="温度参数")
    max_tokens: int = Field(default=4096, gt=0, description="最大 token 数")
    timeout: int = Field(default=60, gt=0, description="超时时间(秒)")

    # 供应商特定配置
    model_name: str = Field(default="gpt-4", description="模型名称")
    api_key: str | None = Field(default=None, description="API 密钥")
    base_url: str | None = Field(default=None, description="API 基础 URL")


class OpenAICompatibleConfig(LLMProviderConfig):
    """OpenAI 兼容接口配置"""

    provider: Literal["openai_compatible"] = "openai_compatible"
    base_url: str = Field(
        default="https://api.openai.com/v1", description="API 基础 URL"
    )
    api_key: str = Field(description="API 密钥")


class GeminiConfig(LLMProviderConfig):
    """Google Gemini 配置"""

    provider: Literal["gemini"] = "gemini"
    model_name: str = Field(default="gemini-pro", description="模型名称")
    api_key: str = Field(description="API 密钥")


class AnthropicConfig(LLMProviderConfig):
    """Anthropic Claude 配置"""

    provider: Literal["anthropic"] = "anthropic"
    model_name: str = Field(default="claude-3-opus-20240229", description="模型名称")
    api_key: str = Field(description="API 密钥")


class EmbeddingConfig(BaseModel):
    """Embedding 模型配置"""

    model_config = ConfigDict(extra="ignore")

    provider: Literal["dashscope", "openai"] = Field(
        default="dashscope", description="Embedding 提供商"
    )
    model_name: str = Field(default="text-embedding-v4", description="模型名称")
    api_key: str = Field(default="", description="API 密钥")
    dimension: int = Field(default=1536, gt=0, description="向量维度")
    batch_size: int = Field(default=32, gt=0, description="批处理大小")


class RerankConfig(BaseModel):
    """Rerank 模型配置"""

    model_config = ConfigDict(extra="ignore")

    provider: Literal["dashscope"] = Field(
        default="dashscope", description="Rerank 提供商"
    )
    model_name: str = Field(default="qwen3-rerank", description="模型名称")
    api_key: str = Field(default="", description="API 密钥")
    top_k: int = Field(default=10, gt=0, description="返回 top-k 结果")


class DatabaseConfig(BaseModel):
    """数据库配置"""

    # SQLite 配置
    sqlite_db_path: Path = Field(
        default=Path("./storage/sqlite/whitepaper.db"), description="SQLite 数据库路径"
    )
    sqlite_pool_size: int = Field(default=10, gt=0, description="连接池大小")
    sqlite_max_overflow: int = Field(default=20, ge=0, description="最大溢出连接数")

    # Chroma 配置
    chroma_db_path: Path = Field(
        default=Path("./storage/chroma"), description="Chroma 数据库路径"
    )
    chroma_collection_name: str = Field(
        default="whitepaper_documents", description="集合名称"
    )
    chroma_persist_directory: Path | None = Field(
        default=None, description="持久化目录"
    )

    # NetworkX 配置
    networkx_data_directory: Path = Field(
        default=Path("./storage/networkx"), description="NetworkX 数据目录"
    )
    networkx_default_graph_name: str = Field(
        default="whitepaper_knowledge_graph", description="默认图名称"
    )
    networkx_graph_path: Path = Field(
        default=Path("./storage/networkx/knowledge_graph.pkl"), description="图数据路径"
    )
    networkx_graph_format: str = Field(default="gml", description="图数据格式")


class RedisConfig(BaseModel):
    """Redis 配置"""

    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    redis_host: str = Field(default="localhost", description="Redis 主机")
    redis_port: int = Field(default=6379, gt=0, lt=65536, description="Redis 端口")
    redis_db: int = Field(default=0, ge=0, description="Redis 数据库编号")
    redis_password: str | None = Field(default=None, description="Redis 密码")
    redis_max_connections: int = Field(default=50, gt=0, description="最大连接数")
    redis_socket_timeout: int = Field(default=5, gt=0, description="Socket 超时时间")
    redis_socket_connect_timeout: int = Field(
        default=5, gt=0, description="连接超时时间"
    )


class ArqConfig(BaseModel):
    """Arq 任务队列配置"""

    queue_name: str = Field(default="whitepaper_tasks", description="队列名称")
    max_jobs: int = Field(default=100, gt=0, description="最大任务数")
    job_timeout: int = Field(default=3600, gt=0, description="任务超时时间")


class APIConfig(BaseModel):
    """API 服务配置"""

    # 服务配置
    host: str = Field(default="0.0.0.0", description="服务主机")
    port: int = Field(default=8000, ge=1, le=65535, description="服务端口")
    reload: bool = Field(default=False, description="是否自动重载")
    workers: int = Field(default=4, gt=0, description="工作进程数")
    log_level: str = Field(default="info", description="日志级别")

    # CORS 配置
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"], description="允许的跨域源"
    )
    cors_credentials: bool = Field(default=True, description="是否允许凭据")
    cors_methods: list[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="允许的 HTTP 方法",
    )
    cors_headers: list[str] = Field(default=["*"], description="允许的请求头")

    # 安全配置
    secret_key: str = Field(
        default="test-secret-key-for-testing", description="JWT 密钥"
    )
    access_token_expire_minutes: int = Field(
        default=30, gt=0, description="访问令牌过期时间(分钟)"
    )
    refresh_token_expire_days: int = Field(
        default=7, gt=0, description="刷新令牌过期时间(天)"
    )


class LogConfig(BaseModel):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    file: Path | None = Field(
        default=Path("./data/logs/app.log"), description="日志文件路径"
    )
    max_bytes: int = Field(default=10485760, gt=0, description="单个日志文件最大大小")
    backup_count: int = Field(default=10, ge=0, description="保留的日志文件数量")
    format: Literal["json", "text"] = Field(default="json", description="日志格式")
    enable_console: bool = Field(default=True, description="是否启用控制台日志")
    enable_file: bool = Field(default=True, description="是否启用文件日志")


class PaddleOCRConfig(BaseModel):
    """PaddleOCR 在线服务配置"""

    model_config = ConfigDict(extra="ignore")

    api_url: str = Field(default="", description="PaddleOCR API URL")
    token: str = Field(default="", description="PaddleOCR API Token")
    timeout: int = Field(default=60, gt=0, description="请求超时时间(秒)")
    max_retries: int = Field(default=3, ge=0, description="最大重试次数")


class MinerUConfig(BaseModel):
    """MinerU 在线服务配置"""

    model_config = ConfigDict(extra="ignore")

    api_key: str = Field(default="", description="MinerU API Key")
    api_url: str = Field(default="https://mineru.net/api", description="MinerU API URL")
    timeout: int = Field(default=300, gt=0, description="请求超时时间(秒)")
    max_retries: int = Field(default=3, ge=0, description="最大重试次数")
    max_file_size_mb: int = Field(default=200, gt=0, description="最大文件大小(MB)")
    max_pages: int = Field(default=600, gt=0, description="最大页数")


class AdCleaningLLMConfig(BaseModel):
    """广告清洗LLM模型配置(OpenAI兼容接口)"""

    model_config = ConfigDict(extra="ignore")

    provider: Literal["openai_compatible"] = Field(
        default="openai_compatible", description="提供商(固定为openai_compatible)"
    )
    base_url: str = Field(default="", description="API 基础 URL")
    api_key: str = Field(default="", description="API 密钥")
    model_name: str = Field(default="", description="模型名称")
    temperature: float = Field(
        default=0.3, ge=0.0, le=1.0, description="温度参数(默认0.3,用于更稳定的输出)"
    )
    # 将默认max_tokens与.env保持一致(128000),避免配置不一致导致的误判
    max_tokens: int = Field(default=128000, gt=0, description="最大输出 token 数")
    # 模型上下文窗口大小(不同模型不同,如GLM-4.6是200K,Claude是200K)
    context_window: int = Field(
        default=200000, gt=0, description="模型上下文窗口大小(tokens)"
    )
    # 超时时间需要足够长,因为大文档(60k+ tokens)处理可能需要2-3分钟
    timeout: int = Field(
        default=300, gt=0, description="请求超时时间(秒),大文档建议300秒以上"
    )


class ChartToJsonLLMConfig(BaseModel):
    """图表转JSON LLM模型配置(支持GLM-4.6V流式调用)"""

    model_config = ConfigDict(extra="ignore")

    provider: Literal["openai_compatible", "glm_4v"] = Field(
        default="glm_4v", description="提供商(glm_4v或openai_compatible)"
    )
    base_url: str = Field(default="", description="API 基础 URL")
    api_key: str = Field(default="", description="API 密钥")
    model_name: str = Field(default="glm-4.6v", description="模型名称(默认glm-4.6v)")
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="温度参数(默认0.1,用于更稳定的结构化输出)",
    )
    max_tokens: int = Field(default=8192, gt=0, description="最大输出 token 数")
    timeout: int = Field(default=120, gt=0, description="请求超时时间(秒)")
    # 是否支持多模态(图像输入)
    supports_vision: bool = Field(
        default=True, description="是否支持视觉输入(多模态模型)"
    )
    # 图表识别的置信度阈值
    confidence_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="图表识别置信度阈值"
    )
    # GLM-4.6V 特定配置
    enable_streaming: bool = Field(
        default=True, description="是否启用流式调用(GLM-4.6V推荐)"
    )
    enable_thinking: bool = Field(
        default=True, description="是否启用思考模式(GLM-4.6V特有)"
    )
    # 重试配置
    max_retries: int = Field(default=3, ge=0, description="最大重试次数")
    retry_delay: float = Field(default=1.0, gt=0, description="重试延迟(秒)")


class SummarizationMiddlewareConfig(BaseModel):
    """总结中间件配置

    用于配置SummarizationMiddleware的阈值和行为。
    支持通过环境变量覆盖,默认开启以保护长文场景。
    """

    model_config = ConfigDict(extra="ignore")

    # 是否启用总结中间件(默认True,保护长文场景)
    enabled: bool = Field(
        default=True, description="是否启用总结中间件,默认开启以保护长文场景"
    )

    # 文档长度阈值(字符数),超过此值将触发总结
    # 默认值基于AdCleaningLLMConfig的context_window(200K tokens),
    # 考虑到token/字符比约为1:2(中文),设置为100000字符(约50K tokens),留出安全余量
    max_tokens: int = Field(
        default=100000, gt=0, description="文档长度阈值(字符数),超过此值将触发总结"
    )

    # 分段大小(字符数),用于分段总结
    chunk_size: int = Field(
        default=50000, gt=0, description="分段大小(字符数),用于分段总结"
    )

    # 分段重叠大小(字符数),确保上下文连贯
    overlap_size: int = Field(
        default=5000, ge=0, description="分段重叠大小(字符数),确保上下文连贯"
    )

    # 是否基于模型token计数进行判断(True)或基于字符数判断(False)
    # 默认False,使用字符数判断(更简单快速)
    use_token_counting: bool = Field(
        default=False,
        description="是否基于模型token计数进行判断,默认False使用字符数判断",
    )

    # 安全余量比例(0.0-1.0),用于在模型context_window基础上留出安全余量
    # 例如,如果context_window=200000,safety_margin=0.2,则实际阈值=200000*0.8=160000
    safety_margin: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="安全余量比例,在模型context_window基础上留出安全余量",
    )


class TextCleaningConfig(BaseModel):
    """文本清洗配置"""

    model_config = ConfigDict(extra="ignore")

    # 基础配置
    cleaning_level: str = Field(
        default="standard", description="清洗级别(basic/standard/deep)"
    )
    enable_archiving: bool = Field(default=True, description="是否启用文件归档功能")

    # 目录配置
    archive_dir: Path = Field(
        default=Path("./data/archive/mineru"), description="归档目录"
    )
    cleaned_dir: Path = Field(default=Path("./data/cleaned"), description="清洗后目录")

    # 清洗规则配置
    enable_unicode_normalization: bool = Field(
        default=True, description="是否启用Unicode标准化"
    )
    enable_zero_width_removal: bool = Field(
        default=True, description="是否去除零宽字符"
    )
    enable_whitespace_normalization: bool = Field(
        default=True, description="是否标准化空白字符"
    )
    enable_punctuation_standardization: bool = Field(
        default=True, description="是否标准化标点符号"
    )
    enable_ocr_noise_removal: bool = Field(default=True, description="是否去除OCR噪声")
    enable_page_number_removal: bool = Field(
        default=True, description="是否去除页码残留"
    )
    enable_paragraph_merging: bool = Field(default=True, description="是否启用段落合并")
    enable_word_break_fix: bool = Field(default=True, description="是否修复断词")

    # 阈值配置
    short_line_threshold: int = Field(default=10, gt=0, description="短行阈值(字符数)")
    max_consecutive_spaces: int = Field(default=2, gt=0, description="最大连续空格数")
    max_consecutive_punctuation: int = Field(
        default=2, gt=0, description="最大连续标点符号数"
    )

    # 性能配置
    max_file_size_mb: int = Field(default=500, gt=0, description="最大文件大小(MB)")
    batch_size: int = Field(default=10, gt=0, description="批处理大小")
    timeout: int = Field(default=300, gt=0, description="处理超时时间(秒)")


class DocumentConfig(BaseModel):
    """文档处理配置"""

    # 上传配置
    max_upload_size: int = Field(
        default=10485760, gt=0, description="最大上传大小(字节)"
    )
    allowed_extensions: list[str] = Field(
        default=["pdf", "docx", "html", "txt", "md"], description="允许的文件扩展名"
    )
    upload_temp_dir: Path = Field(
        default=Path("./data/temp/uploads"), description="临时上传目录"
    )

    # 解析配置
    pdf_parser: str = Field(default="pdfplumber", description="PDF 解析器")
    html_parser: str = Field(default="beautifulsoup4", description="HTML 解析器")
    docx_parser: str = Field(
        default="mineru", description="DOCX 解析器(默认使用MinerU)"
    )

    # OCR 配置
    ocr_enabled: bool = Field(default=True, description="是否启用 OCR")
    ocr_lang: str = Field(default="ch", description="OCR 语言")
    ocr_use_gpu: bool = Field(default=False, description="是否使用 GPU")
    ocr_use_angle_cls: bool = Field(default=True, description="是否使用角度分类")

    # 预处理配置
    chunk_size: int = Field(default=1000, gt=0, description="分块大小")
    chunk_overlap: int = Field(default=200, ge=0, description="分块重叠大小")
    min_chunk_size: int = Field(default=100, gt=0, description="最小分块大小")


class IndexConfig(BaseModel):
    """索引配置"""

    # 向量索引配置
    vector_dimension: int = Field(default=1536, gt=0, description="向量维度")
    vector_metric: str = Field(default="cosine", description="向量距离度量")
    vector_top_k: int = Field(default=10, gt=0, description="向量检索 top-k")

    # BM25 索引配置
    bm25_enabled: bool = Field(default=True, description="是否启用 BM25")
    bm25_k1: float = Field(default=1.5, gt=0, description="BM25 k1 参数")
    bm25_b: float = Field(default=0.75, gt=0, lt=1, description="BM25 b 参数")

    # 元数据索引配置
    metadata_enabled: bool = Field(default=True, description="是否启用元数据索引")
    metadata_fields: list[str] = Field(
        default=["title", "author", "date", "source"], description="元数据字段"
    )

    # 知识图谱配置
    knowledge_graph_enabled: bool = Field(default=True, description="是否启用知识图谱")
    kg_extraction_model: str = Field(default="default", description="知识图谱提取模型")
    kg_max_entities: int = Field(default=1000, gt=0, description="最大实体数")
    kg_max_relations: int = Field(default=5000, gt=0, description="最大关系数")


class AgentConfig(BaseModel):
    """Agent 配置"""

    # 执行配置
    max_iterations: int = Field(default=50, gt=0, description="最大迭代次数")
    max_execution_time: int = Field(default=300, gt=0, description="最大执行时间(秒)")
    enable_memory: bool = Field(default=True, description="是否启用记忆")
    enable_checkpoint: bool = Field(default=True, description="是否启用检查点")

    # LangGraph Checkpointer 配置
    checkpoint_type: str = Field(default="sqlite", description="检查点类型")
    checkpoint_db_path: Path = Field(
        default=Path("./storage/sqlite/checkpoints.db"), description="检查点数据库路径"
    )
    checkpoint_ttl: int = Field(default=86400, gt=0, description="检查点 TTL(秒)")

    # LangMem 记忆配置
    langmem_enabled: bool = Field(default=True, description="是否启用 LangMem")
    langmem_storage_type: str = Field(default="sqlite", description="记忆存储类型")
    langmem_db_path: Path = Field(
        default=Path("./storage/sqlite/memory.db"), description="记忆数据库路径"
    )
    langmem_max_entries: int = Field(default=10000, gt=0, description="最大记忆条目数")


class RetrievalConfig(BaseModel):
    """检索配置"""

    # 混合检索配置
    mode: Literal["hybrid", "vector", "bm25", "metadata"] = Field(
        default="hybrid", description="检索模式"
    )
    vector_weight: float = Field(default=0.6, ge=0.0, le=1.0, description="向量权重")
    bm25_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="BM25 权重")
    metadata_weight: float = Field(
        default=0.1, ge=0.0, le=1.0, description="元数据权重"
    )
    top_k: int = Field(default=10, gt=0, description="检索 top-k")
    rerank_enabled: bool = Field(default=True, description="是否启用重排序")

    # 缓存配置
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl: int = Field(default=3600, gt=0, description="缓存 TTL(秒)")
    cache_max_size: int = Field(default=1000, gt=0, description="缓存最大大小")
    cache_backend: Literal["redis", "memory"] = Field(
        default="redis", description="缓存后端"
    )


class DraftConfig(BaseModel):
    """文稿生成配置"""

    # 生成参数
    max_length: int = Field(default=5000, gt=0, description="最大长度")
    min_length: int = Field(default=500, gt=0, description="最小长度")
    temperature: float = Field(default=0.8, ge=0.0, le=1.0, description="温度参数")
    top_p: float = Field(default=0.9, ge=0.0, le=1.0, description="top-p 参数")
    frequency_penalty: float = Field(
        default=0.5, ge=-2.0, le=2.0, description="频率惩罚"
    )
    presence_penalty: float = Field(
        default=0.5, ge=-2.0, le=2.0, description="存在惩罚"
    )

    # 模板配置
    template_dir: Path = Field(
        default=Path("./data/templates/document_templates"), description="模板目录"
    )
    template_default: str = Field(default="default.md", description="默认模板")


class PerformanceConfig(BaseModel):
    """性能配置"""

    # 并发配置
    max_concurrent_documents: int = Field(default=5, gt=0, description="最大并发文档数")
    max_concurrent_agents: int = Field(default=3, gt=0, description="最大并发 Agent 数")
    max_concurrent_requests: int = Field(default=10, gt=0, description="最大并发请求数")

    # 超时配置
    document_processing_timeout: int = Field(
        default=300, gt=0, description="文档处理超时时间"
    )
    agent_execution_timeout: int = Field(
        default=180, gt=0, description="Agent 执行超时时间"
    )
    api_request_timeout: int = Field(default=60, gt=0, description="API 请求超时时间")

    # 缓存配置
    cache_enabled: bool = Field(default=True, description="是否启用缓存")
    cache_ttl: int = Field(default=3600, gt=0, description="缓存 TTL(秒)")
    cache_max_size: int = Field(default=1000, gt=0, description="缓存最大大小")
    cache_backend: Literal["redis", "memory"] = Field(
        default="redis", description="缓存后端"
    )


class AppConfig(BaseSettings):
    """应用主配置

    整合所有配置项,支持环境变量注入和验证。
    """

    # 环境配置
    environment: Literal["development", "testing", "production"] = Field(
        default="development", description="环境标识"
    )
    testing: bool = Field(default=False, description="是否测试模式")
    debug: bool = Field(default=False, description="是否调试模式")

    # LLM 配置
    llm_provider: Literal["openai_compatible", "gemini", "anthropic"] = Field(
        default="openai_compatible", description="默认 LLM 提供商"
    )
    llm_config: dict[str, Any] | None = Field(default=None, description="LLM 配置")

    # 嵌入和重排序配置
    embedding: EmbeddingConfig = Field(
        default_factory=EmbeddingConfig, description="Embedding 配置"
    )
    rerank: RerankConfig = Field(
        default_factory=RerankConfig, description="Rerank 配置"
    )

    # 数据库配置
    database: DatabaseConfig = Field(
        default_factory=DatabaseConfig, description="数据库配置"
    )

    # Redis 配置
    redis: RedisConfig = Field(default_factory=RedisConfig, description="Redis 配置")

    # Arq 配置
    arq: ArqConfig = Field(default_factory=ArqConfig, description="Arq 配置")

    # API 配置
    api: APIConfig = Field(default_factory=APIConfig, description="API 配置")

    # 日志配置
    log: LogConfig = Field(default_factory=LogConfig, description="日志配置")

    # 文档配置
    document: DocumentConfig = Field(
        default_factory=DocumentConfig, description="文档配置"
    )

    # PaddleOCR 配置
    paddleocr: PaddleOCRConfig = Field(
        default_factory=PaddleOCRConfig, description="PaddleOCR 配置"
    )

    # MinerU 配置
    mineru: MinerUConfig = Field(
        default_factory=MinerUConfig, description="MinerU 配置"
    )

    # 广告清洗LLM配置
    ad_cleaning_llm: AdCleaningLLMConfig = Field(
        default_factory=AdCleaningLLMConfig, description="广告清洗LLM模型配置"
    )

    # 图表转JSON LLM配置
    chart_to_json_llm: ChartToJsonLLMConfig = Field(
        default_factory=ChartToJsonLLMConfig, description="图表转JSON LLM模型配置"
    )

    # 总结中间件配置
    summarization_middleware: SummarizationMiddlewareConfig = Field(
        default_factory=SummarizationMiddlewareConfig, description="总结中间件配置"
    )

    # 文本清洗配置
    text_cleaning: TextCleaningConfig = Field(
        default_factory=TextCleaningConfig, description="文本清洗配置"
    )

    # 索引配置
    index: IndexConfig = Field(default_factory=IndexConfig, description="索引配置")

    # Agent 配置
    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent 配置")

    # 检索配置
    retrieval: RetrievalConfig = Field(
        default_factory=RetrievalConfig, description="检索配置"
    )

    # 文稿配置
    draft: DraftConfig = Field(default_factory=DraftConfig, description="文稿配置")

    # 性能配置
    performance: PerformanceConfig = Field(
        default_factory=PerformanceConfig, description="性能配置"
    )

    # 其他配置
    timezone: str = Field(default="Asia/Shanghai", description="时区")
    encoding: str = Field(default="utf-8", description="字符编码")
    data_dir: Path = Field(default=Path("./data"), description="数据目录")
    storage_dir: Path = Field(default=Path("./storage"), description="存储目录")
    log_dir: Path = Field(default=Path("./data/logs"), description="日志目录")

    # 临时文件清理
    temp_file_cleanup_enabled: bool = Field(
        default=True, description="是否启用临时文件清理"
    )
    temp_file_max_age: int = Field(
        default=3600, gt=0, description="临时文件最大存活时间(秒)"
    )

    # 文件路径分隔符
    path_separator: str = Field(default="/", description="路径分隔符")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("llm_config", mode="before")
    @classmethod
    def validate_llm_config(cls, v: Any, info: ValidationInfo) -> dict[str, Any]:
        """验证 LLM 配置

        从环境变量读取配置,不提供硬编码的默认值。
        所有配置必须通过 .env 文件或环境变量提供。
        """
        import os

        provider = os.getenv("LLM_PROVIDER", "openai_compatible")

        # 根据 provider 构建配置(所有值都从环境变量读取,无硬编码默认值)
        if provider == "openai_compatible":
            base_url = os.getenv("LLM_BASE_URL")
            api_key = os.getenv("LLM_API_KEY")
            model_name = os.getenv("LLM_MODEL_NAME")

            if not api_key:
                msg = "LLM_API_KEY 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)
            if not model_name:
                msg = "LLM_MODEL_NAME 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)
            if not base_url:
                msg = "LLM_BASE_URL 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)

            # 所有配置必须从环境变量读取,无硬编码默认值
            temperature_str = os.getenv("LLM_TEMPERATURE")
            max_tokens_str = os.getenv("LLM_MAX_TOKENS")
            timeout_str = os.getenv("LLM_TIMEOUT")

            if not temperature_str:
                msg = "LLM_TEMPERATURE 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)
            if not max_tokens_str:
                msg = "LLM_MAX_TOKENS 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)
            if not timeout_str:
                msg = "LLM_TIMEOUT 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)

            return {
                "provider": "openai_compatible",
                "base_url": base_url,
                "api_key": api_key,
                "model_name": model_name,
                "temperature": float(temperature_str),
                "max_tokens": int(max_tokens_str),
                "timeout": int(timeout_str),
            }
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            model_name = os.getenv("GEMINI_MODEL_NAME")

            if not api_key:
                msg = "GEMINI_API_KEY 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)
            if not model_name:
                msg = "GEMINI_MODEL_NAME 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)

            # 优先使用 GEMINI_* 配置,否则使用 LLM_* 配置,但都必须设置
            temperature_str = os.getenv("GEMINI_TEMPERATURE") or os.getenv(
                "LLM_TEMPERATURE"
            )
            max_tokens_str = os.getenv("GEMINI_MAX_TOKENS") or os.getenv(
                "LLM_MAX_TOKENS"
            )

            if not temperature_str:
                msg = "GEMINI_TEMPERATURE 或 LLM_TEMPERATURE 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)
            if not max_tokens_str:
                msg = "GEMINI_MAX_TOKENS 或 LLM_MAX_TOKENS 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)

            return {
                "provider": "gemini",
                "api_key": api_key,
                "model_name": model_name,
                "temperature": float(temperature_str),
                "max_tokens": int(max_tokens_str),
            }
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            model_name = os.getenv("ANTHROPIC_MODEL_NAME")

            if not api_key:
                msg = "ANTHROPIC_API_KEY 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)
            if not model_name:
                msg = "ANTHROPIC_MODEL_NAME 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)

            # Anthropic 使用 LLM_* 配置
            temperature_str = os.getenv("LLM_TEMPERATURE")
            max_tokens_str = os.getenv("LLM_MAX_TOKENS")

            if not temperature_str:
                msg = "LLM_TEMPERATURE 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)
            if not max_tokens_str:
                msg = "LLM_MAX_TOKENS 环境变量未设置,请在 .env 文件中配置"
                raise ValueError(msg)

            return {
                "provider": "anthropic",
                "api_key": api_key,
                "model_name": model_name,
                "temperature": float(temperature_str),
                "max_tokens": int(max_tokens_str),
            }

        return v or {}


# 全局配置实例
def load_config(env_file: str | None = None) -> AppConfig:
    """加载配置

    Args:
        env_file: .env 文件路径,如果为 None 则使用默认的 .env 文件
                  Pydantic Settings 会自动从 .env 文件加载环境变量

    Returns:
        AppConfig 实例
    """
    import os

    from dotenv import load_dotenv

    # 总是先加载 .env 文件,确保环境变量可用
    if env_file:
        load_dotenv(env_file, override=True)
    else:
        # 尝试加载项目根目录的 .env 文件
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(env_path, override=True)

    # 加载配置(AppConfig 会自动从环境变量和 .env 文件加载)
    # model_config 中已配置 env_file='.env',会自动加载项目根目录的 .env 文件
    config = AppConfig()

    # 手动从环境变量加载嵌套配置(因为嵌套配置需要特殊处理)

    # 加载 Embedding 配置
    embedding_api_key = os.getenv("EMBEDDING_API_KEY")
    if embedding_api_key:
        config.embedding.api_key = embedding_api_key
    embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME")
    if embedding_model_name:
        config.embedding.model_name = embedding_model_name
    embedding_provider = os.getenv("EMBEDDING_PROVIDER")
    if embedding_provider:
        config.embedding.provider = embedding_provider  # type: ignore
    embedding_dimension = os.getenv("EMBEDDING_DIMENSION")
    if embedding_dimension:
        config.embedding.dimension = int(embedding_dimension)
    embedding_batch_size = os.getenv("EMBEDDING_BATCH_SIZE")
    if embedding_batch_size:
        config.embedding.batch_size = int(embedding_batch_size)

    # 加载 Rerank 配置
    rerank_api_key = os.getenv("RERANK_API_KEY")
    if rerank_api_key:
        config.rerank.api_key = rerank_api_key
    rerank_model_name = os.getenv("RERANK_MODEL_NAME")
    if rerank_model_name:
        config.rerank.model_name = rerank_model_name
    rerank_provider = os.getenv("RERANK_PROVIDER")
    if rerank_provider:
        config.rerank.provider = rerank_provider  # type: ignore
    rerank_top_k = os.getenv("RERANK_TOP_K")
    if rerank_top_k:
        config.rerank.top_k = int(rerank_top_k)

    # 加载 PaddleOCR 配置
    paddleocr_api_url = os.getenv("PADDLEOCR_API_URL")
    if paddleocr_api_url:
        config.paddleocr.api_url = paddleocr_api_url
    paddleocr_token = os.getenv("PADDLEOCR_TOKEN")
    if paddleocr_token:
        config.paddleocr.token = paddleocr_token
    paddleocr_timeout = os.getenv("PADDLEOCR_TIMEOUT")
    if paddleocr_timeout:
        config.paddleocr.timeout = int(paddleocr_timeout)
    paddleocr_max_retries = os.getenv("PADDLEOCR_MAX_RETRIES")
    if paddleocr_max_retries:
        config.paddleocr.max_retries = int(paddleocr_max_retries)

    # 加载 MinerU 配置
    mineru_api_key = os.getenv("MINERU_API_KEY")
    if mineru_api_key:
        config.mineru.api_key = mineru_api_key
    mineru_api_url = os.getenv("MINERU_API_URL")
    if mineru_api_url:
        config.mineru.api_url = mineru_api_url
    mineru_timeout = os.getenv("MINERU_TIMEOUT")
    if mineru_timeout:
        config.mineru.timeout = int(mineru_timeout)
    mineru_max_retries = os.getenv("MINERU_MAX_RETRIES")
    if mineru_max_retries:
        config.mineru.max_retries = int(mineru_max_retries)
    mineru_max_file_size_mb = os.getenv("MINERU_MAX_FILE_SIZE_MB")
    if mineru_max_file_size_mb:
        config.mineru.max_file_size_mb = int(mineru_max_file_size_mb)
    mineru_max_pages = os.getenv("MINERU_MAX_PAGES")
    if mineru_max_pages:
        config.mineru.max_pages = int(mineru_max_pages)

    # 加载广告清洗LLM配置(清理零宽字符,确保配置值安全)
    import re
    import unicodedata

    def clean_config_value(value: str) -> str:
        """清理配置值中的零宽字符"""
        if not value:
            return value
        # Unicode标准化
        value = unicodedata.normalize("NFKC", value)
        # 清理零宽字符
        value = re.sub(
            r"[\u200b-\u200f\uFEFF\uFFFD\u202a-\u202e\u2060-\u206f]", "", value
        )
        # 去除首尾空白
        value = value.strip()
        return value

    ad_cleaning_llm_base_url = os.getenv("AD_CLEANING_LLM_BASE_URL")
    if ad_cleaning_llm_base_url:
        config.ad_cleaning_llm.base_url = clean_config_value(ad_cleaning_llm_base_url)
    ad_cleaning_llm_api_key = os.getenv("AD_CLEANING_LLM_API_KEY")
    if ad_cleaning_llm_api_key:
        config.ad_cleaning_llm.api_key = clean_config_value(ad_cleaning_llm_api_key)
    ad_cleaning_llm_model_name = os.getenv("AD_CLEANING_LLM_MODEL_NAME")
    if ad_cleaning_llm_model_name:
        config.ad_cleaning_llm.model_name = clean_config_value(
            ad_cleaning_llm_model_name
        )
    ad_cleaning_llm_temperature = os.getenv("AD_CLEANING_LLM_TEMPERATURE")
    if ad_cleaning_llm_temperature:
        config.ad_cleaning_llm.temperature = float(ad_cleaning_llm_temperature)
    ad_cleaning_llm_max_tokens = os.getenv("AD_CLEANING_LLM_MAX_TOKENS")
    if ad_cleaning_llm_max_tokens:
        config.ad_cleaning_llm.max_tokens = int(ad_cleaning_llm_max_tokens)
    ad_cleaning_llm_context_window = os.getenv("AD_CLEANING_LLM_CONTEXT_WINDOW")
    if ad_cleaning_llm_context_window:
        config.ad_cleaning_llm.context_window = int(ad_cleaning_llm_context_window)
    ad_cleaning_llm_timeout = os.getenv("AD_CLEANING_LLM_TIMEOUT")
    if ad_cleaning_llm_timeout:
        config.ad_cleaning_llm.timeout = int(ad_cleaning_llm_timeout)

    # 加载图表转JSON LLM配置(清理零宽字符,确保配置值安全)
    chart_to_json_llm_base_url = os.getenv("CHART_TO_JSON_LLM_BASE_URL")
    if chart_to_json_llm_base_url:
        config.chart_to_json_llm.base_url = clean_config_value(
            chart_to_json_llm_base_url
        )
    chart_to_json_llm_api_key = os.getenv("CHART_TO_JSON_LLM_API_KEY")
    if chart_to_json_llm_api_key:
        config.chart_to_json_llm.api_key = clean_config_value(chart_to_json_llm_api_key)
    chart_to_json_llm_model_name = os.getenv("CHART_TO_JSON_LLM_MODEL_NAME")
    if chart_to_json_llm_model_name:
        config.chart_to_json_llm.model_name = clean_config_value(
            chart_to_json_llm_model_name
        )
    chart_to_json_llm_temperature = os.getenv("CHART_TO_JSON_LLM_TEMPERATURE")
    if chart_to_json_llm_temperature:
        config.chart_to_json_llm.temperature = float(chart_to_json_llm_temperature)
    chart_to_json_llm_max_tokens = os.getenv("CHART_TO_JSON_LLM_MAX_TOKENS")
    if chart_to_json_llm_max_tokens:
        config.chart_to_json_llm.max_tokens = int(chart_to_json_llm_max_tokens)
    chart_to_json_llm_timeout = os.getenv("CHART_TO_JSON_LLM_TIMEOUT")
    if chart_to_json_llm_timeout:
        config.chart_to_json_llm.timeout = int(chart_to_json_llm_timeout)
    chart_to_json_llm_supports_vision = os.getenv("CHART_TO_JSON_LLM_SUPPORTS_VISION")
    if chart_to_json_llm_supports_vision:
        config.chart_to_json_llm.supports_vision = (
            chart_to_json_llm_supports_vision.lower() in ("true", "1", "yes")
        )
    chart_to_json_llm_confidence_threshold = os.getenv(
        "CHART_TO_JSON_LLM_CONFIDENCE_THRESHOLD"
    )
    if chart_to_json_llm_confidence_threshold:
        config.chart_to_json_llm.confidence_threshold = float(
            chart_to_json_llm_confidence_threshold
        )

    # GLM-4.6V 特定配置
    chart_to_json_llm_provider = os.getenv("CHART_TO_JSON_LLM_PROVIDER")
    if chart_to_json_llm_provider:
        config.chart_to_json_llm.provider = chart_to_json_llm_provider  # type: ignore
    chart_to_json_llm_enable_streaming = os.getenv("CHART_TO_JSON_LLM_ENABLE_STREAMING")
    if chart_to_json_llm_enable_streaming:
        config.chart_to_json_llm.enable_streaming = (
            chart_to_json_llm_enable_streaming.lower() in ("true", "1", "yes")
        )
    chart_to_json_llm_enable_thinking = os.getenv("CHART_TO_JSON_LLM_ENABLE_THINKING")
    if chart_to_json_llm_enable_thinking:
        config.chart_to_json_llm.enable_thinking = (
            chart_to_json_llm_enable_thinking.lower() in ("true", "1", "yes")
        )
    chart_to_json_llm_max_retries = os.getenv("CHART_TO_JSON_LLM_MAX_RETRIES")
    if chart_to_json_llm_max_retries:
        config.chart_to_json_llm.max_retries = int(chart_to_json_llm_max_retries)
    chart_to_json_llm_retry_delay = os.getenv("CHART_TO_JSON_LLM_RETRY_DELAY")
    if chart_to_json_llm_retry_delay:
        config.chart_to_json_llm.retry_delay = float(chart_to_json_llm_retry_delay)

    # 加载总结中间件配置
    summarization_enabled = os.getenv("SUMMARIZATION_MIDDLEWARE_ENABLED")
    if summarization_enabled:
        config.summarization_middleware.enabled = summarization_enabled.lower() in (
            "true",
            "1",
            "yes",
        )
    summarization_max_tokens = os.getenv("SUMMARIZATION_MIDDLEWARE_MAX_TOKENS")
    if summarization_max_tokens:
        config.summarization_middleware.max_tokens = int(summarization_max_tokens)
    summarization_chunk_size = os.getenv("SUMMARIZATION_MIDDLEWARE_CHUNK_SIZE")
    if summarization_chunk_size:
        config.summarization_middleware.chunk_size = int(summarization_chunk_size)
    summarization_overlap_size = os.getenv("SUMMARIZATION_MIDDLEWARE_OVERLAP_SIZE")
    if summarization_overlap_size:
        config.summarization_middleware.overlap_size = int(summarization_overlap_size)
    summarization_use_token_counting = os.getenv(
        "SUMMARIZATION_MIDDLEWARE_USE_TOKEN_COUNTING"
    )
    if summarization_use_token_counting:
        config.summarization_middleware.use_token_counting = (
            summarization_use_token_counting.lower() in ("true", "1", "yes")
        )
    summarization_safety_margin = os.getenv("SUMMARIZATION_MIDDLEWARE_SAFETY_MARGIN")
    if summarization_safety_margin:
        config.summarization_middleware.safety_margin = float(
            summarization_safety_margin
        )

    return config


# 默认配置实例(延迟加载)
_default_config: AppConfig | None = None


def get_config() -> AppConfig:
    """获取默认配置实例

    Returns:
        AppConfig 实例
    """
    global _default_config
    if _default_config is None:
        _default_config = load_config()
    return _default_config


def get_chart_to_json_llm_config() -> ChartToJsonLLMConfig:
    """获取图表转JSON LLM配置

    Returns:
        ChartToJsonLLMConfig 实例
    """
    config = get_config()
    return config.chart_to_json_llm
