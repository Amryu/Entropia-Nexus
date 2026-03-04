-- Migration: Market price snapshot storage
-- Stores OCR'd market price window data (markup + sales per period)
-- Database: nexus_users

BEGIN;

-- Raw market price snapshots (one row per item per scan)
CREATE TABLE IF NOT EXISTS market_price_snapshots (
  id bigserial PRIMARY KEY,
  item_name text NOT NULL,
  item_id integer,
  tier smallint,
  markup_1d numeric(12,4),
  sales_1d numeric(12,4),
  markup_7d numeric(12,4),
  sales_7d numeric(12,4),
  markup_30d numeric(12,4),
  sales_30d numeric(12,4),
  markup_90d numeric(12,4),
  sales_90d numeric(12,4),
  markup_365d numeric(12,4),
  sales_365d numeric(12,4),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  submitted_by integer
);

CREATE INDEX IF NOT EXISTS idx_mps_item_name
  ON market_price_snapshots (item_name, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_mps_item_id
  ON market_price_snapshots (item_id, recorded_at DESC)
  WHERE item_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_mps_recorded
  ON market_price_snapshots (recorded_at);

-- Permissions
GRANT SELECT, INSERT ON market_price_snapshots TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE market_price_snapshots_id_seq TO nexus_users;

GRANT SELECT, INSERT ON market_price_snapshots TO nexus_bot;
GRANT USAGE, SELECT ON SEQUENCE market_price_snapshots_id_seq TO nexus_bot;

COMMIT;
