-- Migration: Locations System Rework
-- Description: Consolidate Teleporters, NPCs, Interactables, Areas, Estates into unified Locations table
-- Database: nexus
-- Date: 2026-02-05
-- IDEMPOTENT: This script can be safely re-run
-- TRANSACTIONAL: Entire migration runs in a single transaction - all or nothing

BEGIN;

-- ===========================================
-- PHASE 1: DROP EXISTING LOCATIONS VIEW AND CREATE NEW TABLES
-- ===========================================

-- Drop the existing Locations VIEW if it exists (union of Teleporters, Areas, etc with ID offsets)
-- Note: Only drop if it's a VIEW, not if it's already the TABLE from a previous run
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_name = 'Locations' AND table_schema = 'public'
  ) THEN
    DROP VIEW "Locations";
  END IF;
END $$;

-- Create LocationType enum (if not exists)
DO $$ BEGIN
  CREATE TYPE "LocationType" AS ENUM (
    'Teleporter',
    'Npc',
    'Interactable',
    'Area',
    'Estate',
    'Outpost',
    'Camp',
    'City',
    'WaveEvent'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Create unified Locations table
CREATE TABLE IF NOT EXISTS "Locations" (
  "Id" SERIAL PRIMARY KEY,
  "OriginalId" INTEGER,  -- Stores the original ID from source table (no uniqueness constraint - IDs can overlap between types)
  "Name" TEXT NOT NULL,
  "Type" "LocationType" NOT NULL,
  "Description" TEXT,
  "PlanetId" INTEGER REFERENCES "Planets"("Id"),
  "Longitude" INTEGER,
  "Latitude" INTEGER,
  "Altitude" INTEGER,
  "ParentLocationId" INTEGER,
  "TechnicalId" TEXT
);

-- Add OriginalId column if table already exists but column doesn't
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Locations' AND column_name = 'OriginalId' AND table_schema = 'public') THEN
    ALTER TABLE "Locations" ADD COLUMN "OriginalId" INTEGER;
  END IF;
END $$;

-- Index for looking up by OriginalId + Type (for backwards compatibility lookups)
CREATE INDEX IF NOT EXISTS idx_locations_originalid_type ON "Locations"("OriginalId", "Type") WHERE "OriginalId" IS NOT NULL;

-- Add self-reference constraint (if not exists)
DO $$ BEGIN
  ALTER TABLE "Locations"
    ADD CONSTRAINT "Locations_ParentLocationId_fkey"
    FOREIGN KEY ("ParentLocationId") REFERENCES "Locations"("Id") ON DELETE SET NULL;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Create indexes for Locations (IF NOT EXISTS)
CREATE INDEX IF NOT EXISTS idx_locations_type ON "Locations"("Type");
CREATE INDEX IF NOT EXISTS idx_locations_planetid ON "Locations"("PlanetId");
CREATE INDEX IF NOT EXISTS idx_locations_name ON "Locations"("Name");
CREATE INDEX IF NOT EXISTS idx_locations_parent ON "Locations"("ParentLocationId") WHERE "ParentLocationId" IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_locations_technicalid ON "Locations"("TechnicalId") WHERE "TechnicalId" IS NOT NULL;

-- Create Facilities table
CREATE TABLE IF NOT EXISTS "Facilities" (
  "Id" SERIAL PRIMARY KEY,
  "Name" TEXT NOT NULL UNIQUE,
  "Description" TEXT,
  "Icon" TEXT
);

-- Seed standard facilities (ON CONFLICT to be idempotent)
INSERT INTO "Facilities" ("Name", "Description") VALUES
  ('Trade Terminal', 'Has trade terminals'),
  ('Repair Terminal', 'Has repair terminals'),
  ('Storage', 'Has storage terminals'),
  ('Auctioneer', 'Has auction access'),
  ('Technician', 'Has technician NPC/terminal'),
  ('Revival Terminal', 'Serves as revival location'),
  ('Construction Terminal', 'Serves as construction location')
ON CONFLICT ("Name") DO NOTHING;

-- Create LocationFacilities junction table
CREATE TABLE IF NOT EXISTS "LocationFacilities" (
  "LocationId" INTEGER NOT NULL,
  "FacilityId" INTEGER NOT NULL REFERENCES "Facilities"("Id") ON DELETE CASCADE,
  PRIMARY KEY ("LocationId", "FacilityId")
);

CREATE INDEX IF NOT EXISTS idx_locationfacilities_facilityid ON "LocationFacilities"("FacilityId");

-- Create WaveEventWaves table for WaveEvent type
CREATE TABLE IF NOT EXISTS "WaveEventWaves" (
  "Id" SERIAL PRIMARY KEY,
  "LocationId" INTEGER NOT NULL REFERENCES "Locations"("Id") ON DELETE CASCADE,
  "WaveIndex" INTEGER NOT NULL,
  "TimeToComplete" INTEGER,
  "MobMaturities" JSONB DEFAULT '[]'::jsonb,
  UNIQUE ("LocationId", "WaveIndex")
);

CREATE INDEX IF NOT EXISTS idx_waveeventwaves_locationid ON "WaveEventWaves"("LocationId");

-- ===========================================
-- PHASE 2: MIGRATE DATA
-- ===========================================
-- Note: OriginalId stores the source table's Id for backwards compatibility lookups
-- The new auto-generated Id is used for all foreign key references

-- Only migrate if Teleporters table exists and data hasn't been migrated yet
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'Teleporters' AND table_schema = 'public')
     AND NOT EXISTS (SELECT 1 FROM "Locations" WHERE "Type" = 'Teleporter' LIMIT 1) THEN

    -- 2a. Migrate Teleporters to Locations (include OriginalId)
    INSERT INTO "Locations" ("OriginalId", "Name", "Type", "Description", "PlanetId", "Longitude", "Latitude", "Altitude")
    SELECT "Id", "Name", 'Teleporter'::"LocationType", "Description", "PlanetId", "Longitude", "Latitude", "Altitude"
    FROM "Teleporters";
  END IF;
END $$;

-- Create mapping table for Teleporter ID translation using OriginalId
DROP TABLE IF EXISTS "_migration_teleporter_map";
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'Teleporters' AND table_schema = 'public') THEN
    CREATE TABLE "_migration_teleporter_map" AS
    SELECT l."OriginalId" AS "OldId", l."Id" AS "NewId"
    FROM "Locations" l
    WHERE l."Type" = 'Teleporter' AND l."OriginalId" IS NOT NULL;
  ELSE
    CREATE TABLE "_migration_teleporter_map" ("OldId" INTEGER, "NewId" INTEGER);
  END IF;
END $$;

-- Only migrate NPCs if table exists and data hasn't been migrated yet
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'Npcs' AND table_schema = 'public')
     AND NOT EXISTS (SELECT 1 FROM "Locations" WHERE "Type" = 'Npc' LIMIT 1) THEN

    INSERT INTO "Locations" ("OriginalId", "Name", "Type", "Description", "PlanetId", "Longitude", "Latitude", "Altitude")
    SELECT "Id", "Name", 'Npc'::"LocationType", "Description", "PlanetId", "Longitude", "Latitude", "Altitude"
    FROM "Npcs";
  END IF;
END $$;

DROP TABLE IF EXISTS "_migration_npc_map";
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'Npcs' AND table_schema = 'public') THEN
    CREATE TABLE "_migration_npc_map" AS
    SELECT l."OriginalId" AS "OldId", l."Id" AS "NewId"
    FROM "Locations" l
    WHERE l."Type" = 'Npc' AND l."OriginalId" IS NOT NULL;
  ELSE
    CREATE TABLE "_migration_npc_map" ("OldId" INTEGER, "NewId" INTEGER);
  END IF;
END $$;

-- Only migrate Interactables if table exists and data hasn't been migrated yet
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'Interactables' AND table_schema = 'public')
     AND NOT EXISTS (SELECT 1 FROM "Locations" WHERE "Type" = 'Interactable' LIMIT 1) THEN

    INSERT INTO "Locations" ("OriginalId", "Name", "Type", "Description", "PlanetId", "Longitude", "Latitude", "Altitude")
    SELECT "Id", "Name", 'Interactable'::"LocationType", "Description", "PlanetId", "Longitude", "Latitude", "Altitude"
    FROM "Interactables";
  END IF;
END $$;

DROP TABLE IF EXISTS "_migration_interactable_map";
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'Interactables' AND table_schema = 'public') THEN
    CREATE TABLE "_migration_interactable_map" AS
    SELECT l."OriginalId" AS "OldId", l."Id" AS "NewId"
    FROM "Locations" l
    WHERE l."Type" = 'Interactable' AND l."OriginalId" IS NOT NULL;
  ELSE
    CREATE TABLE "_migration_interactable_map" ("OldId" INTEGER, "NewId" INTEGER);
  END IF;
END $$;

-- Only migrate Areas if "Id" column still exists (not yet converted to extension table)
-- IMPORTANT: Use ONLY to exclude inherited audit table rows
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Areas' AND column_name = 'Id' AND table_schema = 'public')
     AND NOT EXISTS (SELECT 1 FROM "Locations" WHERE "Type" = 'Area' LIMIT 1) THEN

    INSERT INTO "Locations" ("OriginalId", "Name", "Type", "Description", "PlanetId", "Longitude", "Latitude", "Altitude", "TechnicalId")
    SELECT "Id", "Name", 'Area'::"LocationType", NULL, "PlanetId", "Longitude", "Latitude", "Altitude", "TechnicalId"
    FROM ONLY "Areas";
  END IF;
END $$;

-- Create mapping using OriginalId (guaranteed unique per type)
DROP TABLE IF EXISTS "_migration_area_map";
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Areas' AND column_name = 'Id' AND table_schema = 'public') THEN
    CREATE TABLE "_migration_area_map" AS
    SELECT l."OriginalId" AS "OldId", l."Id" AS "NewId"
    FROM "Locations" l
    WHERE l."Type" = 'Area' AND l."OriginalId" IS NOT NULL;
  ELSE
    CREATE TABLE "_migration_area_map" ("OldId" INTEGER, "NewId" INTEGER);
  END IF;
END $$;

-- Only migrate Estates if "Id" column still exists (not yet converted to extension table)
-- IMPORTANT: Use ONLY to exclude inherited audit table rows
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Estates' AND column_name = 'Id' AND table_schema = 'public')
     AND NOT EXISTS (SELECT 1 FROM "Locations" WHERE "Type" = 'Estate' LIMIT 1) THEN

    INSERT INTO "Locations" ("OriginalId", "Name", "Type", "Description", "PlanetId", "Longitude", "Latitude", "Altitude")
    SELECT "Id", "Name", 'Estate'::"LocationType", "Description", "PlanetId", "Longitude", "Latitude", "Altitude"
    FROM ONLY "Estates";
  END IF;
END $$;

-- Create mapping using OriginalId (guaranteed unique per type)
DROP TABLE IF EXISTS "_migration_estate_map";
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Estates' AND column_name = 'Id' AND table_schema = 'public') THEN
    CREATE TABLE "_migration_estate_map" AS
    SELECT l."OriginalId" AS "OldId", l."Id" AS "NewId"
    FROM "Locations" l
    WHERE l."Type" = 'Estate' AND l."OriginalId" IS NOT NULL;
  ELSE
    CREATE TABLE "_migration_estate_map" ("OldId" INTEGER, "NewId" INTEGER);
  END IF;
END $$;

-- ===========================================
-- PHASE 3: CONVERT AREAS AND ESTATES TO EXTENSION TABLES
-- ===========================================

-- 3a. Add LocationId to Areas and populate it
DO $$
BEGIN
  -- Add column if not exists
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Areas' AND column_name = 'LocationId' AND table_schema = 'public') THEN
    ALTER TABLE "Areas" ADD COLUMN "LocationId" INTEGER;
  END IF;

  -- Populate LocationId from mapping (use ONLY to exclude audit table rows)
  -- This runs even if column exists (for re-run after cleanup)
  UPDATE ONLY "Areas" a
  SET "LocationId" = m."NewId"
  FROM "_migration_area_map" m
  WHERE a."Id" = m."OldId"
    AND a."LocationId" IS DISTINCT FROM m."NewId";
END $$;

-- 3b. Add LocationId to Estates and populate it
DO $$
BEGIN
  -- Add column if not exists
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Estates' AND column_name = 'LocationId' AND table_schema = 'public') THEN
    ALTER TABLE "Estates" ADD COLUMN "LocationId" INTEGER;
  END IF;

  -- Populate LocationId from mapping (use ONLY to exclude audit table rows)
  -- This runs even if column exists (for re-run after cleanup)
  UPDATE ONLY "Estates" e
  SET "LocationId" = m."NewId"
  FROM "_migration_estate_map" m
  WHERE e."Id" = m."OldId"
    AND e."LocationId" IS DISTINCT FROM m."NewId";
END $$;

-- 3c. Add foreign key constraints (if not exist)
DO $$ BEGIN
  ALTER TABLE "LocationFacilities"
    ADD CONSTRAINT "LocationFacilities_LocationId_fkey"
    FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id") ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  ALTER TABLE "WaveEventWaves"
    ADD CONSTRAINT "WaveEventWaves_LocationId_fkey"
    FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id") ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ===========================================
-- PHASE 4: UPDATE FOREIGN KEY REFERENCES
-- ===========================================

-- 4a. Update MobSpawns to use LocationId instead of AreaId
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns' AND column_name = 'LocationId' AND table_schema = 'public') THEN
    ALTER TABLE "MobSpawns" ADD COLUMN "LocationId" INTEGER;

    UPDATE "MobSpawns" ms
    SET "LocationId" = m."NewId"
    FROM "_migration_area_map" m
    WHERE ms."AreaId" = m."OldId";
  END IF;
END $$;

-- Add foreign key constraint
DO $$ BEGIN
  ALTER TABLE "MobSpawns"
    ADD CONSTRAINT "MobSpawns_LocationId_fkey"
    FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 4a2. Update MobSpawnMaturities to use LocationId instead of AreaId
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawnMaturities' AND column_name = 'LocationId' AND table_schema = 'public') THEN
    ALTER TABLE "MobSpawnMaturities" ADD COLUMN "LocationId" INTEGER;

    UPDATE "MobSpawnMaturities" msm
    SET "LocationId" = m."NewId"
    FROM "_migration_area_map" m
    WHERE msm."AreaId" = m."OldId";
  END IF;
END $$;

-- Add foreign key constraint for MobSpawnMaturities
DO $$ BEGIN
  ALTER TABLE "MobSpawnMaturities"
    ADD CONSTRAINT "MobSpawnMaturities_LocationId_fkey"
    FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 4b. Update EstateSections to use LocationId instead of EstateId
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'EstateSections' AND column_name = 'LocationId' AND table_schema = 'public') THEN
    ALTER TABLE "EstateSections" ADD COLUMN "LocationId" INTEGER;

    UPDATE "EstateSections" es
    SET "LocationId" = m."NewId"
    FROM "_migration_estate_map" m
    WHERE es."EstateId" = m."OldId";
  END IF;
END $$;

-- Add foreign key constraint
DO $$ BEGIN
  ALTER TABLE "EstateSections"
    ADD CONSTRAINT "EstateSections_LocationId_fkey"
    FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id") ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ===========================================
-- PHASE 5: UPDATE MISSION OBJECTIVES (JSONB references)
-- ===========================================
-- Note: MissionObjectives has JSONB payload with targetLocationId and npcLocationId
-- These used the old VIEW IDs with offsets. We need to convert them to new direct IDs.
-- These UPDATEs are safe to re-run (idempotent - they only update if old offset IDs exist)

-- Update targetLocationId references (old VIEW IDs -> new Locations IDs)
-- Old format: Teleporter +100000, Area +200000, Estate +300000, NPC +400000, Interactable +500000

-- Teleporter references (IDs 100001-199999)
UPDATE "MissionObjectives" mo
SET "Payload" = jsonb_set("Payload", '{targetLocationId}', to_jsonb(m."NewId"))
FROM "_migration_teleporter_map" m
WHERE (mo."Payload"->>'targetLocationId')::int = m."OldId" + 100000;

-- Area references (IDs 200001-299999)
UPDATE "MissionObjectives" mo
SET "Payload" = jsonb_set("Payload", '{targetLocationId}', to_jsonb(m."NewId"))
FROM "_migration_area_map" m
WHERE (mo."Payload"->>'targetLocationId')::int = m."OldId" + 200000;

-- Estate references (IDs 300001-399999)
UPDATE "MissionObjectives" mo
SET "Payload" = jsonb_set("Payload", '{targetLocationId}', to_jsonb(m."NewId"))
FROM "_migration_estate_map" m
WHERE (mo."Payload"->>'targetLocationId')::int = m."OldId" + 300000;

-- NPC references (IDs 400001-499999)
UPDATE "MissionObjectives" mo
SET "Payload" = jsonb_set("Payload", '{targetLocationId}', to_jsonb(m."NewId"))
FROM "_migration_npc_map" m
WHERE (mo."Payload"->>'targetLocationId')::int = m."OldId" + 400000;

-- Interactable references (IDs 500001-599999)
UPDATE "MissionObjectives" mo
SET "Payload" = jsonb_set("Payload", '{targetLocationId}', to_jsonb(m."NewId"))
FROM "_migration_interactable_map" m
WHERE (mo."Payload"->>'targetLocationId')::int = m."OldId" + 500000;

-- Same for npcLocationId
UPDATE "MissionObjectives" mo
SET "Payload" = jsonb_set("Payload", '{npcLocationId}', to_jsonb(m."NewId"))
FROM "_migration_npc_map" m
WHERE (mo."Payload"->>'npcLocationId')::int = m."OldId" + 400000;

-- ===========================================
-- PHASE 6: DROP OLD TABLES AND COLUMNS
-- ===========================================

-- Drop old MobSpawns.AreaId column (IF EXISTS)
ALTER TABLE "MobSpawns" DROP COLUMN IF EXISTS "AreaId";

-- Drop old MobSpawnMaturities.AreaId column (IF EXISTS)
ALTER TABLE "MobSpawnMaturities" DROP COLUMN IF EXISTS "AreaId";

-- Drop old EstateSections.EstateId column (IF EXISTS)
ALTER TABLE "EstateSections" DROP COLUMN IF EXISTS "EstateId";

-- Drop old tables
DROP TABLE IF EXISTS "Shops" CASCADE;
DROP TABLE IF EXISTS "Shops_audit" CASCADE;
DROP TABLE IF EXISTS "Teleporters_audit" CASCADE;
DROP TABLE IF EXISTS "Teleporters" CASCADE;
DROP TABLE IF EXISTS "Npcs_audit" CASCADE;
DROP TABLE IF EXISTS "Npcs" CASCADE;
DROP TABLE IF EXISTS "Interactables_audit" CASCADE;
DROP TABLE IF EXISTS "Interactables" CASCADE;

-- ===========================================
-- PHASE 7: CLEAN UP AREAS AND ESTATES EXTENSION TABLES
-- ===========================================

-- First, drop inheritance and triggers from audit tables (if they exist)
-- (They will be recreated in Phase 9 with correct structure)
DROP TRIGGER IF EXISTS "Areas_audit_trigger" ON "Areas";
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"Areas_audit"'::regclass) THEN
    ALTER TABLE "Areas_audit" NO INHERIT "Areas";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DROP TRIGGER IF EXISTS "Estates_audit_trigger" ON "Estates";
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"Estates_audit"'::regclass) THEN
    ALTER TABLE "Estates_audit" NO INHERIT "Estates";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

-- Remove columns from Areas that are now in Locations (IF EXISTS)
-- Remaining columns after drops: Type, Shape, Data, LocationId (LocationId was added last in Phase 3)
ALTER TABLE "Areas" DROP CONSTRAINT IF EXISTS "Areas_pkey";
ALTER TABLE "Areas" DROP COLUMN IF EXISTS "Id";
ALTER TABLE "Areas" DROP COLUMN IF EXISTS "Name";
ALTER TABLE "Areas" DROP COLUMN IF EXISTS "Longitude";
ALTER TABLE "Areas" DROP COLUMN IF EXISTS "Latitude";
ALTER TABLE "Areas" DROP COLUMN IF EXISTS "Altitude";
ALTER TABLE "Areas" DROP COLUMN IF EXISTS "PlanetId";
ALTER TABLE "Areas" DROP COLUMN IF EXISTS "TechnicalId";

-- Make LocationId the primary key (if not already)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = '"Areas"'::regclass AND contype = 'p'
  ) THEN
    ALTER TABLE "Areas" ADD PRIMARY KEY ("LocationId");
  END IF;
END $$;

DO $$ BEGIN
  ALTER TABLE "Areas" ADD CONSTRAINT "Areas_LocationId_fkey"
    FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id") ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Remove columns from Estates that are now in Locations (IF EXISTS)
-- Remaining columns after drops: Type, OwnerId, ItemTradeAvailable, MaxGuests, LocationId
ALTER TABLE "Estates" DROP CONSTRAINT IF EXISTS "Estates_pkey";
ALTER TABLE "Estates" DROP COLUMN IF EXISTS "Id";
ALTER TABLE "Estates" DROP COLUMN IF EXISTS "Name";
ALTER TABLE "Estates" DROP COLUMN IF EXISTS "Description";
ALTER TABLE "Estates" DROP COLUMN IF EXISTS "Longitude";
ALTER TABLE "Estates" DROP COLUMN IF EXISTS "Latitude";
ALTER TABLE "Estates" DROP COLUMN IF EXISTS "Altitude";
ALTER TABLE "Estates" DROP COLUMN IF EXISTS "PlanetId";

-- Make LocationId the primary key (if not already)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = '"Estates"'::regclass AND contype = 'p'
  ) THEN
    ALTER TABLE "Estates" ADD PRIMARY KEY ("LocationId");
  END IF;
END $$;

DO $$ BEGIN
  ALTER TABLE "Estates" ADD CONSTRAINT "Estates_LocationId_fkey"
    FOREIGN KEY ("LocationId") REFERENCES "Locations"("Id") ON DELETE CASCADE;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Drop old sequences
DROP SEQUENCE IF EXISTS "Areas_Id_seq";
DROP SEQUENCE IF EXISTS "Estates_Id_seq";

-- ===========================================
-- PHASE 8: CREATE AUDIT TABLES AND TRIGGERS
-- ===========================================

-- Audit table for Locations
CREATE TABLE IF NOT EXISTS "Locations_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "Id" INTEGER NOT NULL,
  "OriginalId" INTEGER,
  "Name" TEXT NOT NULL,
  "Type" "LocationType" NOT NULL,
  "Description" TEXT,
  "PlanetId" INTEGER,
  "Longitude" INTEGER,
  "Latitude" INTEGER,
  "Altitude" INTEGER,
  "ParentLocationId" INTEGER,
  "TechnicalId" TEXT
);

-- Add OriginalId to existing Locations_audit if it doesn't have it
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'Locations_audit' AND column_name = 'OriginalId' AND table_schema = 'public') THEN
    -- Need to drop inheritance, add column, re-add inheritance
    IF EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"Locations_audit"'::regclass) THEN
      ALTER TABLE "Locations_audit" NO INHERIT "Locations";
    END IF;
    ALTER TABLE "Locations_audit" ADD COLUMN "OriginalId" INTEGER;
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"Locations_audit"'::regclass) THEN
    ALTER TABLE "Locations_audit" INHERIT "Locations";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION "Locations_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "Locations_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "Locations_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "Locations_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "Locations_audit_trigger" ON "Locations";
CREATE TRIGGER "Locations_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "Locations"
  FOR EACH ROW EXECUTE FUNCTION "Locations_audit_trigger"();

-- Audit table for Facilities
CREATE TABLE IF NOT EXISTS "Facilities_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "Id" INTEGER NOT NULL,
  "Name" TEXT NOT NULL,
  "Description" TEXT,
  "Icon" TEXT
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"Facilities_audit"'::regclass) THEN
    ALTER TABLE "Facilities_audit" INHERIT "Facilities";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION "Facilities_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "Facilities_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "Facilities_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "Facilities_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "Facilities_audit_trigger" ON "Facilities";
CREATE TRIGGER "Facilities_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "Facilities"
  FOR EACH ROW EXECUTE FUNCTION "Facilities_audit_trigger"();

-- Audit table for LocationFacilities
CREATE TABLE IF NOT EXISTS "LocationFacilities_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "LocationId" INTEGER NOT NULL,
  "FacilityId" INTEGER NOT NULL
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"LocationFacilities_audit"'::regclass) THEN
    ALTER TABLE "LocationFacilities_audit" INHERIT "LocationFacilities";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION "LocationFacilities_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "LocationFacilities_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "LocationFacilities_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "LocationFacilities_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "LocationFacilities_audit_trigger" ON "LocationFacilities";
CREATE TRIGGER "LocationFacilities_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "LocationFacilities"
  FOR EACH ROW EXECUTE FUNCTION "LocationFacilities_audit_trigger"();

-- Audit table for WaveEventWaves
CREATE TABLE IF NOT EXISTS "WaveEventWaves_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "Id" INTEGER NOT NULL,
  "LocationId" INTEGER NOT NULL,
  "WaveIndex" INTEGER NOT NULL,
  "TimeToComplete" INTEGER,
  "MobMaturities" JSONB
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"WaveEventWaves_audit"'::regclass) THEN
    ALTER TABLE "WaveEventWaves_audit" INHERIT "WaveEventWaves";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION "WaveEventWaves_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "WaveEventWaves_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "WaveEventWaves_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "WaveEventWaves_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "WaveEventWaves_audit_trigger" ON "WaveEventWaves";
CREATE TRIGGER "WaveEventWaves_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "WaveEventWaves"
  FOR EACH ROW EXECUTE FUNCTION "WaveEventWaves_audit_trigger"();

-- ===========================================
-- PHASE 9: RECREATE AUDIT TABLES FOR AREAS AND ESTATES
-- ===========================================
-- The audit tables must be recreated because:
-- 1. Column order must match the main table for INSERT ... SELECT OLD.* to work
-- 2. After Phase 7, Areas has columns: Type, Shape, Data, LocationId (LocationId added last in Phase 3)
-- 3. After Phase 7, Estates has columns: Type, OwnerId, ItemTradeAvailable, MaxGuests, LocationId

-- Drop old Areas_audit and recreate with correct column order
DROP TRIGGER IF EXISTS "Areas_audit_trigger" ON "Areas";
DROP TABLE IF EXISTS "Areas_audit";

CREATE TABLE "Areas_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "Type" "AreaType" NOT NULL,
  "Shape" "Shape" NOT NULL,
  "Data" JSONB NOT NULL,
  "LocationId" INTEGER NOT NULL
);

ALTER TABLE "Areas_audit" INHERIT "Areas";

CREATE OR REPLACE FUNCTION "Areas_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "Areas_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "Areas_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "Areas_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

CREATE TRIGGER "Areas_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "Areas"
  FOR EACH ROW EXECUTE FUNCTION "Areas_audit_trigger"();

-- Insert current data into Areas_audit (only if empty)
INSERT INTO "Areas_audit"
SELECT 'I', now(), current_user, * FROM ONLY "Areas"
WHERE NOT EXISTS (SELECT 1 FROM "Areas_audit" LIMIT 1);

-- Drop old Estates_audit and recreate with correct column order
DROP TRIGGER IF EXISTS "Estates_audit_trigger" ON "Estates";
DROP TABLE IF EXISTS "Estates_audit";

CREATE TABLE "Estates_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "Type" "EstateType" NOT NULL,
  "OwnerId" INTEGER,
  "ItemTradeAvailable" BOOLEAN,
  "MaxGuests" INTEGER,
  "LocationId" INTEGER NOT NULL
);

ALTER TABLE "Estates_audit" INHERIT "Estates";

CREATE OR REPLACE FUNCTION "Estates_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "Estates_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "Estates_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "Estates_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

CREATE TRIGGER "Estates_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "Estates"
  FOR EACH ROW EXECUTE FUNCTION "Estates_audit_trigger"();

-- Insert current data into Estates_audit (only if empty)
INSERT INTO "Estates_audit"
SELECT 'I', now(), current_user, * FROM ONLY "Estates"
WHERE NOT EXISTS (SELECT 1 FROM "Estates_audit" LIMIT 1);

-- ===========================================
-- PHASE 10: GRANTS
-- ===========================================

-- Grants for nexus user (read access)
GRANT SELECT ON "Locations" TO "nexus";
GRANT SELECT ON "Locations_audit" TO "nexus";
GRANT SELECT ON "Facilities" TO "nexus";
GRANT SELECT ON "Facilities_audit" TO "nexus";
GRANT SELECT ON "LocationFacilities" TO "nexus";
GRANT SELECT ON "LocationFacilities_audit" TO "nexus";
GRANT SELECT ON "WaveEventWaves" TO "nexus";
GRANT SELECT ON "WaveEventWaves_audit" TO "nexus";
GRANT SELECT ON "Areas" TO "nexus";
GRANT SELECT ON "Areas_audit" TO "nexus";
GRANT SELECT ON "Estates" TO "nexus";
GRANT SELECT ON "Estates_audit" TO "nexus";
GRANT SELECT ON "EstateSections" TO "nexus";

GRANT USAGE, SELECT ON SEQUENCE "Locations_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "Facilities_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "WaveEventWaves_Id_seq" TO "nexus";

-- Grants for nexus-bot user (CRUD access for bot operations)
GRANT SELECT, INSERT, UPDATE, DELETE ON "Locations" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Locations_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Facilities" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Facilities_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "LocationFacilities" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "LocationFacilities_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "WaveEventWaves" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "WaveEventWaves_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Areas" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Areas_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Estates" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Estates_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "EstateSections" TO "nexus-bot";

GRANT USAGE, SELECT ON SEQUENCE "Locations_Id_seq" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "Facilities_Id_seq" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "WaveEventWaves_Id_seq" TO "nexus-bot";

-- ===========================================
-- PHASE 11: CLEANUP MIGRATION TABLES
-- ===========================================

DROP TABLE IF EXISTS "_migration_teleporter_map";
DROP TABLE IF EXISTS "_migration_npc_map";
DROP TABLE IF EXISTS "_migration_interactable_map";
DROP TABLE IF EXISTS "_migration_area_map";
DROP TABLE IF EXISTS "_migration_estate_map";

COMMIT;

-- ===========================================
-- VERIFICATION QUERIES (run manually after migration)
-- ===========================================
-- SELECT "Type", COUNT(*) FROM "Locations" GROUP BY "Type" ORDER BY "Type";
-- SELECT l.*, a."Type" AS "AreaType", a."Shape" FROM "Locations" l JOIN "Areas" a ON l."Id" = a."LocationId" LIMIT 5;
-- SELECT l.*, e."Type" AS "EstateType" FROM "Locations" l JOIN "Estates" e ON l."Id" = e."LocationId" LIMIT 5;
-- SELECT * FROM "Facilities";
