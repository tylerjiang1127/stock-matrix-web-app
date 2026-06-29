"""
Activity tracking — semantic user-action events (Phase 7, see USER_SYSTEM_PLAN.md §9).

Events live in MongoDB (`activity_events`), NOT Postgres — high-volume append-only
writes don't belong in the operational PG pool. We log *named* events with properties
(login, signup, screener_query, chat_message, ...), not raw clicks. Logging is
fire-and-forget and never breaks the request path.

Privacy: no raw IPs (pass a hash if needed), no credentials/secrets in properties.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
from typing import Optional, Dict, Any, List


class ActivityService:
    def __init__(self, mongo_db):
        # mongo_db may be None if Mongo isn't configured — log() then no-ops.
        self.collection = mongo_db["activity_events"] if mongo_db is not None else None

    async def ensure_indexes(self) -> None:
        if self.collection is None:
            return
        try:
            await self.collection.create_index([("user_id", 1), ("ts", -1)])
            await self.collection.create_index([("event_type", 1), ("ts", -1)])
        except Exception as e:
            print(f"[activity] ensure_indexes failed (non-fatal): {e}")

    async def log(self, event_type: str, user_id: Optional[str] = None,
                  props: Optional[Dict[str, Any]] = None, ip_hash: Optional[str] = None) -> None:
        """Record one event. Never raises — analytics must not break the request."""
        if self.collection is None:
            return
        try:
            await self.collection.insert_one({
                "event_type": event_type,
                "user_id": user_id,           # None for anonymous
                "properties": props or {},
                "ip_hash": ip_hash,           # only ever a hash, never a raw IP
                "ts": datetime.now(_ET),
            })
        except Exception as e:
            print(f"[activity] log '{event_type}' failed (non-fatal): {e}")

    async def recent(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        if self.collection is None:
            return []
        cursor = self.collection.find(
            {"user_id": user_id}, {"_id": 0}
        ).sort("ts", -1).limit(limit)
        rows = await cursor.to_list(length=limit)
        for r in rows:
            if r.get("ts"):
                r["ts"] = r["ts"].isoformat()
        return rows
