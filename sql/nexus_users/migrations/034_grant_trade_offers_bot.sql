-- Grant nexus_bot UPDATE on trade_offers so it can adjust quantities
-- after a trade is marked as completed via /done.
GRANT UPDATE ON trade_offers TO nexus_bot;
