-- Migration: Add grace window support for refresh token rotation
-- Per draft-ietf-oauth-security-topics §4.14.2, the server MAY grant a grace
-- period during which a used refresh token can still be used, returning the
-- same response.  We store the cached JSON response in `replaced_by` and the
-- rotation timestamp in `used_at` so re-presentation within the grace window
-- returns the identical token pair instead of triggering reuse revocation.
-- Database: nexus_users

BEGIN;

ALTER TABLE oauth_refresh_tokens
  ADD COLUMN IF NOT EXISTS replaced_by text DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS used_at timestamptz DEFAULT NULL;

COMMENT ON COLUMN oauth_refresh_tokens.replaced_by IS 'Cached JSON token response for grace-window replay (ephemeral, cleared on cleanup)';
COMMENT ON COLUMN oauth_refresh_tokens.used_at IS 'Timestamp when this token was consumed by rotation';

COMMIT;
