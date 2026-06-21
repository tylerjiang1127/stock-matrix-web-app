import time
import pandas as pd
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class FetchResult:
    success: bool
    data: Optional[Any] = None
    source_name: str = ""
    error: Optional[str] = None
    latency_ms: float = 0.0


class DataSourceAdapter(ABC):
    source_name: str = ""
    supported_intervals: List[str] = field(default_factory=list)

    @abstractmethod
    async def fetch_ohlcv(self, symbol: str, interval: str, start_date=None) -> FetchResult:
        ...

    @abstractmethod
    async def fetch_company_overview(self, symbol: str) -> FetchResult:
        ...

    @abstractmethod
    async def fetch_fundamentals(self, symbol: str) -> FetchResult:
        ...

    @abstractmethod
    async def fetch_news_sentiment(self, symbol: str, limit: int = 50) -> FetchResult:
        ...

    async def fetch_bulk_daily_ohlcv(self, symbols: List[str], start_date=None) -> Dict[str, FetchResult]:
        results = {}
        for symbol in symbols:
            results[symbol] = await self.fetch_ohlcv(symbol, '1d', start_date=start_date)
        return results

    def _timed_result(self, start: float, **kwargs) -> FetchResult:
        kwargs['latency_ms'] = (time.time() - start) * 1000
        kwargs.setdefault('source_name', self.source_name)
        return FetchResult(**kwargs)
