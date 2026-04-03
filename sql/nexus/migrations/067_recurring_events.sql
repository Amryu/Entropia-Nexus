-- Recurring events: game events that repeat periodically (Migration, Mayhem, etc.)
-- Mob spawn areas can be linked to a recurring event so they only display on maps
-- while the event is active.

CREATE TABLE "RecurringEvents" (
  "Id"          SERIAL PRIMARY KEY,
  "Name"        TEXT NOT NULL UNIQUE,
  "Description" TEXT,
  "Color"       TEXT NOT NULL DEFAULT '#ff6b35',
  "CreatedAt"   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add FK column to MobSpawns (keep IsEvent for backward compat during transition)
ALTER TABLE "MobSpawns" ADD COLUMN "RecurringEventId" INTEGER
  REFERENCES "RecurringEvents"("Id") ON DELETE SET NULL;

CREATE INDEX idx_mobspawns_recurring_event
  ON "MobSpawns"("RecurringEventId") WHERE "RecurringEventId" IS NOT NULL;

-- TableChanges tracking (required for API response cache invalidation)
CREATE TRIGGER zz_track_change
AFTER INSERT OR UPDATE OR DELETE ON "RecurringEvents"
FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();

-- Grants for public API (nexus role needs write for admin CRUD via proxy)
GRANT SELECT, INSERT, UPDATE, DELETE ON "RecurringEvents" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "RecurringEvents_Id_seq" TO "nexus";

-- Grants for bot (processes wiki changes that set RecurringEventId on MobSpawns)
GRANT SELECT, INSERT, UPDATE, DELETE ON "RecurringEvents" TO nexus_bot;
GRANT USAGE, SELECT ON SEQUENCE "RecurringEvents_Id_seq" TO nexus_bot;
