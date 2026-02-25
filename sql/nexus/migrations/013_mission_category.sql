-- Migration: Add MissionCategory enum, Removed column, MagicalFlower location type
-- Description: New columns and types for mission data import
-- Database: nexus
-- Date: 2026-02-09

BEGIN;

-- ===========================================
-- PHASE 1: CREATE MISSIONCATEGORY ENUM
-- ===========================================

DO $$ BEGIN
  CREATE TYPE "MissionCategory" AS ENUM (
    'Hunting',
    'Mining',
    'Crafting',
    'Exploring',
    'Dialog',
    'Instance',
    'Collecting',
    'Training',
    'Operation',
    'PvP',
    'Challenge',
    'HandIn',
    'Story',
    'Sweating',
    'Event'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ===========================================
-- PHASE 2: ADD NEW COLUMNS TO MISSIONS
-- ===========================================

ALTER TABLE "Missions" ADD COLUMN IF NOT EXISTS "Category" "MissionCategory";
ALTER TABLE "Missions" ADD COLUMN IF NOT EXISTS "Removed" BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN "Missions"."Category" IS 'Primary activity category of the mission (Hunting, Mining, Crafting, etc.)';
COMMENT ON COLUMN "Missions"."Removed" IS 'Whether this mission has been removed from the game';

-- ===========================================
-- PHASE 3: ADD MAGICALFLOWER TO LOCATIONTYPE ENUM
-- ===========================================

ALTER TYPE "LocationType" ADD VALUE IF NOT EXISTS 'MagicalFlower';

-- ===========================================
-- PHASE 4: RECREATE MISSIONS AUDIT TABLE
-- ===========================================
-- Column order must match main table for INSERT ... SELECT OLD.* to work

DROP TRIGGER IF EXISTS "Missions_audit_trigger" ON "Missions";
DROP TABLE IF EXISTS "Missions_audit";

CREATE TABLE "Missions_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "Id" INTEGER NOT NULL,
  "Name" TEXT NOT NULL,
  "PlanetId" INTEGER,
  "MissionChainId" INTEGER,
  "Type" "MissionType" NOT NULL,
  "Description" TEXT,
  "CooldownDuration" INTERVAL,
  "EventId" INTEGER,
  "CooldownStartsOn" "CooldownStartsOn",
  "StartLocationId" INTEGER,
  "Category" "MissionCategory",
  "Removed" BOOLEAN NOT NULL DEFAULT false
);

ALTER TABLE "Missions_audit" INHERIT "Missions";

CREATE OR REPLACE FUNCTION "Missions_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "Missions_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "Missions_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "Missions_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

CREATE TRIGGER "Missions_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "Missions"
  FOR EACH ROW EXECUTE FUNCTION "Missions_audit_trigger"();

-- Seed audit table with current data (only if empty)
INSERT INTO "Missions_audit"
SELECT 'I', now(), current_user, * FROM ONLY "Missions"
WHERE NOT EXISTS (SELECT 1 FROM "Missions_audit" LIMIT 1);

-- ===========================================
-- PHASE 5: GRANTS
-- ===========================================

GRANT SELECT ON "Missions_audit" TO "nexus";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Missions_audit" TO nexus_bot;

COMMIT;
