-- Migration: Fix audit table column order
-- Description: Move LocationId to end of audit tables to match main table column order
-- Database: nexus
-- Date: 2026-02-06
-- IDEMPOTENT: This script can be safely re-run

BEGIN;

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

-- Fix MobSpawns_audit: move LocationId to end
DO $$
BEGIN
  -- Rename current LocationId to temp
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'LocationId')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'LocationId_old') THEN
    ALTER TABLE "MobSpawns_audit" RENAME COLUMN "LocationId" TO "LocationId_old";
  END IF;
  -- Create new LocationId column at end
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'LocationId') THEN
    ALTER TABLE "MobSpawns_audit" ADD COLUMN "LocationId" INTEGER;
  END IF;
  -- Copy data from old to new
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'LocationId_old') THEN
    UPDATE "MobSpawns_audit" SET "LocationId" = "LocationId_old" WHERE "LocationId" IS NULL;
  END IF;
  -- Drop old column
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'LocationId_old') THEN
    ALTER TABLE "MobSpawns_audit" DROP COLUMN "LocationId_old";
  END IF;
  -- Set NOT NULL (required for inheritance since parent has PK on LocationId)
  ALTER TABLE "MobSpawns_audit" ALTER COLUMN "LocationId" SET NOT NULL;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- Fix MobSpawnMaturities_audit: move LocationId to end
DO $$
BEGIN
  -- Rename current LocationId to temp
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'LocationId')
     AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'LocationId_old') THEN
    ALTER TABLE "MobSpawnMaturities_audit" RENAME COLUMN "LocationId" TO "LocationId_old";
  END IF;
  -- Create new LocationId column at end
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'LocationId') THEN
    ALTER TABLE "MobSpawnMaturities_audit" ADD COLUMN "LocationId" INTEGER;
  END IF;
  -- Copy data from old to new
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'LocationId_old') THEN
    UPDATE "MobSpawnMaturities_audit" SET "LocationId" = "LocationId_old" WHERE "LocationId" IS NULL;
  END IF;
  -- Drop old column
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities_audit' AND column_name = 'LocationId_old') THEN
    ALTER TABLE "MobSpawnMaturities_audit" DROP COLUMN "LocationId_old";
  END IF;
  -- Set NOT NULL (required for inheritance since parent has PK on LocationId)
  ALTER TABLE "MobSpawnMaturities_audit" ALTER COLUMN "LocationId" SET NOT NULL;
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

COMMIT;
