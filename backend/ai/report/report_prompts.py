REPORT_SYSTEM_PROMPT = """You are a professional US stock market daily report analyst, macro strategy analyst, and tech growth stock researcher.

Report style: Professional, clear, data-driven, suitable for investment review and daily trading plans.
Report goal: Help the reader quickly understand what happened in the US stock market on the previous trading day — why the market went up or down, where capital is flowing, which sectors/stocks showed unusual activity, and what risks and opportunities to watch next.

You will receive comprehensive market data from our database covering ~6800 US-listed stocks (NYSE, NASDAQ, AMEX) including OHLCV, technical indicators (RSI, MACD, SMA, Bollinger Bands), and sector performance.

IMPORTANT RULES:
- Be data-driven. Reference specific numbers from the provided data.
- Do NOT fabricate specific news events, Fed decisions, or earnings results that you're not certain about.
- For macro events (FOMC, CPI, etc.), note the most recent known context but acknowledge if you don't have today's specific data.
- Always include a disclaimer that this is not financial advice.
- Output the report in Markdown format with proper headers, tables, and formatting.
- Default language is English.

Generate the report following this structure:

# US Stock Market Daily Report | {date}

## Today's Summary
3-5 sentences covering: Was the market up/down/flat? What drove it (macro, earnings, AI theme, rates, geopolitical, sector rotation)? Risk-on or risk-off? Market breadth improving or deteriorating? What's the main narrative?
End with a one-line market status judgment.

## 1. Market Overview
Table with: Index | Close | Change % | Notes
Cover: Dow Jones, S&P 500, Nasdaq Composite, Russell 2000, SOX Semiconductor Index, VIX.
Note if any index hit new highs/lows, if small caps outperformed, if semiconductors led.

## 2. Intraday Recap
Timeline-style recap: pre-market → open → midday → close → after-hours.
What drove the moves at each phase?

## 3. Macro Environment

### 3.1 Treasury Yields
Table: Maturity | Yield | Change | Signal (2Y, 10Y, 30Y, 2Y-10Y spread)

### 3.2 Fed Rate Expectations
Current rate, market pricing for next meeting, year-end expectations.

### 3.3 Major Assets
Table: Asset | Price | Change | Driver (USD DXY, Gold, WTI Oil, Bitcoin)

### 3.4 Economic Data
Any notable data releases.

## 4. Sector Performance
Table ranking all 11 S&P sectors by performance.
Note which sectors led/lagged, growth vs value, cyclical vs defensive.

## 5. Theme & Style Performance
Cover: Semiconductors (SMH), Software (IGV), AI/Automation, Small cap growth vs value, Equal-weight vs cap-weight.
Is AI hardware still the leader? Is software catching up? Are small caps participating?

## 6. Market Breadth
Use the provided data on advance/decline, % above SMA50/SMA200.
Is breadth healthy or deteriorating? Is the index rally broad-based or narrow?

## 7. Technical Analysis
Table: Symbol | Price | SMA20 | SMA50 | SMA200 | RSI | Key Levels
Cover: SPY, QQQ, IWM, SMH.
Key support/resistance levels, overbought/oversold signals.

## 8. Notable Stock Moves
### 8.1 Mega-Cap Tech (Magnificent 7)
Table with NVDA, MSFT, AAPL, GOOGL, AMZN, META, TSLA performance.

### 8.2 AI Hardware / Semiconductors
Notable moves in NVDA, AMD, AVGO, MRVL, MU, etc.

### 8.3 Software / SaaS
Notable moves in CRM, NOW, SNOW, PANW, CRWD, PLTR, etc.

### 8.4 AI Power / Data Centers
Notable moves in CEG, VST, ETN, VRT, OKLO, etc.

### 8.5 Other Notable Movers
Biggest gainers/losers from the data, any unusual activity.

## 9. Sector Rotation Analysis
Current market stage: AI hardware rally / high-level consolidation / value rotation / risk-off / breadth expansion?
Where is money flowing in? Where is it flowing out?

## 10. Watchlist Observations
For key stocks from the data, provide: Stock | Today's Change | Trend | Support | Resistance | Assessment
Use labels: Strong momentum, Consolidating, Short-term overheated, Pullback support, Breakdown risk, Awaiting catalyst, Low-level recovery, Needs watching.

## 11. Tomorrow's Watch
Key macro events, critical support/resistance levels, sector rotation signals, 10-15 stocks to watch.

## 12. Risk Assessment
Table: Risk Dimension | Current Status | Risk Level (Low/Medium/Medium-High/High)
Cover: Macro rates, Market breadth, AI crowding, Earnings risk, Geopolitical, Technical, Liquidity.

## 13. Conclusion
3-5 sentence final summary. Current market phase. Operational bias. Top 5 signals to watch.

---
*Disclaimer: This report is for informational and educational purposes only. It does not constitute investment advice. All data is based on available market data and may not be fully accurate or timely. Investors should conduct their own due diligence.*
"""


def build_report_user_prompt(data: dict) -> str:
    sections = []
    sections.append(f"# Market Data for {data.get('date', 'today')}")

    # ── Major Indices (from yfinance) ────────────────────
    sections.append("\n## Major Index Performance")
    for idx in data.get("indices", []):
        sections.append(
            f"- **{idx['name']}**: {idx['close']:,.2f} ({idx['change_pct']:+.2f}%)"
        )

    # ── Treasury Yields (from yfinance) ──────────────────
    sections.append("\n## Treasury Yields")
    treasuries = data.get("treasuries", [])
    if treasuries:
        sections.append("| Maturity | Yield (%) | Change |")
        sections.append("|----------|-----------|--------|")
        for t in treasuries:
            chg = f"{t['change']:+.3f}" if t.get("change") is not None else "-"
            sections.append(f"| {t['maturity']} | {t['yield_pct']:.3f}% | {chg} |")

    # ── Major Assets (from yfinance) ─────────────────────
    sections.append("\n## Major Asset Prices")
    for a in data.get("major_assets", []):
        sections.append(
            f"- **{a['name']}**: ${a['close']:,.2f} ({a['change_pct']:+.2f}%)"
        )

    # ── ETF Technicals (from yfinance, with RSI/SMA) ─────
    sections.append("\n## Key ETF Technical Data (SPY, QQQ, IWM, SMH, IGV)")
    etfs = data.get("etf_technicals", [])
    if etfs:
        sections.append("| Symbol | Close | Change % | RSI | SMA20 | SMA50 | SMA200 |")
        sections.append("|--------|-------|----------|-----|-------|-------|--------|")
        for e in etfs:
            sections.append(
                f"| {e['symbol']} | ${e['close']} | {e['change_pct']:+.2f}% | "
                f"{e.get('rsi', 'N/A')} | ${e.get('sma20', 'N/A')} | "
                f"${e.get('sma50', 'N/A')} | ${e.get('sma200', 'N/A')} |"
            )

    # ── Market Breadth (from PG) ─────────────────────────
    sections.append("\n## Market Breadth Data (full US stock universe)")
    breadth = data.get("market_breadth", {})
    if breadth:
        sections.append(
            f"- Advancing stocks: {breadth.get('advancing', 'N/A')}\n"
            f"- Declining stocks: {breadth.get('declining', 'N/A')}\n"
            f"- Advance/Decline Ratio: {breadth.get('advance_decline_ratio', 'N/A')}\n"
            f"- % Above SMA50: {breadth.get('pct_above_sma50', 'N/A')}%\n"
            f"- % Above SMA200: {breadth.get('pct_above_sma200', 'N/A')}%\n"
            f"- Total stocks analyzed: {breadth.get('total', 'N/A')}"
        )

    # ── Top Movers (from PG) ─────────────────────────────
    sections.append("\n## Top Gainers (by daily % change)")
    movers = data.get("top_movers", {})
    if movers.get("gainers"):
        sections.append("| Symbol | Change % | Close |")
        sections.append("|--------|----------|-------|")
        for g in movers["gainers"][:15]:
            sections.append(
                f"| {g['symbol']} | +{g['change_pct']:.2f}% | "
                f"${g.get('latest_close', 'N/A')} |"
            )

    sections.append("\n## Top Losers (by daily % change)")
    if movers.get("losers"):
        sections.append("| Symbol | Change % | Close |")
        sections.append("|--------|----------|-------|")
        for l in movers["losers"][:15]:
            sections.append(
                f"| {l['symbol']} | {l['change_pct']:.2f}% | "
                f"${l.get('latest_close', 'N/A')} |"
            )

    # ── Sector Performance (from PG) ─────────────────────
    sections.append("\n## Sector Performance (average daily change)")
    if data.get("sector_performance"):
        sections.append("| Sector | Avg Change % | # Stocks |")
        sections.append("|--------|-------------|----------|")
        for sp in data["sector_performance"]:
            sections.append(
                f"| {sp['sector']} | {sp['avg_change_pct']:+.2f}% | "
                f"{sp['stock_count']} |"
            )

    # ── Volume Anomalies (from PG) ───────────────────────
    sections.append("\n## Volume Anomalies (stocks with unusually high volume)")
    for va in data.get("volume_anomalies", [])[:15]:
        avg_vol = max(va.get("avg_vol", 1), 1)
        ratio = round(va.get("volume", 0) / avg_vol, 1)
        sections.append(
            f"- **{va['symbol']}**: volume z-score {va.get('volume_zscore', 'N/A'):.1f}, "
            f"{ratio}x average"
        )

    # ── Key Stock Technicals (from PG) ───────────────────
    sections.append("\n## Key Stock Technical Levels (individual stocks from database)")
    key_symbols = data.get("key_technicals", [])
    if key_symbols:
        sections.append("| Symbol | Close | Change % | RSI | MACD Hist | SMA20 | SMA50 | SMA200 |")
        sections.append("|--------|-------|----------|-----|-----------|-------|-------|--------|")
        for s in key_symbols:
            sections.append(
                f"| {s.get('symbol','?')} | ${s.get('close','?')} | "
                f"{s.get('change_pct','?')}% | {s.get('rsi','?')} | "
                f"{s.get('macd_hist','?')} | ${s.get('sma20','?')} | "
                f"${s.get('sma50','?')} | ${s.get('sma200','?')} |"
            )

    # ── Mag 7 (from PG) ─────────────────────────────────
    sections.append("\n## Mega-Cap Tech (Magnificent 7)")
    mag7 = data.get("mag7_data", [])
    if mag7:
        sections.append("| Symbol | Close | Change % | RSI | MACD Hist | Volume |")
        sections.append("|--------|-------|----------|-----|-----------|--------|")
        for s in mag7:
            sections.append(
                f"| {s.get('symbol','?')} | ${s.get('close','?')} | "
                f"{s.get('change_pct', '?')}% | {s.get('rsi','?')} | "
                f"{s.get('macd_hist','?')} | {s.get('volume','?')} |"
            )

    return "\n".join(sections)


REPORT_SYSTEM_PROMPT_ZH = REPORT_SYSTEM_PROMPT.replace(
    "- Default language is English.",
    "- Default language is Chinese (简体中文).",
) + """

CRITICAL LANGUAGE OVERRIDE — output the ENTIRE report in Simplified Chinese (简体中文).
All section headers, analysis, commentary, table column headers, and table cell descriptions
must be in Chinese. Keep ticker symbols (NVDA, AAPL, SPY, QQQ, etc.) in English.
Use standard Chinese financial terms: 纳斯达克, 标普500, 道琼斯, 罗素2000, 费城半导体指数.

Use these Chinese section headers (keep section numbering the same):
# 美股每日收盘报告 | {date}
## 今日总结
## 1. 大盘总览
## 2. 盘中复盘
## 3. 宏观环境
### 3.1 美债收益率 / 3.2 联储利率预期 / 3.3 大类资产 / 3.4 经济数据
## 4. 板块表现
## 5. 主题与风格
## 6. 市场宽度
## 7. 技术面分析
## 8. 重点个股异动
### 8.1 科技七巨头 / 8.2 AI硬件与半导体 / 8.3 软件与SaaS / 8.4 AI电力与数据中心 / 8.5 其他异动
## 9. 板块轮动分析
## 10. 重点观察
## 11. 明日关注
## 12. 风险评估
## 13. 结论

免责声明也用中文。
"""
