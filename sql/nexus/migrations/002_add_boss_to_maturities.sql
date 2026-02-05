-- Add Boss column to MobMaturities
-- Boss maturities are special variants that should be excluded from tier 1 property calculations (level/hp ranges)

ALTER TABLE "MobMaturities"
ADD COLUMN "Boss" BOOLEAN DEFAULT FALSE;

-- Add comment for documentation
COMMENT ON COLUMN "MobMaturities"."Boss" IS 'Indicates if this maturity is a boss variant. Boss maturities are excluded from tier 1 property calculations.';
