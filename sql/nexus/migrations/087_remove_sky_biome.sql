-- Remove 'Sky' from the FishBiome enum.
--
-- Context: Sky was added speculatively in 074 but is not an actual
-- fishing biome in-game. No rows in prod reference it.
--
-- PostgreSQL does not support ALTER TYPE DROP VALUE, so we rename
-- the old type, create the new one, re-point the column, and drop
-- the old type.

BEGIN;

-- Safety: drop any rows referencing 'Sky' before retyping the column.
DELETE FROM "FishBiomes" WHERE "Biome"::text = 'Sky';

ALTER TYPE "FishBiome" RENAME TO "FishBiome_old";

CREATE TYPE "FishBiome" AS ENUM (
    'Sea',
    'River',
    'Lake',
    'Deep Ocean'
);

ALTER TABLE "FishBiomes"
    ALTER COLUMN "Biome" TYPE "FishBiome"
    USING "Biome"::text::"FishBiome";

DROP TYPE "FishBiome_old";

COMMIT;
