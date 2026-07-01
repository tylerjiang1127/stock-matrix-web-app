# Stock Matrix — Complete Project Documentation

**See Through The Market**

## Project Overview

Stock Matrix is a professional AI-powered stock research platform that provides real-time market data visualization, technical analysis, fundamental metrics, news sentiment analysis, and AI-driven market intelligence. Built for traders and investors who want to go beyond surface-level stock data.

**Brand Identity**: Inspired by *The Matrix*, Stock Matrix helps users "see through" the market by revealing the underlying patterns, trends, and signals hidden in stock data.

**Key Differentiators**:
- Two-phase chart loading architecture delivers sub-second chart rendering (optimized from 16s)
- AI suite (Chat, Screener, Daily Intelligence) powered by Deepseek with tool-calling capabilities
- Live quote overlays with real-time indicator computation
- Nightly automated data pipeline with two-phase scheduling
- Tiered user system with credit-based AI quota and referral growth loop

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React.js (CRA) | Single-page application, port 3000 |
| **Charting** | Lightweight Charts (TradingView) | Candlestick, volume, technical indicator charts |
| **Backend** | FastAPI (Python 3.12) | Async API server, port 8000 |
| **Time-series DB** | PostgreSQL + TimescaleDB | OHLCV + technical indicators, hypertable partitioning |
| **Document DB** | MongoDB | Company metadata, fundamentals, AI conversations, reports |
| **Cache / Sessions** | Redis | Session management, health monitoring, data source caching |
| **Market Data** | yfinance (primary), Alpha Vantage Premium (fundamentals/news), Finnhub (fallback) |
| **AI** | Deepseek API | Chat agent with tool-calling, NL stock screener, daily intelligence reports |
| **Email** | SendGrid | Registration verification, password reset |
| **Infrastructure** | Docker Compose | MongoDB, PostgreSQL (TimescaleDB), Redis containers |

---

## System Architecture

### High-Level Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                          React Frontend                                │
│  StockChart.jsx │ ChatPanel.jsx │ Screener.jsx │ DailyIntelligence.jsx │
└──────┬──────────────────┬──────────────────┬───────────────────────────┘
       │ HTTP/WS           │ SSE               │ HTTP
       ▼                   ▼                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                                 │
│                                                                        │
│  /chart (PG)  │  /info (MongoDB)  │  /ai/* (Deepseek)  │  /ws (WS)   │
│               │                    │                     │             │
│  DataSourceManager ──── Adapter Chain (yfinance → AV → Finnhub)       │
│  LiveQuotesService ──── On-demand quotes with indicator computation   │
│  NightlyPipeline ────── Two-phase scheduled data refresh              │
│  ChatAgent ──────────── Tool-calling conversation loop                │
│  NLScreener ─────────── Natural language → SQL query                  │
└──┬──────────┬──────────────┬───────────────────────────────────────────┘
   │          │              │
   ▼          ▼              ▼
PostgreSQL  MongoDB        Redis
(OHLCV,     (metadata,     (sessions,
 indicators, fundamentals,  health,
 users,      AI convos,     cache)
 credits)    reports)
```

### Two-Phase Chart Loading (Sub-second Rendering)

The dashboard loading was optimized from ~16 seconds to under 1 second using a split-endpoint architecture:

| Phase | Endpoint | Source | Latency | Content |
|-------|----------|--------|---------|---------|
| **Phase 1** | `POST /chart` | PostgreSQL | ~0.28s | K-line (1-year lookback default), volume, MAs, technical indicators |
| **Phase 2** | `GET /info` | MongoDB (cached) | ~0.18s | Company overview, news sentiment, fundamentals |

- Phase 1 renders immediately — the chart is usable while Phase 2 loads
- Full history backfills silently when user scrolls to the left edge (TradingView-style lazy loading)
- Phase 2 fields are wiped to `null` on ticker switch to prevent stale data bleed-through
- Race-condition guard uses `useRef` (synchronous) rather than state to detect stale `/info` responses

### Nightly Data Pipeline

Automated two-phase pipeline ensures fresh data every trading day:

| Phase | Schedule | Content | Strategy |
|-------|----------|---------|----------|
| **Phase 1** | 5:00 PM ET (Mon–Fri) | K-line OHLCV + technicals | Bulk download via yfinance (all symbols in one call), then compute TA-Lib indicators and upsert to PG |
| **Phase 2** | 1:00 AM ET (Daily) | Fundamentals + news sentiment | Per-symbol via Alpha Vantage Premium (concurrency 35), store in MongoDB |

Key optimizations:
- Bulk download instead of per-symbol API calls (minutes vs. hours)
- Alpha Vantage Premium allows 75 req/min; pipeline uses 35 concurrent workers
- `reset_pool()` after pipeline to release PG connections back to the pool
- `latest_1d` materialized view for fast "latest row per symbol" queries (avoids full hypertable scans)

### Live Quotes System

On-demand live market data with indicator computation:

1. User views a stock → frontend calls `POST /subscribe/{symbol}`
2. `LiveQuotesService` fetches real-time OHLCV via yfinance
3. Computes all indicators (MAs, MACD, RSI, KDJ, Bollinger) from 60-day history + today's data
4. Upserts single row per symbol in `live_quotes` PG table
5. Frontend polls `GET /live-quotes/{symbol}` every 5 seconds
6. Live candle overlays on the main chart with `market_date_ts` from backend (never computed client-side)

---

## Database Schema

### PostgreSQL

#### Technical Data Tables (Interval-Specific)

Eight hypertables, each with MA periods optimized for that trading timeframe:

| Table | MA Periods |
|-------|-----------|
| `interval_1m_technical` | 5, 10, 20, 30, 60, 120 |
| `interval_5m_technical` | 6, 12, 24, 36, 72, 144 |
| `interval_15m_technical` | 4, 8, 16, 24, 48, 96 |
| `interval_30m_technical` | 3, 6, 12, 18, 36, 72 |
| `interval_60m_technical` | 3, 5, 8, 13, 21, 34 (Fibonacci) |
| `interval_1d_technical` | 5, 10, 20, 30, 60, 120, 250 |
| `interval_1wk_technical` | 5, 10, 20, 30, 60 |
| `interval_1mo_technical` | 3, 5, 10, 12, 24, 36 |

Common fields: `(symbol, datetime_index)` PK, OHLCV, SMA/EMA/WMA/DEMA/TEMA/KAMA per period, Bollinger Bands, MACD, RSI, KDJ, candlestick patterns (JSONB).

#### Derived Tables

- `latest_1d`: Materialized single-row-per-symbol from `interval_1d_technical` — avoids full hypertable scans for AI screener and latest-indicator queries
- `live_quotes`: Single-row-per-symbol cache with all indicators + previous-day values for cross detection

#### User System Tables

| Table | Purpose |
|-------|---------|
| `user_id_security` | Accounts (UUID PK, email, username, tier, referral_code, is_admin) |
| `email_verification_tokens` | Email verification (10-year expiry, effectively permanent) |
| `password_reset_tokens` | Password reset (24-hour expiry) |
| `user_credits` | Credit wallet (base + boost balances, monthly period tracking) |
| `credit_ledger` | Append-only audit trail (every spend/grant with token counts and cost) |
| `referrals` | Double-sided referral tracking (referrer: 100 credits, referee: 50 credits) |
| `subscriptions` | Payment provider placeholder (inactive, for future Stripe integration) |
| `tier_changes` | Tier change audit history |
| `anon_ai_usage` | Anonymous AI usage (sha256-hashed IP, lifetime cap) |
| `user_monitor_list` | Per-user stock monitoring list (tier-based: anon 5 / base 10 / premium 20) |

### MongoDB Collections

| Collection | Content |
|-----------|---------|
| `stock_metadata` | Company overview, fundamentals (income/balance/cash flow), news sentiment — cached with staleness checks |
| `stock_list` | Stock symbols with exchange and market cap |
| `ai_conversations` | Chat sessions — per-user, per-session, with title and message history |
| `ai_reports` | Daily intelligence reports generated by Deepseek |

### Redis

- Session management (HTTP-only cookies, 7-day expiry)
- Data source health monitoring (tracks adapter success rates)
- Cache layer for frequently accessed data

---

## API Endpoints

### Stock Data
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/stocks` | List all stock symbols |
| `POST` | `/api/stocks/{symbol}/chart` | Phase 1: PG chart data (fast) |
| `GET` | `/api/stocks/{symbol}/info` | Phase 2: Company overview + news + fundamentals (MongoDB cached) |
| `POST` | `/api/stocks/{symbol}` | Legacy combined endpoint (calls chart + info internally) |
| `POST` | `/api/stocks/{symbol}/market-close-refresh` | Refresh after market close |

### Live Quotes
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/live-quotes/{symbol}` | Get cached live quote with indicators |
| `POST` | `/api/live-quotes/{symbol}/subscribe` | Start polling for a symbol |
| `POST` | `/api/live-quotes/{symbol}/unsubscribe` | Stop polling |
| `WS` | `/ws/realtime` | WebSocket for real-time price updates during market hours |

### AI Suite (`/api/ai/`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/ai/chat` | Chat with AI agent (SSE streaming, tool-calling) |
| `GET` | `/ai/chat/conversations` | List user's chat sessions |
| `GET` | `/ai/chat/conversations/{id}` | Load a session's messages |
| `PATCH` | `/ai/chat/conversations/{id}/title` | Rename a session |
| `DELETE` | `/ai/chat/conversations/{id}` | Delete a session |
| `POST` | `/ai/screener` | Natural language stock screener |
| `GET` | `/ai/reports` | List daily intelligence reports |
| `GET` | `/ai/reports/{date}` | Get a specific report |
| `POST` | `/ai/reports/generate` | Trigger report generation (background task) |
| `DELETE` | `/ai/reports/{date}` | Delete a report |
| `GET` | `/ai/usage` | AI usage stats |

### Monitor List
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/monitor-list` | Get user's monitored stocks |
| `POST` | `/api/monitor-list/{symbol}` | Add stock (tier-based cap) |
| `DELETE` | `/api/monitor-list/{symbol}` | Remove stock |
| `POST` | `/api/monitor-list/sync` | Sync localStorage → PG on login |

### User System
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/me/entitlements` | Get user's tier, credits, limits |
| `GET` | `/api/me/profile` | Get user profile with credit details |
| `GET` | `/api/me/activity` | Get recent activity log |
| `GET` | `/api/referral` | Get referral code and summary |
| `POST` | `/api/admin/users/{id}/tier` | Admin: change user tier |
| `POST` | `/api/admin/users/{id}/credits` | Admin: adjust credits |

### Authentication (`/api/auth/`)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Register with email verification |
| `POST` | `/auth/login` | Login (session cookie) |
| `POST` | `/auth/logout` | Logout |
| `GET` | `/auth/me` | Current user info |
| `GET` | `/auth/verify-email` | Verify email token |
| `POST` | `/auth/resend-verification` | Resend verification email |
| `POST` | `/auth/forgot-password` | Request password reset |
| `POST` | `/auth/reset-password` | Reset password with token |

### Pipeline & Admin
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/init/status` | Initialization status |
| `POST` | `/api/init/run` | Run full initialization |
| `POST` | `/api/pipeline/nightly` | Trigger full nightly pipeline |
| `POST` | `/api/pipeline/phase1` | Trigger Phase 1 only (K-line) |
| `POST` | `/api/pipeline/phase2` | Trigger Phase 2 only (fundamentals) |
| `GET` | `/api/pipeline/history` | Pipeline run history |
| `GET` | `/api/health/sources` | Data source health status |

---

## Frontend Architecture

### Component Structure

```
frontend/src/
├── App.js                          # React Router: /:ticker? route for URL-based persistence
├── contexts/
│   └── AuthContext.js              # Global auth state (login, register, session)
├── utils/
│   └── quota.js                    # AI quota/credit helpers
├── components/
│   ├── StockChart.jsx              # Main dashboard (~3600 lines)
│   │   ├── Two-phase chart loading (Phase 1: /chart, Phase 2: /info)
│   │   ├── Live quote overlay with real-time candle updates
│   │   ├── Monitor list (up to 5 stocks, live polling, indicator cards)
│   │   ├── Company overview dashboard (OVERVIEW, VALUATION, FINANCIALS, PRICE STATS, ABOUT)
│   │   ├── Fundamental data section (income, balance sheet, cash flow with quarterly/yearly toggle)
│   │   ├── News sentiment gauge with article list
│   │   ├── Cross-chart synchronized cursors (price, volume, technical)
│   │   └── MA highlighting, period selection, interval switching
│   ├── StockChart.css              # Chart and dashboard styling
│   ├── MatrixBackground.jsx        # Animated Matrix rain background
│   ├── Auth/
│   │   ├── LoginModal.jsx          # Email/password login
│   │   ├── RegisterModal.jsx       # Registration with referral code support
│   │   ├── ForgotPasswordModal.jsx # Password reset request
│   │   ├── ResetPasswordPage.jsx   # Token-based password reset
│   │   ├── VerifyEmailPage.jsx     # Email verification handler
│   │   ├── UserMenu.jsx            # Logged-in user dropdown
│   │   ├── ProfilePage.jsx         # User profile with credits, tier, activity
│   │   └── Auth.css
│   ├── AI/
│   │   ├── ChatPanel.jsx           # Multi-session tabbed AI chat
│   │   │   ├── Tab bar with rename (double-click) and close (×)
│   │   │   ├── Persistent history loaded from MongoDB on login
│   │   │   ├── SSE streaming (cumulative text events, not deltas)
│   │   │   └── Lazy-loads messages when switching to a historical tab
│   │   ├── ChatPanel.css
│   │   ├── Screener.jsx            # Natural language stock screener
│   │   ├── Screener.css
│   │   ├── DailyIntelligence.jsx   # AI-generated daily market reports
│   │   └── DailyIntelligence.css
│   └── Navigation/
│       ├── Sidebar.jsx             # App-wide sidebar navigation
│       └── Sidebar.css
```

### Key Frontend Patterns

- **URL-based routing**: `/:ticker?` route preserves selected ticker across page refreshes and enables deep links
- **Two-phase state merge**: `setStockData(prev => ({ ...prev, ...res.data }))` — async fields (`company_info`, `news_sentiment`, `fundamental_data`) are nulled at the start of each ticker switch
- **Race-condition guard**: `infoFetchTickerRef` (useRef, synchronous) prevents stale `/info` responses from overwriting a newer ticker's data
- **Default 3-month chart view**: `setVisibleRange({ from: now - 90 * 86400, to: now })` for daily/weekly charts; `fitContent()` for intraday
- **Skeleton loading**: Shimmer skeleton renders while `company_info` is null and `fundamentalLoading` is true
- **Dual persistence for monitor list**: localStorage for anonymous users, PG for logged-in users, with sync-on-login

---

## Backend Architecture

### Key Backend Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, all stock/chart/live-quote/monitor/user endpoints, startup initialization |
| `ai/ai_router.py` | AI endpoints (chat, screener, reports), quota enforcement |
| `ai/chat/chat_agent.py` | Tool-calling conversation loop with Deepseek, MongoDB persistence |
| `ai/screener/nl_screener.py` | Natural language → SQL against `latest_1d` table |
| `ai/report/report_generator.py` | Daily market intelligence report generation |
| `ai/deepseek_client.py` | Deepseek API client with streaming, tool-call handling, and a priority-gated concurrency limit |
| `ai/priority_gate.py` | Bounded-concurrency gate that admits premium > base > anon AI calls first under load |
| `ai/tools/stock_data_tools.py` | Tool definitions for AI agent (query stock data, compute indicators) |
| `data_sources/data_source_manager.py` | Adapter chain: yfinance → Alpha Vantage → Finnhub with health-aware failover |
| `data_sources/nightly_pipeline.py` | Two-phase scheduled pipeline (Phase 1: K-line 5PM, Phase 2: Fundamentals 1AM) |
| `data_sources/live_quotes_service.py` | On-demand live quotes with full indicator computation, PG-backed caching |
| `data_sources/realtime_service.py` | WebSocket real-time price updates during market hours |
| `data_sources/data_initializer.py` | First-time full initialization for all stocks |
| `data_sources/indicator_calculator.py` | TA-Lib wrapper for computing all technical indicators |
| `data_sources/health_monitor.py` | Redis-backed health tracking per data source |
| `data_sources/data_validator.py` | Validates fetched data quality before storage |
| `data_sources/alpha_vantage_adapter.py` | AV Premium adapter (fundamentals, news, OHLCV) |
| `data_sources/yfinance_adapter.py` | yfinance adapter (OHLCV, overview, fundamentals) |
| `data_sources/finnhub_adapter.py` | Finnhub fallback adapter |
| `postgres_database.py` | asyncpg pool (max_size=100), `reset_pool()` for post-pipeline cleanup |
| `postgres_data_retrieval.py` | PG queries with default 1-year lookback, lazy full-history fetch |
| `repositories.py` | MongoDB repositories (metadata, stock list, AI conversations, reports) |
| `auth_routes.py` | Authentication endpoints (register, login, verify, reset) |
| `credits_service.py` | Credit wallet: spend/refund/grant with append-only ledger |
| `tier_service.py` | User tier management (base/premium) |
| `referral_service.py` | Referral code generation, tracking, reward distribution |
| `entitlements.py` | Tier-based feature limits (monitor list size, monthly credits, action costs) |
| `anon_usage.py` | Anonymous AI usage tracking (hashed IP, lifetime cap) |
| `activity_service.py` | User activity logging |

### Data Source Adapter Chain

```
DataSourceManager
  │
  ├── OHLCV chain:    yfinance → Alpha Vantage
  ├── Overview chain:  yfinance → Alpha Vantage
  ├── Fundamentals:    yfinance → Alpha Vantage
  └── News sentiment:  Alpha Vantage → Finnhub
```

Each adapter is health-monitored. If a source fails repeatedly, the health monitor marks it unhealthy and traffic shifts to the next adapter in the chain. Recovery is automatic.

### AI Suite Architecture

**Chat Agent** (`ChatAgent`):
- Multi-round tool-calling loop with Deepseek (max 5 rounds)
- SSE streaming: each `text` event carries cumulative full text (not deltas)
- Tools can query stock data, compute indicators, look up company info
- `_strip_for_storage()` removes tool-call intermediaries before MongoDB save (prevents Deepseek 400 errors on replay)
- Consecutive assistant message deduplication (safety net for old streaming bugs)

**NL Screener** (`NLScreener`):
- Translates natural language queries ("show me undervalued tech stocks with strong momentum") into SQL against `latest_1d`
- Returns ranked results with AI-generated explanations

**Daily Intelligence** (`ReportGenerator`):
- Scheduled at 7:00 PM ET (Mon–Fri)
- Gathers market data, sector performance, notable movers
- Generates structured report via Deepseek with executive summary, sector analysis, and stock highlights

**Quota Enforcement**:
- Authenticated users: credit-based (base credits refresh monthly, boost credits never expire)
- Anonymous users: lifetime per-IP cap (sha256-hashed, never stores raw IP)
- Refund on failure for authenticated users only
- Cost per action defined in `entitlements.py`

**Concurrency & Prioritization** (`ai/priority_gate.py`):
- All Deepseek calls (chat, screener, report) share one client gated to `AI_MAX_CONCURRENCY` concurrent upstream calls (env, default 8)
- When the gate is saturated, waiters are admitted by priority: **premium → base → anonymous** (FIFO within a tier); scheduled background jobs yield to live users
- Priority is derived from the caller's tier and flows to the client via a `ContextVar`; a slot is held only for a single call/stream round, so premium users jump ahead at each chat round boundary
- Live gate stats are exposed via `GET /api/ai/usage`

---

## User System

### Tier Model

| Tier | Monthly Credits | Monitor List | AI Features |
|------|----------------|-------------|-------------|
| **Base** (default) | 50 | Up to 10 stocks | Chat, Screener, Reports |
| **Premium** | 300 | Up to 20 stocks | All base + priority (AI request priority) |

### Credit Economy

- Each AI action costs credits (defined in `entitlements.py`)
- Base credits refresh monthly (no rollover)
- Boost credits never expire (earned via referrals, admin grants, future purchases)
- Spend order: base first, then boost
- Full audit trail in `credit_ledger` (includes token counts and estimated cost)

### Referral System

- Each user gets a unique 8-character referral code on registration
- Referrer earns 100 boost credits when referred user verifies email
- Referred user earns 50 boost credits as welcome bonus
- Double-sided reward with fraud-prevention status tracking

### Authentication Flow

- Registration → SendGrid verification email → verify token → auto-login
- Login with email/password → session cookie (HTTP-only, Redis-backed, 7-day expiry)
- Password reset: forgot → email with token → reset page → auto-login
- React Strict Mode compatible (useRef guards against double execution)

---

## Performance Characteristics

| Metric | Before | After | How |
|--------|--------|-------|-----|
| Chart loading | ~16s | <1s | Split `/chart` + `/info`, 1-year PG lookback default |
| Screener query | ~38s | <2s | `latest_1d` materialized view instead of full hypertable scan |
| Pipeline (Phase 1) | Hours | ~5 min | Bulk yfinance download, all symbols in one call |
| Pipeline (Phase 2) | Sequential | ~8 min | AV Premium 35 concurrent workers |
| PG pool stability | Connection exhaustion | Stable | `max_connections=200`, asyncpg `max_size=100`, `reset_pool()` after pipeline |

---

## Known Pitfalls & Solutions

| Pitfall | Impact | Solution |
|---------|--------|----------|
| NaN in yfinance fundamentals | `/info` returns 500 (Starlette JSON encoder crashes) | `_sanitize_rows()` replaces NaN/Inf with None in both DataFrame and MongoDB-cached dict paths |
| Timezone naive/aware mix in stale checks | TypeError causes unnecessary refetches for every stock | Compare both sides as naive: `datetime.now(_ET).replace(tzinfo=None)` |
| `setStockData` merge pattern | Previous stock's company info bleeds into new search | Null out async fields before fetch; use ref-based race guards |
| Live quote timestamps | Duplicate candles if computed client-side | `market_date_ts` always comes from backend, matches PG midnight-UTC convention |
| SSE cumulative text | Storing every chunk creates dozens of duplicate messages | Only append the final `last_assistant_text` after streaming ends |
| MongoDB tool-call messages | Replaying stored tool_call IDs with missing pairs causes Deepseek 400 | `_strip_for_storage()` removes all tool-related messages before save |

---

## Infrastructure

### Docker Compose Services

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
    # max_connections=200 (set in postgresql.conf)

  redis:
    image: redis:alpine
    ports: ["6379:6379"]
    volumes: [./docker/data/redis:/data]
```

### Environment Variables (backend/.env)

```
ALPHA_VANTAGE_API_KEY=...
DEEPSEEK_API_KEY=...
SENDGRID_API_KEY=...
SENDGRID_FROM_EMAIL=...
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
SESSION_SECRET=...
MONGODB_URL=mongodb://admin:password123@localhost:27017/stock_data?authSource=admin
REDIS_URL=redis://localhost:6379/0
POSTGRES_URL=postgresql://admin:password123@localhost:5432/postgres
```

### Running the Application

```bash
# 1. Start database services
docker-compose up -d

# 2. Start backend (with hot reload)
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# 3. Start frontend
cd frontend && npm start

# 4. Initialize data (first time only)
curl -X POST http://localhost:8000/api/init/run
```

---

## Project Structure

```
stock-matrix-web-app/
├── frontend/                       # React SPA
│   └── src/
│       ├── components/
│       │   ├── StockChart.jsx/css   # Main dashboard (chart, company info, fundamentals, news)
│       │   ├── AI/                  # ChatPanel, Screener, DailyIntelligence
│       │   ├── Auth/                # Login, Register, Profile, Verify, Reset
│       │   └── Navigation/          # Sidebar
│       ├── contexts/AuthContext.js   # Global auth state
│       └── utils/quota.js            # Credit/quota helpers
├── backend/
│   ├── main.py                      # FastAPI app + endpoints
│   ├── ai/                          # AI suite
│   │   ├── ai_router.py             # AI API endpoints
│   │   ├── deepseek_client.py       # LLM client
│   │   ├── priority_gate.py         # Premium-first AI concurrency gate
│   │   ├── chat/                    # Chat agent + prompts
│   │   ├── screener/                # NL stock screener
│   │   ├── report/                  # Daily intelligence generator
│   │   └── tools/                   # Tool definitions for agent
│   ├── data_sources/                # Market data layer
│   │   ├── data_source_manager.py   # Adapter chain orchestration
│   │   ├── nightly_pipeline.py      # Two-phase scheduled pipeline
│   │   ├── live_quotes_service.py   # Live quote polling + indicators
│   │   ├── realtime_service.py      # WebSocket real-time updates
│   │   ├── alpha_vantage_adapter.py # AV Premium adapter
│   │   ├── yfinance_adapter.py      # yfinance adapter
│   │   ├── finnhub_adapter.py       # Finnhub fallback
│   │   ├── indicator_calculator.py  # TA-Lib computations
│   │   ├── health_monitor.py        # Source health tracking
│   │   └── data_validator.py        # Data quality validation
│   ├── auth_routes.py               # Authentication endpoints
│   ├── credits_service.py           # Credit wallet + ledger
│   ├── tier_service.py              # Tier management
│   ├── referral_service.py          # Referral system
│   ├── entitlements.py              # Tier-based limits
│   ├── anon_usage.py                # Anonymous usage tracking
│   ├── postgres_database.py         # asyncpg pool management
│   ├── postgres_data_retrieval.py   # PG query layer
│   ├── repositories.py             # MongoDB repositories
│   └── redis_database.py           # Redis + session management
├── docker/
│   ├── docker-compose.yml
│   ├── postgres-init.sql            # Full PG schema (auto-generated)
│   └── mongo-init.js
├── CLAUDE.md                        # AI assistant behavior rules
├── PROJECT_DOCUMENTATION.md         # This file
└── USER_SYSTEM_PLAN.md              # User system design document
```

---

## GitHub

- **Repository**: `tylerjiang1127/stock-matrix-web-app`
- **Main branch**: `main`
- **Development branch**: `tyler-develop`

---

**Last Updated**: June 29, 2026
**Version**: 3.0.0
**Author**: Tyler Jiang

---

*Stock Matrix — See Through The Market*
