-- Flatten Fish model: every in-game fish size is its own Fish row.
--
-- Before this migration a single Fish row grouped its size stages via
-- FishSizes (Juvenile/Adult/Ancient/...) with per-size Strength,
-- ScrapsToRefine, and a dedicated Materials ItemId. In-game, each size
-- stage is actually its own distinct fish with its own spawn window,
-- rod/water, rarity. The wiki's nesting was a presentation shortcut that
-- doesn't match game data, so we:
--
-- 1. Pull Strength, ScrapsToRefine, and the per-size ItemId onto Fish
--    itself, plus add a new Weight column (catalog rarity weight).
-- 2. Auto-split each existing Fish row into N rows (one per FishSize),
--    cloning all junction rows and renaming to the size's Name.
-- 3. Replace the FishDifficulty enum with FishTier (drop 'Elite').
-- 4. Seed the 11 family MobSpecies (Cod, Carp, Eel, Tuna, Pike, Bass,
--    Catfish, Salmon, Sturgeon, Swordfish, Misc) so the Species field on
--    Fish maps to the fish family going forward.
-- 5. Drop FishSizes + audit.
-- 6. Rebuild the Items VIEW and the UndiscoveredFishItemIds VIEW (both
--    referenced FishSizes.ItemId).

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. New columns on Fish
-- ---------------------------------------------------------------------------

ALTER TABLE "Fish"
  ADD COLUMN "Strength"       numeric,
  ADD COLUMN "ScrapsToRefine" integer,
  ADD COLUMN "Weight"         numeric,
  ADD COLUMN "ItemId"         integer,
  ADD CONSTRAINT "Fish_Strength_nonneg_chk"
    CHECK ("Strength" IS NULL OR "Strength" >= 0),
  ADD CONSTRAINT "Fish_ScrapsToRefine_nonneg_chk"
    CHECK ("ScrapsToRefine" IS NULL OR "ScrapsToRefine" >= 0),
  ADD CONSTRAINT "Fish_Weight_range_chk"
    CHECK ("Weight" IS NULL OR ("Weight" >= 0 AND "Weight" <= 1));

CREATE UNIQUE INDEX "Fish_ItemId_idx" ON "Fish" ("ItemId") WHERE "ItemId" IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 2. Seed family MobSpecies rows (idempotent)
-- ---------------------------------------------------------------------------

INSERT INTO "MobSpecies" ("Name", "CodexBaseCost", "CodexType")
SELECT f, 6, 'Fish'::"CodexType"
  FROM (VALUES
    ('Cod'), ('Carp'), ('Eel'), ('Tuna'), ('Pike'),
    ('Bass'), ('Catfish'), ('Salmon'), ('Sturgeon'),
    ('Swordfish'), ('Misc')
  ) AS families(f)
ON CONFLICT ("Name") DO UPDATE
  SET "CodexType"    = 'Fish'::"CodexType",
      "CodexBaseCost" = COALESCE("MobSpecies"."CodexBaseCost", 6);

-- ---------------------------------------------------------------------------
-- 3. Auto-split existing Fish rows into per-size rows
--
-- For each Fish f with FishSizes rows (ordered by FishSizes.Id):
--   - First size: UPDATE the original Fish row in place.
--   - Remaining sizes: INSERT new Fish rows cloning all scalar fields +
--     replicating junction tables (FishBiomes, FishRodTypes, FishPlanets,
--     FishSectorLocations).
--
-- Fish rows with zero sizes are left untouched (Strength / ScrapsToRefine /
-- ItemId stay NULL; editor / seed script fills them in later).
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  f_row      RECORD;
  size_row   RECORD;
  is_first   BOOLEAN;
  new_fish_id integer;
BEGIN
  FOR f_row IN
    SELECT f."Id" AS fish_id
      FROM ONLY "Fish" f
      JOIN ONLY "FishSizes" fs ON fs."FishId" = f."Id"
      GROUP BY f."Id"
      ORDER BY f."Id"
  LOOP
    is_first := TRUE;
    FOR size_row IN
      SELECT "Id", "Name", "Strength", "ScrapsToRefine", "ItemId"
        FROM ONLY "FishSizes"
       WHERE "FishId" = f_row.fish_id
       ORDER BY "Id"
    LOOP
      IF is_first THEN
        UPDATE ONLY "Fish"
           SET "Name"           = size_row."Name",
               "Strength"       = size_row."Strength",
               "ScrapsToRefine" = size_row."ScrapsToRefine",
               "ItemId"         = size_row."ItemId"
         WHERE "Id" = f_row.fish_id;
        is_first := FALSE;
      ELSE
        INSERT INTO "Fish" (
          "Name", "Description", "SpeciesId", "Difficulty", "MinDepth",
          "PreferredLureTypes", "FishOilItemId",
          "TimeOfDayStart", "TimeOfDayEnd",
          "Strength", "ScrapsToRefine", "ItemId"
        )
        SELECT size_row."Name",
               f."Description", f."SpeciesId", f."Difficulty", f."MinDepth",
               f."PreferredLureTypes", f."FishOilItemId",
               f."TimeOfDayStart", f."TimeOfDayEnd",
               size_row."Strength", size_row."ScrapsToRefine", size_row."ItemId"
          FROM ONLY "Fish" f
         WHERE f."Id" = f_row.fish_id
        RETURNING "Id" INTO new_fish_id;

        -- Replicate junction rows
        INSERT INTO "FishBiomes" ("FishId", "Biome")
        SELECT new_fish_id, b."Biome"
          FROM "FishBiomes" b
         WHERE b."FishId" = f_row.fish_id
        ON CONFLICT DO NOTHING;

        INSERT INTO "FishRodTypes" ("FishId", "RodType")
        SELECT new_fish_id, rt."RodType"
          FROM "FishRodTypes" rt
         WHERE rt."FishId" = f_row.fish_id
        ON CONFLICT DO NOTHING;

        INSERT INTO "FishPlanets" ("FishId", "PlanetId")
        SELECT new_fish_id, p."PlanetId"
          FROM "FishPlanets" p
         WHERE p."FishId" = f_row.fish_id
        ON CONFLICT DO NOTHING;

        INSERT INTO "FishSectorLocations"
          ("FishId", "PlanetId", "SectorCol", "SectorRow", "Rarity", "Note")
        SELECT new_fish_id, s."PlanetId", s."SectorCol", s."SectorRow",
               s."Rarity", s."Note"
          FROM "FishSectorLocations" s
         WHERE s."FishId" = f_row.fish_id
        ON CONFLICT DO NOTHING;
      END IF;
    END LOOP;
  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- 4. Rebuild Items VIEW: swap FishSizes.ItemId join for Fish.ItemId
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "Items" AS
 SELECT ("Materials"."Id" + 1000000) AS "Id",
        "Materials"."Name",
        "Materials"."Value",
        "Materials"."Weight",
        CASE WHEN f."Id" IS NOT NULL THEN 'Fish'::text ELSE 'Material'::text END AS "Type"
   FROM ONLY "Materials"
   LEFT JOIN ONLY "Fish" f ON f."ItemId" = ("Materials"."Id" + 1000000)
UNION ALL
 SELECT ("Weapons"."Id" + 2000000) AS "Id", "Weapons"."Name", "Weapons"."MaxTT" AS "Value", "Weapons"."Weight", 'Weapon'::text AS "Type"
   FROM ONLY "Weapons"
UNION ALL
 SELECT ("Armors"."Id" + 3000000) AS "Id", "Armors"."Name", "Armors"."MaxTT" AS "Value", "Armors"."Weight", 'Armor'::text AS "Type"
   FROM ONLY "Armors"
UNION ALL
 SELECT ("Tools"."Id" + 4000000) AS "Id", "Tools"."Name", "Tools"."MaxTT" AS "Value", "Tools"."Weight", "Tools"."Type"
   FROM "Tools"
UNION ALL
 SELECT ("Attachments"."Id" + 5000000) AS "Id", "Attachments"."Name", "Attachments"."MaxTT" AS "Value", "Attachments"."Weight", "Attachments"."Type"
   FROM "Attachments"
UNION ALL
 SELECT ("Blueprints"."Id" + 6000000) AS "Id", "Blueprints"."Name", 1 AS "Value", 0.1 AS "Weight", 'Blueprint'::text AS "Type"
   FROM ONLY "Blueprints"
UNION ALL
 SELECT ("Vehicles"."Id" + 7000000) AS "Id", "Vehicles"."Name", "Vehicles"."MaxTT" AS "Value", "Vehicles"."Weight", 'Vehicle'::text AS "Type"
   FROM ONLY "Vehicles"
UNION ALL
 SELECT ("Clothes"."Id" + 8000000) AS "Id", "Clothes"."Name", "Clothes"."MaxTT" AS "Value", "Clothes"."Weight", 'Clothing'::text AS "Type"
   FROM ONLY "Clothes"
UNION ALL
 SELECT ("Furnishings"."Id" + 9000000) AS "Id", "Furnishings"."Name", "Furnishings"."MaxTT" AS "Value", "Furnishings"."Weight", "Furnishings"."Type"
   FROM "Furnishings"
UNION ALL
 SELECT ("Consumables"."Id" + 10000000) AS "Id",
        "Consumables"."Name",
        "Consumables"."Value",
        "Consumables"."Weight",
        CASE WHEN "Consumables"."Type" = 'Food' THEN 'Food'::text ELSE 'Consumable'::text END AS "Type"
   FROM ONLY "Consumables"
UNION ALL
 SELECT ("CreatureControlCapsules"."Id" + 10100000) AS "Id", "CreatureControlCapsules"."Name", "CreatureControlCapsules"."MaxTT" AS "Value", "CreatureControlCapsules"."Weight", 'Capsule'::text AS "Type"
   FROM ONLY "CreatureControlCapsules"
UNION ALL
 SELECT ("Pets"."Id" + 11000000) AS "Id", "Pets"."Name", 0 AS "Value", 0 AS "Weight", 'Pet'::text AS "Type"
   FROM ONLY "Pets"
UNION ALL
 SELECT ("Strongboxes"."Id" + 12000000) AS "Id", "Strongboxes"."Name", 0.00001 AS "Value", 0 AS "Weight", 'Strongbox'::text AS "Type"
   FROM ONLY "Strongboxes";

GRANT SELECT ON "Items" TO "nexus", nexus_bot;

-- ---------------------------------------------------------------------------
-- 5. Rebuild UndiscoveredFishItemIds (migration 089): Fish.ItemId branch
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "UndiscoveredFishItemIds" AS
  SELECT "Id" FROM (
    SELECT f."FishOilItemId" AS "Id",
           (fd."FishId" IS NOT NULL) AS discovered
      FROM ONLY "Fish" f
      LEFT JOIN "FishDiscoveries" fd ON fd."FishId" = f."Id"
      WHERE f."FishOilItemId" IS NOT NULL
    UNION ALL
    SELECT f."ItemId" AS "Id",
           (fd."FishId" IS NOT NULL) AS discovered
      FROM ONLY "Fish" f
      LEFT JOIN "FishDiscoveries" fd ON fd."FishId" = f."Id"
      WHERE f."ItemId" IS NOT NULL
  ) x
  GROUP BY "Id"
  HAVING bool_or(discovered) = FALSE;

GRANT SELECT ON "UndiscoveredFishItemIds" TO nexus;

-- ---------------------------------------------------------------------------
-- 6. Drop FishSizes (table + audit + triggers)
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS zz_track_change ON "FishSizes";
DROP TRIGGER IF EXISTS "FishSizes_audit_trigger" ON "FishSizes";
DROP TABLE IF EXISTS "FishSizes_audit";
DROP TABLE IF EXISTS "FishSizes";
DROP FUNCTION IF EXISTS "FishSizes_audit_trigger"();

-- ---------------------------------------------------------------------------
-- 7. Swap Difficulty enum FishDifficulty -> FishTier (drop 'Elite')
-- ---------------------------------------------------------------------------

-- Null out any existing 'Elite' data before the cast.
UPDATE ONLY "Fish" SET "Difficulty" = NULL WHERE "Difficulty"::text = 'Elite';

CREATE TYPE "FishTier" AS ENUM ('Easy', 'Medium', 'Hard', 'Very Hard');

-- Fish_audit inherits Fish and its Difficulty column will be updated by
-- the ALTER too. Drop it first so the rebuild picks up the final column
-- list cleanly.
DROP TRIGGER IF EXISTS "Fish_audit_trigger" ON "Fish";
DROP TABLE IF EXISTS "Fish_audit";

ALTER TABLE "Fish"
  ALTER COLUMN "Difficulty" TYPE "FishTier"
    USING ("Difficulty"::text::"FishTier");

DROP TYPE "FishDifficulty";

-- ---------------------------------------------------------------------------
-- 8. Rebuild Fish_audit to match new column layout
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION pg_temp._create_audit_for(tbl_name text) RETURNS void AS $outer$
DECLARE
    col_def TEXT := '';
    col_def_temp TEXT;
    check_constraint RECORD;
    audit_table_exists BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = format('%s_audit', tbl_name)
    ) INTO audit_table_exists;

    FOR col_def_temp IN (
        SELECT
            '"' || column_name || '" ' ||
            CASE
                WHEN data_type = 'numeric' AND numeric_precision IS NOT NULL AND numeric_scale IS NOT NULL THEN
                    'numeric(' || numeric_precision || ',' || numeric_scale || ')'
                WHEN data_type = 'character varying' AND character_maximum_length IS NOT NULL THEN
                    'character varying(' || character_maximum_length || ')'
                WHEN data_type = 'character' AND character_maximum_length IS NOT NULL THEN
                    'character(' || character_maximum_length || ')'
                WHEN data_type = 'text' THEN
                    'text COLLATE pg_catalog."default"'
                WHEN data_type = 'USER-DEFINED' THEN
                    '"' || udt_name || '"'
                WHEN data_type = 'ARRAY' THEN
                    '"' || substring(udt_name from 2) || '"[]'
                ELSE
                    COALESCE((SELECT typname FROM pg_type WHERE typname = udt_name), data_type)
            END ||
            (CASE WHEN is_nullable = 'NO' THEN ' NOT NULL' ELSE '' END)
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = tbl_name
        ORDER BY ordinal_position
    ) LOOP
        col_def := col_def || ', ' || col_def_temp;
    END LOOP;

    EXECUTE format('
        CREATE TABLE IF NOT EXISTS "%1$s_audit" (
            operation CHAR(1) NOT NULL,
            stamp     TIMESTAMP NOT NULL,
            userid    TEXT NOT NULL
            %2$s
        );
    ', tbl_name, col_def);

    FOR check_constraint IN (
        SELECT conname, pg_get_constraintdef(oid) AS condef
        FROM pg_constraint
        WHERE conrelid = ('public.' || quote_ident(tbl_name))::regclass
          AND contype = 'c'
    ) LOOP
        EXECUTE format('ALTER TABLE "%1$s_audit" ADD CONSTRAINT "%2$s" %3$s',
                       tbl_name, check_constraint.conname, check_constraint.condef);
    END LOOP;

    EXECUTE format('ALTER TABLE "%1$s_audit" INHERIT "%1$s";', tbl_name);

    IF NOT audit_table_exists THEN
        EXECUTE format($fn$
            CREATE OR REPLACE FUNCTION "%1$s_audit_trigger"() RETURNS TRIGGER AS $func$
            BEGIN
                IF (TG_OP = 'DELETE') THEN
                    INSERT INTO "%1$s_audit" SELECT 'D', now(), current_user, OLD.*;
                    RETURN OLD;
                ELSIF (TG_OP = 'UPDATE') THEN
                    INSERT INTO "%1$s_audit" SELECT 'U', now(), current_user, NEW.*;
                    RETURN NEW;
                ELSIF (TG_OP = 'INSERT') THEN
                    INSERT INTO "%1$s_audit" SELECT 'I', now(), current_user, NEW.*;
                    RETURN NEW;
                END IF;
                RETURN NULL;
            END;
            $func$ LANGUAGE plpgsql;
        $fn$, tbl_name);

        EXECUTE format('DROP TRIGGER IF EXISTS "%1$s_audit_trigger" ON "%1$s";', tbl_name);
        EXECUTE format('
            CREATE TRIGGER "%1$s_audit_trigger"
            AFTER INSERT OR UPDATE OR DELETE ON "%1$s"
            FOR EACH ROW EXECUTE FUNCTION "%1$s_audit_trigger"();
        ', tbl_name);

        EXECUTE format('INSERT INTO "%1$s_audit" SELECT ''I'', now(), current_user, * FROM "%1$s";', tbl_name);
    END IF;
END;
$outer$ LANGUAGE plpgsql;

SELECT pg_temp._create_audit_for('Fish');

GRANT SELECT ON "Fish_audit" TO nexus;
GRANT INSERT ON "Fish_audit" TO nexus_bot;

COMMIT;
