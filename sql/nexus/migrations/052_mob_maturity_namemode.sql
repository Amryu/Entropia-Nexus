-- Add NameMode column to MobMaturities
-- Controls how the full in-game name is constructed from mob name + maturity name:
--   'Suffix':   "MobName MaturityName"  (e.g., "Araneatrox Young")
--   'Prefix':   "MaturityName MobName"  (e.g., "Young Araneatrox")
--   'Verbatim': MaturityName IS the full name
--   'Empty':    MobName IS the full name (single-maturity mobs)
--   NULL:       Unknown (defaults to Suffix for display)

ALTER TABLE "MobMaturities" ADD COLUMN IF NOT EXISTS "NameMode" text;

-- Disable audit trigger during bulk pre-population (avoids column order mismatch)
ALTER TABLE "MobMaturities" DISABLE TRIGGER ALL;

-- Pre-populate: Set Empty for Default-only mobs (single maturity named 'Default')
UPDATE ONLY "MobMaturities" mm
SET "NameMode" = 'Empty'
WHERE mm."Name" = 'Default'
  AND NOT EXISTS (
    SELECT 1 FROM ONLY "MobMaturities" other
    WHERE other."MobId" = mm."MobId" AND other."Id" != mm."Id"
  );

-- Pre-populate: Set Suffix for all remaining maturities (standard game pattern)
UPDATE ONLY "MobMaturities"
SET "NameMode" = 'Suffix'
WHERE "NameMode" IS NULL;

-- Re-enable audit trigger
ALTER TABLE "MobMaturities" ENABLE TRIGGER ALL;