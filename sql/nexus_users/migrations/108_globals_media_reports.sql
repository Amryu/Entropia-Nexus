-- Media reporting system for globals
CREATE TABLE globals_media_reports (
  id SERIAL PRIMARY KEY,
  global_id INTEGER NOT NULL REFERENCES ingested_globals(id) ON DELETE CASCADE,
  reporter_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_by BIGINT REFERENCES users(id),
  resolved_at TIMESTAMPTZ,
  UNIQUE(global_id, reporter_id)
);

CREATE INDEX idx_globals_media_reports_pending ON globals_media_reports(created_at DESC)
  WHERE resolved_at IS NULL;

GRANT SELECT, INSERT ON globals_media_reports TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE globals_media_reports_id_seq TO nexus_users;
