-- Add LureType enum + column to FishingLures.
--
-- Lures categorize into 8 sub-types: Sinkers, Lures, Baits, Worms, Jigs,
-- Flys, Spinners, Spoons. The wiki page exposes this as a dropdown; this
-- migration defines the enum, adds the (nullable) column, backfills from
-- name tokens where possible, and rebuilds FishingLures_audit so the
-- audit trigger's `INSERT ... SELECT NEW.*` keeps column order.
--
-- Column is nullable because not every lure name contains a recognisable
-- type token; unmatched rows are left NULL for a curator to fill in.
--
-- Token scan uses case-insensitive word boundaries (`~*` with `\y`) and
-- matches specific types before the generic "Lure" fallback so e.g.
-- "Jig Lure" resolves to Jigs, not Lures.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Enum + column
-- ---------------------------------------------------------------------------

CREATE TYPE "LureType" AS ENUM (
    'Sinkers',
    'Lures',
    'Baits',
    'Worms',
    'Jigs',
    'Flys',
    'Spinners',
    'Spoons'
);

ALTER TABLE "FishingLures" ADD COLUMN "LureType" "LureType";

-- ---------------------------------------------------------------------------
-- 2. Backfill from name tokens (specific types before generic "Lure")
-- ---------------------------------------------------------------------------

UPDATE "FishingLures" SET "LureType" = CASE
    WHEN "Name" ~* '\ysinker(s)?\y'   THEN 'Sinkers'::"LureType"
    WHEN "Name" ~* '\yworm(s)?\y'     THEN 'Worms'::"LureType"
    WHEN "Name" ~* '\yjig(s)?\y'      THEN 'Jigs'::"LureType"
    WHEN "Name" ~* '\yfly(s|ies)?\y'  THEN 'Flys'::"LureType"
    WHEN "Name" ~* '\yspinner(s)?\y'  THEN 'Spinners'::"LureType"
    WHEN "Name" ~* '\yspoon(s)?\y'    THEN 'Spoons'::"LureType"
    WHEN "Name" ~* '\ybait(s)?\y'     THEN 'Baits'::"LureType"
    WHEN "Name" ~* '\ylure(s)?\y'     THEN 'Lures'::"LureType"
    ELSE NULL
END
WHERE "LureType" IS NULL;

-- ---------------------------------------------------------------------------
-- 3. Rebuild FishingLures_audit (column added, audit schema stale).
--    Helper mirrors 081.
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

DROP TRIGGER IF EXISTS "FishingLures_audit_trigger" ON "FishingLures";
DROP TABLE IF EXISTS "FishingLures_audit";

SELECT pg_temp._create_audit_for('FishingLures');

GRANT SELECT ON "FishingLures_audit" TO nexus;
GRANT INSERT ON "FishingLures_audit" TO nexus_bot;

COMMIT;
