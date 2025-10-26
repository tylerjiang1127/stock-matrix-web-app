# Stock Matrix - Project Documentation

**See Through The Market**

## 📋 Project Overview

Stock Matrix is a comprehensive stock research web application that provides real-time stock data visualization, technical analysis, and market insights. The application features interactive charts, multiple technical indicators, and a hybrid database architecture for optimal performance.

**Brand Identity**: Inspired by the Matrix movie, Stock Matrix helps traders and investors "see through" the market by revealing the underlying patterns and trends hidden in stock data.

## 🏗️ Architecture

### Frontend
- **Framework**: React.js
- **Charts**: Lightweight Charts library
- **Styling**: CSS3 with custom components
- **State Management**: React Hooks (useState, useEffect, useRef, useCallback)

### Backend
- **Framework**: FastAPI (Python)
- **Database Architecture**: Hybrid approach
  - **MongoDB**: Stock list, company overview, fundamental data
  - **PostgreSQL + TimescaleDB**: Technical indicators and OHLCV data
  - **Redis**: Real-time data caching
- **Data Source**: Alpha Vantage API
- **Technical Analysis**: TA-Lib library

### Infrastructure
- **Containerization**: Docker & Docker Compose
- **Database Management**: MongoDB, PostgreSQL, Redis containers
- **Environment**: Python virtual environment

## 📁 Project Structure

```
lazyman-stock-research-web-app/
├── frontend/                          # React frontend application
│   ├── src/
│   │   ├── components/
│   │   │   ├── StockChart.jsx         # Main chart component
│   │   │   ├── StockChart.css         # Chart styling
│   │   │   └── MatrixBackground.jsx   # Background animation
│   │   ├── App.js                     # Main app component
│   │   └── index.js                   # Entry point
│   ├── package.json                   # Frontend dependencies
│   └── public/                        # Static assets
├── backend/                           # FastAPI backend
│   ├── main.py                        # FastAPI app and API endpoints
│   ├── database_init.py               # Database initialization logic
│   ├── stock_metadata_fetcher.py      # Alpha Vantage data fetcher
│   ├── stock_list_manager.py          # Stock list management
│   ├── repositories.py                # MongoDB data access layer
│   ├── simple_postgres_models.py      # PostgreSQL data models
│   ├── postgres_data_retrieval.py     # PostgreSQL data retrieval
│   ├── postgres_database.py           # PostgreSQL connection
│   ├── redis_database.py              # Redis connection and caching
│   ├── models.py                      # Pydantic data models
│   ├── clean_database.py              # Database cleanup utility
│   ├── update_postgres_schema.py      # PostgreSQL schema updates
│   └── requirements.txt               # Python dependencies
├── docker/                            # Docker configuration
│   ├── mongo-init.js                  # MongoDB initialization
│   ├── postgres-init.sql              # PostgreSQL initialization
│   └── data/                          # Database data volumes
├── docker-compose.yml                 # Docker services configuration
└── data/                              # Historical data storage
```

## 🗄️ Database Schema

### MongoDB Collections

#### `stock_list`
- **Purpose**: Store stock symbols and basic information
- **Fields**:
  - `symbol`: Stock ticker symbol
  - `name`: Company name
  - `exchange`: Stock exchange
  - `market_cap`: Market capitalization
  - `create_date`: Record creation date
  - `update_date`: Last update date

#### `stock_metadata`
- **Purpose**: Store company overview and fundamental data
- **Fields**:
  - `symbol`: Stock ticker symbol
  - `company_overview`: Company information from Alpha Vantage
  - `fundamental_data`: Financial statements and ratios
  - `create_date`: Record creation date
  - `update_date`: Last update date

### PostgreSQL Tables

#### Technical Data Tables (by interval)
- `interval_1m_technical`, `interval_5m_technical`, `interval_15m_technical`
- `interval_30m_technical`, `interval_60m_technical`, `interval_1d_technical`
- `interval_1wk_technical`, `interval_1mo_technical`, `interval_3mo_technical`

**Common Fields**:
- `symbol`: Stock ticker symbol (Primary Key)
- `datetime_index`: Timestamp (Primary Key)
- `open`, `high`, `low`, `close`, `volume`: OHLCV data
- **Moving Averages**: `sma5`, `sma10`, `sma20`, `ema10`, `ema20`, etc.
- **Bollinger Bands**: `bbands_upper`, `bbands_lower`
- **MACD**: `macd`, `macd_signal`, `macd_hist`
- **RSI**: `rsi`
- **KDJ**: `k`, `d`, `j`
- **Candlestick Patterns**: Various pattern indicators

### Redis Cache
- **Purpose**: Real-time data caching
- **Structure**: Key-value pairs for quick data access
- **TTL**: Configurable expiration times

## 🚀 API Endpoints

### Database Management
- `POST /api/initialize-database?alpha_vantage_api_key={key}&max_stocks={n}`: Initialize complete database
- `POST /api/initialize-stock-list?alpha_vantage_api_key={key}`: Initialize stock list only
- `POST /api/initialize-stock-metadata?alpha_vantage_api_key={key}&max_stocks={n}`: Initialize metadata only

### Data Retrieval
- `GET /api/stocks`: Get all stock symbols
- `POST /api/stocks/{symbol}`: Get stock data for visualization
  - **Request Body**:
    ```json
    {
      "interval": "1d",
      "ma_options": ["sma"],
      "tech_ind": "macd"
    }
    ```

## 📊 Frontend Features

### Stock Chart Component (`StockChart.jsx`)

#### Chart Types
1. **Stock Price Chart**: Candlestick chart with moving averages and Bollinger Bands
2. **Volume Chart**: Histogram showing trading volume with color coding
3. **Technical Chart**: MACD, RSI, or KDJ indicators

#### Interactive Features
- **Crosshair Synchronization**: Mouse hover updates all three charts simultaneously
- **Legend Updates**: Real-time data display in legend areas
- **MA Line Highlighting**: Closest moving average line highlighting on hover
- **Dynamic Colors**: Volume bars and technical indicators with conditional coloring

#### Configuration Options
- **Intervals**: 1m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo, 3mo
- **Moving Averages**: SMA, EMA, WMA, DEMA, TEMA, KAMA
- **Technical Indicators**: MACD, RSI, KDJ
- **Stock Search**: Autocomplete with symbol and company name search

### Visual Enhancements
- **Matrix Background**: Animated background effect
- **Responsive Design**: Mobile-friendly layout
- **Custom Styling**: Professional chart appearance
- **Grid Lines**: Configurable chart grid display

## 🔧 Technical Implementation

### Data Flow
1. **Initialization**: Stock list fetched from NASDAQ, filtered by market cap
2. **Data Fetching**: Alpha Vantage API calls for each stock
3. **Processing**: Technical indicators calculated using TA-Lib
4. **Storage**: Data distributed across MongoDB, PostgreSQL, and Redis
5. **Retrieval**: Frontend requests data via FastAPI endpoints
6. **Visualization**: Lightweight Charts renders interactive charts

### Key Algorithms
- **Moving Average Calculation**: Multiple MA types with configurable periods
- **Technical Indicators**: MACD, RSI, KDJ with standard parameters
- **Bollinger Bands**: Upper and lower bands with middle band excluded
- **Volume Color Logic**: Green for positive, red for negative price movement

### Performance Optimizations
- **Async Processing**: Concurrent API calls and database operations
- **Memory Management**: Garbage collection and data cleanup
- **Caching Strategy**: Redis for frequently accessed data
- **Database Indexing**: Optimized queries with proper indexes

## 🐳 Docker Configuration

### Services
- **MongoDB**: Port 27017, persistent data volume
- **PostgreSQL**: Port 5432, TimescaleDB extension enabled
- **Redis**: Port 6379, persistent data volume

### Commands
```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Clean database
python clean_database.py
```

## 📦 Dependencies

### Backend (Python)
- `fastapi`: Web framework
- `uvicorn`: ASGI server
- `motor`: Async MongoDB driver
- `asyncpg`: Async PostgreSQL driver
- `aioredis`: Async Redis client
- `pandas`: Data manipulation
- `numpy`: Numerical computing
- `talib`: Technical analysis library
- `requests`: HTTP client
- `pydantic`: Data validation

### Frontend (Node.js)
- `react`: UI framework
- `lightweight-charts`: Charting library
- `axios`: HTTP client

## 🚦 Setup Instructions

### Prerequisites
- Docker and Docker Compose
- Python 3.9+
- Node.js 16+
- Alpha Vantage API key

### Backend Setup
```bash
cd backend
python -m venv myenv
source myenv/bin/activate  # On Windows: myenv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Frontend Setup
```bash
cd frontend
npm install
npm start
```

### Database Initialization
```bash
# Initialize with 5 stocks for testing
curl -X POST "http://localhost:8000/api/initialize-database?alpha_vantage_api_key=YOUR_API_KEY&max_stocks=5"
```

## 🔍 Current Status

### ✅ Completed Features
- Hybrid database architecture (MongoDB + PostgreSQL + Redis)
- Stock list management with market cap filtering
- Technical indicator calculation and storage
- Interactive chart visualization
- Cross-chart data synchronization
- Real-time legend updates
- Moving average highlighting
- Volume color coding
- Technical indicator display (MACD, RSI, KDJ)
- Bollinger Bands visualization
- Stock search with autocomplete
- Docker containerization
- Database initialization and cleanup utilities

### 🔄 Historical Fixes

#### Frontend Chart Issues (January 2025)

**Phase 1: Initial Chart Integration & Crosshair Issues**
- **Fixed `Cannot read properties of null (reading 'volume')` error** *(Jan 15, 2025)*: Added null checks for `crosshairData` before accessing properties
- **Fixed `Cannot read properties of null (reading 'technical')` error** *(Jan 15, 2025)*: Added null checks for technical data access
- **Fixed `Cannot read properties of undefined (reading 'SMA5')` error** *(Jan 15, 2025)*: Corrected data access path from `crosshairData.ma_values[name]` to `crosshairData.price.ma_values[name]`
- **Fixed legend data not updating on mouse move** *(Jan 15, 2025)*: Implemented centralized `updateAllChartsData` function for cross-chart synchronization

**Phase 2: Technical Chart & Legend Synchronization**
- **Fixed volume legend color always gray when hovering on volume chart** *(Jan 16, 2025)*: Corrected color property retrieval from `stockData.volume_data`
- **Fixed MACD Line and Signal Line not updating in technical chart legend** *(Jan 16, 2025)*: Implemented `technicalKeyMapping` to map series keys correctly
- **Fixed MACD Histogram not updating** *(Jan 16, 2025)*: Corrected `technicalKeyMapping` for histogram data

**Phase 3: MA Line Highlighting & Performance**
- **Fixed `priceScale.priceToCoordinate is not a function` error** *(Jan 17, 2025)*: Used `series.coordinateToPrice(param.point.y)` for pixel distance calculation
- **Fixed MA line highlight not displaying** *(Jan 17, 2025)*: Added `useEffect` with `highlightedMA` dependency for dynamic styling updates
- **Fixed MA line highlight staying after cursor leaves chart** *(Jan 17, 2025)*: Implemented `isMouseInChart` logic with proper boundary detection
- **Fixed highlighting process being extremely slow** *(Jan 17, 2025)*: Removed `highlightedMA` dependency from main chart initialization `useEffect`
- **Fixed highlight effect not following closest MA line rules** *(Jan 17, 2025)*: Corrected distance calculation logic and boundary detection

**Phase 4: Visual Enhancements & Styling**
- **Fixed volume legend showing "Volume" title and time** *(Jan 18, 2025)*: Removed title and time display from volume legend
- **Fixed Signal Line color mismatch in technical chart legend** *(Jan 18, 2025)*: Corrected color mapping for signal line
- **Fixed MACD Histogram color and style** *(Jan 18, 2025)*: Implemented dynamic green/red coloring with square shape
- **Fixed volume legend color logic** *(Jan 18, 2025)*: Ensured volume legend matches chart bar colors
- **Fixed Bollinger Bands filling area effect** *(Jan 18, 2025)*: Removed area filling and set dotted line style
- **Fixed Y-axis price/volume tags for most recent data points** *(Jan 18, 2025)*: Set `lastValueVisible: false` for candlestick and volume series
- **Fixed grid lines display** *(Jan 18, 2025)*: Set `vertLines: { visible: false }` and `horzLines: { visible: false }`
- **Fixed close price highlighting** *(Jan 18, 2025)*: Added bold text and colored border matching candlestick color
- **Fixed legend numbers not disappearing when cursor leaves charts** *(Jan 18, 2025)*: Added proper visibility logic
- **Fixed volume legend still showing numbers when cursor is out** *(Jan 18, 2025)*: Corrected volume legend visibility logic

#### Backend Database Issues (January 2025)

**Phase 1: Initial Setup & Import Issues**
- **Fixed `ImportError: attempted relative import with no known parent package`** *(Jan 19, 2025)*: Changed all relative imports to absolute imports
- **Fixed `{"detail":"Not Found"}` error** *(Jan 19, 2025)*: Corrected API endpoint configuration
- **Fixed `Field required` error for `alpha_vantage_api_key`** *(Jan 19, 2025)*: Modified FastAPI endpoint to accept query parameters correctly
- **Fixed `{"message":"Database initialization failed","status":"error"}`** *(Jan 19, 2025)*: Resolved import errors and API configuration issues

**Phase 2: MongoDB Serialization Issues**
- **Fixed `documents must have only string keys, key was Timestamp`** *(Jan 20, 2025)*: Modified `_process_technical_data` to convert DataFrame indices to strings
- **Fixed `cannot encode object: array([...]), of type: <class 'numpy.ndarray'>`** *(Jan 20, 2025)*: Added `convert_to_serializable` helper to convert NumPy arrays to Python lists
- **Fixed `IndentationError: unindent does not match any outer indentation level`** *(Jan 20, 2025)*: Corrected indentation in `stock_metadata_fetcher.py`
- **Fixed `cannot encode object: ... of type: <class 'pandas.core.frame.DataFrame'>`** *(Jan 20, 2025)*: Added DataFrame serialization handling in `_process_technical_data`
- **Fixed `'update' command document too large`** *(Jan 20, 2025)*: Implemented hybrid database solution (MongoDB + PostgreSQL + Redis)

**Phase 3: Database Integration & Compatibility**
- **Fixed `ImportError: cannot import name '_QUERY_OPTIONS' from 'pymongo.cursor'`** *(Jan 21, 2025)*: Updated `requirements.txt` with compatible versions (`motor==3.3.2`, `pymongo==4.6.0`)
- **Fixed `'dict' object has no attribute 'empty'` (PostgreSQL)** *(Jan 21, 2025)*: Corrected DataFrame access in `postgres_models.py`
- **Fixed `Object of type DataFrame is not JSON serializable` (Redis)** *(Jan 21, 2025)*: Added `_convert_to_serializable` method to handle DataFrames and Series
- **Fixed `Object of type Timestamp is not JSON serializable` (Redis)** *(Jan 21, 2025)*: Added Pandas Timestamp serialization
- **Fixed `The truth value of a DataFrame is ambiguous` (PostgreSQL)** *(Jan 21, 2025)*: Changed conditional checks to explicit DataFrame validation

**Phase 4: PostgreSQL & Data Storage**
- **Fixed `AttributeError: 'PostgreSQLDatabase' object has no attribute 'conn'`** *(Jan 22, 2025)*: Corrected asyncpg connection pool access
- **Fixed `asyncpg.exceptions.DataError: invalid input for query argument`** *(Jan 22, 2025)*: Added `idx.tz_localize('UTC')` for timezone-aware timestamps
- **Fixed `Object of type int64 is not JSON serializable` (PostgreSQL)** *(Jan 22, 2025)*: Added NumPy type conversion in `_convert_to_serializable`
- **Fixed OHLCV data not storing in PostgreSQL** *(Jan 22, 2025)*: Corrected column name access (capitalized vs lowercase)
- **Fixed Moving Average data not storing in PostgreSQL** *(Jan 22, 2025)*: Corrected column name construction for MA data

**Phase 5: Database Management & Authentication**
- **Fixed `MongoServerError[Unauthorized]: Command find requires authentication`** *(Jan 23, 2025)*: Provided correct MongoDB connection commands with credentials
- **Fixed MongoDB containing technical data** *(Jan 23, 2025)*: Clarified data routing and provided cleanup commands
- **Fixed `Field required` error for `alpha_vantage_api_key`** *(Jan 23, 2025)*: Corrected curl command to use query parameters
- **Fixed `clean_database.py` errors** *(Jan 23, 2025)*: Corrected MongoDB collection access and Redis method calls

**Phase 6: Frontend-Backend Integration**
- **Fixed Frontend "Error not found" and 404 Not Found** *(Jan 24, 2025)*: Created `DatabaseStockRequest` model to avoid field conflicts
- **Fixed MA lines/BBands not visible, Volume grey, Technical charts empty** *(Jan 24, 2025)*: Updated `postgres_data_retrieval.py` data formatting
- **Fixed MA lines not cleaning, MA legend not showing, Technical legend showing all** *(Jan 24, 2025)*: Implemented proper series cleanup and conditional legend rendering
- **Fixed stock price chart blank with legend updating** *(Jan 24, 2025)*: Reverted time format to Unix timestamp and fixed MA periods mismatch
- **Fixed `TypeError: priceChart.current.series is not a function`** *(Jan 24, 2025)*: Added validation checks before calling `series()` method
- **Fixed `Failed to sync chart X: Error: Value is null`** *(Jan 24, 2025)*: Added timeScale and setVisibleRange validity checks
- **Fixed Bollinger Bands not showing** *(Jan 24, 2025)*: Removed `bbands_middle` and corrected column name access
- **Fixed Moving Average lines data missing** *(Jan 24, 2025)*: Updated MA periods to match `StockMetaDataFetcher` definitions
- **Fixed `max_stocks` parameter not being respected** *(Jan 25, 2025)*: Corrected `StockListManager` to filter NaN market caps before limiting

#### Docker and Infrastructure Issues (January 2025)

**Phase 1: Docker Setup & Configuration**
- **Fixed `zsh: command not found: docker-compose`** *(Jan 19, 2025)*: Provided Docker Desktop installation instructions
- **Fixed `docker-compose.yml: the attribute 'version' is obsolete` warning** *(Jan 19, 2025)*: Removed obsolete version attribute
- **Fixed Docker Compose output interpretation** *(Jan 19, 2025)*: Explained container creation and warning messages

**Phase 2: Database Initialization**
- **Fixed database initialization commands** *(Jan 20, 2025)*: Provided correct curl commands with proper parameters

### 🎯 Known Issues
- None currently identified

### 🔧 Key Technical Concepts Implemented

#### Frontend Architecture
- **React Hooks**: `useState`, `useEffect`, `useRef`, `useCallback` for state management and performance optimization
- **Lightweight Charts Integration**: `createChart`, `subscribeCrosshairMove`, `addLineSeries`, `addHistogramSeries`, `addAreaSeries`
- **Crosshair Event Handling**: Real-time data synchronization across multiple charts
- **Conditional Rendering**: Dynamic JSX based on data availability and user interactions
- **Performance Optimization**: Debouncing, `series.applyOptions` vs. re-creating series, optimized `useEffect` dependencies

#### Backend Architecture
- **FastAPI Framework**: Async web framework with automatic API documentation
- **Hybrid Database Design**: MongoDB for documents, PostgreSQL for time-series, Redis for caching
- **Async Programming**: `asyncio`, `aiohttp`, `await`, `asyncio.gather` for concurrent operations
- **Data Validation**: Pydantic models with V2 compatibility (`BaseModel`, `Field`, `Config`)
- **Database ORM**: SQLAlchemy with Alembic for PostgreSQL migrations
- **Connection Pooling**: Asyncpg for PostgreSQL, Motor for MongoDB, Aioredis for Redis

#### Data Processing
- **Pandas Integration**: DataFrame manipulation, timezone handling, data cleaning
- **Technical Analysis**: TA-Lib library for moving averages, MACD, RSI, KDJ calculations
- **Data Serialization**: Custom converters for NumPy arrays, Pandas DataFrames, and Timestamps
- **Memory Management**: Garbage collection and data cleanup strategies

#### Problem-Solving Approaches
- **Iterative Debugging**: Systematic identification and resolution of issues
- **Cross-Chart Synchronization**: Centralized data collection and distribution
- **Performance Optimization**: Reducing re-renders and optimizing chart operations
- **Error Handling**: Comprehensive try-catch blocks with detailed error messages
- **Data Validation**: Input sanitization and type checking throughout the pipeline

## 📝 Development Notes

### Code Quality
- Comprehensive error handling
- Async/await patterns throughout
- Type hints and Pydantic models
- Modular architecture with clear separation of concerns

### Testing
- Manual testing with limited stock sets
- Database initialization validation
- API endpoint verification
- Frontend chart functionality testing

### Future Enhancements
- Automated testing suite
- Performance monitoring
- Additional technical indicators
- Portfolio management features
- Real-time data streaming
- Advanced charting options

---

**Last Updated**: January 2025
**Version**: 1.0.0
**Maintainer**: Development Team
