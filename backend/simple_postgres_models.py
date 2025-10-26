"""
Enhanced PostgreSQL models for OHLCV data and technical indicators
"""

import pandas as pd
import json
import numpy as np
from typing import Dict, Any, List
from postgres_database import postgres_db

class SimpleTechnicalDataRepository:
    def __init__(self, db):
        self.db = db
        self.interval_tables = {
            '1m': 'interval_1m_technical',
            '5m': 'interval_5m_technical',
            '15m': 'interval_15m_technical',
            '30m': 'interval_30m_technical',
            '60m': 'interval_60m_technical',
            '1d': 'interval_1d_technical',
            '1wk': 'interval_1wk_technical',
            '1mo': 'interval_1mo_technical'
        }
    
    def _convert_to_serializable(self, value):
        """Convert NumPy types to Python native types for JSON serialization"""
        if isinstance(value, (np.integer, np.int64, np.int32)):
            return int(value)
        elif isinstance(value, (np.floating, np.float64, np.float32)):
            return float(value) if not pd.isna(value) else None
        elif isinstance(value, np.ndarray):
            return value.tolist()
        elif pd.isna(value):
            return None
        else:
            return value
    
    async def save_technical_data(self, symbol: str, interval: str, technical_data: Dict[str, Any]) -> bool:
        """Save OHLCV data and technical indicators to PostgreSQL"""
        try:
            table_name = self.interval_tables.get(interval)
            if not table_name:
                print(f"❌ Unknown interval: {interval}")
                return False
            
            # Extract stock_price data
            stock_price_data = technical_data.get('stock_price')
            if stock_price_data is None:
                print(f"⚠️ No stock price data for {symbol} {interval}")
                return False
            
            # Check if it's a DataFrame and if it's empty
            if hasattr(stock_price_data, 'empty'):
                if stock_price_data.empty:
                    print(f"⚠️ Empty stock price data for {symbol} {interval}")
                    return False
            
            # Prepare data for insertion - OHLCV + technical indicators
            records = []
            for idx, row in stock_price_data.iterrows():
                # Convert timezone-naive timestamp to UTC
                if hasattr(idx, 'tz_localize'):
                    datetime_index = idx.tz_localize('UTC')
                else:
                    datetime_index = idx
                
                # Start with basic OHLCV data (note: column names are capitalized)
                record = {
                    'symbol': symbol,
                    'datetime_index': datetime_index,
                    'open': self._convert_to_serializable(row.get('Open')),
                    'high': self._convert_to_serializable(row.get('High')),
                    'low': self._convert_to_serializable(row.get('Low')),
                    'close': self._convert_to_serializable(row.get('Close')),
                    'adjusted_close': self._convert_to_serializable(row.get('Adjusted Close')),  # May not exist
                    'volume': self._convert_to_serializable(row.get('Volume'))
                }
                
                # Add moving averages (SMA, EMA, WMA, DEMA, TEMA, KAMA)
                # Use the same periods as defined in StockMetaDataFetcher
                ma_periods_by_interval = {
                    '1m': [5, 10, 20, 30, 60, 120],
                    '5m': [6, 12, 24, 36, 72, 144],
                    '15m': [4, 8, 16, 24, 48, 96],
                    '30m': [3, 6, 12, 18, 36, 72],
                    '60m': [3, 5, 8, 13, 21, 34],
                    '1d': [5, 10, 20, 30, 60, 120, 250],
                    '1wk': [5, 10, 20, 30, 60],
                    '1mo': [3, 5, 10, 12, 24, 36],
                    '3mo': [2, 4, 8, 12, 16]
                }
                
                periods = ma_periods_by_interval.get(interval, [5, 10, 20, 30, 60, 120, 250])  # default to 1d periods
                
                for ma_type in ['sma', 'ema', 'wma', 'dema', 'tema', 'kama']:
                    ma_data = technical_data.get(ma_type)
                    if ma_data is not None and hasattr(ma_data, 'empty'):
                        if not ma_data.empty and idx in ma_data.index:
                            ma_row = ma_data.loc[idx]
                            for period in periods:
                                # Column names are just the period numbers as strings
                                col_name = str(period)
                                if col_name in ma_row:
                                    record[f"{ma_type.lower()}{period}"] = self._convert_to_serializable(ma_row[col_name])
                
                # Add Bollinger Bands
                sma_data = technical_data.get('sma')
                if sma_data is not None and hasattr(sma_data, 'empty'):
                    if not sma_data.empty and idx in sma_data.index:
                        sma_row = sma_data.loc[idx]
                        record['bbands_upper'] = self._convert_to_serializable(sma_row.get('bbands_upper'))
                        record['bbands_lower'] = self._convert_to_serializable(sma_row.get('bbands_lower'))
                
                # Add MACD
                macd_data = technical_data.get('macd')
                if macd_data is not None and isinstance(macd_data, dict):
                    macd_series = macd_data.get('macd')
                    macd_signal_series = macd_data.get('macd_signal_line')
                    macd_hist_series = macd_data.get('macd_hist')
                    
                    if macd_series is not None and idx in macd_series.index:
                        record['macd'] = self._convert_to_serializable(macd_series.loc[idx])
                    if macd_signal_series is not None and idx in macd_signal_series.index:
                        record['macd_signal'] = self._convert_to_serializable(macd_signal_series.loc[idx])
                    if macd_hist_series is not None and idx in macd_hist_series.index:
                        record['macd_hist'] = self._convert_to_serializable(macd_hist_series.loc[idx])
                
                # Add RSI
                rsi_data = technical_data.get('rsi')
                if rsi_data is not None and isinstance(rsi_data, dict):
                    rsi_series = rsi_data.get('rsi')
                    if rsi_series is not None and idx in rsi_series.index:
                        record['rsi'] = self._convert_to_serializable(rsi_series.loc[idx])
                
                # Add KDJ
                kdj_data = technical_data.get('kdj')
                if kdj_data is not None and isinstance(kdj_data, dict):
                    k_series = kdj_data.get('k')
                    d_series = kdj_data.get('d')
                    j_series = kdj_data.get('j')
                    
                    if k_series is not None and idx in k_series.index:
                        record['k'] = self._convert_to_serializable(k_series.loc[idx])
                    if d_series is not None and idx in d_series.index:
                        record['d'] = self._convert_to_serializable(d_series.loc[idx])
                    if j_series is not None and idx in j_series.index:
                        record['j'] = self._convert_to_serializable(j_series.loc[idx])
                
                # Add candlestick patterns
                candlestick_data = technical_data.get('cdl_pattern')
                if candlestick_data is not None and hasattr(candlestick_data, 'empty'):
                    if not candlestick_data.empty and idx in candlestick_data.index:
                        pattern_row = candlestick_data.loc[idx]
                        # Convert pattern data to JSONB
                        pattern_dict = {}
                        for col in candlestick_data.columns:
                            if col not in ['bullish_signal', 'bearish_signal', 'pattern_signal']:
                                pattern_dict[col] = self._convert_to_serializable(pattern_row[col])
                        record['candlestick_patterns'] = json.dumps(pattern_dict)
                        record['bullish_signal'] = self._convert_to_serializable(pattern_row.get('bullish_signal'))
                        record['bearish_signal'] = self._convert_to_serializable(pattern_row.get('bearish_signal'))
                        record['pattern_signal'] = self._convert_to_serializable(pattern_row.get('pattern_signal'))
                
                records.append(record)
            
            if not records:
                print(f"⚠️ No records to save for {symbol} {interval}")
                return False
            
            # Enhanced batch insert with all technical indicators
            await self._enhanced_batch_insert(table_name, records)
            print(f"✅ Saved {len(records)} records with technical indicators for {symbol} {interval}")
            return True
                
        except Exception as e:
            print(f"❌ Error saving technical data for {symbol} {interval}: {e}")
            return False
    
    async def _simple_batch_insert(self, table_name: str, records: List[Dict[str, Any]]):
        """Simple batch insert for OHLCV data only"""
        if not records:
            return
        
        # Get column names from first record
        columns = list(records[0].keys())
        placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
        column_names = ', '.join(f'"{col}"' for col in columns)
        
        query = f"""
        INSERT INTO {table_name} ({column_names})
        VALUES ({placeholders})
        ON CONFLICT (symbol, datetime_index) 
        DO UPDATE SET
            "open" = EXCLUDED."open",
            "high" = EXCLUDED."high",
            "low" = EXCLUDED."low",
            "close" = EXCLUDED."close",
            "adjusted_close" = EXCLUDED."adjusted_close",
            "volume" = EXCLUDED."volume"
        """
        
        # Prepare data for batch insert
        batch_data = []
        for record in records:
            row_data = [record.get(col) for col in columns]
            batch_data.append(row_data)
        
        # Execute batch insert
        async with self.db.pool.acquire() as connection:
            await connection.executemany(query, batch_data)
    
    async def _enhanced_batch_insert(self, table_name: str, records: List[Dict[str, Any]]):
        """Enhanced batch insert for OHLCV + technical indicators"""
        if not records:
            return
        
        # Get column names from first record
        columns = list(records[0].keys())
        placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
        column_names = ', '.join(f'"{col}"' for col in columns)
        
        # Create comprehensive UPDATE clause for all possible columns
        update_clauses = []
        for col in columns:
            if col not in ['symbol', 'datetime_index']:
                update_clauses.append(f'"{col}" = EXCLUDED."{col}"')
        
        query = f"""
        INSERT INTO {table_name} ({column_names})
        VALUES ({placeholders})
        ON CONFLICT (symbol, datetime_index) 
        DO UPDATE SET
            {', '.join(update_clauses)}
        """
        
        # Prepare data for batch insert
        batch_data = []
        for record in records:
            row_data = [record.get(col) for col in columns]
            batch_data.append(row_data)
        
        # Execute batch insert
        async with self.db.pool.acquire() as connection:
            await connection.executemany(query, batch_data)
