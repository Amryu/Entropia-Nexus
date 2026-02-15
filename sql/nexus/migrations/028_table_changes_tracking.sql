-- Migration 028: Table change tracking for API response caching
-- Creates a tracking table + statement-level triggers on all non-audit tables.
-- The API polls this table to know when cached responses need rebuilding.

BEGIN;

-- Tracking table: one row per entity table, recording last DML timestamps
CREATE TABLE IF NOT EXISTS "TableChanges" (
  "table_name" TEXT PRIMARY KEY,
  "last_insert" TIMESTAMPTZ,
  "last_update" TIMESTAMPTZ,
  "last_delete" TIMESTAMPTZ
);

-- Generic trigger function: upsert the appropriate timestamp column
CREATE OR REPLACE FUNCTION track_table_change() RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO "TableChanges" ("table_name", "last_insert", "last_update", "last_delete")
  VALUES (
    TG_TABLE_NAME,
    CASE WHEN TG_OP = 'INSERT' THEN now() ELSE NULL END,
    CASE WHEN TG_OP = 'UPDATE' THEN now() ELSE NULL END,
    CASE WHEN TG_OP = 'DELETE' THEN now() ELSE NULL END
  )
  ON CONFLICT ("table_name") DO UPDATE SET
    "last_insert" = CASE WHEN TG_OP = 'INSERT' THEN now() ELSE "TableChanges"."last_insert" END,
    "last_update" = CASE WHEN TG_OP = 'UPDATE' THEN now() ELSE "TableChanges"."last_update" END,
    "last_delete" = CASE WHEN TG_OP = 'DELETE' THEN now() ELSE "TableChanges"."last_delete" END;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Attach the trigger to every public table except audit tables and TableChanges itself.
-- Uses zz_ prefix so it fires after existing audit triggers (alphabetical order).
-- FOR EACH STATEMENT: fires once per SQL statement, not per row (efficient for bulk ops).
DO $$
DECLARE
  tbl TEXT;
BEGIN
  FOR tbl IN
    SELECT tablename FROM pg_tables
    WHERE schemaname = 'public'
    AND tablename NOT LIKE '%\_audit'
    AND tablename NOT IN ('TableChanges')
  LOOP
    EXECUTE format(
      'DROP TRIGGER IF EXISTS zz_track_change ON %I;
       CREATE TRIGGER zz_track_change
       AFTER INSERT OR UPDATE OR DELETE ON %I
       FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();',
      tbl, tbl
    );
  END LOOP;
END;
$$;

-- Grant access for app and bot roles (trigger needs INSERT/UPDATE to track changes)
GRANT SELECT, INSERT, UPDATE ON "TableChanges" TO "nexus";
GRANT SELECT, INSERT, UPDATE ON "TableChanges" TO "nexus-bot";

COMMIT;
