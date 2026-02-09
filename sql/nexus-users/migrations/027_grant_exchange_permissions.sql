-- Migration: Grant permissions for exchange and preferences tables
-- The nexus-users app role needs access to tables created in migrations 025 and 026

-- trade_offers table
GRANT SELECT, INSERT, UPDATE, DELETE ON trade_offers TO "nexus-users";
GRANT USAGE ON SEQUENCE offers_id_seq TO "nexus-users";

-- user_items table
GRANT SELECT, INSERT, UPDATE, DELETE ON user_items TO "nexus-users";
GRANT USAGE ON SEQUENCE user_items_id_seq TO "nexus-users";

-- user_preferences table (no sequence, composite PK)
GRANT SELECT, INSERT, UPDATE, DELETE ON user_preferences TO "nexus-users";
