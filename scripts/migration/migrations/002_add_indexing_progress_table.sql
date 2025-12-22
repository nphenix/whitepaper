-- Migration: Add Indexing Progress Table
-- Version: 002
-- Created: 2025-12-21
-- Description: Add table for tracking indexing progress and status management

-- @up
-- 创建索引构建进度跟踪表
CREATE TABLE indexing_progress (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    knowledge_base_id TEXT NOT NULL,
    task_type TEXT CHECK(task_type IN ('CREATE_KNOWLEDGE_BASE', 'UPDATE_KNOWLEDGE_BASE', 'DELETE_KNOWLEDGE_BASE', 'QUERY_KNOWLEDGE_BASE')),
    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')),
    start_time TEXT,
    end_time TEXT,
    duration_seconds REAL,
    
    -- 进度信息
    current_step TEXT,
    total_steps INTEGER,
    completed_steps INTEGER DEFAULT 0,
    progress_percentage REAL DEFAULT 0.0 CHECK(progress_percentage >= 0.0 AND progress_percentage <= 100.0),
    
    -- 详细进度信息（JSON格式）
    progress_details TEXT DEFAULT '{}',
    
    -- 错误信息
    error_message TEXT,
    error_traceback TEXT,
    
    -- 结果统计
    documents_count INTEGER DEFAULT 0,
    nodes_count INTEGER DEFAULT 0,
    chunks_count INTEGER DEFAULT 0,
    
    -- 索引统计
    vector_indexed_count INTEGER DEFAULT 0,
    bm25_indexed_count INTEGER DEFAULT 0,
    metadata_indexed_count INTEGER DEFAULT 0,
    
    -- 元数据
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    
    -- 唯一约束
    UNIQUE(task_id)
);

-- 创建索引
CREATE INDEX idx_indexing_progress_task_id ON indexing_progress(task_id);
CREATE INDEX idx_indexing_progress_knowledge_base_id ON indexing_progress(knowledge_base_id);
CREATE INDEX idx_indexing_progress_status ON indexing_progress(status);
CREATE INDEX idx_indexing_progress_task_type ON indexing_progress(task_type);
CREATE INDEX idx_indexing_progress_created_at ON indexing_progress(created_at);

-- 创建索引构建步骤表
CREATE TABLE indexing_steps (
    id TEXT PRIMARY KEY,
    progress_id TEXT NOT NULL,
    step_name TEXT NOT NULL,
    step_order INTEGER NOT NULL,
    status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED')),
    start_time TEXT,
    end_time TEXT,
    duration_seconds REAL,
    
    -- 步骤详细信息
    description TEXT,
    details TEXT DEFAULT '{}',
    
    -- 错误信息
    error_message TEXT,
    
    -- 元数据
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    
    -- 外键约束
    FOREIGN KEY (progress_id) REFERENCES indexing_progress(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX idx_indexing_steps_progress_id ON indexing_steps(progress_id);
CREATE INDEX idx_indexing_steps_step_order ON indexing_steps(step_order);
CREATE INDEX idx_indexing_steps_status ON indexing_steps(status);

-- @down
-- 删除索引
DROP INDEX IF EXISTS idx_indexing_steps_status;
DROP INDEX IF EXISTS idx_indexing_steps_step_order;
DROP INDEX IF EXISTS idx_indexing_steps_progress_id;
DROP INDEX IF EXISTS idx_indexing_progress_created_at;
DROP INDEX IF EXISTS idx_indexing_progress_task_type;
DROP INDEX IF EXISTS idx_indexing_progress_status;
DROP INDEX IF EXISTS idx_indexing_progress_knowledge_base_id;
DROP INDEX IF EXISTS idx_indexing_progress_task_id;

-- 删除表
DROP TABLE IF EXISTS indexing_steps;
DROP TABLE IF EXISTS indexing_progress;