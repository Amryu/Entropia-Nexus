-- Grant nexus_bot SELECT on FishDiscoveries.
--
-- Migration 089 granted INSERT/UPDATE/DELETE only. The sync in
-- nexus-bot/fish-discoveries.js runs an INSERT ... ON CONFLICT DO UPDATE
-- whose RHS references "FishDiscoveries"."DiscoveredAt" via LEAST(), and
-- Postgres requires SELECT on the table for any such read-back — hence
-- the aclcheck failure.

BEGIN;

GRANT SELECT ON "FishDiscoveries" TO nexus_bot;

COMMIT;
