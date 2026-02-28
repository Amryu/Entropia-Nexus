-- Add mob/maturity resolution columns and extra metadata to ingested_globals.
-- mob_id and maturity_id reference Mobs/MobMaturities in the nexus DB (cross-DB, not FK-constrained).
-- extra stores optional metadata (e.g., tier level for "tier" type globals).

ALTER TABLE ingested_globals ADD COLUMN mob_id integer;
ALTER TABLE ingested_globals ADD COLUMN maturity_id integer;
ALTER TABLE ingested_globals ADD COLUMN extra jsonb;

-- Efficient querying indexes
CREATE INDEX idx_ingested_globals_mob_id ON ingested_globals (mob_id) WHERE mob_id IS NOT NULL;
CREATE INDEX idx_ingested_globals_type_ts ON ingested_globals (global_type, event_timestamp DESC);
CREATE INDEX idx_ingested_globals_player ON ingested_globals (lower(player_name), event_timestamp DESC);
CREATE INDEX idx_ingested_globals_confirmed_ts ON ingested_globals (event_timestamp DESC) WHERE confirmed = true;
