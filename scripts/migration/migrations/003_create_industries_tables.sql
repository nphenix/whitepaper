-- Migration: Create Industries and Industry Databases Tables
-- Version: 003
-- Created: 2025-12-23
-- Description: Add tables for industries and industry databases with predefined data

-- @up
-- 创建行业表
CREATE TABLE industries (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    category TEXT CHECK(category IN (
        'ENERGY',           -- 能源行业
        'TECHNOLOGY',       -- 技术行业
        'MANUFACTURING',     -- 制造业
        'FINANCE',           -- 金融行业
        'HEALTHCARE',       -- 医疗健康
        'EDUCATION',         -- 教育行业
        'RETAIL',            -- 零售行业
        'REAL_ESTATE',       -- 房地产
        'TRANSPORTATION',    -- 交通运输
        'AGRICULTURE',       -- 农业行业
        'OTHER'              -- 其他行业
    )),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0 CHECK(sort_order >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);

-- 创建行业数据库表
CREATE TABLE industry_databases (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE NOT NULL,
    industry_id TEXT NOT NULL,
    database_type TEXT CHECK(database_type IN (
        'KNOWLEDGE_BASE',      -- 知识库
        'MARKET_DATA',         -- 市场数据
        'POLICY_DATABASE',     -- 政策数据库
        'TECHNOLOGY_DATABASE', -- 技术数据库
        'INDUSTRY_REPORTS',    -- 行业报告
        'RESEARCH_PAPERS',     -- 研究论文
        'NEWS_ARTICLES',       -- 新闻文章
        'PATENT_DATABASE',     -- 专利数据库
        'OTHER'                -- 其他
    )),
    data_source TEXT CHECK(data_source IN (
        'PLATFORM_BUILTIN',  -- 平台内置
        'USER_UPLOADED',      -- 用户上传
        'WEB_CRAWLED',        -- 网络爬取
        'THIRD_PARTY',        -- 第三方
        'MIXED'               -- 混合来源
    )),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0 CHECK(sort_order >= 0),
    documents_count INTEGER DEFAULT 0 CHECK(documents_count >= 0),
    size_mb REAL DEFAULT 0.0 CHECK(size_mb >= 0),
    last_updated TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE CASCADE
);

-- 创建索引
-- 行业表索引
CREATE INDEX idx_industries_code ON industries(code);
CREATE INDEX idx_industries_category ON industries(category);
CREATE INDEX idx_industries_is_active ON industries(is_active);
CREATE INDEX idx_industries_sort_order ON industries(sort_order);

-- 行业数据库表索引
CREATE INDEX idx_industry_databases_code ON industry_databases(code);
CREATE INDEX idx_industry_databases_industry_id ON industry_databases(industry_id);
CREATE INDEX idx_industry_databases_database_type ON industry_databases(database_type);
CREATE INDEX idx_industry_databases_data_source ON industry_databases(data_source);
CREATE INDEX idx_industry_databases_is_active ON industry_databases(is_active);
CREATE INDEX idx_industry_databases_is_public ON industry_databases(is_public);
CREATE INDEX idx_industry_databases_sort_order ON industry_databases(sort_order);

-- 初始化预定义行业数据
-- 储能行业
INSERT INTO industries (id, name, code, category, description, is_active, sort_order, created_at, updated_at, metadata)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    '储能行业',
    'ENERGY_STORAGE',
    'ENERGY',
    '储能行业包括电池储能、抽水蓄能、压缩空气储能等各种储能技术及相关应用',
    TRUE,
    1,
    '2025-12-23T00:00:00Z',
    '2025-12-23T00:00:00Z',
    '{}'
);

-- 能源行业
INSERT INTO industries (id, name, code, category, description, is_active, sort_order, created_at, updated_at, metadata)
VALUES (
    '00000000-0000-0000-0000-000000000002',
    '能源行业',
    'ENERGY',
    'ENERGY',
    '能源行业包括传统能源和新能源, 如电力、石油、天然气、太阳能、风能等',
    TRUE,
    2,
    '2025-12-23T00:00:00Z',
    '2025-12-23T00:00:00Z',
    '{}'
);

-- 新能源行业
INSERT INTO industries (id, name, code, category, description, is_active, sort_order, created_at, updated_at, metadata)
VALUES (
    '00000000-0000-0000-0000-000000000003',
    '新能源行业',
    'NEW_ENERGY',
    'ENERGY',
    '新能源行业包括太阳能、风能、生物质能、地热能等可再生能源',
    TRUE,
    3,
    '2025-12-23T00:00:00Z',
    '2025-12-23T00:00:00Z',
    '{}'
);

-- 初始化预定义数据库数据
-- 储能行业知识库
INSERT INTO industry_databases (id, name, code, industry_id, database_type, data_source, description, is_active, is_public, sort_order, documents_count, size_mb, last_updated, created_at, updated_at, metadata)
VALUES (
    '00000000-0000-0000-0000-000000000010',
    '储能行业知识库',
    'ENERGY_STORAGE_KB',
    '00000000-0000-0000-0000-000000000001',
    'KNOWLEDGE_BASE',
    'PLATFORM_BUILTIN',
    '储能行业知识库包含储能技术、市场、政策等相关文档和数据',
    TRUE,
    TRUE,
    1,
    0,
    0.0,
    NULL,
    '2025-12-23T00:00:00Z',
    '2025-12-23T00:00:00Z',
    '{}'
);

-- 储能行业市场数据库
INSERT INTO industry_databases (id, name, code, industry_id, database_type, data_source, description, is_active, is_public, sort_order, documents_count, size_mb, last_updated, created_at, updated_at, metadata)
VALUES (
    '00000000-0000-0000-0000-000000000011',
    '储能行业市场数据库',
    'ENERGY_STORAGE_MARKET',
    '00000000-0000-0000-0000-000000000001',
    'MARKET_DATA',
    'PLATFORM_BUILTIN',
    '储能行业市场数据库包含市场规模、价格趋势、竞争格局等市场数据',
    TRUE,
    TRUE,
    2,
    0,
    0.0,
    NULL,
    '2025-12-23T00:00:00Z',
    '2025-12-23T00:00:00Z',
    '{}'
);

-- 储能行业政策数据库
INSERT INTO industry_databases (id, name, code, industry_id, database_type, data_source, description, is_active, is_public, sort_order, documents_count, size_mb, last_updated, created_at, updated_at, metadata)
VALUES (
    '00000000-0000-0000-0000-000000000012',
    '储能行业政策数据库',
    'ENERGY_STORAGE_POLICY',
    '00000000-0000-0000-0000-000000000001',
    'POLICY_DATABASE',
    'PLATFORM_BUILTIN',
    '储能行业政策数据库包含国家政策、地方政策、行业标准等政策信息',
    TRUE,
    TRUE,
    3,
    0,
    0.0,
    NULL,
    '2025-12-23T00:00:00Z',
    '2025-12-23T00:00:00Z',
    '{}'
);

-- 能源行业知识库
INSERT INTO industry_databases (id, name, code, industry_id, database_type, data_source, description, is_active, is_public, sort_order, documents_count, size_mb, last_updated, created_at, updated_at, metadata)
VALUES (
    '00000000-0000-0000-0000-000000000013',
    '能源行业知识库',
    'ENERGY_KB',
    '00000000-0000-0000-0000-000000000002',
    'KNOWLEDGE_BASE',
    'PLATFORM_BUILTIN',
    '能源行业知识库包含传统能源和新能源相关知识',
    TRUE,
    TRUE,
    4,
    0,
    0.0,
    NULL,
    '2025-12-23T00:00:00Z',
    '2025-12-23T00:00:00Z',
    '{}'
);

-- @down
-- 删除索引
DROP INDEX IF EXISTS idx_industry_databases_sort_order;
DROP INDEX IF EXISTS idx_industry_databases_is_public;
DROP INDEX IF EXISTS idx_industry_databases_is_active;
DROP INDEX IF EXISTS idx_industry_databases_data_source;
DROP INDEX IF EXISTS idx_industry_databases_database_type;
DROP INDEX IF EXISTS idx_industry_databases_industry_id;
DROP INDEX IF EXISTS idx_industry_databases_code;
DROP INDEX IF EXISTS idx_industries_sort_order;
DROP INDEX IF EXISTS idx_industries_is_active;
DROP INDEX IF EXISTS idx_industries_category;
DROP INDEX IF EXISTS idx_industries_code;

-- 删除表
DROP TABLE IF EXISTS industry_databases;
DROP TABLE IF EXISTS industries;
