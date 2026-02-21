-- User skills storage and import tracking
BEGIN;

CREATE TABLE IF NOT EXISTS user_skills (
  user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  skills JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skill_imports (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  skill_count INTEGER NOT NULL DEFAULT 0,
  total_value NUMERIC,
  summary JSONB
);

CREATE TABLE IF NOT EXISTS skill_import_deltas (
  id BIGSERIAL PRIMARY KEY,
  import_id BIGINT NOT NULL REFERENCES skill_imports(id) ON DELETE CASCADE,
  skill_name TEXT NOT NULL,
  old_value NUMERIC,
  new_value NUMERIC
);

CREATE INDEX IF NOT EXISTS idx_skill_imports_user ON skill_imports(user_id);
CREATE INDEX IF NOT EXISTS idx_skill_import_deltas_import ON skill_import_deltas(import_id);

-- Grant permissions for the web application role
GRANT SELECT, INSERT, UPDATE, DELETE ON user_skills TO nexus;
GRANT SELECT, INSERT ON skill_imports TO nexus;
GRANT SELECT, INSERT ON skill_import_deltas TO nexus;
GRANT USAGE, SELECT ON SEQUENCE skill_imports_id_seq TO nexus;
GRANT USAGE, SELECT ON SEQUENCE skill_import_deltas_id_seq TO nexus;

COMMIT;
