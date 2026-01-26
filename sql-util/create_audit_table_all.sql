DO $$
DECLARE
   tbl_name TEXT;
   col_def TEXT = '';
   col_def_temp TEXT;
   excluded_tables TEXT[] := ARRAY['spatial_ref_sys']; -- replace with the names of the tables you want to exclude
BEGIN
   FOR tbl_name IN (SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name NOT IN (SELECT UNNEST(excluded_tables)) AND table_name NOT LIKE '%_audit') LOOP
      col_def := '';
      FOR col_def_temp IN (SELECT '"' || column_name || '" "' || COALESCE((SELECT typname FROM pg_type WHERE typname = udt_name), data_type) || '"' || (CASE WHEN character_maximum_length IS NOT NULL THEN '(' || character_maximum_length || ')' ELSE '' END) FROM information_schema.columns WHERE table_schema = 'public' AND table_name = tbl_name ORDER BY ordinal_position) LOOP
         col_def := col_def || ', ' || col_def_temp;
      END LOOP;
      
      EXECUTE format('
         CREATE TABLE IF NOT EXISTS "%1$s_audit" (
            operation CHAR(1) NOT NULL,
            stamp TIMESTAMP NOT NULL,
            userid TEXT NOT NULL
            %2$s
         );
         
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
         
         CREATE TRIGGER "%1$s_audit_trigger"
         AFTER INSERT OR UPDATE OR DELETE ON "%1$s"
            FOR EACH ROW EXECUTE FUNCTION "%1$s_audit_trigger"();

         INSERT INTO "%1$s_audit" SELECT ''I'', now(), current_user, * FROM "%1$s";
      ', 
      tbl_name, col_def);
   END LOOP;
END $$;