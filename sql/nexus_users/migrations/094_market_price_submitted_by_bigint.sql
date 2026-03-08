-- Migration: Fix submitted_by column type for Discord snowflake IDs
-- Discord snowflakes exceed 32-bit integer range (e.g. 178245652633878528)
-- Database: nexus_users

BEGIN;

ALTER TABLE market_price_snapshots
  ALTER COLUMN submitted_by TYPE bigint;

COMMIT;
