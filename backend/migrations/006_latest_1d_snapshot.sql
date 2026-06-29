-- =============================================================================
-- Migration 006: latest_1d snapshot (perf fix for AI Screener + market tools)
-- =============================================================================
-- Computing "latest row per symbol" by scanning the 26M-row interval_1d_technical
-- hypertable took ~38s PER request. This materializes one row per symbol (~6800 rows)
-- so the screener / breadth / movers become millisecond lookups. Refreshed daily by
-- the pipeline after Phase 1 (daily indicators only change once, after close).
--
-- This migration runs the expensive scan ONCE to populate. Apply:
--   docker exec -i stock_postgresql psql -U stock_user -d stock_technical_data \
--     < backend/migrations/006_latest_1d_snapshot.sql
-- =============================================================================

DROP TABLE IF EXISTS latest_1d;

-- One row per symbol: the latest daily bar + indicators, plus the previous close
-- (for advance/decline + % change without a second scan).
CREATE TABLE latest_1d AS
SELECT DISTINCT ON (symbol)
    t.*,
    LEAD(close) OVER (PARTITION BY symbol ORDER BY datetime_index DESC) AS prev_close
FROM interval_1d_technical t
WHERE close IS NOT NULL
ORDER BY symbol, datetime_index DESC;

ALTER TABLE latest_1d ADD PRIMARY KEY (symbol);
CREATE INDEX IF NOT EXISTS idx_latest_1d_rsi ON latest_1d (rsi);
CREATE INDEX IF NOT EXISTS idx_latest_1d_close ON latest_1d (close);
CREATE INDEX IF NOT EXISTS idx_latest_1d_macd_hist ON latest_1d (macd_hist);
CREATE INDEX IF NOT EXISTS idx_latest_1d_volume ON latest_1d (volume);
