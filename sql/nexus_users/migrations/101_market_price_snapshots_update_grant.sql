-- Grant UPDATE on market_price_snapshots to nexus_users.
-- Finalization uses INSERT ... ON CONFLICT DO UPDATE, which requires UPDATE permission.
-- Migration 081 only granted SELECT + INSERT.

GRANT UPDATE ON market_price_snapshots TO nexus_users;
