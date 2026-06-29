-- =============================================================================
-- Migration 002: Subscription lifecycle dates + tier-change audit trail
-- =============================================================================
-- Adds the temporal fields needed to identify subscription status over time and
-- to drive credit-wallet adjustments on base<->premium switches. Idempotent.
-- Apply to live DB:
--   docker exec -i stock_postgresql psql -U stock_user -d stock_technical_data \
--     < backend/migrations/002_subscription_lifecycle.sql
-- See USER_SYSTEM_PLAN.md.
-- =============================================================================

BEGIN;

-- ── 1. Subscription period / lifecycle timestamps ────────────────────────────
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS current_period_start TIMESTAMPTZ;
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ;   -- first time this user ever became premium
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMPTZ;

-- ── 2. Tier-change audit trail ───────────────────────────────────────────────
-- `user_id_security.tier` is a fast cache; this is the history of how it changed.
-- Needed for churn/MRR analytics and to log credit effects of each switch.
CREATE TABLE IF NOT EXISTS tier_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    from_tier user_tier,
    to_tier user_tier NOT NULL,
    reason VARCHAR(32),          -- initial | upgrade | downgrade | lapse | admin
    effective_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tier_changes_user ON tier_changes(user_id, effective_at DESC);

-- ── 3. Backfill: an 'initial' tier row for existing users (audit from day one) ─
INSERT INTO tier_changes (user_id, from_tier, to_tier, reason, effective_at)
SELECT id, NULL, tier, 'initial', created_at
FROM user_id_security u
WHERE NOT EXISTS (SELECT 1 FROM tier_changes tc WHERE tc.user_id = u.id);

COMMIT;
