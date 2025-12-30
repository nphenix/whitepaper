-- Migration: (DEPRECATED) Extend Drafts Table
-- Version: 010
-- Created: 2025-01-XX
-- Description: Deprecated placeholder. Draft schema is handled by runtime compatibility in DraftService.
--
-- Rationale:
-- - This repository previously had a duplicate 002_*.sql migration file that broke migration loading.
-- - Keeping a no-op migration preserves historical intent without affecting schema.

-- @up
-- NO-OP (intentionally empty)
SELECT 1;

-- @down
-- NO-OP
SELECT 1;


