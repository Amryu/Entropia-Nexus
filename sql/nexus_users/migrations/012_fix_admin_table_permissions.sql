-- Migration: Fix Admin Table Permissions
-- Grants permissions to the nexus_users web app user for admin dashboard tables

-- =============================================
-- GRANT PERMISSIONS TO WEB APP USER
-- =============================================

-- Grant full access on change_history table
GRANT SELECT, INSERT, UPDATE, DELETE ON change_history TO nexus_users;
GRANT USAGE ON SEQUENCE change_history_id_seq TO nexus_users;

-- Grant full access on admin_actions table
GRANT SELECT, INSERT, UPDATE, DELETE ON admin_actions TO nexus_users;
GRANT USAGE ON SEQUENCE admin_actions_id_seq TO nexus_users;

-- Ensure changes table has proper permissions (already exists but verify columns)
GRANT SELECT, INSERT, UPDATE, DELETE ON changes TO nexus_users;

-- Ensure users table has proper permissions for lock/ban columns
GRANT SELECT, INSERT, UPDATE ON users TO nexus_users;
