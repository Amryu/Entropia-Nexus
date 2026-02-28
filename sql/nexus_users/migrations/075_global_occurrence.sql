-- Migration: Add occurrence column for client-side duplicate disambiguation
-- Database: nexus_users
--
-- When a player gets identical globals in quick succession (same mob, same value),
-- the client marks them as occurrence 1, 2, 3. The server uses content_hash + occurrence
-- for deduplication instead of timestamp proximity guessing.

ALTER TABLE ingested_globals ADD COLUMN occurrence integer NOT NULL DEFAULT 1;

ALTER TABLE ingested_globals ADD CONSTRAINT chk_occurrence_range
  CHECK (occurrence BETWEEN 1 AND 3);

-- Composite index for the exact match query: content_hash + occurrence + timestamp window
CREATE INDEX idx_ingested_globals_hash_occ_ts
  ON ingested_globals (content_hash, occurrence, event_timestamp);
