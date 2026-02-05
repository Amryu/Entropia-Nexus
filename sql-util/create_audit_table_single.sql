DO $$
DECLARE
   tbl_name TEXT := 'table_name'; -- Replace with your actual table name
   col_def TEXT := '';
   col_def_temp TEXT;
   check_constraint TEXT;
   audit_table_exists BOOLEAN;
BEGIN
   -- Check if the audit table already exists
   SELECT EXISTS (
      SELECT 1
      FROM information_schema.tables
      WHERE table_schema = 'public'
      AND table_name = format('%s_audit', tbl_name)
   ) INTO audit_table_exists;

   -- Build column definitions for the audit table
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
               -- For enums and other user-defined types, properly quote the type name
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

   -- Create the audit table
   EXECUTE format('
      CREATE TABLE IF NOT EXISTS "%1$s_audit" (
         operation CHAR(1) NOT NULL,
         stamp TIMESTAMP NOT NULL,
         userid TEXT NOT NULL
         %2$s
      );
   ', tbl_name, col_def);

   -- Copy CHECK constraints from parent table to audit table
   FOR check_constraint IN (
      SELECT conname, pg_get_constraintdef(oid) as condef
      FROM pg_constraint
      WHERE conrelid = ('public.' || quote_ident(tbl_name))::regclass
      AND contype = 'c'
   ) LOOP
      EXECUTE format('ALTER TABLE "%1$s_audit" ADD CONSTRAINT "%2$s" %3$s',
                     tbl_name, check_constraint.conname, check_constraint.condef);
   END LOOP;

   -- Add inheritance after table creation
   EXECUTE format('
      ALTER TABLE "%1$s_audit" INHERIT "%1$s";
   ', tbl_name);

   -- Create the trigger and initial inserts only if the audit table did not exist
   IF NOT audit_table_exists THEN
      EXECUTE format('
         CREATE OR REPLACE FUNCTION "%1$s_audit_trigger"() RETURNS TRIGGER AS $func$
         BEGIN
            IF (TG_OP = ''DELETE'') THEN
               INSERT INTO "%1$s_audit" SELECT ''D'', now(), current_user, OLD.*;
               RETURN OLD;
            ELSIF (TG_OP = ''UPDATE'') THEN
               INSERT INTO "%1$s_audit" SELECT ''U'', now(), current_user, NEW.*;
               RETURN NEW;
            ELSIF (TG_OP = ''INSERT'') THEN
               INSERT INTO "%1$s_audit" SELECT ''I'', now(), current_user, NEW.*;
               RETURN NEW;
            END IF;
            RETURN NULL;
         END;
         $func$ LANGUAGE plpgsql;
         
         DROP TRIGGER IF EXISTS "%1$s_audit_trigger" ON "%1$s";
         
         CREATE TRIGGER "%1$s_audit_trigger"
         AFTER INSERT OR UPDATE OR DELETE ON "%1$s"
            FOR EACH ROW EXECUTE FUNCTION "%1$s_audit_trigger"();
         
         INSERT INTO "%1$s_audit" SELECT ''I'', now(), current_user, * FROM "%1$s";
      ', tbl_name);
   END IF;
END $$;