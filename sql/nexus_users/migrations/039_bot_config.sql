-- Migration: Create bot_config table
-- Key-value store for bot runtime configuration (verification codes, etc.)
-- Database: nexus_users

BEGIN;

CREATE TABLE IF NOT EXISTS bot_config (
  key TEXT PRIMARY KEY,
  value TEXT
);

GRANT SELECT, INSERT, UPDATE, DELETE ON bot_config TO nexus_bot;

COMMIT;
