-- Migration: Grant permissions to nexus-bot user for nexus_users database
-- Description: Grant necessary permissions for Discord bot to access required tables
-- Database: nexus_users
-- Date: 2026-01-28

BEGIN;

-- ===========================================
-- NEXUS-USERS DATABASE PERMISSIONS
-- ===========================================

-- Users table - bot needs to read user info and update verification status
GRANT SELECT, INSERT, UPDATE ON users TO "nexus-bot";

-- Changes table - bot needs to read and manage change requests
GRANT SELECT, DELETE, UPDATE ON changes TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE changes_id_seq TO "nexus-bot";

-- NOTE: services table permissions are already granted in migration 001
-- NOTE: flight-related table permissions are granted in migration 004

-- Service ticket offers - bot needs to read ticket offers for on-demand requests
GRANT SELECT ON service_ticket_offers TO "nexus-bot";

COMMIT;
