-- Migration: Rename hyphenated roles to use underscores
-- Database: nexus_users (run on both nexus and nexus_users databases)
--
-- The database itself must be renamed separately (cannot rename while connected):
--   -- Connect to 'postgres' database, terminate existing connections, then:
--   ALTER DATABASE "nexus-users" RENAME TO nexus_users;
--
-- This migration renames the application roles used in GRANT statements.
-- Run once from either database (roles are cluster-wide).

ALTER ROLE "nexus-users" RENAME TO nexus_users;
ALTER ROLE "nexus-bot" RENAME TO nexus_bot;
