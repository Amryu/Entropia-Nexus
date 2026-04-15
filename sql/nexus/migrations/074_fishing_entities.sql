-- Fishing/cooking feature: blueprint type additions + new tools, attachments,
-- fish entity, and food item type.
--
-- Adds everything the DB needs for the fishing and cooking feature after
-- 072 (skills/professions) and 073 (profession category rename). Frontend
-- wiring (common/itemTypes.js, blueprint edit form) is updated in the
-- same commit; Fish info page + API live in separate files.
--
-- Contents:
--   1. BlueprintType enum gains 5 new values.
--   2. New enums: FishingRodType, FishBiome, FishTimeOfDay, FishDifficulty.
--   3. FishingRods table (tool subtype) - audit via helper.
--   4. FishingReels / FishingBlanks / FishingLines / FishingLures tables
--      (attachment subtypes) - audit via helper.
--   5. Fish info entity + FishPlanets + FishRodTypes junctions - audit via
--      helper for Fish (junctions stay audit-free).
--   6. Tools / Attachments / Items VIEWs updated to include the new tables.
--      The Items VIEW tags Fish materials with Type='Fish' via a LEFT JOIN
--      on the new Fish table, so fishes filter out from plain Materials.
--      Food items live in the existing Consumables table with
--      Consumables.Type = 'Food'; the Items VIEW promotes those rows to
--      Items.Type = 'Food' instead of 'Consumable'.
--
-- PG 16 allows ALTER TYPE ... ADD VALUE inside a transaction as long as the
-- new values are not referenced in the same transaction. That is the case
-- here, so everything runs inside one BEGIN/COMMIT.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Enum additions to existing types
-- ---------------------------------------------------------------------------

-- BlueprintType gains 5 new values for the new crafting professions.
ALTER TYPE "BlueprintType" ADD VALUE IF NOT EXISTS 'Fishing Gear';
ALTER TYPE "BlueprintType" ADD VALUE IF NOT EXISTS 'Fishing Attachment';
ALTER TYPE "BlueprintType" ADD VALUE IF NOT EXISTS 'Gastronomer';
ALTER TYPE "BlueprintType" ADD VALUE IF NOT EXISTS 'Provisioner';
ALTER TYPE "BlueprintType" ADD VALUE IF NOT EXISTS 'Nutritionist';

-- CodexType gains 'Fish' so fish species sit in their own codex bucket.
-- Every Fish.SpeciesId → MobSpecies row is expected to carry
-- CodexType='Fish'; the Fish upsert path enforces this.
ALTER TYPE "CodexType" ADD VALUE IF NOT EXISTS 'Fish';

-- ---------------------------------------------------------------------------
-- 2. New enums
-- ---------------------------------------------------------------------------

CREATE TYPE "FishingRodType" AS ENUM (
    'Casting',
    'Angling',
    'Fly Fishing',
    'Deep Ocean Fishing',
    'Baitfishing'
);

CREATE TYPE "FishBiome" AS ENUM (
    'Sea',
    'River',
    'Lake',
    'Deep Ocean',
    'Sky'
);

CREATE TYPE "FishTimeOfDay" AS ENUM (
    'Day',
    'Night'
);

CREATE TYPE "FishDifficulty" AS ENUM (
    'Easy',
    'Medium',
    'Hard',
    'Very Hard',
    'Elite'
);

-- ---------------------------------------------------------------------------
-- 3. Entity tables (no audit yet; audit helper runs at the end)
--
-- FishingRods: tool subtype, standalone like MiscTools / MedicalTools.
-- Items.Id = FishingRods.Id + 4900000 (via Tools VIEW offset below).
-- ---------------------------------------------------------------------------

CREATE TABLE "FishingRods" (
    "Id"           SERIAL PRIMARY KEY,
    "Name"         text NOT NULL,
    "Type"         text NOT NULL DEFAULT 'FishingRod',
    "Weight"       numeric,
    "Decay"        numeric,
    "MaxTT"        numeric,
    "MinTT"        numeric,
    "ProfessionId" integer,
    "IsSib"        integer,
    "MinLevel"     numeric,
    "MaxLevel"     numeric,
    "Strength"     numeric,
    "Flexibility"  numeric,
    "RodType"      "FishingRodType" NOT NULL,
    "Description"  text
);

-- ---------------------------------------------------------------------------
-- 4. Fishing attachment subtypes
-- ---------------------------------------------------------------------------

CREATE TABLE "FishingReels" (
    "Id"          SERIAL PRIMARY KEY,
    "Name"        text NOT NULL,
    "Type"        text NOT NULL DEFAULT 'FishingReel',
    "Weight"      numeric,
    "Decay"       numeric,
    "MaxTT"       numeric,
    "Strength"    numeric,
    "Speed"       numeric,
    "Description" text
);

CREATE TABLE "FishingBlanks" (
    "Id"          SERIAL PRIMARY KEY,
    "Name"        text NOT NULL,
    "Type"        text NOT NULL DEFAULT 'FishingBlank',
    "Weight"      numeric,
    "Decay"       numeric,
    "MaxTT"       numeric,
    "Strength"    numeric,
    "Flexibility" numeric,
    "Description" text
);

CREATE TABLE "FishingLines" (
    "Id"          SERIAL PRIMARY KEY,
    "Name"        text NOT NULL,
    "Type"        text NOT NULL DEFAULT 'FishingLine',
    "Weight"      numeric,
    "Decay"       numeric,
    "MaxTT"       numeric,
    "Flexibility" numeric,
    "Strength"    numeric,
    "Length"      numeric,
    "Description" text
);

CREATE TABLE "FishingLures" (
    "Id"          SERIAL PRIMARY KEY,
    "Name"        text NOT NULL,
    "Type"        text NOT NULL DEFAULT 'FishingLure',
    "Weight"      numeric,
    "Decay"       numeric,
    "MaxTT"       numeric,
    "Depth"       numeric,
    "Quality"     numeric,
    "Description" text
);

-- ---------------------------------------------------------------------------
-- 5. Fish info entity + junctions.
--
-- Fish is a hybrid: every row links to an Items row (the fish as a Material)
-- and a MobSpecies row (the codex entry). Both FKs are NOT NULL - a fish
-- cannot exist without a material item and a species entry.
--
-- Catchability per rod type is stored in FishRodTypes (m:n), not a column
-- on Fish, because a fish can be catchable by multiple rod types.
-- ---------------------------------------------------------------------------

CREATE TABLE "Fish" (
    "Id"              SERIAL PRIMARY KEY,
    "Name"            text NOT NULL,
    "ItemId"          integer NOT NULL,
    "SpeciesId"       integer NOT NULL REFERENCES "MobSpecies"("Id") ON DELETE RESTRICT,
    "Biome"           "FishBiome",
    "Size"            numeric,
    "Strength"        numeric,
    "Difficulty"      "FishDifficulty",
    "MinDepth"        numeric,
    "PreferredLureId" integer,
    "TimeOfDay"       "FishTimeOfDay",
    "Description"     text
);

CREATE UNIQUE INDEX "Fish_ItemId_idx"    ON "Fish" ("ItemId");
CREATE INDEX        "Fish_SpeciesId_idx" ON "Fish" ("SpeciesId");

CREATE TABLE "FishPlanets" (
    "FishId"   integer NOT NULL REFERENCES "Fish"("Id") ON DELETE CASCADE,
    "PlanetId" integer NOT NULL REFERENCES "Planets"("Id") ON DELETE CASCADE,
    PRIMARY KEY ("FishId", "PlanetId")
);

CREATE INDEX "FishPlanets_PlanetId_idx" ON "FishPlanets" ("PlanetId");

CREATE TABLE "FishRodTypes" (
    "FishId"  integer NOT NULL REFERENCES "Fish"("Id") ON DELETE CASCADE,
    "RodType" "FishingRodType" NOT NULL,
    PRIMARY KEY ("FishId", "RodType")
);

CREATE INDEX "FishRodTypes_RodType_idx" ON "FishRodTypes" ("RodType");

-- ---------------------------------------------------------------------------
-- 6. Audit tables + triggers (canonical pattern from
--    sql-util/create_audit_table_single.sql). A temporary helper function
--    mirrors that script so we can call it once per table.
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

SELECT pg_temp._create_audit_for('FishingRods');
SELECT pg_temp._create_audit_for('FishingReels');
SELECT pg_temp._create_audit_for('FishingBlanks');
SELECT pg_temp._create_audit_for('FishingLines');
SELECT pg_temp._create_audit_for('FishingLures');
SELECT pg_temp._create_audit_for('Fish');

-- ---------------------------------------------------------------------------
-- 7. TableChanges tracking for cache invalidation (all new tables incl. junctions)
-- ---------------------------------------------------------------------------

CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "FishingRods"   FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();
CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "FishingReels"  FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();
CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "FishingBlanks" FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();
CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "FishingLines"  FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();
CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "FishingLures"  FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();
CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "Fish"          FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();
CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "FishPlanets"   FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();
CREATE TRIGGER zz_track_change AFTER INSERT OR UPDATE OR DELETE ON "FishRodTypes"  FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();

-- ---------------------------------------------------------------------------
-- 8. Grants
--
-- Pattern mirrors existing wiki-editable entity tables (see MiscTools/
-- ClassIds prod grants):
--   nexus     -> SELECT on the entity table + its audit
--   nexus_bot -> SELECT/INSERT/UPDATE/DELETE on the entity table,
--                INSERT on the audit (required because the audit trigger
--                runs as the invoker and inserts into the audit table),
--                USAGE/SELECT on the sequence for RETURNING Id inserts
-- ---------------------------------------------------------------------------

-- nexus: read-only on every new entity table + junction + audit
GRANT SELECT ON
    "FishingRods", "FishingReels", "FishingBlanks", "FishingLines", "FishingLures",
    "Fish", "FishPlanets", "FishRodTypes"
TO nexus;

GRANT SELECT ON
    "FishingRods_audit", "FishingReels_audit", "FishingBlanks_audit",
    "FishingLines_audit", "FishingLures_audit", "Fish_audit"
TO nexus;

-- nexus_bot: full CRUD on entity tables + junctions
GRANT SELECT, INSERT, UPDATE, DELETE ON
    "FishingRods", "FishingReels", "FishingBlanks", "FishingLines", "FishingLures",
    "Fish", "FishPlanets", "FishRodTypes"
TO nexus_bot;

-- nexus_bot: INSERT on audit tables so the after-row audit triggers can
-- write their rows while running under nexus_bot's session.
GRANT INSERT ON
    "FishingRods_audit", "FishingReels_audit", "FishingBlanks_audit",
    "FishingLines_audit", "FishingLures_audit", "Fish_audit"
TO nexus_bot;

-- nexus_bot: sequence usage for SERIAL PK tables (junctions have composite
-- PKs and no sequence, so they're excluded).
GRANT USAGE, SELECT ON SEQUENCE
    "FishingRods_Id_seq",
    "FishingReels_Id_seq",
    "FishingBlanks_Id_seq",
    "FishingLines_Id_seq",
    "FishingLures_Id_seq",
    "Fish_Id_seq"
TO nexus_bot;

-- ---------------------------------------------------------------------------
-- 9. VIEW updates: Tools, Attachments, Items.
--
-- Tools and Attachments are UNION ALL views with per-subtype Id offsets.
-- Items is also a UNION ALL view that adds a higher-level offset on top.
-- Fishing rods become Tools (+900000 within Tools, final Items offset
-- +4900000). Fishing attachments become Attachments (+800000..+830000
-- within Attachments, final Items offset +5800000..+5830000).
--
-- Items view tweaks:
--   * Materials with a matching Fish row surface as Type='Fish' instead of
--     'Material'.
--   * Consumables with Type='Food' surface as Items.Type='Food' instead of
--     'Consumable'. Food shares the Consumables table; no separate Foods
--     table.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "Tools" AS
 SELECT ("MedicalTools"."Id" + 100000) AS "Id", "MedicalTools"."Name", "MedicalTools"."MaxTT", "MedicalTools"."Weight", 'MedicalTool'::text AS "Type"
   FROM ONLY "MedicalTools"
UNION ALL
 SELECT ("MiscTools"."Id" + 200000) AS "Id", "MiscTools"."Name", "MiscTools"."MaxTT", "MiscTools"."Weight", 'MiscTool'::text AS "Type"
   FROM ONLY "MiscTools"
UNION ALL
 SELECT ("Refiners"."Id" + 300000) AS "Id", "Refiners"."Name", "Refiners"."MaxTT", "Refiners"."Weight", 'Refiner'::text AS "Type"
   FROM ONLY "Refiners"
UNION ALL
 SELECT ("Scanners"."Id" + 400000) AS "Id", "Scanners"."Name", "Scanners"."MaxTT", "Scanners"."Weight", 'Scanner'::text AS "Type"
   FROM ONLY "Scanners"
UNION ALL
 SELECT ("Finders"."Id" + 500000) AS "Id", "Finders"."Name", "Finders"."MaxTT", "Finders"."Weight", 'Finder'::text AS "Type"
   FROM ONLY "Finders"
UNION ALL
 SELECT ("Excavators"."Id" + 600000) AS "Id", "Excavators"."Name", "Excavators"."MaxTT", "Excavators"."Weight", 'Excavator'::text AS "Type"
   FROM ONLY "Excavators"
UNION ALL
 SELECT ("BlueprintBooks"."Id" + 700000) AS "Id", "BlueprintBooks"."Name", "BlueprintBooks"."Value" AS "MaxTT", "BlueprintBooks"."Weight", 'BlueprintBook'::text AS "Type"
   FROM ONLY "BlueprintBooks"
UNION ALL
 SELECT ("MedicalChips"."Id" + 800000) AS "Id", "MedicalChips"."Name", "MedicalChips"."MaxTT", "MedicalChips"."Weight", 'MedicalChip'::text AS "Type"
   FROM ONLY "MedicalChips"
UNION ALL
 SELECT ("TeleportationChips"."Id" + 810000) AS "Id", "TeleportationChips"."Name", "TeleportationChips"."MaxTT", "TeleportationChips"."Weight", 'TeleportationChip'::text AS "Type"
   FROM ONLY "TeleportationChips"
UNION ALL
 SELECT ("EffectChips"."Id" + 820000) AS "Id", "EffectChips"."Name", "EffectChips"."MaxTT", "EffectChips"."Weight", 'EffectChip'::text AS "Type"
   FROM ONLY "EffectChips"
UNION ALL
 SELECT ("FishingRods"."Id" + 900000) AS "Id", "FishingRods"."Name", "FishingRods"."MaxTT", "FishingRods"."Weight", 'FishingRod'::text AS "Type"
   FROM ONLY "FishingRods";


CREATE OR REPLACE VIEW "Attachments" AS
 SELECT ("WeaponAmplifiers"."Id" + 100000) AS "Id", "WeaponAmplifiers"."Name", "WeaponAmplifiers"."MaxTT", "WeaponAmplifiers"."Weight", 'WeaponAmplifier'::text AS "Type"
   FROM ONLY "WeaponAmplifiers"
UNION ALL
 SELECT ("WeaponVisionAttachments"."Id" + 200000) AS "Id", "WeaponVisionAttachments"."Name", "WeaponVisionAttachments"."MaxTT", "WeaponVisionAttachments"."Weight", 'WeaponVisionAttachment'::text AS "Type"
   FROM ONLY "WeaponVisionAttachments"
UNION ALL
 SELECT ("Absorbers"."Id" + 300000) AS "Id", "Absorbers"."Name", "Absorbers"."MaxTT", "Absorbers"."Weight", 'Absorber'::text AS "Type"
   FROM ONLY "Absorbers"
UNION ALL
 SELECT ("FinderAmplifiers"."Id" + 400000) AS "Id", "FinderAmplifiers"."Name", "FinderAmplifiers"."MaxTT", "FinderAmplifiers"."Weight", 'FinderAmplifier'::text AS "Type"
   FROM ONLY "FinderAmplifiers"
UNION ALL
 SELECT ("ArmorPlatings"."Id" + 500000) AS "Id", "ArmorPlatings"."Name", "ArmorPlatings"."MaxTT", "ArmorPlatings"."Weight", 'ArmorPlating'::text AS "Type"
   FROM ONLY "ArmorPlatings"
UNION ALL
 SELECT ("Enhancers"."Id" + 600000) AS "Id", "Enhancers"."Name", "Enhancers"."Value" AS "MaxTT", "Enhancers"."Weight", 'Enhancer'::text AS "Type"
   FROM ONLY "Enhancers"
UNION ALL
 SELECT ("MindforceImplants"."Id" + 700000) AS "Id", "MindforceImplants"."Name", "MindforceImplants"."MaxTT", "MindforceImplants"."Weight", 'MindforceImplant'::text AS "Type"
   FROM ONLY "MindforceImplants"
UNION ALL
 SELECT ("FishingReels"."Id"  + 800000) AS "Id", "FishingReels"."Name",  "FishingReels"."MaxTT",  "FishingReels"."Weight",  'FishingReel'::text  AS "Type" FROM ONLY "FishingReels"
UNION ALL
 SELECT ("FishingBlanks"."Id" + 810000) AS "Id", "FishingBlanks"."Name", "FishingBlanks"."MaxTT", "FishingBlanks"."Weight", 'FishingBlank'::text AS "Type" FROM ONLY "FishingBlanks"
UNION ALL
 SELECT ("FishingLines"."Id"  + 820000) AS "Id", "FishingLines"."Name",  "FishingLines"."MaxTT",  "FishingLines"."Weight",  'FishingLine'::text  AS "Type" FROM ONLY "FishingLines"
UNION ALL
 SELECT ("FishingLures"."Id"  + 830000) AS "Id", "FishingLures"."Name",  "FishingLures"."MaxTT",  "FishingLures"."Weight",  'FishingLure'::text  AS "Type" FROM ONLY "FishingLures";


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

GRANT SELECT ON "Tools", "Attachments", "Items" TO "nexus", nexus_bot;

COMMIT;
