"""
On-demand live quotes service.

When a user views a stock, the service:
  1. Checks PG live_quotes table for fresh data
  2. If missing/stale, fetches from yfinance, computes indicators, upserts
  3. Starts a background polling task (15s) to keep the row fresh
  4. Stops polling when all viewers leave (with 60s grace period)

During market-closed hours, step 3 is skipped (single fetch, no polling).
"""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_type, datetime, time as dtime, timezone
from typing import Dict, Optional, Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

from data_sources.indicator_calculator import IndicatorCalculator
from postgres_database import postgres_db

ET = ZoneInfo("America/New_York")
MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)
POLL_INTERVAL = 15  # seconds between yfinance fetches
STALE_THRESHOLD = 30  # seconds — data older than this triggers a refresh
GRACE_PERIOD = 60  # seconds to keep polling after last viewer leaves

_INDICATOR_COLUMNS = [
    "sma5", "sma10", "sma20", "sma30", "sma60", "sma120", "sma250",
    "ema5", "ema10", "ema20", "ema30", "ema60", "ema120", "ema250",
    "wma5", "wma10", "wma20", "wma30", "wma60", "wma120", "wma250",
    "dema5", "dema10", "dema20", "dema30", "dema60", "dema120", "dema250",
    "tema5", "tema10", "tema20", "tema30", "tema60", "tema120", "tema250",
    "kama5", "kama10", "kama20", "kama30", "kama60", "kama120", "kama250",
    "bbands_upper", "bbands_lower",
    "macd", "macd_signal", "macd_hist",
    "rsi",
    "k", "d", "j",
    "prev_macd_hist", "prev_k", "prev_d",
]

MA_PERIODS = [5, 10, 20, 30, 60, 120, 250]


class _SymbolState:
    __slots__ = ("viewer_count", "task", "last_unsubscribe_time")

    def __init__(self):
        self.viewer_count: int = 0
        self.task: Optional[asyncio.Task] = None
        self.last_unsubscribe_time: Optional[float] = None


class LiveQuotesService:

    def __init__(self):
        self._states: Dict[str, _SymbolState] = {}
        self._lock = asyncio.Lock()
        self._calc = IndicatorCalculator()
        self._executor = ThreadPoolExecutor(max_workers=4)

    # ── public API ────────────────────────────────────────

    @staticmethod
    def is_market_open() -> bool:
        now = datetime.now(ET)
        if now.weekday() >= 5:
            return False
        return MARKET_OPEN <= now.time() <= MARKET_CLOSE

    async def subscribe(self, symbol: str) -> dict:
        """Register a viewer and return current live data."""
        symbol = symbol.upper()
        async with self._lock:
            state = self._states.setdefault(symbol, _SymbolState())
            state.viewer_count += 1
            state.last_unsubscribe_time = None

        row = await self._query(symbol)

        if row is None:
            # No data at all — must wait for first fetch (cold start only)
            data = await self._fetch_and_upsert(symbol)
        elif self._is_stale(row):
            # Have stale data — return immediately, refresh in background
            data = self._row_to_dict(row)
            asyncio.create_task(self._fetch_and_upsert(symbol))
        else:
            data = self._row_to_dict(row)

        if self.is_market_open():
            await self._ensure_polling(symbol)

        return data or {}

    async def unsubscribe(self, symbol: str):
        """Remove a viewer. Polling stops after grace period if no viewers left."""
        symbol = symbol.upper()
        async with self._lock:
            state = self._states.get(symbol)
            if not state:
                return
            state.viewer_count = max(0, state.viewer_count - 1)
            if state.viewer_count == 0:
                state.last_unsubscribe_time = time.monotonic()

    async def get_quote(self, symbol: str) -> Optional[dict]:
        """Read latest data from PG without triggering a fetch."""
        row = await self._query(symbol.upper())
        return self._row_to_dict(row) if row else None

    async def stop_all(self):
        """Cancel every polling task (called on app shutdown)."""
        async with self._lock:
            for sym, state in self._states.items():
                if state.task and not state.task.done():
                    state.task.cancel()
            self._states.clear()
        self._executor.shutdown(wait=False)

    # ── polling lifecycle ────────────────────────────────

    async def _ensure_polling(self, symbol: str):
        async with self._lock:
            state = self._states.setdefault(symbol, _SymbolState())
            if state.task and not state.task.done():
                return
            state.task = asyncio.create_task(self._poll_loop(symbol))

    async def _poll_loop(self, symbol: str):
        """Fetch yfinance → compute indicators → upsert, repeat every POLL_INTERVAL."""
        try:
            while True:
                await asyncio.sleep(POLL_INTERVAL)

                if not self.is_market_open():
                    print(f"[live-quotes] market closed, stopping poll for {symbol}")
                    break

                state = self._states.get(symbol)
                if not state:
                    break

                if state.viewer_count == 0:
                    elapsed = time.monotonic() - (state.last_unsubscribe_time or 0)
                    if elapsed >= GRACE_PERIOD:
                        print(f"[live-quotes] no viewers for {symbol}, stopping poll")
                        break

                await self._fetch_and_upsert(symbol)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[live-quotes] poll error for {symbol}: {e}")

    # ── data fetch + indicator compute ───────────────────

    async def _fetch_and_upsert(self, symbol: str) -> Optional[dict]:
        try:
            data = await asyncio.get_event_loop().run_in_executor(
                self._executor, self._fetch_sync, symbol
            )
            if data is None:
                return None

            await self._upsert(symbol, data)
            return data

        except Exception as e:
            print(f"[live-quotes] fetch error for {symbol}: {e}")
            return None

    def _fetch_sync(self, symbol: str) -> Optional[dict]:
        """Run in thread: yfinance download + indicator computation."""
        yf_sym = symbol.replace(".", "-")
        try:
            # 5y of history so recursive indicators (EMA/DEMA/TEMA/KAMA) warm up and
            # converge — 1y left EMA250 stuck at its SMA seed (TA-Lib unstable period),
            # which made the live point jump away from the historical line.
            hist = yf.Ticker(yf_sym).history(period="5y", interval="1d")
            if hist is None or hist.empty:
                return None

            hist.index = hist.index.tz_localize(None)

            today = hist.iloc[-1]
            prev_close = float(hist.iloc[-2]["Close"]) if len(hist) >= 2 else None
            close = float(today["Close"])

            change = round(close - prev_close, 4) if prev_close else None
            change_pct = (round((close - prev_close) / prev_close * 100, 4)
                          if prev_close and prev_close > 0 else None)

            trading_date = hist.index[-1].date()

            result: dict = {
                "symbol": symbol,
                "open": self._safe(today.get("Open")),
                "high": self._safe(today.get("High")),
                "low": self._safe(today.get("Low")),
                "close": self._safe(close),
                "volume": int(today.get("Volume", 0)),
                "prev_close": self._safe(prev_close),
                "change": self._safe(change),
                "change_pct": self._safe(change_pct),
                "trading_date": trading_date,
            }

            indicators = self._calc.compute_all_indicators(hist, "1d")
            last_idx = hist.index[-1]

            for ma_type in ["sma", "ema", "wma", "dema", "tema", "kama"]:
                ma_df = indicators.get(ma_type)
                if ma_df is not None and not ma_df.empty and last_idx in ma_df.index:
                    row = ma_df.loc[last_idx]
                    for p in MA_PERIODS:
                        col = str(p)
                        if col in row:
                            result[f"{ma_type}{p}"] = self._safe(row[col])

                    if ma_type == "sma":
                        result["bbands_upper"] = self._safe(row.get("bbands_upper"))
                        result["bbands_lower"] = self._safe(row.get("bbands_lower"))

            macd_data = indicators.get("macd")
            if macd_data:
                for key, series in [("macd", "macd"), ("macd_signal", "macd_signal_line"), ("macd_hist", "macd_hist")]:
                    s = macd_data.get(series)
                    if s is not None and last_idx in s.index:
                        result[key] = self._safe(s.loc[last_idx])

            rsi_data = indicators.get("rsi")
            if rsi_data:
                s = rsi_data.get("rsi")
                if s is not None and last_idx in s.index:
                    result["rsi"] = self._safe(s.loc[last_idx])

            kdj_data = indicators.get("kdj")
            if kdj_data:
                for key in ["k", "d", "j"]:
                    s = kdj_data.get(key)
                    if s is not None and last_idx in s.index:
                        result[key] = self._safe(s.loc[last_idx])

            if len(hist) >= 2:
                prev_idx = hist.index[-2]
                macd_hist_s = macd_data.get("macd_hist") if macd_data else None
                if macd_hist_s is not None and prev_idx in macd_hist_s.index:
                    result["prev_macd_hist"] = self._safe(macd_hist_s.loc[prev_idx])
                if kdj_data:
                    for key in ["k", "d"]:
                        s = kdj_data.get(key)
                        if s is not None and prev_idx in s.index:
                            result[f"prev_{key}"] = self._safe(s.loc[prev_idx])

            return result

        except Exception as e:
            print(f"[live-quotes] yfinance error for {symbol}: {e}")
            return None

    @staticmethod
    def _safe(val) -> Any:
        if val is None:
            return None
        if isinstance(val, (np.floating, float)):
            if pd.isna(val) or np.isinf(val):
                return None
            return round(float(val), 4)
        if isinstance(val, (np.integer,)):
            return int(val)
        return val

    # ── PG read / write ──────────────────────────────────

    async def _query(self, symbol: str):
        async with postgres_db.pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM live_quotes WHERE symbol = $1", symbol
            )

    def _is_stale(self, row) -> bool:
        updated = row["updated_at"]
        if updated is None:
            return True
        now = datetime.now(updated.tzinfo or ET)
        age = (now - updated).total_seconds()
        return age > STALE_THRESHOLD

    async def _upsert(self, symbol: str, data: dict):
        cols = ["symbol"]
        vals = [symbol]
        idx = 2

        for col in _INDICATOR_COLUMNS + ["open", "high", "low", "close", "volume",
                                          "prev_close", "change", "change_pct",
                                          "trading_date"]:
            if col in data:
                cols.append(col)
                vals.append(data[col])
                idx += 1

        cols.append("updated_at")
        vals.append(datetime.now(ET))
        idx += 1

        placeholders = ", ".join(f"${i+1}" for i in range(len(cols)))
        col_names = ", ".join(f'"{c}"' for c in cols)

        updates = ", ".join(
            f'"{c}" = EXCLUDED."{c}"'
            for c in cols if c != "symbol"
        )

        sql = f"""
            INSERT INTO live_quotes ({col_names})
            VALUES ({placeholders})
            ON CONFLICT (symbol) DO UPDATE SET {updates}
        """

        async with postgres_db.pool.acquire() as conn:
            await conn.execute(sql, *vals)

    @staticmethod
    def _row_to_dict(row) -> dict:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
            elif (hasattr(v, "is_nan") and v.is_nan()) or (isinstance(v, float) and pd.isna(v)):
                d[k] = None
            elif hasattr(v, "__float__"):
                d[k] = round(float(v), 4)
        td = row.get("trading_date")
        if td:
            if isinstance(td, (date_type, datetime)):
                market_midnight_utc = datetime(td.year, td.month, td.day, tzinfo=timezone.utc)
                d["market_date_ts"] = int(market_midnight_utc.timestamp())
        elif row.get("updated_at"):
            updated = row["updated_at"]
            et_dt = updated.astimezone(ET)
            wd = et_dt.weekday()
            if wd == 5:
                et_dt -= pd.Timedelta(days=1)
            elif wd == 6:
                et_dt -= pd.Timedelta(days=2)
            market_midnight_utc = datetime(et_dt.year, et_dt.month, et_dt.day, tzinfo=timezone.utc)
            d["market_date_ts"] = int(market_midnight_utc.timestamp())
        return d
