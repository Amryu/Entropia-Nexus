-- Migration: OAuth 2.0 API access for external applications
-- Adds OAuth client registration, authorization codes, access/refresh tokens, and scope definitions
-- Database: nexus-users

BEGIN;

-- =============================================
-- OAUTH CLIENT APPLICATIONS
-- =============================================

-- Registered OAuth applications (created by users)
CREATE TABLE IF NOT EXISTS oauth_clients (
  id text PRIMARY KEY,                              -- UUID, public client_id
  secret_hash text NOT NULL,                        -- SHA-256 hash of client_secret
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  description text,
  website_url text,
  redirect_uris text[] NOT NULL DEFAULT '{}',       -- Exact-match redirect URIs
  is_confidential boolean NOT NULL DEFAULT true,    -- false = public client (PKCE only, no secret)
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_oauth_clients_user_id ON oauth_clients(user_id);

-- =============================================
-- OAUTH SCOPES
-- =============================================

-- Predefined scope definitions mapping to grant system
CREATE TABLE IF NOT EXISTS oauth_scopes (
  id serial PRIMARY KEY,
  key text NOT NULL UNIQUE,                         -- e.g. 'inventory:read'
  description text NOT NULL,
  grant_keys text[] NOT NULL DEFAULT '{}',          -- Maps to grants.key values required (empty = any verified user)
  created_at timestamptz NOT NULL DEFAULT now()
);

-- =============================================
-- AUTHORIZATION CODES (short-lived, single-use)
-- =============================================

CREATE TABLE IF NOT EXISTS oauth_authorization_codes (
  code text PRIMARY KEY,                            -- SHA-256 hash of the actual code
  client_id text NOT NULL REFERENCES oauth_clients(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  redirect_uri text NOT NULL,
  scopes text[] NOT NULL DEFAULT '{}',
  code_challenge text NOT NULL,                     -- PKCE S256 challenge
  code_challenge_method text NOT NULL DEFAULT 'S256',
  expires_at timestamptz NOT NULL,
  used boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_oauth_auth_codes_expires ON oauth_authorization_codes(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_auth_codes_client ON oauth_authorization_codes(client_id);

-- =============================================
-- ACCESS TOKENS
-- =============================================

CREATE TABLE IF NOT EXISTS oauth_access_tokens (
  token_hash text PRIMARY KEY,                      -- SHA-256 hash of the raw token
  client_id text NOT NULL REFERENCES oauth_clients(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  scopes text[] NOT NULL DEFAULT '{}',
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_oauth_access_tokens_user ON oauth_access_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_access_tokens_client ON oauth_access_tokens(client_id);
CREATE INDEX IF NOT EXISTS idx_oauth_access_tokens_expires ON oauth_access_tokens(expires_at);

-- =============================================
-- REFRESH TOKENS (single-use with rotation)
-- =============================================

CREATE TABLE IF NOT EXISTS oauth_refresh_tokens (
  token_hash text PRIMARY KEY,                      -- SHA-256 hash of the raw token
  access_token_hash text NOT NULL,                  -- Links to the parent access token
  client_id text NOT NULL REFERENCES oauth_clients(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  scopes text[] NOT NULL DEFAULT '{}',
  expires_at timestamptz NOT NULL,
  used boolean NOT NULL DEFAULT false,              -- For rotation: reuse = breach detection
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_user ON oauth_refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_client ON oauth_refresh_tokens(client_id);
CREATE INDEX IF NOT EXISTS idx_oauth_refresh_tokens_expires ON oauth_refresh_tokens(expires_at);

-- =============================================
-- SEED OAUTH SCOPES
-- =============================================

INSERT INTO oauth_scopes (key, description, grant_keys) VALUES
  ('profile:read',       'Read your profile information',           '{}'),
  ('inventory:read',     'Read your inventory',                     '{}'),
  ('inventory:write',    'Modify your inventory',                   '{}'),
  ('loadouts:read',      'Read your loadouts',                      '{}'),
  ('loadouts:write',     'Create and modify loadouts',              '{}'),
  ('itemsets:read',      'Read your item sets',                     '{}'),
  ('itemsets:write',     'Create and modify item sets',             '{}'),
  ('skills:read',        'Read your skill data',                    '{}'),
  ('skills:write',       'Import skill data',                       '{}'),
  ('exchange:read',      'Read your exchange orders',               '{}'),
  ('exchange:write',     'Create, edit, and close exchange orders', '{}'),
  ('trades:read',        'Read your trade requests',                '{market.trade}'),
  ('trades:write',       'Create trade requests',                   '{market.trade}'),
  ('services:read',      'Read your services and requests',         '{}'),
  ('services:write',     'Modify your services',                    '{}'),
  ('auction:read',       'Read your auctions and bids',             '{}'),
  ('auction:write',      'Create auctions, place bids, settle',     '{}'),
  ('rental:read',        'Read your rental offers and requests',    '{}'),
  ('rental:write',       'Create and modify rental offers',         '{}'),
  ('notifications:read', 'Read your notifications',                 '{}'),
  ('notifications:write','Mark notifications as read',              '{}'),
  ('preferences:read',   'Read your preferences',                   '{}'),
  ('preferences:write',  'Modify your preferences',                 '{}'),
  ('societies:read',     'Read your society membership',            '{}'),
  ('societies:write',    'Join and manage societies',               '{}'),
  ('wiki:read',          'Read wiki change data',                   '{wiki.edit}'),
  ('wiki:write',         'Submit wiki changes',                     '{wiki.edit}'),
  ('guides:write',       'Create and edit guide content',           '{guide.create,guide.edit}'),
  ('uploads:write',      'Upload images',                           '{}')
ON CONFLICT (key) DO NOTHING;

-- =============================================
-- PERMISSIONS
-- =============================================

GRANT SELECT, INSERT, UPDATE, DELETE ON oauth_clients TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON oauth_scopes TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON oauth_authorization_codes TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON oauth_access_tokens TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON oauth_refresh_tokens TO "nexus-users";

GRANT USAGE, SELECT ON SEQUENCE oauth_scopes_id_seq TO "nexus-users";

COMMIT;
