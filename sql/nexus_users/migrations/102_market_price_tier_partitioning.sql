-- Migration: Partition market price data by tier.
-- Snapshots and submissions are now keyed per (item_id, tier, hour)
-- so that different tiers of the same item produce separate snapshots.
-- Database: nexus_users

BEGIN;

-- 1. Snapshots: normalize NULL tier → 0, make NOT NULL
UPDATE market_price_snapshots SET tier = 0 WHERE tier IS NULL;
ALTER TABLE market_price_snapshots ALTER COLUMN tier SET NOT NULL;
ALTER TABLE market_price_snapshots ALTER COLUMN tier SET DEFAULT 0;

-- 2. Snapshots: replace unique index to include tier
DROP INDEX IF EXISTS idx_mps_item_hour_unique;
CREATE UNIQUE INDEX idx_mps_item_tier_hour_unique
  ON market_price_snapshots (item_id, tier, recorded_at)
  WHERE item_id IS NOT NULL;

-- 3. Submissions: normalize NULL tier → 0, make NOT NULL
UPDATE market_price_submissions SET tier = 0 WHERE tier IS NULL;
ALTER TABLE market_price_submissions ALTER COLUMN tier SET NOT NULL;
ALTER TABLE market_price_submissions ALTER COLUMN tier SET DEFAULT 0;

-- 4. Submissions: replace dedup index to include tier
DROP INDEX IF EXISTS idx_mp_sub_dedup;
CREATE UNIQUE INDEX idx_mp_sub_dedup
  ON market_price_submissions (item_id, tier, submitted_by, bucket_hour);

-- 5. Submissions: replace finalization lookup index to include tier
DROP INDEX IF EXISTS idx_mp_sub_item_hour;
CREATE INDEX idx_mp_sub_item_hour
  ON market_price_submissions (item_id, tier, bucket_hour);

COMMIT;
