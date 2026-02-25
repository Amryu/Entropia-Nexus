-- Migration: Item price tracking tables
-- Stores historical item price observations and pre-computed summaries
-- Database: nexus_users

BEGIN;

-- Enum for summary period types
DO $$ BEGIN
  CREATE TYPE price_period_type AS ENUM ('hour', 'day', 'week');
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

-- Raw price observations
CREATE TABLE IF NOT EXISTS item_prices (
  id bigserial PRIMARY KEY,
  item_id integer NOT NULL,
  price_value numeric(12,4) NOT NULL,
  quantity integer NOT NULL DEFAULT 1,
  source text DEFAULT NULL,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_item_prices_item_time
  ON item_prices (item_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_item_prices_source_time
  ON item_prices (source, recorded_at DESC)
  WHERE source IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_item_prices_recorded_at
  ON item_prices (recorded_at);

-- Pre-computed rollup summaries
CREATE TABLE IF NOT EXISTS item_price_summaries (
  id bigserial PRIMARY KEY,
  item_id integer NOT NULL,
  source text DEFAULT NULL,
  period_type price_period_type NOT NULL,
  period_start timestamptz NOT NULL,
  price_min numeric(12,4),
  price_max numeric(12,4),
  price_avg numeric(12,4),
  price_p5 numeric(12,4),
  price_median numeric(12,4),
  price_p95 numeric(12,4),
  price_wap numeric(12,4),
  volume bigint,
  sample_count integer,
  computed_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_item_price_summaries_upsert
  ON item_price_summaries (item_id, COALESCE(source, ''), period_type, period_start);

CREATE INDEX IF NOT EXISTS idx_item_price_summaries_query
  ON item_price_summaries (item_id, period_type, period_start DESC);

-- Watermarks for incremental summary computation
CREATE TABLE IF NOT EXISTS item_price_summary_watermarks (
  period_type price_period_type PRIMARY KEY,
  last_computed_until timestamptz,
  last_run_at timestamptz
);

-- Seed watermark rows
INSERT INTO item_price_summary_watermarks (period_type, last_computed_until, last_run_at)
VALUES
  ('hour', NULL, NULL),
  ('day', NULL, NULL),
  ('week', NULL, NULL)
ON CONFLICT (period_type) DO NOTHING;

-- Permissions: nexus_users (app) gets read on prices, full on summaries/watermarks
GRANT SELECT ON item_prices TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON item_price_summaries TO nexus_users;
GRANT SELECT, UPDATE ON item_price_summary_watermarks TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE item_price_summaries_id_seq TO nexus_users;

-- Permissions: nexus-bot gets insert on prices, full on summaries/watermarks
GRANT INSERT ON item_prices TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE item_prices_id_seq TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON item_price_summaries TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE item_price_summaries_id_seq TO "nexus-bot";
GRANT SELECT, UPDATE ON item_price_summary_watermarks TO "nexus-bot";

COMMIT;
