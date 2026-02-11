-- Change OwnerId columns from integer to bigint to support Discord user IDs (snowflakes)
ALTER TABLE "LandAreas" ALTER COLUMN "OwnerId" TYPE BIGINT;
ALTER TABLE "Estates" ALTER COLUMN "OwnerId" TYPE BIGINT;

-- Add unique constraint for EstateSections upsert (ON CONFLICT requires it)
ALTER TABLE ONLY "EstateSections" ADD CONSTRAINT "EstateSections_LocationId_Name_key" UNIQUE ("LocationId", "Name");
