-- Migration: Trade & Global ingestion/distribution system
-- Crowdsource trade chat and global events from multiple desktop clients,
-- deduplicate with weighted confirmations, detect forgery via conflict analysis,
-- and redistribute confirmed data to all connected clients.
-- Database: nexus_users

BEGIN;

-- =============================================
-- GRANT: ingestion.trusted
-- =============================================

INSERT INTO grants (key, description)
VALUES ('ingestion.trusted', 'Trusted ingestion contributor — submissions count as 3 confirmations')
ON CONFLICT (key) DO NOTHING;

-- =============================================
-- INGESTED GLOBALS (deduplicated canonical events)
-- =============================================

CREATE TABLE IF NOT EXISTS ingested_globals (
  id serial PRIMARY KEY,
  content_hash text NOT NULL,                           -- SHA-256 of canonical fields
  global_type text NOT NULL,                            -- kill, team_kill, deposit, craft, rare_item
  player_name text NOT NULL,
  target_name text NOT NULL,
  value numeric(12,2) NOT NULL,
  value_unit text NOT NULL DEFAULT 'PED',               -- PED or PEC
  location text,
  is_hof boolean NOT NULL DEFAULT false,
  is_ath boolean NOT NULL DEFAULT false,
  event_timestamp timestamptz NOT NULL,
  confirmation_count integer NOT NULL DEFAULT 0,        -- Weighted sum of all submissions
  confirmed boolean NOT NULL DEFAULT false,             -- True when confirmation_count >= 5
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  confirmed_at timestamptz                              -- Set when first confirmed
);

-- Window matching: find by content_hash within ±60s of event_timestamp
CREATE INDEX IF NOT EXISTS idx_ingested_globals_hash_ts
  ON ingested_globals (content_hash, event_timestamp);

-- Slot conflict detection: same (global_type, player_name) within a time window
CREATE INDEX IF NOT EXISTS idx_ingested_globals_slot
  ON ingested_globals (global_type, player_name, event_timestamp);

-- Distribution: fetch entries newer than a cursor
CREATE INDEX IF NOT EXISTS idx_ingested_globals_first_seen
  ON ingested_globals (first_seen_at);

-- =============================================
-- INGESTED GLOBAL SUBMISSIONS (per-client audit trail)
-- =============================================

CREATE TABLE IF NOT EXISTS ingested_global_submissions (
  id serial PRIMARY KEY,
  global_id integer NOT NULL REFERENCES ingested_globals(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  weight integer NOT NULL DEFAULT 1,                    -- 1=normal, 3=trusted, 5=admin
  submitted_at timestamptz NOT NULL DEFAULT now(),
  event_timestamp timestamptz NOT NULL,                 -- Client's original timestamp
  UNIQUE (global_id, user_id)                           -- One submission per user per event
);

CREATE INDEX IF NOT EXISTS idx_ingested_global_subs_user
  ON ingested_global_submissions (user_id);

CREATE INDEX IF NOT EXISTS idx_ingested_global_subs_global
  ON ingested_global_submissions (global_id);

-- =============================================
-- INGESTED TRADE MESSAGES (deduplicated, no confirmation threshold)
-- =============================================

CREATE TABLE IF NOT EXISTS ingested_trade_messages (
  id serial PRIMARY KEY,
  content_hash text NOT NULL,                           -- SHA-256 of (channel, username, message)
  channel text NOT NULL,
  username text NOT NULL,
  message text NOT NULL,
  event_timestamp timestamptz NOT NULL,
  confirmation_count integer NOT NULL DEFAULT 0,        -- Tracked for audit/fraud, no threshold gate
  first_seen_at timestamptz NOT NULL DEFAULT now()
);

-- Window matching: find by content_hash within ±60s
CREATE INDEX IF NOT EXISTS idx_ingested_trades_hash_ts
  ON ingested_trade_messages (content_hash, event_timestamp);

-- Slot conflict detection: same (channel, username) within a time window
CREATE INDEX IF NOT EXISTS idx_ingested_trades_slot
  ON ingested_trade_messages (channel, username, event_timestamp);

-- Distribution: fetch entries newer than a cursor
CREATE INDEX IF NOT EXISTS idx_ingested_trades_first_seen
  ON ingested_trade_messages (first_seen_at);

-- =============================================
-- INGESTED TRADE SUBMISSIONS (per-client audit trail)
-- =============================================

CREATE TABLE IF NOT EXISTS ingested_trade_submissions (
  id serial PRIMARY KEY,
  trade_message_id integer NOT NULL REFERENCES ingested_trade_messages(id) ON DELETE CASCADE,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  weight integer NOT NULL DEFAULT 1,
  submitted_at timestamptz NOT NULL DEFAULT now(),
  event_timestamp timestamptz NOT NULL,
  UNIQUE (trade_message_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_ingested_trade_subs_user
  ON ingested_trade_submissions (user_id);

CREATE INDEX IF NOT EXISTS idx_ingested_trade_subs_trade
  ON ingested_trade_submissions (trade_message_id);

-- =============================================
-- INGESTION BANS
-- =============================================

CREATE TABLE IF NOT EXISTS ingestion_bans (
  id serial PRIMARY KEY,
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
  reason text NOT NULL,
  banned_at timestamptz NOT NULL DEFAULT now(),
  banned_by bigint NOT NULL REFERENCES users(id),
  data_purged boolean NOT NULL DEFAULT false,
  data_purged_at timestamptz,
  data_purged_by bigint REFERENCES users(id)
);

-- =============================================
-- INGESTION ALERTS (suspicious behavior)
-- =============================================

CREATE TABLE IF NOT EXISTS ingestion_alerts (
  id serial PRIMARY KEY,
  type text NOT NULL,                                   -- 'conflict_pattern', 'volume_anomaly'
  user_ids bigint[] NOT NULL,                           -- Accounts involved
  details jsonb NOT NULL,                               -- Conflict evidence, stats
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved boolean NOT NULL DEFAULT false,
  resolved_at timestamptz,
  resolved_by bigint REFERENCES users(id),
  resolution_notes text
);

CREATE INDEX IF NOT EXISTS idx_ingestion_alerts_unresolved
  ON ingestion_alerts (resolved, created_at) WHERE NOT resolved;

-- =============================================
-- INGESTION CONFLICTS (individual data conflicts)
-- =============================================

CREATE TABLE IF NOT EXISTS ingestion_conflicts (
  id serial PRIMARY KEY,
  type text NOT NULL,                                   -- 'global' or 'trade'
  existing_id integer NOT NULL,                         -- FK to ingested_globals or ingested_trade_messages
  existing_hash text NOT NULL,                          -- Content hash of the existing entry
  conflicting_hash text NOT NULL,                       -- Content hash of the conflicting submission
  conflicting_data jsonb NOT NULL,                      -- The data that conflicted
  user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_conflicts_user
  ON ingestion_conflicts (user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_ingestion_conflicts_created
  ON ingestion_conflicts (created_at);

-- =============================================
-- PERMISSIONS
-- =============================================

GRANT SELECT, INSERT, UPDATE, DELETE ON ingested_globals TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON ingested_global_submissions TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON ingested_trade_messages TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON ingested_trade_submissions TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON ingestion_bans TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON ingestion_alerts TO nexus_users;
GRANT SELECT, INSERT, UPDATE, DELETE ON ingestion_conflicts TO nexus_users;

GRANT USAGE, SELECT ON SEQUENCE ingested_globals_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE ingested_global_submissions_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE ingested_trade_messages_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE ingested_trade_submissions_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE ingestion_bans_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE ingestion_alerts_id_seq TO nexus_users;
GRANT USAGE, SELECT ON SEQUENCE ingestion_conflicts_id_seq TO nexus_users;

COMMIT;
