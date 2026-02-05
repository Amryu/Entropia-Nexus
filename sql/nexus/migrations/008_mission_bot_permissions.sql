-- Migration: Grant bot permissions for mission tables + fix missing constraints
-- The original 003_missions.sql only granted SELECT to nexus (API user), not nexus-bot

-- Add unique constraint on MissionRewards.MissionId for ON CONFLICT to work
-- Each mission has exactly one rewards entry
ALTER TABLE "MissionRewards" ADD CONSTRAINT "MissionRewards_MissionId_unique" UNIQUE ("MissionId");

-- Grant full CRUD to nexus-bot for all mission tables
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionChains" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Missions" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionSteps" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionObjectives" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionRewards" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionDependencies" TO "nexus-bot";

-- Grant permissions on audit tables
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionChains_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Missions_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionSteps_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionObjectives_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionRewards_audit" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "MissionDependencies_audit" TO "nexus-bot";

-- Grant sequence permissions for auto-increment IDs
GRANT USAGE, SELECT ON SEQUENCE "MissionChains_Id_seq" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "Missions_Id_seq" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "MissionSteps_Id_seq" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "MissionObjectives_Id_seq" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "MissionRewards_Id_seq" TO "nexus-bot";

-- Events table also needs bot permissions (missions reference it)
GRANT SELECT, INSERT, UPDATE, DELETE ON "Events" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Events_audit" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "Events_Id_seq" TO "nexus-bot";
