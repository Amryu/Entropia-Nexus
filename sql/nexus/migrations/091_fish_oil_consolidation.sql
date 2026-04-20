-- Consolidate fish oil: one oil per *family*, resolved via naming convention
-- at the API layer (no DB FK).
--
-- Before this migration every Fish row carried its own FishOilItemId, so a
-- family like Cod had up to 10 fish rows all referencing the same "Cod Fish
-- Oil" item (or, legacy, per-fish oils like "Calypsocod Fish Oil"). Fish
-- oil is a family-level attribute in the game.
--
-- Rather than tracking the link through another FK column, we rely on the
-- convention that the oil material is named "{FamilyName} Fish Oil" and
-- let the API/SQL views join by name. The migration:
--
--   1. Drops Fish_audit (its local FishOilItemId column would block the
--      DROP COLUMN below).
--   2. Seeds the 10 family oil Materials so the name-based join always
--      resolves post-migration.
--   3. Rebuilds the UndiscoveredFishItemIds view first — the old version
--      from migration 089 reads Fish.FishOilItemId, which would otherwise
--      block the DROP COLUMN that follows.
--   4. Drops Fish.FishOilItemId.
--   5. Rebuilds Fish_audit against the new column layout.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Drop Fish_audit so the DROP COLUMN later is unblocked
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS "Fish_audit_trigger" ON "Fish";
DROP TABLE IF EXISTS "Fish_audit";

-- ---------------------------------------------------------------------------
-- 2. Seed the 10 family oil Materials
-- ---------------------------------------------------------------------------

INSERT INTO "Materials" ("Name", "Weight", "Value", "Type")
SELECT fam || ' Fish Oil', 0.01, 0.01, 'Fish Oil'
  FROM (VALUES
    ('Cod'), ('Carp'), ('Eel'), ('Tuna'), ('Pike'),
    ('Bass'), ('Catfish'), ('Salmon'), ('Sturgeon'),
    ('Swordfish')
  ) AS families(fam)
  WHERE NOT EXISTS (
    SELECT 1 FROM ONLY "Materials" WHERE "Name" = families.fam || ' Fish Oil'
  );

-- ---------------------------------------------------------------------------
-- 3. Rebuild UndiscoveredFishItemIds before the DROP COLUMN so the old
--    view's reference to Fish.FishOilItemId goes away. CREATE OR REPLACE
--    swaps the definition atomically.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW "UndiscoveredFishItemIds" AS
  WITH candidates AS (
    -- Family oil: oil material is `{Species.Name} Fish Oil`. A given oil
    -- stays hidden only while *every* fish in the family is still
    -- undiscovered.
    SELECT (oil."Id" + 1000000) AS "Id",
           (fd."FishId" IS NOT NULL) AS discovered
      FROM ONLY "MobSpecies" ms
      JOIN ONLY "Fish" f ON f."SpeciesId" = ms."Id"
      JOIN ONLY "Materials" oil ON oil."Name" = ms."Name" || ' Fish Oil'
      LEFT JOIN "FishDiscoveries" fd ON fd."FishId" = f."Id"
     WHERE ms."CodexType" = 'Fish'::"CodexType"
    UNION ALL
    -- Per-fish material: hidden while that specific fish is undiscovered.
    SELECT f."ItemId" AS "Id",
           (fd."FishId" IS NOT NULL) AS discovered
      FROM ONLY "Fish" f
      LEFT JOIN "FishDiscoveries" fd ON fd."FishId" = f."Id"
     WHERE f."ItemId" IS NOT NULL
  )
  SELECT "Id" FROM candidates
  GROUP BY "Id"
  HAVING bool_or(discovered) = FALSE;

GRANT SELECT ON "UndiscoveredFishItemIds" TO nexus;

-- ---------------------------------------------------------------------------
-- 4. Drop the now-redundant column on Fish
-- ---------------------------------------------------------------------------

ALTER TABLE "Fish" DROP COLUMN "FishOilItemId";

-- ---------------------------------------------------------------------------
-- 5. Rebuild Fish_audit to match the new column layout
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
