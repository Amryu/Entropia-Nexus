-- Trigram index on location for fuzzy autocomplete in the globals search.
-- Before this, /api/globals/locations did ILIKE '%query%' which couldn't use
-- the existing btree idx_ingested_globals_location and fell back to a seq
-- scan. The gin_trgm_ops index supports both ILIKE and the % similarity
-- operator, matching the indexing already in place on player/target names
-- (migration 117).

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ingested_globals_location_trgm
  ON ingested_globals USING gin (location gin_trgm_ops)
  WHERE confirmed = true AND location IS NOT NULL;
