-- Pre-aggregated ATH leaderboard for globals player detail pages.
-- Replaces 4 expensive CTE ranking queries that scan all confirmed globals.
-- Rebuilt every 15 minutes by the server-side globals cache.

CREATE TABLE globals_ath_leaderboard (
  category text NOT NULL,           -- 'hunting', 'mining', 'crafting', 'pvp'
  target_key text NOT NULL,         -- COALESCE(mob_id::text, target_name) for hunting; target_name for others
  player_name text NOT NULL,
  total_value numeric(14,2) NOT NULL DEFAULT 0,
  best_value numeric(14,2) NOT NULL DEFAULT 0,
  count integer NOT NULL DEFAULT 0,
  mob_id integer,
  best_target_name text,            -- for hunting: the maturity with highest single loot
  total_rank integer,
  best_rank integer,
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (category, target_key, player_name)
);

CREATE INDEX idx_ath_leaderboard_player
  ON globals_ath_leaderboard (lower(player_name), category);

-- Grant permissions for the nexus frontend to read
GRANT SELECT ON globals_ath_leaderboard TO nexus;
GRANT SELECT, INSERT, UPDATE, DELETE ON globals_ath_leaderboard TO nexus_users;
