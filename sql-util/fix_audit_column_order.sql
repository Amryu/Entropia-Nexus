-- Fix Audit Table Column Order
-- This script fixes audit tables where operation, stamp, userid are at the end instead of the beginning
-- Run this on the database where audit tables have incorrect column order

DO $$
DECLARE
    audit_table TEXT;
    parent_table TEXT;
    col_record RECORD;
    audit_columns TEXT := '';
    parent_columns TEXT := '';
    select_columns TEXT := '';
    col_type TEXT;
    has_inheritance BOOLEAN;
BEGIN
    -- Loop through all audit tables
    FOR audit_table IN
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name LIKE '%_audit'
          AND table_type = 'BASE TABLE'
    LOOP
        parent_table := replace(audit_table, '_audit', '');

        -- Check if parent table exists
        IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = parent_table AND table_schema = 'public') THEN
            RAISE NOTICE 'Skipping % - parent table % does not exist', audit_table, parent_table;
            CONTINUE;
        END IF;

        -- Check current column order
        SELECT column_name INTO col_record
        FROM information_schema.columns
        WHERE table_name = audit_table AND table_schema = 'public'
        ORDER BY ordinal_position
        LIMIT 1;

        -- If first column is already 'operation', skip this table
        IF col_record.column_name = 'operation' THEN
            RAISE NOTICE 'Skipping % - already has correct column order', audit_table;
            CONTINUE;
        END IF;

        RAISE NOTICE 'Fixing column order for %', audit_table;

        -- Check if table has inheritance
        SELECT EXISTS (
            SELECT 1 FROM pg_inherits
            WHERE inhrelid = (quote_ident('public') || '.' || quote_ident(audit_table))::regclass
        ) INTO has_inheritance;

        -- Drop trigger if exists
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', parent_table || '_audit_trigger', parent_table);

        -- Remove inheritance if exists
        IF has_inheritance THEN
            EXECUTE format('ALTER TABLE %I NO INHERIT %I', audit_table, parent_table);
        END IF;

        -- Build column definitions for new table
        -- Start with audit columns
        audit_columns := 'operation CHAR(1) NOT NULL, stamp TIMESTAMP NOT NULL, userid TEXT NOT NULL';

        -- Get parent table columns (these go after audit columns)
        parent_columns := '';
        select_columns := '';

        FOR col_record IN
            SELECT column_name, data_type, udt_name, is_nullable, character_maximum_length, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_name = parent_table AND table_schema = 'public'
            ORDER BY ordinal_position
        LOOP
            -- Build type string
            IF col_record.data_type = 'USER-DEFINED' THEN
                col_type := '"' || col_record.udt_name || '"';
            ELSIF col_record.data_type = 'character varying' AND col_record.character_maximum_length IS NOT NULL THEN
                col_type := 'VARCHAR(' || col_record.character_maximum_length || ')';
            ELSIF col_record.data_type = 'numeric' AND col_record.numeric_precision IS NOT NULL THEN
                col_type := 'NUMERIC(' || col_record.numeric_precision || ',' || COALESCE(col_record.numeric_scale, 0) || ')';
            ELSIF col_record.data_type = 'ARRAY' THEN
                col_type := col_record.udt_name;
            ELSE
                col_type := col_record.data_type;
            END IF;

            -- Add NOT NULL if applicable
            IF col_record.is_nullable = 'NO' THEN
                col_type := col_type || ' NOT NULL';
            END IF;

            IF parent_columns != '' THEN
                parent_columns := parent_columns || ', ';
                select_columns := select_columns || ', ';
            END IF;

            parent_columns := parent_columns || '"' || col_record.column_name || '" ' || col_type;
            select_columns := select_columns || '"' || col_record.column_name || '"';
        END LOOP;

        -- Create temp table with correct order and copy data
        EXECUTE format('CREATE TEMP TABLE _temp_audit_fix AS SELECT operation, stamp, userid, %s FROM %I',
                       select_columns, audit_table);

        -- Drop old audit table
        EXECUTE format('DROP TABLE %I', audit_table);

        -- Create new audit table with correct column order
        EXECUTE format('CREATE TABLE %I (%s, %s)', audit_table, audit_columns, parent_columns);

        -- Restore data
        EXECUTE format('INSERT INTO %I SELECT * FROM _temp_audit_fix', audit_table);

        -- Drop temp table
        DROP TABLE _temp_audit_fix;

        -- Re-establish inheritance
        EXECUTE format('ALTER TABLE %I INHERIT %I', audit_table, parent_table);

        -- Recreate trigger function and trigger
        EXECUTE format($func$
            CREATE OR REPLACE FUNCTION %I() RETURNS TRIGGER AS $trigger$
            BEGIN
                IF (TG_OP = 'DELETE') THEN
                    INSERT INTO %I SELECT 'D', now(), current_user, OLD.*;
                    RETURN OLD;
                ELSIF (TG_OP = 'UPDATE') THEN
                    INSERT INTO %I SELECT 'U', now(), current_user, NEW.*;
                    RETURN NEW;
                ELSIF (TG_OP = 'INSERT') THEN
                    INSERT INTO %I SELECT 'I', now(), current_user, NEW.*;
                    RETURN NEW;
                END IF;
                RETURN NULL;
            END;
            $trigger$ LANGUAGE plpgsql
        $func$, parent_table || '_audit_trigger', audit_table, audit_table, audit_table);

        EXECUTE format('CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION %I()',
                       parent_table || '_audit_trigger', parent_table, parent_table || '_audit_trigger');

        RAISE NOTICE 'Fixed %', audit_table;
    END LOOP;
END $$;

-- Verification query to check column order
SELECT
    table_name,
    string_agg(column_name, ', ' ORDER BY ordinal_position) as columns
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name LIKE '%_audit'
GROUP BY table_name
ORDER BY table_name;
