-- Migration 055: Shift mob spawn density values up by 1
-- Old scale: 1=Low, 2=Medium, 3=High
-- New scale: 1=Very Low, 2=Low, 3=Medium, 4=High, 5=Very High
-- Existing values need +1 to preserve their meaning.
-- NULLs are set to 3 (Medium), the new default.

UPDATE ONLY "MobSpawns"
SET "Density" = "Density" + 1
WHERE "Density" IS NOT NULL;

UPDATE ONLY "MobSpawns"
SET "Density" = 3
WHERE "Density" IS NULL;
