-- Migration: Add ON DELETE CASCADE to MobSpawns and MobSpawnMaturities → Locations FKs
-- Description: When a MobArea Location is deleted, its MobSpawns and MobSpawnMaturities
--   should be automatically removed. The Areas → Locations FK already cascades (migration 005),
--   but MobSpawns and MobSpawnMaturities were added without ON DELETE CASCADE.
-- Database: nexus
-- Date: 2026-03-11

BEGIN;

-- Re-add MobSpawns → Locations FK with ON DELETE CASCADE
ALTER TABLE "MobSpawns"
  DROP CONSTRAINT IF EXISTS "MobSpawns_LocationId_fkey";

ALTER TABLE "MobSpawns"
  ADD CONSTRAINT "MobSpawns_LocationId_fkey"
  FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id") ON DELETE CASCADE;

-- Re-add MobSpawnMaturities → Locations FK with ON DELETE CASCADE
ALTER TABLE "MobSpawnMaturities"
  DROP CONSTRAINT IF EXISTS "MobSpawnMaturities_LocationId_fkey";

ALTER TABLE "MobSpawnMaturities"
  ADD CONSTRAINT "MobSpawnMaturities_LocationId_fkey"
  FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id") ON DELETE CASCADE;

COMMIT;
