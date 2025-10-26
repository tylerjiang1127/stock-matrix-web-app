"""
PostgreSQL models for technical data storage
"""

from typing import Dict, Any, Optional, List
import pandas as pd
from datetime import datetime
import json

class TechnicalDataRepository:
    def __init__(self, postgres_db):
        self.db = postgres_db
        
        # Map intervals to table names
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
    
    async def save_technical_data(self, symbol: str, interval: str, technical_data: Dict[str, Any]) -> bool:
        """Save technical data for a specific symbol and interval"""
        try:
            table_name = self.interval_tables.get(interval)
            if not table_name:
                print(f"❌ Unknown interval: {interval}")
                return False
            
            # Extract data from technical_data
            stock_price_data = technical_data.get('stock_price')
            if not stock_price_data:
                print(f"⚠️ No stock price data for {symbol} {interval}")
                return False
            
            # Check if it's a DataFrame and if it's empty
            if hasattr(stock_price_data, 'empty'):
                if stock_price_data.empty:
                    print(f"⚠️ Empty stock price data for {symbol} {interval}")
                    return False
            
            # Prepare data for insertion
            records = []
            for idx, row in stock_price_data.iterrows():
                # Convert timezone-naive timestamp to UTC
                if hasattr(idx, 'tz_localize'):
                    datetime_index = idx.tz_localize('UTC')
                else:
                    datetime_index = idx
                
                record = {
                    'symbol': symbol,
                    'datetime_index': datetime_index,
                    'open': row.get('open'),
                    'high': row.get('high'),
                    'low': row.get('low'),
                    'close': row.get('close'),
                    'adjusted_close': row.get('adjusted_close'),
                    'volume': row.get('volume')
                }
                
                # Add moving averages
                for ma_type in ['sma', 'ema', 'wma', 'dema', 'tema', 'kama']:
                    ma_data = technical_data.get(ma_type)
                    if ma_data is not None and hasattr(ma_data, 'empty'):
                        if not ma_data.empty:
                            if idx in ma_data.index:
                                ma_row = ma_data.loc[idx]
                                for period in [5, 10, 20, 50, 100, 200]:
                                    col_name = f"{ma_type.upper()}{period}"
                                    if col_name in ma_row:
                                        record[col_name.lower()] = ma_row[col_name]
                
                # Add Bollinger Bands
                sma_data = technical_data.get('sma')
                if sma_data is not None and hasattr(sma_data, 'empty'):
                    if not sma_data.empty:
                        if idx in sma_data.index:
                            sma_row = technical_data['sma'].loc[idx]
                            record['bbands_upper'] = sma_row.get('BBANDS_UPPER')
                            record['bbands_middle'] = sma_row.get('BBANDS_MIDDLE')
                            record['bbands_lower'] = sma_row.get('BBANDS_LOWER')
                
                # Add MACD
                macd_data = technical_data.get('macd')
                if macd_data is not None and isinstance(macd_data, dict):
                    macd_series = macd_data.get('macd')
                    macd_signal_series = macd_data.get('macd_signal_line')
                    macd_hist_series = macd_data.get('macd_hist')
                    
                    if macd_series is not None and idx in macd_series.index:
                        record['macd'] = macd_series.loc[idx]
                    if macd_signal_series is not None and idx in macd_signal_series.index:
                        record['macd_signal'] = macd_signal_series.loc[idx]
                    if macd_hist_series is not None and idx in macd_hist_series.index:
                        record['macd_hist'] = macd_hist_series.loc[idx]
                
                # Add RSI
                rsi_data = technical_data.get('rsi')
                if rsi_data is not None and isinstance(rsi_data, dict):
                    rsi_series = rsi_data.get('rsi')
                    if rsi_series is not None and idx in rsi_series.index:
                        record['rsi'] = rsi_series.loc[idx]
                
                # Add KDJ
                kdj_data = technical_data.get('kdj')
                if kdj_data is not None and isinstance(kdj_data, dict):
                    k_series = kdj_data.get('k')
                    d_series = kdj_data.get('d')
                    j_series = kdj_data.get('j')
                    
                    if k_series is not None and idx in k_series.index:
                        record['k'] = k_series.loc[idx]
                    if d_series is not None and idx in d_series.index:
                        record['d'] = d_series.loc[idx]
                    if j_series is not None and idx in j_series.index:
                        record['j'] = j_series.loc[idx]
                
                # Add candlestick patterns
                candlestick_data = technical_data.get('cdl_pattern')
                if candlestick_data is not None and hasattr(candlestick_data, 'empty'):
                    if not candlestick_data.empty:
                        if idx in candlestick_data.index:
                            pattern_row = candlestick_data.loc[idx]
                            # Convert pattern data to JSONB
                            pattern_dict = {}
                            for col in candlestick_data.columns:
                                if col not in ['bullish_signal', 'bearish_signal', 'pattern_signal']:
                                    pattern_dict[col] = pattern_row[col]
                            record['candlestick_patterns'] = json.dumps(pattern_dict)
                            record['bullish_signal'] = pattern_row.get('bullish_signal')
                            record['bearish_signal'] = pattern_row.get('bearish_signal')
                            record['pattern_signal'] = pattern_row.get('pattern_signal')
                
                records.append(record)
            
            # Batch insert records
            if records:
                await self._batch_insert(table_name, records)
                print(f"✅ Saved {len(records)} records for {symbol} {interval}")
                return True
            else:
                print(f"⚠️ No records to save for {symbol} {interval}")
                return False
                
        except Exception as e:
            print(f"❌ Error saving technical data for {symbol} {interval}: {e}")
            return False
    
    async def _batch_insert(self, table_name: str, records: List[Dict[str, Any]]):
        """Batch insert records into PostgreSQL"""
        if not records:
            return
        
        # Get column names from first record
        columns = list(records[0].keys())
        placeholders = ', '.join([f'${i+1}' for i in range(len(columns))])
        column_names = ', '.join(columns)
        
        query = f"""
        INSERT INTO {table_name} ({column_names})
        VALUES ({placeholders})
        ON CONFLICT (symbol, datetime_index) 
        DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            adjusted_close = EXCLUDED.adjusted_close,
            volume = EXCLUDED.volume,
            sma5 = EXCLUDED.sma5,
            sma10 = EXCLUDED.sma10,
            sma20 = EXCLUDED.sma20,
            sma50 = EXCLUDED.sma50,
            sma100 = EXCLUDED.sma100,
            sma200 = EXCLUDED.sma200,
            ema5 = EXCLUDED.ema5,
            ema10 = EXCLUDED.ema10,
            ema20 = EXCLUDED.ema20,
            ema50 = EXCLUDED.ema50,
            ema100 = EXCLUDED.ema100,
            ema200 = EXCLUDED.ema200,
            wma5 = EXCLUDED.wma5,
            wma10 = EXCLUDED.wma10,
            wma20 = EXCLUDED.wma20,
            wma50 = EXCLUDED.wma50,
            wma100 = EXCLUDED.wma100,
            wma200 = EXCLUDED.wma200,
            dema5 = EXCLUDED.dema5,
            dema10 = EXCLUDED.dema10,
            dema20 = EXCLUDED.dema20,
            dema50 = EXCLUDED.dema50,
            dema100 = EXCLUDED.dema100,
            dema200 = EXCLUDED.dema200,
            tema5 = EXCLUDED.tema5,
            tema10 = EXCLUDED.tema10,
            tema20 = EXCLUDED.tema20,
            tema50 = EXCLUDED.tema50,
            tema100 = EXCLUDED.tema100,
            tema200 = EXCLUDED.tema200,
            kama5 = EXCLUDED.kama5,
            kama10 = EXCLUDED.kama10,
            kama20 = EXCLUDED.kama20,
            kama50 = EXCLUDED.kama50,
            kama100 = EXCLUDED.kama100,
            kama200 = EXCLUDED.kama200,
            bbands_upper = EXCLUDED.bbands_upper,
            bbands_middle = EXCLUDED.bbands_middle,
            bbands_lower = EXCLUDED.bbands_lower,
            macd = EXCLUDED.macd,
            macd_signal = EXCLUDED.macd_signal,
            macd_hist = EXCLUDED.macd_hist,
            rsi = EXCLUDED.rsi,
            rsi_overbought = EXCLUDED.rsi_overbought,
            rsi_oversold = EXCLUDED.rsi_oversold,
            k = EXCLUDED.k,
            d = EXCLUDED.d,
            j = EXCLUDED.j,
            candlestick_patterns = EXCLUDED.candlestick_patterns,
            bullish_signal = EXCLUDED.bullish_signal,
            bearish_signal = EXCLUDED.bearish_signal,
            pattern_signal = EXCLUDED.pattern_signal,
            updated_at = NOW()
        """
        
        # Prepare data for batch insert
        batch_data = []
        for record in records:
            row_data = [record.get(col) for col in columns]
            batch_data.append(row_data)
        
        # Execute batch insert
        async with self.db.pool.acquire() as connection:
            await connection.executemany(query, batch_data)
    
    async def get_technical_data(self, symbol: str, interval: str, 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None,
                               limit: Optional[int] = None) -> pd.DataFrame:
        """Get technical data for a specific symbol and interval"""
        try:
            table_name = self.interval_tables.get(interval)
            if not table_name:
                print(f"❌ Unknown interval: {interval}")
                return pd.DataFrame()
            
            query = f"SELECT * FROM {table_name} WHERE symbol = $1"
            params = [symbol]
            param_count = 1
            
            if start_date:
                param_count += 1
                query += f" AND datetime_index >= ${param_count}"
                params.append(start_date)
            
            if end_date:
                param_count += 1
                query += f" AND datetime_index <= ${param_count}"
                params.append(end_date)
            
            query += " ORDER BY datetime_index DESC"
            
            if limit:
                param_count += 1
                query += f" LIMIT ${param_count}"
                params.append(limit)
            
            rows = await self.db.fetch_many(query, *params)
            
            if rows:
                df = pd.DataFrame(rows)
                df['datetime_index'] = pd.to_datetime(df['datetime_index'])
                df.set_index('datetime_index', inplace=True)
                return df
            else:
                return pd.DataFrame()
                
        except Exception as e:
            print(f"❌ Error getting technical data for {symbol} {interval}: {e}")
            return pd.DataFrame()
    
    async def get_latest_data(self, symbol: str, interval: str) -> Optional[Dict[str, Any]]:
        """Get the latest technical data for a symbol and interval"""
        try:
            table_name = self.interval_tables.get(interval)
            if not table_name:
                return None
            
            query = f"""
            SELECT * FROM {table_name} 
            WHERE symbol = $1 
            ORDER BY datetime_index DESC 
            LIMIT 1
            """
            
            row = await self.db.fetch_one(query, symbol)
            return dict(row) if row else None
            
        except Exception as e:
            print(f"❌ Error getting latest data for {symbol} {interval}: {e}")
            return None
