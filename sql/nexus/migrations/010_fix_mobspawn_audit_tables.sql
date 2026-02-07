-- Migration: Fix MobSpawns and MobSpawnMaturities audit tables
-- Description: Fix column structure after 005_locations_rework and update coordinates trigger
-- Database: nexus
-- Date: 2026-02-06
-- IDEMPOTENT: This script can be safely re-run

BEGIN;

-- ===========================================
-- PHASE 1: FIX AUDIT TABLES
-- ===========================================

-- Remove inheritance first
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"MobSpawns_audit"'::regclass) THEN
    ALTER TABLE "MobSpawns_audit" NO INHERIT "MobSpawns";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"MobSpawnMaturities_audit"'::regclass) THEN
    ALTER TABLE "MobSpawnMaturities_audit" NO INHERIT "MobSpawnMaturities";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- Fix MobSpawns_audit: copy LocationId to AreaId, drop LocationId, rename AreaId to LocationId
DO $$
BEGIN
  -- Copy LocationId values to AreaId first (preserve any new data)
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'LocationId')
     AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'AreaId') THEN
    UPDATE "MobSpawns_audit" SET "AreaId" = "LocationId" WHERE "LocationId" IS NOT NULL;
  END IF;
  -- Drop the new LocationId column
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'LocationId') THEN
    ALTER TABLE "MobSpawns_audit" DROP COLUMN "LocationId";
  END IF;
  -- Rename AreaId to LocationId
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'AreaId') THEN
    ALTER TABLE "MobSpawns_audit" RENAME COLUMN "AreaId" TO "LocationId";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- Fix MobSpawnMaturities_audit: copy LocationId to AreaId, drop LocationId, rename AreaId to LocationId
DO $$
BEGIN
  -- Copy LocationId values to AreaId first (preserve any new data)
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'LocationId')
     AND EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'AreaId') THEN
    UPDATE "MobSpawnMaturities_audit" SET "AreaId" = "LocationId" WHERE "LocationId" IS NOT NULL;
  END IF;
  -- Drop the new LocationId column
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'LocationId') THEN
    ALTER TABLE "MobSpawnMaturities_audit" DROP COLUMN "LocationId";
  END IF;
  -- Rename AreaId to LocationId
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'AreaId') THEN
    ALTER TABLE "MobSpawnMaturities_audit" RENAME COLUMN "AreaId" TO "LocationId";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- Re-add inheritance
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"MobSpawns_audit"'::regclass) THEN
    ALTER TABLE "MobSpawns_audit" INHERIT "MobSpawns";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"MobSpawnMaturities_audit"'::regclass) THEN
    ALTER TABLE "MobSpawnMaturities_audit" INHERIT "MobSpawnMaturities";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- ===========================================
-- PHASE 2: FIX UPDATE_COORDINATES TRIGGER
-- ===========================================
-- The trigger now updates the Locations table instead of Areas
-- since Longitude/Latitude live on Locations (1:1 via Areas.LocationId)

DROP TRIGGER IF EXISTS update_coordinates_trigger ON "Areas";

CREATE OR REPLACE FUNCTION update_coordinates() RETURNS TRIGGER AS $$
DECLARE
  x NUMERIC;
  y NUMERIC;
  data JSONB;
BEGIN
  data := NEW."Data";

  IF NEW."Shape" = 'Circle' THEN
    x := (data->>'x')::NUMERIC;
    y := (data->>'y')::NUMERIC;
  ELSIF NEW."Shape" = 'Rectangle' THEN
    x := ((data->>'x')::NUMERIC + (data->>'width')::NUMERIC / 2);
    y := ((data->>'y')::NUMERIC + (data->>'height')::NUMERIC / 2);
  ELSIF NEW."Shape" = 'Polygon' THEN
    SELECT * INTO x, y FROM furthest_point(data);
  END IF;

  -- Update the corresponding Locations row (1:1 relationship via LocationId)
  UPDATE "Locations"
  SET "Longitude" = x, "Latitude" = y
  WHERE "Id" = NEW."LocationId";

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_coordinates_trigger
  AFTER INSERT OR UPDATE ON "Areas"
  FOR EACH ROW EXECUTE FUNCTION update_coordinates();

COMMIT;
