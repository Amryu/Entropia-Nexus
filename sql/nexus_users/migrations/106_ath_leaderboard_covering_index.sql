-- Covering index for ATH leaderboard full rebuilds.
-- Includes all columns needed by the aggregation query so PostgreSQL
-- can use an index-only scan instead of a sequential heap scan on 3M+ rows.
CREATE INDEX CONCURRENTLY idx_ingested_globals_ath_cover
  ON ingested_globals (global_type, player_name, target_name, mob_id, value)
  WHERE confirmed = true;
