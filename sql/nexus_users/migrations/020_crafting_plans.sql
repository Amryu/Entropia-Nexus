-- Migration: Crafting Plans and Blueprint Ownership tables
-- Stores user crafting plans for the construction calculator tool

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Crafting Plans (like loadouts - JSONB with metadata)
CREATE TABLE IF NOT EXISTS crafting_plans (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name text NOT NULL,
  data jsonb NOT NULL,
  created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
  last_update timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crafting_plans_user_id ON crafting_plans(user_id);

-- Global Blueprint Ownership (one row per user)
-- Stores which blueprints the user does NOT own (absence = owned)
CREATE TABLE IF NOT EXISTS blueprint_ownership (
  user_id bigint PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  data jsonb NOT NULL DEFAULT '{}',
  last_update timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

GRANT SELECT, INSERT, UPDATE, DELETE ON crafting_plans TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON blueprint_ownership TO nexus_users;
