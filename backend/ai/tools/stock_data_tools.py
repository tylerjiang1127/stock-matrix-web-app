"""
Tool definitions and handlers for the AI chat agent.
Each tool queries PG or MongoDB and returns structured data.
"""

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def _clean(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(i) for i in obj]
    return obj


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get OHLCV price data for a stock symbol. Returns recent daily prices with open, high, low, close, volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol (e.g. AAPL, MSFT)"},
                    "days": {"type": "integer", "description": "Number of recent trading days to return (default 30, max 250)", "default": 30},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_indicators",
            "description": "Get technical indicator values for a stock: RSI, MACD (line, signal, histogram), and Bollinger Bands (upper, middle, lower).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    "days": {"type": "integer", "description": "Number of recent trading days (default 30)", "default": 30},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_moving_averages",
            "description": "Get moving average values (SMA, EMA) for a stock at multiple periods (5, 10, 20, 30, 60, 120, 250 day).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    "ma_type": {"type": "string", "enum": ["sma", "ema"], "description": "Type of moving average", "default": "sma"},
                    "days": {"type": "integer", "description": "Number of recent days (default 5)", "default": 5},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_overview",
            "description": "Get company fundamentals: PE ratio, market cap, EPS, dividend yield, sector, industry, description, and more.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_statements",
            "description": "Get income statement, balance sheet, or cash flow data for a stock (quarterly or annual).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                    "statement": {"type": "string", "enum": ["income_statement", "balance_sheet", "cash_flow"], "description": "Which financial statement"},
                    "period": {"type": "string", "enum": ["quarterly", "annual"], "description": "Reporting period", "default": "quarterly"},
                    "limit": {"type": "integer", "description": "Number of recent periods (default 4)", "default": 4},
                },
                "required": ["symbol", "statement"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_news_sentiment",
            "description": "Get recent news articles and sentiment analysis for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_summary",
            "description": "Get today's market overview: top gainers/losers, market breadth (advance/decline ratio, % above SMA50/200), and sector performance.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_stocks",
            "description": "Compare two or more stocks side-by-side on key metrics: price, PE ratio, market cap, RSI, recent performance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of stock ticker symbols to compare (2-5 symbols)",
                    },
                },
                "required": ["symbols"],
            },
        },
    },
]


class ToolRegistry:
    """Maps tool names to async handler functions."""

    def __init__(self, pg_repo, stock_metadata_repo, data_source_manager):
        self.pg_repo = pg_repo
        self.metadata_repo = stock_metadata_repo
        self.dsm = data_source_manager
        self._handlers = {
            "get_stock_price": self.get_stock_price,
            "get_technical_indicators": self.get_technical_indicators,
            "get_moving_averages": self.get_moving_averages,
            "get_company_overview": self.get_company_overview,
            "get_financial_statements": self.get_financial_statements,
            "get_news_sentiment": self.get_news_sentiment,
            "get_market_summary": self.get_market_summary,
            "compare_stocks": self.compare_stocks,
        }

    def as_dict(self) -> Dict:
        return self._handlers

    async def get_stock_price(self, symbol: str, days: int = 30) -> Dict:
        symbol = symbol.upper()
        days = min(days, 250)
        query = f"""
            SELECT datetime_index, open, high, low, close, volume
            FROM interval_1d_technical
            WHERE symbol = $1 AND close IS NOT NULL
            ORDER BY datetime_index DESC
            LIMIT $2
        """
        async with self.pg_repo.db.pool.acquire() as conn:
            rows = await conn.fetch(query, symbol, days)
        if not rows:
            return {"error": f"No price data found for {symbol}"}
        data = []
        for r in rows:
            data.append({
                "date": r["datetime_index"].strftime("%Y-%m-%d"),
                "open": _clean(r["open"]),
                "high": _clean(r["high"]),
                "low": _clean(r["low"]),
                "close": _clean(r["close"]),
                "volume": _clean(r["volume"]),
            })
        data.reverse()
        latest = data[-1]
        prev = data[-2] if len(data) > 1 else data[-1]
        change = round((latest["close"] - prev["close"]) / prev["close"] * 100, 2) if prev["close"] else 0
        return {
            "symbol": symbol,
            "latest_close": latest["close"],
            "daily_change_pct": change,
            "period": f"Last {len(data)} trading days",
            "prices": data,
        }

    async def get_technical_indicators(self, symbol: str, days: int = 30) -> Dict:
        symbol = symbol.upper()
        days = min(days, 250)
        query = """
            SELECT datetime_index, close, rsi,
                   macd, macd_signal, macd_hist,
                   bbands_upper, bbands_middle, bbands_lower
            FROM interval_1d_technical
            WHERE symbol = $1 AND close IS NOT NULL
            ORDER BY datetime_index DESC
            LIMIT $2
        """
        async with self.pg_repo.db.pool.acquire() as conn:
            rows = await conn.fetch(query, symbol, days)
        if not rows:
            return {"error": f"No technical data found for {symbol}"}
        latest = rows[0]
        return _clean({
            "symbol": symbol,
            "date": latest["datetime_index"].strftime("%Y-%m-%d"),
            "rsi": latest["rsi"],
            "macd": {"line": latest["macd"], "signal": latest["macd_signal"], "histogram": latest["macd_hist"]},
            "bollinger_bands": {"upper": latest["bbands_upper"], "middle": latest["bbands_middle"], "lower": latest["bbands_lower"]},
            "close": latest["close"],
            "recent_rsi": [{"date": r["datetime_index"].strftime("%Y-%m-%d"), "rsi": r["rsi"], "close": r["close"]}
                           for r in list(reversed(rows))[-10:]],
        })

    async def get_moving_averages(self, symbol: str, ma_type: str = "sma", days: int = 5) -> Dict:
        symbol = symbol.upper()
        days = min(days, 30)
        prefix = ma_type.lower() if ma_type.lower() in ("sma", "ema") else "sma"
        cols = ", ".join([f"{prefix}{p}" for p in [5, 10, 20, 30, 60, 120, 250]])
        query = f"""
            SELECT datetime_index, close, {cols}
            FROM interval_1d_technical
            WHERE symbol = $1 AND close IS NOT NULL
            ORDER BY datetime_index DESC
            LIMIT $2
        """
        async with self.pg_repo.db.pool.acquire() as conn:
            rows = await conn.fetch(query, symbol, days)
        if not rows:
            return {"error": f"No data found for {symbol}"}
        latest = rows[0]
        result = {
            "symbol": symbol,
            "date": latest["datetime_index"].strftime("%Y-%m-%d"),
            "close": _clean(latest["close"]),
            "moving_averages": {},
        }
        for p in [5, 10, 20, 30, 60, 120, 250]:
            val = latest.get(f"{prefix}{p}")
            if val is not None:
                result["moving_averages"][f"{prefix.upper()}{p}"] = _clean(val)
        return result

    async def get_company_overview(self, symbol: str) -> Dict:
        symbol = symbol.upper()
        if self.dsm:
            overview_result = await self.dsm.fetch_company_overview(symbol)
            if overview_result.success and overview_result.data:
                data = overview_result.data
                keys = ["Name", "Symbol", "Sector", "Industry", "MarketCapitalization",
                        "PERatio", "ForwardPE", "PEGRatio", "EPS", "DividendYield",
                        "BookValue", "ReturnOnEquityTTM", "ReturnOnAssetsTTM",
                        "ProfitMargin", "Beta", "52WeekHigh", "52WeekLow",
                        "50DayMovingAverage", "200DayMovingAverage", "Description"]
                return {k: data.get(k) for k in keys if data.get(k) is not None}
        if self.metadata_repo:
            meta = await self.metadata_repo.get_stock_metadata(symbol)
            if meta and "company_overview" in meta:
                return meta["company_overview"]
        return {"error": f"No company data found for {symbol}"}

    async def get_financial_statements(self, symbol: str, statement: str = "income_statement",
                                        period: str = "quarterly", limit: int = 4) -> Dict:
        symbol = symbol.upper()
        if not self.metadata_repo:
            return {"error": "Financial data not available"}
        meta = await self.metadata_repo.get_stock_metadata(symbol)
        if not meta:
            return {"error": f"No metadata found for {symbol}"}
        fund = meta.get("stock_fundamental", {})
        period_data = fund.get(period, {})
        stmt_data = period_data.get(statement, {})
        records = stmt_data.get("data", [])
        if not records:
            return {"error": f"No {period} {statement} data for {symbol}"}
        return {
            "symbol": symbol,
            "statement": statement,
            "period": period,
            "data": records[:limit],
        }

    async def get_news_sentiment(self, symbol: str) -> Dict:
        symbol = symbol.upper()
        if not self.dsm:
            return {"error": "News data not available"}
        result = await self.dsm.fetch_news_sentiment(symbol)
        if not result.success:
            return {"error": f"Could not fetch news for {symbol}"}
        data = result.data
        articles = data.get("articles", [])[:5]
        return {
            "symbol": symbol,
            "average_sentiment": data.get("average_sentiment_score", 0),
            "sentiment_label": data.get("average_sentiment_label", "Neutral"),
            "total_articles": data.get("total_articles", 0),
            "recent_articles": [
                {"title": a.get("title", ""), "sentiment": a.get("overall_sentiment_label", ""),
                 "score": a.get("overall_sentiment_score", 0), "source": a.get("source", "")}
                for a in articles
            ],
        }

    async def get_market_summary(self) -> Dict:
        breadth = await self.pg_repo.get_market_breadth()
        movers = await self.pg_repo.get_top_movers(limit=5)
        return _clean({
            "market_breadth": breadth,
            "top_gainers": movers.get("gainers", [])[:5],
            "top_losers": movers.get("losers", [])[:5],
        })

    async def compare_stocks(self, symbols: List[str]) -> Dict:
        symbols = [s.upper() for s in symbols[:5]]
        comparisons = []
        for sym in symbols:
            query = """
                SELECT close, rsi, macd, sma20, sma60, volume
                FROM interval_1d_technical
                WHERE symbol = $1 AND close IS NOT NULL
                ORDER BY datetime_index DESC
                LIMIT 2
            """
            async with self.pg_repo.db.pool.acquire() as conn:
                rows = await conn.fetch(query, sym)
            if len(rows) < 2:
                comparisons.append({"symbol": sym, "error": "Insufficient data"})
                continue
            latest, prev = rows[0], rows[1]
            change_pct = round((float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100, 2)

            overview = {}
            if self.dsm:
                ov_result = await self.dsm.fetch_company_overview(sym)
                if ov_result.success:
                    overview = ov_result.data or {}

            comparisons.append(_clean({
                "symbol": sym,
                "name": overview.get("Name", sym),
                "close": latest["close"],
                "daily_change_pct": change_pct,
                "rsi": latest["rsi"],
                "macd": latest["macd"],
                "sma20": latest["sma20"],
                "sma60": latest["sma60"],
                "pe_ratio": overview.get("PERatio"),
                "market_cap": overview.get("MarketCapitalization"),
                "sector": overview.get("Sector"),
                "eps": overview.get("EPS"),
                "dividend_yield": overview.get("DividendYield"),
            }))
        return {"comparisons": comparisons}
