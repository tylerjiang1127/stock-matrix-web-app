-- =============================================================================
-- Migration 005: is_admin flag (gates admin-only endpoints, e.g. tier toggle)
-- =============================================================================
-- Idempotent. Apply:
--   docker exec -i stock_postgresql psql -U stock_user -d stock_technical_data \
--     < backend/migrations/005_is_admin.sql
-- =============================================================================

ALTER TABLE user_id_security ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- Bootstrap: make the project owner an admin so they can use the tier toggle.
UPDATE user_id_security SET is_admin = TRUE WHERE email = 'tylerjiang1127@gmail.com';
