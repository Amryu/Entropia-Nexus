-- Replace Fish.TimeOfDay enum array with a numeric range.
--
-- Before this migration a fish tagged a set of coarse named periods
-- (Dawn/Day/Sunset/Night). That was too chunky: fish biting windows do not
-- line up with 4 buckets, and the boundaries were ambiguous. Store an
-- explicit [Start, End] range over the 0..1 day cycle instead, snapped to
-- a 0.05 grid (21 discrete values). Start > End means the window wraps
-- through midnight. Both NULL means "any time".
--
-- Storage: numeric(3,2) — exact, avoids float equality pain in the CHECK.
-- 1.00 is accepted for location-boundary use but is semantically equal to
-- 0.00 since the cycle wraps.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Drop Fish_audit first. Fish_audit was created with its own local
--    TimeOfDay column (ALTER TABLE ... INHERIT was added later, so the
--    column counts as local, not inherited). That means `DROP COLUMN
--    "TimeOfDay"` on Fish does NOT cascade to Fish_audit, and the type
--    drop would fail with:
--      "column TimeOfDay of table Fish_audit depends on type FishTimeOfDay[]"
--    Drop audit up front; section 3 rebuilds it against the new columns.
-- ---------------------------------------------------------------------------

DROP TRIGGER IF EXISTS "Fish_audit_trigger" ON "Fish";
DROP TABLE IF EXISTS "Fish_audit";

-- ---------------------------------------------------------------------------
-- 2. Drop the old column (enum array). No backfill: the four named periods
--    do not map cleanly to numeric ranges and there are few production rows.
-- ---------------------------------------------------------------------------

ALTER TABLE "Fish" DROP COLUMN "TimeOfDay";

DROP TYPE IF EXISTS "FishTimeOfDay";

-- ---------------------------------------------------------------------------
-- 3. Add the two range columns. Both must be NULL (any time) or both set.
-- ---------------------------------------------------------------------------

ALTER TABLE "Fish"
  ADD COLUMN "TimeOfDayStart" numeric(3,2),
  ADD COLUMN "TimeOfDayEnd"   numeric(3,2),
  ADD CONSTRAINT "Fish_TimeOfDayStart_grid_chk"
    CHECK ("TimeOfDayStart" IS NULL OR "TimeOfDayStart" IN (
      0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
      0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00
    )),
  ADD CONSTRAINT "Fish_TimeOfDayEnd_grid_chk"
    CHECK ("TimeOfDayEnd" IS NULL OR "TimeOfDayEnd" IN (
      0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
      0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.00
    )),
  ADD CONSTRAINT "Fish_TimeOfDay_both_or_neither_chk"
    CHECK (("TimeOfDayStart" IS NULL) = ("TimeOfDayEnd" IS NULL));

-- ---------------------------------------------------------------------------
-- 4. Rebuild Fish_audit (column list changed; trigger's INSERT ... SELECT
--    NEW.* relies on column order matching).
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

DROP TRIGGER IF EXISTS "Fish_audit_trigger" ON "Fish";
DROP TABLE IF EXISTS "Fish_audit";

SELECT pg_temp._create_audit_for('Fish');

GRANT SELECT ON "Fish_audit" TO nexus;
GRANT INSERT ON "Fish_audit" TO nexus_bot;

COMMIT;
