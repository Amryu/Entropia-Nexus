-- Market price fraud detection: outlier scoring, user indexing, permanent retention.
--
-- Adds fraud_flags (JSONB) and outlier_score (real) to submissions for inline
-- fraud scoring. Adds indexes for user-based lookups (purge, per-user analysis)
-- and high-outlier queries. Submissions are now kept indefinitely (the 3-day
-- auto-delete is removed in application code).

BEGIN;

-- Fraud scoring columns on submissions
ALTER TABLE market_price_submissions
  ADD COLUMN IF NOT EXISTS fraud_flags jsonb,
  ADD COLUMN IF NOT EXISTS outlier_score real;

-- User-based lookups (purge + fraud analysis)
CREATE INDEX IF NOT EXISTS idx_mp_sub_user
  ON market_price_submissions (submitted_by);

-- High outlier scores for admin review
CREATE INDEX IF NOT EXISTS idx_mp_sub_outlier
  ON market_price_submissions (outlier_score DESC)
  WHERE outlier_score > 0.5;

COMMIT;
