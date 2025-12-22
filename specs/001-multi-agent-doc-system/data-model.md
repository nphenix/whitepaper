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

**描述**: 知识图谱中的实体节点。支持通用实体类型和储能产业特定实体类型。

**字段**:
- `id` (UUID, Primary Key): 实体唯一标识
- `name` (String, Required): 实体名称
- `type` (Enum, Required): 实体类型（见下方实体类型定义）
- `subtype` (String, Nullable): 实体子类型（用于更细粒度的分类）
- `description` (Text, Nullable): 实体描述
- `properties` (JSON): 扩展属性（见下方属性定义）
- `aliases` (Array[String]): 实体别名列表（用于实体消歧）
- `source_document_id` (UUID, Foreign Key → Document.id, Nullable): 来源文档
- `source_chunk_id` (UUID, Foreign Key → DocumentChunk.id, Nullable): 来源文档块
- `source_url` (String, Nullable): 来源URL（如果是网络数据）
- `confidence` (Float, Default: 1.0): 实体提取置信度 (0.0 - 1.0)
- `context` (JSON, Nullable): 上下文信息（时间、地点、领域等，见下方上下文定义）
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**实体类型枚举** (EntityType):
- **通用类型**:
  - `PERSON`: 人物
  - `ORGANIZATION`: 组织机构（企业、机构、协会等）
  - `CONCEPT`: 概念（理论、方法、技术概念等）
  - `EVENT`: 事件（会议、发布、政策出台等）
  - `LOCATION`: 地理位置（国家、地区、城市等）
  - `TIME`: 时间（年份、时间段等）
  - `OTHER`: 其他类型

- **储能产业特定类型**:
  - `ENERGY_STORAGE_TECHNOLOGY`: 储能技术（如：锂离子电池、液流电池、压缩空气储能等）
  - `ENERGY_STORAGE_DEVICE`: 储能设备（如：电池包、储能系统、PCS等）
  - `ENERGY_STORAGE_COMPONENT`: 储能组件（如：电芯、BMS、EMS等）
  - `ENERGY_STORAGE_APPLICATION`: 储能应用场景（如：电网调频、削峰填谷、新能源并网等）
  - `ENERGY_STORAGE_PROJECT`: 储能项目（具体项目实例）
  - `ENERGY_STORAGE_STANDARD`: 储能标准（国家标准、行业标准、国际标准等）
  - `ENERGY_STORAGE_POLICY`: 储能政策（国家政策、地方政策、补贴政策等）
  - `ENERGY_STORAGE_MARKET`: 储能市场（市场分析、市场规模、市场趋势等）
  - `ENERGY_STORAGE_MATERIAL`: 储能材料（正极材料、负极材料、电解质等）
  - `ENERGY_STORAGE_MANUFACTURER`: 储能制造商（电池制造商、系统集成商等）
  - `ENERGY_STORAGE_RESEARCH`: 储能研究（研究机构、研究成果、论文等）

**属性定义** (properties JSON Schema):
根据实体类型，properties 字段包含不同的属性：

- **ENERGY_STORAGE_TECHNOLOGY**:
  - `technology_category` (String): 技术类别（如：电化学储能、机械储能、电磁储能等）
  - `energy_density` (Float, Nullable): 能量密度（Wh/kg）
  - `power_density` (Float, Nullable): 功率密度（W/kg）
  - `cycle_life` (Integer, Nullable): 循环寿命（次）
  - `efficiency` (Float, Nullable): 效率（%）
  - `cost_per_kwh` (Float, Nullable): 成本（元/kWh）
  - `maturity_level` (String): 成熟度（如：研发中、示范应用、商业化等）
  - `advantages` (Array[String]): 优势列表
  - `disadvantages` (Array[String]): 劣势列表

- **ENERGY_STORAGE_DEVICE**:
  - `device_type` (String): 设备类型（如：电池包、储能系统等）
  - `capacity` (Float, Nullable): 容量（kWh或MWh）
  - `power` (Float, Nullable): 功率（kW或MW）
  - `voltage` (Float, Nullable): 电压（V）
  - `manufacturer` (String, Nullable): 制造商
  - `model` (String, Nullable): 型号
  - `specifications` (JSON, Nullable): 详细规格

- **ENERGY_STORAGE_PROJECT**:
  - `project_name` (String): 项目名称
  - `location` (String): 项目地点
  - `capacity` (Float): 项目容量（MWh）
  - `power` (Float): 项目功率（MW）
  - `technology_type` (String): 技术类型
  - `application_scenario` (String): 应用场景
  - `start_date` (Date, Nullable): 开工日期
  - `completion_date` (Date, Nullable): 竣工日期
  - `investment` (Float, Nullable): 投资额（万元）
  - `operator` (String, Nullable): 运营商

- **ENERGY_STORAGE_POLICY**:
  - `policy_type` (String): 政策类型（如：补贴政策、电价政策、规划政策等）
  - `issuing_authority` (String): 发布机构
  - `issue_date` (Date): 发布日期
  - `effective_date` (Date, Nullable): 生效日期
  - `expiry_date` (Date, Nullable): 失效日期
  - `policy_scope` (String): 政策范围（国家、省、市等）
  - `key_points` (Array[String]): 政策要点

- **ORGANIZATION**:
  - `organization_type` (String): 组织类型（如：企业、研究机构、协会等）
  - `industry` (String): 所属行业
  - `founded_date` (Date, Nullable): 成立日期
  - `headquarters` (String, Nullable): 总部地址
  - `scale` (String, Nullable): 规模（如：大型、中型、小型等）
  - `business_scope` (Array[String]): 业务范围

- **通用属性**（所有实体类型都可能包含）:
  - `keywords` (Array[String]): 关键词列表
  - `tags` (Array[String]): 标签列表
  - `related_entities` (Array[UUID]): 相关实体ID列表
  - `external_ids` (JSON): 外部ID映射（如：维基百科ID、标准号等）

**上下文信息定义** (context JSON Schema):
- `time` (String, Nullable): 时间上下文（如："2024年"、"2023-2024年"等）
- `location` (String, Nullable): 地点上下文（如："中国"、"北京市"等）
- `domain` (String, Nullable): 领域上下文（如："储能产业"、"电池技术"等）
- `source_type` (String): 来源类型（如："学术论文"、"行业报告"、"新闻资讯"等）
- `extraction_method` (String): 提取方法（如："LLM提取"、"规则提取"、"人工标注"等）

**关系**:
- 一对多: GraphEntity → GraphRelation (作为源实体)
- 一对多: GraphEntity → GraphRelation (作为目标实体)
- 多对多: GraphEntity → DocumentChunk (通过关系表)
- 多对一: GraphEntity → Document (可选，来源文档)
- 多对一: GraphEntity → DocumentChunk (可选，来源文档块)

**验证规则**:
- name不能为空
- type必须是预定义的枚举值
- confidence必须在 [0.0, 1.0] 范围内
- source_document_id和source_chunk_id必须同时存在或同时为空（如果是文档来源）
- properties必须符合对应实体类型的JSON Schema

**索引**:
- `type` (实体类型索引，用于按类型查询)
- `subtype` (子类型索引)
- `source_document_id` (外键索引)
- `source_chunk_id` (外键索引)
- `name` (名称索引，用于模糊查询)
- `aliases` (别名索引，用于实体消歧)

**存储方式**:
- NetworkX: 作为图节点存储，支持图查询和图算法
- SQLite: 持久化实体元数据，支持复杂查询和统计分析

---

### 6. GraphRelation (图谱关系)

**存储**: NetworkX (内存) + SQLite (持久化)

**描述**: 知识图谱中的关系边。支持通用关系类型和储能产业特定关系类型。

**字段**:
- `id` (UUID, Primary Key): 关系唯一标识
- `source_entity_id` (UUID, Foreign Key → GraphEntity.id): 源实体
- `target_entity_id` (UUID, Foreign Key → GraphEntity.id): 目标实体
- `relation_type` (Enum, Required): 关系类型（见下方关系类型定义）
- `relation_subtype` (String, Nullable): 关系子类型（用于更细粒度的分类）
- `weight` (Float, Default: 1.0): 关系权重（用于图算法和排序）
- `confidence` (Float, Default: 1.0): 关系提取置信度 (0.0 - 1.0)
- `properties` (JSON): 扩展属性（见下方属性定义）
- `source_document_id` (UUID, Foreign Key → Document.id, Nullable): 来源文档
- `source_chunk_id` (UUID, Foreign Key → DocumentChunk.id, Nullable): 来源文档块
- `source_url` (String, Nullable): 来源URL（如果是网络数据）
- `context` (JSON, Nullable): 上下文信息（时间、地点、领域等，见下方上下文定义）
- `created_at` (DateTime): 创建时间
- `updated_at` (DateTime): 更新时间

**关系类型枚举** (RelationType):
- **通用关系类型**:
  - `RELATED_TO`: 相关（通用相关关系）
  - `CONTAINS`: 包含（整体-部分关系）
  - `BELONGS_TO`: 属于（成员-集合关系）
  - `PART_OF`: 部分（部分-整体关系）
  - `SIMILAR_TO`: 相似（相似关系）
  - `OPPOSITE_TO`: 相反（对立关系）
  - `OCCURS_AT`: 发生于（事件-地点关系）
  - `OCCURS_IN`: 发生于（事件-时间关系）
  - `MENTIONS`: 提及（文档-实体关系）
  - `REFERENCES`: 引用（文档-文档关系）

- **储能产业特定关系类型**:
  - `USES_TECHNOLOGY`: 使用技术（设备/项目-技术关系）
  - `BASED_ON`: 基于（技术/设备-技术关系）
  - `COMPOSED_OF`: 由...组成（设备-组件关系）
  - `APPLIES_TO`: 应用于（技术/设备-应用场景关系）
  - `PRODUCED_BY`: 由...生产（设备-制造商关系）
  - `DEVELOPS`: 开发（组织-技术关系）
  - `RESEARCHES`: 研究（组织-研究关系）
  - `GOVERNED_BY`: 受...约束（技术/设备-标准/政策关系）
  - `COMPLIES_WITH`: 符合（设备/项目-标准关系）
  - `AFFECTED_BY`: 受...影响（市场/项目-政策关系）
  - `COMPETES_WITH`: 竞争（技术/企业-技术/企业关系）
  - `COOPERATES_WITH`: 合作（企业-企业关系）
  - `SUPPLIES_TO`: 供应（企业-企业关系）
  - `LOCATED_IN`: 位于（项目/企业-地点关系）
  - `OPERATES_IN`: 运营于（项目-地点关系）
  - `HAS_CAPACITY`: 具有容量（项目/设备-数值关系）
  - `HAS_POWER`: 具有功率（项目/设备-数值关系）
  - `COSTS`: 成本为（设备/项目-数值关系）
  - `PERFORMS_BETTER_THAN`: 性能优于（技术-技术关系）
  - `REPLACES`: 替代（技术-技术关系）
  - `EVOLVES_FROM`: 演进自（技术-技术关系）

**关系层次结构**:
关系类型可以组织成层次结构，支持更细粒度的分类：
- `RELATED_TO` (通用相关)
  - `RELATED_TO_TECHNICALLY` (技术相关)
  - `RELATED_TO_MARKET` (市场相关)
  - `RELATED_TO_POLICY` (政策相关)
- `CONTAINS` (包含)
  - `CONTAINS_COMPONENT` (包含组件)
  - `CONTAINS_SUBSYSTEM` (包含子系统)
- `APPLIES_TO` (应用于)
  - `APPLIES_TO_GRID` (应用于电网)
  - `APPLIES_TO_RENEWABLE` (应用于新能源)
  - `APPLIES_TO_INDUSTRIAL` (应用于工业)

**属性定义** (properties JSON Schema):
根据关系类型，properties 字段包含不同的属性：

- **USES_TECHNOLOGY**:
  - `usage_type` (String): 使用类型（如：主要技术、辅助技术等）
  - `usage_ratio` (Float, Nullable): 使用比例（%）

- **COMPOSED_OF**:
  - `component_role` (String): 组件角色（如：核心组件、辅助组件等）
  - `quantity` (Integer, Nullable): 数量

- **GOVERNED_BY / COMPLIES_WITH**:
  - `compliance_level` (String): 符合程度（如：完全符合、部分符合等）
  - `standard_version` (String, Nullable): 标准版本

- **AFFECTED_BY**:
  - `impact_type` (String): 影响类型（如：正面影响、负面影响等）
  - `impact_degree` (String): 影响程度（如：重大、中等、轻微等）

- **HAS_CAPACITY / HAS_POWER**:
  - `unit` (String): 单位（如：kWh、MWh、kW、MW等）
  - `measurement_date` (Date, Nullable): 测量日期

- **COSTS**:
  - `currency` (String): 货币单位（如：人民币、美元等）
  - `cost_type` (String): 成本类型（如：初始投资、运营成本等）

- **通用属性**（所有关系类型都可能包含）:
  - `description` (String, Nullable): 关系描述
  - `evidence` (Array[String]): 证据文本列表
  - `start_time` (String, Nullable): 关系开始时间
  - `end_time` (String, Nullable): 关系结束时间（如果关系有时间范围）

**上下文信息定义** (context JSON Schema):
- `time` (String, Nullable): 时间上下文（如："2024年"、"2023-2024年"等）
- `location` (String, Nullable): 地点上下文（如："中国"、"北京市"等）
- `domain` (String, Nullable): 领域上下文（如："储能产业"、"电池技术"等）
- `source_type` (String): 来源类型（如："学术论文"、"行业报告"、"新闻资讯"等）
- `extraction_method` (String): 提取方法（如："LLM提取"、"规则提取"、"人工标注"等）

**关系**:
- 多对一: GraphRelation → GraphEntity (source)
- 多对一: GraphRelation → GraphEntity (target)
- 多对一: GraphRelation → Document (可选，来源文档)
- 多对一: GraphRelation → DocumentChunk (可选，来源文档块)

**验证规则**:
- source_entity_id ≠ target_entity_id（不能自环，除非关系类型明确允许）
- relation_type必须是预定义的枚举值
- weight >= 0
- confidence必须在 [0.0, 1.0] 范围内
- source_document_id和source_chunk_id必须同时存在或同时为空（如果是文档来源）
- properties必须符合对应关系类型的JSON Schema
- 某些关系类型对源实体和目标实体的类型有约束（如：USES_TECHNOLOGY的源实体应该是设备或项目，目标实体应该是技术）

**关系类型约束** (Relation Type Constraints):
某些关系类型对实体类型有特定要求：
- `USES_TECHNOLOGY`: 源实体类型应为 ENERGY_STORAGE_DEVICE 或 ENERGY_STORAGE_PROJECT，目标实体类型应为 ENERGY_STORAGE_TECHNOLOGY
- `COMPOSED_OF`: 源实体类型应为 ENERGY_STORAGE_DEVICE，目标实体类型应为 ENERGY_STORAGE_COMPONENT
- `PRODUCED_BY`: 源实体类型应为 ENERGY_STORAGE_DEVICE，目标实体类型应为 ENERGY_STORAGE_MANUFACTURER 或 ORGANIZATION
- `GOVERNED_BY`: 源实体类型应为 ENERGY_STORAGE_TECHNOLOGY 或 ENERGY_STORAGE_DEVICE，目标实体类型应为 ENERGY_STORAGE_STANDARD 或 ENERGY_STORAGE_POLICY
- `APPLIES_TO`: 源实体类型应为 ENERGY_STORAGE_TECHNOLOGY 或 ENERGY_STORAGE_DEVICE，目标实体类型应为 ENERGY_STORAGE_APPLICATION

**索引**:
- `relation_type` (关系类型索引，用于按类型查询)
- `relation_subtype` (关系子类型索引)
- `source_entity_id` (外键索引)
- `target_entity_id` (外键索引)
- `source_document_id` (外键索引)
- `source_chunk_id` (外键索引)
- `weight` (权重索引，用于排序)
- `confidence` (置信度索引)

**存储方式**:
- NetworkX: 作为图边存储，支持图查询、路径查找和图算法
- SQLite: 持久化关系元数据，支持复杂查询和统计分析

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

---

## 知识图谱模式层（本体层）

### 概述

模式层（Schema Layer）定义知识图谱的语义结构，包括实体类型、关系类型及其层次结构、属性定义和约束规则。模式层有助于：
- 规范数据组织，确保数据一致性
- 支持复杂的推理和查询
- 提供领域知识的结构化表示
- 支持实体和关系的自动验证

### 实体类型层次结构

```
Entity (根实体)
├── GenericEntity (通用实体)
│   ├── PERSON (人物)
│   ├── ORGANIZATION (组织机构)
│   ├── CONCEPT (概念)
│   ├── EVENT (事件)
│   ├── LOCATION (地理位置)
│   └── TIME (时间)
│
└── EnergyStorageEntity (储能产业实体)
    ├── ENERGY_STORAGE_TECHNOLOGY (储能技术)
    │   ├── ElectrochemicalStorage (电化学储能)
    │   │   ├── LithiumIonBattery (锂离子电池)
    │   │   ├── FlowBattery (液流电池)
    │   │   └── ...
    │   ├── MechanicalStorage (机械储能)
    │   │   ├── PumpedHydro (抽水蓄能)
    │   │   ├── CompressedAir (压缩空气储能)
    │   │   └── ...
    │   └── ElectromagneticStorage (电磁储能)
    │       ├── Supercapacitor (超级电容器)
    │       └── ...
    │
    ├── ENERGY_STORAGE_DEVICE (储能设备)
    │   ├── BatteryPack (电池包)
    │   ├── EnergyStorageSystem (储能系统)
    │   ├── PowerConversionSystem (PCS)
    │   └── ...
    │
    ├── ENERGY_STORAGE_COMPONENT (储能组件)
    │   ├── BatteryCell (电芯)
    │   ├── BatteryManagementSystem (BMS)
    │   ├── EnergyManagementSystem (EMS)
    │   └── ...
    │
    ├── ENERGY_STORAGE_APPLICATION (储能应用场景)
    │   ├── GridFrequencyRegulation (电网调频)
    │   ├── PeakShaving (削峰填谷)
    │   ├── RenewableEnergyIntegration (新能源并网)
    │   └── ...
    │
    ├── ENERGY_STORAGE_PROJECT (储能项目)
    ├── ENERGY_STORAGE_STANDARD (储能标准)
    ├── ENERGY_STORAGE_POLICY (储能政策)
    ├── ENERGY_STORAGE_MARKET (储能市场)
    ├── ENERGY_STORAGE_MATERIAL (储能材料)
    ├── ENERGY_STORAGE_MANUFACTURER (储能制造商)
    └── ENERGY_STORAGE_RESEARCH (储能研究)
```

### 关系类型层次结构

```
Relation (根关系)
├── GenericRelation (通用关系)
│   ├── RELATED_TO (相关)
│   ├── CONTAINS (包含)
│   ├── BELONGS_TO (属于)
│   ├── PART_OF (部分)
│   ├── SIMILAR_TO (相似)
│   ├── OPPOSITE_TO (相反)
│   ├── OCCURS_AT (发生于-地点)
│   ├── OCCURS_IN (发生于-时间)
│   ├── MENTIONS (提及)
│   └── REFERENCES (引用)
│
└── EnergyStorageRelation (储能产业关系)
    ├── TechnicalRelation (技术关系)
    │   ├── USES_TECHNOLOGY (使用技术)
    │   ├── BASED_ON (基于)
    │   ├── COMPOSED_OF (由...组成)
    │   ├── EVOLVES_FROM (演进自)
    │   ├── REPLACES (替代)
    │   └── PERFORMS_BETTER_THAN (性能优于)
    │
    ├── ApplicationRelation (应用关系)
    │   └── APPLIES_TO (应用于)
    │
    ├── ProductionRelation (生产关系)
    │   ├── PRODUCED_BY (由...生产)
    │   ├── DEVELOPS (开发)
    │   └── RESEARCHES (研究)
    │
    ├── RegulatoryRelation (监管关系)
    │   ├── GOVERNED_BY (受...约束)
    │   ├── COMPLIES_WITH (符合)
    │   └── AFFECTED_BY (受...影响)
    │
    ├── MarketRelation (市场关系)
    │   ├── COMPETES_WITH (竞争)
    │   ├── COOPERATES_WITH (合作)
    │   └── SUPPLIES_TO (供应)
    │
    ├── LocationRelation (位置关系)
    │   ├── LOCATED_IN (位于)
    │   └── OPERATES_IN (运营于)
    │
    └── PropertyRelation (属性关系)
        ├── HAS_CAPACITY (具有容量)
        ├── HAS_POWER (具有功率)
        └── COSTS (成本为)
```

### 属性模式定义

#### 实体属性模式

每个实体类型都有预定义的属性模式，存储在 `properties` JSON 字段中。属性模式包括：
- **必需属性**: 必须存在的属性
- **可选属性**: 可以存在的属性
- **属性类型**: 字符串、数字、日期、数组等
- **属性约束**: 取值范围、格式要求等

#### 关系属性模式

每个关系类型都有预定义的属性模式，存储在 `properties` JSON 字段中。关系属性模式包括：
- **关系特定属性**: 如使用比例、符合程度等
- **时间属性**: 关系开始时间、结束时间等
- **证据属性**: 支持关系的证据文本

### 约束规则

#### 实体类型约束

- 某些实体类型必须具有特定的必需属性
- 某些实体类型的属性值必须在预定义的范围内
- 实体名称和别名必须唯一（在同一类型内）

#### 关系类型约束

- 某些关系类型对源实体和目标实体的类型有特定要求
- 某些关系类型不允许自环（source_entity_id ≠ target_entity_id）
- 某些关系类型要求特定的属性存在

#### 数据完整性约束

- 所有外键必须引用有效的实体
- 时间字段必须符合日期格式
- 数值字段必须在合理范围内
- JSON 字段必须符合预定义的 Schema

### 模式演化

知识图谱的模式层支持演化：
- **新增实体类型**: 可以添加新的实体类型，不影响现有数据
- **新增关系类型**: 可以添加新的关系类型，扩展关系语义
- **属性扩展**: 可以在现有实体类型和关系类型上添加新属性
- **向后兼容**: 模式演化应保持向后兼容，不破坏现有查询和应用

### 模式验证

系统提供模式验证功能：
- **实体验证**: 验证实体是否符合其类型的属性模式
- **关系验证**: 验证关系是否符合其类型的约束规则
- **一致性验证**: 验证实体和关系之间的一致性
- **完整性验证**: 验证必需属性和必需关系是否存在

---

## 储能产业知识图谱特定说明

### 数据来源

储能产业知识图谱的数据来源包括：
1. **学术论文**: 储能技术研究、材料研究、系统研究等
2. **行业报告**: 市场分析报告、技术评估报告、政策分析报告等
3. **政策文件**: 国家政策、地方政策、行业标准等
4. **企业信息**: 制造商信息、项目信息、产品信息等
5. **新闻资讯**: 行业动态、项目动态、技术动态等

### 实体提取策略

1. **技术实体提取**: 从文档中提取储能技术名称、技术参数、技术特点等
2. **设备实体提取**: 从文档中提取设备名称、设备规格、设备厂商等
3. **项目实体提取**: 从文档中提取项目名称、项目地点、项目规模等
4. **政策实体提取**: 从文档中提取政策名称、政策要点、政策影响等
5. **企业实体提取**: 从文档中提取企业名称、企业类型、企业业务等

### 关系提取策略

1. **技术关系提取**: 提取技术之间的演进关系、替代关系、性能比较关系等
2. **应用关系提取**: 提取技术与应用场景之间的应用关系
3. **生产关系提取**: 提取设备与制造商之间的生产关系
4. **监管关系提取**: 提取技术与标准/政策之间的监管关系
5. **市场关系提取**: 提取企业之间的竞争关系、合作关系、供应关系等

### 上下文信息利用

1. **时间上下文**: 利用时间信息区分不同时期的实体和关系（如：2023年的技术 vs 2024年的技术）
2. **地点上下文**: 利用地点信息区分不同地区的实体和关系（如：中国的政策 vs 美国的政策）
3. **领域上下文**: 利用领域信息区分不同领域的实体和关系（如：电池技术 vs 系统集成技术）

### 实体消歧

1. **名称标准化**: 对同一实体的不同名称进行标准化（如："锂离子电池"、"Li-ion电池"、"锂电池"统一为"锂离子电池"）
2. **别名管理**: 维护实体的别名列表，支持通过别名查找实体
3. **上下文消歧**: 利用上下文信息区分同名但不同含义的实体（如：不同公司的"储能系统"）

### 关系权重计算

关系权重可以根据以下因素计算：
1. **证据强度**: 支持关系的证据数量和强度
2. **来源可信度**: 数据来源的可信度
3. **时间相关性**: 关系的时间相关性（越近期的关系权重越高）
4. **领域相关性**: 关系在领域内的相关性

### 知识图谱更新策略

1. **增量更新**: 支持增量添加新的实体和关系
2. **实体合并**: 支持合并重复的实体
3. **关系更新**: 支持更新已有关系的权重和属性
4. **过期处理**: 支持标记和处理过期的实体和关系（如：已失效的政策）

### 查询和推理

知识图谱支持以下类型的查询和推理：
1. **实体查询**: 根据实体类型、属性、关系查询实体
2. **关系查询**: 根据关系类型、实体类型查询关系
3. **路径查询**: 查找两个实体之间的路径
4. **子图查询**: 查询满足特定条件的子图
5. **推理查询**: 基于关系进行推理（如：如果A使用技术B，B基于技术C，则A间接使用技术C）

### 与RAG架构的融合

知识图谱可以与RAG（Retrieval-Augmented Generation）架构融合：
1. **检索增强**: 使用知识图谱检索相关实体和关系，增强检索结果
2. **上下文构建**: 使用知识图谱构建更丰富的上下文信息
3. **答案生成**: 使用知识图谱中的结构化信息生成更准确的答案
4. **事实验证**: 使用知识图谱验证生成答案的事实准确性

