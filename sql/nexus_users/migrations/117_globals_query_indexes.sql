-- Optimize the heaviest globals query patterns.

-- 1. Top loots per player: the query scans by (global_type, value DESC) and
--    filters by player_name, scanning millions of rows for a single player.
--    This covering index lets Postgres seek directly to the player's events
--    sorted by value, turning a ~1s query into a few ms.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ingested_globals_player_type_value
  ON ingested_globals (lower(player_name), global_type, value DESC)
  WHERE confirmed = true;

-- 2. Enable trigram extension for ILIKE index support on agg tables.
--    Search/autocomplete queries do player_name ILIKE '%query%' which
--    requires a full table scan without trigram indexes.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 3. Trigram indexes on agg tables for ILIKE search (~96K and ~33K rows).
--    These replace ILIKE scans on the 6.6M-row raw table.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_globals_player_agg_name_trgm
  ON globals_player_agg USING gin (player_name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_globals_target_agg_name_trgm
  ON globals_target_agg USING gin (target_name gin_trgm_ops);
