-- Migration: Item sets table
-- Stores user-created item sets (collections of instantiated items with metadata)

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS item_sets (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        text NOT NULL,
  data        jsonb NOT NULL DEFAULT '{"items":[]}',
  loadout_id  uuid REFERENCES loadouts(id) ON DELETE RESTRICT,
  created_at  timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_update timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_item_sets_user_id ON item_sets(user_id);
CREATE INDEX IF NOT EXISTS idx_item_sets_loadout_id ON item_sets(loadout_id) WHERE loadout_id IS NOT NULL;

GRANT SELECT, INSERT, UPDATE, DELETE ON item_sets TO nexus_users;
GRANT SELECT ON item_sets TO nexus_bot;
