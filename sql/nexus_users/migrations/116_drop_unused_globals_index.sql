-- Drop the ATH covering index on ingested_globals.
-- This index is 760MB and only had 456 scans since last reset.
-- The ATH leaderboard is now pre-built in globals_ath_leaderboard,
-- and neither full nor incremental rebuilds use this index
-- (full rebuild does Seq Scan, incremental uses idx_ingested_globals_confirmed_at).
-- The fallback CTE ranking queries also don't use it (they use player_type index).

DROP INDEX IF EXISTS idx_ingested_globals_ath_cover;
