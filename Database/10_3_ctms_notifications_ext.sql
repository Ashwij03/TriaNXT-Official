-- 10_3_ctms_notifications_ext.sql
-- =====================================================================
-- Phase-1 v2 wiring: additive extension columns for ctms_notifications.
--
-- The base table (03_operations_governance.sql) is the fully-normalized v2
-- per-recipient notification table. The frontend notificationService store
-- (notificationService.ts) carries fields the base columns cannot express
-- (the localStorage record's stable id, actor name/role, the raw study
-- code, and the record's metadata payload), so this file adds them
-- idempotently. The matching Alembic revision (c2f5a8e1b904) applies the
-- same columns for pure-Alembic databases.
--
-- Additive only: safe to run against any database that already has the
-- base table. No column is dropped or rewritten.
-- =====================================================================

ALTER TABLE ctms_notifications ADD COLUMN IF NOT EXISTS client_key   VARCHAR(255);
ALTER TABLE ctms_notifications ADD COLUMN IF NOT EXISTS actor_name   VARCHAR(255);
ALTER TABLE ctms_notifications ADD COLUMN IF NOT EXISTS actor_role   VARCHAR(100);
ALTER TABLE ctms_notifications ADD COLUMN IF NOT EXISTS study_code   VARCHAR(100);
ALTER TABLE ctms_notifications ADD COLUMN IF NOT EXISTS metadata     JSONB;

-- Per-user lookup by the frontend record id (the sync endpoint upserts on
-- (user_id, client_key)); the existing idx_notifications_user_read index in
-- 07_indexes.sql already covers the common list-by-user + unread filter.
CREATE INDEX IF NOT EXISTS idx_notifications_client_key ON ctms_notifications(user_id, client_key);

COMMIT;
