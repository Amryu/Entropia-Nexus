-- Multi-user market price ingestion: submissions table + snapshots finalization.
--
-- Game prices update once per hour. Multiple users submit the same data;
-- submissions are bucketed by floor-to-hour. After the hour elapses (+5 min
-- grace), a confidence-weighted majority vote finalizes each column into a
-- single authoritative snapshot. Raw submissions are kept 3 days for
-- traceability, then auto-deleted.

BEGIN;

-- Raw per-user submissions (retained 3 days)
CREATE TABLE market_price_submissions (
  id bigserial PRIMARY KEY,
  item_id integer NOT NULL,
  tier smallint,
  bucket_hour timestamptz NOT NULL,
  markup_1d numeric(12,4),
  sales_1d numeric(12,4),
  markup_7d numeric(12,4),
  sales_7d numeric(12,4),
  markup_30d numeric(12,4),
  sales_30d numeric(12,4),
  markup_365d numeric(12,4),
  sales_365d numeric(12,4),
  markup_3650d numeric(12,4),
  sales_3650d numeric(12,4),
  submitted_at timestamptz NOT NULL DEFAULT now(),
  submitted_by bigint NOT NULL,
  confidence real,
  manually_reviewed jsonb
);

-- One submission per user per item per hour
CREATE UNIQUE INDEX idx_mp_sub_dedup
  ON market_price_submissions (item_id, submitted_by, bucket_hour);

-- Finalization lookup: all submissions for an item+hour
CREATE INDEX idx_mp_sub_item_hour
  ON market_price_submissions (item_id, bucket_hour);

-- Cleanup by age
CREATE INDEX idx_mp_sub_age
  ON market_price_submissions (submitted_at);

-- Permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON market_price_submissions TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE market_price_submissions_id_seq TO nexus_users;

-- Finalization metadata on snapshots
ALTER TABLE market_price_snapshots
  ADD COLUMN IF NOT EXISTS finalized_at timestamptz,
  ADD COLUMN IF NOT EXISTS submission_count smallint;

-- Deduplicate existing snapshots within the same (item_id, hour).
-- Keep the row with highest confidence; ties broken by earliest id.
DELETE FROM market_price_snapshots
WHERE id IN (
  SELECT id FROM (
    SELECT id, ROW_NUMBER() OVER (
      PARTITION BY item_id, date_trunc('hour', recorded_at)
      ORDER BY COALESCE(confidence, 0) DESC, id ASC
    ) AS rn
    FROM market_price_snapshots
    WHERE item_id IS NOT NULL
  ) ranked
  WHERE rn > 1
);

-- Truncate recorded_at to hour for existing data
UPDATE market_price_snapshots
  SET recorded_at = date_trunc('hour', recorded_at)
  WHERE recorded_at != date_trunc('hour', recorded_at);

-- One snapshot per item per hour (enables ON CONFLICT for finalization)
CREATE UNIQUE INDEX IF NOT EXISTS idx_mps_item_hour_unique
  ON market_price_snapshots (item_id, recorded_at)
  WHERE item_id IS NOT NULL;

COMMIT;
