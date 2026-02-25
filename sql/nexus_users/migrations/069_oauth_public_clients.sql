-- Migration: Allow NULL secret_hash for public OAuth clients (RFC 6749 Section 2.1)
-- Database: nexus_users
--
-- Public clients (browser-based or native apps) should not have a client secret.
-- The is_confidential column already exists; this makes secret_hash nullable
-- and clears it for any existing public clients.

BEGIN;

ALTER TABLE oauth_clients ALTER COLUMN secret_hash DROP NOT NULL;

-- Clear secret_hash for any existing public clients
UPDATE oauth_clients SET secret_hash = NULL WHERE is_confidential = false;

COMMIT;
