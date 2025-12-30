-- Migration: Create Industry Selection Table
-- Version: 004
-- Created: 2025-12-23
-- Description: Add table for storing user industry and database selections

-- @up
-- 创建行业选择记录表
CREATE TABLE industry_selections (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    industry_id TEXT NOT NULL,
    database_ids TEXT NOT NULL, -- JSON array of database IDs
    selection_name TEXT, -- 用户为这个选择起的名字
    description TEXT, -- 选择描述
    is_active BOOLEAN DEFAULT TRUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (industry_id) REFERENCES industries(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX idx_industry_selections_session_id ON industry_selections(session_id);
CREATE INDEX idx_industry_selections_industry_id ON industry_selections(industry_id);
CREATE INDEX idx_industry_selections_is_active ON industry_selections(is_active);
CREATE INDEX idx_industry_selections_created_at ON industry_selections(created_at);

-- @down
-- 删除索引
DROP INDEX IF EXISTS idx_industry_selections_created_at;
DROP INDEX IF EXISTS idx_industry_selections_is_active;
DROP INDEX IF EXISTS idx_industry_selections_industry_id;
DROP INDEX IF EXISTS idx_industry_selections_session_id;

-- 删除表
DROP TABLE IF EXISTS industry_selections;