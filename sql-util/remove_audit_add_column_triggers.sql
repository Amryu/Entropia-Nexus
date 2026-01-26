-- ============================================================================
-- Remove Audit Add Column Triggers and Functions
-- ============================================================================
-- This script removes all the event triggers and functions created by
-- create_audit_add_column_trigger.sql

DO $$
DECLARE
   tbl_name TEXT;
   trigger_name TEXT;
   function_name TEXT;
BEGIN
   -- Get all table names that would have had triggers created
   FOR tbl_name IN (SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name NOT LIKE '%_audit') LOOP
      
      -- Construct the trigger and function names
      trigger_name := format('sync_%s_trigger', tbl_name);
      function_name := format('public."sync_%s_trigger"()', tbl_name);
      
      -- Drop the event trigger if it exists
      EXECUTE format('DROP EVENT TRIGGER IF EXISTS "%s"', trigger_name);
      RAISE NOTICE 'Dropped event trigger: %', trigger_name;
      
      -- Drop the function if it exists
      EXECUTE format('DROP FUNCTION IF EXISTS %s', function_name);
      RAISE NOTICE 'Dropped function: %', function_name;
      
   END LOOP;
   
   RAISE NOTICE 'Cleanup complete: All audit add column triggers and functions have been removed.';
END $$;

-- ============================================================================
-- Verification Query
-- ============================================================================
-- Run this query to verify all triggers and functions have been removed:

/*
-- Check for remaining event triggers
SELECT evtname as "Event Trigger Name" 
FROM pg_event_trigger 
WHERE evtname LIKE 'sync_%_trigger';

-- Check for remaining sync functions
SELECT proname as "Function Name", prosrc as "Function Body"
FROM pg_proc 
WHERE proname LIKE 'sync_%_trigger';
*/
