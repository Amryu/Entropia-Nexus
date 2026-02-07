-- Migration: Grant SELECT on audit tables to nexus user
-- Description: The API (connecting as 'nexus') needs read access to _audit tables for the audit endpoint
-- Database: nexus
-- Date: 2026-02-07

BEGIN;

-- Grant SELECT on all existing _audit tables to the nexus role
DO $$
DECLARE
  tbl TEXT;
BEGIN
  FOR tbl IN
    SELECT tablename FROM pg_tables
    WHERE tablename LIKE '%\_audit' AND schemaname = 'public'
  LOOP
    EXECUTE format('GRANT SELECT ON %I TO nexus', tbl);
  END LOOP;
END $$;

-- Ensure future _audit tables also get SELECT for nexus
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO nexus;

COMMIT;
