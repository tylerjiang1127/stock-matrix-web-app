-- =============================================================================
-- Migration 001: User System (tiers, Matrix AI Credits, referrals, anon usage)
-- =============================================================================
-- Phase 0 of USER_SYSTEM_PLAN.md. Idempotent and safe to re-run.
-- Apply to live DB:
--   docker exec -i stock_postgresql psql -U stock_user -d stock_technical_data \
--     < backend/migrations/001_user_system.sql
-- =============================================================================

BEGIN;

-- ── 1. Tier enum ────────────────────────────────────────────────────────────
DO $$ BEGIN
    CREATE TYPE user_tier AS ENUM ('base', 'premium');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- ── 2. Extend the auth table (kept lean: tier + referral graph only) ─────────
ALTER TABLE user_id_security ADD COLUMN IF NOT EXISTS tier user_tier NOT NULL DEFAULT 'base';
ALTER TABLE user_id_security ADD COLUMN IF NOT EXISTS referral_code VARCHAR(12) UNIQUE;
ALTER TABLE user_id_security ADD COLUMN IF NOT EXISTS referred_by UUID REFERENCES user_id_security(id);

-- ── 3. Credit wallet (1:1, fast balance cache; truth lives in credit_ledger) ─
CREATE TABLE IF NOT EXISTS user_credits (
    user_id UUID PRIMARY KEY REFERENCES user_id_security(id) ON DELETE CASCADE,
    base_credits INT NOT NULL DEFAULT 100,                                  -- monthly refresh, no rollover
    base_period DATE NOT NULL DEFAULT (date_trunc('month', (NOW() AT TIME ZONE 'US/Eastern')))::date,
    boost_credits INT NOT NULL DEFAULT 0,                                   -- never expires
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── 4. Append-only ledger (audit trail + token analytics) ────────────────────
CREATE TABLE IF NOT EXISTS credit_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    action VARCHAR(32) NOT NULL,        -- chat | screener | monthly_refresh | referral_bonus | welcome_bonus | purchase | admin_adjust
    credits_delta INT NOT NULL,         -- negative = spend, positive = grant
    bucket VARCHAR(8) NOT NULL,         -- base | boost
    balance_after INT NOT NULL,
    ref_type VARCHAR(32),
    ref_id VARCHAR(64),
    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(10,6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ledger_user_time ON credit_ledger(user_id, created_at DESC);

-- ── 5. Referrals (growth loop + fraud audit) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    referred_user_id UUID UNIQUE NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    referral_code VARCHAR(12) NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'pending',  -- pending | approved | rewarded | rejected
    referrer_reward INT NOT NULL DEFAULT 100,
    referee_reward INT NOT NULL DEFAULT 50,         -- double-sided welcome boost (LOCKED §8)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);

-- ── 6. Subscriptions (PLACEHOLDER — no payment provider wired yet) ───────────
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    plan VARCHAR(16) NOT NULL DEFAULT 'premium',
    status VARCHAR(16) NOT NULL DEFAULT 'inactive',  -- inactive | active | past_due | canceled
    provider VARCHAR(16),
    provider_ref VARCHAR(128),
    current_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);

-- ── 7. Anonymous AI usage (durable lifetime per-IP cap; raw IP never stored) ─
CREATE TABLE IF NOT EXISTS anon_ai_usage (
    ip_hash CHAR(64) PRIMARY KEY,       -- sha256(ip + server_salt)
    count INT NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW()
);

-- ── 8. Backfill existing users ───────────────────────────────────────────────
-- 8a. Give every existing user a referral code (only where missing).
UPDATE user_id_security
SET referral_code = upper(substr(md5(id::text || clock_timestamp()::text), 1, 8))
WHERE referral_code IS NULL;

-- 8b. Create a wallet for every existing user (base tier default = 100).
INSERT INTO user_credits (user_id, base_credits, base_period, boost_credits)
SELECT id, 100, (date_trunc('month', (NOW() AT TIME ZONE 'US/Eastern')))::date, 0
FROM user_id_security
ON CONFLICT (user_id) DO NOTHING;

COMMIT;
