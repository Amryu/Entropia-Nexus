-- Migration 030: Add CanonicalName to Effects + UNIQUE constraint on Name
-- CanonicalName stores the in-game display name for effects.
-- UNIQUE on Name is required for the bot's ON CONFLICT upsert logic.

BEGIN;

ALTER TABLE ONLY "Effects" ADD COLUMN IF NOT EXISTS "CanonicalName" TEXT;

-- Name must be unique for the upsert-by-name pattern used by the bot
ALTER TABLE ONLY "Effects" ADD CONSTRAINT "Effects_Name_key" UNIQUE ("Name");

COMMIT;
