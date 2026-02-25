-- Migration: Grant SELECT on grant-related tables to nexus_bot
-- Fixes: syncReviewerRole needs to query grants, role_grants, user_grants
-- for getUsersWithGrant() to resolve wiki.approve permissions
-- Database: nexus_users

BEGIN;

GRANT SELECT ON grants TO nexus_bot;
GRANT SELECT ON role_grants TO nexus_bot;
GRANT SELECT ON user_grants TO nexus_bot;

COMMIT;
