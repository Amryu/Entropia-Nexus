-- Migration: Convert WaveEvent from LocationType to AreaType
-- Description: WaveEvent locations are conceptually areas (like MobArea/LandArea).
--   This migration moves them from Locations.Type='WaveEvent' to
--   Locations.Type='Area' + Areas.Type='WaveEvent', so they share the Area
--   extension table and can have polygon shapes on the map.
--   The WaveEventWaves table and its FK are unchanged.
--   'WaveEvent' is intentionally left in the LocationType enum — removing a
--   PostgreSQL enum value requires recreating the type and is destructive.
-- Database: nexus
-- Date: 2026-03-11
-- IDEMPOTENT: Safe to re-run

BEGIN;

-- Step 1: Add 'WaveEvent' to the AreaType enum
ALTER TYPE "AreaType" ADD VALUE IF NOT EXISTS 'WaveEvent';

-- Step 2: Migrate Locations.Type = 'WaveEvent' → 'Area'
UPDATE ONLY "Locations"
  SET "Type" = 'Area'
  WHERE "Type" = 'WaveEvent';

-- Step 3: Create Areas rows for the migrated locations (idempotent via ON CONFLICT)
INSERT INTO "Areas" ("LocationId", "Type", "Shape", "Data")
SELECT l."Id", 'WaveEvent'::"AreaType", 'Point'::"Shape", '{}'::jsonb
FROM ONLY "Locations" l
WHERE l."Type" = 'Area'
  AND NOT EXISTS (
    SELECT 1 FROM ONLY "Areas" a WHERE a."LocationId" = l."Id"
  )
  AND EXISTS (
    SELECT 1 FROM ONLY "WaveEventWaves" w WHERE w."LocationId" = l."Id"
  )
ON CONFLICT ("LocationId") DO NOTHING;

COMMIT;
