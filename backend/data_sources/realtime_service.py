"""
Real-time stock data service.

Polls yfinance every 30s during market hours (9:30 AM – 4:00 PM ET, Mon–Fri)
for symbols that clients are actively watching. Pushes updates to connected
WebSocket clients. Only updates the current trading day's OHLCV on the 1d chart.
"""

import asyncio
import json
import time as _time
from datetime import datetime, time, timedelta
from typing import Dict, Set
from zoneinfo import ZoneInfo

import yfinance as yf
from fastapi import WebSocket

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
POLL_INTERVAL = 30  # seconds


class RealtimeService:

    def __init__(self):
        self._clients: Dict[WebSocket, Set[str]] = {}
        self._running = False
        self._task: asyncio.Task | None = None

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
            data = await asyncio.to_thread(
                self._download_latest, sym_list
            )
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

    # ── yfinance download (runs in thread) ────────────────

    @staticmethod
    def _download_latest(symbols: list[str]) -> Dict[str, dict]:
        results: Dict[str, dict] = {}
        today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

        for sym in symbols:
            try:
                yf_sym = sym.replace(".", "-")
                ticker = yf.Ticker(yf_sym)
                df = ticker.history(period="1d", interval="1m")
                if df is None or df.empty:
                    continue

                o = float(df["Open"].iloc[0])
                h = float(df["High"].max())
                l = float(df["Low"].min())
                c = float(df["Close"].iloc[-1])
                v = int(df["Volume"].sum())

                prev_close = None
                try:
                    info = ticker.fast_info
                    prev_close = float(info.get("previousClose", 0) or 0)
                except Exception:
                    pass

                change = None
                change_pct = None
                if prev_close and prev_close > 0:
                    change = round(c - prev_close, 4)
                    change_pct = round((change / prev_close) * 100, 2)

                ts = int(
                    datetime.strptime(today, "%Y-%m-%d")
                    .replace(tzinfo=ZoneInfo("America/New_York"))
                    .timestamp()
                )

                results[sym] = {
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

        return results
