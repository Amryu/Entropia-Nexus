-- Performance indexes for globals API endpoints.

-- Location filtering (currently no index, causes seq scan on location autocomplete + filtered stats)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ingested_globals_location
  ON ingested_globals (location) WHERE confirmed = true AND location IS NOT NULL;

-- Player + type composite (player detail runs ~12 queries filtered by player_name + global_type)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ingested_globals_player_type
  ON ingested_globals (lower(player_name), global_type) WHERE confirmed = true;

-- Replace non-partial mob_id index with partial (only ~187K confirmed of 1.6M rows)
DROP INDEX IF EXISTS idx_ingested_globals_mob_id;
CREATE INDEX CONCURRENTLY idx_ingested_globals_mob_id
  ON ingested_globals (mob_id) WHERE confirmed = true AND mob_id IS NOT NULL;
