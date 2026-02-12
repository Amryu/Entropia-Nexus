-- Migration: Discord auction channel integration
-- Tracks which Discord message corresponds to each auction embed.
-- Grants bot read access to auction tables + write access for message ID.

-- Track Discord message ID for each auction's channel embed
ALTER TABLE auctions ADD COLUMN IF NOT EXISTS discord_message_id TEXT;

-- Bot needs to read auctions + audit log, and write only discord_message_id
GRANT SELECT ON auctions TO "nexus-bot";
GRANT UPDATE (discord_message_id) ON auctions TO "nexus-bot";
GRANT SELECT ON auction_audit_log TO "nexus-bot";
GRANT SELECT ON auction_bids TO "nexus-bot";
GRANT USAGE, SELECT ON SEQUENCE auction_audit_log_id_seq TO "nexus-bot";
