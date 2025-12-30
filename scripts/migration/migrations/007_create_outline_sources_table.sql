-- Migration: Create Outline Sources Table
-- Version: 007
-- Created: 2025-01-XX
-- Description: Add table for storing outline sources (recommended literature, custom URLs, uploaded files)

-- @up
-- 创建大纲来源表
CREATE TABLE IF NOT EXISTS outline_sources (
    id TEXT PRIMARY KEY,
    outline_id TEXT NOT NULL,
    source_type TEXT NOT NULL,  -- 'recommended', 'custom_url', 'uploaded_file'
    source_id TEXT,  -- 推荐文献ID、URL或文件ID
    source_data TEXT DEFAULT '{}',  -- JSON格式的额外数据
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (outline_id) REFERENCES outlines(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_outline_sources_outline_id ON outline_sources(outline_id);
CREATE INDEX IF NOT EXISTS idx_outline_sources_source_type ON outline_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_outline_sources_created_at ON outline_sources(created_at);

-- @down
-- 删除索引
DROP INDEX IF EXISTS idx_outline_sources_created_at;
DROP INDEX IF EXISTS idx_outline_sources_source_type;
DROP INDEX IF EXISTS idx_outline_sources_outline_id;

-- 删除表
DROP TABLE IF EXISTS outline_sources;

