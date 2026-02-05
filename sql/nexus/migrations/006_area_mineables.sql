-- Migration: Add AreaMineables table for tracking mineable resources in Land Areas
-- This creates a cross-reference table between Areas (LandArea type) and Materials

BEGIN;

-- Create MineralRarity enum
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mineralrarity') THEN
    CREATE TYPE "MineralRarity" AS ENUM (
      'Common',
      'Uncommon',
      'Rare',
      'Very Rare',
      'Extremely Rare'
    );
  END IF;
END$$;

-- Create AreaMineables table
CREATE TABLE IF NOT EXISTS "AreaMineables" (
  "LocationId" INTEGER NOT NULL REFERENCES "Locations"("Id") ON DELETE CASCADE,
  "MaterialId" INTEGER NOT NULL,
  "Rarity" "MineralRarity" NOT NULL DEFAULT 'Common',
  "Notes" TEXT,
  PRIMARY KEY ("LocationId", "MaterialId")
);

-- Create index for looking up mineables by material
CREATE INDEX IF NOT EXISTS "idx_areamineables_materialid" ON "AreaMineables"("MaterialId");

-- Create audit table for AreaMineables (follows standard audit table pattern)
CREATE TABLE IF NOT EXISTS "AreaMineables_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "LocationId" INTEGER NOT NULL,
  "MaterialId" INTEGER NOT NULL,
  "Rarity" "MineralRarity",
  "Notes" TEXT
);

-- Create audit trigger function (follows standard pattern using OLD.*/NEW.*)
CREATE OR REPLACE FUNCTION "AreaMineables_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "AreaMineables_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "AreaMineables_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "AreaMineables_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

-- Create audit trigger
DROP TRIGGER IF EXISTS "AreaMineables_audit_trigger" ON "AreaMineables";
CREATE TRIGGER "AreaMineables_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "AreaMineables"
  FOR EACH ROW EXECUTE FUNCTION "AreaMineables_audit_trigger"();

COMMIT;

-- Verify creation
SELECT 'AreaMineables table created' AS status, COUNT(*) AS columns
FROM information_schema.columns
WHERE table_name = 'AreaMineables' AND table_schema = 'public';
