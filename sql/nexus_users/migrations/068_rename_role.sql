-- Migration: Rename "nexus-users" role to nexus_users
-- Database: nexus_users
--
-- The database itself must be renamed separately (cannot rename while connected):
--   -- Connect to 'postgres' database, terminate existing connections, then:
--   ALTER DATABASE "nexus-users" RENAME TO nexus_users;
--
-- This migration renames the application role used in GRANT statements.

ALTER ROLE "nexus-users" RENAME TO nexus_users;
