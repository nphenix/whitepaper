-- Migration: Create Initial Tables
-- Version: 001
-- Created: 2025-12-08

-- @up
-- 创建用户表
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    preferences TEXT DEFAULT '{}'
);

-- 创建文档表
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER,
    mime_type TEXT,
    format TEXT CHECK(format IN ('PDF', 'HTML', 'DOCX')),
    uploaded_at TEXT,
    uploaded_by TEXT,  -- 允许为NULL，避免测试时的FOREIGN KEY约束问题
    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'PARSING', 'INDEXED', 'FAILED')),
    parsed_at TEXT,
    error_message TEXT,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
);

-- 创建文档块表
CREATE TABLE document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    start_position INTEGER,
    end_position INTEGER,
    section_path TEXT,
    section_title TEXT,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- 创建知识库条目表
CREATE TABLE knowledge_entries (
    id TEXT PRIMARY KEY,
    document_id TEXT,
    chunk_id TEXT,
    web_data_source_id TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    tags TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE,
    CHECK (
        (document_id IS NOT NULL AND chunk_id IS NOT NULL) OR
        web_data_source_id IS NOT NULL
    ),
    CHECK (
        (document_id IS NOT NULL) OR (web_data_source_id IS NOT NULL)
    )
);

-- 创建图谱实体表
CREATE TABLE graph_entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT CHECK(type IN ('PERSON', 'CONCEPT', 'EVENT', 'ORGANIZATION', 'OTHER')),
    description TEXT,
    properties TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 创建图谱关系表
CREATE TABLE graph_relations (
    id TEXT PRIMARY KEY,
    source_entity_id TEXT NOT NULL,
    target_entity_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0 CHECK(weight >= 0),
    properties TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_entity_id) REFERENCES graph_entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_entity_id) REFERENCES graph_entities(id) ON DELETE CASCADE,
    CHECK (source_entity_id != target_entity_id)
);

-- 创建全局约束条件表
CREATE TABLE global_constraints (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    report_type TEXT CHECK(report_type IN ('MARKET_RESEARCH', 'POLICY_COMPARISON', 'TECHNOLOGY_ASSESSMENT', 'OTHER')),
    platform_knowledge_base_id TEXT,
    language TEXT CHECK(language IN ('CHINESE', 'ENGLISH')),
    target_length INTEGER,
    target_pages INTEGER,
    require_charts BOOLEAN DEFAULT FALSE,
    style_guide TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    CHECK (target_length IS NOT NULL OR target_pages IS NOT NULL)
);

-- 创建大纲表
CREATE TABLE outlines (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    constraints_id TEXT NOT NULL,
    title TEXT NOT NULL,
    structure TEXT NOT NULL,
    original_structure TEXT,
    status TEXT DEFAULT 'DRAFT' CHECK(status IN ('DRAFT', 'OPTIMIZED', 'USED')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (constraints_id) REFERENCES global_constraints(id)
);

-- 创建优化后大纲表
CREATE TABLE optimized_outlines (
    id TEXT PRIMARY KEY,
    outline_id TEXT NOT NULL UNIQUE,
    optimized_structure TEXT NOT NULL,
    optimization_suggestions TEXT DEFAULT '[]',
    applied_suggestions TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (outline_id) REFERENCES outlines(id) ON DELETE CASCADE
);

-- 创建信息源匹配结果表
CREATE TABLE source_matches (
    id TEXT PRIMARY KEY,
    outline_node_id TEXT NOT NULL,
    source_type TEXT CHECK(source_type IN ('PLATFORM_LIB', 'LOCAL_KB', 'UPLOADED_DOC', 'CUSTOM_WEBSITE')),
    source_id TEXT NOT NULL,
    source_url TEXT,
    source_path TEXT,
    relevance_score REAL CHECK(relevance_score >= 0.0 AND relevance_score <= 1.0),
    semantic_similarity REAL CHECK(semantic_similarity >= 0.0 AND semantic_similarity <= 1.0),
    keyword_overlap REAL CHECK(keyword_overlap >= 0.0 AND keyword_overlap <= 1.0),
    source_reliability REAL CHECK(source_reliability >= 0.0 AND source_reliability <= 1.0),
    trust_score REAL DEFAULT 0.5 CHECK(trust_score >= 0.0 AND trust_score <= 1.0),
    snippet TEXT,
    highlighted_keywords TEXT DEFAULT '[]',
    paragraph_position TEXT,
    rank INTEGER CHECK(rank >= 1),
    created_at TEXT NOT NULL
);

-- 创建信息源反馈表
CREATE TABLE source_feedback (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source_match_id TEXT NOT NULL,
    action TEXT CHECK(action IN ('SELECTED', 'REJECTED')),
    preference_score REAL CHECK(preference_score >= 0.0 AND preference_score <= 1.0),
    feedback_metadata TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (source_match_id) REFERENCES source_matches(id) ON DELETE CASCADE
);

-- 创建自定义数据源表
CREATE TABLE custom_data_sources (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    crawl_depth INTEGER DEFAULT 2 CHECK(crawl_depth >= 1),
    index_status TEXT DEFAULT 'PENDING' CHECK(index_status IN ('PENDING', 'CRAWLING', 'INDEXING', 'COMPLETED', 'FAILED')),
    trust_score REAL DEFAULT 0.7 CHECK(trust_score >= 0.0 AND trust_score <= 1.0),
    indexed_pages INTEGER DEFAULT 0,
    indexed_paragraphs INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 创建网络数据源表
CREATE TABLE web_data_sources (
    id TEXT PRIMARY KEY,
    custom_data_source_id TEXT,
    url TEXT NOT NULL,
    title TEXT,
    content TEXT,
    extracted_at TEXT NOT NULL,
    indexed_at TEXT,
    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'EXTRACTED', 'INDEXED', 'FAILED')),
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (custom_data_source_id) REFERENCES custom_data_sources(id) ON DELETE CASCADE
);

-- 创建检索查询表
CREATE TABLE retrieval_queries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    query_type TEXT CHECK(query_type IN ('VECTOR', 'BM25', 'METADATA', 'GRAPH', 'HYBRID')),
    filters TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 创建检索结果表
CREATE TABLE retrieval_results (
    id TEXT PRIMARY KEY,
    query_id TEXT NOT NULL,
    knowledge_entry_id TEXT,
    chunk_id TEXT,
    relevance_score REAL CHECK(relevance_score >= 0.0 AND relevance_score <= 1.0),
    retrieval_method TEXT,
    rank INTEGER CHECK(rank >= 1),
    created_at TEXT NOT NULL,
    FOREIGN KEY (query_id) REFERENCES retrieval_queries(id) ON DELETE CASCADE,
    FOREIGN KEY (knowledge_entry_id) REFERENCES knowledge_entries(id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id) REFERENCES document_chunks(id) ON DELETE CASCADE
);

-- 创建文稿草稿表
CREATE TABLE drafts (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    outline_id TEXT,
    constraints_id TEXT,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    file_path TEXT,
    status TEXT DEFAULT 'DRAFT' CHECK(status IN ('DRAFT', 'POLISHED', 'FINAL')),
    citations TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    polished_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (outline_id) REFERENCES outlines(id) ON DELETE SET NULL,
    FOREIGN KEY (constraints_id) REFERENCES global_constraints(id) ON DELETE SET NULL
);

-- 创建图表配置表
CREATE TABLE chart_configs (
    id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    chart_type TEXT CHECK(chart_type IN ('BAR', 'LINE', 'PIE', 'SCATTER', 'TABLE', 'OTHER')),
    data_source TEXT NOT NULL,
    dsl_config TEXT NOT NULL,
    placeholder_position INTEGER CHECK(placeholder_position >= 0),
    is_editable BOOLEAN DEFAULT TRUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE CASCADE
);

-- 创建草稿编辑界面状态表
CREATE TABLE draft_edit_states (
    id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    left_panel_state TEXT,
    right_panel_state TEXT,
    middle_panel_state TEXT,
    last_updated_at TEXT NOT NULL,
    FOREIGN KEY (draft_id) REFERENCES drafts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建文档模板表
CREATE TABLE document_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT CHECK(category IN ('TECHNICAL_REPORT', 'ACADEMIC_PAPER', 'BUSINESS_PLAN', 'OTHER')),
    structure TEXT NOT NULL,
    style_guide TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 创建记忆条目表
CREATE TABLE memory_entries (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    interaction_type TEXT CHECK(interaction_type IN ('QUERY', 'FEEDBACK', 'OPERATION', 'RESULT')),
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 创建学习模式表
CREATE TABLE learning_patterns (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    pattern_type TEXT CHECK(pattern_type IN ('PROMPT_OPTIMIZATION', 'INTENT_RECOGNITION', 'DOCUMENT_PARSING')),
    pattern_data TEXT NOT NULL,
    confidence REAL CHECK(confidence >= 0.0 AND confidence <= 1.0),
    applied_count INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0 CHECK(success_rate >= 0.0 AND success_rate <= 1.0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 创建索引
-- 用户表索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- 文档表索引
CREATE INDEX idx_documents_uploaded_by ON documents(uploaded_by);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_uploaded_at ON documents(uploaded_at);

-- 文档块表索引
CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_document_chunks_section_path ON document_chunks(section_path);

-- 知识库条目表索引
CREATE INDEX idx_knowledge_entries_document_id ON knowledge_entries(document_id);
CREATE INDEX idx_knowledge_entries_chunk_id ON knowledge_entries(chunk_id);
CREATE INDEX idx_knowledge_entries_tags ON knowledge_entries(tags);

-- 图谱关系表索引
CREATE INDEX idx_graph_relations_source_entity_id ON graph_relations(source_entity_id);
CREATE INDEX idx_graph_relations_target_entity_id ON graph_relations(target_entity_id);

-- 全局约束条件表索引
CREATE INDEX idx_global_constraints_user_id ON global_constraints(user_id);
CREATE INDEX idx_global_constraints_report_type ON global_constraints(report_type);

-- 大纲表索引
CREATE INDEX idx_outlines_user_id ON outlines(user_id);
CREATE INDEX idx_outlines_constraints_id ON outlines(constraints_id);
CREATE INDEX idx_outlines_status ON outlines(status);

-- 信息源匹配结果表索引
CREATE INDEX idx_source_matches_outline_node_id ON source_matches(outline_node_id);
CREATE INDEX idx_source_matches_source_type ON source_matches(source_type);
CREATE INDEX idx_source_matches_relevance_score ON source_matches(relevance_score);
CREATE INDEX idx_source_matches_trust_score ON source_matches(trust_score);

-- 信息源反馈表索引
CREATE INDEX idx_source_feedback_user_id ON source_feedback(user_id);
CREATE INDEX idx_source_feedback_source_match_id ON source_feedback(source_match_id);
CREATE INDEX idx_source_feedback_action ON source_feedback(action);

-- 自定义数据源表索引
CREATE INDEX idx_custom_data_sources_user_id ON custom_data_sources(user_id);
CREATE INDEX idx_custom_data_sources_domain ON custom_data_sources(domain);
CREATE INDEX idx_custom_data_sources_index_status ON custom_data_sources(index_status);

-- 网络数据源表索引
CREATE INDEX idx_web_data_sources_custom_data_source_id ON web_data_sources(custom_data_source_id);
CREATE INDEX idx_web_data_sources_url ON web_data_sources(url);
CREATE INDEX idx_web_data_sources_status ON web_data_sources(status);
CREATE INDEX idx_web_data_sources_indexed_at ON web_data_sources(indexed_at);

-- 检索结果表索引
CREATE INDEX idx_retrieval_results_query_id ON retrieval_results(query_id);
CREATE INDEX idx_retrieval_results_knowledge_entry_id ON retrieval_results(knowledge_entry_id);
CREATE INDEX idx_retrieval_results_chunk_id ON retrieval_results(chunk_id);
CREATE INDEX idx_retrieval_results_relevance_score ON retrieval_results(relevance_score);

-- 文稿草稿表索引
CREATE INDEX idx_drafts_user_id ON drafts(user_id);
CREATE INDEX idx_drafts_outline_id ON drafts(outline_id);
CREATE INDEX idx_drafts_constraints_id ON drafts(constraints_id);
CREATE INDEX idx_drafts_status ON drafts(status);

-- 图表配置表索引
CREATE INDEX idx_chart_configs_draft_id ON chart_configs(draft_id);
CREATE INDEX idx_chart_configs_chart_type ON chart_configs(chart_type);

-- 草稿编辑界面状态表索引
CREATE INDEX idx_draft_edit_states_draft_id ON draft_edit_states(draft_id);
CREATE INDEX idx_draft_edit_states_user_id ON draft_edit_states(user_id);

-- 文档模板表索引
CREATE INDEX idx_document_templates_category ON document_templates(category);
CREATE INDEX idx_document_templates_is_active ON document_templates(is_active);

-- 记忆条目表索引
CREATE INDEX idx_memory_entries_user_id ON memory_entries(user_id);
CREATE INDEX idx_memory_entries_session_id ON memory_entries(session_id);
CREATE INDEX idx_memory_entries_interaction_type ON memory_entries(interaction_type);
CREATE INDEX idx_memory_entries_created_at ON memory_entries(created_at);

-- 学习模式表索引
CREATE INDEX idx_learning_patterns_user_id ON learning_patterns(user_id);
CREATE INDEX idx_learning_patterns_pattern_type ON learning_patterns(pattern_type);

-- @down
-- 删除所有表（按依赖关系倒序）
DROP TABLE IF EXISTS learning_patterns;
DROP TABLE IF EXISTS memory_entries;
DROP TABLE IF EXISTS document_templates;
DROP TABLE IF EXISTS draft_edit_states;
DROP TABLE IF EXISTS chart_configs;
DROP TABLE IF EXISTS drafts;
DROP TABLE IF EXISTS retrieval_results;
DROP TABLE IF EXISTS retrieval_queries;
DROP TABLE IF EXISTS web_data_sources;
DROP TABLE IF EXISTS custom_data_sources;
DROP TABLE IF EXISTS source_feedback;
DROP TABLE IF EXISTS source_matches;
DROP TABLE IF EXISTS optimized_outlines;
DROP TABLE IF EXISTS outlines;
DROP TABLE IF EXISTS global_constraints;
DROP TABLE IF EXISTS graph_relations;
DROP TABLE IF EXISTS graph_entities;
DROP TABLE IF EXISTS knowledge_entries;
DROP TABLE IF EXISTS document_chunks;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS users;