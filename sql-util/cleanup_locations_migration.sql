-- Cleanup script for corrupted Locations migration
-- Run this before re-running 005_locations_rework.sql
-- Issue: Migration ran multiple times creating duplicate Locations

BEGIN;

-- Step 1: Clear LocationId in Areas (to allow re-migration)
UPDATE ONLY "Areas" SET "LocationId" = NULL WHERE "LocationId" IS NOT NULL;

-- Step 2: Clear LocationId in Estates (to allow re-migration)
UPDATE ONLY "Estates" SET "LocationId" = NULL WHERE "LocationId" IS NOT NULL;

-- Step 3: Clear LocationId in MobSpawns (references Area Locations)
UPDATE "MobSpawns" SET "LocationId" = NULL WHERE "LocationId" IS NOT NULL;

-- Step 4: Clear LocationId in MobSpawnMaturities (references Area Locations)
UPDATE "MobSpawnMaturities" SET "LocationId" = NULL WHERE "LocationId" IS NOT NULL;

-- Step 5: Clear LocationId in EstateSections (references Estate Locations)
UPDATE "EstateSections" SET "LocationId" = NULL WHERE "LocationId" IS NOT NULL;

-- Step 6: Clear LocationFacilities (junction table references Locations)
DELETE FROM "LocationFacilities";

-- Step 7: Clear WaveEventWaves (references Locations)
DELETE FROM "WaveEventWaves";

-- Step 8: Delete ALL Locations (duplicates from multiple migration runs)
DELETE FROM "Locations";

-- Step 9: Drop migration mapping tables so they get recreated
DROP TABLE IF EXISTS "_migration_area_map";
DROP TABLE IF EXISTS "_migration_estate_map";
DROP TABLE IF EXISTS "_migration_teleporter_map";
DROP TABLE IF EXISTS "_migration_npc_map";
DROP TABLE IF EXISTS "_migration_interactable_map";

-- Step 10: Reset Locations sequence to 1
SELECT setval('"Locations_Id_seq"', 1, false);

COMMIT;

-- Verify cleanup
SELECT 'Locations count (should be 0):' as check, COUNT(*) FROM "Locations";
SELECT 'Areas LocationId NULL count:' as check, COUNT(*) FROM ONLY "Areas" WHERE "LocationId" IS NULL;
SELECT 'Estates LocationId NULL count:' as check, COUNT(*) FROM ONLY "Estates" WHERE "LocationId" IS NULL;
SELECT 'Next Location Id will be:' as check, currval('"Locations_Id_seq"') as next_id;
