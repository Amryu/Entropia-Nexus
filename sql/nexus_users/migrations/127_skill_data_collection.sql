BEGIN;

-- Anonymized skill data collection for community tools (TT calculator, etc.)
-- contributor_hash is SHA-256(user_id + server salt) — never stores raw user ID.

CREATE TABLE IF NOT EXISTS skill_data_contributors (
  id serial PRIMARY KEY,
  contributor_hash text NOT NULL UNIQUE,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_upload_at timestamptz NOT NULL DEFAULT now(),
  snapshot_count integer NOT NULL DEFAULT 0,
  delta_count integer NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skill_data_snapshots (
  id serial PRIMARY KEY,
  contributor_id integer NOT NULL REFERENCES skill_data_contributors(id) ON DELETE CASCADE,
  scan_timestamp timestamptz NOT NULL,
  uploaded_at timestamptz NOT NULL DEFAULT now(),
  client_version text
);

CREATE INDEX idx_skill_data_snapshots_contributor
  ON skill_data_snapshots (contributor_id, scan_timestamp);

CREATE TABLE IF NOT EXISTS skill_data_snapshot_values (
  id serial PRIMARY KEY,
  snapshot_id integer NOT NULL REFERENCES skill_data_snapshots(id) ON DELETE CASCADE,
  skill_id integer NOT NULL,
  current_points numeric(12,4) NOT NULL
);

CREATE INDEX idx_skill_data_snapshot_values_snapshot
  ON skill_data_snapshot_values (snapshot_id);

CREATE TABLE IF NOT EXISTS skill_data_gain_events (
  id bigserial PRIMARY KEY,
  contributor_id integer NOT NULL REFERENCES skill_data_contributors(id) ON DELETE CASCADE,
  event_ts timestamptz NOT NULL,
  skill_id integer NOT NULL,
  amount numeric(10,4) NOT NULL,
  batch_id integer
);

CREATE INDEX idx_skill_data_gain_events_contributor
  ON skill_data_gain_events (contributor_id, event_ts);
CREATE INDEX idx_skill_data_gain_events_skill
  ON skill_data_gain_events (skill_id, event_ts);

CREATE TABLE IF NOT EXISTS skill_data_upload_batches (
  id serial PRIMARY KEY,
  contributor_id integer NOT NULL REFERENCES skill_data_contributors(id) ON DELETE CASCADE,
  upload_type text NOT NULL,
  min_event_ts timestamptz,
  max_event_ts timestamptz,
  event_count integer NOT NULL DEFAULT 0,
  uploaded_at timestamptz NOT NULL DEFAULT now(),
  client_version text
);

CREATE INDEX idx_skill_data_upload_batches_contributor
  ON skill_data_upload_batches (contributor_id, uploaded_at);

-- Grants
GRANT SELECT, INSERT, UPDATE, DELETE ON skill_data_contributors TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON skill_data_snapshots TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON skill_data_snapshot_values TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON skill_data_gain_events TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON skill_data_upload_batches TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE skill_data_contributors_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE skill_data_snapshots_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE skill_data_snapshot_values_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE skill_data_gain_events_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE skill_data_upload_batches_id_seq TO nexus_users;

COMMIT;
