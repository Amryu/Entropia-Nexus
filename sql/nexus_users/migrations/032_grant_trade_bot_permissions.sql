-- Migration: Grant trade request table permissions to nexus_bot
-- The bot needs to read/update trade requests and read items for Discord thread management

GRANT SELECT, UPDATE ON trade_requests TO nexus_bot;
GRANT SELECT ON trade_request_items TO nexus_bot;
