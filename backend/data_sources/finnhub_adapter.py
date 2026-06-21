import asyncio
import time
import os
import pandas as pd
import finnhub
from datetime import datetime, timedelta
from typing import List, Dict

from data_sources.base_adapter import DataSourceAdapter, FetchResult


class FinnhubAdapter(DataSourceAdapter):

    source_name = "finnhub"
    supported_intervals = ['1m', '5m', '15m', '30m', '60m', '1d', '1wk', '1mo']

    RESOLUTION_MAP = {
        '1m': '1', '5m': '5', '15m': '15', '30m': '30', '60m': '60',
        '1d': 'D', '1wk': 'W', '1mo': 'M',
    }

    LOOKBACK_DAYS = {
        '1m': 1, '5m': 5, '15m': 10, '30m': 30, '60m': 60,
        '1d': 365 * 5, '1wk': 365 * 10, '1mo': 365 * 20,
    }

    def __init__(self, api_key: str = None):
        key = api_key or os.getenv('FINNHUB_API_KEY', '')
        self.client = finnhub.Client(api_key=key)

    # ── OHLCV ────────────────────────────────────────────────

    def _fetch_ohlcv_sync(self, symbol: str, interval: str, start_date=None) -> FetchResult:
        start = time.time()
        try:
            resolution = self.RESOLUTION_MAP.get(interval)
            if not resolution:
                return self._timed_result(start, success=False,
                                          error=f"Unsupported interval: {interval}")

            now = datetime.now()
            if start_date is not None:
                from_ts = int(pd.Timestamp(start_date).timestamp())
            else:
                lookback = self.LOOKBACK_DAYS.get(interval, 365)
                from_ts = int((now - timedelta(days=lookback)).timestamp())
            to_ts = int(now.timestamp())

            candles = self.client.stock_candles(symbol, resolution, from_ts, to_ts)

            if candles.get('s') != 'ok' or not candles.get('t'):
                return self._timed_result(start, success=False,
                                          error=f"No data for {symbol} {interval}")

            df = pd.DataFrame({
                'Open': candles['o'],
                'High': candles['h'],
                'Low': candles['l'],
                'Close': candles['c'],
                'Volume': candles['v'],
            }, index=pd.to_datetime(candles['t'], unit='s'))
            df.index.name = 'Datetime'
            df.sort_index(inplace=True)

            return self._timed_result(start, success=True, data=df)
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_ohlcv(self, symbol: str, interval: str, start_date=None) -> FetchResult:
        return await asyncio.to_thread(self._fetch_ohlcv_sync, symbol, interval, start_date)

    # ── Company overview ─────────────────────────────────────

    def _fetch_overview_sync(self, symbol: str) -> FetchResult:
        start = time.time()
        try:
            profile = self.client.company_profile2(symbol=symbol)
            if not profile or 'ticker' not in profile:
                return self._timed_result(start, success=False,
                                          error=f"No profile for {symbol}")

            overview = {
                'symbol': profile.get('ticker', symbol),
                'longName': profile.get('name', 'N/A'),
                'exchange': profile.get('exchange', 'N/A'),
                'sector': profile.get('finnhubIndustry', 'N/A'),
                'industry': profile.get('finnhubIndustry', 'N/A'),
                'country': profile.get('country', 'N/A'),
                'currency': profile.get('currency', 'USD'),
                'longBusinessSummary': 'No description available.',
                'marketCap': profile.get('marketCapitalization'),
            }
            return self._timed_result(start, success=True, data=overview)
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_company_overview(self, symbol: str) -> FetchResult:
        return await asyncio.to_thread(self._fetch_overview_sync, symbol)

    # ── News sentiment ───────────────────────────────────────

    def _fetch_news_sync(self, symbol: str, limit: int) -> FetchResult:
        start = time.time()
        try:
            now = datetime.now()
            from_date = (now - timedelta(hours=24)).strftime('%Y-%m-%d')
            to_date = now.strftime('%Y-%m-%d')
            articles = self.client.company_news(symbol, _from=from_date, to=to_date)

            if not articles:
                return self._timed_result(start, success=True, data={
                    'average_sentiment_score': 0, 'average_sentiment_label': 'Neutral',
                    'total_articles': 0, 'articles': [],
                })

            processed = []
            for a in articles[:limit]:
                processed.append({
                    'title': a.get('headline', 'No title'),
                    'url': a.get('url', ''),
                    'source': a.get('source', 'Unknown'),
                    'time_published': datetime.fromtimestamp(a.get('datetime', 0)).strftime('%Y%m%dT%H%M%S'),
                    'summary': a.get('summary', ''),
                    'banner_image': a.get('image', ''),
                    'sentiment_score': 0,
                    'sentiment_label': 'Neutral',
                    'relevance_score': 0,
                })

            return self._timed_result(start, success=True, data={
                'average_sentiment_score': 0,
                'average_sentiment_label': 'Neutral',
                'total_articles': len(processed),
                'articles': processed,
            })
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_news_sentiment(self, symbol: str, limit: int = 50) -> FetchResult:
        return await asyncio.to_thread(self._fetch_news_sync, symbol, limit)

    # ── Fundamentals (not supported on free tier) ────────────

    async def fetch_fundamentals(self, symbol: str) -> FetchResult:
        return FetchResult(success=False, source_name=self.source_name,
                           error="Fundamentals not supported on Finnhub free tier")
