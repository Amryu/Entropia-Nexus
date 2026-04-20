-- Allow the nexus role (SvelteKit frontend) to write to FishDiscoveries.
-- Needed for the admin "Manual Unlocks" page which lets an admin mark a
-- fish as discovered without waiting on the bot to ingest a discovery
-- global. Writes still go through a server-only admin-gated API route
-- (nexus/src/routes/api/admin/manual-unlocks/+server.js).

BEGIN;

GRANT INSERT, UPDATE, DELETE ON "FishDiscoveries" TO nexus;

COMMIT;
