import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


MINIMUM_ROWS = {
    '1m': 10, '5m': 10, '15m': 10, '30m': 10, '60m': 10,
    '1d': 50, '1wk': 10, '1mo': 6, '3mo': 4,
}

REQUIRED_OHLCV_COLUMNS = {'Open', 'High', 'Low', 'Close', 'Volume'}


class DataValidator:

    def validate_ohlcv(self, df: Optional[pd.DataFrame], symbol: str, interval: str) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        if df is None:
            return ValidationResult(is_valid=False, errors=[f"{symbol}: DataFrame is None"])
        if not isinstance(df, pd.DataFrame):
            return ValidationResult(is_valid=False, errors=[f"{symbol}: expected DataFrame, got {type(df).__name__}"])
        if df.empty:
            return ValidationResult(is_valid=False, errors=[f"{symbol}: DataFrame is empty"])

        missing = REQUIRED_OHLCV_COLUMNS - set(df.columns)
        if missing:
            return ValidationResult(is_valid=False, errors=[f"{symbol}: missing columns {missing}"])

        if not isinstance(df.index, pd.DatetimeIndex):
            errors.append(f"{symbol}: index is {type(df.index).__name__}, expected DatetimeIndex")

        for col in ['Open', 'High', 'Low', 'Close']:
            if not pd.api.types.is_numeric_dtype(df[col]):
                errors.append(f"{symbol}: column {col} is not numeric")
        if not pd.api.types.is_numeric_dtype(df['Volume']):
            errors.append(f"{symbol}: column Volume is not numeric")

        if errors:
            return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

        bad_hl = (df['High'] < df['Low']).sum()
        if bad_hl > 0:
            errors.append(f"{symbol}: {bad_hl} rows where High < Low")

        neg_price = ((df[['Open', 'High', 'Low', 'Close']] < 0).any(axis=1)).sum()
        if neg_price > 0:
            errors.append(f"{symbol}: {neg_price} rows with negative prices")

        neg_vol = (df['Volume'] < 0).sum()
        if neg_vol > 0:
            errors.append(f"{symbol}: {neg_vol} rows with negative volume")

        zero_close = (df['Close'] == 0).sum()
        if zero_close / len(df) > 0.10:
            errors.append(f"{symbol}: {zero_close}/{len(df)} rows with zero close ({zero_close/len(df):.0%})")

        min_rows = MINIMUM_ROWS.get(interval, 10)
        if len(df) < min_rows:
            errors.append(f"{symbol}: only {len(df)} rows, need at least {min_rows} for interval {interval}")

        dup_count = df.index.duplicated().sum()
        if dup_count > 0:
            errors.append(f"{symbol}: {dup_count} duplicate timestamps")

        if isinstance(df.index, pd.DatetimeIndex) and len(df) > 1:
            if not df.index.is_monotonic_increasing:
                errors.append(f"{symbol}: timestamps are not monotonically increasing")

        if len(df) > 1:
            pct_change = df['Close'].pct_change().abs()
            spikes = pct_change[pct_change > 0.50]
            if len(spikes) > 0:
                spike_dates = [str(d.date()) if hasattr(d, 'date') else str(d) for d in spikes.index[:3]]
                warnings.append(f"{symbol}: {len(spikes)} rows with >50% price change (e.g. {', '.join(spike_dates)})")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_company_overview(self, data: Any, symbol: str) -> ValidationResult:
        if data is None:
            return ValidationResult(is_valid=False, errors=[f"{symbol}: company overview is None"])
        if not isinstance(data, dict):
            return ValidationResult(is_valid=False, errors=[f"{symbol}: expected dict, got {type(data).__name__}"])
        if 'symbol' not in data and 'Symbol' not in data:
            return ValidationResult(is_valid=False, errors=[f"{symbol}: no 'symbol' field in overview"])
        return ValidationResult(is_valid=True)

    def validate_fundamentals(self, data: Any, symbol: str) -> ValidationResult:
        if data is None:
            return ValidationResult(is_valid=False, errors=[f"{symbol}: fundamentals data is None"])
        if not isinstance(data, dict):
            return ValidationResult(is_valid=False, errors=[f"{symbol}: expected dict, got {type(data).__name__}"])
        missing = []
        for key in ('annual', 'quarterly'):
            if key not in data:
                missing.append(key)
        if missing:
            return ValidationResult(is_valid=False, errors=[f"{symbol}: missing keys {missing} in fundamentals"])
        return ValidationResult(is_valid=True)
