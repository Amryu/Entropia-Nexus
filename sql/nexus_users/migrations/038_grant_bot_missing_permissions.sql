-- Migration: Grant missing permissions to nexus-bot
-- Fixes:
--   1. item_prices: bot needs SELECT for computePriceSummaries
--   2. user_roles + roles: bot needs access for assignUserRole during verification
-- Database: nexus_users

BEGIN;

-- Bot needs to SELECT from item_prices to compute summaries
GRANT SELECT ON item_prices TO "nexus-bot";

-- Bot needs to read roles and insert into user_roles during user verification
GRANT SELECT ON roles TO "nexus-bot";
GRANT SELECT, INSERT ON user_roles TO "nexus-bot";

COMMIT;
