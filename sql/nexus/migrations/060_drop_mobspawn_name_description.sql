-- Drop redundant Name and Description columns from MobSpawns
-- Name is always identical to Locations.Name (628/628 match, 114 null)
-- Description is entirely empty (0 non-null values)

DO $$
BEGIN
  -- Detach audit table from parent
  IF EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"MobSpawns_audit"'::regclass) THEN
    ALTER TABLE "MobSpawns_audit" NO INHERIT "MobSpawns";
  END IF;

  -- Drop columns from audit table
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'Name') THEN
    ALTER TABLE "MobSpawns_audit" DROP COLUMN "Name";
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns_audit' AND column_name = 'Description') THEN
    ALTER TABLE "MobSpawns_audit" DROP COLUMN "Description";
  END IF;

  -- Drop columns from parent table
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns' AND column_name = 'Name') THEN
    ALTER TABLE ONLY "MobSpawns" DROP COLUMN "Name";
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'MobSpawns' AND column_name = 'Description') THEN
    ALTER TABLE ONLY "MobSpawns" DROP COLUMN "Description";
  END IF;

  -- Re-attach audit table
  IF NOT EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"MobSpawns_audit"'::regclass) THEN
    ALTER TABLE "MobSpawns_audit" INHERIT "MobSpawns";
  END IF;
END $$;
