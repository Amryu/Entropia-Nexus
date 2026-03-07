-- Pre-computed player and target aggregates for each standard period.
-- Refreshed from rollup tables after each rollup rebuild.
-- Eliminates expensive GROUP BY player_name/target_name queries on every request.

BEGIN;

-- One row per (period, player) — all players for each standard period.
-- Endpoints read with ORDER BY + LIMIT (no GROUP BY needed).
CREATE TABLE globals_player_agg (
  period text NOT NULL,
  player_name text NOT NULL,
  event_count integer NOT NULL DEFAULT 0,
  sum_value numeric(14,2) NOT NULL DEFAULT 0,
  max_value numeric(12,2) NOT NULL DEFAULT 0,
  has_team boolean NOT NULL DEFAULT false,
  has_solo boolean NOT NULL DEFAULT false,
  has_profile boolean NOT NULL DEFAULT false,
  PRIMARY KEY (period, player_name)
);

-- One row per (period, target) — all targets for each standard period.
CREATE TABLE globals_target_agg (
  period text NOT NULL,
  target_name text NOT NULL,
  mob_id integer,
  event_count integer NOT NULL DEFAULT 0,
  sum_value numeric(14,2) NOT NULL DEFAULT 0,
  max_value numeric(12,2) NOT NULL DEFAULT 0,
  primary_type text,
  PRIMARY KEY (period, target_name)
);

GRANT SELECT ON globals_player_agg TO nexus;
GRANT SELECT, INSERT, UPDATE, DELETE ON globals_player_agg TO nexus_users;

GRANT SELECT ON globals_target_agg TO nexus;
GRANT SELECT, INSERT, UPDATE, DELETE ON globals_target_agg TO nexus_users;

COMMIT;
