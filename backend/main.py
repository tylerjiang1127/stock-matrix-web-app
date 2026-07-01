from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Cookie, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
import json
import asyncio
import os

from database_init import db_initializer
from stock_metadata_fetcher import StockMetaDataFetcher
from postgres_data_retrieval import stock_data_retriever
from redis_database import cache_manager, redis_db
from postgres_database import postgres_db
import uuid
from auth_routes import auth_router, get_current_user
from entitlements import monitor_max, get_entitlements
from data_sources import (
    AlphaVantageAdapter, YFinanceAdapter, FinnhubAdapter,
    DataValidator, HealthMonitor, DataSourceManager,
)
from data_sources.nightly_pipeline import NightlyPipeline
from data_sources.realtime_service import RealtimeService
from data_sources.live_quotes_service import LiveQuotesService
from data_sources.data_initializer import DataInitializer
from ai.ai_router import ai_router

app = FastAPI(
    title="Stock Matrix API", 
    version="1.0.0",
    description="Stock Matrix - See Through The Market"
)

# Include routers
app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(ai_router, prefix="/api/ai", tags=["ai"])

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public base URL of the frontend (used to build shareable referral links)
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

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
    days: Optional[int] = None

class DatabaseInitRequest(BaseModel):
    alpha_vantage_api_key: str
    max_stocks: Optional[int] = None
    batch_size: int = 6

class DatabaseInitRequest(BaseModel):
    alpha_vantage_api_key: str
    max_stocks: Optional[int] = None
    batch_size: int = 6

class ChartDataResponse(BaseModel):
    candlestick_data: List[Dict]
    volume_data: List[Dict]
    ma_data: Dict[str, List[Dict]]
    technical_data: Dict[str, List[Dict]]
    company_info: Dict[str, Any]
    chart_config: Dict[str, Any]

ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY', '')

@app.on_event("startup")
async def startup_data_sources():
    av_adapter = AlphaVantageAdapter(api_key=ALPHA_VANTAGE_API_KEY)
    yf_adapter = YFinanceAdapter()
    fh_adapter = FinnhubAdapter(api_key=os.getenv('FINNHUB_API_KEY', ''))
    validator = DataValidator()
    health = HealthMonitor(redis_db)
    dsm = DataSourceManager(
        adapters=[av_adapter, yf_adapter, fh_adapter],
        validator=validator,
        health_monitor=health,
    )
    app.state.data_source_manager = dsm

    await db_initializer.initialize_repositories()
    from simple_postgres_models import SimpleTechnicalDataRepository
    from postgres_database import postgres_db
    from database import db as db_conn
    pg_repo = SimpleTechnicalDataRepository(postgres_db)
    app.state.pg_repo = pg_repo

    from credits_service import CreditsService
    app.state.credits_service = CreditsService(postgres_db)

    from anon_usage import AnonUsageService
    app.state.anon_usage = AnonUsageService(postgres_db, redis_db)

    from referral_service import ReferralService
    app.state.referral_service = ReferralService(postgres_db, app.state.credits_service)

    from tier_service import TierService
    app.state.tier_service = TierService(postgres_db, app.state.credits_service)
    mongo_db = db_conn.mongodb_db if hasattr(db_conn, 'mongodb_db') else None

    from activity_service import ActivityService
    app.state.activity_service = ActivityService(mongo_db)
    await app.state.activity_service.ensure_indexes()

    metadata_repo = db_initializer.stock_metadata_repo \
        if hasattr(db_initializer, 'stock_metadata_repo') else None

    app.state.nightly_pipeline = NightlyPipeline(
        data_source_manager=dsm,
        pg_repo=pg_repo,
        stock_list_repo=db_initializer.stock_list_repo,
        mongo_db=mongo_db,
        stock_metadata_repo=metadata_repo,
    )

    app.state.data_initializer = DataInitializer(
        data_source_manager=dsm,
        pg_repo=pg_repo,
        stock_list_repo=db_initializer.stock_list_repo,
        mongo_db=mongo_db,
        stock_metadata_repo=metadata_repo,
    )
    app.state.init_status = 'pending'

    # ── AI layer init ──────────────────────────────────
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        from ai.deepseek_client import DeepseekClient
        from ai.report.report_generator import ReportGenerator
        from repositories import AIReportRepository

        ai_client = DeepseekClient(
            api_key=deepseek_key,
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            max_concurrency=int(os.getenv("AI_MAX_CONCURRENCY", "8")),
        )
        app.state.ai_client = ai_client

        mongo_db = db_conn.mongodb_db if hasattr(db_conn, "mongodb_db") else None
        if mongo_db is not None:
            ai_report_repo = AIReportRepository(mongo_db)
            await ai_report_repo.ensure_indexes()
            app.state.ai_report_repo = ai_report_repo

            app.state.report_generator = ReportGenerator(
                ai_client=ai_client,
                pg_repo=pg_repo,
                stock_metadata_repo=db_initializer.stock_metadata_repo
                    if hasattr(db_initializer, "stock_metadata_repo") else None,
                report_repo=ai_report_repo,
            )
            print("AI report engine initialized (Deepseek)")

            # ── Chat agent ────────────────────────────────
            from ai.tools.stock_data_tools import ToolRegistry
            from ai.chat.chat_agent import ChatAgent
            from repositories import AIConversationRepository

            tool_registry = ToolRegistry(
                pg_repo=pg_repo,
                stock_metadata_repo=db_initializer.stock_metadata_repo
                    if hasattr(db_initializer, "stock_metadata_repo") else None,
                data_source_manager=dsm,
            )
            conv_repo = AIConversationRepository(mongo_db)
            await conv_repo.ensure_indexes()
            app.state.ai_conversation_repo = conv_repo

            app.state.chat_agent = ChatAgent(
                ai_client=ai_client,
                tool_registry=tool_registry,
                conversation_repo=conv_repo,
            )
            print("AI chat agent initialized")

            # ── NL Screener ──────────────────────────────
            from ai.screener.nl_screener import NLScreener
            app.state.nl_screener = NLScreener(
                ai_client=ai_client,
                pg_repo=pg_repo,
                data_source_manager=dsm,
            )
            print("AI NL screener initialized")
        else:
            app.state.ai_report_repo = None
            app.state.report_generator = None
            app.state.chat_agent = None
            app.state.ai_conversation_repo = None
            app.state.nl_screener = None
            print("AI features skipped (MongoDB not connected)")
    else:
        app.state.ai_client = None
        app.state.ai_report_repo = None
        app.state.report_generator = None
        app.state.chat_agent = None
        app.state.ai_conversation_repo = None
        app.state.nl_screener = None
        print("AI features disabled (no DEEPSEEK_API_KEY)")

    # ── Real-time service ─────────────────────────────
    app.state.realtime_service = RealtimeService()
    app.state.realtime_service.start()
    print("Real-time stock data service started (polls during market hours)")

    # ── Live quotes service ───────────────────────────
    app.state.live_quotes_service = LiveQuotesService()
    print("Live quotes service initialized")

    # ── Scheduler ──────────────────────────────────────
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            app.state.nightly_pipeline.run_phase1_kline,
            CronTrigger(hour=17, minute=0, timezone='US/Eastern', day_of_week='mon-fri'),
            id='pipeline_phase1_kline',
            replace_existing=True,
        )
        scheduler.add_job(
            app.state.nightly_pipeline.run_phase2_fundamentals,
            CronTrigger(hour=1, minute=0, timezone='US/Eastern'),
            id='pipeline_phase2_fundamentals',
            replace_existing=True,
        )
        print("Pipeline Phase 1 (K-line) scheduled at 5:00 PM ET (Mon-Fri)")
        print("Pipeline Phase 2 (Fundamentals+News) scheduled at 1:00 AM ET (Daily)")

        if getattr(app.state, "report_generator", None):
            scheduler.add_job(
                app.state.report_generator.generate_daily_report,
                CronTrigger(
                    hour=19, minute=0, timezone='US/Eastern',
                    day_of_week='mon-fri',
                ),
                id='daily_macro_report',
                replace_existing=True,
            )
            print("AI Macro Daily Report scheduled at 7:00 PM ET (Mon-Fri)")

        scheduler.start()
        app.state.scheduler = scheduler
    except Exception as e:
        print(f"APScheduler not available, nightly cron disabled: {e}")

    # ── Auto-initialization on first launch ───────────
    async def _auto_init():
        initializer = app.state.data_initializer
        if await initializer.needs_initialization():
            print("\n[Startup] Database is empty — starting initialization...")
            app.state.init_status = 'running'
            try:
                result = await initializer.run()
                app.state.init_status = result.get('status', 'completed')
                print(f"[Startup] Initialization {app.state.init_status}")
            except Exception as e:
                app.state.init_status = 'failed'
                print(f"[Startup] Initialization failed: {e}")
        else:
            app.state.init_status = 'completed'
            print("[Startup] Database already initialized, skipping")

    asyncio.create_task(_auto_init())

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
async def initialize_database(request: DatabaseInitRequest):
    """Initialize the complete database with stock list and metadata
    
    Args:
        request: Database initialization request containing:
            - alpha_vantage_api_key: Your Alpha Vantage API key
            - max_stocks: Maximum number of stocks to process (None for all)
            - batch_size: Number of stocks to process concurrently per minute (default: 6)
    """
    try:
        success = await db_initializer.initialize_database(
            request.alpha_vantage_api_key, 
            request.max_stocks, 
            request.batch_size
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

@app.post("/api/stocks/{symbol}/chart")
async def get_stock_chart(symbol: str, request: DatabaseStockRequest):
    """Fast chart data from PG only — renders in <0.1s"""
    try:
        await db_initializer.initialize_repositories()

        technical_data = await stock_data_retriever.get_stock_technical_data(
            symbol, request.interval, days=request.days
        )

        if not technical_data and request.interval in ('1m', '5m', '15m', '30m', '60m'):
            dsm = app.state.data_source_manager
            from data_sources.indicator_calculator import IndicatorCalculator
            calc = IndicatorCalculator()
            ohlcv = await dsm.fetch_ohlcv(symbol, request.interval)
            if ohlcv.success and ohlcv.data is not None and not ohlcv.data.empty:
                indicators = calc.compute_all_indicators(ohlcv.data, request.interval)
                await app.state.pg_repo.save_technical_data(
                    symbol, request.interval, indicators
                )
                technical_data = await stock_data_retriever.get_stock_technical_data(
                    symbol, request.interval, days=request.days
                )

        if not technical_data:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        return {
            "candlestick_data": technical_data.get("candlestick_data", []),
            "volume_data": technical_data.get("volume_data", []),
            "ma_data": technical_data.get("ma_data", {}),
            "technical_data": technical_data.get("technical_data", {}),
            "chart_config": {
                "ticker": symbol,
                "interval": request.interval,
                "ma_options": request.ma_options,
                "tech_ind": request.tech_ind,
                "time_ranges": DataTransformer.get_time_ranges(request.interval)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching chart data: {str(e)}")


@app.post("/api/stocks/{symbol}/market-close-refresh")
async def refresh_market_close(symbol: str, request: DatabaseStockRequest):
    """Fetch today's close from yfinance, compute indicators, save to PG, return chart data."""
    try:
        import yfinance as yf
        from data_sources.indicator_calculator import IndicatorCalculator

        await db_initializer.initialize_repositories()

        yf_symbol = symbol.replace(".", "-")
        df = yf.Ticker(yf_symbol).history(period="1y", interval="1d")
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No yfinance data for {symbol}")

        # Strip timezone so save_technical_data can tz_localize to UTC
        df.index = df.index.tz_localize(None)

        calc = IndicatorCalculator()
        indicators = calc.compute_all_indicators(df, "1d")

        # Save only today's row so we don't overwrite pipeline data
        today_indicators = dict(indicators)
        today_indicators["stock_price"] = df.iloc[[-1]]
        await app.state.pg_repo.save_technical_data(symbol, "1d", today_indicators)

        # Return full chart from PG (now includes today)
        technical_data = await stock_data_retriever.get_stock_technical_data(
            symbol, request.interval, days=request.days
        )
        if not technical_data:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")

        last = df.iloc[-1]
        prev_close = float(df.iloc[-2]["Close"]) if len(df) >= 2 else None
        close = float(last["Close"])

        return {
            "candlestick_data": technical_data.get("candlestick_data", []),
            "volume_data": technical_data.get("volume_data", []),
            "ma_data": technical_data.get("ma_data", {}),
            "technical_data": technical_data.get("technical_data", {}),
            "close_price": {
                "price": round(close, 4),
                "prev_close": prev_close,
                "change": round(close - prev_close, 4) if prev_close else None,
                "change_pct": round((close - prev_close) / prev_close * 100, 2) if prev_close and prev_close > 0 else None,
            },
            "chart_config": {
                "ticker": symbol,
                "interval": request.interval,
                "ma_options": request.ma_options,
                "tech_ind": request.tech_ind,
                "time_ranges": DataTransformer.get_time_ranges(request.interval),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing market close data: {str(e)}")


@app.get("/api/stocks/{symbol}/info")
async def get_stock_info(symbol: str):
    """Company overview + news + fundamentals — cached in MongoDB, parallel fetch"""
    try:
        await db_initializer.initialize_repositories()
        dsm = app.state.data_source_manager
        metadata_repo = db_initializer.stock_metadata_repo

        existing_metadata = await metadata_repo.get_stock_metadata(symbol) or {'ticker': symbol}

        # --- Parallel: overview, news, fundamentals stale-check ---
        async def get_overview():
            cached = existing_metadata.get('company_overview')
            if cached and cached.get('longName'):
                # Validate the cached entry belongs to this symbol.
                # A mismatch means the MongoDB document has stale/corrupt data
                # (e.g. company_overview from a previous ticker stored under the
                # wrong key). Re-fetch in that case rather than returning wrong info.
                cached_sym = (cached.get('Symbol') or cached.get('symbol') or '').upper()
                if not cached_sym or cached_sym == symbol.upper():
                    return cached
                # Symbol mismatch — evict and refetch
                existing_metadata.pop('company_overview', None)
            result = await dsm.fetch_company_overview(symbol)
            if result.success and result.data:
                existing_metadata['company_overview'] = result.data
                return result.data
            return existing_metadata.get('company_overview') or {'symbol': symbol}

        async def get_news():
            cached = existing_metadata.get('news_sentiment')
            if cached and cached.get('fetched_at'):
                fetched_at = cached['fetched_at']
                if isinstance(fetched_at, datetime) and fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=_ET)
                age = (datetime.now(_ET) - fetched_at).total_seconds()
                if age < 86400:
                    return cached
            result = await dsm.fetch_news_sentiment(symbol)
            if result.success and result.data:
                news = result.data
                news['fetched_at'] = datetime.now(_ET)
                existing_metadata['news_sentiment'] = news
                return news
            return cached or {
                'average_sentiment_score': 0, 'average_sentiment_label': 'Neutral',
                'total_articles': 0, 'articles': [],
            }

        async def get_fundamentals():
            stock_fundamental = existing_metadata.get('stock_fundamental', {})
            need_fetch = not stock_fundamental
            if not need_fetch:
                try:
                    quarterly = stock_fundamental.get('quarterly', {})
                    income = quarterly.get('income_statement', {})
                    data_list = income.get('data', []) if isinstance(income, dict) else []
                    if data_list:
                        last_date_val = data_list[0].get('fiscalDateEnding')
                        if isinstance(last_date_val, str):
                            last_date = datetime.strptime(last_date_val[:10], '%Y-%m-%d')
                        elif isinstance(last_date_val, datetime):
                            last_date = last_date_val
                        else:
                            need_fetch = True
                            last_date = None
                        if last_date and (datetime.now(_ET).replace(tzinfo=None) - last_date.replace(tzinfo=None)).days > 100:
                            need_fetch = True
                    else:
                        need_fetch = True
                except Exception:
                    need_fetch = True

            if need_fetch:
                fund_result = await dsm.fetch_fundamentals(symbol)
                new_fund = fund_result.data if fund_result.success else {}
                old_fund = existing_metadata.get('stock_fundamental', {})
                has_content = False
                for period in ['annual', 'quarterly']:
                    if period not in old_fund:
                        old_fund[period] = {}
                    if period in new_fund:
                        for stmt in ['income_statement', 'balance_sheet', 'cash_flow']:
                            new_stmt = new_fund[period].get(stmt)
                            if isinstance(new_stmt, pd.DataFrame) and not new_stmt.empty:
                                old_fund[period][stmt] = new_stmt
                                has_content = True
                if has_content:
                    existing_metadata['stock_fundamental'] = old_fund
                stock_fundamental = existing_metadata.get('stock_fundamental', {})

            return stock_fundamental

        company_overview, news_sentiment, stock_fundamental = await asyncio.gather(
            get_overview(), get_news(), get_fundamentals()
        )

        # Save updated metadata back to MongoDB (background, don't block response)
        asyncio.create_task(
            metadata_repo.create_or_update_stock_metadata(symbol, existing_metadata)
        )

        def _sanitize_rows(rows):
            """Replace NaN/Inf floats with None — JSON does not allow them."""
            return [
                {k: None if isinstance(v, float) and (v != v or v == float('inf') or v == float('-inf')) else v
                 for k, v in row.items()}
                for row in rows
            ]

        # Format fundamentals for frontend
        formatted_fundamental = {}
        for period in ['annual', 'quarterly']:
            if period in stock_fundamental:
                formatted_fundamental[period] = {}
                for statement_type in ['income_statement', 'balance_sheet', 'cash_flow']:
                    statement_data = stock_fundamental[period].get(statement_type, {})
                    if isinstance(statement_data, pd.DataFrame):
                        if not statement_data.empty:
                            try:
                                records = _sanitize_rows(statement_data.to_dict('records'))
                                formatted_fundamental[period][statement_type] = {
                                    'data': records,
                                    'columns': statement_data.columns.tolist(),
                                    'index': statement_data.index.tolist()
                                }
                            except Exception:
                                formatted_fundamental[period][statement_type] = {}
                        else:
                            formatted_fundamental[period][statement_type] = {}
                    elif isinstance(statement_data, dict) and 'data' in statement_data:
                        # MongoDB-cached dict: also sanitize NaN from stored records
                        formatted_fundamental[period][statement_type] = {
                            **statement_data,
                            'data': _sanitize_rows(statement_data.get('data', [])),
                        }
                    else:
                        formatted_fundamental[period][statement_type] = {}

        return {
            "company_info": company_overview,
            "news_sentiment": news_sentiment,
            "fundamental_data": formatted_fundamental,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stock info: {str(e)}")


# Keep legacy endpoint for backwards compatibility
@app.post("/api/stocks/{symbol}")
async def get_stock_data(symbol: str, request: DatabaseStockRequest):
    """Legacy combined endpoint — calls chart + info internally"""
    chart_task = get_stock_chart(symbol, request)
    info_task = get_stock_info(symbol)
    chart_data, info_data = await asyncio.gather(chart_task, info_task)
    return {**chart_data, **info_data}


@app.get("/api/health/sources")
async def get_source_health():
    dsm = app.state.data_source_manager
    return await dsm.get_all_health()


@app.websocket("/ws/realtime")
async def realtime_websocket(ws: WebSocket):
    svc: RealtimeService = app.state.realtime_service
    lqs: LiveQuotesService = app.state.live_quotes_service
    await svc.connect(ws)
    subscribed_symbols: set = set()
    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")
            symbol = (data.get("symbol") or "").upper()

            if action == "subscribe" and symbol:
                subscribed_symbols.add(symbol)
                result = await lqs.subscribe(symbol)
                if result:
                    await ws.send_json({"type": "live_quote", "symbol": symbol, **result})

            elif action == "unsubscribe" and symbol:
                subscribed_symbols.discard(symbol)
                await lqs.unsubscribe(symbol)

            await svc.handle_message(ws, data)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        svc.disconnect(ws)
        for sym in subscribed_symbols:
            await lqs.unsubscribe(sym)


@app.get("/api/live-quotes/{symbol}")
async def get_live_quote(symbol: str):
    """Query the live_quotes table for a symbol's cached data."""
    lqs: LiveQuotesService = app.state.live_quotes_service
    data = await lqs.get_quote(symbol.upper())
    if not data:
        return {"found": False, "symbol": symbol.upper()}
    return {"found": True, **data}


@app.post("/api/live-quotes/{symbol}/subscribe")
async def subscribe_live_quote(symbol: str):
    """Trigger a fetch if needed and start polling. Returns current data."""
    lqs: LiveQuotesService = app.state.live_quotes_service
    data = await lqs.subscribe(symbol.upper())
    return {"found": bool(data), **(data or {})}


@app.post("/api/live-quotes/{symbol}/unsubscribe")
async def unsubscribe_live_quote(symbol: str):
    """Decrement viewer count for a symbol."""
    lqs: LiveQuotesService = app.state.live_quotes_service
    await lqs.unsubscribe(symbol.upper())
    return {"status": "ok"}


# ── Monitor List Endpoints ────────────────────────────────

class MonitorListSyncRequest(BaseModel):
    symbols: List[str]

@app.get("/api/monitor-list")
async def get_monitor_list(session_id: Optional[str] = Cookie(None)):
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    uid = uuid.UUID(user["user_id"])
    async with postgres_db.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT symbol FROM user_monitor_list WHERE user_id = $1 ORDER BY added_at", uid
        )
    return {"symbols": [r["symbol"] for r in rows]}

# NOTE: this static route MUST be declared before "/api/monitor-list/{symbol}",
# otherwise FastAPI matches "sync" as a {symbol} and the add endpoint runs instead.
@app.post("/api/monitor-list/sync")
async def sync_monitor_list(body: MonitorListSyncRequest, session_id: Optional[str] = Cookie(None)):
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    uid = uuid.UUID(user["user_id"])
    async with postgres_db.pool.acquire() as conn:
        tier = await conn.fetchval("SELECT tier FROM user_id_security WHERE id = $1", uid)
        max_stocks = monitor_max(tier)
        for sym in body.symbols[:max_stocks]:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM user_monitor_list WHERE user_id = $1", uid
            )
            if count >= max_stocks:
                break
            await conn.execute(
                "INSERT INTO user_monitor_list (user_id, symbol) VALUES ($1, $2) ON CONFLICT (user_id, symbol) DO NOTHING",
                uid, sym.upper()
            )
        rows = await conn.fetch(
            "SELECT symbol FROM user_monitor_list WHERE user_id = $1 ORDER BY added_at", uid
        )
    return {"symbols": [r["symbol"] for r in rows]}

@app.post("/api/monitor-list/{symbol}")
async def add_to_monitor_list(symbol: str, session_id: Optional[str] = Cookie(None)):
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    uid = uuid.UUID(user["user_id"])
    async with postgres_db.pool.acquire() as conn:
        tier = await conn.fetchval("SELECT tier FROM user_id_security WHERE id = $1", uid)
        max_stocks = monitor_max(tier)
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM user_monitor_list WHERE user_id = $1", uid
        )
        if count >= max_stocks:
            raise HTTPException(
                status_code=400,
                detail=f"Your {tier} plan allows up to {max_stocks} monitored stocks",
            )
        await conn.execute(
            "INSERT INTO user_monitor_list (user_id, symbol) VALUES ($1, $2) ON CONFLICT (user_id, symbol) DO NOTHING",
            uid, symbol.upper()
        )
    return {"status": "ok", "symbol": symbol.upper()}

@app.delete("/api/monitor-list/{symbol}")
async def remove_from_monitor_list(symbol: str, session_id: Optional[str] = Cookie(None)):
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    uid = uuid.UUID(user["user_id"])
    async with postgres_db.pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM user_monitor_list WHERE user_id = $1 AND symbol = $2",
            uid, symbol.upper()
        )
    return {"status": "ok", "symbol": symbol.upper()}


@app.get("/api/me/entitlements")
async def get_my_entitlements(request: Request, session_id: Optional[str] = Cookie(None)):
    """Effective tier limits + credit balances for the caller.

    The frontend reads this so the UI never drifts from server-side rules. Returns
    anonymous entitlements + per-IP AI usage (for the soft paywall) when not logged in.
    """
    user = await get_current_user(session_id)
    if not user:
        anon = getattr(app.state, "anon_usage", None)
        anon_usage = None
        if anon:
            from ai.ai_router import _client_ip
            anon_usage = await anon.get_status(_client_ip(request))
        return {
            "authenticated": False,
            "tier": "anonymous",
            "entitlements": get_entitlements("anonymous"),
            "credits": None,
            "anon_usage": anon_usage,
        }
    wallet = await app.state.credits_service.get_wallet(user["user_id"])
    tier = wallet["tier"]
    return {
        "authenticated": True,
        "tier": tier,
        "entitlements": get_entitlements(tier),
        "credits": {
            "base": wallet["base_credits"],
            "boost": wallet["boost_credits"],
            "total": wallet["total"],
            "monthly_allotment": wallet["monthly_allotment"],
            "resets_on": wallet["resets_on"],
        },
    }


@app.get("/api/referral")
async def get_referral(session_id: Optional[str] = Cookie(None)):
    """The caller's referral code, shareable link, and reward stats (for the profile card)."""
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    async with postgres_db.pool.acquire() as conn:
        code = await conn.fetchval(
            "SELECT referral_code FROM user_id_security WHERE id = $1", uuid.UUID(user["user_id"])
        )
    summary = await app.state.referral_service.get_summary(user["user_id"])
    return {
        "referral_code": code,
        "referral_link": f"{FRONTEND_BASE_URL}/?ref={code}" if code else None,
        **summary,
    }


@app.get("/api/me/profile")
async def get_my_profile(session_id: Optional[str] = Cookie(None)):
    """One-stop payload for the profile page: account, credits, referral, recent history."""
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    uid = uuid.UUID(user["user_id"])
    async with postgres_db.pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT username, email, is_email_verified, tier, referral_code,
                   created_at, last_login_at, is_admin
            FROM user_id_security WHERE id = $1
            """,
            uid,
        )
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    wallet = await app.state.credits_service.get_wallet(user["user_id"])
    summary = await app.state.referral_service.get_summary(user["user_id"])
    history = await app.state.credits_service.history(user["user_id"], limit=15)
    code = row["referral_code"]

    return {
        "user": {
            "user_id": user["user_id"],
            "username": row["username"],
            "email": row["email"],
            "is_email_verified": row["is_email_verified"],
            "tier": row["tier"],
            "is_admin": row["is_admin"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "last_login_at": row["last_login_at"].isoformat() if row["last_login_at"] else None,
        },
        "credits": {
            "base": wallet["base_credits"],
            "boost": wallet["boost_credits"],
            "total": wallet["total"],
            "monthly_allotment": wallet["monthly_allotment"],
            "resets_on": wallet["resets_on"],
        },
        "referral": {
            "referral_code": code,
            "referral_link": f"{FRONTEND_BASE_URL}/?ref={code}" if code else None,
            **summary,
        },
        "history": history,
    }


@app.get("/api/me/activity")
async def get_my_activity(limit: int = 50, session_id: Optional[str] = Cookie(None)):
    """The caller's recent activity events (semantic actions: logins, screens, chats, ...)."""
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    events = await app.state.activity_service.recent(user["user_id"], limit=min(limit, 200))
    return {"events": events}


# ──────────────────────── Admin (tier toggle / credit grant) ────────────────────────

class AdminTierRequest(BaseModel):
    tier: str  # 'base' | 'premium'


class AdminGrantRequest(BaseModel):
    amount: int
    bucket: str = "boost"


async def require_admin(session_id: Optional[str]) -> dict:
    user = await get_current_user(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    async with postgres_db.pool.acquire() as conn:
        is_admin = await conn.fetchval(
            "SELECT is_admin FROM user_id_security WHERE id = $1", uuid.UUID(user["user_id"])
        )
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


@app.post("/api/admin/users/{user_id}/tier")
async def admin_set_tier(user_id: str, body: AdminTierRequest, session_id: Optional[str] = Cookie(None)):
    """Admin: switch a user's tier (applies the §2.6 credit + audit logic). Payment placeholder."""
    await require_admin(session_id)
    try:
        return await app.state.tier_service.set_tier(user_id, body.tier, reason="admin")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError:
        raise HTTPException(status_code=404, detail="User not found")


@app.post("/api/admin/users/{user_id}/credits")
async def admin_grant_credits(user_id: str, body: AdminGrantRequest, session_id: Optional[str] = Cookie(None)):
    """Admin: grant credits to a user (testing / goodwill)."""
    await require_admin(session_id)
    return await app.state.credits_service.grant(
        user_id, body.amount, action="admin_adjust", bucket=body.bucket
    )


@app.on_event("shutdown")
async def shutdown_event():
    lqs: LiveQuotesService = app.state.live_quotes_service
    await lqs.stop_all()


@app.get("/api/init/status")
async def get_init_status():
    return {"status": app.state.init_status}


@app.post("/api/init/run")
async def trigger_initialization(background_tasks: BackgroundTasks):
    if app.state.init_status == 'running':
        return {"status": "already_running"}
    app.state.init_status = 'running'
    background_tasks.add_task(_run_init_background)
    return {"status": "started", "message": "Initialization started in background"}


async def _run_init_background():
    try:
        result = await app.state.data_initializer.run()
        app.state.init_status = result.get('status', 'completed')
    except Exception as e:
        app.state.init_status = 'failed'
        print(f"Background initialization failed: {e}")


@app.post("/api/pipeline/nightly")
async def trigger_nightly_pipeline(background_tasks: BackgroundTasks):
    pipeline = app.state.nightly_pipeline
    background_tasks.add_task(pipeline.run_nightly_update)
    return {"status": "started", "message": "Full nightly pipeline (phase1+phase2) triggered in background"}

@app.post("/api/pipeline/phase1")
async def trigger_phase1(background_tasks: BackgroundTasks):
    pipeline = app.state.nightly_pipeline
    background_tasks.add_task(pipeline.run_phase1_kline)
    return {"status": "started", "message": "Phase 1 (K-line + indicators) triggered in background"}

@app.post("/api/pipeline/phase2")
async def trigger_phase2(background_tasks: BackgroundTasks):
    pipeline = app.state.nightly_pipeline
    background_tasks.add_task(pipeline.run_phase2_fundamentals)
    return {"status": "started", "message": "Phase 2 (Fundamentals + News) triggered in background"}


@app.get("/api/pipeline/history")
async def get_pipeline_history():
    from database import db as db_conn
    mongo_db = db_conn.mongodb_db if hasattr(db_conn, 'mongodb_db') else None
    if mongo_db is None:
        return []
    cursor = mongo_db['pipeline_runs'].find(
        {}, {'_id': 0}
    ).sort('started_at', -1).limit(20)
    return [doc async for doc in cursor]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)