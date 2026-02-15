-- Migration 031: Add UNIQUE constraint on MobSpecies.Name
-- Required for the bot's ON CONFLICT upsert logic when creating new species inline.

BEGIN;

-- Drop existing non-unique index, replace with UNIQUE constraint
DROP INDEX IF EXISTS "MobSpecies_name_idx";
ALTER TABLE ONLY "MobSpecies" ADD CONSTRAINT "MobSpecies_Name_key" UNIQUE ("Name");

COMMIT;
