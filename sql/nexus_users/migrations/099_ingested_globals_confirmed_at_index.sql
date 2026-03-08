-- Index on confirmed_at to support incremental ATH leaderboard rebuilds.
-- The leaderboard rebuild now only processes rows confirmed since the last run,
-- avoiding a full scan of 2M+ rows every 15 minutes.

CREATE INDEX CONCURRENTLY idx_ingested_globals_confirmed_at
ON ingested_globals (confirmed_at)
WHERE confirmed = true AND confirmed_at IS NOT NULL;
