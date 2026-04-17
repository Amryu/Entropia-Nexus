-- Classify fishing attachments by the rod family they fit on.
--
-- Fly Fishing and Deep Ocean rods accept specialised attachments that don't
-- fit on Casting/Angling rods (and vice-versa). Baitfishing is a free-to-play
-- variant with no attachments at all, so it does not appear in this enum.
--
-- The new "RodCategory" column is NOT NULL with a 'Regular' default so every
-- existing row gets a sensible starting value. A name-based backfill then
-- flips the obvious Fly Fishing / Deep Ocean rows; everything else stays
-- Regular and can be corrected via the wiki edit UI.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Enum
-- ---------------------------------------------------------------------------

CREATE TYPE "FishingAttachmentCategory" AS ENUM (
    'Regular',
    'Fly Fishing',
    'Deep Ocean'
);

-- ---------------------------------------------------------------------------
-- 2. Column on every attachment subtype
-- ---------------------------------------------------------------------------

ALTER TABLE "FishingReels"  ADD COLUMN "RodCategory" "FishingAttachmentCategory" NOT NULL DEFAULT 'Regular';
ALTER TABLE "FishingBlanks" ADD COLUMN "RodCategory" "FishingAttachmentCategory" NOT NULL DEFAULT 'Regular';
ALTER TABLE "FishingLines"  ADD COLUMN "RodCategory" "FishingAttachmentCategory" NOT NULL DEFAULT 'Regular';
ALTER TABLE "FishingLures"  ADD COLUMN "RodCategory" "FishingAttachmentCategory" NOT NULL DEFAULT 'Regular';

-- ---------------------------------------------------------------------------
-- 3. Backfill from name tokens (specific matches only; unmatched stay Regular)
-- ---------------------------------------------------------------------------

UPDATE "FishingReels"  SET "RodCategory" = 'Fly Fishing'::"FishingAttachmentCategory" WHERE "Name" ~* '\yfly(\sfishing)?\y';
UPDATE "FishingBlanks" SET "RodCategory" = 'Fly Fishing'::"FishingAttachmentCategory" WHERE "Name" ~* '\yfly(\sfishing)?\y';
UPDATE "FishingLines"  SET "RodCategory" = 'Fly Fishing'::"FishingAttachmentCategory" WHERE "Name" ~* '\yfly(\sfishing)?\y';
UPDATE "FishingLures"  SET "RodCategory" = 'Fly Fishing'::"FishingAttachmentCategory"
    WHERE "Name" ~* '\yfly(\sfishing)?\y' OR "LureType" = 'Flys'::"LureType";

UPDATE "FishingReels"  SET "RodCategory" = 'Deep Ocean'::"FishingAttachmentCategory" WHERE "Name" ~* '\ydeep(\socean)?\y';
UPDATE "FishingBlanks" SET "RodCategory" = 'Deep Ocean'::"FishingAttachmentCategory" WHERE "Name" ~* '\ydeep(\socean)?\y';
UPDATE "FishingLines"  SET "RodCategory" = 'Deep Ocean'::"FishingAttachmentCategory" WHERE "Name" ~* '\ydeep(\socean)?\y';
UPDATE "FishingLures"  SET "RodCategory" = 'Deep Ocean'::"FishingAttachmentCategory" WHERE "Name" ~* '\ydeep(\socean)?\y';

-- ---------------------------------------------------------------------------
-- 4. Rebuild all four audit tables (schema drift: trigger's
--    INSERT ... SELECT NEW.* relies on column order matching).
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

DROP TRIGGER IF EXISTS "FishingReels_audit_trigger"  ON "FishingReels";
DROP TABLE   IF EXISTS "FishingReels_audit";
DROP TRIGGER IF EXISTS "FishingBlanks_audit_trigger" ON "FishingBlanks";
DROP TABLE   IF EXISTS "FishingBlanks_audit";
DROP TRIGGER IF EXISTS "FishingLines_audit_trigger"  ON "FishingLines";
DROP TABLE   IF EXISTS "FishingLines_audit";
DROP TRIGGER IF EXISTS "FishingLures_audit_trigger"  ON "FishingLures";
DROP TABLE   IF EXISTS "FishingLures_audit";

SELECT pg_temp._create_audit_for('FishingReels');
SELECT pg_temp._create_audit_for('FishingBlanks');
SELECT pg_temp._create_audit_for('FishingLines');
SELECT pg_temp._create_audit_for('FishingLures');

GRANT SELECT ON "FishingReels_audit",  "FishingBlanks_audit",
                "FishingLines_audit",  "FishingLures_audit" TO nexus;
GRANT INSERT ON "FishingReels_audit",  "FishingBlanks_audit",
                "FishingLines_audit",  "FishingLures_audit" TO nexus_bot;

COMMIT;
