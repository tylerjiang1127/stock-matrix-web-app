# Stock Matrix - Complete Project Documentation

**See Through The Market**

## 📋 Project Overview

Stock Matrix is a professional stock research web application that provides real-time stock data visualization, technical analysis, fundamental metrics, news sentiment analysis, and user authentication. The application features interactive charts, multiple technical indicators, news sentiment gauges, and a hybrid database architecture for optimal performance.

**Brand Identity**: Inspired by the Matrix movie, Stock Matrix helps traders and investors "see through" the market by revealing the underlying patterns and trends hidden in stock data.

### Technology Stack

**Frontend:**
- React.js (UI Framework)
- Lightweight Charts (TradingView-based charting)
- Axios (HTTP Client)
- CSS3 with custom components

**Backend:**
- FastAPI (Python)
- Alpha Vantage API (Market Data)
- TA-Lib (Technical Analysis)
- SendGrid (Email Service)

**Databases:**
- **PostgreSQL + TimescaleDB**: Stock technical data (OHLCV + indicators)
- **MongoDB**: Stock fundamental data (financial statements)
- **Redis**: Caching and session management

**Infrastructure:**
- Docker & Docker Compose
- Python virtual environment
- Node.js runtime

---

## 🏗️ Architecture

### Database Strategy

#### **PostgreSQL (Technical Data)**
- **Purpose**: Time-series stock price data and technical indicators
- **Structure**: Interval-specific tables with optimized MA periods
- **Tables**: `interval_1m_technical`, `interval_5m_technical`, ..., `interval_1mo_technical`
- **Storage**: Each interval has custom MA periods (e.g., 30m uses [3,6,12,18,36,72])

#### **MongoDB (Fundamental Data)**
- **Purpose**: Company overview and financial statements
- **Collections**: `stock_metadata`, `stock_list`
- **Caching**: 3-month expiry, on-demand fetching

#### **Redis (Session & Cache)**
- **Purpose**: User sessions and UI interaction caching
- **Strategy**: Lazy loading, on-demand only

---

## 📁 Project Structure

```
lazyman-stock-research-web-app/
├── frontend/                           # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── StockChart.jsx          # Main chart component
│   │   │   ├── StockChart.css          # Chart styling
│   │   │   ├── MatrixBackground.jsx    # Background animation
│   │   │   └── Auth/                   # Authentication components
│   │   │       ├── RegisterModal.jsx
│   │   │       ├── LoginModal.jsx
│   │   │       ├── ForgotPasswordModal.jsx
│   │   │       ├── ResetPasswordPage.jsx
│   │   │       ├── VerifyEmailPage.jsx
│   │   │       ├── UserMenu.jsx
│   │   │       └── Auth.css
│   │   ├── contexts/
│   │   │   └── AuthContext.js          # Global auth state
│   │   ├── App.js                      # Main app with routing
│   │   └── index.js
│   └── package.json
├── backend/                            # FastAPI backend
│   ├── main.py                         # FastAPI app & API endpoints
│   ├── stock_metadata_fetcher.py       # Alpha Vantage data fetcher
│   ├── database_init.py                # Database initialization
│   ├── stock_list_manager.py           # Stock list management
│   ├── repositories.py                 # MongoDB data access
│   ├── simple_postgres_models.py       # PostgreSQL models
│   ├── postgres_data_retrieval.py      # PostgreSQL queries
│   ├── postgres_database.py            # PostgreSQL connection
│   ├── redis_database.py               # Redis & session management
│   ├── postgres_models.py              # User authentication models
│   ├── auth_utils.py                   # Password hashing, tokens
│   ├── email_service.py                # SendGrid email service
│   ├── auth_routes.py                  # Auth API endpoints
│   ├── models.py                       # Pydantic data models
│   └── requirements.txt
├── docker/
│   ├── mongo-init.js                   # MongoDB initialization
│   ├── postgres-init.sql               # PostgreSQL schema (auto-generated)
│   └── data/                           # Database volumes
├── docker-compose.yml                  # Docker services
├── generate_postgres_schema.py         # Auto-generate PostgreSQL schema
├── clear_stock_data_only.sh            # Clear stock technical data
├── clear_user_data_only.sh             # Clear user authentication data
├── clear_mongodb_fundamental_only.sh   # Clear fundamental data
└── README.md
```

---

## 🗄️ Database Schema

### PostgreSQL Tables

#### **Technical Data Tables (Interval-Specific)**

Each interval has its own optimized MA periods:

- `interval_1m_technical`: MA periods [5, 10, 20, 30, 60, 120]
- `interval_5m_technical`: MA periods [6, 12, 24, 36, 72, 144]
- `interval_15m_technical`: MA periods [4, 8, 16, 24, 48, 96]
- `interval_30m_technical`: MA periods [3, 6, 12, 18, 36, 72]
- `interval_60m_technical`: MA periods [3, 5, 8, 13, 21, 34] (Fibonacci)
- `interval_1d_technical`: MA periods [5, 10, 20, 30, 60, 120, 250]
- `interval_1wk_technical`: MA periods [5, 10, 20, 30, 60]
- `interval_1mo_technical`: MA periods [3, 5, 10, 12, 24, 36]

**Common Fields:**
- Primary Key: `(symbol, datetime_index)`
- OHLCV: `open`, `high`, `low`, `close`, `volume`
- Moving Averages: `sma{period}`, `ema{period}`, `wma{period}`, `dema{period}`, `tema{period}`, `kama{period}`
- Bollinger Bands: `bbands_upper`, `bbands_lower`
- MACD: `macd`, `macd_signal`, `macd_hist`
- RSI: `rsi`
- KDJ: `k`, `d`, `j`
- Candlestick Patterns: `candlestick_patterns` (JSONB)

#### **User Authentication Tables**

- `user_id_security`: User accounts
  - `id` (UUID), `email`, `username`, `password_hash`
  - `is_email_verified`, `status`, `created_at`, `updated_at`

- `email_verification_tokens`: Email verification
  - `token`, `user_id`, `expires_at`, `used`

- `password_reset_tokens`: Password reset
  - `token`, `user_id`, `expires_at`, `used`

### MongoDB Collections

- `stock_metadata`: Company overview, financial statements
  - `symbol`, `company_overview`, `stock_fundamental`
  - Cached with 3-month expiry

- `stock_list`: Stock symbols with market cap filtering

---

## 🚀 API Endpoints

### Database Management
- `POST /api/initialize-database`: Initialize complete database
- `POST /api/initialize-stock-list`: Initialize stock list only

### Stock Data
- `GET /api/stocks`: Get all stock symbols
- `POST /api/stocks/{symbol}`: Get stock data for visualization
  - Request body: `{"interval": "1d", "ma_options": ["sma"], "tech_ind": "macd"}`
- `GET /api/stocks/{symbol}/company-overview`: Get company overview (on-demand)
- `GET /api/stocks/{symbol}/fundamental-data`: Get financial statements (on-demand)
- `GET /api/stocks/{symbol}/news-sentiment`: Get news sentiment analysis

### Authentication
- `POST /api/auth/register`: User registration
- `POST /api/auth/login`: User login
- `POST /api/auth/logout`: User logout
- `GET /api/auth/verify-email`: Email verification
- `POST /api/auth/resend-verification`: Resend verification email
- `POST /api/auth/forgot-password`: Request password reset
- `POST /api/auth/reset-password`: Reset password
- `GET /api/auth/me`: Get current user info

---

## 📊 Frontend Features

### Stock Chart Component

#### **Company Overview Dashboard**
- **Layout**: Horizontal sections (OVERVIEW, VALUATION, FINANCIALS, PRICE STATS, ABOUT)
- **Rich Metrics**: PE, Forward PE, PEG, Margins, ROE, Beta, Analyst Targets, etc.
- **Smart Formatting**: Distinguishes between zero values and missing data

#### **Interactive Charts**
1. **Stock Price Chart**: Candlestick + Moving Averages + Bollinger Bands
2. **Volume Chart**: Color-coded histogram (green/red)
3. **Technical Indicator Chart**: MACD, RSI, or KDJ

#### **Chart Features**
- Crosshair synchronization across all charts
- Real-time legend updates
- MA line highlighting on hover
- Dynamic period selection (1m, 5m, 15m, 30m, 60m, 1d, 1wk, 1mo)
- Multiple MA types (SMA, EMA, WMA, DEMA, TEMA, KAMA)
- Lightweight Charts attribution

#### **Fundamental Data Section**
- Loading effect
- Right-aligned legends
- Quarterly/Yearly toggle
- Trend charts: Profitability, Debt-Asset Ratio, Cash Flow

#### **News & Sentiment Analysis**
- Gauge view showing average sentiment score (-1 to 1)
- Weighted by relevance score
- Last 24 hours of ticker-related news
- News list with title, image, datetime, relevance percentage

#### **Monitoring List (Sticky)**
- Left column sticky card (content TBD)

### Authentication Features

#### **Registration**
- Email, username, password validation
- Password strength requirements (8-50 chars, uppercase, lowercase, number)
- Email verification required
- SendGrid welcome email
- Real-time password visibility toggle

#### **Login**
- Email & password authentication
- Automatic verification email resend for unverified users
- Session management with HTTP-only cookies
- Remember me functionality

#### **Email Verification**
- Permanent verification tokens (10-year expiry)
- Automatic login after verification
- 3-second countdown with manual redirect option
- React Strict Mode compatible (useRef to prevent double execution)

#### **Password Reset**
- Forgot password flow
- Token-based reset link
- Client-side password strength validation
- Real-time password matching feedback
- Automatic login after successful reset
- Detailed error messages

---

## 🔧 Technical Implementation

### MA Periods Configuration (Code-Driven Schema)

**Philosophy**: Each time interval requires different MA periods optimized for that trading timeframe.

**Implementation**:
1. Define MA periods in `backend/stock_metadata_fetcher.py`
2. Auto-generate PostgreSQL schema using `generate_postgres_schema.py`
3. Database structure adapts to code configuration

**Example**:
```python
# 30-minute interval uses shorter MAs
'30m': {'ma_period': [3, 6, 12, 18, 36, 72]}

# Daily interval uses classic + long-term MAs  
'1d': {'ma_period': [5, 10, 20, 30, 60, 120, 250]}
```

### Authentication System

#### **Password Security**
- `passlib[bcrypt]` for password hashing
- `bcrypt==4.1.2` for compatibility
- Password strength validation: 8-50 chars, mixed case, numbers

#### **Token Management**
- `python-jose[cryptography]` for JWT tokens
- Verification tokens: 10-year expiry (effectively permanent)
- Password reset tokens: 24-hour expiry
- Tokens marked as "used" after successful action

#### **Session Management**
- HTTP-only cookies for session IDs
- Redis-based session storage
- Automatic cleanup on password change
- 7-day expiry (configurable)

#### **Email Service**
- SendGrid API integration
- Welcome emails, verification emails, password reset emails
- HTML templates with professional styling
- DMARC-compliant sender configuration

### Data Flow

```
User Request
    ↓
Frontend (React)
    ↓
FastAPI Backend
    ↓
    ├─> Alpha Vantage API (fetch data)
    ├─> TA-Lib (calculate indicators)
    ├─> PostgreSQL (store technical data)
    ├─> MongoDB (store fundamental data)
    └─> Redis (cache & sessions)
    ↓
Response to Frontend
    ↓
Lightweight Charts (visualization)
```

### Performance Optimizations

- **Async Processing**: Concurrent API calls and database operations
- **Pipeline Architecture**: Producer-Consumer pattern for API fetching and DB insertion
- **Parallel Database Writes**: Simultaneous saves to MongoDB and PostgreSQL
- **Data Filtering**: Reduced data for intraday intervals, full history for daily+
- **Caching Strategy**: Redis for frequently accessed data
- **Chunked Insertions**: Split large datasets (500 records/chunk) with timeout protection
- **Rate Limiting**: 6 stocks/batch with 60-second intervals

---

## 🐳 Docker Configuration

### Services

```yaml
services:
  mongodb:
    image: mongo:latest
    ports: ["27017:27017"]
    volumes: [./docker/data/mongodb:/data/db]
    
  postgresql:
    image: timescale/timescaledb:latest-pg14
    ports: ["5432:5432"]
    volumes: [./docker/data/postgresql:/var/lib/postgresql/data]
    
  redis:
    image: redis:alpine
    ports: ["6379:6379"]
    volumes: [./docker/data/redis:/data]
```

### Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Clear specific data
./clear_stock_data_only.sh
./clear_user_data_only.sh
./clear_mongodb_fundamental_only.sh
```

---

## 📦 Dependencies

### Backend (Python)

**Core:**
- `fastapi`, `uvicorn` - Web framework
- `motor` - Async MongoDB driver
- `asyncpg` - Async PostgreSQL driver
- `redis` - Redis client
- `pandas`, `numpy` - Data manipulation
- `talib` - Technical analysis

**Authentication:**
- `passlib[bcrypt]==1.7.4` - Password hashing
- `bcrypt==4.1.2` - Cryptography backend
- `python-jose[cryptography]==3.3.0` - JWT tokens
- `email-validator==2.1.0` - Email validation
- `sendgrid==6.11.0` - Email service

**Other:**
- `requests` - HTTP client
- `pydantic` - Data validation

### Frontend (Node.js)

- `react` - UI framework
- `react-router-dom` - Routing
- `lightweight-charts` - Charting library
- `axios` - HTTP client

---

## 🚦 Setup Instructions

### Prerequisites

- Docker and Docker Compose
- Python 3.9+
- Node.js 16+
- Alpha Vantage API key
- SendGrid API key (for email features)

### Environment Variables

Create `backend/.env`:

```env
# Alpha Vantage
ALPHA_VANTAGE_API_KEY=your_key_here

# SendGrid
SENDGRID_API_KEY=SG.xxxxx
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
SENDGRID_FROM_NAME=Stock Matrix

# URLs
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000

# Session
SESSION_SECRET=your_secret_key
SESSION_EXPIRE_DAYS=7

# Database
MONGODB_URL=mongodb://admin:password123@localhost:27017/stock_data?authSource=admin
REDIS_URL=redis://localhost:6379/0
POSTGRES_URL=postgresql://admin:password123@localhost:5432/postgres
```

### Backend Setup

```bash
cd backend
python -m venv myenv
source myenv/bin/activate  # Windows: myenv\Scripts\activate
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
# Start Docker services
docker-compose up -d

# Wait for services to start
sleep 10

# Initialize database
curl -X POST "http://localhost:8000/api/initialize-database" \
     -H "Content-Type: application/json" \
     -d '{
       "alpha_vantage_api_key": "YOUR_API_KEY",
       "max_stocks": 12,
       "batch_size": 6
     }'
```

---

## 🔄 Database Management

### Safe Cleanup Scripts

**1. Clear Stock Technical Data Only**
```bash
./clear_stock_data_only.sh
# Preserves: User data + Fundamental data
# Use case: Daily data refresh
```

**2. Clear User Authentication Data Only**
```bash
./clear_user_data_only.sh
# Preserves: Stock data + Fundamental data
# Use case: Clear test accounts
```

**3. Clear MongoDB Fundamental Data Only**
```bash
./clear_mongodb_fundamental_only.sh
# Preserves: Stock data + User data
# Use case: Refresh company data
```

### Updating MA Periods Configuration

```bash
# 1. Edit MA periods in backend/stock_metadata_fetcher.py
# 2. Update MA_PERIODS_CONFIG in generate_postgres_schema.py
# 3. Generate new schema
python3 generate_postgres_schema.py

# 4. Reset PostgreSQL manually
docker-compose stop postgresql
docker-compose rm -f postgresql
rm -rf ./docker/data/postgresql
docker-compose up -d postgresql
sleep 15

# 5. Re-initialize data
curl -X POST "http://localhost:8000/api/initialize-database" ...
```

---

## 🔍 Feature History

### ✅ Completed Features

#### **Core Functionality**
- [x] Hybrid database architecture (MongoDB + PostgreSQL + Redis)
- [x] Stock list management with market cap filtering
- [x] Technical indicator calculation and storage
- [x] Interactive chart visualization
- [x] Cross-chart data synchronization
- [x] Real-time legend updates
- [x] Moving average highlighting
- [x] Volume color coding
- [x] Bollinger Bands visualization
- [x] Stock search with autocomplete
- [x] Docker containerization

#### **Frontend Enhancements**
- [x] Professional company overview dashboard (4-column grid)
- [x] Fundamental data section with trend charts
- [x] News & sentiment analysis with gauge view
- [x] Monitoring list (sticky, left column)
- [x] Matrix-themed background animation
- [x] Lightweight Charts attribution
- [x] Period selection (1m to 1mo)
- [x] Multiple MA types (SMA, EMA, WMA, DEMA, TEMA, KAMA)
- [x] Technical indicators (MACD, RSI, KDJ)

#### **Authentication System**
- [x] User registration with email verification
- [x] Login with session management
- [x] Password reset flow
- [x] Automatic login after verification
- [x] Automatic login after password reset
- [x] Password visibility toggle
- [x] Password strength validation
- [x] SendGrid email integration
- [x] React Strict Mode compatibility

#### **Data Management**
- [x] On-demand fundamental data fetching
- [x] Interval-specific MA periods
- [x] Auto-generated PostgreSQL schema
- [x] Safe cleanup scripts (3 granular scripts)
- [x] Weighted sentiment analysis

---

## 🐛 Bug Fixes & Improvements

### Phase 1: Initial Chart Integration (Jan 15, 2025)

**Fixed Issues:**
- `Cannot read properties of null (reading 'volume')` - Added null checks for crosshairData
- `Cannot read properties of null (reading 'technical')` - Added null checks for technical data
- `Cannot read properties of undefined (reading 'SMA5')` - Corrected data access path
- Legend data not updating on mouse move - Implemented centralized `updateAllChartsData`

### Phase 2: Technical Chart & Legend (Jan 16, 2025)

**Fixed Issues:**
- Volume legend color always gray - Corrected color property retrieval
- MACD Line and Signal not updating - Implemented `technicalKeyMapping`
- MACD Histogram not updating - Corrected mapping for histogram data

### Phase 3: MA Line Highlighting (Jan 17, 2025)

**Fixed Issues:**
- `priceScale.priceToCoordinate is not a function` - Used `series.coordinateToPrice`
- MA highlight not displaying - Added `useEffect` with `highlightedMA` dependency
- Highlight staying after cursor leaves - Implemented `isMouseInChart` logic
- Slow highlighting process - Removed `highlightedMA` dependency from chart init
- Incorrect closest MA detection - Fixed distance calculation and boundaries

### Phase 4: Visual Enhancements (Jan 18, 2025)

**Fixed Issues:**
- Volume legend showing title and time - Removed unnecessary display
- Signal Line color mismatch - Corrected color mapping
- MACD Histogram style - Dynamic green/red with square shape
- Bollinger Bands filling area - Removed fill, set dotted style
- Y-axis price tags - Set `lastValueVisible: false`
- Grid lines display - Hidden vertical and horizontal grid lines
- Close price highlighting - Added bold text and colored border
- Legend visibility when cursor out - Added proper hide logic

### Phase 5: Backend Integration (Jan 19-25, 2025)

**Fixed Issues:**
- `ImportError: attempted relative import` - Changed to absolute imports
- `{"detail":"Not Found"}` error - Corrected API endpoint configuration
- `Field required` for API key - Modified endpoint to accept query parameters
- MongoDB serialization errors - Added `convert_to_serializable` helper
- `'update' command document too large` - Implemented hybrid database solution
- `ImportError: cannot import '_QUERY_OPTIONS'` - Updated motor/pymongo versions
- PostgreSQL timezone issues - Added `tz_localize('UTC')`
- OHLCV and MA data storage issues - Corrected column name access

### Phase 6: Database Management (Jan 23, 2025)

**Fixed Issues:**
- `MongoServerError[Unauthorized]` - Provided correct MongoDB credentials
- MongoDB containing technical data - Clarified data routing
- `clean_database.py` errors - Fixed collection access and method calls

### Phase 7: API & Compatibility (Nov 7, 2025)

**Fixed Issues:**
- `module 'pandas' has no attribute 'isinf'` - Changed to `np.isinf()`
- BRK/A and BRK/B API failures - Added symbol cleaning ('/' to '.')
- API endpoint parameter mismatch - Created `DatabaseInitRequest` model
- Implemented async batch processing with rate limiting (6 stocks/minute)

### Phase 8: Performance & Timeout (Nov 7-8, 2025)

**Fixed Issues:**
- BRK.A/BRK.B "Invalid API call" for intraday - Graceful handling of unsupported intervals
- PostgreSQL timeout on large datasets - Chunked insertion (500 records/chunk)
- `'Close'` KeyError on empty DataFrames - Added validation before indicator calculation
- Slow database saves - Parallel writes using `asyncio.gather` (9x speedup)
- Data filtering bug - Fixed to return filtered data (95% size reduction)

### Phase 9: Pipeline Architecture (Nov 12, 2025)

**Improvements:**
- Implemented Producer-Consumer pattern - API and DB operations now parallel
- Separated fetching and saving - Independent workers for better resource utilization
- 30-40% total time reduction - API batches complete while DB worker processes queue

### Phase 10: Professional Enhancements (Dec 11, 2025)

**Improvements:**
- Comprehensive API rate limit handling - Intelligent retry logic for burst/daily limits
- Critical data filtering fix - Properly returns filtered data for intraday intervals
- On-demand fundamental strategy - Company overview and financials fetched on-demand
- Professional financial metrics - Bloomberg-lite style dashboard with rich data

### Phase 11: Authentication System (Jan 2026)

**Fixed Issues:**
- `ModuleNotFoundError: No module named 'passlib'` - Installed dependencies in venv
- Generic "Registration failed" - Added detailed validation messages
- "password cannot be longer than 72 bytes" - Downgraded bcrypt to 4.1.2
- No verification email (401 Unauthorized) - Fixed SendGrid API key configuration
- DMARC alignment error - Changed from Gmail sender to domain-specific sender
- Verification token expired after 7 hours - Set tokens to 10-year expiry
- "Token has been used" error - Fixed React Strict Mode double execution with `useRef`
- User not auto-logged after verification - Added `withCredentials: true` to axios
- Password reset generic errors - Enhanced error handling with specific messages
- "can't compare offset-naive and offset-aware datetimes" - Fixed timezone comparison

**Improvements:**
- Automatic login after email verification - Sets session cookie, redirects after 3s
- Automatic login after password reset - Creates session, redirects automatically
- Password visibility toggle - SVG eye icons for show/hide
- Password strength hints - Display requirements in registration/reset modals
- Unverified login detection - Automatically resends verification email

### Phase 12: Database Schema Optimization (Jan 17, 2026)

**Fixed Issues:**
- `column "sma3" does not exist` - PostgreSQL schema didn't match code MA periods
- `column "sma30" does not exist` - Database used generic columns for all intervals

**Solution:**
- Created `generate_postgres_schema.py` to auto-generate interval-specific schemas
- Each interval now has its own optimized MA periods
- Database structure adapts to code configuration (code-driven schema)

**Improvements:**
- Interval-specific MA periods for professional trading analysis
- Automated schema generation from code configuration
- Safe cleanup scripts (3 granular scripts replacing dangerous reset script)
- Comprehensive database management documentation

### MongoDB Authentication (Jan 17, 2026)

**Fixed Issues:**
- `Command delete requires authentication` - Updated MONGODB_URL with credentials
- `ValueError: invalid literal for int()` - Fixed `.env` file formatting issue

---

## 🎯 Known Issues

- None currently identified

---

## 📚 Key Technical Concepts

### Frontend Architecture
- React Hooks: `useState`, `useEffect`, `useRef`, `useCallback`, `useMemo`
- Lightweight Charts Integration: `createChart`, `subscribeCrosshairMove`
- Crosshair Event Handling: Real-time synchronization
- Conditional Rendering: Dynamic JSX based on data availability
- Performance Optimization: Debouncing, optimized dependencies

### Backend Architecture
- FastAPI: Async web framework with automatic API documentation
- Hybrid Database Design: MongoDB for documents, PostgreSQL for time-series, Redis for caching
- Async Programming: `asyncio`, `aiohttp`, `asyncio.gather`
- Producer-Consumer Pattern: `asyncio.Queue` for decoupled operations
- Pipeline Architecture: Independent workers for optimal resource utilization
- Data Validation: Pydantic models with V2 compatibility

### Data Processing
- Pandas Integration: DataFrame manipulation, timezone handling
- Technical Analysis: TA-Lib for indicators
- Data Serialization: Custom converters for NumPy/Pandas types
- Memory Management: Garbage collection strategies

### Security
- Password Hashing: bcrypt with passlib
- Token Management: JWT with python-jose
- Session Management: HTTP-only cookies with Redis
- Email Verification: Permanent tokens with used flag
- CSRF Protection: SameSite cookie attributes

---

## 🔮 Future Enhancements

- Automated testing suite
- Real-time data streaming (WebSocket)
- Portfolio management features
- Advanced charting options (more indicators)
- Mobile responsive design
- Multi-language support
- Dark mode toggle
- Customizable dashboard layouts
- Alerts and notifications
- Social features (share insights)

---

## 📝 Development Notes

### Code Quality
- Comprehensive error handling
- Async/await patterns throughout
- Type hints and Pydantic models
- Modular architecture with clear separation of concerns
- Detailed logging for debugging

### Testing
- Manual testing with limited stock sets
- Database initialization validation
- API endpoint verification
- Frontend chart functionality testing
- Authentication flow testing

### Documentation
- Inline code comments
- API endpoint documentation (FastAPI auto-docs)
- Database schema documentation
- Setup guides for authentication
- Troubleshooting guides for common issues

---

**Last Updated**: January 18, 2026  
**Version**: 2.0.0  
**Maintainer**: Development Team

---

## 🙏 Acknowledgments

- **Alpha Vantage** for comprehensive market data API
- **TradingView** for Lightweight Charts library
- **SendGrid** for reliable email delivery
- **TimescaleDB** for time-series database optimization
- **FastAPI** for modern Python web framework
- **React** for powerful frontend framework

---

*Stock Matrix - Professional Stock Research Platform*
