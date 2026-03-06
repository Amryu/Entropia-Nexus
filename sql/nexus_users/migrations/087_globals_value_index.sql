-- Partial index for top-loots queries: sort globals by value within each type.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_ingested_globals_type_value
  ON ingested_globals (global_type, value DESC)
  WHERE confirmed = true;
