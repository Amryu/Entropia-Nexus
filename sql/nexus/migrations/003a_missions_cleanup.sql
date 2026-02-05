-- Migration: Cleanup missions tables (run before 003_missions.sql if re-creating)
-- Description: Drops all mission-related tables, audit tables, triggers, functions, and types
-- Database: nexus
-- Date: 2026-02-04

BEGIN;

-- ===========================================
-- DROP TRIGGERS AND FUNCTIONS
-- ===========================================

DO $$
DECLARE
   tbl_name TEXT;
   tables_to_cleanup TEXT[] := ARRAY['MissionRewards', 'MissionObjectives', 'MissionSteps', 'MissionDependencies', 'Missions', 'MissionChains', 'Events', 'Npcs', 'Interactables'];
BEGIN
   FOREACH tbl_name IN ARRAY tables_to_cleanup LOOP
      -- Drop trigger if exists
      EXECUTE format('DROP TRIGGER IF EXISTS "%1$s_audit_trigger" ON "%1$s"', tbl_name);
      -- Drop function if exists
      EXECUTE format('DROP FUNCTION IF EXISTS "%1$s_audit_trigger"()', tbl_name);
   END LOOP;
END $$;

-- ===========================================
-- DROP AUDIT TABLES (must drop before parent tables due to inheritance)
-- ===========================================

DROP TABLE IF EXISTS "MissionRewards_audit" CASCADE;
DROP TABLE IF EXISTS "MissionObjectives_audit" CASCADE;
DROP TABLE IF EXISTS "MissionSteps_audit" CASCADE;
DROP TABLE IF EXISTS "MissionDependencies_audit" CASCADE;
DROP TABLE IF EXISTS "Missions_audit" CASCADE;
DROP TABLE IF EXISTS "MissionChains_audit" CASCADE;
DROP TABLE IF EXISTS "Events_audit" CASCADE;
DROP TABLE IF EXISTS "Npcs_audit" CASCADE;
DROP TABLE IF EXISTS "Interactables_audit" CASCADE;

-- ===========================================
-- DROP VIEW (depends on Npcs and Interactables)
-- ===========================================

-- Restore Locations view without Npcs and Interactables
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
FROM ONLY "Estates";

-- ===========================================
-- DROP MAIN TABLES (in dependency order)
-- ===========================================

DROP TABLE IF EXISTS "MissionRewards" CASCADE;
DROP TABLE IF EXISTS "MissionObjectives" CASCADE;
DROP TABLE IF EXISTS "MissionSteps" CASCADE;
DROP TABLE IF EXISTS "MissionDependencies" CASCADE;
DROP TABLE IF EXISTS "Missions" CASCADE;
DROP TABLE IF EXISTS "MissionChains" CASCADE;
DROP TABLE IF EXISTS "Events" CASCADE;
DROP TABLE IF EXISTS "Npcs" CASCADE;
DROP TABLE IF EXISTS "Interactables" CASCADE;

-- ===========================================
-- DROP TYPE
-- ===========================================

DROP TYPE IF EXISTS "MissionType" CASCADE;

COMMIT;
