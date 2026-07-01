-- PostgreSQL initialization script for stock technical data
-- Generated automatically based on stock_metadata_fetcher.py MA periods configuration
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =============================================
-- Technical Data Tables (Interval-Specific)
-- =============================================

-- 1M interval
CREATE TABLE IF NOT EXISTS interval_1m_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
    -- Moving Averages
    sma5 DECIMAL(15,4),
    sma10 DECIMAL(15,4),
    sma20 DECIMAL(15,4),
    sma30 DECIMAL(15,4),
    sma60 DECIMAL(15,4),
    sma120 DECIMAL(15,4),
    ema5 DECIMAL(15,4),
    ema10 DECIMAL(15,4),
    ema20 DECIMAL(15,4),
    ema30 DECIMAL(15,4),
    ema60 DECIMAL(15,4),
    ema120 DECIMAL(15,4),
    wma5 DECIMAL(15,4),
    wma10 DECIMAL(15,4),
    wma20 DECIMAL(15,4),
    wma30 DECIMAL(15,4),
    wma60 DECIMAL(15,4),
    wma120 DECIMAL(15,4),
    dema5 DECIMAL(15,4),
    dema10 DECIMAL(15,4),
    dema20 DECIMAL(15,4),
    dema30 DECIMAL(15,4),
    dema60 DECIMAL(15,4),
    dema120 DECIMAL(15,4),
    tema5 DECIMAL(15,4),
    tema10 DECIMAL(15,4),
    tema20 DECIMAL(15,4),
    tema30 DECIMAL(15,4),
    tema60 DECIMAL(15,4),
    tema120 DECIMAL(15,4),
    kama5 DECIMAL(15,4),
    kama10 DECIMAL(15,4),
    kama20 DECIMAL(15,4),
    kama30 DECIMAL(15,4),
    kama60 DECIMAL(15,4),
    kama120 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_middle DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    rsi_overbought DECIMAL(15,4),
    rsi_oversold DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Candlestick Patterns
    candlestick_patterns JSONB,
    bullish_signal INTEGER,
    bearish_signal INTEGER,
    pattern_signal INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, datetime_index)
);


-- 5M interval
CREATE TABLE IF NOT EXISTS interval_5m_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
    -- Moving Averages
    sma6 DECIMAL(15,4),
    sma12 DECIMAL(15,4),
    sma24 DECIMAL(15,4),
    sma36 DECIMAL(15,4),
    sma72 DECIMAL(15,4),
    sma144 DECIMAL(15,4),
    ema6 DECIMAL(15,4),
    ema12 DECIMAL(15,4),
    ema24 DECIMAL(15,4),
    ema36 DECIMAL(15,4),
    ema72 DECIMAL(15,4),
    ema144 DECIMAL(15,4),
    wma6 DECIMAL(15,4),
    wma12 DECIMAL(15,4),
    wma24 DECIMAL(15,4),
    wma36 DECIMAL(15,4),
    wma72 DECIMAL(15,4),
    wma144 DECIMAL(15,4),
    dema6 DECIMAL(15,4),
    dema12 DECIMAL(15,4),
    dema24 DECIMAL(15,4),
    dema36 DECIMAL(15,4),
    dema72 DECIMAL(15,4),
    dema144 DECIMAL(15,4),
    tema6 DECIMAL(15,4),
    tema12 DECIMAL(15,4),
    tema24 DECIMAL(15,4),
    tema36 DECIMAL(15,4),
    tema72 DECIMAL(15,4),
    tema144 DECIMAL(15,4),
    kama6 DECIMAL(15,4),
    kama12 DECIMAL(15,4),
    kama24 DECIMAL(15,4),
    kama36 DECIMAL(15,4),
    kama72 DECIMAL(15,4),
    kama144 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_middle DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    rsi_overbought DECIMAL(15,4),
    rsi_oversold DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Candlestick Patterns
    candlestick_patterns JSONB,
    bullish_signal INTEGER,
    bearish_signal INTEGER,
    pattern_signal INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, datetime_index)
);


-- 15M interval
CREATE TABLE IF NOT EXISTS interval_15m_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
    -- Moving Averages
    sma4 DECIMAL(15,4),
    sma8 DECIMAL(15,4),
    sma16 DECIMAL(15,4),
    sma24 DECIMAL(15,4),
    sma48 DECIMAL(15,4),
    sma96 DECIMAL(15,4),
    ema4 DECIMAL(15,4),
    ema8 DECIMAL(15,4),
    ema16 DECIMAL(15,4),
    ema24 DECIMAL(15,4),
    ema48 DECIMAL(15,4),
    ema96 DECIMAL(15,4),
    wma4 DECIMAL(15,4),
    wma8 DECIMAL(15,4),
    wma16 DECIMAL(15,4),
    wma24 DECIMAL(15,4),
    wma48 DECIMAL(15,4),
    wma96 DECIMAL(15,4),
    dema4 DECIMAL(15,4),
    dema8 DECIMAL(15,4),
    dema16 DECIMAL(15,4),
    dema24 DECIMAL(15,4),
    dema48 DECIMAL(15,4),
    dema96 DECIMAL(15,4),
    tema4 DECIMAL(15,4),
    tema8 DECIMAL(15,4),
    tema16 DECIMAL(15,4),
    tema24 DECIMAL(15,4),
    tema48 DECIMAL(15,4),
    tema96 DECIMAL(15,4),
    kama4 DECIMAL(15,4),
    kama8 DECIMAL(15,4),
    kama16 DECIMAL(15,4),
    kama24 DECIMAL(15,4),
    kama48 DECIMAL(15,4),
    kama96 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_middle DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    rsi_overbought DECIMAL(15,4),
    rsi_oversold DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Candlestick Patterns
    candlestick_patterns JSONB,
    bullish_signal INTEGER,
    bearish_signal INTEGER,
    pattern_signal INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, datetime_index)
);


-- 30M interval
CREATE TABLE IF NOT EXISTS interval_30m_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
    -- Moving Averages
    sma3 DECIMAL(15,4),
    sma6 DECIMAL(15,4),
    sma12 DECIMAL(15,4),
    sma18 DECIMAL(15,4),
    sma36 DECIMAL(15,4),
    sma72 DECIMAL(15,4),
    ema3 DECIMAL(15,4),
    ema6 DECIMAL(15,4),
    ema12 DECIMAL(15,4),
    ema18 DECIMAL(15,4),
    ema36 DECIMAL(15,4),
    ema72 DECIMAL(15,4),
    wma3 DECIMAL(15,4),
    wma6 DECIMAL(15,4),
    wma12 DECIMAL(15,4),
    wma18 DECIMAL(15,4),
    wma36 DECIMAL(15,4),
    wma72 DECIMAL(15,4),
    dema3 DECIMAL(15,4),
    dema6 DECIMAL(15,4),
    dema12 DECIMAL(15,4),
    dema18 DECIMAL(15,4),
    dema36 DECIMAL(15,4),
    dema72 DECIMAL(15,4),
    tema3 DECIMAL(15,4),
    tema6 DECIMAL(15,4),
    tema12 DECIMAL(15,4),
    tema18 DECIMAL(15,4),
    tema36 DECIMAL(15,4),
    tema72 DECIMAL(15,4),
    kama3 DECIMAL(15,4),
    kama6 DECIMAL(15,4),
    kama12 DECIMAL(15,4),
    kama18 DECIMAL(15,4),
    kama36 DECIMAL(15,4),
    kama72 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_middle DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    rsi_overbought DECIMAL(15,4),
    rsi_oversold DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Candlestick Patterns
    candlestick_patterns JSONB,
    bullish_signal INTEGER,
    bearish_signal INTEGER,
    pattern_signal INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, datetime_index)
);


-- 60M interval
CREATE TABLE IF NOT EXISTS interval_60m_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
    -- Moving Averages
    sma3 DECIMAL(15,4),
    sma5 DECIMAL(15,4),
    sma8 DECIMAL(15,4),
    sma13 DECIMAL(15,4),
    sma21 DECIMAL(15,4),
    sma34 DECIMAL(15,4),
    ema3 DECIMAL(15,4),
    ema5 DECIMAL(15,4),
    ema8 DECIMAL(15,4),
    ema13 DECIMAL(15,4),
    ema21 DECIMAL(15,4),
    ema34 DECIMAL(15,4),
    wma3 DECIMAL(15,4),
    wma5 DECIMAL(15,4),
    wma8 DECIMAL(15,4),
    wma13 DECIMAL(15,4),
    wma21 DECIMAL(15,4),
    wma34 DECIMAL(15,4),
    dema3 DECIMAL(15,4),
    dema5 DECIMAL(15,4),
    dema8 DECIMAL(15,4),
    dema13 DECIMAL(15,4),
    dema21 DECIMAL(15,4),
    dema34 DECIMAL(15,4),
    tema3 DECIMAL(15,4),
    tema5 DECIMAL(15,4),
    tema8 DECIMAL(15,4),
    tema13 DECIMAL(15,4),
    tema21 DECIMAL(15,4),
    tema34 DECIMAL(15,4),
    kama3 DECIMAL(15,4),
    kama5 DECIMAL(15,4),
    kama8 DECIMAL(15,4),
    kama13 DECIMAL(15,4),
    kama21 DECIMAL(15,4),
    kama34 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_middle DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    rsi_overbought DECIMAL(15,4),
    rsi_oversold DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Candlestick Patterns
    candlestick_patterns JSONB,
    bullish_signal INTEGER,
    bearish_signal INTEGER,
    pattern_signal INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, datetime_index)
);


-- 1D interval
CREATE TABLE IF NOT EXISTS interval_1d_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
    -- Moving Averages
    sma5 DECIMAL(15,4),
    sma10 DECIMAL(15,4),
    sma20 DECIMAL(15,4),
    sma30 DECIMAL(15,4),
    sma60 DECIMAL(15,4),
    sma120 DECIMAL(15,4),
    sma250 DECIMAL(15,4),
    ema5 DECIMAL(15,4),
    ema10 DECIMAL(15,4),
    ema20 DECIMAL(15,4),
    ema30 DECIMAL(15,4),
    ema60 DECIMAL(15,4),
    ema120 DECIMAL(15,4),
    ema250 DECIMAL(15,4),
    wma5 DECIMAL(15,4),
    wma10 DECIMAL(15,4),
    wma20 DECIMAL(15,4),
    wma30 DECIMAL(15,4),
    wma60 DECIMAL(15,4),
    wma120 DECIMAL(15,4),
    wma250 DECIMAL(15,4),
    dema5 DECIMAL(15,4),
    dema10 DECIMAL(15,4),
    dema20 DECIMAL(15,4),
    dema30 DECIMAL(15,4),
    dema60 DECIMAL(15,4),
    dema120 DECIMAL(15,4),
    dema250 DECIMAL(15,4),
    tema5 DECIMAL(15,4),
    tema10 DECIMAL(15,4),
    tema20 DECIMAL(15,4),
    tema30 DECIMAL(15,4),
    tema60 DECIMAL(15,4),
    tema120 DECIMAL(15,4),
    tema250 DECIMAL(15,4),
    kama5 DECIMAL(15,4),
    kama10 DECIMAL(15,4),
    kama20 DECIMAL(15,4),
    kama30 DECIMAL(15,4),
    kama60 DECIMAL(15,4),
    kama120 DECIMAL(15,4),
    kama250 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_middle DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    rsi_overbought DECIMAL(15,4),
    rsi_oversold DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Candlestick Patterns
    candlestick_patterns JSONB,
    bullish_signal INTEGER,
    bearish_signal INTEGER,
    pattern_signal INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, datetime_index)
);


-- 1WK interval
CREATE TABLE IF NOT EXISTS interval_1wk_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
    -- Moving Averages
    sma5 DECIMAL(15,4),
    sma10 DECIMAL(15,4),
    sma20 DECIMAL(15,4),
    sma30 DECIMAL(15,4),
    sma60 DECIMAL(15,4),
    ema5 DECIMAL(15,4),
    ema10 DECIMAL(15,4),
    ema20 DECIMAL(15,4),
    ema30 DECIMAL(15,4),
    ema60 DECIMAL(15,4),
    wma5 DECIMAL(15,4),
    wma10 DECIMAL(15,4),
    wma20 DECIMAL(15,4),
    wma30 DECIMAL(15,4),
    wma60 DECIMAL(15,4),
    dema5 DECIMAL(15,4),
    dema10 DECIMAL(15,4),
    dema20 DECIMAL(15,4),
    dema30 DECIMAL(15,4),
    dema60 DECIMAL(15,4),
    tema5 DECIMAL(15,4),
    tema10 DECIMAL(15,4),
    tema20 DECIMAL(15,4),
    tema30 DECIMAL(15,4),
    tema60 DECIMAL(15,4),
    kama5 DECIMAL(15,4),
    kama10 DECIMAL(15,4),
    kama20 DECIMAL(15,4),
    kama30 DECIMAL(15,4),
    kama60 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_middle DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    rsi_overbought DECIMAL(15,4),
    rsi_oversold DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Candlestick Patterns
    candlestick_patterns JSONB,
    bullish_signal INTEGER,
    bearish_signal INTEGER,
    pattern_signal INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, datetime_index)
);


-- 1MO interval
CREATE TABLE IF NOT EXISTS interval_1mo_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
    -- Moving Averages
    sma3 DECIMAL(15,4),
    sma5 DECIMAL(15,4),
    sma10 DECIMAL(15,4),
    sma12 DECIMAL(15,4),
    sma24 DECIMAL(15,4),
    sma36 DECIMAL(15,4),
    ema3 DECIMAL(15,4),
    ema5 DECIMAL(15,4),
    ema10 DECIMAL(15,4),
    ema12 DECIMAL(15,4),
    ema24 DECIMAL(15,4),
    ema36 DECIMAL(15,4),
    wma3 DECIMAL(15,4),
    wma5 DECIMAL(15,4),
    wma10 DECIMAL(15,4),
    wma12 DECIMAL(15,4),
    wma24 DECIMAL(15,4),
    wma36 DECIMAL(15,4),
    dema3 DECIMAL(15,4),
    dema5 DECIMAL(15,4),
    dema10 DECIMAL(15,4),
    dema12 DECIMAL(15,4),
    dema24 DECIMAL(15,4),
    dema36 DECIMAL(15,4),
    tema3 DECIMAL(15,4),
    tema5 DECIMAL(15,4),
    tema10 DECIMAL(15,4),
    tema12 DECIMAL(15,4),
    tema24 DECIMAL(15,4),
    tema36 DECIMAL(15,4),
    kama3 DECIMAL(15,4),
    kama5 DECIMAL(15,4),
    kama10 DECIMAL(15,4),
    kama12 DECIMAL(15,4),
    kama24 DECIMAL(15,4),
    kama36 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_middle DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    rsi_overbought DECIMAL(15,4),
    rsi_oversold DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Candlestick Patterns
    candlestick_patterns JSONB,
    bullish_signal INTEGER,
    bearish_signal INTEGER,
    pattern_signal INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol, datetime_index)
);


-- Convert tables to hypertables (TimescaleDB feature)
SELECT create_hypertable('interval_1m_technical', 'datetime_index', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
SELECT create_hypertable('interval_5m_technical', 'datetime_index', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
SELECT create_hypertable('interval_15m_technical', 'datetime_index', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
SELECT create_hypertable('interval_30m_technical', 'datetime_index', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
SELECT create_hypertable('interval_60m_technical', 'datetime_index', chunk_time_interval => INTERVAL '1 day', if_not_exists => TRUE);
SELECT create_hypertable('interval_1d_technical', 'datetime_index', chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);
SELECT create_hypertable('interval_1wk_technical', 'datetime_index', chunk_time_interval => INTERVAL '1 month', if_not_exists => TRUE);
SELECT create_hypertable('interval_1mo_technical', 'datetime_index', chunk_time_interval => INTERVAL '1 year', if_not_exists => TRUE);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_1m_symbol ON interval_1m_technical (symbol);
CREATE INDEX IF NOT EXISTS idx_5m_symbol ON interval_5m_technical (symbol);
CREATE INDEX IF NOT EXISTS idx_15m_symbol ON interval_15m_technical (symbol);
CREATE INDEX IF NOT EXISTS idx_30m_symbol ON interval_30m_technical (symbol);
CREATE INDEX IF NOT EXISTS idx_60m_symbol ON interval_60m_technical (symbol);
CREATE INDEX IF NOT EXISTS idx_1d_symbol ON interval_1d_technical (symbol);
CREATE INDEX IF NOT EXISTS idx_1wk_symbol ON interval_1wk_technical (symbol);
CREATE INDEX IF NOT EXISTS idx_1mo_symbol ON interval_1mo_technical (symbol);

-- Create indexes on datetime for time-based queries
CREATE INDEX IF NOT EXISTS idx_1m_datetime ON interval_1m_technical (datetime_index);
CREATE INDEX IF NOT EXISTS idx_5m_datetime ON interval_5m_technical (datetime_index);
CREATE INDEX IF NOT EXISTS idx_15m_datetime ON interval_15m_technical (datetime_index);
CREATE INDEX IF NOT EXISTS idx_30m_datetime ON interval_30m_technical (datetime_index);
CREATE INDEX IF NOT EXISTS idx_60m_datetime ON interval_60m_technical (datetime_index);
CREATE INDEX IF NOT EXISTS idx_1d_datetime ON interval_1d_technical (datetime_index);
CREATE INDEX IF NOT EXISTS idx_1wk_datetime ON interval_1wk_technical (datetime_index);
CREATE INDEX IF NOT EXISTS idx_1mo_datetime ON interval_1mo_technical (datetime_index);

-- =============================================
-- Latest-per-symbol snapshot (perf for AI screener / market tools)
-- =============================================
-- Mirrors interval_1d_technical + prev_close, one row per symbol. Avoids scanning the
-- 26M-row daily hypertable at request time. Populated/refreshed by the daily pipeline.
CREATE TABLE IF NOT EXISTS latest_1d (LIKE interval_1d_technical INCLUDING DEFAULTS);
ALTER TABLE latest_1d ADD COLUMN IF NOT EXISTS prev_close DECIMAL(15,4);
ALTER TABLE latest_1d ADD COLUMN IF NOT EXISTS avg_vol_20 DOUBLE PRECISION;
ALTER TABLE latest_1d ADD COLUMN IF NOT EXISTS std_vol_20 DOUBLE PRECISION;
DO $$ BEGIN
    ALTER TABLE latest_1d ADD PRIMARY KEY (symbol);
EXCEPTION WHEN others THEN null; END $$;
CREATE INDEX IF NOT EXISTS idx_latest_1d_rsi ON latest_1d (rsi);
CREATE INDEX IF NOT EXISTS idx_latest_1d_close ON latest_1d (close);
CREATE INDEX IF NOT EXISTS idx_latest_1d_macd_hist ON latest_1d (macd_hist);
CREATE INDEX IF NOT EXISTS idx_latest_1d_volume ON latest_1d (volume);

-- =============================================
-- Live Quotes Cache Table
-- =============================================
-- Single-row-per-symbol cache for on-demand live data.
-- Populated when a user views a stock; overwritten every polling cycle.
-- NOT a hypertable — symbol is the sole PK, one row per ticker.

CREATE TABLE IF NOT EXISTS live_quotes (
    symbol VARCHAR(10) PRIMARY KEY,
    -- OHLCV (today's aggregated)
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    volume BIGINT,
    prev_close DECIMAL(15,4),
    change DECIMAL(15,4),
    change_pct DECIMAL(10,4),
    -- SMA
    sma5 DECIMAL(15,4),
    sma10 DECIMAL(15,4),
    sma20 DECIMAL(15,4),
    sma30 DECIMAL(15,4),
    sma60 DECIMAL(15,4),
    sma120 DECIMAL(15,4),
    sma250 DECIMAL(15,4),
    -- EMA
    ema5 DECIMAL(15,4),
    ema10 DECIMAL(15,4),
    ema20 DECIMAL(15,4),
    ema30 DECIMAL(15,4),
    ema60 DECIMAL(15,4),
    ema120 DECIMAL(15,4),
    ema250 DECIMAL(15,4),
    -- WMA
    wma5 DECIMAL(15,4),
    wma10 DECIMAL(15,4),
    wma20 DECIMAL(15,4),
    wma30 DECIMAL(15,4),
    wma60 DECIMAL(15,4),
    wma120 DECIMAL(15,4),
    wma250 DECIMAL(15,4),
    -- DEMA
    dema5 DECIMAL(15,4),
    dema10 DECIMAL(15,4),
    dema20 DECIMAL(15,4),
    dema30 DECIMAL(15,4),
    dema60 DECIMAL(15,4),
    dema120 DECIMAL(15,4),
    dema250 DECIMAL(15,4),
    -- TEMA
    tema5 DECIMAL(15,4),
    tema10 DECIMAL(15,4),
    tema20 DECIMAL(15,4),
    tema30 DECIMAL(15,4),
    tema60 DECIMAL(15,4),
    tema120 DECIMAL(15,4),
    tema250 DECIMAL(15,4),
    -- KAMA
    kama5 DECIMAL(15,4),
    kama10 DECIMAL(15,4),
    kama20 DECIMAL(15,4),
    kama30 DECIMAL(15,4),
    kama60 DECIMAL(15,4),
    kama120 DECIMAL(15,4),
    kama250 DECIMAL(15,4),
    -- Bollinger Bands
    bbands_upper DECIMAL(15,4),
    bbands_lower DECIMAL(15,4),
    -- MACD
    macd DECIMAL(15,4),
    macd_signal DECIMAL(15,4),
    macd_hist DECIMAL(15,4),
    -- RSI
    rsi DECIMAL(15,4),
    -- KDJ
    k DECIMAL(15,4),
    d DECIMAL(15,4),
    j DECIMAL(15,4),
    -- Previous day values (for cross detection)
    prev_macd_hist DECIMAL(15,4),
    prev_k DECIMAL(15,4),
    prev_d DECIMAL(15,4),
    -- Metadata
    trading_date DATE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_live_quotes_updated ON live_quotes (updated_at);

-- =============================================
-- Authentication and User Management Tables
-- =============================================

-- Create user status enum type
DO $$ BEGIN
    CREATE TYPE user_status AS ENUM ('active', 'banned', 'suspended', 'paused');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create user tier enum type (User System — see USER_SYSTEM_PLAN.md)
DO $$ BEGIN
    CREATE TYPE user_tier AS ENUM ('base', 'premium');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- User accounts table
CREATE TABLE IF NOT EXISTS user_id_security (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_email_verified BOOLEAN DEFAULT FALSE,
    status user_status DEFAULT 'active',
    tier user_tier NOT NULL DEFAULT 'base',
    referral_code VARCHAR(12) UNIQUE,
    referred_by UUID REFERENCES user_id_security(id) ON DELETE SET NULL,
    last_login_at TIMESTAMPTZ,
    is_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Email verification tokens table
CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Password reset tokens table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for auth tables
CREATE INDEX IF NOT EXISTS idx_user_email ON user_id_security(email);
CREATE INDEX IF NOT EXISTS idx_user_username ON user_id_security(username);
CREATE INDEX IF NOT EXISTS idx_user_status ON user_id_security(status);
CREATE INDEX IF NOT EXISTS idx_email_verify_token ON email_verification_tokens(token);
CREATE INDEX IF NOT EXISTS idx_email_verify_user ON email_verification_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_user ON password_reset_tokens(user_id);

-- User monitoring list table
CREATE TABLE IF NOT EXISTS user_monitor_list (
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    symbol VARCHAR(10) NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_monitor_list_user ON user_monitor_list(user_id);

-- =============================================
-- User System: Matrix AI Credits, Referrals, Anon Usage
-- (mirrors backend/migrations/001_user_system.sql — see USER_SYSTEM_PLAN.md)
-- =============================================

-- Credit wallet (1:1, fast balance cache; truth lives in credit_ledger)
CREATE TABLE IF NOT EXISTS user_credits (
    user_id UUID PRIMARY KEY REFERENCES user_id_security(id) ON DELETE CASCADE,
    base_credits INT NOT NULL DEFAULT 50,                                   -- monthly refresh, no rollover (base tier allotment)
    base_period DATE NOT NULL DEFAULT (date_trunc('month', (NOW() AT TIME ZONE 'US/Eastern')))::date,
    boost_credits INT NOT NULL DEFAULT 0,                                   -- never expires
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Append-only ledger (audit trail + token analytics)
CREATE TABLE IF NOT EXISTS credit_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    action VARCHAR(32) NOT NULL,        -- chat | screener | monthly_refresh | referral_bonus | welcome_bonus | purchase | admin_adjust
    credits_delta INT NOT NULL,         -- negative = spend, positive = grant
    bucket VARCHAR(8) NOT NULL,         -- base | boost
    balance_after INT NOT NULL,
    ref_type VARCHAR(32),
    ref_id VARCHAR(64),
    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(10,6),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ledger_user_time ON credit_ledger(user_id, created_at DESC);

-- Referrals (growth loop + fraud audit)
CREATE TABLE IF NOT EXISTS referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    referred_user_id UUID UNIQUE NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    referral_code VARCHAR(12) NOT NULL,
    status VARCHAR(12) NOT NULL DEFAULT 'pending',  -- pending | approved | rewarded | rejected
    referrer_reward INT NOT NULL DEFAULT 100,
    referee_reward INT NOT NULL DEFAULT 50,         -- double-sided welcome boost
    created_at TIMESTAMPTZ DEFAULT NOW(),
    approved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);

-- Subscriptions (PLACEHOLDER — no payment provider wired yet)
CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    plan VARCHAR(16) NOT NULL DEFAULT 'premium',
    status VARCHAR(16) NOT NULL DEFAULT 'inactive',  -- inactive | active | past_due | canceled
    provider VARCHAR(16),
    provider_ref VARCHAR(128),
    current_period_start TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    started_at TIMESTAMPTZ,                           -- first time this user ever became premium
    canceled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);

-- Tier-change audit trail (tier on user_id_security is a fast cache; this is history)
CREATE TABLE IF NOT EXISTS tier_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_id_security(id) ON DELETE CASCADE,
    from_tier user_tier,
    to_tier user_tier NOT NULL,
    reason VARCHAR(32),          -- initial | upgrade | downgrade | lapse | admin
    effective_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tier_changes_user ON tier_changes(user_id, effective_at DESC);

-- Anonymous AI usage (durable lifetime per-IP cap; raw IP never stored)
CREATE TABLE IF NOT EXISTS anon_ai_usage (
    ip_hash CHAR(64) PRIMARY KEY,       -- sha256(ip + server_salt)
    count INT NOT NULL DEFAULT 0,
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ DEFAULT NOW()
);
