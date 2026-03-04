BEGIN;

-- Pre-calculated reward score on user profile to avoid JOINing contributor_rewards on every profile view
ALTER TABLE ONLY users ADD COLUMN IF NOT EXISTS reward_score numeric(10,2) NOT NULL DEFAULT 0;

-- Backfill from existing rewards
UPDATE ONLY users u SET reward_score = COALESCE(
  (SELECT SUM(cr.contribution_score) FROM contributor_rewards cr WHERE cr.user_id = u.id), 0
);

COMMIT;
