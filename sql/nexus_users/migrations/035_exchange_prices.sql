-- Exchange price history tables
-- Raw snapshots taken every 15 minutes from active trade_offers
-- and pre-computed summaries for chart display

-- Period type enum for summaries
CREATE TYPE exchange_price_period AS ENUM ('hour', 'day', 'week');

-- Raw snapshots: one row per item per snapshot interval
CREATE TABLE exchange_price_snapshots (
  id            bigserial PRIMARY KEY,
  item_id       integer NOT NULL,
  markup_value  numeric(12,4) NOT NULL,   -- raw markup (% for stackable, +PED for condition)
  volume        integer NOT NULL DEFAULT 0,
  buy_count     smallint NOT NULL DEFAULT 0,
  sell_count    smallint NOT NULL DEFAULT 0,
  recorded_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX exchange_price_snapshots_item_time_idx
  ON exchange_price_snapshots (item_id, recorded_at DESC);
CREATE INDEX exchange_price_snapshots_time_idx
  ON exchange_price_snapshots (recorded_at);

-- Pre-computed rollups for longer time ranges
CREATE TABLE exchange_price_summaries (
  id            bigserial PRIMARY KEY,
  item_id       integer NOT NULL,
  period_type   exchange_price_period NOT NULL,
  period_start  timestamptz NOT NULL,
  price_min     numeric(12,4),
  price_max     numeric(12,4),
  price_avg     numeric(12,4),
  price_p10     numeric(12,4),
  price_median  numeric(12,4),
  price_p90     numeric(12,4),
  price_wap     numeric(12,4),
  volume        bigint,
  sample_count  integer,
  computed_at   timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX exchange_price_summaries_uq
  ON exchange_price_summaries (item_id, period_type, period_start);

-- Watermarks for incremental summary computation
CREATE TABLE exchange_price_summary_watermarks (
  period_type          exchange_price_period PRIMARY KEY,
  last_computed_until  timestamptz,
  last_run_at          timestamptz
);

INSERT INTO exchange_price_summary_watermarks (period_type) VALUES
  ('hour'), ('day'), ('week');

-- Permissions
GRANT SELECT, INSERT ON exchange_price_snapshots TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE ON exchange_price_summaries TO "nexus-bot";
GRANT SELECT, UPDATE ON exchange_price_summary_watermarks TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE exchange_price_snapshots_id_seq TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE exchange_price_summaries_id_seq TO "nexus-bot";
GRANT SELECT ON exchange_price_snapshots TO nexus;
GRANT SELECT ON exchange_price_summaries TO nexus;
GRANT SELECT ON exchange_price_snapshots TO nexus_users;
GRANT SELECT ON exchange_price_summaries TO nexus_users;
