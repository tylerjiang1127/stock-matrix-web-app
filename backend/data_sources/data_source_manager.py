from typing import List, Dict, Any

from data_sources.base_adapter import DataSourceAdapter, FetchResult
from data_sources.data_validator import DataValidator
from data_sources.health_monitor import HealthMonitor


class DataSourceManager:

    def __init__(
        self,
        adapters: List[DataSourceAdapter],
        validator: DataValidator,
        health_monitor: HealthMonitor,
        ohlcv_chain: List[str] = None,
        overview_chain: List[str] = None,
        fundamentals_chain: List[str] = None,
        news_chain: List[str] = None,
    ):
        self.adapters = {a.source_name: a for a in adapters}
        self.validator = validator
        self.health = health_monitor

        self.ohlcv_chain = ohlcv_chain or ['yfinance', 'alpha_vantage', 'finnhub']
        self.overview_chain = overview_chain or ['alpha_vantage', 'yfinance', 'finnhub']
        self.fundamentals_chain = fundamentals_chain or ['alpha_vantage', 'yfinance']
        self.news_chain = news_chain or ['alpha_vantage', 'finnhub']

    def _chain(self, chain_names: List[str]) -> List[DataSourceAdapter]:
        return [self.adapters[n] for n in chain_names if n in self.adapters]

    # ── OHLCV ────────────────────────────────────────────────

    async def fetch_ohlcv(self, symbol: str, interval: str, start_date=None) -> FetchResult:
        for adapter in self._chain(self.ohlcv_chain):
            if interval not in adapter.supported_intervals:
                continue
            if not await self.health.is_source_healthy(adapter.source_name):
                continue

            result = await adapter.fetch_ohlcv(symbol, interval, start_date=start_date)
            await self.health.record_attempt(adapter.source_name, result.success, result.latency_ms)

            if result.success:
                vr = self.validator.validate_ohlcv(result.data, symbol, interval)
                if vr.is_valid:
                    return result
                await self.health.record_validation_failure(adapter.source_name, vr.errors)

        return FetchResult(success=False, source_name="all",
                           error=f"All sources failed for {symbol} {interval}")

    async def fetch_bulk_daily_ohlcv(self, symbols: List[str], start_date=None) -> Dict[str, FetchResult]:
        return await self.fetch_bulk_ohlcv(symbols, '1d', start_date=start_date)

    async def fetch_bulk_ohlcv(self, symbols: List[str], interval: str, start_date=None) -> Dict[str, FetchResult]:
        for adapter in self._chain(self.ohlcv_chain):
            if interval not in adapter.supported_intervals:
                continue
            if not await self.health.is_source_healthy(adapter.source_name):
                continue
            if hasattr(adapter, 'fetch_bulk_ohlcv'):
                results = await adapter.fetch_bulk_ohlcv(symbols, interval, start_date=start_date)
            else:
                results = await adapter.fetch_bulk_daily_ohlcv(symbols, start_date=start_date)
            any_success = any(r.success for r in results.values())
            await self.health.record_attempt(adapter.source_name, any_success)
            if any_success:
                return results
        return {s: FetchResult(success=False, source_name="all",
                               error="All sources failed") for s in symbols}

    # ── Company overview ─────────────────────────────────────

    async def fetch_company_overview(self, symbol: str) -> FetchResult:
        for adapter in self._chain(self.overview_chain):
            if not await self.health.is_source_healthy(adapter.source_name):
                continue

            result = await adapter.fetch_company_overview(symbol)
            await self.health.record_attempt(adapter.source_name, result.success, result.latency_ms)

            if result.success:
                vr = self.validator.validate_company_overview(result.data, symbol)
                if vr.is_valid:
                    return result

        return FetchResult(success=False, source_name="all",
                           error=f"All sources failed for {symbol} overview")

    # ── Fundamentals ─────────────────────────────────────────

    async def fetch_fundamentals(self, symbol: str) -> FetchResult:
        for adapter in self._chain(self.fundamentals_chain):
            if not await self.health.is_source_healthy(adapter.source_name):
                continue

            result = await adapter.fetch_fundamentals(symbol)
            await self.health.record_attempt(adapter.source_name, result.success, result.latency_ms)

            if result.success:
                vr = self.validator.validate_fundamentals(result.data, symbol)
                if vr.is_valid:
                    return result

        return FetchResult(success=False, source_name="all",
                           error=f"All sources failed for {symbol} fundamentals")

    # ── News sentiment ───────────────────────────────────────

    async def fetch_news_sentiment(self, symbol: str, limit: int = 50) -> FetchResult:
        for adapter in self._chain(self.news_chain):
            if not await self.health.is_source_healthy(adapter.source_name):
                continue

            result = await adapter.fetch_news_sentiment(symbol, limit)
            await self.health.record_attempt(adapter.source_name, result.success, result.latency_ms)

            if result.success:
                return result

        return FetchResult(success=False, source_name="all",
                           error=f"All sources failed for {symbol} news",
                           data={'average_sentiment_score': 0,
                                 'average_sentiment_label': 'Neutral',
                                 'total_articles': 0, 'articles': []})

    # ── Health ───────────────────────────────────────────────

    async def get_all_health(self) -> Dict[str, Any]:
        stats = {}
        for name in self.adapters:
            stats[name] = await self.health.get_source_stats(name)
        return stats
