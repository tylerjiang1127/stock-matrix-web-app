-- =============================================================================
-- Migration 003: referred_by FK → ON DELETE SET NULL
-- =============================================================================
-- The self-referential referred_by FK had no ON DELETE action, so deleting a user
-- who referred others was blocked. SET NULL preserves the referred user and just
-- drops the dangling link; the `referrals` table retains the audit trail. Idempotent.
-- Apply: docker exec -i stock_postgresql psql -U stock_user -d stock_technical_data \
--          < backend/migrations/003_referred_by_on_delete.sql
-- =============================================================================

BEGIN;

ALTER TABLE user_id_security DROP CONSTRAINT IF EXISTS user_id_security_referred_by_fkey;
ALTER TABLE user_id_security
    ADD CONSTRAINT user_id_security_referred_by_fkey
    FOREIGN KEY (referred_by) REFERENCES user_id_security(id) ON DELETE SET NULL;

COMMIT;
