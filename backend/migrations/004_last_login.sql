-- =============================================================================
-- Migration 004: last_login_at (Gap B — activity sliver for the profile page)
-- =============================================================================
-- Idempotent. Apply:
--   docker exec -i stock_postgresql psql -U stock_user -d stock_technical_data \
--     < backend/migrations/004_last_login.sql
-- =============================================================================

ALTER TABLE user_id_security ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
