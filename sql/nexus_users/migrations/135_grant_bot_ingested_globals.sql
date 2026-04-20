-- Grant nexus_bot read access to the ingested globals tables so the
-- fish-discovery sync (nexus-bot/fish-discoveries.js) can pull confirmed
-- discovery events. The bot is a new reader; the webapp (nexus_users
-- role) already had these grants from migration 070.

BEGIN;

GRANT SELECT ON ingested_globals              TO nexus_bot;
GRANT SELECT ON ingested_global_submissions   TO nexus_bot;

COMMIT;
