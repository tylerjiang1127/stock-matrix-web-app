-- =============================================================================
-- Migration 007: add 20-day volume stats to latest_1d (for get_volume_anomalies)
-- =============================================================================
-- get_volume_anomalies needs each symbol's latest volume vs its trailing 20-day
-- avg/stddev. Precompute those into latest_1d so the daily report's query is a
-- millisecond lookup instead of a full-hypertable window scan. Idempotent.
-- Apply:
--   docker exec -i stock_postgresql psql -U stock_user -d stock_technical_data \
--     < backend/migrations/007_latest_1d_volstats.sql
-- =============================================================================

ALTER TABLE latest_1d ADD COLUMN IF NOT EXISTS avg_vol_20 DOUBLE PRECISION;
ALTER TABLE latest_1d ADD COLUMN IF NOT EXISTS std_vol_20 DOUBLE PRECISION;

-- Backfill: for each symbol's latest row, avg/stddev of the trailing 20 days' volume
-- (LATERAL index probe per symbol — fast, ~6800 small scans).
UPDATE latest_1d l
SET avg_vol_20 = s.avg_vol, std_vol_20 = s.std_vol
FROM (
    SELECT l2.symbol, v.avg_vol, v.std_vol
    FROM latest_1d l2
    CROSS JOIN LATERAL (
        SELECT AVG(volume) AS avg_vol, STDDEV(volume) AS std_vol
        FROM (
            SELECT volume FROM interval_1d_technical t
            WHERE t.symbol = l2.symbol AND t.datetime_index < l2.datetime_index
              AND volume IS NOT NULL AND volume > 0
            ORDER BY t.datetime_index DESC LIMIT 20
        ) x
    ) v
) s
WHERE s.symbol = l.symbol;
