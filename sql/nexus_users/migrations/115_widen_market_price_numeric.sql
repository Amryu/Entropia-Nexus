-- Widen numeric columns from numeric(12,4) to numeric(16,4) to support
-- sales counts exceeding 100 million (e.g. sales_3650d for popular items).

BEGIN;

-- market_price_submissions
ALTER TABLE market_price_submissions
  ALTER COLUMN markup_1d TYPE numeric(16,4),
  ALTER COLUMN sales_1d TYPE numeric(16,4),
  ALTER COLUMN markup_7d TYPE numeric(16,4),
  ALTER COLUMN sales_7d TYPE numeric(16,4),
  ALTER COLUMN markup_30d TYPE numeric(16,4),
  ALTER COLUMN sales_30d TYPE numeric(16,4),
  ALTER COLUMN markup_365d TYPE numeric(16,4),
  ALTER COLUMN sales_365d TYPE numeric(16,4),
  ALTER COLUMN markup_3650d TYPE numeric(16,4),
  ALTER COLUMN sales_3650d TYPE numeric(16,4);

-- market_price_snapshots
ALTER TABLE market_price_snapshots
  ALTER COLUMN markup_1d TYPE numeric(16,4),
  ALTER COLUMN sales_1d TYPE numeric(16,4),
  ALTER COLUMN markup_7d TYPE numeric(16,4),
  ALTER COLUMN sales_7d TYPE numeric(16,4),
  ALTER COLUMN markup_30d TYPE numeric(16,4),
  ALTER COLUMN sales_30d TYPE numeric(16,4),
  ALTER COLUMN markup_365d TYPE numeric(16,4),
  ALTER COLUMN sales_365d TYPE numeric(16,4),
  ALTER COLUMN markup_3650d TYPE numeric(16,4),
  ALTER COLUMN sales_3650d TYPE numeric(16,4);

COMMIT;
