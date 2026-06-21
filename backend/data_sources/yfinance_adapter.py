import asyncio
import time
import pandas as pd
import yfinance as yf
from typing import Dict, List

from data_sources.base_adapter import DataSourceAdapter, FetchResult


class YFinanceAdapter(DataSourceAdapter):

    source_name = "yfinance"
    supported_intervals = ['1m', '5m', '15m', '30m', '60m', '1d', '1wk', '1mo', '3mo']

    @staticmethod
    def _to_yf_symbol(symbol: str) -> str:
        return symbol.replace('.', '-')

    YF_INTERVAL_MAP = {
        '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
        '60m': '1h', '1d': '1d', '1wk': '1wk', '1mo': '1mo', '3mo': '3mo',
    }

    YF_PERIOD_MAP = {
        '1m': '7d', '5m': '60d', '15m': '60d', '30m': '60d',
        '60m': '730d', '1d': 'max', '1wk': 'max', '1mo': 'max', '3mo': 'max',
    }

    # ── OHLCV ────────────────────────────────────────────────

    def _fetch_ohlcv_sync(self, symbol: str, interval: str, start_date=None) -> FetchResult:
        start = time.time()
        try:
            yf_interval = self.YF_INTERVAL_MAP.get(interval)
            if not yf_interval:
                return self._timed_result(start, success=False,
                                          error=f"Unsupported interval: {interval}")

            ticker = yf.Ticker(self._to_yf_symbol(symbol))
            if start_date is not None:
                df = ticker.history(start=start_date, interval=yf_interval)
            else:
                yf_period = self.YF_PERIOD_MAP.get(interval)
                if not yf_period:
                    return self._timed_result(start, success=False,
                                              error=f"Unsupported interval: {interval}")
                df = ticker.history(period=yf_period, interval=yf_interval)

            if df is None or df.empty:
                return self._timed_result(start, success=False,
                                          error=f"No data for {symbol} {interval}")

            df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            df.index.name = 'Datetime'
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            return self._timed_result(start, success=True, data=df)
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_ohlcv(self, symbol: str, interval: str, start_date=None) -> FetchResult:
        return await asyncio.to_thread(self._fetch_ohlcv_sync, symbol, interval, start_date)

    # ── Bulk daily download ──────────────────────────────────

    def _fetch_bulk_sync(self, symbols: List[str], start_date=None, interval='1d') -> Dict[str, FetchResult]:
        start = time.time()
        results: Dict[str, FetchResult] = {}
        yf_symbols = [self._to_yf_symbol(s) for s in symbols]
        yf_to_canonical = {self._to_yf_symbol(s): s for s in symbols}
        try:
            dl_kwargs = dict(group_by='ticker', threads=True, progress=False, interval=interval)
            if start_date is not None:
                dl_kwargs['start'] = start_date
            else:
                dl_kwargs['period'] = 'max'
            raw = yf.download(yf_symbols, **dl_kwargs)
            if raw is None or raw.empty:
                for s in symbols:
                    results[s] = FetchResult(success=False, source_name=self.source_name,
                                             error="Bulk download returned empty")
                return results

            for yf_sym, symbol in yf_to_canonical.items():
                sym_start = time.time()
                try:
                    if len(symbols) == 1:
                        df = raw[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
                    else:
                        if yf_sym not in raw.columns.get_level_values(0):
                            results[symbol] = FetchResult(
                                success=False, source_name=self.source_name,
                                error=f"{symbol} not in bulk response",
                                latency_ms=(time.time() - sym_start) * 1000)
                            continue
                        df = raw[yf_sym][['Open', 'High', 'Low', 'Close', 'Volume']].copy()

                    df = df.dropna(how='all')
                    if df.empty:
                        results[symbol] = FetchResult(
                            success=False, source_name=self.source_name,
                            error=f"No data for {symbol}",
                            latency_ms=(time.time() - sym_start) * 1000)
                        continue

                    df.index.name = 'Datetime'
                    if df.index.tz is not None:
                        df.index = df.index.tz_localize(None)

                    results[symbol] = FetchResult(
                        success=True, source_name=self.source_name, data=df,
                        latency_ms=(time.time() - sym_start) * 1000)
                except Exception as e:
                    results[symbol] = FetchResult(
                        success=False, source_name=self.source_name, error=str(e),
                        latency_ms=(time.time() - sym_start) * 1000)

        except Exception as e:
            for s in symbols:
                if s not in results:
                    results[s] = FetchResult(success=False, source_name=self.source_name,
                                             error=str(e))
        return results

    async def fetch_bulk_daily_ohlcv(self, symbols: List[str], start_date=None) -> Dict[str, FetchResult]:
        return await asyncio.to_thread(self._fetch_bulk_sync, symbols, start_date)

    async def fetch_bulk_ohlcv(self, symbols: List[str], interval: str, start_date=None) -> Dict[str, FetchResult]:
        return await asyncio.to_thread(self._fetch_bulk_sync, symbols, start_date, interval)

    # ── Company overview ─────────────────────────────────────

    def _fetch_overview_sync(self, symbol: str) -> FetchResult:
        start = time.time()
        try:
            info = yf.Ticker(self._to_yf_symbol(symbol)).info
            if not info or info.get('regularMarketPrice') is None:
                return self._timed_result(start, success=False,
                                          error=f"No info for {symbol}")

            overview = {
                'symbol': info.get('symbol', symbol),
                'longName': info.get('longName') or info.get('shortName', 'N/A'),
                'exchange': info.get('exchange', 'N/A'),
                'sector': info.get('sector', 'N/A'),
                'industry': info.get('industry', 'N/A'),
                'country': info.get('country', 'N/A'),
                'fiscalYearEnd': 'N/A',
                'currency': info.get('currency', 'USD'),
                'longBusinessSummary': info.get('longBusinessSummary', 'No description available.'),
                'marketCap': info.get('marketCap'),
                'ebitda': info.get('ebitda'),
                'peRatio': info.get('trailingPE'),
                'forwardPE': info.get('forwardPE'),
                'pegRatio': info.get('pegRatio'),
                'bookValue': info.get('bookValue'),
                'dividendPerShare': info.get('dividendRate'),
                'dividendYield': info.get('dividendYield'),
                'eps': info.get('trailingEps'),
                'revenueTTM': info.get('totalRevenue'),
                'grossProfitTTM': info.get('grossProfits'),
                'dilutedEPSTTM': info.get('trailingEps'),
                'profitMargin': info.get('profitMargins'),
                'operatingMarginTTM': info.get('operatingMargins'),
                'returnOnAssetsTTM': info.get('returnOnAssets'),
                'returnOnEquityTTM': info.get('returnOnEquity'),
                'beta': info.get('beta'),
                '52WeekHigh': info.get('fiftyTwoWeekHigh'),
                '52WeekLow': info.get('fiftyTwoWeekLow'),
                '50DayMovingAverage': info.get('fiftyDayAverage'),
                '200DayMovingAverage': info.get('twoHundredDayAverage'),
                'analystTargetPrice': info.get('targetMeanPrice'),
                'priceToSalesRatioTTM': info.get('priceToSalesTrailing12Months'),
                'priceToBookRatio': info.get('priceToBook'),
                'evToRevenue': info.get('enterpriseToRevenue'),
                'evToEBITDA': info.get('enterpriseToEbitda'),
            }
            return self._timed_result(start, success=True, data=overview)
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_company_overview(self, symbol: str) -> FetchResult:
        return await asyncio.to_thread(self._fetch_overview_sync, symbol)

    # ── Fundamentals ─────────────────────────────────────────

    def _fetch_fundamentals_sync(self, symbol: str) -> FetchResult:
        start = time.time()
        try:
            t = yf.Ticker(self._to_yf_symbol(symbol))
            inc = t.financials
            bs = t.balance_sheet
            cf = t.cashflow
            inc_q = t.quarterly_financials
            bs_q = t.quarterly_balance_sheet
            cf_q = t.quarterly_cashflow

            def to_dict(df):
                if df is None or df.empty:
                    return pd.DataFrame()
                return df.T.reset_index().rename(columns={'index': 'fiscalDateEnding'})

            result = {
                'annual': {
                    'income_statement': to_dict(inc),
                    'balance_sheet': to_dict(bs),
                    'cash_flow': to_dict(cf),
                },
                'quarterly': {
                    'income_statement': to_dict(inc_q),
                    'balance_sheet': to_dict(bs_q),
                    'cash_flow': to_dict(cf_q),
                },
            }
            return self._timed_result(start, success=True, data=result)
        except Exception as e:
            return self._timed_result(start, success=False, error=str(e))

    async def fetch_fundamentals(self, symbol: str) -> FetchResult:
        return await asyncio.to_thread(self._fetch_fundamentals_sync, symbol)

    # ── News sentiment (not supported by yfinance) ───────────

    async def fetch_news_sentiment(self, symbol: str, limit: int = 50) -> FetchResult:
        return FetchResult(success=False, source_name=self.source_name,
                           error="News sentiment not supported by yfinance")
