-- Migration: Add case-insensitive index for market price dedup
-- Game displays item names in ALL CAPS; dedup and resolution use LOWER()
-- Database: nexus_users

BEGIN;

CREATE INDEX IF NOT EXISTS idx_mps_item_name_lower
  ON market_price_snapshots (LOWER(item_name), recorded_at DESC)
  WHERE item_name IS NOT NULL;

COMMIT;
