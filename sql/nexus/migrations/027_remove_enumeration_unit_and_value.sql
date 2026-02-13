-- Migration 027: Remove deprecated Enumerations.Unit and EnumerationValues.Value columns
-- Safe to run when columns are already absent.

BEGIN;

-- Drop from parent tables first.
ALTER TABLE IF EXISTS "Enumerations"
  DROP COLUMN IF EXISTS "Unit";

ALTER TABLE IF EXISTS "EnumerationValues"
  DROP COLUMN IF EXISTS "Value";

-- Then drop from audit tables in case merged inherited columns remained local.
ALTER TABLE IF EXISTS "Enumerations_audit"
  DROP COLUMN IF EXISTS "Unit";

ALTER TABLE IF EXISTS "EnumerationValues_audit"
  DROP COLUMN IF EXISTS "Value";

COMMIT;
