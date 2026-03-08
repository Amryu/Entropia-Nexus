-- Add confidence column to market_price_snapshots
-- Stores combined OCR confidence score (0.0-1.0) for quality filtering

ALTER TABLE market_price_snapshots
  ADD COLUMN IF NOT EXISTS confidence numeric(4,3);
