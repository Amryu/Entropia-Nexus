-- Rename market price period columns: the game's 5th row is a decade (3650d),
-- not a year. Actual periods are: 1d, 7d, 30d, 365d, 3650d.
-- Rename 365d -> 3650d first to avoid name collision, then 90d -> 365d.

ALTER TABLE market_price_snapshots RENAME COLUMN markup_365d TO markup_3650d;
ALTER TABLE market_price_snapshots RENAME COLUMN sales_365d TO sales_3650d;
ALTER TABLE market_price_snapshots RENAME COLUMN markup_90d TO markup_365d;
ALTER TABLE market_price_snapshots RENAME COLUMN sales_90d TO sales_365d;
