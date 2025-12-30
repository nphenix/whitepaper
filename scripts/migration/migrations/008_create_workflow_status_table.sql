-- Migration: Create Workflow Status Table
-- Version: 008
-- Created: 2025-01-XX
-- Description: Add table for storing workflow status and step progress

-- @up
-- 创建工作流状态表
CREATE TABLE IF NOT EXISTS workflow_status (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL UNIQUE,  -- 工作流ID（通常是outline_id或draft_id）
    current_status TEXT NOT NULL,  -- 当前状态：step1_selected, step2_optimized, step3_sources_selected, step4_generated
    step1_status TEXT DEFAULT 'pending',  -- 步骤1状态：pending, completed
    step2_status TEXT DEFAULT 'pending',  -- 步骤2状态：pending, completed
    step3_status TEXT DEFAULT 'pending',  -- 步骤3状态：pending, completed
    step4_status TEXT DEFAULT 'pending',  -- 步骤4状态：pending, completed
    step_data TEXT DEFAULT '{}',  -- JSON格式的步骤数据（用于数据传递）
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_workflow_status_workflow_id ON workflow_status(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_status_current_status ON workflow_status(current_status);
CREATE INDEX IF NOT EXISTS idx_workflow_status_updated_at ON workflow_status(updated_at);

-- @down
-- 删除索引
DROP INDEX IF EXISTS idx_workflow_status_updated_at;
DROP INDEX IF EXISTS idx_workflow_status_current_status;
DROP INDEX IF EXISTS idx_workflow_status_workflow_id;

-- 删除表
DROP TABLE IF EXISTS workflow_status;

