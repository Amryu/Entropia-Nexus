BEGIN;

-- Allow multiple rewards per change while still preventing duplicate assignment of the same rule.
ALTER TABLE contributor_rewards
  DROP CONSTRAINT IF EXISTS contributor_rewards_change_id_key;

ALTER TABLE contributor_rewards
  DROP CONSTRAINT IF EXISTS contributor_rewards_change_id_rule_id_key;

ALTER TABLE contributor_rewards
  ADD CONSTRAINT contributor_rewards_change_id_rule_id_key UNIQUE (change_id, rule_id);

COMMIT;
