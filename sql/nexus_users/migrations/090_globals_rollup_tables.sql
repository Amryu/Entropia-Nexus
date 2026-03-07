BEGIN;

-- Global-level rollup: no player/target dimension.
-- Serves: /stats summary, by_type breakdown, activity timeline.
CREATE TABLE globals_rollup (
  granularity text NOT NULL,          -- 'daily', 'weekly', 'monthly', 'quarterly'
  period_start timestamptz NOT NULL,  -- truncated to day/week/month/quarter
  global_type text NOT NULL,
  event_count integer NOT NULL DEFAULT 0,
  sum_value numeric(14,2) NOT NULL DEFAULT 0,
  max_value numeric(12,2) NOT NULL DEFAULT 0,
  hof_count integer NOT NULL DEFAULT 0,
  ath_count integer NOT NULL DEFAULT 0,
  PRIMARY KEY (granularity, period_start, global_type)
);

CREATE INDEX idx_globals_rollup_period
  ON globals_rollup (granularity, period_start);

-- Per-player rollup.
-- Serves: top players ranking, player detail summary + activity.
CREATE TABLE globals_rollup_player (
  granularity text NOT NULL,
  period_start timestamptz NOT NULL,
  player_name text NOT NULL,
  global_type text NOT NULL,
  event_count integer NOT NULL DEFAULT 0,
  sum_value numeric(14,2) NOT NULL DEFAULT 0,
  max_value numeric(12,2) NOT NULL DEFAULT 0,
  hof_count integer NOT NULL DEFAULT 0,
  ath_count integer NOT NULL DEFAULT 0,
  PRIMARY KEY (granularity, period_start, player_name, global_type)
);

CREATE INDEX idx_rollup_player_lookup
  ON globals_rollup_player (granularity, lower(player_name), period_start);

CREATE INDEX idx_rollup_player_ranking
  ON globals_rollup_player (granularity, period_start, global_type, sum_value DESC);

-- Per-target rollup.
-- Serves: top targets ranking, target detail summary + activity.
CREATE TABLE globals_rollup_target (
  granularity text NOT NULL,
  period_start timestamptz NOT NULL,
  target_name text NOT NULL,
  mob_id integer,
  global_type text NOT NULL,
  event_count integer NOT NULL DEFAULT 0,
  sum_value numeric(14,2) NOT NULL DEFAULT 0,
  max_value numeric(12,2) NOT NULL DEFAULT 0,
  hof_count integer NOT NULL DEFAULT 0,
  ath_count integer NOT NULL DEFAULT 0,
  PRIMARY KEY (granularity, period_start, target_name, global_type)
);

CREATE INDEX idx_rollup_target_lookup
  ON globals_rollup_target (granularity, lower(target_name), period_start);

CREATE INDEX idx_rollup_target_mob
  ON globals_rollup_target (granularity, mob_id, period_start)
  WHERE mob_id IS NOT NULL;

-- Permissions
GRANT SELECT ON globals_rollup TO nexus;
GRANT SELECT, INSERT, UPDATE, DELETE ON globals_rollup TO nexus_users;

GRANT SELECT ON globals_rollup_player TO nexus;
GRANT SELECT, INSERT, UPDATE, DELETE ON globals_rollup_player TO nexus_users;

GRANT SELECT ON globals_rollup_target TO nexus;
GRANT SELECT, INSERT, UPDATE, DELETE ON globals_rollup_target TO nexus_users;

COMMIT;
