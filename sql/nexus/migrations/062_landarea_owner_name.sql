-- Add OwnerName column to LandAreas and Estates for owners without a Nexus account.
-- OwnerId and OwnerName are mutually exclusive: if the owner is a verified user,
-- OwnerId is set and OwnerName is NULL; otherwise OwnerName holds the player name.

-- ========== LandAreas ==========

ALTER TABLE "LandAreas"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

ALTER TABLE "LandAreas"
  ADD CONSTRAINT "LandAreas_owner_exclusive"
  CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL));

ALTER TABLE "LandAreas_audit"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

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

-- ========== Estates ==========

ALTER TABLE "Estates"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

ALTER TABLE "Estates"
  ADD CONSTRAINT "Estates_owner_exclusive"
  CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL));

ALTER TABLE "Estates_audit"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

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
