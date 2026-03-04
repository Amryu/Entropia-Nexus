-- Grant the Discord bot permissions to read reward rules and assign rewards on approval.

GRANT SELECT ON reward_rules TO nexus_bot;
GRANT SELECT, INSERT ON contributor_rewards TO nexus_bot;
GRANT USAGE, SELECT ON SEQUENCE contributor_rewards_id_seq TO nexus_bot;
