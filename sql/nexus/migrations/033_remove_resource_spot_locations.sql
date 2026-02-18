-- Remove Area-type locations whose names exactly match material names.
-- These are resource spot markers with no exact coordinates — not useful as locations.
-- Excludes "Amber" which is an NPC on ROCKtropia.
-- Affects 521 Area locations across 102 distinct material names.

BEGIN;

-- Delete from Areas extension table first (FK constraint)
DELETE FROM ONLY "Areas"
WHERE "LocationId" IN (
  SELECT l."Id"
  FROM ONLY "Locations" l
  WHERE l."Name" IN (SELECT "Name" FROM ONLY "Materials")
    AND l."Name" != 'Amber'
    AND l."Type" = 'Area'
);

-- Delete the locations themselves
DELETE FROM ONLY "Locations"
WHERE "Name" IN (SELECT "Name" FROM ONLY "Materials")
  AND "Name" != 'Amber'
  AND "Type" = 'Area';

COMMIT;
