import asyncio
import os
import httpx
import yfinance as yf
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime

INDEX_TICKERS = {
    "^DJI": "Dow Jones",
    "^GSPC": "S&P 500",
    "^IXIC": "Nasdaq Composite",
    "^RUT": "Russell 2000",
    "^SOX": "SOX Semiconductor",
    "^VIX": "VIX",
}

TREASURY_TICKERS = {
    "^IRX": "3-Month",
    "^FVX": "5-Year",
    "^TNX": "10-Year",
    "^TYX": "30-Year",
}

ASSET_TICKERS = {
    "DX-Y.NYB": "USD (DXY)",
    "GC=F": "Gold",
    "CL=F": "WTI Crude Oil",
    "BTC-USD": "Bitcoin",
}

ETF_TICKERS = ["SPY", "QQQ", "IWM", "SMH", "IGV"]

AV_BASE_URL = "https://www.alphavantage.co/query"
AV_TREASURY_MAP = {
    "3month": "3-Month",
    "5year": "5-Year",
    "10year": "10-Year",
    "30year": "30-Year",
}


class MarketDataGatherer:
    """Gathers market data from PostgreSQL, MongoDB, and yfinance."""

    def __init__(self, pg_repo, stock_metadata_repo):
        self.pg_repo = pg_repo
        self.metadata_repo = stock_metadata_repo

    MAG7_SYMBOLS = ["NVDA", "MSFT", "AAPL", "GOOGL", "AMZN", "META", "TSLA"]
    KEY_STOCK_SYMBOLS = [
        "NVDA", "AMD", "AVGO", "MRVL", "MU", "QCOM",
        "CRM", "NOW", "SNOW", "PANW", "CRWD", "PLTR",
        "CEG", "VST", "VRT",
    ]

    async def gather_all(self) -> Dict[str, Any]:
        """Run all data gathering queries in parallel."""
        sector_map = await self._build_sector_map()

        (
            top_movers, volume_anomalies, breadth, sector_perf,
            key_technicals, mag7_data,
            external,
        ) = await asyncio.gather(
            self.pg_repo.get_top_movers(limit=15),
            self.pg_repo.get_volume_anomalies(threshold=2.0, limit=15),
            self.pg_repo.get_market_breadth(),
            self.pg_repo.get_sector_performance(sector_map),
            self._get_key_technicals(self.KEY_STOCK_SYMBOLS),
            self._get_key_technicals(self.MAG7_SYMBOLS),
            self._fetch_external_market_data(),
        )

        return {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "top_movers": top_movers,
            "volume_anomalies": volume_anomalies,
            "market_breadth": breadth,
            "sector_performance": sector_perf,
            "key_technicals": key_technicals,
            "mag7_data": mag7_data,
            **external,
        }

    # ── yfinance: indices, treasuries, assets, ETFs ───────────

    async def _fetch_external_market_data(self) -> Dict[str, Any]:
        """Fetch from yfinance, fall back to Alpha Vantage for missing sections."""
        result = await self._fetch_yfinance_data()

        missing = {k for k in ("indices", "treasuries", "major_assets", "etf_technicals")
                   if not result.get(k)}
        if missing:
            print(f"[DataGatherer] yfinance missing {missing}, trying Alpha Vantage")
            av = await self._fetch_av_fallback(missing)
            for k in missing:
                if av.get(k):
                    result[k] = av[k]
                    print(f"[DataGatherer] AV fallback filled: {k} ({len(av[k])} items)")

        return result

    async def _fetch_yfinance_data(self) -> Dict[str, Any]:
        """Primary source: yfinance."""
        try:
            short_tickers = (
                list(INDEX_TICKERS) + list(TREASURY_TICKERS) + list(ASSET_TICKERS)
            )
            short_df, etf_df = await asyncio.gather(
                asyncio.to_thread(
                    yf.download, short_tickers, period="5d", progress=False, auto_adjust=True,
                ),
                asyncio.to_thread(
                    yf.download, ETF_TICKERS, period="1y", progress=False, auto_adjust=True,
                ),
            )
            return {
                "indices": self._extract_price_data(short_df, INDEX_TICKERS),
                "treasuries": self._extract_treasury_data(short_df, TREASURY_TICKERS),
                "major_assets": self._extract_price_data(short_df, ASSET_TICKERS),
                "etf_technicals": self._extract_etf_technicals(etf_df),
            }
        except Exception as e:
            print(f"[DataGatherer] yfinance error: {e}")
            return {
                "indices": [], "treasuries": [],
                "major_assets": [], "etf_technicals": [],
            }

    @staticmethod
    def _get_series(df, col, ticker):
        """Safely extract a series from a single- or multi-ticker DataFrame."""
        if df is None or df.empty:
            return pd.Series(dtype=float)
        try:
            if isinstance(df.columns, pd.MultiIndex):
                return df[(col, ticker)].dropna()
            return df[col].dropna()
        except KeyError:
            return pd.Series(dtype=float)

    def _extract_price_data(self, df, ticker_map) -> list:
        results = []
        for ticker, name in ticker_map.items():
            closes = self._get_series(df, "Close", ticker)
            if len(closes) < 2:
                continue
            close_val = round(float(closes.iloc[-1]), 2)
            prev_val = float(closes.iloc[-2])
            change_pct = round((close_val - prev_val) / prev_val * 100, 2) if prev_val else 0
            results.append({
                "name": name, "ticker": ticker,
                "close": close_val,
                "change": round(close_val - prev_val, 2),
                "change_pct": change_pct,
            })
        return results

    def _extract_treasury_data(self, df, ticker_map) -> list:
        results = []
        for ticker, maturity in ticker_map.items():
            closes = self._get_series(df, "Close", ticker)
            if len(closes) < 2:
                continue
            yield_val = round(float(closes.iloc[-1]), 3)
            prev_val = float(closes.iloc[-2])
            results.append({
                "maturity": maturity, "ticker": ticker,
                "yield_pct": yield_val,
                "change": round(yield_val - prev_val, 3),
            })
        # compute 3M-10Y spread if both available
        by_mat = {r["maturity"]: r["yield_pct"] for r in results}
        if "3-Month" in by_mat and "10-Year" in by_mat:
            spread = round(by_mat["10-Year"] - by_mat["3-Month"], 3)
            results.append({
                "maturity": "3M-10Y Spread",
                "ticker": "-",
                "yield_pct": spread,
                "change": None,
            })
        return results

    def _extract_etf_technicals(self, df) -> list:
        results = []
        for ticker in ETF_TICKERS:
            closes = self._get_series(df, "Close", ticker)
            volumes = self._get_series(df, "Volume", ticker)
            if len(closes) < 20:
                continue
            close_val = round(float(closes.iloc[-1]), 2)
            prev_val = float(closes.iloc[-2])
            change_pct = round((close_val - prev_val) / prev_val * 100, 2)
            results.append({
                "symbol": ticker,
                "close": close_val,
                "change_pct": change_pct,
                "sma20": round(float(closes.tail(20).mean()), 2),
                "sma50": round(float(closes.tail(50).mean()), 2) if len(closes) >= 50 else None,
                "sma200": round(float(closes.tail(200).mean()), 2) if len(closes) >= 200 else None,
                "rsi": self._compute_rsi(closes),
                "volume": int(volumes.iloc[-1]) if len(volumes) > 0 else None,
            })
        return results

    @staticmethod
    def _compute_rsi(closes, period=14):
        if len(closes) < period + 1:
            return None
        delta = closes.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return round(float(val), 1) if pd.notna(val) else None

    # ── Alpha Vantage fallback ────────────────────────────────

    async def _fetch_av_fallback(self, missing: set) -> Dict[str, Any]:
        """Fallback to Alpha Vantage when yfinance data is incomplete."""
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        if not api_key:
            print("[DataGatherer] No ALPHA_VANTAGE_API_KEY, skipping fallback")
            return {}

        result = {}
        self._av_sem = asyncio.Semaphore(1)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                coros = {}
                if "treasuries" in missing:
                    coros["treasuries"] = self._av_treasuries(client, api_key)
                if "major_assets" in missing:
                    coros["major_assets"] = self._av_assets(client, api_key)
                if "etf_technicals" in missing:
                    coros["etf_technicals"] = self._av_etf_technicals(client, api_key)

                if coros:
                    gathered = await asyncio.gather(
                        *coros.values(), return_exceptions=True
                    )
                    for key, val in zip(coros.keys(), gathered):
                        if isinstance(val, Exception):
                            print(f"[DataGatherer] AV {key} failed: {val}")
                        elif val:
                            result[key] = val
        except Exception as e:
            print(f"[DataGatherer] AV fallback error: {e}")

        return result

    async def _av_call(self, client, api_key, **params) -> dict:
        """Single Alpha Vantage API call, throttled to avoid burst detection."""
        async with self._av_sem:
            params["apikey"] = api_key
            resp = await client.get(AV_BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            if "Note" in data or "Information" in data:
                msg = data.get("Note") or data.get("Information", "")
                raise RuntimeError(f"AV API limit: {msg[:120]}")
            await asyncio.sleep(1.0)
            return data

    # ── AV: Treasury Yields ──

    async def _av_treasuries(self, client, api_key) -> list:
        tasks = [
            self._av_single_treasury(client, api_key, m, label)
            for m, label in AV_TREASURY_MAP.items()
        ]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        results = [r for r in raw if isinstance(r, dict)]

        by_mat = {r["maturity"]: r["yield_pct"] for r in results}
        if "3-Month" in by_mat and "10-Year" in by_mat:
            results.append({
                "maturity": "3M-10Y Spread", "ticker": "-",
                "yield_pct": round(by_mat["10-Year"] - by_mat["3-Month"], 3),
                "change": None,
            })
        return results

    async def _av_single_treasury(self, client, api_key, maturity, label):
        data = await self._av_call(
            client, api_key, function="TREASURY_YIELD",
            interval="daily", maturity=maturity,
        )
        points = data.get("data", [])
        if len(points) >= 2 and points[0]["value"] != "." and points[1]["value"] != ".":
            cur = float(points[0]["value"])
            prev = float(points[1]["value"])
            return {
                "maturity": label, "ticker": maturity,
                "yield_pct": round(cur, 3),
                "change": round(cur - prev, 3),
            }
        return None

    # ── AV: Major Assets (Gold via XAU/USD, Oil via WTI, BTC via crypto) ──

    async def _av_assets(self, client, api_key) -> list:
        tasks = [
            self._av_wti(client, api_key),
            self._av_exchange_rate(client, api_key, "BTC", "USD", "Bitcoin"),
        ]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in raw if isinstance(r, dict) and r.get("close")]

    async def _av_exchange_rate(self, client, api_key, from_cur, to_cur, name):
        data = await self._av_call(
            client, api_key, function="CURRENCY_EXCHANGE_RATE",
            from_currency=from_cur, to_currency=to_cur,
        )
        rate_info = data.get("Realtime Currency Exchange Rate", {})
        rate = rate_info.get("5. Exchange Rate")
        if rate:
            return {
                "name": name, "ticker": f"{from_cur}/{to_cur}",
                "close": round(float(rate), 2),
                "change": 0, "change_pct": 0,
            }
        return {}

    async def _av_wti(self, client, api_key):
        data = await self._av_call(
            client, api_key, function="WTI", interval="daily",
        )
        points = data.get("data", [])
        if len(points) >= 2 and points[0]["value"] != "." and points[1]["value"] != ".":
            cur = float(points[0]["value"])
            prev = float(points[1]["value"])
            change = round(cur - prev, 2)
            return {
                "name": "WTI Crude Oil", "ticker": "WTI",
                "close": round(cur, 2), "change": change,
                "change_pct": round(change / prev * 100, 2) if prev else 0,
            }
        return {}

    # ── AV: ETF Technicals (GLOBAL_QUOTE + RSI + SMA endpoints) ──

    async def _av_etf_technicals(self, client, api_key) -> list:
        tasks = [self._av_single_etf(client, api_key, t) for t in ETF_TICKERS]
        raw = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in raw if isinstance(r, dict)]

    async def _av_single_etf(self, client, api_key, symbol):
        quote, rsi_resp = await asyncio.gather(
            self._av_call(client, api_key, function="GLOBAL_QUOTE", symbol=symbol),
            self._av_call(client, api_key, function="RSI", symbol=symbol,
                          interval="daily", time_period="14", series_type="close"),
            return_exceptions=True,
        )

        gq = quote.get("Global Quote", {}) if isinstance(quote, dict) else {}
        close = float(gq["05. price"]) if gq.get("05. price") else 0
        prev = float(gq["08. previous close"]) if gq.get("08. previous close") else 0
        if not close:
            return None

        return {
            "symbol": symbol,
            "close": round(close, 2),
            "change_pct": round((close - prev) / prev * 100, 2) if prev else 0,
            "sma20": None, "sma50": None, "sma200": None,
            "rsi": self._av_indicator_val(rsi_resp, "RSI"),
            "volume": int(gq["06. volume"]) if gq.get("06. volume") else None,
        }

    @staticmethod
    def _av_indicator_val(resp, indicator):
        """Extract the latest value from an AV technical indicator response."""
        if isinstance(resp, Exception) or not isinstance(resp, dict):
            return None
        ts = resp.get(f"Technical Analysis: {indicator}", {})
        if not ts:
            return None
        first = next(iter(ts.values()), {})
        val = first.get(indicator)
        if val:
            return round(float(val), 1 if indicator == "RSI" else 2)
        return None

    # ── PostgreSQL: individual stock data ─────────────────────

    async def _get_key_technicals(self, symbols: List[str]) -> List[Dict]:
        """Fetch latest technical data for individual stocks from PG."""
        results = []
        try:
            pool = self.pg_repo.db.pool
            async with pool.acquire() as conn:
                for symbol in symbols:
                    row = await conn.fetchrow("""
                        SELECT symbol, close, open, high, low, volume,
                               rsi, macd_hist, sma5, sma20, sma60, sma250,
                               bbands_upper, bbands_lower, ema20
                        FROM interval_1d_technical
                        WHERE symbol = $1
                        ORDER BY datetime_index DESC LIMIT 1
                    """, symbol)
                    if row:
                        prev = await conn.fetchrow("""
                            SELECT close FROM interval_1d_technical
                            WHERE symbol = $1
                            ORDER BY datetime_index DESC OFFSET 1 LIMIT 1
                        """, symbol)
                        prev_close = float(prev["close"]) if prev and prev["close"] is not None else None
                        cur_close = float(row["close"]) if row["close"] else None
                        change_pct = None
                        if prev_close and cur_close and prev_close > 0:
                            change_pct = round((cur_close - prev_close) / prev_close * 100, 2)

                        results.append({
                            "symbol": symbol,
                            "close": round(float(row["close"]), 2) if row["close"] else None,
                            "volume": int(row["volume"]) if row["volume"] else None,
                            "rsi": round(float(row["rsi"]), 1) if row["rsi"] else None,
                            "macd_hist": round(float(row["macd_hist"]), 3) if row["macd_hist"] else None,
                            "sma20": round(float(row["sma20"]), 2) if row["sma20"] else None,
                            "sma50": round(float(row["sma60"]), 2) if row["sma60"] else None,
                            "sma200": round(float(row["sma250"]), 2) if row["sma250"] else None,
                            "bbands_upper": round(float(row["bbands_upper"]), 2) if row["bbands_upper"] else None,
                            "bbands_lower": round(float(row["bbands_lower"]), 2) if row["bbands_lower"] else None,
                            "change_pct": change_pct,
                        })
        except Exception as e:
            print(f"[DataGatherer] Error fetching key technicals: {e}")
        return results

    # ── MongoDB: sector mapping ───────────────────────────────

    async def _build_sector_map(self) -> Dict[str, str]:
        """Build {symbol: sector} mapping from MongoDB stock_metadata."""
        try:
            cursor = self.metadata_repo.db.stock_metadata.find(
                {},
                {"_id": 0, "symbol": 1, "company_overview.sector": 1},
            )
            sector_map = {}
            async for doc in cursor:
                symbol = doc.get("symbol")
                overview = doc.get("company_overview", {})
                sector = overview.get("sector")
                if symbol and sector:
                    sector_map[symbol] = sector
            return sector_map
        except Exception as e:
            print(f"Failed to build sector map: {e}")
            return {}
