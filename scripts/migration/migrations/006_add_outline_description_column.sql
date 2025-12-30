-- Migration: Add description column to outlines table
-- Version: 006
-- Created: 2025-12-24
-- Description: Add description column to outlines table if it doesn't exist

-- @up
-- 注意：此迁移使用Python脚本安全地添加列
-- 实际的SQL执行在Python脚本中处理，以检查列是否存在
-- 如果直接使用ALTER TABLE，当列已存在时会失败

-- 由于SQLite的限制，我们需要在Python层面检查列是否存在
-- 这个迁移文件主要用于记录，实际执行由Python脚本处理
-- 如果outlines表存在但description列不存在，添加它
-- 如果列已存在，跳过操作

-- 注意：迁移管理器会执行Python脚本而不是这个SQL
-- 实际的列添加逻辑在 add_outline_description_safe.py 中

-- @down
-- 注意：SQLite不支持DROP COLUMN
-- 回滚操作需要手动处理或重建表
-- 这里不提供回滚SQL，因为删除列需要重建表

