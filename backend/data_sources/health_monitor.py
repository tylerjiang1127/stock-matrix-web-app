import time
import json
from typing import Optional, Dict, Any


class HealthMonitor:

    FAILURE_THRESHOLD = 5
    COOLDOWN_SECONDS = 300
    HALF_OPEN_PROBE_SUCCESS = 2
    TTL_24H = 86400
    DLQ_MAX = 1000

    def __init__(self, redis_db):
        self.redis = redis_db

    # ── circuit state ────────────────────────────────────────

    async def _get(self, key: str) -> Optional[str]:
        return await self.redis.get(key)

    async def _set(self, key: str, value: Any, expire: int = TTL_24H):
        await self.redis.set(key, value if isinstance(value, str) else json.dumps(value), expire=expire)

    async def _get_circuit_state(self, source: str) -> str:
        val = await self._get(f"health:{source}:circuit_state")
        return val if val in ("closed", "open", "half_open") else "closed"

    async def reset_all(self, sources: list[str] | None = None):
        if sources is None:
            sources = ["alpha_vantage", "yfinance", "finnhub"]
        for src in sources:
            await self._set(f"health:{src}:circuit_state", "closed")
            await self._set(f"health:{src}:consecutive_failures", "0")

    async def _get_int(self, key: str) -> int:
        val = await self._get(key)
        try:
            return int(val)
        except (TypeError, ValueError):
            return 0

    async def is_source_healthy(self, source_name: str) -> bool:
        state = await self._get_circuit_state(source_name)
        if state == "closed":
            return True
        if state == "open":
            last_fail = await self._get_int(f"health:{source_name}:last_failure_time")
            if last_fail and time.time() - last_fail > self.COOLDOWN_SECONDS:
                await self._set(f"health:{source_name}:circuit_state", "half_open")
                await self._set(f"health:{source_name}:half_open_successes", "0")
                return True
            return False
        # half_open — allow probes
        return True

    async def record_attempt(self, source_name: str, success: bool, latency_ms: float = 0.0):
        hour_bucket = int(time.time() // 3600)
        if success:
            await self._set(f"health:{source_name}:success:{hour_bucket}", "1", expire=self.TTL_24H)
            state = await self._get_circuit_state(source_name)
            if state == "half_open":
                ho_key = f"health:{source_name}:half_open_successes"
                count = await self._get_int(ho_key) + 1
                if count >= self.HALF_OPEN_PROBE_SUCCESS:
                    await self._set(f"health:{source_name}:circuit_state", "closed")
                    await self._set(f"health:{source_name}:consecutive_failures", "0")
                else:
                    await self._set(ho_key, str(count))
            else:
                await self._set(f"health:{source_name}:consecutive_failures", "0")
        else:
            fail_key = f"health:{source_name}:consecutive_failures"
            failures = await self._get_int(fail_key) + 1
            await self._set(fail_key, str(failures))
            await self._set(f"health:{source_name}:last_failure_time", str(int(time.time())))
            await self._set(f"health:{source_name}:failure:{hour_bucket}", "1", expire=self.TTL_24H)
            if failures >= self.FAILURE_THRESHOLD:
                await self._set(f"health:{source_name}:circuit_state", "open")

    async def record_validation_failure(self, source_name: str, errors: list):
        entry = json.dumps({
            'source': source_name,
            'errors': errors,
            'timestamp': int(time.time()),
        })
        if self.redis.redis:
            await self.redis.redis.lpush("health:dead_letter_queue", entry)
            await self.redis.redis.ltrim("health:dead_letter_queue", 0, self.DLQ_MAX - 1)

    async def get_source_stats(self, source_name: str) -> Dict[str, Any]:
        state = await self._get_circuit_state(source_name)
        failures = await self._get_int(f"health:{source_name}:consecutive_failures")
        last_fail = await self._get_int(f"health:{source_name}:last_failure_time")
        return {
            'source': source_name,
            'circuit_state': state,
            'consecutive_failures': failures,
            'last_failure_time': last_fail,
        }
