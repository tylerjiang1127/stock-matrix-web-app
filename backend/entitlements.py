"""
Central entitlements & Matrix AI Credit configuration.

This is the SINGLE SOURCE OF TRUTH for tier limits and credit costs. The backend
reads it for enforcement; the frontend receives it via GET /api/me/entitlements so
the UI never drifts from the rules. Do NOT scatter these numbers across the codebase
(the old hardcoded monitor-list `5` is exactly what this replaces).

See USER_SYSTEM_PLAN.md (decisions locked 2026-06-25).
"""

DEFAULT_TIER = "base"

# ── Tier limits ──────────────────────────────────────────────────────────────
ENTITLEMENTS = {
    "anonymous": {
        "monitor_max": 5,
        "ai_monthly_credits": 0,
    },
    "base": {
        "monitor_max": 10,
        "ai_monthly_credits": 100,
    },
    "premium": {
        "monitor_max": 20,
        "ai_monthly_credits": 500,
    },
}

# ── AI credit cost per action ────────────────────────────────────────────────
# Config-driven so chat can be re-priced later (it runs a multi-round tool loop)
# WITHOUT a migration. Launch: chat == screener == 1 (LOCKED §8).
AI_ACTION_COST = {
    "chat": 1,
    "screener": 1,
}

# ── Anonymous metering ───────────────────────────────────────────────────────
# 5 LIFETIME AI actions per IP. Enforced via Postgres anon_ai_usage
# (hashed IP) + Redis read-through cache. Bump here if it proves too stingy.
ANON_LIFETIME_AI_LIMIT = 5

# ── Referral rewards (boost credits — never expire) ──────────────────────────
REFERRAL_REFERRER_REWARD = 100   # to the inviter
REFERRAL_REFEREE_REWARD = 50     # double-sided welcome boost to the new user (LOCKED §8)


# ── Helpers ──────────────────────────────────────────────────────────────────
def get_entitlements(tier: str) -> dict:
    """Return the limits dict for a tier, falling back to the default tier."""
    return ENTITLEMENTS.get(tier or DEFAULT_TIER, ENTITLEMENTS[DEFAULT_TIER])


def monitor_max(tier: str) -> int:
    return get_entitlements(tier)["monitor_max"]


def monthly_credits(tier: str) -> int:
    return get_entitlements(tier)["ai_monthly_credits"]


def action_cost(action: str) -> int:
    """Credit cost of an AI action; unknown actions default to 1."""
    return AI_ACTION_COST.get(action, 1)
