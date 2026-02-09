-- Migration: Missions feature tables + NPCs/Interactables + Locations view update
-- Description: Create tables for missions, mission chains, steps, objectives, rewards, events, NPCs, and interactables
-- Database: nexus
-- Date: 2026-02-04

BEGIN;

-- ===========================================
-- MISSION TYPE ENUM
-- ===========================================
-- Types: Regular, Repeatable, Recurring (with cooldown), Event (linked to Events table)

CREATE TYPE "MissionType" AS ENUM ('Regular', 'Repeatable', 'Recurring', 'Event');

-- ===========================================
-- EVENTS TABLE (placeholder for future use)
-- ===========================================

CREATE TABLE "Events" (
    "Id" SERIAL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Description" TEXT,
    "StartDate" TIMESTAMP,
    "EndDate" TIMESTAMP,
    "IsActive" BOOLEAN DEFAULT FALSE
);

COMMENT ON TABLE "Events" IS 'Events table for event-linked missions. Not fully wired up yet.';

-- ===========================================
-- MISSION CHAINS TABLE
-- ===========================================
-- Note: MissionChains are managed through Mission changes, not as separate change type

CREATE TABLE "MissionChains" (
    "Id" SERIAL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "PlanetId" INTEGER REFERENCES "Planets"("Id"),
    "Type" TEXT,
    "Description" TEXT
);

CREATE INDEX idx_missionchains_planetid ON "MissionChains"("PlanetId");
CREATE INDEX idx_missionchains_name ON "MissionChains"("Name");

-- ===========================================
-- MISSIONS TABLE
-- ===========================================

CREATE TABLE "Missions" (
    "Id" SERIAL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "PlanetId" INTEGER REFERENCES "Planets"("Id"),
    "MissionChainId" INTEGER REFERENCES "MissionChains"("Id"),
    "Type" "MissionType" NOT NULL DEFAULT 'Regular',
    "Description" TEXT,
    "CooldownDuration" INTERVAL,  -- Only applicable for Recurring type
    "EventId" INTEGER REFERENCES "Events"("Id")  -- Only applicable for Event type
);

CREATE INDEX idx_missions_planetid ON "Missions"("PlanetId");
CREATE INDEX idx_missions_missionchainid ON "Missions"("MissionChainId");
CREATE INDEX idx_missions_type ON "Missions"("Type");
CREATE INDEX idx_missions_eventid ON "Missions"("EventId");
CREATE INDEX idx_missions_name ON "Missions"("Name");

COMMENT ON COLUMN "Missions"."CooldownDuration" IS 'Cooldown period before mission can be repeated. Only used when Type = Recurring.';
COMMENT ON COLUMN "Missions"."EventId" IS 'Reference to the event this mission belongs to. Only used when Type = Event.';

-- ===========================================
-- MISSION DEPENDENCIES TABLE (DAG structure)
-- ===========================================

CREATE TABLE "MissionDependencies" (
    "MissionId" INTEGER NOT NULL REFERENCES "Missions"("Id") ON DELETE CASCADE,
    "PrerequisiteMissionId" INTEGER NOT NULL REFERENCES "Missions"("Id") ON DELETE CASCADE,
    PRIMARY KEY ("MissionId", "PrerequisiteMissionId"),
    CHECK ("MissionId" != "PrerequisiteMissionId")  -- Prevent self-reference
);

CREATE INDEX idx_missiondependencies_prerequisite ON "MissionDependencies"("PrerequisiteMissionId");

-- ===========================================
-- MISSION STEPS TABLE
-- ===========================================

CREATE TABLE "MissionSteps" (
    "Id" SERIAL PRIMARY KEY,
    "MissionId" INTEGER NOT NULL REFERENCES "Missions"("Id") ON DELETE CASCADE,
    "Index" INTEGER NOT NULL,
    "Title" TEXT,
    "Description" TEXT,
    UNIQUE ("MissionId", "Index")
);

CREATE INDEX idx_missionsteps_missionid ON "MissionSteps"("MissionId");

-- ===========================================
-- MISSION OBJECTIVES TABLE
-- ===========================================
-- Objective types: Dialog, KillCount, KillCycle, Explore, Interact, HandIn, CraftSuccess, CraftAttempt, CraftCycle, MiningCycle, MiningClaim, MiningPoints

CREATE TABLE "MissionObjectives" (
    "Id" SERIAL PRIMARY KEY,
    "StepId" INTEGER NOT NULL REFERENCES "MissionSteps"("Id") ON DELETE CASCADE,
    "Type" TEXT NOT NULL,
    "Payload" JSONB
);

CREATE INDEX idx_missionobjectives_stepid ON "MissionObjectives"("StepId");
CREATE INDEX idx_missionobjectives_type ON "MissionObjectives"("Type");

-- ===========================================
-- MISSION REWARDS TABLE
-- ===========================================

CREATE TABLE "MissionRewards" (
    "Id" SERIAL PRIMARY KEY,
    "MissionId" INTEGER NOT NULL REFERENCES "Missions"("Id") ON DELETE CASCADE,
    "Items" JSONB,  -- Array of { itemId, quantity, minPedValue, pedValue }
    "Skills" JSONB,  -- Array of { skillItemId, pedValue }
    "Unlocks" TEXT[]  -- Free-form descriptions for unique unlocks
);

CREATE INDEX idx_missionrewards_missionid ON "MissionRewards"("MissionId");

-- ===========================================
-- NPCS TABLE
-- ===========================================

CREATE TABLE "Npcs" (
    "Id" SERIAL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Description" TEXT,
    "PlanetId" INTEGER REFERENCES "Planets"("Id"),
    "Longitude" INTEGER,
    "Latitude" INTEGER,
    "Altitude" INTEGER
);

CREATE INDEX idx_npcs_planetid ON "Npcs"("PlanetId");
CREATE INDEX idx_npcs_name ON "Npcs"("Name");

-- ===========================================
-- INTERACTABLES TABLE
-- ===========================================

CREATE TABLE "Interactables" (
    "Id" SERIAL PRIMARY KEY,
    "Name" TEXT NOT NULL,
    "Description" TEXT,
    "PlanetId" INTEGER REFERENCES "Planets"("Id"),
    "Longitude" INTEGER,
    "Latitude" INTEGER,
    "Altitude" INTEGER
);

CREATE INDEX idx_interactables_planetid ON "Interactables"("PlanetId");
CREATE INDEX idx_interactables_name ON "Interactables"("Name");

-- ===========================================
-- UPDATE LOCATIONS VIEW
-- ===========================================
-- Add NPCs (Id + 400000) and Interactables (Id + 500000) to unified Locations view

CREATE OR REPLACE VIEW "Locations" AS
SELECT ("Teleporters"."Id" + 100000) AS "Id",
    "Teleporters"."Name",
    "Teleporters"."Longitude",
    "Teleporters"."Latitude",
    "Teleporters"."Altitude",
    "Teleporters"."PlanetId",
    'Teleporter'::text AS "Type"
FROM ONLY "Teleporters"
UNION ALL
SELECT ("Areas"."Id" + 200000) AS "Id",
    "Areas"."Name",
    "Areas"."Longitude",
    "Areas"."Latitude",
    "Areas"."Altitude",
    "Areas"."PlanetId",
    ("Areas"."Type")::text AS "Type"
FROM ONLY "Areas"
UNION ALL
SELECT ("Estates"."Id" + 300000) AS "Id",
    "Estates"."Name",
    "Estates"."Longitude",
    "Estates"."Latitude",
    "Estates"."Altitude",
    "Estates"."PlanetId",
    ("Estates"."Type")::text AS "Type"
FROM ONLY "Estates"
UNION ALL
SELECT ("Npcs"."Id" + 400000) AS "Id",
    "Npcs"."Name",
    "Npcs"."Longitude",
    "Npcs"."Latitude",
    "Npcs"."Altitude",
    "Npcs"."PlanetId",
    'Npc'::text AS "Type"
FROM ONLY "Npcs"
UNION ALL
SELECT ("Interactables"."Id" + 500000) AS "Id",
    "Interactables"."Name",
    "Interactables"."Longitude",
    "Interactables"."Latitude",
    "Interactables"."Altitude",
    "Interactables"."PlanetId",
    'Interactable'::text AS "Type"
FROM ONLY "Interactables";

-- ===========================================
-- GRANTS FOR API ACCESS
-- ===========================================

GRANT SELECT ON "Events" TO "nexus";
GRANT SELECT ON "MissionChains" TO "nexus";
GRANT SELECT ON "Missions" TO "nexus";
GRANT SELECT ON "MissionDependencies" TO "nexus";
GRANT SELECT ON "MissionSteps" TO "nexus";
GRANT SELECT ON "MissionObjectives" TO "nexus";
GRANT SELECT ON "MissionRewards" TO "nexus";
GRANT SELECT ON "Npcs" TO "nexus";
GRANT SELECT ON "Interactables" TO "nexus";
GRANT SELECT ON "Locations" TO "nexus";

GRANT USAGE, SELECT ON SEQUENCE "Events_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "MissionChains_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "Missions_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "MissionSteps_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "MissionObjectives_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "MissionRewards_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "Npcs_Id_seq" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "Interactables_Id_seq" TO "nexus";

-- ===========================================
-- AUDIT TABLES AND TRIGGERS (iterate over all tables)
-- ===========================================

DO $$
DECLARE
   tbl_name TEXT;
   col_def TEXT;
   col_def_temp TEXT;
   check_constraint TEXT;
   audit_table_exists BOOLEAN;
   tables_to_audit TEXT[] := ARRAY['Events', 'MissionChains', 'Missions', 'MissionDependencies', 'MissionSteps', 'MissionObjectives', 'MissionRewards', 'Npcs', 'Interactables'];
BEGIN
   FOREACH tbl_name IN ARRAY tables_to_audit LOOP
      col_def := '';

      -- Check if the audit table already exists
      SELECT EXISTS (
         SELECT 1
         FROM information_schema.tables
         WHERE table_schema = 'public'
         AND table_name = format('%s_audit', tbl_name)
      ) INTO audit_table_exists;

      -- Build column definitions for the audit table
      FOR col_def_temp IN (
         SELECT
            '"' || column_name || '" ' ||
            CASE
               WHEN data_type = 'numeric' AND numeric_precision IS NOT NULL AND numeric_scale IS NOT NULL THEN
                  'numeric(' || numeric_precision || ',' || numeric_scale || ')'
               WHEN data_type = 'character varying' AND character_maximum_length IS NOT NULL THEN
                  'character varying(' || character_maximum_length || ')'
               WHEN data_type = 'character' AND character_maximum_length IS NOT NULL THEN
                  'character(' || character_maximum_length || ')'
               WHEN data_type = 'text' THEN
                  'text COLLATE pg_catalog."default"'
               WHEN data_type = 'USER-DEFINED' THEN
                  -- For enums and other user-defined types, properly quote the type name
                  '"' || udt_name || '"'
               ELSE
                  COALESCE((SELECT typname FROM pg_type WHERE typname = udt_name), data_type)
            END ||
            (CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END)
         FROM information_schema.columns
         WHERE table_schema = 'public' AND table_name = tbl_name
         ORDER BY ordinal_position
      ) LOOP
         col_def := col_def || ', ' || col_def_temp;
      END LOOP;

      -- Create the audit table only if it doesn't exist
      IF NOT audit_table_exists THEN
         EXECUTE format('
            CREATE TABLE "%1$s_audit" (
               operation CHAR(1) NOT NULL,
               stamp TIMESTAMP NOT NULL,
               userid TEXT NOT NULL
               %2$s
            );
         ', tbl_name, col_def);

         -- Copy CHECK constraints from parent table to audit table
         -- Special handling for MissionDependencies which has a CHECK constraint
         IF tbl_name = 'MissionDependencies' THEN
            EXECUTE 'ALTER TABLE "MissionDependencies_audit" ADD CONSTRAINT "MissionDependencies_check" CHECK ("MissionId" != "PrerequisiteMissionId")';
         END IF;

         -- Add inheritance after table creation
         EXECUTE format('
            ALTER TABLE "%1$s_audit" INHERIT "%1$s";
         ', tbl_name);
      END IF;

      -- Create the trigger and initial inserts only if the audit table did not exist
      IF NOT audit_table_exists THEN
         EXECUTE format('
            CREATE OR REPLACE FUNCTION "%1$s_audit_trigger"() RETURNS TRIGGER AS $func$
            BEGIN
               IF (TG_OP = ''DELETE'') THEN
                  INSERT INTO "%1$s_audit" SELECT ''D'', now(), current_user, OLD.*;
                  RETURN OLD;
               ELSIF (TG_OP = ''UPDATE'') THEN
                  INSERT INTO "%1$s_audit" SELECT ''U'', now(), current_user, NEW.*;
                  RETURN NEW;
               ELSIF (TG_OP = ''INSERT'') THEN
                  INSERT INTO "%1$s_audit" SELECT ''I'', now(), current_user, NEW.*;
                  RETURN NEW;
               END IF;
               RETURN NULL;
            END;
            $func$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS "%1$s_audit_trigger" ON "%1$s";

            CREATE TRIGGER "%1$s_audit_trigger"
            AFTER INSERT OR UPDATE OR DELETE ON "%1$s"
               FOR EACH ROW EXECUTE FUNCTION "%1$s_audit_trigger"();

            INSERT INTO "%1$s_audit" SELECT ''I'', now(), current_user, * FROM "%1$s";
         ', tbl_name);
      END IF;
   END LOOP;
END $$;

COMMIT;
