-- Migration: Grant permissions to nexus_bot user for nexus database
-- Description: Grant necessary permissions for Discord bot to access Estates, Planets, and shop management
-- Database: nexus
-- Date: 2026-01-28

BEGIN;

-- ===========================================
-- NEXUS DATABASE PERMISSIONS
-- ===========================================

-- Estates table - bot needs to read and update shop ownership
GRANT SELECT, UPDATE ON "Estates" TO nexus_bot;
GRANT USAGE, SELECT ON SEQUENCE "Estates_Id_seq" TO nexus_bot;

-- Planets table - bot needs to read planet info for shop locations
GRANT SELECT ON "Planets" TO nexus_bot;

COMMIT;