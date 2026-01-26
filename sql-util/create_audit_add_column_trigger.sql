DO $$
DECLARE
   tbl_name TEXT;
BEGIN
   FOR tbl_name IN (SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name NOT LIKE '%_audit') LOOP
      EXECUTE format('
         CREATE OR REPLACE FUNCTION public."sync_%s_trigger"()
         RETURNS event_trigger
         LANGUAGE plpgsql
         AS $func$
         DECLARE
            cmd RECORD;
            column_name TEXT;
            column_type TEXT;
         BEGIN
            FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands() LOOP
               IF cmd.command_tag = ''ALTER TABLE'' AND cmd.command::text LIKE ''%%ADD%%'' THEN
                  column_name := substring(cmd.command from ''ADD[ ]+([^ ]+)'');
                  column_type := substring(cmd.command from ''[^ ]+[ ]+([^ ]+)'');
                  EXECUTE format(''ALTER TABLE "%%s_audit" ADD COLUMN IF NOT EXISTS "%%s" %%s'', cmd.object_identity, column_name, column_type);
               END IF;
            END LOOP;
         END;
         $func$;
         
         DROP EVENT TRIGGER IF EXISTS "sync_%s_trigger";
         
         CREATE EVENT TRIGGER "sync_%s_trigger" ON DDL_COMMAND_END
         WHEN TAG IN (''ALTER TABLE'')
         EXECUTE PROCEDURE public."sync_%s_trigger"();
         
         ALTER EVENT TRIGGER "sync_%s_trigger"
         OWNER TO postgres;
      ', tbl_name, tbl_name, tbl_name, tbl_name, tbl_name);
   END LOOP;
END $$;