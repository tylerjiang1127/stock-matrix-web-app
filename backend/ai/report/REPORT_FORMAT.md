# AI Macro Daily Report — Format & Content Specification

## Overview

The AI Macro Daily Report is an automated US stock market analysis report generated daily at **6:00 PM Eastern Time** on trading days (Monday–Friday). It uses the Deepseek LLM API to analyze market data gathered from our PostgreSQL database (covering ~500 S&P 500 stocks) and produces a comprehensive markdown report.

## Generation Schedule

- **Time**: 6:00 PM ET, Monday through Friday
- **Trigger**: APScheduler CronTrigger in `main.py`
- **Manual trigger**: `POST /api/ai/reports/generate`
- **Storage**: MongoDB `ai_reports` collection

## Data Sources

Internal (from PostgreSQL `interval_1d_technical` table):
- OHLCV price data for ~504 S&P 500 stocks
- Technical indicators: RSI, MACD, MACD histogram, MACD signal
- Moving averages: SMA5, SMA10, SMA20, SMA50, SMA60, SMA100, SMA200
- EMA: EMA5, EMA10, EMA20, EMA50, EMA100, EMA200
- Bollinger Bands: upper, middle, lower
- Sector mapping from MongoDB `stock_metadata`

## Report Structure (15 Sections)

### 0. Today's Summary
- 3–5 sentence market overview
- Core drivers: macro, earnings, AI theme, rates, geopolitical, sector rotation
- Risk-on vs risk-off assessment
- Market breadth status
- One-line market status judgment

### 1. Market Overview
Table of major indices with close, change %, and notes:
- Dow Jones, S&P 500, Nasdaq Composite, Russell 2000, SOX Semiconductor, VIX

### 2. Intraday Recap
Timeline-style recap: pre-market → open → midday → close → after-hours

### 3. Macro Environment
- **3.1 Treasury Yields**: 2Y, 10Y, 30Y, spread analysis
- **3.2 Fed Rate Expectations**: current rate, market pricing, year-end outlook
- **3.3 Major Assets**: USD DXY, Gold, WTI Oil, Bitcoin
- **3.4 Economic Data**: notable data releases

### 4. Sector Performance
All 11 S&P 500 sectors ranked by performance:
- Technology (XLK), Communication (XLC), Consumer Discretionary (XLY)
- Financials (XLF), Industrials (XLI), Healthcare (XLV)
- Consumer Staples (XLP), Energy (XLE), Utilities (XLU)
- Materials (XLB), Real Estate (XLRE)
- Growth vs value, cyclical vs defensive analysis

### 5. Theme & Style Performance
- Semiconductors (SMH/SOXX), Software (IGV), AI/Automation
- Small cap growth vs value (IWO vs IWN)
- Equal-weight vs cap-weight (RSP vs SPY)
- AI hardware leadership status

### 6. Market Breadth
- Advance/decline ratio from our database
- % above SMA50, % above SMA200
- Health/deterioration assessment

### 7. Technical Analysis
Table for key symbols: SPY, QQQ, IWM, SMH
- Close, SMA20, SMA50, SMA200, RSI, key support/resistance

### 8. Notable Stock Moves
- **8.1 Magnificent 7**: NVDA, MSFT, AAPL, GOOGL, AMZN, META, TSLA
- **8.2 AI Hardware / Semiconductors**: NVDA, AMD, AVGO, MRVL, MU, etc.
- **8.3 Software / SaaS**: CRM, NOW, SNOW, PANW, CRWD, PLTR, etc.
- **8.4 AI Power / Data Centers**: CEG, VST, ETN, VRT, OKLO, etc.
- **8.5 Other Notable Movers**: biggest gainers/losers

### 9. Sector Rotation Analysis
- Current market stage classification
- Capital flow in/out directions
- AI theme health assessment

### 10. Watchlist Observations
Key stocks with: trend, support, resistance, assessment label
Labels: Strong momentum | Consolidating | Short-term overheated | Pullback support | Breakdown risk | Awaiting catalyst | Low-level recovery | Needs watching

### 11. Tomorrow's Watch
- Key macro events
- Critical technical levels
- 10–15 stocks to watch

### 12. Risk Assessment
Table with risk dimensions and levels (Low / Medium / Medium-High / High):
- Macro rates, Market breadth, AI crowding, Earnings risk
- Geopolitical, Technical, Liquidity

### 13. Conclusion
- 3–5 sentence final summary
- Current market phase
- Operational bias
- Top 5 signals to watch
- Disclaimer

## Output Format

- **Format**: Markdown (rendered in frontend via `react-markdown` with `remark-gfm`)
- **Default language**: English
- **Stored as**: `sections.report_markdown` field in MongoDB document
- **Market mood**: Auto-detected from content ("bullish" / "bearish" / "neutral"), stored as `sections.market_mood`

## MongoDB Document Schema

```json
{
  "date": "2026-06-17",
  "report_type": "daily",
  "sections": {
    "report_markdown": "# US Stock Market Daily Report | 2026-06-17\n\n## 0. Today's Summary\n...",
    "market_mood": "bullish"
  },
  "raw_data": { ... },
  "model": "deepseek-chat",
  "tokens_used": { "input": 3500, "output": 6000 },
  "created_at": "2026-06-17T22:00:00Z"
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ai/reports` | GET | List recent reports (date + mood) |
| `/api/ai/reports/{date}` | GET | Full report for a date |
| `/api/ai/reports/generate` | POST | Manual trigger |

## Key Files

| File | Purpose |
|------|---------|
| `backend/ai/report/report_prompts.py` | System prompt and user prompt builder |
| `backend/ai/report/report_generator.py` | Orchestrator: gather → LLM → store |
| `backend/ai/report/data_gatherer.py` | PostgreSQL/MongoDB data queries |
| `frontend/src/components/AI/DailyIntelligence.jsx` | Report viewer page |
| `frontend/src/components/AI/DailyIntelligence.css` | Report styling (markdown theme) |

## Cost Estimate

- Input: ~3,000–5,000 tokens (market data)
- Output: ~4,000–8,000 tokens (full report)
- Cost per report: ~$0.002–$0.005 (Deepseek pricing)
- Monthly (22 trading days): ~$0.05–$0.11

## Reference

The report structure is inspired by the professional Chinese-language daily report format in `美股收盘日报_2026-06-16.html`, adapted to English with comprehensive coverage of macro, sector, technical, and stock-level analysis.
