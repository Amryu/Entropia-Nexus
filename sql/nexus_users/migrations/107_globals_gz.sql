-- GZ (congrats) system for globals
CREATE TABLE globals_gz (
  global_id INTEGER NOT NULL REFERENCES ingested_globals(id) ON DELETE CASCADE,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (global_id, user_id)
);

CREATE INDEX idx_globals_gz_global ON globals_gz(global_id);

GRANT SELECT, INSERT, DELETE ON globals_gz TO nexus_users;
