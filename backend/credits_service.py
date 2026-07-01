"""
Matrix AI Credits — wallet service.

Source of truth = `credit_ledger` (append-only); `user_credits` is a fast balance
cache. All mutations are atomic (transaction + `SELECT ... FOR UPDATE`) so concurrent
AI calls can never double-spend. Monthly base credits refresh lazily on access (no
cron). Spend order: base first, then boost (boost never expires). See USER_SYSTEM_PLAN.md.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Optional, List, Dict, Any

from entitlements import monthly_credits

ET = ZoneInfo("US/Eastern")


def current_period() -> date:
    """First day of the current month in US/Eastern (the credit reset boundary)."""
    now = datetime.now(ET)
    return date(now.year, now.month, 1)


def next_reset(period: date) -> date:
    """First day of the month after `period` — when base credits next refresh."""
    if period.month == 12:
        return date(period.year + 1, 1, 1)
    return date(period.year, period.month + 1, 1)


class InsufficientCredits(Exception):
    """Raised when a wallet cannot cover the cost of an action."""


class UserNotFound(Exception):
    """Raised when no user row exists for the given id."""


@dataclass
class SpendResult:
    base_spent: int
    boost_spent: int
    cost: int
    base_credits: int   # balance after
    boost_credits: int  # balance after
    tier: Optional[str] = None  # spender's tier (for AI priority, etc.)

    @property
    def total(self) -> int:
        return self.base_credits + self.boost_credits


class CreditsService:
    def __init__(self, postgres_db):
        self.db = postgres_db

    # ── helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def _uid(user_id) -> uuid.UUID:
        return uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    _SELECT_LOCKED = """
        SELECT c.base_credits, c.base_period, c.boost_credits, u.tier
        FROM user_credits c
        JOIN user_id_security u ON u.id = c.user_id
        WHERE c.user_id = $1
        FOR UPDATE OF c
    """

    async def _ledger(self, conn, uid, action, credits_delta, bucket, balance_after,
                      ref_type=None, ref_id=None,
                      input_tokens=None, output_tokens=None, cost_usd=None):
        await conn.execute(
            """
            INSERT INTO credit_ledger
                (user_id, action, credits_delta, bucket, balance_after,
                 ref_type, ref_id, input_tokens, output_tokens, cost_usd)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            uid, action, credits_delta, bucket, balance_after,
            ref_type, ref_id, input_tokens, output_tokens, cost_usd,
        )

    async def _load_locked(self, conn, uid):
        """Lock the wallet row, creating it if missing and refreshing if stale."""
        row = await conn.fetchrow(self._SELECT_LOCKED, uid)
        if row is None:
            tier = await conn.fetchval("SELECT tier FROM user_id_security WHERE id = $1", uid)
            if tier is None:
                raise UserNotFound(str(uid))
            await conn.execute(
                """
                INSERT INTO user_credits (user_id, base_credits, base_period, boost_credits)
                VALUES ($1, $2, $3, 0) ON CONFLICT (user_id) DO NOTHING
                """,
                uid, monthly_credits(tier), current_period(),
            )
            row = await conn.fetchrow(self._SELECT_LOCKED, uid)

        # Lazy monthly refresh (no rollover): reset base to the tier allotment.
        period = current_period()
        if row["base_period"] < period:
            new_base = monthly_credits(row["tier"])
            await conn.execute(
                "UPDATE user_credits SET base_credits = $2, base_period = $3, updated_at = NOW() WHERE user_id = $1",
                uid, new_base, period,
            )
            total_after = new_base + row["boost_credits"]
            await self._ledger(conn, uid, "monthly_refresh",
                               new_base - row["base_credits"], "base", total_after)
            row = await conn.fetchrow(self._SELECT_LOCKED, uid)
        return row

    async def _apply(self, conn, uid, base_delta, boost_delta, action,
                     ref_type=None, ref_id=None,
                     input_tokens=None, output_tokens=None, cost_usd=None):
        """Apply deltas to the (already-locked) wallet and write ledger row(s)."""
        rec = await conn.fetchrow(
            """
            UPDATE user_credits
            SET base_credits = base_credits + $2,
                boost_credits = boost_credits + $3,
                updated_at = NOW()
            WHERE user_id = $1
            RETURNING base_credits, boost_credits
            """,
            uid, base_delta, boost_delta,
        )
        total_after = rec["base_credits"] + rec["boost_credits"]
        # Attach token/cost analytics to the first row only.
        if base_delta != 0:
            await self._ledger(conn, uid, action, base_delta, "base", total_after,
                               ref_type, ref_id, input_tokens, output_tokens, cost_usd)
            input_tokens = output_tokens = cost_usd = None
        if boost_delta != 0:
            await self._ledger(conn, uid, action, boost_delta, "boost", total_after,
                               ref_type, ref_id, input_tokens, output_tokens, cost_usd)
        return rec["base_credits"], rec["boost_credits"]

    @staticmethod
    def _wallet_dict(row) -> Dict[str, Any]:
        period = row["base_period"]
        return {
            "tier": row["tier"],
            "base_credits": row["base_credits"],
            "boost_credits": row["boost_credits"],
            "total": row["base_credits"] + row["boost_credits"],
            "monthly_allotment": monthly_credits(row["tier"]),
            "base_period": period.isoformat(),
            "resets_on": next_reset(period).isoformat(),
        }

    # ── public API ───────────────────────────────────────────────────────────
    async def get_wallet(self, user_id) -> Dict[str, Any]:
        """Return wallet balances (with lazy refresh applied)."""
        uid = self._uid(user_id)
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                row = await self._load_locked(conn, uid)
                return self._wallet_dict(row)

    async def spend(self, user_id, action: str, cost: int,
                    ref_type: Optional[str] = None, ref_id: Optional[str] = None,
                    input_tokens=None, output_tokens=None, cost_usd=None) -> SpendResult:
        """Atomically reserve `cost` credits (base first, then boost).

        Raises InsufficientCredits if the wallet can't cover it.
        """
        uid = self._uid(user_id)
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                row = await self._load_locked(conn, uid)
                total = row["base_credits"] + row["boost_credits"]
                if total < cost:
                    raise InsufficientCredits(f"need {cost}, have {total}")
                base_spent = min(cost, row["base_credits"])
                boost_spent = cost - base_spent
                new_base, new_boost = await self._apply(
                    conn, uid, -base_spent, -boost_spent, action,
                    ref_type, ref_id, input_tokens, output_tokens, cost_usd,
                )
                return SpendResult(base_spent, boost_spent, cost, new_base, new_boost,
                                   tier=row["tier"])

    async def refund(self, user_id, spend_result: SpendResult,
                     reason: str = "refund",
                     ref_type: Optional[str] = None, ref_id: Optional[str] = None) -> None:
        """Reverse a prior spend exactly (same bucket split)."""
        if spend_result.cost <= 0:
            return
        uid = self._uid(user_id)
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await self._load_locked(conn, uid)
                await self._apply(conn, uid, spend_result.base_spent,
                                  spend_result.boost_spent, reason, ref_type, ref_id)

    async def grant(self, user_id, amount: int, action: str, bucket: str = "boost",
                    ref_type: Optional[str] = None, ref_id: Optional[str] = None) -> Dict[str, Any]:
        """Grant credits (referrals/purchases/admin). Defaults to the boost bucket."""
        if amount <= 0:
            return await self.get_wallet(user_id)
        uid = self._uid(user_id)
        base_delta = amount if bucket == "base" else 0
        boost_delta = amount if bucket == "boost" else 0
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                await self._load_locked(conn, uid)
                await self._apply(conn, uid, base_delta, boost_delta, action, ref_type, ref_id)
                row = await self._load_locked(conn, uid)
                return self._wallet_dict(row)

    async def set_base_allotment(self, user_id, tier: str, action: str = "tier_upgrade") -> int:
        """Set base credits to a tier's monthly allotment immediately (e.g. on upgrade).

        Used by tier upgrades (§2.6): paying users get the full premium quota now. Stamps
        the current period and logs the net change to the ledger. Returns the new base.
        """
        from entitlements import monthly_credits
        uid = self._uid(user_id)
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                row = await self._load_locked(conn, uid)
                new_base = monthly_credits(tier)
                delta = new_base - row["base_credits"]
                await conn.execute(
                    "UPDATE user_credits SET base_credits = $2, base_period = $3, updated_at = NOW() WHERE user_id = $1",
                    uid, new_base, current_period(),
                )
                await self._ledger(conn, uid, action, delta, "base", new_base + row["boost_credits"])
                return new_base

    async def history(self, user_id, limit: int = 50) -> List[Dict[str, Any]]:
        uid = self._uid(user_id)
        rows = await self.db.fetch_many(
            """
            SELECT action, credits_delta, bucket, balance_after, ref_type, ref_id, created_at
            FROM credit_ledger WHERE user_id = $1
            ORDER BY created_at DESC LIMIT $2
            """,
            uid, limit,
        )
        out = []
        for r in rows:
            d = dict(r)
            if d.get("created_at"):
                d["created_at"] = d["created_at"].isoformat()
            out.append(d)
        return out
