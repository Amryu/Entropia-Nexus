-- Split single TaxRate column into three components: Hunting, Mining, Shops
-- Each ranges 0-5%. All existing TaxRate values are NULL so no data migration needed.

-- 1. Add new columns to main table
ALTER TABLE "LandAreas"
  ADD COLUMN IF NOT EXISTS "TaxRateHunting" NUMERIC,
  ADD COLUMN IF NOT EXISTS "TaxRateMining" NUMERIC,
  ADD COLUMN IF NOT EXISTS "TaxRateShops" NUMERIC;

-- 2. Drop old column from main table
ALTER TABLE "LandAreas" DROP COLUMN IF EXISTS "TaxRate";

-- 5. Recreate audit trigger function with new columns
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
