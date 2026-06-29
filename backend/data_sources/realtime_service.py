"""
Real-time stock data service.

Polls yfinance every 15s during market hours (9:30 AM – 4:00 PM ET, Mon–Fri)
for symbols that clients are actively watching. Pushes updates to connected
WebSocket clients.

v2 optimizations:
  - Concurrent per-symbol downloads via ThreadPoolExecutor (vs sequential)
  - prev_close cached once per day (vs per-poll fast_info call)
  - Poll interval 15s (vs 30s)
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time
from typing import Dict, Set
from zoneinfo import ZoneInfo

import yfinance as yf
from fastapi import WebSocket

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
POLL_INTERVAL = 15  # seconds


class RealtimeService:

    def __init__(self):
        self._clients: Dict[WebSocket, Set[str]] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._prev_close: Dict[str, float] = {}
        self._prev_close_date: str | None = None

    # ── market-hours check ────────────────────────────────

    @staticmethod
    def is_market_open() -> bool:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        return MARKET_OPEN <= now.time() <= MARKET_CLOSE

    @staticmethod
    def _today_str() -> str:
        return datetime.now(ET).strftime("%Y-%m-%d")

    # ── client management ─────────────────────────────────

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._clients[ws] = set()
        await ws.send_json({
            "type": "status",
            "market_open": self.is_market_open(),
        })

    def disconnect(self, ws: WebSocket):
        self._clients.pop(ws, None)

    async def handle_message(self, ws: WebSocket, data: dict):
        action = data.get("action")
        symbol = (data.get("symbol") or "").upper()
        if not symbol:
            return

        if action == "subscribe":
            self._clients.setdefault(ws, set()).add(symbol)
            if self.is_market_open():
                await self._fetch_and_send(ws, symbol)
        elif action == "unsubscribe":
            subs = self._clients.get(ws, set())
            subs.discard(symbol)

    def _active_symbols(self) -> Set[str]:
        syms: Set[str] = set()
        for subs in self._clients.values():
            syms |= subs
        return syms

    # ── polling loop ──────────────────────────────────────

    def start(self):
        if self._task is None or self._task.done():
            self._running = True
            self._task = asyncio.create_task(self._poll_loop())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _poll_loop(self):
        while self._running:
            try:
                if self.is_market_open() and self._clients:
                    symbols = self._active_symbols()
                    if symbols:
                        await self._poll_symbols(symbols)
                await asyncio.sleep(POLL_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[realtime] poll error: {e}")
                await asyncio.sleep(POLL_INTERVAL)

    async def _poll_symbols(self, symbols: Set[str]):
        sym_list = list(symbols)
        try:
            data = await asyncio.to_thread(self._download_latest, sym_list)
        except Exception as e:
            print(f"[realtime] download error: {e}")
            return

        dead: list[WebSocket] = []
        for ws, subs in self._clients.items():
            for sym in subs:
                if sym in data:
                    try:
                        await ws.send_json(data[sym])
                    except Exception:
                        dead.append(ws)
                        break
        for ws in dead:
            self.disconnect(ws)

    async def _fetch_and_send(self, ws: WebSocket, symbol: str):
        try:
            data = await asyncio.to_thread(self._download_latest, [symbol])
            if symbol in data:
                await ws.send_json(data[symbol])
        except Exception:
            pass

    # ── prev_close cache (once per day) ───────────────────

    def _ensure_prev_close(self, symbols: list[str]):
        today = self._today_str()
        if self._prev_close_date != today:
            self._prev_close = {}
            self._prev_close_date = today

        missing = [s for s in symbols if s not in self._prev_close]
        if not missing:
            return

        def fetch_prev(sym):
            try:
                yf_sym = sym.replace(".", "-")
                hist = yf.Ticker(yf_sym).history(period="5d", interval="1d")
                if hist is not None and len(hist) >= 2:
                    return sym, float(hist["Close"].iloc[-2])
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=10) as pool:
            for result in pool.map(fetch_prev, missing):
                if result:
                    sym, pc = result
                    self._prev_close[sym] = pc

    # ── concurrent yfinance download (runs in thread) ─────

    def _download_latest(self, symbols: list[str]) -> Dict[str, dict]:
        results: Dict[str, dict] = {}
        today = self._today_str()

        self._ensure_prev_close(symbols)

        from zoneinfo import ZoneInfo
        ts = int(
            datetime.strptime(today, "%Y-%m-%d")
            .replace(tzinfo=ZoneInfo("UTC"))
            .timestamp()
        )

        def fetch_one(sym: str):
            yf_sym = sym.replace(".", "-")
            try:
                df = yf.Ticker(yf_sym).history(period="1d", interval="1m")
                if df is None or df.empty:
                    return None

                o = float(df["Open"].iloc[0])
                h = float(df["High"].max())
                l = float(df["Low"].min())
                c = float(df["Close"].iloc[-1])
                v = int(df["Volume"].sum())

                prev_close = self._prev_close.get(sym)
                change = round(c - prev_close, 4) if prev_close else None
                change_pct = (round((change / prev_close) * 100, 2)
                              if prev_close and prev_close > 0 else None)

                return sym, {
                    "type": "price_update",
                    "symbol": sym,
                    "time": ts,
                    "date": today,
                    "open": round(o, 4),
                    "high": round(h, 4),
                    "low": round(l, 4),
                    "close": round(c, 4),
                    "volume": v,
                    "prev_close": prev_close,
                    "change": change,
                    "change_pct": change_pct,
                    "market_open": True,
                }
            except Exception as e:
                print(f"[realtime] error fetching {sym}: {e}")
                return None

        with ThreadPoolExecutor(max_workers=10) as pool:
            for result in pool.map(fetch_one, symbols):
                if result:
                    sym, data = result
                    results[sym] = data

        return results
