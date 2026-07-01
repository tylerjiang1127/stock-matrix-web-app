"""
Priority-aware concurrency gate for AI (Deepseek) calls.

Why: every AI feature (chat, screener, daily report) shares one DeepseekClient and,
without a limit, all in-flight requests compete equally for the upstream API. To give
paying users a better experience under load, we cap the number of concurrent Deepseek
calls and, when that cap is saturated, admit higher-priority waiters first.

Priority is carried via a ContextVar set per-request in the AI router (so the value
flows down into the deeply-nested streaming generators without threading it through
every call signature). Lower number = served first.

Fairness: strict priority across classes (premium preempts base preempts anon), FIFO
within the same class (monotonic counter as the heap tiebreaker). The slot is held only
for the duration of a single upstream call/stream round, so a premium user jumps ahead
at each round boundary rather than waiting behind a base user's entire multi-round chat.
"""

import asyncio
import contextlib
import contextvars
import heapq
import itertools

# Lower value = higher priority (admitted first when the gate is saturated).
PRIORITY_PREMIUM = 0
PRIORITY_BASE = 1
PRIORITY_ANON = 2
PRIORITY_BACKGROUND = 3  # scheduled jobs (e.g. nightly report) — yields to live users

# Set per-request in the AI router; read inside DeepseekClient when acquiring a slot.
ai_priority_var: contextvars.ContextVar = contextvars.ContextVar(
    "ai_priority", default=PRIORITY_BASE
)


class PriorityGate:
    """Bounded-concurrency gate that wakes the highest-priority waiter first.

    Uses the standard "hand-off" model: on release, if anyone is waiting, the freed
    slot is transferred directly to the best waiter (active count unchanged); only when
    there are no waiters does the active count drop.
    """

    def __init__(self, max_concurrency: int):
        self.max_concurrency = max(1, int(max_concurrency))
        self._active = 0
        self._waiters: list = []  # heap of (priority, seq, future)
        self._counter = itertools.count()
        self._lock = asyncio.Lock()

    async def acquire(self, priority: int = PRIORITY_BASE) -> None:
        async with self._lock:
            if self._active < self.max_concurrency:
                self._active += 1
                return
            fut = asyncio.get_running_loop().create_future()
            heapq.heappush(self._waiters, (priority, next(self._counter), fut))

        try:
            await fut
        except asyncio.CancelledError:
            # Cancelled while waiting (e.g. client disconnected mid-stream). Either we
            # were already handed a slot — release it — or we're still queued — drop out.
            async with self._lock:
                if fut.done() and not fut.cancelled():
                    self._release_locked()
                else:
                    self._waiters = [w for w in self._waiters if w[2] is not fut]
                    heapq.heapify(self._waiters)
            raise

    def _release_locked(self) -> None:
        while self._waiters:
            _, _, fut = heapq.heappop(self._waiters)
            if not fut.done():
                fut.set_result(None)  # hand the slot to this waiter
                return
            # Waiter was cancelled before being served — try the next one.
        self._active -= 1

    async def release(self) -> None:
        async with self._lock:
            self._release_locked()

    @contextlib.asynccontextmanager
    async def slot(self, priority: int = PRIORITY_BASE):
        await self.acquire(priority)
        try:
            yield
        finally:
            await self.release()

    def stats(self) -> dict:
        return {
            "max_concurrency": self.max_concurrency,
            "active": self._active,
            "waiting": len(self._waiters),
        }
