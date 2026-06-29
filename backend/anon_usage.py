"""
Anonymous AI usage metering — 10 LIFETIME actions per IP (LOCKED §8).

Postgres `anon_ai_usage` is the durable source of truth (keyed by a salted SHA-256 of
the IP — the raw IP is never stored, for privacy). A Redis cache sits in front so we
don't hit PG on every request; the "already exhausted" case is served from cache
without a DB round-trip. The cache has a TTL purely to bound Redis memory — PG remains
authoritative, so an expired cache entry just falls through and re-caches.

This is a soft nudge toward registration, not airtight security (shared/rotating IPs
pool usage). See USER_SYSTEM_PLAN.md §2.5.
"""

import hashlib
import os
from typing import Tuple, Dict, Any

from entitlements import ANON_LIFETIME_AI_LIMIT

ANON_CACHE_TTL = 30 * 24 * 3600  # 30 days — cache only; PG is truth
_DEFAULT_SALT = "stock-matrix-anon-salt-change-me"


class AnonUsageService:
    def __init__(self, postgres_db, redis_db, limit: int = ANON_LIFETIME_AI_LIMIT, salt: str = None):
        self.db = postgres_db
        self.redis = redis_db
        self.limit = limit
        self.salt = salt or os.getenv("ANON_IP_SALT", _DEFAULT_SALT)

    # ── hashing / cache helpers ──────────────────────────────────────────────
    def _hash(self, ip: str) -> str:
        return hashlib.sha256(f"{ip}{self.salt}".encode()).hexdigest()

    def _cache_key(self, h: str) -> str:
        return f"anon_ai:{h}"

    async def _cached_count(self, h: str):
        try:
            v = await self.redis.get(self._cache_key(h))
            return int(v) if v is not None else None
        except Exception:
            return None

    async def _set_cache(self, h: str, count: int) -> None:
        try:
            await self.redis.set(self._cache_key(h), count, expire=ANON_CACHE_TTL)
        except Exception:
            pass

    # ── public API ───────────────────────────────────────────────────────────
    async def try_consume(self, ip: str) -> Tuple[bool, int, int]:
        """Consume one anonymous AI action for this IP.

        Returns (allowed, count, limit). When blocked, `count` is the current usage.
        """
        h = self._hash(ip)

        # Fast path: cache already knows this IP is exhausted → no DB round-trip.
        cached = await self._cached_count(h)
        if cached is not None and cached >= self.limit:
            return False, cached, self.limit

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT count FROM anon_ai_usage WHERE ip_hash = $1 FOR UPDATE", h
                )
                current = row["count"] if row else 0
                if current >= self.limit:
                    await self._set_cache(h, current)
                    return False, current, self.limit
                if row:
                    await conn.execute(
                        "UPDATE anon_ai_usage SET count = count + 1, last_seen = NOW() WHERE ip_hash = $1", h
                    )
                else:
                    await conn.execute(
                        "INSERT INTO anon_ai_usage (ip_hash, count) VALUES ($1, 1)", h
                    )
                new = current + 1
        await self._set_cache(h, new)
        return True, new, self.limit

    async def release(self, ip: str) -> None:
        """Refund one action (e.g. the AI call produced no output)."""
        h = self._hash(ip)
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    "SELECT count FROM anon_ai_usage WHERE ip_hash = $1 FOR UPDATE", h
                )
                if row and row["count"] > 0:
                    await conn.execute(
                        "UPDATE anon_ai_usage SET count = count - 1 WHERE ip_hash = $1", h
                    )
                    await self._set_cache(h, row["count"] - 1)

    async def get_status(self, ip: str) -> Dict[str, Any]:
        """Read-only usage for this IP (for the entitlements endpoint / soft paywall)."""
        h = self._hash(ip)
        cached = await self._cached_count(h)
        if cached is not None:
            count = cached
        else:
            row = await self.db.fetch_one("SELECT count FROM anon_ai_usage WHERE ip_hash = $1", h)
            count = row["count"] if row else 0
            await self._set_cache(h, count)
        return {"used": count, "limit": self.limit, "remaining": max(0, self.limit - count)}
