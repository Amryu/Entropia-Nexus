-- Add MinTT column to fishing attachment tables.
-- FishingRods already has MinTT; the four attachment subtypes were created
-- without it but the game data does carry a MinTT value for these items.

BEGIN;

ALTER TABLE "FishingReels"  ADD COLUMN IF NOT EXISTS "MinTT" numeric DEFAULT 0;
ALTER TABLE "FishingBlanks" ADD COLUMN IF NOT EXISTS "MinTT" numeric DEFAULT 0;
ALTER TABLE "FishingLines"  ADD COLUMN IF NOT EXISTS "MinTT" numeric DEFAULT 0;
ALTER TABLE "FishingLures"  ADD COLUMN IF NOT EXISTS "MinTT" numeric DEFAULT 0;

COMMIT;
