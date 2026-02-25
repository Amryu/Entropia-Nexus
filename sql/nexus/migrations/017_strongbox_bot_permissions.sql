-- Migration: Grant nexus_bot permissions on Strongbox tables
-- The bot needs to insert/update Strongboxes and StrongboxLoots when approving changes,
-- and the audit triggers require INSERT on the audit tables.
-- Database: nexus

BEGIN;

GRANT SELECT, INSERT, UPDATE, DELETE ON "Strongboxes" TO nexus_bot;
GRANT SELECT, INSERT, UPDATE, DELETE ON "Strongboxes_audit" TO nexus_bot;
GRANT SELECT, INSERT, UPDATE, DELETE ON "StrongboxLoots" TO nexus_bot;
GRANT SELECT, INSERT, UPDATE, DELETE ON "StrongboxLoots_audit" TO nexus_bot;

COMMIT;
