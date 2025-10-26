"""
PostgreSQL data retrieval methods for frontend
"""

from typing import Dict, Any
from simple_postgres_models import SimpleTechnicalDataRepository
from postgres_database import postgres_db

class StockDataRetriever:
    def __init__(self):
        self.technical_data_repo = SimpleTechnicalDataRepository(postgres_db)
    
    async def get_stock_technical_data(self, symbol: str, interval: str) -> Dict[str, Any]:
        """Get stock technical data from PostgreSQL"""
        try:
            table_name = self.technical_data_repo.interval_tables.get(interval)
            if not table_name:
                print(f"❌ Unknown interval: {interval}")
                return None
            
            async with postgres_db.pool.acquire() as connection:
                # Get all data for the symbol
                query = f"""
                SELECT * FROM {table_name} 
                WHERE symbol = $1 
                ORDER BY datetime_index ASC
                """
                
                rows = await connection.fetch(query, symbol)
                
                if not rows:
                    print(f"⚠️ No data found for {symbol} {interval}")
                    return None
                
                # Convert to DataFrame-like structure for frontend
                candlestick_data = []
                volume_data = []
                ma_data = {}
                technical_data = {}
                
                for row in rows:
                    # Format time - Lightweight Charts expects Unix timestamp for all intervals
                    time_str = int(row["datetime_index"].timestamp())
                    
                    # Candlestick data
                    candlestick_data.append({
                        "time": time_str,
                        "open": float(row["open"]) if row["open"] else None,
                        "high": float(row["high"]) if row["high"] else None,
                        "low": float(row["low"]) if row["low"] else None,
                        "close": float(row["close"]) if row["close"] else None
                    })
                    
                    # Volume data with proper color logic
                    close_price = float(row["close"]) if row["close"] else 0
                    open_price = float(row["open"]) if row["open"] else 0
                    volume_color = "green" if close_price >= open_price else "red"
                    
                    volume_data.append({
                        "time": time_str,
                        "value": int(row["volume"]) if row["volume"] else 0,
                        "color": volume_color
                    })
                    
                    # Moving averages - organize by type
                    # Use the same periods as StockMetaDataFetcher
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
                    
                    for period in periods:
                        for ma_type in ["sma", "ema", "wma", "dema", "tema", "kama"]:
                            col_name = f"{ma_type}{period}"
                            if col_name in row and row[col_name] is not None:
                                if ma_type not in ma_data:
                                    ma_data[ma_type] = []
                                ma_data[ma_type].append({
                                    "time": time_str,
                                    "value": float(row[col_name]),
                                    "period": period
                                })
                    
                    # Bollinger Bands
                    if row.get("bbands_upper") is not None:
                        if "bbands_upper" not in ma_data:
                            ma_data["bbands_upper"] = []
                        ma_data["bbands_upper"].append({
                            "time": time_str,
                            "value": float(row["bbands_upper"])
                        })
                    
                    if row.get("bbands_lower") is not None:
                        if "bbands_lower" not in ma_data:
                            ma_data["bbands_lower"] = []
                        ma_data["bbands_lower"].append({
                            "time": time_str,
                            "value": float(row["bbands_lower"])
                        })
                    
                    # Technical indicators - MACD
                    if row.get("macd") is not None:
                        if "macd_line" not in technical_data:
                            technical_data["macd_line"] = []
                        technical_data["macd_line"].append({
                            "time": time_str,
                            "value": float(row["macd"])
                        })
                    
                    if row.get("macd_signal") is not None:
                        if "signal_line" not in technical_data:
                            technical_data["signal_line"] = []
                        technical_data["signal_line"].append({
                            "time": time_str,
                            "value": float(row["macd_signal"])
                        })
                    
                    if row.get("macd_hist") is not None:
                        if "histogram" not in technical_data:
                            technical_data["histogram"] = []
                        hist_value = float(row["macd_hist"])
                        technical_data["histogram"].append({
                            "time": time_str,
                            "value": hist_value,
                            "color": "green" if hist_value >= 0 else "red"
                        })
                    
                    # RSI
                    if row.get("rsi") is not None:
                        if "rsi_line" not in technical_data:
                            technical_data["rsi_line"] = []
                        technical_data["rsi_line"].append({
                            "time": time_str,
                            "value": float(row["rsi"])
                        })
                    
                    # KDJ
                    if row.get("k") is not None:
                        if "k_line" not in technical_data:
                            technical_data["k_line"] = []
                        technical_data["k_line"].append({
                            "time": time_str,
                            "value": float(row["k"])
                        })
                    
                    if row.get("d") is not None:
                        if "d_line" not in technical_data:
                            technical_data["d_line"] = []
                        technical_data["d_line"].append({
                            "time": time_str,
                            "value": float(row["d"])
                        })
                    
                    if row.get("j") is not None:
                        if "j_line" not in technical_data:
                            technical_data["j_line"] = []
                        technical_data["j_line"].append({
                            "time": time_str,
                            "value": float(row["j"])
                        })
                
                return {
                    "candlestick_data": candlestick_data,
                    "volume_data": volume_data,
                    "ma_data": ma_data,
                    "technical_data": technical_data
                }
                
        except Exception as e:
            print(f"❌ Error getting technical data for {symbol} {interval}: {e}")
            return None
    
    def _get_volume_color(self, close, open_price):
        """Get volume color based on price movement"""
        if close is None or open_price is None:
            return "#666666"
        return "#26a69a" if close >= open_price else "#ef5350"

# Global instance
stock_data_retriever = StockDataRetriever()
