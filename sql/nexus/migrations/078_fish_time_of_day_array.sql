-- Expand FishTimeOfDay enum with Dawn/Sunset and convert the Fish.TimeOfDay
-- column from a single enum to an array, matching how Biomes/RodTypes work.

BEGIN;

ALTER TYPE "FishTimeOfDay" ADD VALUE IF NOT EXISTS 'Dawn';
ALTER TYPE "FishTimeOfDay" ADD VALUE IF NOT EXISTS 'Sunset';

COMMIT;

-- Array conversion must run outside the transaction that added enum values
-- (PG requires the enum OIDs to be committed before they can be referenced).

ALTER TABLE "Fish"
  ALTER COLUMN "TimeOfDay" DROP DEFAULT,
  ALTER COLUMN "TimeOfDay" TYPE "FishTimeOfDay"[]
    USING CASE WHEN "TimeOfDay" IS NULL THEN ARRAY[]::"FishTimeOfDay"[] ELSE ARRAY["TimeOfDay"] END,
  ALTER COLUMN "TimeOfDay" SET DEFAULT '{}';
