-- Migration 025: Add custom Enumerations support
-- Creates Enumerations and EnumerationValues tables with audit tracking.

BEGIN;

-- ============================================================================
-- Enumerations header table
-- ============================================================================

CREATE TABLE IF NOT EXISTS "Enumerations" (
  "Id" SERIAL PRIMARY KEY,
  "Name" TEXT NOT NULL UNIQUE,
  "Description" TEXT,
  "Metadata" JSONB
);

CREATE TABLE IF NOT EXISTS "Enumerations_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "Id" INTEGER NOT NULL,
  "Name" TEXT NOT NULL,
  "Description" TEXT,
  "Metadata" JSONB
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_inherits
    WHERE inhrelid = '"Enumerations_audit"'::regclass
      AND inhparent = '"Enumerations"'::regclass
  ) THEN
    ALTER TABLE "Enumerations_audit" INHERIT "Enumerations";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION "Enumerations_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "Enumerations_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "Enumerations_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "Enumerations_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "Enumerations_audit_trigger" ON "Enumerations";
CREATE TRIGGER "Enumerations_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "Enumerations"
  FOR EACH ROW EXECUTE FUNCTION "Enumerations_audit_trigger"();

-- ============================================================================
-- Enumeration values table
-- ============================================================================

CREATE TABLE IF NOT EXISTS "EnumerationValues" (
  "EnumerationId" INTEGER NOT NULL REFERENCES "Enumerations"("Id") ON DELETE CASCADE,
  "Name" TEXT NOT NULL,
  "Data" JSONB,
  PRIMARY KEY ("EnumerationId", "Name")
);

ALTER TABLE "EnumerationValues"
  ADD COLUMN IF NOT EXISTS "Data" JSONB;

CREATE INDEX IF NOT EXISTS "idx_enumerationvalues_enumerationid" ON "EnumerationValues"("EnumerationId");

CREATE TABLE IF NOT EXISTS "EnumerationValues_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "EnumerationId" INTEGER NOT NULL,
  "Name" TEXT NOT NULL,
  "Data" JSONB
);

ALTER TABLE "EnumerationValues_audit"
  ADD COLUMN IF NOT EXISTS "Data" JSONB;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_inherits
    WHERE inhrelid = '"EnumerationValues_audit"'::regclass
      AND inhparent = '"EnumerationValues"'::regclass
  ) THEN
    ALTER TABLE "EnumerationValues_audit" INHERIT "EnumerationValues";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

CREATE OR REPLACE FUNCTION "EnumerationValues_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "EnumerationValues_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "EnumerationValues_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "EnumerationValues_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS "EnumerationValues_audit_trigger" ON "EnumerationValues";
CREATE TRIGGER "EnumerationValues_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "EnumerationValues"
  FOR EACH ROW EXECUTE FUNCTION "EnumerationValues_audit_trigger"();

-- ============================================================================
-- Grants
-- ============================================================================

GRANT SELECT ON "Enumerations" TO "nexus";
GRANT SELECT ON "Enumerations_audit" TO "nexus";
GRANT USAGE, SELECT ON SEQUENCE "Enumerations_Id_seq" TO "nexus";
GRANT SELECT ON "EnumerationValues" TO "nexus";
GRANT SELECT ON "EnumerationValues_audit" TO "nexus";

GRANT SELECT, INSERT, UPDATE, DELETE ON "Enumerations" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "Enumerations_Id_seq" TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE, DELETE ON "EnumerationValues" TO "nexus-bot";

COMMIT;
