"""
Natural-language stock screener.
Translates a plain-English query into a SQL filter on interval_1d_technical,
executes it, enriches with company overview data, and returns ranked results
with an AI explanation.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)

SCREENER_SYSTEM_PROMPT = """You are a SQL filter generator for a stock screener.

The database table is `interval_1d_technical` in PostgreSQL with these columns for the LATEST row per symbol:
- symbol (text) — stock ticker
- close (numeric) — latest closing price
- open, high, low (numeric) — daily OHLC
- volume (bigint) — daily trading volume
- rsi (numeric) — Relative Strength Index (0-100). Below 30 = oversold, above 70 = overbought
- macd (numeric) — MACD line value
- macd_signal (numeric) — MACD signal line
- macd_hist (numeric) — MACD histogram (macd - signal). Positive = bullish, negative = bearish
- bbands_upper, bbands_middle, bbands_lower (numeric) — Bollinger Bands
- sma5, sma10, sma20, sma30, sma60, sma120, sma250 (numeric) — Simple Moving Averages
- ema5, ema10, ema20, ema30, ema60, ema120, ema250 (numeric) — Exponential Moving Averages

You also have access to a derived column:
- daily_change_pct: calculated as ((close - prev_close) / prev_close * 100)

IMPORTANT RULES:
1. Output ONLY a valid JSON object — no markdown, no explanation, no code fences.
2. The JSON must have these fields:
   - "where_clause": A SQL WHERE clause (without the WHERE keyword). Use parameterized placeholders $1, $2, etc. ONLY for literal values. Column names and operators must NOT be parameterized.
   - "params": An array of parameter values matching the $N placeholders, in order.
   - "order_by": SQL ORDER BY clause (without ORDER BY keyword). e.g. "rsi ASC" or "volume DESC"
   - "description": One sentence describing what the filter does.
3. Always filter for the latest data point per symbol (the query already does this via a subquery).
4. For "momentum" stocks: RSI > 50, MACD histogram > 0, price > SMA20.
5. For "oversold" stocks: RSI < 30.
6. For "overbought" stocks: RSI > 70.
7. For "breakout" stocks: close > bbands_upper.
8. For "trending up": close > sma50 AND close > sma200 (use sma60 and sma250 as proxies).
9. For "high volume": volume > 2x average. Since we only have the latest row, use volume > 50000000 as a proxy for high volume.
10. For price ranges, use the close column.
11. Keep filters reasonable — avoid overly restrictive combinations that return 0 results.

Example input: "Find oversold tech stocks"
Example output:
{"where_clause": "rsi < $1", "params": [30], "order_by": "rsi ASC", "description": "Stocks with RSI below 30 (oversold condition)"}

Example input: "Stocks with strong upward momentum above $100"
Example output:
{"where_clause": "rsi > $1 AND macd_hist > $2 AND close > sma20 AND close > $3", "params": [50, 0, 100], "order_by": "rsi DESC", "description": "Stocks above $100 with bullish RSI and positive MACD histogram, trading above their 20-day SMA"}
"""

RANK_SYSTEM_PROMPT = """You are a stock analyst. Given screening results, provide a brief analysis.

Guidelines:
- Start with a one-line summary of what was screened and how many results were found.
- Highlight the top 3-5 most interesting picks and why.
- Mention any notable patterns across the results.
- Keep it concise — 3-4 short paragraphs max.
- Use bold for stock symbols.
- End with a disclaimer that this is not financial advice.
"""


def _clean(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(i) for i in obj]
    return obj


class NLScreener:
    def __init__(self, ai_client, pg_repo, data_source_manager=None):
        self.ai_client = ai_client
        self.pg_repo = pg_repo
        self.dsm = data_source_manager

    async def screen(self, query: str, limit: int = 20) -> Dict[str, Any]:
        filter_result = await self._parse_query(query)
        if "error" in filter_result:
            return filter_result

        results = await self._execute_filter(
            filter_result["where_clause"],
            filter_result["params"],
            filter_result.get("order_by", "close DESC"),
            limit,
        )

        explanation = await self._explain_results(query, filter_result, results)

        return {
            "query": query,
            "filter_description": filter_result.get("description", ""),
            "total_results": len(results),
            "results": results,
            "explanation": explanation,
        }

    async def _parse_query(self, query: str) -> Dict[str, Any]:
        messages = [
            {"role": "system", "content": SCREENER_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]
        try:
            response = await self.ai_client.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=512,
            )
            content = response["choices"][0]["message"]["content"].strip()
            content = content.strip("`").removeprefix("json").strip()
            parsed = json.loads(content)

            required = ["where_clause", "params"]
            for key in required:
                if key not in parsed:
                    return {"error": f"LLM response missing '{key}' field"}

            if not isinstance(parsed["params"], list):
                parsed["params"] = []

            return parsed
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM filter response: %s", e)
            return {"error": f"Could not parse the screening criteria. Please try rephrasing your query."}
        except Exception as e:
            logger.error("Screener parse error: %s", e)
            return {"error": str(e)}

    async def _execute_filter(
        self, where_clause: str, params: list, order_by: str, limit: int
    ) -> List[Dict]:
        query = f"""
            WITH latest AS (
                SELECT DISTINCT ON (symbol)
                    symbol, datetime_index, open, high, low, close, volume,
                    rsi, macd, macd_signal, macd_hist,
                    bbands_upper, bbands_middle, bbands_lower,
                    sma5, sma10, sma20, sma30, sma60, sma120, sma250,
                    ema5, ema10, ema20, ema30, ema60, ema120, ema250
                FROM interval_1d_technical
                WHERE close IS NOT NULL
                ORDER BY symbol, datetime_index DESC
            )
            SELECT * FROM latest
            WHERE {where_clause}
            ORDER BY {order_by}
            LIMIT {int(limit)}
        """

        try:
            async with self.pg_repo.db.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)
        except Exception as e:
            logger.error("Screener SQL error: %s | query: %s | params: %s", e, where_clause, params)
            return []

        results = []
        for r in rows:
            results.append(_clean({
                "symbol": r["symbol"],
                "close": r["close"],
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "volume": r["volume"],
                "rsi": r["rsi"],
                "macd": r["macd"],
                "macd_signal": r["macd_signal"],
                "macd_hist": r["macd_hist"],
                "sma20": r["sma20"],
                "sma60": r["sma60"],
                "sma250": r["sma250"],
                "bbands_upper": r["bbands_upper"],
                "bbands_lower": r["bbands_lower"],
                "date": r["datetime_index"].strftime("%Y-%m-%d"),
            }))
        return results

    async def _explain_results(
        self, query: str, filter_result: Dict, results: List[Dict]
    ) -> str:
        if not results:
            return f"No stocks matched your criteria: \"{query}\". Try broadening your filters."

        summary_data = []
        for r in results[:15]:
            summary_data.append({
                "symbol": r["symbol"],
                "close": r["close"],
                "rsi": r["rsi"],
                "macd_hist": r["macd_hist"],
                "volume": r["volume"],
            })

        messages = [
            {"role": "system", "content": RANK_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"User query: \"{query}\"\n"
                f"Filter applied: {filter_result.get('description', '')}\n"
                f"Total matches: {len(results)}\n"
                f"Top results:\n{json.dumps(summary_data, indent=2)}"
            )},
        ]

        try:
            response = await self.ai_client.chat_completion(
                messages=messages, temperature=0.5, max_tokens=1024,
            )
            return response["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("Screener explain error: %s", e)
            return f"Found {len(results)} stocks matching your criteria."
