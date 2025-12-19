# 数据模型: 多 Agent 协作的文档处理与生成系统

**创建时间**: 2025-12-05
**状态**: 完成

## 概述

本文档定义系统的核心数据模型，包括实体、字段、关系和验证规则。数据模型基于功能规范中的关键实体定义，并考虑技术实现细节。

---

## 核心实体

### 1. Document (文档)

**存储**: SQLite

**描述**: 用户上传的原始文档文件及其元数据

**字段**:
- `id` (UUID, Primary Key): 文档唯一标识
- `filename` (String, Required): 原始文件名
- `file_path` (String, Required): 文件存储路径
- `file_size` (Integer): 文件大小（字节）
- `mime_type` (String): MIME类型（如 application/pdf, text/html）
- `format` (Enum: PDF, HTML, DOCX): 文档格式（MVP版本）
- `uploaded_at` (DateTime): 上传时间
- `uploaded_by` (UUID, Foreign Key → User.id): 上传用户
- `status` (Enum: PENDING, PARSING, INDEXED, FAILED): 处理状态
- `parsed_at` (DateTime, Nullable): 解析完成时间
- `error_message` (String, Nullable): 错误信息（如果解析失败）
- `metadata` (JSON): 扩展元数据（标题、作者、创建时间等）

**关系**:
- 一对多: Document → KnowledgeEntry
- 一对多: Document → DocumentChunk

**验证规则**:
- filename不能为空
- file_size必须大于0
- format必须是PDF、HTML或DOCX（MVP版本）
- status转换必须遵循状态机: PENDING → PARSING → INDEXED/FAILED

**索引**:
- `uploaded_by` (外键索引)
- `status` (状态索引，用于查询待处理文档)
- `uploaded_at` (时间索引，用于排序)

---

### 2. DocumentChunk (文档块)

**存储**: SQLite + Chroma

**描述**: 文档解析后的文本块，用于索引和检索

**字段**:
- `id` (UUID, Primary Key): 块唯一标识
- `document_id` (UUID, Foreign Key → Document.id): 所属文档
- `chunk_index` (Integer): 块在文档中的序号
- `content` (Text): 块文本内容
- `start_position` (Integer): 在原始文档中的起始位置
- `end_position` (Integer): 在原始文档中的结束位置
- `section_path` (String): 章节路径（如 "1.2.3"）
- `section_title` (String, Nullable): 章节标题
- `metadata` (JSON): 块元数据（段落类型、样式等）
- `created_at` (DateTime): 创建时间

**关系**:
- 多对一: DocumentChunk → Document
- 一对多: DocumentChunk → VectorEmbedding
- 一对多: DocumentChunk → GraphEntity (如果块中包含实体)

**验证规则**:
- content不能为空
- start_position < end_position
- chunk_index必须唯一（在同一文档内）

**索引**:
- `document_id` (外键索引)
- `section_path` (章节路径索引，用于BM25检索)
- Chroma向量索引（通过chunk_id关联）

---

### 3. VectorEmbedding (向量嵌入)

**存储**: Chroma

**描述**: 文档块的向量表示，用于语义检索

**字段**:
- `chunk_id` (UUID, Foreign Key → DocumentChunk.id): 关联的文档块
- `embedding` (Vector, Dimension: 768/1536): 向量嵌入（维度取决于模型）
- `model_name` (String): 使用的嵌入模型名称
- `created_at` (DateTime): 创建时间

**关系**:
- 多对一: VectorEmbedding → DocumentChunk

**验证规则**:
- embedding维度必须与模型匹配
- model_name不能为空

**存储方式**:
- 存储在Chroma向量数据库中
- 通过chunk_id与SQLite中的DocumentChunk关联

---

### 4. KnowledgeEntry (知识库条目)

**存储**: SQLite

**描述**: 知识库中的条目，关联文档块和检索结果。知识库支持多种数据源：1) 用户上传的文档（通过Document和DocumentChunk）；2) 网络检索数据（通过WebDataSource，已建立索引并进入知识库）

**字段**:
- `id` (UUID, Primary Key): 条目唯一标识
- `document_id` (UUID, Foreign Key → Document.id, Nullable): 来源文档（如果是用户上传的文档）
- `chunk_id` (UUID, Foreign Key → DocumentChunk.id, Nullable): 关联的文档块（如果是用户上传的文档）
- `web_data_source_id` (UUID, Foreign Key → WebDataSource.id, Nullable): 来源网络数据源（如果是网络检索数据）
- `title` (String): 条目标题
- `summary` (Text, Nullable): 条目摘要
- `tags` (Array[String]): 标签列表
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**关系**:
- 多对一: KnowledgeEntry → Document (可选，如果是用户上传的文档)
- 多对一: KnowledgeEntry → DocumentChunk (可选，如果是用户上传的文档)
- 多对一: KnowledgeEntry → WebDataSource (可选，如果是网络检索数据)
- 一对多: KnowledgeEntry → RetrievalResult

**验证规则**:
- title不能为空
- document_id和chunk_id必须同时存在或同时为空（如果是用户上传的文档）
- web_data_source_id必须存在（如果是网络检索数据）
- document_id和web_data_source_id不能同时为空（必须有一个数据源）

**索引**:
- `document_id` (外键索引)
- `chunk_id` (外键索引)
- `tags` (标签索引，用于元数据检索)

---

### 5. GraphEntity (图谱实体)

**存储**: NetworkX (内存) + SQLite (持久化)

**描述**: 知识图谱中的实体节点

**字段**:
- `id` (UUID, Primary Key): 实体唯一标识
- `name` (String, Required): 实体名称
- `type` (Enum: PERSON, CONCEPT, EVENT, ORGANIZATION, OTHER): 实体类型
- `description` (Text, Nullable): 实体描述
- `properties` (JSON): 扩展属性
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**关系**:
- 一对多: GraphEntity → GraphRelation (作为源实体)
- 一对多: GraphEntity → GraphRelation (作为目标实体)
- 多对多: GraphEntity → DocumentChunk (通过关系表)

**验证规则**:
- name不能为空
- type必须是预定义的枚举值

**存储方式**:
- NetworkX: 作为图节点存储，支持图查询
- SQLite: 持久化实体元数据

---

### 6. GraphRelation (图谱关系)

**存储**: NetworkX (内存) + SQLite (持久化)

**描述**: 知识图谱中的关系边

**字段**:
- `id` (UUID, Primary Key): 关系唯一标识
- `source_entity_id` (UUID, Foreign Key → GraphEntity.id): 源实体
- `target_entity_id` (UUID, Foreign Key → GraphEntity.id): 目标实体
- `relation_type` (String): 关系类型（如 "包含", "属于", "相关"）
- `weight` (Float, Default: 1.0): 关系权重
- `properties` (JSON): 扩展属性
- `created_at` (DateTime): 创建时间

**关系**:
- 多对一: GraphRelation → GraphEntity (source)
- 多对一: GraphRelation → GraphEntity (target)

**验证规则**:
- source_entity_id ≠ target_entity_id（不能自环，除非关系类型允许）
- relation_type不能为空
- weight >= 0

**存储方式**:
- NetworkX: 作为图边存储，支持图查询
- SQLite: 持久化关系元数据

---

### 7. GlobalConstraints (硬性规范条件)

**存储**: SQLite

**描述**: 整份白皮书的硬性规则和约束条件，作为后续所有Agent的强约束条件

**字段**:
- `id` (UUID, Primary Key): 规范条件唯一标识
- `user_id` (UUID, Foreign Key → User.id): 创建用户
- `report_type` (Enum: MARKET_RESEARCH, POLICY_COMPARISON, TECHNOLOGY_ASSESSMENT, OTHER): 报告类型
- `platform_knowledge_base_id` (UUID, Foreign Key → KnowledgeBase.id, Nullable): 平台内置用户知识库ID
- `language` (Enum: CHINESE, ENGLISH): 报告语言
- `target_length` (Integer, Nullable): 报告长度目标（字数）
- `target_pages` (Integer, Nullable): 报告长度目标（页数）
- `require_charts` (Boolean, Default: False): 是否必须包含图表
- `style_guide` (JSON, Nullable): 风格指南（写作风格、格式要求等）
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**关系**:
- 多对一: GlobalConstraints → User
- 多对一: GlobalConstraints → KnowledgeBase (可选)
- 一对多: GlobalConstraints → Outline (使用该规范条件的大纲)
- 一对多: GlobalConstraints → Draft (使用该规范条件生成的文稿)

**验证规则**:
- report_type必须是预定义的枚举值
- language必须是预定义的枚举值
- target_length和target_pages至少有一个不为空

**索引**:
- `user_id` (外键索引)
- `report_type` (报告类型索引)

---

### 8. Outline (大纲)

**存储**: SQLite

**描述**: 用户输入的文档大纲，必须遵循硬性规范条件

**字段**:
- `id` (UUID, Primary Key): 大纲唯一标识
- `user_id` (UUID, Foreign Key → User.id): 创建用户
- `constraints_id` (UUID, Foreign Key → GlobalConstraints.id): 关联的硬性规范条件
- `title` (String): 大纲标题
- `structure` (JSON): 大纲结构（章节树）
- `original_structure` (JSON, Nullable): 原始结构（优化前）
- `status` (Enum: DRAFT, OPTIMIZED, USED): 状态
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**关系**:
- 多对一: Outline → User
- 多对一: Outline → GlobalConstraints
- 一对一: Outline → OptimizedOutline (可选)
- 一对多: Outline → Draft (生成的文稿)

**验证规则**:
- structure必须是有效的JSON结构
- structure必须包含至少一个章节
- constraints_id必须有效

**索引**:
- `user_id` (外键索引)
- `constraints_id` (外键索引)
- `status` (状态索引)

---

### 9. OptimizedOutline (优化后大纲)

**存储**: SQLite

**描述**: 经过结构优化的大纲

**字段**:
- `id` (UUID, Primary Key): 优化大纲唯一标识
- `outline_id` (UUID, Foreign Key → Outline.id): 原始大纲
- `optimized_structure` (JSON): 优化后的结构
- `optimization_suggestions` (JSON): 优化建议列表
- `applied_suggestions` (Array[String]): 已应用的建议ID
- `created_at` (DateTime): 创建时间

**关系**:
- 一对一: OptimizedOutline → Outline

**验证规则**:
- optimized_structure必须包含所有原始章节（除非明确删除）
- optimization_suggestions必须是非空数组

---

### 10. SourceMatch (信息源匹配结果)

**存储**: SQLite

**描述**: 信息源排名Agent的输出，包含匹配的信息源列表和相关度评分

**字段**:
- `id` (UUID, Primary Key): 匹配结果唯一标识
- `outline_node_id` (String): 关联的大纲节点ID
- `source_type` (Enum: PLATFORM_LIB, LOCAL_KB, UPLOADED_DOC, CUSTOM_WEBSITE): 信息源类型
- `source_id` (UUID): 信息源ID（文档ID、知识库条目ID等）
- `source_url` (String, Nullable): 信息源URL（如果是网站）
- `source_path` (String, Nullable): 信息源文件路径（如果是本地文件）
- `relevance_score` (Float): 相关度评分（语义相似度+关键词匹配度+来源可信度）
- `semantic_similarity` (Float): 语义相似度
- `keyword_overlap` (Float): 关键词匹配度
- `source_reliability` (Float): 来源可信度
- `trust_score` (Float, Default: 0.5): 信任度评分（用户反馈影响）
- `snippet` (Text): 内容片段预览
- `highlighted_keywords` (Array[String]): 高亮关键词列表
- `paragraph_position` (String, Nullable): 段落位置（章节、页码等）
- `rank` (Integer): 排名
- `created_at` (DateTime): 创建时间

**关系**:
- 多对一: SourceMatch → Document (如果source_type是UPLOADED_DOC)
- 多对一: SourceMatch → KnowledgeEntry (如果source_type是LOCAL_KB)
- 一对多: SourceMatch → SourceFeedback (用户反馈)

**验证规则**:
- relevance_score必须在 [0.0, 1.0] 范围内
- trust_score必须在 [0.0, 1.0] 范围内
- rank必须 >= 1
- source_type和source_id必须匹配

**索引**:
- `outline_node_id` (大纲节点索引)
- `source_type` (信息源类型索引)
- `relevance_score` (相关度评分索引，用于排序)
- `trust_score` (信任度评分索引)

---

### 11. SourceFeedback (信息源反馈)

**存储**: SQLite

**描述**: 用户对信息源的选择反馈，用于优化排名模型和用户定制化知识偏好

**字段**:
- `id` (UUID, Primary Key): 反馈唯一标识
- `user_id` (UUID, Foreign Key → User.id): 反馈用户
- `source_match_id` (UUID, Foreign Key → SourceMatch.id): 关联的信息源匹配结果
- `action` (Enum: SELECTED, REJECTED): 用户操作（勾选/拒绝）
- `preference_score` (Float): 偏好评分（用于用户定制化知识偏好）
- `feedback_metadata` (JSON, Nullable): 扩展反馈元数据
- `created_at` (DateTime): 创建时间

**关系**:
- 多对一: SourceFeedback → User
- 多对一: SourceFeedback → SourceMatch

**验证规则**:
- action必须是预定义的枚举值
- preference_score必须在 [0.0, 1.0] 范围内

**索引**:
- `user_id` (外键索引)
- `source_match_id` (外键索引)
- `action` (操作类型索引)

---

### 12. CustomDataSource (自定义数据源)

**存储**: SQLite

**描述**: 用户添加的网站数据源。系统自动爬取该域名指定深度内容，提取正文、去噪，建立页面级和段落级索引，索引后的内容进入知识库（通过WebDataSource实体），与本地知识库统一检索

**字段**:
- `id` (UUID, Primary Key): 数据源唯一标识
- `user_id` (UUID, Foreign Key → User.id): 创建用户
- `domain` (String): 网站域名
- `crawl_depth` (Integer, Default: 2): 爬取深度
- `index_status` (Enum: PENDING, CRAWLING, INDEXING, COMPLETED, FAILED): 索引状态
- `trust_score` (Float, Default: 0.7): 信任度评分（用户添加的默认提升）
- `indexed_pages` (Integer, Default: 0): 已索引页面数
- `indexed_paragraphs` (Integer, Default: 0): 已索引段落数
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间
- `completed_at` (DateTime, Nullable): 完成时间

**关系**:
- 多对一: CustomDataSource → User
- 一对多: CustomDataSource → SourceMatch (作为信息源)

**验证规则**:
- domain必须是有效的域名格式
- crawl_depth必须 >= 1
- trust_score必须在 [0.0, 1.0] 范围内

**索引**:
- `user_id` (外键索引)
- `domain` (域名索引)
- `index_status` (索引状态索引)

---

### 12A. WebDataSource (网络数据源)

**存储**: SQLite

**描述**: 通过信息源爬取任务获取的网络数据源，已建立索引并进入知识库。与本地知识库统一检索。

**字段**:
- `id` (UUID, Primary Key): 数据源唯一标识
- `custom_data_source_id` (UUID, Foreign Key → CustomDataSource.id, Nullable): 关联的自定义数据源（如果是用户添加的）
- `url` (String, Required): 网页URL
- `title` (String): 网页标题
- `content` (Text): 提取的正文内容
- `extracted_at` (DateTime): 提取时间
- `indexed_at` (DateTime, Nullable): 索引完成时间
- `status` (Enum: PENDING, EXTRACTED, INDEXED, FAILED): 处理状态
- `metadata` (JSON): 扩展元数据（作者、发布时间、关键词等）

**关系**:
- 多对一: WebDataSource → CustomDataSource (可选)
- 一对多: WebDataSource → KnowledgeEntry (作为知识库条目)
- 一对多: WebDataSource → SourceMatch (作为信息源)

**验证规则**:
- url必须是有效的URL格式
- content不能为空（提取成功后）
- status转换必须遵循状态机: PENDING → EXTRACTED → INDEXED/FAILED

**索引**:
- `custom_data_source_id` (外键索引)
- `url` (URL索引，用于去重)
- `status` (状态索引)
- `indexed_at` (时间索引)

---

### 13. RetrievalQuery (检索查询)

**存储**: SQLite (可选，用于历史记录)

**描述**: 用户的检索查询请求

**字段**:
- `id` (UUID, Primary Key): 查询唯一标识
- `user_id` (UUID, Foreign Key → User.id): 查询用户
- `query_text` (String): 查询文本
- `query_type` (Enum: VECTOR, BM25, METADATA, GRAPH, HYBRID): 检索类型
- `filters` (JSON, Nullable): 筛选条件（文档类型、时间范围等）
- `created_at` (DateTime): 查询时间

**关系**:
- 多对一: RetrievalQuery → User
- 一对多: RetrievalQuery → RetrievalResult

**验证规则**:
- query_text不能为空
- query_type必须是预定义的枚举值

---

### 14. RetrievalResult (检索结果)

**存储**: SQLite (临时存储，用于结果缓存)

**描述**: 检索查询的结果

**字段**:
- `id` (UUID, Primary Key): 结果唯一标识
- `query_id` (UUID, Foreign Key → RetrievalQuery.id): 关联查询
- `knowledge_entry_id` (UUID, Foreign Key → KnowledgeEntry.id): 关联知识条目
- `chunk_id` (UUID, Foreign Key → DocumentChunk.id): 关联文档块
- `relevance_score` (Float): 相关性评分 (0.0 - 1.0)
- `retrieval_method` (String): 检索方法（vector/bm25/graph/metadata）
- `rank` (Integer): 结果排名
- `created_at` (DateTime): 创建时间

**关系**:
- 多对一: RetrievalResult → RetrievalQuery
- 多对一: RetrievalResult → KnowledgeEntry
- 多对一: RetrievalResult → DocumentChunk

**验证规则**:
- relevance_score必须在 [0.0, 1.0] 范围内
- rank必须 >= 1

**索引**:
- `query_id` (外键索引)
- `relevance_score` (用于排序)

---

### 15. Draft (文稿草稿)

**存储**: SQLite + 文件系统

**描述**: 系统生成的文稿草稿，包含完整内容、结构、引用信息、图表占位符

**字段**:
- `id` (UUID, Primary Key): 文稿唯一标识
- `user_id` (UUID, Foreign Key → User.id): 创建用户
- `outline_id` (UUID, Foreign Key → Outline.id): 关联大纲
- `constraints_id` (UUID, Foreign Key → GlobalConstraints.id): 关联的硬性规范条件
- `title` (String): 文稿标题
- `content` (Text): 文稿内容（Markdown格式）
- `file_path` (String, Nullable): 文件存储路径（如果导出）
- `status` (Enum: DRAFT, POLISHED, FINAL): 状态
- `citations` (JSON): 引用信息列表
- `chart_placeholders` (JSON): 图表占位符列表
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间
- `polished_at` (DateTime, Nullable): 润色完成时间

**关系**:
- 多对一: Draft → User
- 多对一: Draft → Outline
- 多对一: Draft → GlobalConstraints
- 一对多: Draft → DraftVersion (版本历史)
- 一对多: Draft → ChartConfig (图表配置)

**验证规则**:
- content不能为空
- citations必须是有效的引用列表
- chart_placeholders必须是有效的图表占位符列表

**索引**:
- `user_id` (外键索引)
- `outline_id` (外键索引)
- `constraints_id` (外键索引)
- `status` (状态索引)

---

### 16. ChartConfig (图表配置)

**存储**: SQLite

**描述**: 文稿中的图表配置，包含图表类型、数据源、DSL配置等

**字段**:
- `id` (UUID, Primary Key): 图表配置唯一标识
- `draft_id` (UUID, Foreign Key → Draft.id): 关联的文稿
- `chart_type` (Enum: BAR, LINE, PIE, SCATTER, TABLE, OTHER): 图表类型
- `data_source` (JSON): 数据源（从检索数据中识别的结构化内容）
- `dsl_config` (JSON): 图表DSL配置（如ECharts JSON）
- `placeholder_position` (Integer): 在文稿中的占位符位置
- `is_editable` (Boolean, Default: True): 是否可编辑
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**关系**:
- 多对一: ChartConfig → Draft

**验证规则**:
- chart_type必须是预定义的枚举值
- data_source必须是有效的JSON结构
- dsl_config必须是有效的图表DSL配置
- placeholder_position必须 >= 0

**索引**:
- `draft_id` (外键索引)
- `chart_type` (图表类型索引)

---

### 17. DraftEditState (草稿编辑界面状态)

**存储**: SQLite (可选，用于持久化编辑状态)

**描述**: 草稿编辑界面的状态，包含左侧信息源管理区、右侧AI检索、中间智能分析的状态

**字段**:
- `id` (UUID, Primary Key): 状态唯一标识
- `draft_id` (UUID, Foreign Key → Draft.id): 关联的文稿
- `user_id` (UUID, Foreign Key → User.id): 编辑用户
- `left_panel_state` (JSON): 左侧信息源管理区状态（展示的信息源、高亮的来源等）
- `right_panel_state` (JSON): 右侧AI检索模块状态（检索历史、结果等）
- `middle_panel_state` (JSON): 中间智能分析状态（修改建议、评分等）
- `last_updated_at` (DateTime): 最后更新时间

**关系**:
- 多对一: DraftEditState → Draft
- 多对一: DraftEditState → User

**验证规则**:
- left_panel_state、right_panel_state、middle_panel_state必须是有效的JSON结构

**索引**:
- `draft_id` (外键索引)
- `user_id` (外键索引)

**存储**: SQLite + 文件系统

**描述**: 系统生成的文稿草稿

**字段**:
- `id` (UUID, Primary Key): 文稿唯一标识
- `user_id` (UUID, Foreign Key → User.id): 创建用户
- `outline_id` (UUID, Foreign Key → Outline.id): 关联大纲
- `title` (String): 文稿标题
- `content` (Text): 文稿内容（Markdown格式）
- `file_path` (String, Nullable): 文件存储路径（如果导出）
- `status` (Enum: DRAFT, POLISHED, FINAL): 状态
- `citations` (JSON): 引用信息列表
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间
- `polished_at` (DateTime, Nullable): 润色完成时间

**关系**:
- 多对一: Draft → User
- 多对一: Draft → Outline
- 一对多: Draft → DraftVersion (版本历史)

**验证规则**:
- content不能为空
- citations必须是有效的引用列表

**索引**:
- `user_id` (外键索引)
- `outline_id` (外键索引)
- `status` (状态索引)

---

### 18. DocumentTemplate (文档模板)

**存储**: SQLite

**描述**: 预定义的文档格式模板

**字段**:
- `id` (UUID, Primary Key): 模板唯一标识
- `name` (String): 模板名称
- `category` (Enum: TECHNICAL_REPORT, ACADEMIC_PAPER, BUSINESS_PLAN, OTHER): 模板类别
- `structure` (JSON): 模板结构定义（章节、格式要求）
- `style_guide` (JSON): 样式指南（标题样式、引用格式等）
- `is_active` (Boolean, Default: True): 是否激活
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**关系**:
- 一对多: DocumentTemplate → Draft (使用该模板生成的文稿)

**验证规则**:
- structure必须包含完整的模板定义
- style_guide必须包含所有必需的样式规则

**索引**:
- `category` (类别索引)
- `is_active` (激活状态索引)

---

### 19. MemoryEntry (记忆条目)

**存储**: SQLite (通过LangMem)

**描述**: 用户交互记忆条目

**字段**:
- `id` (UUID, Primary Key): 记忆条目唯一标识
- `user_id` (UUID, Foreign Key → User.id): 关联用户
- `session_id` (UUID): 会话标识
- `interaction_type` (Enum: QUERY, FEEDBACK, OPERATION, RESULT): 交互类型
- `content` (JSON): 交互内容（查询、响应、反馈等）
- `metadata` (JSON): 扩展元数据（操作习惯、识别结果等）
- `created_at` (DateTime): 创建时间

**关系**:
- 多对一: MemoryEntry → User
- 多对多: MemoryEntry → LearningPattern (通过关系表)

**验证规则**:
- content必须是有效的JSON
- interaction_type必须是预定义的枚举值

**索引**:
- `user_id` (外键索引)
- `session_id` (会话索引)
- `interaction_type` (类型索引)
- `created_at` (时间索引，用于时间序列查询)

**存储方式**:
- 通过LangMem管理，底层使用SQLite存储
- LangGraph Checkpointer用于工作流状态记忆

---

### 20. LearningPattern (学习模式)

**存储**: SQLite

**描述**: 从交互记忆中提取的学习模式

**字段**:
- `id` (UUID, Primary Key): 模式唯一标识
- `user_id` (UUID, Foreign Key → User.id, Nullable): 关联用户（如果是个性化模式）
- `pattern_type` (Enum: PROMPT_OPTIMIZATION, INTENT_RECOGNITION, DOCUMENT_PARSING): 模式类型
- `pattern_data` (JSON): 模式数据（优化后的提示词、识别规则等）
- `confidence` (Float): 置信度 (0.0 - 1.0)
- `applied_count` (Integer, Default: 0): 应用次数
- `success_rate` (Float, Default: 0.0): 成功率
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**关系**:
- 多对一: LearningPattern → User (可选，全局模式为NULL)
- 多对多: LearningPattern → MemoryEntry

**验证规则**:
- pattern_data必须符合pattern_type的要求
- confidence必须在 [0.0, 1.0] 范围内
- success_rate必须在 [0.0, 1.0] 范围内

**索引**:
- `user_id` (外键索引，NULL表示全局模式)
- `pattern_type` (类型索引)

---

### 21. User (用户)

**存储**: SQLite

**描述**: 系统用户

**字段**:
- `id` (UUID, Primary Key): 用户唯一标识
- `username` (String, Unique): 用户名
- `email` (String, Unique, Nullable): 邮箱
- `created_at` (DateTime): 注册时间
- `updated_at` (DateTime): 更新时间
- `preferences` (JSON): 用户偏好设置

**关系**:
- 一对多: User → Document
- 一对多: User → Outline
- 一对多: User → Draft
- 一对多: User → GlobalConstraints
- 一对多: User → SourceFeedback
- 一对多: User → CustomDataSource
- 一对多: User → WebDataSource (通过CustomDataSource间接关联)
- 一对多: User → MemoryEntry
- 一对多: User → LearningPattern

**验证规则**:
- username不能为空且必须唯一
- email格式必须有效（如果提供）

**索引**:
- `username` (唯一索引)
- `email` (唯一索引，如果提供)

---

## 数据关系图

```
User
├── GlobalConstraints (硬性规范条件)
│   ├── Outline (大纲)
│   │   ├── OptimizedOutline (优化后大纲)
│   │   └── Draft (文稿草稿)
│   │       ├── DraftVersion (版本历史)
│   │       ├── ChartConfig (图表配置)
│   │       └── DraftEditState (草稿编辑界面状态)
│   └── Draft (使用该规范条件生成的文稿)
│
├── Document (上传的文档)
│   ├── DocumentChunk (文档块)
│   │   ├── VectorEmbedding (向量嵌入)
│   │   └── GraphEntity (图谱实体)
│   └── KnowledgeEntry (知识库条目，来自用户上传的文档)
│
├── CustomDataSource (自定义数据源)
│   └── WebDataSource (网络数据源)
│       └── KnowledgeEntry (知识库条目，来自网络检索数据)
│
├── SourceMatch (信息源匹配结果)
│   ├── SourceFeedback (信息源反馈)
│   ├── CustomDataSource (自定义数据源，如果source_type是CUSTOM_WEBSITE)
│   └── WebDataSource (网络数据源，作为信息源)
│
├── RetrievalQuery (检索查询)
│   └── RetrievalResult (检索结果)
│
├── MemoryEntry (记忆条目)
│   └── LearningPattern (学习模式)
│
└── DocumentTemplate (文档模板)
    └── Draft (使用模板生成的文稿)

GraphEntity (图谱实体)
└── GraphRelation (图谱关系)
    └── GraphEntity (目标实体)
```

---

## 状态转换

### Document状态机
```
PENDING → PARSING → INDEXED
              ↓
           FAILED
```

### Outline状态机
```
DRAFT → OPTIMIZED → USED
```

### Draft状态机
```
DRAFT → POLISHED → FINAL
```

---

## 数据验证规则总结

1. **外键约束**: 所有外键必须引用有效记录
2. **唯一性约束**: username、email必须唯一
3. **非空约束**: 所有标记为Required的字段不能为空
4. **枚举约束**: 所有Enum字段必须使用预定义值
5. **范围约束**: 评分类字段必须在 [0.0, 1.0] 范围内
6. **JSON约束**: 所有JSON字段必须符合定义的schema
7. **状态转换**: 状态字段必须遵循状态机规则

---

## 数据迁移策略

1. **初始迁移**: 创建所有表结构
2. **索引迁移**: 创建所有索引
3. **数据迁移**: 如有历史数据，需要迁移脚本
4. **版本管理**: 使用数据库迁移工具（如Alembic）管理版本

---

## 性能考虑

1. **索引优化**: 为常用查询字段创建索引
2. **分页查询**: 大结果集使用分页
3. **缓存策略**: 检索结果、向量嵌入使用缓存
4. **异步处理**: 文档解析、索引构建使用异步任务
5. **批量操作**: 支持批量插入和更新

