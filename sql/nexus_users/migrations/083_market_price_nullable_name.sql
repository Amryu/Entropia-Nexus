-- Migration: Make item_name nullable in market_price_snapshots
-- When item_id is resolved, we don't store the name redundantly.
-- item_name is only set for unresolved entries (item_id IS NULL).
-- Database: nexus_users

BEGIN;

ALTER TABLE market_price_snapshots ALTER COLUMN item_name DROP NOT NULL;

-- At least one identifier must be present
ALTER TABLE market_price_snapshots
  ADD CONSTRAINT mps_name_or_id CHECK (item_name IS NOT NULL OR item_id IS NOT NULL);

-- Clear item_name on already-resolved rows (they have item_id set)
UPDATE market_price_snapshots SET item_name = NULL WHERE item_id IS NOT NULL;

COMMIT;
