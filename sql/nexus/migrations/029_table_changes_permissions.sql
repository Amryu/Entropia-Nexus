-- Migration 029: Fix TableChanges permissions
-- The track_table_change() trigger fires on every INSERT/UPDATE/DELETE and needs
-- to write to TableChanges. Both nexus (web app) and nexus-bot need INSERT/UPDATE.
-- The original migration 028 granted to "nexus_bot" (underscore) which doesn't exist;
-- the actual role is "nexus-bot" (hyphen).

GRANT SELECT, INSERT, UPDATE ON "TableChanges" TO "nexus";
GRANT SELECT, INSERT, UPDATE ON "TableChanges" TO "nexus-bot";
