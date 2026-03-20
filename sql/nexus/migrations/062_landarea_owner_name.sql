-- Add OwnerName column to LandAreas and Estates for owners without a Nexus account.
-- OwnerId and OwnerName are mutually exclusive: if the owner is a verified user,
-- OwnerId is set and OwnerName is NULL; otherwise OwnerName holds the player name.
-- Audit tables inherit these columns automatically.

ALTER TABLE "LandAreas"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

ALTER TABLE "LandAreas"
  ADD CONSTRAINT "LandAreas_owner_exclusive"
  CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL));

ALTER TABLE "Estates"
  ADD COLUMN IF NOT EXISTS "OwnerName" TEXT;

ALTER TABLE "Estates"
  ADD CONSTRAINT "Estates_owner_exclusive"
  CHECK (NOT ("OwnerId" IS NOT NULL AND "OwnerName" IS NOT NULL));
