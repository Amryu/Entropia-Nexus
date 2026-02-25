-- Grant read access to users and societies tables
-- so the API search endpoint can include user profiles and societies in results.
-- The API connects as 'nexus-bot' to the nexus_users database.

GRANT SELECT ON users TO "nexus-bot";
GRANT SELECT ON societies TO "nexus-bot";
