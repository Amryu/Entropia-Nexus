-- Add gender dimension to exchange price tracking
-- Enables separate price history for Male/Female variants of Armor, ArmorSet, and Clothing items.
-- Convention: gender = '' for non-gendered items, 'Male'/'Female' for gendered items.

-- Price snapshots (raw 15-min snapshots)
ALTER TABLE exchange_price_snapshots
  ADD COLUMN gender VARCHAR(10) NOT NULL DEFAULT '';

-- Price summaries (pre-computed hourly/daily/weekly aggregates)
ALTER TABLE exchange_price_summaries
  ADD COLUMN gender VARCHAR(10) NOT NULL DEFAULT '';

-- Drop old unique index, recreate with gender
DROP INDEX IF EXISTS exchange_price_summaries_uq;
CREATE UNIQUE INDEX exchange_price_summaries_uq
  ON exchange_price_summaries (item_id, gender, period_type, period_start);

-- New index for gender-filtered snapshot queries
CREATE INDEX exchange_price_snapshots_item_gender_time_idx
  ON exchange_price_snapshots (item_id, gender, recorded_at DESC);
