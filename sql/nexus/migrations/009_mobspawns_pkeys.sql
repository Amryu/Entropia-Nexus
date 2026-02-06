-- Migration: Add missing primary keys to MobSpawns and MobSpawnMaturities
-- Description: The 005_locations_rework migration dropped AreaId but forgot to add PKs for LocationId
-- Database: nexus
-- Date: 2026-02-06
-- IDEMPOTENT: This script can be safely re-run

BEGIN;

-- Temporarily remove inheritance from audit tables (they contain NULL LocationId from old records)
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

-- Add PRIMARY KEY to MobSpawns (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = '"MobSpawns"'::regclass AND contype = 'p'
  ) THEN
    ALTER TABLE "MobSpawns" ADD PRIMARY KEY ("LocationId");
  END IF;
END $$;

-- Add PRIMARY KEY to MobSpawnMaturities (if not exists)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = '"MobSpawnMaturities"'::regclass AND contype = 'p'
  ) THEN
    ALTER TABLE "MobSpawnMaturities" ADD PRIMARY KEY ("LocationId", "MaturityId");
  END IF;
END $$;

-- Clean up audit tables: delete old records with NULL LocationId and set NOT NULL
-- These old records used AreaId which no longer exists
DO $$
BEGIN
  DELETE FROM "MobSpawns_audit" WHERE "LocationId" IS NULL;
  ALTER TABLE "MobSpawns_audit" ALTER COLUMN "LocationId" SET NOT NULL;
EXCEPTION WHEN undefined_table THEN NULL;
         WHEN undefined_column THEN NULL;
END $$;

DO $$
BEGIN
  DELETE FROM "MobSpawnMaturities_audit" WHERE "LocationId" IS NULL;
  ALTER TABLE "MobSpawnMaturities_audit" ALTER COLUMN "LocationId" SET NOT NULL;
EXCEPTION WHEN undefined_table THEN NULL;
         WHEN undefined_column THEN NULL;
END $$;

-- Re-add inheritance to audit tables
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
