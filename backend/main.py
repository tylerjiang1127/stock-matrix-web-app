from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np
from datetime import datetime
import json

from database_init import db_initializer
from stock_metadata_fetcher import StockMetaDataFetcher
from postgres_data_retrieval import stock_data_retriever

app = FastAPI(
    title="Stock Matrix API", 
    version="1.0.0",
    description="Stock Matrix - See Through The Market"
)

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def format_timestamp_for_interval(timestamp, interval):
    """format timestamp based on interval"""
    if interval in ['1d', '1wk', '1mo']:
        # daily data uses date format
        return timestamp.strftime('%Y-%m-%d')
    else:
        # minute data uses Unix timestamp (more reliable)
        return int(timestamp.timestamp())


# request model
class StockRequest(BaseModel):
    ticker: str
    interval: str = "1d"
    ma_options: str = "sma"
    tech_ind: str = "macd"

class DatabaseStockRequest(BaseModel):
    interval: str = "1d"
    ma_options: str = "sma"
    tech_ind: str = "macd"

class ChartDataResponse(BaseModel):
    candlestick_data: List[Dict]
    volume_data: List[Dict]
    ma_data: Dict[str, List[Dict]]
    technical_data: Dict[str, List[Dict]]
    company_info: Dict[str, Any]
    chart_config: Dict[str, Any]

# global variable to store API key
# ALPHA_VANTAGE_API_KEY = "EX9111YGBHZ73GG9"
# ALPHA_VANTAGE_API_KEY = 'Y3U65MR1HAWZU87H'
ALPHA_VANTAGE_API_KEY = 'RMHG7PHKL60I5W5V'

# data conversion tool functions
class DataTransformer:
    @staticmethod
    def pandas_to_json_safe(df):
        """convert Pandas DataFrame to JSON format safely"""
        if df.empty:
            return []
        
        # reset index and convert datetime
        df_reset = df.reset_index()
        
        # process datetime column
        if 'Datetime' in df_reset.columns:
            df_reset['Datetime'] = df_reset['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # convert to dictionary list
        return df_reset.to_dict('records')
    
    @staticmethod
    def get_volume_colors(df):
        """calculate volume colors"""
        colors = []
        for _, row in df.iterrows():
            if row['Close'] > row['Open']:
                colors.append('green')
            elif row['Close'] < row['Open']:
                colors.append('red')
            else:
                colors.append('grey')
        return colors
    
    @staticmethod
    def get_macd_colors(macd_hist_series):
        """calculate MACD histogram colors"""
        colors = []
        for value in macd_hist_series:
            if value > 0:
                colors.append('green')
            elif value < 0:
                colors.append('red')
            else:
                colors.append('grey')
        return colors

    @staticmethod
    def get_time_ranges(interval):
        """return time range selector configuration based on interval"""
        if interval == '1d':
            return [
                {'count': 1, 'label': '1D', 'step': 'day'},
                {'count': 5, 'label': '5D', 'step': 'day'},
                {'count': 1, 'label': '1M', 'step': 'month'},
                {'count': 3, 'label': '3M', 'step': 'month'},
                {'count': 6, 'label': '6M', 'step': 'month'},
                {'count': 1, 'label': '1Y', 'step': 'year'},
                {'count': 5, 'label': '5Y', 'step': 'year'},
                {'label': 'All', 'step': 'all'}
            ]
        elif interval in ['1m', '5m', '15m', '30m', '60m']:
            return [
                {'count': 15, 'label': '15min', 'step': 'minute'},
                {'count': 30, 'label': '30min', 'step': 'minute'},
                {'count': 1, 'label': '1hr', 'step': 'hour'},
                {'count': 2, 'label': '2hr', 'step': 'hour'},
                {'count': 4, 'label': '4hr', 'step': 'hour'},
                {'count': 1, 'label': '1D', 'step': 'day'},
                {'label': 'All', 'step': 'all'}
            ]
        else:
            return [
                {'count': 1, 'label': '1M', 'step': 'month'},
                {'count': 3, 'label': '3M', 'step': 'month'},
                {'count': 6, 'label': '6M', 'step': 'month'},
                {'count': 1, 'label': '1Y', 'step': 'year'},
                {'label': 'All', 'step': 'all'}
            ]



@app.get("/")
async def root():
    return {
        "message": "Stock Matrix API is running",
        "tagline": "See Through The Market"
    }

@app.post("/api/stock-data", response_model=ChartDataResponse)
async def get_stock_data(request: StockRequest):
    """get stock data and convert to frontend usable format"""
    try:
        # use StockMetaDataFetcher to get data
        stock_fetcher = StockMetaDataFetcher(request.ticker, ALPHA_VANTAGE_API_KEY)
        stock_metadata = stock_fetcher.stock_metadata

        print(f"📊 Available keys in stock_metadata: {list(stock_metadata.keys())}")
        print(f"📊 Available intervals: {list(stock_metadata['stock_technical_data'].keys())}")
        
        # get data for specified interval
        if request.interval not in stock_metadata['stock_technical_data']:
            print(f"❌ Interval {request.interval} not found in data")
            raise HTTPException(status_code=404, detail=f"Interval {request.interval} not available for {request.ticker}")

        interval_data = stock_metadata['stock_technical_data'][request.interval]
        print(f"📊 Available data in interval {request.interval}: {list(interval_data.keys())}")

        if 'stock_price' not in interval_data:
            print(f"❌ No stock_price data found for interval {request.interval}")
            raise HTTPException(status_code=404, detail=f"No price data found for {request.ticker} at {request.interval}")
 
        stock_price_df = interval_data['stock_price']
        print(f"📊 Stock price data shape: {stock_price_df.shape}")
        
        if stock_price_df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {request.ticker}")
        
        # convert candlestick data
        candlestick_data = []
        volume_data = []
        volume_colors = DataTransformer.get_volume_colors(stock_price_df)
        
        for i, (index, row) in enumerate(stock_price_df.iterrows()):
            timestamp = format_timestamp_for_interval(index, request.interval)
            
            candlestick_data.append({
                'time': timestamp,
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close'])
            })
            
            volume_data.append({
                'time': timestamp,
                'value': float(row['Volume']),
                'color': volume_colors[i]
            })
        
        # convert moving average data
        ma_data = {}
        if request.ma_options and request.ma_options in interval_data:
            ma_df = interval_data[request.ma_options]
            for col in ma_df.columns:
                if col.isdigit():  # moving average period column
                    ma_series = []
                    for index, value in ma_df[col].items():
                        timestamp = format_timestamp_for_interval(index, request.interval)
                        if pd.notna(value):
                            ma_series.append({
                                'time': timestamp,
                                'value': float(value)
                            })
                    ma_data[f"{request.ma_options.upper()}{col}"] = ma_series
                
                # boll band data
                elif col in ['bbands_upper', 'bbands_middle', 'bbands_lower']:
                    bb_series = []
                    for index, value in ma_df[col].items():
                        timestamp = format_timestamp_for_interval(index, request.interval)
                        if pd.notna(value):
                            bb_series.append({
                                'time': timestamp,
                                'value': float(value)
                            })
                    ma_data[col.upper()] = bb_series
        
        # convert technical indicator data
        technical_data = {}
        if request.tech_ind and request.tech_ind in interval_data:
            tech_data = interval_data[request.tech_ind]  # a dictionary
            
            if request.tech_ind == 'macd':
                # MACD data is a dictionary format, containing pandas Series macd is
                macd_line = []
                signal_line = []
                histogram = []
                
                # get pandas Series
                macd_series = tech_data['macd']
                signal_series = tech_data['macd_signal_line'] 
                hist_series = tech_data['macd_hist']
                
                # iterate through Series instead of DataFrame
                for timestamp in macd_series.index:
                    timestamp_str = format_timestamp_for_interval(timestamp, request.interval)
                    
                    if pd.notna(macd_series.loc[timestamp]):
                        macd_line.append({
                            'time': timestamp_str,
                            'value': float(macd_series.loc[timestamp])
                        })
                    
                    if pd.notna(signal_series.loc[timestamp]):
                        signal_line.append({
                            'time': timestamp_str,
                            'value': float(signal_series.loc[timestamp])
                        })
                    
                    if pd.notna(hist_series.loc[timestamp]):
                        hist_value = hist_series.loc[timestamp]
                        color = 'green' if hist_value > 0 else 'red' if hist_value < 0 else 'grey'
                        histogram.append({
                            'time': timestamp_str,
                            'value': float(hist_value),
                            'color': color
                        })
                
                technical_data = {
                    'macd_line': macd_line,
                    'signal_line': signal_line,
                    'histogram': histogram
                }
            
            elif request.tech_ind == 'rsi':
                rsi_line = []
                rsi_series = tech_data['rsi']  # pandas Series
                
                for timestamp, value in rsi_series.items():
                    if pd.notna(value):
                        rsi_line.append({
                            'time': format_timestamp_for_interval(timestamp, request.interval),
                            'value': float(value)
                        })
                technical_data = {'rsi_line': rsi_line}
            
            elif request.tech_ind == 'kdj':
                k_line = []
                d_line = []
                j_line = []
                
                k_series = tech_data['k']  # pandas Series
                d_series = tech_data['d']  # pandas Series
                j_series = tech_data['j']  # pandas Series
                
                for timestamp in k_series.index:
                    timestamp_str = format_timestamp_for_interval(timestamp, request.interval)
                    
                    if pd.notna(k_series.loc[timestamp]):
                        k_line.append({'time': timestamp_str, 'value': float(k_series.loc[timestamp])})
                    if pd.notna(d_series.loc[timestamp]):
                        d_line.append({'time': timestamp_str, 'value': float(d_series.loc[timestamp])})
                    if pd.notna(j_series.loc[timestamp]):
                        j_line.append({'time': timestamp_str, 'value': float(j_series.loc[timestamp])})
                
                technical_data = {
                    'k_line': k_line,
                    'd_line': d_line,
                    'j_line': j_line
                }
                
        # company information
        company_info = stock_metadata.get('company_overview', {})
        
        # chart configuration
        chart_config = {
            'interval': request.interval,
            'ma_options': request.ma_options,
            'tech_ind': request.tech_ind,
            'colors': {
                'ma_colors': ['#A83838', '#F09A16', '#EFF048', '#5DF016', '#13C3F0', '#493CF0', '#F000DF'],
                'bbands_color': '#ADD8E6',
                'macd_line': 'orange',
                'signal_line': 'deepskyblue',
                'rsi_line': 'orange',
                'k_line': 'gold',
                'd_line': 'blue',
                'j_line': 'purple'
            },
            'time_ranges': DataTransformer.get_time_ranges(request.interval)
        }
        
        return ChartDataResponse(
            candlestick_data=candlestick_data,
            volume_data=volume_data,
            ma_data=ma_data,
            technical_data=technical_data,
            company_info=company_info,
            chart_config=chart_config
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/initialize-database")
async def initialize_database(
    alpha_vantage_api_key: str,
    max_stocks: int = None
):
    """Initialize the complete database with stock list and metadata"""
    try:
        success = await db_initializer.initialize_database(
            alpha_vantage_api_key, max_stocks
        )
        
        if success:
            return {"message": "Database initialized successfully", "status": "success"}
        else:
            return {"message": "Database initialization failed", "status": "error"}
            
    except Exception as e:
        return {"message": f"Error: {str(e)}", "status": "error"}

@app.post("/api/initialize-stock-list")
async def initialize_stock_list(alpha_vantage_api_key: str):
    """Initialize only the stock list"""
    try:
        await db_initializer.initialize_repositories()
        success = await db_initializer.initialize_stock_list(alpha_vantage_api_key)
        
        if success:
            return {"message": "Stock list initialized successfully", "status": "success"}
        else:
            return {"message": "Stock list initialization failed", "status": "error"}
            
    except Exception as e:
        return {"message": f"Error: {str(e)}", "status": "error"}

@app.post("/api/initialize-stock-metadata")
async def initialize_stock_metadata(
    alpha_vantage_api_key: str,
    max_stocks: int = None
):
    """Initialize only the stock metadata"""
    try:
        await db_initializer.initialize_repositories()
        success = await db_initializer.initialize_stock_metadata(
            alpha_vantage_api_key, max_stocks
        )
        
        if success:
            return {"message": "Stock metadata initialized successfully", "status": "success"}
        else:
            return {"message": "Stock metadata initialization failed", "status": "error"}
            
    except Exception as e:
        return {"message": f"Error: {str(e)}", "status": "error"}

@app.get("/api/stocks")
async def get_stocks():
    """Get all stocks from database"""
    try:
        await db_initializer.initialize_repositories()
        stocks = await db_initializer.stock_list_repo.get_all_stocks()
        
        # Convert to simple format for frontend
        stock_list = []
        for stock in stocks:
            # Clean market_cap value to ensure JSON compliance
            market_cap = stock.market_cap
            if market_cap is not None and isinstance(market_cap, (int, float)):
                # Check for NaN, Inf, -Inf
                if np.isnan(market_cap) or np.isinf(market_cap):
                    market_cap = None
            
            stock_list.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "exchange": stock.exchange,
                "market_cap": market_cap
            })
        
        return stock_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stocks: {str(e)}")

@app.post("/api/stocks/{symbol}")
async def get_stock_data(symbol: str, request: DatabaseStockRequest):
    """Get stock data from database"""
    try:
        await db_initializer.initialize_repositories()
        
        # Get company overview from MongoDB
        company_info = await db_initializer.stock_metadata_repo.get_stock_metadata(symbol)
        
        # Get technical data from PostgreSQL
        technical_data = await stock_data_retriever.get_stock_technical_data(
            symbol, request.interval
        )
        
        if not technical_data:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        # Format data for frontend (similar to original API response)
        response_data = {
            "candlestick_data": technical_data.get("candlestick_data", []),
            "volume_data": technical_data.get("volume_data", []),
            "ma_data": technical_data.get("ma_data", {}),
            "technical_data": technical_data.get("technical_data", {}),
            "company_info": company_info.get("company_overview", {}) if company_info else {},
            "chart_config": {
                "ticker": symbol,
                "interval": request.interval,
                "ma_options": request.ma_options,
                "tech_ind": request.tech_ind,
                "time_ranges": DataTransformer.get_time_ranges(request.interval)
            }
        }
        
        return response_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stock data: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)