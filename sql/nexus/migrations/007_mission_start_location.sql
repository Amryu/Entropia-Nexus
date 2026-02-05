-- Migration: Add StartLocationId to Missions
-- Description: Add optional reference to a Location where the mission starts
-- Database: nexus
-- Date: 2026-02-05

BEGIN;

-- Add StartLocationId column to Missions table
ALTER TABLE "Missions"
ADD COLUMN "StartLocationId" INTEGER REFERENCES "Locations"("Id");

CREATE INDEX idx_missions_startlocationid ON "Missions"("StartLocationId");

COMMENT ON COLUMN "Missions"."StartLocationId" IS 'Reference to the location where this mission starts (e.g., NPC location, teleporter). Nullable.';

COMMIT;
