-- Drop the unused generic item price tables and related infrastructure.
-- These tables were never populated (0 rows in item_prices and item_price_summaries).
-- Market price data now flows through market_price_submissions → market_price_snapshots.

BEGIN;

DROP TABLE IF EXISTS item_price_summaries;
DROP TABLE IF EXISTS item_price_summary_watermarks;
DROP TABLE IF EXISTS item_prices;
DROP TYPE IF EXISTS price_period_type;

COMMIT;
