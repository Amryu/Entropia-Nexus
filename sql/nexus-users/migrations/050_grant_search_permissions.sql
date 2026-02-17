-- Grant the nexus role read access to users and societies tables
-- so the API search endpoint can include user profiles and societies in results.

GRANT SELECT ON users TO nexus;
GRANT SELECT ON societies TO nexus;
