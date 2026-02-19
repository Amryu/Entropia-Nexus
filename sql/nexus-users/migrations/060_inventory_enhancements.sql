-- Migration 060: Inventory enhancements
-- Adds container path tracking, import history with delta tracking,
-- unknown items tracking, and user markup configuration.

BEGIN;

-- ===========================================
-- 1. Container path on user_items
-- ===========================================

ALTER TABLE user_items ADD COLUMN IF NOT EXISTS container_path TEXT DEFAULT NULL;

-- ===========================================
-- 2. Import history & delta tracking
-- ===========================================

CREATE TYPE inventory_delta_type AS ENUM ('added', 'removed', 'changed');

CREATE TABLE inventory_imports (
  id            BIGSERIAL PRIMARY KEY,
  user_id       BIGINT NOT NULL,
  imported_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  item_count    INTEGER NOT NULL DEFAULT 0,
  total_value   NUMERIC DEFAULT NULL,
  summary       JSONB DEFAULT NULL
);

CREATE INDEX idx_inventory_imports_user
  ON inventory_imports (user_id, imported_at DESC);

CREATE TABLE inventory_import_deltas (
  id            BIGSERIAL PRIMARY KEY,
  import_id     BIGINT NOT NULL REFERENCES inventory_imports(id) ON DELETE CASCADE,
  delta_type    inventory_delta_type NOT NULL,
  item_id       INTEGER NOT NULL,
  item_name     VARCHAR(255) NOT NULL,
  container     VARCHAR(255) DEFAULT NULL,
  instance_key  VARCHAR(255) DEFAULT NULL,
  old_quantity  INTEGER DEFAULT NULL,
  new_quantity  INTEGER DEFAULT NULL,
  old_value     NUMERIC DEFAULT NULL,
  new_value     NUMERIC DEFAULT NULL
);

CREATE INDEX idx_inventory_deltas_import
  ON inventory_import_deltas (import_id);

-- ===========================================
-- 3. Unknown items tracking
-- ===========================================

CREATE TABLE unknown_items (
  id            SERIAL PRIMARY KEY,
  item_name     VARCHAR(255) NOT NULL,
  value         NUMERIC DEFAULT NULL,
  user_count    INTEGER NOT NULL DEFAULT 1,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved      BOOLEAN NOT NULL DEFAULT FALSE,
  resolved_item_id INTEGER DEFAULT NULL
);

CREATE UNIQUE INDEX idx_unknown_items_name
  ON unknown_items (LOWER(item_name));

CREATE INDEX idx_unknown_items_unresolved
  ON unknown_items (resolved, user_count DESC)
  WHERE resolved = FALSE;

CREATE TABLE unknown_item_users (
  unknown_item_id INTEGER NOT NULL REFERENCES unknown_items(id) ON DELETE CASCADE,
  user_id         BIGINT NOT NULL,
  PRIMARY KEY (unknown_item_id, user_id)
);

-- ===========================================
-- 4. User markup configuration
-- ===========================================

CREATE TABLE user_item_markups (
  user_id       BIGINT NOT NULL,
  item_id       INTEGER NOT NULL,
  markup        NUMERIC NOT NULL,
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, item_id)
);

CREATE INDEX idx_user_item_markups_user
  ON user_item_markups (user_id);

-- ===========================================
-- 5. Permissions
-- ===========================================

-- App role
GRANT SELECT, INSERT, UPDATE, DELETE ON inventory_imports TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE inventory_imports_id_seq TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON inventory_import_deltas TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE inventory_import_deltas_id_seq TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON unknown_items TO "nexus-users";
GRANT USAGE, SELECT ON SEQUENCE unknown_items_id_seq TO "nexus-users";
GRANT SELECT, INSERT, DELETE ON unknown_item_users TO "nexus-users";
GRANT SELECT, INSERT, UPDATE, DELETE ON user_item_markups TO "nexus-users";

-- Bot role
GRANT SELECT ON inventory_imports TO "nexus-bot";
GRANT SELECT ON inventory_import_deltas TO "nexus-bot";
GRANT SELECT, INSERT, UPDATE ON unknown_items TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE unknown_items_id_seq TO "nexus-bot";
GRANT SELECT, INSERT ON unknown_item_users TO "nexus-bot";

COMMIT;
