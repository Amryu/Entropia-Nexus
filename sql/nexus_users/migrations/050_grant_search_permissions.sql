-- Grant read access to users and societies tables
-- so the API search endpoint can include user profiles and societies in results.
-- The API connects as 'nexus_bot' to the nexus_users database.

GRANT SELECT ON users TO nexus_bot;
GRANT SELECT ON societies TO nexus_bot;
