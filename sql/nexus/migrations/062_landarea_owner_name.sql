-- Add OwnerName column to LandAreas and Estates for owners without a Nexus account.
-- OwnerId and OwnerName are mutually exclusive: if the owner is a verified user,
-- OwnerId is set and OwnerName is NULL; otherwise OwnerName holds the player name.
-- Audit tables inherit the column automatically, but trigger functions must be
-- recreated with explicit column names to avoid positional mismatches from
-- stale own columns on the audit tables.

-- ========== LandAreas ==========

ALTER TABLE "LandAreas"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

ALTER TABLE "LandAreas"
  ADD CONSTRAINT "LandAreas_owner_exclusive"
  CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL));

CREATE OR REPLACE FUNCTION "LandAreas_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "LandAreas_audit" (operation, stamp, userid, "LocationId", "TaxRateHunting", "TaxRateMining", "TaxRateShops", "OwnerId", "OwnerName")
    VALUES ('D', now(), current_user, OLD."LocationId", OLD."TaxRateHunting", OLD."TaxRateMining", OLD."TaxRateShops", OLD."OwnerId", OLD."OwnerName");
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "LandAreas_audit" (operation, stamp, userid, "LocationId", "TaxRateHunting", "TaxRateMining", "TaxRateShops", "OwnerId", "OwnerName")
    VALUES ('U', now(), current_user, NEW."LocationId", NEW."TaxRateHunting", NEW."TaxRateMining", NEW."TaxRateShops", NEW."OwnerId", NEW."OwnerName");
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "LandAreas_audit" (operation, stamp, userid, "LocationId", "TaxRateHunting", "TaxRateMining", "TaxRateShops", "OwnerId", "OwnerName")
    VALUES ('I', now(), current_user, NEW."LocationId", NEW."TaxRateHunting", NEW."TaxRateMining", NEW."TaxRateShops", NEW."OwnerId", NEW."OwnerName");
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

CREATE OR REPLACE FUNCTION "Estates_audit_trigger"() RETURNS TRIGGER AS $func$
BEGIN
  IF (TG_OP = 'DELETE') THEN
    INSERT INTO "Estates_audit" (operation, stamp, userid, "Type", "OwnerId", "OwnerName", "ItemTradeAvailable", "MaxGuests", "LocationId")
    VALUES ('D', now(), current_user, OLD."Type", OLD."OwnerId", OLD."OwnerName", OLD."ItemTradeAvailable", OLD."MaxGuests", OLD."LocationId");
    RETURN OLD;
  ELSIF (TG_OP = 'UPDATE') THEN
    INSERT INTO "Estates_audit" (operation, stamp, userid, "Type", "OwnerId", "OwnerName", "ItemTradeAvailable", "MaxGuests", "LocationId")
    VALUES ('U', now(), current_user, NEW."Type", NEW."OwnerId", NEW."OwnerName", NEW."ItemTradeAvailable", NEW."MaxGuests", NEW."LocationId");
    RETURN NEW;
  ELSIF (TG_OP = 'INSERT') THEN
    INSERT INTO "Estates_audit" (operation, stamp, userid, "Type", "OwnerId", "OwnerName", "ItemTradeAvailable", "MaxGuests", "LocationId")
    VALUES ('I', now(), current_user, NEW."Type", NEW."OwnerId", NEW."OwnerName", NEW."ItemTradeAvailable", NEW."MaxGuests", NEW."LocationId");
    RETURN NEW;
  END IF;
  RETURN NULL;
END;
$func$ LANGUAGE plpgsql;
