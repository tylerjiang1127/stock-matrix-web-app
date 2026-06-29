-- Add trading_date column to live_quotes so market_date_ts reflects the actual
-- last trading day from yfinance, not the calendar day of updated_at.
ALTER TABLE live_quotes ADD COLUMN IF NOT EXISTS trading_date DATE;
