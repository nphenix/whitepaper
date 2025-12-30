-- Migration: Create Outline and Optimization Tables
-- Version: 005
-- Created: 2025-12-23
-- Description: Add tables for storing outlines, optimized outlines, and optimization feedback

-- @up
-- 注意: outlines 表已在迁移001中创建,此迁移不创建outlines表
-- 如果需要在outlines表中添加新列(如industry_id, database_ids等),应使用ALTER TABLE
-- 但由于SQLite的限制,ALTER TABLE无法添加NOT NULL列或修改外键约束
-- 因此,表结构更新应通过后续迁移(如006)使用ALTER TABLE添加可选列来处理
-- 
-- 本迁移只创建新表: outline_items, outline_versions, optimized_outlines等
-- 这些表依赖outlines表,但不修改outlines表的结构

-- 创建大纲项表
CREATE TABLE IF NOT EXISTS outline_items (
    id TEXT PRIMARY KEY,
    outline_id TEXT NOT NULL,
    parent_id TEXT,
    item_type TEXT NOT NULL, -- SECTION, SUBSECTION, PARAGRAPH, CONTENT
    level INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    order_index INTEGER NOT NULL DEFAULT 0,
    is_optimized BOOLEAN DEFAULT FALSE,
    original_title TEXT,
    original_description TEXT,
    optimization_suggestions TEXT DEFAULT '[]', -- JSON array
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (outline_id) REFERENCES outlines(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES outline_items(id) ON DELETE CASCADE
);

-- 创建大纲版本表
CREATE TABLE IF NOT EXISTS outline_versions (
    id TEXT PRIMARY KEY,
    outline_id TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    status TEXT NOT NULL,
    change_reason TEXT,
    items_snapshot TEXT NOT NULL, -- JSON snapshot
    created_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (outline_id) REFERENCES outlines(id) ON DELETE CASCADE
);

-- 注意: optimized_outlines 表已在迁移001中创建,此迁移不创建optimized_outlines表
-- 迁移001创建的optimized_outlines表使用outline_id列(旧结构)
-- 如果需要更新表结构(如添加original_outline_id等新列),应通过后续迁移使用ALTER TABLE处理
-- 但由于SQLite的限制,ALTER TABLE无法添加NOT NULL列或修改外键约束,需要特殊处理

-- 创建优化后的大纲项表
CREATE TABLE IF NOT EXISTS optimized_outline_items (
    id TEXT PRIMARY KEY,
    optimized_outline_id TEXT NOT NULL,
    original_item_id TEXT,
    optimized_item_id TEXT NOT NULL,
    change_type TEXT NOT NULL DEFAULT 'NONE', -- ADD, MODIFY, DELETE, MOVE, REORDER, MERGE, SPLIT, NONE
    change_description TEXT,
    optimization_reason TEXT,
    optimization_suggestions TEXT DEFAULT '[]', -- JSON array
    is_accepted BOOLEAN DEFAULT FALSE,
    user_feedback TEXT,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (optimized_outline_id) REFERENCES optimized_outlines(id) ON DELETE CASCADE,
    FOREIGN KEY (original_item_id) REFERENCES outline_items(id) ON DELETE CASCADE
);

-- 创建优化摘要表
CREATE TABLE IF NOT EXISTS optimization_summaries (
    id TEXT PRIMARY KEY,
    optimized_outline_id TEXT NOT NULL,
    total_changes INTEGER DEFAULT 0,
    added_items INTEGER DEFAULT 0,
    modified_items INTEGER DEFAULT 0,
    deleted_items INTEGER DEFAULT 0,
    moved_items INTEGER DEFAULT 0,
    reordered_items INTEGER DEFAULT 0,
    merged_items INTEGER DEFAULT 0,
    split_items INTEGER DEFAULT 0,
    quality_score REAL DEFAULT 0.0,
    completeness_score REAL DEFAULT 0.0,
    coherence_score REAL DEFAULT 0.0,
    relevance_score REAL DEFAULT 0.0,
    optimization_summary TEXT NOT NULL,
    key_improvements TEXT DEFAULT '[]', -- JSON array
    potential_issues TEXT DEFAULT '[]', -- JSON array
    created_at TEXT NOT NULL,
    metadata TEXT DEFAULT '{}',
    FOREIGN KEY (optimized_outline_id) REFERENCES optimized_outlines(id) ON DELETE CASCADE
);

-- 创建索引
-- 注意: 使用 IF NOT EXISTS 使索引创建幂等,避免重复创建导致错误
-- 注意: outlines表的索引(如idx_outlines_industry_id)可能在表结构更新后创建,这里不创建
-- 因为outlines表可能还没有industry_id列(如果迁移006未执行)

-- outline_items表索引
CREATE INDEX IF NOT EXISTS idx_outline_items_outline_id ON outline_items(outline_id);
CREATE INDEX IF NOT EXISTS idx_outline_items_parent_id ON outline_items(parent_id);
CREATE INDEX IF NOT EXISTS idx_outline_items_level ON outline_items(level);
CREATE INDEX IF NOT EXISTS idx_outline_items_order ON outline_items(order_index);

-- outline_versions表索引
CREATE INDEX IF NOT EXISTS idx_outline_versions_outline_id ON outline_versions(outline_id);
CREATE INDEX IF NOT EXISTS idx_outline_versions_version_number ON outline_versions(version_number);
CREATE INDEX IF NOT EXISTS idx_outline_versions_created_at ON outline_versions(created_at);

-- 注意: optimized_outlines表由迁移001创建,索引应在表结构更新后创建
-- 因为旧表结构可能没有original_outline_id等新列

-- optimized_outline_items表索引
CREATE INDEX IF NOT EXISTS idx_optimized_outline_items_optimized_outline_id ON optimized_outline_items(optimized_outline_id);
CREATE INDEX IF NOT EXISTS idx_optimized_outline_items_original_item_id ON optimized_outline_items(original_item_id);
CREATE INDEX IF NOT EXISTS idx_optimized_outline_items_change_type ON optimized_outline_items(change_type);
CREATE INDEX IF NOT EXISTS idx_optimized_outline_items_is_accepted ON optimized_outline_items(is_accepted);

-- optimization_summaries表索引
CREATE INDEX IF NOT EXISTS idx_optimization_summaries_optimized_outline_id ON optimization_summaries(optimized_outline_id);

-- @down
-- 删除索引
DROP INDEX IF EXISTS idx_optimization_summaries_optimized_outline_id;
DROP INDEX IF EXISTS idx_optimized_outline_items_is_accepted;
DROP INDEX IF EXISTS idx_optimized_outline_items_change_type;
DROP INDEX IF EXISTS idx_optimized_outline_items_original_item_id;
DROP INDEX IF EXISTS idx_optimized_outline_items_optimized_outline_id;
-- 注意: optimized_outlines表由迁移001创建,这里不删除其索引
-- 如果后续迁移为optimized_outlines表创建了索引,应在相应迁移的回滚中删除
DROP INDEX IF EXISTS idx_outline_versions_created_at;
DROP INDEX IF EXISTS idx_outline_versions_version_number;
DROP INDEX IF EXISTS idx_outline_versions_outline_id;
DROP INDEX IF EXISTS idx_outline_items_order;
DROP INDEX IF EXISTS idx_outline_items_level;
DROP INDEX IF EXISTS idx_outline_items_parent_id;
DROP INDEX IF EXISTS idx_outline_items_outline_id;
-- 注意: outlines表由迁移001创建,这里不删除
-- 如果后续迁移为outlines表创建了索引,应在相应迁移的回滚中删除

-- 删除表
DROP TABLE IF EXISTS optimization_summaries;
DROP TABLE IF EXISTS optimized_outline_items;
-- 注意: optimized_outlines表由迁移001创建,这里不删除
DROP TABLE IF EXISTS outline_versions;
DROP TABLE IF EXISTS outline_items;
-- 注意: outlines表由迁移001创建,这里不删除
