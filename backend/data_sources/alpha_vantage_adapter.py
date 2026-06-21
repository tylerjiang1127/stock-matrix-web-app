import asyncio
import threading
import time
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from data_sources.base_adapter import DataSourceAdapter, FetchResult


class AlphaVantageAdapter(DataSourceAdapter):

    source_name = "alpha_vantage"
    supported_intervals = ['1m', '5m', '15m', '30m', '60m', '1d', '1wk', '1mo']

    AV_INTERVAL_MAP = {
        '1m': '1min', '5m': '5min', '15m': '15min',
        '30m': '30min', '60m': '60min',
        '1d': 'daily', '1wk': 'weekly', '1mo': 'monthly',
    }

    def __init__(self, api_key: str, calls_per_minute: int = 75):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self._rate_lock = threading.Lock()
        self._min_interval = 60.0 / calls_per_minute
        self._last_call_time = 0.0

    # ── helpers ──────────────────────────────────────────────

    def _rate_limit_wait(self):
        """Proactive rate limiter — spaces requests to stay under calls/min ceiling."""
        with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_call_time
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_call_time = time.monotonic()

    @staticmethod
    def _safe_float(value):
        try:
            if value in ('None', '', None, '-'):
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value):
        try:
            if value in ('None', '', None, '-'):
                return None
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _av_request(self, params: dict, timeout: int = 30) -> dict:
        params['apikey'] = self.api_key
        max_retries = 3
        for attempt in range(max_retries):
            self._rate_limit_wait()
            response = requests.get(self.base_url, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()

            if 'Error Message' in data:
                raise Exception(data['Error Message'])

            if 'Note' in data or 'Information' in data:
                msg = data.get('Note') or data.get('Information')
                msg_str = str(msg).lower()
                if 'call frequency' in msg_str or 'daily' in msg_str or 'burst' in msg_str:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    raise Exception(f"Rate limit: {msg}")
                raise Exception(f"API info: {msg}")

            return data
        raise Exception("Max retries exceeded")

    # ── OHLCV ────────────────────────────────────────────────

    def _build_ohlcv_params(self, symbol: str, interval: str, start_date=None) -> dict:
        # compact = last 100 data points; full = 20+ years. Use compact for recent fetches.
        use_compact = False
        if start_date is not None:
            days_back = (datetime.now() - datetime.strptime(str(start_date)[:10], '%Y-%m-%d')).days
            use_compact = days_back <= 100

        output_size = 'compact' if use_compact else 'full'

        if interval in ('1m', '5m', '15m', '30m', '60m'):
            return {
                'function': 'TIME_SERIES_INTRADAY',
                'symbol': symbol,
                'interval': self.AV_INTERVAL_MAP[interval],
                'outputsize': output_size,
            }
        elif interval == '1d':
            return {'function': 'TIME_SERIES_DAILY_ADJUSTED', 'symbol': symbol, 'outputsize': output_size}
        elif interval == '1wk':
            return {'function': 'TIME_SERIES_WEEKLY', 'symbol': symbol}
        elif interval == '1mo':
            return {'function': 'TIME_SERIES_MONTHLY', 'symbol': symbol}
        raise ValueError(f"Unsupported interval: {interval}")

    def _parse_ohlcv(self, data: dict, interval: str) -> pd.DataFrame:
        possible_keys = [
            'Time Series (Daily)', 'Time Series (1min)', 'Time Series (5min)',
            'Time Series (15min)', 'Time Series (30min)', 'Time Series (60min)',
            'Weekly Time Series', 'Monthly Time Series', 'Time Series (Daily) Adjusted',
        ]
        ts_key = next((k for k in possible_keys if k in data), None)
        if not ts_key:
            return pd.DataFrame()

        rows = []
        for timestamp, values in data[ts_key].items():
            try:
                if '5. adjusted close' in values:
                    orig_close = float(values['4. close'])
                    adj_close = float(values['5. adjusted close'])
                    factor = adj_close / orig_close if orig_close != 0 else 1.0
                    rows.append({
                        'Datetime': pd.to_datetime(timestamp),
                        'Open': float(values['1. open']) * factor,
                        'High': float(values['2. high']) * factor,
                        'Low': float(values['3. low']) * factor,
                        'Close': adj_close,
                        'Volume': int(values['6. volume']),
                    })
                else:
                    rows.append({
                        'Datetime': pd.to_datetime(timestamp),
                        'Open': float(values['1. open']),
                        'High': float(values['2. high']),
                        'Low': float(values['3. low']),
                        'Close': float(values['4. close']),
                        'Volume': int(values['5. volume']),
                    })
            except (KeyError, ValueError):
                continue

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows).set_index('Datetime').sort_index()

        if interval in ('1m', '5m', '15m', '30m', '60m'):
            df = self._filter_intraday(df, interval)
        return df

    @staticmethod
    def _filter_intraday(df: pd.DataFrame, interval: str) -> pd.DataFrame:
        if df.empty:
            return df
        now = datetime.now()
        cutoffs = {'1m': 1, '5m': 5, '15m': 5, '30m': 30, '60m': 30}
        days = cutoffs.get(interval, 30)
        return df[df.index >= now - timedelta(days=days)]

    def _fetch_ohlcv_sync(self, symbol: str, interval: str, start_date=None) -> FetchResult:
        start = time.time()
        try:
            params = self._build_ohlcv_params(symbol, interval, start_date=start_date)
            data = self._av_request(params)
            df = self._parse_ohlcv(data, interval)
            if df.empty:
                return self._timed_result(start, success=False, error=f"No data for {symbol} {interval}")
            if start_date is not None:
                df = df[df.index >= pd.Timestamp(start_date)]
                if df.empty:
                    return self._timed_result(start, success=False, error=f"No new data for {symbol} {interval}")
            return self._timed_result(start, success=True, data=df)
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_ohlcv(self, symbol: str, interval: str, start_date=None) -> FetchResult:
        return await asyncio.to_thread(self._fetch_ohlcv_sync, symbol, interval, start_date)

    async def fetch_bulk_daily_ohlcv(self, symbols: List[str], start_date=None) -> Dict[str, FetchResult]:
        return {s: FetchResult(success=False, source_name=self.source_name,
                               error="Bulk download not supported") for s in symbols}

    # ── Company overview ─────────────────────────────────────

    def _fetch_overview_sync(self, symbol: str) -> FetchResult:
        start = time.time()
        try:
            data = self._av_request({'function': 'OVERVIEW', 'symbol': symbol}, timeout=15)
            if 'Symbol' not in data:
                return self._timed_result(start, success=True, data={'symbol': symbol})

            info = {
                'symbol': data.get('Symbol', symbol),
                'longName': data.get('Name', 'N/A'),
                'exchange': data.get('Exchange', 'N/A'),
                'sector': data.get('Sector', 'N/A'),
                'industry': data.get('Industry', 'N/A'),
                'country': data.get('Country', 'N/A'),
                'fiscalYearEnd': data.get('FiscalYearEnd', 'N/A'),
                'currency': data.get('Currency', 'USD'),
                'longBusinessSummary': data.get('Description', 'No description available.'),
                'marketCap': self._safe_int(data.get('MarketCapitalization', 0)),
                'ebitda': self._safe_int(data.get('EBITDA', 0)),
                'peRatio': self._safe_float(data.get('PERatio', 0)),
                'forwardPE': self._safe_float(data.get('ForwardPE', 0)),
                'pegRatio': self._safe_float(data.get('PEGRatio', 0)),
                'bookValue': self._safe_float(data.get('BookValue', 0)),
                'dividendPerShare': self._safe_float(data.get('DividendPerShare', 0)),
                'dividendYield': self._safe_float(data.get('DividendYield', 0)),
                'eps': self._safe_float(data.get('EPS', 0)),
                'revenueTTM': self._safe_int(data.get('RevenueTTM', 0)),
                'grossProfitTTM': self._safe_int(data.get('GrossProfitTTM', 0)),
                'dilutedEPSTTM': self._safe_float(data.get('DilutedEPSTTM', 0)),
                'profitMargin': self._safe_float(data.get('ProfitMargin', 0)),
                'operatingMarginTTM': self._safe_float(data.get('OperatingMarginTTM', 0)),
                'returnOnAssetsTTM': self._safe_float(data.get('ReturnOnAssetsTTM', 0)),
                'returnOnEquityTTM': self._safe_float(data.get('ReturnOnEquityTTM', 0)),
                'beta': self._safe_float(data.get('Beta', 0)),
                '52WeekHigh': self._safe_float(data.get('52WeekHigh', 0)),
                '52WeekLow': self._safe_float(data.get('52WeekLow', 0)),
                '50DayMovingAverage': self._safe_float(data.get('50DayMovingAverage', 0)),
                '200DayMovingAverage': self._safe_float(data.get('200DayMovingAverage', 0)),
                'analystTargetPrice': self._safe_float(data.get('AnalystTargetPrice', 0)),
                'priceToSalesRatioTTM': self._safe_float(data.get('PriceToSalesRatioTTM', 0)),
                'priceToBookRatio': self._safe_float(data.get('PriceToBookRatio', 0)),
                'evToRevenue': self._safe_float(data.get('EVToRevenue', 0)),
                'evToEBITDA': self._safe_float(data.get('EVToEBITDA', 0)),
            }
            return self._timed_result(start, success=True, data=info)
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_company_overview(self, symbol: str) -> FetchResult:
        return await asyncio.to_thread(self._fetch_overview_sync, symbol)

    # ── Fundamentals ─────────────────────────────────────────

    def _fetch_financial_statement(self, symbol: str, function: str, report_key_a: str, report_key_q: str):
        try:
            data = self._av_request({'function': function, 'symbol': symbol})
            annual = pd.DataFrame(data.get(report_key_a, []))
            quarterly = pd.DataFrame(data.get(report_key_q, []))
            for df in (annual, quarterly):
                if 'fiscalDateEnding' in df.columns:
                    df['fiscalDateEnding'] = pd.to_datetime(df['fiscalDateEnding'])
                    df.sort_values('fiscalDateEnding', ascending=False, inplace=True)
            return annual.head(8), quarterly.head(8)
        except Exception:
            return pd.DataFrame(), pd.DataFrame()

    def _process_income_statement(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        mapping = {
            'totalRevenue': 'Total Revenue', 'costOfRevenue': 'Cost Of Revenue',
            'grossProfit': 'Gross Profit', 'operatingIncome': 'Operating Income',
            'netIncome': 'Net Income',
        }
        cols = ['fiscalDateEnding'] + [c for c in mapping if c in df.columns]
        out = df[cols].copy().rename(columns=mapping)
        if 'fiscalDateEnding' in out.columns:
            out['fiscalDateEnding'] = out['fiscalDateEnding'].dt.strftime('%Y-%m-%d')
        for c in mapping.values():
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors='coerce').fillna(0)
        if 'Total Revenue' in out.columns and out['Total Revenue'].sum() != 0:
            out['Gross Margin'] = out['Gross Profit'] / out['Total Revenue']
            out['Operating Margin'] = out['Operating Income'] / out['Total Revenue']
            out['Net Profit Margin'] = out['Net Income'] / out['Total Revenue']
        return out

    def _process_balance_sheet(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        col_map = {
            'totalAssets': 'Total Assets', 'totalLiabilities': 'Total Liab',
            'totalShareholderEquity': 'Total Stockholder Equity',
            'cashAndCashEquivalentsAtCarryingValue': 'Cash',
            'currentAssets': 'Total Current Assets', 'totalCurrentAssets': 'Total Current Assets',
            'currentLiabilities': 'Total Current Liabilities', 'totalCurrentLiabilities': 'Total Current Liabilities',
        }
        out = pd.DataFrame()
        if 'fiscalDateEnding' in df.columns:
            out['fiscalDateEnding'] = pd.to_datetime(df['fiscalDateEnding']).dt.strftime('%Y-%m-%d')
        for orig, new in col_map.items():
            if orig in df.columns:
                out[new] = pd.to_numeric(df[orig], errors='coerce').fillna(0)
        if 'Total Current Liabilities' in out.columns:
            denom = out['Total Current Liabilities'].replace(0, np.nan)
            if 'Cash' in out.columns:
                out['Cash Ratio'] = out['Cash'] / denom
            if 'Total Current Assets' in out.columns:
                out['Current Ratio'] = out['Total Current Assets'] / denom
        return out

    def _process_cash_flow(self, df: pd.DataFrame, income: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        col_map = {
            'operatingCashflow': 'Total Cash From Operating Activities',
            'cashflowFromInvestment': 'Total Cashflows From Investing Activities',
            'cashflowFromFinancing': 'Total Cash From Financing Activities',
            'capitalExpenditures': 'Capital Expenditures',
        }
        out = pd.DataFrame()
        if 'fiscalDateEnding' in df.columns:
            out['fiscalDateEnding'] = pd.to_datetime(df['fiscalDateEnding']).dt.strftime('%Y-%m-%d')
        for orig, new in col_map.items():
            if orig in df.columns:
                out[new] = pd.to_numeric(df[orig], errors='coerce').fillna(0)
        op_col = 'Total Cash From Operating Activities'
        cap_col = 'Capital Expenditures'
        if op_col in out.columns and cap_col in out.columns:
            out['Free Cash Flow'] = out[op_col] + out[cap_col]
        if op_col in out.columns and not income.empty and 'Total Revenue' in income.columns:
            n = min(len(out), len(income))
            rev = income['Total Revenue'].iloc[:n].values
            ocf = out[op_col].iloc[:n].values
            ratio = np.where(rev != 0, ocf / rev, 0)
            if len(out) > n:
                ratio = np.append(ratio, np.zeros(len(out) - n))
            out['OperatingCashflow/SalesRatio'] = ratio
        return out

    def _fetch_fundamentals_sync(self, symbol: str) -> FetchResult:
        start = time.time()
        try:
            inc_a, inc_q = self._fetch_financial_statement(
                symbol, 'INCOME_STATEMENT', 'annualReports', 'quarterlyReports')
            time.sleep(0.1)
            bs_a, bs_q = self._fetch_financial_statement(
                symbol, 'BALANCE_SHEET', 'annualReports', 'quarterlyReports')
            time.sleep(0.1)
            cf_a, cf_q = self._fetch_financial_statement(
                symbol, 'CASH_FLOW', 'annualReports', 'quarterlyReports')

            p_inc_a = self._process_income_statement(inc_a)
            p_inc_q = self._process_income_statement(inc_q)
            p_bs_a = self._process_balance_sheet(bs_a)
            p_bs_q = self._process_balance_sheet(bs_q)
            p_cf_a = self._process_cash_flow(cf_a, p_inc_a)
            p_cf_q = self._process_cash_flow(cf_q, p_inc_q)

            result = {
                'annual': {
                    'income_statement': p_inc_a,
                    'balance_sheet': p_bs_a,
                    'cash_flow': p_cf_a,
                },
                'quarterly': {
                    'income_statement': p_inc_q,
                    'balance_sheet': p_bs_q,
                    'cash_flow': p_cf_q,
                },
            }
            return self._timed_result(start, success=True, data=result)
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_fundamentals(self, symbol: str) -> FetchResult:
        return await asyncio.to_thread(self._fetch_fundamentals_sync, symbol)

    # ── News sentiment ───────────────────────────────────────

    def _fetch_news_sync(self, symbol: str, limit: int) -> FetchResult:
        start = time.time()
        empty = {'average_sentiment_score': 0, 'average_sentiment_label': 'Neutral',
                 'total_articles': 0, 'articles': []}
        try:
            now = datetime.now()
            time_from = now - timedelta(hours=24)
            params = {
                'function': 'NEWS_SENTIMENT', 'tickers': symbol,
                'limit': limit, 'sort': 'LATEST',
                'time_from': time_from.strftime('%Y%m%dT%H%M'),
                'time_to': now.strftime('%Y%m%dT%H%M'),
            }
            data = self._av_request(params)
            articles = data.get('feed', [])

            weighted_sum = 0.0
            total_weight = 0.0
            processed = []

            for article in articles:
                time_pub = article.get('time_published', '')
                if time_pub:
                    try:
                        if datetime.strptime(time_pub, '%Y%m%dT%H%M%S') < time_from:
                            continue
                    except ValueError:
                        pass

                ticker_sentiments = article.get('ticker_sentiment', [])
                matched = False
                for ts in ticker_sentiments:
                    if ts.get('ticker') == symbol:
                        matched = True
                        score = float(ts.get('ticker_sentiment_score', 0) or 0)
                        relevance = float(ts.get('relevance_score', 0) or 0)
                        weight = relevance if relevance > 0 else 0.1
                        weighted_sum += score * weight
                        total_weight += weight
                        processed.append({
                            'title': article.get('title', 'No title'),
                            'url': article.get('url', ''),
                            'source': article.get('source', 'Unknown'),
                            'time_published': time_pub,
                            'summary': article.get('summary', ''),
                            'banner_image': article.get('banner_image', ''),
                            'sentiment_score': score,
                            'sentiment_label': ts.get('ticker_sentiment_label', 'Neutral'),
                            'relevance_score': relevance,
                        })
                        break

                if not matched and len(processed) < limit:
                    overall = float(article.get('overall_sentiment_score', 0) or 0)
                    weighted_sum += overall * 0.3
                    total_weight += 0.3
                    processed.append({
                        'title': article.get('title', 'No title'),
                        'url': article.get('url', ''),
                        'source': article.get('source', 'Unknown'),
                        'time_published': time_pub,
                        'summary': article.get('summary', ''),
                        'banner_image': article.get('banner_image', ''),
                        'sentiment_score': overall,
                        'sentiment_label': article.get('overall_sentiment_label', 'Neutral'),
                        'relevance_score': 0,
                    })

            avg = weighted_sum / total_weight if total_weight > 0 else 0
            if avg >= 0.35:
                label = 'Bullish'
            elif avg >= 0.15:
                label = 'Somewhat-Bullish'
            elif avg >= -0.15:
                label = 'Neutral'
            elif avg >= -0.35:
                label = 'Somewhat-Bearish'
            else:
                label = 'Bearish'

            return self._timed_result(start, success=True, data={
                'average_sentiment_score': round(avg, 4),
                'average_sentiment_label': label,
                'total_articles': len(processed),
                'articles': processed,
            })
        except Exception as e:
            return self._timed_result(start, success=False, data=empty, error=str(e))

    async def fetch_news_sentiment(self, symbol: str, limit: int = 50) -> FetchResult:
        return await asyncio.to_thread(self._fetch_news_sync, symbol, limit)
