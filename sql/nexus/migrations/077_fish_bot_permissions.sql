-- Fix missing nexus_bot permissions on Fish and Fish_audit tables.
-- The audit trigger runs as the invoker, so nexus_bot needs INSERT on
-- the audit table to avoid "permission denied" when inserting/updating Fish.

GRANT SELECT, INSERT, UPDATE, DELETE ON "Fish" TO nexus_bot;
GRANT INSERT ON "Fish_audit" TO nexus_bot;
GRANT SELECT, INSERT, UPDATE, DELETE ON "FishPlanets" TO nexus_bot;
GRANT SELECT, INSERT, UPDATE, DELETE ON "FishRodTypes" TO nexus_bot;
GRANT USAGE, SELECT ON SEQUENCE "Fish_Id_seq" TO nexus_bot;
