-- Add OwnerName column to LandAreas and Estates for owners without a Nexus account.
-- OwnerId and OwnerName are mutually exclusive: if the owner is a verified user,
-- OwnerId is set and OwnerName is NULL; otherwise OwnerName holds the player name.
--
-- Audit tables are dropped and recreated to fix column ordering (own columns
-- operation/stamp/userid must precede inherited columns for the SELECT ... NEW.*
-- trigger pattern). Existing audit data is preserved.

-- ========== LandAreas ==========

ALTER TABLE "LandAreas"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

ALTER TABLE "LandAreas"
  ADD CONSTRAINT "LandAreas_owner_exclusive"
  CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL));

-- Back up audit data, drop and recreate with correct column order
DROP TRIGGER IF EXISTS "LandAreas_audit_trigger" ON "LandAreas";

CREATE TEMP TABLE _la_audit_backup AS
  SELECT operation, stamp, userid, "LocationId", "TaxRateHunting", "TaxRateMining", "TaxRateShops", "OwnerId"
  FROM ONLY "LandAreas_audit";

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"LandAreas_audit"'::regclass) THEN
    ALTER TABLE "LandAreas_audit" NO INHERIT "LandAreas";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DROP TABLE IF EXISTS "LandAreas_audit";

CREATE TABLE "LandAreas_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "LocationId" INTEGER NOT NULL,
  "OwnerId" BIGINT,
  "TaxRateHunting" NUMERIC,
  "TaxRateMining" NUMERIC,
  "TaxRateShops" NUMERIC,
  "OwnerName" TEXT,
  CONSTRAINT "LandAreas_owner_exclusive" CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL))
);

INSERT INTO "LandAreas_audit" (operation, stamp, userid, "LocationId", "TaxRateHunting", "TaxRateMining", "TaxRateShops", "OwnerId")
SELECT operation, stamp, userid, "LocationId", "TaxRateHunting", "TaxRateMining", "TaxRateShops", "OwnerId"
FROM _la_audit_backup;

DROP TABLE _la_audit_backup;

ALTER TABLE "LandAreas_audit" INHERIT "LandAreas";

GRANT SELECT ON "LandAreas_audit" TO "nexus";
GRANT SELECT, INSERT, UPDATE, DELETE ON "LandAreas_audit" TO nexus_bot;

CREATE OR REPLACE FUNCTION "LandAreas_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "LandAreas_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "LandAreas_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "LandAreas_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

CREATE TRIGGER "LandAreas_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "LandAreas"
  FOR EACH ROW EXECUTE FUNCTION "LandAreas_audit_trigger"();

-- ========== Estates ==========

ALTER TABLE "Estates"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

ALTER TABLE "Estates"
  ADD CONSTRAINT "Estates_owner_exclusive"
  CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL));

-- Back up audit data, drop and recreate with correct column order
DROP TRIGGER IF EXISTS "Estates_audit_trigger" ON "Estates";

CREATE TEMP TABLE _est_audit_backup AS
  SELECT operation, stamp, userid, "Type", "OwnerId", "ItemTradeAvailable", "MaxGuests", "LocationId"
  FROM ONLY "Estates_audit";

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_inherits WHERE inhrelid = '"Estates_audit"'::regclass) THEN
    ALTER TABLE "Estates_audit" NO INHERIT "Estates";
  END IF;
EXCEPTION WHEN undefined_table THEN NULL;
END $$;

DROP TABLE IF EXISTS "Estates_audit";

CREATE TABLE "Estates_audit" (
  operation CHAR(1) NOT NULL,
  stamp TIMESTAMP NOT NULL,
  userid TEXT NOT NULL,
  "Type" "EstateType" NOT NULL,
  "OwnerId" BIGINT,
  "ItemTradeAvailable" BOOLEAN,
  "MaxGuests" INTEGER,
  "LocationId" INTEGER NOT NULL,
  "OwnerName" TEXT,
  CONSTRAINT "Estates_owner_exclusive" CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL))
);

INSERT INTO "Estates_audit" (operation, stamp, userid, "Type", "OwnerId", "ItemTradeAvailable", "MaxGuests", "LocationId")
SELECT operation, stamp, userid, "Type", "OwnerId", "ItemTradeAvailable", "MaxGuests", "LocationId"
FROM _est_audit_backup;

DROP TABLE _est_audit_backup;

ALTER TABLE "Estates_audit" INHERIT "Estates";

GRANT SELECT ON "Estates_audit" TO "nexus";
GRANT SELECT, INSERT, UPDATE, DELETE ON "Estates_audit" TO nexus_bot;

CREATE OR REPLACE FUNCTION "Estates_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "Estates_audit" SELECT 'D', now(), current_user, OLD.*;
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "Estates_audit" SELECT 'U', now(), current_user, NEW.*;
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "Estates_audit" SELECT 'I', now(), current_user, NEW.*;
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;

CREATE TRIGGER "Estates_audit_trigger"
  AFTER INSERT OR UPDATE OR DELETE ON "Estates"
  FOR EACH ROW EXECUTE FUNCTION "Estates_audit_trigger"();
