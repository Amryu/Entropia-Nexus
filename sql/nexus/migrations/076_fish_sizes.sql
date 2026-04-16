-- Fish sizes (maturities). Each fish can have multiple size variants, each
-- with its own Strength stat and a ScrapsToRefine cost (number of "Fish
-- Scraps" material needed to refine into the fish's oil type).
--
-- Also adds FishOilItemId to Fish so every fish species knows which oil
-- material it produces, drops the flat Size/Strength columns that are
-- superseded by the per-size rows, and moves Biome from a single column
-- to an m:n junction table (FishBiomes) since fish can inhabit multiple
-- biomes.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. FishSizes table
-- ---------------------------------------------------------------------------

CREATE TABLE "FishSizes" (
    "Id"              SERIAL PRIMARY KEY,
    "FishId"          integer NOT NULL REFERENCES "Fish"("Id") ON DELETE CASCADE,
    "Name"            text NOT NULL,
    "Strength"        numeric,
    "ScrapsToRefine"  integer,
    UNIQUE ("FishId", "Name")
);

CREATE INDEX "FishSizes_FishId_idx" ON "FishSizes" ("FishId");

-- ---------------------------------------------------------------------------
-- 2. FishBiomes junction table (m:n, replaces Fish.Biome column)
-- ---------------------------------------------------------------------------

CREATE TABLE "FishBiomes" (
    "FishId" integer NOT NULL REFERENCES "Fish"("Id") ON DELETE CASCADE,
    "Biome"  "FishBiome" NOT NULL,
    PRIMARY KEY ("FishId", "Biome")
);

CREATE INDEX "FishBiomes_Biome_idx" ON "FishBiomes" ("Biome");

-- Migrate existing single-biome data into the junction table
INSERT INTO "FishBiomes" ("FishId", "Biome")
SELECT "Id", "Biome" FROM "Fish" WHERE "Biome" IS NOT NULL
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3. Fish table changes
-- ---------------------------------------------------------------------------

ALTER TABLE "Fish" ADD COLUMN "FishOilItemId" integer;
ALTER TABLE "Fish" DROP COLUMN IF EXISTS "Size";
ALTER TABLE "Fish" DROP COLUMN IF EXISTS "Strength";
ALTER TABLE "Fish" DROP COLUMN IF EXISTS "Biome";

-- ---------------------------------------------------------------------------
-- 4. Audit for FishSizes (reuse the helper pattern from 074)
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

SELECT pg_temp._create_audit_for('FishSizes');

-- ---------------------------------------------------------------------------
-- 5. Rebuild Fish audit table to reflect dropped/added columns
-- ---------------------------------------------------------------------------

-- Drop and recreate Fish audit to match new column layout
DROP TRIGGER IF EXISTS "Fish_audit_trigger" ON "Fish";
DROP TABLE IF EXISTS "Fish_audit";

SELECT pg_temp._create_audit_for('Fish');

-- ---------------------------------------------------------------------------
-- 6. Cache-invalidation triggers
-- ---------------------------------------------------------------------------

CREATE TRIGGER zz_track_change
    AFTER INSERT OR UPDATE OR DELETE ON "FishSizes"
    FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();

CREATE TRIGGER zz_track_change
    AFTER INSERT OR UPDATE OR DELETE ON "FishBiomes"
    FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();

-- ---------------------------------------------------------------------------
-- 7. Grants
-- ---------------------------------------------------------------------------

GRANT SELECT ON "FishSizes", "FishSizes_audit" TO nexus;
GRANT SELECT ON "FishBiomes" TO nexus;

GRANT SELECT, INSERT, UPDATE, DELETE ON "FishSizes" TO nexus_bot;
GRANT SELECT, INSERT, UPDATE, DELETE ON "FishBiomes" TO nexus_bot;
GRANT INSERT ON "FishSizes_audit" TO nexus_bot;
GRANT USAGE, SELECT ON SEQUENCE "FishSizes_Id_seq" TO nexus_bot;

-- ---------------------------------------------------------------------------
-- 8. FishSectorLocations (fine-grid: each server tile subdivided 4x4)
-- ---------------------------------------------------------------------------

CREATE TABLE "FishSectorLocations" (
    "FishId"    integer NOT NULL REFERENCES "Fish"("Id") ON DELETE CASCADE,
    "PlanetId"  integer NOT NULL REFERENCES "Planets"("Id") ON DELETE CASCADE,
    "SectorCol" integer NOT NULL,
    "SectorRow" integer NOT NULL,
    "Rarity"    text NOT NULL DEFAULT 'Common',
    "Note"      text,
    PRIMARY KEY ("FishId", "PlanetId", "SectorCol", "SectorRow")
);

CREATE INDEX "FishSectorLocations_PlanetId_idx" ON "FishSectorLocations" ("PlanetId");

CREATE TRIGGER zz_track_change
    AFTER INSERT OR UPDATE OR DELETE ON "FishSectorLocations"
    FOR EACH STATEMENT EXECUTE FUNCTION track_table_change();

GRANT SELECT ON "FishSectorLocations" TO nexus;
GRANT SELECT, INSERT, UPDATE, DELETE ON "FishSectorLocations" TO nexus_bot;

-- ---------------------------------------------------------------------------
-- 9. Rebuild Items VIEW to reflect Fish column changes
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

COMMIT;
