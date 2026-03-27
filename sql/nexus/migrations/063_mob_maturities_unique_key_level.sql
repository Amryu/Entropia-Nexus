-- Allow multiple maturities with the same name but different levels per mob.
-- Use a unique index with COALESCE to handle NULL DangerLevel values
-- (PostgreSQL UNIQUE constraints treat NULLs as distinct).

ALTER TABLE ONLY "MobMaturities" DROP CONSTRAINT IF EXISTS "MobMaturities_MobId_Name_key";

CREATE UNIQUE INDEX "MobMaturities_MobId_Name_DangerLevel_key"
  ON "MobMaturities" ("MobId", "Name", COALESCE("DangerLevel", -1));
