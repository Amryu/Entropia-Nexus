-- Migration: Grant permissions to nexus-bot user for nexus database
-- Description: Grant necessary permissions for Discord bot to access Estates, Planets, and shop management
-- Database: nexus
-- Date: 2026-01-28

BEGIN;

-- ===========================================
-- NEXUS DATABASE PERMISSIONS
-- ===========================================

-- Estates table - bot needs to read and update shop ownership
GRANT SELECT, UPDATE ON "Estates" TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE "Estates_Id_seq" TO "nexus-bot";

-- Planets table - bot needs to read planet info for shop locations
GRANT SELECT ON "Planets" TO "nexus-bot";

-- shop_managers table - bot needs to manage shop managers
GRANT SELECT, INSERT, DELETE ON shop_managers TO "nexus-bot";

GRANT SELECT, INSERT, UPDATE, DELETE ON service_tickets TO "nexus-bot";

COMMIT;
