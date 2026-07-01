"""
Tier switching (base <-> premium) with the credit + audit behavior locked in §2.6.

- A switch is an explicit, audited operation (writes `tier_changes`), never a silent
  flip of the `tier` flag.
- Upgrade → premium: credits base is set to the premium allotment immediately (they
  paid), a subscription row goes active.
- Downgrade → base: current month's credits are KEPT (no claw-back); the next lazy
  monthly refresh naturally drops base to the base allotment. Boost is always untouched.

Payment is still a placeholder — tier is flipped by the admin endpoint for now.
"""

import uuid


class TierService:
    def __init__(self, postgres_db, credits_service):
        self.db = postgres_db
        self.credits = credits_service

    @staticmethod
    def _uid(v):
        return uuid.UUID(v) if isinstance(v, str) else v

    async def set_tier(self, user_id, new_tier: str, reason: str = "admin") -> dict:
        if new_tier not in ("base", "premium"):
            raise ValueError(f"invalid tier: {new_tier}")
        uid = self._uid(user_id)

        # 1. Flip the tier + write audit + subscription state (one transaction).
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchval(
                    "SELECT tier FROM user_id_security WHERE id = $1 FOR UPDATE", uid
                )
                if current is None:
                    raise LookupError("user not found")
                if current == new_tier:
                    return {"changed": False, "tier": current}

                await conn.execute(
                    "UPDATE user_id_security SET tier = $2, updated_at = NOW() WHERE id = $1",
                    uid, new_tier,
                )
                await conn.execute(
                    "INSERT INTO tier_changes (user_id, from_tier, to_tier, reason) VALUES ($1, $2, $3, $4)",
                    uid, current, new_tier, reason,
                )
                if new_tier == "premium":
                    await conn.execute(
                        """
                        INSERT INTO subscriptions
                            (user_id, plan, status, current_period_start, current_period_end, started_at)
                        VALUES ($1, 'premium', 'active', NOW(), NOW() + INTERVAL '30 days',
                                COALESCE((SELECT MIN(started_at) FROM subscriptions WHERE user_id = $1), NOW()))
                        """,
                        uid,
                    )
                else:  # downgrade
                    await conn.execute(
                        "UPDATE subscriptions SET status = 'canceled', canceled_at = NOW() "
                        "WHERE user_id = $1 AND status = 'active'",
                        uid,
                    )

        # 2. Credit side (separate txn; CreditsService manages its own locking).
        #    Upgrade → grant the premium allotment now. Downgrade → keep current month's
        #    credits; the next lazy refresh (now tier=base) drops base to the base allotment.
        if new_tier == "premium":
            await self.credits.set_base_allotment(user_id, "premium", action="tier_upgrade")

        wallet = await self.credits.get_wallet(user_id)
        return {"changed": True, "from": current, "to": new_tier, "credits": wallet}
