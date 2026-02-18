-- Remove duplicate Area locations in two passes:
--
-- Pass 1: Exact duplicates — same name, planet, area type, shape, and vertices.
--   Keeps the lowest Id. Affects 15 locations.
--
-- Pass 2: MobArea vertex duplicates — same planet and vertices but different names
--   (mob order swapped, mobs added/removed, planet qualifier added, maturities updated).
--   Keeps the entry with the most complete name (most maturities, most mobs, planet qualifier).
--   Affects 76 locations.
--
-- Excludes:
--   - Non-mob areas (names without " - ") — material resource spots, generic spawn areas
--   - LocationIds 2105/2391 — different mob lists sharing the same polygon (not duplicates)

BEGIN;

-- ── Pass 1: Exact name+vertex duplicates (all area types) ──────────────────────

CREATE TEMP TABLE _exact_dupes AS
WITH ranked AS (
  SELECT a."LocationId",
    ROW_NUMBER() OVER (
      PARTITION BY l."Name", l."PlanetId", a."Type", a."Shape", a."Data"
      ORDER BY l."Id"
    ) as rn
  FROM ONLY "Areas" a
  JOIN ONLY "Locations" l ON l."Id" = a."LocationId"
  WHERE l."Name" IS NOT NULL
)
SELECT "LocationId" FROM ranked WHERE rn > 1;

DELETE FROM ONLY "MobSpawnMaturities" WHERE "LocationId" IN (SELECT "LocationId" FROM _exact_dupes);
DELETE FROM ONLY "MobSpawns" WHERE "LocationId" IN (SELECT "LocationId" FROM _exact_dupes);
DELETE FROM ONLY "Areas" WHERE "LocationId" IN (SELECT "LocationId" FROM _exact_dupes);
DELETE FROM ONLY "Locations" WHERE "Id" IN (SELECT "LocationId" FROM _exact_dupes);

DROP TABLE _exact_dupes;

-- ── Pass 2: MobArea vertex duplicates with different names ─────────────────────
-- Ranking prefers: most maturities (slashes), most mobs (commas),
-- planet qualifier present, longest name, newest Id as tiebreaker.

CREATE TEMP TABLE _vertex_dupes AS
WITH ranked AS (
  SELECT a."LocationId",
    ROW_NUMBER() OVER (
      PARTITION BY l."PlanetId", a."Data"
      ORDER BY
        (LENGTH(l."Name") - LENGTH(REPLACE(l."Name", '/', ''))) DESC,
        (LENGTH(l."Name") - LENGTH(REPLACE(l."Name", ',', ''))) DESC,
        CASE WHEN l."Name" LIKE '%(%)%' THEN 1 ELSE 0 END DESC,
        LENGTH(l."Name") DESC,
        l."Id" DESC
    ) as rn
  FROM ONLY "Areas" a
  JOIN ONLY "Locations" l ON l."Id" = a."LocationId"
  WHERE a."Type" = 'MobArea'
    AND l."Name" IS NOT NULL
    AND l."Name" LIKE '% - %'
    AND l."Id" NOT IN (2105, 2391)
)
SELECT "LocationId" FROM ranked WHERE rn > 1;

DELETE FROM ONLY "MobSpawnMaturities" WHERE "LocationId" IN (SELECT "LocationId" FROM _vertex_dupes);
DELETE FROM ONLY "MobSpawns" WHERE "LocationId" IN (SELECT "LocationId" FROM _vertex_dupes);
DELETE FROM ONLY "Areas" WHERE "LocationId" IN (SELECT "LocationId" FROM _vertex_dupes);
DELETE FROM ONLY "Locations" WHERE "Id" IN (SELECT "LocationId" FROM _vertex_dupes);

DROP TABLE _vertex_dupes;

COMMIT;
