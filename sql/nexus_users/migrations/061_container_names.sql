-- Migration 061: Custom container names for inventory tree view
-- Allows users to rename containers (not base storages) with persistence across imports.

BEGIN;

CREATE TABLE user_container_names (
  id              SERIAL PRIMARY KEY,
  user_id         BIGINT NOT NULL,
  container_path  TEXT NOT NULL,
  custom_name     VARCHAR(100) NOT NULL,
  container_ref   INTEGER DEFAULT NULL,
  item_name       VARCHAR(255) NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, container_path)
);

CREATE INDEX idx_user_container_names_user ON user_container_names (user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON user_container_names TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE user_container_names_id_seq TO nexus_users;

COMMIT;
