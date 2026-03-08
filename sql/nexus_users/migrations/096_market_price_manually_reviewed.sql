-- Add manually_reviewed column to market_price_snapshots.
-- Stores a JSON array of field names that were manually reviewed by the user
-- (e.g. ["markup_365d", "item_name"]) when OCR couldn't resolve them.
-- NULL means no manual review was needed.

ALTER TABLE market_price_snapshots
  ADD COLUMN IF NOT EXISTS manually_reviewed jsonb;
