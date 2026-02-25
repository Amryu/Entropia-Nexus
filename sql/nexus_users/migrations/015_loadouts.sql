-- Migration: Loadouts table
-- Stores user loadouts for the loadout manager

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS loadouts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  data jsonb NOT NULL,
  public boolean NOT NULL DEFAULT false,
  share_code text UNIQUE,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  last_update timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_loadouts_user_id ON loadouts(user_id);
CREATE INDEX IF NOT EXISTS idx_loadouts_share_code ON loadouts(share_code);

GRANT SELECT, INSERT, UPDATE, DELETE ON loadouts TO nexus_users;
