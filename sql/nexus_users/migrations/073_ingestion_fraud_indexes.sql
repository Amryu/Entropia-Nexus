-- Migration: Fraud detection indexes + schema fixes
-- Database: nexus_users

-- Allow NULL value for discovery/tier type globals (e.g., "discovered X" has no PED value)
ALTER TABLE ingested_globals ALTER COLUMN value DROP NOT NULL;

-- Drop useless partial index (WHERE confirmation_count <= 1 doesn't match
-- the dynamic query condition ig.confirmation_count <= gs.weight)
DROP INDEX IF EXISTS idx_ingested_globals_unconfirmed;

-- Drop redundant index (unique constraint on client_id already provides a btree index)
DROP INDEX IF EXISTS idx_ingestion_allowed_client;

-- Index for majority swap: grouping conflicts by (existing_id, conflicting_hash)
CREATE INDEX IF NOT EXISTS idx_ingestion_conflicts_existing
  ON ingestion_conflicts (type, existing_id, conflicting_hash);

-- Composite index for conflict queries filtering by type + time window
CREATE INDEX IF NOT EXISTS idx_ingestion_conflicts_type_created
  ON ingestion_conflicts (type, created_at DESC);

-- Index for fraud detection time-window filters on submissions
CREATE INDEX IF NOT EXISTS idx_ingested_global_subs_submitted
  ON ingested_global_submissions (submitted_at DESC);

-- Index for solo detection: covers JOIN + FILTER on confirmation_count, first_seen_at, is_hof
CREATE INDEX IF NOT EXISTS idx_ingested_globals_confirmation
  ON ingested_globals (id, confirmation_count, first_seen_at, is_hof);

-- GIN index for alert user_ids array lookups (WHERE $1 = ANY(user_ids))
CREATE INDEX IF NOT EXISTS idx_ingestion_alerts_user_ids
  ON ingestion_alerts USING gin (user_ids) WHERE NOT resolved;
