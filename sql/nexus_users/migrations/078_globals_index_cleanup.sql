-- Migration: Optimize ingested_globals indexes
-- Database: nexus_users
--
-- Analysis (production, March 2026):
--   Table: ~1.5M rows, 470 MB data, 550 MB indexes (1.8x the data)
--   All 21 web-facing queries filter on confirmed = true
--
-- Changes:
--   1. Drop redundant idx_ingested_globals_hash_ts (151 MB saved)
--      → fully covered by idx_ingested_globals_hash_occ_ts (content_hash, occurrence, event_timestamp)
--   2. Replace idx_ingested_globals_player (72 MB) with partial WHERE confirmed = true
--   3. Replace idx_ingested_globals_type_ts (46 MB) with partial WHERE confirmed = true
--   4. Add missing target index for target profile pages (currently seq-scanning)
--
-- Estimated savings: ~270+ MB of index space after VACUUM

-- 1. Drop redundant hash index
--    idx_ingested_globals_hash_occ_ts covers all queries that used hash_ts,
--    since occurrence defaults to 1 and the query always includes it.
DROP INDEX IF EXISTS idx_ingested_globals_hash_ts;

-- 2. Replace player index with partial (confirmed-only) version
--    All web queries filter on confirmed = true. The ingestion pipeline
--    does not query by player_name, so the full index is unnecessary.
DROP INDEX IF EXISTS idx_ingested_globals_player;
CREATE INDEX idx_ingested_globals_player
  ON ingested_globals (lower(player_name), event_timestamp DESC)
  WHERE confirmed = true;

-- 3. Replace type+timestamp index with partial (confirmed-only) version
--    Same rationale: all web queries filter confirmed = true.
--    The ingestion pipeline queries by content_hash/first_seen_at, not by type.
DROP INDEX IF EXISTS idx_ingested_globals_type_ts;
CREATE INDEX idx_ingested_globals_type_ts
  ON ingested_globals (global_type, event_timestamp DESC)
  WHERE confirmed = true;

-- 4. Add target index for target profile pages
--    Target queries (lower(target_name) = lower($1) AND confirmed = true)
--    currently do sequential scans. This partial index covers them.
CREATE INDEX idx_ingested_globals_target
  ON ingested_globals (lower(target_name), event_timestamp DESC)
  WHERE confirmed = true;
