"""
Referral system — double-sided boost-credit rewards.

Flow (LOCKED §8):
- At registration, if a valid `?ref=CODE` was supplied, a `referrals` row is created
  `pending` and the new user's `referred_by` is stamped.
- When the referred user verifies their email, the referral auto-approves and grants
  the referrer +100 and the referee +50 boost credits (non-expiring). One reward per
  referee (enforced by the UNIQUE constraint on `referred_user_id`); self-referral is
  rejected.
"""

import uuid

from entitlements import REFERRAL_REFERRER_REWARD, REFERRAL_REFEREE_REWARD


class ReferralService:
    def __init__(self, postgres_db, credits_service):
        self.db = postgres_db
        self.credits = credits_service

    @staticmethod
    def _uid(v):
        return uuid.UUID(v) if isinstance(v, str) else v

    async def record_referral(self, referrer_id, referred_user_id, code: str) -> bool:
        """Create a pending referral at registration time. Idempotent per referee."""
        referrer = self._uid(referrer_id)
        referred = self._uid(referred_user_id)
        if referrer == referred:  # can't refer yourself
            return False
        try:
            await self.db.execute_query(
                """
                INSERT INTO referrals
                    (referrer_id, referred_user_id, referral_code, status, referrer_reward, referee_reward)
                VALUES ($1, $2, $3, 'pending', $4, $5)
                ON CONFLICT (referred_user_id) DO NOTHING
                """,
                referrer, referred, code, REFERRAL_REFERRER_REWARD, REFERRAL_REFEREE_REWARD,
            )
            return True
        except Exception as e:
            print(f"❌ record_referral failed (non-fatal): {e}")
            return False

    async def approve_on_verify(self, referred_user_id) -> None:
        """Approve a pending referral and grant both sides their boost credits."""
        referred = self._uid(referred_user_id)
        try:
            row = await self.db.fetch_one(
                "SELECT * FROM referrals WHERE referred_user_id = $1 AND status = 'pending'",
                referred,
            )
            if not row:
                return
            # Double-sided grant (boost bucket — never expires).
            await self.credits.grant(
                row["referrer_id"], row["referrer_reward"], action="referral_bonus",
                bucket="boost", ref_type="referral", ref_id=str(referred),
            )
            if row["referee_reward"] > 0:
                await self.credits.grant(
                    referred, row["referee_reward"], action="welcome_bonus",
                    bucket="boost", ref_type="referral", ref_id=str(row["referrer_id"]),
                )
            await self.db.execute_query(
                "UPDATE referrals SET status = 'rewarded', approved_at = NOW() WHERE id = $1",
                row["id"],
            )
            print(f"✅ Referral rewarded: referrer {row['referrer_id']} +{row['referrer_reward']}, "
                  f"referee {referred} +{row['referee_reward']} boost")
        except Exception as e:
            print(f"❌ approve_on_verify failed (non-fatal): {e}")

    async def get_summary(self, user_id) -> dict:
        """Referral stats for the profile card."""
        uid = self._uid(user_id)
        total = await self.db.fetch_one(
            "SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = $1", uid
        )
        rewarded = await self.db.fetch_one(
            """
            SELECT COUNT(*) AS c, COALESCE(SUM(referrer_reward), 0) AS credits
            FROM referrals WHERE referrer_id = $1 AND status = 'rewarded'
            """,
            uid,
        )
        return {
            "total_referred": total["c"] if total else 0,
            "successful": rewarded["c"] if rewarded else 0,
            "credits_earned": int(rewarded["credits"]) if rewarded else 0,
        }
