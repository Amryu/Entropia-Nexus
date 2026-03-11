-- Migration: Repair MobSpawnMaturities and MobSpawns for orphaned MobArea Locations
-- Description: Areas created (or left) without MobSpawns entries are invisible to
--   applyMobSpawnChanges (which uses INNER JOIN "MobSpawns"), causing the bot to create
--   duplicate Locations on the next Mob change while leaving the originals with no maturities.
--   This migration:
--     1. Creates missing MobSpawns rows for all MobArea Locations (idempotent).
--     2. Restores missing MobSpawnMaturities from the area's Name field, using the same
--        parsing logic as migration 056 step 5:
--        - Name format: "Mob Name - Mat1/Mat2, Mob2 Name - Mat3"  (comma = multi-mob, slash = multi-maturity)
--        - Segments without " - " use the mob name only, resolved to 'Default' maturity
--        - 'Default' is accepted only when the mob has exactly one maturity
--        Only inserts for LocationIds that currently have zero MobSpawnMaturities rows.
-- Database: nexus
-- Date: 2026-03-11
-- IDEMPOTENT: Safe to re-run

BEGIN;

-- Step 1: Create missing MobSpawns entries for MobArea Locations
INSERT INTO "MobSpawns" ("LocationId")
SELECT l."Id"
FROM ONLY "Locations" l
JOIN ONLY "Areas" a ON a."LocationId" = l."Id"
WHERE a."Type" = 'MobArea'
AND NOT EXISTS (
  SELECT 1 FROM ONLY "MobSpawns" ms WHERE ms."LocationId" = l."Id"
);

-- Step 2: Restore missing MobSpawnMaturities by parsing area names
-- Only targets LocationIds that have no MobSpawnMaturities at all.
INSERT INTO "MobSpawnMaturities" ("LocationId", "MaturityId", "IsRare")
SELECT l."Id" AS "LocationId", mm."Id" AS "MaturityId", 0 AS "IsRare"
FROM ONLY "Locations" l
JOIN ONLY "Areas" a ON a."LocationId" = l."Id"
-- Parse comma-separated mob segments from the area name
CROSS JOIN LATERAL unnest(string_to_array(l."Name", ',')) AS raw_segment
CROSS JOIN LATERAL (SELECT trim(raw_segment) AS segment) AS seg
-- Split each segment into mob name and maturity part
CROSS JOIN LATERAL (
  SELECT
    CASE WHEN seg.segment LIKE '% - %' THEN trim(split_part(seg.segment, ' - ', 1))
         ELSE seg.segment END AS mob_name,
    CASE WHEN seg.segment LIKE '% - %' THEN split_part(seg.segment, ' - ', 2)
         ELSE 'Default' END AS maturity_part
) AS parsed
-- Split maturity part on '/' for multi-maturity segments
CROSS JOIN LATERAL unnest(string_to_array(parsed.maturity_part, '/')) AS raw_mat
CROSS JOIN LATERAL (SELECT trim(raw_mat) AS maturity_name) AS mat
JOIN ONLY "Mobs" m ON m."Name" = parsed.mob_name
JOIN ONLY "MobMaturities" mm ON mm."MobId" = m."Id"
  AND (
    -- Direct name match
    mm."Name" = mat.maturity_name
    OR (
      -- 'Default' resolves to the sole maturity when the mob has exactly one
      mat.maturity_name = 'Default'
      AND NOT EXISTS (
        SELECT 1 FROM ONLY "MobMaturities" mm2
        WHERE mm2."MobId" = m."Id" AND mm2."Id" != mm."Id"
      )
    )
  )
-- Only repair areas with no maturities at all
WHERE a."Type" = 'MobArea'
AND NOT EXISTS (
  SELECT 1 FROM ONLY "MobSpawnMaturities" msm WHERE msm."LocationId" = l."Id"
)
ON CONFLICT ("LocationId", "MaturityId") DO NOTHING;

COMMIT;
