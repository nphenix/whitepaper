-- Migration: Create Outline Items and Outline Versions Tables (Compat)
-- Version: 009
-- Created: 2025-12-29
-- Description: Create outline_items and outline_versions tables if missing (compatible with both legacy and new outlines schemas)

-- @up
-- outlines 表在旧版(001)与新版(005)中都存在，但 outline_items / outline_versions 在部分环境缺失。
-- 该迁移使用 IF NOT EXISTS，避免因历史迁移冲突导致无法补齐表结构。

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

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_outline_items_outline_id ON outline_items(outline_id);
CREATE INDEX IF NOT EXISTS idx_outline_items_parent_id ON outline_items(parent_id);
CREATE INDEX IF NOT EXISTS idx_outline_items_level ON outline_items(level);
CREATE INDEX IF NOT EXISTS idx_outline_items_order ON outline_items(order_index);

CREATE INDEX IF NOT EXISTS idx_outline_versions_outline_id ON outline_versions(outline_id);
CREATE INDEX IF NOT EXISTS idx_outline_versions_version_number ON outline_versions(version_number);
CREATE INDEX IF NOT EXISTS idx_outline_versions_created_at ON outline_versions(created_at);

-- @down
-- 删除索引
DROP INDEX IF EXISTS idx_outline_versions_created_at;
DROP INDEX IF EXISTS idx_outline_versions_version_number;
DROP INDEX IF EXISTS idx_outline_versions_outline_id;

DROP INDEX IF EXISTS idx_outline_items_order;
DROP INDEX IF EXISTS idx_outline_items_level;
DROP INDEX IF EXISTS idx_outline_items_parent_id;
DROP INDEX IF EXISTS idx_outline_items_outline_id;

-- 删除表
DROP TABLE IF EXISTS outline_versions;
DROP TABLE IF EXISTS outline_items;


