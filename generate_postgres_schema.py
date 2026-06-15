#!/usr/bin/env python3
"""
Generate PostgreSQL initialization SQL with interval-specific MA columns
This script generates postgres-init.sql based on the MA periods defined in stock_metadata_fetcher.py
"""

# Define MA periods for each interval (must match stock_metadata_fetcher.py)
MA_PERIODS_CONFIG = {
    '1m': [5, 10, 20, 30, 60, 120],
    '5m': [6, 12, 24, 36, 72, 144],
    '15m': [4, 8, 16, 24, 48, 96],
    '30m': [3, 6, 12, 18, 36, 72],
    '60m': [3, 5, 8, 13, 21, 34],
    '1d': [5, 10, 20, 30, 60, 120, 250],
    '1wk': [5, 10, 20, 30, 60],
    '1mo': [3, 5, 10, 12, 24, 36],
}

# MA types
MA_TYPES = ['sma', 'ema', 'wma', 'dema', 'tema', 'kama']

def generate_ma_columns(interval):
    """Generate MA column definitions for a specific interval"""
    periods = MA_PERIODS_CONFIG[interval]
    lines = []
    lines.append("    -- Moving Averages")
    
    for ma_type in MA_TYPES:
        for period in periods:
            lines.append(f"    {ma_type}{period} DECIMAL(15,4),")
    
    return '\n'.join(lines)

def generate_table_sql(interval, table_suffix):
    """Generate complete CREATE TABLE statement for an interval"""
    ma_columns = generate_ma_columns(interval)
    
    sql = f"""-- {interval.upper()} interval
CREATE TABLE IF NOT EXISTS interval_{table_suffix}_technical (
    symbol VARCHAR(10) NOT NULL,
    datetime_index TIMESTAMPTZ NOT NULL,
    open DECIMAL(15,4),
    high DECIMAL(15,4),
    low DECIMAL(15,4),
    close DECIMAL(15,4),
    adjusted_close DECIMAL(15,4),
    volume BIGINT,
{ma_columns}
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
"""
    return sql

def generate_full_sql():
    """Generate complete postgres-init.sql file"""
    interval_mapping = {
        '1m': '1m',
        '5m': '5m',
        '15m': '15m',
        '30m': '30m',
        '60m': '60m',
        '1d': '1d',
        '1wk': '1wk',
        '1mo': '1mo'
    }
    
    sql_parts = []
    
    # Header
    sql_parts.append("""-- PostgreSQL initialization script for stock technical data
-- Generated automatically based on stock_metadata_fetcher.py MA periods configuration
-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- =============================================
-- Technical Data Tables (Interval-Specific)
-- =============================================
""")
    
    # Generate tables for each interval
    for interval, table_suffix in interval_mapping.items():
        sql_parts.append(generate_table_sql(interval, table_suffix))
        sql_parts.append("")  # Add blank line between tables
    
    # Convert to hypertables
    sql_parts.append("""-- Convert tables to hypertables (TimescaleDB feature)
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
-- Authentication and User Management Tables
-- =============================================

-- Create user status enum type
DO $$ BEGIN
    CREATE TYPE user_status AS ENUM ('active', 'banned', 'suspended', 'paused');
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
""")
    
    return '\n'.join(sql_parts)

if __name__ == '__main__':
    sql_content = generate_full_sql()
    
    # Write to file
    output_path = 'docker/postgres-init.sql'
    with open(output_path, 'w') as f:
        f.write(sql_content)
    
    print(f"✅ Successfully generated {output_path}")
    print(f"\n📊 MA Periods Configuration:")
    for interval, periods in MA_PERIODS_CONFIG.items():
        print(f"  {interval:5s}: {periods}")
    print(f"\n💾 Total MA columns per interval:")
    for interval in MA_PERIODS_CONFIG:
        num_columns = len(MA_PERIODS_CONFIG[interval]) * len(MA_TYPES)
        print(f"  {interval:5s}: {num_columns} columns ({len(MA_PERIODS_CONFIG[interval])} periods × {len(MA_TYPES)} MA types)")
