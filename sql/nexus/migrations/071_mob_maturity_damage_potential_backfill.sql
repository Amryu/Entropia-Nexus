-- Backfill DamagePotential on MobMaturities from max attack damage, without
-- touching any row that already carries a value. Pre-existing values
-- (including legacy free-text that may not match the current enum seeded in
-- 026_seed_enumerations.sql) are preserved and reported via RAISE NOTICE so
-- they can be reviewed manually.
--
-- Bucket ranges (inclusive lower bound, exclusive upper, capped at 500):
--   Minimal  1-19   Small    20-29   Limited  30-39   Medium   40-59
--   Large    60-100 Great    101-160 Huge     161-270 Immense  271-355
--   Gigantic 356-499 Colossal 500+

ALTER TABLE "MobMaturities" DISABLE TRIGGER ALL;

-- Report rows that already have DamagePotential set so they are not touched.
-- Legacy values outside the current enum surface here too — fix those
-- manually from the wiki editor rather than via migration.
DO $$
DECLARE
  r RECORD;
  total_count int := 0;
  nonstandard_count int := 0;
BEGIN
  FOR r IN
    SELECT m."Id", m."MobId", m."Name", m."DamagePotential", mob."Name" AS "MobName"
    FROM ONLY "MobMaturities" m
    LEFT JOIN ONLY "Mobs" mob ON mob."Id" = m."MobId"
    WHERE m."DamagePotential" IS NOT NULL
    ORDER BY mob."Name", m."Name"
  LOOP
    total_count := total_count + 1;
    IF r."DamagePotential" NOT IN ('Minimal','Small','Limited','Medium','Large','Great','Huge','Immense','Gigantic','Colossal') THEN
      nonstandard_count := nonstandard_count + 1;
      RAISE NOTICE 'Skipping (non-standard value): Mob=% Maturity=% DamagePotential=%',
        COALESCE(r."MobName", '?'), COALESCE(r."Name", '?'), r."DamagePotential";
    ELSE
      RAISE NOTICE 'Skipping (already set): Mob=% Maturity=% DamagePotential=%',
        COALESCE(r."MobName", '?'), COALESCE(r."Name", '?'), r."DamagePotential";
    END IF;
  END LOOP;
  RAISE NOTICE 'DamagePotential backfill: % maturities already set (% non-standard), left untouched.',
    total_count, nonstandard_count;
END $$;

-- Backfill from max attack damage per maturity, but ONLY where no value exists.
WITH max_dmg AS (
  SELECT "MaturityId", MAX("Damage") AS d
  FROM ONLY "MobAttacks"
  WHERE "Damage" IS NOT NULL AND "Damage" > 0
  GROUP BY "MaturityId"
)
UPDATE ONLY "MobMaturities" m
SET "DamagePotential" = CASE
  WHEN d >= 500 THEN 'Colossal'
  WHEN d >= 356 THEN 'Gigantic'
  WHEN d >= 271 THEN 'Immense'
  WHEN d >= 161 THEN 'Huge'
  WHEN d >= 101 THEN 'Great'
  WHEN d >= 60  THEN 'Large'
  WHEN d >= 40  THEN 'Medium'
  WHEN d >= 30  THEN 'Limited'
  WHEN d >= 20  THEN 'Small'
  WHEN d >= 1   THEN 'Minimal'
  ELSE NULL
END
FROM max_dmg
WHERE m."Id" = max_dmg."MaturityId"
  AND m."DamagePotential" IS NULL;

ALTER TABLE "MobMaturities" ENABLE TRIGGER ALL;
